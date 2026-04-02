import unittest
import json

from butler_main.chat.feishu_bot.input import FeishuInputAdapter


class ChatFeishuInputTests(unittest.TestCase):
    def test_mission_command_now_stays_on_chat(self) -> None:
        adapter = FeishuInputAdapter()

        invocation = adapter.build_invocation(
            {
                "message": {
                    "message_id": "fs-mid-1",
                    "content": {"text": "/mission create 整理任务"},
                }
            }
        )

        self.assertEqual(invocation.entrypoint, "chat")

    def test_unknown_entrypoint_hint_falls_back_to_chat(self) -> None:
        adapter = FeishuInputAdapter()

        invocation = adapter.build_invocation(
            {
                "message": {
                    "message_id": "fs-mid-2",
                    "content": {"text": "普通聊天消息"},
                }
            },
            entrypoint_hint="background",
        )

        self.assertEqual(invocation.entrypoint, "chat")

    def test_opaque_legacy_marker_stays_on_chat_frontdoor(self) -> None:
        adapter = FeishuInputAdapter()

        invocation = adapter.build_invocation(
            {
                "message": {
                    "message_id": "fs-mid-3",
                    "content": {"text": "【legacy_task_blob】{\"task\":\"整理\"}"},
                }
            }
        )

        self.assertEqual(invocation.entrypoint, "chat")

    def test_build_invocation_keeps_quote_and_rich_text(self) -> None:
        adapter = FeishuInputAdapter()

        invocation = adapter.build_invocation(
            {
                "message": {
                    "message_id": "fs-mid-4",
                    "content": json.dumps(
                        {
                            "text": "用 OCR 方案",
                            "quote": {"text": "把那张图也一起整理"},
                            "content": [[{"tag": "text", "text": "输出到 BrainStorm"}]],
                        },
                        ensure_ascii=False,
                    ),
                }
            }
        )

        self.assertIn("【引用内容】", invocation.user_text)
        self.assertIn("把那张图也一起整理", invocation.user_text)
        self.assertIn("输出到 BrainStorm", invocation.user_text)


if __name__ == "__main__":
    unittest.main()
