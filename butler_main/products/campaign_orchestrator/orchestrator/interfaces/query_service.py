from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from butler_main.agents_os.skills import build_skill_exposure_observation
from butler_main.domains.campaign.status_semantics import build_campaign_semantics

from ..runtime_paths import resolve_orchestrator_run_file

from ..fourth_layer_contracts import (
    build_branch_view,
    build_campaign_observation_snapshot,
    build_campaign_view,
    build_mission_view,
    build_observation_snapshot,
    build_session_view,
)
from ..workspace import build_orchestrator_service_for_workspace, resolve_orchestrator_root
from .campaign_service import OrchestratorCampaignService
from .runner import build_orchestrator_runtime_state_store


class OrchestratorQueryService:
    """Thin query/control boundary for orchestrator-backed missions."""

    def __init__(self, *, campaign_service: OrchestratorCampaignService | None = None) -> None:
        self._campaign_service = campaign_service or OrchestratorCampaignService()

    def get_mission_status(self, workspace: str, mission_id: str) -> dict:
        service = build_orchestrator_service_for_workspace(workspace)
        payload = dict(service.summarize_mission(mission_id))
        payload["mission_view"] = build_mission_view(payload)
        return payload

    def get_campaign_status(self, workspace: str, campaign_id: str) -> dict:
        payload = dict(self._campaign_service.get_campaign_status(workspace, campaign_id))
        artifacts = list(payload.get("artifacts") or self._campaign_service.list_campaign_artifacts(workspace, campaign_id))
        campaign_events = list(payload.get("campaign_events") or self._campaign_service.list_campaign_events(workspace, campaign_id, limit=50))
        payload["artifacts"] = artifacts
        payload["campaign_events"] = campaign_events
        payload["campaign_view"] = build_campaign_view({
            **payload,
            "artifacts": artifacts,
            "artifact_count": len(artifacts),
        })
        mission_id = str(payload.get("mission_id") or "").strip()
        if mission_id:
            try:
                mission_payload = self.get_mission_status(workspace, mission_id)
            except Exception:
                mission_payload = {}
            payload["mission"] = mission_payload
            if mission_payload:
                payload["mission_view"] = mission_payload.get("mission_view") or build_mission_view(mission_payload)
        else:
            payload["mission"] = {}
        session_id = str(
            payload.get("canonical_session_id")
            or payload.get("supervisor_session_id")
            or ""
        ).strip()
        if session_id:
            try:
                session_payload = self.get_workflow_session_status(workspace, session_id)
            except Exception:
                session_payload = {}
            payload["workflow_session"] = session_payload
            if session_payload:
                payload["session_view"] = session_payload.get("session_view") or build_session_view(session_payload)
        else:
            payload["workflow_session"] = {}
        payload["phase_runtime"] = self._build_campaign_phase_runtime(payload)
        payload["session_plane"] = self._build_campaign_session_plane(payload.get("workflow_session"))
        payload["phase_timeline"] = list(payload["phase_runtime"].get("phase_history") or [])
        payload["contract_revisions"] = self._build_campaign_contract_revisions(payload)
        payload["verdict_summary"] = self._build_campaign_verdict_summary(payload)
        payload["session_evidence"] = self._build_campaign_session_evidence(payload)
        payload["user_feedback"] = self._build_campaign_user_feedback(payload)
        payload["planning_summary"] = self._build_campaign_planning_summary(payload)
        payload["evaluation_summary"] = self._build_campaign_evaluation_summary(payload)
        payload["governance_summary"] = self._build_campaign_governance_summary(payload)
        payload.update(self._build_campaign_status_details(payload))
        metadata = dict(payload.get("metadata") or {})
        spec_payload = dict(metadata.get("spec") or {})
        spec_metadata = dict(spec_payload.get("metadata") or {})
        payload["skill_exposure_observation"] = build_skill_exposure_observation(
            workspace,
            exposure=dict(metadata.get("skill_exposure") or spec_metadata.get("skill_exposure") or {}),
            materialization_mode="prompt_block",
        )
        payload["task_summary"] = self._build_campaign_task_summary(payload)
        return payload

    def list_missions(self, workspace: str, *, status: str = "", limit: int = 20) -> list[dict]:
        service = build_orchestrator_service_for_workspace(workspace)
        return [self._annotate_mission_payload(item) for item in service.list_mission_overview(status=status, limit=limit)]

    def list_campaigns(self, workspace: str, *, status: str = "", limit: int = 20) -> list[dict]:
        items = self._campaign_service.list_campaigns(workspace, status=status, limit=limit)
        return [self._annotate_campaign_payload(workspace, item) for item in items]

    def get_branch_status(self, workspace: str, branch_id: str) -> dict:
        service = build_orchestrator_service_for_workspace(workspace)
        payload = dict(service.summarize_branch(branch_id))
        payload["branch_view"] = build_branch_view(payload)
        return payload

    def get_workflow_session_status(self, workspace: str, session_id: str) -> dict:
        service = build_orchestrator_service_for_workspace(workspace)
        payload = dict(service.summarize_workflow_session(session_id))
        payload["session_view"] = build_session_view(payload)
        return payload

    def control_mission(self, workspace: str, mission_id: str, action: str) -> dict:
        service = build_orchestrator_service_for_workspace(workspace)
        return service.control_mission(mission_id, action)

    def append_user_feedback(self, workspace: str, mission_id: str, feedback: str) -> dict:
        service = build_orchestrator_service_for_workspace(workspace)
        return service.append_user_feedback(mission_id, feedback)

    def list_campaign_artifacts(self, workspace: str, campaign_id: str) -> list[dict]:
        return self._campaign_service.list_campaign_artifacts(workspace, campaign_id)

    def list_campaign_events(
        self,
        workspace: str,
        campaign_id: str,
        *,
        event_type: str = "",
        limit: int = 20,
    ) -> list[dict]:
        return self._campaign_service.list_campaign_events(
            workspace,
            campaign_id,
            event_type=event_type,
            limit=limit,
        )

    def list_delivery_events(self, workspace: str, mission_id: str) -> list[dict]:
        service = build_orchestrator_service_for_workspace(workspace)
        return service.list_delivery_events(mission_id)

    def list_recent_events(
        self,
        workspace: str,
        *,
        mission_id: str = "",
        node_id: str = "",
        branch_id: str = "",
        event_type: str = "",
        limit: int = 20,
    ) -> list[dict]:
        service = build_orchestrator_service_for_workspace(workspace)
        return service.list_recent_events(
            mission_id=mission_id,
            node_id=node_id,
            branch_id=branch_id,
            event_type=event_type,
            limit=limit,
        )

    def get_runtime_status(self, workspace: str, *, stale_seconds: int = 120) -> dict:
        runtime_state = build_orchestrator_runtime_state_store(workspace)
        snapshot = runtime_state.status_snapshot(enabled=True, stale_seconds=max(10, int(stale_seconds or 120)))
        return {
            **asdict(snapshot),
            "orchestrator_root": resolve_orchestrator_root(workspace),
            "pid_file": str(runtime_state.pid_file()),
            "watchdog_file": str(runtime_state.watchdog_state_file()),
            "run_state_file": str(runtime_state.run_state_file()),
            "watchdog_state_payload": runtime_state.read_watchdog_state(),
            "run_state_payload": runtime_state.read_run_state(),
        }

    def get_codex_debug_status(self, workspace: str, *, limit: int = 10) -> dict:
        usage_path = resolve_orchestrator_run_file(workspace, "agents_os_runtime_policy_codex_usage.json")
        payload = self._read_json_dict(usage_path)
        selected_at = [str(item).strip() for item in payload.get("selected_at") or [] if str(item).strip()]
        service = build_orchestrator_service_for_workspace(workspace)
        recent_branches: list[dict] = []
        for branch in sorted(service.list_branches(), key=lambda item: str(getattr(item, "updated_at", "") or ""), reverse=True):
            summary = service.summarize_branch(branch.branch_id)
            runtime_debug = dict(summary.get("runtime_debug") or {})
            if not runtime_debug:
                continue
            if not runtime_debug.get("codex_related") and str(runtime_debug.get("cli") or "").strip() != "codex":
                continue
            recent_branches.append(
                {
                    "branch_id": summary.get("branch_id"),
                    "mission_id": summary.get("mission", {}).get("mission_id"),
                    "node_id": summary.get("node", {}).get("node_id"),
                    "status": summary.get("status"),
                    "updated_at": summary.get("updated_at"),
                    "runtime_debug": runtime_debug,
                }
            )
            if len(recent_branches) >= max(1, int(limit or 10)):
                break
        return {
            "usage_file": str(usage_path),
            "window_hours": int(payload.get("window_hours") or 0),
            "selected_count": len(selected_at),
            "selected_at": selected_at[-max(1, int(limit or 10)):],
            "recent_codex_branches": recent_branches,
        }

    def get_startup_observation_window(
        self,
        workspace: str,
        *,
        mission_limit: int = 8,
        branch_limit: int = 8,
        event_limit: int = 20,
        stale_seconds: int = 120,
    ) -> dict:
        service = build_orchestrator_service_for_workspace(workspace)
        observation_window = service.build_observation_window(
            mission_limit=mission_limit,
            branch_limit=branch_limit,
            event_limit=event_limit,
        )
        missions = [self._annotate_mission_payload(item) for item in observation_window.get("missions") or []]
        active_branches = [
            self._annotate_branch_payload(item)
            for item in observation_window.get("active_branches") or []
        ]
        return build_observation_snapshot(
            orchestrator_root=str(resolve_orchestrator_root(workspace)),
            runtime=self.get_runtime_status(workspace, stale_seconds=stale_seconds),
            missions=missions,
            active_branches=active_branches,
            recent_events=list(observation_window.get("recent_events") or []),
            closure_signals=dict(observation_window.get("closure_signals") or {}),
            codex_debug=self.get_codex_debug_status(workspace, limit=branch_limit),
        )

    def get_campaign_observation_window(
        self,
        workspace: str,
        campaign_id: str,
        *,
        event_limit: int = 20,
        stale_seconds: int = 120,
    ) -> dict:
        campaign_payload = self.get_campaign_status(workspace, campaign_id)
        artifacts = self.list_campaign_artifacts(workspace, campaign_id)
        campaign_events = self.list_campaign_events(workspace, campaign_id, limit=event_limit)
        mission_payload: dict[str, object] = {}
        mission_id = str(campaign_payload.get("mission_id") or "").strip()
        if mission_id:
            try:
                mission_payload = self.get_mission_status(workspace, mission_id)
            except Exception:
                mission_payload = {}
        session_payload: dict[str, object] = {}
        session_id = str(
            campaign_payload.get("canonical_session_id")
            or campaign_payload.get("supervisor_session_id")
            or ""
        ).strip()
        if session_id:
            try:
                session_payload = self.get_workflow_session_status(workspace, session_id)
            except Exception:
                session_payload = {}
        return build_campaign_observation_snapshot(
            orchestrator_root=str(resolve_orchestrator_root(workspace)),
            runtime=self.get_runtime_status(workspace, stale_seconds=stale_seconds),
            campaign={
                **campaign_payload,
                "artifacts": artifacts,
                "artifact_count": len(artifacts),
            },
            mission=mission_payload,
            session=session_payload,
            artifacts=artifacts,
            campaign_events=campaign_events,
        )

    @staticmethod
    def _build_campaign_phase_runtime(payload: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(payload.get("metadata") or {})
        phase_runtime = dict(metadata.get("phase_runtime") or {})
        phase_history = [
            dict(item)
            for item in metadata.get("phase_history") or []
            if isinstance(item, dict)
        ]
        contract_history = [
            dict(item)
            for item in payload.get("contract_history") or []
            if isinstance(item, dict)
        ]
        latest_verdict = {}
        verdict_history = [
            dict(item)
            for item in payload.get("verdict_history") or []
            if isinstance(item, dict)
        ]
        if verdict_history:
            latest_verdict = verdict_history[-1]
        semantics = build_campaign_semantics(payload)
        return {
            "runtime_kind": str(phase_runtime.get("runtime_kind") or "").strip(),
            "phase_path": [str(item).strip() for item in phase_runtime.get("phase_path") or [] if str(item).strip()],
            "transition_count": int(phase_runtime.get("transition_count") or len(phase_history)),
            "phase_history": phase_history,
            "bundle_root": str(metadata.get("bundle_root") or "").strip(),
            "runtime_mode": str(dict(metadata.get("campaign_runtime") or {}).get("mode") or "").strip(),
            "pending_checks": list(semantics.get("pending_checks") or []),
            "resolved_checks": list(semantics.get("resolved_checks") or []),
            "waived_checks": list(semantics.get("waived_checks") or []),
            "operational_checks_pending": list(semantics.get("operational_checks_pending") or []),
            "closure_checks_pending": list(semantics.get("closure_checks_pending") or []),
            "contract_versions": [
                int(item.get("version") or 0)
                for item in contract_history
                if int(item.get("version") or 0) > 0
            ],
            "latest_verdict": latest_verdict,
        }

    @staticmethod
    def _build_campaign_session_plane(session_payload: Any) -> dict[str, Any]:
        session = dict(session_payload) if isinstance(session_payload, dict) else {}
        artifact_registry = dict(session.get("artifact_registry") or {})
        blackboard = dict(session.get("blackboard") or {})
        collaboration = dict(session.get("collaboration") or {})
        events = list(session.get("events") or [])
        return {
            "artifact_count": int(artifact_registry.get("artifact_count") or len(artifact_registry.get("artifacts") or [])),
            "blackboard_entry_count": int(blackboard.get("entry_count") or len(blackboard.get("entries") or [])),
            "mailbox_count": int(collaboration.get("mailbox_message_count") or 0),
            "handoff_count": int(collaboration.get("handoff_count") or 0),
            "join_contract_count": int(collaboration.get("join_contract_count") or 0),
            "session_event_count": len(events),
            "session_event_types": sorted(
                {
                    str(item.get("event_type") or "").strip()
                    for item in events
                    if isinstance(item, dict) and str(item.get("event_type") or "").strip()
                }
            ),
        }

    @staticmethod
    def _build_campaign_contract_revisions(payload: dict[str, Any]) -> list[dict[str, Any]]:
        revisions: list[dict[str, Any]] = []
        for item in payload.get("contract_history") or []:
            if not isinstance(item, dict):
                continue
            revisions.append(
                {
                    "contract_id": str(item.get("contract_id") or "").strip(),
                    "version": int(item.get("version") or 0),
                    "working_goal": str(item.get("working_goal") or "").strip(),
                    "rewrite_count": int(item.get("rewrite_count") or 0),
                    "last_verdict_decision": str(item.get("last_verdict_decision") or "").strip(),
                }
            )
        return revisions

    @staticmethod
    def _build_campaign_verdict_summary(payload: dict[str, Any]) -> dict[str, Any]:
        verdicts = [
            dict(item)
            for item in payload.get("verdict_history") or []
            if isinstance(item, dict)
        ]
        latest = verdicts[-1] if verdicts else {}
        return {
            "count": len(verdicts),
            "decisions": [str(item.get("decision") or "").strip() for item in verdicts if str(item.get("decision") or "").strip()],
            "latest": latest,
            "latest_decision": str(latest.get("decision") or "").strip(),
            "latest_score": float(latest.get("score") or 0.0) if latest else 0.0,
            "reviewer_role_id": str(latest.get("reviewer_role_id") or "").strip(),
        }

    @staticmethod
    def _build_campaign_session_evidence(payload: dict[str, Any]) -> dict[str, Any]:
        workflow_session = dict(payload.get("workflow_session") or {})
        session_view = dict(payload.get("session_view") or {})
        session_plane = dict(payload.get("session_plane") or {})
        return {
            "workflow_session_id": str(session_view.get("workflow_session_id") or "").strip(),
            "template_id": str(session_view.get("template_id") or "").strip(),
            "status": str(session_view.get("status") or "").strip(),
            "active_step": str(session_view.get("active_step") or "").strip(),
            "artifact_count": int(session_plane.get("artifact_count") or 0),
            "blackboard_entry_count": int(session_plane.get("blackboard_entry_count") or 0),
            "session_event_count": int(session_plane.get("session_event_count") or 0),
            "session_event_types": list(session_plane.get("session_event_types") or []),
            "driver_kind": str(workflow_session.get("driver_kind") or "").strip(),
        }

    @staticmethod
    def _build_campaign_user_feedback(payload: dict[str, Any]) -> dict[str, Any]:
        mission = dict(payload.get("mission") or {})
        mission_metadata = dict(mission.get("metadata") or {})
        workflow_session = dict(payload.get("workflow_session") or {})
        shared_state = dict((workflow_session.get("shared_state") or {}).get("state") or {})
        mission_events = [
            dict(item)
            for item in mission.get("delivery_events") or []
            if isinstance(item, dict) and str(item.get("event_type") or "").strip() == "user_feedback_appended"
        ]
        recent_events = []
        for item in mission_events[-5:]:
            event_payload = dict(item.get("payload") or {})
            recent_events.append(
                {
                    "event_id": str(item.get("event_id") or "").strip(),
                    "feedback": str(event_payload.get("feedback") or "").strip(),
                    "recorded_at": str(event_payload.get("recorded_at") or item.get("created_at") or "").strip(),
                }
            )
        session_items = [
            dict(item)
            for item in shared_state.get("user_feedback_items") or []
            if isinstance(item, dict)
        ]
        latest_feedback = str(
            shared_state.get("latest_user_feedback")
            or mission_metadata.get("latest_user_feedback")
            or (recent_events[-1].get("feedback") if recent_events else "")
            or ""
        ).strip()
        latest_recorded_at = str(
            shared_state.get("latest_user_feedback_at")
            or mission_metadata.get("latest_user_feedback_at")
            or (recent_events[-1].get("recorded_at") if recent_events else "")
            or ""
        ).strip()
        count = max(
            int(shared_state.get("user_feedback_count") or 0),
            int(mission_metadata.get("user_feedback_count") or 0),
            len(recent_events),
            len(session_items),
        )
        return {
            "count": count,
            "latest_feedback": latest_feedback,
            "latest_recorded_at": latest_recorded_at,
            "recent_items": recent_events or session_items[-5:],
            "session_routed": bool(session_items or shared_state.get("latest_user_feedback")),
        }

    @staticmethod
    def _contracts_from_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        metadata = dict(payload.get("metadata") or {})
        spec_payload = dict(metadata.get("spec") or {})
        spec_metadata = dict(spec_payload.get("metadata") or {})
        planning = dict(metadata.get("planning_contract") or spec_metadata.get("planning_contract") or {})
        evaluation = dict(metadata.get("evaluation_contract") or spec_metadata.get("evaluation_contract") or {})
        governance = dict(metadata.get("governance_contract") or spec_metadata.get("governance_contract") or {})
        return planning, evaluation, governance

    @staticmethod
    def _infer_mode_id_from_payload(payload: dict[str, Any]) -> str:
        metadata = dict(payload.get("metadata") or {})
        spec_payload = dict(metadata.get("spec") or {})
        spec_metadata = dict(spec_payload.get("metadata") or {})
        template_contract = dict(metadata.get("template_contract") or spec_metadata.get("template_contract") or {})
        template_origin = str(
            template_contract.get("template_origin")
            or spec_payload.get("template_origin")
            or spec_metadata.get("template_origin")
            or ""
        ).strip()
        if template_origin == "campaign.research_then_implement":
            return "research"
        if template_origin in {"campaign.single_repo_delivery", "campaign.guarded_autonomy"}:
            return "delivery"
        return "unknown"

    @staticmethod
    def _check_lists_from_payload(payload: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
        metadata = dict(payload.get("metadata") or {})
        pending = [str(item).strip() for item in metadata.get("pending_correctness_checks") or [] if str(item).strip()]
        resolved = [str(item).strip() for item in metadata.get("resolved_correctness_checks") or [] if str(item).strip()]
        waived = [str(item).strip() for item in metadata.get("waived_correctness_checks") or [] if str(item).strip()]
        return pending, resolved, waived

    def _build_campaign_status_details(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(payload.get("metadata") or {})
        runtime_payload = dict(metadata.get("campaign_runtime") or {})
        semantics = build_campaign_semantics(payload)
        return {
            "bundle_root": str(metadata.get("bundle_root") or "").strip(),
            "bundle_manifest": str(metadata.get("bundle_manifest") or "").strip(),
            "runtime_mode": str(runtime_payload.get("mode") or "").strip() or "deterministic",
            "pending_checks": list(semantics.get("pending_checks") or []),
            "resolved_checks": list(semantics.get("resolved_checks") or []),
            "waived_checks": list(semantics.get("waived_checks") or []),
            "operational_checks_pending": list(semantics.get("operational_checks_pending") or []),
            "closure_checks_pending": list(semantics.get("closure_checks_pending") or []),
            "execution_state": str(semantics.get("execution_state") or "").strip(),
            "closure_state": str(semantics.get("closure_state") or "").strip(),
            "progress_reason": str(semantics.get("progress_reason") or "").strip(),
            "closure_reason": str(semantics.get("closure_reason") or "").strip(),
            "latest_stage_summary": str(semantics.get("latest_stage_summary") or "").strip(),
            "stage_artifact_refs": list(semantics.get("stage_artifact_refs") or []),
            "acceptance_requirements_remaining": list(semantics.get("acceptance_requirements_remaining") or []),
            "operator_next_action": str(semantics.get("operator_next_action") or "").strip(),
            "latest_acceptance_decision": str(semantics.get("latest_acceptance_decision") or "").strip(),
            "latest_acceptance_blockers": list(semantics.get("latest_acceptance_blockers") or []),
            "not_done_reason": str(semantics.get("not_done_reason") or "").strip(),
            "canonical_session_id": str(
                payload.get("canonical_session_id")
                or metadata.get("canonical_session_id")
                or dict(metadata.get("control_plane_refs") or {}).get("canonical_session_id")
                or payload.get("supervisor_session_id")
                or ""
            ).strip(),
        }

    def _build_campaign_planning_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        planning, _, _ = self._contracts_from_payload(payload)
        mode_id = str(planning.get("mode_id") or "").strip() or self._infer_mode_id_from_payload(payload)
        return {
            "mode_id": mode_id,
            "method_profile_id": str(planning.get("method_profile_id") or "").strip(),
            "plan_only": bool(planning.get("plan_only")),
            "draft_ref": str(planning.get("draft_ref") or "").strip(),
            "spec_ref": str(planning.get("spec_ref") or "").strip(),
            "plan_ref": str(planning.get("plan_ref") or "").strip(),
            "progress_ref": str(planning.get("progress_ref") or "").strip(),
        }

    def _build_campaign_evaluation_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        _, evaluation, _ = self._contracts_from_payload(payload)
        verdict_summary = dict(payload.get("verdict_summary") or {})
        return {
            "review_ref": str(evaluation.get("review_ref") or "").strip(),
            "latest_review_decision": str(
                evaluation.get("latest_review_decision") or verdict_summary.get("latest_decision") or ""
            ).strip(),
            "latest_acceptance_decision": str(
                evaluation.get("latest_acceptance_decision") or verdict_summary.get("latest_decision") or ""
            ).strip(),
            "review_count": int(verdict_summary.get("count") or 0),
        }

    def _build_campaign_governance_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        _, _, governance = self._contracts_from_payload(payload)
        return {
            "autonomy_profile": str(governance.get("autonomy_profile") or "reviewed_delivery").strip() or "reviewed_delivery",
            "risk_level": str(governance.get("risk_level") or "medium").strip() or "medium",
            "approval_state": str(governance.get("approval_state") or "none").strip() or "none",
        }

    def _build_campaign_task_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(payload.get("metadata") or {})
        structured = dict(metadata.get("task_summary") or {})
        if structured:
            return structured
        planning = self._build_campaign_planning_summary(payload)
        governance = self._build_campaign_governance_summary(payload)
        verdict_summary = dict(payload.get("verdict_summary") or {})
        user_feedback = dict(payload.get("user_feedback") or {})
        semantics = build_campaign_semantics(payload)
        pending_checks = list(semantics.get("pending_checks") or [])
        resolved_checks = list(semantics.get("resolved_checks") or [])
        waived_checks = list(semantics.get("waived_checks") or [])
        artifact_count = len(payload.get("artifacts") or [])
        current_phase = str(payload.get("current_phase") or "").strip()
        next_phase = str(payload.get("next_phase") or "").strip()
        latest_feedback = str(user_feedback.get("latest_feedback") or "").strip()
        runtime_mode = str(payload.get("runtime_mode") or "").strip() or "deterministic"
        latest_acceptance_decision = str(payload.get("latest_acceptance_decision") or "").strip()
        latest_implement_artifact = dict((payload.get("metadata") or {}).get("latest_implement_artifact") or {})
        next_action = str(semantics.get("operator_next_action") or "").strip()
        if not next_action:
            next_action = str(latest_implement_artifact.get("next_action") or "").strip()
        if not next_action:
            if governance.get("approval_state") == "requested":
                next_action = "resolve pending approval"
            elif semantics.get("acceptance_requirements_remaining"):
                next_action = "close acceptance requirements before final closure"
            elif semantics.get("closure_reason"):
                next_action = str(semantics.get("closure_reason") or "").strip()
            elif payload.get("status") == "active":
                next_action = f"advance {next_phase or current_phase or 'campaign'}"
            elif latest_feedback:
                next_action = f"absorb feedback: {latest_feedback[:80]}"
            else:
                next_action = "review current campaign snapshot"
        return {
            "mode_id": planning.get("mode_id"),
            "spec": {
                "goal": str(payload.get("top_level_goal") or "").strip(),
                "campaign_title": str(payload.get("campaign_title") or "").strip(),
                "materials": list(payload.get("materials") or []),
                "hard_constraints": list(payload.get("hard_constraints") or []),
            },
            "plan": {
                "template_origin": str(
                    dict(payload.get("metadata") or {}).get("template_contract", {}).get("template_origin")
                    or dict(payload.get("metadata") or {}).get("spec", {}).get("metadata", {}).get("template_origin")
                    or ""
                ).strip(),
                "method_profile_id": planning.get("method_profile_id"),
                "current_phase": current_phase,
                "next_phase": next_phase,
                "plan_only": bool(planning.get("plan_only")),
            },
            "progress": {
                "status": str(payload.get("status") or "").strip(),
                "execution_state": str(semantics.get("execution_state") or "").strip(),
                "closure_state": str(semantics.get("closure_state") or "").strip(),
                "current_iteration": int(payload.get("current_iteration") or 0),
                "artifact_count": artifact_count,
                "verdict_count": int(verdict_summary.get("count") or 0),
                "user_feedback_count": int(user_feedback.get("count") or 0),
                "runtime_mode": runtime_mode,
                "pending_check_count": len(pending_checks),
                "resolved_check_count": len(resolved_checks),
                "waived_check_count": len(waived_checks),
                "operational_check_count": len(semantics.get("operational_checks_pending") or []),
                "closure_check_count": len(semantics.get("closure_checks_pending") or []),
                "progress_reason": str(semantics.get("progress_reason") or "").strip(),
                "latest_stage_summary": str(semantics.get("latest_stage_summary") or "").strip(),
            },
            "next_action": next_action,
            "operator_next_action": next_action,
            "risk": {
                "risk_level": governance.get("risk_level"),
                "approval_state": governance.get("approval_state"),
                "risk_register": list(dict(payload.get("working_contract") or {}).get("risk_register") or [])[:5],
            },
            "output": {
                "bundle_root": str(payload.get("bundle_root") or "").strip(),
                "bundle_manifest": str(payload.get("bundle_manifest") or "").strip(),
            },
            "closure": {
                "closure_state": str(semantics.get("closure_state") or "").strip(),
                "execution_state": str(semantics.get("execution_state") or "").strip(),
                "progress_reason": str(semantics.get("progress_reason") or "").strip(),
                "closure_reason": str(semantics.get("closure_reason") or "").strip(),
                "latest_acceptance_decision": latest_acceptance_decision,
                "not_done_reason": str(semantics.get("not_done_reason") or "").strip(),
                "pending_checks": pending_checks,
                "resolved_checks": resolved_checks,
                "waived_checks": waived_checks,
                "operational_checks_pending": list(semantics.get("operational_checks_pending") or []),
                "closure_checks_pending": list(semantics.get("closure_checks_pending") or []),
                "acceptance_requirements_remaining": list(semantics.get("acceptance_requirements_remaining") or []),
                "stage_artifact_refs": list(semantics.get("stage_artifact_refs") or []),
            },
        }

    @staticmethod
    def _read_json_dict(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _annotate_mission_payload(payload: dict | object) -> dict:
        mission_payload = dict(payload) if isinstance(payload, dict) else {}
        mission_payload["mission_view"] = build_mission_view(mission_payload)
        return mission_payload

    @staticmethod
    def _annotate_branch_payload(payload: dict | object) -> dict:
        branch_payload = dict(payload) if isinstance(payload, dict) else {}
        branch_payload["branch_view"] = build_branch_view(branch_payload)
        return branch_payload

    def _annotate_campaign_payload(self, workspace: str, payload: dict | object) -> dict:
        campaign_payload = dict(payload) if isinstance(payload, dict) else {}
        campaign_id = str(campaign_payload.get("campaign_id") or "").strip()
        artifact_count = 0
        if campaign_id:
            try:
                artifact_count = len(self._campaign_service.list_campaign_artifacts(workspace, campaign_id))
            except Exception:
                artifact_count = 0
        metadata = dict(campaign_payload.get("metadata") or {})
        campaign_payload["canonical_session_id"] = str(
            campaign_payload.get("canonical_session_id")
            or metadata.get("canonical_session_id")
            or dict(metadata.get("control_plane_refs") or {}).get("canonical_session_id")
            or campaign_payload.get("supervisor_session_id")
            or ""
        ).strip()
        campaign_payload["task_summary"] = dict(metadata.get("task_summary") or {})
        campaign_payload["campaign_view"] = build_campaign_view(
            {
                **campaign_payload,
                "artifact_count": artifact_count,
            }
        )
        return campaign_payload


__all__ = ["OrchestratorQueryService"]
