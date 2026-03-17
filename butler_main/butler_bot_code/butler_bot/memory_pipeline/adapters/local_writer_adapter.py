from __future__ import annotations

from ..models import MemoryWriteRequest


class LocalMemoryWriterAdapter:
    def __init__(self, manager) -> None:
        self._manager = manager

    def apply(self, workspace: str, request: MemoryWriteRequest) -> str:
        return self._manager._upsert_local_memory(
            workspace,
            request.title,
            request.summary,
            list(request.keywords),
            source_type=request.source_type,
            source_memory_id=request.source_memory_id,
            source_reason=request.source_reason,
            source_topic=request.source_topic,
            source_entry=request.metadata.get("source_entry") if isinstance(request.metadata, dict) else None,
        )
