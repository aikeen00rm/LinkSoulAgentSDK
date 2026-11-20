import hashlib
import importlib.metadata
import platform
import queue
import re
import tempfile
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import Settings
from .storage import Store
from .recorder import Recorder


def utc():
    return datetime.now(timezone.utc).isoformat()


STEPS = ["connected", "online", "input", "disconnected", "connected", "online", "input"]
LABELS = ["Gateway connected", "Selected agent online", "First input received", "Gateway disconnected",
          "Gateway reconnected", "Selected agent online again", "New input after reconnect"]
MESSAGES = {
    "connected": "Gateway connection observed", "disconnected": "Gateway disconnected; input freshness reset",
    "online": "Selected agent reported online", "offline": "Selected agent reported offline",
    "input": "ASR input arrived; content not recorded in M1", "response_attempted": "Inference-unavailable reply attempted; delivery unconfirmed",
    "ignored": "Unrelated or out-of-order agent event excluded", "conflict": "Multiple agents found; configure the intended agent filter",
    "transport_error": "Connection failed; check gateway, credentials, network and certificate trust",
    "sdk_warning": "SDK warning captured as metadata only", "sdk_error": "SDK error; inspect setup and connection evidence",
    "configuration_failure": "Configuration validation failed in isolated fixture check",
    "storage_failure": "A real write to an isolated unusable path failed as expected",
}


