from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import runtime_os_codemod


SCRIPT_PATH = Path(runtime_os_codemod.__file__).resolve()


class RuntimeOsCodemodTests(unittest.TestCase):
    def test_scan_paths_reports_rewrites_and_remaining_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "sample.py"
            target.write_text(
                "\n".join(
                    [
                        "from agents_os.runtime import ExecutionRuntime, RuntimeKernel",
                        "from multi_agents_os import WorkflowFactory",
                        "from agents_os.governance import ApprovalTicket",
                    ]
                ),
                encoding="utf-8",
            )

            summary = runtime_os_codemod.scan_paths([str(target)], write=False)

            self.assertEqual(summary.mode, "dry-run")
            self.assertEqual(summary.files_scanned, 1)
            self.assertEqual(summary.changed_files, 1)
            self.assertGreaterEqual(summary.changed_imports, 2)
            self.assertEqual(summary.remaining_files, 0)
            self.assertEqual(summary.reports[0].path, str(target))
            self.assertTrue(summary.reports[0].changed)
            self.assertEqual(summary.reports[0].remaining_legacy_hits, 0)
            self.assertIn("agents_os.runtime", target.read_text(encoding="utf-8"))

            rewritten = runtime_os_codemod.scan_paths([str(target)], write=True)
            self.assertEqual(rewritten.mode, "write")
            self.assertEqual(rewritten.changed_files, 1)

            updated = target.read_text(encoding="utf-8")
            self.assertIn("from runtime_os.agent_runtime import RuntimeKernel", updated)
            self.assertIn("from runtime_os.process_runtime import ExecutionRuntime", updated)
            self.assertIn("from runtime_os.process_runtime import WorkflowFactory", updated)
            self.assertIn("from runtime_os.process_runtime import ApprovalTicket", updated)
            self.assertNotIn("agents_os.runtime", updated)
            self.assertNotIn("multi_agents_os", updated)

    def test_cli_json_and_fail_on_remaining(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "sample.py"
            target.write_text(
                "\n".join(
                    [
                        "from agents_os.runtime import *",
                        "from agents_os.runtime import RuntimeKernel",
                    ]
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(target), "--json", "--fail-on-remaining"],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["mode"], "dry-run")
            self.assertEqual(payload["files_scanned"], 1)
            self.assertEqual(payload["changed_files"], 1)
            self.assertEqual(payload["remaining_files"], 1)
            self.assertEqual(payload["reports"][0]["remaining_legacy_hits"], 1)


if __name__ == "__main__":
    unittest.main()
