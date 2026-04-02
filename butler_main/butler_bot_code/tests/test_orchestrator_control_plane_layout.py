from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.orchestrator import (  # noqa: E402
    OrchestratorGovernanceBridge,
    OrchestratorService,
    OrchestratorWorkflowSessionBridge,
)


class OrchestratorControlPlaneLayoutTests(unittest.TestCase):
    def test_application_package_reexports_root_service(self) -> None:
        module = importlib.import_module("butler_main.orchestrator.application")
        self.assertIs(module.OrchestratorService, OrchestratorService)

    def test_runtime_bridge_package_exports_session_bridge(self) -> None:
        module = importlib.import_module("butler_main.orchestrator.runtime_bridge")
        self.assertIs(module.OrchestratorWorkflowSessionBridge, OrchestratorWorkflowSessionBridge)

    def test_runtime_bridge_package_exports_governance_bridge(self) -> None:
        module = importlib.import_module("butler_main.orchestrator.runtime_bridge")
        self.assertIs(module.OrchestratorGovernanceBridge, OrchestratorGovernanceBridge)


if __name__ == "__main__":
    unittest.main()
