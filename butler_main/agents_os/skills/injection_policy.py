from __future__ import annotations

from .models import CODEX_SKILL_COLLECTION, CONTENT_SHARE_SKILL_COLLECTION, DEFAULT_SKILL_COLLECTION


def resolve_skill_collection_id(*, recent_mode: str = "default", runtime_cli: str = "") -> str:
    normalized_mode = str(recent_mode or "default").strip().lower() or "default"
    normalized_cli = str(runtime_cli or "").strip().lower()
    if normalized_mode in {"content_share", "share"}:
        return CONTENT_SHARE_SKILL_COLLECTION
    if normalized_cli == "codex":
        return CODEX_SKILL_COLLECTION
    return DEFAULT_SKILL_COLLECTION


__all__ = ["resolve_skill_collection_id"]
