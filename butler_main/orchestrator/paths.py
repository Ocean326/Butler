from __future__ import annotations

import os
from pathlib import Path


ORCHESTRATOR_RUN_DIR_REL = Path("butler_main") / "butler_bot_code" / "run" / "orchestrator"


def _normalize_workspace_candidate(workspace: str | Path | None) -> Path:
    candidate = Path(workspace or os.getcwd()).resolve()
    parts_lower = [part.lower() for part in candidate.parts]
    if "butler_main" in parts_lower:
        idx = parts_lower.index("butler_main")
        if idx > 0:
            return Path(*candidate.parts[:idx])
    if candidate.name in {"butler_bot_code", "chat", "orchestrator", "agents_os", "multi_agents_os", "runtime_os", "research", "sources"} and candidate.parent.name == "butler_main":
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
