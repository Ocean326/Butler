import sys
import tempfile
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from registry.skill_registry import load_skill_catalog, render_skill_catalog_for_prompt  # noqa: E402


class SkillRegistryTests(unittest.TestCase):
    def test_load_skill_catalog_parses_extended_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "butler_main" / "butler_bot_agent" / "skills" / "operations" / "sample-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: sample-skill
description: Sample capability for registry parsing.
category: operations
trigger_examples: 巡检, 今日启动, health-check
allowed_roles: feishu-workstation-agent, heartbeat-executor-agent
risk_level: low
heartbeat_safe: true
requires_skill_read: false
---

# Sample Skill
""",
                encoding="utf-8",
            )

            catalog = load_skill_catalog(root)

            self.assertEqual(len(catalog), 1)
            item = catalog[0]
            self.assertEqual(item.name, "sample-skill")
            self.assertEqual(item.category, "operations")
            self.assertEqual(item.trigger_examples, ("巡检", "今日启动", "health-check"))
            self.assertEqual(item.allowed_roles, ("feishu-workstation-agent", "heartbeat-executor-agent"))
            self.assertEqual(item.risk_level, "low")
            self.assertTrue(item.heartbeat_safe)
            self.assertFalse(item.requires_skill_read)
            self.assertTrue(item.relative_skill_file.endswith("sample-skill/SKILL.md"))

    def test_render_skill_catalog_for_prompt_includes_metadata_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "butler_main" / "butler_bot_agent" / "skills" / "research" / "reader-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: reader-skill
description: Reads and summarizes external references.
trigger_examples: 文献, 资料抓取
allowed_roles: literature-agent, discussion-agent
heartbeat_safe: true
---

# Reader Skill
""",
                encoding="utf-8",
            )

            prompt = render_skill_catalog_for_prompt(root)

            self.assertIn("reader-skill", prompt)
            self.assertIn("triggers=文献/资料抓取", prompt)
            self.assertIn("roles=literature-agent/discussion-agent", prompt)
            self.assertIn("heartbeat-safe", prompt)

    def test_load_skill_catalog_skips_temp_and_non_utf8_skill_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good_dir = root / "butler_main" / "butler_bot_agent" / "skills" / "operations" / "good-skill"
            good_dir.mkdir(parents=True, exist_ok=True)
            (good_dir / "SKILL.md").write_text(
                """---
name: good-skill
description: Valid utf8 skill.
---
""",
                encoding="utf-8",
            )

            bad_dir = root / "butler_main" / "butler_bot_agent" / "skills" / "operations" / "bad-skill"
            bad_dir.mkdir(parents=True, exist_ok=True)
            (bad_dir / "SKILL.md").write_bytes(b"---\nname: bad-skill\ndescription: \xb3\xff\n---\n")

            tmp_dir = root / "butler_main" / "butler_bot_agent" / "skills" / "_tmp_probe" / "temp-skill"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            (tmp_dir / "SKILL.md").write_text(
                """---
name: temp-skill
description: Should be ignored.
---
""",
                encoding="utf-8",
            )

            catalog = load_skill_catalog(root)

            self.assertEqual([item.name for item in catalog], ["good-skill"])


if __name__ == "__main__":
    unittest.main()
