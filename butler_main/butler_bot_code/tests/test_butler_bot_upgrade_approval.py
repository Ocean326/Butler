import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "butler_bot" / "butler_bot.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("butler_bot_upgrade_module", MODULE_PATH)
BUTLER_BOT = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(BUTLER_BOT)


class ButlerBotUpgradeApprovalTests(unittest.TestCase):
    def setUp(self):
        BUTLER_BOT.CONFIG.clear()
        BUTLER_BOT.CONFIG.update({"workspace_root": ".", "agent_timeout": 60, "agent_model": "auto"})

    def test_run_agent_approval_restart_sets_post_reply_action(self):
        request = {"request_id": "req-1", "action": "restart", "reason": "需要重启"}
        expected_workspace = str(Path(__file__).resolve().parents[3])
        with mock.patch.object(BUTLER_BOT.MEMORY, "inspect_pending_upgrade_request_prompt", return_value={"decision": "approve-restart", "request": request, "reply": "已收到批准。"}), \
             mock.patch.object(BUTLER_BOT.MEMORY, "on_reply_sent_async") as on_reply_sent, \
             mock.patch.object(BUTLER_BOT.MEMORY, "execute_approved_upgrade_request") as execute_request:
            reply = BUTLER_BOT.run_agent("可以重启")
            BUTLER_BOT._after_reply_persist_memory_async("可以重启", reply)

        self.assertEqual(reply, "已收到批准。")
        on_reply_sent.assert_called_once()
        execute_request.assert_called_once_with(expected_workspace, request)


if __name__ == "__main__":
    unittest.main()
