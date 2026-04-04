"""Top-level compatibility namespace for repo-root runtime_os imports."""

from __future__ import annotations

import sys
from importlib import import_module
from typing import Any


_SUBMODULES = (
    "agent_runtime",
    "multi_agent_protocols",
    "multi_agent_runtime",
    "durability_substrate",
    "process_runtime",
)
_RESOLVED_EXPORTS: dict[str, str] = {}
__all__ = list(_SUBMODULES)


def _load_submodule(name: str):
    module = sys.modules.get(f"{__name__}.{name}")
    if module is None:
        module = globals().get(name)
    if module is None:
        module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    sys.modules.setdefault(f"{__name__}.{name}", module)
    return module


def _resolve_export(name: str) -> Any:
    submodule_name = _RESOLVED_EXPORTS.get(name)
    if submodule_name is not None:
        module = _load_submodule(submodule_name)
        value = getattr(module, name)
        globals()[name] = value
        return value
    for candidate in _SUBMODULES:
        module = _load_submodule(candidate)
        if not hasattr(module, name):
            continue
        _RESOLVED_EXPORTS[name] = candidate
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __getattr__(name: str) -> Any:
    if name in _SUBMODULES:
        return _load_submodule(name)
    return _resolve_export(name)


def __dir__() -> list[str]:
    names = set(globals()) | set(_SUBMODULES)
    for submodule_name in _SUBMODULES:
        module = globals().get(submodule_name)
        if module is None:
            continue
        names.update(getattr(module, "__all__", ()))
    names.update(_RESOLVED_EXPORTS)
    return sorted(names)
