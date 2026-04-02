import sys
import unittest
from pathlib import Path
from unittest import mock


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from butler_main.chat.app import ChatApp, create_default_chat_app, create_default_cli_chat_app, create_default_weixi_chat_app
from butler_main.chat.providers import ButlerChatMemoryProvider, ButlerChatPromptProvider
from butler_main.chat import engine as chat_engine


class _DummyPromptProvider:
    def render_skills_prompt(self, workspace: str) -> str:
        return "skills"

    def render_agent_capabilities_prompt(self, workspace: str) -> str:
        return "capabilities"

    def build_prompt(self, user_prompt: str, **kwargs) -> str:
        return user_prompt


class _DummyMemoryProvider:
    def start_background_services(self) -> None:
        return None

    def get_runtime_request_override(self) -> dict:
        return {}

    def begin_turn(self, user_prompt: str, workspace: str):
        return "mem_1", None

    def prepare_turn_input(self, user_prompt: str, **kwargs) -> str:
        return user_prompt

    def persist_reply_async(self, user_prompt: str, assistant_reply: str, **kwargs) -> None:
        return None


class ChatAppBootstrapTests(unittest.TestCase):
    def test_chat_app_run_delegates_to_feishu_runner(self) -> None:
        app = ChatApp(
            run_agent_fn=lambda prompt, **kwargs: prompt,
            prompt_provider=_DummyPromptProvider(),
            memory_provider=_DummyMemoryProvider(),
        )

        with mock.patch("butler_main.chat.app.run_chat_feishu_bot", return_value=7) as runner:
            rc = app.run()

        self.assertEqual(rc, 7)
        runner.assert_called_once()
        kwargs = runner.call_args.kwargs
        self.assertEqual(kwargs["default_config_name"], "butler_bot")
        self.assertEqual(kwargs["bot_name"], "管家bot")
        self.assertIs(kwargs["run_agent_fn"], app.run_agent_fn)
        self.assertIs(kwargs["on_bot_started"].__self__, app)
        self.assertIs(kwargs["on_bot_started"].__func__, ChatApp.on_bot_started)
        self.assertIs(kwargs["on_reply_sent"].__self__, app)
        self.assertIs(kwargs["on_reply_sent"].__func__, ChatApp.on_reply_sent)

    def test_chat_app_run_delegates_to_weixi_runner_when_channel_switched(self) -> None:
        app = ChatApp(
            run_agent_fn=lambda prompt, **kwargs: prompt,
            prompt_provider=_DummyPromptProvider(),
            memory_provider=_DummyMemoryProvider(),
            channel="weixi",
        )

        with mock.patch("butler_main.chat.app.run_chat_weixin_bot", return_value=9) as runner:
            rc = app.run()

        self.assertEqual(rc, 9)
        runner.assert_called_once()
        kwargs = runner.call_args.kwargs
        self.assertEqual(kwargs["default_config_name"], "butler_bot")
        self.assertEqual(kwargs["bot_name"], "管家bot")
        self.assertIs(kwargs["run_agent_fn"], app.run_agent_fn)

    def test_chat_app_run_delegates_to_cli_runner_when_channel_switched(self) -> None:
        app = ChatApp(
            run_agent_fn=lambda prompt, **kwargs: prompt,
            prompt_provider=_DummyPromptProvider(),
            memory_provider=_DummyMemoryProvider(),
            channel="cli",
        )

        with mock.patch("butler_main.chat.app.run_chat_cli", return_value=11) as runner:
            rc = app.run()

        self.assertEqual(rc, 11)
        runner.assert_called_once()
        kwargs = runner.call_args.kwargs
        self.assertEqual(kwargs["default_config_name"], "butler_bot")
        self.assertEqual(kwargs["bot_name"], "管家bot")
        self.assertIs(kwargs["run_agent_fn"], app.run_agent_fn)

    def test_create_default_chat_app_uses_butler_backed_providers(self) -> None:
        bootstrap = create_default_chat_app()

        self.assertIsInstance(bootstrap.app.prompt_provider, ButlerChatPromptProvider)
        self.assertIsInstance(bootstrap.app.memory_provider, ButlerChatMemoryProvider)
        self.assertIs(bootstrap.app.run_agent_fn, chat_engine.run_agent)
        self.assertIs(bootstrap.app.prompt_provider, chat_engine.PROMPT_PROVIDER)
        self.assertIs(bootstrap.app.memory_provider, chat_engine.MEMORY_PROVIDER)
        self.assertEqual(bootstrap.body_module_name, chat_engine.__name__)
        self.assertEqual(bootstrap.prompt_provider_name, "ButlerChatPromptProvider")
        self.assertEqual(bootstrap.memory_provider_name, "ButlerChatMemoryProvider")
        self.assertEqual(bootstrap.app.immediate_receipt_text, "处理中，{cli} {model} 模型调用中…")

    def test_create_default_weixi_chat_app_switches_channel_only(self) -> None:
        bootstrap = create_default_weixi_chat_app()

        self.assertEqual(bootstrap.app.channel, "weixi")
        self.assertIsInstance(bootstrap.app.prompt_provider, ButlerChatPromptProvider)
        self.assertIsInstance(bootstrap.app.memory_provider, ButlerChatMemoryProvider)
        self.assertIs(bootstrap.app.run_agent_fn, chat_engine.run_agent)

    def test_create_default_cli_chat_app_switches_channel_only(self) -> None:
        bootstrap = create_default_cli_chat_app()

        self.assertEqual(bootstrap.app.channel, "cli")
        self.assertIsInstance(bootstrap.app.prompt_provider, ButlerChatPromptProvider)
        self.assertIsInstance(bootstrap.app.memory_provider, ButlerChatMemoryProvider)
        self.assertIs(bootstrap.app.run_agent_fn, chat_engine.run_agent)

if __name__ == "__main__":
    unittest.main()
