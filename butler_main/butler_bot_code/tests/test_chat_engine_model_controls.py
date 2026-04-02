import os
from pathlib import Path
import tempfile
from unittest import mock
import unittest

from agents_os.contracts import Invocation, OutputBundle
from butler_main.chat import ChatRouter
from butler_main.chat import engine as chat_engine


class ChatEngineModelControlTests(unittest.TestCase):
    def test_decode_cli_payload_falls_back_to_gbk(self):
        payload = "启动失败，请查看日志".encode("gbk")
        text = chat_engine._decode_cli_payload(payload)
        self.assertIn("启动失败", text)

    def test_parse_runtime_control_list_models(self):
        control = chat_engine._parse_runtime_control("请给我模型列表", {"agent_model": "auto"})
        self.assertEqual(control["kind"], "list-models")

    def test_parse_runtime_control_current_model(self):
        control = chat_engine._parse_runtime_control("当前模型", {"agent_model": "auto"})
        self.assertEqual(control["kind"], "current-model")

    def test_parse_runtime_control_model_directive(self):
        control = chat_engine._parse_runtime_control("用 gpt-5 回答：你好", {"agent_model": "auto"})
        self.assertEqual(control["kind"], "run")
        self.assertEqual(control["model"], "gpt-5")
        self.assertEqual(control["prompt"], "你好")

    def test_parse_runtime_control_model_alias(self):
        control = chat_engine._parse_runtime_control(
            "[模型=fast] 帮我总结今天的进展",
            {"agent_model": "auto", "model_aliases": {"fast": "gpt-5"}},
        )
        self.assertEqual(control["model"], "gpt-5")
        self.assertEqual(control["prompt"], "帮我总结今天的进展")

    def test_parse_runtime_control_cli_runtime_json(self):
        control = chat_engine._parse_runtime_control(
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

    def test_parse_runtime_control_profile_directive(self):
        control = chat_engine._parse_runtime_control(
            "用 aixj 回答：整理一份切换方案",
            {"agent_model": "auto"},
        )
        self.assertEqual(control["kind"], "run")
        self.assertEqual(control["cli"], "codex")
        self.assertEqual(control["runtime"]["profile"], "aixj")
        self.assertEqual(control["prompt"], "整理一份切换方案")

    def test_parse_runtime_control_profile_bracket_directive(self):
        control = chat_engine._parse_runtime_control(
            "[profile=openai] 帮我复核当前 provider",
            {"agent_model": "auto"},
        )
        self.assertEqual(control["kind"], "run")
        self.assertEqual(control["cli"], "codex")
        self.assertEqual(control["runtime"]["profile"], "openai")
        self.assertEqual(control["prompt"], "帮我复核当前 provider")

    def test_parse_runtime_control_claude_directive(self):
        control = chat_engine._parse_runtime_control(
            "用 claude-cli 回答：整理抽核清单",
            {
                "agent_model": "auto",
                "cli_runtime": {
                    "active": "claude",
                    "providers": {
                        "cursor": {"enabled": False},
                        "codex": {"enabled": False},
                        "claude": {"enabled": True},
                    },
                },
            },
        )
        self.assertEqual(control["kind"], "run")
        self.assertEqual(control["cli"], "claude")
        self.assertEqual(control["prompt"], "整理抽核清单")

    def test_describe_runtime_target_resolves_effective_cli_and_model(self):
        cfg = {
            "agent_model": "auto",
            "model_aliases": {"fast": "gpt-5.4"},
            "cli_runtime": {
                "active": "cursor",
                "providers": {
                    "cursor": {"enabled": True},
                    "codex": {"enabled": True},
                    "claude": {"enabled": False},
                },
            },
        }
        with mock.patch.object(chat_engine, "get_config", return_value=cfg):
            descriptor = chat_engine.describe_runtime_target("用 codex 回答：用 fast 模型总结")
        self.assertEqual(descriptor["cli"], "codex")
        self.assertEqual(descriptor["model"], "gpt-5.4")
        self.assertEqual(descriptor["kind"], "run")

    def test_format_current_model_reply_includes_aliases(self):
        reply = chat_engine._format_current_model_reply({"agent_model": "auto", "model_aliases": {"fast": "gpt-5"}})
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
        resolved = chat_engine.cli_runtime_service.resolve_runtime_request(cfg, {"cli": "cursor"}, model_override="gpt-5.2")
        self.assertEqual(resolved["cli"], "cursor")
        self.assertEqual(resolved["model"], "auto")

    def test_format_current_model_reply_normalizes_cursor_default(self):
        reply = chat_engine._format_current_model_reply(
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

    def test_format_current_model_reply_includes_profile(self):
        reply = chat_engine._format_current_model_reply(
            {
                "agent_model": "gpt-5.4",
                "cli_runtime": {
                    "active": "codex",
                    "defaults": {"model": "gpt-5.4", "profile": "openai"},
                    "profile_aliases": {"openai": "openai", "aixj": "aixj"},
                    "providers": {
                        "cursor": {"enabled": False},
                        "codex": {"enabled": True},
                    },
                },
            }
        )
        self.assertNotIn("当前默认 profile：openai", reply)
        self.assertIn("可用 profile：", reply)
        self.assertIn("- aixj", reply)

    def test_format_current_model_reply_shows_codex_profile_model_when_default_is_auto(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "codex.toml"
            config_path.write_text(
                '\n'.join(
                    [
                        'profile = "openai"',
                        "",
                        '[profiles.openai]',
                        'model = "gpt-5.4"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = {
                "agent_model": "auto",
                "cli_runtime": {
                    "active": "codex",
                    "provider_failover": {"codex_config_path": str(config_path)},
                    "providers": {
                        "cursor": {"enabled": False},
                        "codex": {"enabled": True},
                    },
                },
            }
            with mock.patch.object(chat_engine.cli_runtime_service.provider_failover, "current_profile", return_value="openai"):
                reply = chat_engine._format_current_model_reply(cfg)
        self.assertIn("当前默认模型：auto（当前 profile 实际落点 gpt-5.4）", reply)

    def test_list_available_models_parses_dash_format(self):
        fake_completed = type(
            "Result",
            (),
            {"stdout": "Available models\n\nauto - Auto  (current, default)\ngpt-5 - GPT-5\nsonnet-4 - Sonnet 4\n", "stderr": "", "returncode": 0},
        )
        with mock.patch.object(chat_engine.cli_runtime_service, "resolve_cursor_cli_cmd_path", return_value="C:/cursor-agent.cmd"), mock.patch.object(chat_engine.cli_runtime_service.os.path, "isfile", return_value=True), mock.patch.object(chat_engine.cli_runtime_service.subprocess, "run", return_value=fake_completed):
            models, error = chat_engine._list_available_models("c:/workspace", 30, cli_name="cursor")
        self.assertIsNone(error)
        self.assertEqual(models, ["auto", "gpt-5", "sonnet-4"])

    def test_list_available_models_applies_hidden_window_kwargs(self):
        fake_completed = type("Result", (), {"stdout": "auto - Auto\n", "stderr": "", "returncode": 0})
        with mock.patch.object(chat_engine.cli_runtime_service, "resolve_cursor_cli_cmd_path", return_value="C:/cursor-agent.cmd"), \
             mock.patch.object(chat_engine.cli_runtime_service.os.path, "isfile", return_value=True), \
             mock.patch.object(chat_engine.cli_runtime_service, "_windows_hidden_subprocess_kwargs", return_value={"creationflags": 321}), \
             mock.patch.object(chat_engine.cli_runtime_service.subprocess, "run", return_value=fake_completed) as mocked_run:
            models, error = chat_engine._list_available_models("c:/workspace", 30, cli_name="cursor")
        self.assertIsNone(error)
        self.assertEqual(models, ["auto"])
        self.assertEqual(mocked_run.call_args.kwargs["creationflags"], 321)

    def test_run_agent_via_cli_tolerates_non_utf8_stdout_json(self):
        receipt = type(
            "Receipt",
            (),
            {
                "status": "completed",
                "output_bundle": type("Bundle", (), {"text_blocks": [type("Block", (), {"text": "启动失败，请查看日志"})()]} )(),
                "metadata": {},
            },
        )()
        with mock.patch.object(chat_engine.cli_runtime_service, "run_prompt_receipt", return_value=receipt):
            receipt = chat_engine._run_agent_via_cli("test", "c:/workspace", 30, "auto")

        self.assertEqual(receipt.status, "completed")
        self.assertEqual(receipt.output_bundle.text_blocks[0].text, "启动失败，请查看日志")

    def test_run_agent_streaming_tolerates_non_utf8_stream_json(self):
        receipt = type(
            "Receipt",
            (),
            {
                "status": "completed",
                "output_bundle": type("Bundle", (), {"text_blocks": [type("Block", (), {"text": "你好，继续处理"})()]} )(),
                "metadata": {},
            },
        )()
        with mock.patch.object(chat_engine.cli_runtime_service, "run_prompt_receipt", return_value=receipt):
            receipt = chat_engine._run_agent_streaming("test", "c:/workspace", 30, "auto")

        self.assertEqual(receipt.status, "completed")
        self.assertEqual(receipt.output_bundle.text_blocks[0].text, "你好，继续处理")

    def test_run_codex_uses_provider_https_proxy(self):
        provider = {
            "path": "codex",
            "https_proxy": "http://127.0.0.1:10808",
        }
        proc = mock.Mock()
        proc.stdout = ['{"output_text":"ok"}\n']
        proc.stderr = mock.Mock(read=mock.Mock(return_value=""), close=mock.Mock())
        proc.stdin = mock.Mock(write=mock.Mock(), close=mock.Mock())
        proc.poll = mock.Mock(return_value=0)
        proc.wait = mock.Mock(return_value=0)
        proc.returncode = 0
        with mock.patch.object(chat_engine.cli_runtime_service, "_provider_config", return_value=provider), mock.patch.object(chat_engine.cli_runtime_service, "_resolve_command_path", return_value="C:/codex.cmd"), mock.patch.object(chat_engine.cli_runtime_service.subprocess, "Popen", return_value=proc) as mocked_popen:
            out, ok = chat_engine.cli_runtime_service._run_codex("hello", "c:/workspace", 30, {}, {"model": "gpt-5"}, on_segment=None)
        self.assertTrue(ok)
        self.assertEqual(out, "ok")
        self.assertEqual(mocked_popen.call_args.kwargs["env"]["HTTPS_PROXY"], "http://127.0.0.1:10808")
        self.assertNotIn("HTTP_PROXY", mocked_popen.call_args.kwargs["env"])
        self.assertNotIn("ALL_PROXY", mocked_popen.call_args.kwargs["env"])

    def test_run_codex_applies_hidden_window_kwargs(self):
        provider = {"path": "codex"}
        proc = mock.Mock()
        proc.stdout = ['{"output_text":"ok"}\n']
        proc.stderr = mock.Mock(read=mock.Mock(return_value=""), close=mock.Mock())
        proc.stdin = mock.Mock(write=mock.Mock(), close=mock.Mock())
        proc.poll = mock.Mock(return_value=0)
        proc.wait = mock.Mock(return_value=0)
        proc.returncode = 0
        with mock.patch.object(chat_engine.cli_runtime_service, "_provider_config", return_value=provider), \
             mock.patch.object(chat_engine.cli_runtime_service, "_resolve_command_path", return_value="C:/codex.cmd"), \
             mock.patch.object(chat_engine.cli_runtime_service, "_windows_hidden_subprocess_kwargs", return_value={"creationflags": 654}), \
             mock.patch.object(chat_engine.cli_runtime_service.subprocess, "Popen", return_value=proc) as mocked_popen:
            out, ok = chat_engine.cli_runtime_service._run_codex("hello", "c:/workspace", 30, {}, {"model": "gpt-5"}, on_segment=None)
        self.assertTrue(ok)
        self.assertEqual(out, "ok")
        self.assertEqual(mocked_popen.call_args.kwargs["creationflags"], 654)

    def test_build_codex_env_strips_inherited_proxies_when_provider_empty(self):
        with mock.patch.dict(
            chat_engine.cli_runtime_service.os.environ,
            {
                "HTTP_PROXY": "http://127.0.0.1:9",
                "HTTPS_PROXY": "http://127.0.0.1:10808",
                "ALL_PROXY": "socks5://127.0.0.1:9",
                "NO_PROXY": "localhost,127.0.0.1",
                "GIT_HTTP_PROXY": "http://127.0.0.1:9",
                "CODEX_SANDBOX_NETWORK_DISABLED": "1",
                "CODEX_THREAD_ID": "test-thread",
            },
            clear=False,
        ):
            env = chat_engine.cli_runtime_service._build_codex_env({})

        self.assertNotIn("HTTP_PROXY", env)
        self.assertNotIn("HTTPS_PROXY", env)
        self.assertNotIn("ALL_PROXY", env)
        self.assertNotIn("NO_PROXY", env)
        self.assertNotIn("GIT_HTTP_PROXY", env)
        self.assertNotIn("CODEX_SANDBOX_NETWORK_DISABLED", env)
        self.assertNotIn("CODEX_THREAD_ID", env)

    def test_build_codex_env_inherits_proxies_when_enabled(self):
        with mock.patch.dict(
            chat_engine.cli_runtime_service.os.environ,
            {
                "HTTP_PROXY": "http://127.0.0.1:10808",
                "HTTPS_PROXY": "http://127.0.0.1:10808",
                "ALL_PROXY": "socks5://127.0.0.1:10808",
                "NO_PROXY": "localhost,127.0.0.1",
                "CODEX_SANDBOX_NETWORK_DISABLED": "1",
                "CODEX_THREAD_ID": "test-thread",
            },
            clear=False,
        ):
            env = chat_engine.cli_runtime_service._build_codex_env({"inherit_proxy_env": True})

        self.assertEqual(env["HTTP_PROXY"], "http://127.0.0.1:10808")
        self.assertEqual(env["HTTPS_PROXY"], "http://127.0.0.1:10808")
        self.assertEqual(env["ALL_PROXY"], "socks5://127.0.0.1:10808")
        self.assertEqual(env["NO_PROXY"], "localhost,127.0.0.1")
        self.assertNotIn("CODEX_SANDBOX_NETWORK_DISABLED", env)
        self.assertNotIn("CODEX_THREAD_ID", env)

    def test_codex_provider_defaults_to_max_permissions(self):
        provider = chat_engine.cli_runtime_service.get_cli_runtime_settings(
            {
                "cli_runtime": {
                    "providers": {
                        "codex": {
                            "enabled": True,
                        }
                    }
                }
            }
        )["providers"]["codex"]

        self.assertEqual(provider["path"], "codex")
        self.assertTrue(provider["inherit_proxy_env"])
        self.assertEqual(provider["sandbox"], "danger-full-access")
        self.assertEqual(provider["ask_for_approval"], "never")
        self.assertTrue(provider["skip_git_repo_check"])
        self.assertTrue(provider["search"])

    def test_run_agent_uses_runtime_request_prompt_when_mainline_rewrites_it(self):
        router = ChatRouter()
        captured = {}

        class _StubMainlineService:
            def handle_prompt(self, user_prompt, *, invocation_metadata=None, talk_executor=None, chat_executor=None):
                del user_prompt, invocation_metadata, chat_executor
                runtime_request = router.build_runtime_request(
                    Invocation(
                        entrypoint="chat",
                        channel="local",
                        session_id="session-1",
                        actor_id="user-1",
                        user_text="前门协商 prompt",
                        metadata={"original_user_prompt": "原始任务"},
                    )
                )
                talk_executor(runtime_request)
                return type(
                    "Result",
                    (),
                    {
                        "text": "协商回复",
                        "output_bundle": OutputBundle(summary="ok"),
                        "runtime_request": runtime_request,
                        "delivery_plan": None,
                    },
                )()

        def _fake_execute(runtime_request, *, effective_prompt, original_user_prompt, **kwargs):
            del runtime_request, kwargs
            captured["effective_prompt"] = effective_prompt
            captured["original_user_prompt"] = original_user_prompt
            return type(
                "Execution",
                (),
                {
                    "pending_memory_id": "",
                    "raw_reply_text": "",
                    "process_events": [],
                    "metadata": {"session_scope_id": ""},
                },
            )()

        with mock.patch.object(
            chat_engine,
            "get_config",
            return_value={"workspace_root": str(Path.cwd()), "agent_timeout": 30, "max_reply_len": 4000},
        ), mock.patch.object(
            chat_engine,
            "_resolve_turn_runtime",
            return_value={
                "control": {"kind": "run", "prompt": "原始任务"},
                "runtime_request": {},
                "effective_model": "gpt-5.4",
                "effective_cli": "codex",
            },
        ), mock.patch.object(chat_engine, "_chat_mainline_service", return_value=_StubMainlineService()), mock.patch.object(
            chat_engine,
            "_execute_chat_turn_runtime",
            side_effect=_fake_execute,
        ):
            reply = chat_engine.run_agent("原始任务", stream_output=False)

        self.assertEqual(reply, "协商回复")
        self.assertEqual(captured["effective_prompt"], "前门协商 prompt")
        self.assertEqual(captured["original_user_prompt"], "原始任务")

    def test_build_codex_env_prefers_project_venv_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python_exe = root / ".venv" / "Scripts" / "python.exe"
            python_exe.parent.mkdir(parents=True, exist_ok=True)
            python_exe.write_text("", encoding="utf-8")

            env = chat_engine.cli_runtime_service._build_codex_env({}, str(root))

        self.assertEqual(env["BUTLER_PROJECT_PYTHON"], str(python_exe.resolve()))
        self.assertEqual(env["VIRTUAL_ENV"], str((root / ".venv").resolve()))
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(python_exe.parent.resolve()))

    def test_run_codex_sends_prompt_via_stdin(self):
        provider = {
            "path": "codex",
        }
        proc = mock.Mock()
        proc.stdout = ['{"output_text":"ok"}\n']
        proc.stderr = mock.Mock(read=mock.Mock(return_value=""), close=mock.Mock())
        proc.stdin = mock.Mock(write=mock.Mock(), close=mock.Mock())
        proc.poll = mock.Mock(return_value=0)
        proc.wait = mock.Mock(return_value=0)
        proc.returncode = 0
        with mock.patch.object(chat_engine.cli_runtime_service, "_provider_config", return_value=provider), mock.patch.object(chat_engine.cli_runtime_service, "_resolve_command_path", return_value="C:/codex.cmd"), mock.patch.object(chat_engine.cli_runtime_service.subprocess, "Popen", return_value=proc) as mocked_popen:
            out, ok = chat_engine.cli_runtime_service._run_codex("very long prompt", "c:/workspace", 30, {}, {"model": "gpt-5.2"}, on_segment=None)
        self.assertTrue(ok)
        self.assertEqual(out, "ok")
        ca = mocked_popen.call_args
        popen_args = ca.kwargs.get("args") or (ca.args[0] if ca.args else [])
        self.assertEqual(popen_args[-1], "-")
        proc.stdin.write.assert_called_once_with("very long prompt")

    def test_run_codex_applies_provider_overrides_and_ephemeral(self):
        provider = {
            "path": "codex",
            "ephemeral": True,
            "config_overrides": ["model_provider='aixj_vip'"],
            "config_overrides_map": {"speed": "model_reasoning_effort"},
        }
        proc = mock.Mock()
        proc.stdout = ['{"output_text":"ok"}\n']
        proc.stderr = mock.Mock(read=mock.Mock(return_value=""), close=mock.Mock())
        proc.stdin = mock.Mock(write=mock.Mock(), close=mock.Mock())
        proc.poll = mock.Mock(return_value=0)
        proc.wait = mock.Mock(return_value=0)
        proc.returncode = 0
        with mock.patch.object(chat_engine.cli_runtime_service, "_provider_config", return_value=provider), mock.patch.object(chat_engine.cli_runtime_service, "_resolve_command_path", return_value="C:/codex.cmd"), mock.patch.object(chat_engine.cli_runtime_service.subprocess, "Popen", return_value=proc) as mocked_popen:
            out, ok = chat_engine.cli_runtime_service._run_codex("hello", "c:/workspace", 30, {}, {"model": "gpt-5.2", "speed": "high", "config_overrides": ["model_reasoning_effort='medium'"]}, on_segment=None)
        self.assertTrue(ok)
        self.assertEqual(out, "ok")
        ca = mocked_popen.call_args
        args = ca.kwargs.get("args") or (ca.args[0] if ca.args else [])
        self.assertIn("--ephemeral", args)
        self.assertIn("model_provider='aixj_vip'", args)
        self.assertIn("model_reasoning_effort=high", args)
        self.assertIn("model_reasoning_effort='medium'", args)

    def test_resolve_runtime_request_merges_skill_exposure_provider_override(self):
        cfg = {
            "cli_runtime": {
                "active": "codex",
                "providers": {
                    "codex": {"enabled": True, "path": "codex"},
                },
            }
        }

        resolved = chat_engine.cli_runtime_service.resolve_runtime_request(
            cfg,
            {
                "cli": "codex",
                "skill_exposure": {
                    "collection_id": "codex_default",
                    "provider_overrides": {
                        "codex": {
                            "profile": "research",
                            "config_overrides": ["model_reasoning_effort='high'"],
                            "extra_args": ["--skip-something"],
                        }
                    },
                },
            },
        )

        self.assertEqual(resolved["profile"], "research")
        self.assertIn("model_reasoning_effort='high'", resolved["config_overrides"])
        self.assertIn("--skip-something", resolved["extra_args"])
        self.assertEqual(resolved["skill_exposure"]["collection_id"], "codex_default")

    def test_resolve_runtime_request_normalizes_profile_alias(self):
        cfg = {
            "cli_runtime": {
                "active": "codex",
                "defaults": {"profile": "openai"},
                "profile_aliases": {
                    "openai": "openai",
                    "aixj": "aixj",
                    "relay": "aixj",
                },
                "providers": {
                    "codex": {"enabled": True, "path": "codex"},
                },
            }
        }

        resolved = chat_engine.cli_runtime_service.resolve_runtime_request(
            cfg,
            {"cli": "codex", "profile": "relay"},
            model_override="gpt-5.4",
        )

        self.assertEqual(resolved["profile"], "aixj")

    def test_run_codex_bypasses_internal_sandbox_for_full_access_provider(self):
        provider = {
            "path": "codex",
            "sandbox": "danger-full-access",
            "ask_for_approval": "never",
        }
        proc = mock.Mock()
        proc.stdout = ['{"output_text":"ok"}\n']
        proc.stderr = mock.Mock(read=mock.Mock(return_value=""), close=mock.Mock())
        proc.stdin = mock.Mock(write=mock.Mock(), close=mock.Mock())
        proc.poll = mock.Mock(return_value=0)
        proc.wait = mock.Mock(return_value=0)
        proc.returncode = 0
        with mock.patch.object(chat_engine.cli_runtime_service, "_provider_config", return_value=provider), mock.patch.object(chat_engine.cli_runtime_service, "_resolve_command_path", return_value="C:/codex.cmd"), mock.patch.object(chat_engine.cli_runtime_service.subprocess, "Popen", return_value=proc) as mocked_popen:
            out, ok = chat_engine.cli_runtime_service._run_codex("hello", "c:/workspace", 30, {}, {"model": "gpt-5.4"}, on_segment=None)
        self.assertTrue(ok)
        self.assertEqual(out, "ok")
        ca = mocked_popen.call_args
        args = ca.kwargs.get("args") or (ca.args[0] if ca.args else [])
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", args)
        self.assertNotIn("--sandbox", args)
        self.assertNotIn("--full-auto", args)
        self.assertNotIn("--ask-for-approval", args)

    def test_run_codex_passes_isolated_codex_home_to_env(self):
        provider = {
            "path": "codex",
        }
        proc = mock.Mock()
        proc.stdout = ['{"output_text":"ok"}\n']
        proc.stderr = mock.Mock(read=mock.Mock(return_value=""), close=mock.Mock())
        proc.stdin = mock.Mock(write=mock.Mock(), close=mock.Mock())
        proc.poll = mock.Mock(return_value=0)
        proc.wait = mock.Mock(return_value=0)
        proc.returncode = 0
        with mock.patch.object(chat_engine.cli_runtime_service, "_provider_config", return_value=provider), mock.patch.object(chat_engine.cli_runtime_service, "_resolve_command_path", return_value="C:/codex.cmd"), mock.patch.object(chat_engine.cli_runtime_service.subprocess, "Popen", return_value=proc) as mocked_popen:
            out, ok = chat_engine.cli_runtime_service._run_codex("hello", "c:/workspace", 30, {}, {"model": "gpt-5.4", "codex_home": "C:/isolated-codex-home"}, on_segment=None)
        self.assertTrue(ok)
        self.assertEqual(out, "ok")
        env = mocked_popen.call_args.kwargs.get("env") or {}
        self.assertEqual(env.get("CODEX_HOME"), "C:/isolated-codex-home")

    def test_run_codex_streams_json_lines_incrementally(self):
        provider = {"path": "codex"}
        proc = mock.Mock()
        proc.stdout = [
            '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"第一段"}}\n',
            '{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"pwsh -NoProfile -Command \\"Write-Output 1\\"","aggregated_output":"","exit_code":null,"status":"in_progress"}}\n',
            '{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"最终版"}}\n',
            '{"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":2,"output_tokens":3}}\n',
        ]
        proc.stderr = mock.Mock(read=mock.Mock(return_value=""), close=mock.Mock())
        proc.stdin = mock.Mock(write=mock.Mock(), close=mock.Mock())
        proc.poll = mock.Mock(return_value=0)
        proc.wait = mock.Mock(return_value=0)
        proc.returncode = 0
        segments = []
        events = []

        with mock.patch.object(chat_engine.cli_runtime_service, "_provider_config", return_value=provider), mock.patch.object(chat_engine.cli_runtime_service, "_resolve_command_path", return_value="C:/codex.cmd"), mock.patch.object(chat_engine.cli_runtime_service.subprocess, "Popen", return_value=proc):
            out, ok = chat_engine.cli_runtime_service._run_codex(
                "hello",
                "c:/workspace",
                30,
                {},
                {"model": "gpt-5.4"},
                on_segment=segments.append,
                on_event=events.append,
            )

        self.assertTrue(ok)
        self.assertEqual(out, "最终版")
        self.assertEqual(segments, ["第一段", "最终版"])
        self.assertEqual([event["kind"] for event in events], ["command", "usage"])

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
        with mock.patch.object(chat_engine.cli_runtime_service, "_run_cursor", return_value=("S: [unavailable]", False)) as mocked_cursor, mock.patch.object(chat_engine.cli_runtime_service, "_run_codex", return_value=("codex ok", True)) as mocked_codex, mock.patch.object(chat_engine.cli_runtime_service, "cli_provider_available", return_value=True):
            out, ok = chat_engine.cli_runtime_service.run_prompt("hello", "c:/workspace", 30, cfg, {"cli": "cursor"})

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
        with mock.patch.object(chat_engine.cli_runtime_service, "_run_cursor", return_value=("S: [unavailable]", False)), mock.patch.object(chat_engine.cli_runtime_service, "_run_codex", return_value=("codex failed", False)), mock.patch.object(chat_engine.cli_runtime_service, "cli_provider_available", return_value=True):
            out, ok = chat_engine.cli_runtime_service.run_prompt("hello", "c:/workspace", 30, cfg, {"cli": "cursor"})

        self.assertFalse(ok)
        self.assertEqual(out, "S: [unavailable]")


if __name__ == "__main__":
    unittest.main()
