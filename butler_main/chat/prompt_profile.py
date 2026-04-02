from __future__ import annotations

from collections.abc import Sequence

from agents_os.contracts import PromptProfile


_BOOTSTRAP_REFS: dict[str, list[str]] = {
    "chat": ["persona:butler_chat", "bootstrap:chat"],
}
_POLICY_REFS: dict[str, list[str]] = {
    "chat": ["policy:chat_default"],
}
_ENTRYPOINT_ALIASES = {
    "chat": "chat",
    "talk": "chat",
}


class ButlerPromptProfileAdapter:
    """Chat-facing mapping from Butler entrypoints to neutral prompt profiles."""

    def build_profile(
        self,
        entrypoint: str,
        *,
        bootstrap_refs: Sequence[str] | None = None,
        policy_refs: Sequence[str] | None = None,
        render_mode: str = "dialogue",
    ) -> PromptProfile:
        route = self._normalize_entrypoint(entrypoint)
        return PromptProfile(
            profile_id=f"butler.{route}",
            display_name="Butler Chat" if route == "chat" else f"Butler {route}",
            bootstrap_refs=list(bootstrap_refs or _BOOTSTRAP_REFS.get(route, _BOOTSTRAP_REFS["chat"])),
            policy_refs=list(policy_refs or _POLICY_REFS.get(route, _POLICY_REFS["chat"])),
            block_order=["route", "user_turn", "memory_policy", "skills", "runtime"],
            render_mode=render_mode,
            metadata={"product_surface": "chat", "normalized_entrypoint": route},
        )

    @staticmethod
    def _normalize_entrypoint(entrypoint: str) -> str:
        normalized = str(entrypoint or "").strip().lower()
        return _ENTRYPOINT_ALIASES.get(normalized, "chat")


__all__ = ["ButlerPromptProfileAdapter"]
