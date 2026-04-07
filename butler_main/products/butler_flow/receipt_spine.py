from __future__ import annotations

from datetime import datetime
from typing import Any


_DEFAULT_STATUS_BY_KIND = {
    "turn_acceptance": "accepted",
    "artifact_acceptance": "accepted",
    "operator_action": "applied",
    "exec_terminal": "terminal",
    "authority_transition": "updated",
    "policy_update": "updated",
}


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _has_queued_operator_updates(flow_state: dict[str, Any] | None) -> bool:
    state = dict(flow_state or {})
    for item in list(state.get("queued_operator_updates") or []):
        payload = dict(item or {})
        status = _text(payload.get("status")).lower()
        if status in {"", "queued", "pending"}:
            return True
    return False


def normalize_task_receipt(
    payload: dict[str, Any] | None,
    *,
    current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = dict(current or {})
    row.update(dict(payload or {}))
    receipt_kind = _text(row.get("receipt_kind") or row.get("kind"))
    if receipt_kind == "flow_exec_receipt":
        receipt_kind = "exec_terminal"
    receipt_id = _text(
        row.get("receipt_id")
        or row.get("action_id")
        or row.get("source_ref")
        or row.get("turn_id")
    )
    if not receipt_id:
        receipt_id = f"receipt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    status = _text(row.get("status") or _DEFAULT_STATUS_BY_KIND.get(receipt_kind) or "accepted")
    return {
        "receipt_id": receipt_id,
        "receipt_kind": receipt_kind,
        "flow_id": _text(row.get("flow_id")),
        "task_contract_id": _text(row.get("task_contract_id")),
        "status": status,
        "phase": _text(row.get("phase") or row.get("current_phase")),
        "attempt_no": _int(row.get("attempt_no")),
        "active_role_id": _text(row.get("active_role_id") or row.get("role_id")),
        "artifact_ref": _text(row.get("artifact_ref")),
        "decision": _text(row.get("decision")),
        "action_type": _text(row.get("action_type")),
        "source_ref": _text(
            row.get("source_ref")
            or row.get("turn_id")
            or row.get("action_id")
            or row.get("flow_dir")
        ),
        "summary": _text(
            row.get("summary")
            or row.get("result_summary")
            or row.get("completion_summary")
            or row.get("reason")
        ),
        "authority_snapshot": dict(row.get("authority_snapshot") or {}),
        "policy_snapshot": dict(row.get("policy_snapshot") or {}),
        "recovery_state": _text(row.get("recovery_state")),
        "payload": dict(row.get("payload") or {}),
        "created_at": _text(row.get("created_at") or _now_text()),
    }


def summarize_task_receipt(receipt: dict[str, Any] | None) -> dict[str, Any]:
    row = normalize_task_receipt(receipt or {})
    return {
        "receipt_id": _text(row.get("receipt_id")),
        "receipt_kind": _text(row.get("receipt_kind")),
        "task_contract_id": _text(row.get("task_contract_id")),
        "status": _text(row.get("status")),
        "phase": _text(row.get("phase")),
        "attempt_no": _int(row.get("attempt_no")),
        "active_role_id": _text(row.get("active_role_id")),
        "artifact_ref": _text(row.get("artifact_ref")),
        "decision": _text(row.get("decision")),
        "action_type": _text(row.get("action_type")),
        "summary": _text(row.get("summary")),
        "recovery_state": _text(row.get("recovery_state")),
        "created_at": _text(row.get("created_at")),
    }


def latest_task_receipt(receipts: list[dict[str, Any]] | None) -> dict[str, Any]:
    normalized = [normalize_task_receipt(item) for item in list(receipts or []) if isinstance(item, dict)]
    if not normalized:
        return {}
    normalized.sort(
        key=lambda row: (
            _text(row.get("created_at")),
            _text(row.get("receipt_id")),
        )
    )
    return dict(normalized[-1])


def latest_artifact_ref(artifacts: list[dict[str, Any]] | None) -> str:
    rows = [dict(item or {}) for item in list(artifacts or []) if isinstance(item, dict)]
    accepted = [
        row
        for row in rows
        if _text(row.get("artifact_ref")) and _text(row.get("status") or "accepted") == "accepted"
    ]
    target = accepted or rows
    if not target:
        return ""
    target.sort(
        key=lambda row: (
            _text(row.get("accepted_at") or row.get("created_at")),
            _text(row.get("artifact_ref")),
        )
    )
    return _text(target[-1].get("artifact_ref"))


def infer_recovery_state(
    *,
    flow_state: dict[str, Any] | None,
    latest_receipt: dict[str, Any] | None = None,
) -> str:
    state = dict(flow_state or {})
    latest = normalize_task_receipt(latest_receipt or {})
    status = _text(state.get("status")).lower()
    approval_state = _text(state.get("approval_state")).lower()
    active_role_id = _text(state.get("active_role_id"))
    codex_session_id = _text(state.get("codex_session_id"))
    role_sessions = dict(state.get("role_sessions") or {})
    role_session = dict(role_sessions.get(active_role_id) or {}) if active_role_id else {}
    has_queued_updates = _has_queued_operator_updates(state)
    latest_receipt_id = _text(latest.get("receipt_id"))
    if status == "completed":
        return "completed"
    if approval_state == "operator_required" or status == "paused":
        if has_queued_updates:
            if codex_session_id:
                return "resume_existing_session"
            if active_role_id and _text(role_session.get("session_id")):
                return "rebind_role_session"
            if latest_receipt_id:
                return "reseed_same_contract"
        return "pause_for_operator"
    if status in {"failed", "interrupted"}:
        return "rollback_to_receipt" if latest_receipt_id else "pause_for_operator"
    if active_role_id and _text(role_session.get("session_id")) and not codex_session_id:
        return "rebind_role_session"
    if codex_session_id:
        return "resume_existing_session"
    if latest_receipt_id:
        return "reseed_same_contract"
    return "reseed_same_contract"


def plan_resume_recovery(
    *,
    flow_state: dict[str, Any] | None,
    task_contract: dict[str, Any] | None,
    recovery_cursor: dict[str, Any] | None,
    receipts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state = dict(flow_state or {})
    contract = dict(task_contract or {})
    latest = latest_task_receipt(receipts)
    cursor = build_recovery_cursor(
        flow_state=state,
        task_contract=contract,
        latest_receipt=latest,
        current=dict(recovery_cursor or {}),
        recovery_state=_text(dict(recovery_cursor or {}).get("recovery_state")),
    )
    active_role_id = _text(cursor.get("active_role_id") or state.get("active_role_id"))
    role_sessions = dict(state.get("role_sessions") or {})
    role_session = dict(role_sessions.get(active_role_id) or {}) if active_role_id else {}
    latest_receipt_id = _text(cursor.get("latest_accepted_receipt_id") or latest.get("receipt_id"))
    codex_session_id = _text(cursor.get("codex_session_id") or state.get("codex_session_id"))
    role_session_id = _text(role_session.get("session_id"))
    requested_action = _text(cursor.get("recovery_state")).lower() or infer_recovery_state(
        flow_state=state,
        latest_receipt=latest,
    )
    action = requested_action
    resume_session_id = ""
    if action == "pause_for_operator" and _has_queued_operator_updates(state):
        if codex_session_id:
            action = "resume_existing_session"
        elif role_session_id:
            action = "rebind_role_session"
        elif latest_receipt_id:
            action = "reseed_same_contract"
    if action == "resume_existing_session" and codex_session_id:
        resume_session_id = codex_session_id
    elif action == "rebind_role_session" and role_session_id:
        resume_session_id = role_session_id
    elif action == "rollback_to_receipt" and not latest_receipt_id:
        action = "pause_for_operator"
    elif action not in {
        "resume_existing_session",
        "reseed_same_contract",
        "rebind_role_session",
        "rollback_to_receipt",
        "pause_for_operator",
        "completed",
    }:
        if codex_session_id:
            action = "resume_existing_session"
            resume_session_id = codex_session_id
        elif role_session_id:
            action = "rebind_role_session"
            resume_session_id = role_session_id
        elif latest_receipt_id:
            action = "reseed_same_contract"
        else:
            action = "pause_for_operator"
    summary_map = {
        "completed": "flow already completed",
        "resume_existing_session": (
            f"resume existing codex session {resume_session_id}"
            if resume_session_id
            else "resume existing codex session"
        ),
        "reseed_same_contract": (
            f"reseed same task contract from accepted receipt {latest_receipt_id}"
            if latest_receipt_id
            else "reseed same task contract from current contract truth"
        ),
        "rebind_role_session": (
            f"rebind active role session {resume_session_id}"
            if resume_session_id
            else "rebind active role session"
        ),
        "rollback_to_receipt": (
            f"rollback to latest accepted receipt {latest_receipt_id}"
            if latest_receipt_id
            else "rollback requires an accepted receipt"
        ),
        "pause_for_operator": "pause for operator input before resuming",
    }
    return {
        "recovery_action": action,
        "recovery_state": _text(cursor.get("recovery_state")) or action,
        "summary": summary_map.get(action, summary_map["pause_for_operator"]),
        "task_contract_id": _text(cursor.get("task_contract_id") or contract.get("task_contract_id")),
        "latest_accepted_receipt_id": latest_receipt_id,
        "latest_artifact_ref": _text(cursor.get("latest_artifact_ref")),
        "active_role_id": active_role_id,
        "current_phase": _text(cursor.get("current_phase") or state.get("current_phase")),
        "resume_session_id": resume_session_id,
        "has_queued_operator_updates": _has_queued_operator_updates(state),
    }


def build_recovery_cursor(
    *,
    flow_state: dict[str, Any] | None,
    task_contract: dict[str, Any] | None,
    latest_receipt: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    current: dict[str, Any] | None = None,
    recovery_state: str = "",
) -> dict[str, Any]:
    state = dict(flow_state or {})
    contract = dict(task_contract or {})
    existing = dict(current or {})
    latest = normalize_task_receipt(latest_receipt or {})
    latest_artifact = _text(latest.get("artifact_ref")) or latest_artifact_ref(artifacts)
    resolved_recovery_state = _text(recovery_state) or infer_recovery_state(flow_state=state, latest_receipt=latest)
    return {
        "flow_id": _text(existing.get("flow_id") or state.get("workflow_id") or state.get("flow_id")),
        "task_contract_id": _text(
            existing.get("task_contract_id")
            or contract.get("task_contract_id")
            or state.get("task_contract_id")
        ),
        "latest_accepted_receipt_id": _text(existing.get("latest_accepted_receipt_id") or latest.get("receipt_id")),
        "latest_artifact_ref": _text(existing.get("latest_artifact_ref") or latest_artifact),
        "current_phase": _text(existing.get("current_phase") or state.get("current_phase")),
        "active_role_id": _text(existing.get("active_role_id") or state.get("active_role_id")),
        "codex_session_id": _text(existing.get("codex_session_id") or state.get("codex_session_id")),
        "recovery_state": resolved_recovery_state,
        "updated_at": _text(existing.get("updated_at") or _now_text()),
    }
