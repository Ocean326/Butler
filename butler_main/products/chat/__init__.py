from __future__ import annotations

import importlib
import sys

from butler_main.repo_layout import HOST_BODY_MODULE_REL, BUTLER_MAIN_REL, resolve_repo_root

_REPO_ROOT = resolve_repo_root(__file__)
_BUTLER_MAIN_DIR = _REPO_ROOT / BUTLER_MAIN_REL
_BODY_MODULE_DIR = _REPO_ROOT / HOST_BODY_MODULE_REL

if str(_BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BUTLER_MAIN_DIR))
if str(_BODY_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_BODY_MODULE_DIR))

_EXPORT_MAP = {
    "ChatApp": (".app", "ChatApp"),
    "ChatAppBootstrap": (".app", "ChatAppBootstrap"),
    "ChannelProfile": (".channel_profiles", "ChannelProfile"),
    "create_default_chat_app": (".app", "create_default_chat_app"),
    "create_default_cli_chat_app": (".app", "create_default_cli_chat_app"),
    "create_default_weixi_chat_app": (".app", "create_default_weixi_chat_app"),
    "ChatMainlineResult": (".mainline", "ChatMainlineResult"),
    "ChatMainlineService": (".mainline", "ChatMainlineService"),
    "ChatRouter": (".routing", "ChatRouter"),
    "ChatRuntimeRequest": (".routing", "ChatRuntimeRequest"),
    "RouteDecision": (".routing", "RouteDecision"),
    "ChatRuntimeExecution": (".runtime", "ChatRuntimeExecution"),
    "ChatRuntimeService": (".runtime", "ChatRuntimeService"),
    "FrontDoorTaskQueryService": (".task_query", "FrontDoorTaskQueryService"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str):
    module_info = _EXPORT_MAP.get(name)
    if module_info is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = module_info
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
