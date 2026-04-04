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
    append_manage_turn,
    flow_artifacts_path,
    flow_dir,
    flow_events_path,
    flow_state_path,
    handoffs_path,
    read_manage_turns,
    new_flow_state,
    write_manage_draft,
    write_manage_pending_action,
    write_manage_session,
    write_json_atomic,
)
from butler_main.butler_flow.surface import (  # noqa: E402
    FlowSummaryDTO,
    RoleRuntimeDTO,
    build_flow_summary,
    build_role_runtime,
    build_single_flow_surface,
    build_workspace_surface,
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


def _seed_manager_session(root: Path, *, manager_session_id: str, flow_id: str = "") -> None:
    active_target = f"instance:{flow_id}" if flow_id else "new"
    write_manage_session(
        root,
        manager_session_id,
        {
            "manager_session_id": manager_session_id,
            "active_manage_target": active_target,
            "manager_stage": "requirements",
            "confirmation_scope": "flow_create",
            "updated_at": "2026-04-05 12:40:00",
        },
    )
    write_manage_draft(
        root,
        manager_session_id,
        {
            "manage_target": active_target,
            "asset_kind": "instance",
            "label": "Desktop 线程工作台",
            "workflow_kind": "managed_flow",
            "goal": "重构 Butler desktop 为线程化工作台",
            "guard_condition": "desktop shell + thread bridge + tests are verified",
            "summary": "先由 Manager 完成对齐，再启动 Supervisor",
            "phase_plan": [{"phase_id": "design"}, {"phase_id": "implement"}, {"phase_id": "verify"}],
            "review_checklist": ["single-stream layout", "day/night theme", "manager to supervisor bridge"],
        },
    )
    write_manage_pending_action(
        root,
        manager_session_id,
        {
            "manage_target": active_target,
            "preview": "Create Team + Supervisor",
            "draft_summary": "launch ready",
        },
    )
    append_manage_turn(
        root,
        manager_session_id,
        {
            "created_at": "2026-04-05 12:20:00",
            "manage_target": active_target,
            "instruction": "请先把 IA 对齐",
            "response": "先确定 Manager 默认入口和 thread-first 布局。",
            "parse_status": "ok",
            "raw_reply": "",
            "error_text": "",
            "session_recovery": {},
            "manager_stage": "idea",
            "draft": {
                "label": "Desktop 线程工作台",
                "goal": "重构 Butler desktop 为线程化工作台",
            },
            "pending_action": {},
            "action_ready": False,
        },
    )
    append_manage_turn(
        root,
        manager_session_id,
        {
            "created_at": "2026-04-05 12:36:00",
            "manage_target": active_target,
            "instruction": "继续把 team 和交付标准准备好",
            "response": "可以创建 flow 并交给 Supervisor。",
            "parse_status": "ok",
            "raw_reply": "",
            "error_text": "",
            "session_recovery": {},
            "manager_stage": "team_draft",
            "draft": {
                "label": "Desktop 线程工作台",
                "goal": "重构 Butler desktop 为线程化工作台",
                "workflow_kind": "managed_flow",
            },
            "pending_action": {"manage_target": active_target, "preview": "Create Team + Supervisor"},
            "action_ready": True,
        },
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
            sample_flow_dir = root / "flow-1"
            sample_flow_dir.mkdir(parents=True, exist_ok=True)
            (sample_flow_dir / "handoffs.jsonl").write_text(
                '{"handoff_id":"handoff-1","status":"pending","summary":"ready"}\n',
                encoding="utf-8",
            )

            def _status(_flow_id: str) -> dict:
                return {
                    "flow_id": "flow-1",
                    "flow_dir": str(sample_flow_dir),
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

    def test_thread_home_and_manager_thread_payloads_project_manager_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            _seed_manager_session(root, manager_session_id="manager_session_1")

            home = flow_surface.thread_home_payload(config=config)
            manager = flow_surface.manager_thread_payload(config=config, manager_session_id="manager_session_1")

            self.assertEqual(home["manager_entry"]["default_manager_session_id"], "manager_session_1")
            self.assertEqual(home["history"][0]["thread_kind"], "manager")
            self.assertEqual(manager["thread"]["title"], "Desktop 线程工作台")
            self.assertEqual(manager["blocks"][0]["kind"], "idea")
            self.assertEqual(manager["blocks"][-1]["kind"], "launch")
            self.assertEqual(manager["pending_action"]["preview"], "Create Team + Supervisor")
            self.assertEqual(len(read_manage_turns(root, "manager_session_1")), 2)

    def test_supervisor_thread_and_agent_focus_payloads_wrap_single_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            path = _write_flow_state(root, flow_id="flow_thread_surface", status="running")
            state = json.loads(flow_state_path(path).read_text(encoding="utf-8"))
            state["approval_state"] = "operator_required"
            state["execution_mode"] = "medium"
            state["session_strategy"] = "role_bound"
            state["active_role_id"] = "implementer"
            state["role_sessions"] = {
                "planner": {"role_id": "planner", "session_id": "sess-1"},
                "implementer": {"role_id": "implementer", "session_id": "sess-2"},
            }
            write_json_atomic(flow_state_path(path), state)
            _append_jsonl(
                flow_events_path(path),
                [
                    {
                        "event_id": "evt-supervisor-thread",
                        "kind": "supervisor_output",
                        "lane": "supervisor",
                        "family": "output",
                        "flow_id": "flow_thread_surface",
                        "phase": "implement",
                        "attempt_no": 1,
                        "created_at": "2026-04-05 12:50:00",
                        "message": "先实现 thread-first shell",
                        "payload": {"role_id": "implementer"},
                    }
                ],
            )
            _append_jsonl(
                handoffs_path(path),
                [
                    {
                        "handoff_id": "handoff-thread-1",
                        "flow_id": "flow_thread_surface",
                        "from_role_id": "planner",
                        "to_role_id": "implementer",
                        "status": "pending",
                        "summary": "开始实现桌面线程壳",
                        "created_at": "2026-04-05 12:45:00",
                    }
                ],
            )
            flow_artifacts_path(path).write_text(
                json.dumps(
                    {
                        "flow_id": "flow_thread_surface",
                        "items": [
                            {
                                "artifact_ref": "artifact://desktop/thread-shell",
                                "phase": "implement",
                                "attempt_no": 1,
                                "created_at": "2026-04-05 12:55:00",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            supervisor = flow_surface.supervisor_thread_payload(config=config, flow_id="flow_thread_surface")
            agent = flow_surface.agent_focus_payload(config=config, flow_id="flow_thread_surface", role_id="implementer")

            self.assertEqual(supervisor["thread"]["thread_kind"], "supervisor")
            self.assertEqual(supervisor["blocks"][0]["kind"], "start")
            self.assertEqual(supervisor["blocks"][1]["action_target"], "role:implementer")
            self.assertEqual(agent["role_id"], "implementer")
            self.assertEqual(agent["blocks"][0]["kind"], "role_brief")
            self.assertTrue(any(block["kind"] == "artifact" for block in agent["blocks"]))
