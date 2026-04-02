"""cursor_cli_support.resolve_cursor_cli_cmd_path 解析顺序回归。"""

from __future__ import annotations

import sys

import pytest

from agents_os.execution.cursor_cli_support import resolve_cursor_cli_cmd_path


def test_resolve_prefers_top_level_cursor_cli_path() -> None:
    cfg = {"cursor_cli_path": sys.executable}
    assert resolve_cursor_cli_cmd_path(cfg) == sys.executable


def test_resolve_uses_cli_runtime_cursor_provider_path() -> None:
    cfg = {
        "cli_runtime": {
            "providers": {
                "cursor": {"path": sys.executable},
            }
        }
    }
    assert resolve_cursor_cli_cmd_path(cfg) == sys.executable


def test_resolve_provider_path_accepts_command_name(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(cmd: str) -> str | None:
        if cmd == "agent":
            return sys.executable
        return None

    monkeypatch.setattr("agents_os.execution.cursor_cli_support.shutil.which", fake_which)
    cfg = {"cli_runtime": {"providers": {"cursor": {"path": "agent"}}}}
    assert resolve_cursor_cli_cmd_path(cfg) == sys.executable
