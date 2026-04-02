from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.agents_os.execution import cli_runner, provider_failover  # noqa: E402


def _cfg(tmp: str) -> dict:
    root = Path(tmp)
    return {
        "agent_model": "gpt-5.4",
        "cli_runtime": {
            "active": "codex",
            "defaults": {
                "model": "gpt-5.4",
                "profile": "aixj",
                "speed": "",
                "config_overrides": [],
                "extra_args": [],
            },
            "providers": {
                "codex": {
                    "enabled": True,
                    "path": "codex",
                    "search": False,
                    "skip_git_repo_check": True,
                }
            },
            "provider_failover": {
                "enabled": True,
                "cli": "codex",
                "primary_profile": "aixj",
                "fallback_profile": "openai",
                "trip_timeout_seconds": 30,
                "cooldown_seconds": 1800,
                "probe_interval_seconds": 900,
                "probe_timeout_seconds": 30,
                "recovery_success_threshold": 2,
                "probe_model": "gpt-5.4",
                "probe_prompt": "Reply with exactly OK.",
                "trip_on_timeout": True,
                "trip_on_network_error": True,
                "trip_on_http_429": True,
                "trip_on_http_5xx": True,
                "state_path": str(root / "provider_failover_state.json"),
                "codex_config_path": str(root / "config.toml"),
            },
        },
    }


