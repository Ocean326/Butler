import sys
import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
from butler_main.chat.feishu_bot import transport


class ChatFeishuConfigPathTests(unittest.TestCase):
    def _make_workspace(self) -> Path:
        root = REPO_ROOT / "工作区" / "temp" / "pytest_runtime" / "chat_config" / f"chat_config_{uuid.uuid4().hex[:8]}"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_resolve_default_config_path_prefers_chat_configs(self) -> None:
        root = self._make_workspace()
        try:
            transport_dir = root / "chat" / "feishu_bot"
            chat_configs = root / "chat" / "configs"
            legacy_configs = root / "butler_bot_code" / "configs"
            transport_dir.mkdir(parents=True)
            chat_configs.mkdir(parents=True)
            legacy_configs.mkdir(parents=True)
            (chat_configs / "butler_bot.json").write_text("{}", encoding="utf-8")
            (legacy_configs / "butler_bot.json").write_text("{\"legacy\":true}", encoding="utf-8")

            fake_transport = transport_dir / "transport.py"
            with mock.patch.object(transport, "__file__", str(fake_transport)):
                resolved = transport._resolve_default_config_path("butler_bot")
        finally:
            shutil.rmtree(root, ignore_errors=True)

        self.assertEqual(resolved, str((chat_configs / "butler_bot.json").resolve()))

    def test_resolve_default_config_path_falls_back_to_legacy_configs(self) -> None:
        root = self._make_workspace()
        try:
            transport_dir = root / "chat" / "feishu_bot"
            legacy_configs = root / "butler_bot_code" / "configs"
            transport_dir.mkdir(parents=True)
            legacy_configs.mkdir(parents=True)
            (legacy_configs / "butler_bot.json").write_text("{\"legacy\":true}", encoding="utf-8")

            fake_transport = transport_dir / "transport.py"
            with mock.patch.object(transport, "__file__", str(fake_transport)):
                resolved = transport._resolve_default_config_path("butler_bot")
        finally:
            shutil.rmtree(root, ignore_errors=True)

        self.assertEqual(resolved, str((legacy_configs / "butler_bot.json").resolve()))


if __name__ == "__main__":
    unittest.main()
