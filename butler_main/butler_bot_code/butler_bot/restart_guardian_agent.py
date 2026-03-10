# -*- coding: utf-8 -*-
"""Restart guardian agent for butler_bot self-upgrade restarts.

This process is launched as a detached helper by heartbeat restart hook.
Responsibilities:
1) Execute restart and verify butler_bot is really alive.
2) Apply fallback recovery flow when restart fails.
3) Persist machine-readable + human-readable reports.
4) Write a compact recent_memory entry so next conversations can learn from failures.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import subprocess
import time
import uuid

from butler_paths import (
    CONFIG_DIR_REL,
    HEARTBEAT_LAST_SENT_REL,
    LOG_DIR_REL,
    MANAGER_PS1_REL,
    RECENT_MEMORY_DIR_REL,
    RESTART_REPORT_DIR_REL,
    RESTART_REQUEST_JSON_REL,
    RUN_DIR_REL,
    resolve_butler_root,
)

RECENT_MEMORY_FILE = "recent_memory.json"
RESTART_REQUESTED_FLAG_REL = RUN_DIR_REL / "restart_requested.flag"
GUARDIAN_PID_FILE_NAME = "restart_guardian.pid"
HEARTBEAT_PID_FILE_NAME = "butler_bot_heartbeat.pid"
HEARTBEAT_WATCHDOG_STATE_FILE_NAME = "heartbeat_watchdog_state.json"
HEARTBEAT_RUN_STATE_FILE_NAME = "heartbeat_run_state.json"
MAIN_PROCESS_STATE_FILE_NAME = "butler_bot_main_state.json"
MAX_RECENT_ITEMS = 10
TRACEBACK_FILE_RE = re.compile(r'File "(?P<path>.+?)", line (?P<line>\d+)', re.IGNORECASE)
HEARTBEAT_HANDOVER_GRACE_SECONDS = 90
HEARTBEAT_MAIN_WATCHDOG_GRACE_SECONDS = 45


def _normalize_workspace_to_project_root(workspace: str | Path) -> Path:
    """若传入的 workspace 为身体层子目录，则规范为 Butler 项目根，避免 manager.ps1 路径错误。"""
    return resolve_butler_root(workspace)


class RestartGuardianAgent:
    def __init__(
        self,
        workspace: str,
        reason: str = "",
        source: str = "heartbeat",
        max_attempts: int = 2,
        command_timeout: int = 120,
        check_interval_seconds: int = 30,
        heartbeat_stale_seconds: int = 240,
        daemon_mode: bool = False,
    ) -> None:
        self.workspace = _normalize_workspace_to_project_root(workspace)
        self.reason = str(reason or "").strip()
        self.source = str(source or "heartbeat").strip() or "heartbeat"
        self.max_attempts = max(1, int(max_attempts or 2))
        self.command_timeout = max(30, int(command_timeout or 120))
        self.check_interval_seconds = max(10, int(check_interval_seconds or 30))
        self.heartbeat_stale_seconds = max(60, int(heartbeat_stale_seconds or 240))
        self.daemon_mode = bool(daemon_mode)
        self.last_recovery_at = 0.0
        self.last_degraded_report_at = 0.0
        self.heartbeat_only_failures = 0
        self.manager_ps1 = self.workspace / MANAGER_PS1_REL
        self.run_dir = self.workspace / RUN_DIR_REL
        self.log_dir = self.workspace / LOG_DIR_REL
        self.report_dir = self.workspace / RESTART_REPORT_DIR_REL
        self.recent_memory_file = self.workspace / RECENT_MEMORY_DIR_REL / RECENT_MEMORY_FILE
        self.heartbeat_last_sent_file = self.workspace / HEARTBEAT_LAST_SENT_REL
        self.restart_json = self.workspace / RESTART_REQUEST_JSON_REL
        self.restart_flag = self.workspace / RESTART_REQUESTED_FLAG_REL
        self.guardian_pid_file = self.run_dir / GUARDIAN_PID_FILE_NAME
        self.heartbeat_pid_file = self.run_dir / HEARTBEAT_PID_FILE_NAME
        self.heartbeat_watchdog_state_file = self.run_dir / HEARTBEAT_WATCHDOG_STATE_FILE_NAME
        self.heartbeat_run_state_file = self.run_dir / HEARTBEAT_RUN_STATE_FILE_NAME
        self.main_process_state_file = self.run_dir / MAIN_PROCESS_STATE_FILE_NAME

    def run(self) -> int:
        if self.daemon_mode:
            return self.run_daemon()
        return self.run_once(reason=self.reason, source=self.source)

    def run_daemon(self) -> int:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if not self._acquire_singleton_lock():
            return 0
        print(
            f"[guardian] 已启动守护巡检: interval={self.check_interval_seconds}s, heartbeat_stale={self.heartbeat_stale_seconds}s, workspace={self.workspace}",
            flush=True,
        )
        try:
            while True:
                trigger_reason = self._consume_restart_markers()
                health_level, details = self._check_health_level()
                healthy = health_level == "ok"
                should_recover = bool(trigger_reason) or (not healthy)

                if should_recover:
                    now = time.time()
                    # Prevent repeated rapid recover loops when startup is still stabilizing.
                    if now - self.last_recovery_at < max(20, self.check_interval_seconds - 5):
                        time.sleep(self.check_interval_seconds)
                        continue
                    reason_parts = []
                    if trigger_reason:
                        reason_parts.append(f"butler请求重启: {trigger_reason}")
                    if not healthy:
                        reason_parts.append("；".join(details) if details else "健康检查失败")
                    reason = " | ".join(reason_parts)[:500]
                    source = "watchdog-restart-request" if trigger_reason else f"watchdog-healthcheck-{health_level}"

                    if (not trigger_reason) and health_level == "heartbeat-only":
                        # Level-1: heartbeat-only recovery. Clear stale/duplicate sidecars and explicitly reattach a fresh one.
                        ok, msg = self._attempt_soft_heartbeat_recovery()
                        if ok:
                            time.sleep(8)
                            post_level, post_details = self._check_health_level()
                            if post_level == "ok":
                                self.heartbeat_only_failures = 0
                                self._persist_soft_recovery_report(
                                    reason=reason,
                                    source="watchdog-soft-heartbeat",
                                    action=msg,
                                    success=True,
                                    post_status="heartbeat restored",
                                )
                                self.last_recovery_at = now
                                time.sleep(self.check_interval_seconds)
                                continue
                            self.heartbeat_only_failures += 1
                            self._persist_degraded_heartbeat_report(
                                reason=f"{reason} | 软恢复后仍异常: {'；'.join(post_details)}",
                                action=msg,
                                details=post_details,
                            )
                            self.last_recovery_at = now
                            time.sleep(self.check_interval_seconds)
                            continue
                        else:
                            self.heartbeat_only_failures += 1
                            self._persist_degraded_heartbeat_report(
                                reason=f"{reason} | 软恢复未执行: {msg}",
                                action=msg,
                                details=details,
                            )
                            self.last_recovery_at = now
                            time.sleep(self.check_interval_seconds)
                            continue

                    self.run_once(reason=reason, source=source)
                    self.last_recovery_at = now
                    self.heartbeat_only_failures = 0

                time.sleep(self.check_interval_seconds)
        finally:
            self._release_singleton_lock()

    def run_once(self, reason: str, source: str) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report: dict = {
            "timestamp": now,
            "workspace": str(self.workspace),
            "source": str(source or self.source or "watchdog").strip(),
            "reason": str(reason or self.reason or "").strip(),
            "success": False,
            "attempts": [],
            "detected_issues": [],
            "recommendations": [],
            "latest_error_log": "",
            "forensics": {},
        }

        if not self.manager_ps1.exists():
            report["detected_issues"] = [f"未找到 manager.ps1: {self.manager_ps1}"]
            report["recommendations"] = ["确认 ./butler_bot_code/manager.ps1 路径正确并存在。"]
            self._persist_report(report)
            self._persist_recent_summary(report)
            return 1

        for attempt in range(1, self.max_attempts + 1):
            attempt_log: dict = {"attempt": attempt, "steps": []}
            self._append_step(attempt_log, "level2-manager-restart", self._run_manager_command("restart", "butler_bot"))
            time.sleep(4)
            status_out, status_ok = self._check_running()
            attempt_log["status_output"] = status_out
            attempt_log["running_after_restart"] = status_ok

            if status_ok:
                report["attempts"].append(attempt_log)
                report["success"] = True
                break

            self._append_step(attempt_log, "level3-pacemaker-stop-all", self._run_manager_command("stop", "--all"))
            time.sleep(2)
            self._append_step(attempt_log, "level3-pacemaker-start", self._run_manager_command("start", "butler_bot"))
            time.sleep(4)
            status_out, status_ok = self._check_running()
            attempt_log["status_output_after_fallback"] = status_out
            attempt_log["running_after_fallback"] = status_ok
            report["attempts"].append(attempt_log)
            if status_ok:
                report["success"] = True
                break

        issues, latest_error_log = self._detect_issues_from_logs()
        report["detected_issues"] = issues
        report["latest_error_log"] = latest_error_log
        report["forensics"] = self._collect_forensics(latest_error_log)
        report["recommendations"] = self._build_recommendations(issues, bool(report.get("success")))

        self._persist_report(report)
        self._persist_recent_summary(report)
        return 0 if report.get("success") else 2

    def _run_manager_command(self, action: str, bot_name: str | None) -> tuple[int, str]:
        if action == "stop" and str(bot_name or "").strip() == "--all":
            return self._run_stop_all_command()
        args = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.manager_ps1),
            str(action),
        ]
        if bot_name:
            args.append(str(bot_name))
        return self._run_command(args, cwd=self.manager_ps1.parent)

    def _run_stop_all_command(self) -> tuple[int, str]:
        command = f"& '{self.manager_ps1}' stop '--all'"
        args = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ]
        return self._run_command(args, cwd=self.manager_ps1.parent)

    def _run_command(self, args: list[str], cwd: Path) -> tuple[int, str]:
        try:
            env = os.environ.copy()
            env["BUTLER_GUARDIAN_CALL"] = "1"
            proc = subprocess.run(
                args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.command_timeout,
                env=env,
            )
            output = "\n".join([(proc.stdout or "").strip(), (proc.stderr or "").strip()]).strip()
            return proc.returncode, output
        except subprocess.TimeoutExpired:
            return 124, f"命令超时（>{self.command_timeout}s）：{' '.join(args)}"
        except Exception as exc:
            return 1, f"命令异常: {exc}"

    def _check_running(self) -> tuple[str, bool]:
        state_payload = self._read_main_process_state()
        if state_payload:
            state_output, is_running = self._check_main_process_runtime_state(state_payload)
            if is_running:
                return state_output, True
            legacy_output, legacy_running = self._check_running_via_manager_status()
            if legacy_running:
                return legacy_output, True
            return state_output, False
        return self._check_running_via_manager_status()

    def _check_running_via_manager_status(self) -> tuple[str, bool]:
        code, output = self._run_manager_command("status", None)
        normalized = str(output or "")
        is_running = code == 0 and ("butler_bot" in normalized and "PID=" in normalized)
        if is_running:
            return normalized, True
        detail = normalized.strip() if normalized.strip() else "未检测到 butler_bot 运行状态"
        return f"对话主进程未运行：{detail}", False

    def _check_health_level(self) -> tuple[str, list[str]]:
        issues: list[str] = []
        running_detail, running = self._check_running()
        if not running:
            issues.append(running_detail or "对话主进程未运行")

        hb_ok, hb_issue = self._check_heartbeat_health()
        if not hb_ok and hb_issue:
            issues.append(hb_issue)

        if running and hb_ok:
            return "ok", []
        if running and not hb_ok:
            return "heartbeat-only", issues
        return "main-down", issues

    def _attempt_soft_heartbeat_recovery(self) -> tuple[bool, str]:
        process_ids = self._list_heartbeat_process_ids()
        if self.heartbeat_pid_file.exists():
            try:
                pid = int(self.heartbeat_pid_file.read_text(encoding="utf-8").strip())
                if pid > 0:
                    process_ids.append(pid)
            except Exception:
                pass
        process_ids = sorted({int(pid) for pid in process_ids if int(pid) > 0})

        stopped: list[int] = []
        failures: list[str] = []
        for pid in process_ids:
            if not self._pid_alive(pid):
                continue
            if sys.platform == "win32":
                code, output = self._run_command(["taskkill", "/PID", str(pid), "/T", "/F"], cwd=self.workspace)
                if code == 0 or (output and "not found" in output.lower()):
                    stopped.append(pid)
                    continue
                failures.append(f"PID={pid}: {self._truncate(output, 120)}")
                continue
            try:
                os.kill(pid, 15)
                stopped.append(pid)
            except ProcessLookupError:
                stopped.append(pid)
            except Exception as exc:
                failures.append(f"PID={pid}: {exc}")

        try:
            if self.heartbeat_pid_file.exists():
                self.heartbeat_pid_file.unlink()
        except Exception:
            pass

        code, output = self._run_manager_command("start", "butler_bot")
        if code == 0:
            detail = f"已清理 heartbeat 进程 {stopped}" if stopped else "未发现存活 heartbeat 进程"
            return True, f"{detail}，并执行 manager start butler_bot 重新挂载 sidecar"

        failure_text = "; ".join(failures[:3])
        base = f"manager start butler_bot 失败: {self._truncate(output, 160)}"
        if failure_text:
            base = f"{base} | 清理失败: {failure_text}"
        return False, base

    def _persist_soft_recovery_report(self, reason: str, source: str, action: str, success: bool, post_status: str) -> None:
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "workspace": str(self.workspace),
            "source": source,
            "reason": reason,
            "success": bool(success),
            "attempts": [
                {
                    "attempt": 1,
                    "steps": [
                        {
                            "name": "level1-soft-heartbeat-restart",
                            "exit_code": 0 if success else 1,
                            "output": self._truncate(action, 400),
                        }
                    ],
                }
            ],
            "detected_issues": [] if success else ["心跳软恢复失败"],
            "recommendations": [post_status] if post_status else [],
            "latest_error_log": "",
            "forensics": self._collect_forensics(""),
        }
        self._persist_report(report)
        self._persist_recent_summary(report)

    def _persist_degraded_heartbeat_report(self, reason: str, action: str, details: list[str]) -> None:
        now = time.time()
        if now - self.last_degraded_report_at < 300:
            return
        self.last_degraded_report_at = now
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "workspace": str(self.workspace),
            "source": "watchdog-heartbeat-degraded",
            "reason": reason,
            "success": False,
            "attempts": [
                {
                    "attempt": 1,
                    "steps": [
                        {
                            "name": "level1-soft-heartbeat-restart",
                            "exit_code": 1,
                            "output": self._truncate(action, 400),
                        }
                    ],
                }
            ],
            "detected_issues": [str(x) for x in (details or [])[:5]] or ["heartbeat 软恢复后仍异常"],
            "recommendations": [
                "暂不重启主进程，避免对话链路跟着抖动。",
                "优先检查 heartbeat 子进程退出原因与 heartbeat_last_sent.json 更新时间。",
            ],
            "latest_error_log": "",
            "forensics": self._collect_forensics(""),
        }
        self._persist_report(report)
        self._persist_recent_summary(report)

    def _collect_forensics(self, latest_error_log: str) -> dict:
        forensics: dict = {
            "error_log_tail": "",
            "runtime_log_tail": "",
            "heartbeat_log_tail": "",
            "traceback_frames": [],
            "recent_code_changes": [],
        }

        latest_err = Path(latest_error_log) if latest_error_log else self._latest_log("*.err.log")
        if latest_err and latest_err.exists():
            tail = self._read_tail(latest_err, max_lines=180)
            forensics["error_log_tail"] = self._truncate(tail, 6000)
            forensics["traceback_frames"] = self._extract_traceback_frames(tail)

        latest_runtime = self._latest_log("butler_bot_*.log")
        if latest_runtime and latest_runtime.exists():
            forensics["runtime_log_tail"] = self._truncate(self._read_tail(latest_runtime, max_lines=120), 4000)

        latest_hb = self._latest_log("butler_bot_heartbeat_*.log")
        if latest_hb and latest_hb.exists():
            forensics["heartbeat_log_tail"] = self._truncate(self._read_tail(latest_hb, max_lines=120), 4000)

        forensics["recent_code_changes"] = self._collect_recent_code_changes(hours=24, limit=20)
        return forensics

    def _latest_log(self, pattern: str) -> Path | None:
        if not self.log_dir.exists():
            return None
        files = sorted(self.log_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return files[0] if files else None

    def _extract_traceback_frames(self, tail: str) -> list[dict]:
        frames: list[dict] = []
        for line in (tail or "").splitlines():
            m = TRACEBACK_FILE_RE.search(line)
            if not m:
                continue
            raw_path = str(m.group("path") or "").strip()
            if not raw_path:
                continue
            try:
                line_no = int(str(m.group("line") or "0"))
            except Exception:
                line_no = 0
            p = Path(raw_path)
            if not p.is_absolute():
                p = (self.workspace / p).resolve()
            code_hint = self._read_code_hint(p, line_no)
            frames.append(
                {
                    "file": str(p),
                    "line": line_no,
                    "code_hint": code_hint,
                }
            )
            if len(frames) >= 8:
                break
        return frames

    def _read_code_hint(self, path: Path, line_no: int, context: int = 1) -> str:
        if not path.exists() or line_no <= 0:
            return ""
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return ""
        idx = max(0, min(len(lines) - 1, line_no - 1))
        start = max(0, idx - context)
        end = min(len(lines), idx + context + 1)
        snippet = []
        for i in range(start, end):
            marker = ">" if i == idx else " "
            snippet.append(f"{marker} {i+1}: {lines[i]}")
        return self._truncate("\n".join(snippet), 800)

    def _collect_recent_code_changes(self, hours: int = 24, limit: int = 20) -> list[dict]:
        base = self.workspace / "scripts" / "butler_bot"
        if not base.exists():
            return []
        cutoff = datetime.now().timestamp() - max(1, hours) * 3600
        exts = {".py", ".ps1", ".json", ".md"}
        candidates: list[Path] = []
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in exts:
                continue
            if any(part in {"logs", "run", "__pycache__"} for part in p.parts):
                continue
            try:
                if p.stat().st_mtime >= cutoff:
                    candidates.append(p)
            except Exception:
                continue
        candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        out: list[dict] = []
        for p in candidates[:limit]:
            try:
                mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                mtime = ""
            try:
                rel = p.relative_to(self.workspace)
                rel_text = str(rel)
            except Exception:
                rel_text = str(p)
            out.append({"path": rel_text.replace("\\", "/"), "modified_at": mtime})
        return out

    def _check_heartbeat_health(self) -> tuple[bool, str]:
        watchdog_state = self._read_heartbeat_watchdog_state()
        cooldown_until = float(watchdog_state.get("cooldown_until_epoch") or 0.0)
        watchdog_mode = str(watchdog_state.get("state") or "").strip().lower()
        if watchdog_mode == "cooldown" and cooldown_until > time.time():
            return True, ""

        heartbeat_pids = self._list_heartbeat_process_ids()
        heartbeat_alive = bool(heartbeat_pids)
        coordinated, _ = self._is_main_watchdog_recovering_heartbeat(watchdog_state, heartbeat_alive)
        if coordinated:
            return True, ""

        if len(heartbeat_pids) > 1:
            return False, f"检测到重复 heartbeat 进程: {', '.join(str(pid) for pid in heartbeat_pids[:6])}"

        run_state_issue = self._check_heartbeat_run_state_health(heartbeat_pids)
        if run_state_issue:
            return False, run_state_issue

        if not self.heartbeat_last_sent_file.exists():
            if heartbeat_alive:
                return True, ""
            return False, "心跳时间戳缺失（heartbeat_last_sent.json 不存在）"

        try:
            payload = json.loads(self.heartbeat_last_sent_file.read_text(encoding="utf-8"))
        except Exception:
            if heartbeat_alive:
                return True, ""
            return False, "心跳时间戳读取失败"

        ts = str(
            (payload or {}).get("last_activity_at")
            or (payload or {}).get("last_sent_at")
            or (payload or {}).get("timestamp")
            or ""
        ).strip()
        if not ts:
            if heartbeat_alive:
                return True, ""
            return False, "心跳时间戳为空"
        try:
            last_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except Exception:
            if heartbeat_alive:
                return True, ""
            return False, f"心跳时间格式异常: {ts}"

        now = datetime.now()
        delta = now - last_dt
        if delta > timedelta(seconds=self.heartbeat_stale_seconds):
            coordinated, _ = self._is_main_watchdog_recovering_heartbeat(watchdog_state, heartbeat_alive)
            if coordinated:
                return True, ""
            return False, f"心跳超时: {int(delta.total_seconds())}s > {self.heartbeat_stale_seconds}s"
        return True, ""

    def _check_heartbeat_run_state_health(self, heartbeat_pids: list[int]) -> str:
        run_state = self._read_heartbeat_run_state()
        if not run_state:
            return ""

        state = str(run_state.get("state") or "").strip().lower()
        phase = str(run_state.get("phase") or "").strip().lower()
        updated_at = str(run_state.get("updated_at") or "").strip()
        run_pid = 0
        try:
            run_pid = int(run_state.get("heartbeat_pid") or 0)
        except Exception:
            run_pid = 0

        if heartbeat_pids and run_pid > 0 and run_pid not in heartbeat_pids:
            return f"heartbeat 状态漂移: run_state_pid={run_pid}, live_pids={','.join(str(pid) for pid in heartbeat_pids[:4])}"

        if not updated_at:
            return ""
        try:
            updated_dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return ""

        age_seconds = int((datetime.now() - updated_dt).total_seconds())
        if state == "running" and age_seconds > self.heartbeat_stale_seconds:
            phase_text = phase or "unknown"
            return f"heartbeat 运行状态卡住: phase={phase_text}, age={age_seconds}s"
        return ""

    def _is_main_watchdog_recovering_heartbeat(self, watchdog_state: dict, heartbeat_alive: bool) -> tuple[bool, str]:
        mode = str((watchdog_state or {}).get("state") or "").strip().lower()
        now = time.time()
        restart_inhibit_until = self._heartbeat_restart_handover_deadline(watchdog_state)

        if mode == "restart-requested" and restart_inhibit_until > now:
            remaining = max(0, int(restart_inhibit_until - now))
            return True, f"guardian handover in progress ({remaining}s)"

        if heartbeat_alive:
            return False, ""

        updated_at = str((watchdog_state or {}).get("updated_at") or "").strip()
        if not updated_at:
            return False, ""
        try:
            updated_dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return False, ""
        age_seconds = (datetime.now() - updated_dt).total_seconds()
        if mode in {"crashed", "restarting"} and age_seconds <= HEARTBEAT_MAIN_WATCHDOG_GRACE_SECONDS:
            return True, f"main watchdog recovery window ({int(age_seconds)}s)"
        return False, ""

    def _heartbeat_restart_handover_deadline(self, watchdog_state: dict) -> float:
        try:
            return float((watchdog_state or {}).get("restart_inhibit_until_epoch") or 0.0)
        except Exception:
            return 0.0

    def _read_main_process_state(self) -> dict:
        if not self.main_process_state_file.exists():
            return {}
        try:
            payload = json.loads(self.main_process_state_file.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _check_main_process_runtime_state(self, payload: dict) -> tuple[str, bool]:
        pid = 0
        try:
            pid = int(payload.get("pid") or 0)
        except Exception:
            pid = 0
        state = str(payload.get("state") or "").strip().lower()
        updated_at = str(payload.get("updated_at") or "").strip()
        started_at = str(payload.get("started_at") or "").strip()
        freshness_limit = max(90, self.check_interval_seconds * 3)

        last_dt = None
        if updated_at:
            try:
                last_dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
            except Exception:
                last_dt = None

        is_alive = pid > 0 and self._pid_alive(pid)
        is_fresh = bool(last_dt) and (datetime.now() - last_dt) <= timedelta(seconds=freshness_limit)
        if state == "running" and is_alive and is_fresh:
            suffix = f", started_at={started_at}" if started_at else ""
            return f"对话主进程运行中 (PID={pid}, updated_at={updated_at}{suffix})", True

        reasons: list[str] = []
        if state and state != "running":
            reasons.append(f"state={state}")
        if pid <= 0:
            reasons.append("pid 缺失")
        elif not is_alive:
            reasons.append(f"PID={pid} 不存活")
        if updated_at:
            if last_dt is None:
                reasons.append(f"updated_at 格式异常: {updated_at}")
            elif not is_fresh:
                age = int((datetime.now() - last_dt).total_seconds())
                reasons.append(f"状态心跳过期 {age}s")
        else:
            reasons.append("updated_at 缺失")
        detail = "；".join(reasons) if reasons else "状态未知"
        return f"对话主进程未运行：{detail}", False

    def _read_heartbeat_watchdog_state(self) -> dict:
        if not self.heartbeat_watchdog_state_file.exists():
            return {}
        try:
            payload = json.loads(self.heartbeat_watchdog_state_file.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _read_heartbeat_run_state(self) -> dict:
        if not self.heartbeat_run_state_file.exists():
            return {}
        try:
            payload = json.loads(self.heartbeat_run_state_file.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _heartbeat_pid_alive(self) -> bool:
        if not self.heartbeat_pid_file.exists():
            return False
        try:
            pid = int(self.heartbeat_pid_file.read_text(encoding="utf-8").strip())
        except Exception:
            return False
        return self._pid_alive(pid)

    def _list_heartbeat_process_ids(self) -> list[int]:
        if sys.platform != "win32":
            if self.heartbeat_pid_file.exists():
                try:
                    pid = int(self.heartbeat_pid_file.read_text(encoding="utf-8").strip())
                    return [pid] if pid > 0 and self._pid_alive(pid) else []
                except Exception:
                    return []
            return []

        command = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'heartbeat_service_runner\\.py' -and $_.CommandLine -match 'butler_bot_code' } | "
            "Select-Object -ExpandProperty ProcessId | Out-String"
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=20,
            )
        except Exception:
            return []

        ids: list[int] = []
        for raw in str(proc.stdout or "").splitlines():
            text = str(raw or "").strip()
            if not text:
                continue
            try:
                pid = int(text)
            except Exception:
                continue
            if pid > 0 and self._pid_alive(pid):
                ids.append(pid)
        return sorted(set(ids))

    def _consume_restart_markers(self) -> str:
        reason = ""
        if self.restart_json.exists():
            try:
                payload = json.loads(self.restart_json.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    reason = str(payload.get("reason") or "").strip()
                elif isinstance(payload, str):
                    reason = payload.strip()
            except Exception:
                reason = ""
        if self.restart_json.exists() or self.restart_flag.exists():
            try:
                if self.restart_json.exists():
                    self.restart_json.unlink()
                if self.restart_flag.exists():
                    self.restart_flag.unlink()
            except Exception:
                pass
            return reason or "收到重启标记"
        return ""

    def _acquire_singleton_lock(self) -> bool:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if self.guardian_pid_file.exists():
            try:
                old_pid = int(self.guardian_pid_file.read_text(encoding="utf-8").strip())
            except Exception:
                old_pid = 0
            if old_pid > 0 and self._pid_alive(old_pid):
                print(f"[guardian] 守护已在运行，PID={old_pid}", flush=True)
                return False
        self.guardian_pid_file.write_text(str(os.getpid()), encoding="utf-8")
        return True

    def _release_singleton_lock(self) -> None:
        try:
            if self.guardian_pid_file.exists():
                self.guardian_pid_file.unlink()
        except Exception:
            pass

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _append_step(self, attempt_log: dict, name: str, result: tuple[int, str]) -> None:
        code, output = result
        attempt_log.setdefault("steps", []).append(
            {
                "name": name,
                "exit_code": int(code),
                "output": self._truncate(output, 1200),
            }
        )

    def _detect_issues_from_logs(self) -> tuple[list[str], str]:
        if not self.log_dir.exists():
            return ["日志目录不存在，无法诊断启动失败详情。"], ""

        err_logs = sorted(self.log_dir.glob("*.err.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not err_logs:
            return ["未找到 err 日志，建议检查启动脚本输出。"], ""

        latest = err_logs[0]
        tail = self._read_tail(latest, max_lines=120)
        issues: list[str] = []
        low = tail.lower()

        if "配置文件不存在" in tail:
            issues.append("启动失败：配置文件不存在或路径错误。")
        if "未找到 cursor cli" in low:
            issues.append("启动失败：未找到 Cursor CLI，导致模型调用不可用。")
        if "execution policy" in low or "无法加载文件" in tail:
            issues.append("PowerShell 执行策略/脚本权限问题。")
        if "permission" in low or "拒绝访问" in tail:
            issues.append("权限不足导致启动或写文件失败。")
        if "traceback" in low:
            issues.append("Python 运行时异常（Traceback）。")
        if "启动失败，请查看 err 日志" in tail and not issues:
            issues.append("manager 启动检查失败，主进程在短时间内退出。")
        if not issues:
            issues.append("未匹配到常见错误模式，请查看最新 err 日志人工确认。")

        return issues, str(latest)

    def _build_recommendations(self, issues: list[str], success: bool) -> list[str]:
        recs: list[str] = []
        if any("配置文件不存在" in x for x in issues):
            recs.append(f"确认 `./{CONFIG_DIR_REL.as_posix()}/butler_bot.json` 存在且字段完整。")
        if any("Cursor CLI" in x for x in issues):
            recs.append("确认 Cursor Agent CLI 已安装，且 `%LOCALAPPDATA%/cursor-agent/versions/dist-package/cursor-agent.cmd` 可访问。")
        if any("执行策略" in x or "权限" in x for x in issues):
            recs.append("在管理员 PowerShell 下验证执行策略与目录写权限。")
        if any("Traceback" in x for x in issues):
            recs.append("优先阅读最新 err 日志中的 Traceback，修复后再触发自我升级。")
        # Evidence-driven recommendation from traceback frames and recent file edits.
        try:
            latest_err = self._latest_log("*.err.log")
            if latest_err and latest_err.exists():
                frames = self._extract_traceback_frames(self._read_tail(latest_err, max_lines=180))
                if frames:
                    top = frames[0]
                    recs.append(f"优先检查报错代码位置：{top.get('file')}:{top.get('line')}")
        except Exception:
            pass
        if not recs:
            recs.append("若再次失败，优先检查最新 err 日志和 manager.ps1 status 输出。")
        if success:
            recs.append("本次已恢复运行，建议将上述问题纳入下次升级前检查清单。")
        return recs[:6]

    def _persist_report(self, report: dict) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        date_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = self.report_dir / f"restart_guardian_{date_tag}.json"
        md_path = self.report_dir / f"restart_guardian_{date_tag}.md"
        latest_json_path = self.report_dir / "restart_guardian_latest.json"
        latest_md_path = self.report_dir / "restart_guardian_latest.md"

        json_text = json.dumps(report, ensure_ascii=False, indent=2)
        md_text = self._render_report_markdown(report, json_path)

        json_path.write_text(json_text, encoding="utf-8")
        md_path.write_text(md_text, encoding="utf-8")
        latest_json_path.write_text(json_text, encoding="utf-8")
        latest_md_path.write_text(md_text, encoding="utf-8")

    def _persist_recent_summary(self, report: dict) -> None:
        self.recent_memory_file.parent.mkdir(parents=True, exist_ok=True)
        entries: list[dict] = []
        if self.recent_memory_file.exists():
            try:
                raw = json.loads(self.recent_memory_file.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    entries = raw
            except Exception:
                entries = []

        issues = report.get("detected_issues") if isinstance(report.get("detected_issues"), list) else []
        recs = report.get("recommendations") if isinstance(report.get("recommendations"), list) else []
        status_text = "成功" if report.get("success") else "失败"
        summary_lines = [
            f"自我升级守护重启{status_text}。",
            f"触发来源：{report.get('source') or 'heartbeat'}。",
        ]
        if report.get("reason"):
            summary_lines.append(f"触发原因：{report.get('reason')}。")
        if issues:
            summary_lines.append("主要问题：" + "；".join(str(x) for x in issues[:3]))

        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "topic": "自我升级守护报告",
            "summary": " ".join(summary_lines),
            "next_actions": [str(x) for x in recs[:3]],
            "heartbeat_tasks": [],
            "heartbeat_long_term_tasks": [],
            "long_term_candidate": {
                "should_write": True,
                "title": "自我升级失败模式与规避",
                "summary": " ".join(summary_lines),
                "keywords": ["自我升级", "重启", "守护", "故障复盘"],
            },
            "memory_id": str(uuid.uuid4()),
            "status": "completed",
        }

        entries.append(entry)
        if len(entries) > MAX_RECENT_ITEMS:
            entries = entries[-MAX_RECENT_ITEMS:]
        self.recent_memory_file.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_tail(self, path: Path, max_lines: int = 120) -> str:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return ""
        return "\n".join(lines[-max(1, max_lines):])

    def _render_report_markdown(self, report: dict, json_path: Path) -> str:
        lines = [
            "# 自我升级守护报告",
            "",
            f"- 时间: {report.get('timestamp', '')}",
            f"- 结果: {'成功' if report.get('success') else '失败'}",
            f"- 来源: {report.get('source') or 'heartbeat'}",
            f"- 原因: {report.get('reason') or '(未提供)'}",
            f"- 报告JSON: `{json_path}`",
            "",
            "## 检测到的问题",
        ]
        issues = report.get("detected_issues") if isinstance(report.get("detected_issues"), list) else []
        if issues:
            lines.extend([f"- {x}" for x in issues[:8]])
        else:
            lines.append("- 无")

        lines.append("")
        lines.append("## 修复建议")
        recs = report.get("recommendations") if isinstance(report.get("recommendations"), list) else []
        if recs:
            lines.extend([f"- {x}" for x in recs[:8]])
        else:
            lines.append("- 无")

        lines.append("")
        lines.append("## 尝试记录")
        attempts = report.get("attempts") if isinstance(report.get("attempts"), list) else []
        if not attempts:
            lines.append("- 无")
        else:
            for item in attempts:
                attempt_id = item.get("attempt")
                lines.append(f"- 第 {attempt_id} 次尝试")
                steps = item.get("steps") if isinstance(item.get("steps"), list) else []
                for step in steps[:6]:
                    lines.append(
                        f"  - {step.get('name')}: exit={step.get('exit_code')} | {self._truncate(step.get('output') or '', 120)}"
                    )
        latest_error_log = str(report.get("latest_error_log") or "").strip()
        if latest_error_log:
            lines.append("")
            lines.append(f"- 最新错误日志: `{latest_error_log}`")

        forensics = report.get("forensics") if isinstance(report.get("forensics"), dict) else {}
        frames = forensics.get("traceback_frames") if isinstance(forensics.get("traceback_frames"), list) else []
        recent_changes = forensics.get("recent_code_changes") if isinstance(forensics.get("recent_code_changes"), list) else []
        if frames or recent_changes:
            lines.append("")
            lines.append("## 抢救诊断证据")
            if frames:
                lines.append("- Traceback 指向代码：")
                for item in frames[:5]:
                    lines.append(f"  - `{item.get('file')}:{item.get('line')}`")
            if recent_changes:
                lines.append("- 近 24h 代码改动（Top 8）：")
                for item in recent_changes[:8]:
                    lines.append(f"  - `{item.get('path')}` @ {item.get('modified_at')}")
        return "\n".join(lines).strip() + "\n"

    def _truncate(self, text: str, limit: int) -> str:
        value = str(text or "").strip()
        if len(value) <= limit:
            return value
        return value[: limit - 1].rstrip() + "..."


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Butler restart guardian agent")
    parser.add_argument("--workspace", required=True, help="Workspace root path")
    parser.add_argument("--reason", default="", help="Restart reason")
    parser.add_argument("--source", default="heartbeat", help="Trigger source")
    parser.add_argument("--max-attempts", type=int, default=2, help="Max recovery attempts")
    parser.add_argument("--timeout", type=int, default=120, help="Per command timeout in seconds")
    parser.add_argument("--daemon", action="store_true", help="Run as persistent watchdog")
    parser.add_argument("--check-interval", type=int, default=30, help="Watchdog check interval (seconds)")
    parser.add_argument("--heartbeat-stale-seconds", type=int, default=240, help="Heartbeat stale threshold (seconds)")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    agent = RestartGuardianAgent(
        workspace=args.workspace,
        reason=args.reason,
        source=args.source,
        max_attempts=args.max_attempts,
        command_timeout=args.timeout,
        check_interval_seconds=args.check_interval,
        heartbeat_stale_seconds=args.heartbeat_stale_seconds,
        daemon_mode=args.daemon,
    )
    return agent.run()


if __name__ == "__main__":
    raise SystemExit(main())
