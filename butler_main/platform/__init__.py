from __future__ import annotations

import importlib.machinery
import sys
import sysconfig


def _load_stdlib_platform_into_current_module() -> None:
    stdlib_path = sysconfig.get_path("stdlib")
    search_paths = [stdlib_path] if stdlib_path else None
    spec = importlib.machinery.PathFinder.find_spec("platform", search_paths)
    if spec is None or spec.loader is None:
        raise ImportError("stdlib platform module not found")
    spec.loader.exec_module(sys.modules[__name__])


if __name__ == "platform":
    _load_stdlib_platform_into_current_module()
else:
    __all__ = ["host_runtime", "runtime", "skills"]
