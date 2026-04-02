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
from butler_main.chat.memory_runtime import ChatRuntimeRequestOverrideRuntime


class ChatRuntimeRequestOverrideRuntimeTests(unittest.TestCase):
    def test_runtime_reads_override_from_generic_state_source(self) -> None:
        state = RuntimeRequestState()
        runtime = ChatRuntimeRequestOverrideRuntime(state_source=state)

        self.assertEqual(runtime.get_runtime_request_override(), {})
        with state.scope({"cli": "cursor", "model": "gpt-5.4"}):
            self.assertEqual(
                runtime.get_runtime_request_override(),
                {"cli": "cursor", "model": "gpt-5.4"},
            )


if __name__ == "__main__":
    unittest.main()
