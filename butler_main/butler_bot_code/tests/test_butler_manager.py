from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.butler_bot_code import manager


_SERVICE_SCRIPT = """\
from __future__ import annotations

import argparse
from pathlib import Path
import signal
import time

running = True


def _stop(*_args):
    global running
    running = False


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

parser = argparse.ArgumentParser()
parser.add_argument("--config", default="")
parser.add_argument("--ready-file", default="")
args, _unknown = parser.parse_known_args()
if args.ready_file:
    Path(args.ready_file).write_text(args.config or "ready", encoding="utf-8")
while running:
    time.sleep(0.1)
"""


class ButlerManagerTests(unittest.TestCase):
    def test_load_registry_resolves_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body_dir = root / "butler_main" / "butler_bot_code"
            body_dir.mkdir(parents=True, exist_ok=True)
            registry_path = body_dir / "registry.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "butler_bot": {
                            "script": "../chat/core.py",
                            "config": "configs/butler_bot.json",
                            "description": "chat core",
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            specs = manager.load_registry(registry_path)

            self.assertIn("butler_bot", specs)
            self.assertEqual(specs["butler_bot"].script_path, (body_dir / "../chat/core.py").resolve())
            self.assertEqual(specs["butler_bot"].config_path, str((body_dir / "configs/butler_bot.json").resolve()))
            self.assertTrue(specs["butler_bot"].health_url.endswith("/health"))

    def test_start_and_stop_service_manage_pid_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service_script = root / "demo_service.py"
            service_script.write_text(_SERVICE_SCRIPT, encoding="utf-8")
            config_path = root / "demo.json"
            config_path.write_text("{}", encoding="utf-8")
            ready_path = root / "ready.txt"
            spec = manager.ServiceSpec(
                name="demo",
                script_path=service_script,
                config_path=str(config_path),
                description="demo service",
            )
            run_dir = root / "run"
            log_dir = root / "logs"

            start_result = manager.start_service(
                spec,
                extra_args=["--ready-file", str(ready_path)],
                run_dir=run_dir,
                log_dir=log_dir,
                repo_root=root,
                python_executable=sys.executable,
            )
            self.assertTrue(start_result["ok"])
            self.assertTrue(start_result["running"])
            for _ in range(20):
                if ready_path.is_file():
                    break
                time.sleep(0.1)
            self.assertTrue(ready_path.is_file())
            self.assertEqual(ready_path.read_text(encoding="utf-8"), str(config_path))
            self.assertTrue((run_dir / "demo.pid").is_file())

            status_result = manager.status_service(spec, run_dir=run_dir, log_dir=log_dir)
            self.assertTrue(status_result["running"])
            self.assertFalse(status_result["stale_pid"])

            stop_result = manager.stop_service(spec, run_dir=run_dir, log_dir=log_dir, timeout_seconds=3.0)
            self.assertTrue(stop_result["ok"])
            self.assertFalse(manager.status_service(spec, run_dir=run_dir, log_dir=log_dir)["running"])
            self.assertFalse((run_dir / "demo.pid").exists())

    def test_status_reports_stale_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = manager.ServiceSpec(
                name="demo",
                script_path=root / "demo.py",
                config_path="",
                description="demo service",
            )
            run_dir = root / "run"
            log_dir = root / "logs"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "demo.pid").write_text("999999", encoding="utf-8")

            status_result = manager.status_service(spec, run_dir=run_dir, log_dir=log_dir)

            self.assertFalse(status_result["running"])
            self.assertTrue(status_result["stale_pid"])

    def test_resolve_service_python_executable_prefers_repo_venv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            venv_python = root / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True, exist_ok=True)
            venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
            venv_python.chmod(0o755)

            resolved = manager._resolve_service_python_executable(
                repo_root=root,
                requested_python=None,
            )

            self.assertEqual(resolved, str(venv_python))

    def test_resolve_service_python_executable_keeps_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            resolved = manager._resolve_service_python_executable(
                repo_root=root,
                requested_python="/custom/python",
            )

            self.assertEqual(resolved, "/custom/python")

    def test_default_health_url_uses_lightweight_core_defaults(self) -> None:
        butler_bot_url = manager._default_health_url_for_service("butler_bot")
        console_url = manager._default_health_url_for_service("console")

        self.assertEqual(butler_bot_url, "http://127.0.0.1:18789/health")
        self.assertEqual(console_url, "http://127.0.0.1:8765/console/api/runtime")


if __name__ == "__main__":
    unittest.main()
