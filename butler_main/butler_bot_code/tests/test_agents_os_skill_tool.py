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

from butler_main.agents_os.skills import skill_tool


class AgentsOsSkillToolTests(unittest.TestCase):
    def test_skill_tool_list_and_read_follow_collection_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "butler_main" / "sources" / "skills" / "collections" / "registry.json"
            alpha = root / "butler_main" / "sources" / "skills" / "pool" / "ops" / "alpha"
            beta = root / "butler_main" / "sources" / "skills" / "pool" / "ops" / "beta"
            registry.parent.mkdir(parents=True, exist_ok=True)
            alpha.mkdir(parents=True, exist_ok=True)
            beta.mkdir(parents=True, exist_ok=True)
            (alpha / "SKILL.md").write_text(
                "---\nname: alpha\ndescription: alpha skill\nrisk_level: low\n---\n# alpha",
                encoding="utf-8",
            )
            (beta / "SKILL.md").write_text(
                "---\nname: beta\ndescription: beta skill\nrisk_level: medium\n---\n# beta",
                encoding="utf-8",
            )
            registry.write_text(
                """{
  "version": 1,
  "collections": {
    "chat_default": {
      "skills": [
        "./butler_main/sources/skills/pool/ops/beta"
      ]
    }
  }
}""",
                encoding="utf-8",
            )

            listed = skill_tool("list", workspace=str(root), collection="chat_default")
            searched = skill_tool("search", workspace=str(root), collection="chat_default", arg="beta")
            expanded = skill_tool("expand", workspace=str(root), collection="chat_default", arg="beta")
            read = skill_tool("read", workspace=str(root), collection="chat_default", name="beta")
            missed = skill_tool("read", workspace=str(root), collection="chat_default", name="alpha")

            self.assertTrue(listed["ok"])
            self.assertEqual([item["name"] for item in listed["items"]], ["beta"])
            self.assertEqual([family["family_id"] for family in listed["families"]], ["beta"])
            self.assertTrue(searched["ok"])
            self.assertEqual([item["name"] for item in searched["skills"]], ["beta"])
            self.assertTrue(expanded["ok"])
            self.assertEqual([item["name"] for item in expanded["items"]], ["beta"])
            self.assertTrue(read["ok"])
            self.assertIn("# beta", read["content"])
            self.assertFalse(missed["ok"])
            self.assertEqual(missed["error"], "skill_not_found")

    def test_skill_tool_exec_returns_stable_not_wired_contract(self) -> None:
        result = skill_tool("exec", workspace=".", name="demo")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "skill_exec_not_wired")


if __name__ == "__main__":
    unittest.main()
