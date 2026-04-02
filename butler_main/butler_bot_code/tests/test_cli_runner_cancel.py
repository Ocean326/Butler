import sys
import unittest
from pathlib import Path
from unittest import mock


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.agents_os.execution import cli_runner


class _FakeProc:
    def __init__(self) -> None:
        self.pid = 12345
        self.terminate_calls = 0
        self.kill_calls = 0

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1


class CliRunnerCancelTests(unittest.TestCase):
    def test_cancel_active_runs_matches_session_and_terminates_process(self) -> None:
        proc = _FakeProc()
        token = cli_runner._register_active_process(proc, {"session_id": "chat_terminate_1", "actor_id": "ou_1"})
        try:
            with mock.patch.object(cli_runner.subprocess, "run") as taskkill_run:
                result = cli_runner.cancel_active_runs(session_id="chat_terminate_1")
        finally:
            cli_runner._unregister_active_process(token)

        self.assertEqual(result["cancelled_count"], 1)
        taskkill_run.assert_called_once()
        self.assertGreaterEqual(proc.terminate_calls + proc.kill_calls, 1)

    def test_cancel_active_runs_prefers_request_id_for_precise_match(self) -> None:
        proc_a = _FakeProc()
        proc_b = _FakeProc()
        token_a = cli_runner._register_active_process(proc_a, {"request_id": "req-a", "actor_id": "ou_same"})
        token_b = cli_runner._register_active_process(proc_b, {"request_id": "req-b", "actor_id": "ou_same"})
        try:
            with mock.patch.object(cli_runner.subprocess, "run") as taskkill_run:
                result = cli_runner.cancel_active_runs(request_id="req-b", actor_id="ou_same")
        finally:
            cli_runner._unregister_active_process(token_a)
            cli_runner._unregister_active_process(token_b)

        self.assertEqual(result["cancelled_count"], 1)
        self.assertEqual(taskkill_run.call_count, 1)
        self.assertEqual(proc_a.terminate_calls + proc_a.kill_calls, 0)
        self.assertGreaterEqual(proc_b.terminate_calls + proc_b.kill_calls, 1)


if __name__ == "__main__":
    unittest.main()
