from __future__ import annotations

from dataclasses import fields
from typing import Any

from .dto import (
    FlowConsoleDTO,
    FlowDetailDTO,
    FlowSummaryDTO,
    OperatorRailDTO,
    RoleRuntimeDTO,
    SupervisorViewDTO,
    WorkflowViewDTO,
)


def _coerce_flow_summary(value: FlowSummaryDTO | dict[str, Any] | None) -> FlowSummaryDTO:
    if isinstance(value, FlowSummaryDTO):
        return value
    payload = dict(value or {}) if isinstance(value, dict) else {}
    allowed = {item.name for item in fields(FlowSummaryDTO)}
    return FlowSummaryDTO(**{key: payload.get(key) for key in allowed if key in payload})


def _normalized_handoffs(handoffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in handoffs:
        row = dict(item or {})
        if not row:
            continue
        normalized.append(
            {
                "handoff_id": str(row.get("handoff_id") or "").strip(),
                "from_role_id": str(row.get("from_role_id") or row.get("source_role_id") or "").strip(),
                "to_role_id": str(row.get("to_role_id") or row.get("target_role_id") or "").strip(),
                "status": str(row.get("status") or "").strip(),
                "summary": str(row.get("summary") or "").strip(),
                "created_at": str(row.get("created_at") or "").strip(),
                "consumed_at": str(row.get("consumed_at") or "").strip(),
                "source_phase": str(row.get("source_phase") or "").strip(),
                "target_phase": str(row.get("target_phase") or "").strip(),
                "next_action": str(row.get("next_action") or "").strip(),
            }
        )
    return normalized


def latest_handoff_summary(handoffs: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = sorted(
        _normalized_handoffs(handoffs),
        key=lambda row: str(row.get("consumed_at") or row.get("created_at") or ""),
    )
    if not normalized:
        return {}
    pending = [row for row in normalized if str(row.get("status") or "").strip() == "pending"]
    if pending:
        return dict(pending[-1])
    return dict(normalized[-1])


def recent_handoffs(handoffs: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    normalized = sorted(
        _normalized_handoffs(handoffs),
        key=lambda row: str(row.get("consumed_at") or row.get("created_at") or ""),
    )
    if not normalized:
        return []
    return list(reversed(normalized[-max(1, int(limit or 5)) :]))


def pending_handoffs(handoffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = sorted(
        _normalized_handoffs(handoffs),
        key=lambda row: str(row.get("consumed_at") or row.get("created_at") or ""),
    )
    pending = [row for row in normalized if str(row.get("status") or "").strip() == "pending"]
    return list(reversed(pending))


def role_chips(*, flow_state: dict[str, Any], handoffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    role_sessions = dict(flow_state.get("role_sessions") or {})
    active_role_id = str(flow_state.get("active_role_id") or "").strip()
    pending = pending_handoffs(handoffs)
    pending_targets = {
        str(item.get("to_role_id") or "").strip()
        for item in pending
        if str(item.get("to_role_id") or "").strip()
    }
    pending_sources = {
        str(item.get("from_role_id") or "").strip()
        for item in pending
        if str(item.get("from_role_id") or "").strip()
    }
    role_order: list[str] = []

    def _add_role(role_id: str) -> None:
        token = str(role_id or "").strip()
        if token and token not in role_order:
            role_order.append(token)

    for role_id in role_sessions:
        _add_role(str(role_id))
    _add_role(active_role_id)
    for handoff in sorted(
        _normalized_handoffs(handoffs),
        key=lambda row: str(row.get("consumed_at") or row.get("created_at") or ""),
    ):
        _add_role(str(handoff.get("from_role_id") or ""))
        _add_role(str(handoff.get("to_role_id") or ""))

    chips: list[dict[str, Any]] = []
    for role_id in role_order:
        session_payload = dict(role_sessions.get(role_id) or {})
        state = "idle"
        if role_id and role_id == active_role_id:
            state = "active"
        elif role_id in pending_targets:
            state = "receiving_handoff"
        elif role_id in pending_sources:
            state = "handoff_source"
        chips.append(
            {
                "role_id": role_id,
                "state": state,
                "is_active": bool(role_id and role_id == active_role_id),
                "session_id": str(session_payload.get("session_id") or "").strip(),
            }
        )
    return chips


def build_flow_summary(*, status_payload: dict[str, Any], handoffs: list[dict[str, Any]]) -> FlowSummaryDTO:
    status = dict(status_payload.get("status") or {})
    if not status:
        status = dict(status_payload or {})
    flow_state = dict(status.get("flow_state") or {})
    latest_judge = dict(flow_state.get("latest_judge_decision") or {})
    last_operator_action = dict(flow_state.get("last_operator_action") or {})
    return FlowSummaryDTO(
        flow_id=str(
            status.get("flow_id")
            or flow_state.get("flow_id")
            or flow_state.get("workflow_id")
            or status_payload.get("flow_id")
            or ""
        ).strip(),
        label=str(flow_state.get("label") or status.get("label") or "").strip(),
        workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
        effective_status=str(status.get("effective_status") or flow_state.get("status") or "").strip(),
        effective_phase=str(status.get("effective_phase") or flow_state.get("current_phase") or "").strip(),
        attempt_count=int(flow_state.get("attempt_count") or 0),
        max_attempts=int(flow_state.get("max_attempts") or 0),
        max_phase_attempts=int(flow_state.get("max_phase_attempts") or 0),
        max_runtime_seconds=int(flow_state.get("max_runtime_seconds") or 0),
        runtime_elapsed_seconds=int(flow_state.get("runtime_elapsed_seconds") or 0),
        goal=str(flow_state.get("goal") or "").strip(),
        guard_condition=str(flow_state.get("guard_condition") or "").strip(),
        approval_state=str(flow_state.get("approval_state") or "").strip() or "not_required",
        execution_mode=str(flow_state.get("execution_mode") or "").strip(),
        session_strategy=str(flow_state.get("session_strategy") or "").strip(),
        active_role_id=str(flow_state.get("active_role_id") or "").strip(),
        role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
        last_judge=str(latest_judge.get("decision") or "").strip(),
        latest_judge_decision=latest_judge,
        last_operator_action=str(last_operator_action.get("action_type") or "").strip(),
        latest_operator_action=last_operator_action,
        queued_operator_updates=list(flow_state.get("queued_operator_updates") or []),
        latest_token_usage=dict(flow_state.get("latest_token_usage") or {}),
        context_governor=dict(flow_state.get("context_governor") or {}),
        latest_handoff_summary=latest_handoff_summary(handoffs),
        updated_at=str(flow_state.get("updated_at") or status.get("updated_at") or flow_state.get("created_at") or "").strip(),
    )


def build_supervisor_view(*, payload: dict[str, Any]) -> SupervisorViewDTO:
    row = dict(payload or {})
    return SupervisorViewDTO(
        header=dict(row.get("header") or {}),
        events=[dict(item or {}) for item in list(row.get("events") or [])],
        latest_supervisor_decision=dict(row.get("latest_supervisor_decision") or {}),
        latest_judge_decision=dict(row.get("latest_judge_decision") or {}),
        latest_operator_action=dict(row.get("latest_operator_action") or {}),
        latest_handoff_summary=dict(row.get("latest_handoff_summary") or {}),
        context_governor=dict(row.get("context_governor") or {}),
        latest_token_usage=dict(row.get("latest_token_usage") or {}),
        pointers=dict(row.get("pointers") or {}),
    )


def build_workflow_view(*, payload: dict[str, Any]) -> WorkflowViewDTO:
    row = dict(payload or {})
    return WorkflowViewDTO(
        events=[dict(item or {}) for item in list(row.get("events") or [])],
        runtime_summary=dict(row.get("runtime_summary") or {}),
        artifact_refs=[str(item or "").strip() for item in list(row.get("artifact_refs") or []) if str(item or "").strip()],
    )


def build_role_runtime(*, payload: dict[str, Any]) -> RoleRuntimeDTO:
    row = dict(payload or {})
    return RoleRuntimeDTO(
        active_role_id=str(row.get("active_role_id") or "").strip(),
        role_sessions=dict(row.get("role_sessions") or {}),
        pending_handoffs=[dict(item or {}) for item in list(row.get("pending_handoffs") or [])],
        recent_handoffs=[dict(item or {}) for item in list(row.get("recent_handoffs") or [])],
        latest_handoff_summary=dict(row.get("latest_handoff_summary") or {}),
        latest_role_handoffs=dict(row.get("latest_role_handoffs") or {}),
        role_chips=[dict(item or {}) for item in list(row.get("role_chips") or [])],
        roles=[dict(item or {}) for item in list(row.get("roles") or [])],
        execution_mode=str(row.get("execution_mode") or "").strip(),
        session_strategy=str(row.get("session_strategy") or "").strip(),
        role_pack_id=str(row.get("role_pack_id") or "").strip(),
    )


def build_operator_rail(*, payload: dict[str, Any]) -> OperatorRailDTO:
    row = dict(payload or {})
    return OperatorRailDTO(
        approval_state=str(row.get("approval_state") or "").strip() or "not_required",
        pending_codex_prompt=str(row.get("pending_codex_prompt") or "").strip(),
        latest_judge_decision=dict(row.get("latest_judge_decision") or {}),
        latest_operator_action=dict(row.get("latest_operator_action") or {}),
        latest_supervisor_decision=dict(row.get("latest_supervisor_decision") or {}),
        latest_handoff_summary=dict(row.get("latest_handoff_summary") or {}),
        manage_handoff=dict(row.get("manage_handoff") or {}),
        role_strip=build_role_runtime(payload=dict(row.get("role_strip") or {})),
        promoted_events=[dict(item or {}) for item in list(row.get("promoted_events") or [])],
    )


def build_flow_console(*, payload: dict[str, Any]) -> FlowConsoleDTO:
    row = dict(payload or {})
    return FlowConsoleDTO(
        flow_id=str(row.get("flow_id") or "").strip(),
        summary=_coerce_flow_summary(row.get("summary")),
        recent_steps=[dict(item or {}) for item in list(row.get("recent_steps") or [])],
        step_history=[dict(item or {}) for item in list(row.get("step_history") or [])],
    )


def build_flow_detail(*, payload: dict[str, Any]) -> FlowDetailDTO:
    row = dict(payload or {})
    return FlowDetailDTO(
        flow_id=str(row.get("flow_id") or "").strip(),
        status=dict(row.get("status") or {}),
        summary=_coerce_flow_summary(row.get("summary")),
        step_history=[dict(item or {}) for item in list(row.get("step_history") or [])],
        timeline=[dict(item or {}) for item in list(row.get("timeline") or [])],
        turns=[dict(item or {}) for item in list(row.get("turns") or [])],
        actions=[dict(item or {}) for item in list(row.get("actions") or [])],
        artifacts=[dict(item or {}) for item in list(row.get("artifacts") or [])],
        handoffs=[dict(item or {}) for item in list(row.get("handoffs") or [])],
        flow_definition=dict(row.get("flow_definition") or {}),
        runtime_snapshot=dict(row.get("runtime_snapshot") or {}),
        navigator_summary=_coerce_flow_summary(row.get("navigator_summary") or row.get("summary")),
        supervisor_view=build_supervisor_view(payload=dict(row.get("supervisor_view") or {})),
        workflow_view=build_workflow_view(payload=dict(row.get("workflow_view") or {})),
        inspector=dict(row.get("inspector") or {}),
        role_strip=build_role_runtime(payload=dict(row.get("role_strip") or {})),
        operator_rail=build_operator_rail(payload=dict(row.get("operator_rail") or {})),
        flow_console=build_flow_console(payload=dict(row.get("flow_console") or {})),
    )
