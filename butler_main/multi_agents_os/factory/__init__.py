"""Compatibility shim for process-runtime factory exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_TARGET_MODULES = ("runtime_os.process_runtime.factory", "butler_main.runtime_os.process_runtime.factory")
__all__ = ["WorkflowFactory"]


def _load_target():
    for candidate in _TARGET_MODULES:
        try:
            return import_module(candidate)
        except ModuleNotFoundError:
            continue
    raise ModuleNotFoundError(f"unable to import process runtime factory from {_TARGET_MODULES!r}")


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = _load_target()
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
