from __future__ import annotations

from typing import Any

from .dto import FlowSummaryDTO


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


def build_flow_summary(*, status_payload: dict[str, Any], handoffs: list[dict[str, Any]]) -> FlowSummaryDTO:
    status = dict(status_payload.get("status") or {})
    if not status:
        status = dict(status_payload or {})
    flow_state = dict(status.get("flow_state") or {})
    latest_judge = dict(flow_state.get("latest_judge_decision") or {})
    last_operator_action = dict(flow_state.get("last_operator_action") or {})
    return FlowSummaryDTO(
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
    )
