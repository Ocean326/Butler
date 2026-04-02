from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.orchestrator.demo_fixtures import build_demo_fixture, list_demo_fixture_ids  # noqa: E402
from butler_main.orchestrator import smoke  # noqa: E402


class OrchestratorSmokeTests(unittest.TestCase):
    def _workspace(self) -> tempfile.TemporaryDirectory[str]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
        return tmp

    def test_lane_d_demo_fixture_ids_are_frozen(self) -> None:
        self.assertEqual(
            list_demo_fixture_ids(),
            ("superpowers_like", "openfang_inspired"),
        )
        superpowers = build_demo_fixture("superpowers_like")
        openfang = build_demo_fixture("openfang_inspired")
        self.assertEqual(superpowers["framework_profile"]["compilation_mode"], "fixture_stub")
        self.assertEqual(openfang["framework_profile"]["compilation_mode"], "fixture_stub")
        self.assertEqual(superpowers["acceptance"]["required_workflow_template_id"], "demo.superpowers_like.delivery_loop")
        self.assertEqual(openfang["acceptance"]["required_workflow_template_id"], "demo.openfang_inspired.guardrail_loop")

    def test_superpowers_demo_smoke_runs_end_to_end(self) -> None:
        with self._workspace() as tmp, mock.patch(
            "butler_main.runtime_os.agent_runtime.cli_runner.cli_provider_available",
            return_value=True,
        ), mock.patch(
            "butler_main.runtime_os.agent_runtime.cli_runner.run_prompt",
            return_value=("superpowers smoke completed", True),
        ):
            payload = smoke.run_superpowers_demo_smoke(
                workspace=tmp,
                timeout_seconds=30,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["demo_id"], "superpowers_like")
        observed = set(payload["acceptance"]["observed_event_types"])
        self.assertTrue(
            {
                "workflow_ir_compiled",
                "workflow_vm_executed",
                "verification_skipped",
                "branch_completed",
            }.issubset(observed)
        )
        self.assertEqual(payload["writeback"]["mission_status"], "completed")
        self.assertEqual(payload["writeback"]["node_status"], "done")
        self.assertEqual(payload["writeback"]["workflow_session_status"], "completed")
        self.assertEqual(payload["receipts"]["execution_phase"], "executed")
        self.assertIn("implementation_brief", payload["workflow_ir"]["artifact_ids"])
        self.assertEqual(payload["workflow_ir"]["framework_origin"]["framework_id"], "superpowers_like")
        self.assertEqual(payload["workflow_ir"]["execution_boundary"]["runtime_namespace"], "runtime_os")
        self.assertEqual(payload["workflow_ir"]["execution_boundary"]["execution_owner"], "runtime_os.agent_runtime")
        self.assertTrue(payload["workflow_ir"]["package_binding_visible"])

    def test_openfang_demo_smoke_reaches_approval_gate(self) -> None:
        with self._workspace() as tmp, mock.patch(
            "butler_main.runtime_os.agent_runtime.cli_runner.cli_provider_available",
            return_value=True,
        ), mock.patch(
            "butler_main.runtime_os.agent_runtime.cli_runner.run_prompt",
            return_value=("openfang smoke completed", True),
        ):
            payload = smoke.run_openfang_demo_smoke(
                workspace=tmp,
                timeout_seconds=30,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["demo_id"], "openfang_inspired")
        observed = set(payload["acceptance"]["observed_event_types"])
        self.assertIn("approval_requested", observed)
        self.assertEqual(payload["writeback"]["mission_status"], "awaiting_decision")
        self.assertEqual(payload["writeback"]["node_status"], "blocked")
        self.assertEqual(payload["writeback"]["workflow_session_status"], "awaiting_approval")
        self.assertEqual(payload["receipts"]["execution_phase"], "executed")
        self.assertEqual(payload["workflow_ir"]["capability_package_ref"], "pkg.cap.openfang.guardian")
        self.assertEqual(payload["workflow_ir"]["governance_policy_ref"], "policy.openfang.manual_approval.required")
        self.assertEqual(payload["workflow_ir"]["framework_origin"]["framework_id"], "openfang_inspired")
        self.assertEqual(payload["workflow_ir"]["execution_boundary"]["runtime_namespace"], "runtime_os")
        self.assertEqual(payload["workflow_ir"]["gate_policies"]["approval"]["target_owner"], "runtime_os.process_runtime")

    def test_campaign_smoke_runs_single_flow_lifecycle(self) -> None:
        with self._workspace() as tmp:
            payload = smoke.run_campaign_smoke(workspace=tmp)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["demo_id"], "campaign")
        self.assertTrue(payload["writeback"]["campaign_id"].startswith("campaign_"))
        self.assertTrue(payload["writeback"]["mission_id"].startswith("mission_"))
        self.assertTrue(payload["writeback"]["workflow_session_id"].startswith("workflow_session_"))
        created = payload["campaign"]["created"]
        resumed = payload["campaign"]["resumed"]
        stopped = payload["campaign"]["stopped"]
        self.assertEqual(created["current_phase"], "discover")
        self.assertEqual(created["next_phase"], "implement")
        self.assertGreaterEqual(payload["observation"]["initial"]["stable_evidence"]["workflow_session_count"], 1)
        self.assertGreaterEqual(payload["observation"]["initial"]["campaign_evidence"]["artifact_count"], 2)
        self.assertEqual(payload["observation"]["resumed"]["campaign_evidence"]["verdict_count"], 1)
        self.assertEqual(created["top_level_goal"], resumed["top_level_goal"])
        self.assertEqual(created["hard_constraints"], resumed["hard_constraints"])
        self.assertEqual(stopped["status"], "stopped")
        self.assertEqual(payload["writeback"]["workflow_session_status"], "stopped")
        self.assertTrue(all(item["ok"] for item in payload["acceptance"]["checks"]))


if __name__ == "__main__":
    unittest.main()
