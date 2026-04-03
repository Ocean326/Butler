from __future__ import annotations

import os
from pathlib import Path

from butler_main.repo_layout import (
    LEGACY_CHAT_REL,
    LEGACY_SKILLS_REL,
    PLATFORM_SKILLS_REL,
    PRODUCT_CHAT_REL,
    resolve_repo_path,
    resolve_repo_root,
)

CHAT_HOME_REL = PRODUCT_CHAT_REL
CHAT_DATA_HOME_REL = CHAT_HOME_REL / "data"
CHAT_HOT_DATA_HOME_REL = CHAT_DATA_HOME_REL / "hot"
CHAT_COLD_DATA_HOME_REL = CHAT_DATA_HOME_REL / "cold"
LOCAL_MEMORY_DIR_REL = CHAT_COLD_DATA_HOME_REL / "local_memory"
RECENT_MEMORY_DIR_REL = CHAT_HOT_DATA_HOME_REL / "recent_memory"
SKILLS_HOME_REL = PLATFORM_SKILLS_REL
SKILLS_SOURCE_HOME_REL = PLATFORM_SKILLS_REL
SKILL_COLLECTIONS_FILE_REL = SKILLS_SOURCE_HOME_REL / "collections" / "registry.json"
SKILL_PROMPT_POLICY_FILE_REL = SKILLS_SOURCE_HOME_REL / "collections" / "prompt_policy.json"
COMPANY_HOME_REL = Path("工作区")

BUTLER_SOUL_FILE_REL = LOCAL_MEMORY_DIR_REL / "Butler_SOUL.md"
CURRENT_USER_PROFILE_FILE_REL = LOCAL_MEMORY_DIR_REL / "Current_User_Profile.private.md"
CURRENT_USER_PROFILE_TEMPLATE_FILE_REL = LOCAL_MEMORY_DIR_REL / "Current_User_Profile.template.md"
SELF_MIND_DIR_REL = LOCAL_MEMORY_DIR_REL / "self_mind"


def prompt_path_text(path: Path) -> str:
    return f"./{path.as_posix()}"


def _normalize_workspace_candidate(workspace: str | Path | None) -> Path:
    if workspace is None:
        return resolve_repo_root(workspace)
    candidate = Path(workspace).resolve()
    if candidate.is_file():
        return resolve_repo_root(candidate)
    if (candidate / "butler_main").exists():
        return candidate
    cwd = Path.cwd().resolve()
    if candidate == cwd:
        return resolve_repo_root(candidate)
    return candidate


def resolve_butler_root(workspace: str | Path | None = None) -> Path:
    return _normalize_workspace_candidate(workspace)


def resolve_chat_home(workspace: str | Path | None = None, *, require_existing: bool = False) -> Path:
    root = resolve_butler_root(workspace)
    return resolve_repo_path(
        root,
        canonical_rel=PRODUCT_CHAT_REL,
        compat_rel=LEGACY_CHAT_REL,
        require_existing=require_existing,
    )


def resolve_skills_home(workspace: str | Path | None = None, *, require_existing: bool = False) -> Path:
    root = resolve_butler_root(workspace)
    return resolve_repo_path(
        root,
        canonical_rel=PLATFORM_SKILLS_REL,
        compat_rel=LEGACY_SKILLS_REL,
        require_existing=require_existing,
    )


def ensure_chat_data_layout(workspace: str | Path | None = None) -> Path:
    root = resolve_butler_root(workspace)
    hot_root = root / CHAT_HOT_DATA_HOME_REL
    cold_root = root / CHAT_COLD_DATA_HOME_REL
    hot_root.mkdir(parents=True, exist_ok=True)
    cold_root.mkdir(parents=True, exist_ok=True)
    (root / RECENT_MEMORY_DIR_REL).mkdir(parents=True, exist_ok=True)
    (root / LOCAL_MEMORY_DIR_REL).mkdir(parents=True, exist_ok=True)
    (root / SELF_MIND_DIR_REL / "cognition").mkdir(parents=True, exist_ok=True)
    return root


__all__ = [
    "BUTLER_SOUL_FILE_REL",
    "CHAT_COLD_DATA_HOME_REL",
    "CHAT_DATA_HOME_REL",
    "CHAT_HOME_REL",
    "CHAT_HOT_DATA_HOME_REL",
    "COMPANY_HOME_REL",
    "CURRENT_USER_PROFILE_FILE_REL",
    "CURRENT_USER_PROFILE_TEMPLATE_FILE_REL",
    "ensure_chat_data_layout",
    "LOCAL_MEMORY_DIR_REL",
    "RECENT_MEMORY_DIR_REL",
    "SELF_MIND_DIR_REL",
    "SKILLS_HOME_REL",
    "SKILLS_SOURCE_HOME_REL",
    "SKILL_COLLECTIONS_FILE_REL",
    "SKILL_PROMPT_POLICY_FILE_REL",
    "prompt_path_text",
    "resolve_chat_home",
    "resolve_butler_root",
    "resolve_skills_home",
]
