from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from agents_os.contracts import Invocation
from .interaction import extract_message_attachments, extract_message_text


_ENTRYPOINT_ALIASES = {
    "chat": "chat",
    "default": "chat",
    "talk": "chat",
}
_MISSION_ROUTE_ALIASES = {"mission", "mission_ingress"}


class FeishuInputAdapter:
    """Map raw Feishu events into the neutral Invocation contract."""

    platform = "feishu"

    def build_invocation(
        self,
        event: Mapping[str, Any] | None,
        *,
        entrypoint_hint: str = "",
        metadata_overrides: Mapping[str, Any] | None = None,
    ) -> Invocation:
        normalized = self.normalize_event(event)
        metadata = dict(normalized["metadata"])
        if isinstance(metadata_overrides, Mapping):
            metadata.update(dict(metadata_overrides))
        explicit_route_hint = str(entrypoint_hint or "").strip().lower()
        if explicit_route_hint in _MISSION_ROUTE_ALIASES:
            metadata["route_hint"] = "mission"
        entrypoint = self._resolve_entrypoint(
            hint=entrypoint_hint,
            metadata=metadata,
            user_text=str(normalized["user_text"]),
        )
        source_event_id = str(metadata.get("feishu.message_id") or normalized.get("source_event_id") or "").strip()
        return Invocation(
            entrypoint=entrypoint,
            channel=self.platform,
            session_id=str(normalized["session_id"]),
            actor_id=str(normalized["actor_id"]),
            user_text=str(normalized["user_text"]),
            attachments=list(normalized["attachments"]),
            metadata=metadata,
            timestamp=str(normalized["timestamp"]) or None,
            source_event_id=source_event_id,
        )

    def normalize_event(self, event: Mapping[str, Any] | None) -> dict[str, Any]:
        root = dict(event or {})
        event_body = root.get("event") if isinstance(root.get("event"), Mapping) else root
        event_body = dict(event_body or {})
        message = event_body.get("message") if isinstance(event_body.get("message"), Mapping) else {}
        sender = event_body.get("sender") if isinstance(event_body.get("sender"), Mapping) else {}
        sender_id = sender.get("sender_id") if isinstance(sender.get("sender_id"), Mapping) else {}
        user_text = self._extract_user_text(message)
        attachments = self._extract_attachments(message)
        source_event_id = self._first_non_empty(
            message.get("message_id"),
            event_body.get("open_message_id"),
            root.get("message_id"),
        )
        metadata = {
            "feishu.chat_id": self._first_non_empty(
                message.get("chat_id"),
                event_body.get("chat_id"),
                root.get("chat_id"),
            ),
            "feishu.chat_type": self._first_non_empty(
                message.get("chat_type"),
                event_body.get("chat_type"),
                root.get("chat_type"),
            ),
            "feishu.event_type": self._first_non_empty(
                root.get("header", {}).get("event_type") if isinstance(root.get("header"), Mapping) else "",
                root.get("event_type"),
            ),
            "feishu.message_id": source_event_id,
            "feishu.message_type": self._first_non_empty(message.get("message_type"), root.get("message_type")),
            "feishu.receive_id": self._first_non_empty(
                sender_id.get("open_id"),
                sender_id.get("user_id"),
                event_body.get("open_id"),
                root.get("open_id"),
            ),
            "feishu.receive_id_type": "open_id",
            "feishu.raw_session_ref": self._first_non_empty(
                message.get("thread_id"),
                message.get("root_id"),
                message.get("chat_id"),
                message.get("message_id"),
                root.get("session_id"),
            ),
            "route_hint": self._detect_route_hint(user_text, root, event_body),
        }
        return {
            "actor_id": self._first_non_empty(
                sender_id.get("open_id"),
                sender_id.get("user_id"),
                sender.get("sender_type"),
                event_body.get("operator_id"),
                "unknown_actor",
            ),
            "attachments": attachments,
            "metadata": {key: value for key, value in metadata.items() if str(value or "").strip()},
            "session_id": self._first_non_empty(
                message.get("thread_id"),
                message.get("root_id"),
                message.get("chat_id"),
                message.get("message_id"),
                root.get("session_id"),
                "unknown_session",
            ),
            "source_event_id": source_event_id,
            "timestamp": self._first_non_empty(
                event_body.get("create_time"),
                root.get("timestamp"),
                root.get("ts"),
            ),
            "user_text": user_text,
        }

    def _resolve_entrypoint(
        self,
        *,
        hint: str,
        metadata: Mapping[str, Any],
        user_text: str,
    ) -> str:
        route_hint = str(metadata.get("route_hint") or "").strip().lower()
        for candidate in (hint, route_hint):
            normalized = _ENTRYPOINT_ALIASES.get(str(candidate or "").strip().lower())
            if normalized:
                return normalized
        return self._detect_route_hint(user_text, metadata, metadata) or "chat"

    def _detect_route_hint(
        self,
        user_text: str,
        raw_event: Mapping[str, Any],
        event_body: Mapping[str, Any],
    ) -> str:
        text = str(user_text or "").strip()
        raw_hint = self._first_non_empty(
            raw_event.get("route_hint"),
            event_body.get("route_hint"),
            raw_event.get("entrypoint"),
            event_body.get("entrypoint"),
        )
        if str(raw_hint or "").strip().lower() in _MISSION_ROUTE_ALIASES:
            return "mission"
        return _ENTRYPOINT_ALIASES.get(str(raw_hint or "").strip().lower(), "chat")

    def _extract_user_text(self, message: Mapping[str, Any]) -> str:
        raw_content = message.get("content")
        text = extract_message_text(raw_content)
        if text:
            return text
        if isinstance(raw_content, Mapping):
            return json.dumps(dict(raw_content), ensure_ascii=False)
        if isinstance(raw_content, str):
            return raw_content.strip()
        return ""

    def _extract_attachments(self, message: Mapping[str, Any]) -> list[str]:
        return extract_message_attachments(message.get("content"))

    @staticmethod
    def _first_non_empty(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""


__all__ = ["FeishuInputAdapter"]
