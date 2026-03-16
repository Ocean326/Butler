from __future__ import annotations

import os
from pathlib import Path


def backup_path_for(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8", keep_backup: bool = False) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_name(f"{target.name}.tmp-{os.getpid()}")
    temp_path.write_text(text, encoding=encoding)
    if keep_backup and target.exists():
        backup_path_for(target).write_text(target.read_text(encoding=encoding), encoding=encoding)
    temp_path.replace(target)


def read_text_with_backup(path: Path, *, encoding: str = "utf-8") -> str:
    target = Path(path)
    primary_error: Exception | None = None
    try:
        return target.read_text(encoding=encoding)
    except Exception as exc:
        primary_error = exc
    backup = backup_path_for(target)
    try:
        return backup.read_text(encoding=encoding)
    except Exception:
        if primary_error is not None:
            raise primary_error
        raise
