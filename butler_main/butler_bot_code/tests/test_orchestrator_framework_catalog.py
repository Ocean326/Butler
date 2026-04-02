from __future__ import annotations

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
    FrameworkCatalog,
    FrameworkCatalogEntry,
    get_builtin_framework_catalog_entry,
    load_builtin_framework_catalog,
)


class OrchestratorFrameworkCatalogTests(unittest.TestCase):
    def test_builtin_framework_catalog_loads_required_entries(self) -> None:
        catalog = load_builtin_framework_catalog()

        self.assertIsInstance(catalog, FrameworkCatalog)
        self.assertEqual(
            set(catalog.list_framework_ids()),
            {
                "superpowers",
                "gstack",
                "openfang",
                "langgraph",
                "openai_agents_sdk",
                "autogen",
                "crewai",
                "metagpt",
                "openhands",
                "temporal",
            },
        )

        openfang = catalog.require_entry("openfang")
        self.assertIsInstance(openfang, FrameworkCatalogEntry)
        self.assertEqual(openfang.display_name, "OpenFang")
        self.assertEqual(openfang.source_kind, "agent_os")
        self.assertIn("Execution Kernel Plane", openfang.focus_layers)
        self.assertTrue(any("product shell" in item for item in openfang.non_goals))

    def test_catalog_entry_can_be_loaded_via_package_api(self) -> None:
        entry = get_builtin_framework_catalog_entry("superpowers")

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.framework_id, "superpowers")
        self.assertIn("hard review and approval gates", entry.strengths)

    def test_catalog_can_filter_by_focus_layer_and_source_kind(self) -> None:
        catalog = load_builtin_framework_catalog()

        execution_layer = catalog.find_by_focus_layer("Execution Kernel Plane")
        workflow_runtime = catalog.find_by_source_kind("workflow_runtime")

        self.assertTrue(any(item.framework_id == "openfang" for item in execution_layer))
        self.assertTrue(any(item.framework_id == "temporal" for item in execution_layer))
        self.assertEqual([item.framework_id for item in workflow_runtime], ["langgraph"])


if __name__ == "__main__":
    unittest.main()
