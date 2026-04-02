from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .constants import (
    DONE_PHASE,
    EXECUTION_MODE_COMPLEX,
    EXECUTION_MODE_MEDIUM,
    EXECUTION_MODE_SIMPLE,
    FIXER_ROLE_ID,
    IMPLEMENTER_ROLE_ID,
    MANAGED_FLOW_KIND,
    PLANNER_ROLE_ID,
    PROJECT_LOOP_KIND,
    REPORTER_ROLE_ID,
    RESEARCHER_ROLE_ID,
    REVIEWER_ROLE_ID,
    ROLE_PACK_CODING_FLOW,
    ROLE_PACK_RESEARCH_FLOW,
    SESSION_STRATEGY_PER_ACTIVATION,
    SESSION_STRATEGY_ROLE_BOUND,
    SESSION_STRATEGY_SHARED,
    SINGLE_GOAL_KIND,
)
from .state import append_jsonl, now_text, read_json, safe_int, write_json_atomic


def _flow_settings(cfg: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(cfg or {})
    raw = payload.get("butler_flow")
    if isinstance(raw, dict):
        return dict(raw or {})
    raw = payload.get("workflow_shell")
    return dict(raw or {}) if isinstance(raw, dict) else {}


def _role_runtime_settings(cfg: dict[str, Any] | None) -> dict[str, Any]:
    settings = _flow_settings(cfg)
    raw = settings.get("role_runtime")
    return dict(raw or {}) if isinstance(raw, dict) else {}


def _prompt_policy_settings(cfg: dict[str, Any] | None) -> dict[str, Any]:
    settings = _flow_settings(cfg)
    raw = settings.get("prompt_policy")
    return dict(raw or {}) if isinstance(raw, dict) else {}


def normalize_execution_mode(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    if token in {EXECUTION_MODE_SIMPLE, EXECUTION_MODE_MEDIUM, EXECUTION_MODE_COMPLEX}:
        return token
    return EXECUTION_MODE_SIMPLE


def normalize_session_strategy(raw: Any, *, execution_mode: str) -> str:
    token = str(raw or "").strip().lower()
    if token in {SESSION_STRATEGY_SHARED, SESSION_STRATEGY_ROLE_BOUND, SESSION_STRATEGY_PER_ACTIVATION}:
        return token
    return session_strategy_for_mode(execution_mode)


def session_strategy_for_mode(execution_mode: str) -> str:
    normalized = normalize_execution_mode(execution_mode)
    if normalized == EXECUTION_MODE_MEDIUM:
        return SESSION_STRATEGY_ROLE_BOUND
    if normalized == EXECUTION_MODE_COMPLEX:
        return SESSION_STRATEGY_PER_ACTIVATION
    return SESSION_STRATEGY_SHARED


def default_execution_mode(cfg: dict[str, Any] | None) -> str:
    settings = _role_runtime_settings(cfg)
    return normalize_execution_mode(settings.get("execution_mode_default"))


def normalize_role_pack_id(raw: Any, *, workflow_kind: str = "") -> str:
    token = str(raw or "").strip().lower()
    if token in {ROLE_PACK_CODING_FLOW, ROLE_PACK_RESEARCH_FLOW}:
        return token
    if str(workflow_kind or "").strip() == MANAGED_FLOW_KIND:
        return ROLE_PACK_CODING_FLOW
    if str(workflow_kind or "").strip() == PROJECT_LOOP_KIND:
        return ROLE_PACK_CODING_FLOW
    if str(workflow_kind or "").strip() == SINGLE_GOAL_KIND:
        return ROLE_PACK_CODING_FLOW
    return ROLE_PACK_CODING_FLOW


def stable_role_ids(role_pack_id: str) -> tuple[str, ...]:
    normalized = str(role_pack_id or "").strip().lower()
    if normalized == ROLE_PACK_RESEARCH_FLOW:
        return (
            PLANNER_ROLE_ID,
            RESEARCHER_ROLE_ID,
            IMPLEMENTER_ROLE_ID,
            REVIEWER_ROLE_ID,
            FIXER_ROLE_ID,
            REPORTER_ROLE_ID,
        )
    return (
        PLANNER_ROLE_ID,
        IMPLEMENTER_ROLE_ID,
        REVIEWER_ROLE_ID,
        FIXER_ROLE_ID,
        REPORTER_ROLE_ID,
    )


def is_ephemeral_role(flow_state: dict[str, Any], *, role_id: str) -> bool:
    role_payload = dict(dict(flow_state.get("role_sessions") or {}).get(str(role_id or "").strip()) or {})
    if str(role_payload.get("role_kind") or "").strip() == "ephemeral":
        return True
    return str(role_id or "").strip() not in stable_role_ids(str(flow_state.get("role_pack_id") or "").strip())


def default_role_pack_id(cfg: dict[str, Any] | None, *, workflow_kind: str = "") -> str:
    settings = _role_runtime_settings(cfg)
    return normalize_role_pack_id(settings.get("role_pack"), workflow_kind=workflow_kind)


def role_runtime_enabled(cfg: dict[str, Any] | None, *, execution_mode: str) -> bool:
    settings = _role_runtime_settings(cfg)
    configured = settings.get("enable_role_handoffs")
    if isinstance(configured, bool):
        return bool(configured)
    return normalize_execution_mode(execution_mode) != EXECUTION_MODE_SIMPLE


def role_sessions_path(flow_dir: Path) -> Path:
    return flow_dir / "role_sessions.json"


def handoffs_path(flow_dir: Path) -> Path:
    return flow_dir / "handoffs.jsonl"


def load_role_sessions(flow_dir: Path) -> dict[str, Any]:
    payload = read_json(role_sessions_path(flow_dir))
    raw_items = payload.get("items")
    if isinstance(raw_items, list):
        rows: dict[str, Any] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            role_id = str(item.get("role_id") or "").strip()
            if role_id:
                rows[role_id] = dict(item)
        return rows
    if isinstance(raw_items, dict):
        return {str(role_id or "").strip(): {"role_id": str(role_id or "").strip(), **dict(item or {})} for role_id, item in raw_items.items() if str(role_id or "").strip()}
    return {}


def save_role_sessions(flow_dir: Path, flow_id: str, role_sessions: dict[str, Any]) -> None:
    items = []
    normalized_map: dict[str, Any] = {}
    for role_id, item in dict(role_sessions or {}).items():
        normalized_role_id = str(role_id or "").strip()
        if not normalized_role_id:
            continue
        payload = {"role_id": normalized_role_id, **dict(item or {})}
        items.append(payload)
        normalized_map[normalized_role_id] = payload
    write_json_atomic(
        role_sessions_path(flow_dir),
        {
            "flow_id": str(flow_id or "").strip(),
            "items": items,
            "by_role_id": normalized_map,
            "updated_at": now_text(),
        },
    )


def load_handoffs(flow_dir: Path) -> dict[str, dict[str, Any]]:
    path = handoffs_path(flow_dir)
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = str(line or "").strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        handoff_id = str(payload.get("handoff_id") or "").strip()
        if not handoff_id:
            continue
        rows[handoff_id] = dict(payload)
    return rows


def append_handoff(flow_dir: Path, payload: dict[str, Any]) -> None:
    append_jsonl(handoffs_path(flow_dir), dict(payload or {}))


def mark_handoff_consumed(flow_dir: Path, handoff_id: str, *, consumed_by_role_id: str = "") -> dict[str, Any]:
    handoffs = load_handoffs(flow_dir)
    payload = dict(handoffs.get(str(handoff_id or "").strip()) or {})
    if not payload:
        return {}
    if str(payload.get("status") or "").strip() == "consumed" and str(payload.get("consumed_at") or "").strip():
        return payload
    payload["status"] = "consumed"
    payload["consumed_at"] = now_text()
    if str(consumed_by_role_id or "").strip():
        payload["consumed_by_role_id"] = str(consumed_by_role_id or "").strip()
    append_handoff(flow_dir, payload)
    return payload


def latest_handoff_for_role(flow_dir: Path, role_id: str) -> dict[str, Any]:
    target = str(role_id or "").strip()
    if not target:
        return {}
    rows = list(load_handoffs(flow_dir).values())
    rows.sort(key=lambda item: str(item.get("created_at") or ""))
    for row in reversed(rows):
        if str(row.get("to_role_id") or "").strip() == target:
            return dict(row)
    return {}


def default_role_for_phase(phase: str, *, workflow_kind: str = "", role_pack_id: str = "") -> str:
    _ = role_pack_id
    normalized_phase = str(phase or "").strip().lower()
    normalized_kind = str(workflow_kind or "").strip()
    if normalized_phase == "plan":
        return PLANNER_ROLE_ID
    if normalized_phase == "review":
        return REVIEWER_ROLE_ID
    if normalized_phase == "done":
        return REPORTER_ROLE_ID
    if normalized_kind == SINGLE_GOAL_KIND:
        return IMPLEMENTER_ROLE_ID
    return IMPLEMENTER_ROLE_ID


def select_active_role(flow_state: dict[str, Any], *, phase: str) -> str:
    workflow_kind = str(flow_state.get("workflow_kind") or "").strip()
    current_role = str(flow_state.get("active_role_id") or "").strip() or default_role_for_phase(
        phase,
        workflow_kind=workflow_kind,
        role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
    )
    latest = dict(flow_state.get("latest_judge_decision") or {})
    issue_kind = str(latest.get("issue_kind") or "").strip().lower()
    followup_kind = str(latest.get("followup_kind") or "").strip().lower()
    decision_name = str(latest.get("decision") or "").strip().upper()
    normalized_phase = str(phase or "").strip().lower()

    if issue_kind == "agent_cli_fault" and followup_kind == "fix":
        return FIXER_ROLE_ID
    if normalized_phase == "review":
        if current_role == FIXER_ROLE_ID:
            if issue_kind == "bug" and followup_kind == "retry":
                return FIXER_ROLE_ID
            if issue_kind == "plan_gap" or followup_kind == "replan":
                return PLANNER_ROLE_ID
            if decision_name in {"ADVANCE", "COMPLETE", "ABORT"} or issue_kind in {"none", "service_fault"}:
                return REVIEWER_ROLE_ID
        if issue_kind == "bug" and followup_kind == "retry":
            return FIXER_ROLE_ID
    if normalized_phase == "plan":
        return PLANNER_ROLE_ID
    if normalized_phase == DONE_PHASE:
        return REPORTER_ROLE_ID
    return default_role_for_phase(
        phase,
        workflow_kind=workflow_kind,
        role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
    )


def determine_followup_role(
    flow_state: dict[str, Any],
    *,
    current_role_id: str,
    current_phase: str,
    next_phase: str,
    decision: dict[str, Any] | None,
) -> str:
    payload = dict(decision or {})
    issue_kind = str(payload.get("issue_kind") or "").strip().lower()
    followup_kind = str(payload.get("followup_kind") or "").strip().lower()
    decision_name = str(payload.get("decision") or "").strip().upper()
    target_phase = str(next_phase or current_phase).strip().lower() or str(current_phase or "").strip().lower()
    if issue_kind == "agent_cli_fault" and followup_kind == "fix":
        return FIXER_ROLE_ID
    if target_phase == "review" and issue_kind == "bug" and followup_kind == "retry":
        return FIXER_ROLE_ID
    if issue_kind == "plan_gap" or followup_kind == "replan":
        return PLANNER_ROLE_ID
    if str(current_role_id or "").strip() == FIXER_ROLE_ID and target_phase == "review":
        if issue_kind == "bug" and followup_kind == "retry":
            return FIXER_ROLE_ID
        if decision_name in {"ADVANCE", "COMPLETE", "ABORT"} or issue_kind in {"none", "service_fault"}:
            return REVIEWER_ROLE_ID
    return default_role_for_phase(
        target_phase,
        workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
        role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
    )


def role_session_id_for_turn(flow_state: dict[str, Any], *, role_id: str) -> str:
    session_strategy = normalize_session_strategy(
        flow_state.get("session_strategy"),
        execution_mode=str(flow_state.get("execution_mode") or "").strip(),
    )
    if session_strategy == SESSION_STRATEGY_SHARED:
        return str(flow_state.get("codex_session_id") or "").strip()
    if session_strategy == SESSION_STRATEGY_PER_ACTIVATION:
        return ""
    role_sessions = dict(flow_state.get("role_sessions") or {})
    role_payload = dict(role_sessions.get(str(role_id or "").strip()) or {})
    return str(role_payload.get("session_id") or "").strip()


def update_role_session_binding(
    flow_state: dict[str, Any],
    *,
    role_id: str,
    session_id: str,
    status: str = "",
    last_handoff_id: str = "",
    role_kind: str = "",
    base_role_id: str = "",
    role_charter_addendum: str = "",
) -> dict[str, Any]:
    role_sessions = dict(flow_state.get("role_sessions") or {})
    role_payload = dict(role_sessions.get(str(role_id or "").strip()) or {})
    role_payload["role_id"] = str(role_id or "").strip()
    role_payload["session_id"] = str(session_id or "").strip()
    if str(status or "").strip():
        role_payload["status"] = str(status or "").strip()
    if str(last_handoff_id or "").strip():
        role_payload["last_handoff_id"] = str(last_handoff_id or "").strip()
    if str(role_kind or "").strip():
        role_payload["role_kind"] = str(role_kind or "").strip()
    if str(base_role_id or "").strip():
        role_payload["base_role_id"] = str(base_role_id or "").strip()
    if str(role_charter_addendum or "").strip():
        role_payload["role_charter_addendum"] = str(role_charter_addendum or "").strip()
    role_payload["updated_at"] = now_text()
    role_sessions[str(role_id or "").strip()] = role_payload
    flow_state["role_sessions"] = role_sessions
    return role_payload


def bump_active_role_turn_no(flow_state: dict[str, Any], *, role_id: str) -> int:
    counts = dict(flow_state.get("role_turn_counts") or {})
    token = str(role_id or "").strip()
    next_value = safe_int(counts.get(token), 0) + 1
    counts[token] = next_value
    flow_state["role_turn_counts"] = counts
    flow_state["active_role_turn_no"] = next_value
    return next_value


def record_latest_handoff(flow_state: dict[str, Any], *, role_id: str, handoff_id: str) -> None:
    latest = dict(flow_state.get("latest_role_handoffs") or {})
    latest[str(role_id or "").strip()] = str(handoff_id or "").strip()
    flow_state["latest_role_handoffs"] = latest


def current_role_prompt(
    *,
    role_pack_id: str,
    role_id: str,
    flow_state: dict[str, Any] | None = None,
) -> str:
    role_state = dict(flow_state or {})
    role_payload = dict(dict(role_state.get("role_sessions") or {}).get(str(role_id or "").strip()) or {})
    base_role_id = str(role_payload.get("base_role_id") or "").strip()
    role_charter_addendum = str(role_payload.get("role_charter_addendum") or "").strip()
    if str(role_payload.get("role_kind") or "").strip() == "ephemeral":
        base_prompt = _role_pack_prompt_text(role_pack_id, base_role_id or role_id) or _fallback_role_prompt(base_role_id or role_id)
        if role_charter_addendum:
            return f"{base_prompt}\n\nEphemeral role addendum:\n{role_charter_addendum}".strip()
        return base_prompt
    prompt_text = _role_pack_prompt_text(role_pack_id, role_id)
    if prompt_text:
        return prompt_text
    return _fallback_role_prompt(role_id)


def _role_pack_prompt_text(role_pack_id: str, role_id: str) -> str:
    role_pack_root = Path(__file__).with_name("role_packs")
    prompt_path = role_pack_root / str(role_pack_id or "").strip() / f"{str(role_id or '').strip()}.md"
    if prompt_path.exists():
        try:
            return prompt_path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
    return ""


def _fallback_role_prompt(role_id: str) -> str:
    normalized = str(role_id or "").strip().lower()
    if normalized == PLANNER_ROLE_ID:
        return (
            "Role: planner\n"
            "Objective: produce or repair the concrete plan, identify files/tests, and leave execution ready.\n"
            "Allowed inputs: goal, guard condition, latest inbound handoff, recent artifacts, recent phase history.\n"
            "Required outputs: plan summary, files/tests to touch next, open questions, next action.\n"
            "Handoff expectations: pass a compact implementation-ready packet to the next role.\n"
            "Artifact expectations: produce plan/decision artifacts instead of repeating long prose."
        )
    if normalized == REVIEWER_ROLE_ID:
        return (
            "Role: reviewer\n"
            "Objective: review the latest implementation, run verification, identify real defects, and summarize residual risk.\n"
            "Allowed inputs: latest implementation artifacts, tests, receipts, inbound handoff, bounded flow truth.\n"
            "Required outputs: review verdict, concrete defects or acceptance evidence, next action.\n"
            "Handoff expectations: if issues remain, hand off concrete repair targets; if done, hand off completion summary.\n"
            "Artifact expectations: produce review evidence and verification refs."
        )
    if normalized == FIXER_ROLE_ID:
        return (
            "Role: fixer\n"
            "Objective: repair the concrete blockers handed off by reviewer or supervisor, then leave the next reviewer turn ready.\n"
            "Allowed inputs: defect handoff, latest artifacts, file refs, failing checks.\n"
            "Required outputs: what was fixed, what was verified, what still remains.\n"
            "Handoff expectations: hand back a bounded repair summary with verification refs.\n"
            "Artifact expectations: produce fix evidence rather than long narrative."
        )
    if normalized == REPORTER_ROLE_ID:
        return (
            "Role: reporter\n"
            "Objective: summarize the final result, verification, residual risks, and next operator-visible facts.\n"
            "Allowed inputs: final handoff, final artifacts, verification refs, flow truth.\n"
            "Required outputs: concise operator-facing result summary.\n"
            "Handoff expectations: none unless an explicit downstream target exists.\n"
            "Artifact expectations: produce final summary artifacts only."
        )
    if normalized == RESEARCHER_ROLE_ID:
        return (
            "Role: researcher\n"
            "Objective: gather and structure the specific evidence needed by the current task without drifting scope.\n"
            "Allowed inputs: research question, bounded context, prior findings, artifact refs.\n"
            "Required outputs: evidence summary, cited findings, open questions, next research or implementation suggestion.\n"
            "Handoff expectations: hand findings to planner or reporter in compact form.\n"
            "Artifact expectations: produce evidence artifacts with clear provenance."
        )
    if normalized == "creator":
        return (
            "Role: creator\n"
            "Objective: discover and remove capability bottlenecks that would block delivery, including missing environment, missing know-how, or missing enabling assets.\n"
            "Allowed inputs: current phase goal, bottleneck description, missing capability notes, recent artifacts.\n"
            "Required outputs: bottleneck diagnosis, enabling plan, concrete artifact or setup proposal, next action.\n"
            "Handoff expectations: hand the resolved bottleneck or next enabling step back to supervisor or planner in compact form.\n"
            "Artifact expectations: produce reusable enablement notes, references, or setup artifacts."
        )
    if normalized in {"product-manager", "product_manager"}:
        return (
            "Role: product-manager\n"
            "Objective: represent user value, workflow fit, scope control, and product-quality tradeoffs for the current task.\n"
            "Allowed inputs: goal, target users, acceptance criteria, prototypes, current output.\n"
            "Required outputs: product critique, missing requirements, prioritization advice, next product-facing action.\n"
            "Handoff expectations: hand concrete user-value deltas or acceptance gaps back to supervisor or implementer.\n"
            "Artifact expectations: produce concise requirement or evaluation artifacts."
        )
    if normalized in {"user-simulator", "user_simulator"}:
        return (
            "Role: user-simulator\n"
            "Objective: exercise the current output like a realistic end user and surface friction, confusion, quality gaps, and missing affordances.\n"
            "Allowed inputs: current build/output, target scenario, expected user journey, acceptance criteria.\n"
            "Required outputs: user-journey observations, concrete pain points, severity, and suggested next checks.\n"
            "Handoff expectations: hand product and usability gaps back to supervisor, product-manager, or implementer.\n"
            "Artifact expectations: produce compact trial notes with scenario and impact."
        )
    return (
        "Role: implementer\n"
        "Objective: do the real repository work for the current task, verify it, and keep momentum.\n"
        "Allowed inputs: plan handoff, current task context, recent artifacts, file/test refs.\n"
        "Required outputs: code/test progress, verification, blockers, next action.\n"
        "Handoff expectations: leave the next role with a bounded summary and artifact refs.\n"
        "Artifact expectations: produce implementation artifacts with file/test evidence."
    )


def build_prompt_overlay(cfg: dict[str, Any] | None) -> str:
    settings = _prompt_policy_settings(cfg)
    include_repo = bool(settings.get("include_repo_governance_blocks", True))
    include_background = bool(settings.get("include_background_task_constraints", False))
    include_heavy_acceptance = bool(settings.get("include_heavy_acceptance_blocks", False))
    blocks: list[str] = []
    if include_repo:
        blocks.append(
            "Repo contract:\n"
            "- Do real repository work.\n"
            "- Run the smallest meaningful verification for the change.\n"
            "- Keep the final reply concrete: done, verified, remaining risk."
        )
    if include_background:
        blocks.append(
            "Boundary contract:\n"
            "- This is foreground butler-flow.\n"
            "- Do not rely on campaign/orchestrator or background task truth."
        )
    if include_heavy_acceptance:
        blocks.append(
            "Acceptance contract:\n"
            "- If you claim completion, cite the verification evidence and the remaining risk explicitly."
        )
    return "\n\n".join(blocks).strip()


def visible_artifacts(flow_dir: Path, *, role_id: str, limit: int = 3) -> list[dict[str, Any]]:
    payload = read_json(flow_dir / "artifacts.json")
    rows = list(payload.get("items") or [])
    visible: list[dict[str, Any]] = []
    normalized_role = str(role_id or "").strip()
    for row in reversed(rows):
        item = dict(row or {})
        producer_role_id = str(item.get("producer_role_id") or "").strip()
        consumer_role_ids = [str(value or "").strip() for value in list(item.get("consumer_role_ids") or []) if str(value or "").strip()]
        if not normalized_role:
            visible.append(item)
        elif producer_role_id == normalized_role or not consumer_role_ids or normalized_role in consumer_role_ids:
            visible.append(item)
        if len(visible) >= max(1, int(limit or 3)):
            break
    visible.reverse()
    return visible


def create_handoff_packet(
    flow_state: dict[str, Any],
    *,
    from_role_id: str,
    to_role_id: str,
    source_phase: str,
    target_phase: str,
    summary: str,
    next_action: str,
    artifact_refs: list[str] | None = None,
    verification_refs: list[str] | None = None,
    risk_flags: list[str] | None = None,
    completion_summary: str = "",
    open_questions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "handoff_id": f"handoff_{uuid4().hex[:12]}",
        "flow_id": str(flow_state.get("workflow_id") or "").strip(),
        "from_role_id": str(from_role_id or "").strip(),
        "to_role_id": str(to_role_id or "").strip(),
        "source_role_id": str(from_role_id or "").strip(),
        "target_role_id": str(to_role_id or "").strip(),
        "source_phase": str(source_phase or "").strip(),
        "target_phase": str(target_phase or "").strip(),
        "summary": str(summary or "").strip(),
        "goal": str(flow_state.get("goal") or "").strip(),
        "guard_condition": str(flow_state.get("guard_condition") or "").strip(),
        "completion_summary": str(completion_summary or "").strip(),
        "open_questions": [str(item or "").strip() for item in list(open_questions or []) if str(item or "").strip()],
        "next_action": str(next_action or "").strip(),
        "artifact_refs": [str(item or "").strip() for item in list(artifact_refs or []) if str(item or "").strip()],
        "verification_refs": [str(item or "").strip() for item in list(verification_refs or []) if str(item or "").strip()],
        "risk_flags": [str(item or "").strip() for item in list(risk_flags or []) if str(item or "").strip()],
        "status": "pending",
        "created_at": now_text(),
        "consumed_at": "",
    }


def extract_role_runtime_summary(flow_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_mode": normalize_execution_mode(flow_state.get("execution_mode")),
        "session_strategy": normalize_session_strategy(
            flow_state.get("session_strategy"),
            execution_mode=str(flow_state.get("execution_mode") or "").strip(),
        ),
        "active_role_id": str(flow_state.get("active_role_id") or "").strip(),
        "role_pack_id": normalize_role_pack_id(
            flow_state.get("role_pack_id"),
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
        ),
        "role_sessions": dict(flow_state.get("role_sessions") or {}),
        "latest_role_handoffs": dict(flow_state.get("latest_role_handoffs") or {}),
    }
