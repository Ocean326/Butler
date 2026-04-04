from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

CURRENT_DIR = Path(__file__).resolve().parent
BUTLER_MAIN_DIR = CURRENT_DIR.parent
REPO_ROOT = BUTLER_MAIN_DIR.parent
BUTLER_BOT_DIR = REPO_ROOT / "butler_main" / "butler_bot_code" / "butler_bot"
for candidate in (str(REPO_ROOT), str(BUTLER_MAIN_DIR), str(BUTLER_BOT_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

if __package__ in {None, ""}:
    from butler_main.orchestrator.campaign_service import OrchestratorCampaignService
    from butler_main.orchestrator.demo_fixtures import build_demo_fixture, list_demo_fixture_ids
    from butler_main.orchestrator.query_service import OrchestratorQueryService
    from butler_main.orchestrator.runner import run_orchestrator_service
    from butler_main.orchestrator.workspace import build_orchestrator_service_for_workspace
else:
    from .campaign_service import OrchestratorCampaignService
    from .demo_fixtures import build_demo_fixture, list_demo_fixture_ids
    from .query_service import OrchestratorQueryService
    from .runner import run_orchestrator_service
    from .workspace import build_orchestrator_service_for_workspace


_DEMO_ALIASES = {
    "campaign": "campaign",
    "normal": "superpowers_like",
    "research": "openfang_inspired",
}


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _prepare_workspace(workspace: str) -> str:
    root = Path(workspace).resolve()
    (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
    (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
    return str(root)


def _default_config(workspace: str, *, timeout_seconds: int, runtime_cli: str = "") -> dict[str, Any]:
    cli_runtime = {
        "providers": {
            "cursor": {"enabled": True},
            "codex": {"enabled": True, "sandbox": "danger-full-access", "skip_git_repo_check": True},
            "claude": {"enabled": False},
        }
    }
    if str(runtime_cli or "").strip():
        cli_runtime["active"] = str(runtime_cli or "").strip()
    return {
        "workspace_root": workspace,
        "orchestrator": {
            "auto_dispatch": True,
            "auto_execute": True,
            "max_dispatch_per_tick": 1,
            "execution_timeout_seconds": int(timeout_seconds),
        },
        "cli_runtime": cli_runtime,
    }


def _as_dict(payload: object) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, Mapping) else {}


def _as_list(payload: object) -> list[Any]:
    return list(payload) if isinstance(payload, list) else []


def _result_excerpt(text: str, *, limit: int = 240) -> str:
    clean = str(text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


def _important_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keep = {
        "workflow_ir_compiled",
        "workflow_session_created",
        "workflow_session_resumed",
        "workflow_vm_executed",
        "workflow_session_updated",
        "verification_skipped",
        "judge_verdict",
        "approval_requested",
        "approval_resolved",
        "recovery_scheduled",
        "recovery_skipped",
        "repair_exhausted",
        "branch_completed",
    }
    result: list[dict[str, Any]] = []
    for item in events:
        event_type = str(item.get("event_type") or "").strip()
        if event_type not in keep:
            continue
        payload = _as_dict(item.get("payload"))
        if event_type == "branch_completed":
            result_payload = _as_dict(payload.get("result_payload"))
            payload = {
                "ok": bool(payload.get("ok")),
                "result_ref": str(payload.get("result_ref") or "").strip(),
                "result_status": str(result_payload.get("status") or "").strip(),
                "summary_excerpt": _result_excerpt(
                    str(
                        result_payload.get("summary")
                        or result_payload.get("output_bundle_summary")
                        or result_payload.get("output_text")
                        or ""
                    ),
                    limit=120,
                ),
            }
        result.append({"event_type": event_type, "payload": payload})
    return result


def _resolve_demo_id(demo_id: str) -> str:
    target = str(demo_id or "").strip()
    return _DEMO_ALIASES.get(target, target)


def _workflow_evidence(workflow_ir_full: dict[str, Any]) -> dict[str, Any]:
    workflow_section = _as_dict(workflow_ir_full.get("workflow"))
    template = _as_dict(workflow_section.get("template"))
    template_metadata = _as_dict(template.get("metadata"))
    if not template_metadata:
        template_metadata = _as_dict(_as_dict(workflow_ir_full.get("workflow_template")).get("metadata"))
    package_refs = _as_dict(workflow_section.get("package_refs"))
    steps = [_as_dict(item) for item in _as_list(workflow_section.get("steps"))]
    artifacts = [_as_dict(item) for item in _as_list(workflow_section.get("artifacts"))]
    handoffs = [_as_dict(item) for item in _as_list(workflow_section.get("handoffs"))]
    roles = [_as_dict(item) for item in _as_list(workflow_section.get("roles"))]
    return {
        "workflow_id": str(workflow_ir_full.get("workflow_id") or "").strip(),
        "template_id": str(workflow_section.get("template_id") or workflow_ir_full.get("workflow_template_id") or workflow_ir_full.get("template_id") or "").strip(),
        "workflow_kind": str(workflow_ir_full.get("workflow_kind") or workflow_section.get("kind") or "").strip(),
        "entry_step_id": str(workflow_section.get("entry_step_id") or workflow_ir_full.get("entry_step_id") or "").strip(),
        "step_ids": [str(item.get("step_id") or item.get("id") or "").strip() for item in steps if str(item.get("step_id") or item.get("id") or "").strip()],
        "artifact_ids": [str(item.get("artifact_id") or "").strip() for item in artifacts if str(item.get("artifact_id") or "").strip()],
        "handoff_ids": [str(item.get("handoff_id") or "").strip() for item in handoffs if str(item.get("handoff_id") or "").strip()],
        "role_ids": [str(item.get("role_id") or item.get("id") or "").strip() for item in roles if str(item.get("role_id") or item.get("id") or "").strip()],
        "capability_package_ref": str(workflow_ir_full.get("capability_package_ref") or package_refs.get("capability_package_ref") or "").strip(),
        "team_package_ref": str(workflow_ir_full.get("team_package_ref") or package_refs.get("team_package_ref") or "").strip(),
        "governance_policy_ref": str(workflow_ir_full.get("governance_policy_ref") or package_refs.get("governance_policy_ref") or "").strip(),
        "execution_boundary": _as_dict(workflow_ir_full.get("execution_boundary")),
        "gate_policies": _as_dict(workflow_ir_full.get("gate_policies")),
        "package_binding_visible": any(
            str(workflow_ir_full.get(key) or package_refs.get(key) or "").strip()
            for key in ("capability_package_ref", "team_package_ref", "governance_policy_ref")
        ),
        "framework_origin": _as_dict(template_metadata.get("framework_origin")),
        "runtime_key": str(workflow_ir_full.get("runtime_key") or "").strip(),
        "worker_profile": str(workflow_ir_full.get("worker_profile") or "").strip(),
    }


def _receipt_evidence(result_payload: dict[str, Any]) -> dict[str, Any]:
    receipt_metadata = _as_dict(result_payload.get("metadata"))
    workflow_metadata = _as_dict(receipt_metadata.get("workflow"))
    workflow_projection = _as_dict(receipt_metadata.get("workflow_projection"))
    cursor = _as_dict(workflow_projection.get("cursor"))
    return {
        "result_status": str(result_payload.get("status") or "").strip(),
        "summary_excerpt": _result_excerpt(
            str(
                result_payload.get("summary")
                or result_payload.get("output_bundle_summary")
                or result_payload.get("output_text")
                or ""
            )
        ),
        "output_bundle_summary": str(result_payload.get("output_bundle_summary") or "").strip(),
        "output_text_excerpt": _result_excerpt(str(result_payload.get("output_text") or "").strip(), limit=180),
        "execution_phase": str(receipt_metadata.get("execution_phase") or "").strip(),
        "resolved_capability_id": str(receipt_metadata.get("resolved_capability_id") or "").strip(),
        "current_step_id": str(workflow_metadata.get("current_step_id") or cursor.get("current_step_id") or "").strip(),
        "completed_step_ids": [
            str(item).strip()
            for item in _as_list(workflow_metadata.get("completed_step_ids"))
            if str(item).strip()
        ],
        "step_receipt_count": len(_as_list(workflow_projection.get("step_receipts"))),
        "decision_receipt_count": len(_as_list(workflow_projection.get("decision_receipts"))),
        "handoff_receipt_count": len(_as_list(workflow_projection.get("handoff_receipts"))),
    }


def _event_evidence(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_types = [str(item.get("event_type") or "").strip() for item in events if str(item.get("event_type") or "").strip()]
    vm_engine = ""
    for item in events:
        if str(item.get("event_type") or "").strip() != "workflow_vm_executed":
            continue
        vm_engine = str(_as_dict(item.get("payload")).get("engine") or "").strip()
        if vm_engine:
            break
    return {
        "event_types": event_types,
        "important_events": _important_events(events),
        "vm_engine": vm_engine,
    }


def _build_checks(
    fixture: dict[str, Any],
    *,
    workflow_evidence: dict[str, Any],
    receipt_evidence: dict[str, Any],
    writeback: dict[str, Any],
    event_evidence: dict[str, Any],
) -> dict[str, Any]:
    acceptance = _as_dict(fixture.get("acceptance"))
    observed_event_types = set(event_evidence.get("event_types") or [])
    checks: list[dict[str, Any]] = []

    for event_type in acceptance.get("required_event_types") or []:
        checks.append(
            {
                "name": f"event:{event_type}",
                "ok": event_type in observed_event_types,
                "expected": event_type,
                "observed": sorted(observed_event_types),
            }
        )

    expected_status = _as_dict(acceptance.get("expected_status"))
    for key, expected in expected_status.items():
        observed = str(writeback.get(f"{key}_status") or "").strip()
        checks.append(
            {
                "name": f"status:{key}",
                "ok": observed == str(expected or "").strip(),
                "expected": str(expected or "").strip(),
                "observed": observed,
            }
        )

    template_id = str(acceptance.get("required_workflow_template_id") or "").strip()
    if template_id:
        checks.append(
            {
                "name": "workflow:template_id",
                "ok": workflow_evidence.get("template_id") == template_id,
                "expected": template_id,
                "observed": workflow_evidence.get("template_id"),
            }
        )

    min_step_count = int(acceptance.get("min_step_count") or 0)
    if min_step_count > 0:
        checks.append(
            {
                "name": "workflow:step_count",
                "ok": len(workflow_evidence.get("step_ids") or []) >= min_step_count,
                "expected": min_step_count,
                "observed": len(workflow_evidence.get("step_ids") or []),
            }
        )

    required_framework_origin = _as_dict(acceptance.get("required_framework_origin"))
    for key, expected in required_framework_origin.items():
        observed = str(_as_dict(workflow_evidence.get("framework_origin")).get(key) or "").strip()
        checks.append(
            {
                "name": f"framework_origin:{key}",
                "ok": observed == str(expected or "").strip(),
                "expected": str(expected or "").strip(),
                "observed": observed,
            }
        )

    for artifact_id in acceptance.get("required_artifact_ids") or []:
        observed_artifacts = workflow_evidence.get("artifact_ids") or []
        checks.append(
            {
                "name": f"artifact:{artifact_id}",
                "ok": artifact_id in observed_artifacts,
                "expected": artifact_id,
                "observed": list(observed_artifacts),
            }
        )

    for key in acceptance.get("required_package_refs") or []:
        observed = str(workflow_evidence.get(key) or "").strip()
        checks.append(
            {
                "name": f"package_ref:{key}",
                "ok": bool(observed),
                "expected": "non-empty",
                "observed": observed,
            }
        )

    expected_vm_engine = str(acceptance.get("required_vm_engine") or "").strip()
    if expected_vm_engine:
        checks.append(
            {
                "name": "workflow_vm:engine",
                "ok": str(event_evidence.get("vm_engine") or "").strip() == expected_vm_engine,
                "expected": expected_vm_engine,
                "observed": str(event_evidence.get("vm_engine") or "").strip(),
            }
        )

    expected_result_status = str(acceptance.get("required_result_status") or "").strip()
    if expected_result_status:
        checks.append(
            {
                "name": "receipt:result_status",
                "ok": str(receipt_evidence.get("result_status") or "").strip() == expected_result_status,
                "expected": expected_result_status,
                "observed": str(receipt_evidence.get("result_status") or "").strip(),
            }
        )

    expected_receipt_phase = str(acceptance.get("required_receipt_phase") or "").strip()
    if expected_receipt_phase:
        checks.append(
            {
                "name": "receipt:execution_phase",
                "ok": str(receipt_evidence.get("execution_phase") or "").strip() == expected_receipt_phase,
                "expected": expected_receipt_phase,
                "observed": str(receipt_evidence.get("execution_phase") or "").strip(),
            }
        )

    if bool(acceptance.get("require_output_bundle_summary")):
        observed_summary = str(receipt_evidence.get("output_bundle_summary") or "").strip()
        checks.append(
            {
                "name": "receipt:output_bundle_summary",
                "ok": bool(observed_summary),
                "expected": "non-empty",
                "observed": observed_summary,
            }
        )

    ok = all(bool(item.get("ok")) for item in checks)
    return {
        "ok": ok,
        "checks": checks,
        "required_event_types": list(acceptance.get("required_event_types") or []),
        "observed_event_types": sorted(observed_event_types),
    }


def _fixture_snapshot(fixture: dict[str, Any]) -> dict[str, Any]:
    mission = _as_dict(fixture.get("mission"))
    nodes = [_as_dict(item) for item in _as_list(mission.get("nodes"))]
    return {
        "demo_id": str(fixture.get("demo_id") or "").strip(),
        "display_name": str(fixture.get("display_name") or "").strip(),
        "framework_profile": _as_dict(fixture.get("framework_profile")),
        "mission_input": {
            "mission_type": str(mission.get("mission_type") or "").strip(),
            "title": str(mission.get("title") or "").strip(),
            "goal": str(mission.get("goal") or "").strip(),
            "inputs": _as_dict(mission.get("inputs")),
            "success_criteria": list(mission.get("success_criteria") or []),
            "constraints": _as_dict(mission.get("constraints")),
            "node_ids": [str(item.get("node_id") or "").strip() for item in nodes if str(item.get("node_id") or "").strip()],
        },
        "acceptance": _as_dict(fixture.get("acceptance")),
    }


def _campaign_smoke_spec(workspace: str) -> dict[str, Any]:
    return {
        "top_level_goal": "Ship observe-first Campaign MVP smoke flow",
        "materials": [
            "docs/daily-upgrade/0325/05_Orchestrator完善设计与实施计划.md",
            "docs/daily-upgrade/0325/09_长期自治Campaign任务层_讨论草稿.md",
        ],
        "hard_constraints": [
            "top-level goal remains immutable",
            "campaign stays single-workspace single-repo",
        ],
        "workspace_root": workspace,
        "repo_root": workspace,
        "iteration_budget": {
            "max_iterations": 2,
            "max_minutes": 30,
            "max_file_changes": 4,
        },
    }


def _campaign_smoke_checks(
    *,
    created: Mapping[str, Any],
    resumed: Mapping[str, Any],
    stopped: Mapping[str, Any],
    initial_window: Mapping[str, Any],
    resumed_window: Mapping[str, Any],
    final_window: Mapping[str, Any],
) -> dict[str, Any]:
    created_map = _as_dict(created)
    resumed_map = _as_dict(resumed)
    stopped_map = _as_dict(stopped)
    created_metadata = _as_dict(created_map.get("metadata"))
    created_refs = _as_dict(created_metadata.get("control_plane_refs")) or _as_dict(created_metadata.get("legacy_refs"))
    initial_campaign_evidence = _as_dict(_as_dict(initial_window).get("campaign_evidence"))
    initial_stable = _as_dict(_as_dict(initial_window).get("stable_evidence"))
    resumed_campaign_evidence = _as_dict(_as_dict(resumed_window).get("campaign_evidence"))
    final_session_view = _as_dict(_as_dict(final_window).get("session_view"))
    checks = [
        {
            "name": "campaign_refs_present",
            "ok": all(
                (
                    str(created_map.get(key) or "").strip()
                    or str(created_refs.get(key) or "").strip()
                )
                for key in ("campaign_id", "mission_id", "supervisor_session_id")
            ),
        },
        {
            "name": "initial_phase_shape",
            "ok": str(created_map.get("current_phase") or "").strip() == "discover"
            and str(created_map.get("next_phase") or "").strip() in {"discover", "implement"},
        },
        {
            "name": "session_count_visible",
            "ok": int(initial_stable.get("workflow_session_count") or 0) >= 1,
        },
        {
            "name": "initial_artifact_count",
            "ok": int(resumed_campaign_evidence.get("artifact_count") or 0) >= 1,
        },
        {
            "name": "verdict_count_after_resume",
            "ok": int(resumed_campaign_evidence.get("verdict_count") or 0) == 1,
        },
        {
            "name": "goal_immutable_through_resume",
            "ok": str(created_map.get("top_level_goal") or "").strip()
            and str(created_map.get("top_level_goal") or "").strip()
            == str(resumed_map.get("top_level_goal") or "").strip()
            == str(stopped_map.get("top_level_goal") or "").strip(),
        },
        {
            "name": "constraints_immutable_through_resume",
            "ok": list(created_map.get("hard_constraints") or [])
            == list(resumed_map.get("hard_constraints") or [])
            == list(stopped_map.get("hard_constraints") or []),
        },
        {
            "name": "session_stopped",
            "ok": str(final_session_view.get("status") or "").strip() in {"paused", "stopped"}
            and not str(final_session_view.get("active_step") or "").strip(),
        },
    ]
    return {
        "ok": all(bool(item.get("ok")) for item in checks),
        "checks": checks,
    }


def _campaign_smoke_payload(
    *,
    workspace: str,
    created: Mapping[str, Any],
    resumed: Mapping[str, Any],
    stopped: Mapping[str, Any],
    initial_window: Mapping[str, Any],
    resumed_window: Mapping[str, Any],
    final_window: Mapping[str, Any],
) -> dict[str, Any]:
    created_map = _as_dict(created)
    created_metadata = _as_dict(created_map.get("metadata"))
    created_refs = _as_dict(created_metadata.get("control_plane_refs")) or _as_dict(created_metadata.get("legacy_refs"))
    mission_id = str(created_map.get("mission_id") or created_refs.get("mission_id") or "").strip()
    workflow_session_id = str(
        created_map.get("supervisor_session_id")
        or created_refs.get("supervisor_session_id")
        or created_refs.get("canonical_session_id")
        or ""
    ).strip()
    final_session_view = _as_dict(_as_dict(final_window).get("session_view"))
    acceptance = _campaign_smoke_checks(
        created=created,
        resumed=resumed,
        stopped=stopped,
        initial_window=initial_window,
        resumed_window=resumed_window,
        final_window=final_window,
    )
    return {
        "ok": bool(acceptance.get("ok")),
        "demo_id": "campaign",
        "display_name": "campaign single-flow smoke",
        "workspace": workspace,
        "campaign": {
            "created": dict(created_map),
            "resumed": dict(_as_dict(resumed)),
            "stopped": dict(_as_dict(stopped)),
        },
        "writeback": {
            "campaign_id": str(created_map.get("campaign_id") or "").strip(),
            "mission_id": mission_id,
            "workflow_session_id": workflow_session_id,
            "campaign_status": str(_as_dict(stopped).get("status") or "").strip(),
            "mission_status": str(_as_dict(_as_dict(final_window).get("mission_view")).get("status") or "").strip(),
            "workflow_session_status": str(final_session_view.get("status") or "").strip(),
        },
        "observation": {
            "initial": dict(_as_dict(initial_window)),
            "resumed": dict(_as_dict(resumed_window)),
            "final": dict(_as_dict(final_window)),
        },
        "acceptance": acceptance,
    }


def _demo_payload(service, fixture: dict[str, Any], mission_id: str, run_summary: dict[str, Any], *, requested_mode: str) -> dict[str, Any]:
    mission_summary = service.summarize_mission(mission_id)
    branch = _as_dict((mission_summary.get("branches") or [{}])[0])
    branch_summary = service.summarize_branch(str(branch.get("branch_id") or "").strip())
    branch_metadata = _as_dict(branch_summary.get("metadata"))
    result_payload = _as_dict(branch_metadata.get("result_payload"))
    workflow_ir_full = _as_dict(branch_metadata.get("workflow_ir"))
    workflow_session = _as_dict(branch.get("workflow_session"))
    events = service.list_delivery_events(mission_id)

    workflow_evidence = _workflow_evidence(workflow_ir_full)
    receipt_evidence = _receipt_evidence(result_payload)
    event_evidence = _event_evidence(events)
    writeback = {
        "mission_status": str(mission_summary.get("status") or "").strip(),
        "node_status": str(_as_dict((mission_summary.get("nodes") or [{}])[0]).get("status") or "").strip(),
        "branch_status": str(branch.get("status") or "").strip(),
        "workflow_session_status": str(workflow_session.get("status") or "").strip(),
    }
    acceptance = _build_checks(
        fixture,
        workflow_evidence=workflow_evidence,
        receipt_evidence=receipt_evidence,
        writeback=writeback,
        event_evidence=event_evidence,
    )

    return {
        "demo_id": str(fixture.get("demo_id") or "").strip(),
        "display_name": str(fixture.get("display_name") or "").strip(),
        "requested_mode": str(requested_mode or "").strip(),
        "fixture": _fixture_snapshot(fixture),
        "run_summary": {
            "phase": run_summary.get("phase"),
            "dispatched_count": run_summary.get("dispatched_count"),
            "executed_branch_count": run_summary.get("executed_branch_count"),
            "completed_branch_count": run_summary.get("completed_branch_count"),
            "failed_branch_count": run_summary.get("failed_branch_count"),
            "note": run_summary.get("note"),
        },
        "writeback": {
            **writeback,
            "mission_id": str(mission_summary.get("mission_id") or "").strip(),
            "branch_id": str(branch.get("branch_id") or "").strip(),
            "workflow_session_id": str(workflow_session.get("session_id") or "").strip(),
        },
        "workflow_ir": workflow_evidence,
        "workflow_session": {
            "status": str(workflow_session.get("status") or "").strip(),
            "active_step": str(workflow_session.get("active_step") or "").strip(),
            "template_id": str(workflow_session.get("template_id") or _as_dict(workflow_session.get("template")).get("template_id") or "").strip(),
            "artifact_registry": _as_dict(workflow_session.get("artifact_registry")),
            "collaboration": _as_dict(workflow_session.get("collaboration")),
        },
        "receipts": receipt_evidence,
        "runtime_debug": _as_dict(branch_summary.get("runtime_debug")),
        "events": event_evidence["important_events"],
        "acceptance": acceptance,
        "ok": bool(acceptance.get("ok")),
    }


def run_demo_smoke(*, demo_id: str, workspace: str, timeout_seconds: int, runtime_cli: str = "") -> dict[str, Any]:
    requested_mode = str(demo_id or "").strip()
    resolved_demo_id = _resolve_demo_id(requested_mode)
    fixture = build_demo_fixture(resolved_demo_id, runtime_cli=runtime_cli)
    service = build_orchestrator_service_for_workspace(workspace)
    mission_payload = _as_dict(fixture.get("mission"))
    mission = service.create_mission(
        mission_type=str(mission_payload.get("mission_type") or resolved_demo_id).strip(),
        title=str(mission_payload.get("title") or resolved_demo_id).strip(),
        goal=str(mission_payload.get("goal") or "").strip(),
        inputs=_as_dict(mission_payload.get("inputs")),
        success_criteria=list(mission_payload.get("success_criteria") or []),
        constraints=_as_dict(mission_payload.get("constraints")),
        nodes=[_as_dict(item) for item in _as_list(mission_payload.get("nodes"))],
        metadata={"framework_profile": _as_dict(fixture.get("framework_profile")), "demo_id": resolved_demo_id},
    )
    run_summary = run_orchestrator_service(
        _default_config(workspace, timeout_seconds=timeout_seconds, runtime_cli=runtime_cli),
        once=True,
    )
    return _demo_payload(service, fixture, mission.mission_id, run_summary, requested_mode=requested_mode)


def run_campaign_smoke(*, workspace: str, timeout_seconds: int = 0, runtime_cli: str = "") -> dict[str, Any]:
    del timeout_seconds, runtime_cli
    campaign_service = OrchestratorCampaignService()
    query_service = OrchestratorQueryService(campaign_service=campaign_service)
    created = campaign_service.create_campaign(workspace, _campaign_smoke_spec(workspace))
    campaign_id = str(_as_dict(created).get("campaign_id") or "").strip()
    initial_window = query_service.get_campaign_observation_window(workspace, campaign_id)
    resumed = campaign_service.resume_campaign(workspace, campaign_id)
    resumed_window = query_service.get_campaign_observation_window(workspace, campaign_id)
    stopped = campaign_service.stop_campaign(workspace, campaign_id)
    final_window = query_service.get_campaign_observation_window(workspace, campaign_id)
    return _campaign_smoke_payload(
        workspace=workspace,
        created=created,
        resumed=resumed,
        stopped=stopped,
        initial_window=initial_window,
        resumed_window=resumed_window,
        final_window=final_window,
    )


def run_superpowers_demo_smoke(*, workspace: str, timeout_seconds: int, runtime_cli: str = "") -> dict[str, Any]:
    return run_demo_smoke(
        demo_id="superpowers_like",
        workspace=workspace,
        timeout_seconds=timeout_seconds,
        runtime_cli=runtime_cli,
    )


def run_openfang_demo_smoke(*, workspace: str, timeout_seconds: int, runtime_cli: str = "") -> dict[str, Any]:
    return run_demo_smoke(
        demo_id="openfang_inspired",
        workspace=workspace,
        timeout_seconds=timeout_seconds,
        runtime_cli=runtime_cli,
    )


def run_normal_smoke(*, workspace: str, timeout_seconds: int, runtime_cli: str = "") -> dict[str, Any]:
    return run_superpowers_demo_smoke(
        workspace=workspace,
        timeout_seconds=timeout_seconds,
        runtime_cli=runtime_cli,
    )


def run_research_smoke(*, workspace: str, timeout_seconds: int) -> dict[str, Any]:
    return run_openfang_demo_smoke(
        workspace=workspace,
        timeout_seconds=timeout_seconds,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run frozen standalone orchestrator demo fixtures")
    parser.add_argument("--workspace", default="", help="workspace root; defaults to a temporary workspace")
    parser.add_argument(
        "--mode",
        choices=tuple(list_demo_fixture_ids()) + ("campaign", "normal", "research", "both"),
        default="both",
    )
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--runtime-cli", default="", help="optional explicit CLI provider for the demo run")
    parser.add_argument("--keep-workspace", action="store_true", help="keep the temporary workspace and print its path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    workspace = str(args.workspace or "").strip()
    if workspace:
        workspace = _prepare_workspace(workspace)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="orchestrator_smoke_")
        workspace = _prepare_workspace(temp_dir.name)

    modes = list_demo_fixture_ids() if args.mode == "both" else (_resolve_demo_id(args.mode),)
    demos: list[dict[str, Any]] = []
    for mode in modes:
        if mode == "campaign":
            demos.append(
                run_campaign_smoke(
                    workspace=workspace,
                    timeout_seconds=args.timeout_seconds,
                    runtime_cli=str(args.runtime_cli or "").strip(),
                )
            )
            continue
        demos.append(
            run_demo_smoke(
                demo_id=mode,
                workspace=workspace,
                timeout_seconds=args.timeout_seconds,
                runtime_cli=str(args.runtime_cli or "").strip(),
            )
        )

    payload = {
        "ok": all(bool(item.get("ok")) for item in demos),
        "workspace": workspace,
        "temporary_workspace": temp_dir is not None,
        "demos": demos,
    }

    if temp_dir is not None and not args.keep_workspace:
        temp_path = temp_dir.name
        temp_dir.cleanup()
        payload["workspace_cleaned"] = not Path(temp_path).exists()
        _print_json(payload)
        return 0 if payload["ok"] else 1

    if temp_dir is not None and args.keep_workspace:
        payload["kept_workspace"] = workspace
        temp_dir = None

    _print_json(payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
