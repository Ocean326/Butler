from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence, Optional


@dataclass
class MemoryRuntime:
    scopes: Sequence[str] = field(default_factory=list)
    store: Mapping[str, Any] = field(default_factory=dict)

    def read(self, scope: str, key: str) -> Optional[Any]:
        return self.store.get(f"{scope}:{key}")

    def write(self, scope: str, key: str, value: Any) -> None:
        self.store[f"{scope}:{key}"] = value
