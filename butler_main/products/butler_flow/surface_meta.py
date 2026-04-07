from __future__ import annotations

from typing import Any


_SURFACE_PROJECTIONS: dict[str, dict[str, Any]] = {
    "workspace": {
        "surface_id": "workspace",
        "canonical_surface": "mission_index",
        "projection_kind": "mission_index",
        "display_title": "Mission Index",
        "legacy_aliases": ["workspace", "history"],
        "truth_basis": ["task_contract.json", "receipts.jsonl", "recovery_cursor.json"],
    },
    "manage_center": {
        "surface_id": "manage_center",
        "canonical_surface": "contract_studio",
        "projection_kind": "contract_studio",
        "display_title": "Contract Studio",
        "legacy_aliases": ["manage_center", "manage", "flows", "list"],
        "truth_basis": ["task_contract.json", "receipts.jsonl", "flow_definition.json"],
    },
    "single_flow": {
        "surface_id": "single_flow",
        "canonical_surface": "run_console",
        "projection_kind": "run_console",
        "display_title": "Run Console",
        "legacy_aliases": ["single_flow", "flow", "inspect", "status"],
        "truth_basis": ["task_contract.json", "receipts.jsonl", "recovery_cursor.json"],
    },
}


def flow_surface_projection(surface_id: str) -> dict[str, Any]:
    payload = dict(_SURFACE_PROJECTIONS.get(str(surface_id or "").strip(), {}))
    if not payload:
        return {}
    payload["title"] = str(payload.get("display_title") or "").strip()
    return payload


def flow_surface_title(surface_id: str, *, fallback: str = "") -> str:
    projection = flow_surface_projection(surface_id)
    return str(projection.get("display_title") or fallback or "").strip()
