from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BUTLER_MAIN_DIR = CURRENT_DIR.parent
REPO_ROOT = BUTLER_MAIN_DIR.parent
for candidate in (str(REPO_ROOT), str(BUTLER_MAIN_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from butler_main.agents_os.state import FileRuntimeStateStore

from .config import load_orchestrator_config
from .execution_bridge import OrchestratorExecutionBridge
from .paths import ORCHESTRATOR_RUN_DIR_REL, resolve_butler_root
from .workflow_vm import OrchestratorWorkflowVM
from .workspace import build_orchestrator_service_for_workspace


ORCHESTRATOR_PID_FILE_NAME = "orchestrator_runtime.pid"
ORCHESTRATOR_WATCHDOG_STATE_FILE_NAME = "orchestrator_watchdog_state.json"
ORCHESTRATOR_RUN_STATE_FILE_NAME = "orchestrator_run_state.json"
ORCHESTRATOR_LOCK_FILE_NAME = "orchestrator_service.lock"
ORCHESTRATOR_TICK_SECONDS_DEFAULT = 30


def build_orchestrator_runtime_state_store(workspace: str) -> FileRuntimeStateStore:
    root = resolve_butler_root(workspace) / ORCHESTRATOR_RUN_DIR_REL
    return FileRuntimeStateStore(
        root,
        pid_file_name=ORCHESTRATOR_PID_FILE_NAME,
        watchdog_state_file_name=ORCHESTRATOR_WATCHDOG_STATE_FILE_NAME,
        run_state_file_name=ORCHESTRATOR_RUN_STATE_FILE_NAME,
        lock_file_name=ORCHESTRATOR_LOCK_FILE_NAME,
    )


def _pid_probe(pid: int) -> dict[str, bool]:
    alive = False
    if int(pid or 0) > 0:
        try:
            os.kill(int(pid), 0)
            alive = True
        except Exception:
            alive = False
    return {"alive": alive, "matches": alive}


def _orchestrator_cfg(config_snapshot: dict) -> dict:
    raw = (config_snapshot or {}).get("orchestrator") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def _tick_seconds(config_snapshot: dict) -> int:
    raw = _orchestrator_cfg(config_snapshot).get("tick_seconds", ORCHESTRATOR_TICK_SECONDS_DEFAULT)
    try:
        value = int(raw)
    except Exception:
        value = ORCHESTRATOR_TICK_SECONDS_DEFAULT
    return max(5, min(600, value))


def _dispatch_limit(config_snapshot: dict) -> int:
    raw = _orchestrator_cfg(config_snapshot).get("max_dispatch_per_tick", 1)
    try:
        value = int(raw)
    except Exception:
        value = 1
    return max(0, min(16, value))


def _auto_dispatch_enabled(config_snapshot: dict) -> bool:
    raw = _orchestrator_cfg(config_snapshot).get("auto_dispatch", False)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(raw)


def _auto_execute_enabled(config_snapshot: dict) -> bool:
    raw = _orchestrator_cfg(config_snapshot).get("auto_execute", False)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(raw)


def run_orchestrator_cycle(
    workspace: str,
    config_snapshot: dict,
    *,
    current_pid: int,
    execution_bridge: OrchestratorExecutionBridge | None = None,
    workflow_vm: OrchestratorWorkflowVM | None = None,
) -> dict:
    service = build_orchestrator_service_for_workspace(workspace)
    tick_result = service.tick()
    dispatch_limit = _dispatch_limit(config_snapshot)
    auto_dispatch = _auto_dispatch_enabled(config_snapshot)
    auto_execute = _auto_execute_enabled(config_snapshot)
    dispatched_count = 0
    executed_branch_count = 0
    completed_branch_count = 0
    failed_branch_count = 0
    non_terminal_branch_count = 0
    if auto_dispatch and dispatch_limit > 0:
        remaining = dispatch_limit
        for mission in service.list_missions():
            if remaining <= 0:
                break
            if str(getattr(mission, "status", "") or "").strip() not in {"ready", "running"}:
                continue
            batch = service.dispatch_ready_nodes(mission.mission_id, limit=remaining)
            dispatched_count += len(batch)
            remaining -= len(batch)
            if auto_execute and batch:
                branch_ids = [
                    str(item.get("branch_id") or "").strip()
                    for item in batch
                    if str(item.get("branch_id") or "").strip()
                ]
                outcomes = []
                if workflow_vm is not None:
                    outcomes = workflow_vm.execute_and_record(
                        service,
                        mission_id=mission.mission_id,
                        branch_ids=branch_ids,
                    )
                elif execution_bridge is not None:
                    outcomes = execution_bridge.execute_and_record(
                        service,
                        mission_id=mission.mission_id,
                        branch_ids=branch_ids,
                    )
                executed_branch_count += len(outcomes)
                completed_branch_count += sum(1 for item in outcomes if item.terminal and item.ok)
                failed_branch_count += sum(1 for item in outcomes if item.terminal and not item.ok)
                non_terminal_branch_count += sum(1 for item in outcomes if not item.terminal)

    missions = service.list_missions()
    mission_status_counts: dict[str, int] = {}
    ready_node_count = 0
    running_node_count = 0
    for mission in missions:
        status = str(getattr(mission, "status", "") or "unknown").strip() or "unknown"
        mission_status_counts[status] = mission_status_counts.get(status, 0) + 1
        for node in list(getattr(mission, "nodes", []) or []):
            node_status = str(getattr(node, "status", "") or "").strip()
            if node_status == "ready":
                ready_node_count += 1
            elif node_status == "running":
                running_node_count += 1

    note = (
        f"missions={len(missions)} | activated={int(tick_result.get('activated_node_count') or 0)} "
        f"| dispatched={dispatched_count} | ready_nodes={ready_node_count} | running_nodes={running_node_count}"
    )
    if auto_execute:
        note += (
            f" | executed={executed_branch_count}"
            f" | completed={completed_branch_count}"
            f" | failed={failed_branch_count}"
            f" | non_terminal={non_terminal_branch_count}"
        )
        if execution_bridge is None:
            note += " | execution_bridge=missing"
    phase = "idle"
    if executed_branch_count > 0 or failed_branch_count > 0 or non_terminal_branch_count > 0:
        phase = "execute"
    elif dispatched_count > 0:
        phase = "dispatch"
    elif int(tick_result.get("activated_node_count") or 0) > 0:
        phase = "tick"
    return {
        "current_pid": int(current_pid or 0),
        "mission_count": len(missions),
        "mission_status_counts": mission_status_counts,
        "ready_node_count": ready_node_count,
        "running_node_count": running_node_count,
        "activated_node_count": int(tick_result.get("activated_node_count") or 0),
        "dispatched_count": dispatched_count,
        "executed_branch_count": executed_branch_count,
        "completed_branch_count": completed_branch_count,
        "failed_branch_count": failed_branch_count,
        "non_terminal_branch_count": non_terminal_branch_count,
        "phase": phase,
        "note": note,
    }


def run_orchestrator_service(
    config_snapshot: dict,
    *,
    once: bool = False,
    execution_bridge: OrchestratorExecutionBridge | None = None,
    workflow_vm: OrchestratorWorkflowVM | None = None,
) -> dict:
    workspace = str((config_snapshot or {}).get("workspace_root") or os.getcwd())
    current_pid = int(os.getpid())
    runtime_state = build_orchestrator_runtime_state_store(workspace)
    cleanup = runtime_state.cleanup_before_start(pid_probe=_pid_probe)
    ok, _ = runtime_state.acquire_lock(current_pid=current_pid, pid_probe=_pid_probe)
    if not ok:
        existing = runtime_state.read_pid()
        print(f"[orchestrator] 检测到已有 orchestrator 在运行 (PID={existing})，本次启动跳过", flush=True)
        return {"ok": False, "reason": "already-running", "pid": existing}

    run_id = f"orchestrator-{int(time.time())}-{current_pid}"
    runtime_state.write_pid(current_pid)
    runtime_state.write_watchdog_state(
        state="running",
        heartbeat_pid=current_pid,
        note="orchestrator standalone runner active",
    )
    try:
        while True:
            summary = run_orchestrator_cycle(
                workspace,
                config_snapshot,
                current_pid=current_pid,
                execution_bridge=execution_bridge,
                workflow_vm=workflow_vm,
            )
            runtime_state.write_run_state(
                run_id=run_id,
                state="running",
                phase=str(summary.get("phase") or "idle"),
                heartbeat_pid=current_pid,
                note=str(summary.get("note") or "")[:500],
            )
            runtime_state.write_watchdog_state(
                state="running",
                heartbeat_pid=current_pid,
                note=str(summary.get("note") or "")[:300],
            )
            last_summary = {"ok": True, "run_id": run_id, "workspace": workspace, **summary}
            if once:
                return last_summary
            time.sleep(_tick_seconds(config_snapshot))
    except BaseException as exc:
        runtime_state.write_run_state(
            run_id=run_id,
            state="failed",
            phase="crashed",
            heartbeat_pid=current_pid,
            error=f"{type(exc).__name__}: {exc}",
        )
        runtime_state.write_watchdog_state(
            state="crashed",
            heartbeat_pid=current_pid,
            note=f"orchestrator crashed: {type(exc).__name__}",
        )
        raise
    finally:
        runtime_state.write_watchdog_state(
            state="stopped",
            heartbeat_pid=current_pid,
            note="orchestrator runner stopped",
        )
        runtime_state.clear_pid()
        runtime_state.release_lock()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    cfg = load_orchestrator_config(args.config)
    cfg["__config_path"] = os.path.abspath(args.config)
    run_orchestrator_service(cfg, once=bool(args.once))
    return 0


if __name__ == "__main__":
    sys.exit(main())
