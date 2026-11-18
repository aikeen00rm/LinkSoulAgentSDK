import json
import logging
import platform
import queue
import threading
from collections import deque
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version
from time import monotonic
from uuid import uuid4

from linksoul_studio import __version__
from linksoul_studio.diagnostics.store import Diagnostics, SafeSDKHandler
from linksoul_studio.events.model import Event, utc
from linksoul_studio.sdk.fixture import FixtureAdapter
from linksoul_studio.sdk.robot import RobotAdapter


LABELS = {
    "gateway_connecting": "Connecting to gateway",
    "gateway_connected": "Gateway connection opened",
    "gateway_disconnected": "Gateway disconnected · robot presence is now unknown",
    "gateway_error": "Gateway connection failed · check region, credentials and network",
    "robot_online": "Selected robot reported online",
    "robot_offline": "Selected robot reported offline",
    "robot_state": "Robot state callback received · payload not recorded",
    "input": "New ASR input received · conversation text not recorded",
    "response_attempted": "Test-agent error response attempted · delivery and execution unconfirmed",
    "adapter_error": "SDK adapter error · check test-agent setup and network; diagnostics saved",
}


class Collector:
    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.RLock()
        self.queue = queue.Queue(maxsize=512)
        self.activity = deque(maxlen=120)
        self.window = []
        self.check_started = None
        self.last_report = None
        self.sequence = 0
        self.gateway = "Unknown"
        self.presence = "Unknown"
        self.presence_mono = None
        self.last_input = None
        self.connected_sequence = None
        self.errors = settings.validate()
        self.adapter_error = False
        self.dropped = 0
        self.probe_error = None
        self.diag = Diagnostics(settings)
        self.adapter = RobotAdapter(settings, self.emit) if settings.mode == "robot" else FixtureAdapter(self.emit)
        self.stopping = False
        self.worker = threading.Thread(target=self._consume, daemon=True, name="studio-collector")
        self.handler = SafeSDKHandler(self.diag, self.emit)
        self.logger_state = []
        self.report_error = None
        self.versions = {"build": __version__, "python": platform.python_version()}
        for name in ("linksoul-agentsdk", "fastapi", "uvicorn"):
            try:
                self.versions[name] = version(name)
            except PackageNotFoundError:
                self.versions[name] = "Unavailable"

    def start(self):
        # Suppress SDK payload logging at its namespace before initialize.
        for name in ("linksoul_agentsdk", "websocket"):
            logger = logging.getLogger(name)
            self.logger_state.append((logger, logger.handlers[:], logger.propagate, logger.level))
            logger.handlers = [self.handler]
            logger.propagate = False
            logger.setLevel(logging.INFO)
        self.worker.start()
        if self.errors:
            self.diag.write("app", "configuration_invalid", mode=self.settings.mode, issues=self.errors)
        if not self.errors:
            try:
                self.adapter.start()
            except Exception:
                self.emit("adapter_error")
                self.errors.append("Adapter could not start. Confirm SDK 1.5.0a1 and test-agent configuration, then restart.")

    def emit(self, kind, agent_id=None, event_id=None, item_id=None):
        if self.stopping:
            return
        if self.settings.mode == "robot" and agent_id and agent_id != self.settings.agent_id:
            return
        if kind not in LABELS:
            return
        source = "fixture" if self.settings.mode == "fixture" else "sdk"
        event = Event(self.settings.mode, self.adapter.run_id, kind, source,
                      direction="outbound" if kind == "response_attempted" else "inbound",
                      agent_id=agent_id, event_id=event_id, item_id=item_id)
        try:
            self.queue.put_nowait(event)
        except queue.Full:
            with self.lock:
                self.dropped += 1

    def _consume(self):
        while True:
            event = self.queue.get()
            try:
                if event is None:
                    return
                with self.lock:
                    self.sequence += 1
                    event.sequence = self.sequence
                    self.activity.append(event)
                    if self.check_started:
                        if len(self.window) < 2048:
                            self.window.append(event)
                        else:
                            self.dropped += 1
                    kind = event.kind
                    if kind == "gateway_connecting":
                        self.gateway = "Connecting"
                    elif kind == "gateway_connected":
                        if self.gateway != "Connected":
                            self.connected_sequence = event.sequence
                            self.presence = "Unknown"
                        self.gateway = "Connected"
                    elif kind in {"gateway_disconnected", "gateway_error"}:
                        self.gateway = "Disconnected" if kind == "gateway_disconnected" else "Error"
                        self.presence = "Unknown"
                    elif kind == "robot_online":
                        self.presence, self.presence_mono = "Online", event.collector_mono
                    elif kind == "robot_offline":
                        self.presence, self.presence_mono = "Offline", event.collector_mono
                    elif kind == "robot_state":
                        self.presence_mono = event.collector_mono
                    elif kind == "input":
                        self.last_input = event
                        self.presence_mono = event.collector_mono
                    elif kind == "adapter_error":
                        self.adapter_error = True
                self.diag.write("sdk", "connection_event", **event.public())
            finally:
                self.queue.task_done()

    def flush(self):
        self.queue.join()

    def begin(self):
        self.flush()
        with self.lock:
            self.check_started = utc()
            self.window = []
            self.last_report = None
            self.check_baseline_dropped = self.dropped
        self.diag.write("app", "verification_started", mode=self.settings.mode)

    def snapshot(self):
        with self.lock:
            age = monotonic() - self.last_input.collector_mono if self.last_input else None
            after_connect = (self.last_input and self.connected_sequence is not None
                             and self.last_input.sequence > self.connected_sequence)
            fresh = bool(age is not None and age < self.settings.stale_seconds
                         and after_connect and self.gateway == "Connected" and self.presence == "Online")
            presence = self.presence
            if presence == "Online" and (self.gateway != "Connected" or self.presence_mono is None
                    or monotonic() - self.presence_mono > self.settings.presence_seconds):
                presence = "Unknown / stale"
                fresh = False
            problems = list(self.errors)
            if self.diag.error: problems.append(self.diag.error)
            if self.probe_error: problems.append(self.probe_error)
            if self.report_error: problems.append(self.report_error)
            if self.adapter_error: problems.append(LABELS["adapter_error"])
            if self.dropped: problems.append("Evidence queue overflow. Some callbacks were lost; restart and repeat verification.")
            return {
                "mode": self.settings.mode, "versions": self.versions,
                "gateway": self.gateway, "presence": presence,
                "freshness": "Fresh" if fresh else "Waiting for new input" if not self.last_input or not after_connect else "Stale / unavailable",
                "input_utc": self.last_input.collector_utc if self.last_input else None,
                "input_age": round(age, 1) if age is not None else None,
                "stale_seconds": self.settings.stale_seconds,
                "problems": problems, "diagnostics": "Saved" if not self.diag.error else "Write failed",
                "activity": [{**e.public(), "summary": LABELS[e.kind],
                              "evidence": "Fixture simulation" if e.mode == "fixture" else "Robot reported" if e.kind.startswith("robot_") else "SDK captured"}
                             for e in reversed(self.activity)],
                "report": self.last_report, "checking": bool(self.check_started),
            }

    def report(self, scenario="manual"):
        self.flush()
        self.diag.write("app", "verification_storage_probe", mode=self.settings.mode)
        with self.lock:
            events = list(self.window)
            # Ordered evidence is required, all within this check and one connection run.
            expected = ["gateway_connected", "robot_online", "input", "gateway_disconnected",
                        "gateway_connected", "robot_online", "input"]
            matched = []
            for e in events:
                if len(matched) < len(expected) and e.kind == expected[len(matched)]:
                    matched.append(e)
            snap = self.snapshot()
            healthy = not snap["problems"]
            checks = [
                {"label": "Gateway connected", "passed": len(matched) >= 1},
                {"label": "Robot online and initial input", "passed": len(matched) >= 3},
                {"label": "Disconnect and gateway recovery", "passed": len(matched) >= 5},
                {"label": "Robot online and fresh input after reconnect", "passed": len(matched) == 7 and snap["freshness"] == "Fresh"},
                {"label": "Diagnostics writable; no configuration, adapter or evidence errors", "passed": healthy},
            ]
            for c in checks:
                c["result"] = "Passed" if c.pop("passed") else "Failed"
            report = {"id": str(uuid4()), "mode": self.settings.mode, "scenario": scenario,
                      "started_utc": self.check_started, "saved_utc": utc(), "versions": self.versions,
                      "result": "Passed" if all(c["result"] == "Passed" for c in checks) else "Failed",
                      "checks": checks, "evidence": [e.public() for e in matched],
                      "problems": snap["problems"],
                      "limitations": ["Fixture evidence is not hardware evidence"] if self.settings.mode == "fixture" else ["ASR test agent only; physical robot identity and firmware require operator confirmation"],
                      "restart_durability": "Pending separate service restart check"}
            try:
                directory = self.settings.data_dir / "verification" / self.settings.mode
                directory.mkdir(parents=True, exist_ok=True)
                target = directory / (report["id"] + ".json")
                # Atomic replacement avoids partially written reports after interruption.
                temp = target.with_suffix(".tmp")
                temp.write_text(json.dumps(report, indent=2), encoding="utf-8")
                temp.replace(target)
                report["download"] = f"/api/reports/{report['id']}"
                self.diag.write("app", "verification_saved", mode=self.settings.mode,
                                report_id=report["id"], result=report["result"])
            except OSError:
                self.report_error = "Verification report could not be saved. Check data/verification permissions and free space."
                report["result"] = "Failed"
                report["save_error"] = self.report_error
            self.last_report = report
            self.check_started = None
            return report

    def probe(self, kind):
        # Exercise real validation / storage code in a bounded isolated fixture directory.
        if kind == "invalid-config":
            probe = replace(self.settings, mode="robot", app_key="", app_secret="", agent_id="")
            issues = probe.validate()
            self.probe_error = "Fixture configuration check: " + " ".join(issues)
        else:
            from tempfile import TemporaryDirectory
            from pathlib import Path
            with TemporaryDirectory() as td:
                blocked = Path(td) / "blocked"
                blocked.write_text("fixture", encoding="utf-8")
                diagnostics = Diagnostics(replace(self.settings, data_dir=blocked))
                self.probe_error = "Fixture storage check: " + (diagnostics.error or "Unexpected success")
                diagnostics.close()
        self.diag.write("app", "fixture_probe_failed", mode="fixture", issue=self.probe_error)

    def stop(self):
        try:
            self.adapter.stop()
        except Exception:
            self.diag.write("app", "adapter_release_failed", mode=self.settings.mode)
        self.stopping = True
        self.flush()
        self.queue.put(None)
        self.worker.join(timeout=5)
        self.diag.write("app", "service_stop", mode=self.settings.mode)
        self.diag.close()
        for logger, handlers, propagate, level in self.logger_state:
            logger.handlers, logger.propagate = handlers, propagate
            logger.setLevel(level)
