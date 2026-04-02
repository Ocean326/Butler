from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.contracts import Invocation, OutputBundle, TextBlock
from agents_os.runtime import (
    AcceptanceReceipt,
    Artifact,
    CAPABILITY_COLLAB,
    CAPABILITY_LOCAL_MEMORY,
    CAPABILITY_RECENT_MEMORY,
    CAPABILITY_SKILLS,
    CapabilityBinding,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionRuntime,
    FileWorkflowCheckpointStore,
    FunctionWorker,
    GuardrailDecision,
    RouteProjection,
    RunInput,
    RuntimeKernel,
    RuntimeRequest,
    SubworkflowCapability,
    VendorCapabilityOwnership,
    VendorResumeRecoveryPolicy,
    WorkerResult,
    WorkflowProjection,
    build_default_vendor_registry,
    normalize_recovery_policy,
)


class AgentsOsRuntimeTests(unittest.TestCase):
    def test_single_worker_runtime_closure(self) -> None:
        kernel = RuntimeKernel()

        def handler(request):
            return WorkerResult(
                output={"echo": request.payload, "context_seen": dict(request.context)},
                artifacts=[Artifact(kind="note", content="done")],
                context_updates={"last_payload": request.payload},
            )

        kernel.register_worker(FunctionWorker("echo", handler))
        result = kernel.execute(
            RunInput(
                session_id="session_demo",
                worker="echo",
                payload={"text": "hello"},
            )
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.output["echo"], {"text": "hello"})
        self.assertEqual(len(result.artifacts), 1)
        self.assertEqual(kernel.context_store.load("session_demo")["last_payload"], {"text": "hello"})
        self.assertIsNotNone(result.acceptance)
        self.assertTrue(result.acceptance.goal_achieved)
        self.assertEqual(result.failure_class, "")
        self.assertGreaterEqual(result.trace_count, 7)
        event_kinds = [event.kind for event in kernel.trace_observer.list_for_run(result.run_id)]
        self.assertEqual(
            event_kinds,
            [
                "run_started",
                "context_prepared",
                "guardrail_checked",
                "worker_dispatched",
                "worker_completed",
                "receipt_emitted",
                "run_completed",
            ],
        )

    def test_guardrail_can_block_worker_dispatch(self) -> None:
        class DenyAllGuardrails:
            def inspect(self, run, *, worker_name, payload):
                return GuardrailDecision(allowed=False, reason="blocked for review", code="review_required")

        kernel = RuntimeKernel(guardrails=DenyAllGuardrails())
        worker_called = {"value": False}

        def handler(request):
            worker_called["value"] = True
            return WorkerResult(output="should not happen")

        kernel.register_worker(FunctionWorker("blocked_worker", handler))
        result = kernel.execute(RunInput(session_id="session_demo", worker="blocked_worker", payload="hi"))

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.error, "blocked for review")
        self.assertEqual(result.failure_class, "policy_blocked")
        self.assertIsNotNone(result.acceptance)
        self.assertFalse(result.acceptance.goal_achieved)
        self.assertEqual(result.acceptance.failure_class, "policy_blocked")
        self.assertFalse(worker_called["value"])

    def test_worker_acceptance_receipt_passes_through_runtime(self) -> None:
        kernel = RuntimeKernel()

        def handler(request):
            return WorkerResult(
                status="completed",
                output={"ok": True},
                acceptance=AcceptanceReceipt(
                    goal_achieved=True,
                    summary="custom acceptance",
                    evidence=["rule:active"],
                    artifacts=["artifact://note"],
                ),
            )

        kernel.register_worker(FunctionWorker("receipt_worker", handler))
        result = kernel.execute(RunInput(worker="receipt_worker", payload="hello"))

        self.assertEqual(result.status, "completed")
        self.assertIsNotNone(result.acceptance)
        self.assertEqual(result.acceptance.summary, "custom acceptance")
        self.assertEqual(result.acceptance.evidence, ["rule:active"])

    def test_worker_exception_is_classified(self) -> None:
        kernel = RuntimeKernel()

        def handler(request):
            raise RuntimeError("boom")

        kernel.register_worker(FunctionWorker("boom_worker", handler))
        result = kernel.execute(RunInput(worker="boom_worker", payload="hello"))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_class, "worker_error")
        self.assertIsNotNone(result.acceptance)
        self.assertEqual(result.acceptance.failure_class, "worker_error")
        event_kinds = [event.kind for event in kernel.trace_observer.list_for_run(result.run_id)]
        self.assertIn("receipt_emitted", event_kinds)
        self.assertEqual(event_kinds[-1], "run_failed")

    def test_execution_runtime_builds_contract_snapshot_with_capability_and_checkpoint(self) -> None:
        registry = CapabilityRegistry()
        registry.register(
            CapabilityBinding(
                capability=SubworkflowCapability(
                    capability_id="brainstorm",
                    supported_entrypoints=["orchestrator_branch"],
                    supported_workflow_kinds=["local_collaboration"],
                    required_policies=["verification"],
                ),
                agent_id="agent.brainstorm",
                priority=10,
            )
        )
        runtime = ExecutionRuntime(capability_resolver=registry)
        request = RuntimeRequest(
            invocation=Invocation(
                entrypoint="orchestrator_branch",
                channel="backend",
                session_id="session_demo",
                actor_id="orchestrator",
                user_text="Plan execution",
            ),
            route=RouteProjection(route_key="orchestrator_branch", workflow_kind="local_collaboration"),
            workflow=WorkflowProjection(
                workflow_id="wf_demo",
                workflow_kind="local_collaboration",
                current_step_id="collect",
                required_capability_ids=["brainstorm"],
                metadata={"verification": {"required": True}},
            ),
            metadata={
                "workflow_ir": {
                    "workflow_template": {
                        "template_id": "brainstorm.plan",
                        "steps": [
                            {"step_id": "collect", "process_role": "planner"},
                            {"step_id": "expand", "process_role": "executor"},
                        ],
                    }
                }
            },
        )

        receipt = runtime.execute(
            ExecutionContext(
                request=request,
                runtime_state={"checkpoint_id": "chk_001", "resume_from": "collect"},
            )
        )

        self.assertEqual(receipt.status, "pending")
        self.assertEqual(receipt.metadata["execution_phase"], "ready")
        self.assertEqual(receipt.metadata["workflow"]["step_count"], 2)
        self.assertEqual(receipt.metadata["workflow"]["next_step_id"], "expand")
        self.assertEqual(receipt.metadata["checkpoint"]["checkpoint_id"], "chk_001")
        self.assertEqual(receipt.metadata["checkpoint"]["resume_from"], "collect")
        self.assertTrue(receipt.metadata["capability_resolution"]["matched"])
        self.assertEqual(receipt.metadata["capability_resolution"]["selected"]["agent_id"], "agent.brainstorm")
        self.assertEqual(receipt.metadata["capability_resolution"]["resolved_capability_ids"], ["brainstorm"])

    def test_execution_runtime_blocks_when_approval_gate_is_pending(self) -> None:
        runtime = ExecutionRuntime()
        request = RuntimeRequest(
            invocation=Invocation(
                entrypoint="orchestrator_branch",
                channel="backend",
                session_id="session_demo",
                actor_id="orchestrator",
                user_text="Apply patch",
            ),
            workflow=WorkflowProjection(
                workflow_id="wf_demo",
                workflow_kind="mission",
                current_step_id="apply",
                metadata={"approval": {"required": True}},
            ),
        )

        receipt = runtime.execute(ExecutionContext(request=request))

        self.assertEqual(receipt.status, "blocked")

    def test_default_vendor_registry_keeps_butler_owned_memory_and_collab(self) -> None:
        registry = build_default_vendor_registry()
        for vendor in ("codex", "claude"):
            self.assertEqual(registry.get_ownership(vendor, CAPABILITY_SKILLS), VendorCapabilityOwnership.BUTLER)
            self.assertEqual(registry.get_ownership(vendor, CAPABILITY_COLLAB), VendorCapabilityOwnership.BUTLER)
            self.assertEqual(registry.get_ownership(vendor, CAPABILITY_RECENT_MEMORY), VendorCapabilityOwnership.BUTLER)
            self.assertEqual(registry.get_ownership(vendor, CAPABILITY_LOCAL_MEMORY), VendorCapabilityOwnership.BUTLER)

    def test_vendor_resume_recovery_policy_defaults_to_transparent_reseed(self) -> None:
        self.assertEqual(normalize_recovery_policy(None), VendorResumeRecoveryPolicy.TRANSPARENT_RESEED)
        self.assertEqual(normalize_recovery_policy("reseed"), VendorResumeRecoveryPolicy.TRANSPARENT_RESEED)
        self.assertEqual(normalize_recovery_policy("degrade"), VendorResumeRecoveryPolicy.EXPLICIT_DEGRADE)
        self.assertEqual(normalize_recovery_policy("strict_fail"), VendorResumeRecoveryPolicy.STRICT_FAIL)

    def test_execution_runtime_uses_handler_after_gate_clearance(self) -> None:
        registry = CapabilityRegistry()
        registry.register(
            CapabilityBinding(
                capability=SubworkflowCapability(
                    capability_id="brainstorm",
                    supported_entrypoints=["orchestrator_branch"],
                    supported_workflow_kinds=["local_collaboration"],
                    required_policies=["approval"],
                ),
                agent_id="agent.brainstorm",
                priority=5,
            )
        )
        runtime = ExecutionRuntime(
            capability_resolver=registry,
            handler=lambda context, *, binding, contract: {
                "status": "completed",
                "summary": f"executed by {binding.agent_id if binding else 'none'}",
                "output_bundle": OutputBundle(
                    summary="handler bundle",
                    text_blocks=[TextBlock(text="done")],
                ),
                "metadata": {"executor": "test_handler", "workflow_id_seen": contract["workflow"]["workflow_id"]},
            },
        )
        request = RuntimeRequest(
            invocation=Invocation(
                entrypoint="orchestrator_branch",
                channel="backend",
                session_id="session_demo",
                actor_id="orchestrator",
                user_text="Run brainstorm",
            ),
            workflow=WorkflowProjection(
                workflow_id="wf_exec",
                workflow_kind="local_collaboration",
                current_step_id="collect",
                required_capability_ids=["brainstorm"],
                metadata={"approval": {"required": True}},
            ),
        )

        receipt = runtime.execute(
            ExecutionContext(
                request=request,
                runtime_state={"approval_status": "approved"},
            )
        )

        self.assertEqual(receipt.status, "completed")
        self.assertEqual(receipt.metadata["execution_phase"], "executed")
        self.assertEqual(receipt.metadata["executor"], "test_handler")
        self.assertEqual(receipt.metadata["workflow_id_seen"], "wf_exec")
        self.assertEqual(receipt.output_bundle.text_blocks[0].text, "executed by agent.brainstorm")

    def test_execution_runtime_executes_real_multi_step_workflow(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            store = FileWorkflowCheckpointStore(Path(tmp) / "workflow_checkpoints.jsonl")
            runtime = ExecutionRuntime(
                checkpoint_store=store,
                handler=lambda context, *, binding, contract: {
                    "status": "completed",
                    "summary": f"executed {contract['step']['step_id']}",
                    "metadata": {"dispatch_executor": binding.agent_id if binding else "none"},
                    "output_bundle": OutputBundle(
                        summary="dispatch bundle",
                        text_blocks=[TextBlock(text="dispatch ok")],
                    ),
                    "handoff_payload": {"from_step": contract["step"]["step_id"]},
                },
            )
            registry = CapabilityRegistry()
            registry.register(
                CapabilityBinding(
                    capability=SubworkflowCapability(
                        capability_id="brainstorm",
                        supported_entrypoints=["orchestrator_branch"],
                        supported_workflow_kinds=["local_collaboration"],
                    ),
                    agent_id="agent.brainstorm",
                    priority=1,
                )
            )
            runtime = ExecutionRuntime(
                capability_resolver=registry,
                checkpoint_store=store,
                handler=lambda context, *, binding, contract: (
                    calls.append(contract["step"]["step_id"]) or {
                        "status": "completed",
                        "summary": f"executed {contract['step']['step_id']}",
                        "metadata": {"dispatch_executor": binding.agent_id if binding else "none"},
                        "output_bundle": OutputBundle(
                            summary="dispatch bundle",
                            text_blocks=[TextBlock(text="dispatch ok")],
                        ),
                        "handoff_payload": {"from_step": contract["step"]["step_id"]},
                    }
                ),
            )
            request = RuntimeRequest(
                invocation=Invocation(
                    entrypoint="orchestrator_branch",
                    channel="backend",
                    session_id="session_demo",
                    actor_id="orchestrator",
                    user_text="Run workflow vm",
                ),
                route=RouteProjection(route_key="orchestrator_branch", workflow_kind="local_collaboration"),
                workflow=WorkflowProjection(
                    workflow_id="wf_minimal",
                    workflow_kind="local_collaboration",
                    current_step_id="dispatch_step",
                    required_capability_ids=["brainstorm"],
                ),
                metadata={
                    "workflow_ir": {
                        "workflow_template": {
                            "template_id": "vm.minimal",
                            "steps": [
                                {"step_id": "dispatch_step", "step_kind": "dispatch", "process_role": "executor", "on_success": "verify_step"},
                                {"step_id": "verify_step", "step_kind": "verify", "process_role": "acceptance", "on_success": "approve_step"},
                                {"step_id": "approve_step", "step_kind": "approve", "process_role": "approval", "on_success": "join_step"},
                                {"step_id": "join_step", "step_kind": "join", "process_role": "manager", "next": "finalize_step"},
                                {"step_id": "finalize_step", "step_kind": "finalize", "process_role": "manager"},
                            ],
                        }
                    }
                },
            )

            receipt = runtime.execute(
                ExecutionContext(
                    request=request,
                    runtime_state={"verification_status": "passed", "approval_status": "approved"},
                )
            )

            self.assertEqual(receipt.status, "completed")
            self.assertEqual(receipt.metadata["execution_phase"], "completed")
            self.assertEqual(calls, ["dispatch_step"])
            self.assertEqual(
                receipt.metadata["workflow"]["completed_step_ids"],
                ["dispatch_step", "verify_step", "approve_step", "join_step", "finalize_step"],
            )
            projection = receipt.metadata["workflow_projection"]
            self.assertEqual(len(projection["step_receipts"]), 5)
            self.assertEqual(len(projection["handoff_receipts"]), 4)
            self.assertEqual(len(projection["decision_receipts"]), 5)
            latest_checkpoint = store.latest()
            self.assertIsNotNone(latest_checkpoint)
            self.assertEqual(latest_checkpoint.cursor.current_step_id, "finalize_step")

    def test_execution_runtime_can_resume_after_approval_gate(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            store = FileWorkflowCheckpointStore(Path(tmp) / "workflow_checkpoints.jsonl")
            runtime = ExecutionRuntime(
                checkpoint_store=store,
                handler=lambda context, *, binding, contract: (
                    calls.append(contract["step"]["step_id"]) or {
                        "status": "completed",
                        "summary": f"executed {contract['step']['step_id']}",
                    }
                ),
            )
            request = RuntimeRequest(
                invocation=Invocation(
                    entrypoint="orchestrator_branch",
                    channel="backend",
                    session_id="session_demo",
                    actor_id="orchestrator",
                    user_text="Resume workflow vm",
                ),
                workflow=WorkflowProjection(
                    workflow_id="wf_resume",
                    workflow_kind="local_collaboration",
                    current_step_id="dispatch_step",
                ),
                metadata={
                    "workflow_ir": {
                        "workflow_template": {
                            "template_id": "vm.resume",
                            "steps": [
                                {"step_id": "dispatch_step", "step_kind": "dispatch", "process_role": "executor", "on_success": "verify_step"},
                                {"step_id": "verify_step", "step_kind": "verify", "process_role": "acceptance", "on_success": "approve_step"},
                                {"step_id": "approve_step", "step_kind": "approve", "process_role": "approval", "on_success": "join_step"},
                                {"step_id": "join_step", "step_kind": "join", "process_role": "manager", "next": "finalize_step"},
                                {"step_id": "finalize_step", "step_kind": "finalize", "process_role": "manager"},
                            ],
                        }
                    }
                },
            )

            first = runtime.execute(
                ExecutionContext(
                    request=request,
                    runtime_state={"verification_status": "passed"},
                )
            )

            self.assertEqual(first.status, "blocked")
            self.assertEqual(first.metadata["execution_phase"], "approval_gate")
            first_checkpoint_id = first.metadata["checkpoint"]["checkpoint_id"]
            self.assertTrue(first_checkpoint_id)
            self.assertEqual(calls, ["dispatch_step"])
            self.assertEqual(first.metadata["workflow"]["current_step_id"], "approve_step")

            resumed = runtime.execute(
                ExecutionContext(
                    request=request,
                    runtime_state={
                        "checkpoint_id": first_checkpoint_id,
                        "verification_status": "passed",
                        "approval_status": "approved",
                    },
                )
            )

            self.assertEqual(resumed.status, "completed")
            self.assertEqual(calls, ["dispatch_step"])
            self.assertTrue(resumed.metadata["workflow"]["resumed_from_checkpoint"])
            self.assertEqual(
                resumed.metadata["workflow"]["completed_step_ids"],
                ["dispatch_step", "verify_step", "approve_step", "join_step", "finalize_step"],
            )
            projection = resumed.metadata["workflow_projection"]
            self.assertEqual(len(projection["step_receipts"]), 6)
            latest_checkpoint = store.latest()
            self.assertIsNotNone(latest_checkpoint)
            self.assertEqual(latest_checkpoint.cursor.current_step_id, "finalize_step")


if __name__ == "__main__":
    unittest.main()
