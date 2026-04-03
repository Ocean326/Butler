from __future__ import annotations

import os
from pathlib import Path

from butler_main.repo_layout import resolve_repo_root

ORCHESTRATOR_RUN_DIR_REL = Path("butler_main") / "butler_bot_code" / "run" / "orchestrator"


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
