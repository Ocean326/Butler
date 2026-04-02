import sys
import unittest
from pathlib import Path

BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.contracts import DeliverySession, FileAsset, ImageAsset, OutputBundle, TextBlock
from butler_main.chat.feishu_bot import FeishuDeliveryAdapter


class FeishuDeliveryAdapterTests(unittest.TestCase):
    def test_deliver_reply_bundle_uses_transport_callbacks(self):
        calls = []
        adapter = FeishuDeliveryAdapter(
            send_reply_text_fn=lambda message_id, text, include_card_actions: calls.append(("reply_text", message_id, text, include_card_actions)) or True,
            upload_image_fn=lambda path: calls.append(("upload_image", path)) or "img_key_1",
            reply_image_fn=lambda message_id, image_key: calls.append(("reply_image", message_id, image_key)) or True,
            upload_file_fn=lambda path: calls.append(("upload_file", path)) or "file_key_1",
            reply_file_fn=lambda message_id, file_key: calls.append(("reply_file", message_id, file_key)) or True,
        )
        session = DeliverySession(
            platform="feishu",
            mode="reply",
            target="ou_test",
            target_type="open_id",
            metadata={"feishu.message_id": "mid-1"},
        )
        bundle = OutputBundle(
            text_blocks=[TextBlock(text="hello chat")],
            images=[ImageAsset(path="plot.png")],
            files=[FileAsset(path="notes.md")],
        )

        result = adapter.deliver(session, bundle)

        self.assertTrue(result.delivered)
        self.assertEqual(result.error, "")
        self.assertIn(("reply_text", "mid-1", "hello chat", False), calls)
        self.assertIn(("upload_image", "plot.png"), calls)
        self.assertIn(("reply_image", "mid-1", "img_key_1"), calls)
        self.assertIn(("upload_file", "notes.md"), calls)
        self.assertIn(("reply_file", "mid-1", "file_key_1"), calls)

    def test_deliver_without_callbacks_reports_transport_not_connected(self):
        adapter = FeishuDeliveryAdapter()
        session = DeliverySession(
            platform="feishu",
            mode="reply",
            target="ou_test",
            target_type="open_id",
            metadata={"feishu.message_id": "mid-2"},
        )
        bundle = OutputBundle(text_blocks=[TextBlock(text="hello chat")])

        result = adapter.deliver(session, bundle)

        self.assertFalse(result.delivered)
        self.assertEqual(result.error, "transport_not_connected")


if __name__ == "__main__":
    unittest.main()
