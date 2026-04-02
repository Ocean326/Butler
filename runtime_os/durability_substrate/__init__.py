"""Top-level compatibility surface for runtime_os.durability_substrate."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_TARGET_MODULE = import_module("butler_main.runtime_os.durability_substrate")
__all__ = list(getattr(_TARGET_MODULE, "__all__", ()))


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_TARGET_MODULE, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
