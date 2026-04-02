from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
ORCHESTRATOR_DIR = CURRENT_DIR.parent
BUTLER_MAIN_DIR = ORCHESTRATOR_DIR.parent
REPO_ROOT = BUTLER_MAIN_DIR.parent
for candidate in (str(REPO_ROOT), str(BUTLER_MAIN_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from butler_main.runtime_os.agent_runtime import FileRuntimeStateStore

from ..config import load_orchestrator_config
from ..execution_bridge import OrchestratorExecutionBridge
from ..feedback_notifier import OrchestratorFeedbackNotifier
from ..models import LedgerEvent
from ..paths import ORCHESTRATOR_RUN_DIR_REL, resolve_butler_root
from ..workflow_vm import OrchestratorWorkflowVM
from ..workspace import build_orchestrator_runtime_stack_for_workspace, build_orchestrator_service_for_workspace


ORCHESTRATOR_PID_FILE_NAME = "orchestrator_runtime.pid"
ORCHESTRATOR_WATCHDOG_STATE_FILE_NAME = "orchestrator_watchdog_state.json"
ORCHESTRATOR_RUN_STATE_FILE_NAME = "orchestrator_run_state.json"
ORCHESTRATOR_LOCK_FILE_NAME = "orchestrator_service.lock"
ORCHESTRATOR_TICK_SECONDS_DEFAULT = 30
ORCHESTRATOR_NOTE_MAX_LEN = 280


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


def _normalize_note(note: str, *, fallback: str = "") -> str:
    cleaned = " ".join(str(note or "").split())
    if not cleaned:
        cleaned = " ".join(str(fallback or "").split())
    if not cleaned:
        return ""
    if len(cleaned) > ORCHESTRATOR_NOTE_MAX_LEN:
        cleaned = cleaned[:ORCHESTRATOR_NOTE_MAX_LEN]
    return cleaned


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
    raw = _orchestrator_cfg(config_snapshot).get("auto_dispatch", True)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(raw)


def _auto_execute_enabled(config_snapshot: dict) -> bool:
    raw = _orchestrator_cfg(config_snapshot).get("auto_execute", True)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(raw)


def _detect_existing_owner(runtime_state: FileRuntimeStateStore, *, pid_probe) -> tuple[int, str]:
    watchdog = runtime_state.read_watchdog_state()
    run_state = runtime_state.read_run_state()
    candidates = [
        ("pid_file", runtime_state.read_pid()),
        ("run_state", int(run_state.get("pid") or 0)),
        ("watchdog", int(watchdog.get("pid") or 0)),
    ]
    seen: set[int] = set()
    for source, pid in candidates:
        pid_value = int(pid or 0)
        if pid_value <= 0 or pid_value in seen:
            continue
        seen.add(pid_value)
        if runtime_state.probe_pid(pid_value, pid_probe=pid_probe)["alive"]:
            return pid_value, source
    return 0, ""


def _resolve_runtime_dependencies(
    workspace: str,
    config_snapshot: dict,
    *,
    execution_bridge: OrchestratorExecutionBridge | None,
    workflow_vm: OrchestratorWorkflowVM | None,
):
    if workflow_vm is None and execution_bridge is None and _auto_execute_enabled(config_snapshot):
        assembly = build_orchestrator_runtime_stack_for_workspace(
            workspace,
            config_snapshot=config_snapshot,
        )
        return assembly.service, assembly.execution_bridge, assembly.workflow_vm
    return build_orchestrator_service_for_workspace(workspace), execution_bridge, workflow_vm


def _dispatch_ordered_missions(service) -> list:
    missions = list(service.list_missions() or [])
    return sorted(
        missions,
        key=lambda mission: (
            int(getattr(mission, "priority", 0) or 0),
            str(getattr(mission, "updated_at", "") or getattr(mission, "created_at", "") or "").strip(),
            str(getattr(mission, "mission_id", "") or "").strip(),
        ),
        reverse=True,
    )


def _recover_interrupted_branches(service, *, recovery_run_id: str = "") -> dict[str, Any]:
    recovered_branch_count = 0
    recovered_by_status: dict[str, int] = {}
    recovered_branch_ids: list[str] = []
    for mission in list(service.list_missions() or []):
        mission_changed = False
        for branch in list(service.list_branches(mission_id=mission.mission_id) or []):
            status = str(getattr(branch, "status", "") or "").strip()
            if status not in {"queued", "leased", "running"}:
                continue
            node = mission.node_by_id(branch.node_id)
            if node is None or bool((node.metadata or {}).get("approval_pending")):
                continue
            session_id = service._workflow_session_id_from_branch(branch)
            resume_from = ""
            if session_id:
                session = service._workflow_session_bridge.load_workflow_session(session_id)
                if session is not None:
                    resume_from = str(getattr(session, "active_step", "") or "").strip()
            branch.metadata = dict(branch.metadata or {})
            branch.status = "failed"
            branch.updated_at = service._now_text()
            branch.metadata["recovered_after_restart"] = True
            branch.metadata["recovery_reason"] = "runner_restart"
            branch.metadata["recovered_from_status"] = status
            if recovery_run_id:
                branch.metadata["recovery_run_id"] = recovery_run_id
            service._branch_store.save(branch)
            node.metadata = dict(node.metadata or {})
            if session_id:
                node.metadata["recovery_action"] = "resume"
            else:
                node.metadata["recovery_action"] = "retry"
            if resume_from:
                node.metadata["recovery_resume_from"] = resume_from
            node.status = "ready"
            mission_changed = True
            recovered_branch_count += 1
            recovered_by_status[status] = recovered_by_status.get(status, 0) + 1
            recovered_branch_ids.append(branch.branch_id)
            service._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    event_type="branch_recovered_after_restart",
                    payload={
                        "workflow_session_id": session_id,
                        "resume_from": resume_from,
                        "recovery_action": str(node.metadata.get("recovery_action") or "").strip(),
                        "recovered_from_status": status,
                        "recovery_run_id": recovery_run_id,
                    },
                )
            )
        if mission_changed:
            mission.status = "running"
            mission.updated_at = service._now_text()
            service._mission_store.save(mission)
    return {
        "recovered_branch_count": recovered_branch_count,
        "recovered_by_status": recovered_by_status,
        "recovered_branch_ids": recovered_branch_ids,
    }


