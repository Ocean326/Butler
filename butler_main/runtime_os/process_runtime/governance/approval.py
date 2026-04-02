from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


APPROVAL_TYPES: tuple[str, ...] = (
    "human_gate",
    "code_change",
    "runtime_restart",
    "tool_elevation",
)

APPROVAL_STATUSES: tuple[str, ...] = (
    "pending",
    "approved",
    "rejected",
    "cancelled",
)


def normalize_approval_type(value: str, *, default: str = "human_gate") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "human_gate").strip() or "human_gate"
    return normalized if normalized in APPROVAL_TYPES else (str(default or "human_gate").strip() or "human_gate")


def normalize_approval_status(value: str, *, default: str = "pending") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "pending").strip() or "pending"
    return normalized if normalized in APPROVAL_STATUSES else (str(default or "pending").strip() or "pending")


@dataclass(slots=True)
class ApprovalTicket:
    ticket_id: str = field(default_factory=lambda: _new_id("approval"))
    source_run_id: str = ""
    source_step_id: str = ""
    approval_type: str = "human_gate"
    risk_level: str = "medium"
    requested_action: str = ""
    reason: str = ""
    target_refs: list[str] = field(default_factory=list)
    verification_plan: list[str] = field(default_factory=list)
    rollback_plan: list[str] = field(default_factory=list)
    status: str = "pending"
    created_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.approval_type = normalize_approval_type(self.approval_type)
        self.status = normalize_approval_status(self.status)


__all__ = [
    "APPROVAL_STATUSES",
    "APPROVAL_TYPES",
    "ApprovalTicket",
    "normalize_approval_status",
    "normalize_approval_type",
]
