from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.butler_flow.state import (  # noqa: E402
    flow_actions_path,
    flow_artifacts_path,
    flow_dir,
    flow_events_path,
    flow_state_path,
    flow_turns_path,
    handoffs_path,
    new_flow_state,
    write_json_atomic,
)
from butler_main.butler_flow.surface import service as flow_surface  # noqa: E402


def _config_path(root: Path) -> str:
    path = root / "butler_flow_surface_config.json"
    path.write_text(json.dumps({"workspace_root": str(root)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _write_flow_state(root: Path, *, flow_id: str, status: str, kind: str = "project_loop") -> Path:
    path = flow_dir(root, flow_id)
    state = new_flow_state(
        workflow_id=flow_id,
        workflow_kind=kind,
        workspace_root=str(root),
        goal="ship desktop",
        guard_condition="verified",
        max_attempts=8,
        max_phase_attempts=4,
    )
    state["status"] = status
    write_json_atomic(flow_state_path(path), state)
    return path


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


class ButlerFlowSurfaceTests(unittest.TestCase):
    def test_single_flow_payload_builds_surface_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            path = _write_flow_state(root, flow_id="flow_surface", status="running")
            state = json.loads(flow_state_path(path).read_text(encoding="utf-8"))
            state["approval_state"] = "operator_required"
            state["execution_mode"] = "medium"
            state["session_strategy"] = "role_bound"
            state["active_role_id"] = "planner"
            state["latest_supervisor_decision"] = {"decision": "execute", "session_mode": "warm"}
            state["latest_judge_decision"] = {"decision": "ADVANCE"}
            state["last_operator_action"] = {"action_type": "append_instruction"}
            state["context_governor"] = {"packet_size": "medium"}
            state["latest_token_usage"] = {"input_tokens": 10}
            state["role_sessions"] = {
                "planner": {"role_id": "planner", "session_id": "sess-1"},
                "reviewer": {"role_id": "reviewer", "session_id": "sess-2"},
            }
            write_json_atomic(flow_state_path(path), state)
            _append_jsonl(
                flow_events_path(path),
                [
                    {
                        "event_id": "evt-supervisor",
                        "kind": "supervisor_output",
                        "lane": "supervisor",
                        "family": "output",
                        "flow_id": "flow_surface",
                        "phase": "plan",
                        "attempt_no": 1,
                        "created_at": "2026-04-03 10:00:01",
                        "message": "supervisor summary",
                    },
                    {
                        "event_id": "evt-workflow",
                        "kind": "artifact_registered",
                        "lane": "workflow",
                        "family": "artifact",
                        "flow_id": "flow_surface",
                        "phase": "imp",
                        "attempt_no": 1,
                        "created_at": "2026-04-03 10:00:02",
                        "message": "artifact:1:imp",
                    },
                ],
            )
            _append_jsonl(
                handoffs_path(path),
                [
                    {
                        "handoff_id": "handoff-1",
                        "flow_id": "flow_surface",
                        "from_role_id": "planner",
                        "to_role_id": "reviewer",
                        "status": "pending",
                        "summary": "ready for review",
                        "created_at": "2026-04-03 10:00:03",
                    }
                ],
            )
            flow_artifacts_path(path).write_text(
                json.dumps(
                    {
                        "flow_id": "flow_surface",
                        "items": [{"artifact_ref": "artifact:1:imp", "phase": "imp", "attempt_no": 1}],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            payload = flow_surface.single_flow_payload(config=config, flow_id="flow_surface")

            self.assertEqual(payload["summary"]["approval_state"], "operator_required")
            self.assertEqual(payload["navigator_summary"]["active_role_id"], "planner")
            self.assertEqual(payload["supervisor_view"]["latest_judge_decision"]["decision"], "ADVANCE")
            self.assertEqual(payload["workflow_view"]["artifact_refs"], ["artifact:1:imp"])
            self.assertEqual(payload["role_strip"]["latest_handoff_summary"]["handoff_id"], "handoff-1")
            self.assertEqual([row["event_id"] for row in payload["supervisor_view"]["events"]], ["evt-supervisor"])
            self.assertEqual([row["event_id"] for row in payload["workflow_view"]["events"]], ["evt-workflow"])

    def test_workspace_payload_enriches_rows_via_surface_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            path = _write_flow_state(root, flow_id="flow_workspace_surface", status="running")
            state = json.loads(flow_state_path(path).read_text(encoding="utf-8"))
            state["approval_state"] = "operator_required"
            state["execution_mode"] = "medium"
            state["session_strategy"] = "role_bound"
            state["active_role_id"] = "planner"
            state["latest_judge_decision"] = {"decision": "RETRY"}
            state["last_operator_action"] = {"action_type": "pause"}
            write_json_atomic(flow_state_path(path), state)
            _append_jsonl(
                handoffs_path(path),
                [
                    {
                        "handoff_id": "handoff-2",
                        "flow_id": "flow_workspace_surface",
                        "from_role_id": "planner",
                        "to_role_id": "implementer",
                        "status": "pending",
                        "summary": "handoff ready",
                        "created_at": "2026-04-03 10:00:00",
                    }
                ],
            )

            payload = flow_surface.workspace_payload(config=config)
            rows = list(dict(payload.get("flows") or {}).get("items") or [])
            row = next((item for item in rows if str(item.get("flow_id") or "") == "flow_workspace_surface"), {})

            self.assertEqual(row.get("approval_state"), "operator_required")
            self.assertEqual(row.get("execution_mode"), "medium")
            self.assertEqual(row.get("session_strategy"), "role_bound")
            self.assertEqual(row.get("active_role_id"), "planner")
            self.assertEqual(dict(row.get("latest_handoff_summary") or {}).get("handoff_id"), "handoff-2")
            self.assertEqual(dict(row.get("latest_judge_decision") or {}).get("decision"), "RETRY")
            self.assertEqual(dict(row.get("latest_operator_action") or {}).get("action_type"), "pause")
