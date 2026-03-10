import importlib.util
import io
from unittest import mock
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "butler_bot" / "butler_bot.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("butler_bot_module", MODULE_PATH)
BUTLER_BOT = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(BUTLER_BOT)


class ButlerBotModelControlTests(unittest.TestCase):
    def test_decode_cli_payload_falls_back_to_gbk(self):
        payload = "启动失败，请查看日志".encode("gbk")
        text = BUTLER_BOT._decode_cli_payload(payload)
        self.assertIn("启动失败", text)

    def test_parse_runtime_control_list_models(self):
        control = BUTLER_BOT._parse_runtime_control("请给我模型列表", {"agent_model": "auto"})
        self.assertEqual(control["kind"], "list-models")

    def test_parse_runtime_control_current_model(self):
        control = BUTLER_BOT._parse_runtime_control("当前模型", {"agent_model": "auto"})
        self.assertEqual(control["kind"], "current-model")

    def test_parse_runtime_control_model_directive(self):
        control = BUTLER_BOT._parse_runtime_control("用 gpt-5 回答：你好", {"agent_model": "auto"})
        self.assertEqual(control["kind"], "run")
        self.assertEqual(control["model"], "gpt-5")
        self.assertEqual(control["prompt"], "你好")

    def test_parse_runtime_control_model_alias(self):
        control = BUTLER_BOT._parse_runtime_control(
            "[模型=fast] 帮我总结今天的进展",
            {"agent_model": "auto", "model_aliases": {"fast": "gpt-5"}},
        )
        self.assertEqual(control["model"], "gpt-5")
        self.assertEqual(control["prompt"], "帮我总结今天的进展")

    def test_format_current_model_reply_includes_aliases(self):
        reply = BUTLER_BOT._format_current_model_reply({"agent_model": "auto", "model_aliases": {"fast": "gpt-5"}})
        self.assertIn("当前默认模型：auto", reply)
        self.assertIn("fast -> gpt-5", reply)

    def test_list_available_models_parses_dash_format(self):
        fake_completed = type("Result", (), {"stdout": "Available models\n\nauto - Auto  (current, default)\ngpt-5 - GPT-5\nsonnet-4 - Sonnet 4\n", "stderr": "", "returncode": 0})
        with mock.patch.object(BUTLER_BOT.os.path, "isfile", return_value=True), mock.patch.object(BUTLER_BOT.subprocess, "run", return_value=fake_completed):
            models, error = BUTLER_BOT._list_available_models("c:/workspace", 30)
        self.assertIsNone(error)
        self.assertEqual(models, ["auto", "gpt-5", "sonnet-4"])

    def test_run_agent_via_cli_tolerates_non_utf8_stdout_json(self):
        payload = io.BytesIO()
        payload.write('{"result":"'.encode("ascii"))
        payload.write("启动失败，请查看日志".encode("gbk"))
        payload.write('"}'.encode("ascii"))
        fake_completed = type("Result", (), {"stdout": payload.getvalue(), "stderr": b"", "returncode": 0})

        with mock.patch.object(BUTLER_BOT.os.path, "isfile", return_value=True), mock.patch.object(BUTLER_BOT.subprocess, "run", return_value=fake_completed):
            out, ok = BUTLER_BOT._run_agent_via_cli("test", "c:/workspace", 30, "auto")

        self.assertTrue(ok)
        self.assertEqual(out, "启动失败，请查看日志")

    def test_run_agent_streaming_tolerates_non_utf8_stream_json(self):
        assistant_line = (
            '{"type":"assistant","message":{"content":[{"type":"text","text":"'.encode("ascii")
            + "你好，继续处理".encode("gbk")
            + '"}]}}\n'.encode("ascii")
        )
        result_line = (
            '{"type":"result","subtype":"success","result":"'.encode("ascii")
            + "你好，继续处理".encode("gbk")
            + '"}\n'.encode("ascii")
        )

        class _FakeProc:
            def __init__(self):
                self.stdin = io.BytesIO()
                self.stdout = [assistant_line, result_line]
                self.stderr = io.BytesIO(b"")
                self.returncode = 0

            def wait(self, timeout=None):
                return 0

            def kill(self):
                self.returncode = -9

        with mock.patch.object(BUTLER_BOT.os.path, "isfile", return_value=True), mock.patch.object(BUTLER_BOT.subprocess, "Popen", return_value=_FakeProc()):
            out, ok = BUTLER_BOT._run_agent_streaming("test", "c:/workspace", 30, "auto")

        self.assertTrue(ok)
        self.assertEqual(out, "你好，继续处理")


if __name__ == "__main__":
    unittest.main()
