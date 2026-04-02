from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from butler_main.chat import ChatRuntimeService
from butler_main.chat import ChatRouter
from butler_main.chat.providers.butler_prompt_provider import ButlerChatPromptProvider
from butler_main.chat.prompting import build_chat_agent_prompt
from butler_main.runtime_os.process_runtime import ConversationTurnOutput, ConversationTurnState
from agents_os.contracts import Invocation


class _FakeMemoryManager:
    def begin_pending_turn(self, prompt: str, workspace: str, session_scope_id: str = ""):
        return "mem_1", {"topic": "previous topic"}

    def prepare_user_prompt_with_recent(
        self,
        prompt: str,
        *,
        exclude_memory_id: str,
        previous_pending,
        recent_mode: str,
        session_scope_id: str = "",
    ):
        return f"[recent:{recent_mode}] {prompt}"


class _FakeRequestIntakeService:
    def __init__(self, mode: str = "default") -> None:
        self._mode = mode
        self.classify_calls = 0

    def classify(self, prompt: str) -> dict:
        self.classify_calls += 1
        return {"mode": self._mode}

    def build_frontdesk_prompt_block(self, intake_decision: dict) -> str:
        return "INTAKE"


class _FakeMemoryProvider:
    def __init__(self, *, recent_prefix: str = "[recent:default]") -> None:
        self._recent_prefix = recent_prefix

    def begin_turn(self, user_prompt: str, workspace: str, *, session_scope_id: str = ""):
        return "mem_1", {"topic": "previous topic"}

    def prepare_turn_input(
        self,
        user_prompt: str,
        *,
        exclude_memory_id: str,
        previous_pending,
        recent_mode: str,
        session_scope_id: str = "",
    ):
        return f"{self._recent_prefix} {user_prompt}"


class _FakeConversationTurnEngine:
    def __init__(self) -> None:
        self.inputs = []

    def run_turn(self, turn_input):
        self.inputs.append(turn_input)
        return ConversationTurnOutput(
            reply_text="正文回复",
            pending_memory_id="mem_delegate",
            state=ConversationTurnState(
                recent_mode="default",
                pending_memory_id="mem_delegate",
                prepared_user_prompt="[recent:default] 请整理今天的升级进度",
            ),
        )


