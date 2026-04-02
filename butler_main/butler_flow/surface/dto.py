from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FlowSummaryDTO:
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
