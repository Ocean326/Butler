import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.chat.feishu_bot.interaction import (
    build_card_action_invocation_metadata,
    build_card_action_prompt,
    build_invocation_metadata_from_message,
    extract_card_action_payload,
    extract_inbound_message_event,
)


class ChatFeishuInteractionTests(unittest.TestCase):
    def test_build_invocation_metadata_from_message_keeps_session_and_target(self) -> None:
        data = SimpleNamespace(
            event=SimpleNamespace(
                message=SimpleNamespace(
                    message_id="om_123",
                    chat_id="chat_123",
                    chat_type="p2p",
                    message_type="text",
                    thread_id="thread_123",
                    content='{"text":"今天进度怎么样"}',
                ),
                sender=SimpleNamespace(
                    sender_id=SimpleNamespace(open_id="ou_123", user_id=""),
                    sender_type="user",
                ),
                open_message_id="om_123",
            ),
            header=SimpleNamespace(event_id="evt_123", event_type="im.message.receive_v1"),
        )

        metadata = build_invocation_metadata_from_message(data)

        self.assertEqual(metadata["channel"], "feishu")
        self.assertEqual(metadata["message_id"], "om_123")
        self.assertEqual(metadata["session_id"], "thread_123")
        self.assertEqual(metadata["actor_id"], "ou_123")
        self.assertEqual(metadata["feishu.receive_id"], "ou_123")
        self.assertEqual(metadata["feishu.chat_id"], "chat_123")
        self.assertEqual(metadata["feishu.raw_session_ref"], "thread_123")
        self.assertEqual(metadata["feishu_event"]["header"]["event_type"], "im.message.receive_v1")

    def test_card_action_payload_and_metadata_keep_route_and_delivery_mode(self) -> None:
        data = SimpleNamespace(
            event=SimpleNamespace(
                action=SimpleNamespace(
                    value={"cmd": "todo", "route": "mission", "delivery_mode": "push"},
                    form_value={},
                    input_value="",
                    name="todo",
                ),
                context=SimpleNamespace(open_message_id="om_card_1", open_chat_id="chat_card_1"),
                operator=SimpleNamespace(open_id="ou_card_1", user_id=""),
            ),
            header=SimpleNamespace(event_id="evt_card_1"),
        )

        payload = extract_card_action_payload(data)
        metadata = build_card_action_invocation_metadata(payload)

        self.assertEqual(payload["cmd"], "todo")
        self.assertEqual(payload["route_hint"], "mission")
        self.assertEqual(payload["delivery_mode"], "push")
        self.assertEqual(metadata["entrypoint_hint"], "mission")
        self.assertEqual(metadata["delivery_mode"], "push")
        self.assertEqual(metadata["feishu.receive_id"], "ou_card_1")
        self.assertEqual(metadata["feishu.chat_id"], "chat_card_1")
        self.assertEqual(metadata["session_id"], "chat_card_1")

    def test_card_action_prompt_prefers_manual_prompt(self) -> None:
        prompt = build_card_action_prompt(
            {
                "cmd": "continue",
                "value": {"prompt": "请基于上一条回复补上风险和依赖。"},
                "form_value": {},
                "input_value": "",
            }
        )

        self.assertEqual(prompt, "请基于上一条回复补上风险和依赖。")

    def test_extract_inbound_message_event_uses_root_id_and_skips_bot(self) -> None:
        data = SimpleNamespace(
            event=SimpleNamespace(
                message=SimpleNamespace(
                    message_id="om_root_reply",
                    chat_id="chat_root",
                    chat_type="group",
                    message_type="text",
                    root_id="om_root_1",
                    thread_id="",
                    content='{"text":"线程内回复"}',
                ),
                sender=SimpleNamespace(
                    sender_id=SimpleNamespace(open_id="ou_bot_1", user_id=""),
                    sender_type="bot",
                ),
            ),
            header=SimpleNamespace(event_type="im.message.receive_v1"),
        )

        extracted = extract_inbound_message_event(data)

        self.assertEqual(extracted["session_id"], "om_root_1")
        self.assertEqual(extracted["text"], "线程内回复")
        self.assertFalse(extracted["should_process"])


if __name__ == "__main__":
    unittest.main()
