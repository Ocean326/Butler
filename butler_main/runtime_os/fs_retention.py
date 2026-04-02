from __future__ import annotations

from pathlib import Path
import shutil
import time


DEFAULT_RETENTION_DAYS = 3


def _retention_cutoff_epoch(*, retention_days: int, now_epoch: float | None = None) -> float:
    effective_days = max(1, int(retention_days or DEFAULT_RETENTION_DAYS))
    current = time.time() if now_epoch is None else float(now_epoch)
    return current - (effective_days * 24 * 60 * 60)


def newest_path_mtime(path: str | Path) -> float:
    target = Path(path)
    try:
        newest = float(target.stat().st_mtime)
    except OSError:
        return 0.0
    if not target.is_dir():
        return newest
    try:
        for nested in target.rglob("*"):
            try:
                newest = max(newest, float(nested.stat().st_mtime))
            except OSError:
                continue
    except OSError:
        return newest
    return newest


def prune_path_children(
    root: str | Path,
    *,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    include_files: bool = True,
    include_dirs: bool = True,
    preserve_names: set[str] | None = None,
    now_epoch: float | None = None,
) -> list[Path]:
    target_root = Path(root)
    if not target_root.exists():
        return []

    cutoff = _retention_cutoff_epoch(retention_days=retention_days, now_epoch=now_epoch)
    preserved = {str(name).strip() for name in (preserve_names or set()) if str(name).strip()}
    removed: list[Path] = []

    try:
        children = sorted(target_root.iterdir(), key=lambda item: item.name)
    except OSError:
        return removed

    for child in children:
        if child.name in preserved:
            continue
        try:
            is_file = child.is_file()
            is_dir = child.is_dir()
        except OSError:
            continue
        if (is_file and not include_files) or (is_dir and not include_dirs):
            continue
        if not is_file and not is_dir:
            continue
        if newest_path_mtime(child) >= cutoff:
            continue
        try:
            if is_dir:
                shutil.rmtree(child, ignore_errors=False)
            else:
                child.unlink(missing_ok=True)
            removed.append(child)
        except OSError:
            continue
    return removed


__all__ = [
    "DEFAULT_RETENTION_DAYS",
    "newest_path_mtime",
    "prune_path_children",
]
