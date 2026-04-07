from __future__ import annotations

from datetime import datetime
from typing import Any


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    text = _text(value)
    return [text] if text else []


def _policy_payload(flow_state: dict[str, Any]) -> dict[str, Any]:
    control_profile = dict(flow_state.get("control_profile") or {})
    return {
        "execution_context": _text(flow_state.get("execution_context")),
        "control_profile": {
            "task_archetype": _text(control_profile.get("task_archetype")),
            "packet_size": _text(control_profile.get("packet_size")),
            "evidence_level": _text(control_profile.get("evidence_level")),
            "gate_cadence": _text(control_profile.get("gate_cadence")),
            "repo_binding_policy": _text(control_profile.get("repo_binding_policy")),
            "repo_contract_paths": _text_list(control_profile.get("repo_contract_paths") or []),
        },
    }


def build_task_contract(
    *,
    flow_state: dict[str, Any],
    flow_definition: dict[str, Any] | None = None,
    current: dict[str, Any] | None = None,
    source_surface: str = "",
) -> dict[str, Any]:
    flow_state = dict(flow_state or {})
    flow_definition = dict(flow_definition or {})
    current = dict(current or {})
    flow_id = _text(current.get("flow_id") or flow_state.get("workflow_id") or flow_definition.get("flow_id"))
    task_contract_id = _text(
        current.get("task_contract_id")
        or flow_definition.get("task_contract_id")
        or flow_state.get("task_contract_id")
        or (f"task_contract_{flow_id}" if flow_id else "")
    )
    if not task_contract_id:
        task_contract_id = f"task_contract_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    review_checklist = _text_list(
        flow_state.get("review_checklist")
        or flow_definition.get("review_checklist")
        or current.get("acceptance", {}).get("review_checklist")
        or []
    )
    requested_by = _text(
        current.get("owner", {}).get("requester")
        or current.get("requester")
        or flow_state.get("requested_by")
        or flow_definition.get("requested_by")
        or "operator"
    )
    manager_actor = _text(
        current.get("owner", {}).get("manager")
        or flow_state.get("manager_actor")
        or flow_definition.get("manager_actor")
        or ("manage_agent" if flow_state.get("manage_handoff") or flow_definition.get("manager_handoff") else "")
    )
    operator_actor = _text(
        current.get("owner", {}).get("operator")
        or flow_state.get("operator_actor")
        or flow_definition.get("operator_actor")
        or "local_operator"
    )
    policy = dict(current.get("policy") or {}) or _policy_payload(flow_state)
    control_profile = dict(policy.get("control_profile") or {})
    repo_scope = {
        "scope_kind": _text(dict(current.get("repo_scope") or {}).get("scope_kind"))
        or ("repo_bound_task" if _text(flow_state.get("execution_context")) == "repo_bound" else "isolated_task"),
        "workspace_root": _text(dict(current.get("repo_scope") or {}).get("workspace_root") or flow_state.get("workspace_root")),
        "repo_binding_policy": _text(
            dict(current.get("repo_scope") or {}).get("repo_binding_policy")
            or control_profile.get("repo_binding_policy")
        ),
        "repo_contract_paths": _text_list(
            dict(current.get("repo_scope") or {}).get("repo_contract_paths")
            or control_profile.get("repo_contract_paths")
            or []
        ),
    }
    acceptance = {
        "guard_condition": _text(
            dict(current.get("acceptance") or {}).get("guard_condition")
            or flow_state.get("guard_condition")
            or flow_definition.get("guard_condition")
        ),
        "review_checklist": review_checklist,
    }
    owner = {
        "requester": requested_by or "operator",
        "manager": manager_actor,
        "operator": operator_actor or "local_operator",
    }
    authority = {
        "requester": _text(dict(current.get("authority") or {}).get("requester") or "request"),
        "manager": _text(
            dict(current.get("authority") or {}).get("manager")
            or ("shape_contract" if owner.get("manager") else "not_assigned")
        ),
        "operator": _text(dict(current.get("authority") or {}).get("operator") or "launch_resume_recover"),
    }
    created_at = _text(
        current.get("created_at")
        or flow_definition.get("created_at")
        or flow_state.get("created_at")
        or _now_text()
    )
    return {
        "task_contract_id": task_contract_id,
        "flow_id": flow_id,
        "goal": _text(current.get("goal") or flow_state.get("goal") or flow_definition.get("goal")),
        "repo_scope": repo_scope,
        "acceptance": acceptance,
        "owner": owner,
        "authority": authority,
        "policy": policy,
        "execution_context": _text(current.get("execution_context") or flow_state.get("execution_context")),
        "source_surface": _text(
            source_surface
            or current.get("source_surface")
            or flow_state.get("entry_mode")
            or flow_definition.get("entry_mode")
            or "butler_flow"
        ),
        "truth_owner": "task_contract.json",
        "materialization": {
            "flow_definition_path": "flow_definition.json",
            "runtime_state_path": "workflow_state.json",
        },
        "created_at": created_at,
        "updated_at": _now_text(),
    }


def build_task_contract_summary(contract: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(contract or {})
    repo_scope = dict(payload.get("repo_scope") or {})
    acceptance = dict(payload.get("acceptance") or {})
    owner = dict(payload.get("owner") or {})
    authority = dict(payload.get("authority") or {})
    policy = dict(payload.get("policy") or {})
    control_profile = dict(policy.get("control_profile") or {})
    return {
        "task_contract_id": _text(payload.get("task_contract_id")),
        "goal": _text(payload.get("goal")),
        "execution_context": _text(payload.get("execution_context")),
        "source_surface": _text(payload.get("source_surface")),
        "repo_scope": {
            "scope_kind": _text(repo_scope.get("scope_kind")),
            "workspace_root": _text(repo_scope.get("workspace_root")),
            "repo_binding_policy": _text(repo_scope.get("repo_binding_policy")),
            "repo_contract_paths": _text_list(repo_scope.get("repo_contract_paths") or []),
        },
        "acceptance_summary": {
            "guard_condition": _text(acceptance.get("guard_condition")),
            "review_checklist": _text_list(acceptance.get("review_checklist") or []),
        },
        "owner_summary": {
            "requester": _text(owner.get("requester")),
            "manager": _text(owner.get("manager")),
            "operator": _text(owner.get("operator")),
        },
        "authority_summary": {
            "requester": _text(authority.get("requester")),
            "manager": _text(authority.get("manager")),
            "operator": _text(authority.get("operator")),
        },
        "policy_summary": {
            "task_archetype": _text(control_profile.get("task_archetype")),
            "packet_size": _text(control_profile.get("packet_size")),
            "evidence_level": _text(control_profile.get("evidence_level")),
            "gate_cadence": _text(control_profile.get("gate_cadence")),
            "repo_binding_policy": _text(control_profile.get("repo_binding_policy")),
            "repo_contract_paths": _text_list(control_profile.get("repo_contract_paths") or []),
        },
        "truth_owner": _text(payload.get("truth_owner") or "task_contract.json"),
    }
