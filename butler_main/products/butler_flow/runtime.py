from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from butler_main.agents_os.execution.cli_runner import cli_provider_available, run_prompt_receipt
from butler_main.chat.cli.runner import TerminalConsole, TerminalStreamPrinter

from .compiler import (
    build_flow_board,
    build_role_board,
    build_turn_task_packet,
    compile_packet,
    default_load_profile,
    session_mode_for_role,
)
from .constants import (
    CONTROL_PACKET_LARGE,
    CONTROL_PACKET_MEDIUM,
    CONTROL_PACKET_SMALL,
    DEFAULT_DISABLED_FLOW_MCP_SERVERS,
    DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS,
    DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS,
    DOCTOR_ROLE_ID,
    DONE_PHASE,
    EVIDENCE_LEVEL_MINIMAL,
    EVIDENCE_LEVEL_STANDARD,
    EVIDENCE_LEVEL_STRICT,
    EXECUTION_MODE_SIMPLE,
    GATE_CADENCE_PHASE,
    GATE_CADENCE_RISK_BASED,
    GATE_CADENCE_STRICT,
    MANAGED_FLOW_KIND,
    PROJECT_LOOP_KIND,
    PROJECT_PHASES,
    REPO_BINDING_DISABLED,
    REPO_BINDING_EXPLICIT,
    SINGLE_GOAL_KIND,
    SINGLE_GOAL_PHASE,
    normalize_execution_context,
)
from .flow_definition import first_phase_id, next_phase_id, phase_ids, phase_prompt_context, resolve_phase_plan
from .display import FlowDisplay
from .events import FlowLifecycleHook, FlowUiEventCallback, build_flow_ui_event, invoke_flow_hook
from .models import (
    CompiledPromptPacketV1,
    FlowActionReceiptV1,
    FlowBoardV1,
    FlowDecision,
    FlowMutationV1,
    FlowRuntimePlanV1,
    FlowStrategyEventV1,
    FlowTurnRecordV1,
    PromptPacketV1,
    RoleBoardV1,
    SupervisorDecisionV1,
    TurnTaskPacketV1,
)
from .prompts import (
    build_managed_flow_judge_prompt,
    build_managed_phase_codex_prompt,
    build_project_loop_judge_prompt,
    build_project_phase_codex_prompt,
    build_role_bound_codex_prompt,
    build_single_goal_codex_prompt,
    build_single_goal_judge_prompt,
    compact_json,
)
from .role_runtime import (
    append_handoff,
    build_prompt_overlay,
    create_handoff_packet,
    current_role_prompt,
    default_execution_mode,
    default_role_pack_id,
    determine_followup_role,
    extract_role_runtime_summary,
    is_ephemeral_role,
    latest_handoff_for_role,
    load_handoffs,
    load_role_sessions,
    mark_handoff_consumed,
    normalize_execution_mode,
    normalize_role_pack_id,
    normalize_session_strategy,
    record_latest_handoff,
    role_runtime_enabled,
    role_session_id_for_turn,
    save_role_sessions,
    select_active_role,
    stable_role_ids,
    session_strategy_for_mode,
    update_role_session_binding,
    visible_artifacts,
    bump_active_role_turn_no,
)
from .state import (
    FileRuntimeStateStore,
    FileTraceStore,
    append_governance_receipts,
    append_jsonl,
    append_task_receipt,
    default_control_profile,
    ensure_trace,
    ensure_flow_sidecars,
    flow_actions_path,
    flow_artifacts_path,
    flow_definition_path,
    flow_events_path,
    handoffs_path,
    role_sessions_path,
    runtime_plan_path,
    strategy_trace_path,
    mutations_path,
    prompt_packets_path,
    sync_flow_recovery_truth,
    sync_task_contract_truth,
    flow_state_path,
    flow_turns_path,
    now_text,
    prepare_flow_codex_home,
    read_flow_state,
    read_json,
    safe_int,
    normalize_control_profile_payload,
    normalize_doctor_policy_payload,
    write_json_atomic,
)


_UI_EVENT_LANE_BY_KIND = {
    "run_started": "system",
    "supervisor_input": "supervisor",
    "supervisor_output": "supervisor",
    "supervisor_decided": "supervisor",
    "supervisor_decision_applied": "supervisor",
    "approval_state_changed": "supervisor",
    "operator_action_applied": "supervisor",
    "judge_result": "supervisor",
    "manage_handoff_ready": "supervisor",
    "role_handoff_created": "workflow",
    "role_handoff_consumed": "workflow",
    "artifact_registered": "workflow",
    "phase_transition": "workflow",
    "codex_segment": "workflow",
    "codex_runtime_event": "workflow",
    "run_completed": "system",
    "run_failed": "system",
    "run_interrupted": "system",
    "error": "system",
    "warning": "supervisor",
}

_UI_EVENT_FAMILY_BY_KIND = {
    "run_started": "run",
    "supervisor_input": "input",
    "supervisor_output": "output",
    "supervisor_decided": "decision",
    "supervisor_decision_applied": "decision",
    "approval_state_changed": "approval",
    "operator_action_applied": "action",
    "judge_result": "decision",
    "manage_handoff_ready": "handoff",
    "role_handoff_created": "handoff",
    "role_handoff_consumed": "handoff",
    "artifact_registered": "artifact",
    "phase_transition": "phase",
    "codex_segment": "raw_execution",
    "codex_runtime_event": "raw_execution",
    "run_completed": "run",
    "run_failed": "run",
    "run_interrupted": "run",
    "error": "error",
    "warning": "risk",
}


def _infer_ui_event_lane(kind: str, payload: dict[str, Any]) -> str:
    resolved = _UI_EVENT_LANE_BY_KIND.get(str(kind or "").strip())
    if resolved:
        return resolved
    if any(key in payload for key in ("approval_state", "latest_supervisor_decision", "latest_operator_action")):
        return "supervisor"
    return "system"


def _infer_ui_event_family(kind: str, payload: dict[str, Any]) -> str:
    resolved = _UI_EVENT_FAMILY_BY_KIND.get(str(kind or "").strip())
    if resolved:
        return resolved
    if any(key in payload for key in ("handoff_id", "source_role_id", "target_role_id")):
        return "handoff"
    if "artifact_ref" in payload:
        return "artifact"
    if "decision" in payload:
        return "decision"
    return "system"


def _normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    return [text] if text else []


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


def _pid_probe(pid: int) -> dict[str, bool]:
    alive = False
    if int(pid or 0) > 0:
        try:
            os.kill(int(pid), 0)
            alive = True
        except Exception:
            alive = False
    return {"alive": alive, "matches": alive}


def _normalize_single_goal_decision(payload: dict[str, Any], *, fallback_reason: str = "") -> FlowDecision:
    decision = str(payload.get("decision") or "").strip().upper()
    if decision not in {"COMPLETE", "RETRY", "ABORT"}:
        decision = "ABORT"
    reason = str(payload.get("reason") or fallback_reason or "").strip()
    normalized: FlowDecision = {
        "decision": decision,
        "reason": reason,
        "next_codex_prompt": str(payload.get("next_codex_prompt") or "").strip(),
        "completion_summary": str(payload.get("completion_summary") or "").strip(),
    }
    issue_kind = str(payload.get("issue_kind") or "").strip().lower()
    if issue_kind in {"agent_cli_fault", "bug", "service_fault", "plan_gap", "none"}:
        normalized["issue_kind"] = issue_kind
    followup_kind = str(payload.get("followup_kind") or "").strip().lower()
    if followup_kind in {"fix", "retry", "replan", "none"}:
        normalized["followup_kind"] = followup_kind
    return normalized


def _normalize_project_decision(
    payload: dict[str, Any],
    *,
    fallback_reason: str = "",
    phase_plan: list[dict[str, Any]] | None = None,
) -> FlowDecision:
    decision = str(payload.get("decision") or "").strip().upper()
    if decision not in {"ADVANCE", "RETRY", "COMPLETE", "ABORT"}:
        decision = "ABORT"
    next_phase = str(payload.get("next_phase") or "").strip().lower()
    if next_phase == "complete":
        next_phase = DONE_PHASE
    valid_next_phases = set(phase_ids(list(phase_plan or []))) or {*PROJECT_PHASES}
    if next_phase not in {*valid_next_phases, DONE_PHASE, ""}:
        next_phase = ""
    reason = str(payload.get("reason") or fallback_reason or "").strip()
    normalized: FlowDecision = {
        "decision": decision,
        "next_phase": next_phase,
        "reason": reason,
        "next_codex_prompt": str(payload.get("next_codex_prompt") or "").strip(),
        "completion_summary": str(payload.get("completion_summary") or "").strip(),
    }
    issue_kind = str(payload.get("issue_kind") or "").strip().lower()
    if issue_kind in {"agent_cli_fault", "bug", "service_fault", "plan_gap", "none"}:
        normalized["issue_kind"] = issue_kind
    followup_kind = str(payload.get("followup_kind") or "").strip().lower()
    if followup_kind in {"fix", "retry", "replan", "none"}:
        normalized["followup_kind"] = followup_kind
    return normalized


def _default_phase(flow_kind: str) -> str:
    if flow_kind == SINGLE_GOAL_KIND:
        return SINGLE_GOAL_PHASE
    return first_phase_id(resolve_phase_plan({"workflow_kind": flow_kind}), workflow_kind=flow_kind)


def _phase_after(flow_state: dict[str, Any], phase: str) -> str:
    plan = resolve_phase_plan(flow_state)
    return next_phase_id(plan, phase) or DONE_PHASE


def _flow_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    raw = cfg.get("butler_flow")
    if isinstance(raw, dict):
        return dict(raw or {})
    raw = cfg.get("workflow_shell")
    return dict(raw or {}) if isinstance(raw, dict) else {}


def _supervisor_runtime_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    raw = _flow_settings(cfg).get("supervisor_runtime")
    return dict(raw or {}) if isinstance(raw, dict) else {}


def llm_supervisor_enabled(cfg: dict[str, Any]) -> bool:
    settings = _supervisor_runtime_settings(cfg)
    configured = settings.get("enable_llm_supervisor")
    if isinstance(configured, bool):
        return configured
    return False


def _launcher_default_kind(cfg: dict[str, Any]) -> str:
    configured = str(_flow_settings(cfg).get("launcher_default_kind") or "").strip().lower()
    if configured in {SINGLE_GOAL_KIND, PROJECT_LOOP_KIND}:
        return configured
    return PROJECT_LOOP_KIND


def _default_guard_condition(flow_kind: str) -> str:
    if flow_kind == PROJECT_LOOP_KIND:
        return "If Codex is interrupted, continue; advance plan -> imp -> review, and only finish after review passes."
    return "If Codex is interrupted, continue until the goal is clearly satisfied or blocked."


AUTO_FIX_MAX_ROUNDS = 2
DEFAULT_DISABLED_TIMEOUT_SECONDS = 24 * 60 * 60
_SERVICE_FAULT_MARKERS = (
    "timeout",
    "timed out",
    "network",
    "connection reset",
    "connection refused",
    "temporarily unavailable",
    "service unavailable",
    "provider unavailable",
    "http 429",
    "http 5",
    "thread/resume failed",
    "no rollout found",
    "too many requests",
)
_AGENT_CLI_FAULT_MARKERS = (
    "agent cli",
    "codex cli",
    "cursor cli",
    "cli invocation",
    "invocation failed",
    "invalid option",
    "unknown option",
    "unrecognized arguments",
    "unsupported flag",
    "failed to parse",
    "parse error",
    "failed to spawn",
    "bootstrap",
    "config.toml",
    "authrequired",
    "rmcp::transport::worker",
    "mcp worker",
    "mcp server config",
    "mcp config",
)


