from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest import mock


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from butler_main.chat.cli.runner import TerminalConsole, TerminalStreamPrinter, _run_repl, _run_single_turn


class ChatCliRunnerTests(unittest.TestCase):
    def test_terminal_stream_printer_appends_only_new_snapshot_text(self) -> None:
        stream = io.StringIO()
        printer = TerminalStreamPrinter(console=TerminalConsole(stream=stream))

        printer.on_segment("你好")
        printer.on_segment("你好，世界")
        printer.finalize("你好，世界")

        self.assertEqual(stream.getvalue(), "管家> 你好，世界\n")

    def test_terminal_stream_printer_falls_back_to_final_block_on_rewrite(self) -> None:
        stream = io.StringIO()
        printer = TerminalStreamPrinter(console=TerminalConsole(stream=stream))

        printer.on_segment("第一版")
        printer.on_segment("完全改写")
        printer.finalize("最终版")

        self.assertEqual(stream.getvalue(), "管家> 第一版\n[final]\n最终版\n")

    def test_run_single_turn_passes_cli_channel_and_session_to_run_agent(self) -> None:
        observed = {}

        def fake_run_agent(prompt: str, **kwargs) -> str:
            observed["prompt"] = prompt
            observed["kwargs"] = dict(kwargs)
            callback = kwargs.get("stream_callback")
            if callable(callback):
                callback("流式")
                callback("流式输出")
            return "流式输出"

        fake_run_agent.describe_runtime_target = lambda prompt, invocation_metadata=None: {
            "kind": "run",
            "cli": "codex",
            "model": "gpt-5.4",
        }
        on_reply_sent = mock.Mock()
        stream = io.StringIO()
        console = TerminalConsole(stream=stream)

        rc = _run_single_turn(
            prompt="测试 prompt",
            run_agent_fn=fake_run_agent,
            session_id="cli_session_demo",
            stream_enabled=True,
            on_reply_sent=on_reply_sent,
            console=console,
        )

        self.assertEqual(rc, 0)
        self.assertEqual(observed["prompt"], "测试 prompt")
        self.assertEqual(observed["kwargs"]["invocation_metadata"]["channel"], "cli")
        self.assertEqual(observed["kwargs"]["invocation_metadata"]["session_id"], "cli_session_demo")
        self.assertTrue(observed["kwargs"]["stream_output"])
        self.assertIn("stream_callback", observed["kwargs"])
        on_reply_sent.assert_called_once_with("测试 prompt", "流式输出")
        self.assertIn("[route=chat cli=codex model=gpt-5.4 session=cli_session_demo stream=on]", stream.getvalue())
        self.assertIn("管家> 流式输出\n", stream.getvalue())

    def test_repl_reuses_same_session_id_across_turns(self) -> None:
        seen_sessions = []

        def fake_run_agent(prompt: str, **kwargs) -> str:
            seen_sessions.append(kwargs["invocation_metadata"]["session_id"])
            return f"reply:{prompt}"

        fake_run_agent.describe_runtime_target = lambda prompt, invocation_metadata=None: {
            "kind": "run",
            "cli": "codex",
            "model": "gpt-5.4",
        }
        stream = io.StringIO()
        console = TerminalConsole(stream=stream)
        on_reply_sent = mock.Mock()

        with mock.patch("builtins.input", side_effect=["第一轮", "第二轮", "exit"]):
            rc = _run_repl(
                bot_name="管家bot",
                run_agent_fn=fake_run_agent,
                session_id="cli_session_stable",
                stream_enabled=False,
                on_reply_sent=on_reply_sent,
                console=console,
            )

        self.assertEqual(rc, 0)
        self.assertEqual(seen_sessions, ["cli_session_stable", "cli_session_stable"])
        self.assertEqual(on_reply_sent.call_args_list, [mock.call("第一轮", "reply:第一轮"), mock.call("第二轮", "reply:第二轮")])

    def test_terminal_console_formats_runtime_events_and_logs(self) -> None:
        stream = io.StringIO()
        console = TerminalConsole(stream=stream)

        console.write_assistant_prefix("管家> ")
        console.write_assistant_text("处理中")
        console.emit_runtime_event({"kind": "command", "status": "in_progress", "text": "pwsh -NoProfile -Command 'Write-Output 1'"})
        console.emit_log_line("[chat-runtime-timing] route=chat | build_prompt=0.003s\n")
        console.write_plain("完成\n")

        self.assertIn("管家> 处理中\n[codex running]", stream.getvalue())
        self.assertIn("[chat-runtime-timing] route=chat | build_prompt=0.003s", stream.getvalue())

    def test_terminal_console_status_window_keeps_only_latest_three_entries(self) -> None:
        stream = io.StringIO()
        console = TerminalConsole(stream=stream)
        console.status_window_enabled = True

        console.emit_runtime_event({"kind": "command", "status": "in_progress", "text": "cmd-1"})
        console.emit_runtime_event({"kind": "command", "status": "in_progress", "text": "cmd-2"})
        console.emit_runtime_event({"kind": "command", "status": "in_progress", "text": "cmd-3"})
        console.emit_runtime_event({"kind": "command", "status": "in_progress", "text": "cmd-4"})

        self.assertEqual(len(console.status_lines), 3)
        lines = [line for line, _ in console.status_lines]
        self.assertEqual(lines[0], "[codex running] cmd-2")
        self.assertEqual(lines[-1], "[codex running] cmd-4")

        console.write_assistant_prefix("管家> ")
        self.assertEqual(len(console.status_lines), 0)

    def test_terminal_console_strips_leading_process_ordinals(self) -> None:
        stream = io.StringIO()
        console = TerminalConsole(stream=stream)

        console.emit_runtime_event({"kind": "command", "status": "in_progress", "text": "1. pytest -q"})
        console.emit_runtime_event({"kind": "command", "status": "completed", "text": "步骤2：rg -n recent_memory"})

        rendered = stream.getvalue()
        self.assertIn("[codex running] pytest -q", rendered)
        self.assertIn("[codex completed] rg -n recent_memory", rendered)
        self.assertNotIn("[codex running] 1. pytest -q", rendered)
        self.assertNotIn("步骤2：", rendered)


if __name__ == "__main__":
    unittest.main()
