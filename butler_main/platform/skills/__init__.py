from __future__ import annotations

from pathlib import Path

from butler_main._package_alias import configure_package_alias


configure_package_alias(
    globals(),
    target_package="butler_main.sources.skills",
    target_dir=Path(__file__).resolve().parents[2] / "sources" / "skills",
)

