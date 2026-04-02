from __future__ import annotations

import contextlib
import io
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

from butler_main.orchestrator import OrchestratorCampaignService  # noqa: E402
from butler_main.orchestrator.observe import main as observe_main  # noqa: E402
from butler_main.orchestrator.query_service import OrchestratorQueryService  # noqa: E402


class OrchestratorCampaignObserveTests(unittest.TestCase):
    def _workspace(self) -> tempfile.TemporaryDirectory[str]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
        return tmp

    def test_query_service_exposes_campaign_views_and_window(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            campaign_service = OrchestratorCampaignService()
            query = OrchestratorQueryService()
            created = campaign_service.create_campaign(
                workspace,
                {
                    "top_level_goal": "Make campaign observable",
                    "materials": ["docs/05", "docs/08", "docs/09"],
                    "hard_constraints": ["goal immutable"],
                    "iteration_budget": {"max_iterations": 2},
                },
            )

            campaigns = query.list_campaigns(workspace, limit=10)
            self.assertEqual(campaigns[0]["campaign_view"]["campaign_id"], created["campaign_id"])
            self.assertEqual(campaigns[0]["campaign_view"]["artifact_count"], 0)
            self.assertEqual(
                campaigns[0]["campaign_view"]["canonical_session_id"],
                created["canonical_session_id"],
            )

            status = query.get_campaign_status(workspace, created["campaign_id"])
            self.assertEqual(status["campaign_view"]["campaign_id"], created["campaign_id"])
            self.assertEqual(status["campaign_view"]["workflow_session_id"], created["canonical_session_id"])
            self.assertEqual(status["campaign_view"]["canonical_session_id"], created["canonical_session_id"])
            self.assertEqual(status.get("mission_view", {}), {})
            self.assertEqual(status["session_view"]["workflow_session_id"], created["canonical_session_id"])
            self.assertEqual(len(status["artifacts"]), 0)
            self.assertEqual(status["campaign_view"]["artifact_count"], 0)
            self.assertEqual(status["campaign_view"]["verdict_count"], 0)
            self.assertIn("workflow_session", status)
            self.assertIn("task_summary", status)
            self.assertEqual(status["task_summary"]["progress"]["artifact_count"], 0)
            self.assertEqual(status["planning_summary"]["mode_id"], "unknown")
            self.assertEqual(status["governance_summary"]["risk_level"], "medium")
            self.assertIn("background_tasks", status["bundle_root"])
            self.assertTrue(status["bundle_manifest"].endswith("manifest.json"))
            self.assertEqual(status["runtime_mode"], "deterministic")
            self.assertEqual(status["pending_checks"], [])
            self.assertEqual(status["execution_state"], "ready")
            self.assertEqual(status["closure_state"], "open")
            self.assertTrue(bool(status["progress_reason"]))
            self.assertEqual(status["latest_stage_summary"], "")

            events = query.list_campaign_events(workspace, created["campaign_id"], limit=20)
            self.assertTrue(any(item["event_type"] == "campaign_created" for item in events))

            window = query.get_campaign_observation_window(workspace, created["campaign_id"])
            self.assertEqual(window["campaign_view"]["campaign_id"], created["campaign_id"])
            self.assertEqual(window["campaign_evidence"]["artifact_count"], 0)
            self.assertTrue(window["campaign_evidence"]["goal_immutable_ok"])
            self.assertTrue(window["campaign_evidence"]["hard_constraints_immutable_ok"])
            self.assertFalse(window["campaign_evidence"]["mission_linked"])
            self.assertTrue(window["campaign_evidence"]["session_linked"])
            self.assertEqual(window["stable_evidence"]["workflow_session_count"], 1)
            self.assertEqual(window["stable_evidence"]["workflow_session_id"], created["canonical_session_id"])
            self.assertIn("workflow_session", window)

            resumed = campaign_service.resume_campaign(workspace, created["campaign_id"])
            resumed_window = query.get_campaign_observation_window(workspace, created["campaign_id"])
            self.assertEqual(resumed_window["campaign_view"]["verdict_count"], 1)
            self.assertEqual(
                resumed_window["campaign_evidence"]["working_contract_version"],
                resumed["working_contract"]["version"],
            )
            self.assertEqual(resumed_window["session_view"]["active_step"], "turn")
            resumed_status = query.get_campaign_status(workspace, created["campaign_id"])
            self.assertEqual(resumed_status["latest_acceptance_decision"], "continue")
            self.assertEqual(resumed_status["execution_state"], "running")
            self.assertEqual(resumed_status["closure_state"], "stage_delivered")
            self.assertTrue(bool(resumed_status["not_done_reason"]))
            self.assertEqual(resumed_status["closure_reason"], "")

    def test_query_service_separates_execution_and_closure_states_for_pending_checks(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            campaign_service = OrchestratorCampaignService()
            query = OrchestratorQueryService()
            created = campaign_service.create_campaign(
                workspace,
                {
                    "top_level_goal": "Separate progression from closure",
                    "materials": ["docs/05"],
                    "metadata": {
                        "strict_acceptance_required": True,
                        "pending_correctness_checks": ["ssh_reachable", "review_packet_signed"],
                    },
                },
            )

            status = query.get_campaign_status(workspace, created["campaign_id"])
            self.assertEqual(status["execution_state"], "ready")
            self.assertEqual(status["closure_state"], "open")
            self.assertEqual(status["operational_checks_pending"], ["ssh_reachable"])
            self.assertEqual(status["closure_checks_pending"], ["review_packet_signed"])
            self.assertIn("ssh_reachable", status["acceptance_requirements_remaining"])
            self.assertIn("review_packet_signed", status["acceptance_requirements_remaining"])
            self.assertEqual(status["task_summary"]["progress"]["status"], "draft")
            self.assertEqual(status["task_summary"]["closure"]["state"], "open")
            self.assertEqual(status["task_summary"]["next_action"], "run the first supervisor turn")

    def test_query_service_exposes_governance_updates_in_task_summary(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            campaign_service = OrchestratorCampaignService()
            query = OrchestratorQueryService()
            created = campaign_service.create_campaign(
                workspace,
                {
                    "top_level_goal": "Expose governance summary",
                    "materials": ["docs/05"],
                    "metadata": {
                        "planning_contract": {"mode_id": "research"},
                    },
                },
            )

            campaign_service.update_campaign_metadata(
                workspace,
                created["campaign_id"],
                {"governance_contract": {"risk_level": "high", "approval_state": "requested"}},
            )

            status = query.get_campaign_status(workspace, created["campaign_id"])
            self.assertEqual(status["governance_summary"]["risk_level"], "high")
            self.assertEqual(status["task_summary"]["risk"]["approval_state"], "requested")
            self.assertEqual(status["task_summary"]["mode_id"], "research")

    def test_observe_cli_supports_campaign_commands(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            campaign_service = OrchestratorCampaignService()
            created = campaign_service.create_campaign(
                workspace,
                {
                    "top_level_goal": "Expose campaign observe CLI",
                    "materials": ["docs/05"],
                    "hard_constraints": ["stay single-flow"],
                },
            )

            for argv, expected_key in (
                (["campaigns", "--workspace", workspace], "campaign_view"),
                (["campaign", "--workspace", workspace, "--campaign-id", created["campaign_id"]], "campaign_view"),
                (["campaign-artifacts", "--workspace", workspace, "--campaign-id", created["campaign_id"]], None),
                (["campaign-events", "--workspace", workspace, "--campaign-id", created["campaign_id"]], None),
                (["campaign-window", "--workspace", workspace, "--campaign-id", created["campaign_id"]], "campaign_evidence"),
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = observe_main(argv)
                self.assertEqual(exit_code, 0)
                payload = json.loads(buffer.getvalue())
                if expected_key is not None:
                    if isinstance(payload, list):
                        self.assertIn(expected_key, payload[0])
                    else:
                        self.assertIn(expected_key, payload)


if __name__ == "__main__":
    unittest.main()
