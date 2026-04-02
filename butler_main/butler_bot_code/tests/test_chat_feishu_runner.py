import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
MODULE_DIR = BUTLER_MAIN_DIR / "butler_bot_code" / "butler_bot"
sys.path.insert(0, str(BUTLER_MAIN_DIR))
sys.path.insert(0, str(MODULE_DIR))

from agents_os.contracts import DeliverySession, OutputBundle, TextBlock
from agents_os.contracts import FileAsset, ImageAsset
from butler_main.chat.feishu_bot.runner import deliver_chat_turn_output_bundle


class ChatFeishuRunnerTests(unittest.TestCase):
    def test_deliver_chat_turn_output_bundle_uses_transport_callbacks(self) -> None:
        def fake_run(prompt=None, stream_callback=None, image_paths=None):
            return "ignored"

        fake_run.get_turn_output_bundle = lambda: OutputBundle(text_blocks=[TextBlock(text="bundle 最终完整回复")])
        fake_run.get_turn_delivery_session = lambda: DeliverySession(
            platform="feishu",
            mode="reply",
            target="ou_chat",
            target_type="open_id",
            metadata={"feishu.message_id": "mid-chat"},
        )

        with mock.patch("butler_main.chat.feishu_bot.runner.transport_module.reply_message", return_value=True) as reply_message:
            ok = deliver_chat_turn_output_bundle("mid-chat", fake_run, workspace=".")

        self.assertTrue(ok)
        reply_message.assert_called_once_with(
            "mid-chat",
            "bundle 最终完整回复",
            use_interactive=True,
            include_card_actions=False,
        )

    def test_deliver_chat_turn_output_bundle_can_send_only_media_without_text(self) -> None:
        def fake_run(prompt=None, stream_callback=None, image_paths=None):
            return "ignored"

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            image_path = workspace / "工作区" / "chart.png"
            file_path = workspace / "工作区" / "report.md"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(b"\x89PNG\r\n\x1a\nrunner")
            file_path.write_text("runner report", encoding="utf-8")

            fake_run.get_turn_output_bundle = lambda: OutputBundle(
                text_blocks=[TextBlock(text="bundle 最终完整回复")],
                images=[ImageAsset(path="./工作区/chart.png")],
                files=[FileAsset(path="./工作区/report.md")],
            )
            fake_run.get_turn_delivery_session = lambda: DeliverySession(
                platform="feishu",
                mode="reply",
                target="ou_chat",
                target_type="open_id",
                metadata={"feishu.message_id": "mid-chat"},
            )

            with mock.patch("butler_main.chat.feishu_bot.runner.transport_module.reply_message", return_value=True) as reply_message, \
                 mock.patch("butler_main.chat.feishu_bot.runner.transport_module.upload_image", return_value="img_key_1") as upload_image, \
                 mock.patch("butler_main.chat.feishu_bot.runner.transport_module.reply_image", return_value=True) as reply_image, \
                 mock.patch("butler_main.chat.feishu_bot.runner.transport_module.upload_file", return_value="file_key_1") as upload_file, \
                 mock.patch("butler_main.chat.feishu_bot.runner.transport_module.reply_file", return_value=True) as reply_file:
                ok = deliver_chat_turn_output_bundle("mid-chat", fake_run, workspace=str(workspace), send_text=False)

        self.assertTrue(ok)
        reply_message.assert_not_called()
        upload_image.assert_called_once()
        reply_image.assert_called_once_with("mid-chat", "img_key_1")
        upload_file.assert_called_once()
        reply_file.assert_called_once_with("mid-chat", "file_key_1")


if __name__ == "__main__":
    unittest.main()
