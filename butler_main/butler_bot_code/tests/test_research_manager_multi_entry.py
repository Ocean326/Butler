from __future__ import annotations

import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from research.manager.code.research_manager import FileResearchScenarioInstanceStore, ResearchManager, normalize_unit_id
from research.manager.code.research_manager.interfaces import (
    build_codex_invocation,
    build_orchestrator_invocation,
    build_talk_invocation,
    invoke_from_codex,
    invoke_from_orchestrator,
    invoke_from_talk,
)
from butler_main.butler_bot_code.tests._tmpdir import test_workdir


class ResearchManagerMultiEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_ctx = test_workdir("research_manager_multi_entry")
        self._tmp_root = self._tmp_ctx.__enter__()
        self.manager = ResearchManager(
            scenario_instance_store=FileResearchScenarioInstanceStore(self._tmp_root / "scenario_instances")
        )

    def tearDown(self) -> None:
        self._tmp_ctx.__exit__(None, None, None)

    def test_unit_id_normalization_accepts_hyphen_and_slash(self) -> None:
        self.assertEqual(
            normalize_unit_id("paper-finding/daily-paper-discovery"),
            "paper_finding.daily_paper_discovery",
        )

    def test_orchestrator_without_unit_uses_default_research_unit(self) -> None:
        result = invoke_from_orchestrator(self.manager, goal="daily scan")
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.unit_id, "paper_finding.daily_paper_discovery")
        self.assertEqual(result.route["entrypoint"], "orchestrator")
        self.assertEqual(result.route["handler_name"], "handle_daily_paper_discovery")
        self.assertIn("paper shortlist", result.acceptance.evidence[-1])

    def test_talk_and_codex_share_same_business_core(self) -> None:
        talk_result = invoke_from_talk(
            self.manager,
            goal="plan the next project step",
            unit_id="paper-manager/project-next-step-planning",
        )
        codex_result = invoke_from_codex(
            self.manager,
            goal="plan the next project step",
            unit_id="paper_manager.project_next_step_planning",
        )
        self.assertEqual(talk_result.status, "ready")
        self.assertEqual(codex_result.status, "ready")
        self.assertEqual(talk_result.unit_id, codex_result.unit_id)
        self.assertEqual(talk_result.acceptance.next_action, codex_result.acceptance.next_action)
        self.assertEqual(talk_result.route["handler_name"], codex_result.route["handler_name"])
        self.assertEqual(
            talk_result.payload["dispatch"]["expected_fields"],
            codex_result.payload["dispatch"]["expected_fields"],
        )
        self.assertNotEqual(talk_result.route["entrypoint"], codex_result.route["entrypoint"])

    def test_talk_builders_return_same_invocation_shape(self) -> None:
        orchestrator = build_orchestrator_invocation(goal="scan")
        talk = build_talk_invocation(goal="scan", unit_id="paper_manager.progress_summary")
        codex = build_codex_invocation(goal="scan", unit_id="paper_manager.progress_summary")
        self.assertEqual(orchestrator.entrypoint, "orchestrator")
        self.assertEqual(talk.entrypoint, "talk")
        self.assertEqual(codex.entrypoint, "codex")
        self.assertEqual(talk.unit_id, "paper_manager.progress_summary")
        self.assertEqual(codex.unit_id, "paper_manager.progress_summary")

    def test_codex_without_explicit_unit_is_blocked(self) -> None:
        result = invoke_from_codex(self.manager, goal="do something")
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.acceptance.failure_class, "context_missing")

    def test_result_contains_unit_root_for_architecture_traceability(self) -> None:
        result = invoke_from_talk(
            self.manager,
            goal="summarize progress",
            unit_id="paper_manager.progress_summary",
        )
        self.assertEqual(
            result.route["unit_root"],
            "butler_main/incubation/research/units/paper_manager/progress_summary",
        )
        self.assertEqual(
            result.payload["dispatch"]["unit_root"],
            "butler_main/incubation/research/units/paper_manager/progress_summary",
        )

    def test_result_includes_scenario_workflow_projection(self) -> None:
        result = invoke_from_orchestrator(self.manager, goal="daily scan")
        scenario = result.payload["dispatch"]["scenario"]
        projection = result.payload["dispatch"]["workflow_projection"]
        self.assertEqual(scenario["scenario_id"], "paper_discovery")
        self.assertEqual(projection["spec"]["workflow_id"], "paper_discovery_round")
        self.assertEqual(projection["cursor"]["workflow_id"], "paper_discovery_round")

    def test_result_includes_active_step_and_receipts_from_scenario_runner(self) -> None:
        result = invoke_from_talk(
            self.manager,
            goal="plan the next project step",
            unit_id="paper_manager.project_next_step_planning",
        )
        dispatch = result.payload["dispatch"]
        self.assertEqual(dispatch["active_step"]["step_id"], "capture")
        self.assertEqual(dispatch["step_receipt"]["step_id"], "capture")
        self.assertEqual(dispatch["handoff_receipt"]["target_step_id"], "cluster")
        self.assertEqual(dispatch["decision_receipt"]["decision"], "proceed")
        self.assertIn("recommended_direction", dispatch["output_template"]["required_fields"])
        self.assertTrue(dispatch["scenario_instance"]["scenario_instance_id"])


if __name__ == "__main__":
    unittest.main()
