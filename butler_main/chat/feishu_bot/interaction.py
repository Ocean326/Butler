from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping
from typing import Any


def parse_message_content(raw_content: Any) -> dict[str, Any]:
    if isinstance(raw_content, Mapping):
        return dict(raw_content)
    if isinstance(raw_content, str):
        stripped = raw_content.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
        except Exception:
            return {"text": stripped}
        if isinstance(parsed, Mapping):
            return dict(parsed)
        return {"text": stripped}
    return {}


def extract_message_text(raw_content: Any) -> str:
    content = parse_message_content(raw_content)
    text = str(content.get("text") or "").strip()
    rich_text = extract_feishu_rich_text(content)
    quote_text = extract_feishu_quote_text(content)
    if quote_text and quote_text not in text:
        text = (f"【引用内容】\n{quote_text}\n\n{text}" if text else f"【引用内容】\n{quote_text}").strip()
    if rich_text and rich_text not in text:
        text = (f"{text}\n\n{rich_text}" if text else rich_text).strip()
    return text


def extract_message_attachments(raw_content: Any) -> list[str]:
    content = parse_message_content(raw_content)
    attachments: list[str] = []
    for key in ("image_key", "file_key", "media_id"):
        value = str(content.get(key) or "").strip()
        if value:
            attachments.append(value)
    for row in content.get("content") or []:
        for item in row if isinstance(row, list) else [row]:
            if not isinstance(item, Mapping):
                continue
            ref = _first_non_empty(item.get("image_key"), item.get("file_key"), item.get("token"), item.get("url"))
            if ref:
                attachments.append(ref)
    for item in content.get("attachments") or []:
        if not isinstance(item, Mapping):
            continue
        ref = _first_non_empty(item.get("file_key"), item.get("image_key"), item.get("token"), item.get("url"))
        if ref:
            attachments.append(ref)
    return _dedupe_values(attachments)


def extract_message_image_keys(raw_content: Any) -> list[str]:
    content = parse_message_content(raw_content)
    image_keys: list[str] = []
    direct_key = str(content.get("image_key") or "").strip()
    if direct_key:
        image_keys.append(direct_key)
    for row in content.get("content") or []:
        for item in row if isinstance(row, list) else [row]:
            if not isinstance(item, Mapping):
                continue
            image_key = str(item.get("image_key") or "").strip()
            if image_key:
                image_keys.append(image_key)
    return _dedupe_values(image_keys)


def extract_feishu_rich_text(content: Mapping[str, Any] | None) -> str:
    lines: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if not isinstance(node, Mapping):
            return
        tag = str(node.get("tag") or "").strip().lower()
        text = str(node.get("text") or "").strip()
        if tag in {"text", "plain_text"} and text:
            lines.append(text)
        elif tag == "a" and text:
            href = str(node.get("href") or "").strip()
            lines.append(f"{text} ({href})" if href else text)
        elif tag == "at" and text:
            lines.append(f"@{text.lstrip('@')}")
        for key in ("content", "children", "elements"):
            child = node.get(key)
            if isinstance(child, (list, Mapping)):
                _walk(child)

    _walk(content.get("content") if isinstance(content, Mapping) else None)
    rendered = "\n".join(part.strip() for part in lines if part.strip()).strip()
    return rendered[:2000]


def extract_feishu_quote_text(content: Mapping[str, Any] | None) -> str:
    candidates: list[str] = []

    def _walk(node: Any, *, depth: int = 0, under_quote: bool = False) -> None:
        if depth > 6:
            return
        if isinstance(node, list):
            for item in node:
                _walk(item, depth=depth + 1, under_quote=under_quote)
            return
        if not isinstance(node, Mapping):
            return
        keys = {str(key).lower() for key in node.keys()}
        tag = str(node.get("tag") or "").strip().lower()
        current_under_quote = under_quote or tag in {"quote", "blockquote"} or any(
            key in keys for key in {"quote", "quoted", "reply", "reference", "parent_message", "root_message"}
        )
        text = str(node.get("text") or "").strip()
        if current_under_quote and text:
            candidates.append(text)
        for value in node.values():
            if isinstance(value, (list, Mapping)):
                _walk(value, depth=depth + 1, under_quote=current_under_quote)

    _walk(content if isinstance(content, Mapping) else {})
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = re.sub(r"\s+", " ", item).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return "\n".join(deduped[:6])[:1600]


