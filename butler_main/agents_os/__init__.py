"""Lean package entrypoint for Butler''s agents OS layers."""

from __future__ import annotations

import sys
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


_ALIASES = ("agents_os", "butler_main.agents_os")
for _alias in _ALIASES:
    sys.modules.setdefault(_alias, sys.modules[__name__])


def _load_submodule(name: str):
    module = globals().get(name)
    if module is not None:
        return module
    module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    sibling_names = {
        alias + f".{name}"
        for alias in _ALIASES
        if alias != __name__
    }
    for sibling_name in sibling_names:
        sys.modules.setdefault(sibling_name, module)
    return module


def __getattr__(name: str) -> Any:
    if name in _SUBMODULES:
        return _load_submodule(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _SUBMODULES)
