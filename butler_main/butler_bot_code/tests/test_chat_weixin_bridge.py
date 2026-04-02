from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from agents_os.contracts import DeliverySession, OutputBundle, TextBlock
from butler_main.chat.weixi.bridge import (
    WeixinOfficialBridgeService,
    build_bridge_url,
    create_weixin_bridge_http_server,
    process_weixin_webhook_event,
)


class ChatWeixinBridgeTests(unittest.TestCase):
    def test_process_weixin_webhook_event_returns_structured_payload(self) -> None:
        def fake_run(prompt=None, **kwargs):
            self.assertEqual(prompt, "你好，Butler")
            self.assertEqual(kwargs["invocation_metadata"]["channel"], "weixin")
            return "已收到"

        fake_run.get_turn_output_bundle = lambda: OutputBundle(text_blocks=[TextBlock(text="已收到")])
        fake_run.get_turn_delivery_session = lambda: DeliverySession(
            platform="weixin",
            mode="reply",
            target="wx-user-1",
            target_type="open_id",
            metadata={"weixin.message_id": "wx-mid-1"},
        )
        fake_run.get_turn_delivery_plan = lambda: None

        payload = process_weixin_webhook_event(
            {
                "message": {
                    "message_id": "wx-mid-1",
                    "conversation_id": "conv-1",
                    "content": {"text": "你好，Butler"},
                },
                "sender": {"open_id": "wx-user-1"},
            },
            run_agent_fn=fake_run,
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["channel"], "weixin")
        self.assertEqual(payload["reply"], "已收到")
        self.assertEqual(payload["output_bundle"]["text_blocks"], ["已收到"])
        self.assertEqual(payload["delivery_session"]["target"], "wx-user-1")

    def test_build_bridge_url_normalizes_path(self) -> None:
        self.assertEqual(
            build_bridge_url(host="127.0.0.1", port=8789, path="weixin/webhook"),
            "http://127.0.0.1:8789/weixin/webhook",
        )

    def test_official_bridge_service_queues_updates_and_tracks_outbox(self) -> None:
        service = WeixinOfficialBridgeService()
        queued = service.enqueue_webhook_event(
            {
                "message": {
                    "message_id": "wx-mid-q1",
                    "session_id": "session-q1",
                    "content": {"text": "排队消息"},
                },
                "sender": {"open_id": "wx-user-q1"},
            }
        )

        self.assertEqual(queued["seq"], 1)
        update_payload = service.get_updates(cursor="")
        self.assertEqual(update_payload["ret"], 0)
        self.assertEqual(update_payload["msgs"][0]["from_user_id"], "wx-user-q1")
        self.assertEqual(update_payload["msgs"][0]["item_list"][0]["text_item"]["text"], "排队消息")
        self.assertEqual(update_payload["get_updates_buf"], "1")
        self.assertEqual(service.get_updates(cursor="1")["msgs"], [])

        service.record_sendmessage({"msg": {"to_user_id": "wx-user-q1", "item_list": [{"type": 1}]}})
        snapshot = service.snapshot()
        self.assertEqual(len(snapshot["outbox"]), 1)

    def test_official_bridge_http_endpoints_roundtrip(self) -> None:
        def fake_run(prompt=None, **kwargs):
            return str(prompt or "")

        server = create_weixin_bridge_http_server(run_agent_fn=fake_run, host="127.0.0.1", port=0)
        try:
            host, port = server.server_address

            import threading

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://{host}:{port}"

            ingress_req = Request(
                f"{base_url}/weixin/bridge/ingress",
                data=json.dumps(
                    {
                        "message": {
                            "message_id": "wx-mid-http-1",
                            "content": {"text": "HTTP 入站"},
                        },
                        "sender": {"open_id": "wx-http-user"},
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            ingress_payload = json.loads(urlopen(ingress_req).read().decode("utf-8"))
            self.assertTrue(ingress_payload["queued"])

            updates_req = Request(
                f"{base_url}/ilink/bot/getupdates",
                data=json.dumps({"get_updates_buf": ""}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            updates_payload = json.loads(urlopen(updates_req).read().decode("utf-8"))
            self.assertEqual(updates_payload["ret"], 0)
            self.assertEqual(updates_payload["msgs"][0]["from_user_id"], "wx-http-user")

            send_req = Request(
                f"{base_url}/ilink/bot/sendmessage",
                data=json.dumps({"msg": {"to_user_id": "wx-http-user"}}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            send_payload = json.loads(urlopen(send_req).read().decode("utf-8"))
            self.assertEqual(send_payload, {})

            upload_ticket_req = Request(
                f"{base_url}/ilink/bot/getuploadurl",
                data=json.dumps({"filekey": "file-1"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            upload_ticket_payload = json.loads(urlopen(upload_ticket_req).read().decode("utf-8"))
            self.assertIn("upload_param", upload_ticket_payload)

            upload_req = Request(
                f"{base_url}/upload?encrypted_query_param={upload_ticket_payload['upload_param']}&filekey=file-1",
                data=b"ciphertext",
                headers={"Content-Type": "application/octet-stream"},
                method="POST",
            )
            with urlopen(upload_req) as upload_response:
                download_param = upload_response.headers["x-encrypted-param"]
            self.assertTrue(download_param)

            with urlopen(f"{base_url}/download?encrypted_query_param={download_param}") as download_response:
                self.assertEqual(download_response.read(), b"ciphertext")

            qr_payload = json.loads(urlopen(f"{base_url}/ilink/bot/get_bot_qrcode").read().decode("utf-8"))
            self.assertIn("qrcode_img_content", qr_payload)
            wait_payload = json.loads(
                urlopen(f"{base_url}/ilink/bot/get_qrcode_status?qrcode={qr_payload['qrcode']}").read().decode("utf-8")
            )
            self.assertEqual(wait_payload["status"], "wait")
            confirm_url = qr_payload["qrcode_img_content"]
            urlopen(confirm_url).read()
            status_payload = json.loads(
                urlopen(f"{base_url}/ilink/bot/get_qrcode_status?qrcode={qr_payload['qrcode']}").read().decode("utf-8")
            )
            self.assertEqual(status_payload["status"], "confirmed")
            self.assertEqual(status_payload["baseurl"], base_url)
        finally:
            server.shutdown()
            server.server_close()

    def test_official_bridge_can_render_qr_page_with_public_base_url(self) -> None:
        def fake_run(prompt=None, **kwargs):
            return str(prompt or "")

        server = create_weixin_bridge_http_server(
            run_agent_fn=fake_run,
            host="127.0.0.1",
            port=0,
            public_base_url="http://10.1.2.3:8789",
        )
        try:
            host, port = server.server_address

            import threading

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://{host}:{port}"

            qr_payload = json.loads(urlopen(f"{base_url}/ilink/bot/get_bot_qrcode").read().decode("utf-8"))
            self.assertEqual(
                qr_payload["qrcode_img_content"],
                f"http://10.1.2.3:8789/weixin/bridge/login/confirm?qrcode={qr_payload['qrcode']}",
            )
            self.assertEqual(
                qr_payload["qrcode_page_url"],
                f"http://10.1.2.3:8789/weixin/bridge/login/qr?qrcode={qr_payload['qrcode']}",
            )
            qr_page = urlopen(f"{base_url}/weixin/bridge/login/qr?qrcode={qr_payload['qrcode']}").read().decode("utf-8")
            self.assertIn("Butler 微信登录二维码", qr_page)
            self.assertIn("/weixin/bridge/login/qr.png?qrcode=", qr_page)
            self.assertIn("http://10.1.2.3:8789/weixin/bridge/login/confirm", qr_page)
        finally:
            server.shutdown()
            server.server_close()

    def test_official_bridge_confirm_can_fallback_to_single_waiting_login(self) -> None:
        def fake_run(prompt=None, **kwargs):
            return str(prompt or "")

        server = create_weixin_bridge_http_server(run_agent_fn=fake_run, host="127.0.0.1", port=0)
        try:
            host, port = server.server_address

            import threading

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://{host}:{port}"

            qr_payload = json.loads(urlopen(f"{base_url}/ilink/bot/get_bot_qrcode").read().decode("utf-8"))
            confirm_html = urlopen(
                f"{base_url}/weixin/bridge/login/confirm?qrcode=stale-login-token"
            ).read().decode("utf-8")
            self.assertIn("Bridge Login Confirmed", confirm_html)
            self.assertIn("requestedQrcode=stale-login-token", confirm_html)
            self.assertIn(f"resolvedQrcode={qr_payload['qrcode']}", confirm_html)

            status_payload = json.loads(
                urlopen(f"{base_url}/ilink/bot/get_qrcode_status?qrcode={qr_payload['qrcode']}").read().decode("utf-8")
            )
            self.assertEqual(status_payload["status"], "confirmed")
        finally:
            server.shutdown()
            server.server_close()

    def test_official_bridge_rejects_unknown_upload_ticket(self) -> None:
        def fake_run(prompt=None, **kwargs):
            return str(prompt or "")

        server = create_weixin_bridge_http_server(run_agent_fn=fake_run, host="127.0.0.1", port=0)
        try:
            host, port = server.server_address

            import threading

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://{host}:{port}"

            upload_req = Request(
                f"{base_url}/upload?encrypted_query_param=missing-ticket&filekey=file-1",
                data=b"ciphertext",
                headers={"Content-Type": "application/octet-stream"},
                method="POST",
            )
            with self.assertRaises(HTTPError) as raised:
                urlopen(upload_req).read()
            raised.exception.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
