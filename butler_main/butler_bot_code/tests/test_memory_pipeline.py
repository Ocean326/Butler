import json
import tempfile
from pathlib import Path
import sys
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

from butler_paths import CURRENT_USER_PROFILE_FILE_REL, resolve_butler_root  # noqa: E402
from memory_manager import MemoryManager  # noqa: E402
from memory_pipeline.feature_flags import MemoryPipelineFeatureFlags  # noqa: E402


class MemoryPipelineTests(unittest.TestCase):
    def test_feature_flags_default_to_off(self):
        flags = MemoryPipelineFeatureFlags.from_runtime_config({})
        self.assertFalse(flags.enabled)
        self.assertFalse(flags.post_turn_agent)
        self.assertFalse(flags.compact_agent)
        self.assertFalse(flags.maintenance_agent)

    def test_post_turn_memory_agent_governs_local_and_profile_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                payload = {
                    "topic": "长期偏好",
                    "summary": "用户希望以后默认输出简洁版本。",
                    "next_actions": [],
                    "relation_signal": {"preference_shift": "以后默认输出简洁版本"},
                    "long_term_candidate": {
                        "should_write": True,
                        "title": "输出风格偏好",
                        "summary": "用户希望以后默认输出简洁版本。",
                        "keywords": ["偏好", "简洁"],
                    },
                }
                return json.dumps(payload, ensure_ascii=False), True

            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "memory": {
                        "pipeline": {
                            "enabled": True,
                            "enable_post_turn_agent": True,
                        }
                    },
                },
                run_model_fn=fake_model,
            )

            manager._persist_recent_and_local_memory("记住：以后默认输出简洁版本", "好的，我记住了。", str(workspace), 60, "auto")

            matches = manager.query_local_memory(str(workspace), query_text="简洁版本", limit=5)
            self.assertEqual(len(matches), 1)
            self.assertEqual(str(matches[0].get("title") or ""), "输出风格偏好")

            profile_path = resolve_butler_root(str(workspace)) / CURRENT_USER_PROFILE_FILE_REL
            self.assertTrue(profile_path.exists())
            profile_text = profile_path.read_text(encoding="utf-8")
            self.assertIn("以后默认输出简洁版本", profile_text)

    def test_compact_memory_agent_writes_summary_candidates_without_touching_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "memory": {
                        "pipeline": {
                            "enabled": True,
                            "enable_compact_agent": True,
                            "recent_compact_min_entries": 2,
                        },
                        "talk_recent": {"storage_items": 3, "storage_max_chars": 999999},
                    },
                },
                run_model_fn=lambda *_: ("", False),
            )
            entries = [
                {
                    "memory_id": f"id-{idx}",
                    "timestamp": f"2026-03-1{idx} 10:00:00",
                    "topic": f"项目进度{idx}",
                    "summary": "项目方案、OCR 参考与产出路径整理",
                    "memory_stream": "talk",
                    "event_type": "conversation_turn",
                    "status": "completed",
                }
                for idx in range(25)
            ]

            kept, info = manager._compact_recent_entries_if_needed(entries, str(workspace), 0, "", "test-compact")

            self.assertEqual(len(kept), 20)
            self.assertIn("pipeline_compact_actions", info)
            self.assertTrue(info["pipeline_compact_actions"])
            profile_path = resolve_butler_root(str(workspace)) / CURRENT_USER_PROFILE_FILE_REL
            self.assertFalse(profile_path.exists())


if __name__ == "__main__":
    unittest.main()
