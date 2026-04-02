import sys
import unittest
from pathlib import Path
from unittest import mock


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.chat.providers.butler_prompt_provider import ButlerChatPromptProvider


class ChatPromptProviderTests(unittest.TestCase):
    def test_render_skills_prompt_uses_chat_default_limit_100(self) -> None:
        provider = ButlerChatPromptProvider()

        with mock.patch(
            "butler_main.chat.providers.butler_prompt_provider._SUPPORT_PROVIDER.render_skills_prompt",
            return_value="skills",
        ) as render_skills_prompt:
            result = provider.render_skills_prompt("c:/workspace")

        self.assertEqual(result, "skills")
        render_skills_prompt.assert_called_once_with(
            "c:/workspace",
            collection_id="chat_default",
            max_skills=100,
            max_chars=2000,
        )


if __name__ == "__main__":
    unittest.main()
