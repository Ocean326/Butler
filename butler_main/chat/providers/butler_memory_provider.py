from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from butler_main.agents_os.runtime.memory_components import (
    BackgroundMemoryServices,
    ReplyPersistenceService,
    RuntimeRequestOverrideProvider,
    TurnLifecycleStore,
    TurnPromptAssembler,
)
from butler_main.agents_os.runtime.provider_interfaces import MemoryRuntimeProvider


class ButlerChatMemoryProvider(MemoryRuntimeProvider):
    """Transitional Butler-backed memory provider for the chat app."""

    def __init__(
        self,
        memory_manager=None,
        *,
        background_services: BackgroundMemoryServices | None = None,
        runtime_request_provider: RuntimeRequestOverrideProvider | None = None,
        turn_lifecycle: TurnLifecycleStore | None = None,
        prompt_assembler: TurnPromptAssembler | None = None,
        reply_persistence: ReplyPersistenceService | None = None,
    ) -> None:
        self._memory_manager = memory_manager
        self._background_services = background_services or memory_manager
        self._runtime_request_provider = runtime_request_provider or memory_manager
        self._turn_lifecycle = turn_lifecycle or memory_manager
        self._prompt_assembler = prompt_assembler or memory_manager
        self._reply_persistence = reply_persistence or memory_manager

    @property
    def manager(self):
        return self._memory_manager

    def start_background_services(self) -> None:
        self._background_services.start_background_services()

    def get_runtime_request_override(self) -> dict[str, Any]:
        return dict(self._runtime_request_provider.get_runtime_request_override())

    def get_runtime_request_override_for_session(
        self,
        *,
        workspace: str = "",
        session_scope_id: str = "",
        preferred_cli: str = "",
    ) -> dict[str, Any]:
        getter = getattr(self._runtime_request_provider, "get_runtime_request_override_for_session", None)
        if callable(getter):
            return dict(
                getter(
                    workspace=workspace,
                    session_scope_id=session_scope_id,
                    preferred_cli=preferred_cli,
                )
                or {}
            )
        return self.get_runtime_request_override()

    def remember_runtime_session(
        self,
        *,
        workspace: str,
        session_scope_id: str,
        runtime_request: dict[str, Any] | None,
        execution_metadata: dict[str, Any] | None,
    ) -> None:
        writer = getattr(self._runtime_request_provider, "remember_runtime_session", None)
        if callable(writer):
            writer(
                workspace=workspace,
                session_scope_id=session_scope_id,
                runtime_request=runtime_request,
                execution_metadata=execution_metadata,
            )

    def begin_turn(
        self,
        user_prompt: str,
        workspace: str,
        *,
        session_scope_id: str = "",
    ) -> tuple[str, dict[str, Any] | None]:
        return self._turn_lifecycle.begin_turn(user_prompt, workspace, session_scope_id=session_scope_id)

    def prepare_turn_input(
        self,
        user_prompt: str,
        *,
        exclude_memory_id: str,
        previous_pending: Mapping[str, Any] | None = None,
        recent_mode: str = "default",
        session_scope_id: str = "",
        mode_state_override=None,
        chat_session_state_override=None,
    ) -> str:
        return self._prompt_assembler.prepare_turn_input(
            user_prompt,
            exclude_memory_id=exclude_memory_id,
            previous_pending=previous_pending,
            recent_mode=recent_mode,
            session_scope_id=session_scope_id,
            mode_state_override=mode_state_override,
            chat_session_state_override=chat_session_state_override,
        )

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
    ) -> None:
        self._reply_persistence.persist_reply_async(
            user_prompt,
            assistant_reply,
            raw_reply=raw_reply,
            memory_id=memory_id,
            model_override=model_override,
            suppress_task_merge=suppress_task_merge,
            session_scope_id=session_scope_id,
            process_events=process_events,
        )


__all__ = ["ButlerChatMemoryProvider"]
