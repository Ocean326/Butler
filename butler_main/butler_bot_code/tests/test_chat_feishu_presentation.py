import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.contracts import DeliverySession, OutputBundle, TextBlock
from butler_main.chat.feishu_bot import ChatFeishuPresentationService


class ChatFeishuPresentationServiceTests(unittest.TestCase):
    def test_build_delivery_adapter_uses_presentation_callbacks(self) -> None:
        calls = []
        service = ChatFeishuPresentationService(
            send_reply_text_fn=lambda message_id, text, include_card_actions: calls.append(("reply_text", message_id, text, include_card_actions)) or True,
            send_push_text_fn=lambda target, text, target_type: calls.append(("push_text", target, text, target_type)) or True,
            upload_image_fn=lambda path: calls.append(("upload_image", path)) or "img_key_1",
            reply_image_fn=lambda message_id, image_key: calls.append(("reply_image", message_id, image_key)) or True,
            push_image_fn=lambda target, image_key, target_type: calls.append(("push_image", target, image_key, target_type)) or True,
            upload_file_fn=lambda path: calls.append(("upload_file", path)) or "file_key_1",
            reply_file_fn=lambda message_id, file_key: calls.append(("reply_file", message_id, file_key)) or True,
            push_file_fn=lambda target, file_key, target_type: calls.append(("push_file", target, file_key, target_type)) or True,
        )
        adapter = service.build_delivery_adapter()
        session = DeliverySession(
            platform="feishu",
            mode="reply",
            target="ou_test",
            target_type="open_id",
            metadata={"feishu.message_id": "mid-pres"},
        )
        bundle = OutputBundle(text_blocks=[TextBlock(text="hello presentation")])

        result = adapter.deliver(session, bundle)

        self.assertTrue(result.delivered)
        self.assertIn(("reply_text", "mid-pres", "hello presentation", False), calls)


if __name__ == "__main__":
    unittest.main()
