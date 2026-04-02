from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_TOOL = REPO_ROOT / "tools" / "orchestrator_layer_audit.py"


class OrchestratorLayerAuditToolTests(unittest.TestCase):
    def test_audit_tool_reports_expected_slots(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(AUDIT_TOOL)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)

        self.assertIn("application_dir_exists", payload)
        self.assertIn("interfaces_dir_exists", payload)
        self.assertIn("application_modules", payload)
        self.assertIn("interface_modules", payload)
        self.assertIn("forbidden_interface_import_violations", payload)

        application_modules = {item["module"]: item for item in payload["application_modules"]}
        interface_modules = {item["module"]: item for item in payload["interface_modules"]}

        self.assertIn("service", application_modules)
        self.assertIn("query_service", interface_modules)
        self.assertIn("ingress_service", interface_modules)
        self.assertIn("mission_orchestrator", interface_modules)
        self.assertIn("observe", interface_modules)
        self.assertIn("runner", interface_modules)

        self.assertTrue(application_modules["service"]["root_exists"])
        self.assertIsInstance(payload["forbidden_interface_import_violations"], list)


if __name__ == "__main__":
    unittest.main()