def build_message_receive_payload(data: Any) -> dict[str, Any]:
    event = _read_field(data, "event", data)
    message = _read_field(event, "message", None)
    sender = _read_field(event, "sender", None)
    sender_id = _read_field(sender, "sender_id", None)
    header = _read_field(data, "header", None)
    return {
        "event": {
            "message": {
                "message_id": str(_read_field(message, "message_id", "") or ""),
                "chat_id": str(_read_field(message, "chat_id", "") or ""),
                "chat_type": str(_read_field(message, "chat_type", "") or ""),
                "message_type": str(_read_field(message, "message_type", "") or ""),
                "content": _read_field(message, "content", "{}") or "{}",
                "root_id": str(_read_field(message, "root_id", "") or ""),
                "thread_id": str(_read_field(message, "thread_id", "") or ""),
            },
            "sender": {
                "sender_id": {
                    "open_id": str(_read_field(sender_id, "open_id", "") or ""),
                    "user_id": str(_read_field(sender_id, "user_id", "") or ""),
                },
                "sender_type": str(_read_field(sender, "sender_type", "") or ""),
            },
            "open_message_id": str(_read_field(event, "open_message_id", "") or ""),
        },
        "header": {
            "event_id": str(_read_field(header, "event_id", "") or ""),
            "event_type": str(_read_field(header, "event_type", "") or ""),
        },
    }


def extract_inbound_message_event(data: Any) -> dict[str, Any]:
    payload = build_message_receive_payload(data)
    header = payload["header"]
    event = payload["event"]
    message = event["message"]
    sender = event["sender"]
    sender_id = sender["sender_id"]
    event_type = str(header.get("event_type") or "").strip()
    sender_type = str(sender.get("sender_type") or "").strip().lower()
    message_type = str(message.get("message_type") or "").strip().lower()
    raw_content = message.get("content", "{}")
    message_id = str(message.get("message_id") or "").strip()
    session_id = str(message.get("thread_id") or message.get("root_id") or message.get("chat_id") or message_id).strip()
    actor_id = str(sender_id.get("open_id") or sender_id.get("user_id") or "").strip()
    text = extract_message_text(raw_content)
    image_keys = extract_message_image_keys(raw_content)
    return {
        "payload": payload,
        "event_type": event_type,
        "sender_type": sender_type,
        "message_type": message_type,
        "message_id": message_id,
        "session_id": session_id,
        "actor_id": actor_id,
        "text": text,
        "image_keys": image_keys,
        "has_content": bool(text or image_keys),
        "should_process": bool(message_id) and sender_type != "bot" and bool(text or image_keys),
    }


def build_invocation_metadata_from_message(data: Any) -> dict[str, Any]:
    extracted = extract_inbound_message_event(data)
    payload = extracted["payload"]
    message = payload["event"]["message"]
    sender_id = payload["event"]["sender"]["sender_id"]
    message_id = str(extracted["message_id"] or "").strip()
    session_id = str(extracted["session_id"] or "").strip()
    actor_id = str(extracted["actor_id"] or "").strip()
    metadata = {
        "feishu_event": payload,
        "message_id": message_id,
        "session_id": session_id,
        "actor_id": actor_id,
        "channel": "feishu",
    }
    if actor_id:
        metadata["feishu.receive_id"] = actor_id
        metadata["feishu.receive_id_type"] = "open_id" if str(sender_id.get("open_id") or "").strip() else "user_id"
    if message_id:
        metadata["feishu.message_id"] = message_id
    chat_id = str(message.get("chat_id") or "").strip()
    if chat_id:
        metadata["feishu.chat_id"] = chat_id
    if session_id:
        metadata["feishu.raw_session_ref"] = session_id
    root_id = str(message.get("root_id") or "").strip()
    if root_id:
        metadata["feishu.root_id"] = root_id
    return metadata


