from __future__ import annotations

from dataclasses import dataclass


DEFAULT_SKILL_COLLECTION = "chat_default"
CONTENT_SHARE_SKILL_COLLECTION = "chat_content_share"
CODEX_SKILL_COLLECTION = "codex_default"
AUTOMATION_SAFE_SKILL_COLLECTION = "automation_safe"


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    category: str
    relative_dir: str
    relative_skill_file: str
    family_id: str = ""
    family_label: str = ""
    family_summary: str = ""
    status: str = "active"
    trigger_examples: tuple[str, ...] = ()
    family_trigger_examples: tuple[str, ...] = ()
    allowed_roles: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    risk_level: str = "unknown"
    automation_safe: bool = False
    requires_skill_read: bool = True
    variant_rank: int = 100


@dataclass(frozen=True)
class SkillFamily:
    family_id: str
    label: str
    summary: str
    category: str
    risk_level: str
    trigger_examples: tuple[str, ...]
    members: tuple[SkillMetadata, ...]


__all__ = [
    "CODEX_SKILL_COLLECTION",
    "CONTENT_SHARE_SKILL_COLLECTION",
    "DEFAULT_SKILL_COLLECTION",
    "AUTOMATION_SAFE_SKILL_COLLECTION",
    "SkillFamily",
    "SkillMetadata",
]
