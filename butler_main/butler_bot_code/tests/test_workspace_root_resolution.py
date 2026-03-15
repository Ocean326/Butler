from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "butler_main" / "butler_bot_code" / "butler_bot"))

from butler_paths import resolve_butler_root  # noqa: E402
from memory_manager import MemoryManager  # noqa: E402


class WorkspaceRootResolutionTests(unittest.TestCase):
    def test_resolve_butler_root_accepts_parent_directory(self) -> None:
        self.assertEqual(resolve_butler_root(REPO_ROOT), REPO_ROOT)

    def test_heartbeat_upgrade_request_path_uses_butler_root(self) -> None:
        manager = MemoryManager(config_provider=lambda: {"workspace_root": str(REPO_ROOT)}, run_model_fn=lambda *_: ("", False))
        path = manager._heartbeat_upgrade_request_path(str(REPO_ROOT))
        self.assertEqual(path, REPO_ROOT / "工作区" / "heartbeat_upgrade_request.json")


if __name__ == "__main__":
    unittest.main()
