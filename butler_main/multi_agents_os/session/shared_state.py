from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(slots=True)
class SharedState:
    """Minimal shared state for one collaboration session."""

    session_id: str = ""
    state: dict[str, Any] = field(default_factory=dict)
    state_version: int = 1
    last_updated_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.session_id = str(self.session_id or "").strip()
        self.state = dict(self.state or {})
        self.state_version = max(1, int(self.state_version or 1))
        self.last_updated_at = str(self.last_updated_at or _utc_now_iso()).strip()

    def patch(self, payload: Mapping[str, Any] | None) -> bool:
        if not isinstance(payload, Mapping):
            return False
        delta = dict(payload)
        changed = any(self.state.get(key) != value for key, value in delta.items())
        if not changed:
            return False
        self.state.update(delta)
        self.state_version += 1
        self.last_updated_at = _utc_now_iso()
        return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "SharedState":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))