class Service:
    def __init__(self, settings, clock=time.monotonic, queue_size=512):
        self.settings, self.clock = settings, clock
        self.store = Store(settings)
        self.lock = threading.RLock()
        self.actions = threading.Lock()
        self.queue = queue.Queue(queue_size)
        self.stop_event = threading.Event()
        self.thread = None
        self.run_id = uuid.uuid4().hex
        self.seq = 0
        self.events = deque(maxlen=120)
        self.dropped = 0
        self.connected = False
        self.online = False
        self.selected = settings.agent_id or None
        self.selection = "configured" if settings.agent_id else "awaiting online discovery"
        self.presence_at = self.input_at = None
        self.incident = None
        self.check = None
        self.last_report = None
        self.adapter = None
        self.recorder = Recorder(self)
        self.versions = {"studio": __version__, "python": platform.python_version(),
                         "sdk": importlib.metadata.version("linksoul-agentsdk")}

    def start(self):
        self.store.open()
        self.recorder.start()
        self.thread = threading.Thread(target=self._consume, name="studio-collector", daemon=True)
        self.thread.start()

    def emit(self, kind, agent_id=None, event_id=None, source=None):
        if kind not in MESSAGES or self.stop_event.is_set():
            return
        item = (kind, agent_id, event_id, source, self.clock(), utc())
        try:
            self.queue.put_nowait(item)
        except queue.Full:
            with self.lock:
                self.dropped += 1
                self.incident = "Capture queue overflow. Evidence was lost; restart and repeat verification."

    def _identifier(self, value):
        if value is None:
            return None
        value = str(value)
        if any(secret in value for secret in self.settings.secrets) or not re.fullmatch(r"[\w.:-]{1,128}", value):
            return "redacted-" + hashlib.sha256(value.encode()).hexdigest()[:12]
        return value

    def _consume(self):
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                with self.lock:
                    self._apply(*item)
            except Exception:
                with self.lock:
                    self.incident = "The event collector failed. Restart and repeat verification; evidence is incomplete."
                    if self.check:
                        self.check["errors"] += 1
            finally:
                self.queue.task_done()

    def drain(self):
        self.queue.join()

    def _apply(self, kind, agent, event, source, monotonic, timestamp):
        original = kind
        if kind == "connected":
            self.connected, self.online = True, False
            self.input_at = self.presence_at = None
        elif kind in {"disconnected", "transport_error"}:
            self.connected = self.online = False
            self.input_at = self.presence_at = None
        elif kind in {"online", "offline", "input", "response_attempted"}:
            if not self.connected or not agent:
                kind = "ignored"
            elif kind == "online" and not self.selected:
                self.selected, self.selection = agent, "first online callback"
            if kind != "ignored" and agent != self.selected:
                kind = "conflict" if original == "online" and not self.settings.agent_id else "ignored"
            if kind == "online":
                self.online, self.presence_at = True, monotonic
            elif kind == "offline":
                self.online = False
                self.input_at = self.presence_at = None
            elif kind == "input":
                if not self.online:
                    kind = "ignored"
                else:
                    self.input_at = self.presence_at = monotonic
        if kind in {"conflict", "transport_error", "configuration_failure", "storage_failure", "sdk_error"}:
            self.incident = MESSAGES[kind]
            if self.check:
                self.check["errors"] += 1
        self.seq += 1
        record = {"id": uuid.uuid4().hex, "schema_version": 1, "run_id": self.run_id, "sequence": self.seq,
                  "mode": self.settings.mode, "kind": kind, "timestamp": timestamp,
                  "source": source or ("SDK captured" if self.settings.mode == "robot" else "Fixture simulation"),
                  "direction": "outbound" if kind == "response_attempted" else "inbound",
                  "agent_id": self._identifier(agent), "event_id": self._identifier(event), "summary": MESSAGES[kind]}
        self.events.append(record)
        self.store.write("sdk" if kind.startswith("sdk_") else "app", record)
        if self.check:
            c = self.check
            if len(c["evidence"]) >= 2048:
                c["errors"] += 1
            else:
                c["evidence"].append(record)
            p = c["progress"]
            if p < len(STEPS) and kind == STEPS[p]:
                # Repeated delivery of the same request must not establish fresh post-reconnect input.
                if kind != "input" or (event and event not in c["input_ids"]):
                    c["progress"] += 1
                    if kind == "input" and event:
                        c["input_ids"].append(event)
            # Lost presence/connection after the final input invalidates current readiness.

    def start_check(self, scenario="manual"):
        self.drain()
        with self.lock:
            self.check = {"id": uuid.uuid4().hex, "scenario": scenario, "started_at": utc(), "progress": 0,
                          "errors": 0, "evidence": [], "input_ids": [], "dropped_start": self.dropped}
            # Incidents remain sticky until an explicit recovery/reset; a new check cannot hide them.

    def _fresh(self):
        return self.connected and self.online and self.input_at is not None and self.clock() - self.input_at <= self.settings.fresh_seconds

    def finish_check(self):
        self.drain()
        with self.lock:
            if not self.check:
                raise ValueError("Start a verification check first.")
            c = self.check
            passed = (c["progress"] == len(STEPS) and self._fresh() and not c["errors"] and not self.dropped
                      and not self.incident and not self.store.error and not self.settings.errors)
            report = {"id": c["id"], "schema_version": 1, "milestone": "M1", "mode": self.settings.mode,
                      "scenario": c["scenario"], "started_at": c["started_at"], "ended_at": utc(),
                      "result": "Passed" if passed else "Failed", "versions": self.versions,
                      "agent_id": self._identifier(self.selected), "selection": self.selection,
                      "physical_association": "Simulated" if self.settings.mode == "fixture" else "Operator verification pending",
                      "steps": [{"label": label, "observed": i < c["progress"]} for i, label in enumerate(LABELS)],
                      "evidence": c["evidence"], "dropped": self.dropped, "saved": True,
                      "reason": "All seven ordered connection steps observed with fresh input." if passed else
                                self.incident or self.store.error or "Complete all steps with new input after reconnect; check configuration and freshness.",
                      "limitations": ["Fixture results are not hardware acceptance." if self.settings.mode == "fixture" else
                                      "Physical device association, firmware and real response execution require separate confirmation.",
                                      "M1 captures metadata only; no conversation, audio, image or video recording.",
                                      "A response attempt is not delivery or execution confirmation."]}
            saved = self.store.save(report)
            if not saved:
                report.update(saved=False, result="Failed", reason=self.store.error)
            self.last_report = report
            self.check = None
            return report

    def reset_fixture(self):
        if self.settings.mode != "fixture":
            raise ValueError("Simulation is available in fixture mode only.")
        self.drain()
        with self.lock:
            self.connected = self.online = False
            self.presence_at = self.input_at = None
            self.selected = self.settings.agent_id or None
            self.selection = "configured" if self.selected else "awaiting online discovery"
            self.incident = None
            self.check = None

    def run_fixture(self, scenario):
        if scenario not in {"recovery", "no-input", "configuration", "storage"}:
            raise ValueError("Unknown fixture scenario.")
        self.reset_fixture()
        self.start_check(scenario)
        if scenario == "configuration":
            probe = Settings.from_env({"STUDIO_MODE": "robot"})
            if probe.errors:
                self.emit("configuration_failure", source="Application measured")
        elif scenario == "storage":
            # A real failing filesystem write, isolated from the persistent report store.
            with tempfile.TemporaryDirectory() as folder:
                blocker = Path(folder) / "file-not-directory"
                blocker.write_text("fixture")
                probe = Store(Settings(data_dir=blocker / "child"))
                probe.open()
                if probe.error:
                    self.emit("storage_failure", source="Application measured")
                probe.close()
        else:
            agent = self.settings.agent_id or "fixture-a3"
            for kind in STEPS if scenario == "recovery" else STEPS[:-1]:
                self.emit(kind, agent if kind in {"online", "input"} else None,
                          uuid.uuid4().hex if kind == "input" else None)
        return self.finish_check()

    def snapshot(self):
        with self.lock:
            now = self.clock()
            presence_age = None if self.presence_at is None else max(0, now - self.presence_at)
            input_age = None if self.input_at is None else max(0, now - self.input_at)
            reports = self.store.reports(self.settings.mode)
            return {"mode": self.settings.mode, "versions": self.versions, "run_id": self.run_id,
                    "gateway": "Connected" if self.connected else "Disconnected",
                    "presence": "Unknown" if not self.connected else ("Stale" if self.online and presence_age is not None and presence_age > self.settings.presence_seconds else "Online reported" if self.online else "Awaiting online"),
                    "input": "Fresh" if self._fresh() else "Stale" if input_age is not None else "Waiting for input",
                    "presence_age": None if presence_age is None else round(presence_age, 1),
                    "input_age": None if input_age is None else round(input_age, 1),
                    "agent_id": self._identifier(self.selected), "selection": self.selection,
                    "physical_association": "Simulated device" if self.settings.mode == "fixture" else "Not independently verified",
                    "errors": self.settings.errors, "incident": self.incident, "storage_error": self.store.error,
                    "storage": "Unavailable" if self.store.error else "Ready", "dropped": self.dropped,
                    "events": list(reversed(self.events)), "reports": reports,
                    "check": None if not self.check else {"steps": [{"label": label, "observed": i < self.check["progress"]} for i, label in enumerate(LABELS)], "started_at": self.check["started_at"]},
                    "last_report": None if not self.last_report else {k: self.last_report[k] for k in ("id", "mode", "result", "reason", "saved", "steps")},
                    "adapter_running": self.adapter is not None,
                    "interaction": "M2 text replies" if self.adapter and self.adapter.conversations else "M1 connection test"}

    def connect_robot(self, conversations=False):
        if self.settings.mode != "robot" or self.settings.errors or self.store.error:
            raise ValueError("Robot mode needs valid server configuration and writable storage.")
        if self.adapter:
            raise ValueError("Disconnect the current test connection first.")
        from .robot import RobotAdapter
        self.incident = None
        self.adapter = RobotAdapter(self, conversations=conversations)
        try:
            self.adapter.start()
        except Exception:
            self.adapter.stop()
            self.adapter = None
            self.emit("transport_error", source="Application measured")

    def disconnect_robot(self):
        if self.adapter:
            self.adapter.stop()
            self.adapter = None
            self.emit("disconnected", source="Application measured")

    def close(self):
        self.disconnect_robot()
        self.recorder.close()
        self.drain()
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
        self.store.write("app", {"kind": "service_stopped", "mode": self.settings.mode, "timestamp": utc()})
        self.store.close()
