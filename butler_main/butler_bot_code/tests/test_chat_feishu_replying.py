import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.chat.feishu_bot.api import FeishuApiClient
from butler_main.chat.feishu_bot.replying import FeishuReplyService


class _FakeRequests:
    def __init__(self) -> None:
        self.calls = []
        self.patch_calls = []

    def post(self, url, json=None, data=None, files=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "data": data, "files": files, "headers": headers, "timeout": timeout})
        if "tenant_access_token/internal" in url:
            return _FakeResponse({"code": 0, "tenant_access_token": "tok_123", "expire": 7200})
        msg_type = ((json or {}).get("msg_type") or "") if isinstance(json, dict) else ""
        if msg_type == "interactive":
            return _FakeResponse({"code": 999, "msg": "interactive failed"})
        return _FakeResponse({"code": 0, "msg": "ok"})

    def get(self, url, headers=None, timeout=None):
        raise AssertionError("unexpected get() call")

    def patch(self, url, json=None, headers=None, timeout=None):
        self.patch_calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return _FakeResponse({"code": 0, "msg": "ok"})


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.headers = {}
        self.content = b""

    def json(self):
        return self._payload


class ChatFeishuReplyingTests(unittest.TestCase):
    def test_reply_service_falls_back_from_interactive_to_post(self) -> None:
        requests_module = _FakeRequests()
        api_client = FeishuApiClient(config_getter=lambda: {"app_id": "cli_x", "app_secret": "sec_y"}, requests_module=requests_module)
        service = FeishuReplyService(
            api_client=api_client,
            config_getter=lambda: {"workspace_root": "."},
            markdown_to_interactive_card=lambda text, include_actions: {"schema": "2.0", "body": {"elements": [{"tag": "markdown", "content": text}]}},
            markdown_to_feishu_post=lambda text: {"zh_cn": {"title": "回复", "content": [[{"tag": "md", "text": text}]]}},
        )

        ok = service.reply_message("mid_123", "hello reply", use_interactive=True, include_card_actions=True)

        self.assertTrue(ok)
        msg_types = [call["json"]["msg_type"] for call in requests_module.calls if isinstance(call.get("json"), dict) and call["json"].get("msg_type")]
        self.assertEqual(msg_types, ["interactive", "post"])

    def test_create_interactive_reply_returns_reply_message_id(self) -> None:
        class _CreateReplyRequests(_FakeRequests):
            def post(self, url, json=None, data=None, files=None, headers=None, timeout=None):
                self.calls.append({"url": url, "json": json, "data": data, "files": files, "headers": headers, "timeout": timeout})
                if "tenant_access_token/internal" in url:
                    return _FakeResponse({"code": 0, "tenant_access_token": "tok_123", "expire": 7200})
                return _FakeResponse({"code": 0, "data": {"message_id": "om_reply_1"}})

        requests_module = _CreateReplyRequests()
        api_client = FeishuApiClient(config_getter=lambda: {"app_id": "cli_x", "app_secret": "sec_y"}, requests_module=requests_module)
        service = FeishuReplyService(
            api_client=api_client,
            config_getter=lambda: {"workspace_root": "."},
            markdown_to_interactive_card=lambda text, include_actions: {"schema": "2.0", "body": {"elements": [{"tag": "markdown", "content": text}]}},
            markdown_to_feishu_post=lambda text: {"zh_cn": {"title": "回复", "content": [[{"tag": "md", "text": text}]]}},
        )

        reply_message_id = service.create_interactive_reply("mid_123", "stream placeholder")

        self.assertEqual(reply_message_id, "om_reply_1")

    def test_update_interactive_message_uses_patch_endpoint(self) -> None:
        requests_module = _FakeRequests()
        api_client = FeishuApiClient(config_getter=lambda: {"app_id": "cli_x", "app_secret": "sec_y"}, requests_module=requests_module)
        service = FeishuReplyService(
            api_client=api_client,
            config_getter=lambda: {"workspace_root": "."},
            markdown_to_interactive_card=lambda text, include_actions: {"schema": "2.0", "body": {"elements": [{"tag": "markdown", "content": text}]}},
            markdown_to_feishu_post=lambda text: {"zh_cn": {"title": "回复", "content": [[{"tag": "md", "text": text}]]}},
        )

        ok = service.update_interactive_message("om_reply_1", "stream update")

        self.assertTrue(ok)
        self.assertEqual(requests_module.patch_calls[-1]["json"]["msg_type"], "interactive")

    def test_create_interactive_reply_retries_without_actions_on_unsupported_action_tag(self) -> None:
        class _RetryRequests(_FakeRequests):
            def __init__(self) -> None:
                super().__init__()
                self._reply_attempts = 0

            def post(self, url, json=None, data=None, files=None, headers=None, timeout=None):
                self.calls.append({"url": url, "json": json, "data": data, "files": files, "headers": headers, "timeout": timeout})
                if "tenant_access_token/internal" in url:
                    return _FakeResponse({"code": 0, "tenant_access_token": "tok_123", "expire": 7200})
                self._reply_attempts += 1
                if self._reply_attempts == 1:
                    return _FakeResponse({"code": 230099, "msg": "unsupported tag action"})
                return _FakeResponse({"code": 0, "data": {"message_id": "om_reply_retry"}})

        requests_module = _RetryRequests()
        api_client = FeishuApiClient(config_getter=lambda: {"app_id": "cli_x", "app_secret": "sec_y"}, requests_module=requests_module)
        service = FeishuReplyService(
            api_client=api_client,
            config_getter=lambda: {"workspace_root": "."},
            markdown_to_interactive_card=lambda text, include_actions, **kwargs: {
                "schema": "2.0",
                "body": {"elements": [{"tag": "markdown", "content": text}, {"tag": "button", "content": "action"}] if include_actions else [{"tag": "markdown", "content": text}]},
            },
            markdown_to_feishu_post=lambda text: {"zh_cn": {"title": "回复", "content": [[{"tag": "md", "text": text}]]}},
        )

        reply_message_id = service.create_interactive_reply("mid_123", "stream placeholder", include_card_actions=True)

        self.assertEqual(reply_message_id, "om_reply_retry")
        self.assertEqual(len([call for call in requests_module.calls if isinstance(call.get("json"), dict) and call["json"].get("msg_type") == "interactive"]), 2)


if __name__ == "__main__":
    unittest.main()
