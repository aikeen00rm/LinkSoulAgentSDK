"""Server-only settings. Invalid setup leaves the console available for recovery."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


@dataclass
class Settings:
    mode: str = "fixture"
    data_dir: Path = Path("data")
    gateway: str = ""
    app_id: str = field(default="", repr=False)
    app_key: str = field(default="", repr=False)
    app_secret: str = field(default="", repr=False)
    agent_id: str = field(default="", repr=False)
    stale_seconds: float = 30
    presence_seconds: float = 60
    log_bytes: int = 1_048_576
    log_backups: int = 5
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls):
        s = cls(mode=os.getenv("STUDIO_MODE", "fixture"),
                data_dir=Path(os.getenv("STUDIO_DATA_DIR", "data")),
                gateway=os.getenv("LINKSOUL_GATEWAY", ""),
                app_id=os.getenv("LINKSOUL_APP_ID", ""),
                app_key=os.getenv("LINKSOUL_APP_KEY", ""),
                app_secret=os.getenv("LINKSOUL_APP_SECRET", ""),
                agent_id=os.getenv("LINKSOUL_AGENT_ID", ""))
        for key, env, cast, low, high in [
            ("stale_seconds", "STUDIO_STALE_SECONDS", float, 1, 3600),
            ("presence_seconds", "STUDIO_PRESENCE_SECONDS", float, 1, 3600),
            ("log_bytes", "STUDIO_LOG_BYTES", int, 1024, 10_485_760),
            ("log_backups", "STUDIO_LOG_BACKUPS", int, 1, 20),
        ]:
            try:
                value = cast(os.getenv(env, str(getattr(s, key))))
                if not low <= value <= high:
                    raise ValueError
                setattr(s, key, value)
            except ValueError:
                s.errors.append(f"Set {env} between {low} and {high}, then restart.")
        return s

    def validate(self):
        errors = list(self.errors)
        if self.mode not in {"fixture", "robot"}:
            errors.append("Set STUDIO_MODE to fixture or robot, then restart.")
        if self.mode == "robot":
            if not all((self.app_id, self.app_key, self.app_secret)):
                errors.append("Set LINKSOUL_APP_ID, LINKSOUL_APP_KEY and LINKSOUL_APP_SECRET credentials on the server, then restart.")
            try:
                u = urlsplit(self.gateway)
                if u.scheme != "wss" or not u.hostname or u.username or u.password or u.query or u.fragment:
                    raise ValueError
            except ValueError:
                errors.append("Set LINKSOUL_GATEWAY to your region's secure wss endpoint without credentials or query parameters.")
        return errors

    @property
    def secrets(self):
        return [v for v in (self.app_id, self.app_key, self.app_secret) if v]
