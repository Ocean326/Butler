from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class LegacyExecutionShellTombstoneTests(unittest.TestCase):
    def test_retired_execution_shell_folders_are_tombstones_only(self) -> None:
        targets = (
            REPO_ROOT / "butler_main" / "butler_bot_code" / "butler_bot" / "heartbeat",
            REPO_ROOT / "butler_main" / "butler_bot_code" / "butler_bot" / "legacy",
            REPO_ROOT / "butler_main" / "butler_bot_code" / "butler_bot" / "obsolete",
        )
        for folder in targets:
            with self.subTest(folder=str(folder)):
                if not folder.exists():
                    self.assertFalse(folder.exists())
                    continue
                self.assertTrue(folder.is_dir(), msg=str(folder))
                self.assertTrue((folder / "README.md").is_file(), msg=f"missing tombstone README in {folder}")
                tracked_python_files = [
                    path
                    for path in folder.rglob("*.py")
                    if "__pycache__" not in path.parts
                ]
                self.assertEqual(tracked_python_files, [], msg=str(tracked_python_files))


if __name__ == "__main__":
    unittest.main()
