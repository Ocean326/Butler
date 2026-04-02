from __future__ import annotations

import sys
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

from agents_os.runtime import AcceptanceReceipt  # noqa: E402
from butler_main.orchestrator import build_research_collaboration_projection  # noqa: E402
from butler_main.research.manager.code.research_manager import ResearchResult  # noqa: E402


class ResearchCollaborationProjectionTests(unittest.TestCase):
    def test_build_research_collaboration_projection_normalizes_research_dispatch(self) -> None:
        result = ResearchResult(
            status="ready",
            entrypoint="codex",
            unit_id="paper_manager.project_next_step_planning",
            summary="Prepared project next-step planning via codex",
            acceptance=AcceptanceReceipt(
                goal_achieved=False,
                summary="Prepared project next-step planning via codex",
                evidence=["manager_id=research_manager"],
                artifacts=["artifact:planning-note"],
                uncertainties=[],
                next_action="finish capture and hand off to cluster",
                failure_class="",
            ),
            route={"scenario_instance_id": "scenario_instance_1"},
            payload={
                "dispatch": {
                    "scenario": {"scenario_id": "brainstorm"},
                    "scenario_instance": {
                        "scenario_instance_id": "scenario_instance_1",
                        "scenario_id": "brainstorm",
                        "workflow_id": "brainstorm_session",
                        "current_step_id": "capture",
                        "latest_decision": "proceed",
                    },
                    "workflow_cursor": {
                        "workflow_id": "brainstorm_session",
                        "current_step_id": "capture",
                    },
                    "active_step": {"step_id": "capture"},
                    "step_receipt": {
                        "step_id": "capture",
                        "workflow_id": "brainstorm_session",
                        "worker_name": "research_manager:brainstorm",
                        "process_role": "manager",
                        "step_kind": "prepare",
                        "status": "pending",
                        "metadata": {
                            "artifact_slot": "research.scenario.brainstorm.capture",
                            "step_output_fields": ["problem_frame"],
                        },
                    },
                    "handoff_receipt": {
                        "workflow_id": "brainstorm_session",
                        "source_step_id": "capture",
                        "target_step_id": "cluster",
                        "producer": "manager",
                        "consumer": "planner",
                        "handoff_kind": "scenario_step",
                        "status": "pending",
                        "summary": "handoff from capture to cluster",
                        "artifacts": ["artifact:planning-note"],
                        "handoff_ready": False,
                        "next_action": "finish Capture Problem Frame and hand off to cluster",
                        "metadata": {"scenario_id": "brainstorm"},
                    },
                    "decision_receipt": {
                        "workflow_id": "brainstorm_session",
                        "decision_id": "decision_1",
                        "step_id": "capture",
                        "producer": "research_manager",
                        "status": "pending",
                        "decision": "proceed",
                        "decision_reason": "scenario_action=prepare",
                        "retryable": False,
                        "next_action": "finish Capture Problem Frame and hand off to cluster",
                        "resume_from": "cluster",
                        "artifacts": ["artifact:planning-note"],
                        "metadata": {"scenario_id": "brainstorm"},
                    },
                }
            },
        )

        projection = build_research_collaboration_projection(
            workflow_session_id="workflow_session_1",
            research_unit_id="paper_manager.project_next_step_planning",
            scenario_action="prepare",
            result=result,
        )

        self.assertIsNotNone(projection)
        assert projection is not None
        self.assertEqual(projection.workflow_session_id, "workflow_session_1")
        self.assertEqual(projection.shared_state_patch["research_unit_id"], "paper_manager.project_next_step_planning")
        self.assertEqual(projection.shared_state_patch["scenario_instance_id"], "scenario_instance_1")
        self.assertEqual(projection.active_step, "capture")
        self.assertEqual([item.ref for item in projection.artifacts], [
            "artifact:planning-note",
            "scenario_instance:scenario_instance_1",
        ])
        self.assertEqual([item.dedupe_key for item in projection.artifacts], [
            "artifact::capture::artifact:planning-note",
            "artifact::capture::scenario_instance:scenario_instance_1",
        ])
        self.assertIsNotNone(projection.step_ownership)
        self.assertEqual(projection.step_ownership.owner_role_id, "manager")
        self.assertIsNotNone(projection.role_handoff)
        self.assertEqual(projection.role_handoff.target_role_id, "planner")
        self.assertEqual(
            projection.role_handoff.dedupe_key,
            "handoff::brainstorm_session::capture::cluster::manager::planner::scenario_step",
        )
        self.assertIsNotNone(projection.mailbox_message)
        self.assertEqual(projection.mailbox_message.recipient_role_id, "planner")
        self.assertEqual(
            projection.mailbox_message.dedupe_key,
            "mailbox::handoff::brainstorm_session::capture::cluster::manager::planner::scenario_step",
        )
        self.assertIsNotNone(projection.join_contract)
        self.assertEqual(projection.join_contract.merge_strategy, "proceed")
        self.assertEqual(projection.join_contract.source_role_ids, ["research_manager", "manager"])
        self.assertEqual(projection.join_contract.dedupe_key, "join::decision_1")


if __name__ == "__main__":
    unittest.main()
