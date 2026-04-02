from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from butler_main.chat.memory_runtime import ChatSummaryPipelineRuntime
from butler_main.chat.pathing import LOCAL_MEMORY_DIR_REL


class ChatSummaryPipelineRuntimeTests(unittest.TestCase):
    def test_govern_long_term_summary_writes_local_memory_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt_output = json.dumps(
                {
                    "should_write": True,
                    "title": "稳定工作偏好",
                    "category": "preferences",
                    "current_conclusion": "当前结论: 用户偏好直接给结果。",
                    "history_evolution": ["2026-03-26：由 summary pool 治理写入"],
                    "applicable_scenarios": ["代码改动", "任务推进"],
                    "keywords": ["偏好", "结果导向"],
                },
                ensure_ascii=False,
            )

            def fake_runner(prompt, workspace, timeout, cfg, runtime_request, stream=False):
                return prompt_output, True

            runtime = ChatSummaryPipelineRuntime(
                config_provider=lambda: {"workspace_root": str(root), "agent_model": "gpt-5.4"},
                prompt_runner=fake_runner,
            )

            result = runtime.govern_long_term_summary(
                {
                    "summary_id": "sum_1",
                    "title": "窗口一",
                    "summary_text": "窗口一总结",
                    "window_start_seq": 1,
                    "window_end_seq": 10,
                    "requirements": ["以后优先直接给结果"],
                    "user_preferences_updates": ["更偏好少解释多结果"],
                },
                workspace=str(root),
                timeout=30,
                model="gpt-5.4",
            )

            local_root = root / LOCAL_MEMORY_DIR_REL
            summary_path = local_root / "L1_summaries" / "稳定工作偏好.md"
            journal_path = local_root / "local_memory_write_journal.jsonl"

            self.assertEqual(result["status"], "written")
            self.assertTrue(summary_path.exists())
            self.assertTrue(journal_path.exists())
            self.assertIn("当前结论: 用户偏好直接给结果。", summary_path.read_text(encoding="utf-8"))
            self.assertIn("summary_pool_governed", journal_path.read_text(encoding="utf-8"))

    def test_summarize_window_falls_back_when_runner_returns_invalid_json(self) -> None:
        runtime = ChatSummaryPipelineRuntime(
            config_provider=lambda: {"workspace_root": ".", "agent_model": "gpt-5.4"},
            prompt_runner=lambda *args, **kwargs: ("not-json", True),
        )

        result = runtime.summarize_window(
            [
                {
                    "memory_id": "mem_1",
                    "turn_seq": 1,
                    "topic": "修 recent 注入",
                    "user_prompt": "把 recent 注入改成 10 + 10000",
                    "assistant_reply_visible": "正在调整 recent 注入和 summary pool。",
                    "process_events": [{"kind": "command", "text": "rg -n recent_memory", "status": "completed"}],
                }
            ]
            * 10,
            [],
            workspace=".",
            timeout=30,
            model="gpt-5.4",
        )

        self.assertIn("window_summary", result)
        self.assertEqual(result["summary_patches"], [])
        self.assertIn("summary_text", result["window_summary"])
        self.assertEqual(result["window_summary"]["user_summary"], result["window_summary"]["summary_text"])
        self.assertIn("执行过", result["window_summary"]["process_reflection"])

    def test_summarize_window_keeps_user_summary_and_process_reflection_separate(self) -> None:
        prompt_output = json.dumps(
            {
                "window_summary": {
                    "title": "窗口一",
                    "summary_text": "用户主线摘要",
                    "user_summary": "用户主线摘要",
                    "process_reflection": "这轮先检索再改 recent，过程里发现一处回写缺口。",
                    "topics": ["recent memory"],
                    "requirements": ["保留过程记录"],
                    "open_loops": ["补测试"],
                    "user_preferences_updates": [],
                },
                "summary_patches": [],
            },
            ensure_ascii=False,
        )
        runtime = ChatSummaryPipelineRuntime(
            config_provider=lambda: {"workspace_root": ".", "agent_model": "gpt-5.4"},
            prompt_runner=lambda *args, **kwargs: (prompt_output, True),
        )

        result = runtime.summarize_window(
            [
                {
                    "memory_id": "mem_1",
                    "turn_seq": 1,
                    "topic": "recent memory",
                    "user_prompt": "把过程执行也保留进 recent memory",
                    "assistant_reply_visible": "正在修改 recent 与 summary。",
                    "process_events": [{"kind": "command", "text": "pytest -q", "status": "completed"}],
                }
            ]
            * 10,
            [],
            workspace=".",
            timeout=30,
            model="gpt-5.4",
        )

        self.assertEqual(result["window_summary"]["user_summary"], "用户主线摘要")
        self.assertEqual(result["window_summary"]["process_reflection"], "这轮先检索再改 recent，过程里发现一处回写缺口。")


if __name__ == "__main__":
    unittest.main()
