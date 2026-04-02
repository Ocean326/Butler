from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping

from ..bindings.role_binding import RoleBinding


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(slots=True)
class WorkflowSession:
    """One local collaboration session assembled for a workflow-backed node."""

    session_id: str = ""
    template_id: str = ""
    driver_kind: str = ""
    status: str = "pending"
    active_step: str = ""
    role_bindings: list[RoleBinding] = field(default_factory=list)
    shared_state_ref: str = ""
    artifact_registry_ref: str = ""
    blackboard_ref: str = ""
    collaboration_ref: str = ""
    event_log_ref: str = ""
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.session_id = str(self.session_id or "").strip()
        self.template_id = str(self.template_id or "").strip()
        self.driver_kind = str(self.driver_kind or "").strip()
        self.status = str(self.status or "pending").strip() or "pending"
        self.active_step = str(self.active_step or "").strip()
        self.role_bindings = [
            item if isinstance(item, RoleBinding) else RoleBinding.from_dict(item)
            for item in (self.role_bindings or [])
            if isinstance(item, (RoleBinding, Mapping))
        ]
        self.shared_state_ref = str(self.shared_state_ref or "").strip()
        self.artifact_registry_ref = str(self.artifact_registry_ref or "").strip()
        self.blackboard_ref = str(self.blackboard_ref or "").strip()
        self.collaboration_ref = str(self.collaboration_ref or "").strip()
        self.event_log_ref = str(self.event_log_ref or "").strip()
        self.created_at = str(self.created_at or _utc_now_iso()).strip()
        self.updated_at = str(self.updated_at or _utc_now_iso()).strip()
        self.metadata = dict(self.metadata or {})

    def touch(self) -> None:
        self.updated_at = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["role_bindings"] = [binding.to_dict() for binding in self.role_bindings]
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowSession":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        data["role_bindings"] = [
            item if isinstance(item, RoleBinding) else RoleBinding.from_dict(item)
            for item in (data.get("role_bindings") or [])
            if isinstance(item, (RoleBinding, Mapping))
        ]
        return cls(**data)