def _toml_escape(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def flow_disabled_mcp_servers(cfg: dict[str, Any]) -> list[str]:
    settings = _flow_settings(cfg)
    if "disable_mcp_servers" in settings:
        requested = _normalize_text_list(settings.get("disable_mcp_servers"))
        return requested
    return list(DEFAULT_DISABLED_FLOW_MCP_SERVERS.keys())


def _flow_mcp_server_specs(cfg: dict[str, Any]) -> dict[str, dict[str, str]]:
    specs = {name: dict(payload) for name, payload in DEFAULT_DISABLED_FLOW_MCP_SERVERS.items()}
    raw_specs = _flow_settings(cfg).get("mcp_server_specs")
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


def flow_codex_config_overrides(cfg: dict[str, Any]) -> list[str]:
    specs = _flow_mcp_server_specs(cfg)
    overrides: list[str] = []
    for server_name in flow_disabled_mcp_servers(cfg):
        spec = dict(specs.get(str(server_name or "").strip()) or {})
        transport = str(spec.get("transport") or "").strip()
        url = str(spec.get("url") or "").strip()
        if not transport or not url:
            continue
        overrides.append(
            f'mcp_servers.{server_name}={{enabled=false,transport="{_toml_escape(transport)}",url="{_toml_escape(url)}"}}'
        )
    return overrides


def _current_project_phase_attempt_count(flow_state: dict[str, Any]) -> int:
    if str(flow_state.get("workflow_kind") or "").strip() not in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
        return 0
    phase = str(flow_state.get("current_phase") or _default_phase(str(flow_state.get("workflow_kind") or ""))).strip()
    count = 0
    for row in reversed(list(flow_state.get("phase_history") or [])):
        if str(row.get("phase") or "").strip() != phase:
            break
        if str(row.get("codex_status") or "").strip() == "completed":
            count += 1
    return count


def _new_flow_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"


def _append_unique_ref(flow_state: dict[str, Any], field: str, value: str) -> None:
    text = str(value or "").strip()
    if not text:
        return
    existing = [str(item or "").strip() for item in list(flow_state.get(field) or []) if str(item or "").strip()]
    if text not in existing:
        existing.append(text)
    flow_state[field] = existing


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _runtime_elapsed_seconds(flow_state: dict[str, Any]) -> int:
    started_at = _parse_timestamp(flow_state.get("runtime_started_at"))
    if started_at is None:
        return int(safe_int(flow_state.get("runtime_elapsed_seconds"), 0))
    return max(0, int((datetime.now() - started_at).total_seconds()))


def _refresh_runtime_clock(flow_state: dict[str, Any]) -> int:
    elapsed = _runtime_elapsed_seconds(flow_state)
    flow_state["runtime_elapsed_seconds"] = elapsed
    return elapsed


def _normalize_usage_payload(metadata: dict[str, Any] | None) -> dict[str, Any]:
    usage = dict((metadata or {}).get("usage") or {})
    normalized: dict[str, Any] = {}
    for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
        if usage.get(key) is None:
            continue
        normalized[key] = int(safe_int(usage.get(key), 0))
    return normalized


def _queued_operator_updates(flow_state: dict[str, Any], *, include_executed: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list(flow_state.get("queued_operator_updates") or []):
        row = dict(item or {})
        if not row:
            continue
        status = str(row.get("status") or "queued").strip().lower() or "queued"
        row["status"] = status
        if include_executed or status != "executed":
            rows.append(row)
    return rows


def _next_operator_update(flow_state: dict[str, Any]) -> dict[str, Any]:
    for row in _queued_operator_updates(flow_state):
        if str(row.get("status") or "").strip() in {"queued", "planned"}:
            return row
    return {}


def _replace_operator_update(flow_state: dict[str, Any], update_id: str, replacement: dict[str, Any]) -> None:
    target = str(update_id or "").strip()
    rows: list[dict[str, Any]] = []
    for item in list(flow_state.get("queued_operator_updates") or []):
        row = dict(item or {})
        current_id = str(row.get("update_id") or "").strip()
        if current_id and current_id == target:
            rows.append(dict(replacement or {}))
        else:
            rows.append(row)
    flow_state["queued_operator_updates"] = rows


def _queue_operator_update(
    flow_state: dict[str, Any],
    *,
    instruction: str,
    action_id: str,
    source: str,
    replace_existing: bool = False,
) -> dict[str, Any]:
    update = {
        "update_id": str(action_id or _new_flow_id("op_update")).strip(),
        "source": str(source or "operator").strip(),
        "instruction": str(instruction or "").strip(),
        "status": "queued",
        "created_at": now_text(),
        "planned_attempt_no": 0,
        "executed_attempt_no": 0,
    }
    existing = [dict(item or {}) for item in list(flow_state.get("queued_operator_updates") or [])]
    if replace_existing:
        existing = [row for row in existing if str(row.get("status") or "").strip().lower() == "executed"]
    existing.append(update)
    flow_state["queued_operator_updates"] = existing
    return update


def _merge_operator_updates(flow_state: dict[str, Any], external_state: dict[str, Any]) -> None:
    external_updates = [dict(item or {}) for item in list(external_state.get("queued_operator_updates") or [])]
    if not external_updates:
        return
    existing = [dict(item or {}) for item in list(flow_state.get("queued_operator_updates") or [])]
    existing_index = {
        str(item.get("update_id") or "").strip(): idx
        for idx, item in enumerate(existing)
        if str(item.get("update_id") or "").strip()
    }
    for update in external_updates:
        update_id = str(update.get("update_id") or "").strip()
        if not update_id:
            continue
        if update_id in existing_index:
            idx = existing_index[update_id]
            merged = dict(existing[idx])
            merged.update(update)
            if str(existing[idx].get("status") or "").strip() == "executed":
                merged["status"] = "executed"
                if existing[idx].get("executed_at") and not merged.get("executed_at"):
                    merged["executed_at"] = existing[idx].get("executed_at")
            existing[idx] = merged
        else:
            existing.append(dict(update))
    flow_state["queued_operator_updates"] = existing


def _plan_operator_update_for_attempt(flow_state: dict[str, Any], *, attempt_no: int) -> dict[str, Any]:
    update = _next_operator_update(flow_state)
    update_id = str(update.get("update_id") or "").strip()
    if not update_id:
        return {}
    if str(update.get("status") or "").strip() == "queued":
        update["status"] = "planned"
        update["planned_attempt_no"] = int(attempt_no or 0)
        _replace_operator_update(flow_state, update_id, update)
    return update


def _mark_operator_update_executed(flow_state: dict[str, Any], *, attempt_no: int, codex_status: str) -> dict[str, Any]:
    for item in list(flow_state.get("queued_operator_updates") or []):
        row = dict(item or {})
        if str(row.get("status") or "").strip() != "planned":
            continue
        row["status"] = "executed"
        row["executed_attempt_no"] = int(attempt_no or 0)
        row["executed_at"] = now_text()
        row["executor_status"] = str(codex_status or "").strip()
        _replace_operator_update(flow_state, str(row.get("update_id") or "").strip(), row)
        return row
    return {}


def _active_operator_instruction(flow_state: dict[str, Any]) -> str:
    return str(_next_operator_update(flow_state).get("instruction") or "").strip()


def _compose_next_instruction(flow_state: dict[str, Any]) -> str:
    operator_instruction = _active_operator_instruction(flow_state)
    pending = str(flow_state.get("pending_codex_prompt") or "").strip()
    if operator_instruction and pending and operator_instruction != pending:
        return (
            "[operator update]\n"
            f"{operator_instruction}\n\n"
            "[runtime follow-up]\n"
            f"{pending}"
        ).strip()
    return operator_instruction or pending


def _append_phase_snapshot(flow_state: dict[str, Any], *, phase: str, attempt_no: int, reason: str) -> None:
    snapshots = [dict(item or {}) for item in list(flow_state.get("phase_snapshots") or [])]
    snapshots.append(
        {
            "snapshot_id": _new_flow_id("phase_snapshot"),
            "phase": str(phase or "").strip(),
            "attempt_no": int(attempt_no or 0),
            "reason": str(reason or "").strip(),
            "created_at": now_text(),
            "latest_supervisor_decision": dict(flow_state.get("latest_supervisor_decision") or {}),
            "latest_judge_decision": dict(flow_state.get("latest_judge_decision") or flow_state.get("last_cursor_decision") or {}),
            "latest_token_usage": dict(flow_state.get("latest_token_usage") or {}),
        }
    )
    flow_state["phase_snapshots"] = snapshots[-24:]


def _governor_state(flow_state: dict[str, Any], *, attempt_no: int) -> dict[str, Any]:
    latest_usage = dict(flow_state.get("latest_token_usage") or {})
    control_profile = dict(flow_state.get("control_profile") or {})
    input_tokens = int(safe_int(latest_usage.get("input_tokens"), 0))
    service_fault_streak = int(safe_int(flow_state.get("service_fault_streak"), 0))
    session_epoch = int(safe_int(flow_state.get("session_epoch"), 0))
    packet_size = str(control_profile.get("packet_size") or CONTROL_PACKET_MEDIUM).strip().lower()
    evidence_level = str(control_profile.get("evidence_level") or EVIDENCE_LEVEL_STANDARD).strip().lower()
    gate_cadence = str(control_profile.get("gate_cadence") or GATE_CADENCE_PHASE).strip().lower()
    compact_attempt_threshold = 6
    reset_attempt_threshold = 10
    compact_input_threshold = 120000
    reset_input_threshold = 180000
    compact_fault_threshold = 2
    reset_fault_threshold = 4
    if packet_size == CONTROL_PACKET_LARGE:
        compact_attempt_threshold = max(3, compact_attempt_threshold - 1)
        reset_attempt_threshold = max(6, reset_attempt_threshold - 1)
    elif packet_size == CONTROL_PACKET_SMALL:
        compact_attempt_threshold += 1
        reset_attempt_threshold += 1
    if evidence_level == EVIDENCE_LEVEL_STRICT:
        compact_attempt_threshold = max(3, compact_attempt_threshold - 1)
        compact_input_threshold = max(90000, compact_input_threshold - 20000)
    elif evidence_level == EVIDENCE_LEVEL_MINIMAL:
        compact_input_threshold += 20000
    if gate_cadence == GATE_CADENCE_STRICT:
        compact_attempt_threshold = min(compact_attempt_threshold, 4)
        reset_attempt_threshold = min(reset_attempt_threshold, 8)
        compact_fault_threshold = 1
        reset_fault_threshold = 3
    elif gate_cadence == GATE_CADENCE_RISK_BASED:
        compact_attempt_threshold += 1
    mode = "normal"
    reasons: list[str] = []
    if attempt_no >= compact_attempt_threshold:
        reasons.append("late_attempt_window")
    if input_tokens >= compact_input_threshold:
        reasons.append("large_input_context")
    if service_fault_streak >= compact_fault_threshold:
        reasons.append("repeated_service_fault")
    if reasons:
        mode = "compact"
    if (
        input_tokens >= reset_input_threshold
        or service_fault_streak >= reset_fault_threshold
        or attempt_no >= reset_attempt_threshold
    ):
        mode = "reset"
    governor = {
        "mode": mode,
        "reasons": reasons,
        "input_tokens": input_tokens,
        "service_fault_streak": service_fault_streak,
        "session_epoch": session_epoch,
        "packet_size": packet_size,
        "evidence_level": evidence_level,
        "gate_cadence": gate_cadence,
        "updated_at": now_text(),
    }
    previous_mode = str(dict(flow_state.get("context_governor") or {}).get("mode") or "").strip()
    if mode == "reset" and previous_mode != "reset":
        flow_state["session_epoch"] = session_epoch + 1
        governor["session_epoch"] = int(flow_state.get("session_epoch") or 0)
    flow_state["context_governor"] = governor
    return governor


def _runtime_budget_reached(flow_state: dict[str, Any]) -> bool:
    budget = int(safe_int(flow_state.get("max_runtime_seconds"), 0))
    if budget <= 0:
        return False
    return _refresh_runtime_clock(flow_state) >= budget


def _packet_size_for_mode(packet_size: str, *, mode: str) -> str:
    normalized = str(packet_size or "").strip().lower()
    if normalized not in {CONTROL_PACKET_SMALL, CONTROL_PACKET_MEDIUM, CONTROL_PACKET_LARGE}:
        normalized = CONTROL_PACKET_MEDIUM
    if mode == "reset":
        return CONTROL_PACKET_SMALL
    if mode == "compact" and normalized == CONTROL_PACKET_LARGE:
        return CONTROL_PACKET_MEDIUM
    return normalized


def _evidence_level_for_mode(evidence_level: str, *, mode: str) -> str:
    normalized = str(evidence_level or "").strip().lower()
    if normalized not in {EVIDENCE_LEVEL_MINIMAL, EVIDENCE_LEVEL_STANDARD, EVIDENCE_LEVEL_STRICT}:
        normalized = EVIDENCE_LEVEL_STANDARD
    if mode == "reset" and normalized == EVIDENCE_LEVEL_STRICT:
        return EVIDENCE_LEVEL_STANDARD
    return normalized


def _turn_kind_for_phase(phase: str) -> str:
    normalized = str(phase or "").strip().lower()
    if normalized in {"plan", "execute", "review", "recover", "operator_wait", "handoff"}:
        return normalized
    if normalized == "imp":
        return "execute"
    if normalized == "wait_operator":
        return "operator_wait"
    return "execute"


def sync_project_phase_attempt_count(flow_state: dict[str, Any]) -> int:
    count = _current_project_phase_attempt_count(flow_state)
    flow_state["phase_attempt_count"] = count
    return count


def flow_timeout_seconds(cfg: dict[str, Any]) -> int:
    raw = _flow_settings(cfg).get("timeout_seconds")
    if raw is None:
        return DEFAULT_DISABLED_TIMEOUT_SECONDS
    value = safe_int(raw, 0)
    if value <= 0:
        return DEFAULT_DISABLED_TIMEOUT_SECONDS
    return max(60, min(DEFAULT_DISABLED_TIMEOUT_SECONDS, value))


def judge_timeout_seconds(cfg: dict[str, Any]) -> int:
    raw = _flow_settings(cfg).get("judge_timeout_seconds")
    if raw is None:
        return DEFAULT_DISABLED_TIMEOUT_SECONDS
    value = safe_int(raw, 0)
    if value <= 0:
        return DEFAULT_DISABLED_TIMEOUT_SECONDS
    return max(30, min(DEFAULT_DISABLED_TIMEOUT_SECONDS, value))


def flow_fix_turns_enabled(cfg: dict[str, Any] | None) -> bool:
    settings = _flow_settings(cfg)
    if "enable_fix_turns" not in settings:
        return False
    return bool(settings.get("enable_fix_turns"))


def _build_default_retry_instruction(flow_state: dict[str, Any], *, codex_ok: bool) -> str:
    if flow_state.get("workflow_kind") in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
        phase = str(flow_state.get("current_phase") or "").strip()
        if phase == "review":
            return "Continue the same session, fix the review blockers, rerun verification, and update the repo."
        if phase == "imp":
            return "Continue the same session, finish the implementation work, and verify."
        return "Continue the same session, tighten the plan, confirm files/tests, and prepare a concrete path."
    if codex_ok:
        return "Continue the same session and close the remaining gap until the guard condition is satisfied."
    return "Resume the same session, recover from the interruption, and continue toward the guard condition."


def _build_default_fix_instruction(flow_state: dict[str, Any], *, phase: str) -> str:
    if flow_state.get("workflow_kind") in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
        return (
            "Continue the same session, repair the local Butler/Codex/Cursor CLI invocation or runtime integration fault, "
            "restore normal agent execution, verify the CLI path with the minimal relevant command, and do not spend this turn on business-level repo bugs."
        )
    return (
        "Continue the same session, repair the local Butler/Codex/Cursor CLI invocation or runtime integration fault, "
        "restore normal agent execution, verify the CLI path, and do not spend this turn on business-level repo bugs."
    )


def _build_default_replan_instruction(flow_state: dict[str, Any]) -> str:
    if flow_state.get("workflow_kind") in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
        return "Resume the same session, repair the plan, identify the right files/tests, and produce a tighter path before more implementation."
    return "Resume the same session, reassess the approach, and tighten the plan before continuing."


def _looks_like_service_fault_text(*values: str) -> bool:
    haystack = " ".join(str(item or "").strip().lower() for item in values if str(item or "").strip())
    if not haystack:
        return False
    return any(marker in haystack for marker in _SERVICE_FAULT_MARKERS)


def _looks_like_agent_cli_fault_text(*values: str) -> bool:
    haystack = " ".join(str(item or "").strip().lower() for item in values if str(item or "").strip())
    if not haystack:
        return False
    return any(marker in haystack for marker in _AGENT_CLI_FAULT_MARKERS)


def _looks_like_resume_no_rollout_failure(*values: str) -> bool:
    haystack = " ".join(str(item or "").strip().lower() for item in values if str(item or "").strip())
    if not haystack:
        return False
    return "thread/resume failed" in haystack or "no rollout found" in haystack


def _classify_decision_defaults(
    decision: FlowDecision,
    *,
    phase: str,
    codex_status: str,
    allow_fix_turns: bool,
) -> FlowDecision:
    normalized = dict(decision or {})
    decision_name = str(normalized.get("decision") or "").strip().upper()
    next_phase = str(normalized.get("next_phase") or "").strip().lower()
    reason = str(normalized.get("reason") or "").strip()
    next_codex_prompt = str(normalized.get("next_codex_prompt") or "").strip()
    completion_summary = str(normalized.get("completion_summary") or "").strip()
    issue_kind = str(normalized.get("issue_kind") or "").strip().lower()
    followup_kind = str(normalized.get("followup_kind") or "").strip().lower()
    codex_status_text = str(codex_status or "").strip().lower()
    agent_cli_marker = _looks_like_agent_cli_fault_text(reason, next_codex_prompt, completion_summary)
    service_fault_signal = bool(
        issue_kind == "service_fault"
        or codex_status_text != "completed"
        or _looks_like_service_fault_text(reason, next_codex_prompt, completion_summary)
    )

    if decision_name in {"COMPLETE", "ABORT"}:
        normalized["issue_kind"] = "none"
        normalized["followup_kind"] = "none"
        return normalized

    if agent_cli_marker and allow_fix_turns:
        normalized["issue_kind"] = "agent_cli_fault"
        normalized["followup_kind"] = "fix"
        return normalized

    if service_fault_signal:
        normalized["issue_kind"] = "service_fault"
        normalized["followup_kind"] = "retry"
        return normalized

    if issue_kind == "agent_cli_fault" and allow_fix_turns:
        normalized["issue_kind"] = "agent_cli_fault"
        normalized["followup_kind"] = "fix"
        return normalized
    if issue_kind == "agent_cli_fault" and not allow_fix_turns:
        normalized["issue_kind"] = "service_fault"
        normalized["followup_kind"] = "retry"
        return normalized

    if issue_kind not in {"agent_cli_fault", "bug", "service_fault", "plan_gap", "none"}:
        issue_kind = ""
    if followup_kind not in {"fix", "retry", "replan", "none"}:
        followup_kind = ""

    if not issue_kind:
        if decision_name == "ADVANCE":
            issue_kind = "none"
        elif next_phase == "plan":
            issue_kind = "plan_gap"
        else:
            issue_kind = "none"
    if not followup_kind:
        if decision_name == "ADVANCE":
            followup_kind = "none"
        elif issue_kind == "agent_cli_fault":
            followup_kind = "fix" if allow_fix_turns else "retry"
        elif issue_kind == "bug":
            followup_kind = "retry"
        elif issue_kind == "service_fault":
            followup_kind = "retry"
        elif issue_kind == "none":
            followup_kind = "retry"
        elif issue_kind == "plan_gap":
            followup_kind = "replan"
        else:
            followup_kind = "retry"

    if issue_kind == "agent_cli_fault" and allow_fix_turns:
        followup_kind = "fix"
    elif issue_kind == "agent_cli_fault":
        issue_kind = "service_fault"
        followup_kind = "retry"
    elif issue_kind == "plan_gap":
        followup_kind = "replan"
    elif issue_kind == "service_fault":
        followup_kind = "retry"
    elif issue_kind == "bug":
        followup_kind = "retry"
        if phase == "plan":
            issue_kind = "plan_gap"
            followup_kind = "replan"
    elif decision_name == "ADVANCE":
        followup_kind = "none"
    elif phase == "plan":
        issue_kind = "plan_gap"
        followup_kind = "replan"

    normalized["issue_kind"] = issue_kind
    normalized["followup_kind"] = followup_kind
    return normalized


def _recent_phase_history(flow_state: dict[str, Any], *, limit: int = 6) -> list[dict[str, Any]]:
    rows = list(flow_state.get("phase_history") or [])
    if limit > 0:
        rows = rows[-limit:]
    return [dict(row or {}) for row in rows]


def _build_phase_artifact(
    flow_state: dict[str, Any],
    *,
    phase: str,
    role_id: str,
    attempt_no: int,
    phase_attempt_no: int,
    codex_receipt,
) -> dict[str, Any]:
    return {
        "workflow_id": str(flow_state.get("workflow_id") or "").strip(),
        "workflow_kind": str(flow_state.get("workflow_kind") or "").strip(),
        "phase": str(phase or "").strip(),
        "role_id": str(role_id or "").strip(),
        "attempt_no": int(attempt_no),
        "phase_attempt_no": int(phase_attempt_no),
        "goal": str(flow_state.get("goal") or "").strip(),
        "guard_condition": str(flow_state.get("guard_condition") or "").strip(),
        "codex_session_id": str(flow_state.get("codex_session_id") or _receipt_thread_id(codex_receipt)).strip(),
        "codex_status": str(getattr(codex_receipt, "status", "") or "").strip(),
        "codex_output": _receipt_text(codex_receipt),
        "codex_metadata": dict(getattr(codex_receipt, "metadata", {}) or {}),
        "pending_codex_prompt": _compose_next_instruction(flow_state),
        "last_cursor_decision": dict(flow_state.get("last_cursor_decision") or {}),
    }


def _normalize_project_loop_decision(decision: dict[str, Any], *, phase: str, flow_state: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(decision or {})
    decision_name = str(normalized.get("decision") or "").strip().upper()
    next_phase = str(normalized.get("next_phase") or "").strip().lower()
    phase_plan = resolve_phase_plan(flow_state)
    phase_ctx = phase_prompt_context(phase_plan, phase)
    default_next_phase = next_phase_id(phase_plan, phase)
    if next_phase == "complete":
        next_phase = DONE_PHASE
    if decision_name == "COMPLETE":
        if not default_next_phase:
            normalized["next_phase"] = DONE_PHASE
            normalized["decision"] = "COMPLETE"
            return normalized
        normalized["decision"] = "ADVANCE"
        if not next_phase or next_phase == DONE_PHASE:
            next_phase = default_next_phase
    elif next_phase == DONE_PHASE:
        next_phase = default_next_phase
    elif decision_name == "RETRY" and not next_phase:
        next_phase = str(phase_ctx.get("retry_phase_id") or phase).strip()
    normalized["next_phase"] = next_phase
    return normalized


class FlowRuntime:
    def __init__(
        self,
        *,
        run_prompt_receipt_fn: Callable[..., Any] = run_prompt_receipt,
        display: FlowDisplay,
        event_callback: FlowUiEventCallback | None = None,
        hook_callback: FlowLifecycleHook | None = None,
    ) -> None:
        self._run_prompt_receipt_fn = run_prompt_receipt_fn
        self._display = display
        self._event_callback = event_callback
        self._hook_callback = hook_callback

    @staticmethod
    def _resolve_bundle_ref(base_dir: Path, ref: Any) -> Path | None:
        token = str(ref or "").strip()
        if not token:
            return None
        path = Path(token)
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        return path

    @staticmethod
    def _read_text_if_exists(path: Path | None) -> str:
        if path is None or not path.exists() or not path.is_file():
            return ""
        try:
            return str(path.read_text(encoding="utf-8")).strip()
        except Exception:
            return ""

    @staticmethod
    def _strip_named_section(text: str, section_name: str) -> str:
        body = str(text or "").strip()
        token = f"[{str(section_name or '').strip().lower()}]"
        if not body or not token.strip("[]"):
            return body
        rows: list[str] = []
        skipping = False
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                skipping = stripped.lower() == token
                if skipping:
                    continue
            if not skipping:
                rows.append(line)
        return "\n".join(rows).strip()

    def _current_control_profile(
        self,
        flow_state: dict[str, Any],
        *,
        current: dict[str, Any] | None = None,
        raw: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return normalize_control_profile_payload(
            raw if raw is not None else flow_state.get("control_profile"),
            current=current or {},
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
            role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
            execution_mode=str(flow_state.get("execution_mode") or "").strip(),
            execution_context=str(flow_state.get("execution_context") or "").strip(),
        )

    def _apply_supervisor_control_profile(
        self,
        flow_state: dict[str, Any],
        decision: dict[str, Any],
        *,
        clear_transient_flags: bool = False,
    ) -> dict[str, Any]:
        current = self._current_control_profile(flow_state)
        updated = dict(current)
        for key in ("packet_size", "evidence_level", "gate_cadence", "repo_binding_policy"):
            value = str(decision.get(key) or "").strip()
            if value:
                updated[key] = value
        if clear_transient_flags:
            updated["force_gate_next_turn"] = False
            updated["force_doctor_next_turn"] = False
        normalized = self._current_control_profile(flow_state, current=current, raw=updated)
        flow_state["control_profile"] = normalized
        return normalized

    def _asset_runtime_context(self, flow_dir_path: Path, flow_state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        definition = read_json(flow_definition_path(flow_dir_path))
        bundle_manifest = dict(definition.get("bundle_manifest") or flow_state.get("bundle_manifest") or {})
        base_control_profile = normalize_control_profile_payload(
            definition.get("control_profile"),
            current={},
            workflow_kind=str(definition.get("workflow_kind") or flow_state.get("workflow_kind") or "").strip(),
            role_pack_id=str(definition.get("role_pack_id") or flow_state.get("role_pack_id") or "").strip(),
            execution_mode=str(definition.get("execution_mode") or flow_state.get("execution_mode") or "").strip(),
            execution_context=str(definition.get("execution_context") or flow_state.get("execution_context") or "").strip(),
        )
        control_profile = self._current_control_profile(
            flow_state,
            current=base_control_profile,
            raw=flow_state.get("control_profile") or definition.get("control_profile"),
        )
        asset_context = {
            "source_asset_key": str(definition.get("source_asset_key") or flow_state.get("source_asset_key") or "").strip(),
            "source_asset_kind": str(definition.get("source_asset_kind") or flow_state.get("source_asset_kind") or "").strip(),
            "source_asset_version": str(definition.get("source_asset_version") or flow_state.get("source_asset_version") or "").strip(),
            "review_checklist": [
                str(item or "").strip()
                for item in list(definition.get("review_checklist") or flow_state.get("review_checklist") or [])
                if str(item or "").strip()
            ],
            "role_guidance": dict(definition.get("role_guidance") or flow_state.get("role_guidance") or {}),
            "doctor_policy": normalize_doctor_policy_payload(
                definition.get("doctor_policy"),
                current=dict(flow_state.get("doctor_policy") or {}),
            ),
            "control_profile": control_profile,
            "supervisor_profile": dict(definition.get("supervisor_profile") or flow_state.get("supervisor_profile") or {}),
            "run_brief": str(definition.get("run_brief") or flow_state.get("run_brief") or "").strip(),
            "bundle_manifest": bundle_manifest,
        }
        base_dir = flow_dir_path
        bundle_root = self._resolve_bundle_ref(base_dir, bundle_manifest.get("bundle_root")) or base_dir
        sources_ref = (
            self._resolve_bundle_ref(base_dir, bundle_manifest.get("sources_ref"))
            or self._resolve_bundle_ref(bundle_root, bundle_manifest.get("sources_path"))
            or self._resolve_bundle_ref(bundle_root, "sources.json")
        )
        sources_payload = read_json(sources_ref) if sources_ref is not None and sources_ref.exists() else {}
        asset_context["source_bindings"] = list(
            definition.get("source_bindings")
            or flow_state.get("source_bindings")
            or sources_payload.get("items")
            or []
        )
        supervisor_ref = (
            self._resolve_bundle_ref(base_dir, bundle_manifest.get("supervisor_ref"))
            or self._resolve_bundle_ref(bundle_root, bundle_manifest.get("supervisor"))
        )
        derived = dict(bundle_manifest.get("derived") or {})
        compiled_ref = (
            self._resolve_bundle_ref(base_dir, derived.get("supervisor_compiled"))
            or self._resolve_bundle_ref(base_dir, bundle_manifest.get("supervisor_compiled_ref"))
            or self._resolve_bundle_ref(bundle_root, "derived/supervisor_knowledge.json")
        )
        handwritten_text = self._read_text_if_exists(supervisor_ref)
        compiled_payload = read_json(compiled_ref) if compiled_ref is not None and compiled_ref.exists() else {}
        compiled_text = str(
            compiled_payload.get("knowledge_text")
            or compiled_payload.get("body")
            or definition.get("compiled_supervisor_knowledge_text")
            or flow_state.get("compiled_supervisor_knowledge_text")
            or ""
        ).strip()
        compiled_text = self._strip_named_section(compiled_text, "control profile")
        control_summary = ""
        if control_profile:
            control_summary = compact_json(
                {
                    "task_archetype": str(control_profile.get("task_archetype") or "").strip(),
                    "packet_size": str(control_profile.get("packet_size") or "").strip(),
                    "evidence_level": str(control_profile.get("evidence_level") or "").strip(),
                    "gate_cadence": str(control_profile.get("gate_cadence") or "").strip(),
                    "repo_binding_policy": str(control_profile.get("repo_binding_policy") or "").strip(),
                    "repo_contract_paths": list(control_profile.get("repo_contract_paths") or []),
                }
            )
        sections = [
            f"[handwritten supervisor]\n{handwritten_text}" if handwritten_text else "",
            f"[compiled supervisor knowledge]\n{compiled_text}" if compiled_text else "",
            f"[control profile]\n{control_summary}" if control_summary else "",
        ]
        knowledge_text = "\n\n".join(section for section in sections if section).strip()
        supervisor_knowledge = {
            "knowledge_text": knowledge_text,
            "composition_mode": str(
                compiled_payload.get("composition_mode")
                or definition.get("supervisor_knowledge_mode")
                or ("handwritten+compiled" if handwritten_text and compiled_text else ("compiled" if compiled_text else ("handwritten" if handwritten_text else "")))
            ).strip(),
            "refs": [
                str(path)
                for path in [supervisor_ref, compiled_ref, sources_ref]
                if path is not None and str(path).strip()
            ],
            "updated_at": str(compiled_payload.get("updated_at") or definition.get("updated_at") or "").strip(),
        }
        return asset_context, supervisor_knowledge

    def _repo_contract_appendix(self, flow_state: dict[str, Any]) -> str:
        control_profile = normalize_control_profile_payload(
            flow_state.get("control_profile"),
            current=default_control_profile(
                workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
                role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
                execution_mode=str(flow_state.get("execution_mode") or "").strip(),
                execution_context=str(flow_state.get("execution_context") or "").strip(),
            ),
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
            role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
            execution_mode=str(flow_state.get("execution_mode") or "").strip(),
            execution_context=str(flow_state.get("execution_context") or "").strip(),
        )
        if str(control_profile.get("repo_binding_policy") or REPO_BINDING_DISABLED).strip().lower() != REPO_BINDING_EXPLICIT:
            return ""
        workspace_root = Path(str(flow_state.get("workspace_root") or ".")).resolve()
        sections: list[str] = []
        for raw_path in list(control_profile.get("repo_contract_paths") or [])[:3]:
            ref = str(raw_path or "").strip()
            if not ref:
                continue
            candidate = Path(ref)
            if not candidate.is_absolute():
                candidate = (workspace_root / candidate).resolve()
            text = self._read_text_if_exists(candidate)
            if not text:
                continue
            if len(text) > 3200:
                text = f"{text[:3197]}..."
            sections.append(f"[repo contract: {ref}]\n{text}")
        if not sections:
            return ""
        return "Explicit repo contracts:\n" + "\n\n".join(sections)

    def _doctor_runtime_appendix(self, flow_dir_path: Path, flow_state: dict[str, Any]) -> str:
        definition = read_json(flow_definition_path(Path(flow_dir_path)))
        bundle_manifest = dict(definition.get("bundle_manifest") or flow_state.get("bundle_manifest") or {})
        base_dir = Path(flow_dir_path)
        bundle_root = self._resolve_bundle_ref(base_dir, bundle_manifest.get("bundle_root")) or base_dir
        doctor_ref = (
            self._resolve_bundle_ref(base_dir, bundle_manifest.get("doctor_ref"))
            or self._resolve_bundle_ref(bundle_root, bundle_manifest.get("doctor_prompt"))
            or self._resolve_bundle_ref(bundle_root, "doctor.md")
        )
        doctor_skill_ref = (
            self._resolve_bundle_ref(base_dir, bundle_manifest.get("doctor_skill_ref"))
            or self._resolve_bundle_ref(bundle_root, Path("skills") / DOCTOR_ROLE_ID / "SKILL.md")
        )
        sections = []
        doctor_text = self._read_text_if_exists(doctor_ref)
        if doctor_text:
            sections.append(f"[doctor bundle]\n{doctor_text}")
        doctor_skill_text = self._read_text_if_exists(doctor_skill_ref)
        if doctor_skill_text:
            sections.append(f"[doctor skill]\n{doctor_skill_text}")
        return "\n\n".join(section for section in sections if section).strip()

    def _doctor_policy(self, flow_state: dict[str, Any]) -> dict[str, Any]:
        return normalize_doctor_policy_payload(flow_state.get("doctor_policy"), current={})

    def _last_codex_failure_blob(self, flow_state: dict[str, Any]) -> str:
        receipt = dict(flow_state.get("last_codex_receipt") or {})
        metadata = dict(receipt.get("metadata") or {})
        external_session = dict(metadata.get("external_session") or {})
        parts = [
            str(receipt.get("summary") or "").strip(),
            str(receipt.get("output_text") or "").strip(),
            str(metadata.get("stderr") or "").strip(),
            str(external_session.get("requested_session_id") or "").strip(),
            str(dict(metadata.get("runtime_request") or {}).get("codex_mode") or "").strip(),
        ]
        return "\n".join(part for part in parts if part).strip()

    def _session_binding_invalid(self, flow_state: dict[str, Any]) -> bool:
        receipt = dict(flow_state.get("last_codex_receipt") or {})
        metadata = dict(receipt.get("metadata") or {})
        runtime_request = dict(metadata.get("runtime_request") or {})
        external_session = dict(metadata.get("external_session") or {})
        expected_session_mode = str(dict(flow_state.get("latest_supervisor_decision") or {}).get("session_mode") or "").strip().lower()
        requested_mode = str(runtime_request.get("codex_mode") or "").strip().lower()
        if expected_session_mode == "cold" and requested_mode == "resume":
            return True
        requested_session_id = str(external_session.get("requested_session_id") or "").strip()
        thread_id = str(external_session.get("thread_id") or "").strip()
        if requested_mode == "resume" and requested_session_id and not thread_id and not bool(external_session.get("resume_durable")):
            return True
        if _looks_like_resume_no_rollout_failure(self._last_codex_failure_blob(flow_state)):
            return True
        return False

    def _doctor_trigger_reason(self, flow_state: dict[str, Any], *, phase: str) -> str:
        if str(phase or "").strip() == DONE_PHASE:
            return ""
        if str(flow_state.get("active_role_id") or "").strip() == DOCTOR_ROLE_ID:
            return ""
        control_profile = dict(flow_state.get("control_profile") or {})
        if bool(control_profile.get("force_doctor_next_turn")):
            return "run doctor on the next bounded turn via explicit operator request"
        policy = self._doctor_policy(flow_state)
        if not bool(policy.get("enabled")):
            return ""
        max_rounds = max(1, safe_int(policy.get("max_rounds_per_episode"), 1))
        if safe_int(dict(flow_state.get("role_turn_counts") or {}).get(DOCTOR_ROLE_ID), 0) >= max_rounds:
            return ""
        activation_rules = {str(item or "").strip() for item in list(policy.get("activation_rules") or []) if str(item or "").strip()}
        if "same_resume_failure" in activation_rules and _looks_like_resume_no_rollout_failure(self._last_codex_failure_blob(flow_state)):
            return "repair repeated resume/no-rollout failure via doctor"
        if "session_binding_invalid" in activation_rules and self._session_binding_invalid(flow_state):
            return "repair invalid session binding via doctor"
        if "repeated_service_fault" in activation_rules and safe_int(flow_state.get("service_fault_streak"), 0) >= 2:
            return "repair repeated service fault via doctor"
        return ""

    def _doctor_instruction(self, flow_state: dict[str, Any]) -> str:
        pending = _compose_next_instruction(flow_state)
        current_phase = str(flow_state.get("current_phase") or "").strip()
        instruction = (
            "Diagnose and repair the current flow before any more business execution. "
            "Priority order: (1) runtime/session bindings, (2) instance-local assets such as flow_definition.json or bundle sidecars, "
            "(3) safe flow-local mode/session corrections. Keep scope inside this flow instance.\n\n"
            "If you conclude the blocker is a butler-flow framework/code bug, do not patch global code from inside the flow. "
            "Instead begin the final reply with `DOCTOR_FRAMEWORK_BUG:` and include `Problem:`, `Evidence:`, and `Fix plan:`."
        )
        if pending:
            instruction = f"{instruction}\n\nCurrent blocked task to resume after repair:\n{pending}"
        if current_phase:
            instruction = f"{instruction}\n\nReturn control so phase `{current_phase}` can continue safely."
        return instruction.strip()

    def _doctor_framework_bug_report(self, codex_receipt) -> str:
        text = _receipt_text(codex_receipt)
        marker = "DOCTOR_FRAMEWORK_BUG:"
        if marker not in text:
            return ""
        _, _, suffix = text.partition(marker)
        report = suffix.strip() or text.strip()
        return report

    def _pause_for_doctor_framework_bug(
        self,
        *,
        flow_dir_path,
        trace_store: FileTraceStore,
        flow_state: dict[str, Any],
        flow_id: str,
        phase: str,
        attempt_no: int,
        report: str,
    ) -> int:
        summary = "doctor detected a butler-flow framework bug; flow paused for operator follow-up"
        flow_state["status"] = "paused"
        flow_state["pending_codex_prompt"] = str(report or "").strip()
        flow_state["last_completion_summary"] = summary
        supervisor_decision = {
            "decision": "ask_operator",
            "turn_kind": "operator_wait",
            "reason": summary,
            "confidence": 0.96,
            "next_action": "ask_operator",
            "attempt_no": int(attempt_no),
            "phase": str(phase or "").strip(),
            "instruction": str(report or "").strip(),
            "issue_kind": "bug",
            "followup_kind": "none",
            "active_role_id": DOCTOR_ROLE_ID,
        }
        flow_state["latest_supervisor_decision"] = dict(supervisor_decision)
        self._set_approval_state(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            flow_id=flow_id,
            phase=phase,
            attempt_no=attempt_no,
            approval_state="operator_required",
            reason=summary,
            source="doctor",
        )
        self._emit_ui_event(
            kind="warning",
            lane="supervisor",
            family="risk",
            flow_dir_path=flow_dir_path,
            flow_id=flow_id,
            phase=phase,
            attempt_no=attempt_no,
            message=summary,
            payload={"reason": summary, "doctor_report": str(report or "").strip(), "role_id": DOCTOR_ROLE_ID},
            raw_text=str(report or "").strip(),
        )
        self._append_strategy_trace(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            kind="doctor_framework_bug",
            title="doctor escalated framework bug",
            summary=summary,
            family="approval",
            payload={"report": str(report or "").strip(), **dict(supervisor_decision)},
            attempt_no=attempt_no,
            phase=phase,
        )
        trace_store.append_event(
            flow_id,
            phase=phase,
            event_type="doctor.framework_bug",
            payload={"attempt_no": attempt_no, "report": str(report or "").strip()},
        )
        self._write_flow_state(flow_dir_path, flow_state)
        return 0

    def _runtime_plan_payload(
        self,
        *,
        flow_state: dict[str, Any],
        plan_stage: str,
        attempt_no: int,
        phase_attempt_no: int,
        summary: str = "",
        flow_board: FlowBoardV1 | None = None,
        active_turn_task: TurnTaskPacketV1 | None = None,
    ) -> FlowRuntimePlanV1:
        return {
            "plan_id": f"runtime_plan_{uuid4().hex[:10]}",
            "flow_id": str(flow_state.get("workflow_id") or "").strip(),
            "workflow_kind": str(flow_state.get("workflow_kind") or "").strip(),
            "phase": str(flow_state.get("current_phase") or "").strip(),
            "attempt_no": int(attempt_no or 0),
            "phase_attempt_no": int(phase_attempt_no or 0),
            "plan_stage": str(plan_stage or "").strip(),
            "active_role_id": str(flow_state.get("active_role_id") or "").strip(),
            "execution_mode": str(flow_state.get("execution_mode") or "").strip(),
            "session_strategy": str(flow_state.get("session_strategy") or "").strip(),
            "goal": str(flow_state.get("goal") or "").strip(),
            "guard_condition": str(flow_state.get("guard_condition") or "").strip(),
            "risk_level": str(flow_state.get("risk_level") or "").strip(),
            "autonomy_profile": str(flow_state.get("autonomy_profile") or "").strip(),
            "summary": str(summary or "").strip(),
            "flow_board": dict(flow_board or {}),
            "active_turn_task": dict(active_turn_task or {}),
            "latest_mutation": dict(flow_state.get("latest_mutation") or {}),
            "context_governor": dict(flow_state.get("context_governor") or {}),
            "updated_at": now_text(),
        }

    def _write_runtime_plan(
        self,
        *,
        flow_dir_path,
        flow_state: dict[str, Any],
        plan_stage: str,
        attempt_no: int,
        phase_attempt_no: int,
        summary: str = "",
        flow_board: FlowBoardV1 | None = None,
        active_turn_task: TurnTaskPacketV1 | None = None,
    ) -> None:
        payload = self._runtime_plan_payload(
            flow_state=flow_state,
            plan_stage=plan_stage,
            attempt_no=attempt_no,
            phase_attempt_no=phase_attempt_no,
            summary=summary,
            flow_board=flow_board,
            active_turn_task=active_turn_task,
        )
        write_json_atomic(runtime_plan_path(flow_dir_path), dict(payload))

    def _append_mutation(
        self,
        *,
        flow_dir_path,
        flow_state: dict[str, Any],
        mutation_kind: str,
        summary: str,
        payload: dict[str, Any] | None = None,
        role_id: str = "",
    ) -> FlowMutationV1:
        mutation: FlowMutationV1 = {
            "mutation_id": f"mutation_{uuid4().hex[:12]}",
            "flow_id": str(flow_state.get("workflow_id") or "").strip(),
            "phase": str(flow_state.get("current_phase") or "").strip(),
            "role_id": str(role_id or flow_state.get("active_role_id") or "").strip(),
            "created_at": now_text(),
            "mutation_kind": str(mutation_kind or "").strip(),
            "summary": str(summary or "").strip(),
            "payload": dict(payload or {}),
        }
        append_jsonl(mutations_path(flow_dir_path), dict(mutation))
        flow_state["latest_mutation"] = dict(mutation)
        return mutation

    def _append_strategy_trace(
        self,
        *,
        flow_dir_path,
        flow_state: dict[str, Any],
        kind: str,
        title: str,
        summary: str,
        family: str,
        payload: dict[str, Any] | None = None,
        attempt_no: int = 0,
        phase: str = "",
    ) -> None:
        event: FlowStrategyEventV1 = {
            "event_id": f"strategy_evt_{uuid4().hex[:12]}",
            "flow_id": str(flow_state.get("workflow_id") or "").strip(),
            "phase": str(phase or flow_state.get("current_phase") or "").strip(),
            "attempt_no": int(attempt_no or 0),
            "created_at": now_text(),
            "lane": "supervisor",
            "family": str(family or "").strip() or "decision",
            "kind": str(kind or "").strip(),
            "title": str(title or "").strip(),
            "summary": str(summary or "").strip(),
            "payload": dict(payload or {}),
        }
        append_jsonl(strategy_trace_path(flow_dir_path), dict(event))

    def _append_prompt_packet(
        self,
        *,
        flow_dir_path,
        flow_state: dict[str, Any],
        prompt_kind: str,
        prompt_text: str,
        role_id: str,
        attempt_no: int,
        phase_attempt_no: int,
        session_mode: str,
        load_profile: str,
    ) -> None:
        packet: PromptPacketV1 = {
            "packet_id": f"prompt_pkt_{uuid4().hex[:10]}",
            "flow_id": str(flow_state.get("workflow_id") or "").strip(),
            "workflow_kind": str(flow_state.get("workflow_kind") or "").strip(),
            "phase": str(flow_state.get("current_phase") or "").strip(),
            "role_id": str(role_id or "").strip(),
            "target_role": str(role_id or "").strip(),
            "attempt_no": int(attempt_no or 0),
            "phase_attempt_no": int(phase_attempt_no or 0),
            "session_mode": str(session_mode or "").strip(),
            "load_profile": str(load_profile or "").strip(),
            "prompt_kind": str(prompt_kind or "").strip(),
            "packet_kind": str(prompt_kind or "").strip(),
            "packet_summary": {},
            "packet": {},
            "prompt_text": str(prompt_text or ""),
            "created_at": now_text(),
            "refs": {
                "execution_mode": str(flow_state.get("execution_mode") or "").strip(),
                "session_strategy": str(flow_state.get("session_strategy") or "").strip(),
            },
        }
        append_jsonl(prompt_packets_path(flow_dir_path), dict(packet))

    def _append_compiled_packet(
        self,
        *,
        flow_dir_path,
        flow_state: dict[str, Any],
        compiled: CompiledPromptPacketV1,
        role_id: str,
        attempt_no: int,
        phase_attempt_no: int,
        prompt_kind: str,
    ) -> None:
        packet: PromptPacketV1 = {
            "packet_id": f"prompt_pkt_{uuid4().hex[:10]}",
            "flow_id": str(flow_state.get("workflow_id") or "").strip(),
            "workflow_kind": str(flow_state.get("workflow_kind") or "").strip(),
            "phase": str(flow_state.get("current_phase") or "").strip(),
            "role_id": str(role_id or "").strip(),
            "target_role": str(compiled.get("target_role") or role_id or "").strip(),
            "attempt_no": int(attempt_no or 0),
            "phase_attempt_no": int(phase_attempt_no or 0),
            "session_mode": str(compiled.get("session_mode") or "").strip(),
            "load_profile": str(compiled.get("load_profile") or "").strip(),
            "prompt_kind": str(prompt_kind or "").strip(),
            "packet_kind": str(compiled.get("packet_kind") or prompt_kind or "").strip(),
            "packet_summary": {
                "flow_id": str(dict(compiled.get("flow_board") or {}).get("flow_id") or "").strip(),
                "current_phase": str(dict(compiled.get("flow_board") or {}).get("current_phase") or "").strip(),
                "active_role_id": str(dict(compiled.get("flow_board") or {}).get("active_role_id") or "").strip(),
                "role_id": str(dict(compiled.get("role_board") or {}).get("role_id") or "").strip(),
                "role_kind": str(dict(compiled.get("role_board") or {}).get("role_kind") or "").strip(),
                "turn_kind": str(dict(compiled.get("turn_task_packet") or {}).get("turn_kind") or "").strip(),
            },
            "packet": dict(compiled),
            "prompt_text": str(compiled.get("rendered_prompt") or ""),
            "created_at": now_text(),
            "refs": {
                "execution_mode": str(flow_state.get("execution_mode") or "").strip(),
                "session_strategy": str(flow_state.get("session_strategy") or "").strip(),
            },
        }
        append_jsonl(prompt_packets_path(flow_dir_path), packet)

    def _emit_ui_event(
        self,
        *,
        kind: str,
        lane: str = "",
        family: str = "",
        title: str = "",
        flow_dir_path=None,
        flow_id: str = "",
        phase: str = "",
        attempt_no: int = 0,
        message: str = "",
        payload: dict[str, Any] | None = None,
        refs: dict[str, Any] | None = None,
        raw_text: str = "",
        display_priority: int = 0,
        hook_name: str = "",
    ) -> None:
        callback = self._event_callback
        payload_dict = dict(payload or {})
        refs_dict = dict(refs or {})
        kind_text = str(kind or "").strip()
        resolved_lane = str(lane or "").strip() or _infer_ui_event_lane(kind_text, payload_dict)
        resolved_family = str(family or "").strip() or _infer_ui_event_family(kind_text, payload_dict)
        resolved_title = str(title or "").strip() or str(message or kind_text).strip()
        resolved_raw_text = str(raw_text or "")
        if not resolved_raw_text and kind_text == "codex_segment":
            resolved_raw_text = str(payload_dict.get("segment") or message or "")
        if not resolved_raw_text and kind_text == "codex_runtime_event":
            resolved_raw_text = str(payload_dict.get("text") or message or "")
        event = build_flow_ui_event(
            kind=kind_text,
            lane=resolved_lane,
            family=resolved_family,
            title=resolved_title,
            flow_id=flow_id,
            phase=phase,
            attempt_no=attempt_no,
            message=message,
            payload=payload_dict,
            refs=refs_dict,
            raw_text=resolved_raw_text,
            display_priority=display_priority,
        )
        if flow_dir_path is not None:
            append_jsonl(flow_events_path(flow_dir_path), event.to_dict())
        if callable(callback):
            callback(event)
        if hook_name:
            invoke_flow_hook(self._hook_callback, hook_name, event)

    def _append_turn_record(self, flow_dir_path, payload: FlowTurnRecordV1) -> None:
        append_jsonl(flow_turns_path(flow_dir_path), dict(payload or {}))

    def _append_action_record(self, flow_dir_path, payload: FlowActionReceiptV1) -> None:
        append_jsonl(flow_actions_path(flow_dir_path), dict(payload or {}))

    def _set_approval_state(
        self,
        *,
        flow_dir_path,
        flow_state: dict[str, Any],
        flow_id: str,
        phase: str,
        attempt_no: int,
        approval_state: str,
        reason: str = "",
        source: str = "",
    ) -> None:
        previous_state = str(flow_state.get("approval_state") or "").strip()
        next_state = str(approval_state or "").strip()
        if not next_state:
            return
        flow_state["approval_state"] = next_state
        if previous_state == next_state:
            return
        payload = {
            "previous_state": previous_state,
            "approval_state": next_state,
            "source": str(source or "").strip(),
        }
        if reason:
            payload["reason"] = str(reason or "").strip()
        self._emit_ui_event(
            kind="approval_state_changed",
            lane="supervisor",
            family="approval",
            flow_dir_path=flow_dir_path,
            flow_id=flow_id,
            phase=phase,
            attempt_no=attempt_no,
            message=f"{previous_state or '-'} -> {next_state}",
            payload=payload,
            hook_name="on_approval_state_changed",
        )

    def _register_artifact(self, flow_dir_path, artifact: dict[str, Any]) -> None:
        artifacts_path = flow_artifacts_path(flow_dir_path)
        payload = read_json(artifacts_path)
        items = list(payload.get("items") or [])
        items.append(dict(artifact or {}))
        write_json_atomic(
            artifacts_path,
            {
                "flow_id": str(payload.get("flow_id") or artifact.get("workflow_id") or "").strip(),
                "items": items,
                "updated_at": now_text(),
            },
        )

    def _role_runtime_active(self, flow_state: dict[str, Any]) -> bool:
        execution_mode = normalize_execution_mode(flow_state.get("execution_mode"))
        return execution_mode != EXECUTION_MODE_SIMPLE

    def _sync_role_runtime_sidecars(self, flow_dir_path, flow_state: dict[str, Any]) -> None:
        save_role_sessions(
            flow_dir_path,
            str(flow_state.get("workflow_id") or "").strip(),
            dict(flow_state.get("role_sessions") or {}),
        )

    def _latest_inbound_handoff(self, flow_dir_path, flow_state: dict[str, Any], *, role_id: str) -> dict[str, Any]:
        latest_handoffs = dict(flow_state.get("latest_role_handoffs") or {})
        handoff_id = str(latest_handoffs.get(str(role_id or "").strip()) or "").strip()
        if handoff_id:
            handoffs = load_handoffs(flow_dir_path)
            payload = dict(handoffs.get(handoff_id) or {})
            if payload:
                return payload
        return latest_handoff_for_role(flow_dir_path, role_id)

    def _latest_handoff_summary(self, flow_dir_path, flow_state: dict[str, Any]) -> dict[str, Any]:
        handoffs = list(load_handoffs(flow_dir_path).values())
        pending = [row for row in handoffs if str(row.get("status") or "").strip() == "pending"]
        if pending:
            pending.sort(key=lambda item: str(item.get("created_at") or ""))
            row = dict(pending[-1])
        elif handoffs:
            handoffs.sort(key=lambda item: str(item.get("created_at") or ""))
            row = dict(handoffs[-1])
        else:
            return {}
        return {
            "handoff_id": str(row.get("handoff_id") or "").strip(),
            "from_role_id": str(row.get("from_role_id") or row.get("source_role_id") or "").strip(),
            "to_role_id": str(row.get("to_role_id") or row.get("target_role_id") or "").strip(),
            "status": str(row.get("status") or "").strip(),
            "summary": str(row.get("summary") or "").strip(),
        }

    def _compile_packet(
        self,
        *,
        flow_dir_path,
        flow_state: dict[str, Any],
        target_role: str,
        role_id: str,
        role_turn_no: int,
        attempt_no: int,
        phase_attempt_no: int,
        session_mode: str,
        load_profile: str,
        task_brief: str = "",
        turn_kind: str = "",
        next_instruction: str = "",
    ) -> CompiledPromptPacketV1:
        inbound_handoff = self._latest_inbound_handoff(flow_dir_path, flow_state, role_id=role_id)
        if target_role == "judge":
            inbound_handoff = dict(dict(flow_state.get("_judge_runtime_context") or {}).get("inbound_handoff") or inbound_handoff)
        role_sessions = dict(flow_state.get("role_sessions") or {})
        role_payload = dict(role_sessions.get(str(role_id or "").strip()) or {})
        asset_context, supervisor_knowledge = self._asset_runtime_context(Path(flow_dir_path), flow_state)
        flow_state["_asset_runtime_context"] = dict(asset_context)
        role_kind = "ephemeral" if is_ephemeral_role(flow_state, role_id=role_id) else "stable"
        role_charter = current_role_prompt(
            role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
            role_id=role_id,
            flow_state=flow_state,
        )
        if str(role_id or "").strip() == DOCTOR_ROLE_ID:
            doctor_appendix = self._doctor_runtime_appendix(flow_dir_path, flow_state)
            if doctor_appendix:
                role_charter = f"{role_charter}\n\n{doctor_appendix}".strip()
        flow_board = build_flow_board(
            flow_state,
            latest_handoff_summary=self._latest_handoff_summary(flow_dir_path, flow_state),
        )
        role_board = build_role_board(
            flow_state=flow_state,
            role_id=role_id,
            role_kind=role_kind,
            base_role_id=str(role_payload.get("base_role_id") or "").strip(),
            role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
            role_turn_no=role_turn_no,
            role_session_id=role_session_id_for_turn(flow_state, role_id=role_id),
            role_charter=role_charter,
            role_charter_addendum=str(role_payload.get("role_charter_addendum") or "").strip(),
            latest_inbound_handoff=inbound_handoff,
            visible_artifacts=visible_artifacts(flow_dir_path, role_id=role_id, limit=3),
            session_binding=role_payload,
        )
        if target_role == "judge":
            judge_context = dict(flow_state.get("_judge_runtime_context") or {})
            role_board["latest_executor_context"] = {
                "codex_status": str(judge_context.get("codex_status") or "").strip(),
                "codex_session_id": str(judge_context.get("codex_session_id") or "").strip(),
                "codex_output": str(judge_context.get("codex_output") or "").strip(),
                "codex_metadata": dict(judge_context.get("codex_metadata") or {}),
                "phase_artifact": dict(judge_context.get("phase_artifact") or {}),
            }
            flow_board["recent_phase_history"] = list(judge_context.get("phase_history") or flow_board.get("recent_phase_history") or [])
        turn_task = build_turn_task_packet(
            role_id=target_role,
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
            phase=str(flow_state.get("current_phase") or "").strip(),
            turn_kind=turn_kind or _turn_kind_for_phase(str(flow_state.get("current_phase") or "").strip()),
            attempt_no=attempt_no,
            phase_attempt_no=phase_attempt_no,
            next_instruction=next_instruction,
            task_brief=task_brief,
            control_profile=dict(flow_state.get("control_profile") or {}),
        )
        compiled = compile_packet(
            target_role=target_role,
            session_mode=session_mode,
            load_profile=load_profile,
            flow_board=flow_board,
            role_board=role_board,
            turn_task_packet=turn_task,
            asset_context=asset_context,
            supervisor_knowledge=supervisor_knowledge if target_role == "supervisor" else {},
        )
        self._append_compiled_packet(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            compiled=compiled,
            role_id=role_id,
            attempt_no=attempt_no,
            phase_attempt_no=phase_attempt_no,
            prompt_kind=str(compiled.get("packet_kind") or f"{target_role}_packet").strip(),
        )
        self._write_runtime_plan(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            plan_stage=f"{target_role}_compiled",
            attempt_no=attempt_no,
            phase_attempt_no=phase_attempt_no,
            summary=str(turn_task.get("task_brief") or "").strip(),
            flow_board=flow_board,
            active_turn_task=turn_task,
        )
        return compiled

    def _build_supervisor_runtime_request(
        self,
        cfg: dict[str, Any],
        *,
        flow_id: str,
        flow_state: dict[str, Any],
        flow_dir_path,
    ) -> dict[str, Any]:
        session_id = str(flow_state.get("supervisor_thread_id") or "").strip()
        request = {
            "cli": "codex",
            "_disable_runtime_fallback": True,
            "workflow_id": flow_id,
            "agent_id": "butler_flow.supervisor",
            "codex_mode": "resume" if session_id else "exec",
            "codex_session_id": session_id,
            "codex_home": str(prepare_flow_codex_home(flow_dir_path)),
            "execution_context": "isolated",
            "execution_workspace_root": str(Path(flow_dir_path) / "supervisor_runtime"),
        }
        overrides = flow_codex_config_overrides(cfg)
        if overrides:
            request["config_overrides"] = overrides
        return request

    def _normalize_supervisor_decision(
        self,
        payload: dict[str, Any],
        *,
        flow_state: dict[str, Any],
        phase: str,
        attempt_no: int,
        fallback_reason: str = "",
    ) -> SupervisorDecisionV1:
        active_role_id = str(payload.get("active_role_id") or "").strip()
        valid_roles = set(stable_role_ids(str(flow_state.get("role_pack_id") or "").strip()))
        ephemeral_role = dict(payload.get("ephemeral_role") or {})
        governor = dict(flow_state.get("context_governor") or {})
        control_profile = self._current_control_profile(flow_state)
        if active_role_id and active_role_id not in valid_roles and not ephemeral_role:
            active_role_id = ""
        if not active_role_id:
            active_role_id = select_active_role(flow_state, phase=phase)
        decision = str(payload.get("decision") or "execute").strip().lower()
        if decision not in {"execute", "fix", "ask_operator"}:
            decision = "execute"
        next_action = str(payload.get("next_action") or "").strip().lower()
        if next_action not in {"run_executor", "ask_operator"}:
            next_action = "ask_operator" if decision == "ask_operator" else "run_executor"
        turn_kind = str(payload.get("turn_kind") or "").strip().lower()
        if turn_kind not in {"execute", "fix", "review", "recover", "operator_wait"}:
            turn_kind = "operator_wait" if decision == "ask_operator" else _turn_kind_for_phase(phase)
        session_mode = str(payload.get("session_mode") or "").strip().lower()
        if session_mode not in {"warm", "cold"}:
            session_mode = session_mode_for_role(
                role_kind="ephemeral" if active_role_id not in valid_roles else "stable",
                has_session=bool(role_session_id_for_turn(flow_state, role_id=active_role_id)),
            )
        if str(governor.get("mode") or "").strip() == "reset":
            session_mode = "cold"
        load_profile = str(payload.get("load_profile") or "").strip().lower()
        if load_profile not in {"delta", "compact", "full"}:
            load_profile = default_load_profile(
                session_mode=session_mode,
                role_id=active_role_id,
                force_compact=bool(str(flow_state.get("latest_mutation", {}).get("mutation_id") or "").strip()),
            )
        governor_mode = str(governor.get("mode") or "").strip()
        if governor_mode == "compact" and load_profile == "delta":
            load_profile = "compact"
        elif governor_mode == "reset":
            load_profile = "compact"
        packet_size = _packet_size_for_mode(
            str(payload.get("packet_size") or control_profile.get("packet_size") or ""),
            mode=governor_mode,
        )
        evidence_level = _evidence_level_for_mode(
            str(payload.get("evidence_level") or control_profile.get("evidence_level") or ""),
            mode=governor_mode,
        )
        gate_cadence = str(payload.get("gate_cadence") or control_profile.get("gate_cadence") or GATE_CADENCE_PHASE).strip().lower()
        if gate_cadence not in {GATE_CADENCE_PHASE, GATE_CADENCE_RISK_BASED, GATE_CADENCE_STRICT}:
            gate_cadence = GATE_CADENCE_PHASE
        gate_required = bool(payload.get("gate_required"))
        if not gate_required:
            gate_required = bool(control_profile.get("force_gate_next_turn"))
        control_mode = str(payload.get("control_mode") or "").strip().lower()
        if control_mode not in {"progress", "stabilize", "recover"}:
            control_mode = "recover" if governor_mode == "reset" else ("stabilize" if gate_required or governor_mode == "compact" else "progress")
        repo_binding_policy = str(
            payload.get("repo_binding_policy") or control_profile.get("repo_binding_policy") or REPO_BINDING_DISABLED
        ).strip().lower()
        if repo_binding_policy not in {REPO_BINDING_DISABLED, REPO_BINDING_EXPLICIT}:
            repo_binding_policy = REPO_BINDING_DISABLED
        normalized: SupervisorDecisionV1 = {
            "decision": decision,
            "turn_kind": turn_kind,
            "reason": str(payload.get("reason") or fallback_reason or f"continue flow via role={active_role_id}").strip(),
            "confidence": float(payload.get("confidence") or 0.72),
            "next_action": next_action,
            "attempt_no": int(attempt_no),
            "phase": str(phase or "").strip(),
            "instruction": str(payload.get("instruction") or _compose_next_instruction(flow_state)).strip(),
            "issue_kind": str(payload.get("issue_kind") or "none").strip().lower() or "none",
            "followup_kind": str(payload.get("followup_kind") or "none").strip().lower() or "none",
            "fix_round_no": int(safe_int(flow_state.get("auto_fix_round_count"), 0)),
            "active_role_id": active_role_id,
            "control_mode": control_mode,
            "packet_size": packet_size,
            "evidence_level": evidence_level,
            "gate_cadence": gate_cadence,
            "gate_required": gate_required,
            "repo_binding_policy": repo_binding_policy,
            "execution_mode": normalize_execution_mode(flow_state.get("execution_mode")),
            "session_strategy": normalize_session_strategy(
                flow_state.get("session_strategy"),
                execution_mode=str(flow_state.get("execution_mode") or "").strip(),
            ),
            "session_mode": session_mode,
            "load_profile": load_profile,
        }
        mutation = dict(payload.get("mutation") or {})
        if str(mutation.get("kind") or "").strip():
            normalized["mutation"] = mutation
        if ephemeral_role:
            normalized["ephemeral_role"] = ephemeral_role
        return normalized

    def _apply_supervisor_mutation(
        self,
        *,
        flow_dir_path,
        flow_state: dict[str, Any],
        decision: SupervisorDecisionV1,
    ) -> None:
        mutation = dict(decision.get("mutation") or {})
        mutation_kind = str(mutation.get("kind") or "").strip()
        if not mutation_kind:
            return
        summary = str(mutation.get("summary") or decision.get("reason") or "").strip()
        if mutation_kind == "switch_role":
            target_role_id = str(mutation.get("target_role_id") or decision.get("active_role_id") or "").strip()
            if target_role_id:
                flow_state["active_role_id"] = target_role_id
        elif mutation_kind == "bounce_back_phase":
            target_phase = str(mutation.get("target_phase") or "").strip()
            if target_phase:
                flow_state["current_phase"] = target_phase
        elif mutation_kind == "insert_subphase":
            target_phase = str(mutation.get("target_phase") or "").strip()
            current_phase = str(flow_state.get("current_phase") or "").strip()
            phase_plan = list(resolve_phase_plan(flow_state))
            if target_phase and target_phase not in {str(row.get("phase_id") or "").strip() for row in phase_plan}:
                insert_row = {
                    "phase_id": target_phase,
                    "title": str(mutation.get("phase_title") or target_phase.replace("_", " ").title()).strip(),
                    "objective": str(mutation.get("phase_objective") or summary or f"Advance {target_phase}.").strip(),
                    "done_when": str(mutation.get("done_when") or "The subphase objective is satisfied.").strip(),
                    "retry_phase_id": target_phase,
                    "fallback_phase_id": current_phase or target_phase,
                    "next_phase_id": current_phase,
                }
                inserted = False
                next_plan: list[dict[str, Any]] = []
                for row in phase_plan:
                    if str(row.get("phase_id") or "").strip() == current_phase:
                        row = dict(row)
                        row["next_phase_id"] = target_phase
                        next_plan.append(row)
                        next_plan.append(insert_row)
                        inserted = True
                    else:
                        next_plan.append(dict(row))
                if inserted:
                    flow_state["phase_plan"] = next_plan
                    flow_state["current_phase"] = target_phase
        elif mutation_kind == "spawn_ephemeral_role":
            ephemeral = dict(decision.get("ephemeral_role") or {})
            role_id = str(ephemeral.get("role_id") or mutation.get("target_role_id") or "").strip()
            base_role_id = str(ephemeral.get("base_role_id") or "").strip()
            if role_id and base_role_id:
                previous_role_id = str(flow_state.get("active_role_id") or "").strip()
                if role_id == DOCTOR_ROLE_ID and previous_role_id and self._session_binding_invalid(flow_state):
                    update_role_session_binding(
                        flow_state,
                        role_id=previous_role_id,
                        session_id="",
                        status="resume_failed",
                    )
                update_role_session_binding(
                    flow_state,
                    role_id=role_id,
                    session_id="",
                    status="pending_session_id",
                    role_kind="ephemeral",
                    base_role_id=base_role_id,
                    role_charter_addendum=str(ephemeral.get("charter_addendum") or "").strip(),
                )
                flow_state["active_role_id"] = role_id
        self._append_mutation(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            mutation_kind=mutation_kind,
            summary=summary,
            payload=mutation,
            role_id=str(decision.get("active_role_id") or "").strip(),
        )

    def _merge_external_operator_state(self, flow_dir_path, flow_state: dict[str, Any]) -> dict[str, Any]:
        external_state = read_flow_state(flow_dir_path)
        if not external_state:
            return {}
        _merge_operator_updates(flow_state, external_state)
        external_action = dict(external_state.get("last_operator_action") or {})
        external_action_id = str(external_action.get("action_id") or "").strip()
        applied_action_id = str(flow_state.get("latest_applied_operator_action_id") or "").strip()
        if not external_action_id or external_action_id == applied_action_id:
            return {}
        flow_state["last_operator_action"] = external_action
        for field in (
            "status",
            "approval_state",
            "pending_codex_prompt",
            "current_phase",
            "phase_attempt_count",
            "runtime_started_at",
            "runtime_elapsed_seconds",
            "latest_token_usage",
            "context_governor",
            "control_profile",
        ):
            if field in external_state:
                flow_state[field] = external_state.get(field)
        for ref in list(external_state.get("trace_refs") or []):
            _append_unique_ref(flow_state, "trace_refs", str(ref or ""))
        for ref in list(external_state.get("receipt_refs") or []):
            _append_unique_ref(flow_state, "receipt_refs", str(ref or ""))
        return external_action

    def _write_flow_state(self, flow_dir_path, flow_state: dict[str, Any]) -> None:
        self._merge_external_operator_state(flow_dir_path, flow_state)
        previous_contract, task_contract = sync_task_contract_truth(flow_dir_path, flow_state)
        append_governance_receipts(
            flow_dir_path,
            previous_contract=previous_contract,
            task_contract=task_contract,
            flow_state=flow_state,
        )
        write_json_atomic(flow_state_path(flow_dir_path), flow_state)
        self._sync_role_runtime_sidecars(flow_dir_path, flow_state)
        sync_flow_recovery_truth(flow_dir_path, flow_state=flow_state, task_contract=task_contract)

    def _consume_operator_action(
        self,
        *,
        flow_dir_path,
        flow_state: dict[str, Any],
        trace_store: FileTraceStore,
        flow_id: str,
        phase: str,
    ) -> int | None:
        action = self._merge_external_operator_state(flow_dir_path, flow_state)
        action_id = str(action.get("action_id") or "").strip()
        action_type = str(action.get("action_type") or "").strip().lower()
        if not action_type:
            return None
        self._emit_ui_event(
            kind="operator_action_applied",
            lane="supervisor",
            family="action",
            flow_id=flow_id,
            phase=phase,
            attempt_no=safe_int(flow_state.get("attempt_count"), 0),
            message=action_type,
            payload={
                "action_type": action_type,
                "action_id": action_id,
                "queued_operator_updates": list(flow_state.get("queued_operator_updates") or []),
            },
            hook_name="on_operator_action",
        )
        flow_state["latest_applied_operator_action_id"] = action_id
        trace_store.append_event(
            flow_id,
            phase=phase,
            event_type="operator.action.applied",
            payload={"action_type": action_type, "action_id": action_id},
        )
        if action_type == "pause":
            flow_state["status"] = "paused"
            flow_state["auto_fix_round_count"] = 0
            flow_state["last_completion_summary"] = str(action.get("result_summary") or "flow paused by operator").strip()
            self._write_flow_state(flow_dir_path, flow_state)
            return 0
        if action_type == "abort":
            flow_state["status"] = "failed"
            flow_state["auto_fix_round_count"] = 0
            flow_state["last_completion_summary"] = str(action.get("result_summary") or "flow aborted by operator").strip()
            self._write_flow_state(flow_dir_path, flow_state)
            return 1
        if action_type == "resume":
            flow_state["status"] = "running"
            flow_state["auto_fix_round_count"] = 0
            self._write_flow_state(flow_dir_path, flow_state)
        elif action_type in {
            "append_instruction",
            "retry_current_phase",
            "shrink_packet",
            "broaden_packet",
            "force_gate",
            "force_doctor",
            "bind_repo_contract",
            "unbind_repo_contract",
        }:
            flow_state["auto_fix_round_count"] = 0
            self._write_flow_state(flow_dir_path, flow_state)
        return None

    def _supervisor_decide(
        self,
        flow_state: dict[str, Any],
        *,
        phase: str,
        attempt_no: int,
        allow_fix_turns: bool,
    ) -> dict[str, Any]:
        pending = _compose_next_instruction(flow_state)
        latest_judge = dict(flow_state.get("latest_judge_decision") or flow_state.get("last_cursor_decision") or {})
        followup_kind = str(latest_judge.get("followup_kind") or "").strip().lower()
        issue_kind = str(latest_judge.get("issue_kind") or "").strip().lower()
        fix_round_no = safe_int(flow_state.get("auto_fix_round_count"), 0)
        active_role_id = select_active_role(flow_state, phase=phase)
        flow_state["active_role_id"] = active_role_id
        governor = _governor_state(flow_state, attempt_no=attempt_no)
        control_profile = self._current_control_profile(
            flow_state,
            current=default_control_profile(
                workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
                role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
                execution_mode=str(flow_state.get("execution_mode") or "").strip(),
                execution_context=str(flow_state.get("execution_context") or "").strip(),
            ),
        )
        flow_state["control_profile"] = control_profile
        governor_mode = str(governor.get("mode") or "").strip()
        gate_required = bool(control_profile.get("force_gate_next_turn"))
        if gate_required:
            governor_mode = "compact"
        control_mode = "recover" if governor_mode == "reset" else ("stabilize" if gate_required or governor_mode == "compact" else "progress")
        packet_size = _packet_size_for_mode(str(control_profile.get("packet_size") or ""), mode=governor_mode)
        evidence_level = _evidence_level_for_mode(str(control_profile.get("evidence_level") or ""), mode=governor_mode)
        gate_cadence = str(control_profile.get("gate_cadence") or GATE_CADENCE_PHASE).strip().lower()
        repo_binding_policy = str(control_profile.get("repo_binding_policy") or REPO_BINDING_DISABLED).strip().lower()
        decision = {
            "decision": "execute",
            "turn_kind": _turn_kind_for_phase(phase),
            "reason": f"continue mainline flow execution via role={active_role_id}",
            "confidence": 0.72,
            "next_action": "run_executor",
            "attempt_no": int(attempt_no),
            "phase": str(phase or "").strip(),
            "instruction": pending,
            "issue_kind": issue_kind or "none",
            "followup_kind": followup_kind or "none",
            "fix_round_no": int(fix_round_no),
            "active_role_id": active_role_id,
            "control_mode": control_mode,
            "packet_size": packet_size,
            "evidence_level": evidence_level,
            "gate_cadence": gate_cadence,
            "gate_required": gate_required,
            "repo_binding_policy": repo_binding_policy,
            "execution_mode": normalize_execution_mode(flow_state.get("execution_mode")),
            "session_strategy": normalize_session_strategy(
                flow_state.get("session_strategy"),
                execution_mode=str(flow_state.get("execution_mode") or "").strip(),
            ),
        }
        doctor_reason = self._doctor_trigger_reason(flow_state, phase=phase)
        if doctor_reason:
            decision.update(
                {
                    "turn_kind": "recover",
                    "reason": doctor_reason,
                    "confidence": 0.9,
                    "instruction": self._doctor_instruction(flow_state),
                    "active_role_id": DOCTOR_ROLE_ID,
                    "session_mode": "cold",
                    "load_profile": "compact",
                    "mutation": {
                        "kind": "spawn_ephemeral_role",
                        "target_role_id": DOCTOR_ROLE_ID,
                        "summary": doctor_reason,
                    },
                    "ephemeral_role": {
                        "role_id": DOCTOR_ROLE_ID,
                        "base_role_id": "fixer",
                        "charter_addendum": self._doctor_instruction(flow_state),
                    },
                }
            )
        elif allow_fix_turns and issue_kind == "agent_cli_fault" and followup_kind == "fix" and pending:
            decision["decision"] = "fix"
            decision["turn_kind"] = "fix"
            decision["reason"] = f"repair the local agent CLI fault identified by the previous judge result via role={active_role_id}"
            decision["confidence"] = 0.8
        elif pending:
            decision["reason"] = f"follow pending instruction from previous judge/recovery via role={active_role_id}"
            decision["confidence"] = 0.78
        if gate_required and decision["decision"] != "ask_operator":
            decision["reason"] = f"force a bounded gate turn before more expansion via role={active_role_id}"
            decision["confidence"] = max(float(decision.get("confidence") or 0.72), 0.8)
        normalized = self._normalize_supervisor_decision(
            decision,
            flow_state=flow_state,
            phase=phase,
            attempt_no=attempt_no,
            fallback_reason=str(decision.get("reason") or "").strip(),
        )
        self._apply_supervisor_control_profile(
            flow_state,
            normalized,
            clear_transient_flags=bool(gate_required or doctor_reason),
        )
        flow_state["latest_supervisor_decision"] = dict(normalized)
        return normalized

    def _run_supervisor_turn(
        self,
        cfg: dict[str, Any],
        flow_dir_path,
        flow_state: dict[str, Any],
        *,
        phase: str,
        attempt_no: int,
        phase_attempt_no: int,
    ) -> SupervisorDecisionV1:
        heuristic = self._supervisor_decide(
            flow_state,
            phase=phase,
            attempt_no=attempt_no,
            allow_fix_turns=flow_fix_turns_enabled(cfg),
        )
        role_id = str(heuristic.get("active_role_id") or flow_state.get("active_role_id") or select_active_role(flow_state, phase=phase)).strip()
        role_turn_no = safe_int(dict(flow_state.get("role_turn_counts") or {}).get(role_id), 0)
        role_payload = dict(dict(flow_state.get("role_sessions") or {}).get(role_id) or {})
        governor = _governor_state(flow_state, attempt_no=attempt_no)
        session_mode = session_mode_for_role(
            role_kind="ephemeral" if is_ephemeral_role(flow_state, role_id=role_id) else "stable",
            has_session=bool(role_session_id_for_turn(flow_state, role_id=role_id)),
        )
        if str(governor.get("mode") or "").strip() == "reset":
            session_mode = "cold"
        load_profile = default_load_profile(
            session_mode=session_mode,
            role_id=role_id,
            phase_changed=attempt_no > 1 and bool(flow_state.get("latest_mutation")),
            force_compact=attempt_no > 1 and str(flow_state.get("current_phase") or "").strip() != str(phase or "").strip(),
        )
        governor_mode = str(governor.get("mode") or "").strip()
        if governor_mode == "compact" and load_profile == "delta":
            load_profile = "compact"
        elif governor_mode == "reset":
            load_profile = "compact"
        compiled = self._compile_packet(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            target_role="supervisor",
            role_id=role_id,
            role_turn_no=role_turn_no,
            attempt_no=attempt_no,
            phase_attempt_no=phase_attempt_no,
            session_mode=session_mode,
            load_profile=load_profile,
            task_brief="Reassess the flow and choose the next bounded move.",
            turn_kind=str(heuristic.get("turn_kind") or _turn_kind_for_phase(phase)).strip(),
            next_instruction=_compose_next_instruction(flow_state),
        )
        self._emit_ui_event(
            kind="supervisor_input",
            lane="supervisor",
            family="input",
            title="supervisor input",
            flow_dir_path=flow_dir_path,
            flow_id=str(flow_state.get("workflow_id") or "").strip(),
            phase=phase,
            attempt_no=attempt_no,
            message=str(compiled.get("rendered_prompt") or ""),
            payload={
                "role_id": "supervisor",
                "active_role_id": role_id,
                "session_mode": session_mode,
                "load_profile": load_profile,
                "context_governor": governor,
            },
            raw_text=str(compiled.get("rendered_prompt") or ""),
        )
        runtime_request = self._build_supervisor_runtime_request(
            cfg,
            flow_id=str(flow_state.get("workflow_id") or "").strip(),
            flow_state=flow_state,
            flow_dir_path=flow_dir_path,
        )
        receipt = self._run_prompt_receipt_fn(
            str(compiled.get("rendered_prompt") or ""),
            str(flow_state.get("workspace_root") or "."),
            flow_timeout_seconds(cfg),
            cfg,
            runtime_request,
            stream=False,
        )
        thread_id = _receipt_thread_id(receipt)
        if thread_id:
            flow_state["supervisor_thread_id"] = thread_id
        supervisor_raw_output = _receipt_text(receipt)
        if supervisor_raw_output:
            self._emit_ui_event(
                kind="supervisor_output",
                lane="supervisor",
                family="output",
                title="supervisor raw output",
                flow_dir_path=flow_dir_path,
                flow_id=str(flow_state.get("workflow_id") or "").strip(),
                phase=phase,
                attempt_no=attempt_no,
                message=supervisor_raw_output,
                payload={
                    "role_id": "supervisor",
                    "active_role_id": role_id,
                    "segment": supervisor_raw_output,
                    "source": "supervisor_runtime",
                    "thread_id": thread_id,
                    "session_mode": session_mode,
                    "load_profile": load_profile,
                    "receipt_status": str(getattr(receipt, "status", "") or "").strip(),
                },
                raw_text=supervisor_raw_output,
            )
            self._emit_ui_event(
                kind="codex_segment",
                lane="supervisor",
                family="raw_execution",
                title="supervisor raw output",
                flow_dir_path=flow_dir_path,
                flow_id=str(flow_state.get("workflow_id") or "").strip(),
                phase=phase,
                attempt_no=attempt_no,
                message=supervisor_raw_output,
                payload={
                    "role_id": "supervisor",
                    "active_role_id": role_id,
                    "segment": supervisor_raw_output,
                    "source": "supervisor_runtime",
                    "compat": True,
                },
                raw_text=supervisor_raw_output,
            )
        reason = ""
        if str(getattr(receipt, "status", "") or "").strip() != "completed":
            reason = _receipt_text(receipt) or "supervisor did not complete successfully"
            decision = dict(heuristic)
            decision["reason"] = reason or str(heuristic.get("reason") or "").strip()
            decision["session_mode"] = session_mode
            decision["load_profile"] = load_profile
            decision["fallback_used"] = True
            self._append_strategy_trace(
                flow_dir_path=flow_dir_path,
                flow_state=flow_state,
                kind="supervisor_fallback",
                title="supervisor fallback used",
                summary=reason,
                family="decision",
                payload={"fallback": "heuristic", "receipt_status": str(getattr(receipt, "status", "") or "").strip()},
                attempt_no=attempt_no,
                phase=phase,
            )
            flow_state["latest_supervisor_decision"] = dict(decision)
            self._emit_ui_event(
                kind="supervisor_output",
                lane="supervisor",
                family="output",
                title="supervisor fallback output",
                flow_dir_path=flow_dir_path,
                flow_id=str(flow_state.get("workflow_id") or "").strip(),
                phase=phase,
                attempt_no=attempt_no,
                message=reason,
                payload={"fallback": "heuristic", "receipt_status": str(getattr(receipt, "status", "") or "").strip()},
                raw_text=reason,
            )
            return decision
        raw_payload = _parse_json_object(_receipt_text(receipt))
        if not raw_payload:
            reason = "supervisor returned invalid JSON"
            decision = dict(heuristic)
            decision["reason"] = reason
            decision["session_mode"] = session_mode
            decision["load_profile"] = load_profile
            decision["fallback_used"] = True
            self._append_strategy_trace(
                flow_dir_path=flow_dir_path,
                flow_state=flow_state,
                kind="supervisor_fallback",
                title="supervisor invalid JSON",
                summary=reason,
                family="decision",
                payload={"fallback": "heuristic"},
                attempt_no=attempt_no,
                phase=phase,
            )
            flow_state["latest_supervisor_decision"] = dict(decision)
            self._emit_ui_event(
                kind="supervisor_output",
                lane="supervisor",
                family="output",
                title="supervisor invalid output",
                flow_dir_path=flow_dir_path,
                flow_id=str(flow_state.get("workflow_id") or "").strip(),
                phase=phase,
                attempt_no=attempt_no,
                message=reason,
                payload={"fallback": "heuristic", "invalid_json": True},
                raw_text=reason,
            )
            return decision
        decision = self._normalize_supervisor_decision(
            raw_payload,
            flow_state=flow_state,
            phase=phase,
            attempt_no=attempt_no,
            fallback_reason=str(heuristic.get("reason") or "").strip(),
        )
        self._apply_supervisor_control_profile(flow_state, decision)
        flow_state["latest_supervisor_decision"] = dict(decision)
        self._append_strategy_trace(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            kind="supervisor_llm_decision",
            title="supervisor decision",
            summary=str(decision.get("reason") or "").strip(),
            family="decision",
            payload=dict(decision),
            attempt_no=attempt_no,
            phase=phase,
        )
        return decision

    def _consume_pending_handoff_once(
        self,
        *,
        flow_dir_path,
        flow_id: str,
        flow_state: dict[str, Any],
        role_id: str,
        phase: str,
        attempt_no: int,
    ) -> dict[str, Any]:
        inbound_handoff = self._latest_inbound_handoff(flow_dir_path, flow_state, role_id=role_id)
        if inbound_handoff and str(inbound_handoff.get("status") or "").strip() == "pending":
            consumed = mark_handoff_consumed(
                flow_dir_path,
                str(inbound_handoff.get("handoff_id") or "").strip(),
                consumed_by_role_id=role_id,
            )
            if consumed:
                inbound_handoff = consumed
                self._emit_ui_event(
                    kind="role_handoff_consumed",
                    flow_dir_path=flow_dir_path,
                    flow_id=flow_id,
                    phase=phase,
                    attempt_no=attempt_no,
                    message=str(consumed.get("summary") or consumed.get("handoff_id") or "handoff consumed").strip(),
                    payload=dict(consumed),
                    hook_name="on_role_handoff",
                )
        return inbound_handoff

    def _maybe_recovery_instruction(self, flow_state: dict[str, Any], *, codex_status: str, judge_decision: dict[str, Any]) -> str:
        if str(codex_status or "").strip() == "completed":
            return ""
        existing = str(judge_decision.get("next_codex_prompt") or "").strip()
        if existing:
            return ""
        return _build_default_retry_instruction(flow_state, codex_ok=False)

    def _should_pause_for_operator(self, flow_state: dict[str, Any], *, decision: dict[str, Any]) -> bool:
        followup_kind = str(decision.get("followup_kind") or "").strip().lower()
        if followup_kind != "fix":
            return False
        if str(decision.get("issue_kind") or "").strip().lower() != "agent_cli_fault":
            return False
        return safe_int(flow_state.get("auto_fix_round_count"), 0) > AUTO_FIX_MAX_ROUNDS

    def _pause_for_operator(
        self,
        *,
        flow_dir_path,
        trace_store: FileTraceStore,
        flow_state: dict[str, Any],
        flow_id: str,
        phase: str,
        attempt_no: int,
        decision: dict[str, Any],
    ) -> int:
        prompt = _compose_next_instruction(flow_state)
        summary = (
            f"auto-fix limit reached ({AUTO_FIX_MAX_ROUNDS}); operator input required before continuing"
        )
        supervisor_decision = {
            "decision": "ask_operator",
            "turn_kind": "operator_wait",
            "reason": summary,
            "confidence": 0.9,
            "next_action": "ask_operator",
            "attempt_no": int(attempt_no),
            "phase": str(phase or "").strip(),
            "instruction": prompt,
            "issue_kind": str(decision.get("issue_kind") or "agent_cli_fault").strip() or "agent_cli_fault",
            "followup_kind": "none",
            "fix_round_no": int(safe_int(flow_state.get("auto_fix_round_count"), 0)),
        }
        flow_state["status"] = "paused"
        self._set_approval_state(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            flow_id=flow_id,
            phase=phase,
            attempt_no=attempt_no,
            approval_state="operator_required",
            reason=summary,
            source="supervisor",
        )
        flow_state["latest_supervisor_decision"] = dict(supervisor_decision)
        flow_state["last_completion_summary"] = summary
        self._emit_ui_event(
            kind="supervisor_decided",
            lane="supervisor",
            family="decision",
            flow_dir_path=flow_dir_path,
            flow_id=flow_id,
            phase=phase,
            attempt_no=attempt_no,
            message=summary,
            payload=dict(supervisor_decision),
        )
        self._emit_ui_event(
            kind="warning",
            lane="supervisor",
            family="risk",
            flow_dir_path=flow_dir_path,
            flow_id=flow_id,
            phase=phase,
            attempt_no=attempt_no,
            message=summary,
            payload={"reason": summary, "auto_fix_round_count": safe_int(flow_state.get("auto_fix_round_count"), 0)},
        )
        self._append_strategy_trace(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            kind="ask_operator",
            title="operator input required",
            summary=summary,
            family="approval",
            payload=dict(supervisor_decision),
            attempt_no=attempt_no,
            phase=phase,
        )
        trace_store.append_event(
            flow_id,
            phase=phase,
            event_type="supervisor.ask_operator",
            payload={"attempt_no": attempt_no, **dict(supervisor_decision)},
        )
        self._write_flow_state(flow_dir_path, flow_state)
        return 0

    def apply_operator_action(
        self,
        *,
        cfg: dict[str, Any],
        flow_dir_path,
        flow_state: dict[str, Any],
        action_type: str,
        payload: dict[str, Any] | None = None,
        operator_id: str = "local_user",
        policy_source: str = "cli",
    ) -> FlowActionReceiptV1:
        _ = cfg
        action = str(action_type or "").strip().lower()
        data = dict(payload or {})
        action_id = _new_flow_id("action")
        before = {
            "status": str(flow_state.get("status") or "").strip(),
            "current_phase": str(flow_state.get("current_phase") or "").strip(),
            "pending_codex_prompt": _compose_next_instruction(flow_state),
            "control_profile": dict(flow_state.get("control_profile") or {}),
        }
        result_summary = ""
        if action == "pause":
            flow_state["status"] = "paused"
            flow_state["auto_fix_round_count"] = 0
            result_summary = "flow paused by operator"
        elif action == "resume":
            if str(flow_state.get("status") or "").strip() != "paused":
                flow_state["status"] = "running"
            flow_state["auto_fix_round_count"] = 0
            result_summary = "resume requested; start a real resume turn to continue execution"
        elif action == "append_instruction":
            instruction = str(data.get("instruction") or "").strip()
            if not instruction:
                raise ValueError("append_instruction requires non-empty instruction")
            queued = _queue_operator_update(
                flow_state,
                instruction=instruction,
                action_id=action_id,
                source=f"operator:{action}",
            )
            flow_state["auto_fix_round_count"] = 0
            result_summary = f"instruction queued for the next executor turn ({queued.get('update_id')})"
        elif action == "retry_current_phase":
            flow_state["auto_fix_round_count"] = 0
            if str(flow_state.get("workflow_kind") or "").strip() in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
                flow_state["phase_attempt_count"] = 0
            instruction = str(data.get("instruction") or "").strip() or _build_default_retry_instruction(flow_state, codex_ok=False)
            _queue_operator_update(
                flow_state,
                instruction=instruction,
                action_id=action_id,
                source=f"operator:{action}",
            )
            result_summary = "current phase prepared for retry; start a real resume turn to continue execution"
        elif action in {"shrink_packet", "broaden_packet", "force_gate", "force_doctor", "bind_repo_contract", "unbind_repo_contract"}:
            control_profile = normalize_control_profile_payload(
                flow_state.get("control_profile"),
                current={},
                workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
                role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
                execution_mode=str(flow_state.get("execution_mode") or "").strip(),
                execution_context=str(flow_state.get("execution_context") or "").strip(),
            )
            if action == "shrink_packet":
                current_size = str(control_profile.get("packet_size") or CONTROL_PACKET_MEDIUM).strip().lower()
                next_size = {
                    CONTROL_PACKET_LARGE: CONTROL_PACKET_MEDIUM,
                    CONTROL_PACKET_MEDIUM: CONTROL_PACKET_SMALL,
                    CONTROL_PACKET_SMALL: CONTROL_PACKET_SMALL,
                }[current_size]
                control_profile["packet_size"] = next_size
                control_profile["force_gate_next_turn"] = True
                result_summary = f"packet size tightened to {next_size}; next turn will run as a bounded gate"
            elif action == "broaden_packet":
                current_size = str(control_profile.get("packet_size") or CONTROL_PACKET_MEDIUM).strip().lower()
                next_size = {
                    CONTROL_PACKET_SMALL: CONTROL_PACKET_MEDIUM,
                    CONTROL_PACKET_MEDIUM: CONTROL_PACKET_LARGE,
                    CONTROL_PACKET_LARGE: CONTROL_PACKET_LARGE,
                }[current_size]
                control_profile["packet_size"] = next_size
                result_summary = f"packet size broadened to {next_size}"
            elif action == "force_gate":
                control_profile["force_gate_next_turn"] = True
                result_summary = "next supervisor turn forced into a bounded gate"
            elif action == "force_doctor":
                control_profile["force_doctor_next_turn"] = True
                result_summary = "doctor will be requested on the next supervisor turn"
            elif action == "bind_repo_contract":
                contract_path = str(data.get("repo_contract_path") or "AGENTS.md").strip()
                existing_paths = [
                    str(item or "").strip()
                    for item in list(control_profile.get("repo_contract_paths") or [])
                    if str(item or "").strip()
                ]
                if contract_path and contract_path not in existing_paths:
                    existing_paths.append(contract_path)
                control_profile["repo_binding_policy"] = REPO_BINDING_EXPLICIT
                control_profile["repo_contract_paths"] = existing_paths
                result_summary = f"repo contract bound explicitly ({contract_path or 'AGENTS.md'})"
            elif action == "unbind_repo_contract":
                control_profile["repo_binding_policy"] = REPO_BINDING_DISABLED
                control_profile["repo_contract_paths"] = []
                result_summary = "repo contract binding cleared"
            flow_state["control_profile"] = normalize_control_profile_payload(
                control_profile,
                current={},
                workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
                role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
                execution_mode=str(flow_state.get("execution_mode") or "").strip(),
                execution_context=str(flow_state.get("execution_context") or "").strip(),
            )
            flow_state["auto_fix_round_count"] = 0
        elif action == "abort":
            flow_state["status"] = "failed"
            flow_state["auto_fix_round_count"] = 0
            result_summary = "flow aborted by operator"
        else:
            raise ValueError(f"unsupported operator action: {action_type}")
        approval_state = {
            "pause": "operator_paused",
            "resume": "not_required",
            "append_instruction": "not_required",
            "retry_current_phase": "not_required",
            "shrink_packet": "not_required",
            "broaden_packet": "not_required",
            "force_gate": "not_required",
            "force_doctor": "not_required",
            "bind_repo_contract": "not_required",
            "unbind_repo_contract": "not_required",
            "abort": "operator_aborted",
        }[action]
        self._set_approval_state(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            flow_id=str(flow_state.get("workflow_id") or "").strip(),
            phase=str(flow_state.get("current_phase") or "").strip(),
            attempt_no=safe_int(flow_state.get("attempt_count"), 0),
            approval_state=approval_state,
            reason=result_summary,
            source=f"operator:{action}",
        )
        trace_id = _new_flow_id("trace")
        receipt: FlowActionReceiptV1 = {
            "action_id": action_id,
            "flow_id": str(flow_state.get("workflow_id") or "").strip(),
            "action_type": action,
            "operator_id": str(operator_id or "local_user").strip() or "local_user",
            "policy_source": str(policy_source or "cli").strip() or "cli",
            "before_state": before,
            "after_state": {
                "status": str(flow_state.get("status") or "").strip(),
                "current_phase": str(flow_state.get("current_phase") or "").strip(),
                "pending_codex_prompt": _compose_next_instruction(flow_state),
                "queued_operator_updates": list(flow_state.get("queued_operator_updates") or []),
                "control_profile": dict(flow_state.get("control_profile") or {}),
            },
            "trace_id": trace_id,
            "receipt_id": action_id,
            "result_summary": result_summary,
            "created_at": now_text(),
        }
        flow_state["last_operator_action"] = dict(receipt)
        _append_unique_ref(flow_state, "trace_refs", trace_id)
        _append_unique_ref(flow_state, "receipt_refs", action_id)
        self._append_action_record(flow_dir_path, receipt)
        append_task_receipt(
            flow_dir_path,
            {
                "receipt_id": action_id,
                "receipt_kind": "operator_action",
                "flow_id": str(flow_state.get("workflow_id") or "").strip(),
                "task_contract_id": str(flow_state.get("task_contract_id") or "").strip(),
                "phase": str(flow_state.get("current_phase") or "").strip(),
                "attempt_no": safe_int(flow_state.get("attempt_count"), 0),
                "active_role_id": str(flow_state.get("active_role_id") or "").strip(),
                "action_type": action,
                "source_ref": action_id,
                "summary": result_summary,
                "recovery_state": str(flow_state.get("status") or "").strip(),
                "created_at": str(receipt.get("created_at") or now_text()).strip(),
                "payload": dict(receipt),
            },
        )
        self._emit_ui_event(
            kind="operator_action_applied",
            flow_dir_path=flow_dir_path,
            flow_id=str(flow_state.get("workflow_id") or "").strip(),
            phase=str(flow_state.get("current_phase") or "").strip(),
            attempt_no=safe_int(flow_state.get("attempt_count"), 0),
            message=result_summary,
            payload={**dict(receipt), "queued_operator_updates": list(flow_state.get("queued_operator_updates") or [])},
            hook_name="on_operator_action",
        )
        return receipt

    def ensure_flow_runtime(self, cfg: dict[str, Any]) -> None:
        if not cli_provider_available("codex", cfg):
            raise RuntimeError("Codex CLI is unavailable for Butler Flow")
        if not cli_provider_available("cursor", cfg):
            raise RuntimeError("Cursor CLI is unavailable for Butler Flow judge")

    def build_codex_runtime_request(
        self,
        cfg: dict[str, Any],
        *,
        flow_id: str,
        flow_state: dict[str, Any],
        flow_dir_path,
    ) -> dict[str, Any]:
        active_role_id = str(flow_state.get("active_role_id") or "").strip()
        session_id = role_session_id_for_turn(flow_state, role_id=active_role_id)
        session_mode = str(dict(flow_state.get("latest_supervisor_decision") or {}).get("session_mode") or "").strip().lower()
        if session_mode == "cold" or active_role_id == DOCTOR_ROLE_ID:
            session_id = ""
        last_receipt = dict(flow_state.get("last_codex_receipt") or {})
        last_metadata = dict(last_receipt.get("metadata") or {})
        last_external_session = dict(last_metadata.get("external_session") or {})
        resume_failed = bool(last_external_session.get("resume_failed")) or self._session_binding_invalid(flow_state)
        effective_session_id = "" if resume_failed else str(session_id or "").strip()
        request = {
            "cli": "codex",
            "_disable_runtime_fallback": True,
            "workflow_id": flow_id,
            "agent_id": "butler_flow.codex_executor",
            "codex_mode": "resume" if effective_session_id else "exec",
            "codex_session_id": effective_session_id,
            "codex_home": str(prepare_flow_codex_home(flow_dir_path)),
            "execution_context": (
                "isolated"
                if active_role_id == DOCTOR_ROLE_ID
                else normalize_execution_context(
                    flow_state.get("execution_context"),
                    role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
                    workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
                )
            ),
        }
        control_profile = normalize_control_profile_payload(
            flow_state.get("control_profile"),
            current=default_control_profile(
                workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
                role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
                execution_mode=str(flow_state.get("execution_mode") or "").strip(),
                execution_context=str(flow_state.get("execution_context") or "").strip(),
            ),
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
            role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
            execution_mode=str(flow_state.get("execution_mode") or "").strip(),
            execution_context=str(flow_state.get("execution_context") or "").strip(),
        )
        request["repo_binding_policy"] = str(
            control_profile.get("repo_binding_policy") or REPO_BINDING_DISABLED
        ).strip().lower()
        if request["repo_binding_policy"] == REPO_BINDING_EXPLICIT:
            request["repo_contract_paths"] = [
                str(item or "").strip()
                for item in list(control_profile.get("repo_contract_paths") or [])
                if str(item or "").strip()
            ]
        if active_role_id == DOCTOR_ROLE_ID:
            request["execution_workspace_root"] = str(Path(flow_dir_path) / "doctor_runtime")
        if str(last_external_session.get("thread_id") or "").strip() == effective_session_id:
            request["_butler_session_binding"] = dict(last_external_session)
        overrides = flow_codex_config_overrides(cfg)
        if overrides:
            request["config_overrides"] = overrides
        return request

    def build_codex_prompt(self, cfg: dict[str, Any], flow_dir_path, flow_state: dict[str, Any], *, attempt_no: int, phase_attempt_no: int) -> str:
        active_role_id = str(flow_state.get("active_role_id") or "").strip() or select_active_role(
            flow_state,
            phase=str(flow_state.get("current_phase") or "").strip(),
        )
        flow_state["active_role_id"] = active_role_id
        role_kind = "ephemeral" if is_ephemeral_role(flow_state, role_id=active_role_id) else "stable"
        role_turn_no = safe_int(flow_state.get("active_role_turn_no"), 0)
        session_mode = str(dict(flow_state.get("latest_supervisor_decision") or {}).get("session_mode") or "").strip().lower()
        if session_mode not in {"warm", "cold"}:
            session_mode = session_mode_for_role(
                role_kind=role_kind,
                has_session=bool(role_session_id_for_turn(flow_state, role_id=active_role_id)),
            )
        governor_mode = str(dict(flow_state.get("context_governor") or {}).get("mode") or "").strip()
        if governor_mode == "reset":
            session_mode = "cold"
        load_profile = str(dict(flow_state.get("latest_supervisor_decision") or {}).get("load_profile") or "").strip().lower()
        if load_profile not in {"delta", "compact", "full"}:
            load_profile = default_load_profile(session_mode=session_mode, role_id=active_role_id)
        if governor_mode == "compact" and load_profile == "delta":
            load_profile = "compact"
        elif governor_mode == "reset":
            load_profile = "compact"
        compiled = self._compile_packet(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            target_role=active_role_id,
            role_id=active_role_id,
            role_turn_no=role_turn_no,
            attempt_no=attempt_no,
            phase_attempt_no=phase_attempt_no,
            session_mode=session_mode,
            load_profile=load_profile,
            task_brief="Do the next bounded role task and preserve forward momentum.",
            turn_kind=str(dict(flow_state.get("latest_supervisor_decision") or {}).get("turn_kind") or _turn_kind_for_phase(str(flow_state.get("current_phase") or ""))).strip(),
            next_instruction=_compose_next_instruction(flow_state),
        )
        prompt = str(compiled.get("rendered_prompt") or "")
        if active_role_id != DOCTOR_ROLE_ID:
            repo_contract_appendix = self._repo_contract_appendix(flow_state)
            if repo_contract_appendix:
                prompt = f"{prompt}\n\n{repo_contract_appendix}".strip()
        return prompt

    def judge_attempt(
        self,
        cfg: dict[str, Any],
        flow_dir_path,
        flow_state: dict[str, Any],
        *,
        codex_receipt,
        attempt_no: int,
        phase_attempt_no: int,
    ):
        flow_kind = str(flow_state.get("workflow_kind") or "").strip()
        goal = str(flow_state.get("goal") or "").strip()
        guard_condition = str(flow_state.get("guard_condition") or "").strip()
        phase = str(flow_state.get("current_phase") or _default_phase(flow_kind)).strip()
        codex_output = _receipt_text(codex_receipt)
        codex_metadata = dict(getattr(codex_receipt, "metadata", {}) or {})
        codex_session_id = str(flow_state.get("codex_session_id") or _receipt_thread_id(codex_receipt)).strip()
        active_role_id = str(flow_state.get("active_role_id") or "").strip()
        role_session_id = role_session_id_for_turn(flow_state, role_id=active_role_id)
        inbound_handoff = self._latest_inbound_handoff(flow_dir_path, flow_state, role_id=active_role_id)
        phase_artifact = _build_phase_artifact(
            flow_state,
            phase=phase,
            role_id=active_role_id,
            attempt_no=attempt_no,
            phase_attempt_no=phase_attempt_no,
            codex_receipt=codex_receipt,
        )
        flow_state["current_phase_artifact"] = dict(phase_artifact)
        recent_history = _recent_phase_history(flow_state)
        phase_plan = resolve_phase_plan(flow_state)
        phase_context = phase_prompt_context(phase_plan, phase)
        judge_context = {
            "codex_status": str(getattr(codex_receipt, "status", "") or "").strip(),
            "codex_session_id": codex_session_id,
            "codex_output": codex_output,
            "codex_metadata": codex_metadata,
            "phase_history": recent_history,
            "phase_artifact": phase_artifact,
            "active_role_id": active_role_id,
            "role_session_id": role_session_id,
            "inbound_handoff": inbound_handoff,
        }
        flow_state["_judge_runtime_context"] = judge_context
        compiled = self._compile_packet(
            flow_dir_path=flow_dir_path,
            flow_state=flow_state,
            target_role="judge",
            role_id="judge",
            role_turn_no=safe_int(flow_state.get("attempt_count"), 0),
            attempt_no=attempt_no,
            phase_attempt_no=phase_attempt_no,
            session_mode="cold",
            load_profile="compact",
            task_brief="Judge the latest executor attempt and return a structured verdict.",
            turn_kind="review",
            next_instruction="Use the latest executor output and artifacts to decide whether the flow should complete, retry, advance, or abort.",
        )
        judge_prompt = str(compiled.get("rendered_prompt") or "")
        cursor_receipt = self._run_prompt_receipt_fn(
            judge_prompt,
            str(flow_state.get("workspace_root") or "."),
            judge_timeout_seconds(cfg),
            cfg,
            {
                "cli": "cursor",
                "_disable_runtime_fallback": True,
                "workflow_id": str(flow_state.get("workflow_id") or "").strip(),
                "agent_id": "butler_flow.cursor_judge",
            },
            stream=False,
        )
        if str(getattr(cursor_receipt, "status", "") or "").strip() != "completed":
            reason = _receipt_text(cursor_receipt) or "Cursor judge did not complete successfully"
            if flow_state.get("workflow_kind") in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
                decision = _normalize_project_decision({}, fallback_reason=reason, phase_plan=phase_plan)
            else:
                decision = _normalize_single_goal_decision({}, fallback_reason=reason)
            decision["reason"] = reason
            decision["next_codex_prompt"] = ""
            decision = _classify_decision_defaults(
                decision,
                phase=phase,
                codex_status=str(getattr(codex_receipt, "status", "") or "").strip(),
                allow_fix_turns=flow_fix_turns_enabled(cfg),
            )
            return cursor_receipt, decision
        raw_payload = _parse_json_object(_receipt_text(cursor_receipt))
        reason = "Cursor judge returned invalid JSON"
        if flow_kind in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
            decision = _normalize_project_decision(raw_payload, fallback_reason=reason, phase_plan=phase_plan)
            decision = _normalize_project_loop_decision(decision, phase=phase, flow_state=flow_state)
        else:
            decision = _normalize_single_goal_decision(raw_payload, fallback_reason=reason)
        decision = _classify_decision_defaults(
            decision,
            phase=phase,
            codex_status=str(getattr(codex_receipt, "status", "") or "").strip(),
            allow_fix_turns=flow_fix_turns_enabled(cfg),
        )
        if not decision.get("next_codex_prompt") and decision.get("decision") in {"RETRY", "ADVANCE"}:
            followup_kind = str(decision.get("followup_kind") or "").strip().lower()
            issue_kind = str(decision.get("issue_kind") or "").strip().lower()
            if issue_kind == "agent_cli_fault" and followup_kind == "fix":
                decision["next_codex_prompt"] = _build_default_fix_instruction(flow_state, phase=phase)
            elif followup_kind == "replan":
                decision["next_codex_prompt"] = _build_default_replan_instruction(flow_state)
            else:
                decision["next_codex_prompt"] = _build_default_retry_instruction(
                    flow_state,
                    codex_ok=str(getattr(codex_receipt, "status", "") or "").strip() == "completed",
                )
        return cursor_receipt, decision

    def run_flow_loop(self, cfg: dict[str, Any], flow_dir_path, flow_state: dict[str, Any], *, stream_enabled: bool) -> int:
        state_store = FileRuntimeStateStore(flow_dir_path)
        ensure_flow_sidecars(flow_dir_path, flow_state)
        cleanup = state_store.cleanup_before_start(pid_probe=_pid_probe)
        locked, _ = state_store.acquire_lock(current_pid=os.getpid(), pid_probe=_pid_probe)
        if not locked:
            owner = state_store.read_pid()
            raise RuntimeError(f"flow is already running under pid={owner or 'unknown'}")
        trace_store = FileTraceStore(state_store.traces_dir())
        ensure_trace(
            trace_store,
            run_id=str(flow_state.get("trace_run_id") or flow_state.get("workflow_id") or "").strip(),
            metadata={
                "flow_kind": str(flow_state.get("workflow_kind") or "").strip(),
                "goal": str(flow_state.get("goal") or "").strip(),
                "guard_condition": str(flow_state.get("guard_condition") or "").strip(),
                "cleanup": cleanup,
            },
        )
        flow_id = str(flow_state.get("workflow_id") or "").strip()
        flow_state["execution_mode"] = normalize_execution_mode(
            flow_state.get("execution_mode")
            or default_execution_mode(cfg, workflow_kind=str(flow_state.get("workflow_kind") or "").strip())
        )
        flow_state["session_strategy"] = normalize_session_strategy(
            flow_state.get("session_strategy"),
            execution_mode=str(flow_state.get("execution_mode") or "").strip(),
        )
        flow_state["role_pack_id"] = normalize_role_pack_id(
            flow_state.get("role_pack_id") or default_role_pack_id(cfg, workflow_kind=str(flow_state.get("workflow_kind") or "").strip()),
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
        )
        if not isinstance(flow_state.get("role_sessions"), dict) or not flow_state.get("role_sessions"):
            flow_state["role_sessions"] = load_role_sessions(flow_dir_path)
        if not flow_state.get("active_role_id"):
            flow_state["active_role_id"] = select_active_role(
                flow_state,
                phase=str(flow_state.get("current_phase") or "").strip(),
            )
        if not str(flow_state.get("supervisor_thread_id") or "").strip():
            flow_state["supervisor_thread_id"] = str(flow_state.get("codex_session_id") or "").strip()
        if not str(flow_state.get("runtime_started_at") or "").strip():
            flow_state["runtime_started_at"] = now_text()
        _refresh_runtime_clock(flow_state)
        self._write_flow_state(flow_dir_path, flow_state)
        trace_store.append_event(flow_id, phase=str(flow_state.get("current_phase") or "").strip(), event_type="flow.shell.start", payload={"cleanup": cleanup})
        state_store.write_pid(os.getpid())
        state_store.write_watchdog_state(state="foreground", pid=os.getpid(), note="butler-flow active")
        try:
            while True:
                current_phase = str(flow_state.get("current_phase") or _default_phase(str(flow_state.get("workflow_kind") or ""))).strip()
                operator_result = self._consume_operator_action(
                    flow_dir_path=flow_dir_path,
                    flow_state=flow_state,
                    trace_store=trace_store,
                    flow_id=flow_id,
                    phase=current_phase,
                )
                if operator_result is not None:
                    return operator_result
                if _runtime_budget_reached(flow_state):
                    budget = int(safe_int(flow_state.get("max_runtime_seconds"), 0))
                    elapsed = int(safe_int(flow_state.get("runtime_elapsed_seconds"), 0))
                    has_queued_updates = bool(_next_operator_update(flow_state))
                    if has_queued_updates:
                        flow_state["status"] = "paused"
                        flow_state["last_completion_summary"] = (
                            f"runtime budget reached ({elapsed}/{budget}s); queued operator updates preserved for the next explicit resume"
                        )
                        self._set_approval_state(
                            flow_dir_path=flow_dir_path,
                            flow_state=flow_state,
                            flow_id=flow_id,
                            phase=current_phase,
                            attempt_no=safe_int(flow_state.get("attempt_count"), 0),
                            approval_state="operator_required",
                            reason=str(flow_state.get("last_completion_summary") or "").strip(),
                            source="runtime_budget",
                        )
                        self._write_flow_state(flow_dir_path, flow_state)
                        self._emit_ui_event(
                            kind="warning",
                            lane="supervisor",
                            family="risk",
                            flow_dir_path=flow_dir_path,
                            flow_id=flow_id,
                            phase=current_phase,
                            attempt_no=safe_int(flow_state.get("attempt_count"), 0),
                            message=str(flow_state.get("last_completion_summary") or "").strip(),
                            payload={"max_runtime_seconds": budget, "runtime_elapsed_seconds": elapsed},
                        )
                        return 0
                    flow_state["status"] = "failed"
                    flow_state["last_completion_summary"] = f"runtime budget reached: {elapsed}/{budget}s"
                    self._write_flow_state(flow_dir_path, flow_state)
                    trace_store.append_event(flow_id, phase=current_phase, event_type="flow.failed", payload={"reason": flow_state["last_completion_summary"]})
                    self._emit_ui_event(
                        kind="run_failed",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=current_phase,
                        attempt_no=safe_int(flow_state.get("attempt_count"), 0),
                        message=str(flow_state["last_completion_summary"]),
                        payload={"reason": flow_state["last_completion_summary"]},
                    )
                    return 1
                attempt_count = safe_int(flow_state.get("attempt_count"), 0)
                max_attempts = safe_int(flow_state.get("max_attempts"), DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS)
                if max_attempts > 0 and attempt_count >= max_attempts:
                    flow_state["status"] = "failed"
                    flow_state["last_completion_summary"] = f"attempt limit reached: {attempt_count}/{max_attempts}"
                    self._write_flow_state(flow_dir_path, flow_state)
                    trace_store.append_event(flow_id, phase=str(flow_state.get("current_phase") or "").strip(), event_type="flow.failed", payload={"reason": flow_state["last_completion_summary"]})
                    self._emit_ui_event(
                        kind="run_failed",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=str(flow_state.get("current_phase") or "").strip(),
                        attempt_no=attempt_count,
                        message=str(flow_state["last_completion_summary"]),
                        payload={"reason": flow_state["last_completion_summary"]},
                    )
                    return 1
                if flow_state.get("workflow_kind") in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
                    phase_attempts = sync_project_phase_attempt_count(flow_state)
                    max_phase_attempts = safe_int(flow_state.get("max_phase_attempts"), DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS)
                    if max_phase_attempts > 0 and phase_attempts >= max_phase_attempts:
                        flow_state["status"] = "failed"
                        flow_state["last_completion_summary"] = (
                            f"phase attempt limit reached for {flow_state.get('current_phase')}: "
                            f"{phase_attempts}/{max_phase_attempts}"
                        )
                        self._write_flow_state(flow_dir_path, flow_state)
                        trace_store.append_event(flow_id, phase=str(flow_state.get("current_phase") or "").strip(), event_type="flow.failed", payload={"reason": flow_state["last_completion_summary"]})
                        self._emit_ui_event(
                            kind="run_failed",
                            flow_dir_path=flow_dir_path,
                            flow_id=flow_id,
                            phase=str(flow_state.get("current_phase") or "").strip(),
                            attempt_no=attempt_count,
                            message=str(flow_state["last_completion_summary"]),
                            payload={"reason": flow_state["last_completion_summary"]},
                        )
                        return 1

                attempt_no = attempt_count + 1
                phase = str(flow_state.get("current_phase") or _default_phase(str(flow_state.get("workflow_kind") or ""))).strip()
                phase_attempt_no = safe_int(flow_state.get("phase_attempt_count"), 0) + 1
                turn_id = _new_flow_id("turn")
                flow_state["current_turn_id"] = turn_id
                _plan_operator_update_for_attempt(flow_state, attempt_no=attempt_no)
                if attempt_no == 1:
                    self._emit_ui_event(
                        kind="run_started",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        message="flow run started",
                        payload={"turn_id": turn_id, "flow_kind": str(flow_state.get("workflow_kind") or "").strip()},
                        hook_name="on_run_started",
                    )
                if llm_supervisor_enabled(cfg):
                    supervisor_decision = self._run_supervisor_turn(
                        cfg,
                        flow_dir_path,
                        flow_state,
                        phase=phase,
                        attempt_no=attempt_no,
                        phase_attempt_no=phase_attempt_no,
                    )
                    self._apply_supervisor_mutation(
                        flow_dir_path=flow_dir_path,
                        flow_state=flow_state,
                        decision=supervisor_decision,
                    )
                else:
                    self._emit_ui_event(
                        kind="supervisor_input",
                        lane="supervisor",
                        family="input",
                        title="supervisor heuristic input",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        message=_compose_next_instruction(flow_state),
                        payload={"heuristic": True, "context_governor": _governor_state(flow_state, attempt_no=attempt_no)},
                        raw_text=_compose_next_instruction(flow_state),
                    )
                    supervisor_decision = self._supervisor_decide(
                        flow_state,
                        phase=phase,
                        attempt_no=attempt_no,
                        allow_fix_turns=flow_fix_turns_enabled(cfg),
                    )
                    self._apply_supervisor_mutation(
                        flow_dir_path=flow_dir_path,
                        flow_state=flow_state,
                        decision=supervisor_decision,
                    )
                    self._emit_ui_event(
                        kind="supervisor_output",
                        lane="supervisor",
                        family="output",
                        title="supervisor heuristic output",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        message=str(supervisor_decision.get("reason") or "").strip(),
                        payload={**dict(supervisor_decision), "heuristic": True},
                        raw_text=json.dumps(supervisor_decision, ensure_ascii=False),
                    )
                phase = str(flow_state.get("current_phase") or phase).strip()
                active_role_id = str(supervisor_decision.get("active_role_id") or flow_state.get("active_role_id") or "").strip()
                flow_state["active_role_id"] = active_role_id
                role_turn_no = bump_active_role_turn_no(flow_state, role_id=active_role_id)
                inbound_handoff = self._consume_pending_handoff_once(
                    flow_dir_path=flow_dir_path,
                    flow_id=flow_id,
                    flow_state=flow_state,
                    role_id=active_role_id,
                    phase=phase,
                    attempt_no=attempt_no,
                )
                role_session_id = role_session_id_for_turn(flow_state, role_id=active_role_id)
                self._emit_ui_event(
                    kind="supervisor_decided",
                    flow_dir_path=flow_dir_path,
                    flow_id=flow_id,
                    phase=phase,
                    attempt_no=attempt_no,
                    message=str(supervisor_decision.get("reason") or "").strip(),
                    payload=dict(supervisor_decision),
                )
                self._emit_ui_event(
                    kind="supervisor_decision_applied",
                    lane="supervisor",
                    family="decision",
                    flow_dir_path=flow_dir_path,
                    flow_id=flow_id,
                    phase=phase,
                    attempt_no=attempt_no,
                    message=str(supervisor_decision.get("next_action") or "run_executor").strip(),
                    payload=dict(supervisor_decision),
                )
                trace_store.append_event(
                    flow_id,
                    phase=phase,
                    event_type="supervisor.decided",
                    payload={"turn_id": turn_id, **dict(supervisor_decision)},
                )
                if str(supervisor_decision.get("next_action") or "").strip() == "ask_operator":
                    flow_state["pending_codex_prompt"] = str(supervisor_decision.get("instruction") or flow_state.get("pending_codex_prompt") or "").strip()
                    self._set_approval_state(
                        flow_dir_path=flow_dir_path,
                        flow_state=flow_state,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        approval_state="operator_required",
                        reason=str(supervisor_decision.get("reason") or "").strip(),
                        source="supervisor",
                    )
                    flow_state["status"] = "paused"
                    self._write_flow_state(flow_dir_path, flow_state)
                    return 0
                flow_state["status"] = "running"
                planned_operator_update = _plan_operator_update_for_attempt(flow_state, attempt_no=attempt_no)
                self._write_flow_state(flow_dir_path, flow_state)
                state_store.write_run_state(
                    run_id=flow_id,
                    state="running",
                    phase=phase,
                    pid=os.getpid(),
                    note=f"attempt {attempt_no} phase={phase}",
                )
                self._display.write(f"[butler-flow] attempt={attempt_no} phase={phase} flow_id={flow_id}")
                codex_prompt = self.build_codex_prompt(cfg, flow_dir_path, flow_state, attempt_no=attempt_no, phase_attempt_no=phase_attempt_no)
                turn_record: FlowTurnRecordV1 = {
                    "turn_id": turn_id,
                    "flow_id": flow_id,
                    "phase": phase,
                    "turn_kind": str(supervisor_decision.get("turn_kind") or _turn_kind_for_phase(phase)).strip(),
                    "role_id": active_role_id,
                    "role_session_id": role_session_id,
                    "source_handoff_id": str(dict(inbound_handoff or {}).get("handoff_id") or "").strip(),
                    "target_handoff_id": "",
                    "attempt_no": int(attempt_no),
                    "supervisor_decision": dict(supervisor_decision),
                    "executor_agent_id": "butler_flow.codex_executor",
                    "judge_agent_id": "butler_flow.cursor_judge",
                    "artifact_refs": [],
                    "trace_id": _new_flow_id("trace"),
                    "receipt_id": _new_flow_id("receipt"),
                    "started_at": now_text(),
                }
                self._append_turn_record(flow_dir_path, turn_record)
                trace_store.append_event(flow_id, phase=phase, event_type="codex.attempt.start", payload={"attempt_no": attempt_no, "phase_attempt_no": phase_attempt_no})
                allow_terminal_stream = bool(getattr(self._display, "supports_terminal_stream", True))
                console = TerminalConsole(stream=self._display._stdout) if stream_enabled and allow_terminal_stream else None
                printer = TerminalStreamPrinter(console=console, prefix="codex> ") if console is not None else None
                def _on_segment(segment: str) -> None:
                    if printer is not None:
                        printer.on_segment(segment)
                    self._emit_ui_event(
                        kind="codex_segment",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        message=str(segment or ""),
                        payload={
                            "segment": str(segment or ""),
                            "role_id": active_role_id,
                            "active_role_id": active_role_id,
                            "turn_kind": str(turn_record.get("turn_kind") or "").strip(),
                        },
                    )
                def _on_event(event: dict[str, Any]) -> None:
                    if console is not None:
                        console.emit_runtime_event(event)
                    payload = dict(event or {})
                    payload.setdefault("role_id", active_role_id)
                    payload.setdefault("active_role_id", active_role_id)
                    payload.setdefault("turn_kind", str(turn_record.get("turn_kind") or "").strip())
                    self._emit_ui_event(
                        kind="codex_runtime_event",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        message=str(payload.get("text") or payload.get("kind") or "").strip(),
                        payload=payload,
                    )
                codex_receipt = self._run_prompt_receipt_fn(
                    codex_prompt,
                    str(flow_state.get("workspace_root") or "."),
                    flow_timeout_seconds(cfg),
                    cfg,
                    self.build_codex_runtime_request(cfg, flow_id=flow_id, flow_state=flow_state, flow_dir_path=flow_dir_path),
                    stream=stream_enabled,
                    on_segment=_on_segment if stream_enabled else None,
                    on_event=_on_event if stream_enabled else None,
                )
                if printer is not None:
                    printer.finalize(_receipt_text(codex_receipt))
                thread_id = _receipt_thread_id(codex_receipt)
                resolved_role_session_id = str(thread_id or role_session_id or "").strip()
                if thread_id:
                    flow_state["codex_session_id"] = thread_id
                    flow_state["primary_executor_session_id"] = thread_id
                    if not str(flow_state.get("supervisor_thread_id") or "").strip():
                        flow_state["supervisor_thread_id"] = thread_id
                if active_role_id:
                    update_role_session_binding(
                        flow_state,
                        role_id=active_role_id,
                        session_id=resolved_role_session_id,
                        status="ready" if resolved_role_session_id else "pending_session_id",
                        last_handoff_id=str(turn_record.get("source_handoff_id") or "").strip(),
                    )
                flow_state["attempt_count"] = attempt_no
                flow_state["last_codex_receipt"] = _serialize_receipt(codex_receipt)
                flow_state["latest_token_usage"] = _normalize_usage_payload(dict(getattr(codex_receipt, "metadata", {}) or {}))
                executed_operator_update = _mark_operator_update_executed(
                    flow_state,
                    attempt_no=attempt_no,
                    codex_status=str(getattr(codex_receipt, "status", "") or "").strip(),
                )
                self._write_flow_state(flow_dir_path, flow_state)
                trace_store.append_event(
                    flow_id,
                    phase=phase,
                    event_type="codex.attempt.done" if str(getattr(codex_receipt, "status", "") or "").strip() == "completed" else "codex.attempt.failed",
                    payload={"attempt_no": attempt_no, "thread_id": str(flow_state.get("codex_session_id") or "").strip()},
                )
                doctor_framework_bug_report = ""
                if active_role_id == DOCTOR_ROLE_ID:
                    doctor_framework_bug_report = self._doctor_framework_bug_report(codex_receipt)
                if doctor_framework_bug_report:
                    turn_record["decision"] = "ASK_OPERATOR"
                    turn_record["reason"] = "doctor escalated a butler-flow framework bug"
                    turn_record["confidence"] = float(supervisor_decision.get("confidence") or 0.0)
                    turn_record["completed_at"] = now_text()
                    self._append_turn_record(flow_dir_path, turn_record)
                    _append_unique_ref(flow_state, "trace_refs", str(turn_record.get("trace_id") or ""))
                    _append_unique_ref(flow_state, "receipt_refs", str(turn_record.get("receipt_id") or ""))
                    self._append_attempt_draft(
                        state_store=state_store,
                        attempt_no=attempt_no,
                        phase=phase,
                        codex_prompt=codex_prompt,
                        codex_receipt=codex_receipt,
                        cursor_receipt=None,
                        decision={
                            "decision": "ASK_OPERATOR",
                            "reason": "doctor escalated a butler-flow framework bug",
                            "next_codex_prompt": doctor_framework_bug_report,
                            "completion_summary": doctor_framework_bug_report,
                            "issue_kind": "bug",
                            "followup_kind": "none",
                        },
                    )
                    return self._pause_for_doctor_framework_bug(
                        flow_dir_path=flow_dir_path,
                        trace_store=trace_store,
                        flow_state=flow_state,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        report=doctor_framework_bug_report,
                    )
                self._display.write("[butler-flow] cursor judge evaluating latest attempt")
                cursor_receipt, decision = self.judge_attempt(
                    cfg,
                    flow_dir_path,
                    flow_state,
                    codex_receipt=codex_receipt,
                    attempt_no=attempt_no,
                    phase_attempt_no=phase_attempt_no,
                )
                self._emit_ui_event(
                    kind="judge_result",
                    flow_dir_path=flow_dir_path,
                    flow_id=flow_id,
                    phase=phase,
                    attempt_no=attempt_no,
                    message=str(decision.get("decision") or "").strip(),
                    payload={
                        "decision": dict(decision or {}),
                        "cursor_status": str(getattr(cursor_receipt, "status", "") or "").strip(),
                        "cursor_receipt": _serialize_receipt(cursor_receipt),
                    },
                    hook_name="on_judge_result",
                )
                flow_state["last_cursor_receipt"] = _serialize_receipt(cursor_receipt)
                flow_state["last_cursor_decision"] = dict(decision or {})
                flow_state["latest_judge_decision"] = dict(decision or {})
                flow_state["last_completion_summary"] = str(decision.get("completion_summary") or decision.get("reason") or "").strip()
                followup_kind = str(decision.get("followup_kind") or "").strip().lower()
                issue_kind = str(decision.get("issue_kind") or "").strip().lower()
                if issue_kind == "agent_cli_fault" and followup_kind == "fix":
                    flow_state["auto_fix_round_count"] = safe_int(flow_state.get("auto_fix_round_count"), 0) + 1
                else:
                    flow_state["auto_fix_round_count"] = 0
                if issue_kind == "service_fault":
                    flow_state["service_fault_streak"] = safe_int(flow_state.get("service_fault_streak"), 0) + 1
                else:
                    flow_state["service_fault_streak"] = 0
                recovery_instruction = self._maybe_recovery_instruction(
                    flow_state,
                    codex_status=str(getattr(codex_receipt, "status", "") or "").strip(),
                    judge_decision=dict(decision or {}),
                )
                flow_state["pending_codex_prompt"] = str(decision.get("next_codex_prompt") or recovery_instruction).strip()
                if flow_state.get("service_fault_streak") and safe_int(flow_state.get("service_fault_streak"), 0) >= 2:
                    shrink_prefix = (
                        "Service instability detected. Shrink the work package, summarize only the critical delta, avoid broad retries, "
                        "and verify the smallest forward step first."
                    )
                    followup = str(flow_state.get("pending_codex_prompt") or "").strip()
                    flow_state["pending_codex_prompt"] = (
                        f"{shrink_prefix}\n\n{followup}".strip() if followup else shrink_prefix
                    )
                flow_state["phase_history"] = list(flow_state.get("phase_history") or []) + [
                    {
                        "at": now_text(),
                        "attempt_no": attempt_no,
                        "phase": phase,
                        "codex_status": str(getattr(codex_receipt, "status", "") or "").strip(),
                        "cursor_status": str(getattr(cursor_receipt, "status", "") or "").strip(),
                        "decision": dict(decision or {}),
                        "token_usage": dict(flow_state.get("latest_token_usage") or {}),
                        "executed_operator_update_id": str(executed_operator_update.get("update_id") or "").strip(),
                    }
                ]
                if flow_state.get("workflow_kind") in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
                    sync_project_phase_attempt_count(flow_state)
                decision_name = str(decision.get("decision") or "").strip().upper()
                next_phase_for_followup = phase
                if flow_state.get("workflow_kind") in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
                    next_phase_for_followup = str(decision.get("next_phase") or "").strip().lower()
                    phase_plan = resolve_phase_plan(flow_state)
                    phase_context = phase_prompt_context(phase_plan, phase)
                    retry_phase = str(phase_context.get("retry_phase_id") or phase).strip() or phase
                    fallback_phase = str(phase_context.get("fallback_phase_id") or retry_phase).strip() or retry_phase
                    if decision_name == "ADVANCE":
                        if not next_phase_for_followup:
                            next_phase_for_followup = _phase_after(flow_state, phase)
                    elif decision_name == "RETRY":
                        if not next_phase_for_followup:
                            next_phase_for_followup = retry_phase
                    else:
                        next_phase_for_followup = phase
                    if issue_kind == "agent_cli_fault" and followup_kind == "fix":
                        next_phase_for_followup = phase
                    elif followup_kind == "replan" or issue_kind == "plan_gap":
                        if flow_state.get("workflow_kind") == PROJECT_LOOP_KIND:
                            next_phase_for_followup = "plan"
                        else:
                            next_phase_for_followup = fallback_phase
                next_role_id = determine_followup_role(
                    flow_state,
                    current_role_id=active_role_id,
                    current_phase=phase,
                    next_phase=next_phase_for_followup or phase,
                    decision=dict(decision or {}),
                )
                artifact = dict(flow_state.get("current_phase_artifact") or {})
                artifact_ref = ""
                if artifact:
                    artifact_ref = f"artifact:{attempt_no}:{phase}"
                    artifact_payload = {
                        "artifact_ref": artifact_ref,
                        "task_contract_id": str(flow_state.get("task_contract_id") or "").strip(),
                        "producer_role_id": active_role_id,
                        "consumer_role_ids": [next_role_id] if str(next_role_id or "").strip() else [],
                        "turn_id": turn_id,
                        "produced_by_receipt_id": str(turn_record.get("receipt_id") or "").strip(),
                        "accepted_in_receipt_id": (
                            str(turn_record.get("receipt_id") or "").strip()
                            if decision_name in {"ADVANCE", "COMPLETE"}
                            else ""
                        ),
                        "status": "accepted" if decision_name in {"ADVANCE", "COMPLETE"} else "recorded",
                        "created_at": now_text(),
                        **artifact,
                    }
                    self._register_artifact(flow_dir_path, artifact_payload)
                    trace_store.append_event(
                        flow_id,
                        phase=phase,
                        event_type="artifact.registered",
                        payload={"turn_id": turn_id, "artifact_ref": artifact_ref},
                    )
                    self._emit_ui_event(
                        kind="artifact_registered",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        message=artifact_ref,
                        payload=artifact_payload,
                    )
                if decision_name in {"ADVANCE", "COMPLETE"}:
                    append_task_receipt(
                        flow_dir_path,
                        {
                            "receipt_id": str(turn_record.get("receipt_id") or "").strip(),
                            "receipt_kind": "turn_acceptance",
                            "flow_id": flow_id,
                            "task_contract_id": str(flow_state.get("task_contract_id") or "").strip(),
                            "phase": phase,
                            "attempt_no": attempt_no,
                            "active_role_id": active_role_id,
                            "decision": decision_name,
                            "source_ref": str(turn_record.get("turn_id") or "").strip(),
                            "summary": str(flow_state.get("last_completion_summary") or decision.get("reason") or "").strip(),
                            "recovery_state": str(flow_state.get("status") or "").strip(),
                            "created_at": now_text(),
                            "payload": {
                                "followup_kind": followup_kind,
                                "issue_kind": issue_kind,
                                "latest_judge_decision": dict(decision or {}),
                            },
                        },
                    )
                    if artifact_ref:
                        append_task_receipt(
                            flow_dir_path,
                            {
                                "receipt_id": f"{str(turn_record.get('receipt_id') or '').strip()}:artifact",
                                "receipt_kind": "artifact_acceptance",
                                "flow_id": flow_id,
                                "task_contract_id": str(flow_state.get("task_contract_id") or "").strip(),
                                "phase": phase,
                                "attempt_no": attempt_no,
                                "active_role_id": active_role_id,
                                "artifact_ref": artifact_ref,
                                "decision": decision_name,
                                "source_ref": str(turn_record.get("receipt_id") or turn_record.get("turn_id") or "").strip(),
                                "summary": f"artifact accepted: {artifact_ref}",
                                "recovery_state": str(flow_state.get("status") or "").strip(),
                                "created_at": now_text(),
                            },
                        )
                if self._role_runtime_active(flow_state) and role_runtime_enabled(
                    cfg,
                    execution_mode=str(flow_state.get("execution_mode") or "").strip(),
                ):
                    current_session_strategy = normalize_session_strategy(
                        flow_state.get("session_strategy"),
                        execution_mode=str(flow_state.get("execution_mode") or "").strip(),
                    )
                    if str(next_role_id or "").strip() and (
                        next_role_id != active_role_id
                        or str(next_phase_for_followup or phase).strip().lower() != str(phase or "").strip().lower()
                        or current_session_strategy != "role_bound"
                    ):
                        handoff = create_handoff_packet(
                            flow_state,
                            from_role_id=active_role_id,
                            to_role_id=next_role_id,
                            source_phase=phase,
                            target_phase=str(next_phase_for_followup or phase).strip(),
                            summary=str(decision.get("reason") or flow_state.get("last_completion_summary") or "").strip(),
                            next_action=str(decision.get("next_codex_prompt") or "").strip(),
                            artifact_refs=[artifact_ref] if artifact_ref else [],
                            verification_refs=[artifact_ref] if artifact_ref and str(decision_name or "") == "COMPLETE" else [],
                            risk_flags=[value for value in (issue_kind, followup_kind) if str(value or "").strip() and str(value or "").strip() != "none"],
                            completion_summary=str(flow_state.get("last_completion_summary") or "").strip(),
                        )
                        append_handoff(flow_dir_path, handoff)
                        self._emit_ui_event(
                            kind="role_handoff_created",
                            flow_dir_path=flow_dir_path,
                            flow_id=flow_id,
                            phase=phase,
                            attempt_no=attempt_no,
                            message=str(handoff.get("summary") or f"{active_role_id} -> {next_role_id}").strip(),
                            payload=dict(handoff),
                            hook_name="on_role_handoff",
                        )
                        record_latest_handoff(flow_state, role_id=next_role_id, handoff_id=str(handoff.get("handoff_id") or "").strip())
                        update_role_session_binding(
                            flow_state,
                            role_id=next_role_id,
                            session_id=role_session_id_for_turn(flow_state, role_id=next_role_id),
                            last_handoff_id=str(handoff.get("handoff_id") or "").strip(),
                        )
                        turn_record["target_handoff_id"] = str(handoff.get("handoff_id") or "").strip()
                self._write_flow_state(flow_dir_path, flow_state)
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
                    flow_id,
                    phase=phase,
                    event_type=f"judge.{str(decision.get('decision') or '').strip().lower() or 'unknown'}",
                    payload={"attempt_no": attempt_no, **dict(decision or {})},
                )
                self._display.write(
                    "[butler-flow] judge decision="
                    f"{str(decision.get('decision') or '').strip()} "
                    f"reason={str(decision.get('reason') or '').strip() or '-'}"
                )
                turn_record["decision"] = str(decision.get("decision") or "").strip().upper()
                turn_record["reason"] = str(decision.get("reason") or "").strip()
                turn_record["confidence"] = float(supervisor_decision.get("confidence") or 0.0)
                turn_record["artifact_refs"] = [artifact_ref] if artifact_ref else []
                turn_record["completed_at"] = now_text()
                self._append_turn_record(flow_dir_path, turn_record)
                _append_unique_ref(flow_state, "trace_refs", str(turn_record.get("trace_id") or ""))
                _append_unique_ref(flow_state, "receipt_refs", str(turn_record.get("receipt_id") or ""))
                self._write_flow_state(flow_dir_path, flow_state)

                if decision_name not in {"COMPLETE", "ABORT"}:
                    operator_result = self._consume_operator_action(
                        flow_dir_path=flow_dir_path,
                        flow_state=flow_state,
                        trace_store=trace_store,
                        flow_id=flow_id,
                        phase=phase,
                    )
                    if operator_result is not None:
                        return operator_result

                if decision_name == "COMPLETE":
                    flow_state["status"] = "completed"
                    flow_state["auto_fix_round_count"] = 0
                    self._write_flow_state(flow_dir_path, flow_state)
                    trace_store.append_event(flow_id, phase=phase, event_type="flow.completed", payload=dict(decision or {}))
                    self._emit_ui_event(
                        kind="run_completed",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        message=str(flow_state.get("last_completion_summary") or "flow completed"),
                        payload=dict(decision or {}),
                        hook_name="on_run_finished",
                    )
                    return 0
                if decision_name == "ABORT":
                    flow_state["status"] = "failed"
                    flow_state["auto_fix_round_count"] = 0
                    self._write_flow_state(flow_dir_path, flow_state)
                    trace_store.append_event(flow_id, phase=phase, event_type="flow.aborted", payload=dict(decision or {}))
                    self._emit_ui_event(
                        kind="run_failed",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        message=str(flow_state.get("last_completion_summary") or "flow aborted"),
                        payload=dict(decision or {}),
                        hook_name="on_run_finished",
                    )
                    return 1
                if self._should_pause_for_operator(flow_state, decision=dict(decision or {})):
                    return self._pause_for_operator(
                        flow_dir_path=flow_dir_path,
                        trace_store=trace_store,
                        flow_state=flow_state,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        decision=dict(decision or {}),
                    )
                if flow_state.get("workflow_kind") not in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
                    if self._role_runtime_active(flow_state):
                        flow_state["active_role_id"] = next_role_id
                    flow_state["status"] = "running"
                    self._write_flow_state(flow_dir_path, flow_state)
                    continue

                next_phase = str(next_phase_for_followup or phase).strip().lower()
                if next_phase == DONE_PHASE:
                    flow_state["status"] = "completed"
                    flow_state["auto_fix_round_count"] = 0
                    self._write_flow_state(flow_dir_path, flow_state)
                    trace_store.append_event(flow_id, phase=phase, event_type="flow.completed", payload=dict(decision or {}))
                    self._emit_ui_event(
                        kind="run_completed",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=phase,
                        attempt_no=attempt_no,
                        message=str(flow_state.get("last_completion_summary") or "flow completed"),
                        payload=dict(decision or {}),
                        hook_name="on_run_finished",
                    )
                    return 0
                if next_phase != phase:
                    _append_phase_snapshot(flow_state, phase=phase, attempt_no=attempt_no, reason=f"phase_transition:{phase}->{next_phase}")
                    flow_state["current_phase"] = next_phase
                    flow_state["phase_attempt_count"] = 0
                    flow_state["active_role_id"] = next_role_id
                    trace_store.append_event(flow_id, phase=next_phase, event_type="flow.phase.advance", payload={"from": phase, "to": next_phase})
                    self._emit_ui_event(
                        kind="phase_transition",
                        flow_dir_path=flow_dir_path,
                        flow_id=flow_id,
                        phase=next_phase,
                        attempt_no=attempt_no,
                        message=f"{phase} -> {next_phase}",
                        payload={"from": phase, "to": next_phase},
                        hook_name="on_phase_transition",
                    )
                elif flow_state.get("workflow_kind") in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
                    flow_state["active_role_id"] = next_role_id
                    sync_project_phase_attempt_count(flow_state)
                flow_state["status"] = "running"
                self._write_flow_state(flow_dir_path, flow_state)
        except KeyboardInterrupt:
            flow_state["status"] = "interrupted"
            flow_state["auto_fix_round_count"] = 0
            flow_state["last_completion_summary"] = "flow interrupted by operator"
            self._write_flow_state(flow_dir_path, flow_state)
            trace_store.append_event(flow_id, phase=str(flow_state.get("current_phase") or "").strip(), event_type="flow.interrupted", payload={})
            self._emit_ui_event(
                kind="run_interrupted",
                flow_dir_path=flow_dir_path,
                flow_id=flow_id,
                phase=str(flow_state.get("current_phase") or "").strip(),
                attempt_no=safe_int(flow_state.get("attempt_count"), 0),
                message="flow interrupted by operator",
                payload={},
                hook_name="on_interrupt",
            )
            raise
        except Exception as exc:
            flow_state["status"] = "failed"
            flow_state["auto_fix_round_count"] = 0
            flow_state["last_completion_summary"] = f"{type(exc).__name__}: {exc}"
            self._write_flow_state(flow_dir_path, flow_state)
            trace_store.append_event(
                flow_id,
                phase=str(flow_state.get("current_phase") or "").strip(),
                event_type="flow.error",
                payload={"error_type": type(exc).__name__, "error": str(exc)},
            )
            self._emit_ui_event(
                kind="error",
                flow_dir_path=flow_dir_path,
                flow_id=flow_id,
                phase=str(flow_state.get("current_phase") or "").strip(),
                attempt_no=safe_int(flow_state.get("attempt_count"), 0),
                message=f"{type(exc).__name__}: {exc}",
                payload={"error_type": type(exc).__name__, "error": str(exc)},
            )
            self._emit_ui_event(
                kind="run_failed",
                flow_dir_path=flow_dir_path,
                flow_id=flow_id,
                phase=str(flow_state.get("current_phase") or "").strip(),
                attempt_no=safe_int(flow_state.get("attempt_count"), 0),
                message=f"{type(exc).__name__}: {exc}",
                payload={"error_type": type(exc).__name__, "error": str(exc)},
                hook_name="on_run_finished",
            )
            raise
        finally:
            final_status = str(flow_state.get("status") or "").strip() or "failed"
            final_phase = str(flow_state.get("current_phase") or "").strip() or _default_phase(str(flow_state.get("workflow_kind") or ""))
            final_note = str(flow_state.get("last_completion_summary") or flow_state.get("pending_codex_prompt") or "").strip()
            state_store.write_run_state(run_id=flow_id, state=final_status, phase=final_phase, pid=0, note=final_note)
            state_store.write_watchdog_state(state=final_status or "stopped", pid=0, note=final_note)
            state_store.clear_pid()
            state_store.release_lock()

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
            "saved_at": now_text(),
            "attempt_no": attempt_no,
            "phase": phase,
            "codex_prompt": codex_prompt,
            "codex_receipt": _serialize_receipt(codex_receipt),
            "cursor_receipt": _serialize_receipt(cursor_receipt),
            "decision": dict(decision or {}),
        }
        draft_path = state_store.drafts_dir() / f"attempt_{attempt_no:04d}.json"
        write_json_atomic(draft_path, payload)
