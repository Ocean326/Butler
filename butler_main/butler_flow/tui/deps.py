from __future__ import annotations

import importlib.util
import os
import shutil


MIN_TUI_COLUMNS = 100


def textual_dependency_installed() -> bool:
    return importlib.util.find_spec("textual") is not None


def terminal_columns(default: int = 0) -> int:
    try:
        return int(shutil.get_terminal_size((default, 0)).columns or 0)
    except Exception:
        return int(default or 0)


def textual_tui_support(*, force: bool = False) -> tuple[bool, str]:
    if not textual_dependency_installed():
        return False, "Textual is not installed. Run `./.venv/bin/pip install -r requirements-cli.txt`."
    columns = terminal_columns()
    if not force and columns and columns < MIN_TUI_COLUMNS:
        return False, f"terminal width {columns} is below the TUI minimum ({MIN_TUI_COLUMNS})"
    if not force and os.environ.get("TERM", "").strip().lower() == "dumb":
        return False, "TERM=dumb does not support the TUI shell"
    return True, ""
