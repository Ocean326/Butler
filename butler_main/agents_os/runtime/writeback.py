from __future__ import annotations

import threading
from typing import Any, Mapping, Sequence


class WritebackCoordinator:
    def persist(self, memory_updates: Sequence[Mapping[str, Any]]) -> None:
        pass

    def emit_artifacts(self, artifacts: Sequence[Any]) -> None:
        pass


class AsyncWritebackRunner:
    """Generic daemon-thread launcher for writeback side effects."""

    def submit(self, target, /, *args, name: str = "writeback-task", daemon: bool = True, **kwargs):
        thread = threading.Thread(
            target=target,
            args=args,
            kwargs=kwargs,
            daemon=daemon,
            name=name,
        )
        thread.start()
        return thread


__all__ = ["AsyncWritebackRunner", "WritebackCoordinator"]
