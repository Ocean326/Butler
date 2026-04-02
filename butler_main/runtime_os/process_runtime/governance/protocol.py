from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4

from ..engine.contracts import normalize_failure_class, normalize_process_role, normalize_step_kind


_RUN_STATUSES: tuple[str, ...] = (
    "pending",
    "running",
    "blocked",
    "failed",
    "completed",
    "cancelled",
    "stale",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _normalize_run_status(value: str, *, default: str = "pending") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "pending").strip() or "pending"
    return normalized if normalized in _RUN_STATUSES else (str(default or "pending").strip() or "pending")


@dataclass(slots=True)
class StepReceipt:
    step_id: str
    workflow_id: str = ""
    worker_name: str = ""
    process_role: str = "executor"
    step_kind: str = "dispatch"
    status: str = "completed"
    summary: str = ""
    evidence: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    failure_class: str = ""
    next_action: str = ""
    handoff_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.process_role = normalize_process_role(self.process_role)
        self.step_kind = normalize_step_kind(self.step_kind)
        self.status = _normalize_run_status(self.status, default="completed")
        self.failure_class = normalize_failure_class(self.failure_class)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "StepReceipt":
        if not isinstance(payload, Mapping):
            return cls(step_id="")
        return cls(**dict(payload))


@dataclass(slots=True)
class HandoffReceipt:
    handoff_id: str = field(default_factory=lambda: _new_id("handoff"))
    workflow_id: str = ""
    source_step_id: str = ""
    target_step_id: str = ""
    producer: str = ""
    consumer: str = ""
    handoff_kind: str = "step_output"
    status: str = "completed"
    summary: str = ""
    artifacts: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    handoff_ready: bool = False
    next_action: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.status = _normalize_run_status(self.status, default="completed")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "HandoffReceipt":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class DecisionReceipt:
    decision_id: str = field(default_factory=lambda: _new_id("decision"))
    workflow_id: str = ""
    step_id: str = ""
    producer: str = ""
    status: str = "completed"
    summary: str = ""
    decision: str = ""
    decision_reason: str = ""
    retryable: bool = False
    next_action: str = ""
    resume_from: str = ""
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.status = _normalize_run_status(self.status, default="completed")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "DecisionReceipt":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


__all__ = ["DecisionReceipt", "HandoffReceipt", "StepReceipt"]
