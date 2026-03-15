"""Guardian 巡检器：评估 butler_main 运行状态。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None  # type: ignore[assignment]


def _parse_datetime(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if psutil is not None:
        return bool(psutil.pid_exists(pid))
    if sys.platform == "win32":
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return str(pid) in (r.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _find_pids_by_cmd_patterns(patterns: list[str]) -> list[int]:
    if psutil is None:
        return []
    pattern_lowers = [p.lower() for p in patterns if p]
    if not pattern_lowers:
        return []
    hits: list[int] = []
    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or []).lower()
            name = str(proc.info.get("name") or "").lower()
            if "python" not in name and "python" not in cmdline:
                continue
            if any(pattern in cmdline for pattern in pattern_lowers):
                hits.append(int(proc.info.get("pid") or 0))
        except (psutil.Error, OSError, ValueError):
            continue
    return sorted([pid for pid in hits if pid > 0])


def _effective_pid(state_pid: int, patterns: list[str]) -> tuple[int, str, list[int]]:
    candidates = _find_pids_by_cmd_patterns(patterns)
    if _is_pid_alive(state_pid):
        return state_pid, "state", candidates
    if candidates:
        return candidates[0], "scan", candidates
    return 0, "none", candidates


def _is_recent(updated_at: datetime | None, max_seconds: int) -> bool:
    if not updated_at:
        return False
    return (datetime.now() - updated_at).total_seconds() <= max_seconds


def inspect_butler_main(butler_root: Path) -> dict:
    """
    巡检 butler_main 状态，返回评估摘要。
    butler_root 通常为 butler_main 目录（含 butler_bot_code 子目录）。
    """
    run_dir = butler_root / "butler_bot_code" / "run"
    project_root = butler_root.parent
    result: dict = {
        "main": {
            "state": "unknown",
            "pid": 0,
            "active_pid": 0,
            "pid_source": "none",
            "candidate_pids": [],
            "updated_at": "",
            "healthy": False,
            "issues": [],
        },
        "heartbeat": {
            "state": "unknown",
            "pid": 0,
            "active_pid": 0,
            "pid_source": "none",
            "candidate_pids": [],
            "updated_at": "",
            "healthy": False,
            "issues": [],
        },
        "guardian_handover": {
            "state": "unknown",
            "pid": 0,
            "updated_at": "",
            "detail": "guardian runs outside Butler",
            "healthy": False,
            "issues": [],
        },
        "overall": {"level": "unhealthy", "healthy": False},
        "summary": "",
        "recommendations": [],
    }

    guardian_pid_path = project_root / "guardian" / "run" / "guardian_bot.pid"
    guardian_snapshot_path = run_dir / "guardian_pid_snapshot.json"
    guardian_pid = 0
    guardian_updated_at = None
    guardian_state = "stopped"
    try:
        if guardian_pid_path.exists():
            guardian_pid = int((guardian_pid_path.read_text(encoding="utf-8") or "").strip() or 0)
            if guardian_pid > 0:
                guardian_state = "running"
    except Exception:
        guardian_pid = 0
    if guardian_snapshot_path.exists():
        try:
            snapshot = json.loads(guardian_snapshot_path.read_text(encoding="utf-8"))
            guardian_updated_at = _parse_datetime(str(snapshot.get("updated_at") or ""))
            if guardian_pid <= 0:
                guardian_pid = int(snapshot.get("guardian_pid") or 0)
            result["guardian_handover"]["updated_at"] = str(snapshot.get("updated_at") or "")
        except Exception:
            result["guardian_handover"]["issues"].append("guardian PID 快照解析失败")
    guardian_alive = _is_pid_alive(guardian_pid)
    guardian_recent = _is_recent(guardian_updated_at, 180) if guardian_updated_at else guardian_alive
    result["guardian_handover"]["pid"] = guardian_pid
    result["guardian_handover"]["state"] = "running" if guardian_alive else guardian_state
    result["guardian_handover"]["healthy"] = guardian_alive and guardian_recent
    if not guardian_alive:
        result["guardian_handover"]["issues"].append("guardian 进程未运行")
    if guardian_updated_at is None:
        result["guardian_handover"]["issues"].append("缺少 guardian PID 快照")
    elif not guardian_recent:
        result["guardian_handover"]["issues"].append("guardian PID 快照超过 180 秒未更新")

    main_state_path = run_dir / "butler_bot_main_state.json"
    if main_state_path.exists():
        try:
            data = json.loads(main_state_path.read_text(encoding="utf-8"))
            pid = int(data.get("pid") or 0)
            updated_at = _parse_datetime(str(data.get("updated_at") or ""))
            result["main"]["state"] = str(data.get("state") or "unknown")
            result["main"]["pid"] = pid
            result["main"]["updated_at"] = str(data.get("updated_at") or "")
            active_pid, source, candidates = _effective_pid(pid, ["butler_bot.py"])
            result["main"]["active_pid"] = active_pid
            result["main"]["pid_source"] = source
            result["main"]["candidate_pids"] = candidates
            alive = _is_pid_alive(active_pid)
            recent = _is_recent(updated_at, 90)
            healthy = alive and recent
            result["main"]["healthy"] = healthy
            if not recent:
                result["main"]["issues"].append("状态文件超过 90 秒未更新")
            if source == "scan":
                result["main"]["issues"].append("状态文件 PID 失效，已切换为进程扫描 PID")
            if len(candidates) > 1:
                result["main"]["issues"].append(f"检测到 {len(candidates)} 个主进程候选，存在重复运行风险")
            if not alive:
                result["main"]["issues"].append("未发现存活主进程")
        except Exception:
            result["main"]["state"] = "error"
            result["main"]["issues"].append("主进程状态文件解析失败")
    else:
        result["main"]["state"] = "no_state_file"
        result["main"]["issues"].append("缺少主进程状态文件")

    hb_state_path = run_dir / "heartbeat_watchdog_state.json"
    hb_run_path = run_dir / "heartbeat_run_state.json"
    if hb_state_path.exists():
        try:
            data = json.loads(hb_state_path.read_text(encoding="utf-8"))
            pid = int(data.get("heartbeat_pid") or 0)
            updated_at = _parse_datetime(str(data.get("updated_at") or ""))
            run_updated_at = None
            run_phase = ""
            run_state = ""
            run_pid = 0
            if hb_run_path.exists():
                try:
                    run_data = json.loads(hb_run_path.read_text(encoding="utf-8"))
                    run_updated_at = _parse_datetime(str(run_data.get("updated_at") or ""))
                    run_phase = str(run_data.get("phase") or "")
                    run_state = str(run_data.get("state") or "")
                    run_pid = int(run_data.get("heartbeat_pid") or 0)
                    if run_pid > 0 and run_pid != pid:
                        pid = run_pid
                except Exception:
                    pass
            result["heartbeat"]["state"] = str(data.get("state") or "unknown")
            result["heartbeat"]["pid"] = pid
            result["heartbeat"]["updated_at"] = str(data.get("updated_at") or "")
            active_pid, source, candidates = _effective_pid(pid, ["heartbeat_service_runner.py"])
            result["heartbeat"]["active_pid"] = active_pid
            result["heartbeat"]["pid_source"] = source
            result["heartbeat"]["candidate_pids"] = candidates
            alive = _is_pid_alive(active_pid)
            running = result["heartbeat"]["state"] in {"running", "starting", "degraded"}
            recent_watchdog = _is_recent(updated_at, 180)
            recent_run = _is_recent(run_updated_at, 300)
            recent = recent_watchdog or recent_run
            healthy = alive and running and recent
            result["heartbeat"]["healthy"] = healthy
            if source == "scan":
                result["heartbeat"]["issues"].append("心跳状态 PID 失效，已切换为进程扫描 PID")
            if not recent_watchdog and recent_run:
                result["heartbeat"]["issues"].append("心跳 watchdog 状态未刷新，但 heartbeat_run_state 仍在更新")
            if not recent:
                result["heartbeat"]["issues"].append("心跳状态与运行态均超过阈值未更新")
            # 调度器(plan)超时：保证提醒任务能被准点调度
            if recent_watchdog and run_updated_at is not None:
                run_age = (datetime.now() - run_updated_at).total_seconds()
                if run_state == "running" and run_phase == "plan" and run_age > 300:
                    result["heartbeat"]["issues"].append(
                        f"调度器(plan)超时（{int(run_age)}s），提醒任务可能无法准点被消费"
                    )
                elif run_state == "running" and run_phase == "execute" and run_age > 600:
                    result["heartbeat"]["issues"].append(
                        f"执行阶段(execute)超时（{int(run_age)}s），可能影响提醒任务投递"
                    )
                elif run_state == "running" and run_phase == "send" and run_age > 180:
                    result["heartbeat"]["issues"].append(
                        f"发送器(send)超时（{int(run_age)}s），提醒消息可能未及时发出"
                    )
                elif run_state == "running" and run_phase in {"plan", "execute"} and run_age > 420:
                    result["heartbeat"]["issues"].append(f"心跳长时间停留在 {run_phase} 阶段（{int(run_age)}s）")
            if str(result["heartbeat"]["state"] or "") == "degraded":
                result["heartbeat"]["issues"].append("心跳最近一轮失败，但 sidecar 仍存活")
            elif not running:
                result["heartbeat"]["issues"].append(f"心跳状态为 {result['heartbeat']['state']}")
            if not alive:
                result["heartbeat"]["issues"].append("未发现存活心跳进程")
        except Exception:
            result["heartbeat"]["state"] = "error"
            result["heartbeat"]["issues"].append("心跳状态文件解析失败")
    else:
        active_pid, source, candidates = _effective_pid(0, ["heartbeat_service_runner.py"])
        result["heartbeat"]["pid"] = 0
        result["heartbeat"]["active_pid"] = active_pid
        result["heartbeat"]["pid_source"] = source
        result["heartbeat"]["candidate_pids"] = candidates
        if active_pid > 0:
            result["heartbeat"]["state"] = "running"
            result["heartbeat"]["healthy"] = True
            result["heartbeat"]["issues"].append("未找到心跳状态文件，已切换为进程扫描模式")
        else:
            result["heartbeat"]["state"] = "stopped"
            result["heartbeat"]["healthy"] = False
            result["heartbeat"]["issues"].append("未发现存活心跳进程")

    main_ok = bool(result["main"]["healthy"])
    heartbeat_ok = bool(result["heartbeat"]["healthy"])
    watchdog_ok = bool(result["guardian_handover"]["healthy"])
    ok_count = sum([main_ok, heartbeat_ok, watchdog_ok])
    if ok_count == 3:
        result["overall"]["level"] = "healthy"
        result["overall"]["healthy"] = True
    elif ok_count >= 1:
        result["overall"]["level"] = "degraded"
        result["overall"]["healthy"] = False
    else:
        result["overall"]["level"] = "unhealthy"
        result["overall"]["healthy"] = False

    if not main_ok:
        result["recommendations"].append("优先确保 butler 主进程状态文件持续刷新，必要时重启 butler_bot")
    if not heartbeat_ok:
        result["recommendations"].append("优先修复心跳 sidecar，保证 heartbeat_watchdog_state 按频率更新")
    hb_issues = result["heartbeat"].get("issues") or []
    if any("调度器" in str(i) for i in hb_issues):
        result["recommendations"].append("调度器超时：检查 planner 负载或网络，必要时 soft-recover 心跳或重启栈")
    if any("发送器" in str(i) for i in hb_issues):
        result["recommendations"].append("发送器超时：检查飞书 API 与 tell_user 配置，确保提醒任务准点被消费")
    if not watchdog_ok:
        result["recommendations"].append("检查 guardian 独立进程，确保外部守护链路正常")

    parts = []
    m = result["main"]
    main_pid = m["active_pid"] or m["pid"]
    parts.append(f"主进程: {m['state']} (PID={main_pid}) {'✓' if m['healthy'] else '✗'}")
    h = result["heartbeat"]
    hb_pid = h["active_pid"] or h["pid"]
    parts.append(f"心跳: {h['state']} (PID={hb_pid}) {'✓' if h['healthy'] else '✗'}")
    g = result["guardian_handover"]
    parts.append(f"守护职责: {g['state']} (PID={g.get('pid') or 0}) {'✓' if g['healthy'] else '✗'}")
    level = result["overall"]["level"]
    icon = "✓" if level == "healthy" else ("△" if level == "degraded" else "✗")
    result["summary"] = f"整体: {level} {icon} | " + " | ".join(parts)
    return result


def format_inspection_report(inspection: dict) -> str:
    """将巡检结果格式化为 Markdown 消息。"""
    main_issues = inspection["main"].get("issues") or []
    heartbeat_issues = inspection["heartbeat"].get("issues") or []
    watchdog_issues = inspection["guardian_handover"].get("issues") or []
    recommendations = inspection.get("recommendations") or []
    lines = [
        "## Guardian 巡检报告",
        "",
        inspection["summary"],
        "",
        "**详情**",
        f"- 主进程: {inspection['main']['state']}, PID={inspection['main'].get('active_pid') or inspection['main']['pid']}, 更新于 {inspection['main']['updated_at']}",
        f"- 心跳: {inspection['heartbeat']['state']}, PID={inspection['heartbeat'].get('active_pid') or inspection['heartbeat']['pid']}, 更新于 {inspection['heartbeat']['updated_at']}",
        f"- 守护职责: {inspection['guardian_handover']['state']}, PID={inspection['guardian_handover'].get('pid') or 0}, 更新于 {inspection['guardian_handover'].get('updated_at') or ''} ({inspection['guardian_handover']['detail']})",
    ]
    if main_issues or heartbeat_issues or watchdog_issues:
        lines.extend(["", "**发现的问题**"])
        for issue in main_issues:
            lines.append(f"- 主进程: {issue}")
        for issue in heartbeat_issues:
            lines.append(f"- 心跳: {issue}")
        for issue in watchdog_issues:
            lines.append(f"- 守护职责: {issue}")
    if recommendations:
        lines.extend(["", "**建议动作**"])
        for rec in recommendations[:3]:
            lines.append(f"- {rec}")
    return "\n".join(lines)