class TalkRuntimeServiceTests(unittest.TestCase):
    def _runtime_request(self, *, channel: str = "feishu"):
        router = ChatRouter()
        invocation = Invocation(
            entrypoint="talk",
            channel=channel,
            session_id="session_1",
            actor_id="user_open_id",
            user_text="请整理今天的升级进度",
            metadata={"feishu.receive_id": "user_open_id", "feishu.receive_id_type": "open_id"},
        )
        return router.build_runtime_request(invocation)

    def test_runtime_service_builds_output_bundle_with_decide_files(self) -> None:
        captured = {}
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: captured.update(
                {"user_prompt": user_prompt, "capabilities": kwargs.get("agent_capabilities_prompt")}
            ) or "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复\n【decide】[{\"send\":\"./工作区/report.md\"}]", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: ("正文回复", [{"send": "./工作区/report.md"}]),
        )

        execution = service.execute(
            self._runtime_request(),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(execution.pending_memory_id, "mem_1")
        self.assertEqual(execution.reply_text, "正文回复")
        self.assertEqual(execution.raw_reply_text, "正文回复\n【decide】[{\"send\":\"./工作区/report.md\"}]")
        self.assertEqual(captured["user_prompt"], "[recent:chat] 请整理今天的升级进度")
        self.assertEqual(execution.output_bundle.text_blocks[0].text, "正文回复")
        self.assertEqual(execution.output_bundle.files[0].path, "./工作区/report.md")
        self.assertEqual(execution.output_bundle.artifacts[0].uri, "./工作区/report.md")

    def test_runtime_service_collects_process_events_from_streaming_runtime(self) -> None:
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None, on_event=None: (
                on_event({"kind": "command", "text": "1. pytest -q", "status": "completed"}) if callable(on_event) else None,
                on_segment("正文回复") if callable(on_segment) else None,
                ("正文回复", True),
            )[-1],
            parse_decide_fn=lambda text: (text, []),
        )

        execution = service.execute(
            self._runtime_request(),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
            stream_callback=lambda segment: None,
        )

        self.assertEqual(execution.process_events, [{"kind": "command", "text": "pytest -q", "status": "completed"}])
        self.assertEqual(execution.metadata["process_events"], execution.process_events)

    def test_runtime_service_exposes_receipt_metadata_for_session_recovery(self) -> None:
        receipt = SimpleNamespace(
            status="completed",
            summary="正文回复",
            output_bundle=SimpleNamespace(text_blocks=[SimpleNamespace(text="正文回复")]),
            metadata={
                "runtime_request": {"cli": "codex", "model": "gpt-5.4"},
                "external_session": {
                    "provider": "codex",
                    "thread_id": "thread-1",
                    "resume_durable": True,
                },
                "recovery_state": {"resume_requested": True, "degraded": False},
                "vendor_capabilities": {"vendor": "codex"},
                "command_events": [{"kind": "command", "text": "1. pytest -q", "status": "completed"}],
            },
        )
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: receipt,
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: (text, []),
        )

        execution = service.execute(
            self._runtime_request(),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(execution.metadata["runtime_request"]["cli"], "codex")
        self.assertEqual(execution.metadata["external_session"]["thread_id"], "thread-1")
        self.assertEqual(execution.metadata["recovery_state"]["resume_requested"], True)
        self.assertEqual(execution.process_events[0]["text"], "pytest -q")

    def test_content_share_mode_omits_agent_capabilities_prompt(self) -> None:
        captured = {}
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(mode="content_share"),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: captured.update(
                {"capabilities": kwargs.get("agent_capabilities_prompt")}
            ) or "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: (text, []),
        )

        execution = service.execute(
            self._runtime_request(),
            effective_prompt="帮我转一下这条内容",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(captured["capabilities"], "")
        self.assertEqual(execution.output_bundle.metadata["decide_count"], 0)

    def test_runtime_service_passes_runtime_cli_into_prompt_builder(self) -> None:
        captured = {}
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: captured.update(
                {
                    "runtime_cli": kwargs.get("runtime_cli"),
                    "skill_exposure": kwargs.get("skill_exposure"),
                    "role_id": kwargs.get("role_id"),
                    "injection_tier": kwargs.get("injection_tier"),
                    "capability_policy": kwargs.get("capability_policy"),
                }
            ) or "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: (text, []),
        )
        runtime_request = self._runtime_request()
        runtime_request.invocation.metadata["runtime_cli"] = "codex"

        service.execute(
            runtime_request,
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(captured["runtime_cli"], "codex")
        self.assertEqual(captured["skill_exposure"]["collection_id"], "codex_default")
        self.assertEqual(captured["skill_exposure"]["provider_skill_source"], "butler")
        self.assertEqual(captured["role_id"], runtime_request.compile_plan.role_id)
        self.assertEqual(captured["injection_tier"], runtime_request.compile_plan.injection_tier)
        self.assertEqual(captured["capability_policy"], runtime_request.compile_plan.capability_policy)

    def test_runtime_service_pure_level_two_skips_skills_and_capabilities(self) -> None:
        captured = {}
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: captured.update(
                {
                    "user_prompt": user_prompt,
                    "skills_prompt": kwargs.get("skills_prompt"),
                    "capabilities": kwargs.get("agent_capabilities_prompt"),
                    "prompt_purity": kwargs.get("prompt_purity"),
                }
            ) or "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: (text, []),
        )
        runtime_request = self._runtime_request()
        runtime_request.invocation.metadata["prompt_purity"] = {"level": 2}

        service.execute(
            runtime_request,
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(captured["skills_prompt"], "")
        self.assertEqual(captured["capabilities"], "")
        self.assertEqual(captured["prompt_purity"], {"level": 2})

    def test_runtime_service_skips_capabilities_render_when_prompt_gate_rejects(self) -> None:
        captured = {"capability_rendered": 0}
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: captured.update(
                {"capabilities": kwargs.get("agent_capabilities_prompt")}
            ) or "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: captured.__setitem__("capability_rendered", captured["capability_rendered"] + 1) or "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: (text, []),
        )

        service.execute(
            self._runtime_request(),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(captured["capability_rendered"], 0)
        self.assertEqual(captured["capabilities"], "")

    def test_runtime_service_pure_level_three_uses_raw_prompt_without_recent(self) -> None:
        captured = {}
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: captured.update(
                {"user_prompt": user_prompt, "prompt_purity": kwargs.get("prompt_purity")}
            ) or "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: (text, []),
        )
        runtime_request = self._runtime_request()
        runtime_request.invocation.metadata["prompt_purity"] = {"level": 3}

        service.execute(
            runtime_request,
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(captured["user_prompt"], "请整理今天的升级进度")
        self.assertEqual(captured["prompt_purity"], {"level": 3})

    def test_runtime_service_keeps_recent_context_in_final_codex_prompt(self) -> None:
        captured = {}
        service = ChatRuntimeService(
            memory_provider=_FakeMemoryProvider(recent_prefix="【recent_memory】\n- 最近主线：整理 chat recent 注入\n\n【用户消息】"),
            prompt_provider=ButlerChatPromptProvider(),
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: "UNUSED",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: captured.update({"prompt": prompt}) or ("正文回复", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: (text, []),
        )
        runtime_request = self._runtime_request()
        runtime_request.invocation.metadata["runtime_cli"] = "codex"

        service.execute(
            runtime_request,
            effective_prompt="继续实现",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        prompt = captured["prompt"]
        self.assertIn("【Codex Chat 约束】", prompt)
        self.assertIn("【recent_memory】", prompt)
        self.assertIn("整理 chat recent 注入", prompt)
        self.assertIn("【用户消息】\n【recent_memory】", prompt)

    def test_runtime_service_exposes_prompt_block_stats(self) -> None:
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=build_chat_agent_prompt,
            render_skills_prompt_fn=lambda workspace: "",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: (text, []),
        )

        execution = service.execute(
            self._runtime_request(),
            effective_prompt="帮我总结今天的设计取舍",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        stats = execution.metadata["prompt_block_stats"]
        block_ids = {str(item.get("block_id") or "") for item in stats}
        self.assertIn("channel_intro", block_ids)
        self.assertIn("dialogue_core", block_ids)
        self.assertIn("dialogue_soul_excerpt", block_ids)
        self.assertIsInstance(execution.metadata["prompt_block_budgets"], dict)
        self.assertFalse(execution.metadata["intake_reused"])

    def test_runtime_service_reuses_prefilled_intake_decision(self) -> None:
        intake = _FakeRequestIntakeService(mode="content_share")
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=intake,
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: (text, []),
        )
        runtime_request = self._runtime_request()
        runtime_request.invocation.metadata["prefilled_intake_decision"] = {"mode": "content_share"}

        execution = service.execute(
            runtime_request,
            effective_prompt="帮我转一下这条内容",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(intake.classify_calls, 0)
        self.assertTrue(execution.metadata["intake_reused"])

    def test_streaming_segments_are_forwarded_immediately(self) -> None:
        observed = []
        runner_returned = {"value": False}

        def fake_stream_run(prompt, workspace, timeout, model, on_segment=None):
            if on_segment:
                on_segment("第一段")
                on_segment("第一段\n第二段")
            runner_returned["value"] = True
            return "第一段\n第二段", True

        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复", True),
            run_agent_streaming_fn=fake_stream_run,
            parse_decide_fn=lambda text: (text, []),
        )

        execution = service.execute(
            self._runtime_request(),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
            stream_callback=lambda segment: observed.append((segment, runner_returned["value"])),
        )

        self.assertEqual(
            observed,
            [
                ("第一段", False),
                ("第一段\n第二段", False),
            ],
        )
        self.assertEqual(execution.reply_text, "第一段\n第二段")

    def test_runtime_service_normalizes_file_outputs_for_cli_channel(self) -> None:
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复\n【decide】[{\"send\":\"./工作区/report.md\"}]", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: ("正文回复", [{"send": "./工作区/report.md"}]),
        )

        execution = service.execute(
            self._runtime_request(channel="cli"),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(execution.output_bundle.files, [])
        self.assertEqual(execution.output_bundle.metadata["channel_profile"], "cli")
        self.assertEqual(execution.output_bundle.metadata["normalized_away"], "files")

    def test_runtime_service_normalizes_file_outputs_for_weixin_alias_channel(self) -> None:
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复\n【decide】[{\"send\":\"./工作区/report.md\"}]", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: ("正文回复", [{"send": "./工作区/report.md"}]),
        )

        execution = service.execute(
            self._runtime_request(channel="weixi"),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(execution.output_bundle.files[0].path, "./工作区/report.md")
        self.assertEqual(execution.output_bundle.metadata["channel_profile"], "weixin")
        self.assertNotIn("normalized_away", execution.output_bundle.metadata)

    def test_runtime_service_routes_image_outputs_into_weixin_images(self) -> None:
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: ("正文回复\n【decide】[{\"send\":\"./工作区/chart.png\"}]", True),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: ("正文回复", [{"send": "./工作区/chart.png"}]),
        )

        execution = service.execute(
            self._runtime_request(channel="weixin"),
            effective_prompt="把图发我",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(execution.output_bundle.images[0].path, "./工作区/chart.png")
        self.assertEqual(execution.output_bundle.files, [])

    def test_runtime_service_flattens_markdown_reply_for_weixin_channel(self) -> None:
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: "PROMPT",
            render_skills_prompt_fn=lambda workspace: "SKILLS",
            render_agent_capabilities_prompt_fn=lambda workspace: "CAPS",
            run_agent_via_cli_fn=lambda prompt, workspace, timeout, model: (
                "## 今日进展\n"
                "- 已修复 `getupdates` 超时边界\n"
                "- 已关闭本地地址代理绕行\n\n"
                "```bash\npython -m unittest butler_main.butler_bot_code.tests.test_talk_runtime_service\n```\n\n"
                "详见[排查记录](https://example.com/report)\n",
                True,
            ),
            run_agent_streaming_fn=lambda prompt, workspace, timeout, model, on_segment=None: ("", False),
            parse_decide_fn=lambda text: (text, []),
        )

        execution = service.execute(
            self._runtime_request(channel="weixi"),
            effective_prompt="同步一下微信链路进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        rendered = execution.output_bundle.text_blocks[0].text
        self.assertIn("【今日进展】", rendered)
        self.assertIn("- 已修复 getupdates 超时边界", rendered)
        self.assertIn("- 已关闭本地地址代理绕行", rendered)
        self.assertIn("python -m unittest butler_main.butler_bot_code.tests.test_talk_runtime_service", rendered)
        self.assertIn("https://example.com/report", rendered)
        self.assertNotIn("## 今日进展", rendered)
        self.assertNotIn("```", rendered)
        self.assertNotIn("`getupdates`", rendered)
        self.assertNotIn("[排查记录](", rendered)
        self.assertEqual(execution.output_bundle.metadata["text_normalized_for_channel"], "weixin")

    def test_runtime_service_can_delegate_turn_execution_to_conversation_engine(self) -> None:
        fake_engine = _FakeConversationTurnEngine()
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda *args, **kwargs: self.fail("build_prompt_fn should not run when engine is injected"),
            render_skills_prompt_fn=lambda workspace: self.fail("render_skills_prompt_fn should not run when engine is injected"),
            render_agent_capabilities_prompt_fn=lambda workspace: self.fail("render_agent_capabilities_prompt_fn should not run when engine is injected"),
            run_agent_via_cli_fn=lambda *args, **kwargs: self.fail("run_agent_via_cli_fn should not run when engine is injected"),
            run_agent_streaming_fn=lambda *args, **kwargs: self.fail("run_agent_streaming_fn should not run when engine is injected"),
            parse_decide_fn=lambda text: (text, []),
            conversation_turn_engine=fake_engine,
        )

        execution = service.execute(
            self._runtime_request(channel="generic"),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(fake_engine.inputs[0].user_prompt, "请整理今天的升级进度")
        self.assertEqual(fake_engine.inputs[0].metadata["session_scope_id"], "")
        self.assertEqual(execution.pending_memory_id, "mem_delegate")
        self.assertEqual(execution.reply_text, "正文回复")

    def test_runtime_service_passes_feishu_session_scope_to_conversation_engine(self) -> None:
        fake_engine = _FakeConversationTurnEngine()
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda *args, **kwargs: self.fail("build_prompt_fn should not run when engine is injected"),
            render_skills_prompt_fn=lambda workspace: self.fail("render_skills_prompt_fn should not run when engine is injected"),
            render_agent_capabilities_prompt_fn=lambda workspace: self.fail("render_agent_capabilities_prompt_fn should not run when engine is injected"),
            run_agent_via_cli_fn=lambda *args, **kwargs: self.fail("run_agent_via_cli_fn should not run when engine is injected"),
            run_agent_streaming_fn=lambda *args, **kwargs: self.fail("run_agent_streaming_fn should not run when engine is injected"),
            parse_decide_fn=lambda text: (text, []),
            conversation_turn_engine=fake_engine,
        )

        execution = service.execute(
            self._runtime_request(channel="feishu"),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(fake_engine.inputs[0].metadata["session_scope_id"], "feishu:session_1")
        self.assertEqual(execution.metadata["session_scope_id"], "feishu:session_1")

    def test_runtime_service_passes_weixin_session_scope_to_conversation_engine(self) -> None:
        fake_engine = _FakeConversationTurnEngine()
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda *args, **kwargs: self.fail("build_prompt_fn should not run when engine is injected"),
            render_skills_prompt_fn=lambda workspace: self.fail("render_skills_prompt_fn should not run when engine is injected"),
            render_agent_capabilities_prompt_fn=lambda workspace: self.fail("render_agent_capabilities_prompt_fn should not run when engine is injected"),
            run_agent_via_cli_fn=lambda *args, **kwargs: self.fail("run_agent_via_cli_fn should not run when engine is injected"),
            run_agent_streaming_fn=lambda *args, **kwargs: self.fail("run_agent_streaming_fn should not run when engine is injected"),
            parse_decide_fn=lambda text: (text, []),
            conversation_turn_engine=fake_engine,
        )

        execution = service.execute(
            self._runtime_request(channel="weixin"),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(fake_engine.inputs[0].metadata["session_scope_id"], "weixin:session_1")
        self.assertEqual(execution.metadata["session_scope_id"], "weixin:session_1")

    def test_runtime_service_passes_cli_session_scope_to_conversation_engine(self) -> None:
        fake_engine = _FakeConversationTurnEngine()
        service = ChatRuntimeService(
            memory_manager=_FakeMemoryManager(),
            request_intake_service=_FakeRequestIntakeService(),
            build_prompt_fn=lambda *args, **kwargs: self.fail("build_prompt_fn should not run when engine is injected"),
            render_skills_prompt_fn=lambda workspace: self.fail("render_skills_prompt_fn should not run when engine is injected"),
            render_agent_capabilities_prompt_fn=lambda workspace: self.fail("render_agent_capabilities_prompt_fn should not run when engine is injected"),
            run_agent_via_cli_fn=lambda *args, **kwargs: self.fail("run_agent_via_cli_fn should not run when engine is injected"),
            run_agent_streaming_fn=lambda *args, **kwargs: self.fail("run_agent_streaming_fn should not run when engine is injected"),
            parse_decide_fn=lambda text: (text, []),
            conversation_turn_engine=fake_engine,
        )

        execution = service.execute(
            self._runtime_request(channel="cli"),
            effective_prompt="请整理今天的升级进度",
            image_paths=None,
            workspace="C:/workspace",
            timeout=30,
            effective_model="gpt-5.4",
            max_len=4000,
        )

        self.assertEqual(fake_engine.inputs[0].metadata["session_scope_id"], "cli:session_1")
        self.assertEqual(execution.metadata["session_scope_id"], "cli:session_1")


if __name__ == "__main__":
    unittest.main()
