from __future__ import annotations

import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.butler_bot_code.tests._tmpdir import test_workdir
from research.manager.code.research_manager import FileResearchScenarioInstanceStore, ResearchManager
from research.manager.code.research_manager.interfaces import invoke_from_codex, invoke_from_talk


class ResearchScenarioInstanceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_ctx = test_workdir("research_scenario_instance")
        self._tmp_root = self._tmp_ctx.__enter__()
        self.manager = ResearchManager(
            scenario_instance_store=FileResearchScenarioInstanceStore(self._tmp_root / "scenario_instances")
        )

    def tearDown(self) -> None:
        self._tmp_ctx.__exit__(None, None, None)

    def test_same_session_shares_same_scenario_instance_across_entrypoints(self) -> None:
        talk_result = invoke_from_talk(
            self.manager,
            goal="plan the next project step",
            unit_id="paper_manager.project_next_step_planning",
            session_id="research-thread-1",
        )
        codex_result = invoke_from_codex(
            self.manager,
            goal="plan the next project step",
            unit_id="paper_manager.project_next_step_planning",
            session_id="research-thread-1",
        )

        first = talk_result.payload["dispatch"]["scenario_instance"]
        second = codex_result.payload["dispatch"]["scenario_instance"]
        self.assertEqual(first["scenario_instance_id"], second["scenario_instance_id"])
        self.assertIn("talk", second["entrypoints_seen"])
        self.assertIn("codex", second["entrypoints_seen"])

    def test_existing_cursor_is_reused_when_advancing_same_instance(self) -> None:
        first = invoke_from_talk(
            self.manager,
            goal="plan the next project step",
            unit_id="paper_manager.project_next_step_planning",
            session_id="research-thread-advance",
        )
        first_instance = first.payload["dispatch"]["scenario_instance"]

        second = invoke_from_codex(
            self.manager,
            goal="plan the next project step",
            unit_id="paper_manager.project_next_step_planning",
            session_id="research-thread-advance",
            metadata={"scenario_action": "advance"},
        )
        second_dispatch = second.payload["dispatch"]
        second_instance = second_dispatch["scenario_instance"]

        self.assertEqual(first_instance["scenario_instance_id"], second_instance["scenario_instance_id"])
        self.assertEqual(second_dispatch["active_step"]["step_id"], "cluster")
        self.assertEqual(second_instance["current_step_id"], "cluster")
        self.assertEqual(second_instance["workflow_cursor"]["current_step_id"], "cluster")


if __name__ == "__main__":
    unittest.main()
