from pathlib import Path
import sys
import tempfile
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from standards.architecture_manifest import DEFAULT_ARCHITECTURE_MANIFEST  # noqa: E402
from standards.code_health_manifest import DEFAULT_CODE_HEALTH_MANIFEST  # noqa: E402
from standards.protocol_registry import get_protocol_registry  # noqa: E402


class EngineeringStandardsTests(unittest.TestCase):
    def test_architecture_manifest_tracks_root_runtime_modules_and_standards_package(self) -> None:
        self.assertIn("memory_manager.py", DEFAULT_ARCHITECTURE_MANIFEST.core_runtime_root_modules)
        self.assertIn("standards", DEFAULT_ARCHITECTURE_MANIFEST.grouped_subpackages)
        self.assertTrue(any("任务状态真源" in item for item in DEFAULT_ARCHITECTURE_MANIFEST.invariants))

    def test_protocol_registry_loads_long_term_protocol_documents(self) -> None:
        registry = get_protocol_registry()
        task_protocol = registry.get("task_collaboration")
        self.assertIsNotNone(task_protocol)
        self.assertIn("统一任务体系", task_protocol.text)
        self.assertIn("task_ledger.json", task_protocol.text)

    def test_code_health_manifest_tracks_dependency_and_budget_rules(self) -> None:
        self.assertTrue(DEFAULT_CODE_HEALTH_MANIFEST.forbidden_import_rules)
        self.assertTrue(DEFAULT_CODE_HEALTH_MANIFEST.file_line_budgets)
        self.assertTrue(any("memory_manager.py" in item.relative_path for item in DEFAULT_CODE_HEALTH_MANIFEST.file_line_budgets))


if __name__ == "__main__":
    unittest.main()
