import json
import tempfile
import time
from pathlib import Path
import sys
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

from memory_manager import MemoryManager  # noqa: E402


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

            self.assertEqual(manager._recent_max_items("talk"), 15)
            self.assertEqual(manager._recent_max_items("beat"), 15)
            self.assertEqual(manager._recent_max_chars("talk"), 15000)
            self.assertEqual(manager._recent_max_chars("beat"), 20000)

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