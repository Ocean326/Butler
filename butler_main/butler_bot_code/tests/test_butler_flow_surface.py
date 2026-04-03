from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.butler_flow.surface import FlowSummaryDTO, build_flow_summary  # noqa: E402


class ButlerFlowSurfaceTests(unittest.TestCase):
    def test_build_flow_summary_returns_publishable_dto(self) -> None:
        payload = {
            "flow_state": {
                "workflow_kind": "project_loop",
                "status": "running",
                "current_phase": "imp",
                "goal": "ship desktop v1",
                "guard_condition": "release checklist green",
                "approval_state": "operator_required",
                "execution_mode": "medium",
                "session_strategy": "role_bound",
                "active_role_id": "implementer",
                "role_pack_id": "coding_flow",
                "latest_judge_decision": {"decision": "RETRY"},
                "last_operator_action": {"action_type": "pause"},
                "latest_token_usage": {"input_tokens": 12},
                "context_governor": {"mode": "reset"},
            },
            "effective_status": "running",
            "effective_phase": "review",
        }
        handoffs = [
            {
                "handoff_id": "handoff-1",
                "from_role_id": "planner",
                "to_role_id": "implementer",
                "status": "pending",
                "summary": "implementation ready",
                "created_at": "2026-04-03 01:20:00",
            }
        ]

        summary = build_flow_summary(status_payload=payload, handoffs=handoffs)

        self.assertIsInstance(summary, FlowSummaryDTO)
        self.assertEqual(summary.effective_status, "running")
        self.assertEqual(summary.effective_phase, "review")
        self.assertEqual(summary.approval_state, "operator_required")
        self.assertEqual(summary.active_role_id, "implementer")
        self.assertEqual(summary.latest_handoff_summary["handoff_id"], "handoff-1")
