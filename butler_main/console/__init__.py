from __future__ import annotations

import importlib
import sys
from pathlib import Path

from butler_main.repo_layout import BUTLER_MAIN_REL, HOST_BODY_MODULE_REL, resolve_repo_root

_REPO_ROOT = resolve_repo_root(__file__)
_BUTLER_MAIN_DIR = _REPO_ROOT / BUTLER_MAIN_REL
_BODY_MODULE_DIR = _REPO_ROOT / HOST_BODY_MODULE_REL
_PRODUCT_DIR = (_REPO_ROOT / "butler_main" / "products" / "campaign_orchestrator" / "console").resolve()

if str(_BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BUTLER_MAIN_DIR))
if str(_BODY_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_BODY_MODULE_DIR))

__path__ = [str(_PRODUCT_DIR)]

_EXPORT_MAP = {
    "AccessDiagnostics": (".types", "AccessDiagnostics"),
    "AgentDetailEnvelope": (".types", "AgentDetailEnvelope"),
    "AgentExecutionView": (".types", "AgentExecutionView"),
    "ArtifactListItem": (".types", "ArtifactListItem"),
    "BoardEdgeView": (".types", "BoardEdgeView"),
    "BoardNodeView": (".types", "BoardNodeView"),
    "BoardSnapshot": (".types", "BoardSnapshot"),
    "ChannelThreadSummary": (".types", "ChannelThreadSummary"),
    "ConsoleControlService": (".service", "ConsoleControlService"),
    "ConsoleEventEnvelope": (".types", "ConsoleEventEnvelope"),
    "ConsoleQueryService": (".service", "ConsoleQueryService"),
    "ControlActionRequest": (".types", "ControlActionRequest"),
    "ControlActionResult": (".types", "ControlActionResult"),
    "create_console_app": (".app", "create_console_app"),
    "create_console_http_server": (".server", "create_console_http_server"),
    "create_console_wsgi_app": (".server", "create_console_wsgi_app"),
    "FrontdoorDraftView": (".types", "FrontdoorDraftView"),
    "GraphEdgeView": (".types", "GraphEdgeView"),
    "GraphNodeActionState": (".types", "GraphNodeActionState"),
    "GraphNodeView": (".types", "GraphNodeView"),
    "GraphSnapshot": (".types", "GraphSnapshot"),
    "PreviewEnvelope": (".types", "PreviewEnvelope"),
    "RecordListItem": (".types", "RecordListItem"),
    "run_console_http_server": (".server", "run_console_http_server"),
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
