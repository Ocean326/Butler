from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from butler_main.agents_os.execution.cli_runner import cli_provider_available

from .constants import EXECUTION_CONTEXT_ISOLATED
from .flow_definition import coerce_workflow_kind, normalize_phase_plan, resolve_phase_plan
from .state import (
    asset_bundle_root,
    normalize_control_profile_payload,
    normalize_doctor_policy_payload,
    normalize_source_items,
    normalize_supervisor_profile_payload,
    now_text,
)


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
MANAGE_CHAT_STAGES = ("discuss", "template_prepare", "template_confirm", "flow_prepare", "flow_confirm", "done")
MANAGE_CHAT_CONFIRMATION_SCOPES = ("none", "template", "flow")
MANAGE_CHAT_SKILL_IDS = (
    "discuss_and_scope",
    "template_select_or_create",
    "template_update",
    "flow_spec_finalize",
    "flow_create_or_update",
)

_MANAGER_PROMPT_ROOT = Path(__file__).resolve().with_name("manager_prompt_assets")
_MANAGER_ROLE_PATH = _MANAGER_PROMPT_ROOT / "role.md"
_MANAGER_SKILL_ROOT = _MANAGER_PROMPT_ROOT / "skills"

_MANAGE_CREATE_HINTS = (
    "create",
    "new",
    "spawn",
    "make",
    "build",
    "创建",
    "新建",
    "生成",
    "做一个",
    "做个",
    "建一个",
    "起一个",
)

_MANAGE_UPDATE_HINTS = (
    "update",
    "edit",
    "clone",
    "refine",
    "adjust",
    "modify",
    "完善",
    "补齐",
    "更新",
    "修改",
    "编辑",
    "克隆",
    "细化",
    "重写",
    "改成",
)

_MANAGE_TEMPLATE_HINTS = (
    "template",
    "模板",
)

_MANAGE_FLOW_HINTS = (
    "flow",
    "pending flow",
    "instance",
    "workflow",
    "工作流",
    "托管流",
    "实例",
)

_MANAGE_CONFIRM_HINTS = (
    "confirm",
    "confirmed",
    "go ahead",
    "proceed",
    "yes",
    "ok",
    "okay",
    "确认",
    "同意",
    "按这个",
    "就这样",
    "可以创建",
    "继续创建",
    "创建吧",
    "创建它",
    "好",
    "行",
)

_MANAGE_EXPLAIN_HINTS = (
    "?",
    "？",
    "how",
    "why",
    "what",
    "explain",
    "intro",
    "introduce",
    "phase",
    "介绍",
    "解释",
    "阶段",
    "怎么",
    "如何",
    "为什么",
    "是什么",
    "分析",
    "概括",
    "讨论",
    "建议",
    "修正",
)

_MANAGE_ONE_OFF_HINTS = (
    "one-off",
    "一次性",
    "不用模板",
    "不需要模板",
    "跳过模板",
    "直接创建flow",
    "直接建flow",
)


def normalize_manage_stage(stage: str) -> str:
    token = str(stage or "").strip().lower()
    if token in MANAGE_STAGES:
        return token
    return "commit"


def _contains_hint(text: str, hints: tuple[str, ...]) -> bool:
    normalized = str(text or "").strip().casefold()
    if not normalized:
        return False
    return any(token.casefold() in normalized for token in hints)


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    token = str(value or "").strip().lower()
    if token in {"true", "1", "yes", "y", "on"}:
        return True
    if token in {"false", "0", "no", "n", "off"}:
        return False
    return default


def _read_prompt_asset(path: Path) -> str:
    try:
        return str(path.read_text(encoding="utf-8")).strip()
    except Exception:
        return ""


def _parse_manage_target_token(token: str) -> tuple[str, str]:
    raw = str(token or "").strip()
    if not raw or ":" not in raw:
        return "", raw
    kind, _, asset_id = raw.partition(":")
    return str(kind or "").strip().lower(), str(asset_id or "").strip()


def _asset_kind_from_manage_target(manage_target: str, *, fallback: str = "instance") -> str:
    target_kind, _ = _parse_manage_target_token(manage_target)
    if target_kind in {"template", "builtin", "instance"}:
        return target_kind
    normalized = str(fallback or "").strip().lower()
    if normalized in {"template", "builtin", "instance"}:
        return normalized
    return "instance"


