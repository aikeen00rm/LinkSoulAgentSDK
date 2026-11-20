from dataclasses import dataclass, field
from pathlib import Path
import os
from urllib.parse import urlsplit


@dataclass
class Settings:
    mode: str = "fixture"
    data_dir: Path = Path("data")
    gateway: str = field(default="", repr=False)
    app_id: str = field(default="", repr=False)
    app_key: str = field(default="", repr=False)
    app_secret: str = field(default="", repr=False)
    agent_id: str = ""
    fresh_seconds: int = 30
    presence_seconds: int = 60
    log_bytes: int = 1048576
    log_backups: int = 5
    reply_provider: str = "disabled"
    ollama_url: str = field(default="http://host.docker.internal:11434", repr=False)
    ollama_model: str = ""
    max_sessions: int = 100
    max_turns: int = 200
    max_text: int = 8192
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls, env=None):
        e = os.environ if env is None else env
        s = cls(mode=e.get("STUDIO_MODE", "fixture"),
                data_dir=Path(e.get("STUDIO_DATA_DIR", "data")),
                gateway=e.get("LINKSOUL_GATEWAY", ""), app_id=e.get("LINKSOUL_APP_ID", ""),
                app_key=e.get("LINKSOUL_APP_KEY", ""), app_secret=e.get("LINKSOUL_APP_SECRET", ""),
                agent_id=e.get("LINKSOUL_AGENT_ID", ""),
                reply_provider=e.get("STUDIO_REPLY_PROVIDER", "disabled"),
                ollama_url=e.get("OLLAMA_URL", "http://host.docker.internal:11434"),
                ollama_model=e.get("OLLAMA_MODEL", ""))
        for key, attr, low, high in [("STUDIO_FRESH_SECONDS", "fresh_seconds", 1, 3600),
                                      ("STUDIO_PRESENCE_SECONDS", "presence_seconds", 1, 3600),
                                      ("STUDIO_LOG_BYTES", "log_bytes", 1024, 10485760),
                                      ("STUDIO_LOG_BACKUPS", "log_backups", 1, 20),
                                      ("STUDIO_MAX_SESSIONS", "max_sessions", 5, 500),
                                      ("STUDIO_MAX_TURNS", "max_turns", 3, 200),
                                      ("STUDIO_MAX_TEXT", "max_text", 1024, 8192)]:
            try:
                value = int(e.get(key, getattr(s, attr)))
                if not low <= value <= high:
                    raise ValueError
                setattr(s, attr, value)
            except (ValueError, TypeError):
                s.errors.append(f"Set {key} to an integer between {low} and {high}.")
        s.validate()
        return s

    def validate(self):
        if self.mode not in {"fixture", "robot"}:
            self.errors.append("Set STUDIO_MODE to fixture or robot and recreate the service.")
        if self.mode == "robot":
            if not all((self.gateway, self.app_id, self.app_key, self.app_secret)):
                self.errors.append("Configure the gateway and application ID, key and secret on the server.")
            try:
                url = urlsplit(self.gateway)
                if url.scheme != "wss" or not url.hostname or url.username or url.password or url.query or url.fragment:
                    raise ValueError
            except ValueError:
                self.errors.append("Use the administrator-confirmed wss gateway URL without credentials or query parameters.")

    @property
    def secrets(self):
        return tuple(v for v in (self.app_id, self.app_key, self.app_secret, self.gateway) if v)
