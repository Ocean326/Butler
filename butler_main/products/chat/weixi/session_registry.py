from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from typing import Any

from .session_model import WeixinConversationSession


class WeixinSessionRegistry:
    def __init__(
        self,
        *,
        recent_limit: int = 8,
        max_sessions: int = 256,
        max_idle_seconds: int = 24 * 60 * 60,
    ) -> None:
        self._recent_limit = max(int(recent_limit or 8), 1)
        self._max_sessions = max(int(max_sessions or 256), 16)
        self._max_idle_seconds = max(int(max_idle_seconds or (24 * 60 * 60)), 60)
        self._lock = threading.Lock()
        self._sessions: dict[str, WeixinConversationSession] = {}

    def record_inbound(
        self,
        *,
        conversation_key: str,
        account_id: str,
        actor_id: str,
        receive_id: str,
        receive_id_type: str,
        chat_type: str,
        raw_session_ref: str,
        session_id: str,
        message_id: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        key = str(conversation_key or "").strip()
        if not key:
            return
        now = time.time()
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                session = WeixinConversationSession(conversation_key=key)
                self._sessions[key] = session
            session.account_id = str(account_id or "").strip()
            session.actor_id = str(actor_id or "").strip()
            session.receive_id = str(receive_id or "").strip()
            session.receive_id_type = str(receive_id_type or "open_id").strip() or "open_id"
            session.chat_type = str(chat_type or "dm").strip() or "dm"
            session.raw_session_ref = str(raw_session_ref or "").strip()
            session.session_id = str(session_id or key).strip() or key
            session.last_message_id = str(message_id or "").strip()
            session.last_seen_at = now
            session.message_count += 1
            if isinstance(metadata, Mapping):
                session.metadata.update(
                    {
                        str(name): value
                        for name, value in metadata.items()
                        if str(name or "").strip() and value not in (None, "")
                    }
                )
            self._prune_locked()

    def record_started(self, conversation_key: str) -> None:
        self._update_runtime_state(
            conversation_key,
            in_flight=True,
            last_started_at=time.time(),
            last_error="",
        )

    def record_completed(self, conversation_key: str, *, delivered_count: int = 0) -> None:
        self._update_runtime_state(
            conversation_key,
            in_flight=False,
            last_finished_at=time.time(),
            last_delivered_count=max(int(delivered_count or 0), 0),
            last_error="",
        )

    def record_failed(self, conversation_key: str, error: str) -> None:
        self._update_runtime_state(
            conversation_key,
            in_flight=False,
            last_finished_at=time.time(),
            last_error=str(error or "").strip(),
        )

    def snapshot(self, *, limit: int | None = None) -> dict[str, Any]:
        with self._lock:
            self._prune_locked()
            sessions = list(self._sessions.values())
            recent_limit = max(int(limit or self._recent_limit), 1)
            recent = sorted(sessions, key=self._recent_sort_key, reverse=True)[:recent_limit]
            return {
                "active_conversation_count": len(sessions),
                "running_conversation_count": sum(1 for item in sessions if item.in_flight),
                "recent_conversations": [item.as_dict() for item in recent],
            }

    def _update_runtime_state(self, conversation_key: str, **changes: Any) -> None:
        key = str(conversation_key or "").strip()
        if not key:
            return
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                session = WeixinConversationSession(conversation_key=key)
                self._sessions[key] = session
            for name, value in changes.items():
                if hasattr(session, name):
                    setattr(session, name, value)

    def _prune_locked(self) -> None:
        if not self._sessions:
            return
        cutoff = time.time() - self._max_idle_seconds
        for key, session in list(self._sessions.items()):
            if session.in_flight:
                continue
            if session.last_seen_at and session.last_seen_at < cutoff:
                self._sessions.pop(key, None)
        if len(self._sessions) <= self._max_sessions:
            return
        ordered = sorted(self._sessions.items(), key=lambda item: self._recent_sort_key(item[1]))
        for key, session in ordered:
            if len(self._sessions) <= self._max_sessions:
                break
            if session.in_flight:
                continue
            self._sessions.pop(key, None)

    @staticmethod
    def _recent_sort_key(session: WeixinConversationSession) -> float:
        return max(session.last_seen_at, session.last_started_at, session.last_finished_at)


__all__ = ["WeixinSessionRegistry"]
