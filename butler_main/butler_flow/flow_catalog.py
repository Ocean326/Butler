from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from butler_main.chat.pathing import resolve_butler_root

from .constants import (
    EXECUTION_LEVEL_MEDIUM,
    EXECUTION_LEVEL_SIMPLE,
    FLOW_CATALOG_DIRNAME,
    FREE_CATALOG_FLOW_ID,
    PROJECT_LOOP_CATALOG_FLOW_ID,
)
from .flow_definition import normalize_phase_plan
from .state import builtin_asset_root


def _legacy_catalog_root() -> Path:
    return Path(__file__).with_name(FLOW_CATALOG_DIRNAME)


def _repo_catalog_root() -> Path:
    return Path(__file__).resolve().parents[2] / "butler_main" / "butler_bot_code" / "assets" / "flows" / "builtin"


def _catalog_roots(workspace: str | Path | None = None) -> list[Path]:
    roots: list[Path] = []
    candidates = []
    if workspace is not None:
        candidates.append(builtin_asset_root(workspace))
    else:
        candidates.append(builtin_asset_root(resolve_butler_root(Path.cwd())))
    candidates.extend([_repo_catalog_root(), _legacy_catalog_root()])
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = str(resolved)
        if key in seen or not resolved.exists():
            continue
        seen.add(key)
        roots.append(resolved)
    return roots


def _read_entry(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    payload["flow_id"] = str(payload.get("flow_id") or path.stem).strip() or path.stem
    payload["label"] = str(payload.get("label") or payload["flow_id"]).strip() or payload["flow_id"]
    payload["description"] = str(payload.get("description") or "").strip()
    payload["workflow_kind"] = str(payload.get("workflow_kind") or "").strip()
    payload["default_role_pack"] = str(payload.get("default_role_pack") or "coding_flow").strip() or "coding_flow"
    payload["allowed_execution_modes"] = [
        str(item or "").strip()
        for item in list(payload.get("allowed_execution_modes") or [])
        if str(item or "").strip()
    ] or [EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM]
    payload["phase_plan"] = normalize_phase_plan(
        payload.get("phase_plan") if isinstance(payload.get("phase_plan"), list) else None,
        workflow_kind=str(payload.get("workflow_kind") or "").strip(),
    )
    return payload


def builtin_flow_catalog(workspace: str | Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for root in _catalog_roots(workspace):
        for path in sorted(root.glob("*.json")):
            entry = _read_entry(path)
            flow_id = str(entry.get("flow_id") or "").strip()
            if entry and flow_id and flow_id not in seen_ids:
                rows.append(entry)
                seen_ids.add(flow_id)
    rows.append(
        {
            "flow_id": FREE_CATALOG_FLOW_ID,
            "label": "Free Design",
            "description": "Use the internal flow designer to build a managed flow before execution.",
            "workflow_kind": "managed_flow",
            "phase_plan": [],
            "default_role_pack": "coding_flow",
            "allowed_execution_modes": [EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM],
            "synthetic": True,
        }
    )
    return rows


def catalog_entry(flow_id: str) -> dict[str, Any]:
    target = str(flow_id or "").strip() or PROJECT_LOOP_CATALOG_FLOW_ID
    for entry in builtin_flow_catalog():
        if str(entry.get("flow_id") or "").strip() == target:
            return dict(entry)
    return {}


__all__ = ["builtin_flow_catalog", "catalog_entry"]
