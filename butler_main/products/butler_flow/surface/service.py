from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .dto import ManageCenterDTO, WorkspaceSurfaceDTO
from .queries import build_flow_detail, build_flow_summary


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
    handoffs_path = flow_path / "handoffs.jsonl"
    if not handoffs_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in handoffs_path.read_text(encoding="utf-8").splitlines():
        text = str(line or "").strip()
        if not text:
            continue
        try:
            import json

            decoded = json.loads(text)
        except Exception:
            continue
        if isinstance(decoded, dict):
            rows.append(decoded)
    return rows


def build_single_flow_surface(*, payload: dict[str, Any]) -> dict[str, Any]:
    return build_flow_detail(payload=payload).to_dict()
