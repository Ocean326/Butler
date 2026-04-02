from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Mapping


def _normalize_mapping_list(values: list[Any] | tuple[Any, ...] | None) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        return []
    normalized: list[dict[str, Any]] = []
    for item in values:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
    return normalized


@dataclass(slots=True)
class WorkflowTemplate:
    """Static template for one local multi-agent collaboration workflow."""

    template_id: str = ""
    kind: str = "generic"
    roles: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    entry_contract: dict[str, Any] = field(default_factory=dict)
    exit_contract: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.template_id = str(self.template_id or "").strip()
        self.kind = str(self.kind or "generic").strip() or "generic"
        self.roles = _normalize_mapping_list(self.roles)
        self.steps = _normalize_mapping_list(self.steps)
        self.entry_contract = dict(self.entry_contract or {})
        self.exit_contract = dict(self.exit_contract or {})
        self.defaults = dict(self.defaults or {})
        self.metadata = dict(self.metadata or {})

    def first_step_id(self) -> str:
        for step in self.steps:
            step_id = str(step.get("step_id") or step.get("id") or "").strip()
            if step_id:
                return step_id
        return ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowTemplate":
        if not isinstance(payload, Mapping):
            return cls()
        allowed = {item.name for item in fields(cls)}
        filtered = {key: value for key, value in dict(payload).items() if key in allowed}
        return cls(**filtered)
