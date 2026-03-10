# -*- coding: utf-8 -*-
"""
Runtime logging controls for butler bot.

Provides a lightweight print hook that supports:
- log levels: debug/info/error
- hot-reload from config JSON (logging.level)
- optional timestamp prefix per line (logging.timestamp, default True)
- backward compatibility with existing print-based logs
"""

from __future__ import annotations

import builtins
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path


_LEVELS = {"debug": 10, "info": 20, "error": 30}
_DEFAULT_CHECK_INTERVAL_SECONDS = 2.0

_STATE = {
    "installed": False,
    "config_path": "",
    "level": "info",
    "check_interval_seconds": _DEFAULT_CHECK_INTERVAL_SECONDS,
    "timestamp": True,
    "last_check_at": 0.0,
    "last_mtime": -1.0,
    "original_print": builtins.print,
}

_LOCK = threading.Lock()


def _normalize_level(raw: str | None) -> str:
    text = str(raw or "").strip().lower()
    if text in _LEVELS:
        return text
    return "info"


def _level_value(level: str) -> int:
    return _LEVELS.get(_normalize_level(level), _LEVELS["info"])


def _extract_level_from_print(args: tuple, kwargs: dict) -> str:
    target_file = kwargs.get("file")
    if target_file in (sys.stderr, getattr(sys, "__stderr__", None)):
        return "error"
    if not args:
        return "info"
    first = str(args[0] or "").strip().lower()
    if first.startswith("[debug]") or first.startswith("debug:"):
        return "debug"
    if first.startswith("[error]") or first.startswith("error:"):
        return "error"
    return "info"


def set_runtime_log_config(config_path: str | None = None, default_level: str | None = None) -> None:
    """Set config path and optional default level used by the print hook."""
    with _LOCK:
        if config_path:
            _STATE["config_path"] = str(Path(config_path).resolve())
        if default_level:
            _STATE["level"] = _normalize_level(default_level)


def _refresh_from_config_if_needed() -> None:
    now = time.monotonic()
    with _LOCK:
        interval = float(_STATE.get("check_interval_seconds") or _DEFAULT_CHECK_INTERVAL_SECONDS)
        if now - float(_STATE.get("last_check_at") or 0.0) < max(0.2, interval):
            return
        _STATE["last_check_at"] = now
        config_path = str(_STATE.get("config_path") or "")
    if not config_path:
        return
    path = Path(config_path)
    if not path.exists():
        return
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return
    with _LOCK:
        if float(_STATE.get("last_mtime") or -1.0) == float(mtime):
            return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    logging_cfg = payload.get("logging") if isinstance(payload.get("logging"), dict) else {}
    new_level = _normalize_level(logging_cfg.get("level") or _STATE.get("level"))
    check_interval = logging_cfg.get("check_interval_seconds")
    try:
        parsed_interval = float(check_interval)
        if parsed_interval <= 0:
            parsed_interval = _DEFAULT_CHECK_INTERVAL_SECONDS
    except Exception:
        parsed_interval = float(_STATE.get("check_interval_seconds") or _DEFAULT_CHECK_INTERVAL_SECONDS)
    ts_cfg = logging_cfg.get("timestamp")
    timestamp_enabled = ts_cfg if isinstance(ts_cfg, bool) else bool(_STATE.get("timestamp", True))
    with _LOCK:
        _STATE["level"] = new_level
        _STATE["check_interval_seconds"] = parsed_interval
        _STATE["timestamp"] = timestamp_enabled
        _STATE["last_mtime"] = float(mtime)


def install_print_hook(default_level: str = "info", config_path: str | None = None) -> None:
    """Install a global print wrapper with level filtering and hot config reload."""
    with _LOCK:
        _STATE["level"] = _normalize_level(default_level)
        if config_path:
            _STATE["config_path"] = str(Path(config_path).resolve())
        if _STATE.get("installed"):
            return
        original_print = _STATE["original_print"]

        def _wrapped_print(*args, **kwargs):
            _refresh_from_config_if_needed()
            level = _extract_level_from_print(args, kwargs)
            with _LOCK:
                current_level = str(_STATE.get("level") or "info")
                add_timestamp = bool(_STATE.get("timestamp", True))
            if _level_value(level) < _level_value(current_level):
                return
            if add_timestamp:
                file = kwargs.get("file", sys.stdout)
                if file in (sys.stdout, getattr(sys, "stdout"), sys.stderr, getattr(sys, "stderr", None)):
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    original_print(f"[{ts}] ", end="", file=file, flush=kwargs.get("flush", False))
            return original_print(*args, **kwargs)

        builtins.print = _wrapped_print
        _STATE["installed"] = True


def current_log_level() -> str:
    _refresh_from_config_if_needed()
    with _LOCK:
        return str(_STATE.get("level") or "info")
