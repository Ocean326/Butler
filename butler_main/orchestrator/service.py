from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from butler_main.multi_agents_os.factory import WorkflowFactory
from butler_main.multi_agents_os.session.artifact_registry import ArtifactRegistry
from butler_main.multi_agents_os.session.shared_state import SharedState
from butler_main.multi_agents_os.session.workflow_session import WorkflowSession
from butler_main.multi_agents_os.templates.workflow_template import WorkflowTemplate

from .branch_store import FileBranchStore
from .compiler import MissionWorkflowCompiler
from .event_store import FileLedgerEventStore
from .judge_adapter import JUDGE_DECISIONS, JudgeVerdict, OrchestratorJudgeAdapter
from .mission_store import FileMissionStore
from .models import (
    Branch,
    LedgerEvent,
    Mission,
    MissionNode,
    normalize_branch_status,
    normalize_mission_status,
    normalize_node_status,
)
from .policy import OrchestratorPolicy
from .scheduler import OrchestratorScheduler
from .workflow_ir import WorkflowIR


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
    ) -> Mission:
        mission = Mission(
            mission_type=str(mission_type or "generic").strip() or "generic",
            title=str(title or "").strip(),
            goal=str(goal or "").strip(),
            status="ready",
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
        target = str(session_id or "").strip()
        if not target:
            raise KeyError("workflow session not found: ")
        try:
            bundle = self._workflow_factory.load_session(target)
        except Exception as exc:
            raise KeyError(f"workflow session not found: {session_id}") from exc
        session = bundle.session
        session_root = self._workflow_factory.session_root(session.session_id)
        event_log_path = session_root / (session.event_log_ref or "events.jsonl")
        template = bundle.template
        shared_state = bundle.shared_state
        artifact_registry = bundle.artifact_registry
        collaboration = bundle.collaboration
        step_ids: list[str] = []
        for step in template.steps:
            step_id = str(step.get("step_id") or step.get("id") or "").strip()
            if step_id:
                step_ids.append(step_id)
        refs_by_step = {step_id: list(refs) for step_id, refs in dict(artifact_registry.refs_by_step or {}).items() if step_id}
        return {
            "session_id": session.session_id,
            "template_id": session.template_id,
            "driver_kind": session.driver_kind,
            "status": session.status,
            "active_step": session.active_step,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "session_root": str(session_root),
            "role_bindings": [binding.to_dict() for binding in session.role_bindings],
            "metadata": dict(session.metadata or {}),
            "template": {
                "template_id": template.template_id,
                "kind": template.kind,
                "role_count": len(template.roles),
                "step_count": len(template.steps),
                "step_ids": step_ids,
                "entry_contract": dict(template.entry_contract or {}),
                "exit_contract": dict(template.exit_contract or {}),
                "metadata": dict(template.metadata or {}),
            },
            "shared_state": {
                "state_version": shared_state.state_version,
                "last_updated_at": shared_state.last_updated_at,
                "key_count": len(shared_state.state),
                "keys": sorted(shared_state.state.keys()),
                "state": dict(shared_state.state or {}),
            },
            "artifact_registry": {
                "artifact_count": len(artifact_registry.artifacts),
                "latest_output_keys": sorted(dict(artifact_registry.latest_outputs or {}).keys()),
                "refs_by_step": refs_by_step,
            },
            "collaboration": {
                "mailbox_message_count": len(collaboration.mailbox_messages),
                "queued_mailbox_message_count": len([item for item in collaboration.mailbox_messages if item.status == "queued"]),
                "owned_step_ids": sorted(collaboration.step_ownerships.keys()),
                "join_contract_count": len(collaboration.join_contracts),
                "open_join_contract_count": len([item for item in collaboration.join_contracts if item.status == "open"]),
                "handoff_count": len(collaboration.handoffs),
                "last_updated_at": collaboration.last_updated_at,
            },
            "event_log": {
                "path": str(event_log_path),
                "exists": event_log_path.exists(),
                "line_count": self._line_count(event_log_path),
            },
        }

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
        event = LedgerEvent(
            mission_id=mission.mission_id,
            event_type="user_feedback_appended",
            payload={"feedback": str(feedback or "").strip()},
        )
        self._event_store.append(event)
        mission.updated_at = self._now_text()
        self._mission_store.save(mission)
        return {"ok": True, "mission_id": mission.mission_id, "event_id": event.event_id}

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
        return {
            "missions": self.list_mission_overview(limit=mission_limit),
            "active_branches": self.list_active_branches(limit=branch_limit),
            "recent_events": self.list_recent_events(limit=event_limit),
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
            try:
                workflow_session = self._workflow_factory.build_session_from_orchestrator_node(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    node_kind=node.kind,
                    node_title=node.title,
                    runtime_plan=workflow_ir.to_runtime_plan_payload(),
                    node_metadata=node.metadata,
                    mission_metadata=mission.metadata,
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
            if workflow_session is not None:
                branch.input_payload["workflow_session_id"] = workflow_session.session_id
                branch.input_payload["workflow_template_id"] = workflow_session.template_id
                branch.metadata["workflow_session_id"] = workflow_session.session_id
                branch.metadata["workflow_template_id"] = workflow_session.template_id
                node.metadata["workflow_session_id"] = workflow_session.session_id
                node.metadata["workflow_template_id"] = workflow_session.template_id
                node.metadata["workflow_driver_kind"] = workflow_session.driver_kind
                workflow_ir = self._update_compiled_workflow_ir(
                    branch=branch,
                    node=node,
                    workflow_ir=workflow_ir,
                    workflow_session_id=workflow_session.session_id,
                    workflow_template_id=workflow_session.template_id,
                )
                self._event_store.append(
                    LedgerEvent(
                        mission_id=mission.mission_id,
                        node_id=node.node_id,
                        branch_id=branch.branch_id,
                        event_type="workflow_session_created",
                        payload={
                            "workflow_session_id": workflow_session.session_id,
                            "workflow_template_id": workflow_session.template_id,
                            "driver_kind": workflow_session.driver_kind,
                        },
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
            workflow_inputs = self._extract_branch_workflow_inputs(
                runtime_plan=workflow_ir.to_runtime_plan_payload(),
                node_metadata=node.metadata,
            )
            if workflow_inputs:
                branch.input_payload["workflow_inputs"] = workflow_inputs
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
        ok: bool,
        result_ref: str = "",
        result_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        mission = self._require_mission(mission_id)
        branch = self._branch_store.get(branch_id)
        if branch is None or branch.mission_id != mission.mission_id:
            raise KeyError(f"branch not found: {branch_id}")
        node = mission.node_by_id(branch.node_id)
        if node is None:
            raise KeyError(f"node not found for branch: {branch.node_id}")

        branch.status = "succeeded" if ok else "failed"
        branch.result_ref = str(result_ref or "").strip()
        branch.metadata["result_payload"] = dict(result_payload or {})
        branch.updated_at = self._now_text()
        workflow_session_summary = self._finalize_branch_workflow_session(
            mission=mission,
            node=node,
            branch=branch,
            ok=ok,
            result_ref=branch.result_ref,
            result_payload=result_payload,
        )
        if workflow_session_summary is not None:
            branch.metadata["workflow_session_status"] = workflow_session_summary["status"]
            branch.metadata["workflow_session_updated_at"] = workflow_session_summary["updated_at"]
            node.metadata["workflow_session_status"] = workflow_session_summary["status"]
            node.metadata["workflow_session_updated_at"] = workflow_session_summary["updated_at"]
        self._branch_store.save(branch)

        mission.current_iteration += 1
        judge_decision = ""

        if ok:
            artifacts = [{"result_ref": branch.result_ref, "result_payload": dict(result_payload or {})}]
            node.status = "awaiting_judge"
            mission.updated_at = self._now_text()
            self._mission_store.save(mission)
            verdict = self._judge.evaluate_node(mission.mission_id, node.node_id, artifacts)
            judge_decision = self._normalize_judge_decision(verdict.decision)
            self._apply_judge_verdict(mission, node, verdict)
            self._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    event_type="judge_verdict",
                    payload={
                        "decision": judge_decision,
                        "reason": verdict.reason,
                        "metadata": dict(verdict.metadata or {}),
                    },
                )
            )
        else:
            attempts = int(node.metadata.get("repair_attempts", 0) or 0) + 1
            node.metadata["repair_attempts"] = attempts
            if attempts > self._policy.max_repair_attempts_per_node:
                node.status = "failed"
                self._event_store.append(
                    LedgerEvent(
                        mission_id=mission.mission_id,
                        node_id=node.node_id,
                        branch_id=branch.branch_id,
                        event_type="repair_exhausted",
                        payload={"repair_attempts": attempts, "cap": self._policy.max_repair_attempts_per_node},
                    )
                )
            else:
                node.status = "repairing"

        mission.updated_at = self._now_text()
        self._mission_store.save(mission)
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                branch_id=branch.branch_id,
                event_type="branch_completed",
                payload={"ok": ok, "result_ref": branch.result_ref, "result_payload": dict(result_payload or {})},
            )
        )
        self._refresh_mission_terminal_state(mission)
        out: dict[str, Any] = {
            "ok": True,
            "mission_id": mission.mission_id,
            "branch_id": branch.branch_id,
            "node_status": node.status,
            "mission_status": mission.status,
        }
        if judge_decision:
            out["judge_decision"] = judge_decision
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
        mission = self._mission_store.get(mission_id)
        if mission is None:
            raise KeyError(f"mission not found: {mission_id}")
        return mission

    def _now_text(self) -> str:
        return str(self._now_factory() or "").strip()

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

    def _normalize_judge_decision(self, raw: str) -> str:
        decision = str(raw or "").strip().lower()
        if decision in ("", "continue"):
            return "accept"
        return decision if decision in JUDGE_DECISIONS else "accept"

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
        return str(
            branch.input_payload.get("workflow_session_id")
            or branch.metadata.get("workflow_session_id")
            or ""
        ).strip()

    def _workflow_session_summary(self, session_id: str) -> dict[str, Any] | None:
        session = self._load_workflow_session(session_id)
        if session is None:
            return None
        return {
            "session_id": session.session_id,
            "template_id": session.template_id,
            "driver_kind": session.driver_kind,
            "status": session.status,
            "active_step": session.active_step,
            "updated_at": session.updated_at,
        }

    def _workflow_ir_summary_from_branch(self, branch: Branch) -> dict[str, Any] | None:
        payload = branch.metadata.get("workflow_ir")
        if not isinstance(payload, dict) or not payload:
            return None
        return WorkflowIR.from_dict(payload).summary()

    def _workflow_ir_summary_from_node(self, node: MissionNode) -> dict[str, Any] | None:
        payload = node.metadata.get("workflow_ir_summary")
        if isinstance(payload, dict) and payload:
            return dict(payload)
        return None

    def _load_workflow_session(self, session_id: str) -> WorkflowSession | None:
        target = str(session_id or "").strip()
        if not target:
            return None
        path = self._workflow_session_file(target)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return WorkflowSession.from_dict(payload)

    def _save_workflow_session(self, session: WorkflowSession) -> WorkflowSession:
        path = self._workflow_session_file(session.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return session

    def _load_json_dict(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _line_count(self, path: Path) -> int:
        if not path.exists():
            return 0
        try:
            with path.open("r", encoding="utf-8") as handle:
                return sum(1 for _ in handle)
        except Exception:
            return 0

    def _workflow_session_file(self, session_id: str) -> Path:
        return self._workflow_factory.session_root(session_id) / "session.json"

    def _update_compiled_workflow_ir(
        self,
        *,
        branch: Branch,
        node: MissionNode,
        workflow_ir: WorkflowIR,
        workflow_session_id: str,
        workflow_template_id: str,
    ) -> WorkflowIR:
        updated = WorkflowIR.from_dict(workflow_ir.to_dict())
        updated.workflow_session_id = str(workflow_session_id or "").strip()
        updated.workflow_template_id = str(workflow_template_id or "").strip()
        branch.metadata["workflow_ir"] = updated.to_dict()
        node.metadata["workflow_ir_summary"] = updated.summary()
        return updated

    def _finalize_branch_workflow_session(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        ok: bool,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        session_id = self._workflow_session_id_from_branch(branch)
        if not session_id:
            return None
        try:
            session = self._load_workflow_session(session_id)
            if session is None:
                self._event_store.append(
                    LedgerEvent(
                        mission_id=mission.mission_id,
                        node_id=node.node_id,
                        branch_id=branch.branch_id,
                        event_type="workflow_session_missing",
                        payload={"workflow_session_id": session_id},
                    )
                )
                return None
            session.status = "completed" if ok else "failed"
            session.active_step = ""
            session.metadata["mission_id"] = mission.mission_id
            session.metadata["node_id"] = node.node_id
            session.metadata["branch_id"] = branch.branch_id
            session.metadata["orchestrator_result"] = self._workflow_session_result_summary(
                ok=ok,
                branch_status=branch.status,
                result_ref=result_ref,
                result_payload=result_payload,
            )
            session.touch()
            self._save_workflow_session(session)
            self._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    event_type="workflow_session_updated",
                    payload={
                        "workflow_session_id": session.session_id,
                        "workflow_template_id": session.template_id,
                        "status": session.status,
                    },
                )
            )
            return self._workflow_session_summary(session.session_id)
        except Exception as exc:
            self._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    event_type="workflow_session_update_failed",
                    payload={
                        "workflow_session_id": session_id,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
            )
            return None

    def _workflow_session_result_summary(
        self,
        *,
        ok: bool,
        branch_status: str,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = dict(result_payload or {})
        summary = str(
            payload.get("summary")
            or payload.get("output_bundle_summary")
            or payload.get("output_text")
            or ""
        ).strip()
        result = {
            "ok": bool(ok),
            "branch_status": str(branch_status or "").strip(),
            "result_ref": str(result_ref or "").strip(),
            "recorded_at": self._now_text(),
        }
        if summary:
            result["summary"] = summary[:500]
        return result

    @staticmethod
    def _extract_branch_reference_fields(
        *,
        runtime_plan: dict[str, Any] | None,
        node_metadata: dict[str, Any] | None,
        keys: tuple[str, ...],
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        for key in keys:
            for source in (runtime_plan or {}, node_metadata or {}):
                value = str(source.get(key) or "").strip()
                if value:
                    result[key] = value
                    break
        return result

    @staticmethod
    def _extract_branch_workflow_inputs(
        *,
        runtime_plan: dict[str, Any] | None,
        node_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        for source in (runtime_plan or {}, node_metadata or {}):
            payload = source.get("workflow_inputs")
            if isinstance(payload, dict):
                return dict(payload)
        return {}

    def _apply_judge_verdict(self, mission: Mission, node: MissionNode, verdict: JudgeVerdict) -> None:
        decision = self._normalize_judge_decision(verdict.decision)
        if decision == "accept":
            node.status = "done"
            node.metadata.pop("repair_attempts", None)
        elif decision == "repair":
            node.status = "repairing"
        elif decision == "reject":
            node.status = "failed"
        elif decision in ("escalate", "expand"):
            node.status = "blocked"
            mission.status = "awaiting_decision"
        else:
            node.status = "done"
            node.metadata.pop("repair_attempts", None)

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
