from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from butler_main.chat.memory_runtime import ChatBackgroundServicesRuntime


class _FakeTaskRunner:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def submit(self, target, /, *args, name: str = "task", daemon: bool = True, **kwargs):
        self.calls.append(
            {
                "target": target,
                "args": args,
                "kwargs": kwargs,
                "name": name,
                "daemon": daemon,
            }
        )
        return None


class _FakeBackgroundManager:
    def __init__(self) -> None:
        self._maintenance_started = False
        self._maintenance_lock = threading.Lock()
        self._main_process_state_started = False
        self.calls: list[tuple] = []

    def _recover_pending_recent_entries_on_startup(self, workspace: str) -> None:
        self.calls.append(("recover", workspace))

    def _write_main_process_state(self, workspace: str, state: str = "running") -> None:
        self.calls.append(("write_state", workspace, state))

    def _register_main_process_exit_hooks(self, workspace: str) -> None:
        self.calls.append(("register_exit_hooks", workspace))

    def _main_process_state_loop(self, workspace: str) -> None:
        self.calls.append(("main_process_loop", workspace))

    def _maintenance_loop(self, workspace: str, timeout: int, model: str) -> None:
        self.calls.append(("maintenance_loop", workspace, timeout, model))


class ChatBackgroundServicesRuntimeTests(unittest.TestCase):
    def test_runtime_starts_background_slices_only_once(self) -> None:
        manager = _FakeBackgroundManager()
        runner = _FakeTaskRunner()
        runtime = ChatBackgroundServicesRuntime(
            manager=manager,
            config_provider=lambda: {
                "workspace_root": "C:/workspace",
                "agent_timeout": 60,
                "agent_model": "gpt-5.4",
            },
            task_runner=runner,
        )

        runtime.start_background_services()
        runtime.start_background_services()

        self.assertTrue(manager._maintenance_started)
        self.assertTrue(manager._main_process_state_started)
        self.assertEqual(
            [item["name"] for item in runner.calls],
            [
                "butler-main-state-writer",
                "memory-maintenance-scheduler",
            ],
        )
        self.assertIn(("recover", "C:/workspace"), manager.calls)
        self.assertIn(("write_state", "C:/workspace", "running"), manager.calls)
        self.assertIn(("register_exit_hooks", "C:/workspace"), manager.calls)
        self.assertNotIn(("self_mind_loop",), manager.calls)
        self.assertNotIn(("self_mind_listener",), manager.calls)

    def test_runtime_starts_main_state_writer_without_legacy_watchdog_concepts(self) -> None:
        manager = _FakeBackgroundManager()
        runner = _FakeTaskRunner()
        runtime = ChatBackgroundServicesRuntime(
            manager=manager,
            config_provider=lambda: {
                "workspace_root": "C:/workspace",
                "agent_timeout": 30,
                "agent_model": "auto",
            },
            task_runner=runner,
        )

        runtime.start_background_services()

        self.assertTrue(manager._maintenance_started)
        self.assertEqual(
            [item["name"] for item in runner.calls],
            [
                "butler-main-state-writer",
                "memory-maintenance-scheduler",
            ],
        )


if __name__ == "__main__":
    unittest.main()
