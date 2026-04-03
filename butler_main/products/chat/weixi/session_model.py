from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WeixinConversationSession:
    conversation_key: str
    account_id: str = ""
    actor_id: str = ""
    receive_id: str = ""
    receive_id_type: str = "open_id"
    chat_type: str = "dm"
    raw_session_ref: str = ""
    session_id: str = ""
    last_message_id: str = ""
    last_seen_at: float = 0.0
    last_started_at: float = 0.0
    last_finished_at: float = 0.0
    in_flight: bool = False
    message_count: int = 0
    last_delivered_count: int = 0
    last_error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "conversation_key": self.conversation_key,
            "account_id": self.account_id,
            "actor_id": self.actor_id,
            "receive_id": self.receive_id,
            "receive_id_type": self.receive_id_type,
            "chat_type": self.chat_type,
            "raw_session_ref": self.raw_session_ref,
            "session_id": self.session_id,
            "last_message_id": self.last_message_id,
            "last_seen_at": self.last_seen_at,
            "last_started_at": self.last_started_at,
            "last_finished_at": self.last_finished_at,
            "in_flight": self.in_flight,
            "message_count": self.message_count,
            "last_delivered_count": self.last_delivered_count,
            "last_error": self.last_error,
            "metadata": dict(self.metadata),
        }


__all__ = ["WeixinConversationSession"]
