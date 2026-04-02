from __future__ import annotations

from datetime import datetime
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

from butler_main.chat.light_memory import ChatLightMemoryState
from butler_main.chat.memory_runtime import ChatRecentPromptAssembler, ChatRecentTurnStore
from butler_main.chat.pathing import RECENT_MEMORY_DIR_REL
from butler_main.chat.memory_runtime.recent_scope_paths import resolve_recent_scope_dir
from butler_main.chat.session_selection import save_chat_session_state, ChatSessionState


class ChatRecentMemoryRuntimeTests(unittest.TestCase):
    def test_begin_turn_persists_pending_entry_and_returns_previous_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recent_dir = root / RECENT_MEMORY_DIR_REL
            recent_dir.mkdir(parents=True, exist_ok=True)
            recent_file = recent_dir / "recent_memory.json"
            recent_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            recent_file.write_text(
                json.dumps(
                    [
                        {
                            "memory_id": "prev_1",
                            "timestamp": recent_timestamp,
                            "topic": "上一个问题",
                            "summary": "状态：正在回复中",
                            "memory_stream": "talk",
                            "status": "replying",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            store = ChatRecentTurnStore(config_provider=lambda: {"workspace_root": str(root)})
            memory_id, previous_pending = store.begin_turn("继续这个任务", str(root))

            saved = json.loads(recent_file.read_text(encoding="utf-8"))
            self.assertTrue(memory_id)
            self.assertEqual(previous_pending["memory_id"], "prev_1")
            self.assertEqual(saved[-1]["memory_id"], memory_id)
            self.assertEqual(saved[-1]["status"], "replying")

    def test_prompt_assembler_includes_recent_and_followup_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recent_dir = root / RECENT_MEMORY_DIR_REL
            recent_dir.mkdir(parents=True, exist_ok=True)
            (recent_dir / "recent_memory.json").write_text(
                json.dumps(
                    [
                        {
                            "memory_id": "done_1",
                            "timestamp": "2026-03-23 03:10:00",
                            "topic": "整理 chat 拆分",
                            "summary": "已经拆完 prompt-support，还剩 memory runtime。",
                            "memory_stream": "talk",
                            "status": "completed",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            store = ChatRecentTurnStore(config_provider=lambda: {"workspace_root": str(root)})
            assembler = ChatRecentPromptAssembler(turn_store=store)
            text = assembler.prepare_turn_input(
                "继续",
                exclude_memory_id="",
                previous_pending={"topic": "上一问：memory 方案"},
            )

            self.assertIn("【recent_memory", text)
            self.assertIn("整理 chat 拆分", text)
            self.assertIn("【追问上下文】", text)
            self.assertIn("【续接提示】", text)

    def test_begin_turn_scopes_weixin_recent_memory_into_independent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            global_recent_dir = root / RECENT_MEMORY_DIR_REL
            global_recent_dir.mkdir(parents=True, exist_ok=True)
            (global_recent_dir / "recent_memory.json").write_text("[]", encoding="utf-8")
            store = ChatRecentTurnStore(config_provider=lambda: {"workspace_root": str(root)})

            memory_id, _ = store.begin_turn(
                "微信用户A继续问",
                str(root),
                session_scope_id="weixin:wx-bot-1:dm:user-a",
            )

            scope_dir = resolve_recent_scope_dir(str(root), session_scope_id="weixin:wx-bot-1:dm:user-a")
            scoped_recent = json.loads((scope_dir / "recent_memory.json").read_text(encoding="utf-8"))
            global_recent = json.loads((global_recent_dir / "recent_memory.json").read_text(encoding="utf-8"))

            self.assertEqual(scoped_recent[-1]["memory_id"], memory_id)
            self.assertEqual(scoped_recent[-1]["session_scope_id"], "weixin:wx-bot-1:dm:user-a")
            self.assertEqual(global_recent, [])

    def test_begin_turn_bootstraps_feishu_scope_from_legacy_global_recent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            global_recent_dir = root / RECENT_MEMORY_DIR_REL
            global_recent_dir.mkdir(parents=True, exist_ok=True)
            legacy_entry = {
                "memory_id": "legacy_1",
                "timestamp": "2026-03-25 20:35:41",
                "topic": "我前面的几次消息你能看到吗？",
                "summary": "用户问最近几次消息能否续接。",
                "memory_stream": "talk",
                "status": "completed",
            }
            (global_recent_dir / "recent_memory.json").write_text(
                json.dumps([legacy_entry], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            store = ChatRecentTurnStore(config_provider=lambda: {"workspace_root": str(root)})

            memory_id, previous_pending = store.begin_turn(
                "继续刚才那条",
                str(root),
                session_scope_id="feishu:thread_123",
            )

            scoped_recent = json.loads(
                (resolve_recent_scope_dir(str(root), session_scope_id="feishu:thread_123") / "recent_memory.json").read_text(encoding="utf-8")
            )
            global_recent = json.loads((global_recent_dir / "recent_memory.json").read_text(encoding="utf-8"))

            self.assertIsNone(previous_pending)
            self.assertEqual(global_recent, [legacy_entry])
            self.assertEqual(scoped_recent[0]["memory_id"], "legacy_1")
            self.assertEqual(scoped_recent[0]["session_scope_id"], "feishu:thread_123")
            self.assertEqual(scoped_recent[-1]["memory_id"], memory_id)
            self.assertEqual(scoped_recent[-1]["session_scope_id"], "feishu:thread_123")

    def test_prompt_assembler_prefers_visible_turns_and_summary_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recent_dir = root / RECENT_MEMORY_DIR_REL
            recent_dir.mkdir(parents=True, exist_ok=True)
            (recent_dir / "recent_memory.json").write_text("[]", encoding="utf-8")
            raw_turns = [
                {
                    "memory_id": f"mem_{idx}",
                    "turn_seq": idx,
                    "timestamp": f"2026-03-26 10:{idx:02d}:00",
                    "topic": f"topic-{idx:02d}",
                    "user_prompt": f"prompt-{idx:02d}",
                    "assistant_reply_visible": f"visible-{idx:02d}",
                    "assistant_reply_raw": f"raw-{idx:02d}",
                    "process_events": [{"kind": "command", "text": f"1. cmd-{idx:02d}", "status": "completed"}],
                    "status": "completed",
                }
                for idx in range(1, 13)
            ]
            (recent_dir / "recent_raw_turns.json").write_text(json.dumps(raw_turns, ensure_ascii=False, indent=2), encoding="utf-8")
            summary_pool = [
                {
                    "summary_id": "sum_1",
                    "window_start_seq": 1,
                    "window_end_seq": 10,
                    "title": "窗口一",
                    "summary_text": "前十轮围绕窗口一推进。",
                    "user_summary": "前十轮围绕窗口一推进。",
                    "process_reflection": "这一窗主要通过 cmd-01 到 cmd-10 推进。",
                    "requirements": ["保持窗口一约束"],
                    "open_loops": ["窗口一未完点"],
                }
            ]
            (recent_dir / "recent_summary_pool.json").write_text(json.dumps(summary_pool, ensure_ascii=False, indent=2), encoding="utf-8")
            store = ChatRecentTurnStore(
                config_provider=lambda: {
                    "workspace_root": str(root),
                    "memory": {
                        "talk_recent": {
                            "inject_visible_items": 10,
                            "inject_summary_items": 5,
                            "prompt_max_chars": 600,
                        }
                    },
                }
            )
            assembler = ChatRecentPromptAssembler(turn_store=store)

            text = assembler.prepare_turn_input("继续", exclude_memory_id="")

            self.assertIn("【最近可见对话】", text)
            self.assertIn("【最近窗口摘要】", text)
            self.assertIn("prompt-12", text)
            self.assertNotIn("prompt-01", text)
            self.assertIn("保持窗口一约束", text)
            self.assertIn("过程：cmd-12", text)
            self.assertNotIn("过程：1. cmd-12", text)
            self.assertIn("过程反思", text)

    def test_prompt_assembler_filters_recent_context_by_active_chat_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scope_dir = resolve_recent_scope_dir(str(root), session_scope_id="feishu:thread_session_filter")
            scope_dir.mkdir(parents=True, exist_ok=True)
            save_chat_session_state(
                str(root),
                session_scope_id="feishu:thread_session_filter",
                state=ChatSessionState(active_chat_session_id="chat_new"),
            )
            (scope_dir / "recent_memory.json").write_text(
                json.dumps(
                    [
                        {
                            "memory_id": "legacy_1",
                            "timestamp": "2026-03-26 10:00:00",
                            "topic": "旧会话主题",
                            "summary": "旧会话摘要",
                            "memory_stream": "talk",
                            "status": "completed",
                            "chat_session_id": "chat_old",
                        },
                        {
                            "memory_id": "current_1",
                            "timestamp": "2026-03-26 10:05:00",
                            "topic": "当前会话主题",
                            "summary": "当前会话摘要",
                            "memory_stream": "talk",
                            "status": "completed",
                            "chat_session_id": "chat_new",
                        },
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (scope_dir / "recent_raw_turns.json").write_text(
                json.dumps(
                    [
                        {
                            "memory_id": "legacy_1",
                            "turn_seq": 1,
                            "timestamp": "2026-03-26 10:00:00",
                            "topic": "旧会话主题",
                            "user_prompt": "旧会话 prompt",
                            "assistant_reply_visible": "旧会话 visible",
                            "assistant_reply_raw": "旧会话 raw",
                            "status": "completed",
                            "chat_session_id": "chat_old",
                        },
                        {
                            "memory_id": "current_1",
                            "turn_seq": 2,
                            "timestamp": "2026-03-26 10:05:00",
                            "topic": "当前会话主题",
                            "user_prompt": "当前会话 prompt",
                            "assistant_reply_visible": "当前会话 visible",
                            "assistant_reply_raw": "当前会话 raw",
                            "status": "completed",
                            "chat_session_id": "chat_new",
                        },
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (scope_dir / "recent_summary_pool.json").write_text(
                json.dumps(
                    [
                        {
                            "summary_id": "summary_old",
                            "title": "旧窗口",
                            "summary_text": "旧窗口摘要",
                            "user_summary": "旧窗口摘要",
                            "chat_session_id": "chat_old",
                        },
                        {
                            "summary_id": "summary_new",
                            "title": "新窗口",
                            "summary_text": "新窗口摘要",
                            "user_summary": "新窗口摘要",
                            "requirements": ["保持当前会话约束"],
                            "chat_session_id": "chat_new",
                        },
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            store = ChatRecentTurnStore(config_provider=lambda: {"workspace_root": str(root)})
            assembler = ChatRecentPromptAssembler(turn_store=store)
            text = assembler.prepare_turn_input(
                "继续",
                exclude_memory_id="",
                session_scope_id="feishu:thread_session_filter",
            )

            self.assertIn("当前会话 prompt", text)
            self.assertIn("新窗口摘要", text)
            self.assertIn("保持当前会话约束", text)
            self.assertNotIn("旧会话 prompt", text)
            self.assertNotIn("旧窗口摘要", text)

    def test_light_memory_state_builds_summary_pool_and_governs_evicted_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            governed: list[str] = []

            def fake_summarizer(window_turns: list[dict], existing_summaries: list[dict], **kwargs) -> dict:
                start_seq = int(window_turns[0]["turn_seq"])
                end_seq = int(window_turns[-1]["turn_seq"])
                return {
                    "window_summary": {
                        "title": f"窗口{start_seq}",
                        "summary_text": f"summary {start_seq}-{end_seq}",
                        "user_summary": f"summary {start_seq}-{end_seq}",
                        "process_reflection": f"summary reflection {start_seq}-{end_seq}",
                        "topics": [f"topic-{start_seq}"],
                        "requirements": [f"req-{start_seq}"],
                        "open_loops": [f"loop-{end_seq}"],
                    },
                    "summary_patches": [],
                }

            def fake_governor(summary_entry: dict, **kwargs) -> dict:
                governed.append(str(summary_entry.get("summary_id") or ""))
                return {"status": "written", "summary_path": "L1_summaries/test.md"}

            state = ChatLightMemoryState(
                config_provider=lambda: {
                    "workspace_root": str(root),
                    "memory": {
                        "talk_recent": {
                            "inject_visible_items": 10,
                            "inject_summary_items": 5,
                            "summary_window_size": 10,
                        }
                    },
                },
                window_summarizer=fake_summarizer,
                long_memory_governor=fake_governor,
            )

            for idx in range(1, 61):
                state.finalize_recent_memory(
                    f"mem_{idx}",
                    f"user-{idx}",
                    f"visible-{idx}",
                    f"raw-{idx}",
                    str(root),
                    30,
                    "gpt-5.4",
                    session_scope_id="cli:demo",
                    process_events=[{"kind": "command", "text": f"{idx}. cmd-{idx}", "status": "completed"}],
                )

            scope_dir = resolve_recent_scope_dir(str(root), session_scope_id="cli:demo")
            summary_pool = json.loads((scope_dir / "recent_summary_pool.json").read_text(encoding="utf-8"))
            raw_turns = json.loads((scope_dir / "recent_raw_turns.json").read_text(encoding="utf-8"))
            queue = json.loads((scope_dir / "long_memory_queue.json").read_text(encoding="utf-8"))

            self.assertEqual(len(summary_pool), 5)
            self.assertEqual(summary_pool[0]["window_start_seq"], 11)
            self.assertEqual(summary_pool[-1]["window_end_seq"], 60)
            self.assertEqual(raw_turns[-1]["assistant_reply_visible"], "visible-60")
            self.assertEqual(raw_turns[-1]["assistant_reply_raw"], "raw-60")
            self.assertEqual(raw_turns[-1]["process_events"], [{"kind": "command", "text": "cmd-60", "status": "completed"}])
            self.assertEqual(summary_pool[-1]["process_reflection"], "summary reflection 51-60")
            self.assertEqual(len(governed), 1)
            self.assertEqual(queue[0]["status"], "written")

    def test_light_memory_state_backfills_recent_turns_and_skips_equivalent_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = ChatLightMemoryState(
                config_provider=lambda: {
                    "workspace_root": str(root),
                    "memory": {"talk_recent": {"store_max_items": 20}},
                }
            )

            state.finalize_recent_memory(
                "mem_live_1",
                "用户问 A",
                "助手答 A",
                "助手答 A RAW",
                str(root),
                30,
                "gpt-5.4",
                session_scope_id="feishu:chat_123",
            )

            written = state.backfill_recent_turns(
                [
                    {
                        "memory_id": "feishu-backfill:om_dup",
                        "timestamp": "2026-03-26 11:00:00",
                        "user_prompt": "用户问 A",
                        "assistant_reply_visible": "助手答 A",
                        "assistant_reply_raw": "助手答 A",
                        "status": "completed",
                        "source_kind": "feishu_backfill",
                        "source_chat_id": "chat_123",
                        "source_message_ids": ["om_user_dup", "om_dup"],
                    },
                    {
                        "memory_id": "feishu-backfill:om_new",
                        "timestamp": "2026-03-26 11:05:00",
                        "user_prompt": "用户问 B",
                        "assistant_reply_visible": "助手答 B",
                        "assistant_reply_raw": "助手答 B RAW",
                        "status": "completed",
                        "source_kind": "feishu_backfill",
                        "source_chat_id": "chat_123",
                        "source_message_ids": ["om_user_b", "om_new"],
                    },
                ],
                str(root),
                session_scope_id="feishu:chat_123",
            )

            scope_dir = resolve_recent_scope_dir(str(root), session_scope_id="feishu:chat_123")
            recent_entries = json.loads((scope_dir / "recent_memory.json").read_text(encoding="utf-8"))
            raw_turns = json.loads((scope_dir / "recent_raw_turns.json").read_text(encoding="utf-8"))

            self.assertEqual(written, 1)
            self.assertEqual(len(recent_entries), 2)
            self.assertEqual(len(raw_turns), 2)
            self.assertEqual(raw_turns[-1]["memory_id"], "feishu-backfill:om_new")
            self.assertEqual(raw_turns[-1]["assistant_reply_visible"], "助手答 B")
            self.assertEqual(raw_turns[-1]["assistant_reply_raw"], "助手答 B RAW")
            self.assertEqual(raw_turns[-1]["source_chat_id"], "chat_123")


if __name__ == "__main__":
    unittest.main()
