from __future__ import annotations

from typing import Any, Mapping


FOURTH_LAYER_PORT_NAMESPACE = "domain_product_plane.v1"
FOURTH_LAYER_PORTS = (
    "frontdoor",
    "mission_facade",
    "observation",
    "domain_pack",
)
FOURTH_LAYER_STABLE_EVIDENCE_KEYS = (
    "mission_id",
    "branch_id",
    "workflow_id",
    "workflow_session_id",
    "status",
    "active_step",
    "workflow_ir_compiled",
    "workflow_vm_executed",
    "workflow_session_count",
)
FOURTH_LAYER_FORBIDDEN_DIRECT_IMPORTS = (
    "butler_main.orchestrator.service",
    "butler_main.orchestrator.workflow_vm",
    "butler_main.orchestrator.workflow_ir",
    "butler_main.orchestrator.runtime_bridge.workflow_session_bridge",
    "butler_main.agents_os.process_runtime.session",
    "butler_main.agents_os.process_runtime.factory",
    "butler_main.multi_agents_os",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _event_types(payload: Mapping[str, Any]) -> set[str]:
    names: set[str] = set()
    for item in _as_list(payload.get("delivery_events")) + _as_list(payload.get("events")):
        event = _as_dict(item)
        event_type = _text(event.get("event_type"))
        if event_type:
            names.add(event_type)
    return names


def _workflow_session_ids(payload: Mapping[str, Any]) -> list[str]:
    result: list[str] = []

    for item in payload.get("branches") or []:
        branch = _as_dict(item)
        workflow_session = _as_dict(branch.get("workflow_session"))
        session_id = _text(
            branch.get("workflow_session_id")
            or workflow_session.get("session_id")
        )
        if session_id and session_id not in result:
            result.append(session_id)

    for item in payload.get("nodes") or []:
        node = _as_dict(item)
        metadata = _as_dict(node.get("metadata"))
        session_id = _text(node.get("workflow_session_id") or metadata.get("workflow_session_id"))
        if session_id and session_id not in result:
            result.append(session_id)

    return result


def _event_payload_value(event: Mapping[str, Any], *path: str) -> str:
    current: Any = _as_dict(event)
    for key in path:
        if not isinstance(current, Mapping):
            return ""
        current = current.get(key)
    return _text(current)


def _recent_execution_reference(recent_events: list[Mapping[str, Any]]) -> dict[str, str]:
    branch_id = ""
    workflow_id = ""
    workflow_session_id = ""
    active_step = ""
    for item in recent_events:
        event = _as_dict(item)
        if not branch_id:
            branch_id = _text(event.get("branch_id"))
        if not workflow_id:
            workflow_id = (
                _event_payload_value(event, "payload", "workflow_id")
                or _event_payload_value(event, "payload", "result_payload", "workflow_ir", "workflow_id")
            )
        if not workflow_session_id:
            workflow_session_id = (
                _event_payload_value(event, "payload", "workflow_session_id")
                or _event_payload_value(event, "payload", "result_payload", "workflow_ir", "workflow_session_id")
            )
        if not active_step:
            active_step = _event_payload_value(event, "payload", "active_step")
        if branch_id and workflow_id and workflow_session_id:
            break
    return {
        "branch_id": branch_id,
        "workflow_id": workflow_id,
        "workflow_session_id": workflow_session_id,
        "active_step": active_step,
    }


def build_fourth_layer_contract_manifest() -> dict[str, Any]:
    return {
        "port_namespace": FOURTH_LAYER_PORT_NAMESPACE,
        "ports": list(FOURTH_LAYER_PORTS),
        "stable_evidence_keys": list(FOURTH_LAYER_STABLE_EVIDENCE_KEYS),
        "forbidden_direct_imports": list(FOURTH_LAYER_FORBIDDEN_DIRECT_IMPORTS),
    }


def build_mission_view(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = _as_dict(payload)
    workflow_session_count = int(summary.get("workflow_session_count") or 0)
    if workflow_session_count <= 0:
        workflow_session_count = len(_workflow_session_ids(summary))
    branch_count = int(summary.get("branch_count") or 0)
    if branch_count <= 0 and isinstance(summary.get("branches"), list):
        branch_count = len(summary.get("branches") or [])
    return {
        "mission_id": _text(summary.get("mission_id")),
        "title": _text(summary.get("title")),
        "status": _text(summary.get("status")),
        "branch_count": branch_count,
        "workflow_session_count": workflow_session_count,
    }


def build_branch_view(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = _as_dict(payload)
    mission = _as_dict(summary.get("mission"))
    node = _as_dict(summary.get("node"))
    workflow_ir = _as_dict(summary.get("workflow_ir"))
    workflow_session = _as_dict(summary.get("workflow_session"))
    return {
        "branch_id": _text(summary.get("branch_id")),
        "mission_id": _text(summary.get("mission_id") or mission.get("mission_id")),
        "node_id": _text(summary.get("node_id") or node.get("node_id")),
        "status": _text(summary.get("status")),
        "workflow_id": _text(summary.get("workflow_id") or workflow_ir.get("workflow_id")),
        "workflow_session_id": _text(
            summary.get("workflow_session_id")
            or workflow_session.get("session_id")
        ),
    }


def build_session_view(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = _as_dict(payload)
    return {
        "workflow_session_id": _text(summary.get("session_id")),
        "template_id": _text(summary.get("template_id")),
        "status": _text(summary.get("status")),
        "active_step": _text(summary.get("active_step")),
    }


def build_campaign_view(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = _as_dict(payload)
    contract = _as_dict(summary.get("working_contract"))
    metadata = _as_dict(summary.get("metadata"))
    control_plane_refs = _as_dict(metadata.get("control_plane_refs"))
    phase_runtime = _as_dict(metadata.get("phase_runtime"))
    artifacts = summary.get("artifacts")
    verdict_history = summary.get("verdict_history")
    canonical_session_id = _text(
        summary.get("canonical_session_id")
        or metadata.get("canonical_session_id")
        or control_plane_refs.get("canonical_session_id")
        or summary.get("supervisor_session_id")
        or summary.get("workflow_session_id")
    )
    artifact_count = int(summary.get("artifact_count") or 0)
    if artifact_count <= 0 and isinstance(artifacts, list):
        artifact_count = len(artifacts)
    verdict_count = int(summary.get("verdict_count") or 0)
    if verdict_count <= 0 and isinstance(verdict_history, list):
        verdict_count = len(verdict_history)
    return {
        "campaign_id": _text(summary.get("campaign_id")),
        "title": _text(summary.get("campaign_title") or summary.get("title")),
        "status": _text(summary.get("status")),
        "current_phase": _text(summary.get("current_phase")),
        "next_phase": _text(summary.get("next_phase")),
        "current_iteration": int(summary.get("current_iteration") or 0),
        "mission_id": _text(summary.get("mission_id")),
        "workflow_session_id": canonical_session_id,
        "canonical_session_id": canonical_session_id,
        "artifact_count": artifact_count,
        "verdict_count": verdict_count,
        "working_contract_version": int(contract.get("version") or 0),
        "contract_rewrite_count": int(contract.get("rewrite_count") or 0),
        "latest_verdict_decision": _text(_as_dict((verdict_history or [{}])[-1] if isinstance(verdict_history, list) and verdict_history else {}).get("decision")),
        "phase_transition_count": int(phase_runtime.get("transition_count") or len(_as_list(metadata.get("phase_history")))),
    }


def build_stable_evidence(
    *,
    closure_signals: Mapping[str, Any],
    missions: list[Mapping[str, Any]],
    active_branches: list[Mapping[str, Any]],
    recent_events: list[Mapping[str, Any]],
) -> dict[str, Any]:
    signal_map = _as_dict(closure_signals)
    workflow_session_count = int(signal_map.get("workflow_session_count") or 0)
    if workflow_session_count <= 0:
        workflow_session_count = sum(int(build_mission_view(item).get("workflow_session_count") or 0) for item in missions)
    active_step = ""
    session_ids = [
        _text(build_branch_view(item).get("workflow_session_id"))
        for item in active_branches
    ]
    for item in active_branches:
        workflow_session = _as_dict(_as_dict(item).get("workflow_session"))
        active_step = _text(workflow_session.get("active_step"))
        if active_step:
            break
    fallback = _recent_execution_reference(recent_events)
    return {
        "mission_id": _text(build_mission_view(missions[0]).get("mission_id")) if missions else "",
        "branch_id": _text(build_branch_view(active_branches[0]).get("branch_id")) if active_branches else fallback["branch_id"],
        "workflow_id": _text(build_branch_view(active_branches[0]).get("workflow_id")) if active_branches else fallback["workflow_id"],
        "workflow_session_id": next((item for item in session_ids if item), "") or fallback["workflow_session_id"],
        "status": _text(build_mission_view(missions[0]).get("status")) if missions else "",
        "active_step": active_step or fallback["active_step"],
        "workflow_ir_compiled": bool(signal_map.get("workflow_ir_compiled_visible")),
        "workflow_vm_executed": bool(signal_map.get("workflow_vm_executed_visible")),
        "workflow_session_count": workflow_session_count,
    }


def build_observation_snapshot(
    *,
    orchestrator_root: str,
    runtime: Mapping[str, Any],
    missions: list[Mapping[str, Any]],
    active_branches: list[Mapping[str, Any]],
    recent_events: list[Mapping[str, Any]],
    closure_signals: Mapping[str, Any],
    codex_debug: Mapping[str, Any],
) -> dict[str, Any]:
    mission_views = [build_mission_view(item) for item in missions]
    active_branch_views = [build_branch_view(item) for item in active_branches]
    return {
        "contract": build_fourth_layer_contract_manifest(),
        "stable_evidence": build_stable_evidence(
            closure_signals=closure_signals,
            missions=missions,
            active_branches=active_branches,
            recent_events=recent_events,
        ),
        "orchestrator_root": orchestrator_root,
        "runtime": dict(runtime),
        "missions": [dict(item) for item in missions],
        "mission_views": mission_views,
        "active_branches": [dict(item) for item in active_branches],
        "active_branch_views": active_branch_views,
        "recent_events": [dict(item) for item in recent_events],
        "closure_signals": dict(closure_signals),
        "codex_debug": dict(codex_debug),
    }


def build_campaign_observation_snapshot(
    *,
    orchestrator_root: str,
    runtime: Mapping[str, Any],
    campaign: Mapping[str, Any],
    mission: Mapping[str, Any],
    session: Mapping[str, Any],
    artifacts: list[Mapping[str, Any]],
    campaign_events: list[Mapping[str, Any]],
) -> dict[str, Any]:
    campaign_payload = _as_dict(campaign)
    mission_payload = _as_dict(mission)
    session_payload = _as_dict(session)
    metadata = _as_dict(campaign_payload.get("metadata"))
    phase_runtime = _as_dict(metadata.get("phase_runtime"))
    phase_history = [
        _as_dict(item)
        for item in _as_list(metadata.get("phase_history"))
    ]
    initial_spec = _as_dict(_as_dict(campaign_payload.get("metadata")).get("spec"))
    initial_goal = _text(initial_spec.get("top_level_goal"))
    current_goal = _text(campaign_payload.get("top_level_goal"))
    initial_constraints = [
        _text(item)
        for item in initial_spec.get("hard_constraints") or []
        if _text(item)
    ]
    current_constraints = [
        _text(item)
        for item in campaign_payload.get("hard_constraints") or []
        if _text(item)
    ]
    event_types = {
        _text(item.get("event_type"))
        for item in campaign_events
        if _text(item.get("event_type"))
    }
    event_types.update(_event_types(mission_payload))
    campaign_view = build_campaign_view({
        **campaign_payload,
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "verdict_count": len(campaign_payload.get("verdict_history") or []),
    })
    mission_view = build_mission_view(mission_payload) if mission_payload else {}
    session_view = build_session_view(session_payload) if session_payload else {}
    blackboard = _as_dict(session_payload.get("blackboard"))
    artifact_registry = _as_dict(session_payload.get("artifact_registry"))
    session_events = _as_list(session_payload.get("events"))
    artifact_count = int(artifact_registry.get("artifact_count") or len(_as_list(artifact_registry.get("artifacts"))))
    blackboard_entry_count = int(blackboard.get("entry_count") or len(_as_list(blackboard.get("entries"))))
    stable_evidence = {
        "mission_id": _text(mission_view.get("mission_id")),
        "branch_id": "",
        "workflow_id": "",
        "workflow_session_id": _text(
            campaign_payload.get("canonical_session_id")
            or session_view.get("workflow_session_id")
            or campaign_view.get("workflow_session_id")
        ),
        "status": _text(campaign_view.get("status")),
        "active_step": _text(session_view.get("active_step")),
        "workflow_ir_compiled": "workflow_ir_compiled" in event_types,
        "workflow_vm_executed": "workflow_vm_executed" in event_types,
        "workflow_session_count": 1 if _text(session_view.get("workflow_session_id")) else 0,
    }
    return {
        "contract": build_fourth_layer_contract_manifest(),
        "stable_evidence": stable_evidence,
        "orchestrator_root": orchestrator_root,
        "runtime": dict(runtime),
        "campaign": dict(campaign_payload),
        "campaign_view": campaign_view,
        "mission": dict(mission_payload),
        "mission_view": mission_view,
        "workflow_session": dict(session_payload),
        "session_view": session_view,
        "phase_runtime": {
            "runtime_kind": _text(phase_runtime.get("runtime_kind")),
            "phase_path": [str(item).strip() for item in phase_runtime.get("phase_path") or [] if str(item).strip()],
            "transition_count": int(phase_runtime.get("transition_count") or len(phase_history)),
            "phase_history": phase_history,
        },
        "phase_timeline": phase_history,
        "contract_revisions": [
            {
                "contract_id": _text(_as_dict(item).get("contract_id")),
                "version": int(_as_dict(item).get("version") or 0),
                "working_goal": _text(_as_dict(item).get("working_goal")),
                "rewrite_count": int(_as_dict(item).get("rewrite_count") or 0),
                "last_verdict_decision": _text(_as_dict(item).get("last_verdict_decision")),
            }
            for item in _as_list(campaign_payload.get("contract_history"))
        ],
        "verdict_summary": {
            "count": len(_as_list(campaign_payload.get("verdict_history"))),
            "latest": _as_dict(_as_list(campaign_payload.get("verdict_history"))[-1]) if _as_list(campaign_payload.get("verdict_history")) else {},
            "latest_decision": _text(_as_dict(_as_list(campaign_payload.get("verdict_history"))[-1]).get("decision")) if _as_list(campaign_payload.get("verdict_history")) else "",
        },
        "session_plane": {
            "artifact_count": artifact_count,
            "blackboard_entry_count": blackboard_entry_count,
            "session_event_count": len(session_events),
            "session_event_types": sorted(
                {
                    _text(_as_dict(item).get("event_type"))
                    for item in session_events
                    if _text(_as_dict(item).get("event_type"))
                }
            ),
        },
        "session_evidence": {
            "workflow_session_id": _text(session_view.get("workflow_session_id")),
            "template_id": _text(session_view.get("template_id")),
            "status": _text(session_view.get("status")),
            "active_step": _text(session_view.get("active_step")),
            "artifact_count": artifact_count,
            "blackboard_entry_count": blackboard_entry_count,
            "session_event_count": len(session_events),
        },
        "artifacts": [dict(item) for item in artifacts],
        "campaign_events": [dict(item) for item in campaign_events],
        "campaign_evidence": {
            "artifact_count": len(artifacts),
            "verdict_count": len(campaign_payload.get("verdict_history") or []),
            "working_contract_version": int(_as_dict(campaign_payload.get("working_contract")).get("version") or 0),
            "contract_revision_count": len(_as_list(campaign_payload.get("contract_history"))),
            "goal_immutable_ok": not initial_goal or current_goal == initial_goal,
            "hard_constraints_immutable_ok": current_constraints == initial_constraints,
            "mission_linked": bool(_text(campaign_payload.get("mission_id")) and mission_view.get("mission_id")),
            "session_linked": bool(
                _text(
                    campaign_payload.get("canonical_session_id")
                    or campaign_payload.get("supervisor_session_id")
                )
                and _text(session_view.get("workflow_session_id"))
            ),
            "blackboard_entry_count": blackboard_entry_count,
            "session_event_count": len(session_events),
        },
    }


__all__ = [
    "FOURTH_LAYER_FORBIDDEN_DIRECT_IMPORTS",
    "FOURTH_LAYER_PORT_NAMESPACE",
    "FOURTH_LAYER_PORTS",
    "FOURTH_LAYER_STABLE_EVIDENCE_KEYS",
    "build_branch_view",
    "build_campaign_observation_snapshot",
    "build_campaign_view",
    "build_fourth_layer_contract_manifest",
    "build_mission_view",
    "build_observation_snapshot",
    "build_session_view",
    "build_stable_evidence",
]
