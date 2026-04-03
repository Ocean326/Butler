from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path

from butler_main.agents_os.runtime import safe_truncate_markdown, sanitize_markdown_structure
from butler_main.chat.pathing import resolve_butler_root

from .api import FeishuApiClient


class FeishuReplyService:
    def __init__(
        self,
        *,
        api_client: FeishuApiClient,
        config_getter: Callable[[], dict],
        markdown_to_interactive_card: Callable[[str, bool], dict],
        markdown_to_feishu_post: Callable[[str], dict],
    ) -> None:
        self._api_client = api_client
        self._config_getter = config_getter
        self._markdown_to_interactive_card = markdown_to_interactive_card
        self._markdown_to_feishu_post = markdown_to_feishu_post

    def reply_message(
        self,
        message_id: str,
        text: str,
        *,
        use_interactive: bool = True,
        include_card_actions: bool | None = None,
        card_action_mode: str = "followup",
        card_action_value_extras: dict | None = None,
    ) -> bool:
        try:
            normalized_text = self._collapse_duplicate_reply_blocks(sanitize_markdown_structure(text))
            image_refs = self._extract_markdown_image_refs(normalized_text)
            plain_text = self._strip_markdown_images(normalized_text).strip()
            sent_any = False
            text_ok = True
            if plain_text:
                interactive_failed_data = None
                if use_interactive:
                    card = self._build_interactive_card(
                        plain_text,
                        include_card_actions=bool(include_card_actions),
                        card_action_mode=card_action_mode,
                        card_action_value_extras=card_action_value_extras,
                    )
                    ok, data = self._api_client.reply_raw_message(message_id, "interactive", card)
                    if not ok and bool(include_card_actions) and self._should_retry_interactive_without_actions(data):
                        ok, data = self._api_client.reply_raw_message(
                            message_id,
                            "interactive",
                            self._build_interactive_card(
                                plain_text,
                                include_card_actions=False,
                                card_action_mode=card_action_mode,
                                card_action_value_extras=card_action_value_extras,
                            ),
                        )
                    if ok:
                        sent_any = True
                    else:
                        interactive_failed_data = data
                if not sent_any:
                    ok_post, data_post = self._api_client.reply_raw_message(
                        message_id,
                        "post",
                        self._markdown_to_feishu_post(plain_text),
                    )
                    if ok_post:
                        sent_any = True
                    else:
                        ok_text, data_text = self._api_client.reply_raw_message(
                            message_id,
                            "text",
                            {"text": safe_truncate_markdown(plain_text, 15000)},
                        )
                        if ok_text:
                            sent_any = True
                        else:
                            text_ok = False
                            print(f"回复失败: interactive={interactive_failed_data}, post={data_post}, text={data_text}", file=sys.stderr)
                    if interactive_failed_data and sent_any:
                        print(f"interactive 回退 post/text: {interactive_failed_data}", file=sys.stderr)
            image_ok = True
            for image_ref in image_refs:
                local_path = self._resolve_image_ref_to_local_path(image_ref)
                if not local_path:
                    image_ok = False
                    continue
                image_key = self._api_client.upload_image(local_path)
                if image_key and self._api_client.reply_image(message_id, image_key):
                    sent_any = True
                else:
                    image_ok = False
            return sent_any and text_ok and image_ok
        except Exception as exc:
            print(f"回复异常: {exc}", file=sys.stderr)
            return False

    def create_interactive_reply(
        self,
        message_id: str,
        text: str,
        *,
        include_card_actions: bool = False,
        card_action_mode: str = "followup",
        card_action_value_extras: dict | None = None,
    ) -> str:
        try:
            plain_text = self._prepare_plain_text(text)
            if not plain_text:
                return ""
            ok, data = self._api_client.reply_raw_message(
                message_id,
                "interactive",
                self._build_interactive_card(
                    plain_text,
                    include_card_actions=include_card_actions,
                    card_action_mode=card_action_mode,
                    card_action_value_extras=card_action_value_extras,
                ),
            )
            if not ok and include_card_actions and self._should_retry_interactive_without_actions(data):
                ok, data = self._api_client.reply_raw_message(
                    message_id,
                    "interactive",
                    self._build_interactive_card(
                        plain_text,
                        include_card_actions=False,
                        card_action_mode=card_action_mode,
                        card_action_value_extras=card_action_value_extras,
                    ),
                )
            if not ok:
                print(f"创建流式占位卡片失败: {data}", file=sys.stderr)
                return ""
            return str(((data.get("data") or {}).get("message_id")) or "").strip()
        except Exception as exc:
            print(f"创建流式占位卡片异常: {exc}", file=sys.stderr)
            return ""

    def update_interactive_message(
        self,
        message_id: str,
        text: str,
        *,
        include_card_actions: bool = False,
        card_action_mode: str = "followup",
        card_action_value_extras: dict | None = None,
    ) -> bool:
        try:
            plain_text = self._prepare_plain_text(text)
            if not plain_text:
                return False
            ok, data = self._api_client.update_raw_message(
                message_id,
                "interactive",
                self._build_interactive_card(
                    plain_text,
                    include_card_actions=include_card_actions,
                    card_action_mode=card_action_mode,
                    card_action_value_extras=card_action_value_extras,
                ),
            )
            if not ok and include_card_actions and self._should_retry_interactive_without_actions(data):
                ok, data = self._api_client.update_raw_message(
                    message_id,
                    "interactive",
                    self._build_interactive_card(
                        plain_text,
                        include_card_actions=False,
                        card_action_mode=card_action_mode,
                        card_action_value_extras=card_action_value_extras,
                    ),
                )
            if not ok:
                print(f"更新流式卡片失败: {data}", file=sys.stderr)
            return ok
        except Exception as exc:
            print(f"更新流式卡片异常: {exc}", file=sys.stderr)
            return False

    def resolve_image_ref_to_local_path(self, image_ref: str) -> str | None:
        return self._resolve_image_ref_to_local_path(image_ref)

    def _build_interactive_card(
        self,
        text: str,
        *,
        include_card_actions: bool,
        card_action_mode: str,
        card_action_value_extras: dict | None,
    ) -> dict:
        try:
            return self._markdown_to_interactive_card(
                text,
                include_card_actions,
                quick_action_mode=card_action_mode,
                action_value_extras=card_action_value_extras,
            )
        except TypeError:
            return self._markdown_to_interactive_card(text, include_card_actions)

    def _prepare_plain_text(self, text: str) -> str:
        normalized_text = self._collapse_duplicate_reply_blocks(sanitize_markdown_structure(text))
        return self._strip_markdown_images(normalized_text).strip()

    @staticmethod
    def _should_retry_interactive_without_actions(data: dict | None) -> bool:
        payload = dict(data or {})
        message = str(payload.get("msg") or "").strip().lower()
        return "unsupported tag action" in message or "no longer support this capability" in message

    @staticmethod
    def _normalize_reply_text(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip())

    def _collapse_duplicate_reply_blocks(self, text: str) -> str:
        if not text:
            return ""
        blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
        if len(blocks) <= 1:
            return text
        deduped: list[str] = []
        previous_key = ""
        for block in blocks:
            current_key = self._normalize_reply_text(block)
            if current_key and current_key == previous_key:
                continue
            deduped.append(block)
            previous_key = current_key
        return "\n\n".join(deduped).strip()

    @staticmethod
    def _extract_markdown_image_refs(md: str) -> list[str]:
        return [m.group(1).strip() for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", md or "") if m.group(1).strip()]

    @staticmethod
    def _strip_markdown_images(md: str) -> str:
        return re.sub(r"!\[[^\]]*\]\(([^)]+)\)", "", md or "")

    def _resolve_image_ref_to_local_path(self, image_ref: str) -> str | None:
        if not image_ref:
            return None
        ref = image_ref.strip().strip('"').strip("'")
        if re.match(r"^https?://", ref, flags=re.IGNORECASE):
            return self._api_client.fetch_remote_image_to_temp(ref)
        path = Path(ref)
        if not path.is_absolute():
            workspace = (self._config_getter() or {}).get("workspace_root") or os.getcwd()
            path = resolve_butler_root(workspace) / path
        try:
            path = path.resolve()
        except Exception:
            pass
        return str(path) if path.is_file() else None


__all__ = ["FeishuReplyService"]