def run_orchestrator_cycle(
    workspace: str,
    config_snapshot: dict,
    *,
    current_pid: int,
    execution_bridge: OrchestratorExecutionBridge | None = None,
    workflow_vm: OrchestratorWorkflowVM | None = None,
    feedback_notifier: OrchestratorFeedbackNotifier | None = None,
    progress_callback=None,
) -> dict:
    service, execution_bridge, workflow_vm = _resolve_runtime_dependencies(
        workspace,
        config_snapshot,
        execution_bridge=execution_bridge,
        workflow_vm=workflow_vm,
    )
    tick_result = service.tick()
    dispatch_limit = _dispatch_limit(config_snapshot)
    auto_dispatch = _auto_dispatch_enabled(config_snapshot)
    auto_execute = _auto_execute_enabled(config_snapshot)
    dispatched_count = 0
    executed_branch_count = 0
    completed_branch_count = 0
    failed_branch_count = 0
    non_terminal_branch_count = 0
    if callable(progress_callback):
        progress_callback(
            phase="tick",
            note=(
                f"cycle started | missions={len(service.list_missions())} "
                f"| auto_dispatch={int(auto_dispatch)} | auto_execute={int(auto_execute)}"
            ),
        )
    if auto_dispatch and dispatch_limit > 0:
        remaining = dispatch_limit
        for mission in _dispatch_ordered_missions(service):
            if remaining <= 0:
                break
            if str(getattr(mission, "status", "") or "").strip() not in {"ready", "running"}:
                continue
            batch = service.dispatch_ready_nodes(mission.mission_id, limit=remaining)
            dispatched_count += len(batch)
            remaining -= len(batch)
            if batch and callable(progress_callback):
                branch_ids = [
                    str(item.get("branch_id") or "").strip()
                    for item in batch
                    if str(item.get("branch_id") or "").strip()
                ]
                progress_callback(
                    phase="dispatch",
                    note=(
                        f"mission={mission.mission_id} | dispatched={len(branch_ids)} "
                        f"| branches={','.join(branch_ids[:4])}"
                    ),
                )
            if auto_execute and batch:
                branch_ids = [
                    str(item.get("branch_id") or "").strip()
                    for item in batch
                    if str(item.get("branch_id") or "").strip()
                ]
                if callable(progress_callback):
                    progress_callback(
                        phase="execute",
                        note=(
                            f"mission={mission.mission_id} | executing={len(branch_ids)} "
                            f"| branches={','.join(branch_ids[:4])}"
                        ),
                    )
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

    feedback_summary: dict[str, Any] = {}
    if feedback_notifier is not None:
        try:
            feedback_summary = dict(feedback_notifier.run_cycle(service=service) or {})
        except Exception as exc:
            feedback_summary = {"error_count": 1, "error": f"{type(exc).__name__}: {exc}"}

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
        if workflow_vm is None and execution_bridge is None:
            note += " | executor=missing"
    if feedback_summary:
        note += (
            f" | feedback_docs={int(feedback_summary.get('doc_sync_count') or 0)}"
            f" | feedback_pushes={int(feedback_summary.get('push_count') or 0)}"
        )
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
        "feedback": feedback_summary,
        "phase": phase,
        "note": note,
    }


