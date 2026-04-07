from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from butler_main.butler_flow.app import FlowApp
from butler_main.butler_flow.state import (
    append_jsonl,
    flow_actions_path,
    flow_artifacts_path,
    flow_events_path,
    flow_turns_path,
    handoffs_path,
    now_text,
    read_json,
    resolve_flow_dir,
)

from .dto import (
    FlowDetailDTO,
    ManageCenterDTO,
    RoleRuntimeDTO,
    SupervisorViewDTO,
    WorkflowViewDTO,
    WorkspaceSurfaceDTO,
)
from .queries import (
    build_flow_detail,
    build_flow_summary,
    latest_handoff_summary,
    pending_handoffs,
    recent_handoffs,
    role_chips,
)


def build_manage_center_surface(
    *,
    preflight_payload: dict[str, Any],
    assets_payload: dict[str, Any],
) -> ManageCenterDTO:
    return ManageCenterDTO(
        preflight=dict(preflight_payload or {}),
        assets=dict(assets_payload or {}),
    )


def build_workspace_surface(
    *,
    preflight_payload: dict[str, Any],
    flows_payload: dict[str, Any],
    resolve_status_payload: Callable[[str], dict[str, Any]],
    read_handoffs: Callable[[str, dict[str, Any]], list[dict[str, Any]]],
    limit: int = 10,
) -> WorkspaceSurfaceDTO:
    flows = dict(flows_payload or {})
    rows = list(flows.get("items") or [])
    enriched: list[dict[str, Any]] = []
    max_rows = max(1, int(limit or 10))
    for row in rows[:max_rows]:
        entry = dict(row or {})
        flow_id = str(entry.get("flow_id") or "").strip()
        if not flow_id:
            enriched.append(entry)
            continue
        try:
            status_payload = resolve_status_payload(flow_id)
            handoffs = read_handoffs(flow_id, status_payload)
            summary = build_flow_summary(status_payload=status_payload, handoffs=handoffs).to_dict()
            flow_state = dict(status_payload.get("flow_state") or {})
            entry.update(
                {
                    "task_contract_summary": summary.get("task_contract_summary"),
                    "approval_state": summary.get("approval_state"),
                    "execution_mode": summary.get("execution_mode"),
                    "session_strategy": summary.get("session_strategy"),
                    "active_role_id": summary.get("active_role_id"),
                    "latest_judge_decision": summary.get("latest_judge_decision"),
                    "latest_operator_action": summary.get("latest_operator_action"),
                    "latest_handoff_summary": summary.get("latest_handoff_summary"),
                    "role_pack_id": summary.get("role_pack_id"),
                    "flow_state": flow_state,
                }
            )
        except Exception:
            enriched.append(entry)
            continue
        enriched.append(entry)
    flows["items"] = enriched
    return WorkspaceSurfaceDTO(preflight=dict(preflight_payload or {}), flows=flows)


def handoffs_from_status_payload(status_payload: dict[str, Any]) -> list[dict[str, Any]]:
    flow_dir_value = str(status_payload.get("flow_dir") or "").strip()
    if not flow_dir_value:
        return []
    flow_path = Path(flow_dir_value)
    payload_path = flow_path / "handoffs.jsonl"
    if not payload_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in payload_path.read_text(encoding="utf-8").splitlines():
        text = str(line or "").strip()
        if not text:
            continue
        try:
            decoded = json.loads(text)
        except Exception:
            continue
        if isinstance(decoded, dict):
            rows.append(decoded)
    return rows


def build_single_flow_surface(*, payload: dict[str, Any]) -> dict[str, Any]:
    return build_flow_detail(payload=payload).to_dict()


