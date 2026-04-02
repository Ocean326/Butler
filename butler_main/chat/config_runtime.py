from __future__ import annotations

import json
import os
from pathlib import Path

from .pathing import resolve_butler_root
from butler_main.agents_os.execution.logging import set_runtime_log_config


CONFIG: dict = {}
_CONFIG_PATH_FOR_RELOAD: str | None = None
_CONFIG_LAST_RELOAD = 0.0
_CONFIG_RELOAD_INTERVAL_SECONDS = 5.0


def candidate_config_paths(default_config_name: str, *, anchor_file: str | None = None) -> list[str]:
    config_name = f"{default_config_name}.json"
    base_file = Path(anchor_file or __file__).resolve()
    chat_root = base_file.parent
    return [
        str((chat_root / "configs" / config_name).resolve()),
        str((chat_root.parent / "butler_bot_code" / "configs" / config_name).resolve()),
    ]


def resolve_default_config_path(default_config_name: str, *, anchor_file: str | None = None) -> str:
    candidates = candidate_config_paths(default_config_name, anchor_file=anchor_file)
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[-1]


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    config = dict(loaded or {})
    config["__config_path"] = os.path.abspath(config_path)
    workspace_root = config.get("workspace_root")
    if workspace_root:
        config["workspace_root"] = str(resolve_butler_root(workspace_root))
    else:
        config["workspace_root"] = str(resolve_butler_root(Path(__file__).resolve().parents[2]))
    return config


def set_active_config(config: dict, *, config_path: str | None = None) -> dict:
    global _CONFIG_PATH_FOR_RELOAD, _CONFIG_LAST_RELOAD
    CONFIG.clear()
    CONFIG.update(dict(config or {}))
    resolved_config_path = str(config_path or CONFIG.get("__config_path") or "").strip()
    if resolved_config_path:
        resolved_config_path = os.path.abspath(resolved_config_path)
        CONFIG["__config_path"] = resolved_config_path
        _CONFIG_PATH_FOR_RELOAD = resolved_config_path
    elif "__config_path" in CONFIG:
        _CONFIG_PATH_FOR_RELOAD = os.path.abspath(str(CONFIG["__config_path"]))
        CONFIG["__config_path"] = _CONFIG_PATH_FOR_RELOAD
    else:
        _CONFIG_PATH_FOR_RELOAD = None
    _CONFIG_LAST_RELOAD = 0.0
    set_runtime_log_config(
        CONFIG.get("__config_path"),
        (CONFIG.get("logging") or {}).get("level") if isinstance(CONFIG.get("logging"), dict) else None,
    )
    return dict(CONFIG)


def load_active_config(config_path: str) -> dict:
    loaded = load_config(config_path)
    return set_active_config(loaded, config_path=config_path)


def get_config() -> dict:
    global _CONFIG_LAST_RELOAD
    config_path = _CONFIG_PATH_FOR_RELOAD or str(CONFIG.get("__config_path") or "").strip() or None
    if config_path and os.path.isfile(config_path):
        import time

        now = time.time()
        if (now - _CONFIG_LAST_RELOAD) >= _CONFIG_RELOAD_INTERVAL_SECONDS:
            try:
                loaded = load_config(config_path)
                set_active_config(loaded, config_path=config_path)
            except Exception:
                pass
            _CONFIG_LAST_RELOAD = now
    return CONFIG


__all__ = [
    "CONFIG",
    "candidate_config_paths",
    "get_config",
    "load_active_config",
    "load_config",
    "resolve_default_config_path",
    "set_active_config",
]
