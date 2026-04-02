from __future__ import annotations

from pathlib import Path

from butler_main.runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children

from .paths import resolve_butler_root


ORCHESTRATOR_ADAPTER_RUN_DIR_REL = Path("butler_main") / "butler_bot_code" / "run" / "agents_os"


def resolve_orchestrator_run_file(workspace: str | Path | None, filename: str) -> Path:
    root = resolve_butler_root(workspace)
    run_dir = root / ORCHESTRATOR_ADAPTER_RUN_DIR_REL
    run_dir.mkdir(parents=True, exist_ok=True)
    prune_path_children(
        run_dir,
        retention_days=DEFAULT_RETENTION_DAYS,
        include_files=True,
        include_dirs=True,
    )
    return run_dir / filename


__all__ = ["ORCHESTRATOR_ADAPTER_RUN_DIR_REL", "resolve_orchestrator_run_file"]
