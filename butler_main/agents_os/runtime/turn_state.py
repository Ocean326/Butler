from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ContextStateSnapshot:
    values: Mapping[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


class ThreadLocalStateStore:
    """Generic thread-local key/value store for per-turn runtime state."""

    def __init__(self, context: threading.local | None = None) -> None:
        self._context = context or threading.local()

    @property
    def raw_context(self) -> threading.local:
        return self._context

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self._context, str(key), default)

    def set(self, **values: Any) -> None:
        for key, value in values.items():
            setattr(self._context, str(key), value)

    def delete(self, *keys: str) -> None:
        for key in keys:
            if hasattr(self._context, str(key)):
                delattr(self._context, str(key))

    def snapshot(self, *keys: str) -> ContextStateSnapshot:
        if not keys:
            return ContextStateSnapshot(values=dict(vars(self._context)))
        return ContextStateSnapshot(values={str(key): getattr(self._context, str(key), None) for key in keys})


__all__ = ["ContextStateSnapshot", "ThreadLocalStateStore"]
