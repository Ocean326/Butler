import unittest

from butler_main.chat.weixi.input import WeixinInputAdapter


class ChatWeixinInputTests(unittest.TestCase):
    def test_build_invocation_promotes_dm_to_stable_conversation_key(self) -> None:
        adapter = WeixinInputAdapter()

        invocation = adapter.build_invocation(
            {
                "message": {
                    "message_id": "wx-mid-3",
                    "session_id": "raw-session-1",
                    "from_user_id": "wx-user-3",
                    "to_user_id": "wx-bot-1",
                    "content": {"text": "你好"},
                }
            }
        )

        self.assertEqual(invocation.session_id, "weixin:wx-bot-1:dm:wx-user-3")
        self.assertEqual(invocation.metadata["weixin.chat_type"], "dm")
        self.assertEqual(invocation.metadata["weixin.conversation_key"], "weixin:wx-bot-1:dm:wx-user-3")
        self.assertEqual(invocation.metadata["weixin.raw_session_ref"], "raw-session-1")

    def test_orchestrator_marker_now_stays_on_chat(self) -> None:
        adapter = WeixinInputAdapter()

        invocation = adapter.build_invocation(
            {
                "message": {
                    "message_id": "wx-mid-1",
                    "content": {"text": "【chat_orchestrator_mission_json】{\"title\":\"整理任务\"}"},
                }
            }
        )

        self.assertEqual(invocation.entrypoint, "chat")

    def test_unknown_entrypoint_hint_falls_back_to_chat(self) -> None:
        adapter = WeixinInputAdapter()

        invocation = adapter.build_invocation(
            {
                "message": {
                    "message_id": "wx-mid-2",
                    "content": {"text": "普通聊天消息"},
                }
            },
            entrypoint_hint="background",
        )

        self.assertEqual(invocation.entrypoint, "chat")


if __name__ == "__main__":
    unittest.main()
