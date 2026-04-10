from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from butler_main.agents_os.execution.cli_runner import cli_provider_available

from .constants import EXECUTION_CONTEXT_ISOLATED
from .flow_definition import coerce_workflow_kind, normalize_phase_plan, resolve_phase_plan
from .runtime import flow_codex_config_overrides
from .state import (
    asset_bundle_root,
    normalize_control_profile_payload,
    normalize_doctor_policy_payload,
    normalize_source_items,
    normalize_supervisor_profile_payload,
    now_text,
    prepare_manage_codex_home,
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


def _receipt_metadata(receipt: Any) -> dict[str, Any]:
    return dict(getattr(receipt, "metadata", {}) or {})


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
_MANAGER_REFERENCE_ROOT = _MANAGER_PROMPT_ROOT / "references"

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


@dataclass(frozen=True)
class ManagerSkillSpec:
    skill_id: str
    purpose: str
    allowed_scopes: tuple[str, ...]
    allowed_targets: tuple[str, ...]
    draft_fields_owned: tuple[str, ...]
    can_prepare_action: bool
    can_mark_ready: bool
    reference_keys: tuple[str, ...]
    fallback_stage: str
    confirmation_scope: str


_MANAGER_SKILL_REGISTRY: dict[str, ManagerSkillSpec] = {
    "discuss_and_scope": ManagerSkillSpec(
        skill_id="discuss_and_scope",
        purpose="Answer, clarify scope, and decide whether the next step belongs to template or flow.",
        allowed_scopes=("discuss",),
        allowed_targets=("workspace", "template", "builtin", "instance"),
        draft_fields_owned=("summary",),
        can_prepare_action=False,
        can_mark_ready=False,
        reference_keys=(),
        fallback_stage="discuss",
        confirmation_scope="none",
    ),
    "template_select_or_create": ManagerSkillSpec(
        skill_id="template_select_or_create",
        purpose="Choose between reusing, lightly modifying, or creating a reusable template.",
        allowed_scopes=("template",),
        allowed_targets=("workspace", "template", "builtin"),
        draft_fields_owned=(
            "manage_target",
            "asset_kind",
            "builtin_mode",
            "label",
            "description",
            "workflow_kind",
            "goal",
            "guard_condition",
            "phase_plan",
            "review_checklist",
            "role_guidance",
            "doctor_policy",
            "control_profile",
            "supervisor_profile",
            "source_bindings",
            "summary",
        ),
        can_prepare_action=True,
        can_mark_ready=False,
        reference_keys=("template-static-fields", "supervisor-design", "role-guidance", "source-bindings"),
        fallback_stage="template_prepare",
        confirmation_scope="template",
    ),
    "template_update": ManagerSkillSpec(
        skill_id="template_update",
        purpose="Update an existing template or decide builtin clone/edit behavior before any flow mutation.",
        allowed_scopes=("template",),
        allowed_targets=("template", "builtin"),
        draft_fields_owned=(
            "manage_target",
            "asset_kind",
            "builtin_mode",
            "label",
            "description",
            "workflow_kind",
            "goal",
            "guard_condition",
            "phase_plan",
            "review_checklist",
            "role_guidance",
            "doctor_policy",
            "control_profile",
            "supervisor_profile",
            "source_bindings",
            "summary",
        ),
        can_prepare_action=True,
        can_mark_ready=False,
        reference_keys=("template-static-fields", "supervisor-design", "builtin-mutation", "role-guidance", "source-bindings"),
        fallback_stage="template_prepare",
        confirmation_scope="template",
    ),
    "flow_spec_finalize": ManagerSkillSpec(
        skill_id="flow_spec_finalize",
        purpose="Finalize the current run's flow-specific spec after the template path is settled.",
        allowed_scopes=("flow",),
        allowed_targets=("workspace", "template", "instance"),
        draft_fields_owned=(
            "manage_target",
            "asset_kind",
            "workflow_kind",
            "goal",
            "guard_condition",
            "phase_plan",
            "review_checklist",
            "control_profile",
            "supervisor_profile",
            "run_brief",
            "source_bindings",
            "summary",
        ),
        can_prepare_action=False,
        can_mark_ready=False,
        reference_keys=("flow-static-fields", "supervisor-design", "source-bindings"),
        fallback_stage="flow_prepare",
        confirmation_scope="flow",
    ),
    "flow_create_or_update": ManagerSkillSpec(
        skill_id="flow_create_or_update",
        purpose="Turn a confirmed flow draft into a concrete create/update proposal.",
        allowed_scopes=("flow",),
        allowed_targets=("workspace", "template", "instance"),
        draft_fields_owned=(
            "manage_target",
            "asset_kind",
            "workflow_kind",
            "goal",
            "guard_condition",
            "phase_plan",
            "review_checklist",
            "control_profile",
            "supervisor_profile",
            "run_brief",
            "source_bindings",
            "summary",
        ),
        can_prepare_action=True,
        can_mark_ready=False,
        reference_keys=("flow-static-fields", "supervisor-design", "source-bindings"),
        fallback_stage="flow_confirm",
        confirmation_scope="flow",
    ),
}

_MANAGER_REFERENCE_FILES = {
    "template-static-fields": _MANAGER_REFERENCE_ROOT / "template-static-fields.md",
    "flow-static-fields": _MANAGER_REFERENCE_ROOT / "flow-static-fields.md",
    "supervisor-design": _MANAGER_REFERENCE_ROOT / "supervisor-design.md",
    "role-guidance": _MANAGER_REFERENCE_ROOT / "role-guidance.md",
    "source-bindings": _MANAGER_REFERENCE_ROOT / "source-bindings.md",
    "builtin-mutation": _MANAGER_REFERENCE_ROOT / "builtin-mutation.md",
}


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


def _manager_skill_spec(skill_id: str) -> ManagerSkillSpec:
    token = str(skill_id or "").strip().lower()
    return _MANAGER_SKILL_REGISTRY.get(token, _MANAGER_SKILL_REGISTRY["discuss_and_scope"])


def _truncate_text(value: Any, *, limit: int = 160) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _compact_text_list(values: Any, *, limit: int = 4, item_limit: int = 72) -> list[str]:
    rows = _dedupe_text_list(values)
    return [_truncate_text(item, limit=item_limit) for item in rows[:limit]]


def _manage_target_scope(manage_target: str, *, asset_kind: str = "") -> str:
    target_kind, _ = _parse_manage_target_token(manage_target)
    if target_kind in {"template", "builtin", "instance"}:
        return target_kind
    normalized_asset_kind = str(asset_kind or "").strip().lower()
    if normalized_asset_kind in {"template", "builtin", "instance"}:
        return normalized_asset_kind
    return "workspace"


def _asset_summary_from_payload(payload: dict[str, Any] | None, *, fallback_target: str = "", asset_kind: str = "") -> dict[str, Any]:
    current = dict(payload or {})
    summary: dict[str, Any] = {}
    manage_target = str(
        current.get("manage_target")
        or current.get("asset_key")
        or current.get("source_asset_key")
        or fallback_target
        or ""
    ).strip()
    if manage_target:
        summary["manage_target"] = manage_target
    resolved_asset_kind = _asset_kind_from_manage_target(
        manage_target,
        fallback=str(current.get("asset_kind") or asset_kind or "").strip(),
    )
    if resolved_asset_kind:
        summary["asset_kind"] = resolved_asset_kind
    for key in ("label", "workflow_kind", "updated_at", "created_at", "role_pack_id", "execution_mode", "session_strategy"):
        value = str(current.get(key) or "").strip()
        if value:
            summary[key] = value
    for key in ("description", "goal", "guard_condition", "run_brief"):
        value = _truncate_text(current.get(key), limit=180 if key == "description" else 220)
        if value:
            summary[key] = value
    control_profile = dict(current.get("control_profile") or {})
    if control_profile:
        summary["control_profile"] = {
            "task_archetype": str(control_profile.get("task_archetype") or "").strip(),
            "packet_size": str(control_profile.get("packet_size") or "").strip(),
            "evidence_level": str(control_profile.get("evidence_level") or "").strip(),
            "gate_cadence": str(control_profile.get("gate_cadence") or "").strip(),
            "repo_binding_policy": str(control_profile.get("repo_binding_policy") or "").strip(),
            "repo_contract_paths": [
                str(item or "").strip()
                for item in list(control_profile.get("repo_contract_paths") or [])[:3]
                if str(item or "").strip()
            ],
        }
    role_guidance = dict(current.get("role_guidance") or {})
    if role_guidance:
        summary["role_guidance"] = {
            "suggested_roles": _compact_text_list(role_guidance.get("suggested_roles") or [], limit=4, item_limit=48),
            "suggested_specialists": _compact_text_list(role_guidance.get("suggested_specialists") or [], limit=4, item_limit=48),
        }
    source_bindings = list(current.get("source_bindings") or [])
    if source_bindings:
        summary["source_bindings"] = [
            {
                "kind": str(item.get("kind") or "").strip(),
                "path": _truncate_text(item.get("path"), limit=96),
                "label": _truncate_text(item.get("label"), limit=64),
            }
            for item in source_bindings[:3]
            if isinstance(item, dict)
        ]
    asset_state = dict(current.get("asset_state") or {})
    if asset_state:
        summary["asset_state"] = {
            key: str(asset_state.get(key) or "").strip()
            for key in ("status", "stage", "mode")
            if str(asset_state.get(key) or "").strip()
        }
    lineage = dict(current.get("lineage") or {})
    if lineage:
        summary["lineage"] = {
            key: _truncate_text(value, limit=96)
            for key, value in lineage.items()
            if _truncate_text(value, limit=96)
        }
    return summary


def _compile_asset_catalog_summary(
    asset_rows: list[dict[str, Any]] | None,
    *,
    manage_target: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    rows = list(asset_rows or [])
    prioritized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        asset_key = str(dict(row or {}).get("asset_key") or "").strip()
        if asset_key == str(manage_target or "").strip():
            prioritized.append(dict(row or {}))
            seen.add(asset_key)
            break
    for row in rows:
        asset_key = str(dict(row or {}).get("asset_key") or "").strip()
        if asset_key in seen:
            continue
        prioritized.append(dict(row or {}))
        seen.add(asset_key)
        if len(prioritized) >= limit:
            break
    return [
        _asset_summary_from_payload(row, fallback_target=str(row.get("asset_key") or "").strip())
        for row in prioritized[:limit]
    ]


def _compile_manager_session_summary(manager_session: dict[str, Any] | None) -> dict[str, Any]:
    session = dict(manager_session or {})
    summary: dict[str, Any] = {}
    for key in ("manager_session_id", "active_manage_target", "manager_stage", "confirmation_scope", "updated_at"):
        value = str(session.get(key) or "").strip()
        if value:
            summary[key] = value
    return summary


def _compile_pending_action_summary(pending_action: dict[str, Any] | None) -> dict[str, Any]:
    current = dict(pending_action or {})
    if not current:
        return {}
    summary = {
        "manage_target": str(current.get("manage_target") or "").strip(),
        "stage": str(current.get("stage") or "").strip(),
        "builtin_mode": str(current.get("builtin_mode") or "").strip(),
        "preview": _truncate_text(current.get("preview") or current.get("draft_summary") or "", limit=220),
        "instruction": _truncate_text(current.get("instruction") or "", limit=240),
    }
    draft = dict(current.get("draft") or {})
    if draft:
        summary["draft_snapshot"] = _asset_summary_from_payload(
            draft,
            fallback_target=str(draft.get("manage_target") or summary["manage_target"]).strip(),
        )
    return {key: value for key, value in summary.items() if value}


def _compile_manager_references(skill_id: str) -> list[dict[str, str]]:
    spec = _manager_skill_spec(skill_id)
    references: list[dict[str, str]] = []
    for key in spec.reference_keys:
        path = _MANAGER_REFERENCE_FILES.get(key)
        if not path:
            continue
        text = _read_prompt_asset(path)
        if not text:
            continue
        references.append({"key": key, "text": text})
    return references


def _manage_chat_runtime_request(
    *,
    cfg: dict[str, Any],
    workspace_root: str,
    flow_state: dict[str, Any] | None,
    manage_target: str,
    manager_session_id: str = "",
) -> dict[str, Any]:
    request = {
        "cli": "codex",
        "_disable_runtime_fallback": True,
        "workflow_id": str((flow_state or {}).get("workflow_id") or manage_target or "butler_flow.manage_chat").strip(),
        "agent_id": "butler_flow.manager_chat",
        "codex_mode": "resume" if str(manager_session_id or "").strip() else "exec",
        "codex_session_id": str(manager_session_id or "").strip(),
        "codex_home": str(prepare_manage_codex_home(workspace_root)),
        "execution_context": EXECUTION_CONTEXT_ISOLATED,
        "execution_scope_id": str(manager_session_id or manage_target or "butler_flow.manage_chat").strip(),
    }
    overrides = flow_codex_config_overrides(cfg)
    if overrides:
        request["config_overrides"] = overrides
    return request


def _is_manage_chat_resume_recoverable(receipt: Any, *, raw_reply: str) -> bool:
    metadata = _receipt_metadata(receipt)
    external_session = dict(metadata.get("external_session") or {})
    vendor_session_state = str(external_session.get("vendor_session_state") or "").strip().lower()
    if bool(external_session.get("resume_failed")) or vendor_session_state == "resume_failed":
        return True
    lowered = str(raw_reply or "").strip().lower()
    markers = (
        "thread/resume failed",
        "no rollout found",
        "resume session not found",
        "timeout waiting for child process to exit",
        "codex 子进程退出超时",
        "reconnecting...",
        "stream disconnected before completion",
    )
    return any(marker in lowered for marker in markers)


def _payload_from_manage_chat_receipt(
    receipt: Any,
    *,
    manage_target: str,
    current_draft: dict[str, Any] | None,
    selected_skill: str = "",
    fallback_manager_session_id: str = "",
) -> tuple[dict[str, Any], str, str]:
    raw_reply = _receipt_text(receipt)
    parsed = _parse_json_object(raw_reply)
    parse_status = "ok" if parsed else ("failed" if raw_reply else "empty")
    error_text = "manager chat returned non-JSON output" if parse_status == "failed" else ""
    payload = normalize_manage_chat_result(
        parsed,
        manage_target=manage_target,
        current_draft=current_draft,
        selected_skill=selected_skill,
        parse_status=parse_status,
        raw_reply=raw_reply,
        error_text=error_text,
    )
    payload["manager_session_id"] = _receipt_thread_id(receipt) or str(fallback_manager_session_id or "").strip()
    return payload, raw_reply, parse_status


def select_manage_chat_skill(
    *,
    manage_target: str,
    asset_kind: str,
    instruction: str,
    manager_session: dict[str, Any] | None = None,
    current_draft: dict[str, Any] | None = None,
    pending_action: dict[str, Any] | None = None,
) -> str:
    target_kind, target_id = _parse_manage_target_token(manage_target)
    normalized_asset_kind = str(asset_kind or "").strip().lower()
    session = dict(manager_session or {})
    draft = dict(current_draft or {})
    pending = dict(pending_action or {})
    text = str(instruction or "").strip()
    has_confirm = _contains_hint(text, _MANAGE_CONFIRM_HINTS)
    has_template = _contains_hint(text, _MANAGE_TEMPLATE_HINTS)
    has_flow = _contains_hint(text, _MANAGE_FLOW_HINTS)
    has_create = _contains_hint(text, _MANAGE_CREATE_HINTS)
    has_update = _contains_hint(text, _MANAGE_UPDATE_HINTS)
    has_explain = _contains_hint(text, _MANAGE_EXPLAIN_HINTS)
    one_off = _contains_hint(text, _MANAGE_ONE_OFF_HINTS)
    confirmation_scope = str(session.get("confirmation_scope") or "").strip().lower()
    draft_target_kind, _ = _parse_manage_target_token(str(draft.get("manage_target") or "").strip())
    draft_workflow_kind = str(draft.get("workflow_kind") or "").strip().lower()

    if pending:
        if confirmation_scope == "template":
            return "template_update" if target_kind in {"template", "builtin"} or draft_target_kind in {"template", "builtin"} else "template_select_or_create"
        if confirmation_scope == "flow":
            return "flow_create_or_update" if has_confirm else "flow_spec_finalize"
    if confirmation_scope == "template":
        return "template_update" if target_kind in {"template", "builtin"} or draft_target_kind in {"template", "builtin"} else "template_select_or_create"
    if confirmation_scope == "flow":
        return "flow_spec_finalize"

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
    if draft_target_kind in {"template", "builtin"} and draft_workflow_kind:
        if has_flow:
            return "flow_create_or_update" if has_confirm else "flow_spec_finalize"
        return "template_update"
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


def _filter_draft_by_skill_ownership(
    raw_draft: Any,
    *,
    current_draft: dict[str, Any] | None,
    active_skill: str,
) -> dict[str, Any]:
    baseline = normalize_manage_chat_draft_payload(current_draft, current=None)
    normalized = normalize_manage_chat_draft_payload(raw_draft, current=baseline)
    if not isinstance(raw_draft, dict):
        return normalized
    allowed = set(_manager_skill_spec(active_skill).draft_fields_owned)
    for key in list(normalized.keys()):
        if key not in allowed:
            normalized[key] = baseline.get(key)
    return normalized


def _validate_manage_chat_action(
    *,
    action: str,
    action_ready: bool,
    action_manage_target: str,
    action_instruction: str,
    action_builtin_mode: str,
    active_skill: str,
) -> tuple[str, bool, str, str, str]:
    spec = _manager_skill_spec(active_skill)
    normalized_action = str(action or "none").strip().lower()
    normalized_ready = bool(action_ready)
    normalized_target = str(action_manage_target or "").strip()
    normalized_instruction = str(action_instruction or "").strip()
    normalized_builtin_mode = str(action_builtin_mode or "").strip().lower()
    if normalized_action != "manage_flow" or not spec.can_prepare_action:
        return "none", False, "", "", ""
    target_scope = _manage_target_scope(normalized_target)
    if target_scope not in spec.allowed_targets:
        return "none", False, "", "", ""
    if target_scope == "builtin" and normalized_builtin_mode not in {"clone", "edit"}:
        normalized_ready = False
    if not normalized_target or not normalized_instruction:
        normalized_ready = False
    if normalized_ready and not spec.can_mark_ready:
        normalized_ready = False
    return normalized_action, normalized_ready, normalized_target, normalized_instruction, normalized_builtin_mode


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
        manager_session=manager_session,
        current_draft=current_draft,
        pending_action=pending_action,
    )
    spec = _manager_skill_spec(skill_id)
    skill_id = spec.skill_id
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
    current_target_summary = _asset_summary_from_payload(
        asset_definition or flow_state or {},
        fallback_target=manage_target,
        asset_kind=asset_kind,
    )
    if not current_target_summary and manage_target:
        current_target_summary = {
            "manage_target": str(manage_target or "").strip(),
            "asset_kind": _asset_kind_from_manage_target(manage_target, fallback=asset_kind),
        }
    payload = {
        "manage_target": str(manage_target or "").strip(),
        "asset_kind": str(asset_kind or "").strip(),
        "selected_skill": skill_id,
        "skill_contract": {
            "purpose": spec.purpose,
            "allowed_scopes": list(spec.allowed_scopes),
            "allowed_targets": list(spec.allowed_targets),
            "draft_fields_owned": list(spec.draft_fields_owned),
            "can_prepare_action": spec.can_prepare_action,
            "can_mark_ready": spec.can_mark_ready,
            "fallback_stage": spec.fallback_stage,
            "confirmation_scope": spec.confirmation_scope,
        },
        "default_creation_path": "template_first_then_flow",
        "current_target_summary": current_target_summary,
        "asset_catalog": _compile_asset_catalog_summary(asset_rows, manage_target=manage_target, limit=5),
        "manager_session": _compile_manager_session_summary(manager_session),
        "current_draft": normalize_manage_chat_draft_payload(current_draft, current=None),
        "pending_action": _compile_pending_action_summary(pending_action),
        "asset_manager_notes_present": bool(manager_notes_text),
        "user_instruction": str(instruction or "").strip(),
        "protocol": [
            "answer the operator's question directly",
            "prefer template-first when the work has reuse value",
            "keep the current draft coherent and scoped to the active skill",
            "prepare actions only when the current skill actually owns that mutation",
            "do not treat discussion as execution authorization",
        ],
    }
    references = _compile_manager_references(skill_id)
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
        + (
            "On-demand references:\n"
            + "".join(f"[{item['key']}]\n{item['text']}\n\n" for item in references)
            if references
            else ""
        )
        + "Operational rules:\n"
        "- 这里是 Manage Center chat mode，先讨论、再整理管理动作。\n"
        "- 默认优先 template-first；one-off 只在用户明确要求或复用价值很低时才走。\n"
        "- 当前 skill 的职责合同由 `skill_contract` 给出；不要越权改写 draft。\n"
        "- `draft` 是当前讨论中的结构化草稿，只维护当前 skill 真正拥有的字段。\n"
        "- `action=manage_flow` 只表示形成了待确认 mutation 草案，不等于已经获准执行。\n"
        "- 只有在 operator 明确确认后，代码层才会真正允许 ready/commit。\n"
        "- 如果用户在解释、审阅、比较、提建议，先回答，不要跳过确认直接执行。\n"
        "- 回复自然、清楚、面向用户，不要像机器状态机。\n\n"
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
    selected_skill: str = "",
    parse_status: str = "ok",
    raw_reply: str = "",
    error_text: str = "",
) -> dict[str, Any]:
    normalized_parse_status = str(parse_status or result.get("parse_status") or "ok").strip().lower() or "ok"
    normalized_raw_reply = str(raw_reply or result.get("raw_reply") or "").strip()
    normalized_error_text = str(error_text or result.get("error_text") or "").strip()
    response = str(result.get("response") or result.get("answer") or result.get("summary") or "").strip()
    if normalized_parse_status != "ok":
        if normalized_parse_status == "empty":
            response = "Manager 本轮没有返回可展示的回复，请直接重试。"
        else:
            response = "Manager 本轮回复解析失败；原始输出已保留用于恢复与排障，请直接重试或继续下一条指令。"
    if not response:
        response = "Manager chat completed."
    action = str(result.get("action") or "none").strip().lower()
    if action not in {"none", "manage_flow"}:
        action = "none"
    manager_stage = str(result.get("manager_stage") or "discuss").strip().lower()
    if manager_stage not in MANAGE_CHAT_STAGES:
        manager_stage = "discuss"
    active_skill = str(result.get("active_skill") or selected_skill or "").strip().lower()
    active_skill = _manager_skill_spec(active_skill).skill_id
    confirmation_scope = str(result.get("confirmation_scope") or "none").strip().lower()
    if confirmation_scope not in MANAGE_CHAT_CONFIRMATION_SCOPES:
        confirmation_scope = _manager_skill_spec(active_skill).confirmation_scope
    confirmation_prompt = str(result.get("confirmation_prompt") or "").strip()
    action_manage_target = str(result.get("action_manage_target") or result.get("manage_target") or manage_target or "").strip()
    action_instruction = str(result.get("action_instruction") or "").strip()
    action_stage = str(result.get("action_stage") or "").strip().lower()
    action_builtin_mode = str(result.get("action_builtin_mode") or "").strip().lower()
    action_ready = _coerce_bool(result.get("action_ready"), default=False)
    draft = _filter_draft_by_skill_ownership(
        result.get("draft"),
        current_draft=current_draft,
        active_skill=active_skill,
    )
    if not str(draft.get("manage_target") or "").strip():
        draft["manage_target"] = action_manage_target or str(result.get("manage_target") or manage_target or "").strip()
    draft["asset_kind"] = _asset_kind_from_manage_target(
        str(draft.get("manage_target") or "").strip(),
        fallback=str(draft.get("asset_kind") or "").strip(),
    )
    action, action_ready, action_manage_target, action_instruction, action_builtin_mode = _validate_manage_chat_action(
        action=action,
        action_ready=action_ready,
        action_manage_target=action_manage_target,
        action_instruction=action_instruction,
        action_builtin_mode=action_builtin_mode,
        active_skill=active_skill,
    )
    if manager_stage not in MANAGE_CHAT_STAGES:
        manager_stage = _manager_skill_spec(active_skill).fallback_stage
    if manager_stage == "discuss" and active_skill != "discuss_and_scope":
        manager_stage = _manager_skill_spec(active_skill).fallback_stage
    if not confirmation_prompt:
        default_scope = _manager_skill_spec(active_skill).confirmation_scope
        if default_scope == "template":
            confirmation_prompt = "如果这版 template 方向正确，我就整理成待确认的 template 变更。"
        elif default_scope == "flow":
            confirmation_prompt = "如果这版 flow 规格正确，我就整理成待确认的 flow 变更。"
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
    selected_skill = select_manage_chat_skill(
        manage_target=manage_target,
        asset_kind=asset_kind,
        instruction=instruction,
        manager_session=manager_session,
        current_draft=current_draft,
        pending_action=pending_action,
    )
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
        selected_skill=selected_skill,
    )
    runtime_request = _manage_chat_runtime_request(
        cfg=cfg,
        workspace_root=workspace_root,
        flow_state=flow_state,
        manage_target=manage_target,
        manager_session_id=manager_session_id,
    )
    receipt = run_prompt_receipt_fn(
        prompt,
        workspace_root,
        300,
        cfg,
        runtime_request,
        stream=False,
    )
    payload, raw_reply, parse_status = _payload_from_manage_chat_receipt(
        receipt,
        manage_target=manage_target,
        current_draft=current_draft,
        selected_skill=selected_skill,
        fallback_manager_session_id=manager_session_id,
    )
    if str(manager_session_id or "").strip() and parse_status != "ok" and _is_manage_chat_resume_recoverable(receipt, raw_reply=raw_reply):
        fresh_receipt = run_prompt_receipt_fn(
            prompt,
            workspace_root,
            300,
            cfg,
            _manage_chat_runtime_request(
                cfg=cfg,
                workspace_root=workspace_root,
                flow_state=flow_state,
                manage_target=manage_target,
                manager_session_id="",
            ),
            stream=False,
        )
        fresh_payload, _, _ = _payload_from_manage_chat_receipt(
            fresh_receipt,
            manage_target=manage_target,
            current_draft=current_draft,
            selected_skill=selected_skill,
            fallback_manager_session_id="",
        )
        fresh_payload["session_recovery"] = {
            "applied": True,
            "kind": "resume_to_fresh_exec",
            "previous_manager_session_id": str(manager_session_id or "").strip(),
            "recovered_manager_session_id": str(fresh_payload.get("manager_session_id") or "").strip(),
            "initial_raw_reply": raw_reply,
        }
        return fresh_payload
    payload["session_recovery"] = {
        "applied": False,
        "kind": "",
        "previous_manager_session_id": "",
        "recovered_manager_session_id": "",
        "initial_raw_reply": "",
    }
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
