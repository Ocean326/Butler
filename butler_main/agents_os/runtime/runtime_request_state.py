from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Mapping

from .turn_state import ThreadLocalStateStore


class RuntimeRequestState:
    """Generic thread-local runtime request override state."""

    def __init__(self, state_store: ThreadLocalStateStore | None = None, *, key: str = "runtime_request") -> None:
        self._state_store = state_store or ThreadLocalStateStore()
        self._key = str(key)

    def get_override(self) -> dict[str, Any]:
        override = self._state_store.get(self._key, None)
        return dict(override or {})

    def set_override(self, runtime_request: Mapping[str, Any] | None) -> None:
        payload = dict(runtime_request or {})
        if not payload:
            self.clear_override()
            return
        self._state_store.set(**{self._key: payload})

    def clear_override(self) -> None:
        self._state_store.delete(self._key)

    @contextmanager
    def scope(self, runtime_request: Mapping[str, Any] | None):
        previous = self._state_store.get(self._key, None)
        self.set_override(runtime_request)
        try:
            yield
        finally:
            if previous is None:
                self.clear_override()
            else:
                self._state_store.set(**{self._key: previous})


__all__ = ["RuntimeRequestState"]
