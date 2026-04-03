from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

from butler_main._package_alias import configure_package_alias


configure_package_alias(
    globals(),
    target_package="butler_main.runtime_os",
    target_dir=Path(__file__).resolve().parents[2] / "runtime_os",
)

for _submodule in (
    "agent_runtime",
    "durability_substrate",
    "multi_agent_protocols",
    "multi_agent_runtime",
    "process_runtime",
):
    _alias_name = f"{__name__}.{_submodule}"
    if _alias_name in sys.modules:
        continue
    try:
        sys.modules[_alias_name] = import_module(f"butler_main.runtime_os.{_submodule}")
    except Exception:
        continue
