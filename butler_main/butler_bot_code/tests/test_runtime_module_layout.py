from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))


class RuntimeModuleLayoutTests(unittest.TestCase):
    def test_root_keeps_only_primary_runtime_modules(self) -> None:
        root_files = {path.name for path in MODULE_DIR.glob("*.py")}
        self.assertEqual(
            root_files,
            {
                "agent.py",
                "butler_bot.py",
                "butler_paths.py",
                "governor.py",
                "heartbeat_orchestration.py",
                "heartbeat_service_runner.py",
                "memory_cli.py",
                "memory_manager.py",
            },
        )

    def test_grouped_subpackages_are_importable(self) -> None:
        modules = (
            "services.task_ledger_service",
            "services.prompt_assembly_service",
            "runtime.cli_runtime",
            "runtime.runtime_router",
            "registry.skill_registry",
            "registry.agent_capability_registry",
            "execution.agent_team_executor",
            "utils.markdown_safety",
        )
        for module_name in modules:
            with self.subTest(module=module_name):
                importlib.import_module(module_name)


if __name__ == "__main__":
    unittest.main()
