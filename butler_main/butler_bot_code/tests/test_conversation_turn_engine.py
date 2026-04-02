from __future__ import annotations

import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from butler_main.runtime_os.process_runtime import (
    ConversationPromptBuild,
    ConversationTurnEngine,
    ConversationTurnInput,
)


class _FakeMemoryProvider:
    def __init__(self) -> None:
        self.begin_calls = []
        self.prepare_calls = []

    def begin_turn(self, user_prompt: str, workspace: str, *, session_scope_id: str = ""):
        self.begin_calls.append((user_prompt, workspace, session_scope_id))
        return "mem_1", {"topic": "previous topic"}

    def prepare_turn_input(
        self,
        user_prompt: str,
        *,
        exclude_memory_id: str,
        previous_pending,
        recent_mode: str,
        session_scope_id: str = "",
    ):
        self.prepare_calls.append((user_prompt, exclude_memory_id, previous_pending, recent_mode, session_scope_id))
        return f"[recent:{recent_mode}] {user_prompt}"


class ConversationTurnEngineTests(unittest.TestCase):
    def test_engine_sequences_memory_prompt_and_execution_with_provider(self) -> None:
        memory_provider = _FakeMemoryProvider()
        captured = {}
        engine = ConversationTurnEngine(
            memory_provider=memory_provider,
            begin_turn_fallback_fn=lambda prompt, workspace: self.fail("fallback begin_turn should not run"),
            prepare_turn_input_fallback_fn=lambda *args, **kwargs: self.fail("fallback prepare_turn_input should not run"),
            classify_turn_fn=lambda prompt: {"mode": "content_share"},
            prompt_builder_fn=lambda **kwargs: captured.update(
                {
                    "prepared_user_prompt": kwargs["prepared_user_prompt"],
                    "recent_mode": kwargs["recent_mode"],
                }
            ) or ConversationPromptBuild(prompt="PROMPT", metadata={"builder": "ok"}),
            reply_executor_fn=lambda **kwargs: captured.update({"prompt": kwargs["prompt"]}) or "REPLY",
        )

        result = engine.run_turn(
            ConversationTurnInput(
                user_prompt="帮我转一下这条内容",
                workspace="C:/workspace",
                metadata={"session_scope_id": "weixin:wx-bot-1:dm:user-a"},
            )
        )

        self.assertEqual(memory_provider.begin_calls, [("帮我转一下这条内容", "C:/workspace", "weixin:wx-bot-1:dm:user-a")])
        self.assertEqual(captured["prepared_user_prompt"], "[recent:share] 帮我转一下这条内容")
        self.assertEqual(captured["recent_mode"], "share")
        self.assertEqual(captured["prompt"], "PROMPT")
        self.assertEqual(result.reply_text, "REPLY")
        self.assertEqual(result.pending_memory_id, "mem_1")
        self.assertEqual(result.state.recent_mode, "share")
        self.assertEqual(result.state.prepared_user_prompt, "[recent:share] 帮我转一下这条内容")
        self.assertIn("timings", result.metadata)

    def test_engine_can_fall_back_to_legacy_turn_functions(self) -> None:
        captured = {}
        engine = ConversationTurnEngine(
            begin_turn_fallback_fn=lambda prompt, workspace, session_scope_id="": (
                "mem_2",
                {"topic": f"fallback topic:{session_scope_id or '-'}"},
            ),
            prepare_turn_input_fallback_fn=lambda prompt, **kwargs: captured.update(kwargs) or f"[fallback] {prompt}",
            classify_turn_fn=None,
            prompt_builder_fn=lambda **kwargs: "PROMPT",
            reply_executor_fn=lambda **kwargs: kwargs["prompt"],
        )

        result = engine.run_turn(
            ConversationTurnInput(
                user_prompt="继续实现",
                workspace="C:/workspace",
                metadata={"session_scope_id": "weixin:wx-bot-1:dm:user-b"},
            )
        )

        self.assertEqual(captured["exclude_memory_id"], "mem_2")
        self.assertEqual(captured["recent_mode"], "chat")
        self.assertEqual(captured["session_scope_id"], "weixin:wx-bot-1:dm:user-b")
        self.assertEqual(result.reply_text, "PROMPT")
        self.assertEqual(result.pending_memory_id, "mem_2")
        self.assertEqual(result.state.prepared_user_prompt, "[fallback] 继续实现")
        self.assertEqual(result.state.recent_mode, "chat")


if __name__ == "__main__":
    unittest.main()
