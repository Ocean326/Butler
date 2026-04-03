from __future__ import annotations

from collections.abc import Mapping, Sequence

from agents_os.contracts import Invocation, PromptBlock, PromptContext, PromptProfile

from butler_main.chat.prompt_profile import ButlerPromptProfileAdapter


class ButlerPromptContextAdapter:
    """Assemble neutral PromptContext objects from Butler chat invocations."""

    def __init__(
        self,
        *,
        prompt_profile_adapter: ButlerPromptProfileAdapter | None = None,
    ) -> None:
        self._prompt_profile_adapter = prompt_profile_adapter or ButlerPromptProfileAdapter()

    def build_context(
        self,
        invocation: Invocation,
        *,
        entrypoint: str = "",
        prompt_profile: PromptProfile | None = None,
        extra_blocks: Sequence[PromptBlock] | None = None,
        dynamic_metadata: Mapping[str, str] | None = None,
        variables: Mapping[str, object] | None = None,
    ) -> PromptContext:
        route = self._normalize_entrypoint(entrypoint or invocation.entrypoint)
        profile = prompt_profile or self._prompt_profile_adapter.build_profile(route)
        blocks = [
            PromptBlock(
                name="route",
                content=route,
                metadata={"channel": invocation.channel, "session_id": invocation.session_id},
            ),
            PromptBlock(
                name="user_turn",
                content=invocation.user_text,
                metadata={"actor_id": invocation.actor_id},
            ),
        ]
        for item in extra_blocks or []:
            if isinstance(item, PromptBlock):
                blocks.append(item)
        metadata = {
            "channel": invocation.channel,
            "entrypoint": route,
            "product_surface": "chat",
            "session_id": invocation.session_id,
        }
        if isinstance(dynamic_metadata, Mapping):
            metadata.update({str(key): str(value) for key, value in dynamic_metadata.items()})
        return PromptContext(
            profile=profile,
            blocks=blocks,
            variables={str(key): value for key, value in (variables or {}).items()},
            dynamic_metadata=metadata,
        )

    @staticmethod
    def _normalize_entrypoint(entrypoint: str) -> str:
        normalized = str(entrypoint or "").strip().lower()
        if normalized in {"chat", "talk"}:
            return "chat"
        return "chat"


__all__ = ["ButlerPromptContextAdapter"]
