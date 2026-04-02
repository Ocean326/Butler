from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from butler_main.agents_os.state import FileRuntimeStateStore, FileTraceStore
from butler_main.chat.pathing import resolve_butler_root

from .constants import (
    DEFAULT_CATALOG_FLOW_ID,
    DEFAULT_LAUNCH_MODE,
    DEFAULT_PROJECT_MAX_RUNTIME_SECONDS,
    EXECUTION_MODE_COMPLEX,
    EXECUTION_MODE_MEDIUM,
    EXECUTION_MODE_SIMPLE,
    FLOW_ASSET_HOME_REL,
    FLOW_AUDIT_LOG_REL,
    FLOW_BUNDLE_HOME_REL,
    FLOW_BUILTIN_HOME_REL,
    FLOW_CODEX_HOME_DIRNAME,
    FLOW_CODEX_HOME_SYNC_FILES,
    FLOW_INSTANCE_HOME_REL,
    FLOW_RUN_HOME_REL,
    FLOW_TEMPLATE_HOME_REL,
    ROLE_PACK_CODING_FLOW,
    SESSION_STRATEGY_PER_ACTIVATION,
    SESSION_STRATEGY_ROLE_BOUND,
    SESSION_STRATEGY_SHARED,
)
from .flow_definition import default_phase_plan, first_phase_id
from .version import BUTLER_FLOW_VERSION


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid4().hex[:6]}")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def flow_asset_root(workspace: str | Path) -> Path:
    return resolve_butler_root(workspace) / FLOW_ASSET_HOME_REL


def builtin_asset_root(workspace: str | Path) -> Path:
    return resolve_butler_root(workspace) / FLOW_BUILTIN_HOME_REL


def template_asset_root(workspace: str | Path) -> Path:
    return resolve_butler_root(workspace) / FLOW_TEMPLATE_HOME_REL


def instance_asset_root(workspace: str | Path) -> Path:
    return resolve_butler_root(workspace) / FLOW_INSTANCE_HOME_REL


def flow_asset_audit_path(workspace: str | Path) -> Path:
    return resolve_butler_root(workspace) / FLOW_AUDIT_LOG_REL


def flow_bundle_root(workspace: str | Path) -> Path:
    return resolve_butler_root(workspace) / FLOW_BUNDLE_HOME_REL


def builtin_bundle_root(workspace: str | Path) -> Path:
    return flow_bundle_root(workspace) / "builtin"


def template_bundle_root(workspace: str | Path) -> Path:
    return flow_bundle_root(workspace) / "templates"


def asset_bundle_root(workspace: str | Path, *, asset_kind: str, asset_id: str) -> Path:
    normalized_kind = str(asset_kind or "").strip().lower()
    normalized_id = str(asset_id or "").strip()
    if normalized_kind == "builtin":
        return builtin_bundle_root(workspace) / normalized_id
    if normalized_kind == "template":
        return template_bundle_root(workspace) / normalized_id
    return Path("")


def asset_bundle_manifest(*, asset_kind: str, asset_id: str) -> dict[str, Any]:
    normalized_kind = str(asset_kind or "").strip().lower()
    normalized_id = str(asset_id or "").strip()
    if normalized_kind not in {"builtin", "template"} or not normalized_id:
        return {}
    bundle_root = Path("bundles") / ("builtin" if normalized_kind == "builtin" else "templates") / normalized_id
    return {
        "bundle_root": str(bundle_root),
        "manager_ref": str(bundle_root / "manager.md"),
        "supervisor_ref": str(bundle_root / "supervisor.md"),
        "sources_ref": str(bundle_root / "sources.json"),
        "manager_prompt": "manager.md",
        "supervisor_prompt": "supervisor.md",
        "sources_path": "sources.json",
        "references_root": "references",
        "assets_root": "assets",
        "derived_root": "derived",
        "derived_supervisor_prompt": str(Path("derived") / "supervisor_compiled.md"),
        "derived_supervisor_knowledge": str(bundle_root / "derived" / "supervisor_knowledge.json"),
        "derived": {
            "supervisor_compiled": str(bundle_root / "derived" / "supervisor_knowledge.json"),
        },
    }


