from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from typing import Any

import lark_oapi as lark

from .interaction import (
    build_card_action_invocation_metadata,
    build_card_action_prompt,
    build_invocation_metadata_from_message,
    extract_card_action_payload,
    extract_inbound_message_event,
)


def build_card_action_response(message: str, *, toast_type: str = "info"):
    return {
        "toast": {
            "type": toast_type,
            "content": (message or "已收到").strip()[:120],
        }
    }


def build_chat_feishu_event_dispatcher(
    *,
    run_agent_fn: Callable[..., str],
    supports_images: bool,
    supports_stream_segment: bool,
    send_output_files: bool,
    on_reply_sent: Callable[[str, str], None] | None,
    immediate_receipt_text: str | None,
    deliver_output_bundle_fn: Callable[..., bool] | None,
    handle_card_control_fn: Callable[[dict[str, Any]], dict[str, Any] | None] | None,
    handle_message_async_fn: Callable[..., None],
    reply_message_fn: Callable[..., bool],
):
    def _on_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        extracted = extract_inbound_message_event(data)
        message_id = str(extracted.get("message_id") or "").strip()
        try:
            if str(extracted.get("sender_type") or "") == "bot":
                print(f"[收到] 跳过 bot sender message_id={message_id[:20]}...", flush=True)
                return
            if not message_id:
                return
            text = str(extracted.get("text") or "").strip()
            image_keys = list(extracted.get("image_keys") or [])
            if not text and not image_keys:
                return
            preview = text or "（用户发送了图片，请分析并回复）"
            print(f"[收到] message_id={message_id[:20]}..., text={preview[:50] if preview else '(图片)'}..., images={len(image_keys)}", flush=True)
            handle_message_async_fn(
                message_id,
                preview,
                image_keys,
                run_agent_fn,
                supports_images=supports_images,
                supports_stream_segment=supports_stream_segment,
                send_output_files=send_output_files,
                on_reply_sent=on_reply_sent,
                immediate_receipt_text=immediate_receipt_text,
                invocation_metadata=build_invocation_metadata_from_message(data),
                deliver_output_bundle_fn=deliver_output_bundle_fn,
            )
        except Exception as exc:
            print(f"处理消息异常: {exc}", file=sys.stderr)
            try:
                if message_id:
                    reply_message_fn(message_id, f"处理异常: {exc}", use_interactive=False)
            except Exception:
                pass

    def _on_card_action(data: lark.cardkit.v1.P2CardActionTrigger):
        payload = extract_card_action_payload(data)
        message_id = str(payload.get("open_message_id") or "").strip()
        cmd = str(payload.get("cmd") or "").strip() or "(unknown)"
        if callable(handle_card_control_fn):
            try:
                control_result = handle_card_control_fn(payload)
            except Exception as exc:
                print(f"[卡片交互] control action failed: {exc}", flush=True)
                control_result = {"handled": True, "message": f"动作处理失败：{exc}", "toast_type": "warning"}
            if isinstance(control_result, Mapping) and control_result.get("handled"):
                return build_card_action_response(
                    str(control_result.get("message") or "已收到").strip() or "已收到",
                    toast_type=str(control_result.get("toast_type") or "info").strip() or "info",
                )
        if not message_id:
            print(f"[卡片交互] 缺少 open_message_id，忽略 cmd={cmd}", flush=True)
            return build_card_action_response("没有找到原消息，已忽略这次点击。", toast_type="warning")

        prompt = build_card_action_prompt(payload)
        print(f"[卡片交互] 收到 cmd={cmd} | message_id={message_id[:20]}...", flush=True)
        handle_message_async_fn(
            message_id,
            prompt,
            None,
            run_agent_fn,
            supports_images=False,
            supports_stream_segment=supports_stream_segment,
            send_output_files=send_output_files,
            on_reply_sent=on_reply_sent,
            dedup_id=str(payload.get("dedup_id") or ""),
            immediate_receipt_text=immediate_receipt_text,
            invocation_metadata=build_card_action_invocation_metadata(payload),
            deliver_output_bundle_fn=deliver_output_bundle_fn,
        )
        return build_card_action_response(f"已收到「{cmd}」，正在处理。")

    return (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(_on_message)
        .register_p2_card_action_trigger(_on_card_action)
        .build()
    )


__all__ = ["build_card_action_response", "build_chat_feishu_event_dispatcher"]
