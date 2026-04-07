from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
for candidate in (REPO_ROOT, BUTLER_MAIN_DIR):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from butler_main import vibe_close  # noqa: E402


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(root),
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _bootstrap_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "test-user")
    _git(root, "config", "user.email", "test@example.com")
    (root / "README.md").write_text("# temp repo\n", encoding="utf-8")
    (root / "docs" / "daily-upgrade" / "0402").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "daily-upgrade" / "0402" / "00_当日总纲.md").write_text("# daily\n", encoding="utf-8")
    (root / "docs" / "project-map").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "project-map" / "03_truth_matrix.md").write_text("# tm\n", encoding="utf-8")
    (root / "docs" / "project-map" / "04_change_packets.md").write_text("# cp\n", encoding="utf-8")
    (root / "docs" / "README.md").write_text("# docs\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "chore: bootstrap")


class VibeCloseAnalysisTests(unittest.TestCase):
    def test_docs_only_governance_closeout_stays_system_without_worktree_when_planned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bootstrap_repo(root)
            (root / "tools").mkdir()
            (root / "tools" / "README.md").write_text("# tools\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# agents updated\n", encoding="utf-8")

            analysis = vibe_close.analyze_repo(root, topic="closeout", planned=True, today=date(2026, 4, 2))

        self.assertEqual(analysis.change_level, "system")
        self.assertFalse(analysis.requires_worktree)
        self.assertIn("docs/project-map/03_truth_matrix.md", analysis.doc_targets)
        self.assertEqual(analysis.suggested_commit_type, "chore")

    def test_frontdoor_change_defaults_to_normal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bootstrap_repo(root)
            chat_dir = root / "butler_main" / "chat"
            chat_dir.mkdir(parents=True)
            (chat_dir / "router.py").write_text("ROUTER = 1\n", encoding="utf-8")

            analysis = vibe_close.analyze_repo(root, topic="router", planned=False, today=date(2026, 4, 2))

        self.assertEqual(analysis.change_level, "normal")
        self.assertFalse(analysis.requires_worktree)
        self.assertIn("docs/daily-upgrade/0402/00_当日总纲.md", analysis.doc_targets)
        self.assertEqual(analysis.suggested_commit_type, "feat")


class VibeCloseApplyTests(unittest.TestCase):
    def test_apply_docs_only_system_closeout_commits_on_main_without_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bootstrap_repo(root)
            (root / "tools").mkdir()
            (root / "tools" / "README.md").write_text("# tool docs\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# updated protocol\n", encoding="utf-8")

            result = vibe_close.apply_closeout(
                root,
                topic="docs-closeout",
                summary="update docs closeout",
                commit_type="chore",
                push=False,
                planned=True,
            )

            current_branch = _git(root, "branch", "--show-current")
            worktree_list = _git(root, "worktree", "list")
            head_subject = _git(root, "log", "--oneline", "-1", "main")

        self.assertTrue(result.commit_created)
        self.assertEqual(result.branch_before, "main")
        self.assertEqual(result.branch_after, "main")
        self.assertEqual(result.commit_branch, "main")
        self.assertFalse(result.worktree_created)
        self.assertIn("chore: update docs closeout", head_subject)
        self.assertEqual(current_branch, "main")
        self.assertNotIn("docs-closeout", worktree_list)

    def test_apply_code_system_closeout_creates_branch_and_worktree_then_returns_to_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bootstrap_repo(root)
            runtime_dir = root / "butler_main" / "runtime_os"
            runtime_dir.mkdir(parents=True)
            (runtime_dir / "core.py").write_text("VALUE = 1\n", encoding="utf-8")

            result = vibe_close.apply_closeout(
                root,
                topic="runtime-closeout",
                summary="update runtime closeout",
                commit_type="chore",
                push=False,
                planned=True,
            )

            current_branch = _git(root, "branch", "--show-current")
            worktree_list = _git(root, "worktree", "list")
            head_subject = _git(root, "log", "--oneline", "-1", result.commit_branch)

        self.assertTrue(result.commit_created)
        self.assertEqual(result.branch_before, "main")
        self.assertEqual(result.branch_after, "main")
        self.assertEqual(result.commit_branch, "feat/runtime-closeout")
        self.assertTrue(result.worktree_created)
        self.assertIn("chore: update runtime closeout", head_subject)
        self.assertEqual(current_branch, "main")
        self.assertIn(result.commit_branch, worktree_list)


class VibeCloseCliTests(unittest.TestCase):
    def test_main_prints_json_for_analyze(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _bootstrap_repo(root)
            (root / "tools").mkdir()
            (root / "tools" / "README.md").write_text("# tools\n", encoding="utf-8")

            stdout = subprocess.run(
                [sys.executable, "-m", "butler_main.vibe_close", "analyze", "--repo-root", str(root), "--topic", "docs"],
                check=True,
                text=True,
                capture_output=True,
            ).stdout

        payload = json.loads(stdout)
        self.assertIn("change_level", payload)
        self.assertEqual(payload["suggested_branch"], "chore/docs")


if __name__ == "__main__":
    unittest.main()
