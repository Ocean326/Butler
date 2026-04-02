from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.execution import cli_runner
from agents_os.execution import codex_cursor_switchover


def _cfg(tmp: str, *, cooldown_seconds: int = 3600) -> dict:
    return {
        "cli_runtime": {
            "active": "cursor",
            "codex_cursor_switchover": {
                "enabled": True,
                "cooldown_seconds": cooldown_seconds,
                "probes_per_hour": 2,
                "state_path": str(Path(tmp) / "switchover.json"),
            },
            "providers": {
                "cursor": {"enabled": True},
                "codex": {"enabled": True},
                "claude": {"enabled": False},
            },
        },
    }


class CodexCursorSwitchoverTests(unittest.TestCase):
    def test_codex_failure_triggers_one_hour_cursor_preference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            t0 = 1_000_000.0
            clock = {"v": t0}

            def fake_time() -> float:
                return float(clock["v"])

            with mock.patch.object(codex_cursor_switchover.time, "time", side_effect=fake_time):
                codex_cursor_switchover.record_codex_primary_failure(cfg)
                skip, _ = codex_cursor_switchover.resolve_codex_first_switchover(cfg)
                self.assertTrue(skip)
                clock["v"] = t0 + 3599
                skip2, _ = codex_cursor_switchover.resolve_codex_first_switchover(cfg)
                self.assertTrue(skip2)
                clock["v"] = t0 + 3600
                skip3, count = codex_cursor_switchover.resolve_codex_first_switchover(cfg)
            self.assertFalse(skip3)
            self.assertTrue(count)

    def test_two_probes_per_hour_then_skip_until_next_hour(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp, cooldown_seconds=60)
            hour = 500_000
            t0 = hour * 3600 + 50.0
            clock = {"v": t0}

            def fake_time() -> float:
                return float(clock["v"])

            with mock.patch.object(codex_cursor_switchover.time, "time", side_effect=fake_time):
                codex_cursor_switchover.record_codex_primary_failure(cfg)
                clock["v"] = t0 + 70.0
                skip1, c1 = codex_cursor_switchover.resolve_codex_first_switchover(cfg)
                self.assertFalse(skip1)
                self.assertTrue(c1)
                codex_cursor_switchover.note_probe_attempt(cfg)
                clock["v"] = t0 + 71.0
                skip2, c2 = codex_cursor_switchover.resolve_codex_first_switchover(cfg)
                self.assertFalse(skip2)
                self.assertTrue(c2)
                codex_cursor_switchover.note_probe_attempt(cfg)
                clock["v"] = t0 + 72.0
                skip3, c3 = codex_cursor_switchover.resolve_codex_first_switchover(cfg)
                self.assertTrue(skip3)
                self.assertFalse(c3)
                clock["v"] = (hour + 1) * 3600 + 5.0
                skip4, c4 = codex_cursor_switchover.resolve_codex_first_switchover(cfg)
            self.assertFalse(skip4)
            self.assertTrue(c4)

    def test_codex_primary_success_clears_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            codex_cursor_switchover.record_codex_primary_failure(cfg)
            codex_cursor_switchover.record_codex_primary_success(cfg)
            skip, count = codex_cursor_switchover.resolve_codex_first_switchover(cfg)
            self.assertFalse(skip)
            self.assertFalse(count)

    def test_run_prompt_records_failure_and_skips_codex_first_in_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            state_path = Path(cfg["cli_runtime"]["codex_cursor_switchover"]["state_path"])
            with mock.patch.object(cli_runner, "_run_codex", return_value=("bad", False)), \
                 mock.patch.object(cli_runner, "_run_cursor", return_value=("ok", True)), \
                 mock.patch.object(cli_runner, "cli_provider_available", return_value=True):
                cli_runner.run_prompt("x", str(tmp), 30, cfg, {"cli": "codex"})
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("phase"), "cooldown")
            with mock.patch.object(cli_runner, "cli_provider_available", side_effect=lambda name, _: name in {"codex", "cursor"}):
                resolved = cli_runner.resolve_runtime_request(cfg, {})
            self.assertEqual(resolved.get("cli"), "cursor")

    def test_run_prompt_receipt_disable_fallback_still_records_codex_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            state_path = Path(cfg["cli_runtime"]["codex_cursor_switchover"]["state_path"])
            with mock.patch.object(cli_runner, "_run_codex", return_value=("bad", False)), \
                 mock.patch.object(cli_runner, "_run_cursor", return_value=("ok", True)), \
                 mock.patch.object(cli_runner, "cli_provider_available", return_value=True):
                receipt = cli_runner.run_prompt_receipt(
                    "x",
                    str(tmp),
                    30,
                    cfg,
                    {"cli": "codex", "_disable_runtime_fallback": True},
                )
            self.assertEqual(receipt.status, "failed")
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("phase"), "cooldown")


if __name__ == "__main__":
    unittest.main()
