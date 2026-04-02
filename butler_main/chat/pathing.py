from __future__ import annotations

import os
from pathlib import Path


CHAT_HOME_REL = Path("butler_main") / "chat"
CHAT_DATA_HOME_REL = CHAT_HOME_REL / "data"
CHAT_HOT_DATA_HOME_REL = CHAT_DATA_HOME_REL / "hot"
CHAT_COLD_DATA_HOME_REL = CHAT_DATA_HOME_REL / "cold"
LOCAL_MEMORY_DIR_REL = CHAT_COLD_DATA_HOME_REL / "local_memory"
RECENT_MEMORY_DIR_REL = CHAT_HOT_DATA_HOME_REL / "recent_memory"
SKILLS_HOME_REL = Path("butler_main") / "sources" / "skills"
SKILLS_SOURCE_HOME_REL = Path("butler_main") / "sources" / "skills"
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
    candidate = Path(workspace or os.getcwd()).resolve()
    parts_lower = [p.lower() for p in candidate.parts]
    if "butler_main" in parts_lower:
        idx = parts_lower.index("butler_main")
        if idx > 0:
            return Path(*candidate.parts[:idx])
    if candidate.name in {"butler_bot_code", "chat", "orchestrator", "sources"} and candidate.parent.name == "butler_main":
        return candidate.parent.parent
    if candidate.name in {"butler_bot", "scripts"} and candidate.parent.name == "butler_bot_code":
        return candidate.parent.parent.parent
    if candidate.name == "工作区":
        return candidate.parent
    return candidate


def resolve_butler_root(workspace: str | Path | None = None) -> Path:
    base = _normalize_workspace_candidate(workspace)
    candidates = [base, base / "Butler"]
    if workspace is None:
        candidates.append(Path(__file__).resolve().parents[2])
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        butler_main_dir = resolved / "butler_main"
        if butler_main_dir.exists() and any(
            (butler_main_dir / rel).exists()
            for rel in ("chat", "orchestrator", "butler_bot_code", "sources")
        ):
            return resolved
    return base


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
    "resolve_butler_root",
]
