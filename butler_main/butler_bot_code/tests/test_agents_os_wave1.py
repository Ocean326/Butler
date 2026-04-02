from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.context import FileMemoryBackend, MemoryQuery
from agents_os.execution import cli_runner
from agents_os.state import FileRuntimeStateStore, FileTraceStore


class AgentsOsWave1Tests(unittest.TestCase):
    def test_default_active_cursor_resolves_codex_first_when_available(self) -> None:
        cfg = {
            "cli_runtime": {
                "codex_cursor_switchover": {"enabled": False},
                "providers": {
                    "cursor": {"enabled": True},
                    "codex": {"enabled": True},
                    "claude": {"enabled": False},
                },
            }
        }
        with mock.patch.object(cli_runner, "cli_provider_available", side_effect=lambda name, _: name in {"codex", "cursor"}):
            settings = cli_runner.get_cli_runtime_settings(cfg)
            available = cli_runner.available_cli_modes(cfg)
            resolved = cli_runner.resolve_runtime_request(cfg, {})
        self.assertEqual(settings["active"], "cursor")
        self.assertEqual(available, ["codex", "cursor"])
        self.assertEqual(resolved["cli"], "codex")

    def test_cli_alias_supports_claude_cli(self) -> None:
        cfg = {
            "cli_runtime": {
                "active": "claude-cli",
                "providers": {
                    "cursor": {"enabled": False},
                    "codex": {"enabled": False},
                    "claude": {"enabled": True},
                },
            }
        }
        with mock.patch.object(cli_runner, "cli_provider_available", side_effect=lambda name, _: name == "claude"):
            settings = cli_runner.get_cli_runtime_settings(cfg)
            available = cli_runner.available_cli_modes(cfg)
        self.assertEqual(settings["active"], "claude")
        self.assertEqual(available, ["claude"])

    def test_codex_any_failure_falls_back_to_cursor_including_502(self) -> None:
        cfg = {
            "cli_runtime": {
                "active": "codex",
                "providers": {
                    "cursor": {"enabled": True},
                    "codex": {"enabled": True},
                    "claude": {"enabled": False},
                },
            }
        }
        bad_gateway = (
            "■ unexpected status 502 Bad Gateway: error code: 502, "
            "url: https://aixj.vip/responses, cf-ray: 9e45a77a8f50f5b9-AMS"
        )
        with mock.patch.object(cli_runner, "_run_codex", return_value=(bad_gateway, False)) as mocked_codex, \
             mock.patch.object(cli_runner, "_run_cursor", return_value=("cursor ok", True)) as mocked_cursor, \
             mock.patch.object(cli_runner, "cli_provider_available", return_value=True):
            out, ok = cli_runner.run_prompt("hello", "c:/workspace", 30, cfg, {"cli": "codex"})
        self.assertTrue(ok)
        self.assertEqual(out, "cursor ok")
        self.assertEqual(mocked_codex.call_count, 1)
        self.assertEqual(mocked_cursor.call_count, 1)

    def test_codex_user_cancel_falls_back_to_cursor_continue(self) -> None:
        cfg = {
            "cli_runtime": {
                "active": "codex",
                "cursor_continue_after_codex_cancel": {"enabled": True},
                "providers": {
                    "cursor": {"enabled": True},
                    "codex": {"enabled": True},
                    "claude": {"enabled": False},
                },
            }
        }
        with mock.patch.object(cli_runner, "_run_codex", return_value=("已终止当前执行。", False)) as mocked_codex, \
             mock.patch.object(cli_runner, "_run_cursor", return_value=("cursor continued", True)) as mocked_cursor, \
             mock.patch.object(cli_runner, "cli_provider_available", return_value=True):
            out, ok = cli_runner.run_prompt("hello", "c:/workspace", 30, cfg, {"cli": "codex"})
        self.assertTrue(ok)
        self.assertEqual(out, "cursor continued")
        self.assertEqual(mocked_codex.call_count, 1)
        self.assertEqual(mocked_cursor.call_count, 1)
        cursor_prompt = mocked_cursor.call_args[0][0]
        self.assertIn("用户终止", cursor_prompt)
        self.assertIn("hello", cursor_prompt)

    def test_codex_user_cancel_respects_disable_flag(self) -> None:
        cfg = {
            "cli_runtime": {
                "active": "codex",
                "cursor_continue_after_codex_cancel": {"enabled": False},
                "providers": {
                    "cursor": {"enabled": True},
                    "codex": {"enabled": True},
                    "claude": {"enabled": False},
                },
            }
        }
        with mock.patch.object(cli_runner, "_run_codex", return_value=("已终止当前执行。", False)), \
             mock.patch.object(cli_runner, "_run_cursor", return_value=("should not run", True)), \
             mock.patch.object(cli_runner, "cli_provider_available", return_value=True):
            out, ok = cli_runner.run_prompt("hello", "c:/workspace", 30, cfg, {"cli": "codex"})
        self.assertFalse(ok)
        self.assertEqual(out, "已终止当前执行。")

    def test_runtime_fallback_prefers_codex_before_claude(self) -> None:
        cfg = {
            "cli_runtime": {
                "active": "cursor",
                "providers": {
                    "cursor": {"enabled": True},
                    "codex": {"enabled": True},
                    "claude": {"enabled": True},
                },
            }
        }
        with mock.patch.object(cli_runner, "_run_cursor", return_value=("S: [unavailable]", False)) as mocked_cursor, \
             mock.patch.object(cli_runner, "_run_codex", return_value=("codex ok", True)) as mocked_codex, \
             mock.patch.object(cli_runner, "_run_claude", return_value=("claude ok", True)) as mocked_claude, \
             mock.patch.object(cli_runner, "cli_provider_available", return_value=True):
            out, ok = cli_runner.run_prompt("hello", "c:/workspace", 30, cfg, {"cli": "cursor"})
        self.assertTrue(ok)
        self.assertEqual(out, "codex ok")
        self.assertEqual(mocked_cursor.call_count, 1)
        self.assertEqual(mocked_codex.call_count, 1)
        self.assertEqual(mocked_claude.call_count, 0)

    def test_run_prompt_receipt_exposes_stable_cli_metadata_fields(self) -> None:
        cfg = {
            "cli_runtime": {
                "active": "codex",
                "providers": {
                    "cursor": {"enabled": False},
                    "codex": {"enabled": True},
                    "claude": {"enabled": False},
                },
            }
        }
        with mock.patch.object(
            cli_runner,
            "_run_codex",
            return_value={
                "provider": "codex",
                "output": "ok",
                "ok": True,
                "returncode": 0,
                "usage": {"input_tokens": 11, "output_tokens": 7},
                "external_session": {"provider": "codex", "thread_id": "thread-1", "resume_capable": True},
                "command_events": [{"kind": "command", "text": "pytest -q", "status": "completed"}],
            },
        ), mock.patch.object(cli_runner, "cli_provider_available", return_value=True):
            receipt = cli_runner.run_prompt_receipt(
                "hello",
                "c:/workspace",
                30,
                cfg,
                {"cli": "codex", "_disable_runtime_fallback": True},
            )
        self.assertEqual(receipt.metadata["provider_returncode"], 0)
        self.assertEqual(receipt.metadata["external_session"]["thread_id"], "thread-1")
        self.assertEqual(receipt.metadata["cli_events"]["usage"]["input_tokens"], 11)
        self.assertEqual(receipt.metadata["cli_events"]["command_events"][0]["text"], "pytest -q")

    def test_run_prompt_receipt_preserves_durable_resume_metadata(self) -> None:
        cfg = {
            "cli_runtime": {
                "active": "codex",
                "providers": {
                    "cursor": {"enabled": False},
                    "codex": {"enabled": True},
                    "claude": {"enabled": False},
                },
            }
        }
        with mock.patch.object(
            cli_runner,
            "_run_codex",
            return_value={
                "provider": "codex",
                "output": "ok",
                "ok": True,
                "returncode": 0,
                "external_session": {
                    "provider": "codex",
                    "thread_id": "thread-9",
                    "durable_resume_id": "resume-9",
                    "resume_capable": True,
                },
            },
        ), mock.patch.object(cli_runner, "cli_provider_available", return_value=True):
            receipt = cli_runner.run_prompt_receipt(
                "hello",
                "c:/workspace",
                30,
                cfg,
                {"cli": "codex", "_disable_runtime_fallback": True},
            )
        session = receipt.metadata["external_session"]
        self.assertEqual(session["thread_id"], "thread-9")
        self.assertEqual(session["durable_resume_id"], "resume-9")
        self.assertNotEqual(session["thread_id"], session["durable_resume_id"])

    def test_file_runtime_state_store_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = FileRuntimeStateStore(Path(tmp_dir) / "run")
            store.write_pid(4321)
            store.write_run_state(run_id="run_demo", state="running", phase="planning", pid=4321, note="working")
            store.write_watchdog_state(state="healthy", pid=4321, note="ok")
            snapshot = store.status_snapshot(
                enabled=True,
                stale_seconds=60,
                tracked_pid=4321,
                pid_probe=lambda pid: {"alive": pid == 4321, "matches": True},
            )
        self.assertEqual(snapshot.config_state, "enabled")
        self.assertEqual(snapshot.process_state, "running")
        self.assertEqual(snapshot.run_id, "run_demo")
        self.assertEqual(snapshot.phase, "planning")

    def test_file_trace_store_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = FileTraceStore(Path(tmp_dir) / "traces")
            run_id = store.start_run(metadata={"source": "wave1"})
            store.append_event(run_id, phase="plan", event_type="fallback.provider", payload={"from": "cursor", "to": "codex"})
            store.append_event(run_id, phase="exec", event_type="retry.worker", payload={"count": 1})
            store.record_tasks(run_id, selected=["t1"], rejected=["t2", "t3"])
            summary = store.summarize(run_id)
            compacted = store.compact_run(run_id)
        self.assertEqual(summary.selected_task_ids, ["t1"])
        self.assertEqual(summary.rejected_task_ids, ["t2", "t3"])
        self.assertEqual(summary.fallback_count, 1)
        self.assertEqual(summary.retry_count, 1)
        self.assertGreaterEqual(compacted["event_count_before_compact"], 2)

    def test_file_memory_backend_protocol_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            backend = FileMemoryBackend(Path(tmp_dir) / "memory_backend")
            backend.episodic.append({"scope": "recent", "record_type": "event", "text": "hello wave1"})
            backend.semantic.upsert("entry_1", {"scope": "recent", "record_type": "semantic", "summary": "wave1 summary"})
            backend.self_model.upsert_thread("thread_1", {"scope": "self", "title": "reflection"})
            backend.prospective.upsert_intention("goal_1", {"scope": "plan", "goal": "extract runtime"})
            episodic_rows = backend.episodic.query(MemoryQuery(scope="recent", query_text="wave1"))
            semantic_row = backend.semantic.get("entry_1")
            self_rows = backend.self_model.query(MemoryQuery(scope="self", limit=5))
            prospective_rows = backend.prospective.query(MemoryQuery(scope="plan", limit=5))
        self.assertEqual(len(episodic_rows), 1)
        self.assertEqual(semantic_row["summary"], "wave1 summary")
        self.assertEqual(self_rows[0]["thread_id"], "thread_1")
        self.assertEqual(prospective_rows[0]["intention_id"], "goal_1")


if __name__ == "__main__":
    unittest.main()
