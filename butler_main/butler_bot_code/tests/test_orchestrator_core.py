from __future__ import annotations

import json
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

from butler_main.orchestrator import (  # noqa: E402
    FileLedgerEventStore,
    FileMissionStore,
    JudgeVerdict,
    MissionNode,
    OrchestratorJudgeAdapter,
    OrchestratorPolicy,
    OrchestratorService,
)
from butler_main.runtime_os.process_runtime import (  # noqa: E402
    ApprovalTicket,
    ProcessExecutionOutcome,
    ProcessWritebackProjection,
    RecoveryDirective,
    RuntimeVerdict,
    VerificationReceipt,
)


class OrchestratorCoreTests(unittest.TestCase):
    def _service(self, root: Path) -> OrchestratorService:
        return OrchestratorService(
            FileMissionStore(root / "orchestrator"),
            FileLedgerEventStore(root / "orchestrator"),
        )

    def test_create_mission_persists_root_node_as_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)

            mission = service.create_mission(
                mission_type="brainstorm_topic",
                title="Brainstorm a topic",
                goal="Generate first-pass ideas",
                nodes=[MissionNode(kind="brainstorm", title="Generate ideas")],
            )

            reloaded = service.get_mission(mission.mission_id)
            self.assertIsNotNone(reloaded)
            assert reloaded is not None
            self.assertEqual(reloaded.status, "ready")
            self.assertEqual(len(reloaded.nodes), 1)
            self.assertEqual(reloaded.nodes[0].status, "ready")

            events = service.list_delivery_events(mission.mission_id)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_type"], "mission_created")

    def test_tick_activates_dependent_node_after_dependency_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)

            mission = service.create_mission(
                mission_type="validate_idea",
                title="Validate idea",
                nodes=[
                    MissionNode(node_id="node_a", kind="prepare", title="Prepare"),
                    MissionNode(node_id="node_b", kind="validate", title="Validate", dependencies=["node_a"]),
                ],
            )
            stored = service.get_mission(mission.mission_id)
            assert stored is not None
            stored.nodes[0].status = "done"
            stored.nodes[1].status = "pending"
            service._mission_store.save(stored)

            result = service.tick(mission.mission_id)
            reloaded = service.get_mission(mission.mission_id)
            assert reloaded is not None

            self.assertTrue(result["ok"])
            self.assertEqual(result["activated_node_count"], 1)
            self.assertEqual(reloaded.status, "running")
            self.assertEqual(reloaded.nodes[1].status, "ready")

    def test_tick_on_empty_mission_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)

            mission = service.create_mission(
                mission_type="empty",
                title="No work yet",
            )

            result = service.tick(mission.mission_id)
            reloaded = service.get_mission(mission.mission_id)
            assert reloaded is not None

            self.assertTrue(result["ok"])
            self.assertEqual(result["activated_node_count"], 0)
            self.assertEqual(reloaded.status, "ready")

    def test_dispatch_respects_total_branch_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = OrchestratorPolicy(max_total_branches_per_mission=1)
            service = OrchestratorService(
                FileMissionStore(root / "orchestrator"),
                FileLedgerEventStore(root / "orchestrator"),
                policy=policy,
            )
            mission = service.create_mission(
                mission_type="parallel",
                title="Two roots",
                nodes=[
                    MissionNode(node_id="a", kind="t", title="A"),
                    MissionNode(node_id="b", kind="t", title="B"),
                ],
            )
            dispatched = service.dispatch_ready_nodes(mission.mission_id)
            self.assertEqual(len(dispatched), 1)
            skipped = [e for e in service.list_delivery_events(mission.mission_id) if e["event_type"] == "dispatch_skipped_policy"]
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0]["payload"].get("reason"), "total_branch_cap")

    def test_repair_exhaustion_marks_node_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = OrchestratorPolicy(max_repair_attempts_per_node=0)
            service = OrchestratorService(
                FileMissionStore(root / "orchestrator"),
                FileLedgerEventStore(root / "orchestrator"),
                policy=policy,
            )
            mission = service.create_mission(
                mission_type="one",
                title="One node",
                nodes=[MissionNode(node_id="only", kind="t", title="Only")],
            )
            dispatched = service.dispatch_ready_nodes(mission.mission_id, limit=1)
            self.assertEqual(len(dispatched), 1)
            service.record_branch_result(mission.mission_id, dispatched[0]["branch_id"], ok=False)
            reloaded = service.get_mission(mission.mission_id)
            assert reloaded is not None
            self.assertEqual(reloaded.nodes[0].status, "failed")
            exhausted = [e for e in service.list_delivery_events(mission.mission_id) if e["event_type"] == "repair_exhausted"]
            self.assertEqual(len(exhausted), 1)

    def test_judge_repair_verdict_keeps_node_in_repair_loop(self) -> None:
        class RepairJudge(OrchestratorJudgeAdapter):
            def evaluate_node(self, mission_id: str, node_id: str, artifacts: list[dict] | None = None) -> JudgeVerdict:
                return JudgeVerdict(decision="repair", reason="needs_retry")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = OrchestratorService(
                FileMissionStore(root / "orchestrator"),
                FileLedgerEventStore(root / "orchestrator"),
                judge=RepairJudge(),
            )
            mission = service.create_mission(
                mission_type="one",
                title="One node",
                nodes=[MissionNode(node_id="only", kind="t", title="Only")],
            )
            dispatched = service.dispatch_ready_nodes(mission.mission_id, limit=1)
            service.record_branch_result(
                mission.mission_id,
                dispatched[0]["branch_id"],
                ok=True,
                result_ref="r1",
                result_payload={},
            )
            reloaded = service.get_mission(mission.mission_id)
            assert reloaded is not None
            self.assertEqual(reloaded.nodes[0].status, "repairing")
            verdicts = [e for e in service.list_delivery_events(mission.mission_id) if e["event_type"] == "judge_verdict"]
            self.assertTrue(any(v["payload"].get("decision") == "repair" for v in verdicts))

    def test_workflow_ir_can_disable_recovery_after_branch_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="recovery_gate",
                title="Recovery disabled",
                nodes=[
                    MissionNode(
                        node_id="only",
                        kind="t",
                        title="Only",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "recovery.disabled",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "run", "title": "Run"}],
                            },
                            "recovery": {"enabled": False},
                        },
                    )
                ],
            )

            branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            result = service.record_branch_result(
                mission.mission_id,
                branch["branch_id"],
                ok=False,
                result_ref="artifact:error",
                result_payload={"summary": "should fail without retry"},
            )

            self.assertEqual(result["node_status"], "failed")
            self.assertEqual(result["mission_status"], "failed")
            reloaded = service.get_mission(mission.mission_id)
            assert reloaded is not None
            self.assertEqual(reloaded.nodes[0].status, "failed")
            events = service.list_delivery_events(mission.mission_id)
            skipped = [event for event in events if event["event_type"] == "recovery_skipped"]
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0]["payload"]["policy"], "workflow_ir_recovery_disabled")
            self.assertEqual(skipped[0]["payload"]["recovery_policy"]["action"], "disabled")

    def test_judge_repair_respects_workflow_ir_recovery_budget(self) -> None:
        class RepairJudge(OrchestratorJudgeAdapter):
            def evaluate_node(self, mission_id: str, node_id: str, artifacts: list[dict] | None = None) -> JudgeVerdict:
                return JudgeVerdict(decision="repair", reason="needs_retry")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = OrchestratorService(
                FileMissionStore(root / "orchestrator"),
                FileLedgerEventStore(root / "orchestrator"),
                judge=RepairJudge(),
            )
            mission = service.create_mission(
                mission_type="recovery_budget",
                title="Recovery budget",
                nodes=[
                    MissionNode(
                        node_id="only",
                        kind="t",
                        title="Only",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "recovery.budget",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "run", "title": "Run"}],
                            },
                            "recovery": {"kind": "retry", "max_attempts": 1},
                        },
                    )
                ],
            )

            first_branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            first = service.record_branch_result(
                mission.mission_id,
                first_branch["branch_id"],
                ok=True,
                result_ref="artifact:first",
                result_payload={"summary": "first repair requested"},
            )
            self.assertEqual(first["node_status"], "repairing")

            tick = service.tick(mission.mission_id)
            self.assertEqual(tick["activated_node_count"], 1)
            second_branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            second = service.record_branch_result(
                mission.mission_id,
                second_branch["branch_id"],
                ok=True,
                result_ref="artifact:second",
                result_payload={"summary": "second repair should exhaust"},
            )

            self.assertEqual(second["node_status"], "failed")
            self.assertEqual(second["mission_status"], "failed")
            reloaded = service.get_mission(mission.mission_id)
            assert reloaded is not None
            self.assertEqual(reloaded.nodes[0].status, "failed")
            events = service.list_delivery_events(mission.mission_id)
            scheduled = [event for event in events if event["event_type"] == "recovery_scheduled"]
            exhausted = [event for event in events if event["event_type"] == "repair_exhausted"]
            self.assertEqual(len(scheduled), 1)
            self.assertEqual(len(exhausted), 1)
            self.assertEqual(exhausted[0]["payload"]["cap"], 1)
            self.assertEqual(scheduled[0]["payload"]["action"], "retry")

    def test_record_branch_result_completes_workflow_session_and_exposes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="workflow",
                title="Workflow branch",
                nodes=[
                    MissionNode(
                        node_id="generate",
                        kind="brainstorm",
                        title="Generate",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "brainstorm.generate",
                                "kind": "local_collaboration",
                                "roles": [{"role_id": "ideator", "capability_id": "brainstorm"}],
                                "steps": [{"step_id": "collect", "title": "Collect"}],
                            }
                        },
                    )
                ],
            )

            dispatched = service.dispatch_ready_nodes(mission.mission_id, limit=1)
            self.assertEqual(len(dispatched), 1)
            branch = dispatched[0]
            session_id = str(branch["input_payload"].get("workflow_session_id") or "")
            self.assertTrue(session_id)

            service.record_branch_result(
                mission.mission_id,
                branch["branch_id"],
                ok=True,
                result_ref="artifact:brainstorm",
                result_payload={"summary": "workflow branch completed"},
            )

            session_file = root / "orchestrator" / "workflow_sessions" / session_id / "session.json"
            payload = json.loads(session_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["active_step"], "")
            self.assertEqual(payload["metadata"]["orchestrator_result"]["result_ref"], "artifact:brainstorm")

            summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(summary["branches"][0]["workflow_session"]["status"], "completed")
            self.assertEqual(summary["nodes"][0]["workflow_session"]["status"], "completed")

    def test_record_branch_result_accepts_runtime_verdict_writeback_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="runtime_verdict",
                title="Runtime verdict contract",
                nodes=[
                    MissionNode(
                        node_id="approve_me",
                        kind="brainstorm",
                        title="Approve me",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "approval.runtime_verdict",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "draft", "title": "Draft"}],
                            },
                            "approval": {"required": True},
                        },
                    )
                ],
            )

            branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            result = service.record_branch_result(
                mission.mission_id,
                branch["branch_id"],
                runtime_verdict=RuntimeVerdict(
                    status="completed",
                    terminal=True,
                    result_ok=True,
                    result_ref="artifact:runtime-verdict",
                    result_payload={"summary": "ready for writeback"},
                    metadata={"bridge": "test"},
                ),
            )

            verdict = result["runtime_verdict"]
            self.assertEqual(verdict["status"], "awaiting_approval")
            self.assertFalse(verdict["terminal"])
            self.assertTrue(verdict["result_ok"])
            self.assertEqual(verdict["metadata"]["writeback"]["node_status"], "blocked")
            self.assertEqual(verdict["metadata"]["writeback"]["mission_status"], "awaiting_decision")
            self.assertEqual(result["process_writeback"]["runtime_status"], "awaiting_approval")
            self.assertEqual(result["process_writeback"]["workflow_session_status"], "awaiting_approval")

    def test_record_branch_result_accepts_process_execution_outcome_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="process_outcome",
                title="Process outcome contract",
                nodes=[MissionNode(node_id="ship", kind="brainstorm", title="Ship")],
            )

            branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            result = service.record_branch_result(
                mission.mission_id,
                branch["branch_id"],
                process_outcome=ProcessExecutionOutcome(
                    status="completed",
                    terminal=True,
                    result_ok=True,
                    result_ref="artifact:process-outcome",
                    result_payload={"summary": "completed through process outcome"},
                    metadata={"bridge": "test_process_outcome"},
                ),
            )

            self.assertEqual(result["runtime_verdict"]["status"], "completed")
            self.assertEqual(result["process_outcome"]["metadata"]["bridge"], "test_process_outcome")
            self.assertEqual(result["process_writeback"]["branch_status"], "succeeded")
            self.assertEqual(result["process_writeback"]["node_status"], "done")
            self.assertEqual(result["process_writeback"]["mission_status"], "completed")

    def test_process_writeback_projection_maps_repairing_to_non_terminal_runtime_status(self) -> None:
        projection = ProcessWritebackProjection.from_runtime_state(
            verdict=RuntimeVerdict(status="failed", terminal=True, result_ok=False),
            branch_status="failed",
            node_status="repairing",
            mission_status="running",
            workflow_session_status="repairing",
        )
        verdict = projection.apply_to_runtime_verdict(
            RuntimeVerdict(status="failed", terminal=True, result_ok=False)
        )

        self.assertEqual(projection.runtime_status, "repair_scheduled")
        self.assertFalse(projection.terminal)
        self.assertEqual(verdict.status, "repair_scheduled")
        self.assertFalse(verdict.terminal)
        self.assertEqual(verdict.metadata["writeback"]["workflow_session_status"], "repairing")

    def test_process_runtime_governance_contracts_are_native_and_normalized(self) -> None:
        approval = ApprovalTicket(approval_type="invalid", status="invalid")
        verification = VerificationReceipt(decision="invalid")
        recovery = RecoveryDirective(action="invalid", retry_budget=-3, backoff_seconds=-1)

        self.assertEqual(approval.approval_type, "human_gate")
        self.assertEqual(approval.status, "pending")
        self.assertEqual(verification.decision, "pass")
        self.assertEqual(recovery.action, "continue")
        self.assertEqual(recovery.retry_budget, 0)
        self.assertEqual(recovery.backoff_seconds, 0)

    def test_record_branch_result_failure_marks_workflow_session_repairing_when_recovery_is_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="workflow",
                title="Workflow branch failure",
                nodes=[
                    MissionNode(
                        node_id="generate",
                        kind="brainstorm",
                        title="Generate",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "brainstorm.generate",
                                "kind": "local_collaboration",
                                "roles": [{"role_id": "ideator", "capability_id": "brainstorm"}],
                                "steps": [{"step_id": "collect", "title": "Collect"}],
                            }
                        },
                    )
                ],
            )

            dispatched = service.dispatch_ready_nodes(mission.mission_id, limit=1)
            self.assertEqual(len(dispatched), 1)
            branch = dispatched[0]
            session_id = str(branch["input_payload"].get("workflow_session_id") or "")
            self.assertTrue(session_id)

            service.record_branch_result(
                mission.mission_id,
                branch["branch_id"],
                ok=False,
                result_ref="artifact:error",
                result_payload={"summary": "workflow branch failed"},
            )

            session_file = root / "orchestrator" / "workflow_sessions" / session_id / "session.json"
            payload = json.loads(session_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "repairing")
            self.assertEqual(payload["metadata"]["orchestrator_result"]["branch_status"], "failed")

    def test_approval_gate_blocks_mission_until_resolved(self) -> None:
        class AcceptJudge(OrchestratorJudgeAdapter):
            def evaluate_node(self, mission_id: str, node_id: str, artifacts: list[dict] | None = None) -> JudgeVerdict:
                return JudgeVerdict(decision="accept", reason="looks_good")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = OrchestratorService(
                FileMissionStore(root / "orchestrator"),
                FileLedgerEventStore(root / "orchestrator"),
                judge=AcceptJudge(),
            )
            mission = service.create_mission(
                mission_type="approval_gate",
                title="Approval gated node",
                nodes=[
                    MissionNode(
                        node_id="review",
                        kind="brainstorm",
                        title="Review",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "approval.review",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "draft", "title": "Draft"}],
                            },
                            "approval": {"required": True},
                        },
                    )
                ],
            )

            branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            result = service.record_branch_result(
                mission.mission_id,
                branch["branch_id"],
                ok=True,
                result_ref="artifact:approval",
                result_payload={"summary": "needs human approval"},
            )

            self.assertEqual(result["node_status"], "blocked")
            self.assertEqual(result["mission_status"], "awaiting_decision")
            reloaded = service.get_mission(mission.mission_id)
            assert reloaded is not None
            self.assertTrue(bool(reloaded.nodes[0].metadata.get("approval_pending")))
            summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(summary["nodes"][0]["workflow_session"]["status"], "awaiting_approval")
            events = service.list_delivery_events(mission.mission_id)
            approval_events = [event for event in events if event["event_type"] == "approval_requested"]
            self.assertEqual(len(approval_events), 1)
            self.assertTrue(approval_events[0]["payload"]["approval_policy"]["required"])

    def test_approval_gate_approve_resumes_into_judge(self) -> None:
        class AcceptJudge(OrchestratorJudgeAdapter):
            def evaluate_node(self, mission_id: str, node_id: str, artifacts: list[dict] | None = None) -> JudgeVerdict:
                return JudgeVerdict(decision="accept", reason="approved_and_verified")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = OrchestratorService(
                FileMissionStore(root / "orchestrator"),
                FileLedgerEventStore(root / "orchestrator"),
                judge=AcceptJudge(),
            )
            mission = service.create_mission(
                mission_type="approval_gate",
                title="Approval resume",
                nodes=[
                    MissionNode(
                        node_id="review",
                        kind="brainstorm",
                        title="Review",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "approval.review",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "draft", "title": "Draft"}],
                            },
                            "approval": {"required": True},
                        },
                    )
                ],
            )

            branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            service.record_branch_result(
                mission.mission_id,
                branch["branch_id"],
                ok=True,
                result_ref="artifact:approval",
                result_payload={"summary": "ready for approval"},
            )
            resolution = service.resolve_node_approval(
                mission.mission_id,
                "review",
                decision="approve",
                note="approved by test",
            )

            self.assertEqual(resolution["node_status"], "done")
            self.assertEqual(resolution["mission_status"], "completed")
            self.assertEqual(resolution["judge_decision"], "accept")
            reloaded = service.get_mission(mission.mission_id)
            assert reloaded is not None
            self.assertFalse(bool(reloaded.nodes[0].metadata.get("approval_pending")))
            summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(summary["nodes"][0]["workflow_session"]["status"], "completed")
            events = service.list_delivery_events(mission.mission_id)
            resolved = [event for event in events if event["event_type"] == "approval_resolved"]
            self.assertEqual(len(resolved), 1)

    def test_verification_gate_can_be_disabled_by_workflow_ir(self) -> None:
        class RepairJudge(OrchestratorJudgeAdapter):
            def evaluate_node(self, mission_id: str, node_id: str, artifacts: list[dict] | None = None) -> JudgeVerdict:
                return JudgeVerdict(decision="repair", reason="should_not_run")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = OrchestratorService(
                FileMissionStore(root / "orchestrator"),
                FileLedgerEventStore(root / "orchestrator"),
                judge=RepairJudge(),
            )
            mission = service.create_mission(
                mission_type="verification_gate",
                title="Verification disabled",
                nodes=[
                    MissionNode(
                        node_id="ship",
                        kind="brainstorm",
                        title="Ship",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "verification.skip",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "draft", "title": "Draft"}],
                            },
                            "verification": {"required": False},
                        },
                    )
                ],
            )

            branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            result = service.record_branch_result(
                mission.mission_id,
                branch["branch_id"],
                ok=True,
                result_ref="artifact:skip-verify",
                result_payload={"summary": "verification skipped by workflow ir"},
            )

            self.assertEqual(result["node_status"], "done")
            self.assertEqual(result["mission_status"], "completed")
            reloaded = service.get_mission(mission.mission_id)
            assert reloaded is not None
            self.assertEqual(reloaded.nodes[0].status, "done")
            events = service.list_delivery_events(mission.mission_id)
            skipped = [event for event in events if event["event_type"] == "verification_skipped"]
            verdicts = [event for event in events if event["event_type"] == "judge_verdict"]
            self.assertEqual(len(skipped), 1)
            self.assertEqual(len(verdicts), 0)
            self.assertEqual(skipped[0]["payload"]["verification_policy"]["mode"], "skip")

    def test_retry_step_reuses_existing_workflow_session_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="retry_step",
                title="Retry step reuses session",
                nodes=[
                    MissionNode(
                        node_id="retry",
                        kind="brainstorm",
                        title="Retry",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "retry.step",
                                "kind": "local_collaboration",
                                "steps": [
                                    {"step_id": "draft", "title": "Draft"},
                                    {"step_id": "review", "title": "Review"},
                                ],
                            },
                            "verification": {"required": False},
                            "recovery": {"kind": "retry_step", "resume_from": "draft", "max_attempts": 1},
                        },
                    )
                ],
            )

            first_branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            first_session_id = str(first_branch["metadata"].get("workflow_session_id") or "")
            self.assertTrue(first_session_id)

            first = service.record_branch_result(
                mission.mission_id,
                first_branch["branch_id"],
                ok=False,
                result_ref="artifact:first",
                result_payload={"summary": "retry from draft"},
            )
            self.assertEqual(first["node_status"], "repairing")

            after_failure = service.summarize_mission(mission.mission_id)
            self.assertEqual(after_failure["nodes"][0]["workflow_session"]["status"], "repairing")
            self.assertEqual(after_failure["nodes"][0]["workflow_session"]["active_step"], "draft")

            tick = service.tick(mission.mission_id)
            self.assertEqual(tick["activated_node_count"], 1)
            second_branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            second_session_id = str(second_branch["metadata"].get("workflow_session_id") or "")
            self.assertEqual(second_session_id, first_session_id)

            second = service.record_branch_result(
                mission.mission_id,
                second_branch["branch_id"],
                ok=True,
                result_ref="artifact:second",
                result_payload={"summary": "recovered from retry_step"},
            )
            self.assertEqual(second["node_status"], "done")
            summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["nodes"][0]["workflow_session"]["status"], "completed")
            resumed = [event for event in service.list_delivery_events(mission.mission_id) if event["event_type"] == "workflow_session_resumed"]
            self.assertEqual(len(resumed), 1)
            self.assertEqual(resumed[0]["payload"]["resume_from"], "draft")

    def test_repair_branch_creates_fresh_workflow_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._service(root)
            mission = service.create_mission(
                mission_type="repair_branch",
                title="Repair branch creates new session",
                nodes=[
                    MissionNode(
                        node_id="repair",
                        kind="brainstorm",
                        title="Repair",
                        runtime_plan={
                            "workflow_template": {
                                "template_id": "repair.branch",
                                "kind": "local_collaboration",
                                "steps": [{"step_id": "draft", "title": "Draft"}],
                            },
                            "verification": {"required": False},
                            "recovery": {"kind": "repair", "max_attempts": 1},
                        },
                    )
                ],
            )

            first_branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            first_session_id = str(first_branch["metadata"].get("workflow_session_id") or "")
            self.assertTrue(first_session_id)

            first = service.record_branch_result(
                mission.mission_id,
                first_branch["branch_id"],
                ok=False,
                result_ref="artifact:first",
                result_payload={"summary": "repair branch requested"},
            )
            self.assertEqual(first["node_status"], "repairing")

            tick = service.tick(mission.mission_id)
            self.assertEqual(tick["activated_node_count"], 1)
            second_branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            second_session_id = str(second_branch["metadata"].get("workflow_session_id") or "")
            self.assertTrue(second_session_id)
            self.assertNotEqual(second_session_id, first_session_id)


if __name__ == "__main__":
    unittest.main()
