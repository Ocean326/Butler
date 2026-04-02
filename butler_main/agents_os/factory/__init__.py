from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AgentFactory",
    "AgentRuntimeFactory",
    "AgentSpec",
    "AgentProfile",
    "AgentCapabilities",
    "AgentProfileRegistry",
    "build_agent_profile",
]

_EXPORTS = {
    "AgentFactory": "agent_factory",
    "AgentRuntimeFactory": "agent_factory",
    "AgentSpec": "agent_spec",
    "AgentProfile": "agent_spec",
    "AgentCapabilities": "agent_spec",
    "AgentProfileRegistry": "profiles",
    "build_agent_profile": "profiles",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
