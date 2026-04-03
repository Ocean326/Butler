from __future__ import annotations

from dataclasses import asdict, is_dataclass
from importlib import import_module
import inspect
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from butler_main.agents_os.skills import normalize_skill_exposure_payload
from butler_main.runtime_os.process_runtime import WorkflowFactory

from ..background_task_bundle import build_campaign_bundle_metadata, ensure_campaign_bundle_files
from ..workspace import build_orchestrator_service_for_workspace, resolve_orchestrator_root

_CAMPAIGN_RUN_DIR_NAME = "campaigns"
_CAMPAIGN_DOMAIN_MODULE = "butler_main.domains.campaign"
_REAL_CAMPAIGN_DOMAIN_PREFIXES = (
    "butler_main.products.campaign_orchestrator.campaign",
    "butler_main.domains.campaign",
)


def _campaign_root_for_workspace(workspace: str) -> Path:
    return Path(resolve_orchestrator_root(workspace)) / _CAMPAIGN_RUN_DIR_NAME


def _campaign_store_root_for_workspace(workspace: str) -> Path:
    return Path(resolve_orchestrator_root(workspace))


def _load_campaign_domain_api() -> tuple[type[Any], type[Any], type[Any] | None]:
    module = import_module(_CAMPAIGN_DOMAIN_MODULE)
    service_cls = getattr(module, "CampaignDomainService")
    store_cls = getattr(module, "FileCampaignStore")
    spec_cls = getattr(module, "CampaignSpec", None)
    return service_cls, store_cls, spec_cls


def _coerce_campaign_spec(raw_spec: Any, spec_cls: type[Any] | None) -> Any:
    if spec_cls is None or isinstance(raw_spec, spec_cls):
        return raw_spec
    if isinstance(raw_spec, Mapping):
        normalized = dict(raw_spec)
        if "goal" in normalized and "top_level_goal" in normalized:
            normalized.pop("goal", None)
        if hasattr(spec_cls, "from_dict") and callable(spec_cls.from_dict):
            return spec_cls.from_dict(normalized)
        return spec_cls(**normalized)
    return raw_spec


