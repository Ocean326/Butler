import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.chat.feishu_bot import build_card_quick_actions, markdown_to_feishu_post, markdown_to_interactive_card


class ChatFeishuRenderingTests(unittest.TestCase):
    def test_markdown_to_interactive_card_supports_quick_actions(self) -> None:
        card = markdown_to_interactive_card("hello", include_quick_actions=True)

        self.assertEqual(card["schema"], "2.0")
        self.assertEqual(card["body"]["elements"][0]["tag"], "markdown")
        self.assertIn("hello", card["body"]["elements"][0]["content"])
        self.assertEqual(card["body"]["elements"][1]["tag"], "markdown")
        self.assertIn("继续展开", card["body"]["elements"][1]["content"])
        self.assertNotIn("请直接回复", card["body"]["elements"][1]["content"])
        self.assertEqual(card["body"]["elements"][2]["tag"], "button")
        self.assertEqual(card["body"]["elements"][2]["value"]["cmd"], "continue")

    def test_markdown_to_feishu_post_returns_md_post(self) -> None:
        post = markdown_to_feishu_post("## hello")

        self.assertEqual(post["zh_cn"]["title"], "回复")
        self.assertEqual(post["zh_cn"]["content"][0][0]["tag"], "md")
        self.assertIn("hello", post["zh_cn"]["content"][0][0]["text"])

    def test_build_card_quick_actions_returns_expected_commands(self) -> None:
        actions = build_card_quick_actions()

        self.assertEqual([item["value"]["cmd"] for item in actions], ["continue", "todo", "brief"])

    def test_running_card_quick_actions_expose_terminate_button(self) -> None:
        card = markdown_to_interactive_card("running", include_quick_actions=True, quick_action_mode="running")

        self.assertEqual(card["body"]["elements"][2]["tag"], "button")
        self.assertEqual(card["body"]["elements"][2]["value"]["cmd"], "terminate")
        self.assertEqual(card["body"]["elements"][2]["type"], "danger")


if __name__ == "__main__":
    unittest.main()
