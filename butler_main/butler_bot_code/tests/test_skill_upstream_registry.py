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

from butler_main.agents_os.skills.upstream_registry import load_upstream_skill_conversion_registry, resolve_upstream_skill_conversion_entry  # noqa: E402


class SkillUpstreamRegistryTests(unittest.TestCase):
    def test_load_and_resolve_upstream_conversion_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = (
                root
                / "butler_main"
                / "platform" / "skills"
                / "agent"
                / "skill_manager_agent"
                / "references"
                / "upstream_skill_conversion_registry.json"
            )
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(
                """{
  "generated_at": "2026-03-24",
  "entries": {
    "demo-candidate": {
      "status": "active",
      "active_skill_name": "demo-skill",
      "active_skill_path": "./butler_main/platform/skills/pool/general/demo-skill",
      "auto_promotable": true
    }
  }
}""",
                encoding="utf-8",
            )

            payload = load_upstream_skill_conversion_registry(root)
            entry = resolve_upstream_skill_conversion_entry(root, "demo-candidate")

            self.assertEqual(payload["generated_at"], "2026-03-24")
            self.assertIsNotNone(entry)
            self.assertEqual(entry["active_skill_name"], "demo-skill")


if __name__ == "__main__":
    unittest.main()
