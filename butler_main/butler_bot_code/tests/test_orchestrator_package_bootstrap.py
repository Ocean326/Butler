from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = REPO_ROOT / "butler_main"
BODY_MODULE_DIR = BUTLER_MAIN_DIR / "butler_bot_code" / "butler_bot"


class OrchestratorPackageBootstrapTests(unittest.TestCase):
    def test_import_orchestrator_package_from_repo_root(self) -> None:
        original_path = list(sys.path)
        cached_package = sys.modules.pop("butler_main.orchestrator", None)
        try:
            sys.path = [item for item in sys.path if item not in {str(BUTLER_MAIN_DIR), str(BODY_MODULE_DIR)}]
            self.assertNotIn(str(BUTLER_MAIN_DIR), sys.path)
            self.assertNotIn(str(BODY_MODULE_DIR), sys.path)

            package = importlib.import_module("butler_main.orchestrator")

            self.assertEqual(package.__name__, "butler_main.orchestrator")
            self.assertIn(str(BUTLER_MAIN_DIR), sys.path)
            self.assertIn(str(BODY_MODULE_DIR), sys.path)
        finally:
            if cached_package is not None:
                sys.modules["butler_main.orchestrator"] = cached_package
            sys.path = original_path


if __name__ == "__main__":
    unittest.main()
