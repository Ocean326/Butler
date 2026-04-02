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
    FileLedgerEventStore,
    FileMissionStore,
    MissionNode,
    OrchestratorExecutionBridge,
    OrchestratorService,
    WorkflowIR,
)
from butler_main.orchestrator.runtime_adapter import ORCHESTRATOR_EXECUTION_CAPABILITY_ID  # noqa: E402


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
                            "role_bindings": [{"role_id": "planner", "capability_id": "cap.plan"}],
                            "worker_profile": "planner",
                            "runtime_key": "codex",
                            "agent_id": "orchestrator.codex.planner",
                            "workflow_template": {
                                "template_id": "brainstorm.plan",
                                "kind": "local_collaboration",
                                "entry_step_id": "scope",
                                "steps": [
                                    {"step_id": "scope", "title": "Scope", "step_kind": "dispatch"},
                                    {"step_id": "review", "title": "Review", "step_kind": "verify"},
                                ],
                                "edges": [
                                    {
                                        "edge_id": "scope__review",
                                        "source_step_id": "scope",
                                        "target_step_id": "review",
                                        "condition": "on_success",
                                    }
                                ],
                                "roles": [{"role_id": "planner", "capability_id": "cap.plan"}],
                                "artifacts": [
                                    {
                                        "artifact_id": "plan_doc",
                                        "artifact_kind": "document",
                                        "producer_step_id": "review",
                                    }
                                ],
                                "handoffs": [
                                    {
                                        "handoff_id": "scope_to_review",
                                        "source_step_id": "scope",
                                        "target_step_id": "review",
                                        "handoff_kind": "step_output",
                                        "artifact_refs": ["plan_doc"],
                                    }
                                ],
                            },
                            "capability_package_ref": "pkg.cap.planning",
                            "team_package_ref": "team.butler.core",
                            "governance_policy_ref": "policy.review.default",
                            "runtime_binding": {
                                "runtime_key": "codex",
                                "agent_id": "orchestrator.codex.planner",
                                "worker_profile": "planner",
                            },
                            "input_contract": {"required": ["goal"]},
                            "output_contract": {"required": ["plan_doc"]},
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
            self.assertEqual(workflow_ir["schema_version"], "butler.workflow_ir.v1")
            self.assertEqual(workflow_ir["capability_package_ref"], "pkg.cap.planning")
            self.assertEqual(workflow_ir["workflow"]["entry_step_id"], "scope")
            self.assertEqual(workflow_ir["workflow"]["edges"][0]["condition"], "on_success")
            self.assertEqual(workflow_ir["workflow"]["artifacts"][0]["artifact_id"], "plan_doc")
            self.assertEqual(workflow_ir["workflow"]["handoffs"][0]["handoff_id"], "scope_to_review")
            self.assertEqual(workflow_ir["workflow"]["package_refs"]["team_package_ref"], "team.butler.core")
            self.assertEqual(workflow_ir["compile_time"]["workflow"]["runtime_binding"]["runtime_key"], "codex")
            self.assertEqual(workflow_ir["runtime"]["workflow_session_id"], branch["metadata"]["workflow_session_id"])
            self.assertEqual(workflow_ir["observability"]["lineage"]["compiler_version"], "orchestrator.workflow_ir.v2")
            gate_policies = workflow_ir.get("gate_policies") or {}
            self.assertEqual(gate_policies["verification"]["mode"], "required")
            self.assertFalse(gate_policies["approval"]["required"])
            self.assertEqual(gate_policies["recovery"]["action"], "retry")
            self.assertEqual(workflow_ir["execution_boundary"]["selected_engine"], "execution_bridge")

            summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(summary["branches"][0]["workflow_ir"]["runtime_key"], "codex")
            self.assertEqual(summary["nodes"][0]["workflow_ir"]["template_id"], "brainstorm.plan")
            self.assertEqual(summary["nodes"][0]["workflow_ir"]["step_count"], 2)

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
            self.assertEqual(runtime.last_request.workflow.current_step_id, "run")
            self.assertEqual(runtime.last_request.route.capability_id, ORCHESTRATOR_EXECUTION_CAPABILITY_ID)
            self.assertEqual(runtime.last_request.workflow.required_capability_ids, [ORCHESTRATOR_EXECUTION_CAPABILITY_ID])
            self.assertEqual(runtime.last_request.workflow.metadata["verification"]["mode"], "required")
            self.assertEqual(workflow_ir["execution_boundary"]["execution_owner"], "runtime_os.agent_runtime")
            self.assertEqual(workflow_ir["execution_boundary"]["collaboration_owner"], "runtime_os.process_runtime")
            self.assertEqual(workflow_ir["execution_boundary"]["protocol_owner"], "runtime_os.multi_agent_protocols")
            self.assertEqual(workflow_ir["execution_boundary"]["session_runtime_owner"], "runtime_os.multi_agent_runtime")
            self.assertEqual(workflow_ir["execution_boundary"]["durability_owner"], "runtime_os.durability_substrate")
            self.assertEqual(workflow_ir["execution_boundary"]["compat_execution_owner"], "agents_os")
            self.assertEqual(workflow_ir["gate_policies"]["verification"]["canonical_target_owner"], "runtime_os.durability_substrate")

            result_payload = outcomes[0].result_payload
            self.assertEqual(result_payload["workflow_ir"]["runtime_key"], "codex")
            self.assertEqual(result_payload["workflow_ir"]["template_id"], "brainstorm.execute")

    def test_workflow_ir_round_trip_preserves_structured_sections(self) -> None:
        ir = WorkflowIR(
            workflow_id="wf.demo",
            mission_id="mission.demo",
            node_id="node.demo",
            branch_id="branch.demo",
            workflow_kind="local_collaboration",
            runtime_key="codex",
            agent_id="orchestrator.codex.demo",
            worker_profile="planner",
            workflow_template={"template_id": "demo.template", "kind": "local_collaboration"},
            capability_package_ref="pkg.cap.demo",
            team_package_ref="team.demo",
            governance_policy_ref="policy.demo",
            runtime_binding={"runtime_key": "codex", "agent_id": "orchestrator.codex.demo", "worker_profile": "planner"},
            input_contract={"required": ["goal"]},
            output_contract={"required": ["answer"]},
            entry_step_id="draft",
            steps=[{"step_id": "draft", "step_kind": "dispatch"}, {"step_id": "approve", "step_kind": "approve"}],
            edges=[{"edge_id": "draft__approve", "source_step_id": "draft", "target_step_id": "approve", "condition": "next"}],
            roles=[{"role_id": "planner", "capability_id": "cap.plan"}],
            artifacts=[{"artifact_id": "answer", "artifact_kind": "document", "producer_step_id": "approve"}],
            handoffs=[{"handoff_id": "draft_to_approve", "source_step_id": "draft", "target_step_id": "approve"}],
            runtime_state={"status": "compiled", "workflow_session_id": "session.demo"},
            observability={"tags": ["local_collaboration", "planner"], "lineage": {"compiler_version": "manual.test"}},
        )

        payload = ir.to_dict()
        cloned = WorkflowIR.from_dict(payload).to_dict()

        self.assertEqual(cloned["workflow"]["steps"][0]["step_id"], "draft")
        self.assertEqual(cloned["workflow"]["edges"][0]["target_step_id"], "approve")
        self.assertEqual(cloned["workflow"]["package_refs"]["capability_package_ref"], "pkg.cap.demo")
        self.assertEqual(cloned["runtime"]["workflow_session_id"], "session.demo")
        self.assertEqual(cloned["observability"]["lineage"]["compiler_version"], "manual.test")

    def test_recovery_policy_preserves_retry_step_and_resume_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="workflow_ir",
                title="Recovery actions stay distinct",
                nodes=[
                    MissionNode(
                        node_id="retry_step",
                        kind="brainstorm",
                        title="Retry step",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "brainstorm.retry_step",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "draft", "title": "Draft"}],
                            },
                            "recovery": {"kind": "retry_step", "resume_from": "draft", "max_attempts": 2},
                        },
                    ),
                    MissionNode(
                        node_id="resume",
                        kind="brainstorm",
                        title="Resume",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "brainstorm.resume",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "review", "title": "Review"}],
                            },
                            "recovery": {"kind": "resume", "resume_from": "review", "max_attempts": 1},
                        },
                    ),
                ],
            )

            dispatched = service.dispatch_ready_nodes(mission.mission_id)
            self.assertEqual(len(dispatched), 2)
            retry_branch = next(item for item in dispatched if item["node_id"] == "retry_step")
            resume_branch = next(item for item in dispatched if item["node_id"] == "resume")

            retry_policy = retry_branch["metadata"]["workflow_ir"]["gate_policies"]["recovery"]
            resume_policy = resume_branch["metadata"]["workflow_ir"]["gate_policies"]["recovery"]

            self.assertEqual(retry_policy["action"], "retry_step")
            self.assertEqual(retry_policy["resume_from"], "draft")
            self.assertEqual(retry_policy["runner"], "workflow_resume_loop")
            self.assertEqual(resume_policy["action"], "resume")
            self.assertEqual(resume_policy["resume_from"], "review")
            self.assertEqual(resume_policy["runner"], "workflow_resume_loop")


if __name__ == "__main__":
    unittest.main()
