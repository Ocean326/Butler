from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from agents_os.contracts import Invocation


_ENTRYPOINT_ALIASES = {
    "chat": "chat",
    "default": "chat",
    "talk": "chat",
}
_MISSION_ROUTE_ALIASES = {"mission", "mission_ingress"}
_GROUP_CHAT_TYPE_ALIASES = {"group", "group_chat", "room", "chatroom"}


class WeixinInputAdapter:
    """Map OpenClaw/Weixin-shaped events into the neutral Invocation contract."""

    platform = "weixin"

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
        source_event_id = str(metadata.get("weixin.message_id") or normalized.get("source_event_id") or "").strip()
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
        message = root.get("message") if isinstance(root.get("message"), Mapping) else root
        message = dict(message or {})
        sender = root.get("sender") if isinstance(root.get("sender"), Mapping) else {}
        content = message.get("content") if isinstance(message.get("content"), Mapping) else {}
        item_list = message.get("item_list") if isinstance(message.get("item_list"), list) else []

        user_text = self._extract_user_text(message)
        attachments = self._extract_attachments(message)
        source_event_id = self._first_non_empty(
            message.get("message_id"),
            root.get("message_id"),
            root.get("event_id"),
        )
        actor_id = self._first_non_empty(
            message.get("from_user_id"),
            sender.get("open_id"),
            sender.get("user_id"),
            root.get("from_user_id"),
            root.get("open_id"),
            "unknown_actor",
        )
        raw_session_ref = self._first_non_empty(
            message.get("session_id"),
            message.get("conversation_id"),
            root.get("session_id"),
            root.get("conversation_id"),
            source_event_id,
            "unknown_session",
        )
        account_id = self._first_non_empty(
            root.get("account_id"),
            root.get("accountId"),
            message.get("to_user_id"),
            root.get("to_user_id"),
        )
        chat_type = self._resolve_chat_type(root, message)
        conversation_key = self._build_conversation_key(
            account_id=account_id,
            actor_id=actor_id,
            chat_type=chat_type,
            message=message,
            root=root,
            raw_session_ref=raw_session_ref,
        )
        session_id = conversation_key or raw_session_ref
        receive_id = self._first_non_empty(
            message.get("from_user_id"),
            sender.get("open_id"),
            sender.get("user_id"),
            root.get("from_user_id"),
            root.get("open_id"),
        )
        metadata = {
            "weixin.account_id": account_id,
            "weixin.chat_type": chat_type,
            "weixin.conversation_key": conversation_key,
            "weixin.context_token": self._first_non_empty(message.get("context_token"), root.get("context_token")),
            "weixin.message_id": source_event_id,
            "weixin.message_type": self._first_non_empty(message.get("message_type"), root.get("message_type")),
            "weixin.receive_id": receive_id,
            "weixin.receive_id_type": "open_id",
            "weixin.raw_session_ref": raw_session_ref,
            "weixin.to_user_id": self._first_non_empty(message.get("to_user_id"), root.get("to_user_id")),
            "weixin.transport": self._first_non_empty(root.get("transport"), "openclaw-http-json"),
            "route_hint": self._detect_route_hint(
                user_text,
                hint=self._first_non_empty(root.get("route_hint"), root.get("entrypoint")),
            ),
        }
        if item_list:
            metadata["weixin.item_count"] = str(len(item_list))
        if content:
            metadata["weixin.content_kind"] = ",".join(sorted(content.keys()))
        return {
            "actor_id": actor_id,
            "attachments": attachments,
            "metadata": {key: value for key, value in metadata.items() if str(value or "").strip()},
            "session_id": session_id,
            "source_event_id": source_event_id,
            "timestamp": self._first_non_empty(
                message.get("create_time_ms"),
                root.get("create_time_ms"),
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
        for candidate in (hint, metadata.get("route_hint")):
            normalized = _ENTRYPOINT_ALIASES.get(str(candidate or "").strip().lower())
            if normalized:
                return normalized
        if str(user_text or "").strip():
            return "chat"
        return "chat"

    @staticmethod
    def _detect_route_hint(user_text: str, *, hint: str) -> str:
        if str(hint or "").strip().lower() in _MISSION_ROUTE_ALIASES:
            return "mission"
        normalized_hint = _ENTRYPOINT_ALIASES.get(str(hint or "").strip().lower())
        if normalized_hint:
            return normalized_hint
        if str(user_text or "").strip():
            return "chat"
        return "chat"

    def _extract_user_text(self, message: Mapping[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, Mapping):
            text = str(content.get("text") or "").strip()
            if text:
                return text
        for item in list(message.get("item_list") or []):
            if not isinstance(item, Mapping):
                continue
            item_type = int(item.get("type") or 0)
            if item_type == 1:
                text_item = item.get("text_item") if isinstance(item.get("text_item"), Mapping) else {}
                text = str(text_item.get("text") or "").strip()
                if text:
                    return text
            if item_type == 3:
                voice_item = item.get("voice_item") if isinstance(item.get("voice_item"), Mapping) else {}
                text = str(voice_item.get("text") or "").strip()
                if text:
                    return text
        if isinstance(content, Mapping):
            return json.dumps(dict(content), ensure_ascii=False)
        if isinstance(content, str):
            return content.strip()
        return ""

    @staticmethod
    def _extract_attachments(message: Mapping[str, Any]) -> list[str]:
        attachments: list[str] = []
        for item in list(message.get("item_list") or []):
            if not isinstance(item, Mapping):
                continue
            item_type = int(item.get("type") or 0)
            if item_type == 2:
                attachments.append("image")
            elif item_type == 4:
                attachments.append("file")
            elif item_type == 5:
                attachments.append("video")
        return attachments

    def _resolve_chat_type(self, root: Mapping[str, Any], message: Mapping[str, Any]) -> str:
        explicit = self._first_non_empty(
            message.get("chat_type"),
            root.get("chat_type"),
            message.get("chatType"),
            root.get("chatType"),
        ).lower()
        if explicit in _GROUP_CHAT_TYPE_ALIASES:
            return "group"
        if explicit == "dm":
            return "dm"
        if self._resolve_chat_id(root, message):
            return "group"
        return "dm"

    def _build_conversation_key(
        self,
        *,
        account_id: str,
        actor_id: str,
        chat_type: str,
        message: Mapping[str, Any],
        root: Mapping[str, Any],
        raw_session_ref: str,
    ) -> str:
        normalized_account_id = str(account_id or "unknown_account").strip() or "unknown_account"
        if chat_type == "group":
            chat_id = self._resolve_chat_id(root, message) or raw_session_ref or actor_id or "unknown_group"
            return f"weixin:{normalized_account_id}:group:{chat_id}"
        normalized_actor_id = str(actor_id or "unknown_actor").strip() or "unknown_actor"
        return f"weixin:{normalized_account_id}:dm:{normalized_actor_id}"

    def _resolve_chat_id(self, root: Mapping[str, Any], message: Mapping[str, Any]) -> str:
        return self._first_non_empty(
            message.get("chat_id"),
            message.get("room_id"),
            message.get("group_id"),
            root.get("chat_id"),
            root.get("room_id"),
            root.get("group_id"),
        )

    @staticmethod
    def _first_non_empty(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""


__all__ = ["WeixinInputAdapter"]