class CodexProviderFailoverTests(unittest.TestCase):
    def test_sync_system_codex_profile_updates_top_level_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            config_path = Path(cfg["cli_runtime"]["provider_failover"]["codex_config_path"])
            config_path.write_text(
                '\n'.join(
                    [
                        'profile = "openai"',
                        "",
                        'model = "gpt-5.4"',
                        "",
                        "[profiles.aixj]",
                        'model_provider = "aixj_vip"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            provider_failover.sync_system_codex_profile(cfg, {"active_profile": "aixj"})
            self.assertEqual(config_path.read_text(encoding="utf-8").splitlines()[0], 'profile = "aixj"')

    def test_sync_system_codex_profile_tolerates_invalid_utf8_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            config_path = Path(cfg["cli_runtime"]["provider_failover"]["codex_config_path"])
            config_path.write_bytes(b'profile = "openai"\nmodel = "\x80\x81"\n')
            provider_failover.sync_system_codex_profile(cfg, {"active_profile": "aixj"})
            content = config_path.read_text(encoding="utf-8")
            self.assertEqual(content.splitlines()[0], 'profile = "aixj"')
            self.assertIn('model = "', content)

    def test_run_prompt_trips_failover_on_primary_timeout_then_cursor_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            calls: list[dict[str, object]] = []

            def _fake_codex(prompt, workspace, timeout, cfg_obj, runtime_request, *, on_segment=None, on_event=None):
                calls.append(
                    {
                        "timeout": timeout,
                        "profile": runtime_request.get("profile"),
                        "active_profile": runtime_request.get("_provider_failover_active_profile"),
                    }
                )
                return "执行超时", False

            with mock.patch.object(cli_runner, "_run_codex", side_effect=_fake_codex), \
                 mock.patch.object(cli_runner, "_run_cursor", return_value=("cursor ok", True)), \
                 mock.patch.object(cli_runner, "cli_provider_available", lambda name, c: name in {"codex", "cursor"}):
                out, ok = cli_runner.run_prompt("hello", tmp, 120, cfg, {"cli": "codex"})

            self.assertTrue(ok)
            self.assertEqual(out, "cursor ok")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["profile"], "")
            self.assertEqual(calls[0]["active_profile"], "aixj")
            self.assertEqual(calls[0]["timeout"], 30)
            state = provider_failover.read_state(cfg)
            self.assertEqual(state["active_profile"], "openai")
            self.assertEqual(state["circuit_state"], "open")
            config_path = Path(cfg["cli_runtime"]["provider_failover"]["codex_config_path"])
            self.assertEqual(config_path.read_text(encoding="utf-8").splitlines()[0], 'profile = "openai"')

    def test_explicit_profile_bypasses_failover_management(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            calls: list[dict[str, object]] = []

            def _fake_codex(prompt, workspace, timeout, cfg_obj, runtime_request, *, on_segment=None, on_event=None):
                calls.append({"timeout": timeout, "profile": runtime_request.get("profile")})
                return "执行超时", False

            with mock.patch.object(cli_runner, "_run_codex", side_effect=_fake_codex), \
                 mock.patch.object(cli_runner, "cli_provider_available", return_value=True), \
                 mock.patch.object(cli_runner, "_run_cursor", return_value=("执行超时", False)):
                out, ok = cli_runner.run_prompt("hello", tmp, 120, cfg, {"cli": "codex", "profile": "aixj"})

            self.assertFalse(ok)
            self.assertEqual(out, "执行超时")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["profile"], "aixj")
            self.assertEqual(calls[0]["timeout"], 120)
            state = provider_failover.read_state(cfg)
            self.assertEqual(state["active_profile"], "aixj")
            self.assertEqual(state["circuit_state"], "closed")

    def test_disable_runtime_fallback_keeps_failed_codex_receipt_and_skips_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            with mock.patch.object(cli_runner, "_run_codex", return_value=("执行超时", False)) as mocked_codex, \
                 mock.patch.object(cli_runner, "_run_cursor", return_value=("cursor should not run", True)) as mocked_cursor, \
                 mock.patch.object(cli_runner, "cli_provider_available", lambda name, c: name in {"codex", "cursor"}):
                receipt = cli_runner.run_prompt_receipt(
                    "hello",
                    tmp,
                    120,
                    cfg,
                    {"cli": "codex", "_disable_runtime_fallback": True},
                )
            self.assertEqual(mocked_codex.call_count, 1)
            self.assertEqual(mocked_cursor.call_count, 0)
            self.assertEqual(receipt.status, "failed")
            self.assertEqual(receipt.metadata["failure_class"], "timeout")
            state = provider_failover.read_state(cfg)
            self.assertEqual(state["active_profile"], "openai")
            self.assertEqual(state["circuit_state"], "open")

    def test_resolved_default_profile_is_not_treated_as_explicit_for_failover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            provider_failover.update_state(
                cfg,
                lambda state, settings: {
                    **state,
                    "active_profile": settings["fallback_profile"],
                    "circuit_state": "open",
                },
            )
            initial = cli_runner.resolve_runtime_request(cfg, {"cli": "codex"})
            self.assertEqual(initial["profile"], "")
            self.assertFalse(initial["_profile_explicit"])
            calls: list[dict[str, str]] = []

            def _fake_codex(prompt, workspace, timeout, cfg_obj, runtime_request, *, on_segment=None, on_event=None):
                calls.append(
                    {
                        "profile": str(runtime_request.get("profile") or ""),
                        "active_profile": str(runtime_request.get("_provider_failover_active_profile") or ""),
                    }
                )
                return "ok", True

            with mock.patch.object(cli_runner, "_run_codex", side_effect=_fake_codex):
                out, ok = cli_runner.run_prompt("hello", tmp, 120, cfg, initial)

            self.assertTrue(ok)
            self.assertEqual(out, "ok")
            self.assertEqual(calls, [{"profile": "", "active_profile": "openai"}])

    def test_current_runtime_profile_reads_failover_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            provider_failover.update_state(
                cfg,
                lambda state, settings: {
                    **state,
                    "active_profile": settings["fallback_profile"],
                    "circuit_state": "open",
                },
            )
            self.assertEqual(cli_runner.current_runtime_profile(cfg, "codex"), "openai")

    def test_reconcile_failover_requires_two_successes_to_recover_primary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            provider_failover.update_state(
                cfg,
                lambda state, settings: {
                    **state,
                    "active_profile": settings["fallback_profile"],
                    "circuit_state": "open",
                },
            )
            with mock.patch.object(provider_failover, "run_primary_probe", return_value=(True, "")):
                first = provider_failover.reconcile_failover(cfg, force_probe=True)
                second = provider_failover.reconcile_failover(cfg, force_probe=True)
            self.assertEqual(first["active_profile"], "openai")
            self.assertEqual(first["circuit_state"], "probing")
            self.assertEqual(first["consecutive_probe_successes"], 1)
            self.assertEqual(second["active_profile"], "aixj")
            self.assertEqual(second["circuit_state"], "closed")
            self.assertEqual(second["consecutive_probe_successes"], 0)

    def test_reconcile_failover_without_probe_only_syncs_existing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            provider_failover.update_state(
                cfg,
                lambda state, settings: {
                    **state,
                    "active_profile": settings["fallback_profile"],
                    "circuit_state": "open",
                    "last_probe_at_utc": "2026-03-29T00:00:00Z",
                },
            )
            with mock.patch.object(provider_failover, "run_primary_probe", side_effect=AssertionError("should not probe")):
                state = provider_failover.reconcile_failover(cfg, force_probe=False)
            self.assertEqual(state["active_profile"], "openai")
            self.assertEqual(state["circuit_state"], "open")


if __name__ == "__main__":
    unittest.main()
