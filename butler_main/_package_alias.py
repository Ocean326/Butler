from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any


def configure_package_alias(
    globals_dict: dict[str, Any],
    *,
    target_package: str,
    target_dir: Path,
) -> None:
    resolved_dir = target_dir.resolve()
    globals_dict["__path__"] = [str(resolved_dir)]
    globals_dict.setdefault("__all__", [])

    def __getattr__(name: str) -> Any:
        module = import_module(target_package)
        value = getattr(module, name)
        globals_dict[name] = value
        return value

    def __dir__() -> list[str]:
        names = set(globals_dict)
        try:
            module = import_module(target_package)
        except Exception:
            return sorted(names)
        names.update(getattr(module, "__all__", ()))
        return sorted(names)

    globals_dict["__getattr__"] = __getattr__
    globals_dict["__dir__"] = __dir__

