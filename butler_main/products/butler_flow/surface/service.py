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
    list_manage_sessions,
    manage_draft_file,
    manage_pending_action_file,
    manage_session_file,
    manage_turns_file,
    now_text,
    read_json,
    read_manage_draft,
    read_manage_pending_action,
    read_manage_session,
    read_manage_turns,
    resolve_flow_dir,
)

from .dto import (
    AgentFocusDTO,
    FlowDetailDTO,
    ManageCenterDTO,
    ManagerThreadDTO,
    RoleRuntimeDTO,
    SupervisorViewDTO,
    SupervisorThreadDTO,
    TemplateTeamDTO,
    ThreadBlockDTO,
    ThreadHomeDTO,
    ThreadSummaryDTO,
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


def _compact_text(value: Any, *, fallback: str = "—", limit: int = 220) -> str:
    if isinstance(value, dict):
        for key in ("summary", "label", "title", "reason", "message", "goal", "guard_condition"):
            token = str(value.get(key) or "").strip()
            if token:
                value = token
                break
        else:
            value = json.dumps(value, ensure_ascii=False)
    elif isinstance(value, list):
        parts = [str(item or "").strip() for item in value if str(item or "").strip()]
        value = " / ".join(parts)
    text = str(value or "").strip()
    if not text:
        return fallback
    return text if len(text) <= limit else f"{text[: max(0, limit - 1)].rstrip()}…"


def _block(
    *,
    block_id: str,
    kind: str,
    title: str,
    summary: str,
    created_at: str = "",
    status: str = "",
    expanded_by_default: bool = False,
    payload: dict[str, Any] | None = None,
    role_id: str = "",
    phase: str = "",
    action_label: str = "",
    action_target: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return ThreadBlockDTO(
        block_id=block_id,
        kind=kind,
        title=title,
        summary=summary,
        created_at=created_at or now_text(),
        status=status,
        expanded_by_default=expanded_by_default,
        payload=dict(payload or {}),
        role_id=role_id,
        phase=phase,
        action_label=action_label,
        action_target=action_target,
        tags=[str(item or "").strip() for item in list(tags or []) if str(item or "").strip()],
    ).to_dict()


def _parse_manage_target(target: str) -> tuple[str, str]:
    token = str(target or "").strip()
    if not token or token == "new":
        return "instance", ""
    if ":" in token:
        asset_kind, asset_id = token.split(":", 1)
        return str(asset_kind or "instance").strip().lower(), str(asset_id or "").strip()
    return "instance", token


def _draft_title(draft: dict[str, Any], *, fallback: str) -> str:
    return (
        str(draft.get("label") or "").strip()
        or str(draft.get("goal") or "").strip()
        or str(draft.get("summary") or "").strip()
        or fallback
    )


def _thread_summary(
    *,
    thread_id: str,
    thread_kind: str,
    title: str,
    subtitle: str = "",
    status: str = "",
    created_at: str = "",
    updated_at: str = "",
    manager_session_id: str = "",
    flow_id: str = "",
    active_role_id: str = "",
    current_phase: str = "",
    badge: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return ThreadSummaryDTO(
        thread_id=thread_id,
        thread_kind=thread_kind,
        title=title,
        subtitle=subtitle,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        manager_session_id=manager_session_id,
        flow_id=flow_id,
        active_role_id=active_role_id,
        current_phase=current_phase,
        badge=badge,
        tags=[str(item or "").strip() for item in list(tags or []) if str(item or "").strip()],
    ).to_dict()


def _manager_stage_kind(stage: str, *, pending_action: dict[str, Any] | None = None) -> str:
    token = str(stage or "").strip().lower()
    if dict(pending_action or {}):
        return "launch"
    if token in {"brainstorm", "idea", "discover", "discovery"}:
        return "idea"
    if token in {"scope", "requirements", "requirement_alignment"}:
        return "requirements"
    if token in {"delivery", "acceptance", "guard", "delivery_criteria"}:
        return "delivery_criteria"
    if token in {"test", "qa", "verification", "test_standard"}:
        return "test_standard"
    if token in {"team", "team_draft", "supervisor", "supervisor_profile"}:
        return "team_draft"
    if token in {"launch", "commit", "confirm"}:
        return "launch"
    return "opening"


def _manager_turn_block(
    manager_session_id: str,
    turn: dict[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    stage = str(turn.get("manager_stage") or "").strip()
    pending_action = dict(turn.get("pending_action") or {})
    kind = _manager_stage_kind(stage, pending_action=pending_action)
    created_at = str(turn.get("created_at") or now_text()).strip()
    response = str(turn.get("response") or turn.get("error_text") or "").strip()
    draft = dict(turn.get("draft") or {})
    parse_status = str(turn.get("parse_status") or "ok").strip().lower()
    title_map = {
        "opening": "Manager 对话入口",
        "idea": "Idea 对齐",
        "requirements": "Requirements 细化",
        "delivery_criteria": "Delivery 标准",
        "test_standard": "Test 标准",
        "team_draft": "Team / Supervisor 草案",
        "launch": "Launch / 创建",
    }
    tags = [stage] if stage else []
    if parse_status not in {"", "ok"}:
        tags.append(f"parse:{parse_status}")
    action_target = ""
    action_label = ""
    active_target = str(
        pending_action.get("manage_target") or draft.get("manage_target") or turn.get("manage_target") or ""
    ).strip()
    target_kind, target_id = _parse_manage_target(active_target)
    if kind == "launch" and target_kind == "instance" and target_id:
        action_target = f"flow:{target_id}"
        action_label = "Open Supervisor"
    elif kind == "launch" and active_target:
        action_target = active_target
        action_label = "Inspect target"
    return _block(
        block_id=f"manager:{manager_session_id or 'draft'}:{index}",
        kind=kind,
        title=title_map.get(kind, "Manager 更新"),
        summary=_compact_text(response or draft.get("summary") or pending_action.get("preview") or turn.get("instruction")),
        created_at=created_at,
        status="attention" if parse_status not in {"", "ok"} else ("ready" if bool(turn.get("action_ready")) else "active"),
        expanded_by_default=index >= 0,
        payload={
            "instruction": str(turn.get("instruction") or "").strip(),
            "response": response,
            "draft": draft,
            "pending_action": pending_action,
            "parse_status": parse_status or "ok",
            "session_recovery": dict(turn.get("session_recovery") or {}),
        },
        action_label=action_label,
        action_target=action_target,
        tags=tags,
    )


def _manager_starter_blocks() -> list[dict[str, Any]]:
    created_at = now_text()
    rows = [
        ("opening", "Manager 入口", "先对着 Manager 说出想法，我们会按 brainstorm -> requirements -> delivery/test alignment 往前推。"),
        ("idea", "Idea 草案", "这里会收敛目标、场景、用户价值与边界。"),
        ("requirements", "Requirements 对齐", "这里会逐步明确 workflow_kind、phase plan、核心需求和非目标。"),
        ("delivery_criteria", "Delivery 标准", "这里会沉淀 guard condition、完成定义与交付口径。"),
        ("test_standard", "Test 标准", "这里会整理 review checklist、验证范围与验收门槛。"),
        ("team_draft", "Team / Supervisor 设计", "这里会准备 role guidance、supervisor profile 与默认 team 轮廓。"),
        ("launch", "Create Team + Supervisor", "当确认完成后，Manager 会创建 flow，然后自动切到 Supervisor 流式工作。"),
    ]
    return [
        _block(
            block_id=f"manager:starter:{index}",
            kind=kind,
            title=title,
            summary=summary,
            created_at=created_at,
            status="idle",
            expanded_by_default=index == 0,
            payload={},
        )
        for index, (kind, title, summary) in enumerate(rows, start=1)
    ]


def _manager_summary_from_session(
    manager_session_id: str,
    session: dict[str, Any],
    draft: dict[str, Any],
    pending_action: dict[str, Any],
    turns: list[dict[str, Any]],
) -> dict[str, Any]:
    manage_target = str(
        session.get("active_manage_target")
        or draft.get("manage_target")
        or pending_action.get("manage_target")
        or ""
    ).strip()
    _, flow_id = _parse_manage_target(manage_target)
    last_turn = dict(turns[-1] or {}) if turns else {}
    stage = str(session.get("manager_stage") or last_turn.get("manager_stage") or "").strip()
    updated_at = str(
        session.get("updated_at")
        or last_turn.get("created_at")
        or draft.get("updated_at")
        or ""
    ).strip()
    status = "draft"
    if dict(pending_action or {}):
        status = "ready"
    elif flow_id:
        status = "launched"
    elif turns:
        status = "active"
    tags = [
        item
        for item in [
            stage,
            str(draft.get("workflow_kind") or "").strip(),
            str(draft.get("asset_kind") or "").strip(),
        ]
        if item
    ]
    return _thread_summary(
        thread_id=f"manager:{manager_session_id or 'draft'}",
        thread_kind="manager",
        title=_draft_title(draft, fallback="Manager 管理台"),
        subtitle=_compact_text(
            draft.get("summary")
            or last_turn.get("response")
            or session.get("active_manage_target")
            or "Brainstorm your next flow with Manager."
        ),
        status=status,
        created_at=str((turns[0] or {}).get("created_at") or "").strip() if turns else "",
        updated_at=updated_at,
        manager_session_id=manager_session_id,
        flow_id=flow_id,
        current_phase=str(stage or "").strip(),
        badge=str(session.get("confirmation_scope") or "").strip(),
        tags=tags,
    )


def _flow_summary_as_thread(summary: dict[str, Any], *, manager_session_id: str = "") -> dict[str, Any]:
    flow_id = str(summary.get("flow_id") or "").strip()
    return _thread_summary(
        thread_id=f"flow:{flow_id}",
        thread_kind="supervisor",
        title=str(summary.get("label") or summary.get("goal") or flow_id or "Supervisor").strip() or "Supervisor",
        subtitle=_compact_text(summary.get("goal") or summary.get("guard_condition") or "Supervisor stream"),
        status=str(summary.get("effective_status") or "").strip(),
        updated_at=str(summary.get("updated_at") or "").strip(),
        manager_session_id=manager_session_id,
        flow_id=flow_id,
        active_role_id=str(summary.get("active_role_id") or "").strip(),
        current_phase=str(summary.get("effective_phase") or "").strip(),
        badge=str(summary.get("approval_state") or "").strip(),
        tags=[
            str(summary.get("workflow_kind") or "").strip(),
            str(summary.get("execution_mode") or "").strip(),
            str(summary.get("session_strategy") or "").strip(),
        ],
    )


def _summary_sort_time(summary: dict[str, Any]) -> str:
    return str(summary.get("updated_at") or summary.get("created_at") or "").strip()


def thread_home_payload(*, config: str | None, limit: int = 20) -> dict[str, Any]:
    snapshot = launcher_snapshot(config=config)
    preflight = dict(snapshot.get("preflight") or {})
    workspace_root = str(preflight.get("workspace_root") or "").strip()
    session_rows = list_manage_sessions(workspace_root, limit=max(1, int(limit or 20))) if workspace_root else []
    manager_history: list[dict[str, Any]] = []
    manager_session_by_flow_id: dict[str, str] = {}
    for row in session_rows:
        manager_session_id = str(row.get("manager_session_id") or "").strip()
        session = dict(row.get("session") or {})
        draft = dict(row.get("draft") or {})
        pending_action = dict(row.get("pending_action") or {})
        turns = read_manage_turns(workspace_root, manager_session_id) if workspace_root else []
        summary = _manager_summary_from_session(manager_session_id, session, draft, pending_action, turns)
        flow_id = str(summary.get("flow_id") or "").strip()
        if flow_id:
            manager_session_by_flow_id[flow_id] = manager_session_id
        manager_history.append(summary)

    supervisor_history: list[dict[str, Any]] = []
    flows = list((workspace_payload(config=config, limit=limit).get("flows") or {}).get("items") or [])
    for row in flows:
        flow_id = str(row.get("flow_id") or "").strip()
        if not flow_id:
            continue
        supervisor_history.append(
            _flow_summary_as_thread(
                dict(row or {}),
                manager_session_id=manager_session_by_flow_id.get(flow_id, ""),
            )
        )

    linked_supervisors_by_flow_id = {
        str(item.get("flow_id") or "").strip(): item
        for item in supervisor_history
        if str(item.get("flow_id") or "").strip()
    }
    used_supervisor_flow_ids: set[str] = set()
    bundles: list[tuple[str, list[dict[str, Any]]]] = []

    for summary in manager_history:
        flow_id = str(summary.get("flow_id") or "").strip()
        linked_supervisor = linked_supervisors_by_flow_id.get(flow_id) if flow_id else None
        rows = [summary]
        bundle_time = _summary_sort_time(summary)
        if linked_supervisor:
            rows.append(linked_supervisor)
            used_supervisor_flow_ids.add(flow_id)
            bundle_time = max(bundle_time, _summary_sort_time(linked_supervisor))
        bundles.append((bundle_time, rows))

    for summary in supervisor_history:
        flow_id = str(summary.get("flow_id") or "").strip()
        if flow_id and flow_id in used_supervisor_flow_ids:
            continue
        bundles.append((_summary_sort_time(summary), [summary]))

    bundles.sort(key=lambda item: item[0], reverse=True)
    history = [row for _, rows in bundles for row in rows]

    manage_surface = manage_center_payload(config=config, limit=limit)
    template_rows = []
    for asset in list(dict(manage_surface.get("assets") or {}).get("items") or []):
        asset_id = str(asset.get("asset_id") or asset.get("id") or "").strip()
        if not asset_id:
            continue
        template_rows.append(
            _thread_summary(
                thread_id=f"template:{asset_id}",
                thread_kind="template",
                title=str(asset.get("label") or asset.get("title") or asset_id).strip() or asset_id,
                subtitle=_compact_text(asset.get("description") or asset.get("goal") or asset.get("run_brief") or "Template + agent team"),
                status=str(dict(asset.get("asset_state") or {}).get("status") or asset.get("status") or "active").strip(),
                updated_at=str(asset.get("updated_at") or "").strip(),
                badge=str(asset.get("asset_kind") or "").strip(),
                tags=[
                    str(asset.get("workflow_kind") or "").strip(),
                    str(asset.get("role_pack_id") or "").strip(),
                ],
            )
        )

    latest_manager_summary = dict(manager_history[0] or {}) if manager_history else {}
    manager_entry = {
        "default_manager_session_id": str(latest_manager_summary.get("manager_session_id") or "").strip(),
        "draft_summary": _compact_text(
            dict(session_rows[0].get("draft") or {}).get("summary")
            if session_rows
            else latest_manager_summary.get("subtitle") or "Start a new flow with Manager."
        ),
        "status": str(latest_manager_summary.get("status") or "draft").strip() if latest_manager_summary else "draft",
        "title": str(latest_manager_summary.get("title") or "Manager 管理台").strip()
        if latest_manager_summary
        else "Manager 管理台",
        "total_sessions": len(session_rows),
        "active_flow_id": str(latest_manager_summary.get("flow_id") or "").strip() if latest_manager_summary else "",
        "active_thread_id": str(latest_manager_summary.get("thread_id") or "").strip()
        if latest_manager_summary
        else "",
    }
    return ThreadHomeDTO(
        preflight=preflight,
        manager_entry=manager_entry,
        history=history,
        templates=template_rows,
    ).to_dict()


def manager_thread_payload(*, config: str | None, manager_session_id: str = "") -> dict[str, Any]:
    snapshot = launcher_snapshot(config=config)
    workspace_root = str(dict(snapshot.get("preflight") or {}).get("workspace_root") or "").strip()
    token = str(manager_session_id or "").strip()
    if not workspace_root or not token:
        thread = _thread_summary(
            thread_id="manager:draft",
            thread_kind="manager",
            title="Manager 管理台",
            subtitle="Brainstorm a new idea, align requirements, then let Supervisor take over.",
            status="draft",
            tags=["starter"],
        )
        return ManagerThreadDTO(
            thread=thread,
            manager_session_id="",
            manage_target="new",
            active_manage_target="new",
            manager_stage="opening",
            confirmation_scope="",
            blocks=_manager_starter_blocks(),
            draft={},
            pending_action={},
            latest_response="",
            linked_flow_id="",
        ).to_dict()

    session = read_manage_session(workspace_root, token)
    draft = read_manage_draft(workspace_root, token)
    pending_action = read_manage_pending_action(workspace_root, token)
    turns = read_manage_turns(workspace_root, token)
    summary = _manager_summary_from_session(token, session, draft, pending_action, turns)
    blocks = [_manager_turn_block(token, dict(turn or {}), index=index) for index, turn in enumerate(turns, start=1)]
    if not blocks:
        blocks = _manager_starter_blocks()
    manage_target = str(
        session.get("active_manage_target")
        or draft.get("manage_target")
        or pending_action.get("manage_target")
        or "new"
    ).strip()
    target_kind, target_id = _parse_manage_target(manage_target)
    if pending_action:
        blocks.append(
            _block(
                block_id=f"manager:{token}:launch-ready",
                kind="launch",
                title="Create Team + Supervisor",
                summary=_compact_text(
                    pending_action.get("preview")
                    or pending_action.get("draft_summary")
                    or "Manager is ready to create the flow."
                ),
                created_at=str(session.get("updated_at") or now_text()).strip(),
                status="ready",
                expanded_by_default=True,
                payload=pending_action,
                action_label="Open target" if target_id else "",
                action_target=f"flow:{target_id}" if target_kind == "instance" and target_id else "",
                tags=["pending_action"],
            )
        )
    elif target_kind == "instance" and target_id:
        blocks.append(
            _block(
                block_id=f"manager:{token}:linked-flow",
                kind="launch",
                title="Supervisor 已接管",
                summary=f"Flow `{target_id}` 已创建，接下来进入 Supervisor 流式工作。",
                created_at=str(session.get("updated_at") or now_text()).strip(),
                status="launched",
                expanded_by_default=True,
                payload={"flow_id": target_id},
                action_label="Open Supervisor",
                action_target=f"flow:{target_id}",
                tags=["launched"],
            )
        )
    latest_response = str((turns[-1] or {}).get("response") or "").strip() if turns else ""
    return ManagerThreadDTO(
        thread=summary,
        manager_session_id=token,
        manage_target=manage_target or "new",
        active_manage_target=str(session.get("active_manage_target") or manage_target or "new").strip(),
        manager_stage=str(session.get("manager_stage") or (turns[-1] or {}).get("manager_stage") or "opening").strip(),
        confirmation_scope=str(session.get("confirmation_scope") or "").strip(),
        blocks=blocks,
        draft=draft,
        pending_action=pending_action,
        latest_response=latest_response,
        linked_flow_id=target_id if target_kind == "instance" else "",
    ).to_dict()


def _supervisor_block_kind(event: dict[str, Any]) -> str:
    kind = str(event.get("kind") or "").strip()
    family = str(event.get("family") or "").strip()
    if kind in {"run_started"}:
        return "start"
    if family in {"decision", "output", "input"}:
        return "decision"
    if family == "approval" or kind == "operator_action_applied":
        return "approval"
    if family in {"error", "risk"} or kind in {"warning", "error"}:
        return "risk"
    if family == "handoff":
        return "handoff"
    if family == "artifact":
        return "artifact"
    return "team_activity"


def _supervisor_blocks(flow_payload: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    summary = dict(flow_payload.get("summary") or {})
    flow_id = str(flow_payload.get("flow_id") or summary.get("flow_id") or "").strip()
    blocks.append(
        _block(
            block_id=f"supervisor:{flow_id}:start",
            kind="start",
            title="Supervisor 启动",
            summary=_compact_text(summary.get("goal") or "Supervisor stream started."),
            created_at=str(summary.get("updated_at") or now_text()).strip(),
            status=str(summary.get("effective_status") or "").strip(),
            expanded_by_default=True,
            payload={
                "summary": summary,
                "operator_rail": dict(flow_payload.get("operator_rail") or {}),
            },
            tags=[
                str(summary.get("effective_phase") or "").strip(),
                str(summary.get("active_role_id") or "").strip(),
            ],
        )
    )
    for index, event in enumerate(list(flow_payload.get("timeline") or []), start=1):
        row = dict(event or {})
        payload = dict(row.get("payload") or {})
        role_id = str(
            payload.get("role_id") or payload.get("to_role_id") or payload.get("from_role_id") or ""
        ).strip()
        action_target = f"role:{role_id}" if role_id else ""
        action_label = "Open Agent" if role_id else ""
        blocks.append(
            _block(
                block_id=f"supervisor:{flow_id}:{index}",
                kind=_supervisor_block_kind(row),
                title=str(row.get("title") or row.get("message") or row.get("kind") or "Supervisor update").strip(),
                summary=_compact_text(row.get("message") or payload.get("summary") or payload.get("reason") or row.get("kind")),
                created_at=str(row.get("created_at") or now_text()).strip(),
                status=str(row.get("family") or row.get("lane") or "").strip(),
                expanded_by_default=index <= 4,
                payload=row,
                role_id=role_id,
                phase=str(row.get("phase") or "").strip(),
                action_label=action_label,
                action_target=action_target,
                tags=[
                    str(row.get("lane") or "").strip(),
                    str(row.get("family") or "").strip(),
                ],
            )
        )
    return blocks


def supervisor_thread_payload(*, config: str | None, flow_id: str) -> dict[str, Any]:
    payload = single_flow_payload(config=config, flow_id=flow_id)
    summary = dict(payload.get("summary") or {})
    thread = _flow_summary_as_thread(summary)
    return SupervisorThreadDTO(
        thread=thread,
        flow_id=flow_id,
        summary=summary,
        blocks=_supervisor_blocks(payload),
        role_strip=dict(payload.get("role_strip") or {}),
        operator_rail=dict(payload.get("operator_rail") or {}),
        latest_handoff=dict(summary.get("latest_handoff_summary") or {}),
    ).to_dict()


def agent_focus_payload(*, config: str | None, flow_id: str, role_id: str) -> dict[str, Any]:
    payload = single_flow_payload(config=config, flow_id=flow_id)
    summary = dict(payload.get("summary") or {})
    role_token = str(role_id or "").strip()
    role_strip = dict(payload.get("role_strip") or {})
    roles = list(role_strip.get("roles") or [])
    role_payload = next(
        (dict(item or {}) for item in roles if str(dict(item or {}).get("role_id") or "").strip() == role_token),
        {},
    )
    handoffs = [
        dict(item or {})
        for item in list(payload.get("handoffs") or [])
        if role_token
        and role_token
        in {
            str(dict(item or {}).get("from_role_id") or "").strip(),
            str(dict(item or {}).get("to_role_id") or "").strip(),
        }
    ]
    blocks = [
        _block(
            block_id=f"agent:{flow_id}:{role_token}:brief",
            kind="role_brief",
            title=f"Agent · {role_token or 'unknown'}",
            summary=_compact_text(
                role_payload.get("summary")
                or role_payload.get("state")
                or dict(summary.get("latest_handoff_summary") or {}).get("summary")
                or "Focused agent stream."
            ),
            created_at=str(summary.get("updated_at") or now_text()).strip(),
            status=str(role_payload.get("state") or "").strip(),
            expanded_by_default=True,
            payload=role_payload,
            role_id=role_token,
            tags=[str(role_payload.get("session_id") or "").strip()],
        )
    ]
    for index, event in enumerate(list(payload.get("timeline") or []), start=1):
        row = dict(event or {})
        event_payload = dict(row.get("payload") or {})
        related_roles = {
            str(event_payload.get("role_id") or "").strip(),
            str(event_payload.get("from_role_id") or "").strip(),
            str(event_payload.get("to_role_id") or "").strip(),
        }
        if role_token and role_token not in related_roles:
            continue
        kind = "handoff" if _supervisor_block_kind(row) == "handoff" else (
            "artifact" if _supervisor_block_kind(row) == "artifact" else "progress"
        )
        blocks.append(
            _block(
                block_id=f"agent:{flow_id}:{role_token}:{index}",
                kind=kind,
                title=str(row.get("title") or row.get("message") or row.get("kind") or "Agent update").strip(),
                summary=_compact_text(row.get("message") or event_payload.get("summary") or row.get("kind")),
                created_at=str(row.get("created_at") or now_text()).strip(),
                status=str(row.get("family") or "").strip(),
                expanded_by_default=index <= 3,
                payload=row,
                role_id=role_token,
                phase=str(row.get("phase") or "").strip(),
                tags=[
                    str(row.get("family") or "").strip(),
                    str(row.get("phase") or "").strip(),
                ],
            )
        )
    artifacts = list(payload.get("artifacts") or [])
    for index, artifact in enumerate(artifacts, start=1):
        row = dict(artifact or {})
        ref = str(row.get("artifact_ref") or "").strip()
        blocks.append(
            _block(
                block_id=f"agent:{flow_id}:{role_token}:artifact:{index}",
                kind="artifact",
                title="Artifact 输出",
                summary=_compact_text(ref or row.get("title") or row.get("summary")),
                created_at=str(row.get("created_at") or now_text()).strip(),
                status="artifact",
                expanded_by_default=False,
                payload=row,
                role_id=role_token,
                action_label="Open Artifact" if ref else "",
                action_target=f"artifact:{ref}" if ref else "",
                tags=[str(row.get("phase") or "").strip()],
            )
        )
    thread = _thread_summary(
        thread_id=f"agent:{flow_id}:{role_token}",
        thread_kind="agent",
        title=role_token or "Agent",
        subtitle=_compact_text(summary.get("goal") or "Agent focus"),
        status=str(summary.get("effective_status") or "").strip(),
        updated_at=str(summary.get("updated_at") or "").strip(),
        flow_id=flow_id,
        active_role_id=role_token,
        current_phase=str(summary.get("effective_phase") or "").strip(),
        badge=str(role_payload.get("state") or "").strip(),
        tags=[str(summary.get("workflow_kind") or "").strip()],
    )
    return AgentFocusDTO(
        thread=thread,
        flow_id=flow_id,
        role_id=role_token,
        title=f"{role_token or 'Agent'} · focus",
        summary=summary,
        blocks=blocks,
        role=role_payload,
        related_handoffs=handoffs,
        artifacts=artifacts,
    ).to_dict()


def template_team_payload(*, config: str | None, asset_id: str = "") -> dict[str, Any]:
    payload = manage_center_payload(config=config, limit=50)
    assets = list(dict(payload.get("assets") or {}).get("items") or [])
    selected = {}
    token = str(asset_id or "").strip()
    for item in assets:
        item_id = str(dict(item or {}).get("asset_id") or dict(item or {}).get("id") or "").strip()
        if item_id and item_id == token:
            selected = dict(item or {})
            break
    if not selected and assets:
        selected = dict(assets[0] or {})
    selected_id = str(selected.get("asset_id") or selected.get("id") or "").strip()
    role_guidance = dict(selected.get("role_guidance") or payload.get("role_guidance") or {})
    review_checklist = list(selected.get("review_checklist") or payload.get("review_checklist") or [])
    bundle_manifest = dict(selected.get("bundle_manifest") or payload.get("bundle_manifest") or {})
    manager_notes = str(selected.get("run_brief") or payload.get("manager_notes") or "").strip()
    blocks = [
        _block(
            block_id=f"template:{selected_id or 'empty'}:overview",
            kind="overview",
            title="Templates / Team",
            summary=_compact_text(
                selected.get("description")
                or selected.get("goal")
                or "Manage reusable templates and the default agent team around them."
            ),
            created_at=str(selected.get("updated_at") or now_text()).strip(),
            status=str(dict(selected.get("asset_state") or {}).get("status") or "active").strip(),
            expanded_by_default=True,
            payload=selected,
            tags=[str(selected.get("asset_kind") or "").strip()],
        )
    ]
    if selected:
        blocks.append(
            _block(
                block_id=f"template:{selected_id}:team",
                kind="team",
                title="Default Team",
                summary=_compact_text(role_guidance or "No explicit role guidance yet."),
                created_at=str(selected.get("updated_at") or now_text()).strip(),
                status="configured" if role_guidance else "idle",
                expanded_by_default=True,
                payload=role_guidance,
                tags=list(role_guidance.keys())[:4],
            )
        )
        blocks.append(
            _block(
                block_id=f"template:{selected_id}:standards",
                kind="default_standards",
                title="Delivery / Test Defaults",
                summary=_compact_text(review_checklist or manager_notes or "No checklist configured."),
                created_at=str(selected.get("updated_at") or now_text()).strip(),
                status="configured" if review_checklist else "draft",
                expanded_by_default=True,
                payload={
                    "review_checklist": review_checklist,
                    "manager_notes": manager_notes,
                    "bundle_manifest": bundle_manifest,
                },
                tags=["checklist"],
            )
        )
    thread = _thread_summary(
        thread_id=f"template:{selected_id or 'overview'}",
        thread_kind="template",
        title=str(selected.get("label") or selected.get("title") or "Templates").strip() or "Templates",
        subtitle=_compact_text(selected.get("goal") or selected.get("description") or "Template + agent team management"),
        status=str(dict(selected.get("asset_state") or {}).get("status") or "active").strip(),
        updated_at=str(selected.get("updated_at") or "").strip(),
        badge=str(selected.get("asset_kind") or "").strip(),
        tags=[
            str(selected.get("workflow_kind") or "").strip(),
            str(selected.get("role_pack_id") or "").strip(),
        ],
    )
    return TemplateTeamDTO(
        thread=thread,
        asset_id=selected_id,
        blocks=blocks,
        assets=assets,
        selected_asset=selected,
        role_guidance=role_guidance,
        review_checklist=review_checklist,
        bundle_manifest=bundle_manifest,
        manager_notes=manager_notes,
    ).to_dict()


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