_TIMELINE_KIND_ORDER = {
    "run_started": 10,
    "supervisor_input": 15,
    "supervisor_output": 18,
    "supervisor_decided": 20,
    "supervisor_decision_applied": 21,
    "operator_action_applied": 30,
    "codex_segment": 40,
    "codex_runtime_event": 50,
    "judge_result": 60,
    "approval_state_changed": 65,
    "artifact_registered": 70,
    "role_handoff_created": 72,
    "role_handoff_consumed": 73,
    "manage_handoff_ready": 74,
    "phase_transition": 80,
    "run_completed": 90,
    "run_failed": 90,
    "run_interrupted": 90,
}
_LANE_BY_KIND = {
    "supervisor_input": "supervisor",
    "supervisor_output": "supervisor",
    "supervisor_decided": "supervisor",
    "supervisor_decision_applied": "supervisor",
    "judge_result": "supervisor",
    "approval_state_changed": "supervisor",
    "operator_action_applied": "supervisor",
    "manage_handoff_ready": "supervisor",
    "role_handoff_created": "workflow",
    "role_handoff_consumed": "workflow",
    "artifact_registered": "workflow",
    "phase_transition": "workflow",
    "codex_segment": "workflow",
    "codex_runtime_event": "workflow",
    "run_started": "system",
    "run_completed": "system",
    "run_failed": "system",
    "run_interrupted": "system",
}
_FAMILY_BY_KIND = {
    "supervisor_input": "input",
    "supervisor_output": "output",
    "supervisor_decided": "decision",
    "supervisor_decision_applied": "decision",
    "judge_result": "decision",
    "approval_state_changed": "approval",
    "operator_action_applied": "action",
    "manage_handoff_ready": "handoff",
    "role_handoff_created": "handoff",
    "role_handoff_consumed": "handoff",
    "artifact_registered": "artifact",
    "phase_transition": "phase",
    "codex_segment": "raw_execution",
    "codex_runtime_event": "raw_execution",
    "run_started": "run",
    "run_completed": "run",
    "run_failed": "run",
    "run_interrupted": "run",
    "warning": "risk",
    "error": "error",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = str(line or "").strip()
        if not text:
            continue
        try:
            decoded = json.loads(text)
        except Exception:
            decoded = {}
        if isinstance(decoded, dict):
            rows.append(decoded)
    return rows


def _new_plain_app() -> FlowApp:
    return FlowApp(
        run_prompt_receipt_fn=lambda *args, **kwargs: None,
        input_fn=lambda prompt: "",
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )


def _normalize_status(status: str) -> str:
    token = str(status or "").strip().lower()
    if token in {"done", "complete"}:
        return "completed"
    return token


def _payload_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _infer_lane(entry: dict[str, Any]) -> str:
    explicit = str(entry.get("lane") or "").strip().lower()
    if explicit:
        return explicit
    kind = str(entry.get("kind") or "").strip()
    lane = _LANE_BY_KIND.get(kind)
    if lane:
        return lane
    payload = _payload_dict(entry.get("payload"))
    if kind in {"warning", "error"} and any(
        key in payload for key in ("approval_state", "latest_supervisor_decision", "latest_operator_action")
    ):
        return "supervisor"
    return "system"


def _infer_family(entry: dict[str, Any]) -> str:
    explicit = str(entry.get("family") or "").strip().lower()
    if explicit:
        return explicit
    kind = str(entry.get("kind") or "").strip()
    family = _FAMILY_BY_KIND.get(kind)
    if family:
        return family
    payload = _payload_dict(entry.get("payload"))
    if "handoff_id" in payload or "from_role_id" in payload or "to_role_id" in payload:
        return "handoff"
    if "artifact_ref" in payload:
        return "artifact"
    if "decision" in payload:
        return "decision"
    return "system"


def _normalize_event(entry: dict[str, Any]) -> dict[str, Any]:
    row = dict(entry or {})
    row["lane"] = _infer_lane(row)
    row["family"] = _infer_family(row)
    if row.get("lane") == "supervisor" and str(row.get("kind") or "").strip() == "codex_segment":
        row["family"] = "output"
    if "title" not in row or not str(row.get("title") or "").strip():
        row["title"] = str(row.get("message") or row.get("kind") or "").strip()
    if "raw_text" not in row or row.get("raw_text") is None:
        row["raw_text"] = ""
    return row


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_optional_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return _read_jsonl(path)


def _format_supervisor_output(decision: dict[str, Any]) -> str:
    payload = dict(decision or {})
    if not payload:
        return ""

    def _add(parts: list[str], label: str, value: Any) -> None:
        token = str(value or "").strip()
        if token:
            parts.append(f"{label}={token}")

    parts: list[str] = []
    _add(parts, "decision", payload.get("decision"))
    _add(parts, "next_action", payload.get("next_action"))
    _add(parts, "turn_kind", payload.get("turn_kind"))
    _add(parts, "active_role", payload.get("active_role_id"))
    _add(parts, "session_mode", payload.get("session_mode"))
    _add(parts, "load_profile", payload.get("load_profile"))
    issue_kind = str(payload.get("issue_kind") or "").strip()
    if issue_kind and issue_kind != "none":
        parts.append(f"issue={issue_kind}")
    followup_kind = str(payload.get("followup_kind") or "").strip()
    if followup_kind and followup_kind != "none":
        parts.append(f"followup={followup_kind}")
    confidence = payload.get("confidence")
    if confidence is not None:
        try:
            parts.append(f"confidence={float(confidence):.2f}")
        except (TypeError, ValueError):
            _add(parts, "confidence", confidence)
    return " | ".join(parts) if parts else json.dumps(payload, ensure_ascii=False)


def _timeline_event(
    *,
    flow_id: str,
    kind: str,
    created_at: str,
    phase: str = "",
    attempt_no: int = 0,
    message: str = "",
    payload: dict[str, Any] | None = None,
    event_id: str = "",
) -> dict[str, Any]:
    return {
        "event_id": str(event_id or f"flow_timeline_evt_{uuid4().hex[:12]}").strip(),
        "kind": str(kind or "").strip(),
        "flow_id": str(flow_id or "").strip(),
        "phase": str(phase or "").strip(),
        "attempt_no": int(attempt_no or 0),
        "created_at": str(created_at or now_text()).strip(),
        "message": str(message or ""),
        "payload": dict(payload or {}),
    }


def _timeline_key(entry: dict[str, Any]) -> str:
    event_id = str(entry.get("event_id") or "").strip()
    if event_id:
        return f"id:{event_id}"
    return "|".join(
        [
            str(entry.get("kind") or "").strip(),
            str(entry.get("created_at") or "").strip(),
            str(entry.get("message") or "").strip(),
            str(entry.get("phase") or "").strip(),
            str(entry.get("attempt_no") or "").strip(),
        ]
    )


def _timeline_semantic_key(entry: dict[str, Any]) -> str:
    payload = _payload_dict(entry.get("payload"))
    identity = (
        str(payload.get("artifact_ref") or "").strip()
        or str(payload.get("handoff_id") or "").strip()
        or str(payload.get("turn_id") or "").strip()
        or str(payload.get("instruction") or "").strip()
        or str(payload.get("summary") or "").strip()
        or str(entry.get("message") or "").strip()
    )
    return "|".join(
        [
            str(entry.get("kind") or "").strip(),
            str(entry.get("phase") or "").strip(),
            identity,
        ]
    )


def _merge_timeline(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    primary_semantic: set[str] = set()
    primary_lanes: set[str] = set()
    for entry in primary:
        row = dict(entry or {})
        key = _timeline_key(row)
        if key in seen:
            continue
        seen.add(key)
        primary_semantic.add(_timeline_semantic_key(row))
        primary_lanes.add(_infer_lane(row))
        merged.append(row)
    for entry in secondary:
        row = dict(entry or {})
        key = _timeline_key(row)
        if key in seen:
            continue
        lane = _infer_lane(row)
        if lane in primary_lanes and lane in {"supervisor", "workflow"}:
            continue
        if _timeline_semantic_key(row) in primary_semantic:
            continue
        seen.add(key)
        merged.append(row)
    merged.sort(
        key=lambda item: (
            str(item.get("created_at") or ""),
            int(item.get("attempt_no") or 0),
            _TIMELINE_KIND_ORDER.get(str(item.get("kind") or "").strip(), 999),
            str(item.get("event_id") or ""),
        )
    )
    return merged


def launcher_snapshot(*, config: str | None) -> dict[str, Any]:
    app = _new_plain_app()
    preflight = app.build_preflight_payload(argparse.Namespace(config=config, json=False))
    flows = app.build_flows_payload(
        argparse.Namespace(config=config, limit=10, json=False, manage="", goal="", guard_condition="", instruction="")
    )
    return {"preflight": preflight, "flows": flows}


def manage_center_payload(*, config: str | None, limit: int = 20) -> dict[str, Any]:
    app = _new_plain_app()
    preflight = app.build_preflight_payload(argparse.Namespace(config=config, json=False))
    assets = app.build_manage_payload(
        argparse.Namespace(config=config, limit=limit, json=False, manage="", goal="", guard_condition="", instruction="")
    )
    rows = list(assets.get("items") or [])
    selected_asset = dict(rows[0] or {}) if rows else {}
    role_guidance = dict(selected_asset.get("role_guidance") or {})
    review_checklist = list(selected_asset.get("review_checklist") or [])
    bundle_manifest = dict(selected_asset.get("bundle_manifest") or {})
    manager_notes = str(role_guidance.get("manager_notes") or "").strip()
    dto = ManageCenterDTO(
        preflight=preflight,
        assets=assets,
        selected_asset=selected_asset,
        role_guidance=role_guidance,
        review_checklist=review_checklist,
        bundle_manifest=bundle_manifest,
        manager_notes=manager_notes,
    )
    return dto.to_dict()


def status_payload(*, config: str | None, flow_id: str) -> dict[str, Any]:
    app = _new_plain_app()
    return app.build_status_payload(
        argparse.Namespace(config=config, flow_id=flow_id, workflow_id="", last=False, json=False)
    )


def _resolve_flow_path(*, status_payload: dict[str, Any], flow_id: str) -> Path:
    flow_dir_value = str(status_payload.get("flow_dir") or "").strip()
    if flow_dir_value:
        flow_path = Path(flow_dir_value)
        if flow_path.exists():
            return flow_path
    return resolve_flow_dir(status_payload.get("workspace_root") or "", flow_id)


def inspect_payload(*, config: str | None, flow_id: str) -> dict[str, Any]:
    status = status_payload(config=config, flow_id=flow_id)
    flow_path = _resolve_flow_path(status_payload=status, flow_id=flow_id)
    return {
        "status": status,
        "turns": _read_jsonl(flow_turns_path(flow_path)),
        "actions": _read_jsonl(flow_actions_path(flow_path)),
        "artifacts": read_json(flow_artifacts_path(flow_path)).get("items") or [],
        "handoffs": _read_jsonl(handoffs_path(flow_path)),
    }


def _synthesized_timeline(*, flow_id: str, inspected: dict[str, Any]) -> list[dict[str, Any]]:
    status = dict(inspected.get("status") or {})
    flow_state = dict(status.get("flow_state") or {})
    turns = list(inspected.get("turns") or [])
    actions = list(inspected.get("actions") or [])
    artifacts = list(inspected.get("artifacts") or [])
    handoffs = list(inspected.get("handoffs") or [])
    timeline: list[dict[str, Any]] = []

    if turns:
        first_turn = dict(turns[0] or {})
        timeline.append(
            _timeline_event(
                flow_id=flow_id,
                kind="run_started",
                created_at=str(first_turn.get("started_at") or flow_state.get("created_at") or now_text()).strip(),
                phase=str(first_turn.get("phase") or flow_state.get("current_phase") or "").strip(),
                attempt_no=int(first_turn.get("attempt_no") or 0),
                message="flow run started",
                payload={"turn_id": str(first_turn.get("turn_id") or "").strip(), "synthetic": True},
            )
        )

    for turn in turns:
        row = dict(turn or {})
        phase = str(row.get("phase") or "").strip()
        attempt_no = int(row.get("attempt_no") or 0)
        supervisor = dict(row.get("supervisor_decision") or {})
        instruction = str(supervisor.get("instruction") or "").strip()
        if instruction:
            timeline.append(
                _timeline_event(
                    flow_id=flow_id,
                    kind="supervisor_input",
                    created_at=str(row.get("started_at") or flow_state.get("updated_at") or now_text()).strip(),
                    phase=phase,
                    attempt_no=attempt_no,
                    message=instruction,
                    payload={"instruction": instruction, "decision": supervisor, "synthetic": True},
                )
            )
        output_summary = _format_supervisor_output(supervisor)
        if output_summary:
            timeline.append(
                _timeline_event(
                    flow_id=flow_id,
                    kind="supervisor_output",
                    created_at=str(row.get("started_at") or flow_state.get("updated_at") or now_text()).strip(),
                    phase=phase,
                    attempt_no=attempt_no,
                    message=output_summary,
                    payload={"summary": output_summary, "decision": supervisor, "synthetic": True},
                )
            )
        if supervisor:
            timeline.append(
                _timeline_event(
                    flow_id=flow_id,
                    kind="supervisor_decided",
                    created_at=str(row.get("started_at") or flow_state.get("updated_at") or now_text()).strip(),
                    phase=phase,
                    attempt_no=attempt_no,
                    message=str(supervisor.get("reason") or "").strip(),
                    payload={**supervisor, "synthetic": True},
                )
            )
        decision = str(row.get("decision") or "").strip()
        if decision:
            timeline.append(
                _timeline_event(
                    flow_id=flow_id,
                    kind="judge_result",
                    created_at=str(row.get("completed_at") or row.get("started_at") or now_text()).strip(),
                    phase=phase,
                    attempt_no=attempt_no,
                    message=decision,
                    payload={
                        "decision": {
                            "decision": decision,
                            "reason": str(row.get("reason") or "").strip(),
                        },
                        "synthetic": True,
                    },
                )
            )

    for action in actions:
        row = dict(action or {})
        timeline.append(
            _timeline_event(
                flow_id=flow_id,
                kind="operator_action_applied",
                created_at=str(row.get("created_at") or flow_state.get("updated_at") or now_text()).strip(),
                phase=str((row.get("after_state") or {}).get("current_phase") or flow_state.get("current_phase") or "").strip(),
                attempt_no=int(flow_state.get("attempt_count") or 0),
                message=str(row.get("result_summary") or row.get("action_type") or "").strip(),
                payload={**row, "synthetic": True},
            )
        )

    for artifact in artifacts:
        row = dict(artifact or {})
        timeline.append(
            _timeline_event(
                flow_id=flow_id,
                kind="artifact_registered",
                created_at=str(row.get("created_at") or flow_state.get("updated_at") or now_text()).strip(),
                phase=str(row.get("phase") or flow_state.get("current_phase") or "").strip(),
                attempt_no=int(row.get("attempt_no") or 0),
                message=str(row.get("artifact_ref") or "").strip(),
                payload={**row, "synthetic": True},
            )
        )

    for handoff in handoffs:
        row = dict(handoff or {})
        status_value = str(row.get("status") or "").strip()
        created_at = str(row.get("created_at") or now_text()).strip()
        kind = "role_handoff_created"
        if status_value == "consumed" and str(row.get("consumed_at") or "").strip():
            kind = "role_handoff_consumed"
            created_at = str(row.get("consumed_at") or created_at).strip()
        timeline.append(
            _timeline_event(
                flow_id=flow_id,
                kind=kind,
                created_at=created_at,
                phase=str(row.get("target_phase") or row.get("source_phase") or flow_state.get("current_phase") or "").strip(),
                attempt_no=int(flow_state.get("attempt_count") or 0),
                message=str(row.get("summary") or row.get("next_action") or "").strip(),
                payload={**row, "synthetic": True},
            )
        )

    final_status = _normalize_status(status.get("effective_status") or flow_state.get("status") or "")
    final_message = str(flow_state.get("last_completion_summary") or "").strip()
    if final_status in {"completed", "failed", "interrupted"}:
        final_kind = {
            "completed": "run_completed",
            "failed": "run_failed",
            "interrupted": "run_interrupted",
        }[final_status]
        timeline.append(
            _timeline_event(
                flow_id=flow_id,
                kind=final_kind,
                created_at=str(flow_state.get("updated_at") or now_text()).strip(),
                phase=str(status.get("effective_phase") or flow_state.get("current_phase") or "").strip(),
                attempt_no=int(flow_state.get("attempt_count") or 0),
                message=final_message or final_status,
                payload={"synthetic": True},
            )
        )

    return _merge_timeline(timeline, [])


def timeline_payload(*, config: str | None, flow_id: str) -> list[dict[str, Any]]:
    inspected = inspect_payload(config=config, flow_id=flow_id)
    flow_path = _resolve_flow_path(status_payload=dict(inspected.get("status") or {}), flow_id=flow_id)
    events_path = flow_events_path(flow_path)
    events = _read_jsonl(events_path)
    synthesized = _synthesized_timeline(flow_id=flow_id, inspected=inspected)
    unified = _merge_timeline(events, synthesized)
    if synthesized and (not events_path.exists() or not events_path.read_text(encoding="utf-8").strip()):
        for row in synthesized:
            append_jsonl(events_path, row)
    return [_normalize_event(row) for row in unified]


def build_role_runtime_payload(*, flow_state: dict[str, Any], handoffs: list[dict[str, Any]]) -> dict[str, Any]:
    role_sessions = dict(flow_state.get("role_sessions") or {})
    chips = role_chips(flow_state=flow_state, handoffs=handoffs)
    roles: list[dict[str, Any]] = []
    for chip in chips:
        role_id = str(chip.get("role_id") or "").strip()
        payload = dict(role_sessions.get(role_id) or {})
        payload["role_id"] = str(payload.get("role_id") or role_id or "").strip()
        payload["state"] = str(chip.get("state") or "").strip()
        payload["is_active"] = bool(chip.get("is_active"))
        roles.append(payload)
    dto = RoleRuntimeDTO(
        active_role_id=str(flow_state.get("active_role_id") or "").strip(),
        role_sessions=role_sessions,
        pending_handoffs=pending_handoffs(handoffs),
        recent_handoffs=recent_handoffs(handoffs),
        latest_handoff_summary=latest_handoff_summary(handoffs),
        latest_role_handoffs=dict(flow_state.get("latest_role_handoffs") or {}),
        role_chips=chips,
        roles=roles,
        execution_mode=str(flow_state.get("execution_mode") or "").strip(),
        session_strategy=str(flow_state.get("session_strategy") or "").strip(),
        role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
    )
    return dto.to_dict()


def _step_history(*, inspected: dict[str, Any]) -> list[dict[str, Any]]:
    status = dict(inspected.get("status") or {})
    flow_state = dict(status.get("flow_state") or {})
    phase_history = list(flow_state.get("phase_history") or [])
    steps: list[dict[str, Any]] = []
    for row in phase_history:
        entry = dict(row or {})
        decision = dict(entry.get("decision") or {})
        phase = str(entry.get("phase") or status.get("effective_phase") or flow_state.get("current_phase") or "").strip()
        steps.append(
            {
                "step_id": f"phase:{len(steps) + 1}:{phase or 'unknown'}",
                "phase": phase,
                "attempt_no": int(entry.get("attempt_no") or 0),
                "decision": str(decision.get("decision") or "").strip(),
                "summary": str(decision.get("completion_summary") or decision.get("reason") or "").strip(),
                "created_at": str(entry.get("at") or "").strip(),
            }
        )
    if steps:
        return steps
    for row in list(inspected.get("turns") or []):
        entry = dict(row or {})
        steps.append(
            {
                "step_id": str(entry.get("turn_id") or f"turn:{len(steps) + 1}").strip(),
                "phase": str(entry.get("phase") or "").strip(),
                "attempt_no": int(entry.get("attempt_no") or 0),
                "decision": str(entry.get("decision") or "").strip(),
                "summary": str(entry.get("reason") or "").strip(),
                "created_at": str(entry.get("completed_at") or entry.get("started_at") or "").strip(),
            }
        )
    return steps


def build_supervisor_view_payload(
    *,
    flow_id: str,
    summary: dict[str, Any],
    flow_state: dict[str, Any],
    timeline: list[dict[str, Any]],
    runtime_plan: dict[str, Any],
) -> dict[str, Any]:
    header = {
        "flow_id": flow_id,
        "workflow_kind": summary.get("workflow_kind"),
        "status": summary.get("effective_status"),
        "phase": summary.get("effective_phase"),
        "goal": summary.get("goal"),
        "guard_condition": summary.get("guard_condition"),
        "active_role_id": summary.get("active_role_id"),
        "approval_state": summary.get("approval_state"),
        "execution_mode": summary.get("execution_mode"),
        "session_strategy": summary.get("session_strategy"),
        "supervisor_thread_id": str(flow_state.get("supervisor_thread_id") or "").strip(),
    }
    supervisor_events = [row for row in timeline if str(row.get("lane") or "").strip() == "supervisor"]
    latest_supervisor = dict(flow_state.get("latest_supervisor_decision") or {})
    pointers = {
        "approval_state": summary.get("approval_state"),
        "pending_codex_prompt": str(flow_state.get("pending_codex_prompt") or "").strip(),
        "queued_operator_updates": list(flow_state.get("queued_operator_updates") or []),
        "latest_supervisor_decision": latest_supervisor,
        "latest_judge_decision": dict(flow_state.get("latest_judge_decision") or flow_state.get("last_cursor_decision") or {}),
        "latest_operator_action": dict(flow_state.get("last_operator_action") or {}),
        "latest_handoff_summary": dict(summary.get("latest_handoff_summary") or {}),
        "max_runtime_seconds": int(flow_state.get("max_runtime_seconds") or 0),
        "runtime_elapsed_seconds": int(flow_state.get("runtime_elapsed_seconds") or 0),
        "latest_token_usage": dict(flow_state.get("latest_token_usage") or {}),
        "context_governor": dict(flow_state.get("context_governor") or {}),
        "risk_level": str(runtime_plan.get("risk_level") or flow_state.get("risk_level") or "").strip(),
        "autonomy_profile": str(runtime_plan.get("autonomy_profile") or flow_state.get("autonomy_profile") or "").strip(),
        "supervisor_session_mode": str(latest_supervisor.get("session_mode") or "").strip(),
        "supervisor_load_profile": str(latest_supervisor.get("load_profile") or "").strip(),
        "latest_mutation": dict(runtime_plan.get("latest_mutation") or flow_state.get("latest_mutation") or {}),
    }
    dto = SupervisorViewDTO(
        header=header,
        events=supervisor_events,
        latest_supervisor_decision=latest_supervisor,
        latest_judge_decision=dict(flow_state.get("latest_judge_decision") or flow_state.get("last_cursor_decision") or {}),
        latest_operator_action=dict(flow_state.get("last_operator_action") or {}),
        latest_handoff_summary=dict(summary.get("latest_handoff_summary") or {}),
        context_governor=dict(flow_state.get("context_governor") or {}),
        latest_token_usage=dict(flow_state.get("latest_token_usage") or {}),
        pointers=pointers,
    )
    return dto.to_dict()


def build_workflow_view_payload(
    *,
    timeline: list[dict[str, Any]],
    runtime_snapshot: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    workflow_events = [row for row in timeline if str(row.get("lane") or "").strip() == "workflow"]
    artifact_refs = [
        str(dict(item or {}).get("artifact_ref") or "").strip()
        for item in artifacts
        if str(dict(item or {}).get("artifact_ref") or "").strip()
    ]
    dto = WorkflowViewDTO(
        events=workflow_events,
        runtime_summary=dict(runtime_snapshot or {}),
        artifact_refs=artifact_refs,
    )
    return dto.to_dict()


def _operator_rail_payload_from_inspected(
    *,
    flow_state: dict[str, Any],
    handoffs: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
    role_payload: dict[str, Any],
) -> dict[str, Any]:
    promoted_kinds = {
        "warning",
        "error",
        "phase_transition",
        "role_handoff_created",
        "role_handoff_consumed",
        "manage_handoff_ready",
    }
    promoted = [row for row in timeline if str(row.get("kind") or "").strip() in promoted_kinds]
    return {
        "approval_state": str(flow_state.get("approval_state") or "").strip() or "not_required",
        "pending_codex_prompt": str(flow_state.get("pending_codex_prompt") or "").strip(),
        "latest_judge_decision": dict(flow_state.get("latest_judge_decision") or {}),
        "latest_operator_action": dict(flow_state.get("last_operator_action") or {}),
        "latest_supervisor_decision": dict(flow_state.get("latest_supervisor_decision") or {}),
        "latest_handoff_summary": latest_handoff_summary(handoffs),
        "manage_handoff": dict(flow_state.get("manage_handoff") or {}),
        "role_strip": role_payload,
        "promoted_events": promoted,
    }


def role_strip_payload(*, config: str | None, flow_id: str) -> dict[str, Any]:
    inspected = inspect_payload(config=config, flow_id=flow_id)
    flow_state = dict(dict(inspected.get("status") or {}).get("flow_state") or {})
    return build_role_runtime_payload(flow_state=flow_state, handoffs=list(inspected.get("handoffs") or []))


def operator_rail_payload(*, config: str | None, flow_id: str) -> dict[str, Any]:
    inspected = inspect_payload(config=config, flow_id=flow_id)
    status = dict(inspected.get("status") or {})
    flow_state = dict(status.get("flow_state") or {})
    handoffs = list(inspected.get("handoffs") or [])
    role_payload = build_role_runtime_payload(flow_state=flow_state, handoffs=handoffs)
    timeline = timeline_payload(config=config, flow_id=flow_id)
    return _operator_rail_payload_from_inspected(
        flow_state=flow_state,
        handoffs=handoffs,
        timeline=timeline,
        role_payload=role_payload,
    )


def _flow_console_payload_from_inspected(
    *,
    flow_id: str,
    summary: dict[str, Any],
    step_history: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "flow_id": flow_id,
        "summary": summary,
        "recent_steps": step_history[-3:] if step_history else [],
        "step_history": step_history,
    }


def flow_console_payload(*, config: str | None, flow_id: str) -> dict[str, Any]:
    inspected = inspect_payload(config=config, flow_id=flow_id)
    summary = build_flow_summary(
        status_payload=dict(inspected.get("status") or {}),
        handoffs=list(inspected.get("handoffs") or []),
    ).to_dict()
    step_history = _step_history(inspected=inspected)
    return _flow_console_payload_from_inspected(
        flow_id=flow_id,
        summary=summary,
        step_history=step_history,
    )


def _detail_payload_from_inspected(
    *,
    flow_id: str,
    status: dict[str, Any],
    flow_state: dict[str, Any],
    inspected: dict[str, Any],
    timeline: list[dict[str, Any]],
    role_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "flow_id": flow_id,
        "status": status,
        "task_contract": dict(status.get("task_contract") or {}),
        "task_contract_summary": dict(status.get("task_contract_summary") or {}),
        "approval": {
            "approval_state": str(flow_state.get("approval_state") or "").strip() or "not_required",
            "pending_codex_prompt": str(flow_state.get("pending_codex_prompt") or "").strip(),
            "latest_supervisor_decision": dict(flow_state.get("latest_supervisor_decision") or {}),
            "latest_operator_action": dict(flow_state.get("last_operator_action") or {}),
        },
        "receipts": {
            "operator_actions": list(inspected.get("actions") or []),
            "turns": list(inspected.get("turns") or []),
        },
        "timeline": timeline,
        "roles": {
            "role_sessions": dict(flow_state.get("role_sessions") or {}),
            "latest_role_handoffs": dict(flow_state.get("latest_role_handoffs") or {}),
            "handoffs": list(inspected.get("handoffs") or []),
        },
        "multi_agent": {
            "active_role_id": str(flow_state.get("active_role_id") or "").strip(),
            "role_chips": list(role_payload.get("role_chips") or []),
            "role_sessions": dict(flow_state.get("role_sessions") or {}),
            "pending_handoffs": list(role_payload.get("pending_handoffs") or []),
            "recent_handoffs": list(role_payload.get("recent_handoffs") or []),
            "latest_handoff_summary": dict(role_payload.get("latest_handoff_summary") or {}),
        },
        "artifacts": list(inspected.get("artifacts") or []),
        "plan": {
            "phase_plan": list(flow_state.get("phase_plan") or []),
            "flow_definition": dict(status.get("flow_definition") or {}),
        },
        "runtime": {
            "runtime_snapshot": dict(status.get("runtime_snapshot") or {}),
            "trace_summary": dict(status.get("trace_summary") or {}),
        },
    }


def detail_payload(*, config: str | None, flow_id: str) -> dict[str, Any]:
    inspected = inspect_payload(config=config, flow_id=flow_id)
    status = dict(inspected.get("status") or {})
    flow_state = dict(status.get("flow_state") or {})
    handoffs = list(inspected.get("handoffs") or [])
    role_payload = build_role_runtime_payload(flow_state=flow_state, handoffs=handoffs)
    timeline = timeline_payload(config=config, flow_id=flow_id)
    return _detail_payload_from_inspected(
        flow_id=flow_id,
        status=status,
        flow_state=flow_state,
        inspected=inspected,
        timeline=timeline,
        role_payload=role_payload,
    )


def workspace_payload(*, config: str | None, limit: int = 10) -> dict[str, Any]:
    snapshot = launcher_snapshot(config=config)
    flows = dict(snapshot.get("flows") or {})
    rows = list(flows.get("items") or [])
    enriched: list[dict[str, Any]] = []
    for row in rows[: max(1, int(limit or 10))]:
        entry = dict(row or {})
        flow_id = str(entry.get("flow_id") or "").strip()
        if not flow_id:
            enriched.append(entry)
            continue
        try:
            status = status_payload(config=config, flow_id=flow_id)
            flow_path = _resolve_flow_path(status_payload=status, flow_id=flow_id)
            handoffs = _read_jsonl(handoffs_path(flow_path))
            summary = build_flow_summary(status_payload=status, handoffs=handoffs).to_dict()
            entry.update(
                {
                    "task_contract_summary": dict(status.get("task_contract_summary") or {}),
                    "approval_state": summary.get("approval_state"),
                    "execution_mode": summary.get("execution_mode"),
                    "session_strategy": summary.get("session_strategy"),
                    "active_role_id": summary.get("active_role_id"),
                    "latest_judge_decision": summary.get("latest_judge_decision"),
                    "latest_operator_action": summary.get("latest_operator_action"),
                    "latest_handoff_summary": summary.get("latest_handoff_summary"),
                    "role_pack_id": summary.get("role_pack_id"),
                    "flow_state": dict(status.get("flow_state") or {}),
                }
            )
        except Exception:
            pass
        enriched.append(entry)
    flows["items"] = enriched
    return {"preflight": snapshot.get("preflight"), "flows": flows}


def _inspector_payload(
    *,
    flow_id: str,
    status: dict[str, Any],
    flow_state: dict[str, Any],
    inspected: dict[str, Any],
    role_payload: dict[str, Any],
) -> dict[str, Any]:
    flow_path = _resolve_flow_path(status_payload=status, flow_id=flow_id)
    return {
        "selected_event": {},
        "roles": role_payload,
        "handoffs": list(inspected.get("handoffs") or []),
        "artifacts": list(inspected.get("artifacts") or []),
        "plan": {
            "phase_plan": list(flow_state.get("phase_plan") or []),
            "flow_definition": dict(status.get("flow_definition") or {}),
        },
        "runtime": {
            "runtime_snapshot": dict(status.get("runtime_snapshot") or {}),
            "trace_summary": dict(status.get("trace_summary") or {}),
            "runtime_plan": _read_optional_json(flow_path / "runtime_plan.json"),
            "strategy_trace": _read_optional_jsonl(flow_path / "strategy_trace.jsonl"),
            "mutations": _read_optional_jsonl(flow_path / "mutations.jsonl"),
            "prompt_packets": _read_optional_jsonl(flow_path / "prompt_packets.jsonl"),
        },
    }


def single_flow_payload(*, config: str | None, flow_id: str) -> dict[str, Any]:
    inspected = inspect_payload(config=config, flow_id=flow_id)
    status = dict(inspected.get("status") or {})
    flow_state = dict(status.get("flow_state") or {})
    handoffs = list(inspected.get("handoffs") or [])
    summary = build_flow_summary(status_payload=status, handoffs=handoffs).to_dict()
    timeline = timeline_payload(config=config, flow_id=flow_id)
    role_payload = build_role_runtime_payload(flow_state=flow_state, handoffs=handoffs)
    step_history = _step_history(inspected=inspected)
    detail_dto = FlowDetailDTO(
        flow_id=flow_id,
        status=status,
        task_contract=dict(status.get("task_contract") or {}),
        task_contract_summary=dict(status.get("task_contract_summary") or {}),
        summary=summary,
        step_history=step_history,
        timeline=timeline,
        turns=list(inspected.get("turns") or []),
        actions=list(inspected.get("actions") or []),
        artifacts=list(inspected.get("artifacts") or []),
        handoffs=handoffs,
        flow_definition=dict(status.get("flow_definition") or {}),
        runtime_snapshot=dict(status.get("runtime_snapshot") or {}),
    ).to_dict()
    inspector = _inspector_payload(
        flow_id=flow_id,
        status=status,
        flow_state=flow_state,
        inspected=inspected,
        role_payload=role_payload,
    )
    supervisor_view = build_supervisor_view_payload(
        flow_id=flow_id,
        summary=summary,
        flow_state=flow_state,
        timeline=timeline,
        runtime_plan=dict(dict(inspector.get("runtime") or {}).get("runtime_plan") or {}),
    )
    workflow_view = build_workflow_view_payload(
        timeline=timeline,
        runtime_snapshot=dict(status.get("runtime_snapshot") or {}),
        artifacts=list(inspected.get("artifacts") or []),
    )
    operator_rail = _operator_rail_payload_from_inspected(
        flow_state=flow_state,
        handoffs=handoffs,
        timeline=timeline,
        role_payload=role_payload,
    )
    flow_console = _flow_console_payload_from_inspected(
        flow_id=flow_id,
        summary=summary,
        step_history=step_history,
    )
    detail = _detail_payload_from_inspected(
        flow_id=flow_id,
        status=status,
        flow_state=flow_state,
        inspected=inspected,
        timeline=timeline,
        role_payload=role_payload,
    )
    return {
        "flow_id": flow_id,
        "status": status,
        **detail_dto,
        "navigator_summary": summary,
        "supervisor_view": supervisor_view,
        "workflow_view": workflow_view,
        "inspector": inspector,
        "role_strip": role_payload,
        "operator_rail": operator_rail,
        "flow_console": flow_console,
        "surface": {
            "summary": summary,
            "detail": detail,
            "supervisor": supervisor_view,
            "workflow": workflow_view,
            "inspector": inspector,
            "role_strip": role_payload,
            "operator_rail": operator_rail,
            "flow_console": flow_console,
        },
    }


def artifacts_payload(*, config: str | None, flow_id: str) -> list[dict[str, Any]]:
    inspected = inspect_payload(config=config, flow_id=flow_id)
    return list(inspected.get("artifacts") or [])
