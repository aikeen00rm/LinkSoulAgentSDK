"""M1 metadata only: bounded diagnostics and atomic, manually retained reports."""
import fcntl
import json
import os
import re
from logging.handlers import RotatingFileHandler
import logging
from pathlib import Path


class Store:
    def __init__(self, settings):
        self.root = settings.data_dir
        self.settings = settings
        self.lock_file = None
        self.handlers = {}
        self.error = None

    def open(self):
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.lock_file = (self.root / ".owner.lock").open("a")
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            (self.root / "logs").mkdir(exist_ok=True, mode=0o700)
            for mode in ("fixture", "robot"):
                (self.root / "verification" / mode).mkdir(parents=True, exist_ok=True, mode=0o700)
            for channel in ("app", "sdk"):
                handler = RotatingFileHandler(self.root / "logs" / f"{channel}.jsonl",
                                              maxBytes=self.settings.log_bytes,
                                              backupCount=self.settings.log_backups, encoding="utf-8")
                # Standard logging handlers swallow write failures. Raise them for visible health.
                handler.handleError = self._raise_write_error
                self.handlers[channel] = handler
            self.write("app", {"kind": "service_started", "mode": self.settings.mode})
        except BlockingIOError:
            self.error = "This data directory is already owned by another service. Run one worker and stop the other owner."
            self.close()
        except OSError:
            self.error = "Persistent storage is unavailable. Check the data mount, free space and owner permissions."
            self.close()

    @staticmethod
    def _raise_write_error(record):
        raise OSError("diagnostic write failed")

    def encode(self, obj):
        # Callers pass only allowlisted metadata; this is additional secret redaction.
        value = json.dumps(obj, ensure_ascii=True)
        for secret in self.settings.secrets:
            value = value.replace(json.dumps(secret)[1:-1], "[redacted]")
        return value

    def write(self, channel, metadata):
        if self.error or channel not in self.handlers:
            return False
        try:
            record = logging.LogRecord("studio", logging.INFO, "", 0, self.encode(metadata), (), None)
            self.handlers[channel].handle(record)
            return True
        except OSError:
            self.error = "Diagnostics could not be saved. Check disk space and permissions, then restart the service."
            return False

    def save(self, report):
        if self.error:
            return False
        parent = self.root / "verification" / report["mode"]
        target = parent / f'{report["id"]}.json'
        temp = target.with_suffix(".tmp")
        try:
            with temp.open("w", encoding="utf-8") as out:
                out.write(self.encode(report))
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, target)
            directory_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return True
        except OSError:
            self.error = "Verification report could not be saved. Check storage, then restart; this result is not durable."
            return False

    def reports(self, mode):
        if mode not in {"fixture", "robot"}:
            return []
        result = []
        try:
            paths = sorted((self.root / "verification" / mode).glob("*.json"),
                           key=lambda p: p.stat().st_mtime, reverse=True)[:100]
            for path in paths:
                try:
                    r = json.loads(path.read_text())
                    result.append({k: r[k] for k in ("id", "mode", "scenario", "result", "ended_at")})
                except (OSError, ValueError, KeyError):
                    self.error = "A saved report is unreadable. Restore it from backup; other reports remain available."
        except OSError:
            self.error = "Saved reports cannot be listed. Check storage permissions."
        return result

    def read_report(self, mode, report_id):
        if mode not in {"fixture", "robot"} or not re.fullmatch(r"[0-9a-f]{32}", report_id):
            raise FileNotFoundError
        return json.loads((self.root / "verification" / mode / f"{report_id}.json").read_text())

    def close(self):
        for handler in self.handlers.values():
            handler.close()
        self.handlers.clear()
        if self.lock_file:
            self.lock_file.close()
            self.lock_file = None
