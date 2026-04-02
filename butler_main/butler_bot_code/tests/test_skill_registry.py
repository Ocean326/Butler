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

from butler_main.agents_os.skills.runtime_catalog import (  # noqa: E402
    build_skill_registry_diagnostics,
    get_skill_collection_detail,
    list_skill_collections,
    load_skill_catalog,
    render_skill_catalog_for_prompt,
)


class SkillRegistryTests(unittest.TestCase):
    def test_load_skill_catalog_parses_extended_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "butler_main" / "sources" / "skills" / "pool" / "operations" / "sample-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: sample-skill
description: Sample capability for registry parsing.
category: operations
trigger_examples: 巡检, 今日启动, health-check
allowed_roles: feishu-workstation-agent, codex-executor-agent
risk_level: low
automation_safe: true
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
            self.assertEqual(item.family_id, "sample-skill")
            self.assertEqual(item.family_label, "sample-skill")
            self.assertEqual(item.trigger_examples, ("巡检", "今日启动", "health-check"))
            self.assertEqual(item.allowed_roles, ("feishu-workstation-agent", "codex-executor-agent"))
            self.assertEqual(item.risk_level, "low")
            self.assertTrue(item.automation_safe)
            self.assertFalse(item.requires_skill_read)
            self.assertTrue(item.relative_skill_file.endswith("sample-skill/SKILL.md"))

    def test_render_skill_catalog_for_prompt_renders_family_shortlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "butler_main" / "sources" / "skills" / "pool" / "research" / "reader-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: reader-skill
description: Reads and summarizes external references.
trigger_examples: 文献, 资料抓取
allowed_roles: literature-agent, discussion-agent
automation_safe: true
---

# Reader Skill
""",
                encoding="utf-8",
            )

            prompt = render_skill_catalog_for_prompt(root)

            self.assertIn("capability families", prompt)
            self.assertIn("reader-skill", prompt)
            self.assertIn("family=reader-skill", prompt)
            self.assertNotIn("triggers=", prompt)
            self.assertNotIn("roles=", prompt)
            self.assertNotIn("automation-safe", prompt)

    def test_load_skill_catalog_skips_temp_and_non_utf8_skill_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good_dir = root / "butler_main" / "sources" / "skills" / "pool" / "operations" / "good-skill"
            good_dir.mkdir(parents=True, exist_ok=True)
            (good_dir / "SKILL.md").write_text(
                """---
name: good-skill
description: Valid utf8 skill.
---
""",
                encoding="utf-8",
            )

            bad_dir = root / "butler_main" / "sources" / "skills" / "pool" / "operations" / "bad-skill"
            bad_dir.mkdir(parents=True, exist_ok=True)
            (bad_dir / "SKILL.md").write_bytes(b"---\nname: bad-skill\ndescription: \xb3\xff\n---\n")

            tmp_dir = root / "butler_main" / "sources" / "skills" / "_tmp_probe" / "temp-skill"
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

    def test_load_skill_catalog_honors_sources_collection_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_registry = root / "butler_main" / "sources" / "skills" / "collections" / "registry.json"
            skill_a = root / "butler_main" / "sources" / "skills" / "pool" / "operations" / "alpha-skill"
            skill_b = root / "butler_main" / "sources" / "skills" / "pool" / "operations" / "beta-skill"
            source_registry.parent.mkdir(parents=True, exist_ok=True)
            skill_a.mkdir(parents=True, exist_ok=True)
            skill_b.mkdir(parents=True, exist_ok=True)
            (skill_a / "SKILL.md").write_text("---\nname: alpha-skill\n---\n", encoding="utf-8")
            (skill_b / "SKILL.md").write_text("---\nname: beta-skill\n---\n", encoding="utf-8")
            source_registry.write_text(
                """{
  "version": 1,
  "collections": {
    "chat_default": {
                        "skills": [
        "./butler_main/sources/skills/pool/operations/beta-skill"
      ]
    }
  }
}""",
                encoding="utf-8",
            )

            catalog = load_skill_catalog(root, collection_id="chat_default")

            self.assertEqual([item.name for item in catalog], ["beta-skill"])

    def test_collection_registry_views_surface_metadata_and_skip_inactive_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_registry = root / "butler_main" / "sources" / "skills" / "collections" / "registry.json"
            active_skill = root / "butler_main" / "sources" / "skills" / "pool" / "operations" / "active-skill"
            private_skill = root / "butler_main" / "sources" / "skills" / "pool" / "operations" / "private-skill"
            source_registry.parent.mkdir(parents=True, exist_ok=True)
            active_skill.mkdir(parents=True, exist_ok=True)
            private_skill.mkdir(parents=True, exist_ok=True)
            (active_skill / "SKILL.md").write_text(
                "---\nname: active-skill\nstatus: active\nrisk_level: low\n---\n",
                encoding="utf-8",
            )
            (private_skill / "SKILL.md").write_text(
                "---\nname: private-skill\nstatus: private\nrisk_level: high\n---\n",
                encoding="utf-8",
            )
            source_registry.write_text(
                """{
  "version": 1,
  "collections": {
    "codex_default": {
      "description": "Default Codex skill exposure",
      "owner": "butler",
      "default_injection_mode": "shortlist",
      "skills": [
        "./butler_main/sources/skills/pool/operations/active-skill",
        "./butler_main/sources/skills/pool/operations/private-skill"
      ]
    }
  }
}""",
                encoding="utf-8",
            )

            collections = list_skill_collections(root)
            detail = get_skill_collection_detail(root, collection_id="codex_default")
            diagnostics = build_skill_registry_diagnostics(root)

            self.assertEqual(collections[0]["collection_id"], "codex_default")
            self.assertEqual(collections[0]["owner"], "butler")
            self.assertEqual(collections[0]["skill_count"], 1)
            self.assertEqual([item["name"] for item in detail["skills"]], ["active-skill"])
            self.assertTrue(any(item["kind"] == "inactive_reference" for item in diagnostics["issues"]))

    def test_load_skill_catalog_skips_inactive_skills_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active_dir = root / "butler_main" / "sources" / "skills" / "pool" / "general" / "active-skill"
            draft_dir = root / "butler_main" / "sources" / "skills" / "pool" / "incubating" / "draft-skill"
            active_dir.mkdir(parents=True, exist_ok=True)
            draft_dir.mkdir(parents=True, exist_ok=True)
            (active_dir / "SKILL.md").write_text(
                """---
name: active-skill
description: Visible skill.
status: active
---
""",
                encoding="utf-8",
            )
            (draft_dir / "SKILL.md").write_text(
                """---
name: draft-skill
description: Draft only.
status: incubating
---
""",
                encoding="utf-8",
            )

            catalog = load_skill_catalog(root)

            self.assertEqual([item.name for item in catalog], ["active-skill"])

    def test_repo_research_reading_skill_is_exposed_in_chat_and_codex_collections(self):
        chat_catalog = {item.name: item for item in load_skill_catalog(REPO_ROOT, collection_id="chat_default")}
        codex_catalog = {item.name: item for item in load_skill_catalog(REPO_ROOT, collection_id="codex_default")}

        self.assertIn("paper-first-principles-review", chat_catalog)
        self.assertIn("paper-first-principles-review", codex_catalog)
        self.assertEqual(chat_catalog["paper-first-principles-review"].family_id, "paper-reading")
        self.assertEqual(chat_catalog["paper-first-principles-review"].family_label, "论文精读族")
        self.assertEqual(chat_catalog["paper-first-principles-review"].risk_level, "low")


if __name__ == "__main__":
    unittest.main()
