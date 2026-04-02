from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class BackgroundMemoryServices(Protocol):
    def start_background_services(self) -> None: ...


class RuntimeRequestOverrideProvider(Protocol):
    def get_runtime_request_override(self) -> dict[str, Any]: ...


class TurnLifecycleStore(Protocol):
    def begin_turn(
        self,
        user_prompt: str,
        workspace: str,
        *,
        session_scope_id: str = "",
    ) -> tuple[str, dict[str, Any] | None]: ...


class TurnPromptAssembler(Protocol):
    def prepare_turn_input(
        self,
        user_prompt: str,
        *,
        exclude_memory_id: str,
        previous_pending: Mapping[str, Any] | None = None,
        recent_mode: str = "default",
        session_scope_id: str = "",
    ) -> str: ...


class ReplyPersistenceService(Protocol):
    def persist_reply_async(
        self,
        user_prompt: str,
        assistant_reply: str,
        *,
        raw_reply: str | None = None,
        memory_id: str | None = None,
        model_override: str | None = None,
        suppress_task_merge: bool = False,
        session_scope_id: str = "",
        process_events: Sequence[Mapping[str, Any]] | None = None,
    ) -> None: ...


__all__ = [
    "BackgroundMemoryServices",
    "ReplyPersistenceService",
    "RuntimeRequestOverrideProvider",
    "TurnLifecycleStore",
    "TurnPromptAssembler",
]