def select_manage_chat_skill(
    *,
    manage_target: str,
    asset_kind: str,
    instruction: str,
) -> str:
    target_kind, target_id = _parse_manage_target_token(manage_target)
    normalized_asset_kind = str(asset_kind or "").strip().lower()
    text = str(instruction or "").strip()
    has_confirm = _contains_hint(text, _MANAGE_CONFIRM_HINTS)
    has_template = _contains_hint(text, _MANAGE_TEMPLATE_HINTS)
    has_flow = _contains_hint(text, _MANAGE_FLOW_HINTS)
    has_create = _contains_hint(text, _MANAGE_CREATE_HINTS)
    has_update = _contains_hint(text, _MANAGE_UPDATE_HINTS)
    has_explain = _contains_hint(text, _MANAGE_EXPLAIN_HINTS)
    one_off = _contains_hint(text, _MANAGE_ONE_OFF_HINTS)

    if target_kind in {"builtin", "template"}:
        if has_flow and has_confirm:
            return "flow_create_or_update"
        if has_flow:
            return "flow_spec_finalize"
        if has_explain and not (has_confirm or has_update or has_create):
            return "discuss_and_scope"
        if target_id == "new":
            return "template_select_or_create"
        if has_confirm or has_update or has_create or target_kind == "builtin":
            return "template_update"
        return "template_update"
    if target_kind == "instance":
        return "flow_create_or_update" if has_confirm else "flow_spec_finalize"
    if one_off and has_flow:
        return "flow_create_or_update" if has_confirm else "flow_spec_finalize"
    if has_flow:
        return "flow_create_or_update" if has_confirm else "template_select_or_create"
    if has_template or has_create or has_update or normalized_asset_kind in {"template", "builtin"}:
        return "template_select_or_create"
    if has_explain:
        return "discuss_and_scope"
    return "discuss_and_scope"


def _resolve_asset_manager_notes(
    *,
    workspace_root: str,
    manage_target: str,
    flow_state: dict[str, Any] | None = None,
    asset_definition: dict[str, Any] | None = None,
) -> str:
    for payload in (asset_definition or {}, flow_state or {}):
        manifest = dict(payload.get("bundle_manifest") or {})
        manager_ref = str(manifest.get("manager_ref") or "").strip()
        if manager_ref:
            text = _read_prompt_asset(Path(manager_ref))
            if text:
                return text
    target_kind, target_id = _parse_manage_target_token(manage_target)
    if target_kind in {"builtin", "template", "instance"} and target_id and target_id != "new":
        bundle_root = asset_bundle_root(workspace_root, asset_kind=target_kind, asset_id=target_id)
        text = _read_prompt_asset(bundle_root / "manager.md")
        if text:
            return text
    return ""


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


