from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(WORKSPACE_ROOT))

from butler_main.chat.feishu_bot import transport
from butler_main.chat.feishu_bot.rendering import markdown_to_feishu_post, markdown_to_interactive_card


def _mask(value: str, head: int = 6, tail: int = 4) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    if len(raw) <= head + tail:
        return raw[:head] + "***"
    return f"{raw[:head]}***{raw[-tail:]}"


def _compact(obj):
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            lowered = str(key).lower()
            if isinstance(value, str) and ("token" in lowered or lowered.endswith("id") or "key" in lowered):
                result[key] = _mask(value)
            else:
                result[key] = _compact(value)
        return result
    if isinstance(obj, list):
        return [_compact(item) for item in obj[:10]]
    return obj


def _load_runtime() -> tuple[dict, str, str, str]:
    config_path = transport._resolve_default_config_path("butler_bot")
    cfg = transport.load_config(config_path)
    transport.CONFIG.clear()
    transport.CONFIG.update(cfg)
    transport.CONFIG["__config_path"] = os.path.abspath(config_path)
    transport._sync_feishu_runtime_state(cfg)
    target_id = str(cfg.get("tell_user_receive_id") or cfg.get("startup_notify_open_id") or "").strip()
    target_type = str(cfg.get("tell_user_receive_id_type") or cfg.get("startup_notify_receive_id_type") or "open_id").strip() or "open_id"
    if not target_id:
        raise RuntimeError("missing tell_user_receive_id/startup_notify_open_id in config")
    return cfg, config_path, target_id, target_type


def _extract_first_message(detail_payload: dict) -> dict:
    items = ((detail_payload.get("data") or {}).get("items") or [])
    return items[0] if items else {}


def _verify_message(client, message_id: str, *, expected_msg_type: str | None = None, chat_id: str = "") -> dict:
    ok_get, detail_payload = client.get_message(message_id)
    detail_item = _extract_first_message(detail_payload)
    resolved_chat_id = str(chat_id or detail_item.get("chat_id") or "").strip()
    result = {
        "message_id": _mask(message_id),
        "get_ok": ok_get,
        "detail_msg_type": detail_item.get("msg_type"),
        "detail_chat_id": _mask(resolved_chat_id),
        "detail_found": bool(detail_item),
        "recent_ok": False,
        "recent_found": False,
        "recent_count": 0,
    }
    if expected_msg_type:
        result["msg_type_match"] = detail_item.get("msg_type") == expected_msg_type
    if not resolved_chat_id:
        return result
    ok_list, list_payload = client.list_messages(container_id=resolved_chat_id, container_id_type="chat", page_size=10)
    items = ((list_payload.get("data") or {}).get("items") or [])
    result["recent_ok"] = ok_list
    result["recent_count"] = len(items)
    result["recent_found"] = any(str((item or {}).get("message_id") or "") == message_id for item in items)
    return result


def _send_direct_cases(client, target_id: str, target_type: str) -> list[dict]:
    cases = [
        ("text", "text", {"text": "[VERIFY] direct text"}),
        ("post", "post", markdown_to_feishu_post("## [VERIFY] post\n- direct send")),
        (
            "interactive",
            "interactive",
            markdown_to_interactive_card("## [VERIFY] interactive\n- direct send\n- schema v2"),
        ),
    ]
    results: list[dict] = []
    for name, msg_type, content_payload in cases:
        ok_send, send_payload = client.send_raw_message(target_id, target_type, msg_type, content_payload)
        data = send_payload.get("data") or {}
        message_id = str(data.get("message_id") or "").strip()
        chat_id = str(data.get("chat_id") or "").strip()
        verification = _verify_message(client, message_id, expected_msg_type=msg_type, chat_id=chat_id) if message_id else {}
        results.append(
            {
                "case": name,
                "send_ok": ok_send,
                "send_code": send_payload.get("code"),
                "send_msg": send_payload.get("msg"),
                "message_id": _mask(message_id),
                "chat_id": _mask(chat_id),
                "verification": verification,
            }
        )
    return results


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, args=None, kwargs=None):
        self._target = target
        self._args = tuple(args or ())
        self._kwargs = dict(kwargs or {})

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


