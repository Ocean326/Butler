import tempfile
from pathlib import Path
import sys
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from memory_manager import MemoryManager  # noqa: E402


class SelfMindServicesTests(unittest.TestCase):
    def test_self_mind_state_service_resolves_paths_and_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {
                    "workspace_root": str(workspace),
                    "tell_user_receive_id": "talk-default",
                    "tell_user_receive_id_type": "open_id",
                    "memory": {"self_mind": {"talk_receive_id": "talk-self", "talk_receive_id_type": "chat_id"}},
                },
                run_model_fn=lambda *_: ("", False),
            )

            service = manager._self_mind_state_service
            self.assertTrue(str(service.context_path(str(workspace))).endswith("self_mind\\current_context.md"))
            self.assertEqual(service.talk_target({}), ("talk-self", "chat_id"))
            self.assertFalse(service.listener_enabled())

    def test_self_mind_prompt_service_builds_handoff_receipt(self) -> None:
        manager = MemoryManager(config_provider=lambda: {"workspace_root": "."}, run_model_fn=lambda *_: ("", False))
        text = manager._self_mind_prompt_service.build_cycle_receipt_text(
            {
                "action_channel": "agent",
                "agent_task": "整理规划与证据链",
                "why": "这件事适合留给 self_mind agent_space 推进",
                "done_when": "形成一条真实任务并落账",
            }
        )

        self.assertIn("self_mind agent handoff", text)
        self.assertIn("整理规划与证据链", text)
        self.assertIn("形成一条真实任务并落账", text)

    def test_self_mind_chat_prompt_uses_companion_memory_not_talk_recent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(config_provider=lambda: {"workspace_root": str(workspace)}, run_model_fn=lambda *_: ("", False))
            prompt = manager._self_mind_prompt_service.build_chat_prompt(str(workspace), "今天有点累，陪我聊聊")

            self.assertIn("用户偏好与陪伴记忆", prompt)
            self.assertIn("self_mind 自己最近聊天", prompt)
            self.assertNotIn("最近主对话", prompt)

    def test_self_mind_state_service_resolves_listener_credentials(self) -> None:
        manager = MemoryManager(
            config_provider=lambda: {
                "workspace_root": ".",
                "memory": {
                    "self_mind": {
                        "listener_enabled": True,
                        "listener_app_id": "cli_listener",
                        "listener_app_secret": "secret_listener",
                    }
                },
            },
            run_model_fn=lambda *_: ("", False),
        )

        service = manager._self_mind_state_service
        self.assertTrue(service.listener_enabled())
        self.assertEqual(service.listener_delivery_override(), {"app_id": "cli_listener", "app_secret": "secret_listener"})


if __name__ == "__main__":
    unittest.main()
