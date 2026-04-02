from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

try:
    from butler_main.agents_os.runtime.provider_interfaces import MemoryRuntimeProvider
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from agents_os.runtime.provider_interfaces import MemoryRuntimeProvider

from butler_main.chat.session_modes import resolve_recent_mode


@dataclass(slots=True, frozen=True)
class ConversationTurnInput:
    user_prompt: str
    workspace: str
    image_paths: Sequence[str] | None = None
    timeout: int = 300
    model: str = "auto"
    max_len: int = 4000
    metadata: dict[str, Any] = field(default_factory=dict)
    stream_callback: Callable[[str], None] | None = None


@dataclass(slots=True, frozen=True)
class ConversationPromptBuild:
    prompt: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ConversationTurnState:
    intake_decision: dict[str, Any] = field(default_factory=dict)
    recent_mode: str = "default"
    pending_memory_id: str = ""
    previous_pending: dict[str, Any] | None = None
    prepared_user_prompt: str = ""
    built_prompt: str = ""
    prompt_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ConversationTurnOutput:
    reply_text: str
    pending_memory_id: str = ""
    state: ConversationTurnState | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationTurnEngine:
    """Reusable sequencing for a single conversation turn.

    The engine owns only neutral orchestration:
    classify -> memory prepare -> prompt build -> reply execute.
    Product- or channel-specific policy stays in injected callbacks.
    """

    def __init__(
        self,
        *,
        memory_provider: MemoryRuntimeProvider | None = None,
        begin_turn_fallback_fn: Callable[[str, str], tuple[str, dict[str, Any] | None]],
        prepare_turn_input_fallback_fn: Callable[..., str],
        classify_turn_fn: Callable[[str], Mapping[str, Any]] | None,
        prompt_builder_fn: Callable[..., ConversationPromptBuild | Mapping[str, Any] | str],
        reply_executor_fn: Callable[..., str],
        time_source: Callable[[], float] | None = None,
    ) -> None:
        self._memory_provider = memory_provider
        self._begin_turn_fallback_fn = begin_turn_fallback_fn
        self._prepare_turn_input_fallback_fn = prepare_turn_input_fallback_fn
        self._classify_turn_fn = classify_turn_fn
        self._prompt_builder_fn = prompt_builder_fn
        self._reply_executor_fn = reply_executor_fn
        self._time_source = time_source or time.perf_counter

    def run_turn(self, turn_input: ConversationTurnInput) -> ConversationTurnOutput:
        total_started_at = self._time_source()
        intake_started_at = total_started_at
        intake_decision = self._classify_turn(turn_input.user_prompt)
        intake_elapsed = self._time_source() - intake_started_at
        recent_mode = self._resolve_recent_mode(turn_input=turn_input, intake_decision=intake_decision)

        recent_started_at = self._time_source()
        pending_memory_id, previous_pending, prepared_user_prompt = self._prepare_turn_input(
            turn_input=turn_input,
            recent_mode=recent_mode,
        )
        recent_elapsed = self._time_source() - recent_started_at

        build_prompt_started_at = self._time_source()
        prompt_build = self._normalize_prompt_build(
            self._prompt_builder_fn(
                prepared_user_prompt=prepared_user_prompt,
                turn_input=turn_input,
                intake_decision=intake_decision,
                recent_mode=recent_mode,
            )
        )
        build_prompt_elapsed = self._time_source() - build_prompt_started_at

        state = ConversationTurnState(
            intake_decision=dict(intake_decision),
            recent_mode=recent_mode,
            pending_memory_id=pending_memory_id,
            previous_pending=dict(previous_pending) if isinstance(previous_pending, dict) else previous_pending,
            prepared_user_prompt=prepared_user_prompt,
            built_prompt=prompt_build.prompt,
            prompt_metadata=dict(prompt_build.metadata or {}),
        )

        model_exec_started_at = self._time_source()
        reply_text = self._reply_executor_fn(
            prompt=prompt_build.prompt,
            turn_input=turn_input,
            turn_state=state,
        )
        model_exec_elapsed = self._time_source() - model_exec_started_at
        total_elapsed = self._time_source() - total_started_at

        return ConversationTurnOutput(
            reply_text=reply_text,
            pending_memory_id=pending_memory_id,
            state=state,
            metadata={
                "recent_mode": recent_mode,
                "timings": {
                    "intake": intake_elapsed,
                    "recent": recent_elapsed,
                    "build_prompt": build_prompt_elapsed,
                    "model_exec": model_exec_elapsed,
                    "total": total_elapsed,
                },
            },
        )

    def _classify_turn(self, user_prompt: str) -> dict[str, Any]:
        if self._classify_turn_fn is None:
            return {}
        result = self._classify_turn_fn(user_prompt)
        return dict(result or {})

    def _prepare_turn_input(
        self,
        *,
        turn_input: ConversationTurnInput,
        recent_mode: str,
    ) -> tuple[str, dict[str, Any] | None, str]:
        session_scope_id = str(turn_input.metadata.get("session_scope_id") or "").strip()
        mode_state_snapshot = dict(turn_input.metadata.get("chat_mode_state_snapshot") or {})
        chat_session_state_snapshot = dict(turn_input.metadata.get("chat_session_state_snapshot") or {})
        memory = self._memory_provider
        if memory is not None:
            pending_memory_id, previous_pending = memory.begin_turn(
                turn_input.user_prompt,
                turn_input.workspace,
                session_scope_id=session_scope_id,
            )
            try:
                prepared = memory.prepare_turn_input(
                    turn_input.user_prompt,
                    exclude_memory_id=pending_memory_id,
                    previous_pending=previous_pending,
                    recent_mode=recent_mode,
                    session_scope_id=session_scope_id,
                    mode_state_override=mode_state_snapshot,
                    chat_session_state_override=chat_session_state_snapshot,
                )
            except TypeError:
                prepared = memory.prepare_turn_input(
                    turn_input.user_prompt,
                    exclude_memory_id=pending_memory_id,
                    previous_pending=previous_pending,
                    recent_mode=recent_mode,
                    session_scope_id=session_scope_id,
                )
            return pending_memory_id, previous_pending, prepared

        try:
            pending_memory_id, previous_pending = self._begin_turn_fallback_fn(
                turn_input.user_prompt,
                turn_input.workspace,
                session_scope_id=session_scope_id,
            )
        except TypeError:
            pending_memory_id, previous_pending = self._begin_turn_fallback_fn(turn_input.user_prompt, turn_input.workspace)
        try:
            prepared = self._prepare_turn_input_fallback_fn(
                turn_input.user_prompt,
                exclude_memory_id=pending_memory_id,
                previous_pending=previous_pending,
                recent_mode=recent_mode,
                session_scope_id=session_scope_id,
                mode_state_override=mode_state_snapshot,
                chat_session_state_override=chat_session_state_snapshot,
            )
        except TypeError:
            prepared = self._prepare_turn_input_fallback_fn(
                turn_input.user_prompt,
                exclude_memory_id=pending_memory_id,
                previous_pending=previous_pending,
                recent_mode=recent_mode,
            )
        return pending_memory_id, previous_pending, prepared

    @staticmethod
    def _resolve_recent_mode(
        *,
        turn_input: ConversationTurnInput,
        intake_decision: Mapping[str, Any],
    ) -> str:
        metadata = dict(turn_input.metadata or {})
        explicit_mode = (
            str(metadata.get("recent_mode") or "").strip()
            or str(metadata.get("chat_recent_mode") or "").strip()
            or str(metadata.get("chat_main_mode") or "").strip()
        )
        return resolve_recent_mode(explicit_mode=explicit_mode, intake_decision=intake_decision)

    @staticmethod
    def _normalize_prompt_build(payload: ConversationPromptBuild | Mapping[str, Any] | str) -> ConversationPromptBuild:
        if isinstance(payload, ConversationPromptBuild):
            return payload
        if isinstance(payload, str):
            return ConversationPromptBuild(prompt=payload)
        if isinstance(payload, Mapping):
            return ConversationPromptBuild(
                prompt=str(payload.get("prompt") or ""),
                metadata=dict(payload.get("metadata") or {}),
            )
        raise TypeError(f"unsupported conversation prompt build payload: {type(payload)!r}")


__all__ = [
    "ConversationPromptBuild",
    "ConversationTurnEngine",
    "ConversationTurnInput",
    "ConversationTurnOutput",
    "ConversationTurnState",
]
