from __future__ import annotations

import unittest

from butler_main.chat.weixi.status import (
    get_weixin_runtime_status_snapshot,
    reset_weixin_runtime_status,
    set_weixin_runtime_status,
)


class ChatWeixinStatusTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_weixin_runtime_status()

    def test_status_snapshot_aggregates_multiple_bindings(self) -> None:
        set_weixin_runtime_status(
            {
                "connected": True,
                "login_state": "ready",
                "account_id": "wx-a",
                "active_conversation_count": 2,
                "running_conversation_count": 1,
                "recent_conversations": [{"conversation_key": "weixin:wx-a:dm:user-a"}],
            },
            binding_id="alpha",
        )
        set_weixin_runtime_status(
            {
                "connected": False,
                "login_state": "error",
                "account_id": "wx-b",
                "active_conversation_count": 1,
                "running_conversation_count": 0,
                "recent_conversations": [{"conversation_key": "weixin:wx-b:dm:user-b"}],
                "last_error": "token expired",
            },
            binding_id="beta",
        )

        aggregate = get_weixin_runtime_status_snapshot()

        self.assertTrue(aggregate["connected"])
        self.assertEqual(aggregate["binding_count"], 2)
        self.assertEqual(aggregate["active_binding_count"], 1)
        self.assertEqual(aggregate["active_conversation_count"], 3)
        self.assertEqual(aggregate["running_conversation_count"], 1)
        self.assertEqual({item["binding_id"] for item in aggregate["bindings"]}, {"alpha", "beta"})
        self.assertEqual({item["binding_id"] for item in aggregate["recent_conversations"]}, {"alpha", "beta"})

    def test_status_snapshot_can_read_single_binding(self) -> None:
        set_weixin_runtime_status(
            {
                "connected": True,
                "login_state": "ready",
                "account_id": "wx-a",
                "active_conversation_count": 2,
            },
            binding_id="alpha",
        )

        snapshot = get_weixin_runtime_status_snapshot(binding_id="alpha")

        self.assertEqual(snapshot["binding_id"], "alpha")
        self.assertEqual(snapshot["account_id"], "wx-a")
        self.assertTrue(snapshot["connected"])


if __name__ == "__main__":
    unittest.main()
