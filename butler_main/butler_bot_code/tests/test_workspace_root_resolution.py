from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "butler_bot_code" / "butler_bot"))

from butler_paths import resolve_butler_root  # noqa: E402
from memory_manager import MemoryManager  # noqa: E402


class WorkspaceRootResolutionTests(unittest.TestCase):
    def test_resolve_butler_root_accepts_parent_directory(self) -> None:
        parent = ROOT.parent
        self.assertEqual(resolve_butler_root(parent), ROOT)

    def test_heartbeat_upgrade_request_path_uses_butler_root(self) -> None:
        manager = MemoryManager(config_provider=lambda: {"workspace_root": str(ROOT.parent)}, run_model_fn=lambda *_: ("", False))
        path = manager._heartbeat_upgrade_request_path(str(ROOT.parent))
        self.assertEqual(path, ROOT / "工作区" / "heartbeat_upgrade_request.json")


if __name__ == "__main__":
    unittest.main()