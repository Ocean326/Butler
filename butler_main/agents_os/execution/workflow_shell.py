from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from butler_main.agents_os.execution.cli_runner import cli_provider_available, run_prompt_receipt
from butler_main.agents_os.state import FileRuntimeStateStore, FileTraceStore
from butler_main.chat.cli.runner import TerminalConsole, TerminalStreamPrinter
from butler_main.chat.config_runtime import load_active_config, resolve_default_config_path
from butler_main.chat.pathing import resolve_butler_root

from .workflow_prompts import (
    build_project_loop_judge_prompt,
    build_project_phase_codex_prompt,
    build_single_goal_codex_prompt,
    build_single_goal_judge_prompt,
)


WORKFLOW_SHELL_RUN_HOME_REL = Path("butler_main") / "butler_bot_code" / "run" / "workflow_shell"
SINGLE_GOAL_KIND = "single_goal"
SINGLE_GOAL_PHASE = "free"
PROJECT_LOOP_KIND = "project_loop"
PROJECT_PHASES = ("plan", "imp", "review")
DONE_PHASE = "done"
DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS = 12
DEFAULT_PROJECT_LOOP_MAX_ATTEMPTS = 18
DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS = 6
DEFAULT_WORKFLOW_LIST_LIMIT = 10
DEFAULT_WORKFLOW_LAUNCHER_RECENT_LIMIT = 5
DEFAULT_WORKFLOW_LAUNCHER_KIND = PROJECT_LOOP_KIND
WORKFLOW_CODEX_HOME_DIRNAME = "codex_home"
WORKFLOW_CODEX_HOME_SYNC_FILES = ("config.toml", "auth.json", "version.json")
DEFAULT_DISABLED_WORKFLOW_MCP_SERVERS: dict[str, dict[str, str]] = {
    "stripe": {"transport": "streamable_http", "url": "https://mcp.stripe.com"},
    "supabase": {"transport": "streamable_http", "url": "https://mcp.supabase.com/mcp"},
    "vercel": {"transport": "streamable_http", "url": "https://mcp.vercel.com"},
}


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid4().hex[:6]}")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _new_workflow_id() -> str:
    return f"workflow_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"


def _pid_probe(pid: int) -> dict[str, bool]:
    alive = False
    if int(pid or 0) > 0:
        try:
            os.kill(int(pid), 0)
            alive = True
        except Exception:
            alive = False
    return {"alive": alive, "matches": alive}


def _receipt_text(receipt) -> str:
    bundle = getattr(receipt, "output_bundle", None)
    if bundle is not None:
        for block in list(getattr(bundle, "text_blocks", []) or [])[::-1]:
            text = str(getattr(block, "text", "") or "").strip()
            if text:
                return text
    return str(getattr(receipt, "summary", "") or "").strip()


def _serialize_receipt(receipt) -> dict[str, Any]:
    bundle = getattr(receipt, "output_bundle", None)
    text_blocks = []
    if bundle is not None:
        for block in list(getattr(bundle, "text_blocks", []) or []):
            text_blocks.append({"text": str(getattr(block, "text", "") or ""), "style": str(getattr(block, "style", "") or "")})
    return {
        "execution_id": str(getattr(receipt, "execution_id", "") or "").strip(),
        "workflow_id": str(getattr(receipt, "workflow_id", "") or "").strip(),
        "agent_id": str(getattr(receipt, "agent_id", "") or "").strip(),
        "status": str(getattr(receipt, "status", "") or "").strip(),
        "summary": str(getattr(receipt, "summary", "") or "").strip(),
        "output_text": _receipt_text(receipt),
        "metadata": dict(getattr(receipt, "metadata", {}) or {}),
        "output_bundle": {
            "status": str(getattr(bundle, "status", "") or "").strip() if bundle is not None else "",
            "summary": str(getattr(bundle, "summary", "") or "").strip() if bundle is not None else "",
            "text_blocks": text_blocks,
        },
    }


def _receipt_thread_id(receipt) -> str:
    metadata = dict(getattr(receipt, "metadata", {}) or {})
    external_session = dict(metadata.get("external_session") or {})
    return str(external_session.get("thread_id") or "").strip()


def _workflow_state_path(workflow_dir: Path) -> Path:
    return workflow_dir / "workflow_state.json"


def _system_codex_home() -> Path:
    configured = str(os.environ.get("CODEX_HOME") or "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


def _workflow_codex_home_dir(workflow_dir: Path) -> Path:
    return workflow_dir / WORKFLOW_CODEX_HOME_DIRNAME


def _copy_codex_home_file(source_path: Path, target_path: Path) -> None:
    if not source_path.is_file():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)


def _prepare_workflow_codex_home(workflow_dir: Path) -> Path:
    source_root = _system_codex_home()
    target_root = _workflow_codex_home_dir(workflow_dir)
    target_root.mkdir(parents=True, exist_ok=True)
    for filename in WORKFLOW_CODEX_HOME_SYNC_FILES:
        _copy_codex_home_file(source_root / filename, target_root / filename)
    if not (target_root / "config.toml").exists():
        (target_root / "config.toml").write_text("", encoding="utf-8")
    return target_root


def build_workflow_shell_root(workspace: str | Path) -> Path:
    return resolve_butler_root(workspace) / WORKFLOW_SHELL_RUN_HOME_REL


def _workflow_dir(workspace: str | Path, workflow_id: str) -> Path:
    return build_workflow_shell_root(workspace) / str(workflow_id or "").strip()


def _ensure_trace(trace_store: FileTraceStore, *, run_id: str, metadata: dict[str, Any]) -> None:
    if trace_store.load(run_id):
        return
    trace_store.save(
        run_id,
        {
            "run_id": run_id,
            "parent_run_id": "",
            "created_at": _now_text(),
            "metadata": dict(metadata or {}),
            "events": [],
            "progress_counter": 0,
            "selected_task_ids": [],
            "rejected_task_ids": [],
            "fallback_count": 0,
            "retry_count": 0,
            "timeout_count": 0,
            "degrade_count": 0,
        },
    )


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = str(text or "").strip()
    if not stripped:
        return {}
    candidates = [stripped]
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            candidates.append("\n".join(lines[1:-1]).strip())
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        candidates.append(stripped[start : end + 1].strip())
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _normalize_single_goal_decision(payload: dict[str, Any], *, fallback_reason: str = "") -> dict[str, Any]:
    decision = str(payload.get("decision") or "").strip().upper()
    if decision not in {"COMPLETE", "RETRY", "ABORT"}:
        decision = "ABORT"
    reason = str(payload.get("reason") or fallback_reason or "").strip()
    return {
        "decision": decision,
        "reason": reason,
        "next_codex_prompt": str(payload.get("next_codex_prompt") or "").strip(),
        "completion_summary": str(payload.get("completion_summary") or "").strip(),
    }


def _normalize_project_decision(payload: dict[str, Any], *, fallback_reason: str = "") -> dict[str, Any]:
    decision = str(payload.get("decision") or "").strip().upper()
    if decision not in {"ADVANCE", "RETRY", "COMPLETE", "ABORT"}:
        decision = "ABORT"
    next_phase = str(payload.get("next_phase") or "").strip().lower()
    if next_phase == "complete":
        next_phase = DONE_PHASE
    if next_phase not in {*PROJECT_PHASES, DONE_PHASE, ""}:
        next_phase = ""
    reason = str(payload.get("reason") or fallback_reason or "").strip()
    return {
        "decision": decision,
        "next_phase": next_phase,
        "reason": reason,
        "next_codex_prompt": str(payload.get("next_codex_prompt") or "").strip(),
        "completion_summary": str(payload.get("completion_summary") or "").strip(),
    }


def _default_phase(workflow_kind: str) -> str:
    return SINGLE_GOAL_PHASE if workflow_kind == SINGLE_GOAL_KIND else PROJECT_PHASES[0]