def ensure_asset_bundle_files(workspace: str | Path, *, asset_kind: str, asset_id: str, definition: dict[str, Any] | None = None) -> dict[str, Any]:
    root = asset_bundle_root(workspace, asset_kind=asset_kind, asset_id=asset_id)
    if root == Path(""):
        return {}
    root.mkdir(parents=True, exist_ok=True)
    (root / "references").mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(parents=True, exist_ok=True)
    (root / "derived").mkdir(parents=True, exist_ok=True)
    payload = dict(definition or {})
    label = str(payload.get("label") or asset_id).strip() or asset_id
    goal = str(payload.get("goal") or "").strip()
    guard_condition = str(payload.get("guard_condition") or "").strip()
    manager_path = root / "manager.md"
    supervisor_path = root / "supervisor.md"
    sources_path = root / "sources.json"
    derived_path = root / "derived" / "supervisor_knowledge.json"
    if not manager_path.exists():
        manager_path.write_text(
            "\n".join(
                [
                    f"# Manager Notes · {label}",
                    "",
                    f"- asset_kind: {asset_kind}",
                    f"- asset_id: {asset_id}",
                    f"- goal: {goal or '-'}",
                    f"- guard_condition: {guard_condition or '-'}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    if not supervisor_path.exists():
        supervisor_path.write_text(
            "\n".join(
                [
                    f"# Supervisor Notes · {label}",
                    "",
                    f"- Preserve the flow goal: {goal or '-'}",
                    f"- Respect the guard condition: {guard_condition or '-'}",
                    "- Apply shared-asset management constraints before mutating local runtime state.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    if not sources_path.exists():
        write_json_atomic(
            sources_path,
            {
                "asset_kind": asset_kind,
                "asset_id": asset_id,
                "items": [],
                "updated_at": now_text(),
            },
        )
    if not derived_path.exists():
        write_json_atomic(
            derived_path,
            {
                "composition_mode": "handwritten+compiled",
                "knowledge_text": "",
                "updated_at": now_text(),
            },
        )
    return asset_bundle_manifest(asset_kind=asset_kind, asset_id=asset_id)


def legacy_flow_root(workspace: str | Path) -> Path:
    return resolve_butler_root(workspace) / FLOW_RUN_HOME_REL


def legacy_flow_dir(workspace: str | Path, flow_id: str) -> Path:
    return legacy_flow_root(workspace) / str(flow_id or "").strip()


def new_flow_id() -> str:
    return f"flow_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"


def flow_state_path(flow_dir: Path) -> Path:
    return flow_dir / "workflow_state.json"


def legacy_flow_state_path(flow_dir: Path) -> Path:
    return flow_dir / "flow_state.json"


def flow_turns_path(flow_dir: Path) -> Path:
    return flow_dir / "turns.jsonl"


def flow_actions_path(flow_dir: Path) -> Path:
    return flow_dir / "actions.jsonl"


def flow_artifacts_path(flow_dir: Path) -> Path:
    return flow_dir / "artifacts.json"


def flow_events_path(flow_dir: Path) -> Path:
    return flow_dir / "events.jsonl"


def runtime_plan_path(flow_dir: Path) -> Path:
    return flow_dir / "runtime_plan.json"


def strategy_trace_path(flow_dir: Path) -> Path:
    return flow_dir / "strategy_trace.jsonl"


def mutations_path(flow_dir: Path) -> Path:
    return flow_dir / "mutations.jsonl"


def prompt_packets_path(flow_dir: Path) -> Path:
    return flow_dir / "prompt_packets.jsonl"


def flow_definition_path(flow_dir: Path) -> Path:
    return flow_dir / "flow_definition.json"


def role_sessions_path(flow_dir: Path) -> Path:
    return flow_dir / "role_sessions.json"


def handoffs_path(flow_dir: Path) -> Path:
    return flow_dir / "handoffs.jsonl"


def design_session_path(flow_dir: Path) -> Path:
    return flow_dir / "design_session.json"


def design_turns_path(flow_dir: Path) -> Path:
    return flow_dir / "design_turns.jsonl"


def design_draft_path(flow_dir: Path) -> Path:
    return flow_dir / "design_draft.json"


def read_flow_state(flow_dir: Path) -> dict[str, Any]:
    primary = read_json(flow_state_path(flow_dir))
    if primary:
        state = ensure_flow_state_v1(primary)
    else:
        state = ensure_flow_state_v1(read_json(legacy_flow_state_path(flow_dir)))
    if not state:
        return {}
    role_sessions_payload = read_json(role_sessions_path(flow_dir))
    if isinstance(role_sessions_payload.get("items"), list):
        state["role_sessions"] = {
            str(item.get("role_id") or "").strip(): dict(item)
            for item in list(role_sessions_payload.get("items") or [])
            if isinstance(item, dict) and str(item.get("role_id") or "").strip()
        }
    elif isinstance(role_sessions_payload.get("items"), dict):
        state["role_sessions"] = {
            str(role_id or "").strip(): {"role_id": str(role_id or "").strip(), **dict(item or {})}
            for role_id, item in dict(role_sessions_payload.get("items") or {}).items()
            if str(role_id or "").strip()
        }
    return state


def ensure_flow_state_v1(payload: dict[str, Any]) -> dict[str, Any]:
    state = dict(payload or {})
    if not state:
        return {}
    workflow_kind = str(state.get("workflow_kind") or "").strip()
    if not state.get("workflow_id"):
        state["workflow_id"] = str(state.get("flow_id") or "").strip()
    if not isinstance(state.get("phase_history"), list):
        state["phase_history"] = []
    if not isinstance(state.get("trace_refs"), list):
        state["trace_refs"] = []
    if not isinstance(state.get("receipt_refs"), list):
        state["receipt_refs"] = []
    if not state.get("status"):
        state["status"] = "pending"
    if "latest_supervisor_decision" not in state:
        state["latest_supervisor_decision"] = {}
    if "latest_judge_decision" not in state:
        state["latest_judge_decision"] = dict(state.get("last_cursor_decision") or {})
    if "current_turn_id" not in state:
        state["current_turn_id"] = ""
    if "supervisor_thread_id" not in state:
        state["supervisor_thread_id"] = str(state.get("codex_session_id") or "").strip()
    if "primary_executor_session_id" not in state:
        state["primary_executor_session_id"] = str(state.get("codex_session_id") or "").strip()
    if "approval_state" not in state:
        state["approval_state"] = "not_required"
    if "auto_fix_round_count" not in state:
        state["auto_fix_round_count"] = 0
    if "risk_level" not in state:
        state["risk_level"] = "normal"
    if "autonomy_profile" not in state:
        state["autonomy_profile"] = "default"
    if "artifact_index_ref" not in state:
        state["artifact_index_ref"] = "artifacts.json"
    if "last_operator_action" not in state:
        state["last_operator_action"] = {}
    if "latest_applied_operator_action_id" not in state:
        state["latest_applied_operator_action_id"] = ""
    if not isinstance(state.get("queued_operator_updates"), list):
        state["queued_operator_updates"] = []
    if not isinstance(state.get("phase_snapshots"), list):
        state["phase_snapshots"] = []
    if not isinstance(state.get("context_governor"), dict):
        state["context_governor"] = {}
    if "session_epoch" not in state:
        state["session_epoch"] = 0
    if "service_fault_streak" not in state:
        state["service_fault_streak"] = 0
    if not isinstance(state.get("latest_token_usage"), dict):
        state["latest_token_usage"] = {}
    if "max_runtime_seconds" not in state:
        state["max_runtime_seconds"] = (
            DEFAULT_PROJECT_MAX_RUNTIME_SECONDS if workflow_kind in {"project_loop", "managed_flow"} else 0
        )
    if "runtime_started_at" not in state:
        state["runtime_started_at"] = ""
    if "runtime_elapsed_seconds" not in state:
        state["runtime_elapsed_seconds"] = 0
    if "entry_mode" not in state:
        state["entry_mode"] = workflow_kind or "single_goal"
    if "launch_mode" not in state:
        state["launch_mode"] = DEFAULT_LAUNCH_MODE if workflow_kind == "single_goal" else "flow"
    if "catalog_flow_id" not in state:
        state["catalog_flow_id"] = "" if workflow_kind == "single_goal" else DEFAULT_CATALOG_FLOW_ID
    if "phase_plan" not in state or not isinstance(state.get("phase_plan"), list):
        state["phase_plan"] = default_phase_plan(workflow_kind)
    if not state.get("current_phase"):
        state["current_phase"] = first_phase_id(list(state.get("phase_plan") or []), workflow_kind=workflow_kind)
    if "manage_handoff" not in state:
        state["manage_handoff"] = {}
    if not isinstance(state.get("role_guidance"), dict):
        state["role_guidance"] = {}
    execution_mode = str(state.get("execution_mode") or "").strip().lower()
    if execution_mode not in {EXECUTION_MODE_SIMPLE, EXECUTION_MODE_MEDIUM, EXECUTION_MODE_COMPLEX}:
        execution_mode = EXECUTION_MODE_SIMPLE
    state["execution_mode"] = execution_mode
    session_strategy = str(state.get("session_strategy") or "").strip().lower()
    if session_strategy not in {SESSION_STRATEGY_SHARED, SESSION_STRATEGY_ROLE_BOUND, SESSION_STRATEGY_PER_ACTIVATION}:
        if execution_mode == EXECUTION_MODE_MEDIUM:
            session_strategy = SESSION_STRATEGY_ROLE_BOUND
        elif execution_mode == EXECUTION_MODE_COMPLEX:
            session_strategy = SESSION_STRATEGY_PER_ACTIVATION
        else:
            session_strategy = SESSION_STRATEGY_SHARED
    state["session_strategy"] = session_strategy
    if "active_role_id" not in state:
        state["active_role_id"] = ""
    if "active_role_turn_no" not in state:
        state["active_role_turn_no"] = 0
    if "role_pack_id" not in state:
        state["role_pack_id"] = ROLE_PACK_CODING_FLOW
    if not isinstance(state.get("role_sessions"), dict):
        state["role_sessions"] = {}
    else:
        normalized_role_sessions: dict[str, Any] = {}
        for role_id, raw in dict(state.get("role_sessions") or {}).items():
            token = str(role_id or "").strip()
            if not token:
                continue
            item = dict(raw or {})
            item["role_id"] = str(item.get("role_id") or token).strip()
            item["role_kind"] = str(item.get("role_kind") or "stable").strip() or "stable"
            item["base_role_id"] = str(item.get("base_role_id") or "").strip()
            item["role_charter_addendum"] = str(item.get("role_charter_addendum") or "").strip()
            normalized_role_sessions[token] = item
        state["role_sessions"] = normalized_role_sessions
    if not isinstance(state.get("latest_role_handoffs"), dict):
        state["latest_role_handoffs"] = {}
    if not isinstance(state.get("role_turn_counts"), dict):
        state["role_turn_counts"] = {}
    if not isinstance(state.get("latest_mutation"), dict):
        state["latest_mutation"] = {}
    if "flow_version" not in state:
        state["flow_version"] = BUTLER_FLOW_VERSION
    pending_prompt = str(state.get("pending_codex_prompt") or "").strip()
    if pending_prompt and not list(state.get("queued_operator_updates") or []):
        state["queued_operator_updates"] = [
            {
                "update_id": f"legacy_update_{uuid4().hex[:10]}",
                "source": "legacy_pending_codex_prompt",
                "instruction": pending_prompt,
                "status": "planned",
                "created_at": str(state.get("updated_at") or state.get("created_at") or now_text()).strip(),
                "planned_attempt_no": int(safe_int(state.get("attempt_count"), 0)) + 1,
            }
        ]
    return state


def build_flow_root(workspace: str | Path) -> Path:
    return instance_asset_root(workspace)


def flow_dir(workspace: str | Path, flow_id: str) -> Path:
    return build_flow_root(workspace) / str(flow_id or "").strip()


def resolve_flow_dir(workspace: str | Path, flow_id: str) -> Path:
    target = str(flow_id or "").strip()
    primary = flow_dir(workspace, target)
    if flow_state_path(primary).exists() or legacy_flow_state_path(primary).exists():
        return primary
    legacy = legacy_flow_dir(workspace, target)
    if flow_state_path(legacy).exists() or legacy_flow_state_path(legacy).exists():
        return legacy
    return primary


def new_flow_state(
    *,
    workflow_id: str,
    workflow_kind: str,
    workspace_root: str,
    goal: str,
    guard_condition: str,
    max_attempts: int,
    max_phase_attempts: int,
    max_runtime_seconds: int | None = None,
    launch_mode: str = DEFAULT_LAUNCH_MODE,
    catalog_flow_id: str = "",
    codex_session_id: str = "",
    pending_codex_prompt: str = "",
    resume_source: str = "",
) -> dict[str, Any]:
    normalized_kind = str(workflow_kind or "").strip()
    phase_plan = default_phase_plan(normalized_kind)
    current_phase = first_phase_id(phase_plan, workflow_kind=normalized_kind)
    return ensure_flow_state_v1(
        {
        "workflow_id": str(workflow_id or "").strip(),
        "workflow_kind": normalized_kind,
        "launch_mode": str(launch_mode or DEFAULT_LAUNCH_MODE).strip(),
        "catalog_flow_id": str(catalog_flow_id or "").strip(),
        "workspace_root": str(workspace_root or "").strip(),
        "goal": str(goal or "").strip(),
        "guard_condition": str(guard_condition or "").strip(),
        "status": "pending",
        "current_phase": current_phase,
        "attempt_count": 0,
        "phase_attempt_count": 0,
        "max_attempts": safe_int(max_attempts, 0),
        "max_phase_attempts": safe_int(max_phase_attempts, 0),
        "max_runtime_seconds": safe_int(
            max_runtime_seconds,
            DEFAULT_PROJECT_MAX_RUNTIME_SECONDS if normalized_kind in {"project_loop", "managed_flow"} else 0,
        ),
        "codex_session_id": str(codex_session_id or "").strip(),
        "pending_codex_prompt": str(pending_codex_prompt or "").strip(),
        "queued_operator_updates": [],
        "last_cursor_decision": {},
        "last_completion_summary": "",
        "last_codex_receipt": {},
        "last_cursor_receipt": {},
        "current_phase_artifact": {},
        "phase_history": [],
        "phase_snapshots": [],
        "auto_fix_round_count": 0,
        "runtime_started_at": "",
        "runtime_elapsed_seconds": 0,
        "context_governor": {},
        "session_epoch": 0,
        "service_fault_streak": 0,
        "latest_token_usage": {},
        "resume_source": str(resume_source or "").strip(),
        "trace_run_id": str(workflow_id or "").strip(),
        "phase_plan": phase_plan,
        "entry_mode": normalized_kind,
        "manage_handoff": {},
        "role_guidance": {},
        "execution_mode": EXECUTION_MODE_SIMPLE,
        "session_strategy": SESSION_STRATEGY_SHARED,
        "active_role_id": "",
        "active_role_turn_no": 0,
        "role_pack_id": ROLE_PACK_CODING_FLOW,
        "role_sessions": {},
        "latest_role_handoffs": {},
        "role_turn_counts": {},
        "latest_mutation": {},
        "flow_version": BUTLER_FLOW_VERSION,
        "created_at": now_text(),
        "updated_at": now_text(),
        }
    )


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(payload or {}), ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def ensure_flow_sidecars(flow_dir: Path, flow_state: dict[str, Any]) -> None:
    turns = flow_turns_path(flow_dir)
    actions = flow_actions_path(flow_dir)
    artifacts = flow_artifacts_path(flow_dir)
    events = flow_events_path(flow_dir)
    definition = flow_definition_path(flow_dir)
    role_sessions = role_sessions_path(flow_dir)
    handoffs = handoffs_path(flow_dir)
    runtime_plan = runtime_plan_path(flow_dir)
    strategy_trace = strategy_trace_path(flow_dir)
    mutations = mutations_path(flow_dir)
    prompt_packets = prompt_packets_path(flow_dir)
    design_session = design_session_path(flow_dir)
    design_turns = design_turns_path(flow_dir)
    design_draft = design_draft_path(flow_dir)
    turns.parent.mkdir(parents=True, exist_ok=True)
    if not turns.exists():
        turns.write_text("", encoding="utf-8")
    if not actions.exists():
        actions.write_text("", encoding="utf-8")
    if not events.exists():
        events.write_text("", encoding="utf-8")
    if not handoffs.exists():
        handoffs.write_text("", encoding="utf-8")
    if not strategy_trace.exists():
        strategy_trace.write_text("", encoding="utf-8")
    if not mutations.exists():
        mutations.write_text("", encoding="utf-8")
    if not prompt_packets.exists():
        prompt_packets.write_text("", encoding="utf-8")
    if not design_turns.exists():
        design_turns.write_text("", encoding="utf-8")
    if not artifacts.exists():
        write_json_atomic(
            artifacts,
            {
                "flow_id": str(flow_state.get("workflow_id") or "").strip(),
                "items": [],
                "updated_at": now_text(),
            },
        )
    if not definition.exists():
        write_json_atomic(
            definition,
            {
                "definition_id": str(flow_state.get("workflow_id") or "").strip(),
                "flow_id": str(flow_state.get("workflow_id") or "").strip(),
                "workflow_kind": str(flow_state.get("workflow_kind") or "").strip(),
                "entry_mode": str(flow_state.get("entry_mode") or flow_state.get("workflow_kind") or "").strip(),
                "launch_mode": str(flow_state.get("launch_mode") or "").strip(),
                "catalog_flow_id": str(flow_state.get("catalog_flow_id") or "").strip(),
                "goal": str(flow_state.get("goal") or "").strip(),
                "guard_condition": str(flow_state.get("guard_condition") or "").strip(),
                "phase_plan": list(flow_state.get("phase_plan") or []),
                "risk_level": str(flow_state.get("risk_level") or "normal").strip(),
                "autonomy_profile": str(flow_state.get("autonomy_profile") or "default").strip(),
                "manager_handoff": dict(flow_state.get("manage_handoff") or {}),
                "execution_mode": str(flow_state.get("execution_mode") or EXECUTION_MODE_SIMPLE).strip(),
                "session_strategy": str(flow_state.get("session_strategy") or SESSION_STRATEGY_SHARED).strip(),
                "role_pack_id": str(flow_state.get("role_pack_id") or ROLE_PACK_CODING_FLOW).strip(),
                "version": str(flow_state.get("flow_version") or BUTLER_FLOW_VERSION).strip(),
                "created_at": str(flow_state.get("created_at") or now_text()).strip(),
                "updated_at": now_text(),
            },
        )
    if not runtime_plan.exists():
        write_json_atomic(
            runtime_plan,
            {
                "plan_id": f"runtime_plan_{str(flow_state.get('workflow_id') or '').strip()}",
                "flow_id": str(flow_state.get("workflow_id") or "").strip(),
                "workflow_kind": str(flow_state.get("workflow_kind") or "").strip(),
                "phase": str(flow_state.get("current_phase") or "").strip(),
                "active_role_id": str(flow_state.get("active_role_id") or "").strip(),
                "execution_mode": str(flow_state.get("execution_mode") or EXECUTION_MODE_SIMPLE).strip(),
                "session_strategy": str(flow_state.get("session_strategy") or SESSION_STRATEGY_SHARED).strip(),
                "goal": str(flow_state.get("goal") or "").strip(),
                "guard_condition": str(flow_state.get("guard_condition") or "").strip(),
                "risk_level": str(flow_state.get("risk_level") or "normal").strip(),
                "autonomy_profile": str(flow_state.get("autonomy_profile") or "default").strip(),
                "summary": "",
                "flow_board": {},
                "active_turn_task": {},
                "latest_mutation": dict(flow_state.get("latest_mutation") or {}),
                "updated_at": now_text(),
            },
        )
    if not design_session.exists():
        write_json_atomic(
            design_session,
            {
                "flow_id": str(flow_state.get("workflow_id") or "").strip(),
                "designer_session_id": "",
                "design_stage": "proposal",
                "design_status": "drafting",
                "selected_mode": str(flow_state.get("launch_mode") or "").strip(),
                "selected_level": str(flow_state.get("execution_mode") or "").strip(),
                "source_kind": str(flow_state.get("catalog_flow_id") or "").strip(),
                "active_draft_ref": design_draft.name,
                "last_review_summary": "",
                "created_at": str(flow_state.get("created_at") or now_text()).strip(),
                "updated_at": now_text(),
            },
        )
    if not design_draft.exists():
        write_json_atomic(
            design_draft,
            {
                "flow_id": str(flow_state.get("workflow_id") or "").strip(),
                "workflow_kind": str(flow_state.get("workflow_kind") or "").strip(),
                "goal": str(flow_state.get("goal") or "").strip(),
                "guard_condition": str(flow_state.get("guard_condition") or "").strip(),
                "phase_plan": list(flow_state.get("phase_plan") or []),
                "updated_at": now_text(),
            },
        )
    if not role_sessions.exists():
        write_json_atomic(
            role_sessions,
            {
                "flow_id": str(flow_state.get("workflow_id") or "").strip(),
                "items": [
                    {
                        "role_id": str(role_id or "").strip(),
                        "role_kind": str(dict(item or {}).get("role_kind") or "stable").strip() or "stable",
                        **dict(item or {}),
                    }
                    for role_id, item in dict(flow_state.get("role_sessions") or {}).items()
                    if str(role_id or "").strip()
                ],
                "updated_at": now_text(),
            },
        )


def ensure_trace(trace_store: FileTraceStore, *, run_id: str, metadata: dict[str, Any]) -> None:
    if trace_store.load(run_id):
        return
    trace_store.save(
        run_id,
        {
            "run_id": run_id,
            "parent_run_id": "",
            "created_at": now_text(),
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


def system_codex_home() -> Path:
    configured = str(os.environ.get("CODEX_HOME") or "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


def flow_codex_home_dir(flow_dir: Path) -> Path:
    return flow_dir / FLOW_CODEX_HOME_DIRNAME


def copy_codex_home_file(source_path: Path, target_path: Path) -> None:
    if not source_path.is_file():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)


def prepare_flow_codex_home(flow_dir: Path) -> Path:
    source_root = system_codex_home()
    target_root = flow_codex_home_dir(flow_dir)
    target_root.mkdir(parents=True, exist_ok=True)
    for filename in FLOW_CODEX_HOME_SYNC_FILES:
        copy_codex_home_file(source_root / filename, target_root / filename)
    if not (target_root / "config.toml").exists():
        (target_root / "config.toml").write_text("", encoding="utf-8")
    return target_root


__all__ = [
    "FileRuntimeStateStore",
    "FileTraceStore",
    "append_jsonl",
    "build_flow_root",
    "asset_bundle_manifest",
    "ensure_asset_bundle_files",
    "asset_bundle_root",
    "builtin_bundle_root",
    "ensure_flow_sidecars",
    "ensure_flow_state_v1",
    "legacy_flow_state_path",
    "copy_codex_home_file",
    "design_draft_path",
    "design_session_path",
    "design_turns_path",
    "ensure_trace",
    "flow_actions_path",
    "flow_artifacts_path",
    "flow_events_path",
    "flow_definition_path",
    "handoffs_path",
    "flow_codex_home_dir",
    "flow_dir",
    "flow_bundle_root",
    "mutations_path",
    "prompt_packets_path",
    "runtime_plan_path",
    "strategy_trace_path",
    "template_bundle_root",
    "role_sessions_path",
    "flow_turns_path",
    "new_flow_state",
    "flow_state_path",
    "new_flow_id",
    "now_text",
    "prepare_flow_codex_home",
    "read_flow_state",
    "read_json",
    "safe_int",
    "system_codex_home",
    "write_json_atomic",
]
