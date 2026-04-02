from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .pathing import SKILL_COLLECTIONS_FILE_REL, SKILLS_HOME_REL, SKILLS_SOURCE_HOME_REL, resolve_butler_root


def legacy_skills_root(workspace: str | Path | None) -> Path:
    return resolve_butler_root(workspace) / SKILLS_HOME_REL


def source_skills_root(workspace: str | Path | None) -> Path:
    return resolve_butler_root(workspace) / SKILLS_SOURCE_HOME_REL


def collections_registry_file(workspace: str | Path | None) -> Path:
    return resolve_butler_root(workspace) / SKILL_COLLECTIONS_FILE_REL


def normalize_rel_path(raw_path: str | None) -> str:
    text = str(raw_path or "").strip().replace("\\", "/")
    if text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_skill_collection_registry(workspace: str | Path | None) -> dict[str, Any]:
    path = collections_registry_file(workspace)
    if not path.exists():
        return {}
    payload = _read_json(path)
    collections = payload.get("collections")
    if not isinstance(collections, dict):
        return {}
    return payload


def resolve_collection_skill_dirs(workspace: str | Path | None, collection_id: str) -> list[Path]:
    registry = load_skill_collection_registry(workspace)
    collections = registry.get("collections") if isinstance(registry.get("collections"), dict) else {}
    collection = collections.get(str(collection_id or "").strip()) if isinstance(collections, dict) else None
    if not isinstance(collection, dict):
        return []
    root = resolve_butler_root(workspace)
    entries = collection.get("skills") if isinstance(collection.get("skills"), list) else []
    resolved: list[Path] = []
    seen: set[str] = set()
    for entry in entries:
        raw_path = entry.get("path") if isinstance(entry, dict) else entry
        normalized = normalize_rel_path(raw_path)
        if not normalized:
            continue
        candidate = root / Path(normalized)
        skill_file = candidate if candidate.name.lower() == "skill.md" else candidate / "SKILL.md"
        if not skill_file.exists():
            continue
        skill_dir = skill_file.parent
        key = skill_dir.as_posix().lower()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(skill_dir)
    return resolved


__all__ = [
    "collections_registry_file",
    "legacy_skills_root",
    "load_skill_collection_registry",
    "normalize_rel_path",
    "resolve_collection_skill_dirs",
    "source_skills_root",
]
