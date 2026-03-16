import tempfile
from datetime import datetime
from pathlib import Path
import json
import time
import sys
import unittest
from unittest import mock


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

from memory_manager import BEAT_RECENT_POOL, MemoryManager  # noqa: E402
from services.task_ledger_service import TaskLedgerService  # noqa: E402


class MemoryManagerMaintenanceTests(unittest.TestCase):
    def test_upsert_heartbeat_task_board_item_quarantines_non_utf8_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("", False),
            )

            manager._ensure_heartbeat_task_board(str(workspace))
            path = manager._heartbeat_task_category_path(str(workspace), "work")
            path.write_bytes(b"\x89PNG\r\n\x1a\nnot-markdown")

            manager._upsert_heartbeat_task_board_item(
                str(workspace),
                {"task_id": "task-utf8", "title": "普通任务", "detail": "恢复可读 markdown", "task_category": "work"},
                long_term=False,
                action="update",
                source="test",
            )

            content = path.read_text(encoding="utf-8")
            self.assertIn("task_id=task-utf8", content)
            quarantine_dir = manager._heartbeat_task_board_quarantine_dir(str(workspace))
            quarantined = list(quarantine_dir.glob("*.corrupt"))
            self.assertTrue(quarantined)

    def test_safe_read_heartbeat_task_board_text_retries_permission_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("", False),
            )

            manager._ensure_heartbeat_task_board(str(workspace))
            path = manager._heartbeat_task_category_path(str(workspace), "work")
            expected = path.read_text(encoding="utf-8")

            with mock.patch("memory_manager.Path.read_text", side_effect=[PermissionError("busy"), expected]):
                content = manager._safe_read_heartbeat_task_board_text(str(workspace), path)

            self.assertEqual(content, expected)

    def test_start_background_services_skips_embedded_heartbeat_when_external_runtime_is_forced(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "agent_timeout": 60,
                    "agent_model": "auto",
                    "heartbeat": {"enabled": True},
                },
                run_model_fn=lambda *_: ("", False),
            )

            launches = []
            manager._start_heartbeat_service_locked = lambda cfg: launches.append(cfg)

            with mock.patch.object(manager, "_run_local_memory_maintenance_once", return_value={"skipped": True}), \
                 mock.patch.object(manager, "_run_recent_memory_maintenance_once", return_value={"before_count": 0, "after_count": 0, "compacted": False, "reflections_count": 0}), \
                 mock.patch.object(manager, "_use_external_heartbeat_process", return_value=True), \
                 mock.patch("memory_manager.threading.Thread") as thread_cls, \
                 mock.patch("memory_manager.multiprocessing.Process") as proc_cls:
                proc_cls.return_value.start = lambda: None
                proc_cls.return_value.pid = 123
                thread_cls.return_value.start = lambda: None
                manager.start_background_services()

            self.assertEqual(launches, [])
            self.assertTrue(manager._self_mind_started)

    def test_heartbeat_watchdog_enters_cooldown_after_burst_restarts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "heartbeat": {"enabled": True, "every_minutes": 1},
                },
                run_model_fn=lambda *_: ("", False),
            )

            class DeadProc:
                exitcode = 1
                def is_alive(self):
                    return False

            manager._heartbeat_process = DeadProc()
            manager._heartbeat_started = True
            launches = []

            def fake_start(cfg):
                launches.append(time.time())
                manager._heartbeat_started = True

            manager._start_heartbeat_service_locked = fake_start

            sleep_calls = {"count": 0}
            real_time = time.time
            base = [1000.0]

            def fake_time():
                return base[0]

            def fake_sleep(seconds: float):
                sleep_calls["count"] += 1
                base[0] += seconds
                manager._heartbeat_process = DeadProc()
                manager._heartbeat_started = True
                if sleep_calls["count"] >= 4:
                    raise RuntimeError("stop-watchdog")

            with mock.patch("memory_manager.time.sleep", side_effect=fake_sleep), mock.patch("memory_manager.time.time", side_effect=fake_time):
                with self.assertRaises(RuntimeError):
                    manager._heartbeat_process_watchdog_loop(str(workspace))

            self.assertEqual(len(launches), 2)
            self.assertGreater(manager._heartbeat_restart_cooldown_until, 0)

    def test_restart_hook_requests_user_approval_instead_of_guardian(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            req = workspace / "工作区" / "restart_request.json"
            req.parent.mkdir(parents=True, exist_ok=True)
            req.write_text(json.dumps({"reason": "更新了 memory_manager"}, ensure_ascii=False), encoding="utf-8")

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            sent = {}

            def fake_send(cfg: dict, text: str, **kwargs) -> bool:
                sent["text"] = text
                return True

            manager._send_private_message = fake_send
            manager._launch_restart_guardian = lambda *_: (_ for _ in ()).throw(AssertionError("heartbeat must not launch guardian directly"))

            manager._check_and_perform_restart(str(workspace))

            request = manager._read_heartbeat_upgrade_request(str(workspace))
            self.assertEqual(str(request.get("status") or ""), "pending")
            self.assertEqual(str(request.get("action") or ""), "restart")
            self.assertEqual(str(request.get("reason") or ""), "更新了 memory_manager")
            self.assertTrue(str(request.get("user_notified_at") or ""))
            self.assertIn("等待用户批准", sent.get("text") or "")
            self.assertTrue(req.exists())

    def test_pending_upgrade_request_reject_clears_request_and_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            req = workspace / "工作区" / "restart_request.json"
            req.parent.mkdir(parents=True, exist_ok=True)
            req.write_text(json.dumps({"reason": "更新了 memory_manager"}, ensure_ascii=False), encoding="utf-8")

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            manager._write_heartbeat_upgrade_request(
                str(workspace),
                {"request_id": "req-1", "status": "pending", "action": "restart", "reason": "更新了 memory_manager", "summary": "需要重启"},
            )

            decision = manager.inspect_pending_upgrade_request_prompt(str(workspace), "先别重启 req-1")

            self.assertEqual(decision["decision"], "reject")
            self.assertEqual(manager._read_heartbeat_upgrade_request(str(workspace)), {})
            self.assertFalse(req.exists())

    def test_pending_upgrade_request_approve_restart_returns_restart_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            manager._write_heartbeat_upgrade_request(
                str(workspace),
                {"request_id": "req-1", "status": "pending", "action": "restart", "reason": "更新了 memory_manager", "summary": "需要重启"},
            )

            decision = manager.inspect_pending_upgrade_request_prompt(str(workspace), "可以重启 req-1")

            self.assertEqual(decision["decision"], "approve-restart")
            stored = manager._read_heartbeat_upgrade_request(str(workspace))
            self.assertEqual(str(stored.get("status") or ""), "approved")

    def test_pending_upgrade_request_approve_execute_keeps_update_agent_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            manager._write_heartbeat_upgrade_request(
                str(workspace),
                {
                    "request_id": "req-2",
                    "status": "pending",
                    "action": "execute_prompt",
                    "reason": "需要收敛 prompt 注入",
                    "summary": "统一维护入口执行",
                    "execute_prompt": "请修改 prompt builder 并补测试。",
                    "maintainer_agent_role": "update-agent",
                    "target_paths": ["./butler_main/butler_bot_code/butler_bot/agent.py"],
                },
            )

            decision = manager.inspect_pending_upgrade_request_prompt(str(workspace), "同意按计划执行 req-2")

            self.assertEqual(decision["decision"], "approve-execute")
            self.assertIn("update-agent", decision["execute_prompt"])
            self.assertIn("prompt builder", decision["execute_prompt"])

    def test_heartbeat_watchdog_skips_respawn_during_restart_handover(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "heartbeat": {"enabled": True, "every_minutes": 1},
                },
                run_model_fn=lambda *_: ("", False),
            )

            class DeadProc:
                exitcode = 0
                def is_alive(self):
                    return False

            manager._heartbeat_process = DeadProc()
            manager._heartbeat_started = True
            launches = []
            manager._start_heartbeat_service_locked = lambda cfg: launches.append(cfg)
            manager._write_heartbeat_watchdog_state(
                str(workspace),
                state="restart-requested",
                restart_inhibit_until_epoch=time.time() + 120,
                note="guardian handover in progress",
            )

            sleep_calls = {"count": 0}
            def fake_sleep(seconds: float):
                sleep_calls["count"] += 1
                if sleep_calls["count"] >= 2:
                    raise RuntimeError("stop-watchdog")

            with mock.patch("memory_manager.time.sleep", side_effect=fake_sleep):
                with self.assertRaises(RuntimeError):
                    manager._heartbeat_process_watchdog_loop(str(workspace))

            self.assertEqual(launches, [])
            state = manager._read_heartbeat_watchdog_state(str(workspace))
            self.assertEqual(str(state.get("state") or ""), "restart-requested")

    def test_heartbeat_watchdog_restarts_stale_alive_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "heartbeat": {"enabled": True, "every_minutes": 1, "heartbeat_stale_seconds": 60},
                },
                run_model_fn=lambda *_: ("", False),
            )

            class AliveProc:
                pid = 4321
                def is_alive(self):
                    return True
                def terminate(self):
                    return None
                def join(self, timeout=None):
                    return None
                def kill(self):
                    return None

            manager._heartbeat_process = AliveProc()
            manager._heartbeat_started = True
            manager._write_heartbeat_run_state(
                str(workspace),
                run_id="stale-run",
                state="running",
                phase="execute",
                note="stuck",
            )
            run_state = manager._heartbeat_run_state_file(str(workspace))
            payload = json.loads(run_state.read_text(encoding="utf-8"))
            payload["heartbeat_pid"] = 4321
            payload["updated_at"] = "2026-03-16 00:00:00"
            run_state.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            launches = []
            stop_calls = []

            def fake_stop(ws: str, reason: str = ""):
                stop_calls.append(reason)
                manager._heartbeat_process = None
                manager._heartbeat_started = False
                return True

            def fake_start(cfg):
                launches.append(dict(cfg))
                manager._heartbeat_started = True

            manager._stop_heartbeat_service_locked = fake_stop
            manager._start_heartbeat_service_locked = fake_start

            sleep_calls = {"count": 0}
            def fake_sleep(seconds: float):
                sleep_calls["count"] += 1
                if sleep_calls["count"] >= 3:
                    raise RuntimeError("stop-watchdog")

            with mock.patch("memory_manager.time.sleep", side_effect=fake_sleep), mock.patch("memory_manager.time.time", return_value=datetime(2026, 3, 16, 1, 5, 0).timestamp()):
                with self.assertRaises(RuntimeError):
                    manager._heartbeat_process_watchdog_loop(str(workspace))

            self.assertEqual(len(stop_calls), 1)
            self.assertIn("run_state stale", stop_calls[0])
            self.assertEqual(len(launches), 1)

    def test_heartbeat_run_state_stale_check_ignores_previous_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "heartbeat": {"enabled": True, "heartbeat_stale_seconds": 60},
                },
                run_model_fn=lambda *_: ("", False),
            )

            class AliveProc:
                pid = 5555

            manager._heartbeat_process = AliveProc()
            manager._write_heartbeat_run_state(
                str(workspace),
                run_id="old-run",
                state="running",
                phase="execute",
                note="old",
            )
            run_state = manager._heartbeat_run_state_file(str(workspace))
            payload = json.loads(run_state.read_text(encoding="utf-8"))
            payload["heartbeat_pid"] = 4444
            payload["updated_at"] = "2026-03-16 00:00:00"
            run_state.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            stale, note = manager._heartbeat_run_state_stale_info(
                str(workspace),
                {"heartbeat_stale_seconds": 60},
                datetime(2026, 3, 16, 1, 5, 0).timestamp(),
            )

            self.assertFalse(stale)
            self.assertEqual(note, "")

    def test_heartbeat_activity_timestamp_updates_even_when_send_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace), "agent_timeout": 60},
                run_model_fn=lambda *_: ("", False),
            )

            manager._plan_heartbeat_action = lambda *args, **kwargs: {"user_message": "本轮心跳", "task_groups": [], "updates": {}}
            manager._execute_heartbeat_plan = lambda *args, **kwargs: ("执行完成", [])
            manager._apply_heartbeat_plan = lambda *args, **kwargs: None
            manager._persist_heartbeat_snapshot_to_recent = lambda *args, **kwargs: None
            manager._send_private_message = lambda *args, **kwargs: False
            manager._check_and_perform_restart = lambda *_: None

            manager._run_heartbeat_once(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "message": "fallback", "receive_id": "", "receive_id_type": "open_id"},
            )

            marker = manager._heartbeat_last_sent_path(str(workspace))
            self.assertTrue(marker.exists())
            payload = json.loads(marker.read_text(encoding="utf-8"))
            self.assertTrue(str(payload.get("last_activity_at") or "").strip())
            self.assertEqual(str(payload.get("last_sent_at") or ""), "")
            self.assertFalse(bool(payload.get("sent")))

            run_state = manager._heartbeat_run_state_file(str(workspace))
            self.assertTrue(run_state.exists())
            run_payload = json.loads(run_state.read_text(encoding="utf-8"))
            self.assertEqual(str(run_payload.get("state") or ""), "completed")
            self.assertEqual(str(run_payload.get("phase") or ""), "done")

    def test_heartbeat_run_state_records_failure_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace), "agent_timeout": 60},
                run_model_fn=lambda *_: ("", False),
            )

            manager._plan_heartbeat_action = lambda *args, **kwargs: {"user_message": "本轮心跳", "task_groups": [], "updates": {}}
            manager._execute_heartbeat_plan = lambda *args, **kwargs: ("执行完成", [])
            manager._persist_heartbeat_snapshot_to_recent = lambda *args, **kwargs: None
            manager._send_private_message = lambda *args, **kwargs: False
            manager._check_and_perform_restart = lambda *_: None

            def explode(*args, **kwargs):
                raise RuntimeError("apply failed")

            manager._apply_heartbeat_plan = explode

            with self.assertRaises(RuntimeError):
                manager._run_heartbeat_once(
                    {"workspace_root": str(workspace), "agent_timeout": 60},
                    {"enabled": True, "message": "fallback", "receive_id": "", "receive_id_type": "open_id"},
                )

            run_state = manager._heartbeat_run_state_file(str(workspace))
            self.assertTrue(run_state.exists())
            payload = json.loads(run_state.read_text(encoding="utf-8"))
            self.assertEqual(str(payload.get("state") or ""), "failed")
            self.assertEqual(str(payload.get("phase") or ""), "apply")
            self.assertIn("RuntimeError: apply failed", str(payload.get("error") or ""))

    def test_long_memory_maintenance_skips_within_cooldown(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return "整理完成", True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            first = manager._run_local_memory_maintenance_once(str(workspace), 60, "auto", reason="startup-subprocess")
            second = manager._run_local_memory_maintenance_once(str(workspace), 60, "auto", reason="startup-watchdog")

            self.assertFalse(first["skipped"])
            self.assertTrue(second["skipped"])
            self.assertEqual(len(calls), 1)
            self.assertIn("未满 30 分钟", second["model_summary"])

    def test_long_memory_maintenance_cooldown_survives_new_manager_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return "整理完成", True

            manager1 = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            manager1._run_local_memory_maintenance_once(str(workspace), 60, "auto", reason="startup-subprocess")

            manager2 = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            second = manager2._run_local_memory_maintenance_once(str(workspace), 60, "auto", reason="startup-subprocess")

            self.assertTrue(second["skipped"])
            self.assertEqual(len(calls), 1)

    def test_heartbeat_uses_startup_delay_once_then_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            hb_cfg = {"every_minutes": 3, "startup_delay_seconds": 15, "align_to_interval": False}

            first = manager._seconds_to_next_heartbeat(datetime(2026, 3, 7, 10, 0, 0), hb_cfg)
            second = manager._seconds_to_next_heartbeat(datetime(2026, 3, 7, 10, 0, 10), hb_cfg)

            self.assertEqual(first, 15.0)
            self.assertEqual(second, 180.0)

    def test_heartbeat_loop_runs_immediately_before_first_sleep(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "heartbeat": {"enabled": True, "every_minutes": 3, "startup_delay_seconds": 15, "align_to_interval": False},
                },
                run_model_fn=lambda *_: ("", False),
            )

            calls = []
            sleeps = []

            def fake_run_once(cfg: dict, heartbeat_cfg: dict):
                calls.append((cfg, heartbeat_cfg))

            def fake_sleep(seconds: float):
                sleeps.append(seconds)
                raise RuntimeError("stop-loop")

            manager._run_heartbeat_once = fake_run_once
            with mock.patch("memory_manager.time.sleep", side_effect=fake_sleep):
                with self.assertRaises(RuntimeError):
                    manager._heartbeat_loop(run_immediately=True)

            self.assertEqual(len(calls), 1)
            self.assertEqual(sleeps, [180.0])

    def test_heartbeat_loop_bootstrap_failure_marks_watchdog_degraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "heartbeat": {"enabled": True, "every_minutes": 3, "startup_delay_seconds": 15, "align_to_interval": False},
                },
                run_model_fn=lambda *_: ("", False),
            )

            manager._send_heartbeat_start_notification = lambda *args, **kwargs: None
            manager._run_heartbeat_once = mock.Mock(side_effect=RuntimeError("bad bootstrap"))

            def fake_sleep(seconds: float):
                raise RuntimeError("stop-loop")

            with mock.patch("memory_manager.time.sleep", side_effect=fake_sleep):
                with self.assertRaises(RuntimeError):
                    manager._heartbeat_loop(run_immediately=True)

            state = manager._read_heartbeat_watchdog_state(str(workspace))
            self.assertEqual(str(state.get("state") or ""), "degraded")
            run_payload = json.loads(manager._heartbeat_run_state_file(str(workspace)).read_text(encoding="utf-8"))
            self.assertEqual(str(run_payload.get("state") or ""), "failed")
            self.assertEqual(str(run_payload.get("phase") or ""), "bootstrap")

    def test_heartbeat_planner_runs_without_legacy_agent_prompt_and_completes_selected_short_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                if len(calls) == 1:
                    payload = {
                        "chosen_mode": "short_task",
                        "reason": "先处理短期任务",
                        "user_message": "本次心跳先处理短期任务。",
                        "execute_prompt": "执行：整理待办摘要",
                        "selected_task_ids": ["task-1"],
                        "updates": {
                            "complete_task_ids": ["task-1"],
                            "defer_task_ids": [],
                            "touch_long_task_ids": []
                        }
                    }
                    return json.dumps(payload, ensure_ascii=False), True
                return "已完成短期任务整理", True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            manager._save_heartbeat_memory(str(workspace), {
                "version": 1,
                "updated_at": "",
                "tasks": [
                    {
                        "task_id": "task-1",
                        "source": "conversation",
                        "source_memory_id": "",
                        "created_at": "2026-03-07 10:00:00",
                        "updated_at": "2026-03-07 10:00:00",
                        "status": "pending",
                        "priority": "medium",
                        "title": "整理待办",
                        "detail": "整理待办摘要",
                        "trigger_hint": "conversation",
                        "due_at": "",
                        "tags": [],
                        "last_result": ""
                    }
                ],
                "notes": []
            })

            sent = []
            manager._send_private_message = lambda cfg, text, **kwargs: sent.append(text) or True
            manager._run_heartbeat_once({"workspace_root": str(workspace), "agent_timeout": 60}, {"enabled": True, "message": "fallback", "receive_id": "u", "receive_id_type": "open_id"})

            self.assertEqual(len(calls), 2)
            payload = manager._load_heartbeat_memory(str(workspace))
            self.assertEqual(payload["tasks"][0]["status"], "done")
            ledger_file = TaskLedgerService(str(workspace)).path
            self.assertTrue(ledger_file.exists())
            ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
            ledger_items = {item["task_id"]: item for item in ledger.get("items") or []}
            self.assertEqual(ledger_items["task-1"]["status"], "done")
            self.assertTrue(sent)
            self.assertTrue(any("本次心跳先处理短期任务" in text for text in sent))

    def test_heartbeat_due_long_task_runs_through_planner(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                if len(calls) == 1:
                    payload = {
                        "chosen_mode": "long_task",
                        "execution_mode": "single",
                        "reason": "到期长期任务优先",
                        "user_message": "本次心跳先处理到期长期任务。",
                        "task_groups": [
                            {
                                "group_id": "g1",
                                "branches": [
                                    {
                                        "branch_id": "b1",
                                        "prompt": "执行长期提醒任务",
                                        "touch_long_task_ids": ["long-1"],
                                        "selected_task_ids": [],
                                        "can_run_parallel": False,
                                    }
                                ],
                            }
                        ],
                        "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []}
                    }
                    return json.dumps(payload, ensure_ascii=False), True
                return "已完成长期任务", True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            manager._save_heartbeat_long_tasks(str(workspace), {
                "version": 1,
                "updated_at": "",
                "tasks": [
                    {
                        "task_id": "long-1",
                        "kind": "reminder",
                        "schedule_type": "daily",
                        "schedule_value": "09:00",
                        "timezone": "Asia/Shanghai",
                        "enabled": True,
                        "title": "每日提醒",
                        "detail": "执行长期提醒任务",
                        "created_at": "2026-03-07 10:00:00",
                        "updated_at": "2026-03-07 10:00:00",
                        "last_run_at": "",
                        "next_due_at": "2026-03-07 09:00:00",
                        "last_result": ""
                    }
                ]
            })

            sent = []
            manager._send_private_message = lambda cfg, text, **kwargs: sent.append(text) or True
            manager._run_heartbeat_once({"workspace_root": str(workspace), "agent_timeout": 60}, {"enabled": True, "message": "fallback", "receive_id": "u", "receive_id_type": "open_id"})

            self.assertEqual(len(calls), 3)
            long_store = manager._load_heartbeat_long_tasks(str(workspace))
            task = long_store["tasks"][0]
            self.assertIn("已完成长期任务", task["last_result"])
            self.assertTrue(str(task.get("last_run_at") or "").strip())
            self.assertNotEqual(task["next_due_at"], "2026-03-07 09:00:00")
            ledger_file = TaskLedgerService(str(workspace)).path
            self.assertTrue(ledger_file.exists())
            ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
            ledger_items = {item["task_id"]: item for item in ledger.get("items") or []}
            self.assertTrue(str(ledger_items["long-1"].get("last_run_at") or "").strip())
            self.assertTrue(sent)
            self.assertTrue(any("到期长期任务" in text for text in sent))

    def test_heartbeat_apply_plan_cleans_retired_markdown_mirrors_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                if len(calls) == 1:
                    payload = {
                        "chosen_mode": "short_task",
                        "execution_mode": "single",
                        "reason": "处理短期任务",
                        "user_message": "本轮处理短期任务。",
                        "execute_prompt": "执行：整理待办摘要",
                        "selected_task_ids": ["task-1"],
                        "updates": {
                            "complete_task_ids": ["task-1"],
                            "defer_task_ids": [],
                            "touch_long_task_ids": []
                        }
                    }
                    return json.dumps(payload, ensure_ascii=False), True
                return "已完成短期任务整理", True

            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "features": {"legacy_heartbeat_markdown_mirrors": False},
                },
                run_model_fn=fake_model,
            )
            manager._save_heartbeat_memory(str(workspace), {
                "version": 1,
                "updated_at": "",
                "tasks": [
                    {
                        "task_id": "task-1",
                        "source": "conversation",
                        "source_memory_id": "",
                        "created_at": "2026-03-07 10:00:00",
                        "updated_at": "2026-03-07 10:00:00",
                        "status": "pending",
                        "priority": "medium",
                        "title": "整理待办",
                        "detail": "整理待办摘要",
                        "trigger_hint": "conversation",
                        "due_at": "",
                        "tags": [],
                        "last_result": ""
                    }
                ],
                "notes": []
            })
            mirror_recent = manager._heartbeat_memory_mirror_path(str(workspace))
            mirror_long = manager._heartbeat_long_tasks_mirror_path(str(workspace))
            mirror_recent.parent.mkdir(parents=True, exist_ok=True)
            mirror_long.parent.mkdir(parents=True, exist_ok=True)
            mirror_recent.write_text("stale recent mirror", encoding="utf-8")
            mirror_long.write_text("stale long mirror", encoding="utf-8")

            manager._send_private_message = lambda cfg, text, **kwargs: True
            manager._run_heartbeat_once(
                {"workspace_root": str(workspace), "agent_timeout": 60, "features": {"legacy_heartbeat_markdown_mirrors": False}},
                {"enabled": True, "message": "fallback", "receive_id": "u", "receive_id_type": "open_id"},
            )

            self.assertEqual(len(calls), 2)
            self.assertFalse(mirror_recent.exists())
            self.assertFalse(mirror_long.exists())

    def test_heartbeat_no_task_still_uses_planner_and_includes_local_memory_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                if len(calls) == 1:
                    self.assertIn("长期记忆候选", prompt)
                    self.assertIn("长期约束", prompt)
                    payload = {
                        "chosen_mode": "short_task",
                        "execution_mode": "single",
                        "reason": "从长期记忆中恢复一个低风险治理任务",
                        "user_message": "本轮没有显式近期任务，已从长期记忆中提取一个待推进事项继续处理。",
                        "execute_prompt": "根据长期约束整理一个低风险治理待办，并写入工作区说明",
                        "selected_task_ids": [],
                        "deferred_task_ids": [],
                        "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []}
                    }
                    return json.dumps(payload, ensure_ascii=False), True
                return "已根据长期记忆恢复一个治理待办", True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            local_file = workspace / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "长期约束.md"
            local_file.parent.mkdir(parents=True, exist_ok=True)
            local_file.write_text("# 长期约束\n\n继续做低风险治理，不要空转。", encoding="utf-8")
            sent = []
            manager._send_private_message = lambda cfg, text, **kwargs: sent.append(text) or True

            manager._run_heartbeat_once(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "message": "fallback", "receive_id": "u", "receive_id_type": "open_id", "every_seconds": 5},
            )

            self.assertEqual(len(calls), 2)
            self.assertTrue(sent)
            self.assertTrue(any("长期记忆" in text for text in sent))

    def test_heartbeat_emits_progress_receipt_before_final_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace), "agent_timeout": 60},
                run_model_fn=lambda *_: ("", False),
            )

            manager._plan_heartbeat_action = lambda *args, **kwargs: {
                "chosen_mode": "short_task",
                "execution_mode": "single",
                "reason": "先推进一条明确短任务",
                "user_message": "本轮先推进一条短任务。",
                "task_groups": [
                    {
                        "group_id": "g1",
                        "branches": [
                            {"branch_id": "b1", "prompt": "执行一次短任务", "selected_task_ids": ["task-1"], "can_run_parallel": False}
                        ],
                    }
                ],
                "updates": {"complete_task_ids": ["task-1"], "defer_task_ids": [], "touch_long_task_ids": []},
            }
            manager._execute_heartbeat_plan = lambda *args, **kwargs: ("已完成短任务。", [])
            manager._apply_heartbeat_plan = lambda *args, **kwargs: None
            manager._persist_heartbeat_snapshot_to_recent = lambda *args, **kwargs: None
            manager._check_and_perform_restart = lambda *_: None

            sent = []
            manager._send_private_message = lambda cfg, text, **kwargs: sent.append(text) or True

            manager._run_heartbeat_once(
                {"workspace_root": str(workspace), "agent_timeout": 60, "features": {"heartbeat_debug_receipts": True}},
                {"enabled": True, "message": "fallback", "receive_id": "u", "receive_id_type": "open_id"},
            )

            self.assertGreaterEqual(len(sent), 3)
            self.assertIn("阶段：新一轮已开始，正在规划", sent[0])
            self.assertTrue(any("阶段：已完成规划，开始执行" in text for text in sent))
            self.assertTrue(any("本轮先推进一条短任务" in text for text in sent))
            self.assertIn("已完成短任务", sent[-1])

    def test_build_planning_prompt_tolerates_legacy_literal_braces(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            orchestrator = manager._heartbeat_orchestrator

            legacy_template = """# 心跳规划器

## JSON Schema

{json_schema}

## 最近上下文

{recent_text}

## 示例

请参考这个字面量示例，不要把它当占位符：{长期记忆候选}
"""
            manager._load_heartbeat_prompt_template = lambda _workspace: legacy_template
            manager._render_heartbeat_local_memory_snippet = lambda _workspace: "长期约束：继续做低风险治理"

            prompt = orchestrator.build_planning_prompt({}, {"context_prompt": "(无)"}, str(workspace))

            self.assertIn("长期记忆候选", prompt)
            self.assertIn("长期约束：继续做低风险治理", prompt)
            self.assertIn("{长期记忆候选}", prompt)

    def test_long_task_not_touched_when_branch_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            manager._save_heartbeat_long_tasks(str(workspace), {
                "version": 1,
                "updated_at": "",
                "tasks": [
                    {
                        "task_id": "long-1",
                        "kind": "reminder",
                        "schedule_type": "daily",
                        "schedule_value": "09:00",
                        "timezone": "Asia/Shanghai",
                        "enabled": True,
                        "title": "每日提醒",
                        "detail": "提醒",
                        "created_at": "2026-03-07 10:00:00",
                        "updated_at": "2026-03-07 10:00:00",
                        "last_run_at": "",
                        "next_due_at": "2026-03-07 09:00:00",
                        "last_result": ""
                    }
                ]
            })

            plan = {
                "user_message": "本轮执行长期任务",
                "updates": {"touch_long_task_ids": []},
            }
            branch_results = [{"ok": False, "touch_long_task_ids": ["long-1"], "selected_task_ids": []}]
            manager._apply_heartbeat_plan(str(workspace), plan, "", branch_results=branch_results)

            long_store = manager._load_heartbeat_long_tasks(str(workspace))
            task = long_store["tasks"][0]
            self.assertEqual(task.get("last_run_at") or "", "")
            self.assertEqual(task["next_due_at"], "2026-03-07 09:00:00")

    def test_heartbeat_parallel_branches_capped_to_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            active = {"count": 0, "max": 0}
            stats = {"exec_calls": 0}

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                if "JSON Schema" in prompt:
                    payload = {
                        "chosen_mode": "short_task",
                        "execution_mode": "parallel",
                        "reason": "并行推进互不依赖任务",
                        "user_message": "本次心跳将并行推进多项任务。",
                        "selected_task_ids": ["task-1", "task-2", "task-3", "task-4"],
                        "deferred_task_ids": ["task-4"],
                        "defer_reason": "本轮并行预算上限为 3",
                        "task_groups": [
                            {
                                "group_id": "g1",
                                "branches": [
                                    {"branch_id": "b1", "prompt": "执行分支-1", "selected_task_ids": ["task-1"], "can_run_parallel": True},
                                    {"branch_id": "b2", "prompt": "执行分支-2", "selected_task_ids": ["task-2"], "can_run_parallel": True},
                                    {"branch_id": "b3", "prompt": "执行分支-3", "selected_task_ids": ["task-3"], "can_run_parallel": True},
                                    {"branch_id": "b4", "prompt": "执行分支-4", "selected_task_ids": ["task-4"], "can_run_parallel": True}
                                ]
                            }
                        ],
                        "updates": {"complete_task_ids": [], "defer_task_ids": ["task-4"], "touch_long_task_ids": []}
                    }
                    return json.dumps(payload, ensure_ascii=False), True

                if "执行分支-" in prompt:
                    stats["exec_calls"] += 1
                    active["count"] += 1
                    active["max"] = max(active["max"], active["count"])
                    try:
                        time.sleep(0.12)
                    finally:
                        active["count"] -= 1
                    return "分支执行完成", True
                return "", False

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=fake_model)
            manager._save_heartbeat_memory(str(workspace), {
                "version": 1,
                "updated_at": "",
                "tasks": [
                    {"task_id": "task-1", "status": "pending", "title": "t1", "detail": "d1", "created_at": "", "updated_at": "", "priority": "medium", "source": "conversation", "source_memory_id": "", "trigger_hint": "conversation", "due_at": "", "tags": [], "last_result": ""},
                    {"task_id": "task-2", "status": "pending", "title": "t2", "detail": "d2", "created_at": "", "updated_at": "", "priority": "medium", "source": "conversation", "source_memory_id": "", "trigger_hint": "conversation", "due_at": "", "tags": [], "last_result": ""},
                    {"task_id": "task-3", "status": "pending", "title": "t3", "detail": "d3", "created_at": "", "updated_at": "", "priority": "medium", "source": "conversation", "source_memory_id": "", "trigger_hint": "conversation", "due_at": "", "tags": [], "last_result": ""},
                    {"task_id": "task-4", "status": "pending", "title": "t4", "detail": "d4", "created_at": "", "updated_at": "", "priority": "medium", "source": "conversation", "source_memory_id": "", "trigger_hint": "conversation", "due_at": "", "tags": [], "last_result": ""}
                ],
                "notes": []
            })

            manager._send_private_message = lambda cfg, text, **kwargs: True
            manager._run_heartbeat_once(
                {"workspace_root": str(workspace), "agent_timeout": 90},
                {"enabled": True, "message": "fallback", "receive_id": "u", "receive_id_type": "open_id", "max_parallel_branches": 6}
            )

            payload = manager._load_heartbeat_memory(str(workspace))
            by_id = {item["task_id"]: item for item in payload["tasks"]}
            self.assertEqual(stats["exec_calls"], 3)
            self.assertLessEqual(active["max"], 3)
            self.assertEqual(by_id["task-1"]["status"], "done")
            self.assertEqual(by_id["task-2"]["status"], "done")
            self.assertEqual(by_id["task-3"]["status"], "done")
            self.assertEqual(by_id["task-4"]["status"], "waiting_input")

            sent_msg = ""
            entries = manager._load_recent_entries(str(workspace), pool=BEAT_RECENT_POOL)
            snapshots = [e for e in entries if str(e.get("topic") or "") == "心跳规划与执行"]
            self.assertTrue(snapshots)
            latest = snapshots[-1]
            snap = latest.get("heartbeat_execution_snapshot") if isinstance(latest.get("heartbeat_execution_snapshot"), dict) else {}
            self.assertTrue(bool(snap.get("parallel_used")))
            self.assertEqual(int(snap.get("parallel_branch_count") or 0), 4)
            self.assertEqual(int(snap.get("serial_branch_count") or 0), 0)
            self.assertEqual(len(snap.get("deferred_task_ids") or []), 1)

            # 验证可见性：每轮消息里要包含并行情况与 defer 信息
            sent_msgs = []
            manager._send_private_message = lambda cfg, text, **kwargs: sent_msgs.append(text) or True
            manager._run_heartbeat_once(
                {"workspace_root": str(workspace), "agent_timeout": 90},
                {"enabled": True, "message": "fallback", "receive_id": "u", "receive_id_type": "open_id", "max_parallel_branches": 3, "force_model_planner": True}
            )
            self.assertTrue(sent_msgs)
            sent_msg = sent_msgs[-1]
            self.assertIn("## 本轮心跳", sent_msg)
            self.assertIn("并行 3 路", sent_msg)
            self.assertIn("## 延后", sent_msg)

    def test_long_task_due_time_not_advanced_without_touch(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            manager._save_heartbeat_long_tasks(str(workspace), {
                "version": 1,
                "updated_at": "",
                "tasks": [
                    {
                        "task_id": "long-1",
                        "kind": "reminder",
                        "schedule_type": "daily",
                        "schedule_value": "09:00",
                        "time_window": "",
                        "timezone": "Asia/Shanghai",
                        "enabled": True,
                        "title": "每日提醒",
                        "detail": "提醒",
                        "created_at": "2026-03-07 10:00:00",
                        "updated_at": "2026-03-07 10:00:00",
                        "last_run_at": "",
                        "next_due_at": "2026-03-07 09:00:00",
                        "last_result": ""
                    }
                ]
            })
            plan = manager._default_heartbeat_plan(str(workspace))
            manager._apply_heartbeat_plan(str(workspace), plan, "", branch_results=[])

            long_store = manager._load_heartbeat_long_tasks(str(workspace))
            task = long_store["tasks"][0]
            self.assertEqual(task["next_due_at"], "2026-03-07 09:00:00")
            self.assertEqual(task.get("last_run_at") or "", "")

    def test_human_preview_text_uses_ellipsis_instead_of_hard_cut(self):
        manager = MemoryManager(config_provider=lambda: {}, run_model_fn=lambda *_: ("", False))
        text = "执行 Phase 1.2：在 飞书与记忆约定 文档中补充后续规则，然后继续检查第二份治理文档是否需要同步更新以及是否存在遗漏项"
        preview = manager._human_preview_text(text, limit=40)
        self.assertTrue(preview.endswith("…") or preview.endswith("。"))
        self.assertLessEqual(len(preview), 40)

    def test_truncate_heartbeat_message_adds_notice(self):
        manager = MemoryManager(config_provider=lambda: {}, run_model_fn=lambda *_: ("", False))
        long_text = "A" * 4100
        truncated = manager._truncate_heartbeat_message_for_send(long_text)
        self.assertLessEqual(len(truncated), 4000)
        self.assertIn("消息已截断", truncated)

    def test_heartbeat_send_path_keeps_markdown_summary_without_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace), "agent_timeout": 60},
                run_model_fn=lambda *_: ("", False),
            )

            long_markdown = "## 本轮心跳\n- " + ("A" * 4500)
            sent = {}
            manager._plan_heartbeat_action = lambda *args, **kwargs: {"user_message": "本轮心跳", "task_groups": [], "updates": {}}
            manager._execute_heartbeat_plan = lambda *args, **kwargs: (long_markdown, [])
            manager._apply_heartbeat_plan = lambda *args, **kwargs: None
            manager._persist_heartbeat_snapshot_to_recent = lambda *args, **kwargs: None
            manager._check_and_perform_restart = lambda *_: None

            def fake_send(cfg: dict, text: str, **kwargs) -> bool:
                sent["text"] = text
                return True

            manager._send_private_message = fake_send
            manager._continue_reflective_tell_user = lambda *args, **kwargs: ("", None)

            manager._run_heartbeat_once(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "message": "fallback", "receive_id": "u", "receive_id_type": "open_id"},
            )

            self.assertIn(long_markdown, sent.get("text") or "")
            self.assertNotIn("消息已截断", sent.get("text") or "")

    def test_heartbeat_round_no_longer_pushes_talk_intent_into_self_mind_main_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            planner_calls = {"count": 0}

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                if "JSON Schema" in prompt:
                    planner_calls["count"] += 1
                    if planner_calls["count"] == 1:
                        return json.dumps(
                            {
                                "chosen_mode": "short_task",
                                "execution_mode": "single",
                                "reason": "先把这轮文档整理收口",
                                "user_message": "本轮先把文档整理收口。",
                                "tell_user_candidate": "我刚把这轮文档整理到了一个可复用版本。",
                                "tell_user_reason": "这轮形成了一个值得自然同步给用户的阶段成果。",
                                "tell_user_type": "result_share",
                                "tell_user_priority": 80,
                                "task_groups": [
                                    {
                                        "group_id": "g1",
                                        "branches": [
                                            {
                                                "branch_id": "b1",
                                                "prompt": "执行一次文档整理",
                                                "selected_task_ids": ["task-1"],
                                                "complete_task_ids": ["task-1"],
                                                "can_run_parallel": False,
                                            }
                                        ],
                                    }
                                ],
                                "updates": {"complete_task_ids": ["task-1"], "defer_task_ids": [], "touch_long_task_ids": []},
                            },
                            ensure_ascii=False,
                        ), True
                    return json.dumps(
                        {
                            "chosen_mode": "status",
                            "execution_mode": "defer",
                            "reason": "本轮没有新的高优先级任务",
                            "user_message": "本轮先观察一下。",
                            "task_groups": [],
                            "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []},
                        },
                        ensure_ascii=False,
                    ), True
                return "已完成文档整理", True

            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace), "agent_timeout": 60}, run_model_fn=fake_model)
            manager._save_heartbeat_memory(str(workspace), {
                "version": 1,
                "updated_at": "",
                "tasks": [
                    {
                        "task_id": "task-1",
                        "status": "pending",
                        "title": "整理文档",
                        "detail": "整理一轮文档并收口",
                        "created_at": "",
                        "updated_at": "",
                        "priority": "medium",
                        "source": "conversation",
                        "source_memory_id": "",
                        "trigger_hint": "conversation",
                        "due_at": "",
                        "tags": [],
                        "last_result": "",
                    }
                ],
                "notes": [],
            })

            sent_texts = []
            manager._send_private_message = lambda cfg, text, **kwargs: sent_texts.append(text) or True

            runtime_cfg = {
                "workspace_root": str(workspace),
                "agent_timeout": 60,
                "tell_user_receive_id": "talk-u",
                "tell_user_receive_id_type": "open_id",
            }
            heartbeat_cfg = {
                "enabled": True,
                "message": "fallback",
                "receive_id": "hb-u",
                "receive_id_type": "open_id",
                "proactive_talk": {"enabled": True, "defer_if_recent_talk_seconds": 0, "min_interval_seconds": 0},
            }

            manager._run_heartbeat_once(runtime_cfg, heartbeat_cfg)
            legacy_intents = [path for path in workspace.rglob("*talk_intent*.json")]
            self.assertEqual(legacy_intents, [])
            beat_recent = manager.get_recent_entries(str(workspace), pool="beat")
            self.assertTrue(beat_recent)
            self.assertTrue(any("本轮先把文档整理收口" in text or "已完成文档整理" in text for text in sent_texts))


if __name__ == "__main__":
    unittest.main()
