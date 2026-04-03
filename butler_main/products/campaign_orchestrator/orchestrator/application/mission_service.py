from __future__ import annotations
from datetime import UTC, datetime
from typing import Any

from butler_main.runtime_os.process_runtime import (
    ProcessExecutionOutcome,
    ProcessWritebackProjection,
    RuntimeVerdict,
    WorkflowFactory,
)

from ..branch_store import FileBranchStore
from ..compiler import MissionWorkflowCompiler
from ..event_store import FileLedgerEventStore
from ..judge_adapter import OrchestratorJudgeAdapter
from ..mission_store import FileMissionStore
from ..models import (
    Branch,
    LedgerEvent,
    Mission,
    MissionNode,
    normalize_branch_status,
    normalize_mission_status,
    normalize_node_status,
)
from ..policy import OrchestratorPolicy
from ..runtime_bridge.governance_bridge import OrchestratorGovernanceBridge
from ..runtime_bridge.workflow_session_bridge import OrchestratorWorkflowSessionBridge
from ..scheduler import OrchestratorScheduler
from ..workflow_ir import WorkflowIR


__all__ = ["OrchestratorService"]


_CLOSURE_REQUIRED_EVENT_TYPES = {
    "workflow_ir_compiled",
    "workflow_vm_executed",
}
_CLOSURE_GOVERNANCE_EVENT_TYPES = {
    "approval_requested",
    "approval_resolved",
    "verification_skipped",
    "judge_verdict",
    "recovery_scheduled",
    "recovery_skipped",
    "repair_exhausted",
}
_WORKFLOW_PACKAGE_REF_KEYS = (
    "capability_package_ref",
    "team_package_ref",
    "governance_policy_ref",
)


