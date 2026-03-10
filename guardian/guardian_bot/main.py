from __future__ import annotations

import argparse
import os
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from guardian_bot.butler_inspector import format_inspection_report, inspect_butler_main
from guardian_bot.feishu_client import send_private_message
from guardian_bot.feishu_ws_client import start_feishu_ws_in_background
from guardian_bot.runtime import GuardianRuntime


def _default_config_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / "configs" / "guardian_bot.json"


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _send_startup_and_inspection(cfg: dict, workspace_root: Path | None) -> None:
    """启动时发送「Guardian 正在值守」+ 一次巡检评估。"""
    feishu = cfg.get("feishu") or {}
    app_id = str(feishu.get("app_id") or "").strip()
    app_secret = str(feishu.get("app_secret") or "").strip()
    receive_id = str(feishu.get("receive_id") or "").strip()
    receive_id_type = str(feishu.get("receive_id_type") or "open_id").strip() or "open_id"
    if not app_id or not app_secret or not receive_id:
        print("[guardian] 未配置 feishu.app_id/app_secret/receive_id，跳过飞书通知", flush=True)
        return
    msg_lines = ["**Guardian 正在值守**", ""]
    if workspace_root and workspace_root.exists():
        inspection = inspect_butler_main(workspace_root)
        msg_lines.append(format_inspection_report(inspection))
    else:
        msg_lines.append("butler_root 未配置或不存在，跳过巡检。")
    text = "\n".join(msg_lines)
    if send_private_message(app_id, app_secret, text, receive_id, receive_id_type):
        print("[guardian] 已发送启动值守+巡检到飞书", flush=True)
    else:
        print("[guardian] 飞书发送失败", flush=True)


def _send_periodic_inspection(cfg: dict, workspace_root: Path | None) -> None:
    """每 30 分钟体检：发送巡检报告。"""
    feishu = cfg.get("feishu") or {}
    app_id = str(feishu.get("app_id") or "").strip()
    app_secret = str(feishu.get("app_secret") or "").strip()
    receive_id = str(feishu.get("receive_id") or "").strip()
    receive_id_type = str(feishu.get("receive_id_type") or "open_id").strip() or "open_id"
    if not app_id or not app_secret or not receive_id:
        return
    if workspace_root and workspace_root.exists():
        inspection = inspect_butler_main(workspace_root)
        text = format_inspection_report(inspection)
        if send_private_message(app_id, app_secret, text, receive_id, receive_id_type):
            print("[guardian] 已发送 30min 体检到飞书", flush=True)


def _write_pid_snapshot(workspace_root: Path | None, inspection: dict | None) -> None:
    """由 Guardian 维护统一 PID 快照，避免非标准重启链路导致状态文件缺失。"""
    if not workspace_root or not workspace_root.exists() or not isinstance(inspection, dict):
        return
    run_dir = workspace_root / "butler_bot_code" / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    target = run_dir / "guardian_pid_snapshot.json"
    main_block = inspection.get("main") or {}
    heartbeat_block = inspection.get("heartbeat") or {}
    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "writer": "guardian",
        "guardian_pid": int(os.getpid()),
        "main": {
            "state": str(main_block.get("state") or "unknown"),
            "pid": int(main_block.get("active_pid") or main_block.get("pid") or 0),
            "healthy": bool(main_block.get("healthy")),
        },
        "heartbeat": {
            "state": str(heartbeat_block.get("state") or "unknown"),
            "pid": int(heartbeat_block.get("active_pid") or heartbeat_block.get("pid") or 0),
            "healthy": bool(heartbeat_block.get("healthy")),
        },
        "overall": inspection.get("overall") or {},
    }
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def _run_standard_restart(workspace_root: Path | None) -> tuple[bool, str]:
    if not workspace_root:
        return False, "workspace_root is empty"
    manager = workspace_root.parent / "guardian" / "manager.ps1"
    if not manager.exists():
        return False, f"guardian manager not found: {manager}"
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(manager),
                "restart-stack",
            ],
            cwd=str(manager.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        out = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        if len(out) > 1200:
            out = out[-1200:]
        if result.returncode != 0:
            return False, out or f"restart-stack exit={result.returncode}"
        return True, out or "restart-stack done"
    except subprocess.TimeoutExpired:
        return False, "restart-stack timeout >120s"
    except Exception as exc:
        return False, f"restart-stack exception: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Guardian bot runtime")
    parser.add_argument("--config", default=str(_default_config_path()), help="配置文件路径")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    paths = cfg.get("paths") or {}
    runtime_cfg = cfg.get("runtime") or {}
    inbox_dir = Path(str(paths.get("request_inbox") or ""))
    ledger_dir = Path(str(paths.get("ledger_root") or ""))
    workspace_root = Path(str(paths.get("butler_root") or "")) if paths.get("butler_root") else None
    runtime = GuardianRuntime(
        inbox_dir=inbox_dir,
        ledger_dir=ledger_dir,
        workspace_root=workspace_root,
    )
    poll_seconds = max(2, int(runtime_cfg.get("poll_seconds") or 10))
    health_check_interval = max(5, int(runtime_cfg.get("health_check_interval_minutes") or 30)) * 60
    pid_snapshot_interval = max(5, int(runtime_cfg.get("pid_snapshot_interval_seconds") or 15))
    auto_repair_enabled = bool(runtime_cfg.get("auto_repair_stack", True))
    repair_cooldown_seconds = max(30, int(runtime_cfg.get("auto_repair_cooldown_seconds") or 180))

    if not args.loop:
        summary = runtime.process_pending_requests()
        executed = summary.get("executed", 0)
        print(f"guardian runtime once | pending={summary['pending']} | approve={summary['approve']} | reject={summary['reject']} | need-info={summary['need-info']} | executed={executed}")
        return 0

    print(f"guardian runtime loop start | poll_seconds={poll_seconds} | health_check_interval={health_check_interval}s")
    feishu = cfg.get("feishu") or {}
    ws_thread = start_feishu_ws_in_background(
        str(feishu.get("app_id") or ""),
        str(feishu.get("app_secret") or ""),
        workspace_root,
    )
    if ws_thread:
        print("[guardian] 飞书长连接已在后台启动", flush=True)
    startup_inspection = inspect_butler_main(workspace_root) if workspace_root and workspace_root.exists() else None
    _write_pid_snapshot(workspace_root, startup_inspection)
    _send_startup_and_inspection(cfg, workspace_root)
    last_health_check = time.monotonic()
    last_pid_snapshot = time.monotonic()
    last_repair_at = 0.0
    while True:
        summary = runtime.process_pending_requests()
        if summary["pending"]:
            executed = summary.get("executed", 0)
            print(f"guardian runtime tick | pending={summary['pending']} | approve={summary['approve']} | reject={summary['reject']} | need-info={summary['need-info']} | executed={executed}")
        now = time.monotonic()
        if now - last_pid_snapshot >= pid_snapshot_interval and workspace_root and workspace_root.exists():
            inspection = inspect_butler_main(workspace_root)
            _write_pid_snapshot(workspace_root, inspection)
            if auto_repair_enabled and not bool((inspection.get("overall") or {}).get("healthy")):
                if now - last_repair_at >= repair_cooldown_seconds:
                    ok, detail = _run_standard_restart(workspace_root)
                    last_repair_at = now
                    print(f"[guardian] auto-repair restart-stack: {'ok' if ok else 'fail'} | {detail[:400]}", flush=True)
            last_pid_snapshot = now
        if now - last_health_check >= health_check_interval:
            _send_periodic_inspection(cfg, workspace_root)
            last_health_check = now
        time.sleep(poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
