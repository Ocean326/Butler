from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from butler_main.runtime_os.process_runtime import WorkflowFactory

from .models import (
    CampaignArtifactSummary,
    CampaignEvent,
    CampaignInstance,
    CampaignPhase,
    CampaignSpec,
    CampaignTurnReceipt,
    EvaluationVerdict,
    IterationBudget,
    OperatorActionRecord,
    OperatorPatchReceipt,
    RecoveryDecisionReceipt,
    WorkingContract,
    _template_contract_payload,
)
from .codex_runtime import (
    CliRunnerCampaignCodexProvider,
    CodexCampaignSupervisorRuntime,
    _merge_runtime_request,
    _runtime_request_from_metadata,
    _workspace_from_instance,
    _write_phase_bundle_outputs,
)
from .phase_runtime import CampaignArtifactRecord, CampaignEventRecord, CampaignPhaseOutcome, merge_phase_metadata
from .status_semantics import build_campaign_semantics
from .store import FileCampaignStore
from .supervisor import CampaignSupervisorRuntime


def _contract_payload(metadata: Mapping[str, Any] | None, key: str) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}
    value = metadata.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _merge_dict_patch(base: Mapping[str, Any] | None, patch: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(patch or {}).items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge_dict_patch(merged.get(key), value)
        else:
            merged[key] = value
    return merged


def _normalized_text_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _merge_text_lists(*values: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for items in values:
        for item in _normalized_text_list(items):
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def _operator_plane_payload(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(metadata or {})
    operator_plane = payload.get("operator_plane")
    if not isinstance(operator_plane, Mapping):
        operator_plane = {}
    return {
        "actions": [
            OperatorActionRecord.from_dict(item).to_dict()
            for item in operator_plane.get("actions") or []
            if isinstance(item, Mapping)
        ],
        "patch_receipts": [
            OperatorPatchReceipt.from_dict(item).to_dict()
            for item in operator_plane.get("patch_receipts") or []
            if isinstance(item, Mapping)
        ],
        "recovery_decisions": [
            RecoveryDecisionReceipt.from_dict(item).to_dict()
            for item in operator_plane.get("recovery_decisions") or []
            if isinstance(item, Mapping)
        ],
        "latest_action_id": str(operator_plane.get("latest_action_id") or "").strip(),
    }


def _phase_path_from_metadata(metadata: Mapping[str, Any] | None) -> list[str]:
    phase_runtime = _contract_payload(metadata, "phase_runtime")
    path = _normalized_text_list(phase_runtime.get("phase_path"))
    if path:
        return path
    return [
        CampaignPhase.DISCOVER.value,
        CampaignPhase.IMPLEMENT.value,
        CampaignPhase.EVALUATE.value,
        CampaignPhase.ITERATE.value,
    ]


def _next_phase_after(phase_path: list[str], current_phase: str) -> str:
    normalized_current = str(current_phase or "").strip().lower()
    if normalized_current in phase_path:
        index = phase_path.index(normalized_current)
        if index + 1 < len(phase_path):
            return phase_path[index + 1]
    return normalized_current


def _campaign_turn_template() -> dict[str, Any]:
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


class CampaignDomainService:
    """Campaign domain service with an explicit supervisor/phase runtime chain."""

    def __init__(
        self,
        root: str | Path | FileCampaignStore,
        *,
        now_factory=None,
        workspace: str = "",
        config_snapshot: Mapping[str, Any] | None = None,
        supervisor_runtime: CampaignSupervisorRuntime | None = None,
        workflow_factory=None,
        orchestrator_service=None,
        codex_provider=None,
        campaign_runtime_mode: str = "",
        codex_timeout: int = 600,
        codex_runtime_request: Mapping[str, Any] | None = None,
    ) -> None:
        self._store = root if isinstance(root, FileCampaignStore) else FileCampaignStore(root)
        self._now_factory = now_factory
        self._workspace = str(workspace or "").strip()
        self._config_snapshot = dict(config_snapshot or {})
        self._workflow_factory = workflow_factory
        self._orchestrator_service = orchestrator_service
        self._supervisor_runtime_override = supervisor_runtime
        self._default_supervisor_runtime = supervisor_runtime or CampaignSupervisorRuntime()
        self._codex_provider = codex_provider
        self._campaign_runtime_mode = str(campaign_runtime_mode or "").strip().lower()
        self._codex_timeout = max(10, int(codex_timeout or 0))
        self._codex_runtime_request = dict(codex_runtime_request or {})
        if self._workflow_factory is None:
            self._workflow_factory = WorkflowFactory(self._store.root / "workflow_sessions")

    @property
    def store(self) -> FileCampaignStore:
        return self._store

    def create_campaign(
        self,
        spec: CampaignSpec | Mapping[str, Any] | None = None,
        *,
        mission_id: str = "",
        supervisor_session_id: str = "",
        campaign_id: str = "",
    ) -> CampaignInstance:
        campaign_spec = self._coerce_spec(spec)
        if not self._use_legacy_supervisor_for_spec(campaign_spec):
            return self._create_campaign_agent_turn(
                campaign_spec,
                mission_id=mission_id,
                supervisor_session_id=supervisor_session_id,
                campaign_id=campaign_id,
            )
        campaign_spec = self._coerce_spec(spec)
        self._store.ensure_single_active_campaign(exclude_campaign_id=campaign_id)
        initial_contract = self._build_initial_working_contract(campaign_spec)
        supervisor_runtime = self._supervisor_runtime_for_spec(campaign_spec)
        discover_outcome = supervisor_runtime.bootstrap_campaign(
            spec=campaign_spec,
            contract=initial_contract,
            mission_id=str(mission_id or "").strip(),
            supervisor_session_id=str(supervisor_session_id or "").strip(),
        )
        template_contract = self._template_contract_from_spec(campaign_spec)
        legacy_runtime_payload = self._campaign_runtime_config(campaign_spec.metadata)
        legacy_runtime_payload["engine"] = "legacy_supervisor"
        metadata: dict[str, Any] = {
            "domain_layer": "campaign",
            "mvp_version": "v1",
            "single_repo_mode": True,
            "control_plane_refs": {
                "mission_id": str(mission_id or "").strip(),
                "supervisor_session_id": str(supervisor_session_id or "").strip(),
            },
            "phase_runtime": discover_outcome.metadata,
            "phase_history": [
                {
                    "phase": discover_outcome.phase.value,
                    "next_phase": discover_outcome.next_phase.value,
                    "status": discover_outcome.status,
                }
            ],
            "campaign_runtime": legacy_runtime_payload,
            "bundle_root": str(campaign_spec.metadata.get("bundle_root") or "").strip(),
            "bundle_manifest": str(campaign_spec.metadata.get("bundle_manifest") or "").strip(),
            "topic_slug": str(campaign_spec.metadata.get("topic_slug") or "").strip(),
            "bundle_created_at_local": str(campaign_spec.metadata.get("bundle_created_at_local") or "").strip(),
            "primary_carrier": str(campaign_spec.metadata.get("primary_carrier") or "campaign").strip() or "campaign",
            "startup_mode": str(campaign_spec.metadata.get("startup_mode") or "").strip(),
            "strict_acceptance_required": bool(campaign_spec.metadata.get("strict_acceptance_required")),
            "minimal_correctness_ready": bool(campaign_spec.metadata.get("minimal_correctness_ready")),
            "pending_correctness_checks": _normalized_text_list(
                campaign_spec.metadata.get("pending_correctness_checks")
            ),
            "resolved_correctness_checks": _normalized_text_list(
                campaign_spec.metadata.get("resolved_correctness_checks")
            ),
            "waived_correctness_checks": _normalized_text_list(
                campaign_spec.metadata.get("waived_correctness_checks")
            ),
            "latest_implement_artifact": {},
            "latest_acceptance_blockers": [],
            "latest_acceptance_decision": "",
            "execution_state": "",
            "closure_state": "",
            "progress_reason": "",
            "closure_reason": "",
            "operational_checks_pending": [],
            "closure_checks_pending": [],
            "not_done_reason": "",
            "spec": campaign_spec.to_dict(),
        }
        metadata["planning_contract"] = self._build_planning_contract(campaign_spec.metadata)
        metadata["evaluation_contract"] = self._build_evaluation_contract(campaign_spec.metadata)
        metadata["governance_contract"] = self._build_governance_contract(campaign_spec.metadata)
        if template_contract:
            metadata["template_contract"] = template_contract

        instance = CampaignInstance(
            campaign_id=str(campaign_id or "").strip(),
            campaign_title=campaign_spec.campaign_title or self._default_title(campaign_spec.top_level_goal),
            top_level_goal=campaign_spec.top_level_goal,
            materials=list(campaign_spec.materials),
            hard_constraints=list(campaign_spec.hard_constraints),
            workspace_root=campaign_spec.workspace_root,
            repo_root=campaign_spec.repo_root or campaign_spec.workspace_root,
            mission_id=str(mission_id or "").strip(),
            supervisor_session_id=str(supervisor_session_id or "").strip(),
            status="active",
            current_phase=CampaignPhase.DISCOVER.value,
            next_phase=CampaignPhase.IMPLEMENT.value,
            current_iteration=0,
            working_contract=initial_contract,
            contract_history=[initial_contract],
            metadata=metadata,
        )
        self._refresh_status_semantics(instance)
        self._sync_spec_metadata(instance)
        self._store.save_instance(instance)
        discover_artifacts = self._apply_phase_outcome(instance, discover_outcome)
        if discover_artifacts:
            for event in discover_outcome.events:
                if event.event_type == "campaign_created":
                    event.payload.setdefault("discover_artifact_id", discover_artifacts[0].artifact_id)
                    event.payload.setdefault("working_contract_id", initial_contract.contract_id)
        self._apply_events(instance, discover_outcome.events)
        self._refresh_status_semantics(instance)
        self._sync_spec_metadata(instance)
        instance.touch()
        self._store.save_instance(instance)
        return self._reload_required(instance.campaign_id)

    def _use_legacy_supervisor_for_spec(self, spec: CampaignSpec) -> bool:
        runtime_payload = _contract_payload(spec.metadata, "campaign_runtime")
        engine = str(runtime_payload.get("engine") or "").strip().lower()
        if engine == "legacy_supervisor":
            return True
        if engine == "agent_turn":
            return False
        return self._supervisor_runtime_override is not None

    def _use_legacy_supervisor_for_instance(self, instance: CampaignInstance) -> bool:
        runtime_payload = _contract_payload(instance.metadata, "campaign_runtime")
        engine = str(runtime_payload.get("engine") or "").strip().lower()
        if engine == "legacy_supervisor":
            return True
        if engine == "agent_turn":
            return False
        return self._supervisor_runtime_override is not None

    def _create_campaign_agent_turn(
        self,
        spec: CampaignSpec,
        *,
        mission_id: str = "",
        supervisor_session_id: str = "",
        campaign_id: str = "",
    ) -> CampaignInstance:
        self._store.ensure_single_active_campaign(exclude_campaign_id=campaign_id)
        initial_contract = self._build_initial_working_contract(spec)
        session_id = self._ensure_campaign_session(
            spec=spec,
            campaign_id=str(campaign_id or "").strip(),
            mission_id=str(mission_id or "").strip(),
            supervisor_session_id=str(supervisor_session_id or "").strip(),
        )
        template_contract = self._template_contract_from_spec(spec)
        runtime_payload = self._campaign_runtime_config(spec.metadata)
        metadata: dict[str, Any] = {
            "domain_layer": "campaign",
            "campaign_engine": "agent_turn",
            "mvp_version": "v2",
            "single_repo_mode": True,
            "control_plane_refs": {
                "canonical_session_id": session_id,
            },
            "legacy_refs": {
                "mission_id": str(mission_id or "").strip(),
                "supervisor_session_id": str(supervisor_session_id or "").strip(),
            },
            "campaign_runtime": runtime_payload,
            "bundle_root": str(spec.metadata.get("bundle_root") or "").strip(),
            "bundle_manifest": str(spec.metadata.get("bundle_manifest") or "").strip(),
            "topic_slug": str(spec.metadata.get("topic_slug") or "").strip(),
            "bundle_created_at_local": str(spec.metadata.get("bundle_created_at_local") or "").strip(),
            "primary_carrier": str(spec.metadata.get("primary_carrier") or "campaign").strip() or "campaign",
            "startup_mode": str(spec.metadata.get("startup_mode") or "").strip(),
            "strict_acceptance_required": bool(spec.metadata.get("strict_acceptance_required")),
            "minimal_correctness_ready": bool(spec.metadata.get("minimal_correctness_ready")),
            "pending_correctness_checks": _normalized_text_list(spec.metadata.get("pending_correctness_checks")),
            "resolved_correctness_checks": _normalized_text_list(spec.metadata.get("resolved_correctness_checks")),
            "waived_correctness_checks": _normalized_text_list(spec.metadata.get("waived_correctness_checks")),
            "planning_contract": self._build_planning_contract(spec.metadata),
            "evaluation_contract": self._build_evaluation_contract(spec.metadata),
            "governance_contract": self._build_governance_contract(spec.metadata),
            "latest_delivery_refs": [],
            "latest_verdict": {},
            "latest_summary": "",
            "latest_next_action": "run the first supervisor turn",
            "latest_turn_receipt": {},
            "turn_cursor": {
                "turn_count": 0,
                "last_turn_id": "",
                "continue_token": f"campaign:{str(campaign_id or '').strip() or session_id}:turn:1",
            },
            "spec": spec.to_dict(),
        }
        if template_contract:
            metadata["template_contract"] = template_contract
        instance = CampaignInstance(
            campaign_id=str(campaign_id or "").strip(),
            campaign_title=spec.campaign_title or self._default_title(spec.top_level_goal),
            top_level_goal=spec.top_level_goal,
            materials=list(spec.materials),
            hard_constraints=list(spec.hard_constraints),
            workspace_root=spec.workspace_root,
            repo_root=spec.repo_root or spec.workspace_root,
            mission_id="",
            supervisor_session_id=session_id,
            status="draft",
            current_phase=CampaignPhase.DISCOVER.value,
            next_phase=CampaignPhase.DISCOVER.value,
            current_iteration=0,
            working_contract=initial_contract,
            contract_history=[initial_contract],
            metadata=metadata,
        )
        self._refresh_status_semantics(instance)
        self._sync_spec_metadata(instance)
        self._store.save_instance(instance)
        self._append_event(
            instance,
            event_type="campaign_created",
            iteration=0,
            phase=CampaignPhase.DISCOVER,
            payload={
                "canonical_session_id": session_id,
                "engine": "agent_turn",
            },
        )
        self._sync_campaign_session(instance, reason="campaign_created")
        instance.touch()
        self._store.save_instance(instance)
        return self._reload_required(instance.campaign_id)

    def _ensure_campaign_session(
        self,
        *,
        spec: CampaignSpec,
        campaign_id: str,
        mission_id: str,
        supervisor_session_id: str,
    ) -> str:
        session_id = str(supervisor_session_id or "").strip()
        if session_id and self._workflow_factory.session_exists(session_id):
            return session_id
        session = self._workflow_factory.create_session(
            template=_campaign_turn_template(),
            driver_kind="campaign_supervisor",
            active_step="turn",
            initial_shared_state={
                "campaign_id": str(campaign_id or "").strip(),
                "mission_id": str(mission_id or "").strip(),
                "top_level_goal": spec.top_level_goal,
                "materials": list(spec.materials),
                "hard_constraints": list(spec.hard_constraints),
                "workspace_root": spec.workspace_root,
                "repo_root": spec.repo_root or spec.workspace_root,
            },
            metadata={
                "campaign_id": str(campaign_id or "").strip(),
                "legacy_mission_id": str(mission_id or "").strip(),
                "campaign_engine": "agent_turn",
            },
            session_id=session_id,
        )
        return str(session.session_id or "").strip()

    def _sync_campaign_session(self, instance: CampaignInstance, *, reason: str) -> None:
        session_id = str(instance.supervisor_session_id or "").strip()
        if not session_id:
            return
        status = str(instance.status or "").strip()
        active_step = "" if status in {"completed", "failed", "cancelled", "paused"} else "turn"
        try:
            self._workflow_factory.update_active_step(session_id, active_step, status=status or "running")
            self._workflow_factory.patch_shared_state(
                session_id,
                {
                    "campaign_id": instance.campaign_id,
                    "campaign_status": status,
                    "turn_count": int(instance.current_iteration or 0),
                    "latest_summary": str(instance.metadata.get("latest_summary") or "").strip(),
                    "latest_next_action": str(instance.metadata.get("latest_next_action") or "").strip(),
                    "latest_delivery_refs": list(instance.metadata.get("latest_delivery_refs") or []),
                    "latest_verdict": dict(instance.metadata.get("latest_verdict") or {}),
                    "task_summary": dict(instance.metadata.get("task_summary") or {}),
                },
            )
            latest_receipt = dict(instance.metadata.get("latest_turn_receipt") or {})
            if latest_receipt:
                self._workflow_factory.upsert_blackboard_entry(
                    session_id,
                    entry_key="campaign.latest_turn_receipt",
                    payload=latest_receipt,
                    entry_kind="campaign_turn_receipt",
                    step_id="turn",
                    author_role_id="campaign_supervisor",
                    dedupe_key=str(latest_receipt.get("turn_id") or "").strip(),
                )
            for ref in list(instance.metadata.get("latest_delivery_refs") or []):
                self._workflow_factory.add_artifact(
                    session_id,
                    step_id="turn",
                    ref=str(ref or "").strip(),
                    payload={"campaign_id": instance.campaign_id, "ref": str(ref or "").strip()},
                    producer_role_id="campaign_supervisor",
                    owner_role_id="campaign_supervisor",
                    dedupe_key=f"campaign_delivery:{str(ref or '').strip()}",
                )
            self._workflow_factory._event_log.append(
                session_id=session_id,
                event_type="campaign_ledger_synced",
                layer="Domain.control_plane",
                payload={
                    "reason": reason,
                    "campaign_id": instance.campaign_id,
                    "status": status,
                    "turn_count": int(instance.current_iteration or 0),
                },
            )
        except Exception:
            return

    def update_campaign_metadata(
        self,
        campaign_id: str,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> CampaignInstance:
        instance = self._require_instance(campaign_id)
        if not isinstance(metadata_patch, Mapping) or not metadata_patch:
            return instance
        instance.metadata = _merge_dict_patch(instance.metadata, metadata_patch)
        spec_payload = dict(instance.metadata.get("spec") or {})
        spec_metadata = dict(spec_payload.get("metadata") or {})
        spec_payload["metadata"] = _merge_dict_patch(spec_metadata, metadata_patch)
        instance.metadata["spec"] = spec_payload
        self._refresh_status_semantics(instance)
        self._sync_spec_metadata(instance)
        instance.touch()
        self._store.save_instance(instance)
        self._append_event(
            instance,
            event_type="campaign_metadata_updated",
            iteration=instance.current_iteration,
            phase=CampaignPhase.normalize(instance.current_phase),
            payload={"metadata_keys": sorted(dict(metadata_patch).keys())},
        )
        return self._reload_required(campaign_id)

    def get_campaign_status(self, campaign_id: str) -> CampaignInstance:
        instance = self._store.get_instance(campaign_id)
        if instance is None:
            raise KeyError(f"campaign not found: {campaign_id}")
        return instance

    def summarize_campaign_task(self, campaign_id: str) -> dict[str, Any]:
        instance = self._require_instance(campaign_id)
        self._refresh_status_semantics(instance)
        return dict(instance.metadata.get("task_summary") or {})

    def append_campaign_feedback(self, campaign_id: str, feedback: str) -> CampaignInstance:
        instance = self._require_instance(campaign_id)
        feedback_text = str(feedback or "").strip()
        if not feedback_text:
            raise ValueError("feedback is required")
        session_id = str(instance.supervisor_session_id or "").strip()
        if not session_id:
            raise ValueError(f"campaign session is missing: {campaign_id}")

        feedback_recorded_at = self._now_text()
        try:
            shared_state = self._workflow_factory.load_session(session_id).shared_state.state
        except Exception as exc:
            raise ValueError(f"campaign session is unavailable: {campaign_id}") from exc
        history = [
            dict(item)
            for item in (shared_state.get("user_feedback_items") or [])
            if isinstance(item, Mapping)
        ]
        feedback_item = {
            "event_id": f"campaign_feedback_{len(history) + 1}",
            "feedback": feedback_text,
            "recorded_at": feedback_recorded_at,
        }
        history.append(feedback_item)
        history = history[-10:]
        self._workflow_factory.patch_shared_state(
            session_id,
            {
                "latest_user_feedback": feedback_text,
                "latest_user_feedback_at": feedback_recorded_at,
                "user_feedback_count": len(history),
                "user_feedback_items": history,
            },
        )
        entry_key = f"user_feedback_{len(history)}"
        self._workflow_factory.upsert_blackboard_entry(
            session_id,
            entry_key=entry_key,
            payload=feedback_item,
            entry_kind="user_feedback",
            step_id="turn",
            author_role_id="user",
            tags=["user_feedback", "campaign_feedback"],
            visibility_scope="session",
            dedupe_key=f"{feedback_recorded_at}:{feedback_text}",
        )
        self._append_event(
            instance,
            event_type="user_feedback_appended",
            iteration=instance.current_iteration,
            phase=CampaignPhase.normalize(instance.current_phase),
            payload=feedback_item,
        )
        instance.touch()
        self._store.save_instance(instance)
        return self._reload_required(campaign_id)

    def list_campaigns(
        self,
        *,
        status: str = "",
        limit: int = 20,
    ) -> list[CampaignInstance]:
        target_status = str(status or "").strip().lower()
        items = [
            instance
            for instance in self._store.list_instances()
            if not target_status or instance.status == target_status
        ]
        items.sort(
            key=lambda item: (str(item.updated_at or "").strip(), str(item.campaign_id or "").strip()),
            reverse=True,
        )
        if int(limit or 0) > 0:
            return items[: int(limit)]
        return items

    def list_campaign_artifacts(self, campaign_id: str) -> list[CampaignArtifactSummary]:
        self._require_instance(campaign_id)
        return self._store.load_artifact_index(campaign_id)

    def list_campaign_events(
        self,
        campaign_id: str,
        *,
        event_type: str = "",
        limit: int = 20,
    ) -> list[CampaignEvent]:
        self._require_instance(campaign_id)
        items = self._store.list_events(campaign_id, event_type=event_type)
        items.sort(
            key=lambda item: (str(item.created_at or "").strip(), str(item.event_id or "").strip()),
            reverse=True,
        )
        if int(limit or 0) > 0:
            return items[: int(limit)]
        return items

    def list_operator_actions(
        self,
        campaign_id: str,
        *,
        limit: int = 50,
    ) -> list[OperatorActionRecord]:
        instance = self._require_instance(campaign_id)
        operator_plane = _operator_plane_payload(instance.metadata)
        items = [
            OperatorActionRecord.from_dict(item)
            for item in operator_plane.get("actions") or []
            if isinstance(item, Mapping)
        ]
        items.sort(key=lambda item: (str(item.created_at or "").strip(), str(item.action_id or "").strip()), reverse=True)
        if int(limit or 0) > 0:
            return items[: int(limit)]
        return items

    def get_operator_action_detail(self, campaign_id: str, action_id: str) -> dict[str, Any]:
        instance = self._require_instance(campaign_id)
        operator_plane = _operator_plane_payload(instance.metadata)
        target_action_id = str(action_id or "").strip()
        action = next(
            (
                OperatorActionRecord.from_dict(item)
                for item in operator_plane.get("actions") or []
                if isinstance(item, Mapping) and str(item.get("action_id") or "").strip() == target_action_id
            ),
            None,
        )
        if action is None:
            raise KeyError(f"operator action not found: {target_action_id}")
        receipt = next(
            (
                OperatorPatchReceipt.from_dict(item)
                for item in operator_plane.get("patch_receipts") or []
                if isinstance(item, Mapping) and str(item.get("action_id") or "").strip() == target_action_id
            ),
            None,
        )
        recovery = next(
            (
                RecoveryDecisionReceipt.from_dict(item)
                for item in operator_plane.get("recovery_decisions") or []
                if isinstance(item, Mapping) and str(item.get("action_id") or "").strip() == target_action_id
            ),
            None,
        )
        return {
            "action": action.to_dict(),
            "patch_receipt": receipt.to_dict() if receipt is not None else {},
            "recovery_decision": recovery.to_dict() if recovery is not None else {},
        }

    def apply_operator_patch(
        self,
        campaign_id: str,
        *,
        status: str = "",
        current_phase: str = "",
        next_phase: str = "",
        metadata_patch: Mapping[str, Any] | None = None,
        reason: str = "",
    ) -> CampaignInstance:
        instance = self._require_instance(campaign_id)
        if not self._use_legacy_supervisor_for_instance(instance):
            previous_status = instance.status
            if status:
                normalized_status = str(status or "").strip().lower()
                if normalized_status in {"active", "running"}:
                    instance.status = "running"
                elif normalized_status in {"stopped", "paused"}:
                    instance.status = "paused"
                elif normalized_status in {"failed", "cancelled", "completed", "draft", "waiting"}:
                    instance.status = normalized_status
            if isinstance(metadata_patch, Mapping) and metadata_patch:
                instance.metadata = _merge_dict_patch(instance.metadata, metadata_patch)
            if current_phase or next_phase:
                instance.metadata["operator_runtime_overrides"] = _merge_dict_patch(
                    instance.metadata.get("operator_runtime_overrides"),
                    {
                        "last_action": "operator_patch",
                        "resume_from": str(current_phase or next_phase or "").strip(),
                        "requested_next_phase": str(next_phase or "").strip(),
                    },
                )
            self._refresh_status_semantics(instance)
            self._sync_spec_metadata(instance)
            self._sync_campaign_session(instance, reason="operator_patch")
            instance.touch()
            self._store.save_instance(instance)
            self._append_event(
                instance,
                event_type="campaign_operator_patch_applied",
                iteration=instance.current_iteration,
                phase=CampaignPhase.normalize(instance.current_phase),
                payload={
                    "reason": str(reason or "").strip(),
                    "from_status": previous_status,
                    "to_status": instance.status,
                },
            )
            return self._reload_required(campaign_id)
        previous_phase = instance.current_phase
        previous_status = instance.status
        phase_path = _phase_path_from_metadata(instance.metadata)
        if status:
            instance.status = str(status or "").strip().lower()
        if current_phase:
            instance.current_phase = CampaignPhase.normalize(current_phase).value
        if next_phase:
            instance.next_phase = CampaignPhase.normalize(next_phase, default=CampaignPhase.ITERATE).value
        elif current_phase:
            instance.next_phase = _next_phase_after(phase_path, instance.current_phase)
        if isinstance(metadata_patch, Mapping) and metadata_patch:
            instance.metadata = _merge_dict_patch(instance.metadata, metadata_patch)
        phase_runtime = _contract_payload(instance.metadata, "phase_runtime")
        if current_phase:
            phase_runtime["last_operator_transition_at"] = self._now_text()
            phase_runtime["last_operator_transition_reason"] = str(reason or "").strip()
            phase_runtime["phase_path"] = phase_path
            instance.metadata["phase_runtime"] = phase_runtime
        if current_phase and previous_phase != instance.current_phase:
            phase_history = [
                dict(item)
                for item in instance.metadata.get("phase_history") or []
                if isinstance(item, Mapping)
            ]
            phase_history.append(
                {
                    "phase": instance.current_phase,
                    "next_phase": instance.next_phase,
                    "status": "operator_patch",
                    "reason": str(reason or "").strip(),
                    "from_phase": previous_phase,
                }
            )
            instance.metadata["phase_history"] = phase_history
        self._refresh_status_semantics(instance)
        self._sync_spec_metadata(instance)
        instance.touch()
        self._store.save_instance(instance)
        payload = {
            "reason": str(reason or "").strip(),
            "from_status": previous_status,
            "to_status": instance.status,
            "from_phase": previous_phase,
            "to_phase": instance.current_phase,
            "next_phase": instance.next_phase,
        }
        self._append_event(
            instance,
            event_type="campaign_operator_patch_applied",
            iteration=instance.current_iteration,
            phase=CampaignPhase.normalize(instance.current_phase),
            payload=payload,
        )
        return self._reload_required(campaign_id)

    def record_operator_action(
        self,
        campaign_id: str,
        *,
        action: OperatorActionRecord | Mapping[str, Any],
        patch_receipt: OperatorPatchReceipt | Mapping[str, Any] | None = None,
        recovery_decision: RecoveryDecisionReceipt | Mapping[str, Any] | None = None,
    ) -> CampaignInstance:
        instance = self._require_instance(campaign_id)
        action_record = action if isinstance(action, OperatorActionRecord) else OperatorActionRecord.from_dict(action)
        receipt = (
            patch_receipt
            if isinstance(patch_receipt, OperatorPatchReceipt)
            else OperatorPatchReceipt.from_dict(patch_receipt)
            if isinstance(patch_receipt, Mapping)
            else None
        )
        recovery = (
            recovery_decision
            if isinstance(recovery_decision, RecoveryDecisionReceipt)
            else RecoveryDecisionReceipt.from_dict(recovery_decision)
            if isinstance(recovery_decision, Mapping)
            else None
        )
        operator_plane = _operator_plane_payload(instance.metadata)
        actions = [
            item
            for item in operator_plane.get("actions") or []
            if isinstance(item, Mapping) and str(item.get("action_id") or "").strip() != action_record.action_id
        ]
        receipts = [
            item
            for item in operator_plane.get("patch_receipts") or []
            if isinstance(item, Mapping) and str(item.get("action_id") or "").strip() != action_record.action_id
        ]
        recoveries = [
            item
            for item in operator_plane.get("recovery_decisions") or []
            if isinstance(item, Mapping) and str(item.get("action_id") or "").strip() != action_record.action_id
        ]
        if receipt is not None:
            action_record.receipt_id = action_record.receipt_id or receipt.receipt_id
            receipts.append(receipt.to_dict())
        if recovery is not None:
            action_record.recovery_decision_id = action_record.recovery_decision_id or recovery.decision_id
            recoveries.append(recovery.to_dict())
        actions.append(action_record.to_dict())
        actions.sort(key=lambda item: (str(item.get("created_at") or "").strip(), str(item.get("action_id") or "").strip()))
        receipts.sort(key=lambda item: (str(item.get("created_at") or "").strip(), str(item.get("receipt_id") or "").strip()))
        recoveries.sort(key=lambda item: (str(item.get("created_at") or "").strip(), str(item.get("decision_id") or "").strip()))
        operator_plane["actions"] = actions
        operator_plane["patch_receipts"] = receipts
        operator_plane["recovery_decisions"] = recoveries
        operator_plane["latest_action_id"] = action_record.action_id
        instance.metadata["operator_plane"] = operator_plane
        self._refresh_status_semantics(instance)
        self._sync_spec_metadata(instance)
        instance.touch()
        self._store.save_instance(instance)
        self._append_event(
            instance,
            event_type="operator_action_recorded",
            iteration=instance.current_iteration,
            phase=CampaignPhase.normalize(instance.current_phase),
            payload={
                "action_id": action_record.action_id,
                "action_type": action_record.action_type,
                "target_scope": action_record.target_scope,
                "target_node_id": action_record.target_node_id,
                "trace_id": action_record.trace_id,
                "status": action_record.status,
                "result_summary": action_record.result_summary,
            },
        )
        if receipt is not None:
            self._append_event(
                instance,
                event_type="operator_patch_recorded",
                iteration=instance.current_iteration,
                phase=CampaignPhase.normalize(instance.current_phase),
                payload={
                    "action_id": action_record.action_id,
                    "receipt_id": receipt.receipt_id,
                    "patch_kind": receipt.patch_kind,
                    "effective_scope": receipt.effective_scope,
                    "effective_timing": receipt.effective_timing,
                },
            )
        if recovery is not None:
            self._append_event(
                instance,
                event_type="operator_recovery_recorded",
                iteration=instance.current_iteration,
                phase=CampaignPhase.normalize(instance.current_phase),
                payload={
                    "action_id": action_record.action_id,
                    "decision_id": recovery.decision_id,
                    "resume_from": recovery.resume_from,
                    "recovery_candidate_id": recovery.recovery_candidate_id,
                    "result_state": recovery.result_state,
                },
            )
        return self._reload_required(campaign_id)

    def resume_campaign(self, campaign_id: str) -> CampaignInstance:
        instance = self._require_instance(campaign_id)
        if not self._use_legacy_supervisor_for_instance(instance):
            return self.run_campaign_turn(campaign_id)
        if instance.status == "stopped":
            raise ValueError(f"campaign is stopped: {campaign_id}")
        if instance.status == "completed":
            return instance

        iteration = instance.current_iteration + 1
        instance.current_iteration = iteration
        instance.status = "active"
        supervisor_runtime = self._supervisor_runtime_for_instance(instance)
        implement_outcome = supervisor_runtime.run_implement_phase(instance=instance)
        implement_artifacts = self._apply_phase_outcome(instance, implement_outcome)
        implement_artifact = implement_artifacts[0]
        implement_payload = self._load_artifact_payload(instance.campaign_id, implement_artifact)
        self._record_implement_artifact(instance, artifact=implement_artifact, payload=implement_payload)
        for event in implement_outcome.events:
            if event.event_type == "implement_completed":
                event.payload.setdefault("artifact_id", implement_artifact.artifact_id)
        self._apply_events(instance, implement_outcome.events)
        verdict = supervisor_runtime.review_iteration(
            instance=instance,
            implement_artifact_id=implement_artifact.artifact_id,
        )
        instance.add_verdict(verdict)
        instance.metadata["evaluation_contract"] = self._merge_evaluation_contract(
            instance.metadata.get("evaluation_contract"),
            verdict,
        )
        self._record_acceptance_verdict(instance, verdict)
        verdict_artifact = self._record_artifact(
            instance,
            phase=CampaignPhase.EVALUATE,
            iteration=iteration,
            kind="evaluation_verdict",
            label=f"Evaluation verdict iteration {iteration}",
            payload=verdict.to_dict(),
            metadata={"decision": verdict.decision, "reviewer_role_id": verdict.reviewer_role_id},
        )
        self._append_event(
            instance,
            event_type="evaluate_completed",
            iteration=iteration,
            phase=CampaignPhase.EVALUATE,
            payload={
                "verdict_id": verdict.verdict_id,
                "decision": verdict.decision,
                "artifact_id": verdict_artifact.artifact_id,
                "reviewer_role_id": verdict.reviewer_role_id,
            },
        )
        instance.current_phase = CampaignPhase.ITERATE.value
        iterate_outcome = supervisor_runtime.run_iterate_phase(
            instance=instance,
            verdict=verdict,
        )
        revised_contract = iterate_outcome.revised_contract
        if revised_contract is not None:
            instance.add_contract_revision(revised_contract)
        iterate_artifacts = self._apply_phase_outcome(instance, iterate_outcome.iterate)
        for event in iterate_outcome.iterate.events:
            if event.event_type == "working_contract_rewritten" and iterate_artifacts:
                event.payload.setdefault("artifact_id", iterate_artifacts[0].artifact_id)
            if event.event_type == "campaign_converged":
                event.payload.setdefault("verdict_id", verdict.verdict_id)
        self._apply_events(instance, iterate_outcome.iterate.events)
        instance.next_phase = iterate_outcome.iterate.next_phase.value
        instance.status = iterate_outcome.iterate.status
        self._record_runtime_metadata(
            instance,
            merge_phase_metadata(
                implement_outcome.metadata,
                {"phase_path": ["evaluate"], "reviewer_role_id": verdict.reviewer_role_id},
                iterate_outcome.runtime_metadata,
            ),
        )
        self._refresh_status_semantics(instance)
        self._sync_spec_metadata(instance)
        instance.touch()
        self._store.save_instance(instance)
        return self._reload_required(campaign_id)

    def run_campaign_turn(self, campaign_id: str, *, reason: str = "") -> CampaignInstance:
        instance = self._require_instance(campaign_id)
        if self._use_legacy_supervisor_for_instance(instance):
            return self.resume_campaign(campaign_id)
        return self._resume_campaign_agent_turn(instance, reason=reason)

    def stop_campaign(self, campaign_id: str) -> CampaignInstance:
        instance = self._require_instance(campaign_id)
        if not self._use_legacy_supervisor_for_instance(instance):
            instance.status = "paused"
            instance.next_phase = instance.current_phase
            instance.stopped_at = self._now_text() or instance.updated_at
            self._refresh_status_semantics(instance)
            self._sync_spec_metadata(instance)
            self._sync_campaign_session(instance, reason="campaign_paused")
            instance.touch()
            self._store.save_instance(instance)
            self._append_event(
                instance,
                event_type="campaign_paused",
                iteration=instance.current_iteration,
                phase=CampaignPhase.normalize(instance.current_phase),
                payload={"stopped_at": instance.stopped_at},
            )
            return self._reload_required(campaign_id)
        if instance.status == "completed":
            return instance
        instance.status = "stopped"
        instance.current_phase = CampaignPhase.ITERATE.value
        instance.next_phase = CampaignPhase.ITERATE.value
        instance.stopped_at = self._now_text() or instance.updated_at
        self._refresh_status_semantics(instance)
        self._sync_spec_metadata(instance)
        instance.touch()
        self._store.save_instance(instance)
        self._append_event(
            instance,
            event_type="campaign_stopped",
            iteration=instance.current_iteration,
            phase=CampaignPhase.ITERATE,
            payload={"stopped_at": instance.stopped_at},
        )
        return self._reload_required(campaign_id)

    def _resume_campaign_agent_turn(self, instance: CampaignInstance, *, reason: str = "") -> CampaignInstance:
        if instance.status in {"completed", "failed", "cancelled"}:
            return instance
        if instance.status == "paused":
            instance.status = "running"
        receipt = self._run_agent_turn(instance)
        self._apply_turn_receipt(instance, receipt)
        self._refresh_status_semantics(instance)
        self._sync_spec_metadata(instance)
        self._sync_campaign_session(instance, reason=reason or "campaign_turn_committed")
        instance.touch()
        self._store.save_instance(instance)
        return self._reload_required(instance.campaign_id)

    def _run_agent_turn(self, instance: CampaignInstance) -> CampaignTurnReceipt:
        next_turn = int(instance.current_iteration or 0) + 1
        metadata = dict(instance.metadata or {})
        runtime_payload = dict(metadata.get("campaign_runtime") or {})
        runtime_mode = str(runtime_payload.get("mode") or "deterministic").strip().lower() or "deterministic"
        result = None
        if runtime_mode == "codex" and self._codex_provider is not None:
            runtime_request = _merge_runtime_request(
                self._codex_runtime_request,
                _runtime_request_from_metadata(metadata),
            )
            result = self._codex_provider.run(
                prompt=self._agent_turn_prompt(instance, turn_index=next_turn),
                workspace=_workspace_from_instance(instance),
                timeout=self._codex_timeout,
                runtime_request=runtime_request,
            )
        summary = str(
            getattr(result, "output_text", "")
            or metadata.get("latest_summary")
            or f"campaign turn {next_turn} recorded for {instance.top_level_goal or instance.campaign_id}"
        ).strip()
        delivery_refs = self._build_turn_delivery_refs(
            instance=instance,
            turn_index=next_turn,
            output_text=summary,
            runtime_mode=runtime_mode,
        )
        decision = self._agent_turn_decision(
            instance=instance,
            turn_index=next_turn,
            delivery_refs=delivery_refs,
        )
        macro_state = "completed" if decision == "converge" else "running"
        next_action = (
            "publish or hand off accepted deliverables"
            if macro_state == "completed"
            else f"resume the next supervisor turn ({next_turn + 1})"
        )
        verdict = EvaluationVerdict(
            campaign_id=instance.campaign_id,
            iteration=next_turn,
            phase=CampaignPhase.ITERATE.value,
            decision=decision,
            score=1.0 if decision == "converge" else 0.65,
            rationale=summary[:400],
            reviewer_role_id="campaign_supervisor",
            evidence_artifact_ids=[],
            next_iteration_goal="" if decision == "converge" else instance.top_level_goal,
            metadata={
                "evaluator_kind": "agent_supervisor",
                "runtime_mode": runtime_mode,
            },
        )
        artifact_records = [
            {
                "phase": CampaignPhase.ITERATE.value,
                "iteration": next_turn,
                "kind": "campaign_turn_report",
                "label": f"Campaign turn {next_turn}",
                "payload": {
                    "summary": summary,
                    "next_action": next_action,
                    "deliverable_refs": delivery_refs,
                    "runtime_mode": runtime_mode,
                    "placeholder": not bool(delivery_refs),
                },
                "metadata": {
                    "turn_index": next_turn,
                    "runtime_mode": runtime_mode,
                    "placeholder": not bool(delivery_refs),
                },
            }
        ]
        return CampaignTurnReceipt(
            campaign_id=instance.campaign_id,
            session_id=str(instance.supervisor_session_id or "").strip(),
            macro_state=macro_state,
            summary=summary[:500],
            next_action=next_action,
            delivery_refs=delivery_refs,
            verdict=verdict.to_dict(),
            artifact_records=artifact_records,
            session_patch={
                "turn_count": next_turn,
                "latest_summary": summary[:500],
                "latest_next_action": next_action,
                "latest_delivery_refs": delivery_refs,
                "latest_verdict": verdict.to_dict(),
            },
            advisory_updates={
                "runtime_mode": runtime_mode,
            },
            continue_token="" if macro_state == "completed" else f"campaign:{instance.campaign_id}:turn:{next_turn + 1}",
            yield_reason="completed" if macro_state == "completed" else "turn_completed",
        )

    def _build_turn_delivery_refs(
        self,
        *,
        instance: CampaignInstance,
        turn_index: int,
        output_text: str,
        runtime_mode: str,
    ) -> list[str]:
        metadata = dict(instance.metadata or {})
        if runtime_mode == "codex":
            refs = _write_phase_bundle_outputs(
                phase=CampaignPhase.IMPLEMENT,
                iteration=turn_index,
                output_text=output_text,
                metadata=metadata,
            )
            if refs:
                return refs
        bundle_root = str(metadata.get("bundle_root") or "").strip()
        if not bundle_root:
            return []
        target = Path(bundle_root) / "artifacts" / f"turn_{turn_index:02d}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# Campaign Turn {turn_index}\n\n{output_text}\n", encoding="utf-8")
        return [str(target)]

    def _agent_turn_decision(
        self,
        *,
        instance: CampaignInstance,
        turn_index: int,
        delivery_refs: list[str],
    ) -> str:
        metadata = dict(instance.metadata or {})
        spec_payload = dict(metadata.get("spec") or {})
        spec_metadata = dict(spec_payload.get("metadata") or {})
        sequence = _normalized_text_list(
            metadata.get("reviewer_decision_sequence") or spec_metadata.get("reviewer_decision_sequence")
        )
        if sequence:
            index = max(0, turn_index - 1)
            if index < len(sequence):
                decision = sequence[index].lower()
                if decision in {"continue", "recover", "converge"}:
                    return decision
        strict_acceptance = bool(metadata.get("strict_acceptance_required"))
        pending = [
            item
            for item in _normalized_text_list(metadata.get("pending_correctness_checks"))
            if item not in set(_normalized_text_list(metadata.get("resolved_correctness_checks")))
            and item not in set(_normalized_text_list(metadata.get("waived_correctness_checks")))
        ]
        max_iterations = int(instance.working_contract.iteration_budget.max_iterations or 1)
        if strict_acceptance and (pending or not delivery_refs):
            return "recover" if turn_index >= max_iterations else "continue"
        if turn_index >= max_iterations:
            return "converge"
        return "continue"

    def _apply_turn_receipt(self, instance: CampaignInstance, receipt: CampaignTurnReceipt) -> None:
        instance.current_iteration = int(instance.current_iteration or 0) + 1
        instance.status = receipt.macro_state
        instance.current_phase = CampaignPhase.ITERATE.value
        instance.next_phase = CampaignPhase.ITERATE.value
        instance.metadata["latest_summary"] = receipt.summary
        instance.metadata["latest_next_action"] = receipt.next_action
        instance.metadata["latest_delivery_refs"] = list(receipt.delivery_refs)
        instance.metadata["latest_turn_receipt"] = receipt.to_dict()
        turn_cursor = dict(instance.metadata.get("turn_cursor") or {})
        turn_cursor["turn_count"] = int(instance.current_iteration or 0)
        turn_cursor["last_turn_id"] = receipt.turn_id
        turn_cursor["continue_token"] = receipt.continue_token
        instance.metadata["turn_cursor"] = turn_cursor
        verdict_payload = dict(receipt.verdict or {})
        if verdict_payload:
            verdict = EvaluationVerdict.from_dict(verdict_payload)
            instance.add_verdict(verdict)
            instance.metadata["latest_verdict"] = verdict.to_dict()
            instance.metadata["latest_acceptance_decision"] = verdict.decision
            pending_checks = [
                item
                for item in _normalized_text_list(instance.metadata.get("pending_correctness_checks"))
                if item not in set(_normalized_text_list(instance.metadata.get("resolved_correctness_checks")))
                and item not in set(_normalized_text_list(instance.metadata.get("waived_correctness_checks")))
            ]
            instance.metadata["latest_acceptance_blockers"] = ["pending_correctness_checks"] if pending_checks else []
            instance.metadata["evaluation_contract"] = self._merge_evaluation_contract(
                instance.metadata.get("evaluation_contract"),
                verdict,
            )
        for record in receipt.artifact_records:
            artifact_record = CampaignArtifactRecord(
                phase=CampaignPhase.normalize(record.get("phase"), default=CampaignPhase.ITERATE),
                iteration=int(record.get("iteration") or instance.current_iteration),
                kind=str(record.get("kind") or "").strip(),
                label=str(record.get("label") or "").strip(),
                payload=dict(record.get("payload") or {}),
                metadata=dict(record.get("metadata") or {}),
            )
            artifact = self._record_artifact_from_record(instance, artifact_record)
            payload = dict(artifact_record.payload or {})
            if artifact_record.kind == "campaign_turn_report":
                payload.setdefault("deliverable_refs", list(receipt.delivery_refs))
                self._record_implement_artifact(instance, artifact=artifact, payload=payload)
        self._store.append_turn_receipt(receipt)
        self._append_event(
            instance,
            event_type="campaign_turn_committed",
            iteration=instance.current_iteration,
            phase=CampaignPhase.ITERATE,
            payload={
                "turn_id": receipt.turn_id,
                "macro_state": receipt.macro_state,
                "yield_reason": receipt.yield_reason,
            },
        )

    def _agent_turn_prompt(self, instance: CampaignInstance, *, turn_index: int) -> str:
        metadata = dict(instance.metadata or {})
        task_summary = dict(metadata.get("task_summary") or {})
        return (
            "You are the campaign supervisor.\n"
            f"Campaign: {instance.campaign_id}\n"
            f"Goal: {instance.top_level_goal}\n"
            f"Turn: {turn_index}\n"
            f"Materials: {', '.join(instance.materials) if instance.materials else 'none'}\n"
            f"Constraints: {', '.join(instance.hard_constraints) if instance.hard_constraints else 'none'}\n"
            f"Current summary: {str(task_summary.get('progress', {}).get('latest_summary') or metadata.get('latest_summary') or '').strip() or 'none'}\n"
            "Produce a concise turn summary, what changed, and the next action."
        )

    def _coerce_spec(self, spec: CampaignSpec | Mapping[str, Any] | None) -> CampaignSpec:
        if isinstance(spec, CampaignSpec):
            return spec
        if isinstance(spec, Mapping):
            return CampaignSpec.from_dict(spec)
        raise TypeError("campaign spec is required")

    def _require_instance(self, campaign_id: str) -> CampaignInstance:
        instance = self._store.get_instance(campaign_id)
        if instance is None:
            raise KeyError(f"campaign not found: {campaign_id}")
        return instance

    def _reload_required(self, campaign_id: str) -> CampaignInstance:
        return self._require_instance(campaign_id)

    def _build_initial_working_contract(self, spec: CampaignSpec) -> WorkingContract:
        goal = spec.top_level_goal or "Deliver a bounded repository improvement"
        materials = list(spec.materials)
        acceptance = [
            "produce at least one implementation-ready change proposal",
            "record reviewer-owned convergence evidence",
            "keep goal and hard constraints immutable",
        ]
        if materials:
            acceptance.append(f"consume {len(materials)} material input(s) during discovery")
        risks = ["uncertain implementation detail", "acceptance criteria may need refinement"]
        if spec.hard_constraints:
            risks.append("hard constraints may reduce feasible iteration space")
        return WorkingContract(
            working_goal=goal,
            working_acceptance=acceptance,
            iteration_budget=IterationBudget.from_dict(spec.iteration_budget.to_dict()),
            risk_register=risks,
            phase_scorecard={
                CampaignPhase.DISCOVER.value: "completed",
                CampaignPhase.IMPLEMENT.value: "queued",
            },
            strategy_notes=[
                "discover produces the initial contract",
                "reviewer owns convergence decisions",
            ],
            last_verdict_decision="continue",
        )

    def _record_artifact(
        self,
        instance: CampaignInstance,
        *,
        phase: CampaignPhase,
        iteration: int,
        kind: str,
        label: str,
        payload: Mapping[str, Any] | None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CampaignArtifactSummary:
        artifact_payload = dict(payload or {})
        artifact_metadata = dict(metadata or {})
        deliverable_refs = _normalized_text_list(artifact_payload.get("deliverable_refs"))
        if deliverable_refs and not str(artifact_metadata.get("deliverable_ref") or "").strip():
            artifact_metadata["deliverable_ref"] = deliverable_refs[0]
        if "placeholder" in artifact_payload and "placeholder" not in artifact_metadata:
            artifact_metadata["placeholder"] = bool(artifact_payload.get("placeholder"))
        artifact = CampaignArtifactSummary(
            campaign_id=instance.campaign_id,
            iteration=iteration,
            phase=phase.value,
            kind=kind,
            label=label,
            metadata=artifact_metadata,
        )
        path = self._store.write_artifact_payload(instance.campaign_id, artifact, artifact_payload)
        artifact.ref = str(path.relative_to(self._store.campaign_root(instance.campaign_id)))
        artifacts = self._store.load_artifact_index(instance.campaign_id)
        artifacts.append(artifact)
        self._store.save_artifact_index(instance.campaign_id, artifacts)
        self._append_event(
            instance,
            event_type="artifact_recorded",
            iteration=iteration,
            phase=phase,
            payload={
                "artifact_id": artifact.artifact_id,
                "kind": artifact.kind,
                "label": artifact.label,
                "ref": artifact.ref,
            },
        )
        return artifact

    def _apply_phase_outcome(
        self,
        instance: CampaignInstance,
        outcome: CampaignPhaseOutcome,
    ) -> list[CampaignArtifactSummary]:
        instance.current_phase = outcome.phase.value
        instance.next_phase = outcome.next_phase.value
        instance.status = outcome.status
        self._record_runtime_metadata(instance, outcome.metadata)
        artifacts: list[CampaignArtifactSummary] = []
        for spec in outcome.artifacts:
            artifacts.append(
                self._record_artifact_from_record(instance, spec),
            )
        self._append_phase_history(instance, outcome)
        return artifacts

    def _apply_events(self, instance: CampaignInstance, events: list[CampaignEventRecord]) -> None:
        for event in events:
            self._append_event_from_record(instance, event)

    def _append_phase_history(self, instance: CampaignInstance, outcome: CampaignPhaseOutcome) -> None:
        phase_history = instance.metadata.setdefault("phase_history", [])
        if not isinstance(phase_history, list):
            phase_history = []
            instance.metadata["phase_history"] = phase_history
        phase_history.append(
            {
                "phase": outcome.phase.value,
                "next_phase": outcome.next_phase.value,
                "status": outcome.status,
                "iteration": instance.current_iteration,
            }
        )

    def _record_runtime_metadata(self, instance: CampaignInstance, metadata: Mapping[str, Any] | None) -> None:
        if not isinstance(metadata, Mapping):
            return
        current = instance.metadata.get("phase_runtime")
        instance.metadata["phase_runtime"] = merge_phase_metadata(
            current if isinstance(current, Mapping) else {},
            metadata,
        )

    def _load_artifact_payload(
        self,
        campaign_id: str,
        artifact: CampaignArtifactSummary,
    ) -> dict[str, Any]:
        if not str(artifact.ref or "").strip():
            return {}
        return self._store.read_artifact_payload(campaign_id, artifact.ref)

    def _record_implement_artifact(
        self,
        instance: CampaignInstance,
        *,
        artifact: CampaignArtifactSummary,
        payload: Mapping[str, Any] | None,
    ) -> None:
        artifact_payload = dict(payload or {})
        deliverable_refs = _merge_text_lists(
            artifact_payload.get("deliverable_refs"),
            [artifact.metadata.get("deliverable_ref")],
        )
        snapshot = {
            **artifact_payload,
            "artifact_id": artifact.artifact_id,
            "artifact_ref": artifact.ref,
            "kind": artifact.kind,
            "phase": artifact.phase,
            "iteration": artifact.iteration,
            "deliverable_refs": deliverable_refs,
            "placeholder": bool(
                artifact_payload.get("placeholder", artifact.metadata.get("placeholder", False))
            ),
        }
        instance.metadata["latest_implement_artifact"] = snapshot
        self._sync_correctness_checks_from_payload(instance, artifact_payload)

    def _sync_correctness_checks_from_payload(
        self,
        instance: CampaignInstance,
        payload: Mapping[str, Any] | None,
    ) -> None:
        artifact_payload = dict(payload or {})
        resolved = _merge_text_lists(
            instance.metadata.get("resolved_correctness_checks"),
            artifact_payload.get("checks_resolved"),
        )
        waived = _merge_text_lists(
            instance.metadata.get("waived_correctness_checks"),
            artifact_payload.get("checks_waived"),
        )
        pending_source = artifact_payload.get("checks_remaining")
        pending = (
            _normalized_text_list(pending_source)
            if isinstance(pending_source, list)
            else _normalized_text_list(instance.metadata.get("pending_correctness_checks"))
        )
        pending = [item for item in pending if item not in resolved and item not in waived]
        instance.metadata["resolved_correctness_checks"] = resolved
        instance.metadata["waived_correctness_checks"] = waived
        instance.metadata["pending_correctness_checks"] = pending
        instance.metadata["minimal_correctness_ready"] = not pending

    def _record_acceptance_verdict(self, instance: CampaignInstance, verdict: EvaluationVerdict) -> None:
        blockers = _normalized_text_list(dict(verdict.metadata or {}).get("acceptance_blockers"))
        instance.metadata["latest_acceptance_blockers"] = blockers
        instance.metadata["latest_acceptance_decision"] = str(verdict.decision or "").strip()
        if blockers:
            reason = ", ".join(blockers)
        elif str(verdict.decision or "").strip() != "converge":
            reason = str(verdict.rationale or "").strip()
        else:
            reason = ""
        instance.metadata["closure_reason"] = reason
        instance.metadata["not_done_reason"] = reason

    def _sync_spec_metadata(self, instance: CampaignInstance) -> None:
        spec_payload = dict(instance.metadata.get("spec") or {})
        spec_metadata = dict(spec_payload.get("metadata") or {})
        for key in (
            "bundle_root",
            "bundle_manifest",
            "topic_slug",
            "bundle_created_at_local",
            "primary_carrier",
            "startup_mode",
            "strict_acceptance_required",
            "minimal_correctness_ready",
            "pending_correctness_checks",
            "resolved_correctness_checks",
            "waived_correctness_checks",
            "campaign_runtime",
            "planning_contract",
            "evaluation_contract",
            "governance_contract",
            "template_contract",
            "latest_delivery_refs",
            "latest_verdict",
            "latest_summary",
            "latest_next_action",
            "latest_turn_receipt",
            "turn_cursor",
            "task_summary",
            "legacy_refs",
        ):
            if key in instance.metadata:
                value = instance.metadata.get(key)
                if isinstance(value, (dict, list)):
                    spec_metadata[key] = json.loads(json.dumps(value, ensure_ascii=False))
                else:
                    spec_metadata[key] = value
        spec_payload["metadata"] = spec_metadata
        instance.metadata["spec"] = spec_payload

    def _refresh_status_semantics(self, instance: CampaignInstance) -> None:
        if not self._use_legacy_supervisor_for_instance(instance):
            instance.metadata["task_summary"] = self._build_agent_turn_task_summary(instance)
            return
        semantics = build_campaign_semantics(
            {
                **instance.to_dict(),
                "artifacts": [item.to_dict() for item in self._store.load_artifact_index(instance.campaign_id)],
            }
        )
        for key in (
            "execution_state",
            "closure_state",
            "progress_reason",
            "closure_reason",
            "not_done_reason",
            "operational_checks_pending",
            "closure_checks_pending",
            "latest_acceptance_decision",
            "latest_acceptance_blockers",
        ):
            value = semantics.get(key)
            if value is not None:
                instance.metadata[key] = value

    def _build_agent_turn_task_summary(self, instance: CampaignInstance) -> dict[str, Any]:
        metadata = dict(instance.metadata or {})
        governance = dict(metadata.get("governance_contract") or {})
        planning = dict(metadata.get("planning_contract") or {})
        latest_verdict = dict(metadata.get("latest_verdict") or {})
        latest_delivery_refs = list(metadata.get("latest_delivery_refs") or [])
        latest_summary = str(metadata.get("latest_summary") or "").strip()
        latest_next_action = str(metadata.get("latest_next_action") or "").strip()
        status = str(instance.status or "").strip()
        turn_count = int(instance.current_iteration or 0)
        artifact_count = len(self._store.load_artifact_index(instance.campaign_id))
        runtime_mode = str(dict(metadata.get("campaign_runtime") or {}).get("mode") or "deterministic").strip() or "deterministic"
        if status == "completed":
            closure_state = "accepted"
        elif status == "failed":
            closure_state = "failed"
        elif status == "cancelled":
            closure_state = "cancelled"
        elif latest_delivery_refs:
            closure_state = "stage_delivered"
        else:
            closure_state = "open"
        return {
            "mode_id": str(planning.get("mode_id") or "unknown").strip() or "unknown",
            "spec": {
                "goal": str(instance.top_level_goal or "").strip(),
                "campaign_title": str(instance.campaign_title or "").strip(),
                "mode_id": str(planning.get("mode_id") or "unknown").strip() or "unknown",
            },
            "progress": {
                "status": status,
                "turn_count": turn_count,
                "session_status": status,
                "latest_summary": latest_summary,
                "latest_next_action": latest_next_action,
                "artifact_count": artifact_count,
                "runtime_mode": runtime_mode,
            },
            "next_action": latest_next_action or ("campaign is idle" if status == "draft" else "resume the next supervisor turn"),
            "risk": {
                "risk_level": str(governance.get("risk_level") or "medium").strip() or "medium",
                "autonomy_profile": str(governance.get("autonomy_profile") or "reviewed_delivery").strip() or "reviewed_delivery",
                "approval_state": str(governance.get("approval_state") or "none").strip() or "none",
            },
            "output": {
                "bundle_root": str(metadata.get("bundle_root") or "").strip(),
                "latest_delivery_refs": latest_delivery_refs,
                "artifact_count": artifact_count,
            },
            "closure": {
                "state": closure_state,
                "latest_verdict": latest_verdict,
                "final_summary": latest_summary if status in {"completed", "failed", "cancelled"} else "",
            },
        }

    def _record_artifact_from_record(
        self,
        instance: CampaignInstance,
        spec: CampaignArtifactRecord,
    ) -> CampaignArtifactSummary:
        return self._record_artifact(
            instance,
            phase=spec.phase,
            iteration=spec.iteration,
            kind=spec.kind,
            label=spec.label,
            payload=spec.payload,
            metadata=spec.metadata,
        )

    def _append_event_from_record(
        self,
        instance: CampaignInstance,
        spec: CampaignEventRecord,
    ) -> CampaignEvent:
        return self._append_event(
            instance,
            event_type=spec.event_type,
            phase=spec.phase,
            payload=spec.payload,
            iteration=spec.iteration,
        )

    def _append_event(
        self,
        instance: CampaignInstance,
        *,
        event_type: str,
        phase: CampaignPhase,
        payload: Mapping[str, Any] | None = None,
        iteration: int | None = None,
    ) -> CampaignEvent:
        event = CampaignEvent(
            campaign_id=instance.campaign_id,
            event_type=event_type,
            iteration=instance.current_iteration if iteration is None else max(0, int(iteration)),
            phase=phase.value,
            payload=dict(payload or {}),
            created_at=self._now_text(),
        )
        self._store.append_event(event)
        return event

    def _default_title(self, goal: str) -> str:
        text = " ".join(str(goal or "").strip().split())
        return text[:80] if text else "Campaign MVP"

    def _now_text(self) -> str:
        if self._now_factory is None:
            return ""
        return str(self._now_factory() or "").strip()

    def _campaign_runtime_config(self, metadata: Mapping[str, Any] | None) -> dict[str, Any]:
        payload = dict(metadata or {})
        runtime_payload = payload.get("campaign_runtime")
        runtime_config = dict(runtime_payload) if isinstance(runtime_payload, Mapping) else {}
        engine = str(runtime_config.get("engine") or "agent_turn").strip().lower() or "agent_turn"
        if engine not in {"agent_turn", "legacy_supervisor"}:
            engine = "agent_turn"
        mode = str(
            runtime_config.get("mode")
            or payload.get("campaign_runtime_mode")
            or self._campaign_runtime_mode
            or "deterministic"
        ).strip().lower()
        if mode not in {"deterministic", "codex"}:
            mode = "deterministic"
        return {
            "engine": engine,
            "mode": mode,
            "provider": "codex" if mode == "codex" else "deterministic",
        }

    @staticmethod
    def _build_planning_contract(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
        contract = _contract_payload(metadata, "planning_contract")
        return {
            "mode_id": str(contract.get("mode_id") or "unknown").strip() or "unknown",
            "method_profile_id": str(contract.get("method_profile_id") or "").strip(),
            "plan_only": bool(contract.get("plan_only")),
            "draft_ref": str(contract.get("draft_ref") or "").strip(),
            "spec_ref": str(contract.get("spec_ref") or "").strip(),
            "plan_ref": str(contract.get("plan_ref") or "").strip(),
            "progress_ref": str(contract.get("progress_ref") or "").strip(),
        }

    @staticmethod
    def _build_evaluation_contract(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
        contract = _contract_payload(metadata, "evaluation_contract")
        return {
            "review_ref": str(contract.get("review_ref") or "").strip(),
            "latest_review_decision": str(contract.get("latest_review_decision") or "").strip(),
            "latest_acceptance_decision": str(contract.get("latest_acceptance_decision") or "").strip(),
        }

    @staticmethod
    def _build_governance_contract(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
        contract = _contract_payload(metadata, "governance_contract")
        return {
            "autonomy_profile": str(contract.get("autonomy_profile") or "reviewed_delivery").strip() or "reviewed_delivery",
            "risk_level": str(contract.get("risk_level") or "medium").strip() or "medium",
            "approval_state": str(contract.get("approval_state") or "none").strip() or "none",
        }

    @staticmethod
    def _merge_evaluation_contract(
        current: Mapping[str, Any] | None,
        verdict: EvaluationVerdict,
    ) -> dict[str, Any]:
        payload = dict(current or {})
        payload["review_ref"] = str(payload.get("review_ref") or f"verdict:{verdict.verdict_id}").strip()
        payload["latest_review_decision"] = str(verdict.decision or "").strip()
        payload["latest_acceptance_decision"] = str(verdict.decision or "").strip()
        return payload

    @staticmethod
    def _template_contract_from_spec(spec: CampaignSpec) -> dict[str, Any]:
        contract = _template_contract_payload(
            template_origin=spec.template_origin,
            composition_mode=spec.composition_mode,
            skeleton_changed=spec.skeleton_changed,
            composition_plan=spec.composition_plan,
            created_from=spec.created_from,
            negotiation_session_id=spec.negotiation_session_id,
        )
        return contract or {}

    def _supervisor_runtime_for_spec(self, spec: CampaignSpec) -> CampaignSupervisorRuntime:
        return self._supervisor_runtime_for_mode(
            self._campaign_runtime_config(spec.metadata),
            workspace=spec.repo_root or spec.workspace_root,
        )

    def _supervisor_runtime_for_instance(self, instance: CampaignInstance) -> CampaignSupervisorRuntime:
        return self._supervisor_runtime_for_mode(
            self._campaign_runtime_config(instance.metadata),
            workspace=instance.repo_root or instance.workspace_root,
        )

    def _supervisor_runtime_for_mode(
        self,
        runtime_config: Mapping[str, Any],
        *,
        workspace: str,
    ) -> CampaignSupervisorRuntime:
        if self._supervisor_runtime_override is not None:
            return self._supervisor_runtime_override
        if str(runtime_config.get("mode") or "").strip().lower() != "codex":
            return self._default_supervisor_runtime
        provider = self._codex_provider or CliRunnerCampaignCodexProvider(
            cfg=self._config_snapshot,
            runtime_request=self._codex_runtime_request,
        )
        return CodexCampaignSupervisorRuntime(
            phase_runtime=self._default_supervisor_runtime._phase_runtime,
            reviewer_runtime=self._default_supervisor_runtime._reviewer_runtime,
            codex_provider=provider,
            codex_timeout=self._codex_timeout,
            codex_runtime_request={
                **self._codex_runtime_request,
                "workspace_root": str(workspace or self._workspace).strip(),
            },
        )
