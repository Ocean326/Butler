from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class PromptRuntimeProvider(Protocol):
    """Generic prompt provider contract for product-specific agents."""

    def render_skills_prompt(self, workspace: str) -> str: ...

    def render_agent_capabilities_prompt(self, workspace: str) -> str: ...

    def build_prompt(
        self,
        user_prompt: str,
        *,
        workspace: str,
        image_paths: Sequence[str] | None = None,
        raw_user_prompt: str | None = None,
        request_intake_prompt: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> str: ...


class MemoryRuntimeProvider(Protocol):
    """Generic memory provider contract for conversation-style agents."""

    def start_background_services(self) -> None: ...

    def get_runtime_request_override(self) -> dict[str, Any]: ...

    def begin_turn(
        self,
        user_prompt: str,
        workspace: str,
        *,
        session_scope_id: str = "",
    ) -> tuple[str, dict[str, Any] | None]: ...

    def prepare_turn_input(
        self,
        user_prompt: str,
        *,
        exclude_memory_id: str,
        previous_pending: Mapping[str, Any] | None = None,
        recent_mode: str = "default",
        session_scope_id: str = "",
    ) -> str: ...

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


__all__ = ["MemoryRuntimeProvider", "PromptRuntimeProvider"]
