from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))


class RuntimeModuleLayoutTests(unittest.TestCase):
    def test_grouped_subpackages_are_importable(self) -> None:
        modules = (
                "butler_main.orchestrator.interfaces.ingress_service",
                "butler_main.orchestrator.interfaces.query_service",
                "butler_main.orchestrator.runtime_policy_adapter",
                "butler_main.orchestrator.runtime_paths",
                "butler_main.agents_os.runtime.request_intake",
                "butler_main.agents_os.execution.cli_runner",
                "butler_main.agents_os.execution.cursor_cli_support",
                "butler_main.agents_os.execution.runtime_policy",
                "butler_main.agents_os.execution.logging",
                "butler_main.agents_os.state.run_state_store",
                "butler_main.agents_os.state.trace_store",
                "butler_main.agents_os.skills.runtime_catalog",
                "butler_main.agents_os.skills.upstream_registry",
                "butler_main.agents_os.runtime.markdown_safety",
        )
        for module_name in modules:
            with self.subTest(module=module_name):
                importlib.import_module(module_name)

    def test_interfaces_package_does_not_eagerly_import_runner(self) -> None:
        module = importlib.import_module("butler_main.products.campaign_orchestrator.orchestrator.interfaces")
        init_path = Path(str(module.__file__ or ""))
        content = init_path.read_text(encoding="utf-8")

        self.assertNotIn("from .runner import", content)
        self.assertIn('"run_orchestrator_service"', content)


if __name__ == "__main__":
    unittest.main()