def extract_card_action_payload(data: Any) -> dict[str, Any]:
    event = _read_field(data, "event", data)
    header = _read_field(data, "header", None)
    action = _read_field(event, "action", None)
    context = _read_field(event, "context", None)
    operator = _read_field(event, "operator", None)

    raw_value = _read_field(action, "value", {}) or {}
    value = dict(raw_value) if isinstance(raw_value, Mapping) else {}
    raw_form_value = _read_field(action, "form_value", {}) or {}
    form_value = dict(raw_form_value) if isinstance(raw_form_value, Mapping) else {}
    input_value = str(_read_field(action, "input_value", "") or "").strip()
    action_name = str(_read_field(action, "name", "") or "").strip()
    cmd = str(value.get("cmd") or value.get("action") or action_name or "").strip().lower()
    event_id = str(_read_field(header, "event_id", "") or "").strip()
    open_message_id = str(_read_field(context, "open_message_id", "") or "").strip()
    open_chat_id = str(_read_field(context, "open_chat_id", "") or "").strip()
    open_id = str(_read_field(operator, "open_id", "") or "").strip()
    user_id = str(_read_field(operator, "user_id", "") or "").strip()
    route_hint = str(value.get("entrypoint") or value.get("route_hint") or value.get("route") or "").strip().lower()
    delivery_mode = str(value.get("delivery_mode") or "").strip().lower()

    return {
        "event_id": event_id,
        "dedup_id": f"card-action:{event_id}" if event_id else f"card-action:{int(time.time() * 1000)}",
        "open_message_id": open_message_id,
        "open_chat_id": open_chat_id,
        "open_id": open_id,
        "user_id": user_id,
        "cmd": cmd,
        "action_name": action_name,
        "value": value,
        "form_value": form_value,
        "input_value": input_value,
        "route_hint": route_hint,
        "delivery_mode": delivery_mode,
    }


def build_card_action_prompt(payload: Mapping[str, Any]) -> str:
    cmd = str(payload.get("cmd") or "").strip().lower()
    value = payload.get("value") or {}
    form_value = payload.get("form_value") or {}
    input_value = str(payload.get("input_value") or "").strip()

    manual_prompt = str((value.get("prompt") if isinstance(value, Mapping) else "") or "").strip()
    if not manual_prompt and isinstance(form_value, Mapping):
        manual_prompt = str(form_value.get("prompt") or "").strip()
    if manual_prompt:
        return manual_prompt

    if cmd == "continue":
        return "请基于你上一条回复继续展开，优先补充可执行步骤、风险点和下一步建议。"
    if cmd == "todo":
        return "请把你上一条回复整理成任务清单，按优先级给出可直接执行的 TODO。"
    if cmd == "brief":
        return "请用一句话总结你上一条回复，并给一个最关键行动建议。"

    context_lines = [
        "用户触发了卡片交互动作，请你自行判断并给出最合适的回复。",
        f"动作标识: {cmd or 'unknown'}",
    ]
    if input_value:
        context_lines.append(f"用户输入: {input_value}")
    if isinstance(form_value, Mapping) and form_value:
        context_lines.append(f"表单参数: {json.dumps(dict(form_value), ensure_ascii=False)}")
    if isinstance(value, Mapping) and value:
        context_lines.append(f"动作参数: {json.dumps(dict(value), ensure_ascii=False)}")
    return "\n".join(context_lines)


def build_card_action_invocation_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    message_id = str(payload.get("open_message_id") or "").strip()
    session_id = str(payload.get("open_chat_id") or message_id).strip()
    actor_id = str(payload.get("open_id") or payload.get("user_id") or "").strip()
    target_type = "open_id" if str(payload.get("open_id") or "").strip() else "user_id"
    metadata = {
        "channel": "feishu",
        "message_id": message_id,
        "session_id": session_id,
        "actor_id": actor_id,
        "entrypoint_hint": str(payload.get("route_hint") or "chat").strip() or "chat",
        "card_action": dict(payload),
    }
    if message_id:
        metadata["feishu.message_id"] = message_id
    if actor_id:
        metadata["feishu.receive_id"] = actor_id
        metadata["feishu.receive_id_type"] = target_type
    chat_id = str(payload.get("open_chat_id") or "").strip()
    if chat_id:
        metadata["feishu.chat_id"] = chat_id
    if session_id:
        metadata["feishu.raw_session_ref"] = session_id
    delivery_mode = str(payload.get("delivery_mode") or "").strip().lower()
    if delivery_mode:
        metadata["delivery_mode"] = delivery_mode
        metadata["feishu.delivery_mode"] = delivery_mode
    return metadata


def _dedupe_values(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _read_field(node: Any, key: str, default: Any = "") -> Any:
    if isinstance(node, Mapping):
        return node.get(key, default)
    return getattr(node, key, default)


__all__ = [
    "build_card_action_invocation_metadata",
    "build_card_action_prompt",
    "build_invocation_metadata_from_message",
    "build_message_receive_payload",
    "extract_card_action_payload",
    "extract_feishu_quote_text",
    "extract_feishu_rich_text",
    "extract_inbound_message_event",
    "extract_message_attachments",
    "extract_message_image_keys",
    "extract_message_text",
    "parse_message_content",
]
