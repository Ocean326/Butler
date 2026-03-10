import json
import tempfile
from pathlib import Path
import sys
import importlib.util
import time
import unittest
from datetime import datetime, timedelta


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
spec = importlib.util.spec_from_file_location("restart_guardian_agent", MODULE_DIR / "restart_guardian_agent.py")
if spec is None or spec.loader is None:
    raise RuntimeError("failed to load restart_guardian_agent module")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
RestartGuardianAgent = module.RestartGuardianAgent


class _FakeGuardian(RestartGuardianAgent):
    def __init__(self, *args, status_sequence=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._status_sequence = list(status_sequence or [True])
        self.calls = []

    def _run_manager_command(self, action: str, bot_name: str | None):
        self.calls.append((action, bot_name))
        if action == "status":
            ok = self._status_sequence.pop(0) if self._status_sequence else True
            if ok:
                return 0, "运行中的飞书机器人：\n  butler_bot  PID=12345"
            return 0, "无运行中的飞书机器人"
        return 0, f"{action} {bot_name or ''} ok"


class RestartGuardianAgentTests(unittest.TestCase):
    def _prepare_workspace(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "butler_bot_code" / "logs").mkdir(parents=True, exist_ok=True)
        manager_ps1 = root / "butler_bot_code" / "manager.ps1"
        manager_ps1.write_text("# mock", encoding="utf-8")
        return root

    def test_guardian_success_on_first_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            agent = _FakeGuardian(workspace=str(root), reason="升级后生效", status_sequence=[True])

            code = agent.run()

            self.assertEqual(code, 0)
            latest_json = root / "工作区" / "governance" / "self_upgrade_reports" / "restart_guardian_latest.json"
            self.assertTrue(latest_json.exists())
            payload = json.loads(latest_json.read_text(encoding="utf-8"))
            self.assertTrue(payload.get("success"))
            self.assertEqual(len(payload.get("attempts") or []), 1)
            self.assertIn(("restart", "butler_bot"), agent.calls)

            recent_path = root / "butler_bot_agent" / "agents" / "recent_memory" / "recent_memory.json"
            self.assertTrue(recent_path.exists())
            recent = json.loads(recent_path.read_text(encoding="utf-8"))
            self.assertTrue(any(str(x.get("topic") or "") == "自我升级守护报告" for x in recent))

    def test_guardian_fallback_flow_and_issue_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            err = root / "butler_bot_code" / "logs" / "butler_bot_20260308_001.err.log"
            err.write_text("启动失败，请查看 err 日志\n未找到 Cursor CLI", encoding="utf-8")

            agent = _FakeGuardian(
                workspace=str(root),
                reason="自我升级后重启",
                status_sequence=[False, True],
            )

            code = agent.run()

            self.assertEqual(code, 0)
            latest_json = root / "工作区" / "governance" / "self_upgrade_reports" / "restart_guardian_latest.json"
            payload = json.loads(latest_json.read_text(encoding="utf-8"))
            self.assertTrue(payload.get("success"))
            issues = payload.get("detected_issues") or []
            self.assertTrue(any("Cursor CLI" in str(x) for x in issues))
            self.assertIn(("stop", "--all"), agent.calls)
            self.assertIn(("start", "butler_bot"), agent.calls)

    def test_consume_restart_markers_reads_reason_and_deletes_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            req = root / "工作区" / "restart_request.json"
            req.parent.mkdir(parents=True, exist_ok=True)
            req.write_text(json.dumps({"reason": "需要重启"}, ensure_ascii=False), encoding="utf-8")
            flag = root / "butler_bot_code" / "run" / "restart_requested.flag"
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.write_text("1", encoding="utf-8")

            agent = _FakeGuardian(workspace=str(root))
            reason = agent._consume_restart_markers()

            self.assertEqual(reason, "需要重启")
            self.assertFalse(req.exists())
            self.assertFalse(flag.exists())

    def test_heartbeat_health_detects_stale_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            hb = root / "butler_bot_agent" / "agents" / "recent_memory" / "heartbeat_last_sent.json"
            hb.parent.mkdir(parents=True, exist_ok=True)
            stale = (datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            hb.write_text(json.dumps({"last_sent_at": stale}, ensure_ascii=False), encoding="utf-8")
            pid_file = root / "butler_bot_code" / "run" / "butler_bot_heartbeat.pid"
            if pid_file.exists():
                pid_file.unlink()

            agent = _FakeGuardian(workspace=str(root), heartbeat_stale_seconds=120)
            ok, issue = agent._check_heartbeat_health()

            self.assertFalse(ok)
            self.assertIn("心跳超时", issue)

    def test_heartbeat_missing_timestamp_but_pid_alive_treated_as_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            hb = root / "butler_bot_agent" / "agents" / "recent_memory" / "heartbeat_last_sent.json"
            hb.parent.mkdir(parents=True, exist_ok=True)
            hb.write_text(json.dumps({"last_sent_at": ""}, ensure_ascii=False), encoding="utf-8")

            pid_file = root / "butler_bot_code" / "run" / "butler_bot_heartbeat.pid"
            pid_file.parent.mkdir(parents=True, exist_ok=True)
            pid_file.write_text("4321", encoding="utf-8")

            agent = _FakeGuardian(workspace=str(root))
            agent._pid_alive = lambda pid: pid == 4321
            ok, issue = agent._check_heartbeat_health()

            self.assertTrue(ok)
            self.assertEqual(issue, "")

    def test_health_level_heartbeat_only_when_main_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            hb = root / "butler_bot_agent" / "agents" / "recent_memory" / "heartbeat_last_sent.json"
            hb.parent.mkdir(parents=True, exist_ok=True)
            stale = (datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            hb.write_text(json.dumps({"last_sent_at": stale}, ensure_ascii=False), encoding="utf-8")

            agent = _FakeGuardian(workspace=str(root), heartbeat_stale_seconds=120, status_sequence=[True])
            level, issues = agent._check_health_level()

            self.assertEqual(level, "heartbeat-only")
            self.assertTrue(issues)

    def test_heartbeat_cooldown_state_suppresses_guardian_misjudgment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            state_file = root / "butler_bot_code" / "run" / "heartbeat_watchdog_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                json.dumps(
                    {
                        "state": "cooldown",
                        "cooldown_until_epoch": time.time() + 300,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            agent = _FakeGuardian(workspace=str(root), heartbeat_stale_seconds=120)
            ok, issue = agent._check_heartbeat_health()

            self.assertTrue(ok)
            self.assertEqual(issue, "")

    def test_restart_requested_handover_state_suppresses_guardian_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            state_file = root / "butler_bot_code" / "run" / "heartbeat_watchdog_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                json.dumps(
                    {
                        "state": "restart-requested",
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "restart_inhibit_until_epoch": time.time() + 60,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            agent = _FakeGuardian(workspace=str(root), heartbeat_stale_seconds=120)
            ok, issue = agent._check_heartbeat_health()

            self.assertTrue(ok)
            self.assertEqual(issue, "")

    def test_fresh_crashed_state_gives_main_watchdog_time_to_recover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            state_file = root / "butler_bot_code" / "run" / "heartbeat_watchdog_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                json.dumps(
                    {
                        "state": "crashed",
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "heartbeat_pid": 0,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            agent = _FakeGuardian(workspace=str(root), heartbeat_stale_seconds=120, status_sequence=[True])
            ok, issue = agent._check_heartbeat_health()

            self.assertTrue(ok)
            self.assertEqual(issue, "")

    def test_main_runtime_state_treated_as_authoritative_health_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            state_file = root / "butler_bot_code" / "run" / "butler_bot_main_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                json.dumps(
                    {
                        "state": "running",
                        "pid": 24680,
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            agent = _FakeGuardian(workspace=str(root), status_sequence=[False])
            agent._pid_alive = lambda pid: pid == 24680
            status, ok = agent._check_running()

            self.assertTrue(ok)
            self.assertIn("PID=24680", status)
            self.assertNotIn(("status", None), agent.calls)

    def test_main_runtime_state_stale_falls_back_to_manager_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            state_file = root / "butler_bot_code" / "run" / "butler_bot_main_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            stale = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
            state_file.write_text(
                json.dumps(
                    {
                        "state": "running",
                        "pid": 13579,
                        "updated_at": stale,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            agent = _FakeGuardian(workspace=str(root), status_sequence=[True])
            agent._pid_alive = lambda pid: pid == 13579
            status, ok = agent._check_running()

            self.assertTrue(ok)
            self.assertIn("butler_bot", status)
            self.assertIn("PID=12345", status)
            self.assertIn(("status", None), agent.calls)

    def test_soft_recovery_kills_heartbeat_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            pid_file = root / "scripts" / "butler_bot" / "run" / "butler_bot_heartbeat.pid"
            pid_file.parent.mkdir(parents=True, exist_ok=True)
            pid_file.write_text("12345", encoding="utf-8")

            agent = _FakeGuardian(workspace=str(root))

            def fake_run(args, cwd):
                if args and str(args[0]).lower() == "taskkill":
                    return 0, "SUCCESS"
                return 0, "OK"

            agent._run_command = fake_run
            ok, msg = agent._attempt_soft_heartbeat_recovery()

            self.assertTrue(ok)
            self.assertIn("PID=12345", msg)

    def test_forensics_collects_traceback_and_recent_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._prepare_workspace(tmp)
            sample_py = root / "scripts" / "butler_bot" / "butler_bot" / "sample_bug.py"
            sample_py.parent.mkdir(parents=True, exist_ok=True)
            sample_py.write_text("def f():\n    x = 1\n    return x\n", encoding="utf-8")

            err = root / "scripts" / "butler_bot" / "logs" / "x.err.log"
            err.write_text(
                f"Traceback (most recent call last):\n  File \"{sample_py}\", line 2, in f\nValueError: boom\n",
                encoding="utf-8",
            )

            agent = _FakeGuardian(workspace=str(root))
            info = agent._collect_forensics(str(err))

            frames = info.get("traceback_frames") or []
            changes = info.get("recent_code_changes") or []
            self.assertTrue(frames)
            self.assertIn("sample_bug.py", str(frames[0].get("file") or ""))
            self.assertTrue(changes)


if __name__ == "__main__":
    unittest.main()
