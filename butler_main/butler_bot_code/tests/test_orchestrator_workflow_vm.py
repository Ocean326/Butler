from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.agents_os.runtime import ExecutionReceipt  # noqa: E402
from butler_main.orchestrator import (  # noqa: E402
    FileLedgerEventStore,
    FileMissionStore,
    MissionNode,
    OrchestratorExecutionBridge,
    OrchestratorResearchBridge,
    OrchestratorService,
    OrchestratorWorkflowVM,
)
from butler_main.orchestrator.runner import run_orchestrator_service  # noqa: E402
from butler_main.orchestrator.workspace import build_orchestrator_service_for_workspace  # noqa: E402


class _CompletedRuntime:
    def execute(self, context) -> ExecutionReceipt:
        request = context.request
        return ExecutionReceipt(
            invocation_id=request.invocation.invocation_id,
            workflow_id=request.workflow.workflow_id if request.workflow is not None else "",
            route=request.route,
            projection=request.workflow,
            agent_id=request.agent_spec.agent_id if request.agent_spec is not None else "orchestrator.vm",
            status="completed",
            summary="workflow vm executed runtime branch",
            metadata={
                "mission_id": str(request.metadata.get("mission_id") or ""),
                "node_id": str(request.metadata.get("node_id") or ""),
                "branch_id": str(request.metadata.get("branch_id") or ""),
            },
        )


class _FakeResearchBridge(OrchestratorResearchBridge):
    def execute_branch(self, service, mission, node, branch):
        return type(
            "ResearchOutcome",
            (),
            {
                "branch_id": branch.branch_id,
                "status": "ready",
                "terminal": True,
                "ok": True,
                "result_ref": f"research:{branch.branch_id}",
                "result_payload": {
                    "summary": "research branch executed by fake bridge",
                    "workflow_session_id": str(branch.metadata.get("workflow_session_id") or ""),
                    "scenario_instance_id": "scenario_vm",
                },
            },
        )()


class OrchestratorWorkflowVMTests(unittest.TestCase):
    def _workspace(self) -> tempfile.TemporaryDirectory[str]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "butler_main" / "butler_bot_agent").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
        return tmp

    def _service(self, root: Path) -> OrchestratorService:
        return OrchestratorService(
            FileMissionStore(root / "orchestrator"),
            FileLedgerEventStore(root / "orchestrator"),
        )

    def test_workflow_vm_routes_research_nodes_to_research_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="research",
                title="VM routes research",
                nodes=[
                    MissionNode(
                        node_id="research_node",
                        kind="research_scenario",
                        title="Research",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "research.vm",
                                "kind": "research_scenario",
                                "steps": [{"step_id": "scan", "title": "Scan"}],
                            },
                            "subworkflow_kind": "research_scenario",
                            "research_unit_id": "demo.unit",
                            "scenario_action": "scan",
                        },
                    )
                ],
            )
            branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            vm = OrchestratorWorkflowVM(
                execution_bridge=OrchestratorExecutionBridge(runtime=_CompletedRuntime()),
                research_bridge=_FakeResearchBridge(),
            )

            outcomes = vm.execute_and_record(
                service,
                mission_id=mission.mission_id,
                branch_ids=[branch["branch_id"]],
            )

            self.assertEqual(len(outcomes), 1)
            self.assertEqual(outcomes[0].engine, "research_bridge")

            events = service.list_delivery_events(mission.mission_id)
            vm_events = [item for item in events if item["event_type"] == "workflow_vm_executed"]
            self.assertEqual(len(vm_events), 1)
            self.assertEqual(vm_events[0]["payload"]["engine"], "research_bridge")

    def test_runner_auto_execute_can_use_workflow_vm(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = build_orchestrator_service_for_workspace(workspace)
            mission = service.create_mission(
                mission_type="vm_runtime",
                title="Runner uses workflow vm",
                nodes=[
                    MissionNode(
                        node_id="implement",
                        kind="brainstorm",
                        title="Implement",
                        runtime_plan={
                            "runtime_key": "codex",
                            "worker_profile": "planner",
                            "workflow_template": {
                                "template_id": "vm.runtime",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "run", "title": "Run"}],
                            },
                        },
                    )
                ],
            )
            vm = OrchestratorWorkflowVM(
                execution_bridge=OrchestratorExecutionBridge(runtime=_CompletedRuntime())
            )

            summary = run_orchestrator_service(
                {
                    "workspace_root": workspace,
                    "orchestrator": {
                        "auto_dispatch": True,
                        "auto_execute": True,
                        "max_dispatch_per_tick": 1,
                    },
                },
                once=True,
                workflow_vm=vm,
            )

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["executed_branch_count"], 1)
            self.assertEqual(summary["completed_branch_count"], 1)

            mission_summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(mission_summary["status"], "completed")
            events = service.list_delivery_events(mission.mission_id)
            vm_events = [item for item in events if item["event_type"] == "workflow_vm_executed"]
            self.assertEqual(len(vm_events), 1)
            self.assertEqual(vm_events[0]["payload"]["engine"], "execution_bridge")


if __name__ == "__main__":
    unittest.main()
