import ast
from pathlib import Path
import sys
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from standards.code_health_manifest import DEFAULT_CODE_HEALTH_MANIFEST  # noqa: E402


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(str(alias.name or "").split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(str(node.module).split(".", 1)[0])
    return modules


class CodeHealthTests(unittest.TestCase):
    def test_forbidden_import_rules_hold(self) -> None:
        for rule in DEFAULT_CODE_HEALTH_MANIFEST.forbidden_import_rules:
            for path in MODULE_DIR.glob(rule.relative_glob):
                if path.name == "__init__.py":
                    continue
                imported = _imported_modules(path)
                for forbidden in rule.forbidden_modules:
                    with self.subTest(path=path.name, forbidden=forbidden):
                        self.assertNotIn(forbidden, imported, msg=rule.rationale)

    def test_file_line_budgets_hold(self) -> None:
        for budget in DEFAULT_CODE_HEALTH_MANIFEST.file_line_budgets:
            path = MODULE_DIR / budget.relative_path
            with self.subTest(path=budget.relative_path):
                self.assertTrue(path.exists())
                lines = len(path.read_text(encoding="utf-8").splitlines())
                self.assertLessEqual(lines, budget.max_lines, msg=budget.rationale)

    def test_health_manifest_principles_exist(self) -> None:
        self.assertGreaterEqual(len(DEFAULT_CODE_HEALTH_MANIFEST.maintenance_principles), 4)
        self.assertTrue(any("可自动检查" in item for item in DEFAULT_CODE_HEALTH_MANIFEST.maintenance_principles))


if __name__ == "__main__":
    unittest.main()
