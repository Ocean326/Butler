import tempfile
from pathlib import Path
import sys
from datetime import datetime
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

from memory_manager import MemoryManager  # noqa: E402


class HeartbeatProactiveTalkTests(unittest.TestCase):
    def _manager(self, workspace: str) -> MemoryManager:
        return MemoryManager(
            config_provider=lambda: {"workspace_root": workspace},
            run_model_fn=lambda *_: ("", False),
        )

    def test_proactive_talk_default_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager(tmp)
            policy = manager._resolve_proactive_talk_policy({})
            self.assertTrue(policy["enabled"])
            self.assertGreaterEqual(policy["min_interval_seconds"], 10)
            self.assertEqual(policy["min_heartbeat_runs_since_last"], 3)
            self.assertEqual(policy["min_completed_branches"], 2)
            self.assertEqual(policy["defer_if_recent_talk_seconds"], 180)
            self.assertFalse(policy["allow_light_chat"])

    def test_build_next_round_intent_from_latest_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager(tmp)
            plan = {
                "chosen_mode": "short_task",
                "execution_mode": "single",
                "reason": "这轮收口了一个阶段成果",
                "user_message": "本轮先把文档整理收口。",
                "tell_user_candidate": "我刚把这轮文档整理到一个可复用版本了。",
                "tell_user_reason": "这轮形成了一个适合自然同步给用户的阶段成果。",
                "tell_user_type": "result_share",
                "tell_user_priority": 75,
                "updates": {"complete_task_ids": ["task-a"]},
            }
            branch_results = [{"branch_id": "b1", "ok": True, "complete_task_ids": ["task-a"], "output": "已完成整理"}]
            manager._persist_heartbeat_snapshot_to_recent(tmp, plan, branch_results, "已完成整理", 1)

            intent = manager._build_reflective_tell_user_intent_for_next_round(tmp, plan, {"proactive_talk": {"enabled": True}})

            self.assertEqual(intent["status"], "pending")
            self.assertEqual(intent["share_type"], "result_share")
            self.assertEqual(intent["share_priority"], 75)
            self.assertIn("可复用版本", intent["candidate"])

    def test_build_next_round_growth_intent_from_latest_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager(tmp)
            plan = {
                "chosen_mode": "short_task",
                "execution_mode": "single",
                "reason": "这轮补上了新的外部能力接入思路",
                "user_message": "本轮把缺能力问题推进成可重试闭环。",
                "tell_user_candidate": "我刚把一个新能力接进来，后面可以直接拿它继续干活了。",
                "tell_user_reason": "这轮不只是调研，而是真的补上了一项能继续服务用户的新能力。",
                "tell_user_type": "growth_share",
                "updates": {"complete_task_ids": ["task-growth"]},
            }
            branch_results = [{"branch_id": "b1", "ok": True, "complete_task_ids": ["task-growth"], "output": "已完成能力接入并回到原任务重试"}]
            manager._persist_heartbeat_snapshot_to_recent(tmp, plan, branch_results, "已完成能力接入并回到原任务重试", 1)

            intent = manager._build_reflective_tell_user_intent_for_next_round(tmp, plan, {"proactive_talk": {"enabled": True}})

            self.assertEqual(intent["status"], "pending")
            self.assertEqual(intent["share_type"], "growth_share")
            self.assertEqual(intent["share_priority"], 65)
            self.assertIn("新能力", intent["share_reason"])

    def test_pending_intent_is_written_into_self_mind_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager(tmp)
            intent = {
                "status": "pending",
                "share_type": "thought_share",
                "share_reason": "上一轮留下了还想继续说的一句。",
                "candidate": "我刚又顺着想了一下，有个点想跟你接着聊。",
                "source_memory_id": "beat-1",
            }

            manager._remember_reflective_tell_user_intent(tmp, intent)

            context_path = Path(tmp) / "butler_main" / "butle_bot_space" / "self_mind" / "current_context.md"
            log_dir = Path(tmp) / "butler_main" / "butle_bot_space" / "self_mind" / "logs"
            self.assertTrue(context_path.exists())
            self.assertTrue(log_dir.exists())
            self.assertIn("当前想说的话头", context_path.read_text(encoding="utf-8"))

    def test_previous_intent_defers_when_talk_window_is_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager(tmp)
            manager._save_recent_entries(
                tmp,
                [
                    {
                        "memory_id": "talk-1",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "topic": "用户刚发来新消息",
                        "summary": "继续讨论 Butler 设计。",
                        "memory_stream": "talk",
                        "event_type": "conversation_turn",
                        "status": "completed",
                    }
                ],
            )
            manager._save_heartbeat_tell_user_intent(
                tmp,
                {
                    "status": "pending",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "created_epoch": __import__("time").time(),
                    "share_type": "thought_share",
                    "share_priority": 60,
                    "share_reason": "上一轮留下了还想继续聊一句的心理活动。",
                    "candidate": "我刚又顺着想了一下，有个点想跟你接着聊。",
                },
            )

            text, updated_intent = manager._continue_reflective_tell_user(
                tmp,
                {"proactive_talk": {"enabled": True, "defer_if_recent_talk_seconds": 600}},
                60,
                "auto",
            )

            self.assertEqual(text, "")
            self.assertTrue(updated_intent["deferred_for_user_activity"])
            self.assertEqual(updated_intent["deferred_reason"], "talk-window-active")

    def test_compose_reflective_tell_user_uses_feishu_persona_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            captured = {"prompt": ""}

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                captured["prompt"] = prompt
                return "我刚刚顺着上一轮又想了一下，想先跟你同步个小进展。", True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": tmp},
                run_model_fn=fake_model,
            )
            text = manager._compose_reflective_tell_user_text_via_feishu(
                tmp,
                {
                    "share_type": "thought_share",
                    "candidate": "刚刚整理完之后，我有个后续想法。",
                    "share_reason": "上一轮心理活动里留下了还想继续说的一句。",
                    "mental_context": ["这轮先把结构理顺了"],
                    "relationship_context": ["用户更喜欢自然一点的表达"],
                },
                "我刚刚又顺着这个念头多想了一层。",
                60,
                "auto",
            )

            self.assertIn("feishu-workstation-agent", captured["prompt"])
            self.assertIn("Butler 主意识摘录", captured["prompt"])
            self.assertIn("self_mind 当前上下文", captured["prompt"])
            self.assertIn("上一轮想说的话头", captured["prompt"])
            self.assertIn("刚刚整理完之后", captured["prompt"])
            self.assertTrue(text.startswith("我刚刚顺着上一轮又想了一下"))

    def test_compose_reflective_tell_user_growth_share_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager(tmp)
            text = manager._compose_reflective_tell_user_fallback(
                {
                    "share_type": "growth_share",
                    "candidate": "我现在新会了一条能力接入路径，后面可以直接拿来补缺口。",
                    "share_reason": "这轮补上了一个稳定能力点。",
                }
            )

            self.assertIn("新长出来的能力点", text)
            self.assertIn("能力接入路径", text)


if __name__ == "__main__":
    unittest.main()
