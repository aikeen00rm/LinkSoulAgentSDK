"""Bounded JSONL diagnostics; SDK free-text is deliberately never formatted."""
import json
import logging
import re
import threading
from logging.handlers import RotatingFileHandler

from linksoul_studio.events.model import utc


def redact(value, secrets=()):
    if isinstance(value, dict):
        return {k: ("[redacted]" if re.search(r"secret|token|authorization|signature|app.?key|password|text|audio|body|histories|param", k, re.I)
                    else redact(v, secrets)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in sorted(secrets, key=len, reverse=True):
            value = value.replace(secret, "[redacted]")
        return re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[redacted]", value)
    return value


class StrictRotation(RotatingFileHandler):
    def handleError(self, record):
        raise OSError("diagnostic write failed")


class Diagnostics:
    def __init__(self, settings):
        self.settings = settings
        self.error = None
        self.handlers = {}
        self.lock = threading.RLock()
        try:
            path = settings.data_dir / "logs"
            path.mkdir(parents=True, exist_ok=True)
            for name in ("app", "sdk"):
                h = StrictRotation(path / f"{name}.jsonl", maxBytes=settings.log_bytes,
                                   backupCount=settings.log_backups, encoding="utf-8")
                h.setFormatter(logging.Formatter("%(message)s"))
                self.handlers[name] = h
            self.write("app", "service_start", mode=settings.mode)
        except OSError:
            self.error = "Diagnostics cannot be saved. Make the data/logs directory writable and restart."

    def write(self, channel, diagnostic, **fields):
        with self.lock:
            if channel not in self.handlers:
                return False
            try:
                payload = redact({"utc": utc(), "diagnostic": diagnostic, **fields}, self.settings.secrets)
                self.handlers[channel].handle(logging.makeLogRecord({
                    "msg": json.dumps(payload, ensure_ascii=False), "levelno": logging.INFO}))
                return True
            except OSError:
                self.error = "Diagnostics cannot be saved. Check free space and data/logs permissions, then restart."
                return False

    def close(self):
        for h in self.handlers.values():
            h.close()


class SafeSDKHandler(logging.Handler):
    def __init__(self, diagnostics, emit):
        super().__init__()
        self.diagnostics, self.emit_event = diagnostics, emit

    def emit(self, record):
        # SDK logs include entire histories/text, URLs, auth and exception strings.
        # Keep only level/category; do not call getMessage() or serialize exc_info.
        self.diagnostics.write("sdk", "sdk_diagnostic", level=record.levelname,
                               category="websocket" if record.name.startswith("websocket") else "sdk")
        if record.levelno >= logging.ERROR:
            self.emit_event("adapter_error")
