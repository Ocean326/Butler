from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from butler_main.repo_layout import LEGACY_SKILLS_REL, PLATFORM_SKILLS_REL, resolve_repo_path

from .pathing import resolve_butler_root


UPSTREAM_SKILL_CONVERSION_REGISTRY_REL = (
    Path("butler_main") / "sources" / "skills" / "agent" / "skill_manager_agent" / "references" / "upstream_skill_conversion_registry.json"
)
UPSTREAM_SKILL_CONVERSION_REGISTRY_CANONICAL_REL = (
    PLATFORM_SKILLS_REL / "agent" / "skill_manager_agent" / "references" / "upstream_skill_conversion_registry.json"
)
UPSTREAM_SKILL_CONVERSION_REGISTRY_COMPAT_REL = (
    LEGACY_SKILLS_REL / "agent" / "skill_manager_agent" / "references" / "upstream_skill_conversion_registry.json"
)


def upstream_skill_conversion_registry_file(workspace: str | Path | None) -> Path:
    repo_root = resolve_butler_root(workspace)
    return resolve_repo_path(
        repo_root,
        canonical_rel=UPSTREAM_SKILL_CONVERSION_REGISTRY_CANONICAL_REL,
        compat_rel=UPSTREAM_SKILL_CONVERSION_REGISTRY_COMPAT_REL,
        require_existing=True,
    )


def load_upstream_skill_conversion_registry(workspace: str | Path | None) -> dict[str, Any]:
    path = upstream_skill_conversion_registry_file(workspace)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_upstream_skill_conversion_entry(workspace: str | Path | None, candidate_id: str) -> dict[str, Any] | None:
    payload = load_upstream_skill_conversion_registry(workspace)
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        return None
    entry = entries.get(str(candidate_id or "").strip())
    return dict(entry) if isinstance(entry, dict) else None


__all__ = [
    "UPSTREAM_SKILL_CONVERSION_REGISTRY_REL",
    "UPSTREAM_SKILL_CONVERSION_REGISTRY_CANONICAL_REL",
    "UPSTREAM_SKILL_CONVERSION_REGISTRY_COMPAT_REL",
    "load_upstream_skill_conversion_registry",
    "resolve_upstream_skill_conversion_entry",
    "upstream_skill_conversion_registry_file",
]