def run_orchestrator_service(
    config_snapshot: dict,
    *,
    once: bool = False,
    execution_bridge: OrchestratorExecutionBridge | None = None,
    workflow_vm: OrchestratorWorkflowVM | None = None,
    feedback_notifier: OrchestratorFeedbackNotifier | None = None,
) -> dict:
    workspace = str((config_snapshot or {}).get("workspace_root") or os.getcwd())
    current_pid = int(os.getpid())
    runtime_state = build_orchestrator_runtime_state_store(workspace)
    existing_pid, existing_source = _detect_existing_owner(runtime_state, pid_probe=_pid_probe)
    if existing_pid > 0 and existing_pid != current_pid:
        print(
            f"[orchestrator] 检测到已有 orchestrator 在运行 (PID={existing_pid}, source={existing_source})，本次启动跳过",
            flush=True,
        )
        return {
            "ok": False,
            "reason": "already-running",
            "pid": existing_pid,
            "source": existing_source,
        }
    cleanup = runtime_state.cleanup_before_start(pid_probe=_pid_probe)
    ok, _ = runtime_state.acquire_lock(current_pid=current_pid, pid_probe=_pid_probe)
    if not ok:
        existing = runtime_state.read_pid()
        if existing <= 0:
            try:
                existing = int((runtime_state.lock_file().read_text(encoding="utf-8") or "").strip().split()[0])
            except Exception:
                existing = 0
        print(f"[orchestrator] 检测到已有 orchestrator 在运行 (PID={existing})，本次启动跳过", flush=True)
        return {"ok": False, "reason": "already-running", "pid": existing}

    run_id = f"orchestrator-{int(time.time())}-{current_pid}"
    notifier = feedback_notifier or OrchestratorFeedbackNotifier(
        workspace=workspace,
        config_snapshot=config_snapshot,
    )
    runtime_state.write_pid(current_pid)
    runtime_state.write_watchdog_state(
        state="running",
        pid=current_pid,
        note="orchestrator standalone runner active",
    )
    last_note = ""

    def _write_progress(*, phase: str, note: str) -> None:
        nonlocal last_note
        stable_note = _normalize_note(note, fallback=last_note or f"phase={phase}")
        last_note = stable_note
        runtime_state.write_run_state(
            run_id=run_id,
            state="running",
            phase=str(phase or "idle"),
            pid=current_pid,
            note=stable_note,
        )
        runtime_state.write_watchdog_state(
            state="running",
            pid=current_pid,
            note=stable_note,
        )

    cleanup_archived = list(cleanup.get("archived") or [])
    boot_note = "orchestrator runner booted"
    if cleanup_archived:
        boot_note = f"{boot_note} | startup_cleanup={len(cleanup_archived)}"
    _write_progress(phase="boot", note=boot_note)
    try:
        bootstrap_service, execution_bridge, workflow_vm = _resolve_runtime_dependencies(
            workspace,
            config_snapshot,
            execution_bridge=execution_bridge,
            workflow_vm=workflow_vm,
        )
        recovery_summary = _recover_interrupted_branches(bootstrap_service, recovery_run_id=run_id)
        if int(recovery_summary.get("recovered_branch_count") or 0) > 0:
            recovered_by_status = recovery_summary.get("recovered_by_status") or {}
            status_note = " ".join(
                f"{status}={count}"
                for status, count in sorted(recovered_by_status.items())
                if int(count or 0) > 0
            )
            status_note = f" | {status_note}" if status_note else ""
            _write_progress(
                phase="recover",
                note=(
                    f"recovered_branches={int(recovery_summary.get('recovered_branch_count') or 0)}"
                    f"{status_note}"
                ),
            )
        while True:
            summary = run_orchestrator_cycle(
                workspace,
                config_snapshot,
                current_pid=current_pid,
                execution_bridge=execution_bridge,
                workflow_vm=workflow_vm,
                feedback_notifier=notifier,
                progress_callback=_write_progress,
            )
            _write_progress(
                phase=str(summary.get("phase") or "idle"),
                note=str(summary.get("note") or ""),
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
            pid=current_pid,
            error=f"{type(exc).__name__}: {exc}",
        )
        runtime_state.write_watchdog_state(
            state="crashed",
            pid=current_pid,
            note=_normalize_note(
                f"orchestrator crashed: {type(exc).__name__}"
                + (f" | last_note={last_note}" if last_note else "")
            ),
        )
        raise
    finally:
        runtime_state.write_watchdog_state(
            state="stopped",
            pid=current_pid,
            note=_normalize_note(
                f"stopped | {last_note}" if last_note else "orchestrator runner stopped"
            ),
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