def normalize_manage_chat_draft_payload(
    raw: Any,
    *,
    current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(raw or {}) if isinstance(raw, dict) else {}
    existing = dict(current or {})
    workflow_kind = coerce_workflow_kind(str(payload.get("workflow_kind") or existing.get("workflow_kind") or "managed_flow"))
    phase_plan = normalize_phase_plan(
        payload.get("phase_plan") if isinstance(payload.get("phase_plan"), list) else existing.get("phase_plan"),
        workflow_kind=workflow_kind,
    )

    def _text(key: str, *fallback_keys: str) -> str:
        if key in payload:
            return str(payload.get(key) or "").strip()
        for item in fallback_keys:
            if item in payload:
                return str(payload.get(item) or "").strip()
        if key in existing:
            return str(existing.get(key) or "").strip()
        for item in fallback_keys:
            if item in existing:
                return str(existing.get(item) or "").strip()
        return ""

    manage_target = _text("manage_target")
    asset_kind = _asset_kind_from_manage_target(
        manage_target,
        fallback=_text("asset_kind") or str(existing.get("asset_kind") or "").strip(),
    )

    return {
        "manage_target": manage_target,
        "asset_kind": asset_kind,
        "builtin_mode": _text("builtin_mode", "action_builtin_mode"),
        "label": _text("label"),
        "description": _text("description"),
        "workflow_kind": workflow_kind,
        "goal": _text("goal"),
        "guard_condition": _text("guard_condition"),
        "phase_plan": phase_plan,
        "review_checklist": _dedupe_text_list(payload.get("review_checklist") or existing.get("review_checklist") or []),
        "role_guidance": normalize_role_guidance_payload(
            payload.get("role_guidance") or {},
            current=dict(existing.get("role_guidance") or {}),
        ),
        "doctor_policy": normalize_doctor_policy_payload(
            payload.get("doctor_policy"),
            current=dict(existing.get("doctor_policy") or {}),
        ),
        "control_profile": normalize_control_profile_payload(
            payload.get("control_profile"),
            current=dict(existing.get("control_profile") or {}),
            workflow_kind=workflow_kind,
        ),
        "supervisor_profile": normalize_supervisor_profile_payload(
            payload.get("supervisor_profile"),
            current=dict(existing.get("supervisor_profile") or {}),
        ),
        "run_brief": _text("run_brief", "supervisor_brief"),
        "source_bindings": normalize_source_items(
            payload.get("source_bindings") or payload.get("sources") or [],
            current=list(existing.get("source_bindings") or []),
        ),
        "summary": _text("summary"),
    }


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
            '    "suggested_specialists": ["creator","doctor","product-manager","user-simulator"],\n'
            '    "activation_hints": ["when capability, environment, runtime, or session gaps block progress"],\n'
            '    "promotion_candidates": ["creator"],\n'
            '    "manager_notes": "lightweight advisory notes only"\n'
            "  },\n"
            '  "control_profile": {\n'
            '    "task_archetype": "repo_delivery | research_writing | product_iteration | general",\n'
            '    "packet_size": "small | medium | large",\n'
            '    "evidence_level": "minimal | standard | strict",\n'
            '    "gate_cadence": "phase | risk_based | strict",\n'
            '    "repo_binding_policy": "disabled | explicit",\n'
            '    "repo_contract_paths": ["optional explicit repo contracts such as AGENTS.md"],\n'
            '    "manager_notes": "why this control profile fits the task"\n'
            "  },\n"
            '  "doctor_policy": {\n'
            '    "enabled": true,\n'
            '    "activation_rules": ["repeated_service_fault","same_resume_failure","session_binding_invalid"],\n'
            '    "repair_scope": "runtime_assets_first",\n'
            '    "framework_bug_action": "pause",\n'
            '    "max_rounds_per_episode": 1\n'
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
        '    "suggested_specialists": ["creator","doctor","product-manager","user-simulator"],\n'
        '    "activation_hints": ["when capability, environment, runtime, or session gaps block progress"],\n'
        '    "promotion_candidates": ["creator"],\n'
        '    "manager_notes": "lightweight advisory notes only"\n'
        "  },\n"
        '  "control_profile": {\n'
        '    "task_archetype": "repo_delivery | research_writing | product_iteration | general",\n'
        '    "packet_size": "small | medium | large",\n'
        '    "evidence_level": "minimal | standard | strict",\n'
        '    "gate_cadence": "phase | risk_based | strict",\n'
        '    "repo_binding_policy": "disabled | explicit",\n'
        '    "repo_contract_paths": ["optional explicit repo contracts such as AGENTS.md"],\n'
        '    "manager_notes": "why this control profile fits the task"\n'
        "  },\n"
        '  "doctor_policy": {\n'
        '    "enabled": true,\n'
        '    "activation_rules": ["repeated_service_fault","same_resume_failure","session_binding_invalid"],\n'
        '    "repair_scope": "runtime_assets_first",\n'
        '    "framework_bug_action": "pause",\n'
        '    "max_rounds_per_episode": 1\n'
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
        "- Use doctor_policy only as a lightweight recovery hint for supervisor runtime repair, not as a heavyweight governance layer.\n"
        "- The summary should read like a user handoff note.\n\n"
        f"Negotiation payload:\n{_compact_json(payload)}\n"
    )


