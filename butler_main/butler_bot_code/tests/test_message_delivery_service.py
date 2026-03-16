import json
import sys
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

from services.message_delivery_service import MessageDeliveryService  # noqa: E402


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.trust_env = True

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _FakeResponse(self._responses.pop(0))


class _FakeRequestsModule:
    def __init__(self, session):
        self._session = session

    def Session(self):
        return self._session


class MessageDeliveryServiceTests(unittest.TestCase):
    def test_interactive_card_uses_schema_2_body_markdown(self):
        card = MessageDeliveryService.markdown_to_interactive_card("hello")

        self.assertEqual(card["schema"], "2.0")
        self.assertEqual(card["body"]["elements"][0]["tag"], "markdown")
        self.assertEqual(card["body"]["elements"][0]["content"], "hello")
        self.assertNotIn("elements", card)

    def test_send_private_message_prefers_interactive_then_falls_back_to_post(self):
        session = _FakeSession(
            [
                {"code": 0, "tenant_access_token": "token-123"},
                {"code": 230099, "msg": "interactive failed"},
                {"code": 0, "data": {"message_id": "msg-1"}},
            ]
        )
        service = MessageDeliveryService(object(), requests_module=_FakeRequestsModule(session))

        ok = service.send_private_message(
            {"app_id": "app", "app_secret": "secret"},
            "test body",
            receive_id="ou_test",
            receive_id_type="open_id",
        )

        self.assertTrue(ok)
        self.assertEqual(len(session.calls), 3)
        interactive_call = session.calls[1]["json"]
        self.assertEqual(interactive_call["msg_type"], "interactive")
        interactive_content = json.loads(interactive_call["content"])
        self.assertEqual(interactive_content["schema"], "2.0")
        self.assertEqual(interactive_content["body"]["elements"][0]["tag"], "markdown")
        post_call = session.calls[2]["json"]
        self.assertEqual(post_call["msg_type"], "post")


if __name__ == "__main__":
    unittest.main()
