from __future__ import annotations

from typing import Any


class ChatRuntimeRequestOverrideRuntime:
    """Chat-facing adapter over a generic runtime-request state source."""

    def __init__(self, *, state_source) -> None:
        self._state_source = state_source

    def get_runtime_request_override(self) -> dict[str, Any]:
        getter = getattr(self._state_source, "get_runtime_request_override", None)
        if callable(getter):
            return dict(getter() or {})
        return dict(self._state_source.get_override())

    def get_runtime_request_override_for_session(
        self,
        *,
        workspace: str = "",
        session_scope_id: str = "",
        preferred_cli: str = "",
    ) -> dict[str, Any]:
        getter = getattr(self._state_source, "get_runtime_request_override_for_session", None)
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
        writer = getattr(self._state_source, "remember_runtime_session", None)
        if callable(writer):
            writer(
                workspace=workspace,
                session_scope_id=session_scope_id,
                runtime_request=runtime_request,
                execution_metadata=execution_metadata,
            )


__all__ = ["ChatRuntimeRequestOverrideRuntime"]
