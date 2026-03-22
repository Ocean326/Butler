from __future__ import annotations

from dataclasses import dataclass

from .compiler import MissionWorkflowCompiler
from .execution_bridge import BranchExecutionOutcome, OrchestratorExecutionBridge
from .models import Branch, Mission, MissionNode
from .research_bridge import OrchestratorResearchBridge, ResearchBranchExecutionOutcome
from .workflow_ir import WorkflowIR


@dataclass(slots=True, frozen=True)
class WorkflowVMExecutionOutcome:
    branch_id: str
    engine: str
    status: str
    terminal: bool
    ok: bool
    result_ref: str
    result_payload: dict[str, object]


class OrchestratorWorkflowVM:
    """Select and execute the right branch engine from orchestrator workflow IR."""

    def __init__(
        self,
        *,
        execution_bridge: OrchestratorExecutionBridge | None = None,
        research_bridge: OrchestratorResearchBridge | None = None,
        workflow_compiler: MissionWorkflowCompiler | None = None,
    ) -> None:
        self._execution_bridge = execution_bridge
        self._research_bridge = research_bridge
        self._workflow_compiler = workflow_compiler or MissionWorkflowCompiler()

    def execute_and_record(
        self,
        service,
        *,
        mission_id: str,
        branch_ids: list[str],
    ) -> list[WorkflowVMExecutionOutcome]:
        outcomes: list[WorkflowVMExecutionOutcome] = []
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
            outcome = self.execute_branch(service, mission=mission, node=node, branch=branch)
            outcomes.append(outcome)
            if outcome.terminal:
                service.record_branch_result(
                    mission_id,
                    branch.branch_id,
                    ok=outcome.ok,
                    result_ref=outcome.result_ref,
                    result_payload=outcome.result_payload,
                )
        return outcomes

    def execute_branch(
        self,
        service,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
    ) -> WorkflowVMExecutionOutcome:
        workflow_ir = self._resolve_workflow_ir(mission=mission, node=node, branch=branch)
        if self._use_research_engine(workflow_ir, node):
            if self._research_bridge is None:
                raise RuntimeError("workflow VM requires a research bridge for research_scenario branches")
            outcome = self._research_bridge.execute_branch(service, mission, node, branch)
            engine = "research_bridge"
        else:
            if self._execution_bridge is None:
                raise RuntimeError("workflow VM requires an execution bridge for non-research branches")
            outcome = self._execution_bridge.execute_branch(mission, node, branch)
            engine = "execution_bridge"
        service._event_store.append(
            service_event(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                branch_id=branch.branch_id,
                event_type="workflow_vm_executed",
                payload={
                    "engine": engine,
                    "workflow_kind": workflow_ir.workflow_kind,
                    "driver_kind": workflow_ir.driver_kind,
                    "subworkflow_kind": workflow_ir.subworkflow_kind,
                    "status": outcome.status,
                    "ok": outcome.ok,
                    "result_ref": outcome.result_ref,
                },
            )
        )
        return WorkflowVMExecutionOutcome(
            branch_id=outcome.branch_id,
            engine=engine,
            status=outcome.status,
            terminal=outcome.terminal,
            ok=outcome.ok,
            result_ref=outcome.result_ref,
            result_payload=outcome.result_payload,
        )

    def _resolve_workflow_ir(self, *, mission: Mission, node: MissionNode, branch: Branch) -> WorkflowIR:
        payload = branch.metadata.get("workflow_ir")
        if isinstance(payload, dict) and payload:
            return WorkflowIR.from_dict(payload)
        return self._workflow_compiler.compile(mission=mission, node=node, branch=branch)

    @staticmethod
    def _use_research_engine(workflow_ir: WorkflowIR, node: MissionNode) -> bool:
        if workflow_ir.subworkflow_kind == "research_scenario":
            return True
        if workflow_ir.driver_kind == "research_scenario":
            return True
        return str(node.kind or "").strip() == "research_scenario"


def service_event(*, mission_id: str, node_id: str, branch_id: str, event_type: str, payload: dict[str, object]):
    from .models import LedgerEvent

    return LedgerEvent(
        mission_id=mission_id,
        node_id=node_id,
        branch_id=branch_id,
        event_type=event_type,
        payload=payload,
    )
