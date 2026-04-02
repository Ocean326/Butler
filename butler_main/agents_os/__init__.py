"""Lean package entrypoint for Butler''s agents OS layers."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_SUBMODULES = {
    "contracts",
    "factory",
    "governance",
    "process_runtime",
    "protocol",
    "recovery",
    "runtime",
    "verification",
    "workflow",
}

__all__ = sorted(_SUBMODULES)


def __getattr__(name: str) -> Any:
    if name in _SUBMODULES:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _SUBMODULES)