class OrchestratorService:
    def __init__(
        self,
        mission_store: FileMissionStore,
        event_store: FileLedgerEventStore,
        branch_store: FileBranchStore | None = None,
        *,
        scheduler: OrchestratorScheduler | None = None,
        judge: OrchestratorJudgeAdapter | None = None,
        policy: OrchestratorPolicy | None = None,
        workflow_factory: WorkflowFactory | None = None,
        workflow_compiler: MissionWorkflowCompiler | None = None,
        now_factory=None,
    ) -> None:
        self._mission_store = mission_store
        self._event_store = event_store
        self._branch_store = branch_store or FileBranchStore(self._mission_store.root)
        self._scheduler = scheduler or OrchestratorScheduler()
        self._judge = judge or OrchestratorJudgeAdapter()
        self._policy = policy or OrchestratorPolicy()
        self._workflow_factory = workflow_factory or WorkflowFactory(self._mission_store.root / "workflow_sessions")
        self._workflow_compiler = workflow_compiler or MissionWorkflowCompiler()
        self._now_factory = now_factory or (lambda: datetime.now(UTC).isoformat(timespec="seconds"))
        self._workflow_session_bridge = OrchestratorWorkflowSessionBridge(
            workflow_factory=self._workflow_factory,
            event_store=self._event_store,
            now_factory=self._now_text,
        )
        self._governance_bridge = OrchestratorGovernanceBridge(
            event_store=self._event_store,
            mission_store=self._mission_store,
            judge=self._judge,
            policy=self._policy,
            workflow_session_bridge=self._workflow_session_bridge,
            now_factory=self._now_text,
        )

    def create_mission(
        self,
        *,
        mission_type: str,
        title: str,
        goal: str = "",
        inputs: dict[str, Any] | None = None,
        success_criteria: list[str] | None = None,
        constraints: dict[str, Any] | None = None,
        nodes: list[MissionNode | dict[str, Any]] | None = None,
        priority: int = 50,
        metadata: dict[str, Any] | None = None,
        initial_status: str = "ready",
        activate_on_create: bool = True,
    ) -> Mission:
        mission_status = normalize_mission_status(initial_status, default="ready")
        mission = Mission(
            mission_type=str(mission_type or "generic").strip() or "generic",
            title=str(title or "").strip(),
            goal=str(goal or "").strip(),
            status=mission_status,
            priority=priority,
            inputs=dict(inputs or {}),
            success_criteria=list(success_criteria or []),
            constraints=dict(constraints or {}),
            nodes=[
                item if isinstance(item, MissionNode) else MissionNode.from_dict(item)
                for item in (nodes or [])
            ],
            metadata=dict(metadata or {}),
        )
        activated: list[str] = []
        if activate_on_create and normalize_mission_status(mission.status) not in {
            "completed",
            "failed",
            "cancelled",
            "parked",
            "awaiting_decision",
        }:
            activated = self._scheduler.activate_ready_nodes(mission)
        mission.updated_at = self._now_text()
        self._mission_store.save(mission)
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                event_type="mission_created",
                payload={
                    "mission_type": mission.mission_type,
                    "activated_node_ids": activated,
                    "node_count": len(mission.nodes),
                },
            )
        )
        return mission

    def get_mission(self, mission_id: str) -> Mission | None:
        return self._mission_store.get(mission_id)

    def list_missions(self) -> list[Mission]:
        return self._mission_store.list_missions()

    def get_branch(self, branch_id: str) -> Branch | None:
        return self._branch_store.get(branch_id)

    def list_branches(self, *, mission_id: str = "", node_id: str = "") -> list[Branch]:
        return self._branch_store.list_branches(mission_id=mission_id, node_id=node_id)

    def list_mission_overview(self, *, status: str = "", limit: int = 0) -> list[dict[str, Any]]:
        target_status = str(status or "").strip()
        items: list[dict[str, Any]] = []
        for mission in self._mission_store.list_missions():
            if target_status and normalize_mission_status(mission.status) != target_status:
                continue
            items.append(self._mission_overview(mission))
        items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        if int(limit or 0) > 0:
            return items[: int(limit)]
        return items

    def list_active_branches(self, *, mission_id: str = "", limit: int = 0) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for branch in self._branch_store.list_branches(mission_id=mission_id):
            if normalize_branch_status(branch.status) not in {"queued", "leased", "running"}:
                continue
            payload = self._branch_summary(branch)
            payload["runtime_debug"] = self._branch_runtime_debug(branch)
            items.append(payload)
        items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        if int(limit or 0) > 0:
            return items[: int(limit)]
        return items

    def summarize_branch(self, branch_id: str) -> dict[str, Any]:
        branch = self._branch_store.get(branch_id)
        if branch is None:
            raise KeyError(f"branch not found: {branch_id}")
        mission = self._require_mission(branch.mission_id)
        node = mission.node_by_id(branch.node_id)
        payload = self._branch_summary(branch)
        payload["runtime_debug"] = self._branch_runtime_debug(branch)
        payload["mission"] = {
            "mission_id": mission.mission_id,
            "title": mission.title,
            "status": mission.status,
            "current_iteration": mission.current_iteration,
        }
        if node is not None:
            payload["node"] = {
                "node_id": node.node_id,
                "title": node.title,
                "kind": node.kind,
                "status": node.status,
                "metadata": dict(node.metadata or {}),
            }
        payload["events"] = self.list_recent_events(
            mission_id=mission.mission_id,
            node_id=branch.node_id,
            branch_id=branch.branch_id,
            limit=20,
        )
        return payload

    def summarize_workflow_session(self, session_id: str) -> dict[str, Any]:
        return self._workflow_session_bridge.summarize_workflow_session(session_id)

    def summarize_mission(self, mission_id: str) -> dict[str, Any]:
        mission = self._require_mission(mission_id)
        nodes = [self._node_summary(node) for node in mission.nodes]
        branches = [
            self._branch_summary(branch)
            for branch in self._branch_store.list_branches(mission_id=mission.mission_id)
        ]
        return {
            "mission_id": mission.mission_id,
            "mission_type": mission.mission_type,
            "title": mission.title,
            "goal": mission.goal,
            "status": mission.status,
            "current_iteration": mission.current_iteration,
            "nodes": nodes,
            "branches": branches,
            "delivery_events": [event.to_dict() for event in self._event_store.list_events(mission_id=mission.mission_id)],
        }

    def append_user_feedback(self, mission_id: str, feedback: str) -> dict[str, Any]:
        mission = self._require_mission(mission_id)
        feedback_text = str(feedback or "").strip()
        recorded_at = self._now_text()
        event = LedgerEvent(
            mission_id=mission.mission_id,
            event_type="user_feedback_appended",
            payload={"feedback": feedback_text, "recorded_at": recorded_at},
        )
        self._event_store.append(event)
        mission.metadata = dict(mission.metadata or {})
        feedback_item = {
            "event_id": event.event_id,
            "feedback": feedback_text,
            "recorded_at": recorded_at,
        }
        feedback_history = self._normalize_feedback_history(mission.metadata.get("user_feedback_items"))
        if feedback_text:
            feedback_history.append(feedback_item)
        feedback_history = feedback_history[-10:]
        if feedback_history:
            mission.metadata["latest_user_feedback"] = feedback_history[-1]["feedback"]
            mission.metadata["latest_user_feedback_at"] = feedback_history[-1]["recorded_at"]
            mission.metadata["user_feedback_count"] = len(feedback_history)
            mission.metadata["user_feedback_items"] = feedback_history
        routed_targets: list[dict[str, Any]] = []
        for node in self._feedback_target_nodes(mission):
            routed = self._workflow_session_bridge.append_user_feedback(
                mission=mission,
                node=node,
                feedback=feedback_text,
                event_id=event.event_id,
                recorded_at=recorded_at,
            )
            if routed is not None:
                routed_targets.append(dict(routed))
        if routed_targets:
            mission.metadata["last_feedback_routed_targets"] = routed_targets
            mission.metadata["last_feedback_event_id"] = event.event_id
        mission.updated_at = recorded_at
        self._mission_store.save(mission)
        return {
            "ok": True,
            "mission_id": mission.mission_id,
            "event_id": event.event_id,
            "routed_target_count": len(routed_targets),
            "workflow_sessions": [
                str(item.get("workflow_session_id") or "").strip()
                for item in routed_targets
                if str(item.get("workflow_session_id") or "").strip()
            ],
        }

    def control_mission(self, mission_id: str, action: str) -> dict[str, Any]:
        mission = self._require_mission(mission_id)
        normalized = str(action or "").strip().lower()
        if normalized == "pause":
            mission.status = "parked"
        elif normalized == "resume":
            mission.status = "running" if mission.nodes else "ready"
        elif normalized == "cancel":
            mission.status = "cancelled"
        else:
            raise ValueError(f"unsupported action: {action}")
        mission.updated_at = self._now_text()
        self._mission_store.save(mission)
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                event_type="mission_controlled",
                payload={"action": normalized, "status": mission.status},
            )
        )
        return {"ok": True, "mission_id": mission.mission_id, "status": mission.status}

    def list_delivery_events(self, mission_id: str) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._event_store.list_events(mission_id=mission_id)]

    def list_recent_events(
        self,
        *,
        mission_id: str = "",
        node_id: str = "",
        branch_id: str = "",
        event_type: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        target_node_id = str(node_id or "").strip()
        target_branch_id = str(branch_id or "").strip()
        items: list[dict[str, Any]] = []
        for event in self._event_store.list_events(mission_id=mission_id, event_type=event_type):
            if target_node_id and str(event.node_id or "").strip() != target_node_id:
                continue
            if target_branch_id and str(event.branch_id or "").strip() != target_branch_id:
                continue
            items.append(event.to_dict())
        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        if int(limit or 0) > 0:
            return items[: int(limit)]
        return items

    def build_observation_window(
        self,
        *,
        mission_limit: int = 8,
        branch_limit: int = 8,
        event_limit: int = 20,
    ) -> dict[str, Any]:
        missions = self.list_mission_overview(limit=mission_limit)
        active_branches = self.list_active_branches(limit=branch_limit)
        recent_events = self.list_recent_events(limit=event_limit)
        return {
            "missions": missions,
            "active_branches": active_branches,
            "recent_events": recent_events,
            "closure_signals": self._build_closure_signals(
                missions=missions,
                recent_events=self.list_recent_events(limit=max(event_limit, 50)),
            ),
        }

    def dispatch_ready_nodes(self, mission_id: str, *, limit: int = 0) -> list[dict[str, Any]]:
        mission = self._require_mission(mission_id)
        ready_nodes = [node for node in mission.nodes if normalize_node_status(node.status) == "ready"]
        if int(limit or 0) > 0:
            ready_nodes = ready_nodes[: int(limit)]
        dispatched: list[dict[str, Any]] = []
        for node in ready_nodes:
            allowed, reason = self._branch_budget_allows(mission, node)
            if not allowed:
                self._event_store.append(
                    LedgerEvent(
                        mission_id=mission.mission_id,
                        node_id=node.node_id,
                        event_type="dispatch_skipped_policy",
                        payload={"reason": reason},
                    )
                )
                continue
            branch_input_payload = {"mission_id": mission.mission_id, "node_id": node.node_id, "kind": node.kind}
            branch = Branch(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                status="running",
                worker_profile=str((node.runtime_plan or {}).get("worker_profile") or "").strip(),
                input_payload=branch_input_payload,
                metadata={"node_title": node.title},
            )
            workflow_ir = self._workflow_compiler.compile(mission=mission, node=node, branch=branch)
            try:
                workflow_session, session_reused = self._prepare_branch_workflow_session(
                    mission=mission,
                    node=node,
                    branch=branch,
                    workflow_ir=workflow_ir,
                )
            except Exception as exc:
                self._event_store.append(
                    LedgerEvent(
                        mission_id=mission.mission_id,
                        node_id=node.node_id,
                        branch_id=branch.branch_id,
                        event_type="workflow_session_failed",
                        payload={"error": f"{type(exc).__name__}: {exc}"},
                    )
                )
                continue
            workflow_ir = self._workflow_session_bridge.bind_dispatched_branch_workflow_session(
                mission=mission,
                node=node,
                branch=branch,
                workflow_ir=workflow_ir,
                workflow_session=workflow_session,
                session_reused=session_reused,
            )
            branch.worker_profile = workflow_ir.worker_profile or branch.worker_profile
            branch.input_payload["workflow_id"] = workflow_ir.workflow_id
            branch.metadata["workflow_ir"] = workflow_ir.to_dict()
            node.metadata["workflow_ir_summary"] = workflow_ir.summary()
            self._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    event_type="workflow_ir_compiled",
                    payload=workflow_ir.summary(),
                )
            )
            research_refs = self._extract_branch_reference_fields(
                runtime_plan=workflow_ir.to_runtime_plan_payload(),
                node_metadata=node.metadata,
                keys=("subworkflow_kind", "research_unit_id", "scenario_action"),
            )
            for key, value in research_refs.items():
                branch.input_payload[key] = value
                branch.metadata[key] = value
                node.metadata[key] = value
            recovery_action = str(node.metadata.get("recovery_action") or "").strip()
            recovery_resume_from = str(node.metadata.get("recovery_resume_from") or "").strip()
            if recovery_action:
                branch.input_payload["recovery_action"] = recovery_action
                branch.metadata["recovery_action"] = recovery_action
            if recovery_resume_from:
                branch.input_payload["resume_from"] = recovery_resume_from
                branch.metadata["resume_from"] = recovery_resume_from
            workflow_inputs = self._extract_branch_workflow_inputs(
                runtime_plan=workflow_ir.to_runtime_plan_payload(),
                node_metadata=node.metadata,
            )
            if workflow_inputs:
                branch.input_payload["workflow_inputs"] = workflow_inputs
            self._refresh_branch_workflow_session_metadata(branch=branch, node=node)
            self._branch_store.save(branch)
            node.status = "running"
            dispatched.append(branch.to_dict())
            self._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    event_type="branch_dispatched",
                    payload={"worker_profile": branch.worker_profile, "node_kind": node.kind},
                )
            )
        if dispatched:
            mission.status = "running"
            mission.updated_at = self._now_text()
            self._mission_store.save(mission)
        return dispatched

    def record_branch_result(
        self,
        mission_id: str,
        branch_id: str,
        *,
        ok: bool | None = None,
        result_ref: str = "",
        result_payload: dict[str, Any] | None = None,
        process_outcome: ProcessExecutionOutcome | dict[str, Any] | None = None,
        runtime_verdict: RuntimeVerdict | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        mission = self._require_mission(mission_id)
        branch = self._branch_store.get(branch_id)
        if branch is None or branch.mission_id != mission.mission_id:
            raise KeyError(f"branch not found: {branch_id}")
        node = mission.node_by_id(branch.node_id)
        if node is None:
            raise KeyError(f"node not found for branch: {branch.node_id}")

        process_result = self._coerce_process_execution_outcome(
            process_outcome=process_outcome,
            runtime_verdict=runtime_verdict,
            ok=ok,
            result_ref=result_ref,
            result_payload=result_payload,
        )
        verdict = process_result.to_runtime_verdict()
        branch.status = "succeeded" if verdict.ok else "failed"
        branch.result_ref = verdict.result_ref
        branch.metadata["result_payload"] = dict(verdict.result_payload or {})
        branch.metadata["process_outcome"] = process_result.to_dict()
        branch.updated_at = self._now_text()

        mission.current_iteration += 1
        governance = self._governance_bridge.handle_branch_completion(
            mission=mission,
            node=node,
            branch=branch,
            ok=verdict.ok,
            result_ref=branch.result_ref,
            result_payload=verdict.result_payload,
            runtime_verdict=verdict,
        )

        self._refresh_mission_terminal_state(mission)
        session_summary = self._refresh_branch_workflow_session_metadata(branch=branch, node=node)
        projection = ProcessWritebackProjection.from_runtime_state(
            verdict=verdict,
            branch_status=branch.status,
            node_status=node.status,
            mission_status=mission.status,
            workflow_session_status=str((session_summary or {}).get("status") or "").strip(),
            metadata={"governance_writeback_status": governance.writeback_status},
        )
        final_verdict = projection.apply_to_runtime_verdict(verdict)
        branch.metadata["runtime_verdict"] = final_verdict.to_dict()
        branch.metadata["process_writeback"] = projection.to_dict()
        self._branch_store.save(branch)
        mission.updated_at = self._now_text()
        self._mission_store.save(mission)
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                branch_id=branch.branch_id,
                event_type="branch_completed",
                payload={
                    "ok": final_verdict.ok,
                    "result_ref": branch.result_ref,
                    "result_payload": dict(verdict.result_payload or {}),
                    "runtime_verdict": final_verdict.to_dict(),
                    "process_outcome": process_result.to_dict(),
                    "process_writeback": projection.to_dict(),
                },
            )
        )
        out: dict[str, Any] = {
            "ok": True,
            "mission_id": mission.mission_id,
            "branch_id": branch.branch_id,
            "node_status": node.status,
            "mission_status": mission.status,
            "process_outcome": process_result.to_dict(),
            "process_writeback": projection.to_dict(),
            "runtime_verdict": final_verdict.to_dict(),
        }
        if governance.judge_decision:
            out["judge_decision"] = governance.judge_decision
        return out

    def resolve_node_approval(
        self,
        mission_id: str,
        node_id: str,
        *,
        decision: str,
        note: str = "",
    ) -> dict[str, Any]:
        mission = self._require_mission(mission_id)
        node = mission.node_by_id(node_id)
        if node is None:
            raise KeyError(f"node not found: {node_id}")
        branch_id = str(node.metadata.get("approval_branch_id") or "").strip()
        if not bool(node.metadata.get("approval_pending")) or not branch_id:
            raise ValueError(f"node is not awaiting approval: {node_id}")
        branch = self._branch_store.get(branch_id)
        if branch is None or branch.mission_id != mission.mission_id:
            raise KeyError(f"branch not found for approval: {branch_id}")
        resolution = self._governance_bridge.resolve_node_approval(
            mission=mission,
            node=node,
            branch=branch,
            decision=decision,
            note=note,
        )
        mission.updated_at = self._now_text()
        self._refresh_branch_workflow_session_metadata(branch=branch, node=node)
        self._branch_store.save(branch)
        self._mission_store.save(mission)
        self._refresh_mission_terminal_state(mission)
        out: dict[str, Any] = {
            "ok": True,
            "mission_id": mission.mission_id,
            "node_id": node.node_id,
            "branch_id": branch.branch_id,
            "decision": resolution.decision,
            "node_status": node.status,
            "mission_status": mission.status,
        }
        if resolution.judge_decision:
            out["judge_decision"] = resolution.judge_decision
        return out

    def tick(self, mission_id: str = "") -> dict[str, Any]:
        missions = [self._require_mission(mission_id)] if str(mission_id or "").strip() else self._mission_store.list_missions()
        activated_total = 0
        touched_missions: list[str] = []
        for mission in missions:
            if normalize_mission_status(mission.status) in {"completed", "failed", "cancelled", "parked", "awaiting_decision"}:
                continue
            activated = self._scheduler.activate_ready_nodes(mission)
            if activated:
                mission.status = "running"
                mission.updated_at = self._now_text()
                self._mission_store.save(mission)
                activated_total += len(activated)
                touched_missions.append(mission.mission_id)
                self._event_store.append(
                    LedgerEvent(
                        mission_id=mission.mission_id,
                        event_type="nodes_activated",
                        payload={"node_ids": activated},
                    )
                )
            self._refresh_mission_terminal_state(mission)
        return {
            "ok": True,
            "mission_count": len(missions),
            "activated_node_count": activated_total,
            "touched_mission_ids": touched_missions,
        }

    def _require_mission(self, mission_id: str) -> Mission:
        target_mission_id = str(mission_id or "").strip()
        mission = None
        if target_mission_id:
            mission = self._mission_store.get(target_mission_id)
        else:
            missions = self._mission_store.list_missions()
            if len(missions) == 1:
                mission = missions[0]
        if mission is None:
            raise KeyError(f"mission not found: {mission_id}")
        return mission

    def _now_text(self) -> str:
        return str(self._now_factory() or "").strip()

    @staticmethod
    def _coerce_runtime_verdict(
        *,
        runtime_verdict: RuntimeVerdict | dict[str, Any] | None,
        ok: bool | None,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> RuntimeVerdict:
        if isinstance(runtime_verdict, RuntimeVerdict):
            return runtime_verdict
        if isinstance(runtime_verdict, dict):
            return RuntimeVerdict.from_dict(runtime_verdict)
        if ok is None:
            raise ValueError("record_branch_result requires ok or runtime_verdict")
        return RuntimeVerdict.from_legacy(
            ok=bool(ok),
            result_ref=result_ref,
            result_payload=result_payload,
        )

    @staticmethod
    def _coerce_process_execution_outcome(
        *,
        process_outcome: ProcessExecutionOutcome | dict[str, Any] | None,
        runtime_verdict: RuntimeVerdict | dict[str, Any] | None,
        ok: bool | None,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> ProcessExecutionOutcome:
        if isinstance(process_outcome, ProcessExecutionOutcome):
            return process_outcome
        if isinstance(process_outcome, dict):
            return ProcessExecutionOutcome.from_runtime_verdict(process_outcome)
        return ProcessExecutionOutcome.from_runtime_verdict(
            OrchestratorService._coerce_runtime_verdict(
                runtime_verdict=runtime_verdict,
                ok=ok,
                result_ref=result_ref,
                result_payload=result_payload,
            )
        )

    def _branch_budget_allows(self, mission: Mission, node: MissionNode) -> tuple[bool, str]:
        total = len(self._branch_store.list_branches(mission_id=mission.mission_id))
        if total >= self._policy.max_total_branches_per_mission:
            return False, "total_branch_cap"
        active = 0
        for branch in self._branch_store.list_branches(mission_id=mission.mission_id, node_id=node.node_id):
            if normalize_branch_status(branch.status) in {"queued", "leased", "running"}:
                active += 1
        if active >= self._policy.max_parallel_branches_per_node:
            return False, "parallel_node_cap"
        return True, ""

    def _node_summary(self, node: MissionNode) -> dict[str, Any]:
        payload = node.to_dict()
        workflow_session = self._workflow_session_summary(
            str(node.metadata.get("workflow_session_id") or "").strip()
        )
        if workflow_session is not None:
            payload["workflow_session"] = workflow_session
        workflow_ir = self._workflow_ir_summary_from_node(node)
        if workflow_ir is not None:
            payload["workflow_ir"] = workflow_ir
        return payload

    def _branch_summary(self, branch: Branch) -> dict[str, Any]:
        payload = branch.to_dict()
        workflow_session = self._workflow_session_summary(self._workflow_session_id_from_branch(branch))
        if workflow_session is not None:
            payload["workflow_session"] = workflow_session
        workflow_ir = self._workflow_ir_summary_from_branch(branch)
        if workflow_ir is not None:
            payload["workflow_ir"] = workflow_ir
        return payload

    def _mission_overview(self, mission: Mission) -> dict[str, Any]:
        node_status_counts: dict[str, int] = {}
        workflow_session_ids: list[str] = []
        for node in mission.nodes:
            status = normalize_node_status(node.status)
            node_status_counts[status] = node_status_counts.get(status, 0) + 1
            workflow_session_id = str(node.metadata.get("workflow_session_id") or "").strip()
            if workflow_session_id and workflow_session_id not in workflow_session_ids:
                workflow_session_ids.append(workflow_session_id)
        branches = self._branch_store.list_branches(mission_id=mission.mission_id)
        branch_status_counts: dict[str, int] = {}
        active_branch_count = 0
        for branch in branches:
            status = normalize_branch_status(branch.status)
            branch_status_counts[status] = branch_status_counts.get(status, 0) + 1
            if status in {"queued", "leased", "running"}:
                active_branch_count += 1
        recent_events = self.list_recent_events(mission_id=mission.mission_id, limit=3)
        return {
            "mission_id": mission.mission_id,
            "mission_type": mission.mission_type,
            "title": mission.title,
            "status": mission.status,
            "priority": mission.priority,
            "current_iteration": mission.current_iteration,
            "node_count": len(mission.nodes),
            "branch_count": len(branches),
            "active_branch_count": active_branch_count,
            "workflow_session_count": len(workflow_session_ids),
            "node_status_counts": node_status_counts,
            "branch_status_counts": branch_status_counts,
            "created_at": mission.created_at,
            "updated_at": mission.updated_at,
            "recent_event_types": [str(item.get("event_type") or "").strip() for item in recent_events],
        }

    @staticmethod
    def _normalize_feedback_history(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        result: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            feedback = str(item.get("feedback") or "").strip()
            recorded_at = str(item.get("recorded_at") or "").strip()
            event_id = str(item.get("event_id") or "").strip()
            if not feedback and not recorded_at and not event_id:
                continue
            result.append(
                {
                    "event_id": event_id,
                    "feedback": feedback,
                    "recorded_at": recorded_at,
                }
            )
        return result

    @staticmethod
    def _feedback_target_nodes(mission: Mission) -> list[MissionNode]:
        active_statuses = {"running", "blocked", "ready", "repairing", "awaiting_decision", "pending"}
        session_nodes = [
            node
            for node in mission.nodes
            if str(node.metadata.get("workflow_session_id") or "").strip()
        ]
        active_nodes = [
            node
            for node in session_nodes
            if normalize_node_status(node.status) in active_statuses
        ]
        if active_nodes:
            return active_nodes
        return session_nodes[:1]

    def _build_closure_signals(
        self,
        *,
        missions: list[dict[str, Any]],
        recent_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        observed_event_types = {
            str(item.get("event_type") or "").strip()
            for item in recent_events
            if str(item.get("event_type") or "").strip()
        }
        workflow_session_count = sum(int(item.get("workflow_session_count") or 0) for item in missions)
        session_aware_branch_count = 0
        package_bound_branch_count = 0
        execution_boundary_samples: list[dict[str, Any]] = []

        for branch in self._branch_store.list_branches():
            if self._workflow_session_id_from_branch(branch):
                session_aware_branch_count += 1
            workflow_ir = self._workflow_ir_summary_from_branch(branch)
            if workflow_ir is None:
                continue
            if any(str(workflow_ir.get(key) or "").strip() for key in _WORKFLOW_PACKAGE_REF_KEYS):
                package_bound_branch_count += 1
            boundary = workflow_ir.get("execution_boundary")
            if isinstance(boundary, dict) and boundary and len(execution_boundary_samples) < 3:
                execution_boundary_samples.append(dict(boundary))

        return {
            "runtime_namespace": "runtime_os",
            "workflow_ir_compiled_visible": "workflow_ir_compiled" in observed_event_types,
            "workflow_vm_executed_visible": "workflow_vm_executed" in observed_event_types,
            "required_event_types": sorted(_CLOSURE_REQUIRED_EVENT_TYPES),
            "observed_event_types": sorted(observed_event_types),
            "workflow_session_count": workflow_session_count,
            "session_aware_branch_count": session_aware_branch_count,
            "package_binding_visible": package_bound_branch_count > 0,
            "package_bound_branch_count": package_bound_branch_count,
            "governance_event_types_visible": sorted(
                observed_event_types.intersection(_CLOSURE_GOVERNANCE_EVENT_TYPES)
            ),
            "execution_boundary_samples": execution_boundary_samples,
        }

    def _branch_runtime_debug(self, branch: Branch) -> dict[str, Any]:
        branch_metadata = dict(branch.metadata or {})
        runtime_profile = branch_metadata.get("runtime_profile")
        runtime_profile_map = dict(runtime_profile) if isinstance(runtime_profile, dict) else {}
        result_payload = branch_metadata.get("result_payload")
        result_payload_map = dict(result_payload) if isinstance(result_payload, dict) else {}
        result_runtime_debug = result_payload_map.get("runtime_debug")
        result_runtime_map = dict(result_runtime_debug) if isinstance(result_runtime_debug, dict) else {}
        receipt_metadata = result_payload_map.get("metadata")
        receipt_metadata_map = dict(receipt_metadata) if isinstance(receipt_metadata, dict) else {}
        cli = str(result_runtime_map.get("cli") or runtime_profile_map.get("cli") or receipt_metadata_map.get("cli") or "").strip()
        model = str(result_runtime_map.get("model") or runtime_profile_map.get("model") or receipt_metadata_map.get("model") or "").strip()
        reasoning_effort = str(result_runtime_map.get("reasoning_effort") or runtime_profile_map.get("reasoning_effort") or receipt_metadata_map.get("reasoning_effort") or "").strip()
        why = str(result_runtime_map.get("why") or runtime_profile_map.get("why") or receipt_metadata_map.get("why") or "").strip()
        agent_id = str(result_runtime_map.get("agent_id") or result_payload_map.get("agent_id") or receipt_metadata_map.get("agent_id") or "").strip()
        debug = {
            "worker_profile": str(branch.worker_profile or "").strip(),
            "agent_id": agent_id,
            "cli": cli,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "why": why,
            "codex_related": cli == "codex" or "codex" in why.lower() or "codex" in agent_id.lower(),
        }
        if not any(str(value or "").strip() for key, value in debug.items() if key != "codex_related"):
            return {}
        return debug

    def _workflow_session_id_from_branch(self, branch: Branch) -> str:
        return self._workflow_session_bridge.session_id_from_branch(branch)

    def _workflow_session_summary(self, session_id: str) -> dict[str, Any] | None:
        return self._workflow_session_bridge.workflow_session_summary(session_id)

    def _workflow_ir_summary_from_branch(self, branch: Branch) -> dict[str, Any] | None:
        return self._workflow_session_bridge.workflow_ir_summary_from_branch(branch)

    def _workflow_ir_summary_from_node(self, node: MissionNode) -> dict[str, Any] | None:
        return self._workflow_session_bridge.workflow_ir_summary_from_node(node)

    def _prepare_branch_workflow_session(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        workflow_ir: WorkflowIR,
    ):
        return self._workflow_session_bridge.prepare_branch_workflow_session(
            mission=mission,
            node=node,
            branch=branch,
            workflow_ir=workflow_ir,
        )

    def _refresh_branch_workflow_session_metadata(self, *, branch: Branch, node: MissionNode) -> dict[str, Any] | None:
        return self._workflow_session_bridge.refresh_branch_workflow_session_metadata(
            branch=branch,
            node=node,
        )

    @staticmethod
    def _extract_branch_reference_fields(
        *,
        runtime_plan: dict[str, Any] | None,
        node_metadata: dict[str, Any] | None,
        keys: tuple[str, ...],
    ) -> dict[str, str]:
        return OrchestratorWorkflowSessionBridge.extract_branch_reference_fields(
            runtime_plan=runtime_plan,
            node_metadata=node_metadata,
            keys=keys,
        )

    @staticmethod
    def _extract_branch_workflow_inputs(
        *,
        runtime_plan: dict[str, Any] | None,
        node_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return OrchestratorWorkflowSessionBridge.extract_branch_workflow_inputs(
            runtime_plan=runtime_plan,
            node_metadata=node_metadata,
        )

    def _refresh_mission_terminal_state(self, mission: Mission) -> None:
        if normalize_mission_status(mission.status) in {"cancelled", "parked"}:
            return
        if normalize_mission_status(mission.status) == "awaiting_decision":
            return
        statuses = {normalize_node_status(node.status) for node in mission.nodes}
        updated = False
        if "failed" in statuses and mission.status != "failed":
            mission.status = "failed"
            updated = True
        elif mission.nodes and statuses and statuses <= {"done", "skipped"} and mission.status != "completed":
            mission.status = "completed"
            updated = True
        elif (
            "running" in statuses
            or "ready" in statuses
            or "dispatching" in statuses
            or "partial_ready" in statuses
            or "awaiting_judge" in statuses
            or "repairing" in statuses
            or "blocked" in statuses
        ):
            if mission.status not in {"running", "completed"}:
                mission.status = "running"
                updated = True
        if updated:
            mission.updated_at = self._now_text()
            self._mission_store.save(mission)
