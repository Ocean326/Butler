import importlib.util
from pathlib import Path
import shutil
import sys
import unittest
import uuid


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
REPO_ROOT = Path(__file__).resolve().parents[3]
TMP_ROOT = REPO_ROOT / "_tmp_test_harness"
sys.path.insert(0, str(MODULE_DIR))

from memory_manager import MemoryManager  # noqa: E402
from services.task_ledger_service import TaskLedgerService  # noqa: E402


SPEC = importlib.util.spec_from_file_location("butler_bot_module", MODULE_DIR / "butler_bot.py")
BUTLER_BOT = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(BUTLER_BOT)


class ExplicitHeartbeatTaskProtocolTests(unittest.TestCase):
    def _make_workspace(self) -> Path:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        workspace = TMP_ROOT / f"explicit_task_{uuid.uuid4().hex[:8]}"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def _cleanup_workspace(self, workspace: Path) -> None:
        shutil.rmtree(workspace, ignore_errors=True)

    def _build_manager(self, workspace: Path) -> MemoryManager:
        return MemoryManager(
            config_provider=lambda: {"workspace_root": str(workspace), "agent_model": "auto", "agent_timeout": 60},
            run_model_fn=lambda *_args, **_kwargs: ("", False),
        )

    def test_memory_manager_explicit_add_cancel_and_complete(self):
        workspace = self._make_workspace()
        try:
            manager = self._build_manager(workspace)

            added = manager.handle_explicit_heartbeat_task_command(str(workspace), "放进心跳：整理周报")
            self.assertIsNotNone(added)
            self.assertIn("已放入心跳任务", str(added.get("reply") or ""))

            ledger_payload = TaskLedgerService(str(workspace)).load()
            first_item = next(item for item in (ledger_payload.get("items") or []) if str(item.get("title") or "") == "整理周报")
            first_task_id = str(first_item.get("task_id") or "")

            cancelled = manager.handle_explicit_heartbeat_task_command(str(workspace), f"取消心跳任务 task_id={first_task_id}")
            self.assertIsNotNone(cancelled)
            self.assertIn("已取消心跳任务", str(cancelled.get("reply") or ""))

            ledger_payload = TaskLedgerService(str(workspace)).load()
            cancelled_item = next(item for item in (ledger_payload.get("items") or []) if str(item.get("task_id") or "") == first_task_id)
            self.assertEqual(str(cancelled_item.get("status") or ""), "closed")

            added_second = manager.handle_explicit_heartbeat_task_command(str(workspace), "放进心跳：整理月报")
            self.assertIsNotNone(added_second)
            self.assertIn("已放入心跳任务", str(added_second.get("reply") or ""))

            ledger_payload = TaskLedgerService(str(workspace)).load()
            second_item = next(item for item in (ledger_payload.get("items") or []) if str(item.get("title") or "") == "整理月报")
            second_task_id = str(second_item.get("task_id") or "")

            completed = manager.handle_explicit_heartbeat_task_command(str(workspace), f"完成心跳任务 task_id={second_task_id}")
            self.assertIsNotNone(completed)
            self.assertIn("已标记心跳任务完成", str(completed.get("reply") or ""))

            ledger_payload = TaskLedgerService(str(workspace)).load()
            completed_item = next(item for item in (ledger_payload.get("items") or []) if str(item.get("task_id") or "") == second_task_id)
            self.assertEqual(str(completed_item.get("status") or ""), "done")
        finally:
            self._cleanup_workspace(workspace)

    def test_run_agent_short_circuits_explicit_task_command_without_cli(self):
        workspace = self._make_workspace()
        try:
            manager = self._build_manager(workspace)
            original_memory = BUTLER_BOT.MEMORY
            original_get_config = BUTLER_BOT.get_config
            original_run_agent_via_cli = BUTLER_BOT._run_agent_via_cli
            try:
                BUTLER_BOT.MEMORY = manager
                BUTLER_BOT.get_config = lambda: {"workspace_root": str(workspace), "agent_timeout": 60, "agent_model": "auto"}

                def _should_not_run_cli(*_args, **_kwargs):
                    raise AssertionError("explicit heartbeat task command should not call CLI")

                BUTLER_BOT._run_agent_via_cli = _should_not_run_cli
                reply = BUTLER_BOT.run_agent("放进心跳：整理测试任务")
                self.assertIn("已放入心跳任务", reply)
                self.assertTrue(bool(getattr(BUTLER_BOT.TURN_CONTEXT, "turn_suppress_task_merge", False)))
            finally:
                BUTLER_BOT.MEMORY = original_memory
                BUTLER_BOT.get_config = original_get_config
                BUTLER_BOT._run_agent_via_cli = original_run_agent_via_cli
                for attr_name in ("pending_memory_id", "turn_model", "turn_cli_request", "turn_user_prompt", "post_reply_action", "turn_suppress_task_merge"):
                    if hasattr(BUTLER_BOT.TURN_CONTEXT, attr_name):
                        delattr(BUTLER_BOT.TURN_CONTEXT, attr_name)
        finally:
            self._cleanup_workspace(workspace)


if __name__ == "__main__":
    unittest.main()

