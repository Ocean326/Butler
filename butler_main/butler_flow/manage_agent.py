from __future__ import annotations

import json
from typing import Any, Callable

from butler_main.agents_os.execution.cli_runner import cli_provider_available

from .flow_definition import coerce_workflow_kind, normalize_phase_plan, resolve_phase_plan
from .state import now_text


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _receipt_text(receipt: Any) -> str:
    text = str(getattr(receipt, "summary", "") or "").strip()
    bundle = getattr(receipt, "output_bundle", None)
    if bundle is not None:
        for block in list(getattr(bundle, "text_blocks", []) or [])[::-1]:
            block_text = str(getattr(block, "text", "") or "").strip()
            if block_text:
                return block_text
    return text


def _receipt_thread_id(receipt: Any) -> str:
    metadata = dict(getattr(receipt, "metadata", {}) or {})
    external_session = dict(metadata.get("external_session") or {})
    return str(external_session.get("thread_id") or "").strip()


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = str(text or "").strip()
    if not stripped:
        return {}
    start = stripped.find("{")
    end = stripped.rfind("}")
    candidates = [stripped]
    if start >= 0 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


MANAGE_STAGES = ("proposal", "build", "review", "commit")


def normalize_manage_stage(stage: str) -> str:
    token = str(stage or "").strip().lower()
    if token in MANAGE_STAGES:
        return token
    return "commit"


def _dedupe_text_list(value: Any) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for item in list(value or []):
        token = str(item or "").strip()
        if not token:
            continue
        normalized = token.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        rows.append(token)
    return rows


