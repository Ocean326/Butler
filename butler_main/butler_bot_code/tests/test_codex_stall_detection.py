from __future__ import annotations

import sys
import unittest
from pathlib import Path

BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.execution import cli_runner


class CodexStallDetectionTests(unittest.TestCase):
    def test_abort_blob_detects_final_reconnect_ratio(self) -> None:
        cfg = {"cli_runtime": {"codex_stall_detection": {"enabled": True}}}
        stall = cli_runner._codex_stall_settings(cfg)
        r = cli_runner._codex_stall_abort_blob("prefix Reconnecting... 5 / 5 suffix", stall)
        self.assertIsNotNone(r)
        self.assertIn("5/5", r)

    def test_abort_blob_ignores_in_progress_ratio(self) -> None:
        cfg = {"cli_runtime": {"codex_stall_detection": {"enabled": True}}}
        stall = cli_runner._codex_stall_settings(cfg)
        self.assertIsNone(cli_runner._codex_stall_abort_blob("Reconnecting... 2/5 ok", stall))

    def test_abort_blob_child_process_timeout_message(self) -> None:
        cfg = {"cli_runtime": {"codex_stall_detection": {"enabled": True}}}
        stall = cli_runner._codex_stall_settings(cfg)
        r = cli_runner._codex_stall_abort_blob("Reconnecting... 3/5 (timeout waiting for child process to exit)", stall)
        self.assertIsNotNone(r)
        self.assertIn("child process", r.lower())

    def test_force_failed_when_exhausted_in_final_output(self) -> None:
        cfg = {"cli_runtime": {"codex_stall_detection": {"enabled": True}}}
        stall = cli_runner._codex_stall_settings(cfg)
        out = "some text\nReconnecting... 5/5\n"
        self.assertTrue(cli_runner._codex_output_force_failed(out, stall))


if __name__ == "__main__":
    unittest.main()