def _mapping_payload(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        payload = value.to_dict()
        if isinstance(payload, Mapping):
            return dict(payload)
    if is_dataclass(value):
        payload = asdict(value)
        if isinstance(payload, dict):
            return payload
    return None


def _payload_dict(value: Any) -> dict[str, Any]:
    payload = _mapping_payload(value)
    if payload is None:
        raise TypeError(f"campaign payload is not dict-like: {type(value).__name__}")
    return payload


def _payload_list(values: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in values or []:
        result.append(_payload_dict(item))
    return result


def _limited_payload_list(values: Any, *, limit: int = 0) -> list[dict[str, Any]]:
    items = _payload_list(values)
    target_limit = max(0, int(limit or 0))
    if target_limit > 0:
        return items[:target_limit]
    return items


def _shared_state_contract_versions(contract_history: list[dict[str, Any]]) -> list[int]:
    versions: list[int] = []
    for item in contract_history:
        version = int(dict(item).get("version") or 0)
        if version > 0:
            versions.append(version)
    return versions


def _phase_history_from_metadata(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    metadata = _mapping_payload(payload.get("metadata")) or {}
    return _payload_list(metadata.get("phase_history"))


def _default_campaign_title(goal: Any) -> str:
    text = " ".join(str(goal or "").strip().split())
    return text[:80] if text else "Campaign MVP"


def _normalize_spec_payload(raw_spec: Any, workspace: str) -> Any:
    payload = _mapping_payload(raw_spec)
    if payload is None:
        return raw_spec
    normalized = dict(payload)
    if not str(normalized.get("top_level_goal") or "").strip():
        normalized["top_level_goal"] = str(normalized.get("goal") or "").strip()
    normalized["workspace_root"] = str(normalized.get("workspace_root") or workspace).strip() or workspace
    normalized["repo_root"] = (
        str(normalized.get("repo_root") or normalized["workspace_root"]).strip()
        or normalized["workspace_root"]
    )
    normalized.pop("goal", None)
    if not str(normalized.get("campaign_title") or "").strip():
        normalized["campaign_title"] = _default_campaign_title(normalized.get("top_level_goal"))
    _normalize_template_contract_payload(normalized)
    _normalize_feedback_contract_payload(normalized)
    _normalize_contract_metadata(normalized)
    _normalize_runtime_metadata(normalized)
    return normalized


def _normalize_contract_metadata(payload: dict[str, Any]) -> None:
    metadata = _mapping_payload(payload.get("metadata")) or {}
    planning_contract = _mapping_payload(metadata.get("planning_contract")) or {}
    if planning_contract:
        planning_contract.setdefault("mode_id", _infer_mode_id(payload, metadata))
        planning_contract.setdefault("method_profile_id", "")
        planning_contract.setdefault("plan_only", False)
        planning_contract.setdefault("draft_ref", "")
        planning_contract.setdefault("spec_ref", "")
        planning_contract.setdefault("plan_ref", "")
        planning_contract.setdefault("progress_ref", "")
        metadata["planning_contract"] = planning_contract
    evaluation_contract = _mapping_payload(metadata.get("evaluation_contract")) or {}
    if evaluation_contract:
        evaluation_contract.setdefault("review_ref", "")
        evaluation_contract.setdefault("latest_review_decision", "")
        evaluation_contract.setdefault("latest_acceptance_decision", "")
        metadata["evaluation_contract"] = evaluation_contract
    governance_contract = _mapping_payload(metadata.get("governance_contract")) or {}
    if governance_contract:
        governance_contract.setdefault("autonomy_profile", "reviewed_delivery")
        governance_contract.setdefault("risk_level", "medium")
        governance_contract.setdefault("approval_state", "none")
        metadata["governance_contract"] = governance_contract
    if metadata:
        payload["metadata"] = metadata


def _normalize_runtime_metadata(payload: dict[str, Any]) -> None:
    metadata = _mapping_payload(payload.get("metadata")) or {}
    planning_contract = _mapping_payload(metadata.get("planning_contract")) or {}
    runtime_payload = _mapping_payload(metadata.get("campaign_runtime")) or {}
    raw_codex_runtime_request = _mapping_payload(metadata.get("codex_runtime_request")) or {}
    created_from = str(metadata.get("created_from") or "").strip().lower()
    mode_id = str(planning_contract.get("mode_id") or _infer_mode_id(payload, metadata)).strip().lower()
    if not runtime_payload and created_from == "campaign_negotiation" and mode_id in {"delivery", "research"}:
        runtime_payload = {"mode": "codex"}
    if runtime_payload:
        mode = str(runtime_payload.get("mode") or "").strip().lower() or "deterministic"
        if mode not in {"deterministic", "codex"}:
            mode = "deterministic"
        runtime_payload["mode"] = mode
        metadata["campaign_runtime"] = runtime_payload
        if mode == "codex":
            raw_skill_exposure = _mapping_payload(metadata.get("skill_exposure")) or _mapping_payload(
                raw_codex_runtime_request.get("skill_exposure")
            ) or {}
            skill_exposure = normalize_skill_exposure_payload(
                raw_skill_exposure,
                default_collection_id="codex_default",
                provider_skill_source="butler",
            )
            if skill_exposure is not None:
                metadata["skill_exposure"] = skill_exposure
    if created_from == "campaign_negotiation":
        metadata["strict_acceptance_required"] = True
    if metadata:
        payload["metadata"] = metadata


def _infer_mode_id(payload: Mapping[str, Any], metadata: Mapping[str, Any]) -> str:
    planning_contract = _mapping_payload(metadata.get("planning_contract")) or {}
    explicit_mode_id = str(
        payload.get("mode_id")
        or metadata.get("mode_id")
        or planning_contract.get("mode_id")
        or ""
    ).strip().lower()
    if explicit_mode_id in {"plan", "delivery", "research", "status", "govern"}:
        return explicit_mode_id
    template_contract = _mapping_payload(metadata.get("template_contract")) or {}
    template_origin = str(
        payload.get("template_origin")
        or metadata.get("template_origin")
        or template_contract.get("template_origin")
        or ""
    ).strip()
    if template_origin == "campaign.research_then_implement":
        return "research"
    if template_origin in {"campaign.single_repo_delivery", "campaign.guarded_autonomy"}:
        return "delivery"
    if str(payload.get("created_from") or metadata.get("created_from") or "").strip().lower() == "campaign_negotiation":
        return "delivery"
    return "unknown"


def _normalize_template_contract_payload(payload: dict[str, Any]) -> None:
    metadata = _mapping_payload(payload.get("metadata")) or {}
    template_contract = _mapping_payload(metadata.get("template_contract")) or {}

    template_origin = str(payload.get("template_origin") or "").strip()
    if not template_origin:
        template_origin = str(
            metadata.get("template_origin")
            or metadata.get("template_id")
            or metadata.get("template")
            or template_contract.get("template_origin")
            or template_contract.get("template_id")
            or template_contract.get("template")
            or ""
        ).strip()

    composition_mode = str(payload.get("composition_mode") or "").strip().lower()
    if not composition_mode:
        composition_mode = str(
            metadata.get("composition_mode") or template_contract.get("composition_mode") or ""
        ).strip().lower()
    if composition_mode not in {"template", "composition"}:
        composition_mode = ""

    sentinel = object()
    raw_skeleton = payload.get("skeleton_changed", sentinel)
    if raw_skeleton is sentinel:
        raw_skeleton = metadata.get("skeleton_changed", sentinel)
    if raw_skeleton is sentinel:
        raw_skeleton = template_contract.get("skeleton_changed", sentinel)
    skeleton_changed = bool(raw_skeleton) if raw_skeleton is not sentinel else False

    composition_plan = payload.get("composition_plan", None)
    if composition_plan is None:
        composition_plan = metadata.get("composition_plan")
    if composition_plan is None:
        composition_plan = template_contract.get("composition_plan")
    if not isinstance(composition_plan, Mapping):
        composition_plan = {}
    else:
        composition_plan = dict(composition_plan)

    created_from = str(payload.get("created_from") or metadata.get("created_from") or template_contract.get("created_from") or "").strip()
    negotiation_session_id = str(
        payload.get("negotiation_session_id")
        or metadata.get("negotiation_session_id")
        or template_contract.get("negotiation_session_id")
        or ""
    ).strip()

    if skeleton_changed and composition_mode != "composition":
        composition_mode = "composition"
    if not composition_mode:
        if skeleton_changed or composition_plan:
            composition_mode = "composition"
        elif template_origin:
            composition_mode = "template"

    if any(
        [
            template_origin,
            composition_mode,
            skeleton_changed,
            composition_plan,
            created_from,
            negotiation_session_id,
        ]
    ):
        payload["template_origin"] = template_origin
        payload["composition_mode"] = composition_mode
        payload["skeleton_changed"] = bool(skeleton_changed)
        payload["composition_plan"] = composition_plan
        if created_from:
            payload["created_from"] = created_from
        if negotiation_session_id:
            payload["negotiation_session_id"] = negotiation_session_id
        metadata = dict(metadata)
        contract = {
            "template_origin": template_origin,
            "composition_mode": composition_mode,
            "skeleton_changed": bool(skeleton_changed),
            "composition_plan": composition_plan,
        }
        if created_from:
            contract["created_from"] = created_from
        if negotiation_session_id:
            contract["negotiation_session_id"] = negotiation_session_id
        metadata["template_contract"] = contract
        payload["metadata"] = metadata


def _normalize_feedback_contract_payload(payload: dict[str, Any]) -> None:
    metadata = _mapping_payload(payload.get("metadata")) or {}
    feedback_contract = _mapping_payload(payload.get("feedback_contract")) or {}
    if not feedback_contract:
        feedback_contract = _mapping_payload(metadata.get("feedback_contract")) or {}
    has_signal = bool(feedback_contract)
    if not has_signal:
        has_signal = any(
            str(payload.get(key) or metadata.get(key) or "").strip()
            for key in (
                "feedback_platform",
                "feedback_target",
                "feedback_thread_id",
                "feedback_session_id",
                "feedback_progress_surface",
            )
        )
    if not has_signal and metadata.get("feedback_doc_enabled") is not None:
        has_signal = True
    if not has_signal:
        return

    platform = str(
        payload.get("feedback_platform")
        or feedback_contract.get("platform")
        or metadata.get("feedback_platform")
        or ""
    ).strip().lower()
    target = str(
        payload.get("feedback_target")
        or feedback_contract.get("target")
        or metadata.get("feedback_target")
        or ""
    ).strip()
    target_type = str(
        payload.get("feedback_target_type")
        or feedback_contract.get("target_type")
        or metadata.get("feedback_target_type")
        or "open_id"
    ).strip() or "open_id"
    delivery_mode = str(
        payload.get("feedback_delivery_mode")
        or feedback_contract.get("delivery_mode")
        or metadata.get("feedback_delivery_mode")
        or "reply"
    ).strip() or "reply"
    thread_id = str(
        payload.get("feedback_thread_id")
        or feedback_contract.get("thread_id")
        or metadata.get("feedback_thread_id")
        or ""
    ).strip()
    session_id = str(
        payload.get("feedback_session_id")
        or feedback_contract.get("session_id")
        or metadata.get("feedback_session_id")
        or ""
    ).strip()
    progress_surface = str(
        payload.get("feedback_progress_surface")
        or feedback_contract.get("progress_surface")
        or metadata.get("feedback_progress_surface")
        or ""
    ).strip()
    raw_doc_enabled = feedback_contract.get("doc_enabled", metadata.get("feedback_doc_enabled"))
    doc_enabled = bool(raw_doc_enabled) if raw_doc_enabled is not None else platform == "feishu"
    contract_metadata = _mapping_payload(feedback_contract.get("metadata")) or {}

    contract = {
        "platform": platform,
        "target": target,
        "target_type": target_type,
        "delivery_mode": delivery_mode,
        "thread_id": thread_id,
        "session_id": session_id,
        "progress_surface": progress_surface or ("doc_plus_push" if platform == "feishu" else "push_only"),
        "doc_enabled": doc_enabled,
        "metadata": contract_metadata,
    }
    contract = {
        key: value
        for key, value in contract.items()
        if value not in (None, "", {}) and not (key == "doc_enabled" and raw_doc_enabled is None and value is False)
    }
    if not contract:
        return
    metadata = dict(metadata)
    metadata["feedback_contract"] = contract
    payload["metadata"] = metadata


def _prepare_bundle_metadata(
    *,
    workspace: str,
    campaign_id: str,
    spec_payload: dict[str, Any],
) -> dict[str, Any]:
    metadata = _mapping_payload(spec_payload.get("metadata")) or {}
    bundle_metadata = build_campaign_bundle_metadata(
        workspace=workspace,
        campaign_id=campaign_id,
        campaign_title=str(spec_payload.get("campaign_title") or spec_payload.get("top_level_goal") or "").strip(),
        created_at=str(metadata.get("created_at") or "").strip(),
        metadata=metadata,
    )
    planning_contract = _mapping_payload(metadata.get("planning_contract")) or {}
    if planning_contract:
        bundle_root = Path(str(bundle_metadata.get("bundle_root") or "").strip())
        if not str(planning_contract.get("spec_ref") or "").strip():
            planning_contract["spec_ref"] = str(bundle_root / "briefs" / "spec.md")
        if not str(planning_contract.get("plan_ref") or "").strip():
            planning_contract["plan_ref"] = str(bundle_root / "briefs" / "plan.md")
        if not str(planning_contract.get("progress_ref") or "").strip():
            planning_contract["progress_ref"] = str(bundle_root / "progress.md")
        metadata["planning_contract"] = planning_contract
    metadata.update(bundle_metadata)
    metadata.setdefault("resolved_correctness_checks", [])
    metadata.setdefault("waived_correctness_checks", [])
    metadata.setdefault("primary_carrier", "campaign")
    spec_payload["metadata"] = metadata
    return spec_payload


def _feedback_contract_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    direct = _mapping_payload(payload.get("feedback_contract")) or {}
    if direct:
        return direct
    metadata = _mapping_payload(payload.get("metadata")) or {}
    return _mapping_payload(metadata.get("feedback_contract")) or {}


def _merge_feedback_doc_payload(payload: Mapping[str, Any], feedback_doc: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    doc_payload = dict(feedback_doc or {})
    if not doc_payload:
        return enriched
    enriched["feedback_doc"] = doc_payload
    metadata = _mapping_payload(enriched.get("metadata")) or {}
    metadata["feedback_doc"] = doc_payload
    enriched["metadata"] = metadata
    return enriched


def _merge_metadata_patch(base: Mapping[str, Any] | None, patch: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(patch or {}).items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge_metadata_patch(merged.get(key), value)
        else:
            merged[key] = value
    return merged


def _bootstrap_feedback_surface(
    *,
    workspace: str,
    spec_payload: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    feedback_contract = _feedback_contract_from_payload(spec_payload)
    if str(feedback_contract.get("platform") or "").strip().lower() != "feishu":
        return None
    campaign_id = str(payload.get("campaign_id") or "").strip()
    mission_id = str(payload.get("mission_id") or "").strip()
    if not campaign_id:
        return None
    try:
        from ..feedback_notifier import OrchestratorFeedbackNotifier

        notifier = OrchestratorFeedbackNotifier(workspace=workspace)
        return notifier.ensure_feedback_surface_for_campaign(
            campaign_id=campaign_id,
            mission_id=mission_id,
            feedback_contract=feedback_contract,
            startup_mode=str((_mapping_payload(spec_payload.get("metadata")) or {}).get("startup_mode") or "").strip(),
            send_startup_push=True,
        )
    except Exception:
        return None


def _new_campaign_id() -> str:
    return f"campaign_{uuid4().hex[:12]}"


def _campaign_role_bindings() -> list[dict[str, Any]]:
    return [
        {
            "role_id": "campaign_supervisor",
            "agent_spec_id": "butler.campaign_supervisor",
            "capability_id": "campaign.supervise",
            "metadata": {"final_decider": False},
        },
        {
            "role_id": "campaign_reviewer",
            "agent_spec_id": "butler.campaign_reviewer",
            "capability_id": "campaign.review",
            "metadata": {"final_decider": True},
        },
    ]


def _campaign_workflow_template() -> dict[str, Any]:
    return {
        "template_id": "campaign.supervisor.v1",
        "kind": "campaign_supervisor",
        "roles": [
            {"role_id": "campaign_supervisor", "capability_id": "campaign.supervise"},
            {"role_id": "campaign_reviewer", "capability_id": "campaign.review"},
        ],
        "steps": [
            {"step_id": "discover", "title": "Discover", "kind": "dispatch"},
            {"step_id": "implement", "title": "Implement", "kind": "dispatch"},
            {"step_id": "evaluate", "title": "Evaluate", "kind": "verify"},
            {"step_id": "iterate", "title": "Iterate", "kind": "finalize"},
        ],
        "metadata": {"domain_layer": "campaign", "mvp_version": "v1"},
    }


def _campaign_agent_turn_template() -> dict[str, Any]:
    return {
        "template_id": "campaign.agent_turn.v1",
        "kind": "campaign_agent_turn",
        "roles": [
            {"role_id": "campaign_supervisor", "capability_id": "campaign.supervise"},
        ],
        "steps": [
            {"step_id": "turn", "title": "Campaign Turn", "kind": "dispatch"},
        ],
        "metadata": {"domain_layer": "campaign", "engine": "agent_turn"},
    }


def _create_campaign_mission(
    *,
    orchestrator_service,
    campaign_id: str,
    spec_payload: Mapping[str, Any],
) -> Any:
    title = str(spec_payload.get("campaign_title") or "").strip() or _default_campaign_title(
        spec_payload.get("top_level_goal")
    )
    goal = str(spec_payload.get("top_level_goal") or "").strip()
    workflow_template = _campaign_workflow_template()
    role_bindings = _campaign_role_bindings()
    feedback_contract = _feedback_contract_from_payload(spec_payload)
    return orchestrator_service.create_mission(
        mission_type="campaign",
        title=title,
        goal=goal,
        priority=80,
        inputs={
            "materials": list(spec_payload.get("materials") or []),
            "hard_constraints": list(spec_payload.get("hard_constraints") or []),
            "workspace_root": str(spec_payload.get("workspace_root") or "").strip(),
            "repo_root": str(spec_payload.get("repo_root") or "").strip(),
        },
        constraints={"hard_constraints": list(spec_payload.get("hard_constraints") or [])},
        nodes=[
            {
                "node_id": "campaign_supervisor",
                "kind": "campaign_supervisor",
                "title": "Campaign supervisor",
                "runtime_plan": {
                    "worker_profile": "campaign.supervisor",
                    "workflow_template": workflow_template,
                    "role_bindings": role_bindings,
                    "workflow_inputs": {
                        "campaign_id": campaign_id,
                        "top_level_goal": goal,
                    },
                },
                "metadata": {
                    "campaign_id": campaign_id,
                    "domain_layer": "campaign",
                    "primary_carrier": "campaign",
                },
            }
        ],
        metadata={
            "campaign_id": campaign_id,
            "domain_layer": "campaign",
            "single_repo_mode": True,
            "primary_carrier": "campaign",
            **({"feedback_contract": feedback_contract} if feedback_contract else {}),
        },
        initial_status="parked",
        activate_on_create=False,
    )


def _create_supervisor_session(
    *,
    workflow_factory: WorkflowFactory,
    campaign_id: str,
    mission_id: str,
    spec_payload: Mapping[str, Any],
) -> Any:
    return workflow_factory.create_session(
        template=_campaign_agent_turn_template(),
        driver_kind="campaign_supervisor",
        role_bindings=[_campaign_role_bindings()[0]],
        active_step="turn",
        initial_shared_state={
            "campaign_id": campaign_id,
            "mission_id": mission_id,
            "campaign_status": "draft",
            "turn_count": 0,
            "top_level_goal": str(spec_payload.get("top_level_goal") or "").strip(),
            "materials": list(spec_payload.get("materials") or []),
            "hard_constraints": list(spec_payload.get("hard_constraints") or []),
            "workspace_root": str(spec_payload.get("workspace_root") or "").strip(),
            "repo_root": str(spec_payload.get("repo_root") or "").strip(),
        },
        metadata={
            "campaign_id": campaign_id,
            "mission_id": mission_id,
            "domain_layer": "campaign",
            "created_by": "OrchestratorCampaignService",
        },
    )


def _bind_supervisor_session_to_mission(
    *,
    orchestrator_service,
    mission_id: str,
    campaign_id: str,
    supervisor_session: Any,
) -> None:
    if not hasattr(orchestrator_service, "get_mission") or not hasattr(orchestrator_service, "_mission_store"):
        return
    mission = orchestrator_service.get_mission(str(mission_id or "").strip())
    if mission is None:
        return
    node = mission.node_by_id("campaign_supervisor")
    if node is None:
        return
    session_id = str(getattr(supervisor_session, "session_id", "") or "").strip()
    if not session_id:
        return
    template_id = str(getattr(supervisor_session, "template_id", "") or "campaign.agent_turn.v1").strip()
    driver_kind = str(getattr(supervisor_session, "driver_kind", "") or "campaign_supervisor").strip()
    mission.metadata = dict(mission.metadata or {})
    mission.metadata["campaign_id"] = campaign_id
    mission.metadata["supervisor_session_id"] = session_id
    node.metadata = dict(node.metadata or {})
    node.metadata["campaign_id"] = campaign_id
    node.metadata["workflow_session_id"] = session_id
    node.metadata["workflow_template_id"] = template_id
    node.metadata["workflow_driver_kind"] = driver_kind
    runtime_plan = dict(node.runtime_plan or {})
    workflow_inputs = dict(runtime_plan.get("workflow_inputs") or {})
    workflow_inputs["campaign_id"] = campaign_id
    workflow_inputs["supervisor_session_id"] = session_id
    runtime_plan["workflow_inputs"] = workflow_inputs
    node.runtime_plan = runtime_plan
    mission.updated_at = str(mission.updated_at or "")
    orchestrator_service._mission_store.save(mission)


def _session_status_from_campaign_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "completed":
        return "completed"
    if normalized == "stopped":
        return "stopped"
    if normalized == "failed":
        return "failed"
    return "active"


def _sync_supervisor_session(
    *,
    workflow_factory: WorkflowFactory,
    payload: Mapping[str, Any],
) -> None:
    session_id = str(payload.get("supervisor_session_id") or "").strip()
    if not session_id:
        return
    next_phase = str(payload.get("next_phase") or payload.get("current_phase") or "").strip()
    status = _session_status_from_campaign_status(str(payload.get("status") or "").strip())
    active_step = next_phase if status == "active" else ""
    try:
        artifacts = _payload_list(payload.get("artifacts"))
        campaign_events = _payload_list(payload.get("campaign_events"))
        contract_history = _payload_list(payload.get("contract_history"))
        verdict_history = _payload_list(payload.get("verdict_history"))
        phase_history = _phase_history_from_metadata(payload)
        latest_verdict = verdict_history[-1] if verdict_history else {}
        workflow_factory.update_active_step(session_id, active_step, status=status)
        workflow_factory.patch_shared_state(
            session_id,
            {
                "campaign_id": str(payload.get("campaign_id") or "").strip(),
                "mission_id": str(payload.get("mission_id") or "").strip(),
                "status": str(payload.get("status") or "").strip(),
                "current_phase": str(payload.get("current_phase") or "").strip(),
                "next_phase": str(payload.get("next_phase") or "").strip(),
                "current_iteration": int(payload.get("current_iteration") or 0),
                "top_level_goal": str(payload.get("top_level_goal") or "").strip(),
                "hard_constraints": list(payload.get("hard_constraints") or []),
                "working_contract": dict(payload.get("working_contract") or {}),
                "contract_history_versions": _shared_state_contract_versions(contract_history),
                "verdict_count": len(payload.get("verdict_history") or []),
                "latest_verdict": latest_verdict,
                "phase_history": phase_history,
                "artifact_count": len(artifacts),
                "bundle_root": str((_mapping_payload(payload.get("metadata")) or {}).get("bundle_root") or "").strip(),
                "runtime_mode": str(
                    (_mapping_payload((_mapping_payload(payload.get("metadata")) or {}).get("campaign_runtime")) or {}).get("mode")
                    or ""
                ).strip(),
                "pending_correctness_checks": list((_mapping_payload(payload.get("metadata")) or {}).get("pending_correctness_checks") or []),
                "resolved_correctness_checks": list((_mapping_payload(payload.get("metadata")) or {}).get("resolved_correctness_checks") or []),
                "waived_correctness_checks": list((_mapping_payload(payload.get("metadata")) or {}).get("waived_correctness_checks") or []),
                "operational_checks_pending": list((_mapping_payload(payload.get("metadata")) or {}).get("operational_checks_pending") or []),
                "closure_checks_pending": list((_mapping_payload(payload.get("metadata")) or {}).get("closure_checks_pending") or []),
                "execution_state": str((_mapping_payload(payload.get("metadata")) or {}).get("execution_state") or "").strip(),
                "closure_state": str((_mapping_payload(payload.get("metadata")) or {}).get("closure_state") or "").strip(),
                "progress_reason": str((_mapping_payload(payload.get("metadata")) or {}).get("progress_reason") or "").strip(),
                "closure_reason": str((_mapping_payload(payload.get("metadata")) or {}).get("closure_reason") or "").strip(),
                "latest_acceptance_decision": str((_mapping_payload(payload.get("metadata")) or {}).get("latest_acceptance_decision") or "").strip(),
                "not_done_reason": str((_mapping_payload(payload.get("metadata")) or {}).get("not_done_reason") or "").strip(),
            },
        )
        working_contract = dict(payload.get("working_contract") or {})
        contract_id = str(working_contract.get("contract_id") or "").strip()
        contract_version = int(working_contract.get("version") or 0)
        if working_contract:
            workflow_factory.upsert_blackboard_entry(
                session_id,
                entry_key="campaign.working_contract",
                payload=working_contract,
                entry_kind="campaign_working_contract",
                step_id=str(payload.get("current_phase") or "").strip() or str(payload.get("next_phase") or "").strip(),
                author_role_id="campaign_supervisor",
                dedupe_key=f"campaign_contract:{contract_id}:{contract_version}",
            )
        if latest_verdict:
            workflow_factory.upsert_blackboard_entry(
                session_id,
                entry_key="campaign.latest_verdict",
                payload=latest_verdict,
                entry_kind="campaign_verdict",
                step_id="evaluate",
                author_role_id=str(latest_verdict.get("reviewer_role_id") or "campaign_reviewer").strip(),
                dedupe_key=f"campaign_verdict:{str(latest_verdict.get('verdict_id') or '').strip()}",
            )
        for event in campaign_events:
            event_id = str(event.get("event_id") or "").strip()
            event_type = str(event.get("event_type") or "").strip()
            workflow_factory.upsert_blackboard_entry(
                session_id,
                entry_key=f"campaign.event.{event_type or 'event'}.{event_id or 'latest'}",
                payload=event,
                entry_kind="campaign_event",
                step_id=str(event.get("phase") or "").strip(),
                author_role_id="campaign_supervisor",
                dedupe_key=f"campaign_event:{event_id}",
            )
        for artifact in artifacts:
            artifact_id = str(artifact.get("artifact_id") or "").strip()
            ref = str(artifact.get("ref") or artifact_id).strip()
            workflow_factory.add_artifact(
                session_id,
                step_id=str(artifact.get("phase") or "").strip(),
                ref=ref,
                payload=artifact,
                producer_role_id="campaign_supervisor",
                owner_role_id="campaign_supervisor",
                dedupe_key=f"campaign_artifact:{artifact_id}",
            )
    except Exception:
        return


def _arm_campaign_mission(
    *,
    orchestrator_service,
    mission_id: str,
) -> None:
    target_mission_id = str(mission_id or "").strip()
    if not target_mission_id:
        return
    control_mission = getattr(orchestrator_service, "control_mission", None)
    if callable(control_mission):
        control_mission(target_mission_id, "resume")
    tick = getattr(orchestrator_service, "tick", None)
    if callable(tick):
        tick(target_mission_id)


def _build_campaign_domain_service(workspace: str) -> Any:
    orchestrator_root = _campaign_store_root_for_workspace(workspace)
    campaign_root = _campaign_root_for_workspace(workspace)
    workflow_sessions_root = orchestrator_root / "workflow_sessions"
    service_cls, store_cls, _ = _load_campaign_domain_api()
    store = store_cls(orchestrator_root)
    orchestrator_service = build_orchestrator_service_for_workspace(workspace)
    workflow_factory = WorkflowFactory(workflow_sessions_root)
    kwargs: dict[str, Any] = {}
    signature = inspect.signature(service_cls)
    parameters = signature.parameters
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    if "store" in parameters or accepts_kwargs:
        kwargs["store"] = store
    if "root" in parameters or accepts_kwargs:
        kwargs["root"] = orchestrator_root
    if "campaign_root" in parameters or accepts_kwargs:
        kwargs["campaign_root"] = campaign_root
    if "workspace" in parameters or accepts_kwargs:
        kwargs["workspace"] = workspace
    if "orchestrator_service" in parameters or accepts_kwargs:
        kwargs["orchestrator_service"] = orchestrator_service
    if "workflow_factory" in parameters or accepts_kwargs:
        kwargs["workflow_factory"] = workflow_factory
    return service_cls(**kwargs)


def _should_bootstrap_campaign_mission(service: Any) -> bool:
    module_name = type(service).__module__
    return any(module_name.startswith(prefix) for prefix in _REAL_CAMPAIGN_DOMAIN_PREFIXES)


def _campaign_control_plane_patch(*, mission_id: str, supervisor_session_id: str) -> dict[str, Any]:
    return {
        "control_plane_refs": {
            "mission_id": mission_id,
            "supervisor_session_id": supervisor_session_id,
            "canonical_session_id": supervisor_session_id,
        },
        "legacy_refs": {
            "mission_id": mission_id,
            "supervisor_session_id": supervisor_session_id,
        },
    }


def _should_expose_public_mission_id(payload: Mapping[str, Any]) -> bool:
    status = str(payload.get("status") or "").strip().lower()
    return status not in {"", "draft"}


class OrchestratorCampaignService:
    """Thin fourth-layer campaign facade rooted in the orchestrator run area."""

    def __init__(self, *, service_factory=None) -> None:
        self._service_factory = service_factory or _build_campaign_domain_service

    def create_campaign(self, workspace: str, spec: Any) -> dict[str, Any]:
        service = self._service_factory(workspace)
        if self._service_factory is _build_campaign_domain_service:
            _, _, spec_cls = _load_campaign_domain_api()
            normalized_spec = _normalize_spec_payload(spec, workspace)
            if hasattr(service, "store") and hasattr(service.store, "ensure_single_active_campaign"):
                service.store.ensure_single_active_campaign()
            campaign_id = _new_campaign_id()
            mission_id = ""
            supervisor_session_id = ""
            orchestrator_service = None
            if _should_bootstrap_campaign_mission(service):
                orchestrator_service = build_orchestrator_service_for_workspace(workspace)
                workflow_factory = WorkflowFactory(_campaign_store_root_for_workspace(workspace) / "workflow_sessions")
                mission = _create_campaign_mission(
                    orchestrator_service=orchestrator_service,
                    campaign_id=campaign_id,
                    spec_payload=normalized_spec,
                )
                mission_id = str(getattr(mission, "mission_id", "") or "").strip()
                supervisor_session = _create_supervisor_session(
                    workflow_factory=workflow_factory,
                    campaign_id=campaign_id,
                    mission_id=mission_id,
                    spec_payload=normalized_spec,
                )
                supervisor_session_id = str(getattr(supervisor_session, "session_id", "") or "").strip()
                _bind_supervisor_session_to_mission(
                    orchestrator_service=orchestrator_service,
                    mission_id=mission_id,
                    campaign_id=campaign_id,
                    supervisor_session=supervisor_session,
                )
            normalized_spec = _prepare_bundle_metadata(
                workspace=workspace,
                campaign_id=campaign_id,
                spec_payload=normalized_spec,
            )
            spec = _coerce_campaign_spec(normalized_spec, spec_cls)
            payload = _payload_dict(
                service.create_campaign(
                    spec if spec_cls is not None else normalized_spec,
                    campaign_id=campaign_id,
                    mission_id=mission_id,
                    supervisor_session_id=supervisor_session_id,
                )
            )
            if mission_id or supervisor_session_id:
                payload = _payload_dict(
                    service.update_campaign_metadata(
                        campaign_id,
                        _campaign_control_plane_patch(
                            mission_id=mission_id,
                            supervisor_session_id=supervisor_session_id,
                        ),
                    )
                )
                payload.setdefault("mission_id", mission_id)
                payload.setdefault("supervisor_session_id", supervisor_session_id)
                if orchestrator_service is not None and mission_id:
                    _arm_campaign_mission(
                        orchestrator_service=orchestrator_service,
                        mission_id=mission_id,
                    )
            if "metadata" not in payload and isinstance(normalized_spec, Mapping):
                payload["metadata"] = dict(normalized_spec.get("metadata") or {})
            payload.setdefault(
                "campaign_title",
                str(normalized_spec.get("campaign_title") or normalized_spec.get("top_level_goal") or "").strip(),
            )
            payload.setdefault("top_level_goal", str(normalized_spec.get("top_level_goal") or "").strip())
            payload = self._enrich_campaign_payload(workspace, payload)
            ensure_campaign_bundle_files(workspace=workspace, payload=payload)
            feedback_doc = _bootstrap_feedback_surface(
                workspace=workspace,
                spec_payload=normalized_spec,
                payload=payload,
            )
            if feedback_doc:
                payload = _merge_feedback_doc_payload(payload, feedback_doc)
            return payload
        return self._enrich_campaign_payload(workspace, _payload_dict(service.create_campaign(spec)))

    def get_campaign_status(self, workspace: str, campaign_id: str) -> dict[str, Any]:
        service = self._service_factory(workspace)
        payload = _payload_dict(service.get_campaign_status(str(campaign_id or "").strip()))
        if self._service_factory is _build_campaign_domain_service:
            return self._enrich_campaign_payload(workspace, payload)
        return payload

    def summarize_campaign_task(self, workspace: str, campaign_id: str) -> dict[str, Any]:
        service = self._service_factory(workspace)
        target_campaign_id = str(campaign_id or "").strip()
        if hasattr(service, "summarize_campaign_task") and callable(service.summarize_campaign_task):
            return dict(service.summarize_campaign_task(target_campaign_id) or {})
        payload = self.get_campaign_status(workspace, target_campaign_id)
        return dict(payload.get("task_summary") or {})

    def append_campaign_feedback(self, workspace: str, campaign_id: str, feedback: str) -> dict[str, Any]:
        service = self._service_factory(workspace)
        target_campaign_id = str(campaign_id or "").strip()
        if hasattr(service, "append_campaign_feedback") and callable(service.append_campaign_feedback):
            payload = _payload_dict(service.append_campaign_feedback(target_campaign_id, feedback))
        else:
            payload = _payload_dict(service.get_campaign_status(target_campaign_id))
        if self._service_factory is _build_campaign_domain_service:
            return self._enrich_campaign_payload(workspace, payload)
        return payload

    def update_campaign_metadata(
        self,
        workspace: str,
        campaign_id: str,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = self._service_factory(workspace)
        target_campaign_id = str(campaign_id or "").strip()
        if hasattr(service, "update_campaign_metadata") and callable(service.update_campaign_metadata):
            payload = _payload_dict(service.update_campaign_metadata(target_campaign_id, metadata_patch))
        else:
            payload = _payload_dict(service.get_campaign_status(target_campaign_id))
            payload["metadata"] = _merge_metadata_patch(payload.get("metadata"), metadata_patch)
        if self._service_factory is _build_campaign_domain_service:
            return self._enrich_campaign_payload(workspace, payload)
        return payload

    def apply_operator_patch(
        self,
        workspace: str,
        campaign_id: str,
        *,
        status: str = "",
        current_phase: str = "",
        next_phase: str = "",
        metadata_patch: Mapping[str, Any] | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        service = self._service_factory(workspace)
        target_campaign_id = str(campaign_id or "").strip()
        if hasattr(service, "apply_operator_patch") and callable(service.apply_operator_patch):
            payload = _payload_dict(
                service.apply_operator_patch(
                    target_campaign_id,
                    status=status,
                    current_phase=current_phase,
                    next_phase=next_phase,
                    metadata_patch=metadata_patch,
                    reason=reason,
                )
            )
        else:
            payload = _payload_dict(service.get_campaign_status(target_campaign_id))
            payload["metadata"] = _merge_metadata_patch(payload.get("metadata"), metadata_patch)
            if status:
                payload["status"] = status
            if current_phase:
                payload["current_phase"] = current_phase
            if next_phase:
                payload["next_phase"] = next_phase
        if self._service_factory is _build_campaign_domain_service:
            return self._enrich_campaign_payload(workspace, payload)
        return payload

    def record_operator_action(
        self,
        workspace: str,
        campaign_id: str,
        *,
        action: Mapping[str, Any],
        patch_receipt: Mapping[str, Any] | None = None,
        recovery_decision: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = self._service_factory(workspace)
        target_campaign_id = str(campaign_id or "").strip()
        if hasattr(service, "record_operator_action") and callable(service.record_operator_action):
            payload = _payload_dict(
                service.record_operator_action(
                    target_campaign_id,
                    action=action,
                    patch_receipt=patch_receipt,
                    recovery_decision=recovery_decision,
                )
            )
        else:
            payload = _payload_dict(service.get_campaign_status(target_campaign_id))
            metadata = _mapping_payload(payload.get("metadata")) or {}
            operator_plane = _mapping_payload(metadata.get("operator_plane")) or {}
            actions = [
                dict(item)
                for item in operator_plane.get("actions") or []
                if isinstance(item, Mapping)
            ]
            receipts = [
                dict(item)
                for item in operator_plane.get("patch_receipts") or []
                if isinstance(item, Mapping)
            ]
            recoveries = [
                dict(item)
                for item in operator_plane.get("recovery_decisions") or []
                if isinstance(item, Mapping)
            ]
            actions.append(dict(action))
            if isinstance(patch_receipt, Mapping):
                receipts.append(dict(patch_receipt))
            if isinstance(recovery_decision, Mapping):
                recoveries.append(dict(recovery_decision))
            operator_plane["actions"] = actions
            operator_plane["patch_receipts"] = receipts
            operator_plane["recovery_decisions"] = recoveries
            operator_plane["latest_action_id"] = str(action.get("action_id") or "").strip()
            metadata["operator_plane"] = operator_plane
            payload["metadata"] = metadata
        if self._service_factory is _build_campaign_domain_service:
            return self._enrich_campaign_payload(workspace, payload)
        return payload

    def list_operator_actions(
        self,
        workspace: str,
        campaign_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        service = self._service_factory(workspace)
        target_campaign_id = str(campaign_id or "").strip()
        target_limit = max(0, int(limit or 0))
        if hasattr(service, "list_operator_actions") and callable(service.list_operator_actions):
            return _limited_payload_list(service.list_operator_actions(target_campaign_id, limit=target_limit), limit=target_limit)
        payload = _payload_dict(service.get_campaign_status(target_campaign_id))
        metadata = _mapping_payload(payload.get("metadata")) or {}
        operator_plane = _mapping_payload(metadata.get("operator_plane")) or {}
        items = [
            dict(item)
            for item in operator_plane.get("actions") or []
            if isinstance(item, Mapping)
        ]
        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        if target_limit > 0:
            return items[:target_limit]
        return items

    def get_operator_action_detail(
        self,
        workspace: str,
        campaign_id: str,
        action_id: str,
    ) -> dict[str, Any]:
        service = self._service_factory(workspace)
        target_campaign_id = str(campaign_id or "").strip()
        target_action_id = str(action_id or "").strip()
        if hasattr(service, "get_operator_action_detail") and callable(service.get_operator_action_detail):
            return _payload_dict(service.get_operator_action_detail(target_campaign_id, target_action_id))
        payload = _payload_dict(service.get_campaign_status(target_campaign_id))
        metadata = _mapping_payload(payload.get("metadata")) or {}
        operator_plane = _mapping_payload(metadata.get("operator_plane")) or {}
        action = next(
            (
                dict(item)
                for item in operator_plane.get("actions") or []
                if isinstance(item, Mapping) and str(item.get("action_id") or "").strip() == target_action_id
            ),
            None,
        )
        if action is None:
            raise KeyError(f"operator action not found: {target_action_id}")
        receipt = next(
            (
                dict(item)
                for item in operator_plane.get("patch_receipts") or []
                if isinstance(item, Mapping) and str(item.get("action_id") or "").strip() == target_action_id
            ),
            {},
        )
        recovery = next(
            (
                dict(item)
                for item in operator_plane.get("recovery_decisions") or []
                if isinstance(item, Mapping) and str(item.get("action_id") or "").strip() == target_action_id
            ),
            {},
        )
        return {
            "action": action,
            "patch_receipt": receipt,
            "recovery_decision": recovery,
        }

    def list_campaigns(self, workspace: str, *, status: str = "", limit: int = 20) -> list[dict[str, Any]]:
        service = self._service_factory(workspace)
        target_status = str(status or "").strip().lower()
        target_limit = max(0, int(limit or 0))
        if hasattr(service, "list_campaigns") and callable(service.list_campaigns):
            items = _limited_payload_list(
                service.list_campaigns(status=target_status, limit=target_limit),
                limit=target_limit,
            )
            if self._service_factory is _build_campaign_domain_service:
                return [self._enrich_campaign_payload(workspace, item) for item in items]
            return items
        if hasattr(service, "store") and hasattr(service.store, "list_instances"):
            items = _payload_list(service.store.list_instances())
            if target_status:
                items = [item for item in items if str(item.get("status") or "").strip().lower() == target_status]
            items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            if target_limit > 0:
                items = items[:target_limit]
            if self._service_factory is _build_campaign_domain_service:
                return [self._enrich_campaign_payload(workspace, item) for item in items]
            return items
        raise AttributeError("campaign service does not support list_campaigns")

    def list_campaign_artifacts(self, workspace: str, campaign_id: str) -> list[dict[str, Any]]:
        service = self._service_factory(workspace)
        return _payload_list(service.list_campaign_artifacts(str(campaign_id or "").strip()))

    def list_campaign_events(
        self,
        workspace: str,
        campaign_id: str,
        *,
        event_type: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        service = self._service_factory(workspace)
        target_campaign_id = str(campaign_id or "").strip()
        target_event_type = str(event_type or "").strip()
        target_limit = max(0, int(limit or 0))
        if hasattr(service, "list_campaign_events") and callable(service.list_campaign_events):
            return _limited_payload_list(
                service.list_campaign_events(
                    target_campaign_id,
                    event_type=target_event_type,
                    limit=target_limit,
                ),
                limit=target_limit,
            )
        if hasattr(service, "store") and hasattr(service.store, "list_events"):
            items = _payload_list(service.store.list_events(target_campaign_id, event_type=target_event_type))
            items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
            if target_limit > 0:
                items = items[:target_limit]
            return items
        raise AttributeError("campaign service does not support list_campaign_events")

    def resume_campaign(self, workspace: str, campaign_id: str) -> dict[str, Any]:
        service = self._service_factory(workspace)
        payload = _payload_dict(service.resume_campaign(str(campaign_id or "").strip()))
        if self._service_factory is _build_campaign_domain_service:
            payload = self._enrich_campaign_payload(workspace, payload)
        return payload

    def run_campaign_turn(self, workspace: str, campaign_id: str, *, reason: str = "") -> dict[str, Any]:
        service = self._service_factory(workspace)
        target_campaign_id = str(campaign_id or "").strip()
        if hasattr(service, "run_campaign_turn") and callable(service.run_campaign_turn):
            payload = _payload_dict(service.run_campaign_turn(target_campaign_id, reason=reason))
        else:
            payload = _payload_dict(service.resume_campaign(target_campaign_id))
        if self._service_factory is _build_campaign_domain_service:
            payload = self._enrich_campaign_payload(workspace, payload)
        return payload

    def stop_campaign(self, workspace: str, campaign_id: str) -> dict[str, Any]:
        service = self._service_factory(workspace)
        payload = _payload_dict(service.stop_campaign(str(campaign_id or "").strip()))
        if self._service_factory is _build_campaign_domain_service:
            payload = self._enrich_campaign_payload(workspace, payload)
        return payload

    def _enrich_campaign_payload(self, workspace: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        enriched = dict(payload)
        campaign_id = str(enriched.get("campaign_id") or "").strip()
        if not campaign_id:
            return enriched
        try:
            enriched["artifacts"] = self.list_campaign_artifacts(workspace, campaign_id)
        except Exception:
            enriched["artifacts"] = []
        try:
            enriched["campaign_events"] = self.list_campaign_events(workspace, campaign_id, limit=50)
        except Exception:
            enriched["campaign_events"] = []
        bundle_patch = ensure_campaign_bundle_files(workspace=workspace, payload=enriched)
        if bundle_patch:
            metadata = _mapping_payload(enriched.get("metadata")) or {}
            metadata.update(bundle_patch)
            enriched["metadata"] = metadata
        metadata = _mapping_payload(enriched.get("metadata")) or {}
        control_plane_refs = _mapping_payload(metadata.get("control_plane_refs")) or {}
        legacy_refs = _mapping_payload(metadata.get("legacy_refs")) or {}
        internal_mission_id = str(
            enriched.get("mission_id")
            or control_plane_refs.get("mission_id")
            or legacy_refs.get("mission_id")
            or ""
        ).strip()
        enriched["mission_id"] = internal_mission_id if _should_expose_public_mission_id(enriched) else ""
        enriched["supervisor_session_id"] = str(
            enriched.get("supervisor_session_id")
            or control_plane_refs.get("supervisor_session_id")
            or control_plane_refs.get("canonical_session_id")
            or legacy_refs.get("supervisor_session_id")
            or ""
        ).strip()
        enriched["bundle_root"] = str(metadata.get("bundle_root") or "").strip()
        enriched["bundle_manifest"] = str(metadata.get("bundle_manifest") or "").strip()
        enriched["runtime_mode"] = str((_mapping_payload(metadata.get("campaign_runtime")) or {}).get("mode") or "").strip()
        enriched["canonical_session_id"] = str(
            metadata.get("canonical_session_id")
            or control_plane_refs.get("canonical_session_id")
            or enriched.get("supervisor_session_id")
            or ""
        ).strip()
        enriched["task_summary"] = _mapping_payload(metadata.get("task_summary")) or {}
        return enriched


__all__ = [
    "OrchestratorCampaignService",
    "_build_campaign_domain_service",
    "_campaign_root_for_workspace",
]
