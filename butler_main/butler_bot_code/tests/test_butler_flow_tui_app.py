from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from textual import events as textual_events


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from textual.widgets import Input, ListView, RichLog, Static  # noqa: E402

from butler_main.butler_flow.models import PreparedFlowRun  # noqa: E402
from butler_main.butler_flow.state import FileRuntimeStateStore, flow_dir, flow_events_path, handoffs_path, new_flow_state, runtime_plan_path, write_json_atomic  # noqa: E402
from butler_main.butler_flow.tui.app import ButlerFlowTuiApp, PasteAwareInput  # noqa: E402


def _config_path(root: Path) -> str:
    path = root / "butler_flow_tui_app_config.json"
    path.write_text(json.dumps({"workspace_root": str(root)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _transcript_text(app: ButlerFlowTuiApp) -> str:
    widget = app.query_one("#transcript", RichLog)
    return "\n".join(line.text for line in list(widget.lines or []))


def _manage_transcript_text(app: ButlerFlowTuiApp) -> str:
    widget = app.query_one("#manage-transcript", RichLog)
    return "\n".join(line.text for line in list(widget.lines or []))


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )




class ButlerFlowTuiAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_input_large_paste_uses_placeholder_but_preserves_full_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                command_input = app._command_input()
                command_input.value = "/manage new "
                command_input.cursor_position = len(command_input.value)
                pasted = "x" * 201
                command_input._on_paste(textual_events.Paste(pasted))
                await pilot.pause(0.1)

                self.assertEqual(command_input.value, "/manage new [201 characters]")
                self.assertEqual(command_input.resolved_value(), f"/manage new {pasted}")

    async def test_setup_goal_submission_uses_resolved_large_paste_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._handle_command("new", [])
                app._set_setup_stage("goal")
                await pilot.pause(0.1)

                command_input = app._command_input()
                pasted = "goal " * 50
                command_input._on_paste(textual_events.Paste(pasted))
                await pilot.pause(0.1)

                app.on_input_submitted(Input.Submitted(command_input, command_input.value, None))
                await pilot.pause(0.1)

                self.assertEqual(app._setup_goal, pasted.strip())
                self.assertEqual(command_input.value, "")
                self.assertEqual(command_input.resolved_value(), "")

    async def test_command_input_grows_when_text_wraps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(60, 20)) as pilot:
                await pilot.pause(0.2)
                command_input = app._command_input()
                base_height = command_input.region.height
                command_input.value = "wrap " * 30
                await pilot.pause(0.2)
                self.assertGreater(command_input.region.height, base_height)

    async def test_command_input_has_slash_command_suggester(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                command_input = app._command_input()
                self.assertIsNotNone(command_input.suggester)
                suggestions = tuple(command_input.suggester._command_provider())
                self.assertIn("/new", suggestions)
                self.assertIn("/manage", suggestions)
                self.assertIn("/resume [flow_id|last]", suggestions)
                self.assertNotIn("/history", suggestions)
                self.assertNotIn("/flows", suggestions)

    async def test_flow_view_enter_refreshes_without_opening_inspector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_alpha",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            state["approval_state"] = "operator_required"
            write_json_atomic(flow_dir(root, "flow_alpha") / "workflow_state.json", state)

            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_alpha")
                app._back_to_flow()
                await pilot.pause(0.1)

                self.assertFalse(app._inspector_open)
                app.action_open_selected()
                await pilot.pause(0.1)
                self.assertFalse(app._inspector_open)
                self.assertIn("Supervisor Stream", _transcript_text(app))

    async def test_history_command_switches_to_history_and_returns_to_single_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state_alpha = new_flow_state(
                workflow_id="flow_alpha",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            state_beta = new_flow_state(
                workflow_id="flow_beta",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="beta",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            state_alpha["updated_at"] = "2026-03-31 10:00:00"
            state_beta["updated_at"] = "2026-03-31 10:05:00"
            write_json_atomic(flow_dir(root, "flow_alpha") / "workflow_state.json", state_alpha)
            write_json_atomic(flow_dir(root, "flow_beta") / "workflow_state.json", state_beta)

            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                self.assertEqual(app._view_mode, "history")

                app._handle_command("history", [])
                await pilot.pause(0.1)
                self.assertEqual(app._view_mode, "history")
                self.assertIs(app.screen.focused, app.query_one("#history-list", ListView))
                self.assertEqual(app._history_cursor_flow_id, "flow_beta")

                await pilot.press("down")
                await pilot.pause(0.1)
                self.assertEqual(app._view_mode, "history")
                self.assertEqual(app._history_cursor_flow_id, "flow_alpha")
                history_detail = str(app.query_one("#history-detail", Static).renderable)
                self.assertIn("flow_id=flow_alpha", history_detail)
                self.assertIn("Recent Runtime Steps", history_detail)

                await pilot.press("enter")
                await pilot.pause(0.1)

                self.assertEqual(app._view_mode, "flow")
                self.assertEqual(app._selected_flow_id, "flow_alpha")
                self.assertIn("flow_id=flow_alpha", _transcript_text(app))

    async def test_flow_screen_is_single_column_and_shift_tab_switches_streams(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state_alpha = new_flow_state(
                workflow_id="flow_alpha",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            state_alpha["approval_state"] = "operator_required"
            state_alpha["pending_codex_prompt"] = "approve next step"
            state_alpha["latest_judge_decision"] = {"decision": "RETRY"}
            state_alpha["last_operator_action"] = {"action_type": "pause"}
            state_alpha["supervisor_thread_id"] = "super-thread-1"
            state_alpha["latest_supervisor_decision"] = {"session_mode": "warm", "load_profile": "compact"}
            state_alpha["latest_mutation"] = {"mutation_kind": "spawn_ephemeral_role"}
            state_alpha["active_role_id"] = "planner"
            state_alpha["execution_mode"] = "medium"
            state_alpha["session_strategy"] = "role_bound"
            state_alpha["role_pack_id"] = "coding_flow"
            state_alpha["role_sessions"] = {
                "planner": {"role_id": "planner", "session_id": "sess-1"},
                "reviewer": {"role_id": "reviewer", "session_id": "sess-2"},
            }
            state_alpha["latest_role_handoffs"] = {"reviewer": "handoff_1"}
            state_alpha["manage_handoff"] = {
                "summary": "managed flow prepared",
                "operator_guidance": "review then resume",
                "confirmation_prompt": "confirm before run",
                "managed_at": "2026-03-31 10:06:00",
            }
            state_beta = new_flow_state(
                workflow_id="flow_beta",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="beta",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            write_json_atomic(flow_dir(root, "flow_alpha") / "workflow_state.json", state_alpha)
            write_json_atomic(flow_dir(root, "flow_beta") / "workflow_state.json", state_beta)
            write_json_atomic(
                runtime_plan_path(flow_dir(root, "flow_alpha")),
                {
                    "plan_stage": "executor_compiled",
                    "summary": "planner packet compiled",
                    "latest_mutation": {"mutation_kind": "spawn_ephemeral_role"},
                },
            )
            handoffs_path(flow_dir(root, "flow_alpha")).write_text(
                json.dumps(
                    {
                        "handoff_id": "handoff_1",
                        "flow_id": "flow_alpha",
                        "from_role_id": "planner",
                        "to_role_id": "reviewer",
                        "status": "pending",
                        "summary": "ready for review",
                        "created_at": "2026-03-31 10:02:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_alpha")
                app._back_to_flow()
                await pilot.pause(0.1)
                workspace_header = str(app.query_one("#workspace-header", Static).renderable)
                workspace_list = str(app.query_one("#workspace-list", Static).renderable)
                transcript = _transcript_text(app)
                action_bar = str(app.query_one("#action-bar", Static).renderable)

                self.assertIn("Workspace", workspace_header)
                self.assertIn("flows=2", workspace_header)
                self.assertIn("flow_alpha", workspace_list)
                self.assertIn("flow_beta", workspace_list)

                self.assertFalse(app.query_one("#flow-sidebar").display)
                self.assertFalse(app.query_one("#inspector-panel").display)
                self.assertIn("Supervisor Stream", transcript)
                self.assertIn("approval_state=operator_required", transcript)
                self.assertIn("active_role=planner", transcript)
                self.assertIn("supervisor_thread=super-thread-1", transcript)
                self.assertIn("supervisor_session_mode=warm", transcript)
                self.assertIn("supervisor_load_profile=compact", transcript)
                self.assertIn("latest_mutation=spawn_ephemeral_role", transcript)
                self.assertIn("latest_handoff=planner -> reviewer | pending | ready for review", transcript)
                self.assertIn("view=supervisor", action_bar)
                self.assertIn("Shift+Tab: Workflow", action_bar)

                app.on_key(textual_events.Key("shift+tab", None))
                await pilot.pause(0.1)
                self.assertEqual(app._flow_view_mode, "workflow")
                action_bar = str(app.query_one("#action-bar", Static).renderable)
                self.assertIn("view=workflow", action_bar)
                self.assertIn("Shift+Tab: Supervisor", action_bar)
                workflow_transcript = _transcript_text(app)
                self.assertIn("Workflow Stream", workflow_transcript)
                self.assertIn("[workflow/handoff]", workflow_transcript)
                self.assertIn(" ready for review", workflow_transcript)

    async def test_transcript_groups_compact_repeated_titles_and_reintroduce_after_group_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_alpha",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            write_json_atomic(flow_dir(root, "flow_alpha") / "workflow_state.json", state)
            flow_events_path(flow_dir(root, "flow_alpha")).write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event_id": "evt-1",
                                "kind": "supervisor_decided",
                                "lane": "supervisor",
                                "family": "decision",
                                "title": "plan accepted",
                                "message": "plan accepted",
                                "created_at": "2026-04-01 10:00:00",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "event_id": "evt-2",
                                "kind": "judge_result",
                                "lane": "supervisor",
                                "family": "decision",
                                "title": "RETRY",
                                "message": "RETRY",
                                "created_at": "2026-04-01 10:00:01",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "event_id": "evt-3",
                                "kind": "approval_state_changed",
                                "lane": "supervisor",
                                "family": "approval",
                                "title": "operator required",
                                "message": "operator required",
                                "created_at": "2026-04-01 10:00:02",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "event_id": "evt-4",
                                "kind": "judge_result",
                                "lane": "supervisor",
                                "family": "decision",
                                "title": "APPROVE",
                                "message": "APPROVE",
                                "created_at": "2026-04-01 10:00:03",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "event_id": "evt-5",
                                "kind": "codex_runtime_event",
                                "lane": "workflow",
                                "family": "raw_execution",
                                "title": "stdout",
                                "message": "stdout line 1",
                                "raw_text": "stdout line 1",
                                "payload": {"kind": "stdout", "role_id": "implementer", "active_role_id": "implementer"},
                                "created_at": "2026-04-01 10:00:04",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "event_id": "evt-6",
                                "kind": "codex_runtime_event",
                                "lane": "workflow",
                                "family": "raw_execution",
                                "title": "stdout",
                                "message": "stdout line 2",
                                "raw_text": "stdout line 2",
                                "payload": {"kind": "stdout", "role_id": "implementer", "active_role_id": "implementer"},
                                "created_at": "2026-04-01 10:00:05",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "event_id": "evt-7",
                                "kind": "artifact_registered",
                                "lane": "workflow",
                                "family": "artifact",
                                "title": "report.md",
                                "message": "report.md",
                                "payload": {"artifact_ref": "artifact:7:plan", "producer_role_id": "implementer", "phase": "plan", "attempt_no": 1},
                                "created_at": "2026-04-01 10:00:06",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "event_id": "evt-8",
                                "kind": "codex_runtime_event",
                                "lane": "workflow",
                                "family": "raw_execution",
                                "title": "stdout",
                                "message": "stdout line 3",
                                "raw_text": "stdout line 3",
                                "payload": {"kind": "stdout", "role_id": "reviewer", "active_role_id": "reviewer"},
                                "created_at": "2026-04-01 10:00:07",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_alpha")
                app._back_to_flow()
                await pilot.pause(0.1)

                supervisor_lines = [line.rstrip() for line in _transcript_text(app).splitlines()]
                self.assertEqual(supervisor_lines.count("[supervisor/decision]"), 2)
                self.assertIn(" plan accepted", supervisor_lines)
                self.assertIn(" RETRY", supervisor_lines)
                self.assertIn("", supervisor_lines)
                self.assertIn("[supervisor/approval]", supervisor_lines)
                self.assertIn(" operator required", supervisor_lines)
                self.assertIn(" APPROVE", supervisor_lines)

                app.on_key(textual_events.Key("shift+tab", None))
                await pilot.pause(0.1)
                workflow_lines = [line.rstrip() for line in _transcript_text(app).splitlines()]
                self.assertEqual(workflow_lines.count("[workflow/raw_execution]"), 2)
                self.assertIn(" implementer · stdout line 1", workflow_lines)
                self.assertIn(" implementer · stdout line 2", workflow_lines)
                self.assertIn("[workflow/artifact]", workflow_lines)
                self.assertIn(" artifact:7:plan · role=implementer · phase=plan · attempt=1", workflow_lines)
                self.assertIn(" reviewer · stdout line 3", workflow_lines)

    async def test_meta_transcript_messages_use_grouped_system_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_alpha",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            write_json_atomic(flow_dir(root, "flow_alpha") / "workflow_state.json", state)

            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_alpha")
                app._back_to_flow()
                await pilot.pause(0.1)

                app._handle_command("follow", ["off"])
                await pilot.pause(0.1)
                transcript = _transcript_text(app)
                self.assertIn("[system/settings]", transcript)
                self.assertIn(" auto_follow=off", transcript)

    async def test_history_screen_renders_header_and_latest_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_state = new_flow_state(
                workflow_id="flow_alpha",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_state["current_phase"] = "review"
            flow_state["latest_judge_decision"] = {"decision": "RETRY"}
            flow_state["last_operator_action"] = {"action_type": "pause"}
            flow_state["active_role_id"] = "planner"
            flow_state["role_sessions"] = {"planner": {"role_id": "planner", "session_id": "sess-1"}}
            flow_state["manage_handoff"] = {
                "summary": "managed flow prepared",
                "operator_guidance": "review then resume",
                "confirmation_prompt": "confirm before run",
                "managed_at": "2026-03-31 10:06:00",
            }
            flow_state["phase_history"] = [
                {
                    "at": "2026-03-31 10:00:00",
                    "attempt_no": 1,
                    "phase": "plan",
                    "decision": {"decision": "ADVANCE", "reason": "plan done", "completion_summary": "plan done"},
                },
                {
                    "at": "2026-03-31 10:05:00",
                    "attempt_no": 2,
                    "phase": "imp",
                    "decision": {"decision": "ADVANCE", "reason": "imp done", "completion_summary": "imp done"},
                },
            ]
            write_json_atomic(flow_dir(root, "flow_alpha") / "workflow_state.json", flow_state)
            handoffs_path(flow_dir(root, "flow_alpha")).write_text(
                json.dumps(
                    {
                        "handoff_id": "handoff-9",
                        "flow_id": "flow_alpha",
                        "from_role_id": "planner",
                        "to_role_id": "reviewer",
                        "status": "pending",
                        "summary": "ready for review",
                        "created_at": "2026-03-31 10:02:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._handle_command("history", [])
                await pilot.pause(0.1)

                history_header = str(app.query_one("#history-header", Static).renderable)
                history_detail = str(app.query_one("#history-detail", Static).renderable)

                self.assertIn("Workspace Browser", history_header)
                self.assertIn("items=1", history_header)
                self.assertIn("Latest Signals", history_detail)
                self.assertIn("active_role=planner", history_detail)
                self.assertIn("last_judge=RETRY", history_detail)
                self.assertIn("last_operator=pause", history_detail)
                self.assertIn("Recovery", history_detail)
                self.assertIn("resume=/resume flow_alpha", history_detail)
                self.assertIn("Terminal Receipt", history_detail)
                self.assertIn("Manage Handoff", history_detail)
                self.assertIn("latest_handoff=planner -> reviewer | pending | ready for review", history_detail)
                self.assertIn("Recent Runtime Steps", history_detail)

    async def test_history_detail_panel_stays_in_right_column_after_selection_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            for flow_id, updated_at in (("flow_alpha", "2026-03-31 10:00:00"), ("flow_beta", "2026-03-31 10:05:00")):
                state = new_flow_state(
                    workflow_id=flow_id,
                    workflow_kind="project_loop",
                    workspace_root=str(root),
                    goal=f"{flow_id} goal",
                    guard_condition="done",
                    max_attempts=4,
                    max_phase_attempts=2,
                )
                state["updated_at"] = updated_at
                state["guard_condition"] = "this is a deliberately long guard condition used to keep the detail panel rendering wide and stable"
                write_json_atomic(flow_dir(root, flow_id) / "workflow_state.json", state)

            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._handle_command("history", [])
                await pilot.pause(0.1)

                history_left = app.query_one("#history-left")
                history_right = app.query_one("#history-right")
                initial_left_x = history_left.region.x
                initial_right_x = history_right.region.x
                self.assertGreater(initial_right_x, initial_left_x)

                await pilot.press("down")
                await pilot.pause(0.1)

                self.assertEqual(history_left.region.x, initial_left_x)
                self.assertEqual(history_right.region.x, initial_right_x)
                self.assertGreater(history_right.region.x, history_left.region.x)
                self.assertIn("flow_id=flow_alpha", str(app.query_one("#history-detail", Static).renderable))

    async def test_flows_command_switches_to_manage_center_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            write_json_atomic(
                flow_dir(root, "flow_alpha") / "workflow_state.json",
                new_flow_state(
                    workflow_id="flow_alpha",
                    workflow_kind="project_loop",
                    workspace_root=str(root),
                    goal="alpha",
                    guard_condition="done",
                    max_attempts=4,
                    max_phase_attempts=2,
                ),
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._handle_command("flows", [])
                await pilot.pause(0.1)
                self.assertEqual(app._view_mode, "flows")
                self.assertEqual(getattr(app, "_flows_screen_mode", ""), "manage")
                manage_header = str(app.query_one("#manage-header", Static).renderable)
                self.assertIn("Manage Center", manage_header)
                manage_transcript = _manage_transcript_text(app)
                self.assertIn("Manage Center", manage_transcript)
                self.assertIn("Assets", manage_transcript)

    async def test_manage_command_opens_manage_center(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._handle_command("manage", [])
                await pilot.pause(0.1)
                self.assertEqual(app._view_mode, "flows")
                self.assertEqual(getattr(app, "_flows_screen_mode", ""), "manage")
                self.assertIn("Manage Center", str(app.query_one("#manage-header", Static).renderable))

    async def test_manage_input_supports_asset_mentions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            write_json_atomic(
                root / "butler_main" / "butler_bot_code" / "assets" / "flows" / "templates" / "template_demo.json",
                {
                    "flow_id": "template_demo",
                    "label": "Template Demo",
                    "workflow_kind": "managed_flow",
                    "phase_plan": [{"phase_id": "plan", "title": "Plan", "objective": "plan", "done_when": "done", "retry_phase_id": "plan", "fallback_phase_id": "plan", "next_phase_id": ""}],
                },
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                await pilot.pause(0.1)
                command_input = app._command_input()
                command_input.focus()
                command_input.value = "$tem"
                command_input.cursor_position = len(command_input.value)
                await pilot.pause(0.3)
                self.assertIn("template:template_demo", str(getattr(command_input, "_suggestion", "")))
                self.assertEqual(app._split_manage_prompt("$template:template_demo refine checklist"), ("template:template_demo", "refine checklist"))
                self.assertEqual(app._split_manage_prompt("template:template_demo refine checklist"), ("template:template_demo", "refine checklist"))

    async def test_manage_plain_text_routes_to_manager_chat_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                await pilot.pause(0.1)
                with mock.patch.object(
                    app._controller,
                    "manage_chat",
                    return_value={
                        "response": "先确认细节，再决定是建 template 还是 pending flow。",
                        "manager_session_id": "manager-thread-1",
                    },
                ) as manage_chat, mock.patch.object(app._controller, "manage_flow") as manage_flow:
                    command_input = app._command_input()
                    command_input.value = "按我的需求创建一个新的 pending flow"
                    app.on_input_submitted(Input.Submitted(command_input, "按我的需求创建一个新的 pending flow", None))
                    await pilot.pause(0.3)
                    manage_chat.assert_called_once()
                    manage_flow.assert_not_called()
                    self.assertEqual(manage_chat.call_args.kwargs["manage_target"], app._manage_cursor_asset_key)
                    self.assertIn("manager-thread-1", app._manage_chat_session_id)
                    self.assertIn("先确认细节", _manage_transcript_text(app))

    async def test_manage_explicit_template_text_overrides_builtin_focus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            write_json_atomic(
                root / "butler_main" / "butler_bot_code" / "assets" / "flows" / "templates" / "academic_paper_review_v1.json",
                {
                    "flow_id": "academic_paper_review_v1",
                    "label": "Academic Paper Review",
                    "workflow_kind": "managed_flow",
                    "phase_plan": [{"phase_id": "review", "title": "Review", "objective": "review", "done_when": "done", "retry_phase_id": "review", "fallback_phase_id": "review", "next_phase_id": ""}],
                },
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                app._manage_cursor_asset_key = "builtin:project_loop"
                await pilot.pause(0.1)
                with mock.patch.object(
                    app._controller,
                    "manage_chat",
                    return_value={
                        "response": "这个问题我按 academic_paper_review_v1 来回答。",
                        "manager_session_id": "manager-thread-explicit",
                    },
                ) as manage_chat, mock.patch.object(app._controller, "manage_flow") as manage_flow:
                    command_input = app._command_input()
                    command_input.value = "template:academic_paper_review_v1 具体介绍一下其中的阶段"
                    app.on_input_submitted(Input.Submitted(command_input, "template:academic_paper_review_v1 具体介绍一下其中的阶段", None))
                    await pilot.pause(0.3)
                    self.assertEqual(manage_chat.call_args.kwargs["manage_target"], "template:academic_paper_review_v1")
                    manage_flow.assert_not_called()
                    self.assertIn("academic_paper_review_v1", _manage_transcript_text(app))

    async def test_manage_dangling_dollar_is_sanitized_before_chat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                await pilot.pause(0.1)
                with mock.patch.object(
                    app._controller,
                    "manage_chat",
                    return_value={"response": "继续讨论模板。", "manager_session_id": "manager-thread-sanitize"},
                ) as manage_chat:
                    command_input = app._command_input()
                    command_input.value = "$\n之前的模板需要重新讨论一下"
                    app.on_input_submitted(Input.Submitted(command_input, command_input.value, None))
                    await pilot.pause(0.3)
                    self.assertEqual(manage_chat.call_args.kwargs["instruction"], "之前的模板需要重新讨论一下")

    async def test_manage_chat_applies_pending_flow_creation_only_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                await pilot.pause(0.1)
                with mock.patch.object(
                    app._controller,
                    "manage_chat",
                    side_effect=[
                        {
                            "response": "我先整理 pending flow 草稿，确认后再创建。",
                            "manager_session_id": "manager-thread-2",
                            "draft_summary": "new · managed_flow\n目标: 按用户需求创建 pending flow",
                            "pending_action_preview": "如果你认可这版 pending flow 草稿，我就创建它。",
                            "action": "manage_flow",
                            "action_ready": False,
                        },
                        {
                            "response": "收到，按刚才确认的草稿创建。",
                            "manager_session_id": "manager-thread-2",
                            "action": "manage_flow",
                            "action_ready": True,
                            "action_manage_target": "new",
                            "action_instruction": "按用户需求创建 pending flow，并补齐目标与守护条件",
                            "action_goal": "按用户需求创建 pending flow",
                            "action_guard_condition": "flow 可继续执行",
                            "action_draft": {"goal": "按用户需求创建 pending flow", "guard_condition": "flow 可继续执行"},
                        },
                    ],
                ) as manage_chat, mock.patch.object(
                    app._controller,
                    "manage_flow",
                    return_value={
                        "asset_key": "instance:flow_new",
                        "asset_kind": "instance",
                        "asset_id": "flow_new",
                        "manage_handoff": {"summary": "pending flow created"},
                    },
                ) as manage_flow:
                    command_input = app._command_input()
                    command_input.value = "按我的需求创建一个新的 pending flow"
                    app.on_input_submitted(Input.Submitted(command_input, command_input.value, None))
                    await pilot.pause(0.3)
                    manage_flow.assert_not_called()
                    command_input.value = "确认"
                    app.on_input_submitted(Input.Submitted(command_input, command_input.value, None))
                    await pilot.pause(0.3)
                    self.assertEqual(manage_chat.call_count, 2)
                    manage_flow.assert_called_once()
                    self.assertEqual(manage_flow.call_args.kwargs["manage_target"], "new")
                    self.assertEqual(manage_flow.call_args.kwargs["instruction"], "按用户需求创建 pending flow，并补齐目标与守护条件")
                    self.assertEqual(manage_flow.call_args.kwargs["draft_payload"]["goal"], "按用户需求创建 pending flow")
                    self.assertIn("pending flow created", _manage_transcript_text(app))

    async def test_manage_chat_applies_template_creation_only_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                await pilot.pause(0.1)
                with mock.patch.object(
                    app._controller,
                    "manage_chat",
                    side_effect=[
                        {
                            "response": "这个需求更适合先沉淀成模板，我先整理模板草稿。",
                            "manager_session_id": "manager-thread-3",
                            "draft_summary": "template:new · managed_flow\n目标: 创建一个可复用模板，用于学术论文评审",
                            "pending_action_preview": "如果你认可这版模板草稿，我就创建 template。",
                            "action": "manage_flow",
                            "action_ready": False,
                        },
                        {
                            "response": "收到，我现在创建 template。",
                            "manager_session_id": "manager-thread-3",
                            "action": "manage_flow",
                            "action_ready": True,
                            "action_manage_target": "template:new",
                            "action_instruction": "创建一个可复用模板，用于学术论文评审",
                            "action_draft": {"goal": "创建一个可复用模板，用于学术论文评审"},
                        },
                    ],
                ) as manage_chat, mock.patch.object(
                    app._controller,
                    "manage_flow",
                    return_value={
                        "asset_key": "template:20260402_学术论文评审",
                        "asset_kind": "template",
                        "asset_id": "20260402_学术论文评审",
                        "manage_handoff": {"summary": "template created"},
                    },
                ) as manage_flow:
                    command_input = app._command_input()
                    command_input.value = "创建一个可复用模板，用于学术论文评审"
                    app.on_input_submitted(Input.Submitted(command_input, command_input.value, None))
                    await pilot.pause(0.3)
                    manage_flow.assert_not_called()
                    command_input.value = "确认"
                    app.on_input_submitted(Input.Submitted(command_input, command_input.value, None))
                    await pilot.pause(0.3)
                    self.assertEqual(manage_chat.call_count, 2)
                    manage_flow.assert_called_once()
                    self.assertEqual(manage_flow.call_args.kwargs["manage_target"], "template:new")
                    self.assertEqual(manage_flow.call_args.kwargs["draft_payload"]["goal"], "创建一个可复用模板，用于学术论文评审")
                    self.assertIn("template created", _manage_transcript_text(app))

    async def test_manage_chat_followup_reuses_current_asset_focus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                await pilot.pause(0.1)
                first_payload = {
                    "response": "我建议先把论文评审模板定下来。",
                    "manage_target": "template:academic_paper_review_v1",
                    "manager_stage": "template_confirm",
                    "active_skill": "template_select_or_create",
                    "confirmation_scope": "template",
                    "confirmation_prompt": "如果你认可这个模板方案，我就先按它整理模板。",
                    "manager_session_id": "manager-thread-review",
                }
                second_payload = {
                    "response": "收到，我继续围绕这个模板整理下一步。",
                    "manager_session_id": "manager-thread-review",
                }
                with mock.patch.object(
                    app._controller,
                    "manage_chat",
                    side_effect=[first_payload, second_payload],
                ) as manage_chat, mock.patch.object(app._controller, "manage_flow") as manage_flow:
                    command_input = app._command_input()
                    command_input.value = "先帮我定论文评审模板"
                    app.on_input_submitted(Input.Submitted(command_input, command_input.value, None))
                    await pilot.pause(0.3)
                    command_input.value = "确认，按这个模板继续"
                    app.on_input_submitted(Input.Submitted(command_input, command_input.value, None))
                    await pilot.pause(0.3)
                    self.assertEqual(manage_chat.call_count, 2)
                    manage_flow.assert_not_called()
                    self.assertEqual(manage_chat.call_args_list[1].kwargs["manage_target"], "")
                    self.assertEqual(app._manage_cursor_asset_key, "template:academic_paper_review_v1")
                    self.assertIn("confirm=template", _manage_transcript_text(app))

    async def test_manage_chat_parse_failure_surfaces_raw_reply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                await pilot.pause(0.1)
                with mock.patch.object(
                    app._controller,
                    "manage_chat",
                    return_value={
                        "response": "先把模板和 supervisor 方向讨论清楚，再决定是否创建。",
                        "parse_status": "failed",
                        "raw_reply": "先把模板和 supervisor 方向讨论清楚，再决定是否创建。",
                        "error_text": "manager chat returned non-JSON output",
                        "manager_session_id": "manager-thread-parse",
                    },
                ):
                    command_input = app._command_input()
                    command_input.value = "重新讨论一下模板"
                    app.on_input_submitted(Input.Submitted(command_input, command_input.value, None))
                    await pilot.pause(0.3)
                    transcript = _manage_transcript_text(app)
                    self.assertIn("manager chat returned non-JSON output", transcript)
                    self.assertIn("先把模板和 supervisor 方向讨论清楚", transcript)

    async def test_manage_chat_shows_manager_stage_and_confirmation_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                await pilot.pause(0.1)
                with mock.patch.object(
                    app._controller,
                    "manage_chat",
                    return_value={
                        "response": "我建议先把模板确认下来，再去创建 flow。",
                        "manager_session_id": "manager-thread-explain",
                        "manager_stage": "flow_confirm",
                        "active_skill": "flow_spec_finalize",
                        "confirmation_scope": "flow",
                        "confirmation_prompt": "如果你认可这次 run 的 flow 定义，我就创建 pending flow。",
                    },
                ) as manage_chat, mock.patch.object(app._controller, "manage_flow") as manage_flow:
                    command_input = app._command_input()
                    command_input.value = "基于这个模板创建 flow"
                    app.on_input_submitted(Input.Submitted(command_input, command_input.value, None))
                    await pilot.pause(0.3)
                    manage_chat.assert_called_once()
                    manage_flow.assert_not_called()
                    transcript = _manage_transcript_text(app)
                    self.assertIn("stage=flow_confirm", transcript)
                    self.assertIn("skill=flow_spec_finalize", transcript)
                    self.assertIn("如果你认可这次 run 的 flow 定义", transcript)

    async def test_manage_picker_shows_seven_items_and_enter_selects_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            for index in range(8):
                write_json_atomic(
                    root / "butler_main" / "butler_bot_code" / "assets" / "flows" / "templates" / f"template_demo_{index}.json",
                    {
                        "flow_id": f"template_demo_{index}",
                        "label": f"Template Demo {index}",
                        "workflow_kind": "managed_flow",
                        "phase_plan": [{"phase_id": "plan", "title": "Plan", "objective": "plan", "done_when": "done", "retry_phase_id": "plan", "fallback_phase_id": "plan", "next_phase_id": ""}],
                    },
                )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                await pilot.pause(0.1)
                command_input = app._command_input()
                command_input.focus()
                command_input.value = "$template:"
                command_input.cursor_position = len(command_input.value)
                await pilot.pause(0.3)
                picker = app.query_one("#mention-picker", Static)
                self.assertTrue(picker.display)
                self.assertEqual(app._manage_picker.visible_height, 7)
                first_candidate = app._manage_picker.selected_candidate
                app.on_key(textual_events.Key("down", None))
                await pilot.pause(0.1)
                self.assertNotEqual(app._manage_picker.selected_candidate, first_candidate)
                app.on_key(textual_events.Key("enter", None))
                await pilot.pause(0.1)
                self.assertTrue(command_input.value.startswith("$template:"))
                self.assertTrue(command_input.value.endswith(" "))
                self.assertFalse(picker.display)

    async def test_manage_picker_stays_attached_to_input_composer_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            for index in range(3):
                write_json_atomic(
                    root / "butler_main" / "butler_bot_code" / "assets" / "flows" / "templates" / f"template_attach_{index}.json",
                    {
                        "flow_id": f"template_attach_{index}",
                        "label": f"Template Attach {index}",
                        "workflow_kind": "managed_flow",
                        "phase_plan": [{"phase_id": "plan", "title": "Plan", "objective": "plan", "done_when": "done", "retry_phase_id": "plan", "fallback_phase_id": "plan", "next_phase_id": ""}],
                    },
                )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                app._open_manage_center()
                await pilot.pause(0.1)
                command_input = app._command_input()
                action_bar = app.query_one("#action-bar", Static)
                picker = app.query_one("#mention-picker", Static)
                command_input.focus()
                command_input.value = "$template:"
                command_input.cursor_position = len(command_input.value)
                await pilot.pause(0.3)

                self.assertTrue(picker.display)
                self.assertEqual(action_bar.region.x, command_input.region.x)
                self.assertEqual(command_input.region.x, picker.region.x)
                self.assertEqual(action_bar.region.y + action_bar.region.height, command_input.region.y)
                self.assertEqual(command_input.region.y + command_input.region.height, picker.region.y)

    async def test_manage_detail_renders_role_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            detail = app._render_manage_detail(
                {
                    "asset_key": "template:paper_flow",
                    "asset_kind": "template",
                    "workflow_kind": "managed_flow",
                    "label": "Paper Flow",
                    "goal": "deliver a paper",
                    "guard_condition": "paper is complete",
                    "asset_path": str(root / "template.json"),
                    "role_pack_id": "research_flow",
                    "updated_at": "2026-04-02 12:00:00",
                    "definition": {
                        "role_guidance": {
                            "suggested_roles": ["planner", "researcher", "reviewer"],
                            "suggested_specialists": ["creator", "user-simulator"],
                            "activation_hints": ["when formatting or figure production blocks delivery"],
                            "promotion_candidates": ["creator"],
                            "manager_notes": "Keep this reference-only and let supervisor decide when to spawn.",
                        }
                    },
                }
            )
            self.assertIn("Role Guidance", detail)
            self.assertIn("suggested_roles=planner, researcher, reviewer", detail)
            self.assertIn("suggested_specialists=creator, user-simulator", detail)
            self.assertIn("promotion_candidates=creator", detail)

    async def test_flow_plain_text_queues_supervisor_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_alpha",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            state["status"] = "running"
            flow_path = flow_dir(root, "flow_alpha")
            write_json_atomic(flow_path / "workflow_state.json", state)
            runtime_store = FileRuntimeStateStore(flow_path)
            runtime_store.write_pid(os.getpid())
            runtime_store.write_watchdog_state(state="foreground", pid=os.getpid(), note="attached")
            runtime_store.write_run_state(
                run_id="flow_alpha",
                state="running",
                phase="plan",
                pid=os.getpid(),
                note="attempt 1 phase=plan",
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_alpha")
                app._back_to_flow()
                await pilot.pause(0.1)
                with mock.patch.object(app._controller, "apply_action", return_value={"ok": True, "action_type": "append_instruction"}) as apply_action:
                    command_input = app._command_input()
                    command_input.value = "继续实现剩余部分"
                    app.on_input_submitted(Input.Submitted(command_input, "继续实现剩余部分", None))
                    await pilot.pause(0.1)
                    apply_action.assert_called_once()
                    self.assertIn("queued to running session flow_alpha", _transcript_text(app))

    async def test_flow_action_bar_shows_working_badge_for_running_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_running",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_path = flow_dir(root, "flow_running")
            write_json_atomic(flow_path / "workflow_state.json", state)
            runtime_store = FileRuntimeStateStore(flow_path)
            runtime_store.write_pid(os.getpid())
            runtime_store.write_watchdog_state(state="foreground", pid=os.getpid(), note="attached")
            runtime_store.write_run_state(
                run_id="flow_running",
                state="running",
                phase="imp",
                pid=os.getpid(),
                note="attempt 1 phase=imp",
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_running")
                app._back_to_flow()
                app._poll_runtime_surface()
                await pilot.pause(0.1)

                action_bar = str(app.query_one("#action-bar", Static).renderable).lower()
                self.assertIn("working (", action_bar)

    async def test_supervisor_view_prefers_supervisor_raw_session_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_supervisor_raw",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_path = flow_dir(root, "flow_supervisor_raw")
            write_json_atomic(flow_path / "workflow_state.json", state)
            _write_jsonl(
                flow_events_path(flow_path),
                [
                    {
                        "event_id": "evt_sup_raw",
                        "kind": "codex_segment",
                        "lane": "supervisor",
                        "family": "raw_execution",
                        "flow_id": "flow_supervisor_raw",
                        "phase": "plan",
                        "attempt_no": 1,
                        "created_at": "2026-04-02 10:00:00",
                        "title": "supervisor raw output",
                        "message": "{\"decision\":\"execute\"}",
                        "raw_text": "{\"decision\":\"execute\"}",
                        "payload": {
                            "segment": "{\"decision\":\"execute\"}",
                            "source": "supervisor_runtime",
                            "active_role_id": "planner",
                        },
                    }
                ],
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_supervisor_raw")
                app._back_to_flow()
                await pilot.pause(0.1)

                transcript = _transcript_text(app)
                self.assertIn("{\"decision\":\"execute\"}", transcript)
                self.assertIn("[supervisor/output]", transcript)
                self.assertIn("active_role=planner", transcript)

    async def test_flow_transcript_prefers_surface_view_events_over_top_level_timeline_filtering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_surface_first",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            write_json_atomic(flow_dir(root, "flow_surface_first") / "workflow_state.json", state)

            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            payload = {
                "flow_id": "flow_surface_first",
                "timeline": [
                    {
                        "event_id": "evt-system",
                        "kind": "run_started",
                        "lane": "system",
                        "family": "run",
                        "message": "flow started",
                        "created_at": "2026-04-03 10:00:00",
                    },
                    {
                        "event_id": "evt-ignored",
                        "kind": "supervisor_output",
                        "lane": "supervisor",
                        "family": "output",
                        "message": "timeline-only supervisor event",
                        "created_at": "2026-04-03 10:00:01",
                    },
                ],
                "navigator_summary": {
                    "workflow_kind": "project_loop",
                    "effective_status": "running",
                    "effective_phase": "plan",
                    "goal": "alpha",
                    "guard_condition": "done",
                    "approval_state": "operator_required",
                    "active_role_id": "planner",
                },
                "summary": {
                    "workflow_kind": "project_loop",
                    "effective_status": "running",
                    "effective_phase": "plan",
                    "goal": "alpha",
                    "guard_condition": "done",
                    "approval_state": "operator_required",
                    "active_role_id": "planner",
                },
                "supervisor_view": {
                    "header": {
                        "flow_id": "flow_surface_first",
                        "workflow_kind": "project_loop",
                        "status": "running",
                        "phase": "plan",
                        "goal": "alpha",
                        "guard_condition": "done",
                        "active_role_id": "planner",
                        "approval_state": "operator_required",
                    },
                    "pointers": {},
                    "events": [
                        {
                            "event_id": "evt-supervisor",
                            "kind": "supervisor_output",
                            "lane": "supervisor",
                            "family": "output",
                            "message": "surface supervisor event",
                            "created_at": "2026-04-03 10:00:02",
                        }
                    ],
                },
                "workflow_view": {
                    "events": [
                        {
                            "event_id": "evt-workflow",
                            "kind": "artifact_registered",
                            "lane": "workflow",
                            "family": "artifact",
                            "message": "surface workflow event",
                            "created_at": "2026-04-03 10:00:03",
                            "payload": {"artifact_ref": "artifact:9:workflow"},
                        }
                    ]
                },
                "inspector": {},
                "step_history": [],
                "artifacts": [],
                "turns": [],
                "actions": [],
                "handoffs": [],
            }

            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                with mock.patch.object(app._controller, "single_flow_payload", return_value=payload):
                    app._focus_flow("flow_surface_first")
                    app._back_to_flow()
                    await pilot.pause(0.1)

                    transcript = _transcript_text(app)
                    self.assertIn("surface supervisor event", transcript)
                    self.assertNotIn("timeline-only supervisor event", transcript)
                    self.assertIn("status=running", transcript)
                    self.assertIn("phase=plan", transcript)
                    self.assertIn("active_role=planner", transcript)

                    app.on_key(textual_events.Key("shift+tab", None))
                    await pilot.pause(0.1)
                    workflow_transcript = _transcript_text(app)
                    self.assertIn("artifact:9:workflow", workflow_transcript)
                    self.assertNotIn("timeline-only supervisor event", workflow_transcript)

    async def test_supervisor_input_output_render_actual_body_not_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_supervisor_titles",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_path = flow_dir(root, "flow_supervisor_titles")
            write_json_atomic(flow_path / "workflow_state.json", state)
            _write_jsonl(
                flow_events_path(flow_path),
                [
                    {
                        "event_id": "evt_sup_input",
                        "kind": "supervisor_input",
                        "lane": "supervisor",
                        "family": "input",
                        "flow_id": "flow_supervisor_titles",
                        "phase": "plan",
                        "attempt_no": 1,
                        "created_at": "2026-04-02 10:00:00",
                        "title": "supervisor heuristic input",
                        "message": "Please focus on the unresolved blockers.",
                        "raw_text": "Please focus on the unresolved blockers.",
                        "payload": {"active_role_id": "implementer"},
                    },
                    {
                        "event_id": "evt_sup_output",
                        "kind": "supervisor_output",
                        "lane": "supervisor",
                        "family": "output",
                        "flow_id": "flow_supervisor_titles",
                        "phase": "plan",
                        "attempt_no": 1,
                        "created_at": "2026-04-02 10:00:01",
                        "title": "supervisor heuristic output",
                        "message": "decision=execute | next_action=run_executor",
                        "raw_text": "",
                        "payload": {"active_role_id": "implementer"},
                    },
                ],
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_supervisor_titles")
                app._back_to_flow()
                await pilot.pause(0.1)

                transcript = _transcript_text(app)
                self.assertIn("Please focus on the unresolved blockers.", transcript)
                self.assertIn("decision=execute | next_action=run_executor", transcript)
                self.assertNotIn("supervisor heuristic input", transcript)
                self.assertNotIn("supervisor heuristic output", transcript)

    async def test_supervisor_event_with_non_mapping_payload_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_supervisor_bad_payload",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_path = flow_dir(root, "flow_supervisor_bad_payload")
            write_json_atomic(flow_path / "workflow_state.json", state)
            _write_jsonl(
                flow_events_path(flow_path),
                [
                    {
                        "event_id": "evt_sup_bad_payload",
                        "kind": "supervisor_decided",
                        "lane": "supervisor",
                        "family": "decision",
                        "flow_id": "flow_supervisor_bad_payload",
                        "phase": "synthesize",
                        "attempt_no": 32,
                        "created_at": "2026-04-02 10:00:00",
                        "title": "",
                        "message": "follow pending instruction from previous judge/recovery via role=implementer",
                        "raw_text": "",
                        "payload": "corrupted-payload",
                    }
                ],
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_supervisor_bad_payload")
                app._back_to_flow()
                await pilot.pause(0.1)

                transcript = _transcript_text(app)
                self.assertIn("follow pending instruction from previous judge/recovery via role=implementer", transcript)

    async def test_supervisor_event_with_string_decision_field_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_supervisor_string_decision",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_path = flow_dir(root, "flow_supervisor_string_decision")
            write_json_atomic(flow_path / "workflow_state.json", state)
            _write_jsonl(
                flow_events_path(flow_path),
                [
                    {
                        "event_id": "evt_sup_string_decision",
                        "kind": "supervisor_decided",
                        "lane": "supervisor",
                        "family": "decision",
                        "flow_id": "flow_supervisor_string_decision",
                        "phase": "synthesize",
                        "attempt_no": 32,
                        "created_at": "2026-04-02 10:00:00",
                        "title": "",
                        "message": "follow pending instruction from previous judge/recovery via role=implementer",
                        "raw_text": "",
                        "payload": {
                            "decision": "execute",
                            "active_role_id": "implementer",
                            "next_action": "run_executor",
                        },
                    }
                ],
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_supervisor_string_decision")
                app._back_to_flow()
                await pilot.pause(0.1)

                transcript = _transcript_text(app)
                self.assertIn("follow pending instruction from previous", transcript)
                self.assertIn("judge/recovery via role=implementer", transcript)
                self.assertIn("active_role=implementer", transcript)

    async def test_history_plain_text_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                with mock.patch.object(app, "notify") as notify:
                    command_input = app._command_input()
                    command_input.value = "just text"
                    app.on_input_submitted(Input.Submitted(command_input, "just text", None))
                    await pilot.pause(0.1)
                    notify.assert_called_once()
                    self.assertIn("History view only accepts slash commands.", notify.call_args.args[0])

    async def test_new_command_opens_setup_screen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._handle_command("new", ["ship", "tui"])
                await pilot.pause(0.1)
                self.assertEqual(app._view_mode, "setup")
                self.assertEqual(app._setup_stage, "mode")
                self.assertIs(app.screen.focused, app.query_one("#setup-list", ListView))

    async def test_new_setup_flow_path_orders_mode_then_catalog_then_level(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._handle_command("new", [])
                await pilot.pause(0.1)

                self.assertEqual(app._setup_stage, "mode")
                app._apply_setup_selection("flow")
                await pilot.pause(0.1)
                self.assertEqual(app._setup_stage, "catalog")

                app._apply_setup_selection("project_loop")
                await pilot.pause(0.1)
                self.assertEqual(app._setup_stage, "level")

                setup_detail = str(app.query_one("#setup-detail", Static).renderable)
                self.assertIn("mode=flow", setup_detail)
                self.assertIn("catalog=project_loop", setup_detail)

    async def test_printable_key_from_history_re_focuses_command_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            write_json_atomic(
                flow_dir(root, "flow_alpha") / "workflow_state.json",
                new_flow_state(
                    workflow_id="flow_alpha",
                    workflow_kind="project_loop",
                    workspace_root=str(root),
                    goal="alpha",
                    guard_condition="done",
                    max_attempts=4,
                    max_phase_attempts=2,
                ),
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._handle_command("history", [])
                await pilot.pause(0.1)
                self.assertIs(app.screen.focused, app.query_one("#history-list", ListView))

                await pilot.press("x")
                await pilot.pause(0.1)

                command_input = app._command_input()
                self.assertIs(app.screen.focused, command_input)
                self.assertEqual(command_input.value, "x")

                await pilot.press("down")
                await pilot.pause(0.1)

                history_list = app.query_one("#history-list", ListView)
                self.assertIs(app.screen.focused, history_list)

    async def test_tab_accepts_command_suggestion_without_changing_focus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                command_input = app._command_input()
                command_input.focus()
                command_input.value = "/man"
                command_input.cursor_position = len(command_input.value)
                await pilot.pause(0.3)

                self.assertTrue(getattr(command_input, "_suggestion", ""))
                await pilot.press("tab")
                await pilot.pause(0.1)

                self.assertIs(app.screen.focused, command_input)
                self.assertEqual(command_input.value, "/manage")

    async def test_view_switches_do_not_force_full_snapshot_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            write_json_atomic(
                flow_dir(root, "flow_alpha") / "workflow_state.json",
                new_flow_state(
                    workflow_id="flow_alpha",
                    workflow_kind="project_loop",
                    workspace_root=str(root),
                    goal="alpha",
                    guard_condition="done",
                    max_attempts=4,
                    max_phase_attempts=2,
                ),
            )
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                with mock.patch.object(app, "_refresh_snapshot") as mocked_refresh:
                    app._handle_command("history", [])
                    await pilot.pause(0.1)
                    app._handle_command("settings", [])
                    await pilot.pause(0.1)
                    app._handle_command("flows", [])
                    await pilot.pause(0.1)
                    app._handle_command("back", [])
                    await pilot.pause(0.1)
                mocked_refresh.assert_not_called()

    async def test_settings_screen_cycles_session_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._handle_command("settings", [])
                await pilot.pause(0.1)
                self.assertEqual(app._view_mode, "settings")

                app._settings_cursor_key = "auto_follow"
                app.action_open_selected()
                await pilot.pause(0.1)
                self.assertFalse(app._session_preferences["auto_follow"])

                app._settings_cursor_key = "transcript_filter"
                app.action_open_selected()
                await pilot.pause(0.1)
                self.assertEqual(app._session_preferences["transcript_filter"], "assistant")

    async def test_transcript_near_bottom_snaps_back_to_end_but_manual_scroll_stays_put(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_alpha",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            write_json_atomic(flow_dir(root, "flow_alpha") / "workflow_state.json", state)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_alpha")
                app._back_to_flow()
                await pilot.pause(0.1)
                transcript = app.query_one("#transcript", RichLog)
                for index in range(80):
                    app._write_transcript_note(family="timeline", body=f"line {index}")
                await pilot.pause(0.1)

                transcript.scroll_to(y=max(0, transcript.max_scroll_y - 6), animate=False, immediate=True)
                await pilot.pause(0.1)
                app._write_transcript_note(family="timeline", body="tail snap")
                await pilot.pause(0.1)
                self.assertEqual(transcript.scroll_offset.y, transcript.max_scroll_y)

                manual_y = max(0, transcript.max_scroll_y - 12)
                transcript.scroll_to(y=manual_y, animate=False, immediate=True)
                await pilot.pause(0.1)
                app._write_transcript_note(family="timeline", body="stay put")
                await pilot.pause(0.1)
                self.assertLess(transcript.scroll_offset.y, transcript.max_scroll_y)

    async def test_flow_page_page_keys_scroll_transcript_and_snap_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_alpha",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            write_json_atomic(flow_dir(root, "flow_alpha") / "workflow_state.json", state)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_alpha")
                app._back_to_flow()
                await pilot.pause(0.1)
                self.assertTrue(app._command_input_has_focus())

                transcript = app.query_one("#transcript", RichLog)
                for index in range(120):
                    app._write_transcript_note(family="timeline", body=f"line {index}")
                await pilot.pause(0.1)

                bottom_y = transcript.max_scroll_y
                await pilot.press("pageup")
                await pilot.pause(0.1)
                self.assertLess(transcript.scroll_offset.y, bottom_y)

                await pilot.press("pagedown")
                await pilot.pause(0.1)
                self.assertEqual(transcript.scroll_offset.y, transcript.max_scroll_y)

                await pilot.press("home")
                await pilot.pause(0.1)
                self.assertEqual(transcript.scroll_offset.y, 0)

                await pilot.press("end")
                await pilot.pause(0.1)
                self.assertEqual(transcript.scroll_offset.y, transcript.max_scroll_y)

    async def test_flow_streams_restore_manual_scroll_per_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            state = new_flow_state(
                workflow_id="flow_alpha",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="alpha",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_path = flow_dir(root, "flow_alpha")
            write_json_atomic(flow_path / "workflow_state.json", state)
            rows = []
            for index in range(80):
                rows.append(
                    {
                        "event_id": f"sup-{index}",
                        "kind": "supervisor_decided",
                        "flow_id": "flow_alpha",
                        "lane": "supervisor",
                        "family": "decision",
                        "created_at": f"2026-04-02 10:00:{index:02d}",
                        "title": "Supervisor",
                        "message": f"supervisor {index}",
                        "payload": {},
                    }
                )
                rows.append(
                    {
                        "event_id": f"wf-{index}",
                        "kind": "codex_runtime_event",
                        "flow_id": "flow_alpha",
                        "lane": "workflow",
                        "family": "raw_execution",
                        "created_at": f"2026-04-02 10:01:{index:02d}",
                        "title": "stdout",
                        "message": f"workflow {index}",
                        "raw_text": f"workflow {index}",
                        "payload": {"kind": "stdout"},
                    }
                )
            _write_jsonl(flow_events_path(flow_path), rows)

            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                app._focus_flow("flow_alpha")
                app._back_to_flow()
                await pilot.pause(0.1)

                transcript = app.query_one("#transcript", RichLog)
                supervisor_y = max(0, transcript.max_scroll_y - 18)
                transcript.scroll_to(y=supervisor_y, animate=False, immediate=True)
                await pilot.pause(0.1)

                app.on_key(textual_events.Key("shift+tab", None))
                await pilot.pause(0.1)
                workflow_y = max(0, transcript.max_scroll_y - 10)
                transcript.scroll_to(y=workflow_y, animate=False, immediate=True)
                await pilot.pause(0.1)

                app.on_key(textual_events.Key("shift+tab", None))
                await pilot.pause(0.1)
                self.assertEqual(transcript.scroll_offset.y, min(supervisor_y, transcript.max_scroll_y))

                app.on_key(textual_events.Key("shift+tab", None))
                await pilot.pause(0.1)
                self.assertEqual(transcript.scroll_offset.y, min(workflow_y, transcript.max_scroll_y))

    async def test_manage_transcript_follow_preference_and_near_bottom_snap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause(0.2)
                app._handle_command("manage", [])
                await pilot.pause(0.1)

                manage_transcript = app.query_one("#manage-transcript", RichLog)
                self.assertTrue(manage_transcript.auto_scroll)

                app._handle_command("follow", ["off"])
                await pilot.pause(0.1)
                self.assertFalse(manage_transcript.auto_scroll)

                app._handle_command("follow", ["on"])
                await pilot.pause(0.1)
                self.assertTrue(manage_transcript.auto_scroll)

                for index in range(80):
                    app._write_manage_note(family="manage", body=f"note {index}")
                await pilot.pause(0.1)

                manage_transcript.scroll_to(y=max(0, manage_transcript.max_scroll_y - 2), animate=False, immediate=True)
                await pilot.pause(0.1)
                app._write_manage_note(family="manage", body="tail snap")
                await pilot.pause(0.1)
                self.assertEqual(manage_transcript.scroll_offset.y, manage_transcript.max_scroll_y)

                manual_y = max(0, manage_transcript.max_scroll_y - 12)
                manage_transcript.scroll_to(y=manual_y, animate=False, immediate=True)
                await pilot.pause(0.1)
                app._write_manage_note(family="manage", body="stay put")
                await pilot.pause(0.1)
                self.assertLess(manage_transcript.scroll_offset.y, manage_transcript.max_scroll_y)

    async def test_background_run_error_does_not_leave_tui_stuck_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_state = new_flow_state(
                workflow_id="flow_tui_error",
                workflow_kind="project_loop",
                workspace_root=str(root),
                goal="ship tui",
                guard_condition="verified",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_path = flow_dir(root, "flow_tui_error")
            write_json_atomic(flow_path / "workflow_state.json", flow_state)
            prepared = PreparedFlowRun(
                cfg={"workspace_root": str(root)},
                config_path=config,
                workspace_root=str(root),
                flow_path=flow_path,
                flow_state=flow_state,
            )

            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            with mock.patch.object(app._controller, "prepare_run", return_value=prepared), \
                 mock.patch.object(app._controller, "execute_prepared_flow", side_effect=RuntimeError("boom")):
                async with app.run_test() as pilot:
                    app._begin_run(prepared, stream_enabled=True)
                    for _ in range(20):
                        await pilot.pause(0.05)
                        if not app._attached_run_active:
                            break

                    transcript = _transcript_text(app)
                    self.assertFalse(app._attached_run_active)
                    self.assertIn("[system/error]", transcript)
                    self.assertIn(" flow=flow_tui_error RuntimeError: boom", transcript)

    async def test_manage_center_opens_from_flows_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = ButlerFlowTuiApp(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                initial_args=Namespace(config=config),
                initial_mode="launcher",
            )
            async with app.run_test() as pilot:
                await pilot.pause(0.2)
                app._handle_command("flows", [])
                await pilot.pause(0.1)
                self.assertEqual(app._view_mode, "flows")
                self.assertEqual(app._flows_screen_mode, "manage")


if __name__ == "__main__":
    unittest.main()
