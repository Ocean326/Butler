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

from butler_main.orchestrator import OrchestratorCampaignService  # noqa: E402
from butler_main.orchestrator.interfaces.campaign_dashboard import (  # noqa: E402
    build_campaign_dashboard_payload,
    main as campaign_dashboard_main,
    render_campaign_dashboard_html,
)


class OrchestratorCampaignDashboardTests(unittest.TestCase):
    def _workspace(self) -> tempfile.TemporaryDirectory[str]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
        return tmp

    def test_dashboard_payload_exposes_additive_query_aggregates(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = OrchestratorCampaignService()
            created = service.create_campaign(
                workspace,
                {
                    "top_level_goal": "Render campaign dashboard",
                    "materials": ["docs/09"],
                    "hard_constraints": ["keep dashboard read-only"],
                    "iteration_budget": {"max_iterations": 3},
                },
            )
            service.resume_campaign(workspace, created["campaign_id"])
            payload = build_campaign_dashboard_payload(workspace, created["campaign_id"])
            self.assertIn("phase_timeline", payload)
            self.assertIn("verdict_summary", payload)
            self.assertIn("session_evidence", payload)
            html = render_campaign_dashboard_html(payload)
            self.assertIn(created["campaign_id"], html)
            self.assertIn("Campaign Dashboard", html)
            self.assertIn("Session Snapshot", html)

    def test_dashboard_main_writes_static_html(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = OrchestratorCampaignService()
            created = service.create_campaign(
                workspace,
                {
                    "top_level_goal": "Write dashboard html",
                    "materials": ["docs/05"],
                    "hard_constraints": ["single campaign only"],
                },
            )
            output_path = Path(workspace) / "campaign_dashboard.html"
            exit_code = campaign_dashboard_main(
                [
                    "--workspace",
                    workspace,
                    "--campaign-id",
                    created["campaign_id"],
                    "--output",
                    str(output_path),
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())
            html = output_path.read_text(encoding="utf-8")
            self.assertIn(created["campaign_id"], html)
            self.assertIn("Event Timeline", html)


if __name__ == "__main__":
    unittest.main()
