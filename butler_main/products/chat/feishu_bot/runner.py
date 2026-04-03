from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from agents_os.contracts import DeliverySession, OutputBundle
from . import transport as transport_module
from .presentation import ChatFeishuPresentationService


def _resolve_delivery_asset_path(asset_path: str, workspace: str) -> str:
    path_text = str(asset_path or "").strip()
    if not path_text:
        return ""
    candidate = Path(path_text)
    if not candidate.is_absolute():
        candidate = transport_module.resolve_butler_root(workspace) / candidate
    try:
        candidate = candidate.resolve()
    except Exception:
        pass
    return str(candidate) if candidate.is_file() else ""


def _get_run_agent_delivery_state(run_agent_fn: Callable[..., str]) -> tuple[OutputBundle | None, DeliverySession | None]:
    output_bundle = None
    delivery_session = None
    output_bundle_getter = getattr(run_agent_fn, "get_turn_output_bundle", None)
    if callable(output_bundle_getter):
        try:
            output_bundle = output_bundle_getter()
        except Exception as exc:
            print(f"[chat-delivery] get_turn_output_bundle failed: {exc}", flush=True)
    delivery_session_getter = getattr(run_agent_fn, "get_turn_delivery_session", None)
    if callable(delivery_session_getter):
        try:
            delivery_session = delivery_session_getter()
        except Exception as exc:
            print(f"[chat-delivery] get_turn_delivery_session failed: {exc}", flush=True)
    if not isinstance(output_bundle, OutputBundle):
        output_bundle = None
    if not isinstance(delivery_session, DeliverySession):
        delivery_session = None
    return output_bundle, delivery_session


def _delivery_result_has_transport_effect(delivery_result) -> bool:
    if not delivery_result:
        return False
    if bool(getattr(delivery_result, "delivered", False)):
        return True
    for entry in list(getattr(delivery_result, "log", []) or []):
        if "_delivered:" in str(entry or ""):
            return True
    return False


def _build_chat_presentation_service(workspace: str) -> ChatFeishuPresentationService:
    def _upload_image_for_delivery(path_text: str) -> str:
        resolved = _resolve_delivery_asset_path(path_text, workspace)
        return str(transport_module.upload_image(resolved) or "") if resolved else ""

    def _upload_file_for_delivery(path_text: str) -> str:
        resolved = _resolve_delivery_asset_path(path_text, workspace)
        return str(transport_module.upload_file(resolved) or "") if resolved else ""

    return ChatFeishuPresentationService(
        send_reply_text_fn=lambda reply_message_id, text, include_card_actions: transport_module.reply_message(
            reply_message_id,
            text,
            use_interactive=True,
            include_card_actions=include_card_actions,
        ),
        send_push_text_fn=lambda target, text, target_type: transport_module._send_private_text_message(target, text, target_type),
        upload_image_fn=_upload_image_for_delivery,
        reply_image_fn=transport_module.reply_image,
        push_image_fn=transport_module.send_image_by_open_id,
        upload_file_fn=_upload_file_for_delivery,
        reply_file_fn=transport_module.reply_file,
        push_file_fn=transport_module.send_file_by_open_id,
    )


def _prepare_delivery_bundle(output_bundle: OutputBundle, *, send_text: bool) -> OutputBundle:
    if send_text:
        return output_bundle
    return replace(
        output_bundle,
        text_blocks=[],
        cards=[],
        doc_links=[],
    )


def deliver_chat_turn_output_bundle(
    message_id: str,
    run_agent_fn: Callable[..., str],
    workspace: str,
    *,
    send_text: bool = True,
) -> bool:
    output_bundle, delivery_session = _get_run_agent_delivery_state(run_agent_fn)
    if output_bundle is None:
        print("[chat-delivery] skipped: no turn output bundle", flush=True)
        return False
    if delivery_session is None:
        print("[chat-delivery] skipped: no delivery session", flush=True)
        return False
    if output_bundle.is_empty():
        print("[chat-delivery] skipped: output bundle is empty", flush=True)
        return False
    if str(delivery_session.platform or "").strip().lower() not in {"", "feishu"}:
        print(f"[chat-delivery] skipped: unsupported platform={delivery_session.platform}", flush=True)
        return False
    delivery_bundle = _prepare_delivery_bundle(output_bundle, send_text=send_text)
    if delivery_bundle.is_empty():
        print("[chat-delivery] skipped: delivery bundle empty after prepare", flush=True)
        return False
    metadata = dict(delivery_session.metadata or {})
    if not str(metadata.get("feishu.message_id") or "").strip() and str(message_id or "").strip():
        metadata["feishu.message_id"] = str(message_id).strip()
        delivery_session = DeliverySession(
            platform=delivery_session.platform,
            mode=delivery_session.mode,
            target=delivery_session.target,
            session_id=delivery_session.session_id,
            target_type=delivery_session.target_type,
            thread_id=delivery_session.thread_id,
            metadata=metadata,
        )
    adapter = _build_chat_presentation_service(workspace).build_delivery_adapter()
    delivery_result = adapter.deliver(delivery_session, delivery_bundle)
    log_preview = " | ".join(list(delivery_result.log or [])[:6])
    print(
        f"[chat-delivery] status={delivery_result.status} delivered={delivery_result.delivered} error={delivery_result.error or '-'} log={log_preview}",
        flush=True,
    )
    return _delivery_result_has_transport_effect(delivery_result)


def run_chat_feishu_bot(
    *,
    default_config_name: str,
    bot_name: str,
    run_agent_fn: Callable[..., str],
    supports_images: bool = True,
    supports_stream_segment: bool = True,
    send_output_files: bool = True,
    args_extra: argparse.ArgumentParser | None = None,
    local_test_fn: Callable[[str, argparse.Namespace], str] | Callable[[str], str] | None = None,
    on_bot_started: Callable[[], None] | None = None,
    on_reply_sent: Callable[[str, str], None] | None = None,
    immediate_receipt_text: str | None = None,
) -> int:
    return transport_module.run_feishu_bot(
        config_path="",
        default_config_name=default_config_name,
        bot_name=bot_name,
        run_agent_fn=run_agent_fn,
        supports_images=supports_images,
        supports_stream_segment=supports_stream_segment,
        send_output_files=send_output_files,
        args_extra=args_extra,
        local_test_fn=local_test_fn,
        on_bot_started=on_bot_started,
        on_reply_sent=on_reply_sent,
        immediate_receipt_text=immediate_receipt_text,
        deliver_output_bundle_fn=deliver_chat_turn_output_bundle,
    )


def run_chat_feishu_bot_with_loaded_config(
    config: dict,
    *,
    bot_name: str,
    run_agent_fn: Callable[..., str],
    supports_images: bool = True,
    supports_stream_segment: bool = True,
    send_output_files: bool = True,
    on_bot_started: Callable[[], None] | None = None,
    on_reply_sent: Callable[[str, str], None] | None = None,
    immediate_receipt_text: str | None = None,
) -> int:
    return transport_module.run_feishu_bot_with_loaded_config(
        config,
        bot_name=bot_name,
        run_agent_fn=run_agent_fn,
        supports_images=supports_images,
        supports_stream_segment=supports_stream_segment,
        send_output_files=send_output_files,
        on_bot_started=on_bot_started,
        on_reply_sent=on_reply_sent,
        immediate_receipt_text=immediate_receipt_text,
        deliver_output_bundle_fn=deliver_chat_turn_output_bundle,
    )


__all__ = ["deliver_chat_turn_output_bundle", "run_chat_feishu_bot", "run_chat_feishu_bot_with_loaded_config"]
