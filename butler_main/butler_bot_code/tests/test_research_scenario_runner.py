from __future__ import annotations

import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from research.manager.code.research_manager.contracts import RESEARCH_UNITS, ResearchInvocation
from research.manager.code.research_manager.services.scenario_runner import build_scenario_dispatch


class ResearchScenarioRunnerTests(unittest.TestCase):
    def test_brainstorm_prepare_starts_from_capture(self) -> None:
        invocation = ResearchInvocation(
            entrypoint="talk",
            unit_id="paper_manager.project_next_step_planning",
            goal="brainstorm next step",
        )
        unit = RESEARCH_UNITS[invocation.unit_id]
        payload = build_scenario_dispatch(invocation, unit)

        self.assertEqual(payload["scenario"]["scenario_id"], "brainstorm")
        self.assertEqual(payload["active_step"]["step_id"], "capture")
        self.assertEqual(payload["active_step"]["next_step_id"], "cluster")
        self.assertIn("recommended_direction", payload["output_template"]["required_fields"])
        self.assertIn("problem_frame", payload["active_step"]["step_output_fields"])

    def test_paper_discovery_advance_moves_to_query_plan(self) -> None:
        invocation = ResearchInvocation(
            entrypoint="orchestrator",
            unit_id="paper_finding.daily_paper_discovery",
            goal="daily scan",
            metadata={
                "scenario_action": "advance",
                "workflow_cursor": {"current_step_id": "topic_lock"},
            },
        )
        unit = RESEARCH_UNITS[invocation.unit_id]
        payload = build_scenario_dispatch(invocation, unit)

        self.assertEqual(payload["active_step"]["step_id"], "query_plan")
        self.assertEqual(payload["active_step"]["next_step_id"], "search")
        self.assertEqual(payload["workflow_cursor"]["current_step_id"], "query_plan")
        self.assertEqual(payload["handoff_receipt"]["target_step_id"], "search")

    def test_idea_loop_retry_routes_final_verify_to_recover(self) -> None:
        invocation = ResearchInvocation(
            entrypoint="codex",
            unit_id="research_idea.idea_loop",
            goal="improve result",
            metadata={
                "scenario_action": "advance",
                "decision": "retry",
                "workflow_cursor": {"current_step_id": "final_verify"},
            },
        )
        unit = RESEARCH_UNITS[invocation.unit_id]
        payload = build_scenario_dispatch(invocation, unit)

        self.assertEqual(payload["active_step"]["step_id"], "recover")
        self.assertEqual(payload["decision_receipt"]["decision"], "retry")
        self.assertTrue(payload["decision_receipt"]["retryable"])
        self.assertEqual(payload["workflow_cursor"]["current_step_id"], "recover")


if __name__ == "__main__":
    unittest.main()
