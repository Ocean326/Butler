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

from butler_main.agents_os.runtime.writeback import AsyncWritebackRunner
from butler_main.chat.memory_runtime import ChatReplyPersistenceRuntime


class _FakeWritebackRunner:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def submit(self, target, /, *args, name: str = "writeback-task", daemon: bool = True, **kwargs):
        self.calls.append(
            {
                "target": target,
                "args": args,
                "kwargs": kwargs,
                "name": name,
                "daemon": daemon,
            }
        )
        return None


class ChatReplyPersistenceRuntimeTests(unittest.TestCase):
    def test_runtime_writes_fallback_before_scheduling_finalize(self) -> None:
        fallback_calls: list[tuple[tuple, dict]] = []
        finalize_calls: list[tuple[tuple, dict]] = []
        runner = _FakeWritebackRunner()

        runtime = ChatReplyPersistenceRuntime(
            config_provider=lambda: {
                "workspace_root": "C:/workspace",
                "agent_timeout": 45,
                "agent_model": "auto",
            },
            fallback_writer=lambda *args, **kwargs: fallback_calls.append((args, kwargs)),
            finalize_reply=lambda *args, **kwargs: finalize_calls.append((args, kwargs)),
            writeback_runner=runner,
        )

        runtime.persist_reply_async(
            "继续这个任务",
            "已经处理",
            memory_id="mem_1",
            model_override="gpt-5.4",
            suppress_task_merge=True,
            session_scope_id="weixin:wx-bot-1:dm:user-a",
        )

        self.assertEqual(
            fallback_calls,
            [(("mem_1", "继续这个任务", "已经处理", "已经处理", "C:/workspace", "weixin:wx-bot-1:dm:user-a"), {"process_events": []})],
        )
        self.assertEqual(finalize_calls, [])
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0]["name"], "recent-memory-writer")
        self.assertTrue(runner.calls[0]["daemon"])
        self.assertEqual(
            runner.calls[0]["args"],
            ("mem_1", "继续这个任务", "已经处理", "已经处理", "C:/workspace", 45, "gpt-5.4", True, "weixin:wx-bot-1:dm:user-a"),
        )
        self.assertEqual(runner.calls[0]["kwargs"], {"process_events": []})

    def test_runtime_uses_default_model_when_override_missing(self) -> None:
        runner = _FakeWritebackRunner()
        runtime = ChatReplyPersistenceRuntime(
            config_provider=lambda: {
                "workspace_root": "C:/workspace",
                "agent_timeout": 30,
                "agent_model": "cursor-fast",
            },
            fallback_writer=lambda *args, **kwargs: None,
            finalize_reply=lambda *args, **kwargs: None,
            writeback_runner=runner,
        )

        runtime.persist_reply_async("hi", "hello", memory_id="mem_2")

        self.assertEqual(
            runner.calls[0]["args"],
            ("mem_2", "hi", "hello", "hello", "C:/workspace", 30, "cursor-fast", False, ""),
        )

    def test_runtime_propagates_raw_reply_when_provided(self) -> None:
        fallback_calls: list[tuple] = []
        runner = _FakeWritebackRunner()
        runtime = ChatReplyPersistenceRuntime(
            config_provider=lambda: {
                "workspace_root": "C:/workspace",
                "agent_timeout": 30,
                "agent_model": "cursor-fast",
            },
            fallback_writer=lambda *args, **kwargs: fallback_calls.append((args, kwargs)),
            finalize_reply=lambda *args, **kwargs: None,
            writeback_runner=runner,
        )

        runtime.persist_reply_async("hi", "visible", raw_reply="raw-full", memory_id="mem_3")

        self.assertEqual(
            fallback_calls,
            [(("mem_3", "hi", "visible", "raw-full", "C:/workspace", ""), {"process_events": []})],
        )
        self.assertEqual(
            runner.calls[0]["args"],
            ("mem_3", "hi", "visible", "raw-full", "C:/workspace", 30, "cursor-fast", False, ""),
        )
        self.assertEqual(runner.calls[0]["kwargs"], {"process_events": []})

    def test_runtime_propagates_process_events_when_provided(self) -> None:
        fallback_calls: list[tuple[tuple, dict]] = []
        runner = _FakeWritebackRunner()
        runtime = ChatReplyPersistenceRuntime(
            config_provider=lambda: {
                "workspace_root": "C:/workspace",
                "agent_timeout": 30,
                "agent_model": "cursor-fast",
            },
            fallback_writer=lambda *args, **kwargs: fallback_calls.append((args, kwargs)),
            finalize_reply=lambda *args, **kwargs: None,
            writeback_runner=runner,
        )

        process_events = [{"kind": "command", "text": "pytest -q", "status": "completed"}]
        runtime.persist_reply_async("hi", "visible", raw_reply="raw-full", memory_id="mem_4", process_events=process_events)

        self.assertEqual(fallback_calls[0][1]["process_events"], process_events)
        self.assertEqual(runner.calls[0]["kwargs"], {"process_events": process_events})

    def test_async_writeback_runner_starts_daemon_thread(self) -> None:
        marker = {"value": 0}
        thread = AsyncWritebackRunner().submit(lambda: marker.__setitem__("value", 1), name="test-writeback")
        thread.join(timeout=1)

        self.assertEqual(marker["value"], 1)
        self.assertEqual(thread.name, "test-writeback")
        self.assertTrue(thread.daemon)


if __name__ == "__main__":
    unittest.main()
