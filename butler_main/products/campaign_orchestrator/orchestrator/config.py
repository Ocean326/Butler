from __future__ import annotations

import json
from .paths import resolve_butler_root


def load_orchestrator_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    workspace_root = loaded.get("workspace_root")
    if workspace_root:
        loaded["workspace_root"] = str(resolve_butler_root(workspace_root))
    else:
        loaded["workspace_root"] = str(resolve_butler_root(config_path))
    return loaded
