import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.chat.feishu_bot.api import FeishuApiClient


class _FakeRequests:
    def __init__(self) -> None:
        self.token_calls = 0
        self.get_calls = []
        self.patch_calls = []

    def post(self, url, json=None, data=None, files=None, headers=None, timeout=None):
        if "tenant_access_token/internal" in url:
            self.token_calls += 1
            return _FakeResponse({"code": 0, "tenant_access_token": f"tok_{self.token_calls}", "expire": 7200})
        return _FakeResponse({"code": 0})

    def get(self, url, headers=None, params=None, timeout=None):
        self.get_calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        return _FakeResponse({"code": 0})

    def patch(self, url, headers=None, json=None, timeout=None):
        self.patch_calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _FakeResponse({"code": 0})


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.headers = {}
        self.content = b""

    def json(self):
        return self._payload


class ChatFeishuApiTests(unittest.TestCase):
    def test_sync_runtime_config_clears_cached_token_when_credentials_change(self) -> None:
        current = {"app_id": "cli_a", "app_secret": "sec_a"}
        requests_module = _FakeRequests()
        client = FeishuApiClient(config_getter=lambda: current, requests_module=requests_module)

        token_a = client.get_tenant_access_token()
        token_b = client.get_tenant_access_token()

        self.assertEqual(token_a, "tok_1")
        self.assertEqual(token_b, "tok_1")
        self.assertEqual(requests_module.token_calls, 1)

        current["app_secret"] = "sec_b"
        token_c = client.get_tenant_access_token()

        self.assertEqual(token_c, "tok_2")
        self.assertEqual(requests_module.token_calls, 2)

    def test_run_preflight_reports_missing_keys(self) -> None:
        client = FeishuApiClient(config_getter=lambda: {"app_id": ""}, requests_module=_FakeRequests())

        result = client.run_preflight(auth_probe=False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["missing"], ["app_id", "app_secret"])

    def test_get_message_calls_message_detail_endpoint(self) -> None:
        requests_module = _FakeRequests()
        client = FeishuApiClient(
            config_getter=lambda: {"app_id": "cli_a", "app_secret": "sec_a"},
            requests_module=requests_module,
        )

        ok, data = client.get_message("om_123")

        self.assertTrue(ok)
        self.assertEqual(data["code"], 0)
        self.assertEqual(
            requests_module.get_calls[-1]["url"],
            "https://open.feishu.cn/open-apis/im/v1/messages/om_123",
        )
        self.assertIsNone(requests_module.get_calls[-1]["params"])

    def test_list_messages_passes_recent_history_query_params(self) -> None:
        requests_module = _FakeRequests()
        client = FeishuApiClient(
            config_getter=lambda: {"app_id": "cli_a", "app_secret": "sec_a"},
            requests_module=requests_module,
        )

        ok, data = client.list_messages(
            container_id="oc_xxx",
            container_id_type="chat",
            page_size=10,
            sort_type="ByCreateTimeDesc",
            page_token="pt_1",
        )

        self.assertTrue(ok)
        self.assertEqual(data["code"], 0)
        self.assertEqual(
            requests_module.get_calls[-1]["url"],
            "https://open.feishu.cn/open-apis/im/v1/messages",
        )
        self.assertEqual(
            requests_module.get_calls[-1]["params"],
            {
                "container_id_type": "chat",
                "container_id": "oc_xxx",
                "page_size": 10,
                "sort_type": "ByCreateTimeDesc",
                "page_token": "pt_1",
            },
        )

    def test_update_raw_message_calls_patch_endpoint(self) -> None:
        requests_module = _FakeRequests()
        client = FeishuApiClient(
            config_getter=lambda: {"app_id": "cli_a", "app_secret": "sec_a"},
            requests_module=requests_module,
        )

        ok, data = client.update_raw_message("om_123", "interactive", {"schema": "2.0"})

        self.assertTrue(ok)
        self.assertEqual(data["code"], 0)
        self.assertEqual(
            requests_module.patch_calls[-1]["url"],
            "https://open.feishu.cn/open-apis/im/v1/messages/om_123",
        )
        self.assertEqual(
            requests_module.patch_calls[-1]["json"],
            {"content": "{\"schema\": \"2.0\"}", "msg_type": "interactive"},
        )


if __name__ == "__main__":
    unittest.main()