def _run_stream_case(client, target_id: str, target_type: str, *, name: str, run_agent_fn) -> dict:
    ok_anchor, anchor_payload = client.send_raw_message(
        target_id,
        target_type,
        "text",
        {"text": f"[VERIFY] {name} anchor"},
    )
    anchor_data = anchor_payload.get("data") or {}
    anchor_message_id = str(anchor_data.get("message_id") or "").strip()
    anchor_chat_id = str(anchor_data.get("chat_id") or "").strip()
    reply_records: list[dict] = []
    update_records: list[dict] = []
    original_reply_raw_message = transport._API_CLIENT.reply_raw_message
    original_update_raw_message = transport._API_CLIENT.update_raw_message
    original_thread = transport.threading.Thread

    def _wrapped_reply_raw_message(message_id: str, msg_type: str, content_payload: dict, *, timeout: int = 15):
        ok, payload = original_reply_raw_message(message_id, msg_type, content_payload, timeout=timeout)
        reply_data = payload.get("data") or {}
        reply_records.append(
            {
                "ok": ok,
                "attempt_msg_type": msg_type,
                "reply_message_id": str(reply_data.get("message_id") or "").strip(),
                "reply_chat_id": str(reply_data.get("chat_id") or "").strip(),
                "code": payload.get("code"),
                "msg": payload.get("msg"),
            }
        )
        return ok, payload

    def _wrapped_update_raw_message(message_id: str, msg_type: str, content_payload: dict, *, timeout: int = 15):
        ok, payload = original_update_raw_message(message_id, msg_type, content_payload, timeout=timeout)
        preview = ""
        if msg_type == "interactive":
            try:
                preview = str((((content_payload.get("body") or {}).get("elements") or [{}])[0].get("content") or "")).replace("\n", " ")[:120]
            except Exception:
                preview = ""
        update_records.append(
            {
                "ok": ok,
                "attempt_msg_type": msg_type,
                "message_id": message_id,
                "code": payload.get("code"),
                "msg": payload.get("msg"),
                "preview": preview,
            }
        )
        return ok, payload

    transport._API_CLIENT.reply_raw_message = _wrapped_reply_raw_message
    transport._API_CLIENT.update_raw_message = _wrapped_update_raw_message
    transport.threading.Thread = _ImmediateThread
    try:
        transport.handle_message_async(
            message_id=anchor_message_id,
            prompt=f"{name} verify",
            image_keys=None,
            run_agent_fn=run_agent_fn,
            supports_images=False,
            supports_stream_segment=True,
            send_output_files=False,
        )
    finally:
        transport._API_CLIENT.reply_raw_message = original_reply_raw_message
        transport._API_CLIENT.update_raw_message = original_update_raw_message
        transport.threading.Thread = original_thread

    successful_replies = [item for item in reply_records if item.get("ok") and item.get("reply_message_id")]
    last_reply = successful_replies[-1] if successful_replies else {}
    verification = {}
    if last_reply:
        verification = _verify_message(
            client,
            last_reply["reply_message_id"],
            expected_msg_type=last_reply.get("attempt_msg_type"),
            chat_id=last_reply.get("reply_chat_id") or anchor_chat_id,
        )
    return {
        "case": name,
        "anchor_send_ok": ok_anchor,
        "anchor_message_id": _mask(anchor_message_id),
        "anchor_chat_id": _mask(anchor_chat_id),
        "reply_attempts": [
            {
                "ok": item["ok"],
                "attempt_msg_type": item["attempt_msg_type"],
                "reply_message_id": _mask(item["reply_message_id"]),
                "reply_chat_id": _mask(item["reply_chat_id"]),
                "code": item["code"],
                "msg": item["msg"],
            }
            for item in reply_records
        ],
        "update_attempts": [
            {
                "ok": item["ok"],
                "attempt_msg_type": item["attempt_msg_type"],
                "message_id": _mask(item["message_id"]),
                "code": item["code"],
                "msg": item["msg"],
                "preview": item["preview"],
            }
            for item in update_records
        ],
        "verification": verification,
    }


def _run_stream_cases(client, target_id: str, target_type: str) -> list[dict]:
    def _run_stream_final(prompt, stream_callback=None, image_paths=None, invocation_metadata=None):
        del prompt, image_paths, invocation_metadata
        if stream_callback:
            stream_callback("第一段")
            stream_callback("第一段\n第二段")
            stream_callback("第一段\n第二段\n第三段")
        return "[VERIFY] stream final reply"

    def _run_stream_snapshot(prompt, stream_callback=None, image_paths=None, invocation_metadata=None):
        del prompt, image_paths, invocation_metadata
        if stream_callback:
            stream_callback("快照一")
            stream_callback("快照一\n快照二")
            stream_callback("快照一\n快照二\n快照三")
        return ""

    return [
        _run_stream_case(client, target_id, target_type, name="stream_final", run_agent_fn=_run_stream_final),
        _run_stream_case(client, target_id, target_type, name="stream_snapshot", run_agent_fn=_run_stream_snapshot),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Feishu send + readback verification")
    parser.add_argument(
        "--cases",
        default="direct,stream",
        help="comma-separated cases: direct,stream",
    )
    args = parser.parse_args()

    _, config_path, target_id, target_type = _load_runtime()
    client = transport._API_CLIENT
    requested_cases = {item.strip() for item in str(args.cases or "").split(",") if item.strip()}
    summary = {
        "config_path": config_path,
        "target_id": _mask(target_id),
        "target_type": target_type,
        "cases": [],
    }
    if "direct" in requested_cases:
        summary["cases"].extend(_send_direct_cases(client, target_id, target_type))
    if "stream" in requested_cases:
        summary["cases"].extend(_run_stream_cases(client, target_id, target_type))
    print(json.dumps(_compact(summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
