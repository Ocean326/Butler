import importlib.util
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

    def test_parse_runtime_control_cli_runtime_json(self):
        control = BUTLER_BOT._parse_runtime_control(
            "【cli_runtime_json】\n"
            '{"cli":"codex","model":"gpt-5","speed":"medium"}\n'
            "【/cli_runtime_json】\n"
            "帮我写一份 Butler CLI 切换方案",
            {"agent_model": "auto"},
        )
        self.assertEqual(control["kind"], "run")
        self.assertEqual(control["cli"], "codex")
        self.assertEqual(control["model"], "gpt-5")
        self.assertEqual(control["runtime"]["speed"], "medium")
        self.assertEqual(control["prompt"], "帮我写一份 Butler CLI 切换方案")

    def test_extract_self_mind_chat_request(self):
        prompt, is_self_mind = BUTLER_BOT._extract_self_mind_chat_request("self-mind: 你刚才为什么没回我")
        self.assertTrue(is_self_mind)
        self.assertEqual(prompt, "你刚才为什么没回我")

    def test_format_current_model_reply_includes_aliases(self):
        reply = BUTLER_BOT._format_current_model_reply({"agent_model": "auto", "model_aliases": {"fast": "gpt-5"}})
        self.assertIn("当前默认模型：auto", reply)
        self.assertIn("fast -> gpt-5", reply)

    def test_cursor_runtime_forces_auto_model(self):
        cfg = {
            "agent_model": "gpt-5.2",
            "cli_runtime": {
                "active": "cursor",
                "defaults": {"model": "gpt-5.2"},
                "providers": {
                    "cursor": {"enabled": True},
                    "codex": {"enabled": False},
                },
            },
        }
        resolved = BUTLER_BOT.cli_runtime_service.resolve_runtime_request(cfg, {"cli": "cursor"}, model_override="gpt-5.2")
        self.assertEqual(resolved["cli"], "cursor")
        self.assertEqual(resolved["model"], "auto")

    def test_format_current_model_reply_normalizes_cursor_default(self):
        reply = BUTLER_BOT._format_current_model_reply(
            {
                "agent_model": "gpt-5.2",
                "cli_runtime": {
                    "active": "cursor",
                    "defaults": {"model": "gpt-5.2"},
                    "providers": {
                        "cursor": {"enabled": True},
                        "codex": {"enabled": False},
                    },
                },
            }
        )
        self.assertIn("当前默认模型：auto", reply)

    def test_list_available_models_parses_dash_format(self):
        fake_completed = type("Result", (), {"stdout": "Available models\n\nauto - Auto  (current, default)\ngpt-5 - GPT-5\nsonnet-4 - Sonnet 4\n", "stderr": "", "returncode": 0})
        with mock.patch.object(BUTLER_BOT.cli_runtime_service, "resolve_cursor_cli_cmd_path", return_value="C:/cursor-agent.cmd"), mock.patch.object(BUTLER_BOT.cli_runtime_service.os.path, "isfile", return_value=True), mock.patch.object(BUTLER_BOT.cli_runtime_service.subprocess, "run", return_value=fake_completed):
            models, error = BUTLER_BOT._list_available_models("c:/workspace", 30)
        self.assertIsNone(error)
        self.assertEqual(models, ["auto", "gpt-5", "sonnet-4"])

    def test_run_agent_via_cli_tolerates_non_utf8_stdout_json(self):
        with mock.patch.object(BUTLER_BOT.cli_runtime_service, "run_prompt", return_value=("启动失败，请查看日志", True)):
            out, ok = BUTLER_BOT._run_agent_via_cli("test", "c:/workspace", 30, "auto")

        self.assertTrue(ok)
        self.assertEqual(out, "启动失败，请查看日志")

    def test_run_agent_streaming_tolerates_non_utf8_stream_json(self):
        with mock.patch.object(BUTLER_BOT.cli_runtime_service, "run_prompt", return_value=("你好，继续处理", True)):
            out, ok = BUTLER_BOT._run_agent_streaming("test", "c:/workspace", 30, "auto")

        self.assertTrue(ok)
        self.assertEqual(out, "你好，继续处理")

    def test_run_codex_uses_provider_https_proxy(self):
        provider = {
            "path": "codex",
            "https_proxy": "http://127.0.0.1:10808",
        }
        completed = type("Result", (), {"stdout": '{"output_text":"ok"}\n', "stderr": "", "returncode": 0})
        with mock.patch.object(BUTLER_BOT.cli_runtime_service, "_provider_config", return_value=provider), mock.patch.object(BUTLER_BOT.cli_runtime_service, "_resolve_command_path", return_value="C:/codex.cmd"), mock.patch.object(BUTLER_BOT.cli_runtime_service.subprocess, "run", return_value=completed) as mocked_run:
            out, ok = BUTLER_BOT.cli_runtime_service._run_codex("hello", "c:/workspace", 30, {}, {"model": "gpt-5"}, on_segment=None)
        self.assertTrue(ok)
        self.assertEqual(out, "ok")
        self.assertEqual(mocked_run.call_args.kwargs["env"]["HTTPS_PROXY"], "http://127.0.0.1:10808")

    def test_run_codex_sends_prompt_via_stdin(self):
        provider = {
            "path": "codex",
        }
        completed = type("Result", (), {"stdout": '{"output_text":"ok"}\n', "stderr": "", "returncode": 0})
        with mock.patch.object(BUTLER_BOT.cli_runtime_service, "_provider_config", return_value=provider), mock.patch.object(BUTLER_BOT.cli_runtime_service, "_resolve_command_path", return_value="C:/codex.cmd"), mock.patch.object(BUTLER_BOT.cli_runtime_service.subprocess, "run", return_value=completed) as mocked_run:
            out, ok = BUTLER_BOT.cli_runtime_service._run_codex("very long prompt", "c:/workspace", 30, {}, {"model": "gpt-5.2"}, on_segment=None)
        self.assertTrue(ok)
        self.assertEqual(out, "ok")
        self.assertEqual(mocked_run.call_args.args[0][-1], "-")
        self.assertEqual(mocked_run.call_args.kwargs["input"], "very long prompt")

    def test_run_prompt_falls_back_to_codex_when_cursor_unavailable(self):
        cfg = {
            "cli_runtime": {
                "active": "cursor",
                "providers": {
                    "cursor": {"enabled": True},
                    "codex": {"enabled": True, "path": "codex"},
                },
            }
        }
        with mock.patch.object(BUTLER_BOT.cli_runtime_service, "_run_cursor", return_value=("S: [unavailable]", False)) as mocked_cursor, mock.patch.object(BUTLER_BOT.cli_runtime_service, "_run_codex", return_value=("codex ok", True)) as mocked_codex, mock.patch.object(BUTLER_BOT.cli_runtime_service, "cli_provider_available", return_value=True):
            out, ok = BUTLER_BOT.cli_runtime_service.run_prompt("hello", "c:/workspace", 30, cfg, {"cli": "cursor"})

        self.assertTrue(ok)
        self.assertEqual(out, "codex ok")
        self.assertEqual(mocked_cursor.call_count, 1)
        self.assertEqual(mocked_codex.call_count, 1)
        self.assertEqual(mocked_codex.call_args.args[4]["fallback_from"], "cursor")

    def test_run_prompt_keeps_original_error_when_fallback_fails(self):
        cfg = {
            "cli_runtime": {
                "active": "cursor",
                "providers": {
                    "cursor": {"enabled": True},
                    "codex": {"enabled": True, "path": "codex"},
                },
            }
        }
        with mock.patch.object(BUTLER_BOT.cli_runtime_service, "_run_cursor", return_value=("S: [unavailable]", False)), mock.patch.object(BUTLER_BOT.cli_runtime_service, "_run_codex", return_value=("codex failed", False)), mock.patch.object(BUTLER_BOT.cli_runtime_service, "cli_provider_available", return_value=True):
            out, ok = BUTLER_BOT.cli_runtime_service.run_prompt("hello", "c:/workspace", 30, cfg, {"cli": "cursor"})

        self.assertFalse(ok)
        self.assertEqual(out, "S: [unavailable]")


if __name__ == "__main__":
    unittest.main()