def _phase_after(phase: str) -> str:
    if phase == "plan":
        return "imp"
    if phase == "imp":
        return "review"
    return DONE_PHASE


def _workflow_shell_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    raw = cfg.get("workflow_shell")
    return dict(raw or {}) if isinstance(raw, dict) else {}


def _launcher_default_kind(cfg: dict[str, Any]) -> str:
    configured = str(_workflow_shell_settings(cfg).get("launcher_default_kind") or "").strip().lower()
    if configured in {SINGLE_GOAL_KIND, PROJECT_LOOP_KIND}:
        return configured
    return DEFAULT_WORKFLOW_LAUNCHER_KIND


def _default_guard_condition(workflow_kind: str) -> str:
    if workflow_kind == PROJECT_LOOP_KIND:
        return "如果 Codex 中断就继续，同一会话按 plan -> imp -> review 推进，只有 review 明确通过才结束。"
    return "如果 Codex 中断就继续，直到目标完成或明确阻塞再结束。"


def _toml_escape(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def _workflow_disabled_mcp_servers(cfg: dict[str, Any]) -> list[str]:
    settings = _workflow_shell_settings(cfg)
    if "disable_mcp_servers" in settings:
        requested = _normalize_text_list(settings.get("disable_mcp_servers"))
        return requested
    return list(DEFAULT_DISABLED_WORKFLOW_MCP_SERVERS.keys())


def _workflow_mcp_server_specs(cfg: dict[str, Any]) -> dict[str, dict[str, str]]:
    specs = {name: dict(payload) for name, payload in DEFAULT_DISABLED_WORKFLOW_MCP_SERVERS.items()}
    raw_specs = _workflow_shell_settings(cfg).get("mcp_server_specs")
    if not isinstance(raw_specs, dict):
        return specs
    for raw_name, raw_payload in raw_specs.items():
        name = str(raw_name or "").strip()
        payload = dict(raw_payload or {}) if isinstance(raw_payload, dict) else {}
        transport = str(payload.get("transport") or "").strip()
        url = str(payload.get("url") or "").strip()
        if name and transport and url:
            specs[name] = {"transport": transport, "url": url}
    return specs


def _workflow_codex_config_overrides(cfg: dict[str, Any]) -> list[str]:
    specs = _workflow_mcp_server_specs(cfg)
    overrides: list[str] = []
    for server_name in _workflow_disabled_mcp_servers(cfg):
        spec = dict(specs.get(str(server_name or "").strip()) or {})
        transport = str(spec.get("transport") or "").strip()
        url = str(spec.get("url") or "").strip()
        if not transport or not url:
            continue
        overrides.append(
            f'mcp_servers.{server_name}={{enabled=false,transport="{_toml_escape(transport)}",url="{_toml_escape(url)}"}}'
        )
    return overrides


def _current_project_phase_attempt_count(workflow_state: dict[str, Any]) -> int:
    if str(workflow_state.get("workflow_kind") or "").strip() != PROJECT_LOOP_KIND:
        return 0
    phase = str(workflow_state.get("current_phase") or _default_phase(PROJECT_LOOP_KIND)).strip()
    count = 0
    for row in reversed(list(workflow_state.get("phase_history") or [])):
        if str(row.get("phase") or "").strip() != phase:
            break
        if str(row.get("codex_status") or "").strip() == "completed":
            count += 1
    return count


def _sync_project_phase_attempt_count(workflow_state: dict[str, Any]) -> int:
    count = _current_project_phase_attempt_count(workflow_state)
    workflow_state["phase_attempt_count"] = count
    return count


def _workflow_timeout_seconds(cfg: dict[str, Any]) -> int:
    raw = ((cfg.get("workflow_shell") or {}) if isinstance(cfg.get("workflow_shell"), dict) else {}).get("timeout_seconds", cfg.get("agent_timeout", 1800))
    return max(60, min(7200, _safe_int(raw, 1800)))


def _judge_timeout_seconds(cfg: dict[str, Any]) -> int:
    raw = ((cfg.get("workflow_shell") or {}) if isinstance(cfg.get("workflow_shell"), dict) else {}).get("judge_timeout_seconds", 300)
    return max(30, min(1800, _safe_int(raw, 300)))


def _build_default_retry_instruction(workflow_state: dict[str, Any], *, codex_ok: bool) -> str:
    if workflow_state.get("workflow_kind") == PROJECT_LOOP_KIND:
        phase = str(workflow_state.get("current_phase") or "").strip()
        if phase == "review":
            return "Continue the same session, fix the real review blockers, rerun verification, and update the repo to a review-pass state."
        if phase == "imp":
            return "Continue the same session, finish the implementation work, run verification, and leave the repo ready for review."
        return "Continue the same session, tighten the plan, confirm files/tests, and prepare a concrete implementation path."
    if codex_ok:
        return "Continue the same session and close the remaining gap until the guard condition is clearly satisfied."
    return "Resume the same session, recover from the interruption, and continue toward the guard condition."


def _recent_phase_history(workflow_state: dict[str, Any], *, limit: int = 6) -> list[dict[str, Any]]:
    rows = list(workflow_state.get("phase_history") or [])
    if limit > 0:
        rows = rows[-limit:]
    return [dict(row or {}) for row in rows]


def _build_phase_artifact(
    workflow_state: dict[str, Any],
    *,
    phase: str,
    attempt_no: int,
    phase_attempt_no: int,
    codex_receipt,
) -> dict[str, Any]:
    return {
        "workflow_id": str(workflow_state.get("workflow_id") or "").strip(),
        "workflow_kind": str(workflow_state.get("workflow_kind") or "").strip(),
        "phase": str(phase or "").strip(),
        "attempt_no": int(attempt_no),
        "phase_attempt_no": int(phase_attempt_no),
        "goal": str(workflow_state.get("goal") or "").strip(),
        "guard_condition": str(workflow_state.get("guard_condition") or "").strip(),
        "codex_session_id": str(workflow_state.get("codex_session_id") or _receipt_thread_id(codex_receipt)).strip(),
        "codex_status": str(getattr(codex_receipt, "status", "") or "").strip(),
        "codex_output": _receipt_text(codex_receipt),
        "codex_metadata": dict(getattr(codex_receipt, "metadata", {}) or {}),
        "pending_codex_prompt": str(workflow_state.get("pending_codex_prompt") or "").strip(),
        "last_cursor_decision": dict(workflow_state.get("last_cursor_decision") or {}),
    }


def _normalize_project_loop_decision(decision: dict[str, Any], *, phase: str) -> dict[str, Any]:
    normalized = dict(decision or {})
    decision_name = str(normalized.get("decision") or "").strip().upper()
    next_phase = str(normalized.get("next_phase") or "").strip().lower()
    if next_phase == "complete":
        next_phase = DONE_PHASE
    if phase == "review":
        if decision_name == "COMPLETE":
            normalized["next_phase"] = DONE_PHASE
            normalized["decision"] = "COMPLETE"
            return normalized
        if next_phase not in {"imp", "plan"}:
            next_phase = "imp"
        normalized["decision"] = "RETRY"
        normalized["next_phase"] = next_phase
        return normalized
    if decision_name == "COMPLETE":
        normalized["decision"] = "ADVANCE"
        if not next_phase or next_phase == DONE_PHASE:
            next_phase = _phase_after(phase)
    elif next_phase == DONE_PHASE:
        next_phase = _phase_after(phase)
    normalized["next_phase"] = next_phase
    return normalized


def _new_workflow_state(
    *,
    workflow_id: str,
    workflow_kind: str,
    workspace_root: str,
    goal: str,
    guard_condition: str,
    max_attempts: int,
    max_phase_attempts: int,
    codex_session_id: str = "",
    resume_source: str = "",
) -> dict[str, Any]:
    now = _now_text()
    return {
        "workflow_id": workflow_id,
        "workflow_kind": workflow_kind,
        "workspace_root": workspace_root,
        "goal": goal,
        "guard_condition": guard_condition,
        "status": "pending",
        "current_phase": _default_phase(workflow_kind),
        "attempt_count": 0,
        "phase_attempt_count": 0,
        "max_attempts": max_attempts,
        "max_phase_attempts": max_phase_attempts,
        "codex_session_id": codex_session_id,
        "pending_codex_prompt": "",
        "last_cursor_decision": {},
        "last_completion_summary": "",
        "last_codex_receipt": {},
        "last_cursor_receipt": {},
        "current_phase_artifact": {},
        "phase_history": [],
        "resume_source": resume_source,
        "trace_run_id": workflow_id,
        "created_at": now,
        "updated_at": now,
    }


class _SnapshotPrinter:
    def __init__(self, stream, *, prefix: str = "codex> ") -> None:
        self._stream = stream
        self._prefix = prefix
        self._started = False
        self._emitted = ""

    def _write(self, text: str) -> None:
        if not text:
            return
        self._stream.write(text)
        self._stream.flush()

    def on_segment(self, segment: str) -> None:
        text = str(segment or "")
        if not text:
            return
        if not self._started:
            self._write(self._prefix)
            self._started = True
        if not self._emitted:
            self._write(text)
            self._emitted = text
            return
        if text.startswith(self._emitted):
            delta = text[len(self._emitted) :]
            if delta:
                self._write(delta)
            self._emitted = text
            return
        if text != self._emitted:
            self._write(f"\n[final]\n{text}")
            self._emitted = text

    def finalize(self, final_text: str) -> None:
        text = str(final_text or "")
        if not text:
            if self._started:
                self._write("\n")
            return
        if not self._started:
            self._write(f"{self._prefix}{text}\n")
            self._started = True
            self._emitted = text
            return
        if text.startswith(self._emitted):
            delta = text[len(self._emitted) :]
            if delta:
                self._write(delta)
        elif text != self._emitted:
            self._write(f"\n[final]\n{text}")
        self._write("\n")
        self._emitted = text


class WorkflowShellApp:
    def __init__(
        self,
        *,
        run_prompt_receipt_fn: Callable[..., Any] = run_prompt_receipt,
        input_fn: Callable[[str], str] = input,
        stdout=None,
        stderr=None,
    ) -> None:
        self._run_prompt_receipt_fn = run_prompt_receipt_fn
        self._input_fn = input_fn
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def _write(self, text: str = "", *, err: bool = False) -> None:
        stream = self._stderr if err else self._stdout
        stream.write(text)
        if not text.endswith("\n"):
            stream.write("\n")
        stream.flush()

    def _write_json(self, payload: dict[str, Any]) -> None:
        self._stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        self._stdout.flush()

    def _prompt_value(self, prompt: str, current: str = "") -> str:
        if str(current or "").strip():
            return str(current).strip()
        return str(self._input_fn(prompt)).strip()

    def _emit_runtime_event(self, event: dict[str, Any]) -> None:
        kind = str(event.get("kind") or "").strip()
        text = str(event.get("text") or "").strip()
        if not text:
            return
        if kind == "command":
            status = str(event.get("status") or "").strip().lower() or "update"
            self._write(f"[codex {status}] {text}")
            return
        if kind == "usage":
            self._write(f"[codex usage] {text}")
            return
        if kind in {"stderr", "error"}:
            self._write(f"[codex stderr] {text}")

    def _build_console(self) -> TerminalConsole:
        return TerminalConsole(stream=self._stdout)

    def _truncate(self, value: str, *, limit: int = 88) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        head = max(16, (limit - 3) // 2)
        tail = max(12, limit - head - 3)
        return f"{text[:head]}...{text[-tail:]}"

    def _workflow_rows(self, *, workspace_root: str, limit: int = DEFAULT_WORKFLOW_LIST_LIMIT) -> list[dict[str, Any]]:
        shell_root = build_workflow_shell_root(workspace_root)
        if not shell_root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for workflow_dir in sorted(shell_root.iterdir()):
            if not workflow_dir.is_dir():
                continue
            state_path = _workflow_state_path(workflow_dir)
            workflow_state = _read_json(state_path)
            if not workflow_state:
                continue
            sort_value = 0.0
            for field in ("updated_at", "created_at"):
                stamp = str(workflow_state.get(field) or "").strip()
                if not stamp:
                    continue
                try:
                    sort_value = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").timestamp()
                    break
                except Exception:
                    continue
            if sort_value <= 0:
                try:
                    sort_value = state_path.stat().st_mtime
                except Exception:
                    sort_value = 0.0
            rows.append(
                {
                    "workflow_id": str(workflow_state.get("workflow_id") or workflow_dir.name).strip(),
                    "workflow_dir": str(workflow_dir),
                    "workflow_kind": str(workflow_state.get("workflow_kind") or "").strip(),
                    "status": str(workflow_state.get("status") or "").strip(),
                    "current_phase": str(workflow_state.get("current_phase") or "").strip(),
                    "attempt_count": _safe_int(workflow_state.get("attempt_count"), 0),
                    "max_attempts": _safe_int(workflow_state.get("max_attempts"), 0),
                    "codex_session_id": str(workflow_state.get("codex_session_id") or "").strip(),
                    "updated_at": str(workflow_state.get("updated_at") or workflow_state.get("created_at") or "").strip(),
                    "goal": str(workflow_state.get("goal") or "").strip(),
                    "_sort_value": float(sort_value),
                }
            )
        rows.sort(key=lambda item: item.get("_sort_value") or 0.0, reverse=True)
        return rows[: max(1, int(limit or DEFAULT_WORKFLOW_LIST_LIMIT))]

    def _resolve_recent_workflow_id(self, *, workspace_root: str) -> str:
        rows = self._workflow_rows(workspace_root=workspace_root, limit=1)
        if not rows:
            raise FileNotFoundError("no local workflow shell state found")
        return str(rows[0].get("workflow_id") or "").strip()

    def _workflow_identity_from_args(self, *, workspace_root: str, args: argparse.Namespace) -> str:
        workflow_id = str(getattr(args, "workflow_id", "") or "").strip()
        if workflow_id:
            return workflow_id
        if bool(getattr(args, "last", False)):
            return self._resolve_recent_workflow_id(workspace_root=workspace_root)
        return ""

    def _load_config(self, raw_config: str | None) -> tuple[dict[str, Any], str, str]:
        config_path = str(raw_config or "").strip() or resolve_default_config_path("butler_bot")
        cfg = load_active_config(config_path)
        workspace_root = str(cfg.get("workspace_root") or resolve_butler_root(Path.cwd())).strip() or str(resolve_butler_root(Path.cwd()))
        return cfg, config_path, workspace_root

    def _ensure_workflow_runtime(self, cfg: dict[str, Any]) -> None:
        if not cli_provider_available("codex", cfg):
            raise RuntimeError("Codex CLI is unavailable for workflow shell")
        if not cli_provider_available("cursor", cfg):
            raise RuntimeError("Cursor CLI is unavailable for workflow shell judge")

    def _workflow_status_payload(self, *, workspace_root: str, workflow_id: str) -> dict[str, Any]:
        workflow_dir = _workflow_dir(workspace_root, workflow_id)
        state_path = _workflow_state_path(workflow_dir)
        if not state_path.exists():
            raise FileNotFoundError(f"workflow not found: {workflow_id}")
        state_store = FileRuntimeStateStore(workflow_dir)
        trace_store = FileTraceStore(state_store.traces_dir())
        trace_summary = trace_store.summarize(workflow_id)
        snapshot = state_store.status_snapshot(enabled=True, stale_seconds=600, tracked_pid=state_store.read_pid(), pid_probe=_pid_probe)
        workflow_state = _read_json(state_path)
        return {
            "workflow_id": workflow_id,
            "workflow_dir": str(workflow_dir),
            "workflow_state": workflow_state,
            "runtime_snapshot": {
                "config_state": snapshot.config_state,
                "process_state": snapshot.process_state,
                "watchdog_state": snapshot.watchdog_state,
                "run_state": snapshot.run_state,
                "progress_state": snapshot.progress_state,
                "pid": snapshot.pid,
                "run_id": snapshot.run_id,
                "phase": snapshot.phase,
                "updated_at": snapshot.updated_at,
                "note": snapshot.note,
            },
            "trace_summary": {
                "progress_counter": trace_summary.progress_counter,
                "retry_count": trace_summary.retry_count,
                "fallback_count": trace_summary.fallback_count,
                "timeout_count": trace_summary.timeout_count,
                "degrade_count": trace_summary.degrade_count,
            },
        }

    def _save_workflow_state(self, workflow_dir: Path, workflow_state: dict[str, Any]) -> None:
        workflow_state["updated_at"] = _now_text()
        _write_json_atomic(_workflow_state_path(workflow_dir), workflow_state)

    def preflight(self, args: argparse.Namespace) -> int:
        cfg, config_path, workspace_root = self._load_config(getattr(args, "config", None))
        disabled_mcp_servers = _workflow_disabled_mcp_servers(cfg)
        payload = {
            "config_path": config_path,
            "workspace_root": workspace_root,
            "workflow_shell_root": str(build_workflow_shell_root(workspace_root)),
            "codex_available": bool(cli_provider_available("codex", cfg)),
            "cursor_available": bool(cli_provider_available("cursor", cfg)),
            "workflow_codex_disabled_mcp_servers": disabled_mcp_servers,
        }
        if bool(getattr(args, "json", False)):
            self._write_json(payload)
            return 0
        self._write("[workflow preflight]")
        self._write(f"config={payload['config_path']}")
        self._write(f"workspace_root={payload['workspace_root']}")
        self._write(f"workflow_shell_root={payload['workflow_shell_root']}")
        self._write(f"codex_available={'yes' if payload['codex_available'] else 'no'}")
        self._write(f"cursor_available={'yes' if payload['cursor_available'] else 'no'}")
        self._write(f"codex_mcp_guard={', '.join(disabled_mcp_servers) if disabled_mcp_servers else '-'}")
        self._write("codex_exec_home=isolated per workflow")
        self._write("next=butler -workflow run --goal \"...\" --guard-condition \"...\"")
        return 0

    def list_workflows(self, args: argparse.Namespace) -> int:
        _, _, workspace_root = self._load_config(getattr(args, "config", None))
        rows = self._workflow_rows(workspace_root=workspace_root, limit=_safe_int(getattr(args, "limit", DEFAULT_WORKFLOW_LIST_LIMIT), DEFAULT_WORKFLOW_LIST_LIMIT))
        payload = {"workflow_shell_root": str(build_workflow_shell_root(workspace_root)), "items": rows}
        if bool(getattr(args, "json", False)):
            self._write_json(payload)
            return 0
        self._write(f"workflow_shell_root={payload['workflow_shell_root']}")
        if not rows:
            self._write("no workflow state found")
            return 0
        for row in rows:
            self._write(
                f"{row['workflow_id']}  status={row['status'] or '-'}  phase={row['current_phase'] or '-'}  "
                f"kind={row['workflow_kind'] or '-'}  attempts={row['attempt_count']}/{row['max_attempts'] or '-'}"
            )
            self._write(f"  updated_at={row['updated_at'] or '-'}  session={row['codex_session_id'] or '-'}")
            self._write(f"  goal={self._truncate(str(row.get('goal') or '-'), limit=96)}")
        return 0

    def _append_attempt_draft(
        self,
        *,
        state_store: FileRuntimeStateStore,
        attempt_no: int,
        phase: str,
        codex_prompt: str,
        codex_receipt,
        cursor_receipt,
        decision: dict[str, Any],
    ) -> None:
        payload = {
            "saved_at": _now_text(),
            "attempt_no": attempt_no,
            "phase": phase,
            "codex_prompt": codex_prompt,
            "codex_receipt": _serialize_receipt(codex_receipt),
            "cursor_receipt": _serialize_receipt(cursor_receipt),
            "decision": dict(decision or {}),
        }
        draft_path = state_store.drafts_dir() / f"attempt_{attempt_no:04d}.json"
        _write_json_atomic(draft_path, payload)

    def _build_codex_runtime_request(
        self,
        cfg: dict[str, Any],
        *,
        workflow_id: str,
        workflow_state: dict[str, Any],
        workflow_dir: Path,
    ) -> dict[str, Any]:
        request = {
            "cli": "codex",
            "_disable_runtime_fallback": True,
            "workflow_id": workflow_id,
            "agent_id": "workflow_shell.codex_executor",
            "codex_mode": "resume" if str(workflow_state.get("codex_session_id") or "").strip() else "exec",
            "codex_session_id": str(workflow_state.get("codex_session_id") or "").strip(),
            "codex_home": str(_prepare_workflow_codex_home(workflow_dir)),
        }
        overrides = _workflow_codex_config_overrides(cfg)
        if overrides:
            request["config_overrides"] = overrides
        return request

    def _print_launcher_recent_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            self._write("recent_workflows=none")
            return
        self._write("recent_workflows:")
        for index, row in enumerate(rows, start=1):
            self._write(
                f"  {index}. {row['workflow_id']}  status={row['status'] or '-'}  phase={row['current_phase'] or '-'}  "
                f"kind={row['workflow_kind'] or '-'}"
            )
            self._write(f"     updated_at={row['updated_at'] or '-'}  goal={self._truncate(str(row.get('goal') or '-'), limit=96)}")

    def _prompt_workflow_selection(self, rows: list[dict[str, Any]], *, action_label: str) -> tuple[str, bool]:
        if not rows:
            raise FileNotFoundError("no local workflow shell state found")
        raw = str(self._input_fn(f"{action_label} workflow [enter=last, number, or workflow_id]: ")).strip()
        if not raw:
            return "", True
        if raw.isdigit():
            index = int(raw) - 1
            if 0 <= index < len(rows):
                return str(rows[index].get("workflow_id") or "").strip(), False
        return raw, False

    def launcher(self, args: argparse.Namespace) -> int:
        cfg, config_path, workspace_root = self._load_config(getattr(args, "config", None))
        launcher_default_kind = _launcher_default_kind(cfg)
        while True:
            rows = self._workflow_rows(workspace_root=workspace_root, limit=DEFAULT_WORKFLOW_LAUNCHER_RECENT_LIMIT)
            last_row = rows[0] if rows else {}
            last_status = str(last_row.get("status") or "").strip().lower()
            default_action = "2" if last_row and last_status != "completed" else "1"
            self._write("[workflow launcher]")
            self._write(f"config={config_path}")
            self._write(f"workspace={workspace_root}")
            self._write(f"workflow_shell_root={build_workflow_shell_root(workspace_root)}")
            self._write(f"codex_available={'yes' if cli_provider_available('codex', cfg) else 'no'}")
            self._write(f"cursor_available={'yes' if cli_provider_available('cursor', cfg) else 'no'}")
            disabled_mcp = _workflow_disabled_mcp_servers(cfg)
            self._write(f"codex_mcp_guard={', '.join(disabled_mcp) if disabled_mcp else '-'}")
            if last_row:
                self._write(
                    f"last={last_row['workflow_id']} status={last_row['status'] or '-'} phase={last_row['current_phase'] or '-'} "
                    f"kind={last_row['workflow_kind'] or '-'}"
                )
            self._print_launcher_recent_rows(rows)
            self._write("actions: [1] run  [2] resume  [3] status  [4] list  [5] preflight  [q] quit")
            choice = str(self._input_fn(f"select action [{default_action}]: ")).strip().lower()
            if not choice:
                choice = default_action
            if choice in {"q", "quit", "exit"}:
                return 0
            if choice in {"4", "list"}:
                self.list_workflows(
                    argparse.Namespace(command="list", config=config_path, limit=DEFAULT_WORKFLOW_LAUNCHER_RECENT_LIMIT, json=False)
                )
                continue
            if choice in {"5", "preflight"}:
                self.preflight(argparse.Namespace(command="preflight", config=config_path, json=False))
                continue
            if choice in {"3", "status"}:
                try:
                    workflow_id, use_last = self._prompt_workflow_selection(rows, action_label="status")
                except FileNotFoundError as exc:
                    self._write(f"[workflow] error: {exc}", err=True)
                    continue
                self.status(
                    argparse.Namespace(command="status", config=config_path, workflow_id=workflow_id, last=use_last, json=False)
                )
                continue
            if choice in {"2", "resume"}:
                try:
                    workflow_id, use_last = self._prompt_workflow_selection(rows, action_label="resume")
                except FileNotFoundError as exc:
                    self._write(f"[workflow] error: {exc}", err=True)
                    continue
                return self.resume(
                    argparse.Namespace(
                        command="resume",
                        config=config_path,
                        workflow_id=workflow_id,
                        last=use_last,
                        codex_session_id="",
                        kind=launcher_default_kind,
                        goal="",
                        guard_condition="",
                        max_attempts=0,
                        max_phase_attempts=0,
                        no_stream=False,
                    )
                )
            if choice not in {"1", "run", "new"}:
                self._write(f"[workflow] error: unsupported selection `{choice}`", err=True)
                continue
            workflow_kind = str(
                self._input_fn(f"workflow kind [{launcher_default_kind}] ({PROJECT_LOOP_KIND}/{SINGLE_GOAL_KIND}): ")
            ).strip().lower() or launcher_default_kind
            if workflow_kind not in {SINGLE_GOAL_KIND, PROJECT_LOOP_KIND}:
                self._write(f"[workflow] error: unsupported workflow kind `{workflow_kind}`", err=True)
                continue
            goal = str(self._input_fn("goal: ")).strip()
            if not goal:
                self._write("[workflow] error: goal is required", err=True)
                continue
            guard_default = _default_guard_condition(workflow_kind)
            guard_condition = str(self._input_fn(f"guard condition [{guard_default}]: ")).strip() or guard_default
            return self.run_new(
                argparse.Namespace(
                    command="run",
                    config=config_path,
                    kind=workflow_kind,
                    goal=goal,
                    guard_condition=guard_condition,
                    max_attempts=None,
                    max_phase_attempts=None,
                    no_stream=False,
                )
            )

    def _build_codex_prompt(self, workflow_state: dict[str, Any], *, attempt_no: int, phase_attempt_no: int) -> str:
        pending = str(workflow_state.get("pending_codex_prompt") or "").strip()
        goal = str(workflow_state.get("goal") or "").strip()
        guard_condition = str(workflow_state.get("guard_condition") or "").strip()
        codex_session_id = str(workflow_state.get("codex_session_id") or "").strip()
        if workflow_state.get("workflow_kind") == PROJECT_LOOP_KIND:
            return build_project_phase_codex_prompt(
                goal=goal,
                guard_condition=guard_condition,
                phase=str(workflow_state.get("current_phase") or _default_phase(PROJECT_LOOP_KIND)).strip(),
                attempt_no=attempt_no,
                phase_attempt_no=phase_attempt_no,
                next_instruction=pending,
                resume_mode=bool(codex_session_id),
            )
        return build_single_goal_codex_prompt(
            goal=goal,
            guard_condition=guard_condition,
            attempt_no=attempt_no,
            next_instruction=pending,
            resume_mode=bool(codex_session_id),
        )

    def _judge_attempt(self, cfg: dict[str, Any], workflow_state: dict[str, Any], *, codex_receipt, attempt_no: int, phase_attempt_no: int):
        workflow_kind = str(workflow_state.get("workflow_kind") or "").strip()
        goal = str(workflow_state.get("goal") or "").strip()
        guard_condition = str(workflow_state.get("guard_condition") or "").strip()
        phase = str(workflow_state.get("current_phase") or _default_phase(workflow_kind)).strip()
        codex_output = _receipt_text(codex_receipt)
        codex_metadata = dict(getattr(codex_receipt, "metadata", {}) or {})
        codex_session_id = str(workflow_state.get("codex_session_id") or _receipt_thread_id(codex_receipt)).strip()
        phase_artifact = _build_phase_artifact(
            workflow_state,
            phase=phase,
            attempt_no=attempt_no,
            phase_attempt_no=phase_attempt_no,
            codex_receipt=codex_receipt,
        )
        workflow_state["current_phase_artifact"] = dict(phase_artifact)
        recent_history = _recent_phase_history(workflow_state)
        if workflow_kind == PROJECT_LOOP_KIND:
            judge_prompt = build_project_loop_judge_prompt(
                workflow_kind=workflow_kind,
                goal=goal,
                guard_condition=guard_condition,
                phase=phase,
                attempt_no=attempt_no,
                phase_attempt_no=phase_attempt_no,
                codex_status=str(getattr(codex_receipt, "status", "") or "").strip(),
                codex_session_id=codex_session_id,
                codex_output=codex_output,
                codex_metadata=codex_metadata,
                phase_history=recent_history,
                phase_artifact=phase_artifact,
            )
        else:
            judge_prompt = build_single_goal_judge_prompt(
                workflow_kind=workflow_kind,
                goal=goal,
                guard_condition=guard_condition,
                phase=phase,
                attempt_no=attempt_no,
                codex_status=str(getattr(codex_receipt, "status", "") or "").strip(),
                codex_session_id=codex_session_id,
                codex_output=codex_output,
                codex_metadata=codex_metadata,
                phase_history=recent_history,
                phase_artifact=phase_artifact,
            )
        cursor_receipt = self._run_prompt_receipt_fn(
            judge_prompt,
            str(workflow_state.get("workspace_root") or "."),
            _judge_timeout_seconds(cfg),
            cfg,
            {
                "cli": "cursor",
                "_disable_runtime_fallback": True,
                "workflow_id": str(workflow_state.get("workflow_id") or "").strip(),
                "agent_id": "workflow_shell.cursor_judge",
            },
            stream=False,
        )
        if str(getattr(cursor_receipt, "status", "") or "").strip() != "completed":
            reason = _receipt_text(cursor_receipt) or "Cursor judge did not complete successfully"
            if workflow_state.get("workflow_kind") == PROJECT_LOOP_KIND:
                decision = _normalize_project_decision({}, fallback_reason=reason)
            else:
                decision = _normalize_single_goal_decision({}, fallback_reason=reason)
            decision["reason"] = reason
            decision["next_codex_prompt"] = ""
            return cursor_receipt, decision
        raw_payload = _parse_json_object(_receipt_text(cursor_receipt))
        reason = "Cursor judge returned invalid JSON"
        if workflow_kind == PROJECT_LOOP_KIND:
            decision = _normalize_project_decision(raw_payload, fallback_reason=reason)
            decision = _normalize_project_loop_decision(decision, phase=phase)
        else:
            decision = _normalize_single_goal_decision(raw_payload, fallback_reason=reason)
        if not decision.get("next_codex_prompt") and decision.get("decision") in {"RETRY", "ADVANCE"}:
            decision["next_codex_prompt"] = _build_default_retry_instruction(
                workflow_state,
                codex_ok=str(getattr(codex_receipt, "status", "") or "").strip() == "completed",
            )
        return cursor_receipt, decision

    def _run_workflow_loop(self, cfg: dict[str, Any], workflow_dir: Path, workflow_state: dict[str, Any], *, stream_enabled: bool) -> int:
        state_store = FileRuntimeStateStore(workflow_dir)
        cleanup = state_store.cleanup_before_start(pid_probe=_pid_probe)
        locked, _ = state_store.acquire_lock(current_pid=os.getpid(), pid_probe=_pid_probe)
        if not locked:
            owner = state_store.read_pid()
            raise RuntimeError(f"workflow is already running under pid={owner or 'unknown'}")
        trace_store = FileTraceStore(state_store.traces_dir())
        _ensure_trace(
            trace_store,
            run_id=str(workflow_state.get("trace_run_id") or workflow_state.get("workflow_id") or "").strip(),
            metadata={
                "workflow_kind": str(workflow_state.get("workflow_kind") or "").strip(),
                "goal": str(workflow_state.get("goal") or "").strip(),
                "guard_condition": str(workflow_state.get("guard_condition") or "").strip(),
                "cleanup": cleanup,
            },
        )
        workflow_id = str(workflow_state.get("workflow_id") or "").strip()
        trace_store.append_event(workflow_id, phase=str(workflow_state.get("current_phase") or "").strip(), event_type="workflow.shell.start", payload={"cleanup": cleanup})
        state_store.write_pid(os.getpid())
        state_store.write_watchdog_state(state="foreground", pid=os.getpid(), note="workflow shell active")
        try:
            while True:
                attempt_count = _safe_int(workflow_state.get("attempt_count"), 0)
                max_attempts = max(1, _safe_int(workflow_state.get("max_attempts"), DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS))
                if attempt_count >= max_attempts:
                    workflow_state["status"] = "failed"
                    workflow_state["last_completion_summary"] = f"attempt limit reached: {attempt_count}/{max_attempts}"
                    self._save_workflow_state(workflow_dir, workflow_state)
                    trace_store.append_event(workflow_id, phase=str(workflow_state.get("current_phase") or "").strip(), event_type="workflow.failed", payload={"reason": workflow_state["last_completion_summary"]})
                    return 1
                if workflow_state.get("workflow_kind") == PROJECT_LOOP_KIND:
                    phase_attempts = _sync_project_phase_attempt_count(workflow_state)
                    max_phase_attempts = max(1, _safe_int(workflow_state.get("max_phase_attempts"), DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS))
                    if phase_attempts >= max_phase_attempts:
                        workflow_state["status"] = "failed"
                        workflow_state["last_completion_summary"] = (
                            f"phase attempt limit reached for {workflow_state.get('current_phase')}: "
                            f"{phase_attempts}/{max_phase_attempts}"
                        )
                        self._save_workflow_state(workflow_dir, workflow_state)
                        trace_store.append_event(workflow_id, phase=str(workflow_state.get("current_phase") or "").strip(), event_type="workflow.failed", payload={"reason": workflow_state["last_completion_summary"]})
                        return 1

                attempt_no = attempt_count + 1
                phase = str(workflow_state.get("current_phase") or _default_phase(str(workflow_state.get("workflow_kind") or ""))).strip()
                phase_attempt_no = _safe_int(workflow_state.get("phase_attempt_count"), 0) + 1
                workflow_state["status"] = "running"
                self._save_workflow_state(workflow_dir, workflow_state)
                state_store.write_run_state(
                    run_id=workflow_id,
                    state="running",
                    phase=phase,
                    pid=os.getpid(),
                    note=f"attempt {attempt_no} phase={phase}",
                )
                self._write(f"[workflow] attempt={attempt_no} phase={phase} workflow_id={workflow_id}")
                codex_prompt = self._build_codex_prompt(workflow_state, attempt_no=attempt_no, phase_attempt_no=phase_attempt_no)
                trace_store.append_event(workflow_id, phase=phase, event_type="codex.attempt.start", payload={"attempt_no": attempt_no, "phase_attempt_no": phase_attempt_no})
                console = self._build_console() if stream_enabled else None
                printer = TerminalStreamPrinter(console=console, prefix="codex> ") if console is not None else None
                codex_receipt = self._run_prompt_receipt_fn(
                    codex_prompt,
                    str(workflow_state.get("workspace_root") or "."),
                    _workflow_timeout_seconds(cfg),
                    cfg,
                    self._build_codex_runtime_request(
                        cfg,
                        workflow_id=workflow_id,
                        workflow_state=workflow_state,
                        workflow_dir=workflow_dir,
                    ),
                    stream=stream_enabled,
                    on_segment=printer.on_segment if printer is not None else None,
                    on_event=console.emit_runtime_event if console is not None else None,
                )
                if printer is not None:
                    printer.finalize(_receipt_text(codex_receipt))
                thread_id = _receipt_thread_id(codex_receipt)
                if thread_id:
                    workflow_state["codex_session_id"] = thread_id
                workflow_state["attempt_count"] = attempt_no
                workflow_state["last_codex_receipt"] = _serialize_receipt(codex_receipt)
                self._save_workflow_state(workflow_dir, workflow_state)
                trace_store.append_event(
                    workflow_id,
                    phase=phase,
                    event_type="codex.attempt.done" if str(getattr(codex_receipt, "status", "") or "").strip() == "completed" else "codex.attempt.failed",
                    payload={"attempt_no": attempt_no, "thread_id": str(workflow_state.get("codex_session_id") or "").strip()},
                )
                self._write("[workflow] cursor judge evaluating latest attempt")
                cursor_receipt, decision = self._judge_attempt(
                    cfg,
                    workflow_state,
                    codex_receipt=codex_receipt,
                    attempt_no=attempt_no,
                    phase_attempt_no=phase_attempt_no,
                )
                workflow_state["last_cursor_receipt"] = _serialize_receipt(cursor_receipt)
                workflow_state["last_cursor_decision"] = dict(decision or {})
                workflow_state["last_completion_summary"] = str(decision.get("completion_summary") or decision.get("reason") or "").strip()
                workflow_state["pending_codex_prompt"] = str(decision.get("next_codex_prompt") or "").strip()
                workflow_state["phase_history"] = list(workflow_state.get("phase_history") or []) + [
                    {
                        "at": _now_text(),
                        "attempt_no": attempt_no,
                        "phase": phase,
                        "codex_status": str(getattr(codex_receipt, "status", "") or "").strip(),
                        "cursor_status": str(getattr(cursor_receipt, "status", "") or "").strip(),
                        "decision": dict(decision or {}),
                    }
                ]
                if workflow_state.get("workflow_kind") == PROJECT_LOOP_KIND:
                    _sync_project_phase_attempt_count(workflow_state)
                self._save_workflow_state(workflow_dir, workflow_state)
                self._append_attempt_draft(
                    state_store=state_store,
                    attempt_no=attempt_no,
                    phase=phase,
                    codex_prompt=codex_prompt,
                    codex_receipt=codex_receipt,
                    cursor_receipt=cursor_receipt,
                    decision=decision,
                )
                trace_store.append_event(
                    workflow_id,
                    phase=phase,
                    event_type=f"judge.{str(decision.get('decision') or '').strip().lower() or 'unknown'}",
                    payload={"attempt_no": attempt_no, **dict(decision or {})},
                )
                self._write(
                    "[workflow] judge decision="
                    f"{str(decision.get('decision') or '').strip()} "
                    f"reason={str(decision.get('reason') or '').strip() or '-'}"
                )

                decision_name = str(decision.get("decision") or "").strip().upper()
                if decision_name == "COMPLETE":
                    workflow_state["status"] = "completed"
                    self._save_workflow_state(workflow_dir, workflow_state)
                    trace_store.append_event(workflow_id, phase=phase, event_type="workflow.completed", payload=dict(decision or {}))
                    return 0
                if decision_name == "ABORT":
                    workflow_state["status"] = "failed"
                    self._save_workflow_state(workflow_dir, workflow_state)
                    trace_store.append_event(workflow_id, phase=phase, event_type="workflow.aborted", payload=dict(decision or {}))
                    return 1
                if workflow_state.get("workflow_kind") != PROJECT_LOOP_KIND:
                    workflow_state["status"] = "running"
                    self._save_workflow_state(workflow_dir, workflow_state)
                    continue

                next_phase = str(decision.get("next_phase") or "").strip().lower()
                if decision_name == "ADVANCE":
                    if not next_phase:
                        next_phase = _phase_after(phase)
                elif decision_name == "RETRY":
                    if not next_phase:
                        next_phase = phase
                else:
                    next_phase = phase
                if next_phase == DONE_PHASE:
                    workflow_state["status"] = "completed"
                    self._save_workflow_state(workflow_dir, workflow_state)
                    trace_store.append_event(workflow_id, phase=phase, event_type="workflow.completed", payload=dict(decision or {}))
                    return 0
                if next_phase != phase:
                    workflow_state["current_phase"] = next_phase
                    workflow_state["phase_attempt_count"] = 0
                    trace_store.append_event(workflow_id, phase=next_phase, event_type="workflow.phase.advance", payload={"from": phase, "to": next_phase})
                elif workflow_state.get("workflow_kind") == PROJECT_LOOP_KIND:
                    _sync_project_phase_attempt_count(workflow_state)
                workflow_state["status"] = "running"
                self._save_workflow_state(workflow_dir, workflow_state)
        except KeyboardInterrupt:
            workflow_state["status"] = "interrupted"
            workflow_state["last_completion_summary"] = "interrupted by user"
            self._save_workflow_state(workflow_dir, workflow_state)
            trace_store.append_event(
                workflow_id,
                phase=str(workflow_state.get("current_phase") or "").strip(),
                event_type="workflow.interrupted",
                payload={"reason": "user_interrupt"},
            )
            self._write("[workflow] interrupted by user")
            return 130
        finally:
            final_status = str(workflow_state.get("status") or "").strip() or "failed"
            final_phase = str(workflow_state.get("current_phase") or "").strip() or _default_phase(str(workflow_state.get("workflow_kind") or ""))
            final_note = str(workflow_state.get("last_completion_summary") or workflow_state.get("pending_codex_prompt") or "").strip()
            state_store.write_run_state(run_id=workflow_id, state=final_status, phase=final_phase, pid=0, note=final_note)
            state_store.write_watchdog_state(state=final_status or "stopped", pid=0, note=final_note)
            state_store.clear_pid()
            state_store.release_lock()

    def run_new(self, args: argparse.Namespace) -> int:
        cfg, config_path, workspace_root = self._load_config(getattr(args, "config", None))
        self._ensure_workflow_runtime(cfg)
        workflow_kind = str(getattr(args, "kind", "") or SINGLE_GOAL_KIND).strip()
        goal = self._prompt_value("Codex task: ", getattr(args, "goal", ""))
        guard_condition = self._prompt_value("Cursor guard condition: ", getattr(args, "guard_condition", ""))
        workflow_id = _new_workflow_id()
        workflow_dir = _workflow_dir(workspace_root, workflow_id)
        workflow_state = _new_workflow_state(
            workflow_id=workflow_id,
            workflow_kind=workflow_kind,
            workspace_root=workspace_root,
            goal=goal,
            guard_condition=guard_condition,
            max_attempts=_safe_int(getattr(args, "max_attempts", 0), DEFAULT_PROJECT_LOOP_MAX_ATTEMPTS if workflow_kind == PROJECT_LOOP_KIND else DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS),
            max_phase_attempts=_safe_int(getattr(args, "max_phase_attempts", 0), DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS),
        )
        self._save_workflow_state(workflow_dir, workflow_state)
        self._write(f"[workflow] config={config_path}")
        self._write(f"[workflow] workspace={workspace_root}")
        self._write(f"[workflow] workflow_id={workflow_id}")
        self._write(f"[workflow] workflow_dir={workflow_dir}")
        self._write(f"[workflow] kind={workflow_kind}")
        self._write(f"[workflow] goal={self._truncate(goal, limit=120)}")
        self._write(f"[workflow] guard={self._truncate(guard_condition, limit=120)}")
        return self._run_workflow_loop(cfg, workflow_dir, workflow_state, stream_enabled=not bool(getattr(args, "no_stream", False)))

    def resume(self, args: argparse.Namespace) -> int:
        cfg, config_path, workspace_root = self._load_config(getattr(args, "config", None))
        self._ensure_workflow_runtime(cfg)
        workflow_id = self._workflow_identity_from_args(workspace_root=workspace_root, args=args)
        if workflow_id:
            workflow_dir = _workflow_dir(workspace_root, workflow_id)
            workflow_state = _read_json(_workflow_state_path(workflow_dir))
            if not workflow_state:
                raise FileNotFoundError(f"workflow not found: {workflow_id}")
            if str(workflow_state.get("workflow_kind") or "").strip() == PROJECT_LOOP_KIND:
                _sync_project_phase_attempt_count(workflow_state)
            if str(getattr(args, "goal", "") or "").strip():
                workflow_state["goal"] = str(args.goal).strip()
            if str(getattr(args, "guard_condition", "") or "").strip():
                workflow_state["guard_condition"] = str(args.guard_condition).strip()
            if getattr(args, "max_attempts", None):
                workflow_state["max_attempts"] = _safe_int(args.max_attempts, workflow_state.get("max_attempts", DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS))
            if getattr(args, "max_phase_attempts", None):
                workflow_state["max_phase_attempts"] = _safe_int(args.max_phase_attempts, workflow_state.get("max_phase_attempts", DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS))
            if str(workflow_state.get("status") or "").strip() == "completed":
                self._write(f"[workflow] already completed: {workflow_id}")
                return 0
            self._save_workflow_state(workflow_dir, workflow_state)
            self._write(f"[workflow] config={config_path}")
            self._write(f"[workflow] resuming workflow_id={workflow_id}")
            self._write(f"[workflow] kind={workflow_state.get('workflow_kind')}")
            self._write(f"[workflow] goal={self._truncate(str(workflow_state.get('goal') or ''), limit=120)}")
            return self._run_workflow_loop(cfg, workflow_dir, workflow_state, stream_enabled=not bool(getattr(args, "no_stream", False)))

        codex_session_id = str(getattr(args, "codex_session_id", "") or "").strip()
        if not codex_session_id:
            raise ValueError("resume requires --workflow-id, --last, or --codex-session-id")
        goal = self._prompt_value("Codex task: ", getattr(args, "goal", ""))
        guard_condition = self._prompt_value("Cursor guard condition: ", getattr(args, "guard_condition", ""))
        workflow_kind = str(getattr(args, "kind", "") or SINGLE_GOAL_KIND).strip() or SINGLE_GOAL_KIND
        workflow_id = _new_workflow_id()
        workflow_dir = _workflow_dir(workspace_root, workflow_id)
        workflow_state = _new_workflow_state(
            workflow_id=workflow_id,
            workflow_kind=workflow_kind,
            workspace_root=workspace_root,
            goal=goal,
            guard_condition=guard_condition,
            max_attempts=_safe_int(getattr(args, "max_attempts", 0), DEFAULT_PROJECT_LOOP_MAX_ATTEMPTS if workflow_kind == PROJECT_LOOP_KIND else DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS),
            max_phase_attempts=_safe_int(getattr(args, "max_phase_attempts", 0), DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS),
            codex_session_id=codex_session_id,
            resume_source="codex_session_id",
        )
        workflow_state["pending_codex_prompt"] = "Resume the provided Codex session, assess whether the goal is already satisfied, and continue until the guard condition is met."
        self._save_workflow_state(workflow_dir, workflow_state)
        self._write(f"[workflow] config={config_path}")
        self._write(f"[workflow] derived workflow_id={workflow_id}")
        self._write(f"[workflow] resuming codex_session_id={codex_session_id}")
        self._write(f"[workflow] kind={workflow_kind}")
        self._write(f"[workflow] goal={self._truncate(goal, limit=120)}")
        return self._run_workflow_loop(cfg, workflow_dir, workflow_state, stream_enabled=not bool(getattr(args, "no_stream", False)))

    def status(self, args: argparse.Namespace) -> int:
        _, _, workspace_root = self._load_config(getattr(args, "config", None))
        workflow_id = self._workflow_identity_from_args(workspace_root=workspace_root, args=args)
        if not workflow_id:
            raise ValueError("status requires --workflow-id or --last")
        payload = self._workflow_status_payload(workspace_root=workspace_root, workflow_id=workflow_id)
        if bool(getattr(args, "json", False)):
            self._write_json(payload)
            return 0
        workflow_state = dict(payload.get("workflow_state") or {})
        runtime = dict(payload.get("runtime_snapshot") or {})
        self._write(f"workflow_id={payload['workflow_id']}")
        self._write(f"workflow_dir={payload['workflow_dir']}")
        self._write(f"kind={workflow_state.get('workflow_kind')}")
        self._write(f"status={workflow_state.get('status')}")
        self._write(f"phase={workflow_state.get('current_phase')}")
        self._write(f"attempt_count={workflow_state.get('attempt_count')}/{workflow_state.get('max_attempts')}")
        self._write(f"codex_session_id={workflow_state.get('codex_session_id') or '-'}")
        self._write(f"process_state={runtime.get('process_state')} pid={runtime.get('pid') or 0}")
        self._write(f"last_decision={dict(workflow_state.get('last_cursor_decision') or {}).get('decision') or '-'}")
        self._write(f"last_summary={workflow_state.get('last_completion_summary') or '-'}")
        return 0


def _common_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", "-c", help="Path to Butler config json")
    return parser


def _workflow_subcommand_from_argv(argv: list[str]) -> str:
    skip_next = False
    for raw_token in list(argv or []):
        token = str(raw_token or "").strip()
        if not token:
            continue
        if skip_next:
            skip_next = False
            continue
        if token in {"-c", "--config"}:
            skip_next = True
            continue
        if token in {"-h", "--help"}:
            return ""
        if token.startswith("-"):
            continue
        return token
    return ""


def _stdin_is_interactive() -> bool:
    probe = getattr(sys.stdin, "isatty", None)
    try:
        return bool(callable(probe) and probe())
    except Exception:
        return False


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butler workflow",
        description="Butler foreground workflow shell",
        epilog=(
            "No subcommand on an interactive terminal opens the workflow launcher.\n\n"
            "Examples:\n"
            "  butler -workflow\n"
            "  butler -workflow run --goal \"Close the feature gap\" --guard-condition \"tests pass\"\n"
            "  butler workflow run --kind project_loop --goal \"Ship the workflow shell\"\n"
            "  butler workflow resume --last\n"
            "  butler workflow status --last\n"
            "  butler workflow list --limit 5\n"
            "  butler workflow preflight\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    common = _common_parser()
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", parents=[common], help="Run a new foreground workflow")
    run_parser.add_argument("--kind", choices=(SINGLE_GOAL_KIND, PROJECT_LOOP_KIND), default=SINGLE_GOAL_KIND)
    run_parser.add_argument("--goal", help="Primary goal for Codex")
    run_parser.add_argument("--guard-condition", help="Cursor judge condition")
    run_parser.add_argument("--max-attempts", type=int, help="Maximum total attempts before stopping")
    run_parser.add_argument("--max-phase-attempts", type=int, help="Maximum attempts within one project_loop phase")
    run_parser.add_argument("--no-stream", action="store_true", help="Disable foreground Codex streaming")

    free_parser = subparsers.add_parser("free", parents=[common], help="Compatibility alias for `run --kind single_goal`")
    free_parser.add_argument("--goal", help="Primary goal for Codex")
    free_parser.add_argument("--guard-condition", help="Cursor judge condition")
    free_parser.add_argument("--max-attempts", type=int, help="Maximum total attempts before stopping")
    free_parser.add_argument("--max-phase-attempts", type=int, help="Maximum attempts before stopping")
    free_parser.add_argument("--no-stream", action="store_true", help="Disable foreground Codex streaming")

    resume_parser = subparsers.add_parser("resume", parents=[common], help="Resume workflow by workflow_id or Codex session id")
    resume_parser.add_argument("--workflow-id", help="Local workflow shell id")
    resume_parser.add_argument("--last", action="store_true", help="Resume the most recent local workflow state")
    resume_parser.add_argument("--codex-session-id", help="Existing Codex session/thread id")
    resume_parser.add_argument("--kind", choices=(SINGLE_GOAL_KIND, PROJECT_LOOP_KIND), default=SINGLE_GOAL_KIND)
    resume_parser.add_argument("--goal", help="Primary goal for Codex when deriving a workflow from Codex session id")
    resume_parser.add_argument("--guard-condition", help="Cursor judge condition")
    resume_parser.add_argument("--max-attempts", type=int, help="Maximum total attempts before stopping")
    resume_parser.add_argument("--max-phase-attempts", type=int, help="Maximum attempts within one project_loop phase")
    resume_parser.add_argument("--no-stream", action="store_true", help="Disable foreground Codex streaming")

    status_parser = subparsers.add_parser("status", parents=[common], help="Show workflow shell status")
    status_parser.add_argument("--workflow-id", help="Local workflow shell id")
    status_parser.add_argument("--last", action="store_true", help="Inspect the most recent local workflow state")
    status_parser.add_argument("--json", action="store_true", help="Print full status payload as JSON")

    list_parser = subparsers.add_parser("list", parents=[common], help="List recent local workflow state")
    list_parser.add_argument("--limit", type=int, default=DEFAULT_WORKFLOW_LIST_LIMIT, help="Maximum rows to show")
    list_parser.add_argument("--json", action="store_true", help="Print the list as JSON")

    preflight_parser = subparsers.add_parser("preflight", parents=[common], help="Show workflow runtime availability and paths")
    preflight_parser.add_argument("--json", action="store_true", help="Print preflight payload as JSON")

    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if not _workflow_subcommand_from_argv(raw_argv):
        parser = build_arg_parser()
        if any(str(token or "").strip() in {"-h", "--help"} for token in raw_argv):
            parser.print_help()
            return 0
        if not _stdin_is_interactive():
            parser.print_help()
            return 0
        launcher_parser = _common_parser()
        launcher_args = launcher_parser.parse_args(raw_argv)
        app = WorkflowShellApp()
        try:
            return app.launcher(launcher_args)
        except KeyboardInterrupt:
            app._write("[workflow] interrupted by user", err=True)
            return 130
        except Exception as exc:
            app._write(f"[workflow] error: {type(exc).__name__}: {exc}", err=True)
            return 1
    parser = build_arg_parser()
    args = parser.parse_args(raw_argv)
    if not getattr(args, "command", ""):
        parser.print_help()
        return 0
    if args.command == "free":
        args.kind = SINGLE_GOAL_KIND
        args.command = "run"
    app = WorkflowShellApp()
    try:
        if args.command == "preflight":
            return app.preflight(args)
        if args.command == "list":
            return app.list_workflows(args)
        if args.command == "run":
            return app.run_new(args)
        if args.command == "resume":
            return app.resume(args)
        if args.command == "status":
            return app.status(args)
    except KeyboardInterrupt:
        app._write("[workflow] interrupted by user", err=True)
        return 130
    except Exception as exc:
        app._write(f"[workflow] error: {type(exc).__name__}: {exc}", err=True)
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
