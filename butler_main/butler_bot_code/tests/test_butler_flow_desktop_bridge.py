from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from butler_main.butler_flow.desktop_bridge import main
from butler_main.butler_flow.state import (
    append_manage_turn,
    flow_artifacts_path,
    flow_dir,
    flow_state_path,
    new_flow_state,
    write_manage_draft,
    write_manage_pending_action,
    write_manage_session,
    write_json_atomic,
)


def _config_path(root: Path) -> str:
    path = root / "butler_flow_desktop_bridge_config.json"
    path.write_text(json.dumps({"workspace_root": str(root)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _seed_flow(root: Path, *, flow_id: str) -> None:
    path = flow_dir(root, flow_id)
    state = new_flow_state(
        workflow_id=flow_id,
        workflow_kind="managed_flow",
        workspace_root=str(root),
        goal="ship desktop shell",
        guard_condition="verified",
        max_attempts=8,
        max_phase_attempts=4,
    )
    state["status"] = "running"
    state["current_phase"] = "build"
    state["execution_mode"] = "medium"
    state["session_strategy"] = "role_bound"
    state["active_role_id"] = "implementer"
    write_json_atomic(flow_state_path(path), state)
    write_json_atomic(
        flow_artifacts_path(path),
        {
            "items": [
                {
                    "artifact_ref": "artifact://desktop/workbench",
                    "phase": "build",
                    "attempt_no": 1,
                }
            ]
        },
    )


def _seed_manager_session(root: Path, *, manager_session_id: str) -> None:
    write_manage_session(
        root,
        manager_session_id,
        {
            "manager_session_id": manager_session_id,
            "active_manage_target": "new",
            "manager_stage": "requirements",
            "confirmation_scope": "flow_create",
            "updated_at": "2026-04-05 12:40:00",
        },
    )
    write_manage_draft(
        root,
        manager_session_id,
        {
            "manage_target": "new",
            "asset_kind": "instance",
            "label": "Desktop 线程工作台",
            "workflow_kind": "managed_flow",
            "goal": "重构 desktop shell",
        },
    )
    write_manage_pending_action(
        root,
        manager_session_id,
        {
            "manage_target": "new",
            "preview": "Create Team + Supervisor",
        },
    )
    append_manage_turn(
        root,
        manager_session_id,
        {
            "created_at": "2026-04-05 12:20:00",
            "manage_target": "new",
            "instruction": "先把想法收敛",
            "response": "Manager 已整理出 thread-first IA。",
            "parse_status": "ok",
            "raw_reply": "",
            "error_text": "",
            "session_recovery": {},
            "manager_stage": "idea",
            "draft": {
                "label": "Desktop 线程工作台",
                "goal": "重构 desktop shell",
            },
            "pending_action": {},
            "action_ready": False,
        },
    )


class ButlerFlowDesktopBridgeTests(unittest.TestCase):
    def test_home_command_emits_workspace_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            _seed_flow(root, flow_id="flow_desktop_bridge")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(["--config", config, "home"])

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["flows"]["items"][0]["flow_id"], "flow_desktop_bridge")

    def test_flow_command_emits_single_flow_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            _seed_flow(root, flow_id="flow_desktop_bridge")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(["--config", config, "flow", "--flow-id", "flow_desktop_bridge"])

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["flow_id"], "flow_desktop_bridge")
            self.assertEqual(payload["workflow_view"]["artifact_refs"], ["artifact://desktop/workbench"])

    def test_thread_commands_emit_thread_first_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            _seed_flow(root, flow_id="flow_desktop_bridge")
            _seed_manager_session(root, manager_session_id="manager_session_bridge")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(["--config", config, "thread-home"])

            home = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(home["manager_entry"]["default_manager_session_id"], "manager_session_bridge")

            manager_buffer = io.StringIO()
            with redirect_stdout(manager_buffer):
                exit_code = main(
                    ["--config", config, "manager-thread", "--manager-session-id", "manager_session_bridge"]
                )

            manager = json.loads(manager_buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(manager["thread"]["thread_kind"], "manager")
            self.assertEqual(manager["blocks"][0]["kind"], "idea")

            supervisor_buffer = io.StringIO()
            with redirect_stdout(supervisor_buffer):
                exit_code = main(["--config", config, "supervisor-thread", "--flow-id", "flow_desktop_bridge"])

            supervisor = json.loads(supervisor_buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(supervisor["thread"]["thread_kind"], "supervisor")

    def test_manager_message_launch_does_not_depend_on_thread_home_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            _seed_manager_session(root, manager_session_id="manager_session_bridge")
            chat_payload = {
                "manager_session_id": "manager_session_bridge",
                "action": "manage_flow",
                "action_ready": True,
                "action_manage_target": "new",
                "action_goal": "ship desktop shell",
                "action_guard_condition": "verified",
                "action_instruction": "launch now",
                "action_stage": "launch",
                "action_builtin_mode": "greenfield",
                "action_draft": {"label": "Desktop 线程工作台"},
                "response": "准备创建 flow。",
            }
            launched_flow = {
                "flow_id": "flow_created_from_manager",
                "summary": "Flow created and handed off to Supervisor: flow_created_from_manager",
            }

            with (
                patch(
                    "butler_main.butler_flow.desktop_bridge._invoke_app_json",
                    side_effect=[chat_payload, launched_flow],
                ),
                patch(
                    "butler_main.butler_flow.desktop_bridge.thread_home_payload",
                    side_effect=AssertionError("thread_home_payload should not be called"),
                ),
                patch(
                    "butler_main.butler_flow.desktop_bridge.manager_thread_payload",
                    return_value={"thread": {"thread_kind": "manager"}, "blocks": []},
                ),
            ):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    exit_code = main(
                        [
                            "--config",
                            config,
                            "manager-message",
                            "--instruction",
                            "launch now",
                            "--manager-session-id",
                            "manager_session_bridge",
                        ]
                    )

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["launched_flow"]["flow_id"], "flow_created_from_manager")
            self.assertEqual(payload["thread"]["thread"]["thread_kind"], "manager")


if __name__ == "__main__":
    unittest.main()
