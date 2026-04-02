from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


def _normalize_string_list(values: list[Any] | tuple[Any, ...] | None) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


@dataclass(slots=True)
class RoleBinding:
    """Explicit mapping from template role to executor capability."""

    role_id: str = ""
    agent_spec_id: str = ""
    capability_id: str = ""
    policy_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.role_id = str(self.role_id or "").strip()
        self.agent_spec_id = str(self.agent_spec_id or "").strip()
        self.capability_id = str(self.capability_id or "").strip()
        self.policy_refs = _normalize_string_list(self.policy_refs)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "RoleBinding":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))
