from __future__ import annotations

import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from butler_main.chat import ChatMainlineService, ChatRouter, ChatRuntimeService
from butler_main.chat.feishu_bot import ChatFeishuPresentationService
from butler_main.chat.feishu_bot.delivery import FeishuDeliveryAdapter
from butler_main.chat.feishu_bot.input import FeishuInputAdapter
from butler_main.chat.weixi import WeixinDeliveryAdapter, WeixinInputAdapter


class ChatModuleExportsTests(unittest.TestCase):
    def test_root_chat_exports_resolve_to_chat_named_body_modules(self) -> None:
        self.assertEqual(ChatMainlineService.__module__, "butler_main.chat.mainline")
        self.assertEqual(ChatRouter.__module__, "butler_main.chat.routing")
        self.assertEqual(ChatRuntimeService.__module__, "butler_main.chat.runtime")

    def test_feishu_bot_modules_exist_under_chat_namespace(self) -> None:
        self.assertEqual(FeishuInputAdapter.__module__, "butler_main.chat.feishu_bot.input")
        self.assertEqual(FeishuDeliveryAdapter.__module__, "butler_main.chat.feishu_bot.delivery")
        self.assertEqual(ChatFeishuPresentationService.__module__, "butler_main.chat.feishu_bot.presentation")

    def test_weixi_modules_exist_under_chat_namespace(self) -> None:
        self.assertEqual(WeixinInputAdapter.__module__, "butler_main.chat.weixi.input")
        self.assertEqual(WeixinDeliveryAdapter.__module__, "butler_main.chat.weixi.delivery")


if __name__ == "__main__":
    unittest.main()
