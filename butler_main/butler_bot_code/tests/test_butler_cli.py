from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
for candidate in (REPO_ROOT, BUTLER_MAIN_DIR):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from butler_main import butler_cli  # noqa: E402


class ButlerCliTests(unittest.TestCase):
    def test_no_args_defaults_to_chat_cli(self) -> None:
        with mock.patch.object(butler_cli, "_chat_main", return_value=0) as mocked_chat:
            rc = butler_cli.main([])
        self.assertEqual(rc, 0)
        mocked_chat.assert_called_once_with([])

    def test_legacy_workflow_aliases_fail_with_migration_hint(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(sys, "stdout", stdout), mock.patch.object(sys, "stderr", stderr):
            rc = butler_cli.main(["-workflow", "list", "--limit", "3"])
        self.assertNotEqual(rc, 0)
        combined = f"{stdout.getvalue()}\n{stderr.getvalue()}"
        self.assertIn("butler-flow", combined)

    def test_manager_status_dispatch_preserves_args(self) -> None:
        with mock.patch.object(butler_cli, "_manager_main", return_value=0) as mocked_manager:
            rc = butler_cli.main(["status", "butler_bot"])
        self.assertEqual(rc, 0)
        mocked_manager.assert_called_once_with(["status", "butler_bot"])

    def test_help_prints_root_help(self) -> None:
        stream = io.StringIO()
        with mock.patch.object(sys, "stdout", stream):
            rc = butler_cli.main(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("Butler CLI", stream.getvalue())
        self.assertNotIn("-workflow", stream.getvalue())
        self.assertNotIn("codex-guard", stream.getvalue())


class ButlerMainEntryTests(unittest.TestCase):
    def test_python_module_entry_delegates_to_butler_flow(self) -> None:
        from butler_main import __main__ as butler_main_entry

        with mock.patch.object(butler_main_entry, "butler_flow_main", return_value=0) as mocked_flow:
            rc = butler_main_entry.main(["--help"])
        self.assertEqual(rc, 0)
        mocked_flow.assert_called_once_with(["--help"])


if __name__ == "__main__":
    unittest.main()
