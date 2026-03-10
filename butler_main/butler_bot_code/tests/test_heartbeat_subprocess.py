from pathlib import Path
import sys
import unittest
from unittest import mock


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

import memory_manager  # noqa: E402


class HeartbeatSubprocessTests(unittest.TestCase):
    def test_decode_subprocess_stream_falls_back_to_gbk(self):
        payload = "启动失败，请查看日志".encode("gbk")
        text = memory_manager._decode_subprocess_stream(payload)
        self.assertIn("启动失败", text)

    def test_build_cursor_cli_env_rotates_configured_key_pool(self):
        cfg = {"cursor_api_keys": ["key-a", "key-b"]}
        with mock.patch("memory_manager.random.choice", return_value="key-b"):
            env = memory_manager.build_cursor_cli_env(cfg, {"EXISTING": "1", "CURSOR_API_KEY": "legacy"})

        self.assertEqual(env["EXISTING"], "1")
        self.assertEqual(env["CURSOR_API_KEY"], "key-b")

    def test_run_model_subprocess_tolerates_non_utf8_stderr(self):
        """CLI 可能输出 GBK；run 使用 encoding=utf-8, errors=replace 后 stderr 已是 str，此处仅验证失败时返回 stderr 内容。"""
        with mock.patch("memory_manager.os.path.isfile", return_value=True), mock.patch(
            "memory_manager.subprocess.run",
            return_value=mock.MagicMock(returncode=1, stdout="", stderr="启动失败，请查看日志"),
        ):
            out, ok = memory_manager._run_model_subprocess("test", ".", 5, "auto")

        self.assertFalse(ok)
        self.assertIn("启动失败", out)

    def test_run_model_subprocess_uses_rotated_cursor_api_key(self):
        captured = {}

        def _fake_run(*args, **kwargs):
            captured["env"] = kwargs.get("env") or {}
            return mock.MagicMock(returncode=0, stdout='{"result":"ok"}', stderr="")

        with mock.patch("memory_manager.os.path.isfile", return_value=True), \
             mock.patch("memory_manager.random.choice", return_value="key-b"), \
             mock.patch("memory_manager.subprocess.run", side_effect=_fake_run):
            out, ok = memory_manager._run_model_subprocess("test", ".", 5, "auto", {"cursor_api_keys": ["key-a", "key-b"]})

        self.assertTrue(ok)
        self.assertEqual(out, "ok")
        self.assertEqual(captured["env"]["CURSOR_API_KEY"], "key-b")


if __name__ == "__main__":
    unittest.main()