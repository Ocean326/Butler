from __future__ import annotations

import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from butler_main.agents_os.runtime import RuntimeRequestState


class RuntimeRequestStateTests(unittest.TestCase):
    def test_scope_sets_and_restores_override(self) -> None:
        state = RuntimeRequestState()

        self.assertEqual(state.get_override(), {})
        with state.scope({"cli": "cursor", "model": "gpt-5.4"}):
            self.assertEqual(state.get_override(), {"cli": "cursor", "model": "gpt-5.4"})
        self.assertEqual(state.get_override(), {})

    def test_nested_scope_restores_previous_value(self) -> None:
        state = RuntimeRequestState()

        with state.scope({"cli": "cursor"}):
            self.assertEqual(state.get_override(), {"cli": "cursor"})
            with state.scope({"cli": "codex", "model": "auto"}):
                self.assertEqual(state.get_override(), {"cli": "codex", "model": "auto"})
            self.assertEqual(state.get_override(), {"cli": "cursor"})


if __name__ == "__main__":
    unittest.main()
