from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path
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

from butler_main.chat.core import ChatCoreService, WeixinBindingConfig, _resolve_weixin_bindings, create_chat_core_http_server


class ChatCoreServerTests(unittest.TestCase):
    def test_core_server_exposes_health_and_chat(self) -> None:
        observed = {}

        def fake_run_agent(prompt: str, **kwargs) -> str:
            observed["prompt"] = prompt
            observed["invocation_metadata"] = dict(kwargs.get("invocation_metadata") or {})
            return f"echo:{prompt}"

        def fake_after_reply(prompt: str, reply: str) -> None:
            observed["persisted"] = (prompt, reply)

        service = ChatCoreService(
            run_agent_fn=fake_run_agent,
            after_reply_fn=fake_after_reply,
            config_path="C:/workspace/butler_bot.json",
            channels=("cli",),
            weixin_state_dir="C:/workspace/weixin_state",
            weixin_official_bridge_base_url="https://ilinkai.weixin.qq.com",
            weixin_official_cdn_base_url="https://novac2c.cdn.weixin.qq.com/c2c",
            weixin_status_provider=lambda: {
                "connected": True,
                "login_state": "ready",
                "account_id": "wx-bot-1",
                "active_conversation_count": 2,
                "running_conversation_count": 1,
                "recent_conversations": [
                    {
                        "conversation_key": "weixin:wx-bot-1:dm:user-a",
                        "in_flight": True,
                        "last_error": "",
                    }
                ],
            },
        )
        server = create_chat_core_http_server(service, host="127.0.0.1", port=0)
        try:
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            index_html = urlopen(f"http://{host}:{port}/").read().decode("utf-8")
            health = json.loads(urlopen(f"http://{host}:{port}/health").read().decode("utf-8"))
            self.assertTrue(health["ok"])
            self.assertTrue(health["channels"]["cli"]["enabled"])
            self.assertEqual(health["weixin_state_dir"], "C:/workspace/weixin_state")
            self.assertEqual(health["weixin_bindings"][0]["binding_id"], "default")
            self.assertEqual(health["weixin_runtime"]["active_conversation_count"], 2)
            self.assertEqual(health["weixin_runtime"]["recent_conversations"][0]["conversation_key"], "weixin:wx-bot-1:dm:user-a")
            self.assertIn("微信活跃会话：2", index_html)

            request = Request(
                f"http://{host}:{port}/v1/chat",
                data=json.dumps({"prompt": "hello core", "session_id": "cli_session_test"}).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            payload = json.loads(urlopen(request).read().decode("utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["reply"], "echo:hello core")
            self.assertEqual(payload["session_id"], "cli_session_test")
            self.assertEqual(observed["prompt"], "hello core")
            self.assertEqual(observed["invocation_metadata"]["channel"], "cli")
            self.assertEqual(observed["invocation_metadata"]["session_id"], "cli_session_test")
            self.assertEqual(observed["persisted"], ("hello core", "echo:hello core"))
        finally:
            server.shutdown()
            server.server_close()

    def test_core_server_health_renders_multi_binding_runtime(self) -> None:
        service = ChatCoreService(
            run_agent_fn=lambda prompt, **kwargs: str(prompt),
            after_reply_fn=lambda prompt, reply: None,
            config_path="C:/workspace/butler_bot.json",
            channels=("weixin",),
            weixin_state_dir="C:/workspace/weixin_state_a",
            weixin_official_bridge_base_url="https://ilinkai.weixin.qq.com",
            weixin_official_cdn_base_url="https://novac2c.cdn.weixin.qq.com/c2c",
            weixin_bindings=(
                WeixinBindingConfig(
                    binding_id="wx_a",
                    state_dir="C:/workspace/weixin_state_a",
                    bridge_base_url="https://bridge-a.example/",
                    cdn_base_url="https://cdn-a.example/",
                ),
                WeixinBindingConfig(
                    binding_id="wx_b",
                    state_dir="C:/workspace/weixin_state_b",
                    bridge_base_url="https://bridge-b.example/",
                    cdn_base_url="https://cdn-b.example/",
                ),
            ),
            weixin_status_provider=lambda: {
                "connected": True,
                "login_state": "ready",
                "binding_count": 2,
                "active_conversation_count": 3,
                "running_conversation_count": 1,
                "recent_conversations": [
                    {
                        "binding_id": "wx_a",
                        "conversation_key": "weixin:wx-bot-a:dm:user-a",
                        "in_flight": True,
                        "last_error": "",
                    }
                ],
                "bindings": [
                    {
                        "binding_id": "wx_a",
                        "connected": True,
                        "account_id": "wx-bot-a",
                        "active_conversation_count": 2,
                        "running_conversation_count": 1,
                        "last_error": "",
                    },
                    {
                        "binding_id": "wx_b",
                        "connected": False,
                        "account_id": "wx-bot-b",
                        "active_conversation_count": 1,
                        "running_conversation_count": 0,
                        "last_error": "token expired",
                    },
                ],
            },
        )
        server = create_chat_core_http_server(service, host="127.0.0.1", port=0)
        try:
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            index_html = urlopen(f"http://{host}:{port}/").read().decode("utf-8")
            health = json.loads(urlopen(f"http://{host}:{port}/health").read().decode("utf-8"))
            self.assertEqual(len(health["weixin_bindings"]), 2)
            self.assertEqual(health["weixin_bindings"][1]["binding_id"], "wx_b")
            self.assertEqual(health["weixin_runtime"]["binding_count"], 2)
            self.assertEqual(health["weixin_runtime"]["bindings"][1]["last_error"], "token expired")
            self.assertIn("绑定数：2", index_html)
            self.assertIn("wx_a", index_html)
            self.assertIn("wx_b", index_html)
        finally:
            server.shutdown()
            server.server_close()

    def test_resolve_weixin_bindings_prefers_config_bindings(self) -> None:
        bindings = _resolve_weixin_bindings(
            config={
                "weixin": {
                    "bindings": [
                        {
                            "binding_id": "alpha",
                            "state_dir": "C:/workspace/alpha",
                            "bridge_base_url": "https://bridge-alpha.example/",
                            "cdn_base_url": "https://cdn-alpha.example/",
                            "reuse_session": False,
                        },
                        {
                            "binding_id": "beta",
                            "enabled": False,
                            "state_dir": "C:/workspace/beta",
                        },
                    ]
                }
            },
            default_state_dir="C:/workspace/default",
            default_bridge_base_url="https://default-bridge.example/",
            default_cdn_base_url="https://default-cdn.example/",
        )

        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].binding_id, "alpha")
        self.assertEqual(bindings[0].state_dir, "C:/workspace/alpha")
        self.assertFalse(bindings[0].reuse_session)


if __name__ == "__main__":
    unittest.main()
