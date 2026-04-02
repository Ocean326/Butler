import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.chat.feishu_bot.dispatcher import build_card_action_response


class ChatFeishuDispatcherTests(unittest.TestCase):
    def test_build_card_action_response_returns_plain_toast_payload(self) -> None:
        payload = build_card_action_response("已请求终止当前执行", toast_type="success")

        self.assertEqual(
            payload,
            {
                "toast": {
                    "type": "success",
                    "content": "已请求终止当前执行",
                }
            },
        )


if __name__ == "__main__":
    unittest.main()
