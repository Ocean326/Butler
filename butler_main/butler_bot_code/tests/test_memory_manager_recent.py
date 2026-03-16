import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

from memory_manager import MemoryManager  # noqa: E402
from services.task_ledger_service import TaskLedgerService  # noqa: E402


class MemoryManagerRecentTests(unittest.TestCase):
    def test_begin_pending_turn_then_followup_prompt_mentions_previous_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            _, previous_pending = manager.begin_pending_turn("第一个问题是什么", str(workspace))
            self.assertIsNone(previous_pending)

            second_id, previous_pending = manager.begin_pending_turn("那第二个问题呢", str(workspace))
            prompt = manager.prepare_user_prompt_with_recent(
                "那第二个问题呢",
                exclude_memory_id=second_id,
                previous_pending=previous_pending,
            )

            self.assertIn("上一问仍在回复中", prompt)
            self.assertIn("第一个问题是什么", prompt)
            self.assertIn("用户又追问：那第二个问题呢", prompt)

    def test_prepare_user_prompt_with_recent_adds_continuation_hint_for_short_followup(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            manager._save_recent_entries(
                str(workspace),
                [
                    {
                        "memory_id": "talk-1",
                        "timestamp": "2026-03-16 10:00:00",
                        "topic": "整理小红书网页与图片 OCR",
                        "summary": "用户要求把网页正文和图片 OCR 一起整理到 BrainStorm。",
                        "raw_user_prompt": "把今天那条小红书连同图片 OCR 一起整理到 BrainStorm",
                        "memory_stream": "talk",
                        "event_type": "conversation_turn",
                        "status": "completed",
                        "next_actions": ["优先确定 OCR 方案"],
                    }
                ],
            )

            prompt = manager.prepare_user_prompt_with_recent("用PaddleOCR吧")

            self.assertIn("【续接提示】", prompt)
            self.assertIn("不要当成全新任务", prompt)
            self.assertIn("【最近显式要求与未完约束】", prompt)
            self.assertIn("图片 OCR", prompt)

    def test_stale_pending_turn_is_not_reused_as_followup_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            stale_entry = {
                "memory_id": "stale-1",
                "timestamp": "2026-03-10 00:00:00",
                "topic": "现在就去代码上加上这条通路，加完之后",
                "summary": "状态：正在回复中",
                "memory_stream": "talk",
                "event_type": "conversation_turn",
                "status": "replying",
            }
            manager._save_recent_entries(str(workspace), [stale_entry])

            _, previous_pending = manager.begin_pending_turn("新问题", str(workspace))
            self.assertIsNone(previous_pending)

            data = manager._load_recent_entries(str(workspace))
            repaired = next(item for item in data if item.get("memory_id") == "stale-1")
            self.assertEqual(repaired["status"], "interrupted")

    def test_missing_result_text_still_persists_and_gets_refined(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "topic": "普通闲聊",
                    "summary": "用户进行普通闲聊，本轮 result_text 缺失，已由模型补写摘要。",
                    "next_actions": [],
                    "long_term_candidate": {
                        "should_write": False,
                        "title": "",
                        "summary": "",
                        "keywords": [],
                    },
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            manager._persist_recent_and_local_memory("今天天气不错", "", str(workspace), 60, "auto")

            recent_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "recent_memory" / "recent_memory.json"
            self.assertTrue(recent_file.exists())
            data = json.loads(recent_file.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["topic"], "普通闲聊")
            self.assertIn("已由模型补写摘要", data[0]["summary"])

    def test_invalid_refine_result_keeps_provisional_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                return "not-json", False

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            pending_id, _ = manager.begin_pending_turn("写一条测试", str(workspace))
            manager._finalize_recent_and_local_memory(pending_id, "写一条测试", "", str(workspace), 60, "auto")

            recent_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "recent_memory" / "recent_memory.json"
            data = json.loads(recent_file.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["summary"], "状态：正在回复中")
            self.assertEqual(data[0]["status"], "completed")

    def test_on_reply_sent_async_writes_fallback_before_refine_finishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def slow_model(prompt: str, workspace_path: str, timeout: int, model: str):
                time.sleep(0.2)
                payload = {
                    "topic": "已精炼",
                    "summary": "模型精炼完成",
                    "next_actions": [],
                    "long_term_candidate": {
                        "should_write": False,
                        "title": "",
                        "summary": "",
                        "keywords": [],
                    },
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=slow_model)
            pending_id, _ = manager.begin_pending_turn("补一条记忆", str(workspace))
            manager.on_reply_sent_async("补一条记忆", "已经回复", memory_id=pending_id, model_override="auto")

            recent_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "recent_memory" / "recent_memory.json"
            data = json.loads(recent_file.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["status"], "completed")
            self.assertIn("已经回复", data[0]["summary"])

    def test_manual_access_helpers_append_and_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            recent = manager.append_recent_entry(str(workspace), "测试主题", "测试摘要", next_actions=["下一步"])
            self.assertEqual(recent["topic"], "测试主题")

            manager.append_local_memory_entry(str(workspace), "长期主题", "这是长期记忆摘要", ["测试"])
            matches = manager.query_local_memory(str(workspace), keyword="长期记忆", limit=5)
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["title"], "长期主题")

    def test_prune_stale_recent_entries_archives_old_companion_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            entries = [
                {
                    "memory_id": "talk-1",
                    "timestamp": "2026-03-10 10:00:00",
                    "topic": "最近对话",
                    "summary": "这是最近一轮对话。",
                    "memory_stream": "talk",
                    "event_type": "conversation_turn",
                    "status": "completed",
                },
                {
                    "memory_id": "mental-1",
                    "timestamp": "2026-03-10 08:00:00",
                    "topic": "旧心理信号",
                    "summary": "这是已经过时的 mental companion。",
                    "memory_stream": "mental",
                    "event_type": "companion_memory",
                    "status": "completed",
                    "active_window": "recent",
                    "derived_from": ["old-talk"],
                },
            ]
            manager._save_recent_entries(str(workspace), entries)

            result = manager.prune_stale_recent_entries(str(workspace), reason="test-cleanup")

            self.assertEqual(result["stale_count"], 1)
            self.assertTrue(result["archive_path"])
            remaining = manager._load_recent_entries(str(workspace))
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0]["memory_id"], "talk-1")
            archive_payload = json.loads(Path(result["archive_path"]).read_text(encoding="utf-8"))
            self.assertEqual(archive_payload["count"], 1)

    def test_recent_pool_thresholds_are_split_for_talk_and_beat(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            self.assertEqual(manager._recent_max_items("talk"), 20)
            self.assertEqual(manager._recent_max_items("beat"), 15)
            self.assertEqual(manager._recent_storage_max_items("talk"), 100)
            self.assertEqual(manager._recent_max_chars("talk"), 18000)
            self.assertEqual(manager._recent_max_chars("beat"), 20000)

    def test_recent_pool_thresholds_can_be_overridden_by_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "memory": {
                        "talk_recent": {
                            "prompt_visible_items": 12,
                            "storage_items": 48,
                            "prompt_max_chars": 9000,
                            "storage_max_chars": 30000,
                        },
                        "local_memory": {"maintenance_min_interval_seconds": 1200},
                    },
                },
                run_model_fn=lambda *_: ("", False),
            )

            self.assertEqual(manager._recent_max_items("talk"), 12)
            self.assertEqual(manager._recent_storage_max_items("talk"), 48)
            self.assertEqual(manager._recent_max_chars("talk"), 9000)
            self.assertEqual(manager._recent_storage_max_chars("talk"), 30000)
            self.assertEqual(manager._long_maintenance_min_interval_seconds(), 1200)

    def test_self_mind_cycle_prompt_is_narrow_kernel_with_three_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("", False),
            )

            prompt = manager._build_self_mind_cycle_prompt(str(workspace))

            self.assertIn("self_mind 精简内核", prompt)
            self.assertIn("【1. 当前上下文】", prompt)
            self.assertIn("【2. 用户画像与陪伴记忆】", prompt)
            self.assertIn("【3. 自己最近续思】", prompt)
            self.assertIn('"decision":"talk|agent|hold"', prompt)

    def test_normalize_self_mind_cycle_output_keeps_longer_self_note(self):
        manager = MemoryManager(config_provider=lambda: {"workspace_root": "."}, run_model_fn=lambda *_: ("", False))

        payload = manager._normalize_self_mind_cycle_output({"self_note": "我" * 1800})

        self.assertEqual(len(payload["self_note"]), 1800)

    def test_local_memory_query_defaults_to_l1_and_relations_track_l2(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            long_summary = "这是长期记忆摘要。" + ("细节段落" * 120) + "只在L2里出现的特征词_深层定位"
            manager.append_local_memory_entry(str(workspace), "分层长期主题", long_summary, ["测试", "分层"])

            local_dir = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory"
            relations_file = local_dir / ".relations.json"
            self.assertTrue(relations_file.exists())

            default_matches = manager.query_local_memory(str(workspace), keyword="特征词_深层定位", limit=5)
            self.assertEqual(default_matches, [])

            detail_matches = manager.query_local_memory(str(workspace), keyword="特征词_深层定位", limit=5, include_details=True)
            self.assertEqual(len(detail_matches), 1)
            self.assertTrue(detail_matches[0]["detail_path"])

    def test_rebuild_local_memory_index_scans_root_l1_and_orphan_l2(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            local_dir = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory"
            l1_dir = local_dir / "L1_summaries"
            l2_dir = local_dir / "L2_details"
            l1_dir.mkdir(parents=True, exist_ok=True)
            l2_dir.mkdir(parents=True, exist_ok=True)
            (local_dir / "人格与自我认知.md").write_text(
                "# 人格与自我认知\n\n## 当前结论\n- 默认保持真实、轻快、少客服腔。\n",
                encoding="utf-8",
            )
            (l1_dir / "工作区治理.md").write_text(
                "# 工作区治理\n\n## 当前结论\n- 工作区要优先收敛真源和减少碎片。\n",
                encoding="utf-8",
            )
            (l2_dir / "孤立细节.md").write_text(
                "# 孤立细节\n\n这里是只存在于 L2 的补充细节。",
                encoding="utf-8",
            )

            payload = manager.rebuild_local_memory_index(str(workspace))
            self.assertGreaterEqual(payload["entry_count"], 3)

            matches = manager.query_local_memory(str(workspace), keyword="少客服腔", limit=5)
            self.assertTrue(any(item["title"] == "人格与自我认知" for item in matches))
            orphan_matches = manager.query_local_memory(str(workspace), keyword="孤立细节", limit=5, include_details=True)
            self.assertTrue(any(item["layer"] == "L2" for item in orphan_matches))

    def test_query_local_memory_supports_query_text_and_memory_type_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            local_dir = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory"
            local_dir.mkdir(parents=True, exist_ok=True)
            (local_dir / "Current_User_Profile.private.md").write_text(
                "# Current User Profile\n\n## 当前结论\n- 用户偏好少客服腔，允许自然一点。\n",
                encoding="utf-8",
            )
            manager.rebuild_local_memory_index(str(workspace))

            matches = manager.query_local_memory(
                str(workspace),
                query_text="请按偏好少客服腔地回复我",
                limit=5,
                memory_types=["personal"],
            )

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["memory_type"], "personal")
            self.assertIn("少客服腔", matches[0]["current_conclusion"])

    def test_recent_refine_writes_heartbeat_task_and_long_task_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "topic": "后台提醒",
                    "summary": "用户要求把提醒加入后台心跳。",
                    "next_actions": ["补充提醒"],
                    "heartbeat_tasks": [
                        {
                            "title": "后台整理汇报",
                            "detail": "在后台继续整理汇报材料",
                            "priority": "high"
                        }
                    ],
                    "heartbeat_long_term_tasks": [
                        {
                            "title": "每天 12:00 提醒",
                            "detail": "每天 12:00 提醒用户检查今日任务",
                            "schedule_type": "daily",
                            "schedule_value": "12:00",
                            "kind": "reminder"
                        }
                    ],
                    "long_term_candidate": {
                        "should_write": False,
                        "title": "",
                        "summary": "",
                        "keywords": []
                    }
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            manager._persist_recent_and_local_memory("你今天的任务是在后台整理汇报，以后每天12:00提醒我", "收到，我会在后台跟进", str(workspace), 60, "auto")

            short_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "recent_memory" / "heart_beat_memory.json"
            long_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_long_tasks.json"
            self.assertTrue(short_file.exists())
            self.assertTrue(long_file.exists())

            short_data = json.loads(short_file.read_text(encoding="utf-8"))
            long_data = json.loads(long_file.read_text(encoding="utf-8"))
            self.assertEqual(short_data["tasks"][0]["title"], "后台整理汇报")
            self.assertEqual(long_data["tasks"][0]["schedule_value"], "12:00")

            board_index = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_tasks.md"
            board_work = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_tasks" / "01_工作任务.md"
            board_cleanup = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_tasks" / "05_整理清洁.md"
            board_scheduled = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_tasks" / "03_定时.md"
            board_longterm = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_tasks" / "04_长期.md"
            board_log = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_tasks" / "task_change_log.jsonl"
            task_workspaces_dir = workspace / "butler_main" / "butler_bot_agent" / "agents" / "state" / "task_workspaces"
            self.assertTrue(board_index.exists())
            self.assertTrue(board_work.exists())
            self.assertTrue(board_cleanup.exists())
            self.assertTrue(board_scheduled.exists())
            self.assertTrue(board_longterm.exists())
            self.assertTrue(board_log.exists())
            self.assertTrue((task_workspaces_dir / "未进行").exists())
            self.assertTrue((task_workspaces_dir / "进行中").exists())
            self.assertTrue((task_workspaces_dir / "已完成").exists())
            board_text = board_work.read_text(encoding="utf-8") + "\n" + board_cleanup.read_text(encoding="utf-8")
            self.assertIn("后台整理汇报", board_text)
            schedule_text = board_scheduled.read_text(encoding="utf-8") + "\n" + board_longterm.read_text(encoding="utf-8")
            self.assertIn("每天 12:00 提醒", schedule_text)

    def test_recent_refine_reclassifies_self_mind_tasks_into_cues(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "topic": "自我整理",
                    "summary": "这轮更适合留在 self_mind 里继续想。",
                    "scene_mode": "self_growth",
                    "self_mind_cues": ["继续梳理最近的自我认知变化"],
                    "heartbeat_tasks": [
                        {
                            "title": "做一轮自我反思",
                            "detail": "梳理最近自我认知和情绪变化",
                            "priority": "medium",
                        }
                    ],
                    "heartbeat_long_term_tasks": [],
                    "long_term_candidate": {
                        "should_write": False,
                        "title": "",
                        "summary": "",
                        "keywords": [],
                    },
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            manager._persist_recent_and_local_memory("我最近想认真做一轮自我反思", "这部分先留给 self_mind 内部整理", str(workspace), 60, "auto")

            recent_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "recent_memory" / "recent_memory.json"
            short_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "recent_memory" / "heart_beat_memory.json"

            recent_data = json.loads(recent_file.read_text(encoding="utf-8"))
            short_data = json.loads(short_file.read_text(encoding="utf-8")) if short_file.exists() else {"tasks": []}

            talk_entry = next(item for item in recent_data if item.get("memory_stream") == "talk")
            self.assertIn("梳理最近自我认知和情绪变化", talk_entry.get("self_mind_cues") or [])
            self.assertEqual(short_data.get("tasks") or [], [])

    def test_recent_entry_contains_unified_schema_fields_after_refine(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "topic": "统一记忆",
                    "summary": "本轮开始按统一记忆 schema 写回。",
                    "next_actions": ["继续实现"],
                    "mental_notes": ["需要先把 schema 和触发层级定稳"],
                    "relationship_signals": ["用户希望先定方案再动实现"],
                    "context_tags": ["memory", "implementation"],
                    "relation_signal": {"tone": "serious", "preference_shift": "先定方案再动实现", "importance": 0.8},
                    "salience": 0.9,
                    "active_window": "current",
                    "long_term_candidate": {
                        "should_write": False,
                        "title": "",
                        "summary": "",
                        "keywords": [],
                    },
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            manager._persist_recent_and_local_memory("开始实现统一记忆", "先把骨架落下", str(workspace), 60, "auto")

            recent_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "recent_memory" / "recent_memory.json"
            data = json.loads(recent_file.read_text(encoding="utf-8"))

            talk_entry = next(item for item in data if item.get("memory_stream") == "talk")
            self.assertEqual(talk_entry["event_type"], "conversation_turn")
            self.assertEqual(talk_entry["active_window"], "current")
            self.assertEqual(talk_entry["context_tags"], ["memory", "implementation"])
            self.assertEqual(talk_entry["mental_notes"], ["需要先把 schema 和触发层级定稳"])
            self.assertEqual(talk_entry["relationship_signals"], ["用户希望先定方案再动实现"])
            self.assertGreaterEqual(float(talk_entry["salience"]), 0.8)

            streams = {item.get("memory_stream") for item in data}
            self.assertIn("mental", streams)
            self.assertIn("relationship_signal", streams)
            self.assertIn("task_signal", streams)

    def test_prepare_user_prompt_with_recent_renders_stream_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            manager._save_recent_entries(
                str(workspace),
                [
                    {
                        "memory_id": "talk-1",
                        "timestamp": "2026-03-10 10:00:00",
                        "topic": "实现启动",
                        "summary": "开始搭统一记忆骨架。",
                        "memory_stream": "talk",
                        "event_type": "conversation_turn",
                        "status": "completed",
                    },
                    {
                        "memory_id": "mental-1",
                        "timestamp": "2026-03-10 10:01:00",
                        "topic": "最近在想什么",
                        "summary": "先把 schema 和双环边界定稳。",
                        "memory_stream": "mental",
                        "event_type": "post_turn_reflection",
                        "status": "completed",
                    },
                    {
                        "memory_id": "relation-1",
                        "timestamp": "2026-03-10 10:02:00",
                        "topic": "关系与情绪信号",
                        "summary": "用户偏好先定方案再进实现。",
                        "memory_stream": "relationship_signal",
                        "event_type": "relationship_observation",
                        "status": "completed",
                    },
                ],
            )

            prompt = manager.prepare_user_prompt_with_recent("继续实现")
            self.assertIn("【对话短期记忆】", prompt)
            self.assertIn("【最近在想什么】", prompt)
            self.assertIn("【关系与情绪信号】", prompt)

    def test_prepare_user_prompt_with_recent_uses_lightweight_context_for_content_share(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            manager._save_recent_entries(
                str(workspace),
                [
                    {
                        "memory_id": "talk-1",
                        "timestamp": "2026-03-10 10:00:00",
                        "topic": "之前讨论过如何抓取小红书",
                        "summary": "用户之前确认过不要总让他手工跑命令。",
                        "raw_user_prompt": "以后你自己推进，不要只教我跑命令",
                        "memory_stream": "talk",
                        "event_type": "conversation_turn",
                        "status": "completed",
                        "next_actions": ["默认直接给结论"],
                    },
                ],
            )

            prompt = manager.prepare_user_prompt_with_recent(
                "Ocean:\n一个文件让 Claude Code 战斗力翻倍 http://xhslink.com/o/AirylJSxpim",
                recent_mode="content_share",
            )
            self.assertEqual(
                prompt,
                "Ocean:\n一个文件让 Claude Code 战斗力翻倍 http://xhslink.com/o/AirylJSxpim",
            )
            self.assertNotIn("【recent_memory", prompt)
            self.assertNotIn("【使用规则】", prompt)

    def test_recent_summary_pool_is_generated_and_injected_by_relevance(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            entries = []
            for index in range(25):
                entries.append(
                    {
                        "memory_id": f"talk-{index}",
                        "timestamp": f"2026-03-10 10:{index:02d}:00",
                        "topic": "recent-summary-test",
                        "summary": f"第{index}轮在讨论记忆总结与自我思考机制。",
                        "memory_stream": "talk",
                        "event_type": "conversation_turn",
                        "status": "completed",
                        "context_tags": ["memory", "self_mind"],
                    }
                )
            manager._save_recent_entries(str(workspace), entries)

            summary_pool = manager._load_recent_summary_pool(str(workspace))
            self.assertTrue(summary_pool)
            prompt = manager.prepare_user_prompt_with_recent("继续讨论 self_mind 的记忆总结")
            self.assertIn("recent_summary", prompt)
            self.assertIn("self_mind", prompt)

    def test_heuristic_extraction_still_creates_long_term_reminder_when_model_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            manager._persist_recent_and_local_memory("以后每天12:00提醒我检查今日计划，今天2:00-5:00是工作时间", "好的", str(workspace), 60, "auto")

            long_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_long_tasks.json"
            long_data = json.loads(long_file.read_text(encoding="utf-8"))
            titles = [item.get("title") for item in long_data.get("tasks") or []]
            self.assertIn("每天 12:00 提醒", titles)
            self.assertTrue(any("工作时间" in str(title) for title in titles))

    def test_governor_enabled_still_allows_memory_and_task_candidate_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "topic": "后台提醒",
                    "summary": "用户要求把提醒加入后台心跳。",
                    "next_actions": [],
                    "heartbeat_tasks": [{"title": "后台整理汇报", "detail": "继续整理汇报材料"}],
                    "heartbeat_long_term_tasks": [{"title": "每天 12:00 提醒", "detail": "提醒检查任务", "schedule_type": "daily", "schedule_value": "12:00", "kind": "reminder"}],
                    "long_term_candidate": {"should_write": True, "title": "用户长期偏好", "summary": "用户希望每天中午收到提醒。", "keywords": ["提醒", "偏好"]}
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace), "features": {"governor": True}},
                run_model_fn=fake_model,
            )
            manager._persist_recent_and_local_memory("以后每天 12:00 提醒我", "好的", str(workspace), 60, "auto")

            long_task_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_long_tasks.json"
            self.assertTrue(long_task_file.exists())
            local_root = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory"
            local_files = list(local_root.glob("*.md")) + list((local_root / "L1_summaries").glob("*.md"))
            self.assertTrue(any("用户长期偏好" in path.stem for path in local_files))

    def test_local_memory_write_journal_records_source_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "topic": "长期偏好",
                    "summary": "用户希望后续默认记录关键结论。",
                    "next_actions": [],
                    "long_term_candidate": {
                        "should_write": True,
                        "title": "结论记录偏好",
                        "summary": "用户希望后续默认记录关键结论。",
                        "keywords": ["默认", "偏好"],
                    },
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            manager._persist_recent_and_local_memory("以后默认把关键结论记住", "收到", str(workspace), 60, "auto")

            _, _, local_dir = manager._memory_paths(str(workspace))
            journal = local_dir / "local_memory_write_journal.jsonl"
            self.assertTrue(journal.exists())
            lines = [line for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(lines)
            last = json.loads(lines[-1])
            self.assertIn(last.get("action"), {"write-new", "append-existing", "append-similar", "duplicate-skip"})
            self.assertEqual(str(last.get("source_type") or ""), "per-turn")
            self.assertEqual(str(last.get("source_reason") or ""), "long_term_candidate")
            self.assertTrue(str(last.get("source_memory_id") or "").strip())

    def test_recent_maintenance_sweep_promotes_unmarked_should_write_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            entry = {
                "memory_id": "m-1",
                "timestamp": "2026-03-10 10:00:00",
                "topic": "长期共识",
                "summary": "我们明确了长期协作风格。",
                "status": "completed",
                "next_actions": [],
                "heartbeat_tasks": [],
                "heartbeat_long_term_tasks": [],
                "long_term_candidate": {
                    "should_write": True,
                    "title": "协作风格",
                    "summary": "我们明确了长期协作风格。",
                    "keywords": ["风格", "长期"],
                },
            }
            manager._save_recent_entries(str(workspace), [entry])

            info = manager._run_recent_memory_maintenance_once(str(workspace), 60, "auto", reason="test-sweep")
            self.assertEqual(int(info.get("promoted_count") or 0), 1)

            latest = manager._load_recent_entries(str(workspace))[-1]
            lt = latest.get("long_term_candidate") if isinstance(latest.get("long_term_candidate"), dict) else {}
            self.assertTrue(str(lt.get("promoted_to_local_at") or "").strip())
            self.assertEqual(str(lt.get("promoted_source") or ""), "recent-sweep")
            self.assertIn(str(lt.get("promoted_action") or ""), {"write-new", "append-existing", "append-similar", "duplicate-skip"})

    def test_legacy_heartbeat_markdown_mirrors_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace), "features": {"legacy_heartbeat_markdown_mirrors": False}},
                run_model_fn=lambda *_: ("", False),
            )

            manager._save_heartbeat_memory(str(workspace), {"version": 1, "updated_at": "", "tasks": [], "notes": []})
            manager._save_heartbeat_long_tasks(str(workspace), {"version": 1, "updated_at": "", "tasks": []})

            self.assertTrue((workspace / "butler_main" / "butler_bot_agent" / "agents" / "recent_memory" / "heart_beat_memory.json").exists())
            self.assertTrue((workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_long_tasks.json").exists())
            self.assertFalse((workspace / "butler_main" / "butler_bot_agent" / "agents" / "recent_memory" / "heart_beat_memory.md").exists())
            self.assertFalse((workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "heartbeat_long_tasks.md").exists())

    def test_local_memory_upsert_writes_structured_sections_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            manager._upsert_local_memory(
                str(workspace),
                "统一记忆约定",
                "当前结论是 heartbeat 规划必须读取统一 Soul、role 和长期记忆索引。这个结论来自本轮统一记忆机制改造。",
                ["Soul", "heartbeat", "local-memory"],
                source_type="per-turn",
                source_reason="long_term_candidate",
                source_topic="统一记忆机制",
                source_entry={"context_tags": ["memory", "planner"]},
            )

            local_root = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory"
            summary_file = local_root / "L1_summaries" / "统一记忆约定.md"
            index_file = local_root / "L0_index.json"

            self.assertTrue(summary_file.exists())
            text = summary_file.read_text(encoding="utf-8")
            self.assertIn("### 当前结论", text)
            self.assertIn("### 历史演化", text)
            self.assertIn("### 适用情景", text)

            payload = json.loads(index_file.read_text(encoding="utf-8"))
            entry = next(item for item in payload.get("entries") if item.get("title") == "统一记忆约定")
            self.assertTrue(str(entry.get("current_conclusion") or "").strip())
            self.assertTrue(isinstance(entry.get("history_evolution"), list))
            self.assertTrue(isinstance(entry.get("applicable_scenarios"), list))

    def test_heartbeat_planning_prompt_loads_soul_role_and_structured_local_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            agent_dir = workspace / "butler_main" / "butler_bot_agent" / "agents"
            local_dir = agent_dir / "local_memory"
            agent_dir.mkdir(parents=True, exist_ok=True)
            local_dir.mkdir(parents=True, exist_ok=True)
            (agent_dir / "heartbeat-planner-agent.md").write_text("你是独立的 heartbeat planner role。", encoding="utf-8")
            (local_dir / "Butler_SOUL.md").write_text("Butler soul excerpt test", encoding="utf-8")

            manager._save_recent_entries(
                str(workspace),
                [{
                    "memory_id": "talk-1",
                    "timestamp": "2026-03-10 12:00:00",
                    "topic": "统一记忆",
                    "summary": "近期正在打通 heartbeat 与 recent/local memory。",
                    "memory_stream": "talk",
                    "event_type": "conversation_turn",
                    "status": "completed",
                }],
            )
            manager._upsert_local_memory(
                str(workspace),
                "心跳规划上下文",
                "当前结论是 planner 应该读统一 Soul、role、recent 和 local index。",
                ["planner", "Soul"],
                source_type="per-turn",
                source_reason="long_term_candidate",
                source_topic="heartbeat planning",
            )

            prompt = manager._build_heartbeat_planning_prompt({"workspace_root": str(workspace)}, {"enabled": True}, str(workspace))
            self.assertIn("Soul 摘录", prompt)
            self.assertIn("角色摘录", prompt)
            self.assertIn("对话侧统一近期流", prompt)
            self.assertIn("当前结论:", prompt)
            self.assertIn("你是独立的 heartbeat planner role", prompt)

    def test_self_mind_log_refreshes_raw_and_review_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            manager._append_self_mind_log(
                str(workspace),
                "intent_pending",
                {
                    "candidate": "我刚又顺着上一轮想了一下。",
                    "share_reason": "上一轮留下了一个还值得继续长的念头。",
                    "share_type": "thought_share",
                },
            )
            manager._append_self_mind_log(
                str(workspace),
                "intent_deferred",
                {
                    "candidate": "先不急着说，继续在心里放一会儿。",
                    "share_reason": "还没完全收口。",
                    "share_type": "thought_share",
                },
            )

            raw_path = workspace / "butler_main" / "butle_bot_space" / "self_mind" / "raw_thoughts.json"
            review_path = workspace / "butler_main" / "butle_bot_space" / "self_mind" / "thought_reviews.json"
            self.assertTrue(raw_path.exists())
            self.assertTrue(review_path.exists())
            raw_items = json.loads(raw_path.read_text(encoding="utf-8"))
            review_items = json.loads(review_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(raw_items), 2)
            self.assertTrue(review_items)

    def test_recent_summary_ladder_builds_time_buckets(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "memory": {
                        "talk_recent": {
                            "prompt_visible_items": 1,
                            "storage_items": 20,
                            "summary_chunk_size": 2,
                            "max_active_summaries": 10,
                        }
                    },
                },
                run_model_fn=lambda *_: ("", False),
            )

            now = datetime.now()
            stamps = [
                now - timedelta(days=6),
                now - timedelta(days=5),
                now - timedelta(days=45),
                now - timedelta(days=44),
                now - timedelta(days=220),
                now - timedelta(days=219),
                now,
            ]
            entries = []
            for index, stamp in enumerate(stamps):
                entries.append(
                    {
                        "memory_id": f"talk-{index}",
                        "timestamp": stamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "topic": f"阶段{index}",
                        "summary": f"第{index}轮围绕 Butler 的记忆与表达进行整理。",
                        "memory_stream": "talk",
                        "event_type": "conversation_turn",
                        "status": "completed",
                        "context_tags": ["memory", "self_mind"],
                        "self_mind_cues": [f"续想线索{index}"],
                    }
                )

            manager._save_recent_entries(str(workspace), entries)

            ladder = manager._load_recent_summary_ladder(str(workspace))
            labels = [item.get("label") for item in ladder]
            self.assertIn("最近10天", labels)
            self.assertIn("最近4个月", labels)
            self.assertIn("最近1年", labels)
            text = manager._render_recent_summary_ladder_context(ladder, max_chars=2000)
            self.assertIn("最近10天", text)
            self.assertIn("最近4个月", text)

    def test_behavior_mirror_uses_audit_and_digest_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            manager._append_heartbeat_tell_user_audit(
                str(workspace),
                intent={"share_type": "thought_share", "share_reason": "想同步一下", "candidate": "有个想法"},
                text="作为系统：请查看当前处理结果：第一，第二，第三",
                status="sent",
            )
            digest_dir = workspace / "工作区" / "with_user" / "feishu_chat_history" / "digest"
            digest_dir.mkdir(parents=True, exist_ok=True)
            (digest_dir / "digest_20260311.md").write_text("# digest\n\n- 今天的飞书回顾显示语气偏硬。", encoding="utf-8")

            excerpt = manager._render_behavior_mirror_excerpt(str(workspace), max_chars=2000)
            self.assertIn("镜像观察", excerpt)
            self.assertIn("digest回看", excerpt)

    def test_refresh_self_mind_context_includes_history_and_behavior_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            manager._append_heartbeat_tell_user_audit(
                str(workspace),
                intent={"share_type": "thought_share", "share_reason": "想顺手说一句"},
                text="作为系统：这是一次较硬的播报。",
                status="ready",
            )
            manager._append_self_mind_listener_turn(
                str(workspace),
                "你这两天在想什么",
                "我在想怎么更自然地陪你聊天。",
            )

            manager._refresh_self_mind_context(str(workspace), {"status": "pending", "share_type": "thought_share"}, last_event="intent_pending")

            context_path = workspace / "butler_main" / "butle_bot_space" / "self_mind" / "current_context.md"
            mirror_path = workspace / "butler_main" / "butle_bot_space" / "self_mind" / "behavior_mirror.md"
            perception_path = workspace / "butler_main" / "butle_bot_space" / "self_mind" / "perception_snapshot.md"
            text = context_path.read_text(encoding="utf-8")
            self.assertIn("自我认知体系", text)
            self.assertIn("最近感知", text)
            self.assertIn("self_mind 自己最近聊天", text)
            self.assertIn("行为镜像", text)
            self.assertTrue(mirror_path.exists())
            self.assertTrue(perception_path.exists())
            self.assertFalse((workspace / "butler_main" / "butle_bot_space" / "self_mind" / "behavior_queue.json").exists())

    def test_self_mind_cycle_keeps_agent_task_as_pending_self_lane_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "focus": "继续推进记忆架构拆层",
                    "why": "这件事已经超出单句表达，需要 self_mind 自己的工程空间推进",
                    "self_note": "self_mind 读取 talk-heartbeat，但不再让它们反写我。",
                    "decision": "agent",
                    "agent_task": "把 self_mind 和 heartbeat 的边界再收紧一层，并写到 agent_space",
                    "priority": 88,
                    "done_when": "先补规则，再留结果、证据和下一步",
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )
            manager._save_recent_entries(
                str(workspace),
                [
                    {
                        "memory_id": "beat-1",
                        "timestamp": "2026-03-11 13:20:00",
                        "topic": "心跳规划与执行",
                        "summary": "heartbeat 刚完成一轮规划与执行。",
                        "memory_stream": "task_signal",
                        "event_type": "heartbeat_snapshot",
                        "status": "completed",
                    }
                ],
                pool="beat",
            )
            manager._run_self_mind_cycle_once(str(workspace), timeout=60, model="auto")

            context_path = workspace / "butler_main" / "butle_bot_space" / "self_mind" / "current_context.md"
            state_path = workspace / "butler_main" / "butle_bot_space" / "self_mind" / "mind_loop_state.json"

            self.assertTrue(context_path.exists())
            self.assertTrue(state_path.exists())
            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            pending_item = state_payload.get("pending_self_lane_item") or {}
            self.assertEqual(pending_item.get("action_type"), "agent_task")
            self.assertIn("边界再收紧一层", str(pending_item.get("candidate") or ""))
            context_text = context_path.read_text(encoding="utf-8")
            self.assertIn("当前主体感", context_text)
            self.assertIn("self_mind agent_space 待续动作", context_text)

    def test_self_mind_cycle_can_send_direct_talk(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "focus": "顺着上一轮继续说一句",
                    "why": "这是低复杂度、适合直接说的一句",
                    "self_note": "说短一点，不要像系统播报。",
                    "decision": "talk",
                    "talk": "【talk】我刚把脑子和 heartbeat 的关系又理顺了一层，想跟你同步个很短的点。",
                    "priority": 90,
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "tell_user_receive_id": "ou_demo",
                    "tell_user_receive_id_type": "open_id",
                },
                run_model_fn=fake_model,
            )
            sent = {"text": ""}
            manager._send_private_message = lambda _cfg, text, **_kwargs: sent.__setitem__("text", text) or True

            proposal = manager._run_self_mind_cycle_once(str(workspace), timeout=60, model="auto")

            self.assertEqual(proposal["status"], "self-executed")
            self.assertIn("理顺了一层", sent["text"])
            state_path = workspace / "butler_main" / "butle_bot_space" / "self_mind" / "mind_loop_state.json"
            self.assertTrue(state_path.exists())
            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn("last_direct_talk_at", state_payload)

    def test_self_mind_cycle_no_longer_enqueues_heartbeat_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "focus": "把这轮想法留给 self_mind agent_space",
                    "why": "先在自己的执行空间落结果，不干预心跳。",
                    "decision": "agent",
                    "agent_task": "把这个想法先落成 self_mind agent_space 里的任务，不要接 heartbeat。",
                    "done_when": "进入 pending_self_lane_item",
                    "priority": 90,
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )
            sent_calls = []
            manager._send_private_message = lambda _cfg, text, **kwargs: sent_calls.append({"text": text, **kwargs}) or True

            proposal = manager._run_self_mind_cycle_once(str(workspace), timeout=60, model="auto")

            self.assertEqual(proposal["status"], "agent-pending")
            self.assertEqual(sent_calls, [])
            beat_recent = manager.get_recent_entries(str(workspace), pool="beat")
            self.assertEqual(beat_recent, [])
            state_payload = manager._load_self_mind_state(str(workspace))
            self.assertEqual((state_payload.get("pending_self_lane_item") or {}).get("action_type"), "agent_task")

    def test_self_mind_direct_talk_requires_explicit_talk_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "startup_notify_open_id": "startup-u",
                    "startup_notify_receive_id_type": "open_id",
                },
                run_model_fn=lambda *_: (
                    json.dumps(
                        {
                            "decision": "talk",
                            "focus": "同步一个进展",
                            "why": "这轮更适合直接开口",
                            "talk": "【talk】想跟你同步个小进展。",
                            "self_note": "短一点",
                        },
                        ensure_ascii=False,
                    ),
                    True,
                ),
            )
            sent = []
            manager._send_private_message = lambda _cfg, text, **kwargs: sent.append({"text": text, **kwargs}) or True

            proposal = manager._run_self_mind_cycle_once(str(workspace), 60, "auto")

            self.assertEqual(proposal["decision"], "talk")
            self.assertEqual(proposal["status"], "hold")
            self.assertEqual(proposal["suppression_reason"], "direct-talk-deferred-or-unavailable")
            self.assertEqual(sent, [])

    def test_self_mind_direct_talk_respects_priority_threshold_and_logs_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "tell_user_receive_id": "talk-u",
                    "tell_user_receive_id_type": "open_id",
                    "memory": {
                        "self_mind": {
                            "direct_talk_priority_threshold": 80,
                            "direct_talk_min_interval_seconds": 0,
                            "direct_talk_recent_talk_defer_seconds": 0,
                        }
                    },
                },
                run_model_fn=lambda *_: (
                    json.dumps(
                        {
                            "decision": "talk",
                            "focus": "同步一个低优先级进展",
                            "why": "有点想说，但优先级不高",
                            "talk": "【talk】这是一个低优先级同步。",
                            "priority": 40,
                        },
                        ensure_ascii=False,
                    ),
                    True,
                ),
            )
            sent = []
            manager._send_private_message = lambda _cfg, text, **kwargs: sent.append({"text": text, **kwargs}) or True

            proposal = manager._run_self_mind_cycle_once(str(workspace), 60, "auto")

            self.assertEqual(proposal["decision"], "talk")
            self.assertEqual(proposal["status"], "hold")
            self.assertEqual(proposal["suppression_reason"], "direct-talk-deferred-or-unavailable")
            self.assertEqual(sent, [])
            log_text = (workspace / "butler_main" / "butle_bot_space" / "self_mind" / "logs" / f"mental_stream_{datetime.now().strftime('%Y%m%d')}.jsonl").read_text(encoding="utf-8")
            self.assertIn('"event_type": "self_mind_direct_talk_suppressed"', log_text)
            self.assertIn('"suppression_reason": "priority-below-threshold"', log_text)

    def test_self_mind_direct_talk_logs_send_failure_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "tell_user_receive_id": "talk-u",
                    "tell_user_receive_id_type": "open_id",
                    "memory": {
                        "self_mind": {
                            "direct_talk_priority_threshold": 0,
                            "direct_talk_min_interval_seconds": 0,
                            "direct_talk_recent_talk_defer_seconds": 0,
                        }
                    },
                },
                run_model_fn=lambda *_: (
                    json.dumps(
                        {
                            "decision": "talk",
                            "focus": "同步一个进展",
                            "why": "这轮适合直接说",
                            "talk": "【talk】这轮准备直接说。",
                            "priority": 90,
                        },
                        ensure_ascii=False,
                    ),
                    True,
                ),
            )
            manager._send_private_message = lambda *_args, **_kwargs: False

            proposal = manager._run_self_mind_cycle_once(str(workspace), 60, "auto")

            self.assertEqual(proposal["status"], "hold")
            self.assertEqual(proposal["suppression_reason"], "direct-talk-deferred-or-unavailable")
            log_text = (workspace / "butler_main" / "butle_bot_space" / "self_mind" / "logs" / f"mental_stream_{datetime.now().strftime('%Y%m%d')}.jsonl").read_text(encoding="utf-8")
            self.assertIn('"suppression_reason": "direct-talk-send-failed"', log_text)

    def test_self_mind_cycle_can_close_or_expire_existing_bridge_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            manager._save_self_mind_bridge_items(
                str(workspace),
                [
                    {
                        "bridge_id": "bridge-done",
                        "created_at": "2026-03-11 10:00:00",
                        "created_epoch": time.time() - 3600,
                        "candidate": "学会给用户发图",
                        "action_channel": "heartbeat",
                        "action_type": "visual",
                        "status": "body_progressed",
                    },
                    {
                        "bridge_id": "bridge-old",
                        "created_at": "2026-03-07 10:00:00",
                        "created_epoch": time.time() - 5 * 24 * 3600,
                        "candidate": "一个旧想法",
                        "action_channel": "heartbeat",
                        "action_type": "explore",
                        "status": "pending",
                    },
                ],
            )

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {"action_channel": "hold", "action_type": "none"}
                return json.dumps(payload, ensure_ascii=False), True

            manager._run_model_fn = fake_model
            manager._run_self_mind_cycle_once(str(workspace), timeout=60, model="auto")

            bridge_path = workspace / "butler_main" / "butle_bot_space" / "self_mind" / "mind_body_bridge.json"
            self.assertFalse(bridge_path.exists())

    def test_self_mind_cycle_preserves_custom_action_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "focus": "想去网上逛一圈找灵感",
                    "candidate": "看看最近有没有能学来给用户惊喜的小技巧",
                    "reason": "这是一个还没必要硬塞进固定动作词表的新动作",
                    "action_channel": "agent",
                    "action_type": "web-roam",
                    "priority": 72,
                    "agent_task": "先查最近能复用的 skill 和外部案例",
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )
            proposal = manager._run_self_mind_cycle_once(str(workspace), timeout=60, model="auto")

            self.assertEqual(proposal["action_type"], "web-roam")
            state_payload = manager._load_self_mind_state(str(workspace))
            self.assertEqual((state_payload.get("pending_self_lane_item") or {}).get("action_type"), "web-roam")

    def test_heartbeat_executor_branch_loads_subagent_role_excerpt(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            captured = {"prompt": ""}

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                captured["prompt"] = prompt
                return "executor ok", True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            subagent_dir = workspace / "butler_main" / "butler_bot_agent" / "agents" / "sub-agents"
            subagent_dir.mkdir(parents=True, exist_ok=True)
            (subagent_dir / "heartbeat-executor-agent.md").write_text("你是 heartbeat executor。负责把规划变成实际执行。", encoding="utf-8")

            result = manager._heartbeat_orchestrator.run_branch(
                {"branch_id": "b1", "agent_role": "executor", "prompt": "执行一次小任务"},
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(result["ok"])
            self.assertIn("你是 heartbeat executor", captured["prompt"])
            self.assertIn("执行一次小任务", captured["prompt"])

    def test_heartbeat_snapshot_flows_through_subconscious_and_can_promote_local_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))

            plan = {
                "chosen_mode": "explore",
                "execution_mode": "single",
                "reason": "从长期记忆恢复一个自我认知治理事项",
                "deferred_task_ids": [],
                "defer_reason": "",
                "tell_user": "我顺手把这轮心跳的结论整理进记忆里了。",
                "summary_prompt": "本轮心跳明确：planner 结果和 executor 结果都应交给潜意识汇总，并沉淀成长期自我认知。",
            }
            branch_results = [
                {
                    "branch_id": "self-cognition",
                    "agent_role": "executor",
                    "run_mode": "serial",
                    "ok": True,
                    "duration_seconds": 1.2,
                    "selected_task_ids": ["t-1"],
                    "defer_task_ids": [],
                    "output": "已完成一版自我认知整理，并形成可复用结论。",
                }
            ]

            manager._persist_heartbeat_snapshot_to_recent(str(workspace), plan, branch_results, "已完成一版自我认知整理，并形成可复用结论。", 1)

            beat_recent = manager._load_recent_entries(str(workspace), pool="beat")
            streams = {item.get("memory_stream") for item in beat_recent}
            self.assertIn("heartbeat_observation", streams)
            self.assertIn("mental", streams)
            self.assertIn("task_signal", streams)
            self.assertIn("relationship_signal", streams)

            local_root = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory"
            index_file = local_root / "L0_index.json"
            payload = json.loads(index_file.read_text(encoding="utf-8"))
            self.assertTrue(any(str(item.get("source_type") or "") == "heartbeat" for item in payload.get("entries") or []))


if __name__ == "__main__":
    unittest.main()