def normalize_role_guidance_payload(
    raw: Any,
    *,
    current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(raw or {}) if isinstance(raw, dict) else {}
    existing = dict(current or {})

    def _pick_list(*keys: str) -> list[str]:
        for key in keys:
            if key in payload:
                return _dedupe_text_list(payload.get(key))
        for key in keys:
            if key in existing:
                return _dedupe_text_list(existing.get(key))
        return []

    def _pick_text(*keys: str) -> str:
        for key in keys:
            if key in payload:
                return str(payload.get(key) or "").strip()
        for key in keys:
            if key in existing:
                return str(existing.get(key) or "").strip()
        return ""

    normalized: dict[str, Any] = {}
    suggested_roles = _pick_list("suggested_roles", "roles", "prebuilt_roles")
    suggested_specialists = _pick_list("suggested_specialists", "specialists", "temporary_roles")
    activation_hints = _pick_list("activation_hints", "activation_triggers", "hints")
    promotion_candidates = _pick_list("promotion_candidates", "promotion_roles", "promotable_roles")
    manager_notes = _pick_text("manager_notes", "notes", "manager_note")
    if suggested_roles:
        normalized["suggested_roles"] = suggested_roles
    if suggested_specialists:
        normalized["suggested_specialists"] = suggested_specialists
    if activation_hints:
        normalized["activation_hints"] = activation_hints
    if promotion_candidates:
        normalized["promotion_candidates"] = promotion_candidates
    if manager_notes:
        normalized["manager_notes"] = manager_notes
    return normalized


def build_manage_prompt(
    *,
    flow_state: dict[str, Any] | None,
    manage_target: str,
    asset_kind: str,
    goal: str,
    guard_condition: str,
    instruction: str,
    stage: str = "commit",
) -> str:
    manage_stage = normalize_manage_stage(stage)
    current = dict(flow_state or {})
    payload = {
        "manage_target": manage_target,
        "asset_kind": asset_kind,
        "stage": manage_stage,
        "current_flow_state": current,
        "requested_goal": goal,
        "requested_guard_condition": guard_condition,
        "user_instruction": instruction,
        "protocol": [
            "intake: clarify whether this is a new flow or an update",
            "shape: propose workflow kind and ordered phases",
            "risk: set risk_level and autonomy_profile",
            "handoff: provide a concise user-facing summary plus a flow definition",
        ],
    }
    if manage_stage == "proposal":
        return (
            "You are the Butler Flow manager.\n\n"
            "Stage: proposal.\n"
            "Reply with JSON only.\n\n"
            "Required schema:\n"
            "{\n"
            '  "summary": "short proposal summary",\n'
            '  "label": "short asset label",\n'
            '  "description": "short asset description",\n'
            '  "goal": "refined goal text",\n'
            '  "guard_condition": "refined guard condition",\n'
            '  "workflow_kind": "single_goal" | "project_loop" | "managed_flow",\n'
            '  "asset_kind": "template" | "builtin" | "instance",\n'
            '  "recommended_execution_level": "simple" | "medium",\n'
            '  "confirmation_prompt": "one concise confirmation sentence"\n'
            "}\n\n"
            "Rules:\n"
            "- Keep the proposal concise and user-facing.\n"
            "- Prefer managed_flow when custom phases are needed.\n\n"
            f"Negotiation payload:\n{_compact_json(payload)}\n"
        )
    if manage_stage == "review":
        return (
            "You are the Butler Flow manager.\n\n"
            "Stage: review.\n"
            "Reply with JSON only.\n\n"
            "Required schema:\n"
            "{\n"
            '  "approved": true | false,\n'
            '  "summary": "short review summary",\n'
            '  "issues": ["issue 1", "issue 2"],\n'
            '  "confirmation_prompt": "one concise next-step sentence"\n'
            "}\n\n"
            "Rules:\n"
            "- Approve only when the draft is coherent, ordered, and directly runnable.\n"
            "- If not approved, issues must be concrete enough for the next build iteration.\n\n"
            f"Negotiation payload:\n{_compact_json(payload)}\n"
        )
    if manage_stage == "build":
        return (
            "You are the Butler Flow manager.\n\n"
            "Stage: build.\n"
            "Reply with JSON only.\n\n"
            "Required schema:\n"
            "{\n"
            '  "summary": "short build summary",\n'
            '  "label": "short asset label",\n'
            '  "description": "short asset description",\n'
            '  "goal": "final goal text",\n'
            '  "guard_condition": "final guard condition",\n'
            '  "workflow_kind": "single_goal" | "project_loop" | "managed_flow",\n'
            '  "asset_kind": "template" | "builtin" | "instance",\n'
            '  "risk_level": "low" | "normal" | "high",\n'
            '  "autonomy_profile": "default" | "guarded" | "operator_first",\n'
            '  "phase_plan": [\n'
            '    {"phase_id":"plan","title":"Plan","objective":"...","done_when":"...","retry_phase_id":"plan","fallback_phase_id":"plan","next_phase_id":"imp"}\n'
            "  ],\n"
            '  "role_guidance": {\n'
            '    "suggested_roles": ["planner","implementer","reviewer"],\n'
            '    "suggested_specialists": ["creator","product-manager","user-simulator"],\n'
            '    "activation_hints": ["when capability or environment gaps block progress"],\n'
            '    "promotion_candidates": ["creator"],\n'
            '    "manager_notes": "lightweight advisory notes only"\n'
            "  },\n"
            '  "operator_guidance": "how the user should manage this flow next",\n'
            '  "confirmation_prompt": "one concise confirmation sentence"\n'
            "}\n\n"
            "Rules:\n"
            "- Keep the phase plan ordered and minimal.\n"
            "- Do not create arbitrary DAGs.\n"
            "- Match asset_kind to the target.\n"
            "- role_guidance is advisory only: it helps manager creation and gives supervisor lightweight temporary-role hints, not a rigid team contract.\n\n"
            f"Negotiation payload:\n{_compact_json(payload)}\n"
        )
    return (
        "You are the Butler Flow manager agent.\n\n"
        f"Stage: {manage_stage}.\n\n"
        "Your job is to negotiate and hand off a manageable foreground flow definition.\n"
        "Reply with JSON only.\n\n"
        "Required schema:\n"
        "{\n"
        '  "summary": "short handoff summary",\n'
        '  "label": "short asset label",\n'
        '  "description": "short asset description",\n'
        '  "goal": "final goal text",\n'
        '  "guard_condition": "final guard condition",\n'
        '  "workflow_kind": "single_goal" | "project_loop" | "managed_flow",\n'
        '  "asset_kind": "instance" | "template" | "builtin",\n'
        '  "mutation": "create" | "update",\n'
        '  "risk_level": "low" | "normal" | "high",\n'
        '  "autonomy_profile": "default" | "guarded" | "operator_first",\n'
        '  "phase_plan": [\n'
        '    {"phase_id":"plan","title":"Plan","objective":"...","done_when":"...","retry_phase_id":"plan","fallback_phase_id":"plan","next_phase_id":"imp"}\n'
        "  ],\n"
        '  "role_guidance": {\n'
        '    "suggested_roles": ["planner","implementer","reviewer"],\n'
        '    "suggested_specialists": ["creator","product-manager","user-simulator"],\n'
        '    "activation_hints": ["when capability or environment gaps block progress"],\n'
        '    "promotion_candidates": ["creator"],\n'
        '    "manager_notes": "lightweight advisory notes only"\n'
        "  },\n"
        '  "operator_guidance": "how the user should manage this flow next",\n'
        '  "confirmation_prompt": "one concise confirmation sentence"\n'
        "}\n\n"
        "Rules:\n"
        "- Use managed_flow when the user needs custom phases.\n"
        "- Keep the phase plan ordered and minimal.\n"
        "- Do not create arbitrary DAGs.\n"
        "- Match asset_kind to the target. Use instance for runnable flow instances, template for reusable editable assets, builtin for repo-owned builtins.\n"
        "- role_guidance is advisory only: it should guide manager design and give supervisor lightweight role references, not impose a rigid team contract.\n"
        "- The summary should read like a user handoff note.\n\n"
        f"Negotiation payload:\n{_compact_json(payload)}\n"
    )


def build_manage_chat_prompt(
    *,
    manage_target: str,
    asset_kind: str,
    instruction: str,
    flow_state: dict[str, Any] | None = None,
    asset_definition: dict[str, Any] | None = None,
    asset_rows: list[dict[str, Any]] | None = None,
) -> str:
    payload = {
        "manage_target": str(manage_target or "").strip(),
        "asset_kind": str(asset_kind or "").strip(),
        "current_flow_state": dict(flow_state or {}),
        "asset_definition": dict(asset_definition or {}),
        "asset_index": [dict(row or {}) for row in list(asset_rows or [])[:12]],
        "user_instruction": str(instruction or "").strip(),
        "protocol": [
            "answer the operator's question directly",
            "if a specific asset is targeted, ground the answer in that asset's phases, static fields, lineage, bundle, and handoff",
            "if the request implies editing a builtin/template, explain the correct next action instead of mutating files in chat mode",
            "suggest when a supervisor prompt or bundled static asset should also be updated",
            "treat role guidance as a lightweight default skill set for manager and supervisor, not a rigid team contract",
        ],
    }
    return (
        "You are the Butler Flow manager chat.\n\n"
        "This is Manage Center conversational mode.\n"
        "Reply with JSON only.\n\n"
        "Required schema:\n"
        "{\n"
        '  "summary": "short chat summary",\n'
        '  "response": "direct operator-facing answer",\n'
        '  "manage_target": "resolved asset key or empty string",\n'
        '  "suggested_next_action": "optional short next step",\n'
        '  "should_edit_asset": true | false,\n'
        '  "edit_hint": "optional concise edit guidance",\n'
        '  "action": "none" | "manage_flow",\n'
        '  "action_ready": true | false,\n'
        '  "action_manage_target": "resolved manage target for manage_flow or empty string",\n'
        '  "action_instruction": "instruction text to pass into manage_flow or empty string",\n'
        '  "action_stage": "optional manage stage",\n'
        '  "action_builtin_mode": "optional builtin mode clone|edit"\n'
        "}\n\n"
        "Rules:\n"
        "- Chat mode is the default frontdoor for Manage Center.\n"
        "- Discuss, clarify, and refine first when needed.\n"
        "- When the request is already actionable, set action=manage_flow and return the executable target/instruction.\n"
        "- Use action_manage_target=new to create a pending flow instance, template:new to create a reusable template, or an explicit asset key when updating an existing asset.\n"
        "- If the request is still ambiguous, keep action=none and ask the next best question.\n"
        "- If the target is a builtin asset, mention clone/edit requirements when relevant.\n"
        "- If a builtin mutation is ready, set action_builtin_mode explicitly to clone or edit.\n"
        "- If the user asks about phases/static assets/supervisor prompt coupling, answer concretely from the supplied asset state.\n"
        "- When discussing design quality, recommend lightweight role_guidance for manager creation and supervisor temporary-node reference.\n"
        "- Keep the response concise but specific.\n\n"
        f"Conversation payload:\n{_compact_json(payload)}\n"
    )


def normalize_manage_result(
    result: dict[str, Any],
    *,
    flow_state: dict[str, Any] | None = None,
    asset_kind: str = "instance",
    manage_target: str = "",
) -> dict[str, Any]:
    current = dict(flow_state or {})
    workflow_kind = coerce_workflow_kind(str(result.get("workflow_kind") or current.get("workflow_kind") or "managed_flow"))
    goal = str(result.get("goal") or current.get("goal") or "").strip()
    guard_condition = str(result.get("guard_condition") or current.get("guard_condition") or "").strip()
    phase_plan = normalize_phase_plan(result.get("phase_plan") if isinstance(result.get("phase_plan"), list) else current.get("phase_plan"), workflow_kind=workflow_kind)
    if workflow_kind == "single_goal":
        phase_plan = resolve_phase_plan({"workflow_kind": workflow_kind})
    normalized_asset_kind = str(result.get("asset_kind") or asset_kind or "instance").strip().lower()
    if normalized_asset_kind not in {"builtin", "template", "instance"}:
        normalized_asset_kind = "instance"
    mutation = str(result.get("mutation") or ("create" if str(manage_target or "").strip().endswith(":new") or str(manage_target or "").strip() == "new" else "update")).strip().lower()
    if mutation not in {"create", "update"}:
        mutation = "update"
    label = str(result.get("label") or current.get("label") or current.get("flow_id") or goal or workflow_kind).strip()
    description = str(result.get("description") or current.get("description") or "").strip()
    review_checklist = [
        str(item or "").strip()
        for item in list(result.get("review_checklist") or current.get("review_checklist") or [])
        if str(item or "").strip()
    ]
    role_guidance = normalize_role_guidance_payload(
        result.get("role_guidance") or {},
        current=dict(current.get("role_guidance") or dict(current.get("manage_handoff") or {}).get("role_guidance") or {}),
    )
    return {
        "summary": str(result.get("summary") or f"managed flow prepared for {goal or 'foreground work'}").strip(),
        "label": label,
        "description": description,
        "goal": goal,
        "guard_condition": guard_condition,
        "workflow_kind": workflow_kind,
        "asset_kind": normalized_asset_kind,
        "mutation": mutation,
        "risk_level": str(result.get("risk_level") or current.get("risk_level") or "normal").strip() or "normal",
        "autonomy_profile": str(result.get("autonomy_profile") or current.get("autonomy_profile") or "default").strip() or "default",
        "phase_plan": phase_plan,
        "review_checklist": review_checklist,
        "role_guidance": role_guidance,
        "instance_defaults": dict(result.get("instance_defaults") or current.get("instance_defaults") or {}),
        "lineage": dict(result.get("lineage") or current.get("lineage") or {}),
        "asset_state": dict(result.get("asset_state") or current.get("asset_state") or {}),
        "bundle_manifest": dict(result.get("bundle_manifest") or current.get("bundle_manifest") or {}),
        "operator_guidance": str(result.get("operator_guidance") or "Review the handoff, then run or resume the managed flow.").strip(),
        "confirmation_prompt": str(result.get("confirmation_prompt") or "Review this managed flow definition before execution.").strip(),
        "managed_at": now_text(),
    }


def normalize_manage_stage_result(
    stage: str,
    result: dict[str, Any],
    *,
    flow_state: dict[str, Any] | None = None,
    asset_kind: str = "instance",
    manage_target: str = "",
) -> dict[str, Any]:
    manage_stage = normalize_manage_stage(stage)
    current = dict(flow_state or {})
    if manage_stage == "proposal":
        goal = str(result.get("goal") or current.get("goal") or "").strip()
        guard_condition = str(result.get("guard_condition") or current.get("guard_condition") or "").strip()
        workflow_kind = coerce_workflow_kind(str(result.get("workflow_kind") or current.get("workflow_kind") or "managed_flow"))
        level = str(result.get("recommended_execution_level") or "simple").strip().lower()
        if level not in {"simple", "medium"}:
            level = "simple"
        normalized_asset_kind = str(result.get("asset_kind") or asset_kind or "instance").strip().lower()
        if normalized_asset_kind not in {"builtin", "template", "instance"}:
            normalized_asset_kind = "instance"
        return {
            "summary": str(result.get("summary") or f"proposal ready for {goal or 'foreground work'}").strip(),
            "label": str(result.get("label") or current.get("label") or current.get("flow_id") or goal or workflow_kind).strip(),
            "description": str(result.get("description") or current.get("description") or "").strip(),
            "goal": goal,
            "guard_condition": guard_condition,
            "workflow_kind": workflow_kind,
            "asset_kind": normalized_asset_kind,
            "recommended_execution_level": level,
            "confirmation_prompt": str(result.get("confirmation_prompt") or "Review this proposal before building the flow.").strip(),
            "proposed_at": now_text(),
        }
    if manage_stage == "review":
        approved = bool(result.get("approved"))
        issues = [str(item or "").strip() for item in list(result.get("issues") or []) if str(item or "").strip()]
        return {
            "approved": approved,
            "summary": str(result.get("summary") or ("review passed" if approved else "review requires changes")).strip(),
            "issues": issues,
            "confirmation_prompt": str(result.get("confirmation_prompt") or ("Review passed. Save this flow." if approved else "Review found issues. Return to build.")).strip(),
            "reviewed_at": now_text(),
        }
    if manage_stage == "build":
        payload = normalize_manage_result(result, flow_state=flow_state, asset_kind=asset_kind, manage_target=manage_target)
        payload["built_at"] = now_text()
        return payload
    payload = normalize_manage_result(result, flow_state=flow_state, asset_kind=asset_kind, manage_target=manage_target)
    payload["manage_stage"] = manage_stage
    return payload


def build_design_prompt(
    *,
    stage: str,
    flow_state: dict[str, Any] | None,
    goal: str,
    guard_condition: str,
    instruction: str,
    draft: dict[str, Any] | None = None,
    proposal: dict[str, Any] | None = None,
    review_issues: list[str] | None = None,
) -> str:
    current = dict(flow_state or {})
    payload = {
        "stage": str(stage or "").strip(),
        "current_flow_state": current,
        "goal": goal,
        "guard_condition": guard_condition,
        "instruction": instruction,
        "proposal": dict(proposal or {}),
        "draft": dict(draft or {}),
        "review_issues": [str(item or "").strip() for item in list(review_issues or []) if str(item or "").strip()],
    }
    if stage == "proposal":
        return (
            "You are the Butler Flow designer.\n\n"
            "Stage: proposal.\n"
            "Reply with JSON only.\n\n"
            "Required schema:\n"
            "{\n"
            '  "summary": "short proposal summary",\n'
            '  "goal": "refined goal",\n'
            '  "guard_condition": "refined guard condition",\n'
            '  "workflow_kind": "single_goal" | "project_loop" | "managed_flow",\n'
            '  "recommended_execution_level": "simple" | "medium",\n'
            '  "confirmation_prompt": "one concise sentence asking the user to confirm the proposal"\n'
            "}\n\n"
            "Rules:\n"
            "- Prefer managed_flow when custom flow design is needed.\n"
            "- Keep the proposal concise and user-facing.\n\n"
            f"Design payload:\n{_compact_json(payload)}\n"
        )
    if stage == "review":
        return (
            "You are the Butler Flow designer.\n\n"
            "Stage: review.\n"
            "Reply with JSON only.\n\n"
            "Required schema:\n"
            "{\n"
            '  "approved": true | false,\n'
            '  "summary": "short review summary",\n'
            '  "issues": ["issue 1", "issue 2"],\n'
            '  "confirmation_prompt": "one concise next-step sentence"\n'
            "}\n\n"
            "Rules:\n"
            "- Approve only when the draft is coherent, ordered, and directly runnable as a managed flow.\n"
            "- If not approved, issues must be concrete enough for the next build iteration.\n\n"
            f"Design payload:\n{_compact_json(payload)}\n"
        )
    return (
        "You are the Butler Flow designer.\n\n"
        "Stage: build.\n"
        "Reply with JSON only.\n\n"
        "Required schema:\n"
        "{\n"
        '  "summary": "short build summary",\n'
        '  "goal": "final goal text",\n'
        '  "guard_condition": "final guard condition",\n'
        '  "workflow_kind": "managed_flow" | "project_loop" | "single_goal",\n'
        '  "risk_level": "low" | "normal" | "high",\n'
        '  "autonomy_profile": "default" | "guarded" | "operator_first",\n'
        '  "phase_plan": [\n'
        '    {"phase_id":"plan","title":"Plan","objective":"...","done_when":"...","retry_phase_id":"plan","fallback_phase_id":"plan","next_phase_id":"imp"}\n'
        "  ],\n"
        '  "operator_guidance": "how the user should operate this flow",\n'
        '  "confirmation_prompt": "one concise confirmation sentence"\n'
        "}\n\n"
        "Rules:\n"
        "- Keep the phase plan ordered and minimal.\n"
        "- Do not create arbitrary DAGs.\n"
        "- Prefer managed_flow when custom phases are present.\n\n"
        f"Design payload:\n{_compact_json(payload)}\n"
    )


def normalize_design_result(
    stage: str,
    result: dict[str, Any],
    *,
    flow_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = dict(flow_state or {})
    goal = str(result.get("goal") or current.get("goal") or "").strip()
    guard_condition = str(result.get("guard_condition") or current.get("guard_condition") or "").strip()
    if stage == "proposal":
        level = str(result.get("recommended_execution_level") or "simple").strip().lower()
        if level not in {"simple", "medium"}:
            level = "simple"
        return {
            "summary": str(result.get("summary") or f"proposal ready for {goal or 'foreground work'}").strip(),
            "goal": goal,
            "guard_condition": guard_condition,
            "workflow_kind": coerce_workflow_kind(str(result.get("workflow_kind") or "managed_flow")),
            "recommended_execution_level": level,
            "confirmation_prompt": str(result.get("confirmation_prompt") or "Review this proposal before building the flow.").strip(),
            "designed_at": now_text(),
        }
    if stage == "review":
        approved = bool(result.get("approved"))
        issues = [str(item or "").strip() for item in list(result.get("issues") or []) if str(item or "").strip()]
        return {
            "approved": approved,
            "summary": str(result.get("summary") or ("review passed" if approved else "review requires changes")).strip(),
            "issues": issues,
            "confirmation_prompt": str(result.get("confirmation_prompt") or ("Review passed. Save this flow." if approved else "Review found issues. Return to build.")).strip(),
            "reviewed_at": now_text(),
        }
    return normalize_manage_result(result, flow_state=flow_state)


def run_design_stage(
    *,
    cfg: dict[str, Any],
    workspace_root: str,
    run_prompt_receipt_fn: Callable[..., Any],
    flow_state: dict[str, Any] | None,
    stage: str,
    goal: str,
    guard_condition: str,
    instruction: str,
    draft: dict[str, Any] | None = None,
    proposal: dict[str, Any] | None = None,
    review_issues: list[str] | None = None,
) -> dict[str, Any]:
    if not cli_provider_available("cursor", cfg):
        raise RuntimeError("Cursor CLI is unavailable for Butler Flow design")
    prompt = build_design_prompt(
        stage=stage,
        flow_state=flow_state,
        goal=goal,
        guard_condition=guard_condition,
        instruction=instruction,
        draft=draft,
        proposal=proposal,
        review_issues=review_issues,
    )
    receipt = run_prompt_receipt_fn(
        prompt,
        workspace_root,
        300,
        cfg,
        {
            "cli": "cursor",
            "_disable_runtime_fallback": True,
            "workflow_id": str((flow_state or {}).get("workflow_id") or "butler_flow.design").strip(),
            "agent_id": f"butler_flow.designer_{str(stage or '').strip() or 'stage'}",
        },
        stream=False,
    )
    payload = normalize_design_result(
        stage,
        _parse_json_object(_receipt_text(receipt)),
        flow_state=flow_state,
    )
    payload["designer_session_id"] = _receipt_thread_id(receipt)
    return payload


def normalize_manage_chat_result(
    result: dict[str, Any],
    *,
    manage_target: str = "",
) -> dict[str, Any]:
    response = str(result.get("response") or result.get("answer") or result.get("summary") or "").strip()
    if not response:
        response = "Manager chat completed."
    action = str(result.get("action") or "none").strip().lower()
    if action not in {"none", "manage_flow"}:
        action = "none"
    action_manage_target = str(result.get("action_manage_target") or result.get("manage_target") or manage_target or "").strip()
    action_instruction = str(result.get("action_instruction") or "").strip()
    action_stage = str(result.get("action_stage") or "").strip().lower()
    action_builtin_mode = str(result.get("action_builtin_mode") or "").strip().lower()
    action_ready = bool(result.get("action_ready"))
    if action == "manage_flow" and action_manage_target and action_instruction:
        action_ready = True
    return {
        "summary": str(result.get("summary") or response).strip(),
        "response": response,
        "manage_target": str(result.get("manage_target") or manage_target or "").strip(),
        "suggested_next_action": str(result.get("suggested_next_action") or "").strip(),
        "should_edit_asset": bool(result.get("should_edit_asset")),
        "edit_hint": str(result.get("edit_hint") or "").strip(),
        "action": action,
        "action_ready": action_ready,
        "action_manage_target": action_manage_target,
        "action_instruction": action_instruction,
        "action_stage": action_stage,
        "action_builtin_mode": action_builtin_mode,
    }


def run_manage_agent(
    *,
    cfg: dict[str, Any],
    workspace_root: str,
    run_prompt_receipt_fn: Callable[..., Any],
    flow_state: dict[str, Any] | None,
    manage_target: str,
    asset_kind: str,
    goal: str,
    guard_condition: str,
    instruction: str,
    stage: str = "commit",
) -> dict[str, Any]:
    if not cli_provider_available("cursor", cfg):
        raise RuntimeError("Cursor CLI is unavailable for Butler Flow manage")
    prompt = build_manage_prompt(
        flow_state=flow_state,
        manage_target=manage_target,
        asset_kind=str(asset_kind or "instance").strip() or "instance",
        goal=goal,
        guard_condition=guard_condition,
        instruction=instruction,
        stage=stage,
    )
    receipt = run_prompt_receipt_fn(
        prompt,
        workspace_root,
        300,
        cfg,
        {
            "cli": "cursor",
            "_disable_runtime_fallback": True,
            "workflow_id": str((flow_state or {}).get("workflow_id") or manage_target or "butler_flow.manage").strip(),
            "agent_id": "butler_flow.manager_agent",
        },
        stream=False,
    )
    payload = normalize_manage_stage_result(
        stage,
        _parse_json_object(_receipt_text(receipt)),
        flow_state=flow_state,
        asset_kind=str(asset_kind or "instance").strip() or "instance",
        manage_target=manage_target,
    )
    payload["manager_session_id"] = _receipt_thread_id(receipt)
    payload["manage_stage"] = normalize_manage_stage(stage)
    return payload


def run_manage_chat_agent(
    *,
    cfg: dict[str, Any],
    workspace_root: str,
    run_prompt_receipt_fn: Callable[..., Any],
    manage_target: str,
    asset_kind: str,
    instruction: str,
    flow_state: dict[str, Any] | None = None,
    asset_definition: dict[str, Any] | None = None,
    asset_rows: list[dict[str, Any]] | None = None,
    manager_session_id: str = "",
) -> dict[str, Any]:
    if not cli_provider_available("codex", cfg):
        raise RuntimeError("Codex CLI is unavailable for Butler Flow manage chat")
    prompt = build_manage_chat_prompt(
        manage_target=manage_target,
        asset_kind=asset_kind,
        instruction=instruction,
        flow_state=flow_state,
        asset_definition=asset_definition,
        asset_rows=asset_rows,
    )
    runtime_request = {
        "cli": "codex",
        "_disable_runtime_fallback": True,
        "workflow_id": str((flow_state or {}).get("workflow_id") or manage_target or "butler_flow.manage_chat").strip(),
        "agent_id": "butler_flow.manager_chat",
        "codex_mode": "resume" if str(manager_session_id or "").strip() else "exec",
        "codex_session_id": str(manager_session_id or "").strip(),
    }
    receipt = run_prompt_receipt_fn(
        prompt,
        workspace_root,
        300,
        cfg,
        runtime_request,
        stream=False,
    )
    payload = normalize_manage_chat_result(
        _parse_json_object(_receipt_text(receipt)),
        manage_target=manage_target,
    )
    payload["manager_session_id"] = _receipt_thread_id(receipt) or str(manager_session_id or "").strip()
    return payload


__all__ = [
    "build_design_prompt",
    "build_manage_chat_prompt",
    "build_manage_prompt",
    "normalize_design_result",
    "normalize_manage_chat_result",
    "normalize_manage_result",
    "normalize_role_guidance_payload",
    "normalize_manage_stage_result",
    "normalize_manage_stage",
    "run_manage_chat_agent",
    "run_design_stage",
    "run_manage_agent",
]
