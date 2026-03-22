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
    OrchestratorService,
)


class _InspectRuntime:
    def __init__(self) -> None:
        self.last_request = None

    def execute(self, context) -> ExecutionReceipt:
        self.last_request = context.request
        request = context.request
        return ExecutionReceipt(
            invocation_id=request.invocation.invocation_id,
            workflow_id=request.workflow.workflow_id if request.workflow is not None else "",
            route=request.route,
            projection=request.workflow,
            agent_id=request.agent_spec.agent_id if request.agent_spec is not None else "orchestrator.inspect",
            status="completed",
            summary="compiled workflow ir consumed by runtime",
            metadata={
                "mission_id": str(request.metadata.get("mission_id") or ""),
                "node_id": str(request.metadata.get("node_id") or ""),
                "branch_id": str(request.metadata.get("branch_id") or ""),
            },
        )


class OrchestratorWorkflowIRTests(unittest.TestCase):
    def _service(self, root: Path) -> OrchestratorService:
        return OrchestratorService(
            FileMissionStore(root / "orchestrator"),
            FileLedgerEventStore(root / "orchestrator"),
        )

    def test_dispatch_compiles_workflow_ir_and_exposes_it_in_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="workflow_ir",
                title="Compile node to workflow IR",
                nodes=[
                    MissionNode(
                        node_id="plan",
                        kind="brainstorm",
                        title="Plan",
                        runtime_plan={
                            "worker_profile": "planner",
                            "runtime_key": "codex",
                            "agent_id": "orchestrator.codex.planner",
                            "workflow_template": {
                                "template_id": "brainstorm.plan",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "scope", "title": "Scope"}],
                            },
                            "workflow_inputs": {"goal": "Plan execution"},
                            "verification": {"kind": "judge", "mode": "required"},
                            "approval": {"kind": "human_gate", "required": False},
                            "recovery": {"kind": "retry", "max_attempts": 2},
                        },
                    )
                ],
            )

            dispatched = service.dispatch_ready_nodes(mission.mission_id, limit=1)
            self.assertEqual(len(dispatched), 1)
            branch = dispatched[0]

            workflow_ir = branch["metadata"].get("workflow_ir")
            self.assertIsInstance(workflow_ir, dict)
            assert isinstance(workflow_ir, dict)
            self.assertEqual(workflow_ir["workflow_id"], branch["branch_id"])
            self.assertEqual(workflow_ir["runtime_key"], "codex")
            self.assertEqual(workflow_ir["agent_id"], "orchestrator.codex.planner")
            self.assertEqual(workflow_ir["workflow_template_id"], "brainstorm.plan")
            self.assertEqual(workflow_ir["workflow_session_id"], branch["metadata"]["workflow_session_id"])
            self.assertEqual(workflow_ir["verification"]["mode"], "required")
            self.assertEqual(workflow_ir["approval"]["kind"], "human_gate")
            self.assertEqual(workflow_ir["recovery"]["kind"], "retry")

            summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(summary["branches"][0]["workflow_ir"]["runtime_key"], "codex")
            self.assertEqual(summary["nodes"][0]["workflow_ir"]["template_id"], "brainstorm.plan")

            events = service.list_delivery_events(mission.mission_id)
            compiled = [item for item in events if item["event_type"] == "workflow_ir_compiled"]
            self.assertEqual(len(compiled), 1)
            self.assertEqual(compiled[0]["payload"]["workflow_id"], branch["branch_id"])

    def test_execution_bridge_consumes_compiled_workflow_ir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="workflow_ir",
                title="Execution consumes workflow ir",
                nodes=[
                    MissionNode(
                        node_id="execute",
                        kind="brainstorm",
                        title="Execute",
                        runtime_plan={
                            "worker_profile": "planner",
                            "runtime_key": "codex",
                            "agent_id": "orchestrator.codex.executor",
                            "workflow_template": {
                                "template_id": "brainstorm.execute",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "run", "title": "Run"}],
                            },
                            "verification": {"kind": "judge", "mode": "required"},
                            "recovery": {"kind": "retry", "max_attempts": 1},
                        },
                    )
                ],
            )
            branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            runtime = _InspectRuntime()
            bridge = OrchestratorExecutionBridge(runtime=runtime)

            outcomes = bridge.execute_and_record(
                service,
                mission_id=mission.mission_id,
                branch_ids=[branch["branch_id"]],
            )

            self.assertEqual(len(outcomes), 1)
            self.assertIsNotNone(runtime.last_request)
            assert runtime.last_request is not None
            workflow_ir = runtime.last_request.metadata.get("workflow_ir")
            self.assertIsInstance(workflow_ir, dict)
            assert isinstance(workflow_ir, dict)
            self.assertEqual(workflow_ir["workflow_id"], branch["branch_id"])
            self.assertEqual(workflow_ir["runtime_key"], "codex")
            self.assertEqual(runtime.last_request.workflow.workflow_id, branch["branch_id"])
            self.assertEqual(runtime.last_request.workflow.metadata["verification"]["mode"], "required")

            result_payload = outcomes[0].result_payload
            self.assertEqual(result_payload["workflow_ir"]["runtime_key"], "codex")
            self.assertEqual(result_payload["workflow_ir"]["template_id"], "brainstorm.execute")


if __name__ == "__main__":
    unittest.main()
