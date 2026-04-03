import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from butler_main.sources.skills.shared.upstream_source_runtime import SOURCE_OUTPUT_NAMES
from butler_main.sources.skills.shared.workspace_layout import skill_runtime_dir, skill_source_root, skill_temp_dir


class SkillWorkspaceLayoutTests(unittest.TestCase):
    def test_runtime_outputs_live_under_butler_runtime_namespace(self) -> None:
        path = skill_runtime_dir(REPO_ROOT, "web-article-extract")
        self.assertEqual(
            path,
            REPO_ROOT / "工作区" / "Butler" / "runtime" / "skills" / "web-article-extract",
        )

    def test_skill_temp_outputs_live_under_skill_source_namespace(self) -> None:
        path = skill_temp_dir(REPO_ROOT, "verify")
        self.assertEqual(
            path,
            REPO_ROOT / "butler_main" / "platform" / "skills" / "temp" / "verify",
        )

    def test_upstream_runtime_uses_public_skill_name_for_output(self) -> None:
        self.assertEqual(SOURCE_OUTPUT_NAMES["trafilatura-web-extract"], "web-article-extract")
        self.assertEqual(SOURCE_OUTPUT_NAMES["feedparser-rss-ingest"], "rss-feed-watch")

    def test_skill_source_root_points_to_platform_skills(self) -> None:
        self.assertEqual(
            skill_source_root(REPO_ROOT),
            REPO_ROOT / "butler_main" / "platform" / "skills",
        )


if __name__ == "__main__":
    unittest.main()
