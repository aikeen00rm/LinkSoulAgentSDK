from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from time import monotonic
from uuid import uuid4


def utc():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Event:
    mode: str
    connection_run_id: str
    kind: str
    source: str
    sequence: int = 0
    record_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: int = 1
    direction: str = "inbound"
    collector_utc: str = field(default_factory=utc)
    collector_mono: float = field(default_factory=monotonic)
    agent_id: str | None = None
    event_id: str | None = None
    item_id: str | None = None

    def public(self):
        # Identifiers are kept for correlation in memory, never exposed as arbitrary payloads.
        return {k: v for k, v in asdict(self).items()
                if k not in {"collector_mono", "agent_id", "event_id", "item_id"}}
