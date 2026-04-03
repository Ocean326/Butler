from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.chat.providers.butler_prompt_support_provider import ButlerChatPromptSupportProvider
from butler_main.chat.pathing import LOCAL_MEMORY_DIR_REL


class ChatPromptSupportProviderTests(unittest.TestCase):
    def test_provider_renders_chat_owned_catalogs_and_local_memory_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "butler_main" / "sources" / "skills" / "pool" / "ops" / "daily-review"
            local_memory_dir = root / LOCAL_MEMORY_DIR_REL
            skills_dir.mkdir(parents=True, exist_ok=True)
            local_memory_dir.mkdir(parents=True, exist_ok=True)

            (skills_dir / "SKILL.md").write_text(
                "---\nname: daily-review\ndescription: 每日复盘整理\ncategory: operations\n---\n# daily-review",
                encoding="utf-8",
            )
            (local_memory_dir / "prefs.md").write_text(
                "# 用户偏好\n\n当前结论：以后输出先给结论再给细节。\n",
                encoding="utf-8",
            )

            provider = ButlerChatPromptSupportProvider()
            skills_text = provider.render_skills_prompt(str(root))
            capabilities_text = provider.render_agent_capabilities_prompt(str(root))
            local_hits = provider.render_local_memory_hits(str(root), "结论 细节", memory_types=("profile", "task", "reference"))

            self.assertIn("daily-review", skills_text)
            self.assertIn("capability families", skills_text)
            self.assertIn("Codex 原生并行协作", capabilities_text)
            self.assertIn("不要为了并行而并行", capabilities_text)
            self.assertIn("以后输出先给结论再给细节", local_hits)

    def test_provider_renders_protocol_block(self) -> None:
        provider = ButlerChatPromptSupportProvider()
        block = provider.render_protocol_block("update_agent_maintenance")
        self.assertIn("统一维护入口协议", block)

    def test_provider_prefers_sources_skill_collection_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_registry = root / "butler_main" / "sources" / "skills" / "collections" / "registry.json"
            legacy_a = root / "butler_main" / "sources" / "skills" / "pool" / "ops" / "alpha"
            legacy_b = root / "butler_main" / "sources" / "skills" / "pool" / "ops" / "beta"
            source_registry.parent.mkdir(parents=True, exist_ok=True)
            legacy_a.mkdir(parents=True, exist_ok=True)
            legacy_b.mkdir(parents=True, exist_ok=True)
            (legacy_a / "SKILL.md").write_text(
                "---\nname: alpha\ndescription: alpha skill\ncategory: operations\n---\n# alpha",
                encoding="utf-8",
            )
            (legacy_b / "SKILL.md").write_text(
                "---\nname: beta\ndescription: beta skill\ncategory: operations\n---\n# beta",
                encoding="utf-8",
            )
            source_registry.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "collections": {
                            "chat_default": {
                                "skills": [
                                    "./butler_main/platform/skills/pool/ops/beta",
                                    "./butler_main/platform/skills/pool/ops/alpha",
                                ]
                            }
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            provider = ButlerChatPromptSupportProvider()
            skills_text = provider.render_skills_prompt(str(root), collection_id="chat_default", max_skills=10, max_chars=4000)

            self.assertIn("collection=chat_default", skills_text)
            self.assertLess(skills_text.find("beta"), skills_text.find("alpha"))
            self.assertNotIn("collection=all", skills_text)
            self.assertNotIn("@ ./butler_main", skills_text)

    def test_provider_filters_obsolete_guardian_memory_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_memory_dir = root / LOCAL_MEMORY_DIR_REL
            local_memory_dir.mkdir(parents=True, exist_ok=True)

            (local_memory_dir / "guardian架构与运维_总览.md").write_text(
                "# Guardian 架构与运维（总览）\n\n"
                "当前结论：Guardian 为守护进程，负责重启 Butler 的权限在 Guardian。\n",
                encoding="utf-8",
            )
            (local_memory_dir / "人格与自我认知.md").write_text(
                "# 人格与自我认知\n\n"
                "当前结论：旧 guardian 已退役，当前守护与任务真源以主进程 + task_ledger.json + background_maintenance 为准。\n",
                encoding="utf-8",
            )

            provider = ButlerChatPromptSupportProvider()
            local_hits = provider.render_local_memory_hits(
                str(root),
                "guardian 守护 重启",
                memory_types=("profile", "task", "reference"),
                max_chars=4000,
            )

            self.assertIn("旧 guardian 已退役", local_hits)
            self.assertIn("task_ledger.json", local_hits)
            self.assertNotIn("负责重启 Butler 的权限在 Guardian", local_hits)

    def test_provider_rebuilds_local_memory_index_when_source_files_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_memory_dir = root / LOCAL_MEMORY_DIR_REL
            local_memory_dir.mkdir(parents=True, exist_ok=True)
            prefs_path = local_memory_dir / "prefs.md"
            prefs_path.write_text(
                "# 用户偏好\n\n当前结论：以后输出先给短结论。\n",
                encoding="utf-8",
            )

            provider = ButlerChatPromptSupportProvider()
            initial_hits = provider.render_local_memory_hits(
                str(root),
                "短结论",
                memory_types=("profile", "task", "reference"),
            )
            self.assertIn("先给短结论", initial_hits)

            prefs_path.write_text(
                "# 用户偏好\n\n当前结论：以后输出先给最终结论，再补细节。\n",
                encoding="utf-8",
            )
            future = time.time() + 2
            os.utime(prefs_path, (future, future))

            refreshed_hits = provider.render_local_memory_hits(
                str(root),
                "最终结论 细节",
                memory_types=("profile", "task", "reference"),
            )
            self.assertIn("先给最终结论，再补细节", refreshed_hits)
            self.assertNotIn("先给短结论", refreshed_hits)


if __name__ == "__main__":
    unittest.main()
