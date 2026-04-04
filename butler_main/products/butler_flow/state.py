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
    CONTROL_PACKET_LARGE,
    CONTROL_PACKET_MEDIUM,
    CONTROL_PACKET_SMALL,
    DEFAULT_CATALOG_FLOW_ID,
    DEFAULT_LAUNCH_MODE,
    DEFAULT_PROJECT_MAX_RUNTIME_SECONDS,
    DOCTOR_ROLE_ID,
    EVIDENCE_LEVEL_MINIMAL,
    EVIDENCE_LEVEL_STANDARD,
    EVIDENCE_LEVEL_STRICT,
    EXECUTION_CONTEXT_REPO_BOUND,
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
    GATE_CADENCE_PHASE,
    GATE_CADENCE_RISK_BASED,
    GATE_CADENCE_STRICT,
    ROLE_PACK_CODING_FLOW,
    ROLE_PACK_RESEARCH_FLOW,
    REPO_BINDING_DISABLED,
    REPO_BINDING_EXPLICIT,
    TASK_ARCHETYPE_GENERAL,
    TASK_ARCHETYPE_PRODUCT_ITERATION,
    TASK_ARCHETYPE_REPO_DELIVERY,
    TASK_ARCHETYPE_RESEARCH_WRITING,
    normalize_execution_context,
    SESSION_STRATEGY_PER_ACTIVATION,
    SESSION_STRATEGY_ROLE_BOUND,
    SESSION_STRATEGY_SHARED,
)
from .flow_definition import default_phase_plan, first_phase_id
from .version import BUTLER_FLOW_VERSION


