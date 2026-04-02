from __future__ import annotations

import json
import os
import sys
import threading
import time
import unittest
from unittest import mock
from pathlib import Path
from urllib.request import urlopen


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
TEST_TEMP_ROOT = Path(__file__).resolve().parents[3] / "工作区" / "temp" / "pytest_runtime" / "weixin_client"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from butler_main.chat.weixi.bridge import WeixinOfficialBridgeService, create_weixin_bridge_http_server
from butler_main.chat.weixi.client import (
    WeixinBridgeConfig,
    WeixinLoginTicket,
    _ensure_logged_in_bridge_session,
    _resolve_login_qr_page_url,
    _write_local_login_qr_page,
    WeixinBridgeSession,
    poll_weixin_bridge_once,
    resolve_weixin_bridge_config,
    start_weixin_bridge_login,
    wait_for_weixin_bridge_login,
)
from butler_main.chat.weixi.dispatcher import WeixinConversationDispatcher
from butler_main.chat.weixi.session_registry import WeixinSessionRegistry
from agents_os.contracts import DeliverySession, FileAsset, ImageAsset, OutputBundle, TextBlock


class ChatWeixinClientTests(unittest.TestCase):
    def test_resolve_weixin_bridge_config_prefers_state_dir_values(self) -> None:
        temp_dir = TEST_TEMP_ROOT / "state"
        temp_dir.mkdir(parents=True, exist_ok=True)
        state_file = temp_dir / "weixin.json"
        state_file.write_text(
            json.dumps(
                {
                    "channels": {
                        "weixin": {
                            "baseUrl": "http://127.0.0.1:9011/",
                            "cdnBaseUrl": "http://127.0.0.1:9012/",
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        config = resolve_weixin_bridge_config(state_dir=str(temp_dir))

        self.assertEqual(config.bridge_base_url, "http://127.0.0.1:9011/")
        self.assertEqual(config.cdn_base_url, "http://127.0.0.1:9012/")
        self.assertTrue(config.session_file.endswith("weixin_session.json"))

    def test_resolve_login_qr_page_url_falls_back_to_scan_link_for_official_base(self) -> None:
        resolved = _resolve_login_qr_page_url(
            bridge_base_url="https://ilinkai.weixin.qq.com/",
            qrcode="abc123",
            qrcode_url="https://liteapp.weixin.qq.com/q/demo?qrcode=abc123&bot_type=3",
            qrcode_page_url="",
        )

        self.assertEqual(resolved, "https://liteapp.weixin.qq.com/q/demo?qrcode=abc123&bot_type=3")

    def test_write_local_login_qr_page_persists_html_file(self) -> None:
        temp_dir = TEST_TEMP_ROOT / "qr"
        temp_dir.mkdir(parents=True, exist_ok=True)
        config = WeixinBridgeConfig(
            bridge_base_url="https://ilinkai.weixin.qq.com/",
            cdn_base_url="https://novac2c.cdn.weixin.qq.com/c2c/",
            state_dir=str(temp_dir),
            session_file=str(temp_dir / "weixin_session.json"),
        )
        ticket = WeixinLoginTicket(
            qrcode="official-qr-1",
            qrcode_url="https://liteapp.weixin.qq.com/q/demo?qrcode=official-qr-1&bot_type=3",
            qrcode_page_url="https://liteapp.weixin.qq.com/q/demo?qrcode=official-qr-1&bot_type=3",
        )

        written = Path(_write_local_login_qr_page(config=config, ticket=ticket))

        self.assertTrue(written.is_file())
        content = written.read_text(encoding="utf-8")
        self.assertIn("official-qr-1", content)
        self.assertIn("liteapp.weixin.qq.com/q/demo", content)
        self.assertIn("data:image/png;base64,", content)
        self.assertIn("立即刷新二维码", content)
        self.assertIn("自动刷新倒计时", content)
        self.assertIn("refreshNow()", content)

    def test_ensure_logged_in_bridge_session_refreshes_expired_qr(self) -> None:
        temp_dir = TEST_TEMP_ROOT / "login_retry"
        temp_dir.mkdir(parents=True, exist_ok=True)
        config = WeixinBridgeConfig(
            bridge_base_url="https://ilinkai.weixin.qq.com/",
            cdn_base_url="https://novac2c.cdn.weixin.qq.com/c2c/",
            state_dir=str(temp_dir),
            session_file=str(temp_dir / "weixin_session.json"),
        )
        ticket_one = WeixinLoginTicket(
            qrcode="retry-1",
            qrcode_url="https://liteapp.weixin.qq.com/q/demo?qrcode=retry-1&bot_type=3",
            qrcode_page_url="https://liteapp.weixin.qq.com/q/demo?qrcode=retry-1&bot_type=3",
        )
        ticket_two = WeixinLoginTicket(
            qrcode="retry-2",
            qrcode_url="https://liteapp.weixin.qq.com/q/demo?qrcode=retry-2&bot_type=3",
            qrcode_page_url="https://liteapp.weixin.qq.com/q/demo?qrcode=retry-2&bot_type=3",
        )
        expected_session = WeixinBridgeSession(
            bridge_base_url=config.bridge_base_url,
            cdn_base_url=config.cdn_base_url,
            bot_token="token-retry",
            account_id="wx-retry-bot",
            user_id="wx-retry-user",
        )
        status_updates: list[str] = []

        with (
            mock.patch(
                "butler_main.chat.weixi.client.start_weixin_bridge_login",
                side_effect=[ticket_one, ticket_two],
            ) as start_login_mock,
            mock.patch(
                "butler_main.chat.weixi.client.wait_for_weixin_bridge_login",
                side_effect=[RuntimeError("weixin bridge login expired"), expected_session],
            ) as wait_login_mock,
            mock.patch(
                "butler_main.chat.weixi.client._write_local_login_qr_page",
                side_effect=[
                    str(temp_dir / "weixin_login_qr_1.html"),
                    str(temp_dir / "weixin_login_qr_2.html"),
                ],
            ) as write_qr_mock,
            mock.patch("butler_main.chat.weixi.client.time.sleep") as sleep_mock,
        ):
            resolved = _ensure_logged_in_bridge_session(
                config,
                login_timeout_ms=30_000,
                reuse_session=False,
                session_registry=None,
                publish_status_fn=lambda **kwargs: status_updates.append(str(kwargs.get("login_state") or "")),
            )

        self.assertEqual(resolved.account_id, "wx-retry-bot")
        self.assertEqual(start_login_mock.call_count, 2)
        self.assertEqual(wait_login_mock.call_count, 2)
        self.assertEqual(write_qr_mock.call_count, 2)
        self.assertEqual(status_updates, ["waiting_login", "waiting_login"])
        self.assertTrue(Path(config.session_file).is_file())
        saved = WeixinBridgeSession.load(config.session_file)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.account_id if saved is not None else "", "wx-retry-bot")
        sleep_mock.assert_called_once()

    def test_poll_weixin_bridge_once_delivers_reply_back_to_bridge(self) -> None:
        def fake_run(prompt=None, **kwargs):
            self.assertEqual(str(prompt or ""), "客户端轮询测试")
            self.assertEqual(kwargs["invocation_metadata"]["channel"], "weixin")
            return "Butler 已回"

        bridge_state = WeixinOfficialBridgeService()
        server = create_weixin_bridge_http_server(
            run_agent_fn=fake_run,
            bridge_state=bridge_state,
            host="127.0.0.1",
            port=0,
        )
        try:
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            base_url = f"http://{host}:{port}/"
            config = resolve_weixin_bridge_config(
                bridge_base_url=base_url,
                cdn_base_url=base_url,
            )
            ticket = start_weixin_bridge_login(config)
            self.assertTrue(ticket.qrcode)
            self.assertTrue(ticket.qrcode_url.startswith(base_url))
            self.assertTrue(ticket.qrcode_page_url.startswith(base_url))
            urlopen(ticket.qrcode_page_url).read()
            urlopen(ticket.qrcode_url).read()

            session = wait_for_weixin_bridge_login(config, ticket=ticket, timeout_ms=5_000)
            self.assertIsInstance(session, WeixinBridgeSession)
            self.assertTrue(session.bot_token)
            self.assertTrue(session.account_id)

            bridge_state.enqueue_webhook_event(
                {
                    "message": {
                        "message_id": "wx-client-1",
                        "session_id": "wx-session-1",
                        "content": {"text": "客户端轮询测试"},
                    },
                    "sender": {"open_id": "wx-client-user"},
                }
            )
            result = poll_weixin_bridge_once(session, run_agent_fn=fake_run, timeout_ms=5_000)

            self.assertEqual(result.received_count, 1)
            self.assertEqual(result.delivered_count, 1)
            snapshot = bridge_state.snapshot()
            self.assertEqual(len(snapshot["outbox"]), 1)
            sent = snapshot["outbox"][0]
            self.assertEqual(sent["msg"]["to_user_id"], "wx-client-user")
            self.assertEqual(sent["msg"]["item_list"][0]["text_item"]["text"], "Butler 已回")
        finally:
            server.shutdown()
            server.server_close()

    def test_poll_weixin_bridge_once_dispatches_multi_user_batch_in_parallel(self) -> None:
        runtime_state = {"active": 0, "overlap": False}
        callback_calls: list[tuple[str, str]] = []
        lock = threading.Lock()

        def fake_run(prompt=None, **kwargs):
            event = kwargs["invocation_metadata"]["weixin_event"]
            self.assertIn(str(event.get("from_user_id") or ""), {"wx-user-a", "wx-user-b"})
            with lock:
                runtime_state["active"] += 1
                if runtime_state["active"] >= 2:
                    runtime_state["overlap"] = True
            try:
                time.sleep(0.15)
            finally:
                with lock:
                    runtime_state["active"] -= 1
            return f"回:{prompt}"

        def fake_after_reply(prompt: str, reply: str) -> None:
            with lock:
                callback_calls.append((prompt, reply))

        bridge_state = WeixinOfficialBridgeService()
        server = create_weixin_bridge_http_server(
            run_agent_fn=fake_run,
            bridge_state=bridge_state,
            host="127.0.0.1",
            port=0,
        )
        dispatcher = None
        try:
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            base_url = f"http://{host}:{port}/"
            config = resolve_weixin_bridge_config(bridge_base_url=base_url, cdn_base_url=base_url)
            ticket = start_weixin_bridge_login(config)
            urlopen(ticket.qrcode_url).read()
            session = wait_for_weixin_bridge_login(config, ticket=ticket, timeout_ms=5_000)
            registry = WeixinSessionRegistry()
            dispatcher = WeixinConversationDispatcher(registry=registry, max_workers=2)

            bridge_state.enqueue_webhook_event(
                {
                    "message": {
                        "message_id": "wx-client-par-1",
                        "session_id": "wx-session-a",
                        "content": {"text": "用户A"},
                    },
                    "sender": {"open_id": "wx-user-a"},
                }
            )
            bridge_state.enqueue_webhook_event(
                {
                    "message": {
                        "message_id": "wx-client-par-2",
                        "session_id": "wx-session-b",
                        "content": {"text": "用户B"},
                    },
                    "sender": {"open_id": "wx-user-b"},
                }
            )

            result = poll_weixin_bridge_once(
                session,
                run_agent_fn=fake_run,
                timeout_ms=5_000,
                dispatcher=dispatcher,
                session_registry=registry,
                on_reply_sent=fake_after_reply,
            )

            self.assertEqual(result.received_count, 2)
            self.assertEqual(result.delivered_count, 2)
            self.assertTrue(runtime_state["overlap"])
            self.assertEqual(set(callback_calls), {("用户A", "回:用户A"), ("用户B", "回:用户B")})
            snapshot = bridge_state.snapshot()
            self.assertEqual({entry["msg"]["to_user_id"] for entry in snapshot["outbox"]}, {"wx-user-a", "wx-user-b"})
            status_snapshot = registry.snapshot(limit=4)
            self.assertEqual(status_snapshot["active_conversation_count"], 2)
            self.assertEqual(
                {
                    item["conversation_key"]
                    for item in status_snapshot["recent_conversations"]
                },
                {
                    "weixin:bridge-bot@im.bot:dm:wx-user-a",
                    "weixin:bridge-bot@im.bot:dm:wx-user-b",
                },
            )
        finally:
            if dispatcher is not None:
                dispatcher.shutdown(wait=True)
            server.shutdown()
            server.server_close()

    def test_poll_weixin_bridge_once_keeps_same_conversation_serialized(self) -> None:
        runtime_state = {"max_active_for_actor": 0}
        active_by_actor: dict[str, int] = {}
        lock = threading.Lock()

        def fake_run(prompt=None, **kwargs):
            actor_id = str(kwargs["invocation_metadata"]["weixin_event"].get("from_user_id") or "")
            with lock:
                active_by_actor[actor_id] = active_by_actor.get(actor_id, 0) + 1
                runtime_state["max_active_for_actor"] = max(runtime_state["max_active_for_actor"], active_by_actor[actor_id])
            try:
                time.sleep(0.05)
            finally:
                with lock:
                    active_by_actor[actor_id] -= 1
            return f"回:{prompt}"

        bridge_state = WeixinOfficialBridgeService()
        server = create_weixin_bridge_http_server(
            run_agent_fn=fake_run,
            bridge_state=bridge_state,
            host="127.0.0.1",
            port=0,
        )
        dispatcher = None
        try:
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            base_url = f"http://{host}:{port}/"
            config = resolve_weixin_bridge_config(bridge_base_url=base_url, cdn_base_url=base_url)
            ticket = start_weixin_bridge_login(config)
            urlopen(ticket.qrcode_url).read()
            session = wait_for_weixin_bridge_login(config, ticket=ticket, timeout_ms=5_000)
            registry = WeixinSessionRegistry()
            dispatcher = WeixinConversationDispatcher(registry=registry, max_workers=2)

            bridge_state.enqueue_webhook_event(
                {
                    "message": {
                        "message_id": "wx-client-seq-1",
                        "session_id": "wx-session-c",
                        "content": {"text": "第一条"},
                    },
                    "sender": {"open_id": "wx-user-c"},
                }
            )
            bridge_state.enqueue_webhook_event(
                {
                    "message": {
                        "message_id": "wx-client-seq-2",
                        "session_id": "wx-session-c",
                        "content": {"text": "第二条"},
                    },
                    "sender": {"open_id": "wx-user-c"},
                }
            )

            result = poll_weixin_bridge_once(
                session,
                run_agent_fn=fake_run,
                timeout_ms=5_000,
                dispatcher=dispatcher,
                session_registry=registry,
            )

            self.assertEqual(result.received_count, 2)
            self.assertEqual(result.delivered_count, 2)
            self.assertEqual(runtime_state["max_active_for_actor"], 1)
            snapshot = bridge_state.snapshot()
            self.assertEqual(
                [entry["msg"]["item_list"][0]["text_item"]["text"] for entry in snapshot["outbox"]],
                ["回:第一条", "回:第二条"],
            )
            self.assertEqual(registry.snapshot()["active_conversation_count"], 1)
        finally:
            if dispatcher is not None:
                dispatcher.shutdown(wait=True)
            server.shutdown()
            server.server_close()

    def test_poll_weixin_bridge_once_uploads_media_before_sendmessage(self) -> None:
        temp_dir = TEST_TEMP_ROOT / "outbound_media"
        temp_dir.mkdir(parents=True, exist_ok=True)
        image_path = temp_dir / "reply.png"
        file_path = temp_dir / "summary.txt"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nwx-media")
        file_path.write_text("hello weixin file", encoding="utf-8")

        def fake_run(prompt=None, **kwargs):
            self.assertEqual(str(prompt or ""), "发附件给我")
            return "已发图片和文件"

        fake_run.get_turn_output_bundle = lambda: OutputBundle(
            text_blocks=[TextBlock(text="【结论】已发图片和文件")],
            images=[ImageAsset(path=str(image_path))],
            files=[FileAsset(path=str(file_path), description="summary")],
        )
        fake_run.get_turn_delivery_session = lambda: DeliverySession(
            platform="weixin",
            mode="reply",
            target="wx-client-user-2",
            target_type="open_id",
            metadata={"weixin.context_token": "ctx-media-1"},
        )

        bridge_state = WeixinOfficialBridgeService()
        server = create_weixin_bridge_http_server(
            run_agent_fn=fake_run,
            bridge_state=bridge_state,
            host="127.0.0.1",
            port=0,
        )
        try:
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            base_url = f"http://{host}:{port}/"
            config = resolve_weixin_bridge_config(bridge_base_url=base_url, cdn_base_url=base_url)
            ticket = start_weixin_bridge_login(config)
            urlopen(ticket.qrcode_url).read()
            session = wait_for_weixin_bridge_login(config, ticket=ticket, timeout_ms=5_000)

            bridge_state.enqueue_webhook_event(
                {
                    "message": {
                        "message_id": "wx-client-media-1",
                        "session_id": "wx-session-media-1",
                        "content": {"text": "发附件给我"},
                    },
                    "sender": {"open_id": "wx-client-user-2"},
                }
            )
            result = poll_weixin_bridge_once(session, run_agent_fn=fake_run, timeout_ms=5_000)

            self.assertEqual(result.received_count, 1)
            self.assertEqual(result.delivered_count, 3)
            snapshot = bridge_state.snapshot()
            self.assertEqual(len(snapshot["outbox"]), 3)
            self.assertGreaterEqual(snapshot["upload_count"], 2)
            self.assertEqual(snapshot["outbox"][0]["msg"]["item_list"][0]["text_item"]["text"], "【结论】已发图片和文件")
            self.assertIn("media", snapshot["outbox"][1]["msg"]["item_list"][0]["image_item"])
            self.assertNotIn("local_path", snapshot["outbox"][1]["msg"]["item_list"][0]["image_item"])
            self.assertIn("media", snapshot["outbox"][2]["msg"]["item_list"][0]["file_item"])
            self.assertNotIn("local_path", snapshot["outbox"][2]["msg"]["item_list"][0]["file_item"])
        finally:
            server.shutdown()
            server.server_close()

    def test_poll_weixin_bridge_once_resolves_relative_media_paths_from_butler_root(self) -> None:
        temp_dir = TEST_TEMP_ROOT / "relative_media"
        temp_dir.mkdir(parents=True, exist_ok=True)
        image_path = temp_dir / "reply.png"
        file_path = temp_dir / "summary.txt"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nwx-relative")
        file_path.write_text("hello relative weixin file", encoding="utf-8")
        relative_image = f"./{image_path.relative_to(REPO_ROOT).as_posix()}"
        relative_file = f"./{file_path.relative_to(REPO_ROOT).as_posix()}"

        def fake_run(prompt=None, **kwargs):
            self.assertEqual(str(prompt or ""), "发相对路径附件")
            return "已发相对路径图片和文件"

        fake_run.get_turn_output_bundle = lambda: OutputBundle(
            text_blocks=[TextBlock(text="【结论】已发相对路径图片和文件")],
            images=[ImageAsset(path=relative_image)],
            files=[FileAsset(path=relative_file, description="summary")],
        )
        fake_run.get_turn_delivery_session = lambda: DeliverySession(
            platform="weixin",
            mode="reply",
            target="wx-client-user-3",
            target_type="open_id",
            metadata={"weixin.context_token": "ctx-media-relative-1"},
        )

        bridge_state = WeixinOfficialBridgeService()
        server = create_weixin_bridge_http_server(
            run_agent_fn=fake_run,
            bridge_state=bridge_state,
            host="127.0.0.1",
            port=0,
        )
        original_cwd = os.getcwd()
        try:
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            base_url = f"http://{host}:{port}/"
            config = resolve_weixin_bridge_config(bridge_base_url=base_url, cdn_base_url=base_url)
            ticket = start_weixin_bridge_login(config)
            urlopen(ticket.qrcode_url).read()
            session = wait_for_weixin_bridge_login(config, ticket=ticket, timeout_ms=5_000)

            os.chdir(REPO_ROOT / "butler_main" / "chat")
            bridge_state.enqueue_webhook_event(
                {
                    "message": {
                        "message_id": "wx-client-media-relative-1",
                        "session_id": "wx-session-media-relative-1",
                        "content": {"text": "发相对路径附件"},
                    },
                    "sender": {"open_id": "wx-client-user-3"},
                }
            )
            result = poll_weixin_bridge_once(session, run_agent_fn=fake_run, timeout_ms=5_000)

            self.assertEqual(result.received_count, 1)
            self.assertEqual(result.delivered_count, 3)
            snapshot = bridge_state.snapshot()
            self.assertEqual(len(snapshot["outbox"]), 3)
            self.assertGreaterEqual(snapshot["upload_count"], 2)
            self.assertIn("media", snapshot["outbox"][1]["msg"]["item_list"][0]["image_item"])
            self.assertIn("media", snapshot["outbox"][2]["msg"]["item_list"][0]["file_item"])
        finally:
            os.chdir(original_cwd)
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
