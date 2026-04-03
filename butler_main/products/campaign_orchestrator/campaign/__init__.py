from __future__ import annotations

from pathlib import Path

from butler_main._package_alias import configure_package_alias


configure_package_alias(
    globals(),
    target_package="butler_main.domains.campaign",
    target_dir=Path(__file__).resolve().parents[3] / "domains" / "campaign",
)

