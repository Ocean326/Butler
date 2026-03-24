from __future__ import annotations

import json
import sys
import threading
import unittest
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
    _resolve_login_qr_page_url,
    _write_local_login_qr_page,
    WeixinBridgeSession,
    poll_weixin_bridge_once,
    resolve_weixin_bridge_config,
    start_weixin_bridge_login,
    wait_for_weixin_bridge_login,
)


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


if __name__ == "__main__":
    unittest.main()
