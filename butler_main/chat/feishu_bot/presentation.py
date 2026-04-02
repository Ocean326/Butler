from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from butler_main.chat.feishu_bot.delivery import FeishuDeliveryAdapter


@dataclass(slots=True)
class ChatFeishuPresentationService:
    """Feishu presentation-layer transport facade for chat delivery."""

    send_reply_text_fn: Callable[[str, str, bool], bool]
    send_push_text_fn: Callable[[str, str, str], bool]
    upload_image_fn: Callable[[str], str]
    reply_image_fn: Callable[[str, str], bool]
    push_image_fn: Callable[[str, str, str], bool]
    upload_file_fn: Callable[[str], str]
    reply_file_fn: Callable[[str, str], bool]
    push_file_fn: Callable[[str, str, str], bool]

    def send_reply_text(
        self,
        message_id: str,
        text: str,
        *,
        include_card_actions: bool = False,
    ) -> bool:
        return bool(self.send_reply_text_fn(message_id, text, include_card_actions))

    def send_push_text(
        self,
        target: str,
        text: str,
        *,
        target_type: str = "open_id",
    ) -> bool:
        return bool(self.send_push_text_fn(target, text, target_type))

    def upload_image(self, path_text: str) -> str:
        return str(self.upload_image_fn(path_text) or "")

    def send_reply_image(self, message_id: str, image_key: str) -> bool:
        return bool(self.reply_image_fn(message_id, image_key))

    def send_push_image(
        self,
        target: str,
        image_key: str,
        *,
        target_type: str = "open_id",
    ) -> bool:
        return bool(self.push_image_fn(target, image_key, target_type))

    def upload_file(self, path_text: str) -> str:
        return str(self.upload_file_fn(path_text) or "")

    def send_reply_file(self, message_id: str, file_key: str) -> bool:
        return bool(self.reply_file_fn(message_id, file_key))

    def send_push_file(
        self,
        target: str,
        file_key: str,
        *,
        target_type: str = "open_id",
    ) -> bool:
        return bool(self.push_file_fn(target, file_key, target_type))

    def build_delivery_adapter(self) -> FeishuDeliveryAdapter:
        return FeishuDeliveryAdapter(
            send_reply_text_fn=self.send_reply_text_fn,
            send_push_text_fn=self.send_push_text_fn,
            upload_image_fn=self.upload_image_fn,
            reply_image_fn=self.reply_image_fn,
            push_image_fn=self.push_image_fn,
            upload_file_fn=self.upload_file_fn,
            reply_file_fn=self.reply_file_fn,
            push_file_fn=self.push_file_fn,
        )


__all__ = ["ChatFeishuPresentationService"]
