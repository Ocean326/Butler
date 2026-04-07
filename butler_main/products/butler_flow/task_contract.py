from __future__ import annotations

from datetime import datetime
from typing import Any


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_text(*values: Any) -> str:
    for value in values:
        token = _text(value)
        if token:
            return token
    return ""


def _text_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    text = _text(value)
    return [text] if text else []


def _first_text_list(*values: Any) -> list[str]:
    for value in values:
        items = _text_list(value)
        if items:
            return items
    return []


def _control_profile_payload(source: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(source or {})
    if isinstance(payload.get("control_profile"), dict):
        payload = dict(payload.get("control_profile") or {})
    return {
        "task_archetype": _text(payload.get("task_archetype")),
        "packet_size": _text(payload.get("packet_size")),
        "evidence_level": _text(payload.get("evidence_level")),
        "gate_cadence": _text(payload.get("gate_cadence")),
        "repo_binding_policy": _text(payload.get("repo_binding_policy")),
        "repo_contract_paths": _text_list(payload.get("repo_contract_paths") or []),
    }


def _policy_payload(
    flow_state: dict[str, Any],
    *,
    flow_definition: dict[str, Any] | None = None,
    current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_policy = dict(dict(current or {}).get("policy") or {})
    current_control_profile = _control_profile_payload(current_policy)
    definition_control_profile = _control_profile_payload(flow_definition)
    flow_control_profile = _control_profile_payload(flow_state)
    return {
        "execution_context": _first_text(
            flow_state.get("execution_context"),
            dict(flow_definition or {}).get("execution_context"),
            current_policy.get("execution_context"),
            dict(current or {}).get("execution_context"),
        ),
        "control_profile": {
            "task_archetype": _first_text(
                flow_control_profile.get("task_archetype"),
                definition_control_profile.get("task_archetype"),
                current_control_profile.get("task_archetype"),
            ),
            "packet_size": _first_text(
                flow_control_profile.get("packet_size"),
                definition_control_profile.get("packet_size"),
                current_control_profile.get("packet_size"),
            ),
            "evidence_level": _first_text(
                flow_control_profile.get("evidence_level"),
                definition_control_profile.get("evidence_level"),
                current_control_profile.get("evidence_level"),
            ),
            "gate_cadence": _first_text(
                flow_control_profile.get("gate_cadence"),
                definition_control_profile.get("gate_cadence"),
                current_control_profile.get("gate_cadence"),
            ),
            "repo_binding_policy": _first_text(
                flow_control_profile.get("repo_binding_policy"),
                definition_control_profile.get("repo_binding_policy"),
                current_control_profile.get("repo_binding_policy"),
            ),
            "repo_contract_paths": _first_text_list(
                flow_control_profile.get("repo_contract_paths") or [],
                definition_control_profile.get("repo_contract_paths") or [],
                current_control_profile.get("repo_contract_paths") or [],
            ),
        },
    }


def _responsibility_summary(*, owner: dict[str, Any], authority: dict[str, Any]) -> dict[str, Any]:
    return {
        role: {
            "owner": _text(owner.get(role)),
            "authority": _text(authority.get(role)),
        }
        for role in ("requester", "manager", "operator")
    }


def build_derived_responsibility_graph(
    contract_summary: dict[str, Any] | None,
    *,
    flow_state: dict[str, Any] | None = None,
    handoffs: list[dict[str, Any]] | None = None,
    latest_governance_receipt_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = dict(contract_summary or {})
    state = dict(flow_state or {})
    role_sessions = dict(state.get("role_sessions") or {})
    active_role_id = _text(state.get("active_role_id"))
    runtime_role_ids: list[str] = []

    def _add_runtime_role(role_id: Any) -> None:
        token = _text(role_id)
        if token and token not in runtime_role_ids:
            runtime_role_ids.append(token)

    for role_id in role_sessions:
        _add_runtime_role(role_id)
    _add_runtime_role(active_role_id)
    for handoff in list(handoffs or []):
        row = dict(handoff or {})
        _add_runtime_role(row.get("from_role_id") or row.get("source_role_id"))
        _add_runtime_role(row.get("to_role_id") or row.get("target_role_id"))

    runtime_roles: list[dict[str, Any]] = []
    for role_id in runtime_role_ids:
        session_payload = dict(role_sessions.get(role_id) or {})
        runtime_roles.append(
            {
                "role_id": role_id,
                "session_id": _text(session_payload.get("session_id")),
                "status": _text(session_payload.get("status") or ("active" if role_id and role_id == active_role_id else "idle")),
                "is_active": bool(role_id and role_id == active_role_id),
            }
        )

    handoff_edges: list[dict[str, Any]] = []
    for handoff in list(handoffs or []):
        row = dict(handoff or {})
        handoff_id = _text(row.get("handoff_id"))
        if not handoff_id:
            continue
        handoff_edges.append(
            {
                "handoff_id": handoff_id,
                "from_role_id": _text(row.get("from_role_id") or row.get("source_role_id")),
                "to_role_id": _text(row.get("to_role_id") or row.get("target_role_id")),
                "status": _text(row.get("status")),
                "summary": _text(row.get("summary")),
            }
        )

    responsibility_summary = dict(summary.get("responsibility_summary") or {})
    return {
        "graph_kind": "derived_responsibility_graph",
        "truth_basis": ["task_contract.json", "receipts.jsonl", "role_sessions.json", "handoffs.jsonl"],
        "contract_roles": [
            {
                "role": role,
                "owner": _text(dict(summary.get("owner_summary") or {}).get(role)),
                "authority": _text(dict(summary.get("authority_summary") or {}).get(role)),
            }
            for role in ("requester", "manager", "operator")
        ],
        "runtime_roles": runtime_roles,
        "handoff_edges": handoff_edges,
        "active_role_id": active_role_id,
        "latest_governance_receipt_summary": dict(latest_governance_receipt_summary or {}),
        "responsibility_summary": responsibility_summary,
    }


def build_governance_summary(
    contract_summary: dict[str, Any] | None,
    *,
    latest_governance_receipt_summary: dict[str, Any] | None = None,
    derived_responsibility_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = dict(contract_summary or {})
    return {
        "task_contract_id": _text(summary.get("task_contract_id")),
        "owner_summary": dict(summary.get("owner_summary") or {}),
        "authority_summary": dict(summary.get("authority_summary") or {}),
        "policy_summary": dict(summary.get("policy_summary") or {}),
        "responsibility_summary": dict(
            dict(derived_responsibility_graph or {}).get("responsibility_summary") or summary.get("responsibility_summary") or {}
        ),
        "derived_responsibility_graph": dict(derived_responsibility_graph or {}),
        "latest_governance_receipt_summary": dict(latest_governance_receipt_summary or {}),
        "truth_owner": _text(summary.get("truth_owner") or "task_contract.json"),
        "ledger_owner": "receipts.jsonl",
    }


def build_mission_console_summary(
    contract_summary: dict[str, Any] | None,
    *,
    latest_receipt_summary: dict[str, Any] | None = None,
    latest_governance_receipt_summary: dict[str, Any] | None = None,
    latest_artifact_ref: str = "",
    recovery_state: str = "",
    derived_responsibility_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = dict(contract_summary or {})
    return {
        "task_contract_id": _text(summary.get("task_contract_id")),
        "goal": _text(summary.get("goal")),
        "acceptance_summary": dict(summary.get("acceptance_summary") or {}),
        "owner_summary": dict(summary.get("owner_summary") or {}),
        "authority_summary": dict(summary.get("authority_summary") or {}),
        "policy_summary": dict(summary.get("policy_summary") or {}),
        "responsibility_summary": dict(
            dict(derived_responsibility_graph or {}).get("responsibility_summary") or summary.get("responsibility_summary") or {}
        ),
        "derived_responsibility_graph": dict(derived_responsibility_graph or {}),
        "latest_receipt_summary": dict(latest_receipt_summary or {}),
        "latest_governance_receipt_summary": dict(latest_governance_receipt_summary or {}),
        "latest_artifact_ref": _text(latest_artifact_ref),
        "recovery_state": _text(recovery_state),
        "truth_basis": ["task_contract.json", "receipts.jsonl", "recovery_cursor.json"],
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
    review_checklist = _first_text_list(
        flow_state.get("review_checklist"),
        flow_definition.get("review_checklist"),
        dict(current.get("acceptance") or {}).get("review_checklist"),
        [],
    )
    requested_by = _first_text(
        flow_state.get("requested_by"),
        flow_definition.get("requested_by"),
        dict(current.get("owner") or {}).get("requester"),
        current.get("requester"),
        "operator",
    )
    manager_actor = _first_text(
        flow_state.get("manager_actor"),
        flow_definition.get("manager_actor"),
        dict(current.get("owner") or {}).get("manager"),
        "manage_agent" if flow_state.get("manage_handoff") or flow_definition.get("manager_handoff") else "",
    )
    operator_actor = _first_text(
        flow_state.get("operator_actor"),
        flow_definition.get("operator_actor"),
        dict(current.get("owner") or {}).get("operator"),
        "local_operator",
    )
    policy = _policy_payload(flow_state, flow_definition=flow_definition, current=current)
    control_profile = dict(policy.get("control_profile") or {})
    current_repo_scope = dict(current.get("repo_scope") or {})
    repo_scope = {
        "scope_kind": _first_text(
            dict(flow_state.get("repo_scope") or {}).get("scope_kind"),
            dict(flow_definition.get("repo_scope") or {}).get("scope_kind"),
            current_repo_scope.get("scope_kind"),
            "repo_bound_task" if _first_text(flow_state.get("execution_context"), flow_definition.get("execution_context"), current.get("execution_context")) == "repo_bound" else "isolated_task",
        ),
        "workspace_root": _first_text(
            dict(flow_state.get("repo_scope") or {}).get("workspace_root"),
            dict(flow_definition.get("repo_scope") or {}).get("workspace_root"),
            flow_state.get("workspace_root"),
            flow_definition.get("workspace_root"),
            current_repo_scope.get("workspace_root"),
        ),
        "repo_binding_policy": _first_text(
            dict(flow_state.get("repo_scope") or {}).get("repo_binding_policy"),
            dict(flow_definition.get("repo_scope") or {}).get("repo_binding_policy"),
            control_profile.get("repo_binding_policy"),
            current_repo_scope.get("repo_binding_policy"),
        ),
        "repo_contract_paths": _first_text_list(
            dict(flow_state.get("repo_scope") or {}).get("repo_contract_paths") or [],
            dict(flow_definition.get("repo_scope") or {}).get("repo_contract_paths") or [],
            control_profile.get("repo_contract_paths") or [],
            current_repo_scope.get("repo_contract_paths") or [],
        ),
    }
    acceptance = {
        "guard_condition": _first_text(
            flow_state.get("guard_condition"),
            flow_definition.get("guard_condition"),
            dict(current.get("acceptance") or {}).get("guard_condition"),
        ),
        "review_checklist": review_checklist,
    }
    owner = {
        "requester": requested_by or "operator",
        "manager": manager_actor,
        "operator": operator_actor or "local_operator",
    }
    current_authority = dict(current.get("authority") or {})
    state_authority = dict(flow_state.get("authority") or {})
    definition_authority = dict(flow_definition.get("authority") or {})
    manager_authority = _first_text(
        state_authority.get("manager"),
        definition_authority.get("manager"),
    )
    if not manager_authority:
        current_manager_authority = _text(current_authority.get("manager"))
        if current_manager_authority not in {"", "not_assigned", "shape_contract"}:
            manager_authority = current_manager_authority
        else:
            manager_authority = "shape_contract" if owner.get("manager") else "not_assigned"
    authority = {
        "requester": _first_text(
            state_authority.get("requester"),
            definition_authority.get("requester"),
            current_authority.get("requester"),
            "request",
        ),
        "manager": manager_authority,
        "operator": _first_text(
            state_authority.get("operator"),
            definition_authority.get("operator"),
            current_authority.get("operator"),
            "launch_resume_recover",
        ),
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
        "goal": _first_text(flow_state.get("goal"), flow_definition.get("goal"), current.get("goal")),
        "repo_scope": repo_scope,
        "acceptance": acceptance,
        "owner": owner,
        "authority": authority,
        "policy": policy,
        "execution_context": _first_text(
            flow_state.get("execution_context"),
            flow_definition.get("execution_context"),
            current.get("execution_context"),
        ),
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
    responsibility_summary = _responsibility_summary(owner=owner, authority=authority)
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
            "execution_context": _text(payload.get("execution_context") or policy.get("execution_context")),
            "task_archetype": _text(control_profile.get("task_archetype")),
            "packet_size": _text(control_profile.get("packet_size")),
            "evidence_level": _text(control_profile.get("evidence_level")),
            "gate_cadence": _text(control_profile.get("gate_cadence")),
            "repo_binding_policy": _text(control_profile.get("repo_binding_policy")),
            "repo_contract_paths": _text_list(control_profile.get("repo_contract_paths") or []),
        },
        "responsibility_summary": responsibility_summary,
        "truth_owner": _text(payload.get("truth_owner") or "task_contract.json"),
    }
