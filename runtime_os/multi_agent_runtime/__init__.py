"""Top-level compatibility surface for runtime_os.multi_agent_runtime."""

from __future__ import annotations

import sys
from importlib import import_module
from typing import Any


_TARGET_MODULE = import_module("butler_main.runtime_os.multi_agent_runtime")
__all__ = list(getattr(_TARGET_MODULE, "__all__", ()))
for _parent_name in ("runtime_os", "butler_main.runtime_os"):
    _parent = sys.modules.get(_parent_name)
    if _parent is not None:
        setattr(_parent, "multi_agent_runtime", sys.modules[__name__])


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_TARGET_MODULE, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
