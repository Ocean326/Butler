from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from .config_runtime import get_config as get_runtime_config


_ENV_CHAT_FRONTDOOR_TASKS_ENABLED = "BUTLER_CHAT_FRONTDOOR_TASKS_ENABLED"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_TASK_FRONTDOOR_SLASH_MODES = {"delivery", "research"}


def chat_frontdoor_tasks_enabled(config: Mapping[str, Any] | None = None) -> bool:
    """Return whether chat-side background/task frontdoor features are enabled."""

    env_value = os.getenv(_ENV_CHAT_FRONTDOOR_TASKS_ENABLED)
    if env_value is not None and str(env_value).strip():
        return str(env_value).strip().lower() in _TRUE_VALUES
    resolved_config = config if isinstance(config, Mapping) else get_runtime_config()
    features = resolved_config.get("features") if isinstance(resolved_config, Mapping) else None
    if isinstance(features, Mapping) and "chat_frontdoor_tasks_enabled" in features:
        return bool(features.get("chat_frontdoor_tasks_enabled"))
    return True


def chat_frontdoor_slash_mode_enabled(mode_id: str, config: Mapping[str, Any] | None = None) -> bool:
    normalized_mode = str(mode_id or "").strip().lower()
    if normalized_mode in _TASK_FRONTDOOR_SLASH_MODES:
        return chat_frontdoor_tasks_enabled(config)
    return True


__all__ = [
    "chat_frontdoor_slash_mode_enabled",
    "chat_frontdoor_tasks_enabled",
]