def build_manage_chat_prompt(
    *,
    workspace_root: str,
    manage_target: str,
    asset_kind: str,
    instruction: str,
    flow_state: dict[str, Any] | None = None,
    asset_definition: dict[str, Any] | None = None,
    asset_rows: list[dict[str, Any]] | None = None,
    manager_session: dict[str, Any] | None = None,
    current_draft: dict[str, Any] | None = None,
    pending_action: dict[str, Any] | None = None,
    selected_skill: str = "",
    manager_role_text: str | None = None,
    skill_prompt_text: str | None = None,
    asset_manager_notes: str | None = None,
) -> str:
    skill_id = str(selected_skill or "").strip().lower() or select_manage_chat_skill(
        manage_target=manage_target,
        asset_kind=asset_kind,
        instruction=instruction,
    )
    if skill_id not in MANAGE_CHAT_SKILL_IDS:
        skill_id = "discuss_and_scope"
    role_text = str(manager_role_text).strip() if manager_role_text is not None else _read_prompt_asset(_MANAGER_ROLE_PATH)
    skill_text = (
        str(skill_prompt_text).strip()
        if skill_prompt_text is not None
        else _read_prompt_asset(_MANAGER_SKILL_ROOT / f"{skill_id}.md")
    )
    manager_notes_text = (
        str(asset_manager_notes).strip()
        if asset_manager_notes is not None
        else _resolve_asset_manager_notes(
            workspace_root=workspace_root,
            manage_target=manage_target,
            flow_state=flow_state,
            asset_definition=asset_definition,
        )
    )
    payload = {
        "manage_target": str(manage_target or "").strip(),
        "asset_kind": str(asset_kind or "").strip(),
        "selected_skill": skill_id,
        "default_creation_path": "template_first_then_flow",
        "current_flow_state": dict(flow_state or {}),
        "asset_definition": dict(asset_definition or {}),
        "asset_index": [dict(row or {}) for row in list(asset_rows or [])[:12]],
        "manager_session": dict(manager_session or {}),
        "current_draft": dict(current_draft or {}),
        "pending_action": dict(pending_action or {}),
        "asset_manager_notes_present": bool(manager_notes_text),
        "user_instruction": str(instruction or "").strip(),
        "protocol": [
            "answer the operator's question directly",
            "if a specific asset is targeted, ground the answer in that asset's phases, static fields, lineage, bundle, and handoff",
            "default to template-first: discuss -> template shaping -> template confirm -> flow shaping -> flow confirm -> execute",
            "before creating a flow, align the template, goal, and supervisor prompt direction",
            "keep a structured draft of the current template/flow plan",
            "if there is an existing pending action, either refine that draft or confirm it; do not silently replace it",
            "only set action_ready=true when the operator has explicitly confirmed the current management action in this session",
            "treat role guidance and doctor policy as lightweight defaults, not a rigid team contract",
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
        '  "manager_stage": "discuss" | "template_prepare" | "template_confirm" | "flow_prepare" | "flow_confirm" | "done",\n'
        '  "active_skill": "discuss_and_scope" | "template_select_or_create" | "template_update" | "flow_spec_finalize" | "flow_create_or_update",\n'
        '  "confirmation_scope": "none" | "template" | "flow",\n'
        '  "confirmation_prompt": "the sentence the operator should confirm or answer next",\n'
        '  "suggested_next_action": "optional short next step",\n'
        '  "reuse_decision": "reuse_existing_template" | "update_existing_template" | "create_new_template" | "one_off_flow" | "defer",\n'
        '  "should_edit_asset": true | false,\n'
        '  "edit_hint": "optional concise edit guidance",\n'
        '  "draft": {\n'
        '    "manage_target": "template:new | template:<id> | new | instance:<id> | builtin:<id>",\n'
        '    "asset_kind": "template | instance | builtin",\n'
        '    "builtin_mode": "optional clone|edit",\n'
        '    "label": "optional label",\n'
        '    "description": "optional description",\n'
        '    "workflow_kind": "managed_flow | project_loop | single_goal",\n'
        '    "goal": "draft goal",\n'
        '    "guard_condition": "draft guard condition",\n'
        '    "phase_plan": [],\n'
        '    "review_checklist": [],\n'
        '    "role_guidance": {},\n'
        '    "control_profile": {},\n'
        '    "supervisor_profile": {},\n'
        '    "run_brief": "optional run brief",\n'
        '    "source_bindings": []\n'
        '  },\n'
        '  "pending_action_preview": "short preview of the mutation waiting for confirmation",\n'
        '  "supervisor_profile_preview": "short preview of supervisor tuning or empty",\n'
        '  "action": "none" | "manage_flow",\n'
        '  "action_ready": true | false,\n'
        '  "action_manage_target": "resolved manage target for manage_flow or empty string",\n'
        '  "action_instruction": "instruction text to pass into manage_flow or empty string",\n'
        '  "action_stage": "optional manage stage",\n'
        '  "action_builtin_mode": "optional builtin mode clone|edit"\n'
        "}\n\n"
        "Manager role instructions:\n"
        f"{role_text or '- missing manager role prompt -'}\n\n"
        f"Active skill · {skill_id}\n"
        f"{skill_text or '- missing manager skill prompt -'}\n\n"
        + (
            f"Asset-specific manager notes:\n{manager_notes_text}\n\n"
            if manager_notes_text
            else ""
        )
        + "Operational rules:\n"
        "- 这里是 Manage Center 的 chat mode，默认先讨论、再整理管理动作。\n"
        "- 默认新需求都先走 template-first；除非用户明确说这是 one-off，不需要沉淀 template。\n"
        "- 在创建 flow 之前，先处理 template 选择/修改，并把 goal / guard / supervisor 方向理顺。\n"
        "- `draft` 是当前真正在讨论的结构化草稿，尽量始终保持更新。\n"
        "- `control_profile` 用来表达 supervisor 的控制哲学：工作包大小、证据强度、gate 节奏，以及 repo 合同是否显式绑定。\n"
        "- `supervisor_profile` 只保留精选原则：项目风格、质量门槛、风险偏置、review 关注点与 done policy。\n"
        "- 默认不要把仓库级 `AGENTS.md` 当作环境里天然生效的强约束；只有真的需要时，才把它放进 `control_profile.repo_contract_paths` 作为显式 repo contract。\n"
        "- `source_bindings` 只保留对当前 template/flow 真有帮助的上下文来源，不要堆满。\n"
        "- 用 manager_stage 明确表示你现在处在哪一步。\n"
        "- 用 confirmation_scope 明确告诉用户你现在要确认的是 template 还是 flow。\n"
        "- action=manage_flow 只表示“当前这个具体 mutation 已经准备好执行”。\n"
        "- action_ready=true 只在用户已经明确确认当前 mutation 后才能出现。\n"
        "- 首次给出 draft 时，正常也应该保持 action_ready=false；先让用户看草稿摘要和待确认动作。\n"
        "- 处理 template 时，action_manage_target 应是 template:new、template:<id>，或带明确 clone/edit 的 builtin:<id>。\n"
        "- 处理 flow 时，action_manage_target 通常应是 new 或具体实例 key。\n"
        "- 如果用户是在问解释、审阅、比较、建议，先回答，不要跳过确认直接执行。\n"
        "- 回复要自然、清楚、面向用户，不要像机器状态机。\n\n"
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
    doctor_policy = normalize_doctor_policy_payload(
        result.get("doctor_policy"),
        current=dict(current.get("doctor_policy") or dict(current.get("manage_handoff") or {}).get("doctor_policy") or {}),
    )
    control_profile = normalize_control_profile_payload(
        result.get("control_profile"),
        current=dict(current.get("control_profile") or dict(current.get("manage_handoff") or {}).get("control_profile") or {}),
        workflow_kind=workflow_kind,
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
        "control_profile": control_profile,
        "doctor_policy": doctor_policy,
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
            "execution_context": EXECUTION_CONTEXT_ISOLATED,
            "execution_scope_id": str((flow_state or {}).get("workflow_id") or f"butler_flow.design.{stage or 'stage'}").strip(),
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
    current_draft: dict[str, Any] | None = None,
    parse_status: str = "ok",
    raw_reply: str = "",
    error_text: str = "",
) -> dict[str, Any]:
    normalized_parse_status = str(parse_status or result.get("parse_status") or "ok").strip().lower() or "ok"
    normalized_raw_reply = str(raw_reply or result.get("raw_reply") or "").strip()
    normalized_error_text = str(error_text or result.get("error_text") or "").strip()
    response = str(result.get("response") or result.get("answer") or result.get("summary") or "").strip()
    if normalized_parse_status != "ok" and normalized_raw_reply:
        response = normalized_raw_reply
    if not response:
        response = "Manager chat completed."
    action = str(result.get("action") or "none").strip().lower()
    if action not in {"none", "manage_flow"}:
        action = "none"
    manager_stage = str(result.get("manager_stage") or "discuss").strip().lower()
    if manager_stage not in MANAGE_CHAT_STAGES:
        manager_stage = "discuss"
    active_skill = str(result.get("active_skill") or "").strip().lower()
    if active_skill not in MANAGE_CHAT_SKILL_IDS:
        active_skill = ""
    confirmation_scope = str(result.get("confirmation_scope") or "none").strip().lower()
    if confirmation_scope not in MANAGE_CHAT_CONFIRMATION_SCOPES:
        confirmation_scope = "none"
    confirmation_prompt = str(result.get("confirmation_prompt") or "").strip()
    action_manage_target = str(result.get("action_manage_target") or result.get("manage_target") or manage_target or "").strip()
    action_instruction = str(result.get("action_instruction") or "").strip()
    action_stage = str(result.get("action_stage") or "").strip().lower()
    action_builtin_mode = str(result.get("action_builtin_mode") or "").strip().lower()
    action_ready = _coerce_bool(result.get("action_ready"), default=False)
    if action == "manage_flow" and (not action_manage_target or not action_instruction):
        action_ready = False
    draft = normalize_manage_chat_draft_payload(result.get("draft"), current=current_draft)
    if not str(draft.get("manage_target") or "").strip():
        draft["manage_target"] = action_manage_target or str(result.get("manage_target") or manage_target or "").strip()
    draft["asset_kind"] = _asset_kind_from_manage_target(
        str(draft.get("manage_target") or "").strip(),
        fallback=str(draft.get("asset_kind") or "").strip(),
    )
    return {
        "summary": str(result.get("summary") or response).strip(),
        "response": response,
        "parse_status": normalized_parse_status,
        "raw_reply": normalized_raw_reply,
        "error_text": normalized_error_text,
        "manage_target": str(result.get("manage_target") or manage_target or "").strip(),
        "manager_stage": manager_stage,
        "active_skill": active_skill,
        "confirmation_scope": confirmation_scope,
        "confirmation_prompt": confirmation_prompt,
        "suggested_next_action": str(result.get("suggested_next_action") or "").strip(),
        "reuse_decision": str(result.get("reuse_decision") or "").strip(),
        "should_edit_asset": _coerce_bool(result.get("should_edit_asset"), default=False),
        "edit_hint": str(result.get("edit_hint") or "").strip(),
        "draft": draft,
        "pending_action_preview": str(result.get("pending_action_preview") or "").strip(),
        "supervisor_profile_preview": str(result.get("supervisor_profile_preview") or "").strip(),
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
            "execution_context": EXECUTION_CONTEXT_ISOLATED,
            "execution_scope_id": str(manage_target or (flow_state or {}).get("workflow_id") or "butler_flow.manage").strip(),
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
    manager_session: dict[str, Any] | None = None,
    current_draft: dict[str, Any] | None = None,
    pending_action: dict[str, Any] | None = None,
    manager_session_id: str = "",
) -> dict[str, Any]:
    if not cli_provider_available("codex", cfg):
        raise RuntimeError("Codex CLI is unavailable for Butler Flow manage chat")
    prompt = build_manage_chat_prompt(
        workspace_root=workspace_root,
        manage_target=manage_target,
        asset_kind=asset_kind,
        instruction=instruction,
        flow_state=flow_state,
        asset_definition=asset_definition,
        asset_rows=asset_rows,
        manager_session=manager_session,
        current_draft=current_draft,
        pending_action=pending_action,
    )
    runtime_request = {
        "cli": "codex",
        "_disable_runtime_fallback": True,
        "workflow_id": str((flow_state or {}).get("workflow_id") or manage_target or "butler_flow.manage_chat").strip(),
        "agent_id": "butler_flow.manager_chat",
        "codex_mode": "resume" if str(manager_session_id or "").strip() else "exec",
        "codex_session_id": str(manager_session_id or "").strip(),
        "execution_context": EXECUTION_CONTEXT_ISOLATED,
        "execution_scope_id": str(manager_session_id or manage_target or "butler_flow.manage_chat").strip(),
    }
    receipt = run_prompt_receipt_fn(
        prompt,
        workspace_root,
        300,
        cfg,
        runtime_request,
        stream=False,
    )
    raw_reply = _receipt_text(receipt)
    parsed = _parse_json_object(raw_reply)
    parse_status = "ok" if parsed else ("failed" if raw_reply else "empty")
    error_text = "manager chat returned non-JSON output" if parse_status == "failed" else ""
    payload = normalize_manage_chat_result(
        parsed,
        manage_target=manage_target,
        current_draft=current_draft,
        parse_status=parse_status,
        raw_reply=raw_reply,
        error_text=error_text,
    )
    payload["manager_session_id"] = _receipt_thread_id(receipt) or str(manager_session_id or "").strip()
    return payload


__all__ = [
    "build_design_prompt",
    "build_manage_chat_prompt",
    "build_manage_prompt",
    "normalize_design_result",
    "normalize_manage_chat_result",
    "normalize_manage_chat_draft_payload",
    "normalize_manage_result",
    "normalize_role_guidance_payload",
    "normalize_manage_stage_result",
    "normalize_manage_stage",
    "run_manage_chat_agent",
    "run_design_stage",
    "run_manage_agent",
    "select_manage_chat_skill",
]
