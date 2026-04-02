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

from butler_main.runtime_os.process_runtime import ExecutionReceipt  # noqa: E402
from butler_main.orchestrator import (  # noqa: E402
    Branch,
    FileLedgerEventStore,
    FileMissionStore,
    load_framework_compiler_inputs,
    Mission,
    MissionNode,
    MissionWorkflowCompiler,
    OrchestratorExecutionBridge,
    OrchestratorService,
    OrchestratorWorkflowVM,
)


class _CompletedRuntime:
    def execute(self, context) -> ExecutionReceipt:
        request = context.request
        return ExecutionReceipt(
            invocation_id=request.invocation.invocation_id,
            workflow_id=request.workflow.workflow_id if request.workflow is not None else "",
            route=request.route,
            projection=request.workflow,
            agent_id=request.agent_spec.agent_id if request.agent_spec is not None else "orchestrator.framework",
            status="completed",
            summary="framework compiled workflow executed",
            metadata={
                "mission_id": str(request.metadata.get("mission_id") or ""),
                "node_id": str(request.metadata.get("node_id") or ""),
                "branch_id": str(request.metadata.get("branch_id") or ""),
            },
        )


class OrchestratorFrameworkCompilerTests(unittest.TestCase):
    def _service(self, root: Path) -> OrchestratorService:
        return OrchestratorService(
            FileMissionStore(root / "orchestrator"),
            FileLedgerEventStore(root / "orchestrator"),
        )

    def test_compile_framework_profile_entry_produces_superpowers_ir(self) -> None:
        mission = Mission(
            mission_type="framework_demo",
            title="Superpowers demo",
            goal="Design a delivery flow",
            inputs={"problem_statement": "Need a better content workflow"},
        )
        node = MissionNode(
            node_id="framework_node",
            kind="framework_task",
            title="Compile Superpowers profile",
            runtime_plan={
                "workflow_inputs": {
                    "problem_statement": "Need a better content workflow",
                    "constraints": "Ship this week",
                }
            },
        )
        branch = Branch(mission_id=mission.mission_id, node_id=node.node_id)
        compiler = MissionWorkflowCompiler()

        workflow_ir = compiler.compile_framework_profile(
            mission=mission,
            node=node,
            branch=branch,
            profile_id="superpowers_like",
        )

        self.assertEqual(workflow_ir.workflow_kind, "local_collaboration")
        self.assertEqual(workflow_ir.workflow_template["template_id"], "framework.superpowers.superpowers_like")
        self.assertEqual([step["step_id"] for step in workflow_ir.steps], ["brainstorm", "plan", "implement", "review"])
        self.assertEqual([item["role_id"] for item in workflow_ir.role_bindings], ["brainstormer", "planner", "implementer", "reviewer"])
        self.assertEqual(workflow_ir.role_bindings[0]["metadata"]["package_ref"], "pkg.cap.ideation")
        self.assertEqual(workflow_ir.roles[0]["package_ref"], "pkg.cap.ideation")
        self.assertEqual(workflow_ir.capability_package_ref, "pkg.framework.superpowers.delivery")
        self.assertEqual(workflow_ir.team_package_ref, "team.framework.superpowers.core")
        self.assertEqual(workflow_ir.governance_policy_ref, "policy.framework.superpowers.review_gate")
        self.assertEqual(workflow_ir.runtime_binding["runtime_key"], "codex")
        self.assertEqual(workflow_ir.metadata["framework_origin"]["framework_id"], "superpowers")
        self.assertEqual(workflow_ir.metadata["framework_origin"]["profile_id"], "superpowers_like")
        self.assertEqual(workflow_ir.workflow_inputs["problem_statement"], "Need a better content workflow")
        self.assertEqual(workflow_ir.input_contract["required"], ["problem_statement"])
        self.assertIn("implementation_plan", workflow_ir.output_contract["required"])

    def test_mission_compiler_auto_detects_gstack_profile_from_framework_id(self) -> None:
        mission = Mission(
            mission_type="framework_demo",
            title="gstack demo",
            goal="Ship a change safely",
        )
        node = MissionNode(
            node_id="gstack_node",
            kind="framework_task",
            title="Compile gstack profile",
            runtime_plan={
                "framework_id": "gstack",
                "workflow_inputs": {
                    "goal": "Ship a change safely",
                    "risk_budget": "medium",
                },
            },
        )
        branch = Branch(mission_id=mission.mission_id, node_id=node.node_id)
        compiler = MissionWorkflowCompiler()

        workflow_ir = compiler.compile(mission=mission, node=node, branch=branch)

        self.assertEqual(workflow_ir.metadata["framework_origin"]["framework_id"], "gstack")
        self.assertEqual(workflow_ir.metadata["framework_origin"]["profile_id"], "gstack_like")
        self.assertEqual([step["step_id"] for step in workflow_ir.steps], ["think", "plan", "build", "qa", "ship"])
        self.assertEqual(workflow_ir.steps[-1]["step_kind"], "finalize")
        self.assertEqual(workflow_ir.output_contract["required"], ["qa_report", "release_summary"])
        self.assertEqual(workflow_ir.runtime_binding["worker_profile"], "framework.gstack")

    def test_openfang_profile_carries_governance_packages_and_runtime_hints(self) -> None:
        mission = Mission(
            mission_type="framework_demo",
            title="OpenFang demo",
            goal="Monitor and supervise autonomous execution",
        )
        node = MissionNode(
            node_id="openfang_node",
            kind="framework_task",
            title="Compile OpenFang-inspired profile",
            runtime_plan={
                "framework_profile_id": "openfang_guarded_autonomy",
                "framework_profile": {
                    "runtime_binding_hints": {"runtime_key": "cursor"},
                    "workflow_inputs": {"monitor_target": "repo.health"},
                },
            },
        )
        branch = Branch(mission_id=mission.mission_id, node_id=node.node_id)
        compiler = MissionWorkflowCompiler()

        workflow_ir = compiler.compile(mission=mission, node=node, branch=branch)

        self.assertEqual(workflow_ir.metadata["framework_origin"]["framework_id"], "openfang")
        self.assertEqual(workflow_ir.capability_package_ref, "pkg.framework.openfang.autonomy.monitoring")
        self.assertEqual(workflow_ir.team_package_ref, "team.framework.openfang.ops")
        self.assertEqual(workflow_ir.governance_policy_ref, "policy.framework.openfang.supervised_autonomy")
        self.assertTrue(workflow_ir.approval_policy()["required"])
        self.assertEqual(workflow_ir.approval_policy()["runner"], "human_gate")
        self.assertEqual(workflow_ir.runtime_key, "cursor")
        self.assertEqual(workflow_ir.runtime_binding["runtime_key"], "cursor")
        self.assertEqual([step["step_id"] for step in workflow_ir.steps], ["observe", "analyze", "propose", "approve", "execute", "finalize"])
        self.assertEqual(workflow_ir.workflow_inputs["monitor_target"], "repo.health")
        self.assertEqual(workflow_ir.summary()["framework_origin"]["profile_id"], "openfang_guarded_autonomy")

    def test_framework_compiler_consumes_explicit_lane_a_compiler_inputs(self) -> None:
        mission = Mission(
            mission_type="framework_demo",
            title="Lane A overlay demo",
            goal="Overlay mapping defaults onto framework compilation",
        )
        node = MissionNode(
            node_id="overlay_node",
            kind="framework_task",
            title="Compile with Lane A compiler inputs",
            runtime_plan={
                "framework_profile_id": "openfang_guarded_autonomy",
                "framework_compiler_inputs": load_framework_compiler_inputs("openfang"),
                "workflow_inputs": {"monitor_target": "ops.runtime"},
            },
        )
        branch = Branch(mission_id=mission.mission_id, node_id=node.node_id)
        compiler = MissionWorkflowCompiler()

        workflow_ir = compiler.compile(mission=mission, node=node, branch=branch)

        self.assertEqual(workflow_ir.metadata["framework_origin"]["framework_id"], "openfang")
        self.assertEqual(workflow_ir.metadata["framework_origin"]["source_kind"], "agent_os")
        self.assertEqual([step["step_id"] for step in workflow_ir.steps], ["observe", "analyze", "propose", "approve", "execute", "finalize"])
        self.assertEqual(workflow_ir.capability_package_ref, "pkg.cap.autonomous.research")
        self.assertEqual(workflow_ir.governance_policy_ref, "policy.autonomy.audit_required")
        self.assertTrue(workflow_ir.runtime_binding["requires_supervisor"])
        self.assertEqual(workflow_ir.runtime_binding["host_kind"], "background_runtime")

    def test_framework_compiled_ir_runs_through_existing_workflow_vm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="framework_demo",
                title="Run framework compiled flow",
                goal="Compile then execute through VM",
                nodes=[
                    MissionNode(
                        node_id="framework_node",
                        kind="framework_task",
                        title="Framework runtime node",
                        runtime_plan={
                            "framework_profile_id": "gstack_like",
                            "workflow_inputs": {"goal": "Compile then execute through VM"},
                        },
                    )
                ],
            )
            branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            workflow_ir = branch["metadata"]["workflow_ir"]
            self.assertEqual(workflow_ir["metadata"]["framework_origin"]["framework_id"], "gstack")
            self.assertEqual(workflow_ir["workflow"]["steps"][0]["step_id"], "think")
            self.assertEqual(workflow_ir["workflow"]["package_refs"]["capability_package_ref"], "pkg.framework.gstack.delivery")
            self.assertEqual(workflow_ir["runtime_binding"]["worker_profile"], "framework.gstack")
            session_summary = service.summarize_workflow_session(branch["metadata"]["workflow_session_id"])
            self.assertEqual(session_summary["role_bindings"][0]["metadata"]["package_ref"], "pkg.cap.think")

            vm = OrchestratorWorkflowVM(
                execution_bridge=OrchestratorExecutionBridge(runtime=_CompletedRuntime())
            )
            outcomes = vm.execute_and_record(
                service,
                mission_id=mission.mission_id,
                branch_ids=[branch["branch_id"]],
            )

            self.assertEqual(len(outcomes), 1)
            self.assertTrue(outcomes[0].ok)
            mission_summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(mission_summary["status"], "completed")
            self.assertEqual(mission_summary["nodes"][0]["workflow_ir"]["framework_origin"]["framework_id"], "gstack")


if __name__ == "__main__":
    unittest.main()
