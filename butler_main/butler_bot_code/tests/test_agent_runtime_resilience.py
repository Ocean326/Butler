from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))


class _FakeEventDispatcherBuilder:
    def register_p2_im_message_receive_v1(self, _handler):
        return self

    def register_p2_card_action_trigger(self, _handler):
        return self

    def build(self):
        return object()


if "lark_oapi" not in sys.modules:
    sys.modules["lark_oapi"] = SimpleNamespace(
        LogLevel=SimpleNamespace(INFO="INFO"),
        EventDispatcherHandler=SimpleNamespace(builder=lambda *_args, **_kwargs: _FakeEventDispatcherBuilder()),
        im=SimpleNamespace(v1=SimpleNamespace(P2ImMessageReceiveV1=object)),
        cardkit=SimpleNamespace(v1=SimpleNamespace(P2CardActionTrigger=object)),
        ws=SimpleNamespace(Client=mock.Mock()),
    )
if "requests" not in sys.modules:
    sys.modules["requests"] = SimpleNamespace(
        get=mock.Mock(),
        post=mock.Mock(),
        patch=mock.Mock(),
        request=mock.Mock(),
    )

from butler_main.chat.feishu_bot import transport


class AgentRuntimeResilienceTests(unittest.TestCase):
    def tearDown(self) -> None:
        transport._recent_feishu_sessions.clear()

    def test_feishu_loop_restarts_after_clean_return_until_limit(self) -> None:
        saved_config = dict(transport.CONFIG)
        transport.CONFIG.clear()
        transport.CONFIG.update(
            {
                "app_id": "app",
                "app_secret": "secret",
                "workspace_root": ".",
                "feishu_long_connection": {
                    "auto_restart_on_disconnect": True,
                    "max_restart_attempts": 1,
                    "restart_backoff_seconds": 1,
                    "restart_backoff_max_seconds": 1,
                },
            }
        )
        try:
            fake_client = mock.Mock()
            fake_client.start.side_effect = [None, None]
            with mock.patch.object(transport.ws, "Client", return_value=fake_client), mock.patch.object(transport.time, "sleep", return_value=None):
                result = transport._run_feishu_loop(
                    bot_name="test-bot",
                    run_agent_fn=lambda *_args, **_kwargs: "",
                    supports_images=False,
                    supports_stream_segment=False,
                    send_output_files=False,
                    on_bot_started=None,
                    on_reply_sent=None,
                )
        finally:
            transport.CONFIG.clear()
            transport.CONFIG.update(saved_config)

        self.assertEqual(result, 1)
        self.assertEqual(fake_client.start.call_count, 2)

    def test_feishu_loop_retries_exception_and_recovers(self) -> None:
        saved_config = dict(transport.CONFIG)
        transport.CONFIG.clear()
        transport.CONFIG.update(
            {
                "app_id": "app",
                "app_secret": "secret",
                "workspace_root": ".",
                "feishu_long_connection": {
                    "auto_restart_on_disconnect": True,
                    "max_restart_attempts": 2,
                    "restart_backoff_seconds": 1,
                    "restart_backoff_max_seconds": 1,
                },
            }
        )
        try:
            fake_client_first = mock.Mock()
            fake_client_first.start.side_effect = RuntimeError("disconnect")
            fake_client_second = mock.Mock()
            fake_client_second.start.side_effect = [None, None]
            with mock.patch.object(transport.ws, "Client", side_effect=[fake_client_first, fake_client_second, fake_client_second]), mock.patch.object(transport.time, "sleep", return_value=None):
                result = transport._run_feishu_loop(
                    bot_name="test-bot",
                    run_agent_fn=lambda *_args, **_kwargs: "",
                    supports_images=False,
                    supports_stream_segment=False,
                    send_output_files=False,
                    on_bot_started=None,
                    on_reply_sent=None,
                )
        finally:
            transport.CONFIG.clear()
            transport.CONFIG.update(saved_config)

        self.assertEqual(result, 1)
        self.assertEqual(fake_client_first.start.call_count, 1)
        self.assertGreaterEqual(fake_client_second.start.call_count, 2)

    def test_feishu_loop_backfills_recent_messages_before_restart(self) -> None:
        saved_config = dict(transport.CONFIG)
        transport.CONFIG.clear()
        transport.CONFIG.update(
            {
                "app_id": "app",
                "app_secret": "secret",
                "workspace_root": ".",
                "feishu_long_connection": {
                    "auto_restart_on_disconnect": True,
                    "max_restart_attempts": 1,
                    "restart_backoff_seconds": 1,
                    "restart_backoff_max_seconds": 1,
                },
            }
        )
        transport._register_recent_feishu_session(
            {
                "feishu.chat_id": "chat_123",
                "feishu.raw_session_ref": "thread_123",
                "feishu.message_id": "om_latest",
            }
        )
        fake_run_agent = mock.Mock(return_value="")
        fake_run_agent.backfill_recent_feishu_messages = mock.Mock(return_value=2)
        fake_client = mock.Mock()
        fake_client.start.side_effect = [None, None]
        try:
            with mock.patch.object(transport, "_run_feishu_preflight", return_value=(True, "ok")), \
                 mock.patch.object(transport, "build_chat_feishu_event_dispatcher", return_value=object()), \
                 mock.patch.object(transport.ws, "Client", return_value=fake_client), \
                 mock.patch.object(
                     transport._API_CLIENT,
                     "list_messages",
                     return_value=(
                         True,
                         {
                             "data": {
                                 "items": [
                                     {
                                         "message_id": "om_user_1",
                                         "create_time": "1711440000000",
                                         "sender": {"sender_type": "user"},
                                         "body": {"content": "{\"text\":\"用户问题\"}"},
                                         "msg_type": "text",
                                     },
                                     {
                                         "message_id": "om_bot_1",
                                         "create_time": "1711440060000",
                                         "sender": {"sender_type": "bot"},
                                         "body": {"content": "{\"text\":\"助手回复\"}"},
                                         "msg_type": "text",
                                     },
                                 ]
                             }
                         },
                     ),
                 ) as list_messages, \
                 mock.patch.object(transport.time, "sleep", return_value=None):
                result = transport._run_feishu_loop(
                    bot_name="test-bot",
                    run_agent_fn=fake_run_agent,
                    supports_images=False,
                    supports_stream_segment=False,
                    send_output_files=False,
                    on_bot_started=None,
                    on_reply_sent=None,
                )
        finally:
            transport.CONFIG.clear()
            transport.CONFIG.update(saved_config)

        self.assertEqual(result, 1)
        list_messages.assert_called_once_with(
            container_id="chat_123",
            container_id_type="chat",
            page_size=20,
            sort_type="ByCreateTimeDesc",
        )
        fake_run_agent.backfill_recent_feishu_messages.assert_called_once()
        backfill_args, backfill_kwargs = fake_run_agent.backfill_recent_feishu_messages.call_args
        self.assertEqual(backfill_kwargs["session_scope_id"], "feishu:thread_123")
        self.assertEqual(backfill_kwargs["chat_id"], "chat_123")
        self.assertEqual(backfill_args[0][0]["user_prompt"], "用户问题")
        self.assertEqual(backfill_args[0][0]["assistant_reply_visible"], "助手回复")


if __name__ == "__main__":
    unittest.main()
