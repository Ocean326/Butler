from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from butler_main.runtime_os.process_runtime import AcceptanceReceipt, ProcessExecutionOutcome, RuntimeVerdict
from butler_main.research.manager.code.research_manager import ResearchInvocation, ResearchManager, ResearchResult

from .models import Branch, Mission, MissionNode
from .research_projection import ResearchCollaborationProjection, build_research_collaboration_projection


@dataclass(slots=True, frozen=True)
class ResearchBranchExecutionOutcome:
    branch_id: str
    result: ResearchResult
    process_outcome: ProcessExecutionOutcome

    @property
    def status(self) -> str:
        result_status = str(self.result.status or "").strip()
        return result_status or self.process_outcome.status

    @property
    def terminal(self) -> bool:
        return self.process_outcome.terminal

    @property
    def ok(self) -> bool:
        return self.process_outcome.ok

    @property
    def result_ref(self) -> str:
        return self.process_outcome.result_ref

    @property
    def result_payload(self) -> dict[str, object]:
        return dict(self.process_outcome.result_payload)

    @property
    def runtime_verdict(self) -> RuntimeVerdict:
        return self.process_outcome.to_runtime_verdict()


class OrchestratorResearchBridge:
    """Bridge research_scenario branches onto ResearchManager while keeping orchestrator authoritative."""

    def __init__(
        self,
        *,
        manager: ResearchManager | None = None,
        manager_factory: Callable[[], ResearchManager] | None = None,
        workspace_resolver: Callable[[Mission, MissionNode, Branch], str] | None = None,
    ) -> None:
        self._manager = manager
        self._manager_factory = manager_factory
        self._workspace_resolver = workspace_resolver or self._default_workspace_resolver

    def execute_and_record(
        self,
        service,
        *,
        mission_id: str,
        branch_ids: list[str],
    ) -> list[ResearchBranchExecutionOutcome]:
        outcomes: list[ResearchBranchExecutionOutcome] = []
        for branch_id in branch_ids:
            mission = service.get_mission(mission_id)
            if mission is None:
                break
            branch = service.get_branch(branch_id)
            if branch is None or branch.mission_id != mission_id:
                continue
            node = mission.node_by_id(branch.node_id)
            if node is None:
                continue
            outcome = self.execute_branch(service, mission, node, branch)
            outcomes.append(outcome)
            if not outcome.terminal:
                continue
            service.record_branch_result(
                mission_id,
                branch.branch_id,
                process_outcome=outcome.process_outcome,
            )
        return outcomes

    def execute_branch(self, service, mission: Mission, node: MissionNode, branch: Branch) -> ResearchBranchExecutionOutcome:
        if not self._is_research_node(node):
            raise ValueError(f"node is not a research_scenario: {node.node_id}")

        workflow_session_id = self._workflow_session_id(branch, node)
        research_unit_id = self._resolve_reference(node, branch, "research_unit_id")
        scenario_action = self._resolve_reference(node, branch, "scenario_action")
        subworkflow_kind = self._resolve_reference(node, branch, "subworkflow_kind") or "research_scenario"
        workflow_inputs = self._resolve_workflow_inputs(node, branch)

        if not research_unit_id:
            result = ResearchResult(
                status="blocked",
                entrypoint="codex",
                unit_id="",
                summary="research_scenario branch missing research_unit_id",
                acceptance=AcceptanceReceipt(
                    goal_achieved=False,
                    summary="research_scenario branch blocked before invoking research manager",
                    evidence=["failure_class=context_missing"],
                    artifacts=[],
                    uncertainties=["research_unit_id was not provided"],
                    next_action="research_unit_id is required for research_scenario branches",
                    failure_class="context_missing",
                ),
                route={"bridge": "orchestrator.research_bridge", "subworkflow_kind": subworkflow_kind},
                payload={
                    "task_id": branch.branch_id,
                    "session_id": workflow_session_id,
                    "workspace": self._workspace_resolver(mission, node, branch),
                    "metadata": {"scenario_action": scenario_action},
                },
            )
            result_ref = workflow_session_id or branch.branch_id
            return ResearchBranchExecutionOutcome(
                branch_id=branch.branch_id,
                result=result,
                process_outcome=ProcessExecutionOutcome(
                    status="failed",
                    terminal=True,
                    result_ok=False,
                    result_ref=result_ref,
                    result_payload=self._build_result_payload(
                        result=result,
                        mission=mission,
                        node=node,
                        branch=branch,
                        workflow_session_id=workflow_session_id,
                        result_ref=result_ref,
                        artifact_refs=[],
                    ),
                    metadata={
                        "bridge": "research_bridge",
                        "receipt_status": str(result.status or "").strip(),
                        "summary": str(result.summary or "").strip(),
                    },
                ),
            )

        shared_state = self._load_shared_state(service, workflow_session_id)
        workflow_cursor = shared_state.get("workflow_cursor")
        workflow_cursor_payload = dict(workflow_cursor) if isinstance(workflow_cursor, dict) and workflow_cursor else {}
        invocation = ResearchInvocation(
            entrypoint="codex",
            goal=self._build_goal(mission, node, workflow_inputs),
            unit_id=research_unit_id,
            session_id=workflow_session_id,
            task_id=branch.branch_id,
            workspace=self._workspace_resolver(mission, node, branch),
            payload={
                "workflow_session_id": workflow_session_id,
                "workflow_inputs": workflow_inputs,
                **({"workflow_cursor": workflow_cursor_payload} if workflow_cursor_payload else {}),
            },
            metadata={
                "mission_id": mission.mission_id,
                "node_id": node.node_id,
                "branch_id": branch.branch_id,
                "scenario_action": scenario_action,
                "subworkflow_kind": subworkflow_kind,
                **({"workflow_cursor": workflow_cursor_payload} if workflow_cursor_payload else {}),
            },
        )
        result = self._resolve_manager().invoke(invocation)
        artifact_refs = self._write_back_workflow_session(
            service,
            workflow_session_id=workflow_session_id,
            research_unit_id=research_unit_id,
            scenario_action=scenario_action,
            result=result,
        )
        result_ref = self._result_ref(result, workflow_session_id, branch.branch_id)
        return ResearchBranchExecutionOutcome(
            branch_id=branch.branch_id,
            result=result,
            process_outcome=ProcessExecutionOutcome(
                status="completed" if result.status == "ready" else "failed",
                terminal=True,
                result_ok=result.status == "ready",
                result_ref=result_ref,
                result_payload=self._build_result_payload(
                    result=result,
                    mission=mission,
                    node=node,
                    branch=branch,
                    workflow_session_id=workflow_session_id,
                    result_ref=result_ref,
                    artifact_refs=artifact_refs,
                ),
                metadata={
                    "bridge": "research_bridge",
                    "receipt_status": str(result.status or "").strip(),
                    "summary": str(result.summary or "").strip(),
                },
            ),
        )

    def _resolve_manager(self) -> ResearchManager:
        if self._manager is not None:
            return self._manager
        if self._manager_factory is not None:
            self._manager = self._manager_factory()
            return self._manager
        self._manager = ResearchManager()
        return self._manager

    @staticmethod
    def _is_research_node(node: MissionNode) -> bool:
        if str(node.kind or "").strip() == "research_scenario":
            return True
        return str(node.metadata.get("subworkflow_kind") or "").strip() == "research_scenario"

    @staticmethod
    def _workflow_session_id(branch: Branch, node: MissionNode) -> str:
        return str(
            branch.input_payload.get("workflow_session_id")
            or branch.metadata.get("workflow_session_id")
            or node.metadata.get("workflow_session_id")
            or ""
        ).strip()

    @staticmethod
    def _resolve_reference(node: MissionNode, branch: Branch, key: str) -> str:
        for source in (
            branch.input_payload or {},
            branch.metadata or {},
            node.metadata or {},
            node.runtime_plan or {},
        ):
            value = str(source.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _resolve_workflow_inputs(node: MissionNode, branch: Branch) -> dict[str, Any]:
        for source in (
            branch.input_payload or {},
            branch.metadata or {},
            node.runtime_plan or {},
            node.metadata or {},
        ):
            payload = source.get("workflow_inputs")
            if isinstance(payload, dict):
                return dict(payload)
        return {}

    @staticmethod
    def _build_goal(mission: Mission, node: MissionNode, workflow_inputs: dict[str, Any]) -> str:
        for value in (
            workflow_inputs.get("goal"),
            workflow_inputs.get("task"),
            mission.goal,
            node.title,
            mission.title,
        ):
            text = str(value or "").strip()
            if text:
                return text
        return "execute research scenario"

    @staticmethod
    def _default_workspace_resolver(mission: Mission, node: MissionNode, branch: Branch) -> str:
        for source in (
            branch.input_payload or {},
            branch.metadata or {},
            node.runtime_plan or {},
            node.metadata or {},
            mission.metadata or {},
        ):
            workspace = str(source.get("workspace") or source.get("workspace_root") or "").strip()
            if workspace:
                return workspace
        return str(Path.cwd())

    @staticmethod
    def _load_shared_state(service, workflow_session_id: str) -> dict[str, Any]:
        if not workflow_session_id:
            return {}
        try:
            return service._workflow_session_bridge.load_shared_state(workflow_session_id)
        except Exception:
            return {}

    def _write_back_workflow_session(
        self,
        service,
        *,
        workflow_session_id: str,
        research_unit_id: str,
        scenario_action: str,
        result: ResearchResult,
    ) -> list[str]:
        projection = build_research_collaboration_projection(
            workflow_session_id=workflow_session_id,
            research_unit_id=research_unit_id,
            scenario_action=scenario_action,
            result=result,
        )
        if projection is None:
            return []
        self._apply_collaboration_projection(service, projection)
        return self._unique_strings([item.ref for item in projection.artifacts])

    @staticmethod
    def _dispatch_payload(result: ResearchResult) -> dict[str, Any]:
        payload = result.payload.get("dispatch")
        return dict(payload) if isinstance(payload, dict) else {}

    @staticmethod
    def _result_ref(result: ResearchResult, workflow_session_id: str, branch_id: str) -> str:
        dispatch = result.payload.get("dispatch")
        scenario_instance = dispatch.get("scenario_instance") if isinstance(dispatch, dict) and isinstance(dispatch.get("scenario_instance"), dict) else {}
        scenario_instance_id = str(
            result.route.get("scenario_instance_id")
            or scenario_instance.get("scenario_instance_id")
            or ""
        ).strip()
        if scenario_instance_id:
            return f"research_scenario:{scenario_instance_id}"
        if workflow_session_id:
            return workflow_session_id
        return branch_id

    @staticmethod
    def _unique_strings(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in values:
            value = str(item or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _apply_collaboration_projection(
        self,
        service,
        projection: ResearchCollaborationProjection,
    ) -> None:
        service._workflow_session_bridge.apply_collaboration_projection(projection)

    def _build_result_payload(
        self,
        *,
        result: ResearchResult,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        workflow_session_id: str,
        result_ref: str,
        artifact_refs: list[str],
    ) -> dict[str, object]:
        dispatch = self._dispatch_payload(result)
        scenario_instance = dispatch.get("scenario_instance") if isinstance(dispatch.get("scenario_instance"), dict) else {}
        return {
            "status": str(result.status or "").strip(),
            "summary": str(result.summary or "").strip(),
            "entrypoint": str(result.entrypoint or "").strip(),
            "unit_id": str(result.unit_id or "").strip(),
            "mission_id": mission.mission_id,
            "node_id": node.node_id,
            "branch_id": branch.branch_id,
            "workflow_session_id": workflow_session_id,
            "scenario_instance_id": str(scenario_instance.get("scenario_instance_id") or result.route.get("scenario_instance_id") or "").strip(),
            "next_action": str(result.acceptance.next_action or "").strip(),
            "failure_class": str(result.acceptance.failure_class or "").strip(),
            "route": dict(result.route or {}),
            "dispatch": dispatch,
            "artifact_refs": self._unique_strings(artifact_refs),
            "result_ref": result_ref,
        }
