from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agents_os.contracts import MemoryPolicy


_POLICY_MATRIX: dict[str, dict[str, Any]] = {
    "chat": {
        "session_read": True,
        "session_write": True,
        "retrieval_scopes": ["recent_turn", "user_profile", "workspace_context"],
        "long_term_write": "turn_summary",
        "visibility_flags": ["chat_visible"],
    },
}
_ENTRYPOINT_ALIASES = {
    "chat": "chat",
    "talk": "chat",
}


class ButlerMemoryPolicyAdapter:
    """Translate chat route visibility rules into the neutral MemoryPolicy contract."""

    def resolve_policy(
        self,
        entrypoint: str,
        *,
        visibility_flags: Sequence[str] | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> MemoryPolicy:
        route = self._normalize_entrypoint(entrypoint)
        payload = dict(_POLICY_MATRIX.get(route, _POLICY_MATRIX["chat"]))
        if isinstance(overrides, Mapping):
            payload.update(dict(overrides))
        flags = list(payload.get("visibility_flags") or [])
        for value in visibility_flags or []:
            flag = str(value or "").strip()
            if flag and flag not in flags:
                flags.append(flag)
        payload["visibility_flags"] = flags
        return MemoryPolicy(
            session_read=bool(payload.get("session_read")),
            session_write=bool(payload.get("session_write")),
            retrieval_scopes=[str(item) for item in payload.get("retrieval_scopes") or [] if str(item or "").strip()],
            long_term_write=str(payload.get("long_term_write") or "none"),
            visibility_flags=flags,
        )

    @staticmethod
    def _normalize_entrypoint(entrypoint: str) -> str:
        normalized = str(entrypoint or "").strip().lower()
        return _ENTRYPOINT_ALIASES.get(normalized, "chat")


__all__ = ["ButlerMemoryPolicyAdapter"]
