from __future__ import annotations

from pathlib import Path

from butler_main.repo_layout import LEGACY_SKILLS_REL, PLATFORM_SKILLS_REL, resolve_repo_path, resolve_repo_root

WORKSPACE_DIR_NAME = "工作区"
BUTLER_NAMESPACE = "Butler"


def find_workspace_root(start: str | Path) -> Path:
    root = resolve_repo_root(start)
    if (root / "butler_main").exists():
        return root
    raise SystemExit("workspace root not found")


def butler_workspace_root(start: str | Path) -> Path:
    return find_workspace_root(start) / WORKSPACE_DIR_NAME / BUTLER_NAMESPACE


def skill_source_root(start: str | Path) -> Path:
    return resolve_repo_path(
        find_workspace_root(start),
        canonical_rel=PLATFORM_SKILLS_REL,
        compat_rel=LEGACY_SKILLS_REL,
    )


def skill_temp_dir(start: str | Path, task_name: str) -> Path:
    return skill_source_root(start) / "temp" / str(task_name or "general").strip()


def skill_runtime_dir(start: str | Path, skill_name: str) -> Path:
    return butler_workspace_root(start) / "runtime" / "skills" / str(skill_name or "skill").strip()


def skill_governance_dir(start: str | Path, report_name: str) -> Path:
    return butler_workspace_root(start) / "governance" / "skills" / str(report_name or "general").strip()


def resolve_output_dir(start: str | Path, output_dir: str | Path | None, *, default_path: Path) -> Path:
    workspace_root = find_workspace_root(start)
    raw = str(output_dir or "").strip()
    if raw:
        candidate = Path(raw)
        path = candidate if candidate.is_absolute() else workspace_root / candidate
    else:
        path = default_path
    resolved = path.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
