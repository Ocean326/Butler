from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class TurnLifecycle:
    turn_id: str
    session_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        pass

    def update(self, updates: Mapping[str, Any]) -> None:
        pass

    def finish(self) -> None:
        pass
