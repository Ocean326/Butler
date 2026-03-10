import tempfile
from pathlib import Path
import sys
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

from task_ledger_service import TaskLedgerService  # noqa: E402


class TaskLedgerServiceTests(unittest.TestCase):
    def test_bootstrap_from_legacy_short_and_long_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            service = TaskLedgerService(str(workspace))
            payload = service.ensure_bootstrapped(
                short_tasks=[
                    {
                        "task_id": "task-1",
                        "title": "整理待办",
                        "detail": "整理待办摘要",
                        "status": "pending",
                    }
                ],
                long_tasks=[
                    {
                        "task_id": "long-1",
                        "title": "每日提醒",
                        "detail": "提醒",
                        "schedule_type": "daily",
                        "schedule_value": "09:00",
                    }
                ],
            )

            items = payload["items"]
            self.assertEqual(len(items), 2)
            self.assertEqual({item["task_type"] for item in items}, {"short", "long"})
            self.assertTrue(service.path.exists())

    def test_apply_heartbeat_result_updates_items_and_records_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            service = TaskLedgerService(str(workspace))
            service.ensure_bootstrapped(
                short_tasks=[
                    {
                        "task_id": "task-1",
                        "title": "整理待办",
                        "detail": "整理待办摘要",
                        "status": "pending",
                    }
                ],
                long_tasks=[
                    {
                        "task_id": "long-1",
                        "title": "每日提醒",
                        "detail": "提醒",
                        "schedule_type": "daily",
                        "schedule_value": "09:00",
                        "next_due_at": "2026-03-07 09:00:00",
                    }
                ],
            )

            payload = service.apply_heartbeat_result(
                {
                    "chosen_mode": "parallel",
                    "execution_mode": "parallel",
                    "updates": {"complete_task_ids": ["task-1"], "touch_long_task_ids": []},
                    "deferred_task_ids": [],
                },
                "已完成短期任务和长期提醒",
                [
                    {"branch_id": "b1", "ok": True, "complete_task_ids": ["task-1"], "touch_long_task_ids": ["long-1"], "defer_task_ids": []}
                ],
            )

            items = {item["task_id"]: item for item in payload["items"]}
            self.assertEqual(items["task-1"]["status"], "done")
            self.assertTrue(items["long-1"]["last_run_at"])
            self.assertNotEqual(items["long-1"]["next_due_at"], "2026-03-07 09:00:00")
            self.assertEqual(len(payload["runs"]), 1)

            workspace_file = service.task_workspaces_dir / "task-1.json"
            self.assertTrue(workspace_file.exists())

    def test_render_task_workspace_context_includes_recent_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            service = TaskLedgerService(str(workspace))
            service.ensure_bootstrapped(
                short_tasks=[
                    {
                        "task_id": "task-1",
                        "title": "测 30 条耗时",
                        "detail": "在当前 chat_id 上测一次拉取 30 条消息耗时",
                        "status": "pending",
                    }
                ]
            )

            service.apply_heartbeat_result(
                {
                    "run_id": "run-1",
                    "chosen_mode": "short_task",
                    "execution_mode": "single",
                    "reason": "优先续接未完成任务",
                    "selected_task_ids": ["task-1"],
                    "updates": {"complete_task_ids": [], "touch_long_task_ids": [], "defer_task_ids": []},
                    "deferred_task_ids": [],
                },
                "已创建测速脚本并准备执行。",
                [
                    {
                        "branch_id": "short-task-1",
                        "ok": True,
                        "selected_task_ids": ["task-1"],
                        "complete_task_ids": [],
                        "touch_long_task_ids": [],
                        "defer_task_ids": [],
                        "output": "已创建 temp/latency_test.py，并记录下一步需要实际调用一次接口。",
                    }
                ],
            )

            context = service.render_task_workspaces_context()
            self.assertIn("测 30 条耗时", context)
            self.assertIn("最近动作", context)
            self.assertIn("short-task-1", context)


if __name__ == "__main__":
    unittest.main()
