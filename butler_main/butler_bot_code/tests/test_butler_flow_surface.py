from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.butler_flow.surface import (  # noqa: E402
    FlowDetailDTO,
    FlowSummaryDTO,
    RoleRuntimeDTO,
    build_flow_summary,
    build_role_runtime,
    build_single_flow_surface,
    build_workspace_surface,
)


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

    def test_build_role_runtime_wraps_role_and_handoff_payload(self) -> None:
        runtime = build_role_runtime(
            payload={
                "execution_mode": "medium",
                "session_strategy": "role_bound",
                "active_role_id": "reviewer",
                "role_pack_id": "coding_flow",
                "roles": [{"role_id": "reviewer", "session_id": "role-session-1"}],
                "role_chips": [{"role_id": "reviewer", "state": "active"}],
                "pending_handoffs": [{"handoff_id": "handoff-2"}],
                "recent_handoffs": [{"handoff_id": "handoff-1"}],
                "latest_handoff_summary": {"handoff_id": "handoff-2"},
            }
        )

        self.assertIsInstance(runtime, RoleRuntimeDTO)
        self.assertEqual(runtime.active_role_id, "reviewer")
        self.assertEqual(runtime.role_pack_id, "coding_flow")
        self.assertEqual(runtime.pending_handoffs[0]["handoff_id"], "handoff-2")

    def test_build_single_flow_surface_returns_nested_desktop_ready_payload(self) -> None:
        summary = build_flow_summary(
            status_payload={
                "flow_id": "flow-desktop",
                "flow_state": {
                    "label": "Desktop surface",
                    "workflow_kind": "managed_flow",
                    "status": "running",
                    "current_phase": "plan",
                    "goal": "ship shared surface",
                },
                "effective_status": "running",
                "effective_phase": "plan",
            },
            handoffs=[],
        )

        payload = build_single_flow_surface(
            payload={
                "flow_id": "flow-desktop",
                "status": {"flow_id": "flow-desktop"},
                "summary": summary.to_dict(),
                "step_history": [{"step_id": "phase:1:plan"}],
                "timeline": [{"event_id": "evt-1", "lane": "supervisor"}],
                "artifacts": [{"artifact_ref": "artifact-1"}],
                "turns": [{"turn_id": "turn-1"}],
                "actions": [{"action_type": "pause"}],
                "handoffs": [{"handoff_id": "handoff-1"}],
                "navigator_summary": summary.to_dict(),
                "supervisor_view": {"header": {"flow_id": "flow-desktop"}, "events": [{"event_id": "evt-1"}]},
                "workflow_view": {"events": [{"event_id": "evt-2"}]},
                "inspector": {"selected_event": {}},
                "role_strip": {"active_role_id": "planner"},
                "operator_rail": {"approval_state": "operator_required", "role_strip": {"active_role_id": "planner"}},
                "flow_console": {"flow_id": "flow-desktop", "summary": summary.to_dict()},
            }
        )

        self.assertIsInstance(payload["summary"], dict)
        self.assertEqual(payload["summary"]["flow_id"], "flow-desktop")
        self.assertEqual(payload["supervisor_view"]["header"]["flow_id"], "flow-desktop")
        self.assertEqual(payload["operator_rail"]["approval_state"], "operator_required")

    def test_build_workspace_surface_enriches_rows_with_summary_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_dir = root / "flow-1"
            flow_dir.mkdir(parents=True, exist_ok=True)
            (flow_dir / "handoffs.jsonl").write_text(
                '{"handoff_id":"handoff-1","status":"pending","summary":"ready"}\n',
                encoding="utf-8",
            )

            def _status(_flow_id: str) -> dict:
                return {
                    "flow_id": "flow-1",
                    "flow_dir": str(flow_dir),
                    "flow_state": {
                        "workflow_kind": "managed_flow",
                        "approval_state": "operator_required",
                        "execution_mode": "medium",
                        "session_strategy": "role_bound",
                        "active_role_id": "planner",
                        "latest_judge_decision": {"decision": "RETRY"},
                        "last_operator_action": {"action_type": "pause"},
                        "role_pack_id": "coding_flow",
                    },
                }

            surface = build_workspace_surface(
                preflight_payload={"workspace_root": str(root)},
                flows_payload={"items": [{"flow_id": "flow-1"}]},
                resolve_status_payload=_status,
                read_handoffs=lambda _flow_id, status_payload: [
                    {"handoff_id": "handoff-1", "status": "pending", "summary": "ready"}
                ]
                if str(status_payload.get("flow_dir") or "").strip()
                else [],
                limit=10,
            )

            row = surface.to_dict()["flows"]["items"][0]
            self.assertEqual(row["approval_state"], "operator_required")
            self.assertEqual(row["execution_mode"], "medium")
            self.assertEqual(row["latest_handoff_summary"]["handoff_id"], "handoff-1")