def resolve_flow_workspace_root(workspace: str | Path | None = None) -> Path:
    if isinstance(workspace, Path):
        candidate = workspace
    else:
        token = str(workspace or "").strip()
        candidate = Path(token).expanduser() if token else Path("")
    if str(candidate).strip():
        if candidate.exists() and candidate.is_file():
            return candidate.parent.resolve()
        return candidate.resolve()
    return resolve_butler_root(Path.cwd())


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def normalize_doctor_policy_payload(raw: Any, *, current: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(raw or {}) if isinstance(raw, dict) else {}
    existing = dict(current or {})
    merged = {**existing, **payload}
    enabled = merged.get("enabled")
    if enabled is None:
        return {}
    activation_rules = [
        str(item or "").strip()
        for item in list(merged.get("activation_rules") or [])
        if str(item or "").strip()
    ]
    if not activation_rules:
        activation_rules = [
            "repeated_service_fault",
            "same_resume_failure",
            "session_binding_invalid",
            "supervisor_manual",
        ]
    repair_scope = str(merged.get("repair_scope") or "runtime_assets_first").strip() or "runtime_assets_first"
    framework_bug_action = str(merged.get("framework_bug_action") or "pause").strip() or "pause"
    max_rounds = max(1, safe_int(merged.get("max_rounds_per_episode"), 1))
    return {
        "enabled": bool(enabled),
        "activation_rules": activation_rules,
        "repair_scope": repair_scope,
        "framework_bug_action": framework_bug_action,
        "max_rounds_per_episode": max_rounds,
    }


def default_control_profile(
    *,
    workflow_kind: str = "",
    role_pack_id: str = "",
    execution_mode: str = "",
    execution_context: str = "",
) -> dict[str, Any]:
    normalized_kind = str(workflow_kind or "").strip().lower()
    normalized_role_pack = str(role_pack_id or "").strip().lower()
    normalized_mode = str(execution_mode or "").strip().lower()
    normalized_context = str(execution_context or "").strip().lower()
    task_archetype = TASK_ARCHETYPE_GENERAL
    if normalized_role_pack == ROLE_PACK_RESEARCH_FLOW:
        task_archetype = TASK_ARCHETYPE_RESEARCH_WRITING
    elif normalized_kind in {"project_loop", "managed_flow"}:
        task_archetype = TASK_ARCHETYPE_REPO_DELIVERY
    packet_size = CONTROL_PACKET_SMALL if normalized_kind == "single_goal" else CONTROL_PACKET_MEDIUM
    evidence_level = EVIDENCE_LEVEL_MINIMAL if normalized_kind == "single_goal" else EVIDENCE_LEVEL_STANDARD
    gate_cadence = GATE_CADENCE_RISK_BASED if normalized_kind == "single_goal" else GATE_CADENCE_PHASE
    if normalized_role_pack == ROLE_PACK_RESEARCH_FLOW:
        evidence_level = EVIDENCE_LEVEL_STRICT
        packet_size = CONTROL_PACKET_SMALL if normalized_kind == "single_goal" else CONTROL_PACKET_MEDIUM
        task_archetype = TASK_ARCHETYPE_RESEARCH_WRITING
    if normalized_mode == EXECUTION_MODE_COMPLEX:
        packet_size = CONTROL_PACKET_SMALL
        gate_cadence = GATE_CADENCE_STRICT
    elif normalized_mode == EXECUTION_MODE_MEDIUM and packet_size == CONTROL_PACKET_LARGE:
        packet_size = CONTROL_PACKET_MEDIUM
    repo_binding_policy = REPO_BINDING_DISABLED
    return {
        "task_archetype": task_archetype,
        "packet_size": packet_size,
        "evidence_level": evidence_level,
        "gate_cadence": gate_cadence,
        "repo_binding_policy": repo_binding_policy,
        "repo_contract_paths": [],
        "manager_notes": "",
    }


def normalize_control_profile_payload(
    raw: Any,
    *,
    current: dict[str, Any] | None = None,
    workflow_kind: str = "",
    role_pack_id: str = "",
    execution_mode: str = "",
    execution_context: str = "",
) -> dict[str, Any]:
    base = default_control_profile(
        workflow_kind=workflow_kind,
        role_pack_id=role_pack_id,
        execution_mode=execution_mode,
        execution_context=execution_context,
    )
    payload = dict(current or {})
    if isinstance(raw, dict):
        payload.update(dict(raw))
    if not payload and not base:
        return {}
    merged = {**base, **payload}
    task_archetype = str(merged.get("task_archetype") or base.get("task_archetype") or "").strip().lower()
    if task_archetype not in {
        TASK_ARCHETYPE_GENERAL,
        TASK_ARCHETYPE_REPO_DELIVERY,
        TASK_ARCHETYPE_RESEARCH_WRITING,
        TASK_ARCHETYPE_PRODUCT_ITERATION,
    }:
        task_archetype = str(base.get("task_archetype") or TASK_ARCHETYPE_GENERAL)
    packet_size = str(merged.get("packet_size") or base.get("packet_size") or "").strip().lower()
    if packet_size not in {CONTROL_PACKET_SMALL, CONTROL_PACKET_MEDIUM, CONTROL_PACKET_LARGE}:
        packet_size = str(base.get("packet_size") or CONTROL_PACKET_MEDIUM)
    evidence_level = str(merged.get("evidence_level") or base.get("evidence_level") or "").strip().lower()
    if evidence_level not in {EVIDENCE_LEVEL_MINIMAL, EVIDENCE_LEVEL_STANDARD, EVIDENCE_LEVEL_STRICT}:
        evidence_level = str(base.get("evidence_level") or EVIDENCE_LEVEL_STANDARD)
    gate_cadence = str(merged.get("gate_cadence") or base.get("gate_cadence") or "").strip().lower()
    if gate_cadence not in {GATE_CADENCE_PHASE, GATE_CADENCE_RISK_BASED, GATE_CADENCE_STRICT}:
        gate_cadence = str(base.get("gate_cadence") or GATE_CADENCE_PHASE)
    repo_binding_policy = str(merged.get("repo_binding_policy") or base.get("repo_binding_policy") or "").strip().lower()
    if repo_binding_policy in {"explicit", "explicit_contract"}:
        repo_binding_policy = REPO_BINDING_EXPLICIT
    elif repo_binding_policy in {"disabled", "detached", "off", "inherit_workspace", "inherit"}:
        repo_binding_policy = REPO_BINDING_DISABLED
    if repo_binding_policy not in {REPO_BINDING_DISABLED, REPO_BINDING_EXPLICIT}:
        repo_binding_policy = str(base.get("repo_binding_policy") or REPO_BINDING_DISABLED)
    repo_contract_paths = [
        str(item or "").strip()
        for item in list(merged.get("repo_contract_paths") or [])
        if str(item or "").strip()
    ]
    return {
        "task_archetype": task_archetype,
        "packet_size": packet_size,
        "evidence_level": evidence_level,
        "gate_cadence": gate_cadence,
        "repo_binding_policy": repo_binding_policy,
        "repo_contract_paths": repo_contract_paths,
        "manager_notes": str(merged.get("manager_notes") or "").strip(),
        "force_gate_next_turn": bool(merged.get("force_gate_next_turn")),
        "force_doctor_next_turn": bool(merged.get("force_doctor_next_turn")),
    }


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = str(line or "").strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def flow_asset_root(workspace: str | Path) -> Path:
    return resolve_flow_workspace_root(workspace) / FLOW_ASSET_HOME_REL


def builtin_asset_root(workspace: str | Path) -> Path:
    return resolve_flow_workspace_root(workspace) / FLOW_BUILTIN_HOME_REL


def template_asset_root(workspace: str | Path) -> Path:
    return resolve_flow_workspace_root(workspace) / FLOW_TEMPLATE_HOME_REL


def instance_asset_root(workspace: str | Path) -> Path:
    return resolve_flow_workspace_root(workspace) / FLOW_INSTANCE_HOME_REL


def flow_asset_audit_path(workspace: str | Path) -> Path:
    return resolve_flow_workspace_root(workspace) / FLOW_AUDIT_LOG_REL


def flow_bundle_root(workspace: str | Path) -> Path:
    return resolve_flow_workspace_root(workspace) / FLOW_BUNDLE_HOME_REL


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
    if normalized_kind == "instance":
        return instance_asset_root(workspace) / normalized_id / "bundle"
    return Path("")


def manage_session_root(workspace: str | Path) -> Path:
    return flow_asset_root(workspace) / "manage_sessions"


def manage_session_dir(workspace: str | Path, manager_session_id: str) -> Path:
    token = str(manager_session_id or "").strip()
    if not token:
        return Path("")
    return manage_session_root(workspace) / token


def manage_session_file(workspace: str | Path, manager_session_id: str) -> Path:
    return manage_session_dir(workspace, manager_session_id) / "session.json"


def manage_draft_file(workspace: str | Path, manager_session_id: str) -> Path:
    return manage_session_dir(workspace, manager_session_id) / "draft.json"


def manage_turns_file(workspace: str | Path, manager_session_id: str) -> Path:
    return manage_session_dir(workspace, manager_session_id) / "turns.jsonl"


def manage_pending_action_file(workspace: str | Path, manager_session_id: str) -> Path:
    return manage_session_dir(workspace, manager_session_id) / "pending_action.json"


def asset_bundle_manifest(*, asset_kind: str, asset_id: str) -> dict[str, Any]:
    normalized_kind = str(asset_kind or "").strip().lower()
    normalized_id = str(asset_id or "").strip()
    if normalized_kind not in {"builtin", "template", "instance"} or not normalized_id:
        return {}
    if normalized_kind == "instance":
        bundle_root = Path("bundle")
    else:
        bundle_root = Path("bundles") / ("builtin" if normalized_kind == "builtin" else "templates") / normalized_id
    return {
        "bundle_root": str(bundle_root),
        "manager_ref": str(bundle_root / "manager.md"),
        "supervisor_ref": str(bundle_root / "supervisor.md"),
        "doctor_ref": str(bundle_root / "doctor.md"),
        "doctor_skill_ref": str(bundle_root / "skills" / DOCTOR_ROLE_ID / "SKILL.md"),
        "sources_ref": str(bundle_root / "sources.json"),
        "manager_prompt": "manager.md",
        "supervisor_prompt": "supervisor.md",
        "doctor_prompt": "doctor.md",
        "sources_path": "sources.json",
        "references_root": "references",
        "doctor_references_root": str(Path("references") / DOCTOR_ROLE_ID),
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
    (root / "references" / DOCTOR_ROLE_ID).mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(parents=True, exist_ok=True)
    (root / "derived").mkdir(parents=True, exist_ok=True)
    (root / "skills" / DOCTOR_ROLE_ID).mkdir(parents=True, exist_ok=True)
    payload = dict(definition or {})
    label = str(payload.get("label") or asset_id).strip() or asset_id
    goal = str(payload.get("goal") or "").strip()
    guard_condition = str(payload.get("guard_condition") or "").strip()
    manager_path = root / "manager.md"
    supervisor_path = root / "supervisor.md"
    doctor_path = root / "doctor.md"
    doctor_skill_path = root / "skills" / DOCTOR_ROLE_ID / "SKILL.md"
    sources_path = root / "sources.json"
    derived_path = root / "derived" / "supervisor_knowledge.json"
    if not manager_path.exists():
        manager_path.write_text(
            "\n".join(
                [
                    f"# Manager Notes · {label}",
                    "",
                    "## Asset Identity",
                    f"- asset_kind: {asset_kind}",
                    f"- asset_id: {asset_id}",
                    f"- goal: {goal or '-'}",
                    f"- guard_condition: {guard_condition or '-'}",
                    "",
                    "## Reuse Guidance",
                    "- Default to discussing and refining this asset before creating any concrete flow from it.",
                    "- Prefer template-first: if this asset is being used to shape a new task, settle the reusable template contract before instantiating a pending flow.",
                    "",
                    "## Manager Checklist",
                    "- Clarify what should stay reusable at the template layer and what is specific to the current run.",
                    "- Align `goal`, `guard_condition`, and `phase_plan` before creating or updating a flow instance.",
                    "- Check whether `supervisor.md` also needs to be updated so the runtime instruction matches the newly agreed flow intent.",
                    "- Ask for explicit confirmation before mutating the template or creating a new flow.",
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
    if not doctor_path.exists():
        doctor_path.write_text(
            "\n".join(
                [
                    f"# Doctor Notes · {label}",
                    "",
                    "- You are a temporary recovery specialist for this single flow instance.",
                    "- Repair runtime/session/instance-asset issues before anything else.",
                    "- If you conclude the blocker is a `butler-flow` framework/code bug, do not patch global code from inside the flow.",
                    "- In that case, begin the final reply with `DOCTOR_FRAMEWORK_BUG:` and include `Problem:`, `Evidence:`, and `Fix plan:` sections.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    if not doctor_skill_path.exists():
        doctor_skill_path.write_text(
            "---\n"
            "name: flow-doctor\n"
            "description: Repair the current flow's runtime assets first; if the fault is in butler-flow code, emit diagnosis + fix plan and request pause.\n"
            "---\n\n"
            "# Flow Doctor\n\n"
            "## Recovery order\n\n"
            "1. Validate current flow runtime bindings and local sidecars.\n"
            "2. Repair instance-local assets before suggesting broader action.\n"
            "3. If the fault is a framework bug, do not fake recovery; output `DOCTOR_FRAMEWORK_BUG:` with diagnosis and fix plan.\n\n"
            "## Allowed repairs\n\n"
            "- Clear or reseed invalid role/session bindings.\n"
            "- Repair missing `flow_definition.json` or instance bundle files for the current flow.\n"
            "- Normalize execution/session mode for the current flow when required for safe recovery.\n\n"
            "## Forbidden\n\n"
            "- Do not rewrite global templates, role catalogs, or unrelated repo code from inside the flow.\n",
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


def read_manage_session(workspace: str | Path, manager_session_id: str) -> dict[str, Any]:
    path = manage_session_file(workspace, manager_session_id)
    return read_json(path) if path != Path("") else {}


def write_manage_session(workspace: str | Path, manager_session_id: str, payload: dict[str, Any]) -> None:
    path = manage_session_file(workspace, manager_session_id)
    if path == Path(""):
        return
    write_json_atomic(path, dict(payload or {}))


def read_manage_draft(workspace: str | Path, manager_session_id: str) -> dict[str, Any]:
    path = manage_draft_file(workspace, manager_session_id)
    return read_json(path) if path != Path("") else {}


def write_manage_draft(workspace: str | Path, manager_session_id: str, payload: dict[str, Any]) -> None:
    path = manage_draft_file(workspace, manager_session_id)
    if path == Path(""):
        return
    write_json_atomic(path, dict(payload or {}))


def append_manage_turn(workspace: str | Path, manager_session_id: str, payload: dict[str, Any]) -> None:
    path = manage_turns_file(workspace, manager_session_id)
    if path == Path(""):
        return
    append_jsonl(path, dict(payload or {}))


def read_manage_pending_action(workspace: str | Path, manager_session_id: str) -> dict[str, Any]:
    path = manage_pending_action_file(workspace, manager_session_id)
    return read_json(path) if path != Path("") else {}


def write_manage_pending_action(workspace: str | Path, manager_session_id: str, payload: dict[str, Any]) -> None:
    path = manage_pending_action_file(workspace, manager_session_id)
    if path == Path(""):
        return
    write_json_atomic(path, dict(payload or {}))


def clear_manage_pending_action(workspace: str | Path, manager_session_id: str) -> None:
    path = manage_pending_action_file(workspace, manager_session_id)
    if path == Path("") or not path.exists():
        return
    try:
        path.unlink()
    except Exception:
        pass


def read_manage_turns(workspace: str | Path, manager_session_id: str) -> list[dict[str, Any]]:
    path = manage_turns_file(workspace, manager_session_id)
    return read_jsonl(path) if path != Path("") else []


def list_manage_sessions(workspace: str | Path, *, limit: int = 20) -> list[dict[str, Any]]:
    root = manage_session_root(workspace)
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for session_dir in sorted(root.iterdir(), key=lambda item: item.name, reverse=True):
        if not session_dir.is_dir():
            continue
        manager_session_id = str(session_dir.name or "").strip()
        if not manager_session_id:
            continue
        session = read_manage_session(workspace, manager_session_id)
        draft = read_manage_draft(workspace, manager_session_id)
        pending_action = read_manage_pending_action(workspace, manager_session_id)
        turns = read_manage_turns(workspace, manager_session_id)
        last_turn = dict(turns[-1] or {}) if turns else {}
        updated_at = str(
            session.get("updated_at")
            or last_turn.get("created_at")
            or draft.get("updated_at")
            or ""
        ).strip()
        rows.append(
            {
                "manager_session_id": manager_session_id,
                "session": session,
                "draft": draft,
                "pending_action": pending_action,
                "turn_count": len(turns),
                "last_turn": last_turn,
                "updated_at": updated_at,
            }
        )
    rows.sort(
        key=lambda item: (
            str(item.get("updated_at") or ""),
            str(item.get("manager_session_id") or ""),
        ),
        reverse=True,
    )
    return rows[: max(1, int(limit or 20))]


def _dedupe_text_list(items: Any) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for item in list(items or []):
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
    return rows


def normalize_supervisor_profile_payload(raw: Any, *, current: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(current or {})
    if isinstance(raw, dict):
        payload.update(dict(raw))
    if not payload:
        return {}
    archetype = str(payload.get("archetype") or "").strip()
    primary_posture = str(payload.get("primary_posture") or "").strip()
    quality_bar = str(payload.get("quality_bar") or "").strip()
    risk_bias = str(payload.get("risk_bias") or "").strip()
    review_focus = _dedupe_text_list(payload.get("review_focus") or [])
    done_policy_raw = dict(payload.get("done_policy") or {})
    done_policy = {
        "must_block_on": _dedupe_text_list(done_policy_raw.get("must_block_on") or []),
        "can_defer_with_note": _dedupe_text_list(done_policy_raw.get("can_defer_with_note") or []),
    }
    manager_notes = str(payload.get("manager_notes") or "").strip()
    normalized = {
        "archetype": archetype,
        "primary_posture": primary_posture,
        "quality_bar": quality_bar,
        "risk_bias": risk_bias,
        "review_focus": review_focus,
        "done_policy": done_policy,
        "manager_notes": manager_notes,
    }
    if any(
        [
            archetype,
            primary_posture,
            quality_bar,
            risk_bias,
            review_focus,
            done_policy["must_block_on"],
            done_policy["can_defer_with_note"],
            manager_notes,
        ]
    ):
        return normalized
    return {}


def normalize_source_items(raw: Any, *, current: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in list(raw or current or []):
        if isinstance(item, str):
            payload = {"kind": "note", "label": item, "ref": item, "notes": ""}
        elif isinstance(item, dict):
            payload = {
                "kind": str(item.get("kind") or "reference").strip() or "reference",
                "label": str(item.get("label") or item.get("title") or item.get("ref") or "").strip(),
                "ref": str(item.get("ref") or item.get("path") or item.get("url") or "").strip(),
                "notes": str(item.get("notes") or item.get("summary") or "").strip(),
            }
        else:
            continue
        fingerprint = "|".join([payload["kind"], payload["label"], payload["ref"], payload["notes"]])
        if not payload["label"] and not payload["ref"]:
            continue
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        rows.append(payload)
    return rows


def write_bundle_sources(
    workspace: str | Path,
    *,
    asset_kind: str,
    asset_id: str,
    items: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = asset_bundle_root(workspace, asset_kind=asset_kind, asset_id=asset_id)
    if root == Path(""):
        return {}
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "asset_kind": str(asset_kind or "").strip(),
        "asset_id": str(asset_id or "").strip(),
        "items": list(items or []),
        "updated_at": now_text(),
    }
    if metadata:
        payload.update({key: value for key, value in dict(metadata).items() if key not in {"items"}})
    write_json_atomic(root / "sources.json", payload)
    return payload


def build_supervisor_knowledge_payload(definition: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(definition or {})
    review_checklist = _dedupe_text_list(payload.get("review_checklist") or [])
    supervisor_profile = normalize_supervisor_profile_payload(payload.get("supervisor_profile"), current={})
    control_profile = normalize_control_profile_payload(
        payload.get("control_profile"),
        current={},
        workflow_kind=str(payload.get("workflow_kind") or "").strip(),
        role_pack_id=str(payload.get("role_pack_id") or payload.get("default_role_pack") or "").strip(),
        execution_mode=str(payload.get("execution_mode") or "").strip(),
        execution_context=str(payload.get("execution_context") or "").strip(),
    )
    run_brief = str(payload.get("run_brief") or "").strip()
    source_items = normalize_source_items(payload.get("source_bindings") or payload.get("source_items") or [])
    knowledge_parts: list[str] = []
    if run_brief:
        knowledge_parts.append(f"[run brief]\n{run_brief}")
    if control_profile:
        control_lines = []
        for key in ("task_archetype", "packet_size", "evidence_level", "gate_cadence", "repo_binding_policy"):
            value = str(control_profile.get(key) or "").strip()
            if value:
                control_lines.append(f"- {key}: {value}")
        repo_contract_paths = _dedupe_text_list(control_profile.get("repo_contract_paths") or [])
        if repo_contract_paths:
            control_lines.append(f"- repo_contract_paths: {', '.join(repo_contract_paths)}")
        if control_lines:
            knowledge_parts.append("[control profile]\n" + "\n".join(control_lines))
    if supervisor_profile:
        profile_lines = []
        for key in ("archetype", "primary_posture", "quality_bar", "risk_bias", "manager_notes"):
            value = str(supervisor_profile.get(key) or "").strip()
            if value:
                profile_lines.append(f"- {key}: {value}")
        for key in ("must_block_on", "can_defer_with_note"):
            values = _dedupe_text_list(dict(supervisor_profile.get("done_policy") or {}).get(key) or [])
            if values:
                profile_lines.append(f"- done_policy.{key}: {', '.join(values)}")
        review_focus = _dedupe_text_list(supervisor_profile.get("review_focus") or [])
        if review_focus:
            profile_lines.append(f"- review_focus: {', '.join(review_focus)}")
        if profile_lines:
            knowledge_parts.append("[supervisor profile]\n" + "\n".join(profile_lines))
    if source_items:
        source_lines = []
        for item in source_items[:8]:
            label = str(item.get("label") or item.get("ref") or "").strip()
            detail = str(item.get("notes") or item.get("ref") or "").strip()
            if label and detail and detail != label:
                source_lines.append(f"- {label}: {detail}")
            elif label:
                source_lines.append(f"- {label}")
        if source_lines:
            knowledge_parts.append("[sources]\n" + "\n".join(source_lines))
    if review_checklist:
        knowledge_parts.append("[review checklist]\n" + "\n".join(f"- {item}" for item in review_checklist[:8]))
    return {
        "composition_mode": "handwritten+compiled",
        "knowledge_text": "\n\n".join(part for part in knowledge_parts if part).strip(),
        "control_profile": control_profile,
        "supervisor_profile": supervisor_profile,
        "run_brief": run_brief,
        "source_items": source_items,
        "review_checklist": review_checklist,
        "updated_at": now_text(),
    }


def write_compiled_supervisor_knowledge(
    workspace: str | Path,
    *,
    asset_kind: str,
    asset_id: str,
    definition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = asset_bundle_root(workspace, asset_kind=asset_kind, asset_id=asset_id)
    if root == Path(""):
        return {}
    (root / "derived").mkdir(parents=True, exist_ok=True)
    payload = build_supervisor_knowledge_payload(definition)
    write_json_atomic(root / "derived" / "supervisor_knowledge.json", payload)
    return payload


def legacy_flow_root(workspace: str | Path) -> Path:
    return resolve_flow_workspace_root(workspace) / FLOW_RUN_HOME_REL


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
    state["doctor_policy"] = normalize_doctor_policy_payload(state.get("doctor_policy"), current={})
    state["supervisor_profile"] = normalize_supervisor_profile_payload(
        state.get("supervisor_profile"),
        current={},
    )
    execution_mode = str(state.get("execution_mode") or "").strip().lower()
    if execution_mode not in {EXECUTION_MODE_SIMPLE, EXECUTION_MODE_MEDIUM, EXECUTION_MODE_COMPLEX}:
        execution_mode = (
            EXECUTION_MODE_MEDIUM
            if workflow_kind in {"project_loop", "managed_flow"}
            else EXECUTION_MODE_SIMPLE
        )
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
    state["execution_context"] = normalize_execution_context(
        state.get("execution_context"),
        role_pack_id=str(state.get("role_pack_id") or "").strip(),
        workflow_kind=workflow_kind,
    )
    state["control_profile"] = normalize_control_profile_payload(
        state.get("control_profile"),
        current={},
        workflow_kind=workflow_kind,
        role_pack_id=str(state.get("role_pack_id") or "").strip(),
        execution_mode=execution_mode,
        execution_context=str(state.get("execution_context") or "").strip(),
    )
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
    execution_context: str = "",
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
        "doctor_policy": {},
        "execution_mode": (
            EXECUTION_MODE_MEDIUM
            if normalized_kind in {"project_loop", "managed_flow"}
            else EXECUTION_MODE_SIMPLE
        ),
        "session_strategy": (
            SESSION_STRATEGY_ROLE_BOUND
            if normalized_kind in {"project_loop", "managed_flow"}
            else SESSION_STRATEGY_SHARED
        ),
        "active_role_id": "",
        "active_role_turn_no": 0,
        "role_pack_id": ROLE_PACK_CODING_FLOW,
        "execution_context": str(execution_context or EXECUTION_CONTEXT_REPO_BOUND).strip(),
        "control_profile": default_control_profile(
            workflow_kind=normalized_kind,
            role_pack_id=ROLE_PACK_CODING_FLOW,
            execution_mode=(
                EXECUTION_MODE_MEDIUM
                if normalized_kind in {"project_loop", "managed_flow"}
                else EXECUTION_MODE_SIMPLE
            ),
            execution_context=str(execution_context or EXECUTION_CONTEXT_REPO_BOUND).strip(),
        ),
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
                "control_profile": dict(flow_state.get("control_profile") or {}),
                "supervisor_profile": dict(flow_state.get("supervisor_profile") or {}),
                "execution_mode": str(flow_state.get("execution_mode") or EXECUTION_MODE_SIMPLE).strip(),
                "session_strategy": str(flow_state.get("session_strategy") or SESSION_STRATEGY_SHARED).strip(),
                "role_pack_id": str(flow_state.get("role_pack_id") or ROLE_PACK_CODING_FLOW).strip(),
                "execution_context": str(flow_state.get("execution_context") or "").strip(),
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
                "execution_context": str(flow_state.get("execution_context") or "").strip(),
                "control_profile": dict(flow_state.get("control_profile") or {}),
                "supervisor_profile": dict(flow_state.get("supervisor_profile") or {}),
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
    "append_manage_turn",
    "build_flow_root",
    "build_supervisor_knowledge_payload",
    "clear_manage_pending_action",
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
    "flow_asset_root",
    "handoffs_path",
    "flow_codex_home_dir",
    "flow_dir",
    "flow_bundle_root",
    "manage_draft_file",
    "manage_pending_action_file",
    "manage_session_dir",
    "manage_session_file",
    "manage_session_root",
    "manage_turns_file",
    "mutations_path",
    "normalize_source_items",
    "normalize_supervisor_profile_payload",
    "prompt_packets_path",
    "read_jsonl",
    "read_manage_draft",
    "read_manage_pending_action",
    "read_manage_session",
    "read_manage_turns",
    "runtime_plan_path",
    "strategy_trace_path",
    "template_bundle_root",
    "role_sessions_path",
    "flow_turns_path",
    "new_flow_state",
    "flow_state_path",
    "new_flow_id",
    "now_text",
    "default_control_profile",
    "normalize_control_profile_payload",
    "prepare_flow_codex_home",
    "read_flow_state",
    "read_json",
    "resolve_flow_workspace_root",
    "safe_int",
    "system_codex_home",
    "list_manage_sessions",
    "write_bundle_sources",
    "write_compiled_supervisor_knowledge",
    "write_manage_draft",
    "write_manage_pending_action",
    "write_manage_session",
    "write_json_atomic",
]
