from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FlowSummaryDTO:
    flow_id: str = ""
    workflow_kind: str = ""
    effective_status: str = ""
    effective_phase: str = ""
    attempt_count: int = 0
    max_attempts: int = 0
    max_phase_attempts: int = 0
    max_runtime_seconds: int = 0
    runtime_elapsed_seconds: int = 0
    goal: str = ""
    guard_condition: str = ""
    approval_state: str = "not_required"
    execution_mode: str = ""
    session_strategy: str = ""
    active_role_id: str = ""
    role_pack_id: str = ""
    last_judge: str = ""
    latest_judge_decision: dict[str, Any] = field(default_factory=dict)
    last_operator_action: str = ""
    latest_operator_action: dict[str, Any] = field(default_factory=dict)
    queued_operator_updates: list[Any] = field(default_factory=list)
    latest_token_usage: dict[str, Any] = field(default_factory=dict)
    context_governor: dict[str, Any] = field(default_factory=dict)
    latest_handoff_summary: dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RoleRuntimeDTO:
    active_role_id: str = ""
    role_sessions: dict[str, Any] = field(default_factory=dict)
    pending_handoffs: list[dict[str, Any]] = field(default_factory=list)
    recent_handoffs: list[dict[str, Any]] = field(default_factory=list)
    latest_handoff_summary: dict[str, Any] = field(default_factory=dict)
    latest_role_handoffs: dict[str, Any] = field(default_factory=dict)
    role_chips: list[dict[str, Any]] = field(default_factory=list)
    roles: list[dict[str, Any]] = field(default_factory=list)
    execution_mode: str = ""
    session_strategy: str = ""
    role_pack_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SupervisorViewDTO:
    header: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    latest_supervisor_decision: dict[str, Any] = field(default_factory=dict)
    latest_judge_decision: dict[str, Any] = field(default_factory=dict)
    latest_operator_action: dict[str, Any] = field(default_factory=dict)
    latest_handoff_summary: dict[str, Any] = field(default_factory=dict)
    context_governor: dict[str, Any] = field(default_factory=dict)
    latest_token_usage: dict[str, Any] = field(default_factory=dict)
    pointers: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class WorkflowViewDTO:
    events: list[dict[str, Any]] = field(default_factory=list)
    runtime_summary: dict[str, Any] = field(default_factory=dict)
    artifact_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ManageCenterDTO:
    preflight: dict[str, Any] = field(default_factory=dict)
    assets: dict[str, Any] = field(default_factory=dict)
    selected_asset: dict[str, Any] = field(default_factory=dict)
    role_guidance: dict[str, Any] = field(default_factory=dict)
    review_checklist: list[str] = field(default_factory=list)
    bundle_manifest: dict[str, Any] = field(default_factory=dict)
    manager_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FlowDetailDTO:
    summary: dict[str, Any] = field(default_factory=dict)
    step_history: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    turns: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    handoffs: list[dict[str, Any]] = field(default_factory=list)
    flow_definition: dict[str, Any] = field(default_factory=dict)
    runtime_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
