from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
TEST_TEMP_ROOT = Path(__file__).resolve().parents[3] / "工作区" / "temp" / "pytest_runtime" / "weixin_official"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from agents_os.contracts import DeliverySession, FileAsset, ImageAsset, OutputBundle, TextBlock
from butler_main.chat.weixi.bridge import create_weixin_bridge_http_server
from butler_main.chat.weixi.delivery import WeixinDeliveryAdapter
from butler_main.chat.weixi.official import (
    build_getupdates_response,
    fetch_bridge_qr_link,
    write_bridge_qr_link_markdown,
    write_qr_link_markdown,
)


class ChatWeixinOfficialTests(unittest.TestCase):
    def test_delivery_adapter_builds_official_sendmessage_request(self) -> None:
        adapter = WeixinDeliveryAdapter()
        session = DeliverySession(
            platform="weixin",
            mode="reply",
            target="wx-user-1",
            target_type="open_id",
            metadata={"weixin.context_token": "ctx-1", "weixin.message_id": "wx-mid-1"},
        )
        plan = adapter.create(
            session,
            OutputBundle(text_blocks=[TextBlock(text="你好，微信")]),
        )

        self.assertEqual(plan.rendered_text, "你好，微信")
        self.assertEqual(len(plan.official_requests), 1)
        request = plan.official_requests[0]
        self.assertEqual(request["msg"]["to_user_id"], "wx-user-1")
        self.assertEqual(request["msg"]["context_token"], "ctx-1")
        self.assertEqual(request["msg"]["item_list"][0]["text_item"]["text"], "你好，微信")

    def test_delivery_adapter_builds_image_and_file_requests(self) -> None:
        temp_dir = TEST_TEMP_ROOT / "delivery_media"
        temp_dir.mkdir(parents=True, exist_ok=True)
        image_path = temp_dir / "wx_image.png"
        file_path = temp_dir / "wx_file.txt"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nwx")
        file_path.write_text("hello file", encoding="utf-8")

        adapter = WeixinDeliveryAdapter()
        session = DeliverySession(
            platform="weixin",
            mode="reply",
            target="wx-user-2",
            target_type="open_id",
            metadata={"weixin.context_token": "ctx-2"},
        )
        plan = adapter.create(
            session,
            OutputBundle(
                text_blocks=[TextBlock(text="【结论】已生成附件")],
                images=[ImageAsset(path=str(image_path))],
                files=[FileAsset(path=str(file_path), description="report")],
            ),
        )

        self.assertEqual(len(plan.official_requests), 3)
        self.assertEqual(plan.official_requests[0]["msg"]["item_list"][0]["text_item"]["text"], "【结论】已生成附件")
        self.assertEqual(plan.official_requests[1]["msg"]["item_list"][0]["image_item"]["local_path"], str(image_path))
        self.assertEqual(plan.official_requests[2]["msg"]["item_list"][0]["file_item"]["local_path"], str(file_path))

    def test_getupdates_response_matches_official_shape(self) -> None:
        payload = build_getupdates_response(messages=[{"message_id": 1}], cursor="cursor-1")

        self.assertEqual(payload["ret"], 0)
        self.assertEqual(payload["msgs"], [{"message_id": 1}])
        self.assertEqual(payload["get_updates_buf"], "cursor-1")
        self.assertIn("longpolling_timeout_ms", payload)

    def test_write_qr_link_markdown_persists_utf8_entry(self) -> None:
        temp_dir = TEST_TEMP_ROOT
        temp_dir.mkdir(parents=True, exist_ok=True)
        target = temp_dir / "weixin_qr_login_test.md"
        written = write_qr_link_markdown(target)

        self.assertEqual(written, target)
        content = target.read_text(encoding="utf-8")
        self.assertIn("http://127.0.0.1:18789/", content)
        self.assertIn("butler-core", content)

    def test_fetch_and_write_bridge_qr_link_markdown(self) -> None:
        def fake_run(prompt=None, **kwargs):
            return str(prompt or "")

        server = create_weixin_bridge_http_server(run_agent_fn=fake_run, host="127.0.0.1", port=0)
        try:
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            base_url = f"http://{host}:{port}/"
            qr_link = fetch_bridge_qr_link(base_url)
            self.assertTrue(qr_link.qrcode)
            self.assertTrue(qr_link.qrcode_url.startswith(base_url))
            self.assertTrue(qr_link.qrcode_page_url.startswith(base_url))
            urlopen(qr_link.qrcode_page_url).read()
            urlopen(qr_link.qrcode_url).read()

            temp_dir = TEST_TEMP_ROOT
            temp_dir.mkdir(parents=True, exist_ok=True)
            target = temp_dir / "weixin_bridge_qr_login_test.md"
            written = write_bridge_qr_link_markdown(target, bridge_base_url=base_url)
            self.assertEqual(written, target)
            content = target.read_text(encoding="utf-8")
            self.assertIn(base_url, content)
            self.assertIn("cdnBaseUrl", content)
            self.assertIn("Butler Weixin Bridge Login", content)
            self.assertIn("当前二维码网页", content)
        finally:
            server.shutdown()
            server.server_close()

    def test_fetch_bridge_qr_link_uses_scan_link_when_upstream_has_no_page(self) -> None:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import json

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = json.dumps(
                    {
                        "qrcode": "official-qr-1",
                        "qrcode_img_content": "https://liteapp.weixin.qq.com/q/demo?qrcode=official-qr-1&bot_type=3",
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return None

        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        try:
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            qr_link = fetch_bridge_qr_link(f"http://{host}:{port}/")
            self.assertEqual(qr_link.qrcode, "official-qr-1")
            self.assertEqual(
                qr_link.qrcode_url,
                "https://liteapp.weixin.qq.com/q/demo?qrcode=official-qr-1&bot_type=3",
            )
            self.assertEqual(qr_link.qrcode_page_url, qr_link.qrcode_url)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
