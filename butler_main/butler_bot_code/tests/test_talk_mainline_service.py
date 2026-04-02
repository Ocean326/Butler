from __future__ import annotations

import json
import os
import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from agents_os.contracts import Invocation, OutputBundle, TextBlock
from butler_main.chat import ChatMainlineService, ChatRouter
from butler_main.chat.session_modes import ChatSessionModeState
from butler_main.chat.session_selection import load_chat_session_state
from butler_main.butler_bot_code.tests._tmpdir import test_workdir


class TalkMainlineServiceTests(unittest.TestCase):
    def test_frontdoor_capability_preserves_original_user_prompt_on_rewritten_invocation(self) -> None:
        service = ChatMainlineService()
        router = ChatRouter()
        runtime_request = router.build_runtime_request(
            Invocation(
                entrypoint="chat",
                channel="local",
                session_id="session_frontdoor_meta",
                actor_id="user_frontdoor_meta",
                user_text="原始用户任务",
            )
        )

        class _CapabilityResult:
            metadata = {"negotiation_status": "started", "frontdoor_action": "background_entry"}

        captured: dict[str, str] = {}

        with test_workdir("chat_mainline_frontdoor_capability_meta") as root:
            result = service._handle_frontdoor_capability_via_model(
                runtime_request,
                chat_executor=lambda request: captured.update(
                    {
                        "user_text": str(request.invocation.user_text or ""),
                        "original_user_prompt": str((request.invocation.metadata or {}).get("original_user_prompt") or ""),
                    }
                )
                or type(
                    "Execution",
                    (),
                    {
                        "reply_text": "模型协商回复",
                        "output_bundle": OutputBundle(
                            summary="ok",
                            text_blocks=[TextBlock(text="模型协商回复")],
                        ),
                    },
                )(),
                capability_result=_CapabilityResult(),
                model_reply_prompt="内部协作 prompt",
                workspace=str(root),
                session_scope_id="",
                mode_state=ChatSessionModeState(),
                source_user_text="原始用户任务",
            )

        self.assertEqual(captured["user_text"], "内部协作 prompt")
        self.assertEqual(captured["original_user_prompt"], "原始用户任务")
        self.assertEqual(
            str((result.runtime_request.invocation.metadata or {}).get("original_user_prompt") or ""),
            "原始用户任务",
        )

    def test_builds_feishu_invocation_from_event_payload(self) -> None:
        service = ChatMainlineService()
        event = {
            "event": {
                "message": {
                    "message_id": "om_123",
                    "chat_id": "chat_1",
                    "chat_type": "p2p",
                    "message_type": "text",
                    "thread_id": "thread_1",
                    "content": json.dumps({"text": "今天的进度怎么样？"}, ensure_ascii=False),
                },
                "sender": {
                    "sender_id": {"open_id": "ou_123"},
                    "sender_type": "user",
                },
            },
            "header": {"event_type": "im.message.receive_v1"},
        }

        invocation = service.build_invocation(
            "今天的进度怎么样？",
            invocation_metadata={"feishu_event": event, "workspace": "C:/workspace"},
        )

        self.assertEqual(invocation.channel, "feishu")
        self.assertEqual(invocation.session_id, "thread_1")
        self.assertEqual(invocation.actor_id, "ou_123")
        self.assertEqual(invocation.entrypoint, "chat")
        self.assertEqual(invocation.metadata["workspace"], "C:/workspace")

    def test_build_invocation_strips_pure_prefix_and_records_level(self) -> None:
        service = ChatMainlineService()

        invocation = service.build_invocation(
            "/pure2 继续按刚才方案推进",
            invocation_metadata={"channel": "feishu", "session_id": "thread_pure", "actor_id": "ou_pure"},
        )

        self.assertEqual(invocation.user_text, "继续按刚才方案推进")
        self.assertEqual((invocation.metadata or {}).get("prompt_purity"), {"level": 2, "command_text": "/pure2", "source": "slash_command"})

    def test_pure_command_without_body_returns_help_without_executor(self) -> None:
        service = ChatMainlineService()

        result = service.handle_prompt(
            "/pure3",
            invocation_metadata={
                "channel": "feishu",
                "message_id": "om_pure_help",
                "session_id": "thread_pure_help",
                "actor_id": "ou_pure_help",
                "feishu.receive_id": "ou_pure_help",
                "feishu.receive_id_type": "open_id",
            },
            talk_executor=lambda request: (_ for _ in ()).throw(AssertionError("executor should not run for pure help")),
        )

        self.assertIn("`/pure` 是单轮纯净模式前缀", result.text)
        self.assertTrue(bool((result.metadata or {}).get("prompt_purity_help")))

    def test_routes_plain_talk_into_output_bundle_and_delivery_plan(self) -> None:
        service = ChatMainlineService()
        result = service.handle_prompt(
            "请总结今天的升级计划",
            invocation_metadata={
                "channel": "feishu",
                "message_id": "om_123",
                "session_id": "thread_1",
                "actor_id": "ou_123",
                "feishu.receive_id": "ou_123",
                "feishu.receive_id_type": "open_id",
            },
            talk_executor=lambda request: f"route={request.decision.route}; agent={request.agent_spec.agent_id}",
        )

        self.assertEqual(result.runtime_request.decision.route, "chat")
        self.assertEqual(result.output_bundle.text_blocks[0].text, "route=chat; agent=butler.chat")
        self.assertIsNotNone(result.delivery_plan)
        assert result.delivery_plan is not None
        self.assertEqual(result.delivery_plan.operations[0].action, "create")
        self.assertEqual(result.delivery_plan.session.target, "ou_123")

    def test_auto_router_detects_project_review_and_persists_sticky_role(self) -> None:
        with test_workdir("chat_mainline_auto_router_review") as root:
            service = ChatMainlineService()
            metadata = {
                "channel": "feishu",
                "message_id": "om_auto_router_1",
                "session_id": "thread_auto_router_1",
                "actor_id": "ou_auto_router_1",
                "feishu.receive_id": "ou_auto_router_1",
                "feishu.receive_id_type": "open_id",
                "workspace": str(root),
            }

            first = service.handle_prompt(
                "请帮我 review 这个实现方案并找风险",
                invocation_metadata=metadata,
                talk_executor=lambda request: "先给出 review 结论。",
            )
            second = service.handle_prompt(
                "继续，把 blocker 也列出来",
                invocation_metadata=metadata,
                talk_executor=lambda request: "继续补充 blocker。",
            )

            self.assertEqual(first.runtime_request.compile_plan.main_mode, "project")
            self.assertEqual(first.runtime_request.compile_plan.project_phase, "review")
            self.assertEqual(first.runtime_request.compile_plan.role_id, "project_reviewer")
            self.assertEqual(second.runtime_request.compile_plan.main_mode, "project")
            self.assertEqual(second.runtime_request.compile_plan.project_phase, "review")
            self.assertEqual(second.runtime_request.compile_plan.role_id, "project_reviewer")
            self.assertEqual(str((second.runtime_request.invocation.metadata or {}).get("router_explicit_override_source") or ""), "sticky_mode")

    def test_unrelated_prompt_reopens_internal_chat_session(self) -> None:
        with test_workdir("chat_mainline_session_reopen") as root:
            service = ChatMainlineService()
            metadata = {
                "channel": "feishu",
                "message_id": "om_session_reopen_1",
                "session_id": "thread_session_reopen_1",
                "actor_id": "ou_session_reopen_1",
                "feishu.receive_id": "ou_session_reopen_1",
                "feishu.receive_id_type": "open_id",
                "workspace": str(root),
            }

            first = service.handle_prompt(
                "请帮我 review 这个实现方案并找风险",
                invocation_metadata=metadata,
                talk_executor=lambda request: "先给出 review 结论。",
            )
            first_state = load_chat_session_state(str(root), session_scope_id="feishu:thread_session_reopen_1")
            second = service.handle_prompt(
                "今天下午 3 点我有什么安排？",
                invocation_metadata=metadata,
                talk_executor=lambda request: "这是一个全新日程问题。",
            )
            second_state = load_chat_session_state(str(root), session_scope_id="feishu:thread_session_reopen_1")

            self.assertEqual(first.runtime_request.compile_plan.main_mode, "project")
            self.assertTrue(bool(first_state.active_chat_session_id))
            self.assertEqual(second.runtime_request.compile_plan.main_mode, "chat")
            self.assertEqual(
                str((second.runtime_request.invocation.metadata or {}).get("router_session_action") or ""),
                "reopen_new_session",
            )
            self.assertTrue(bool(str((second.runtime_request.invocation.metadata or {}).get("chat_session_id") or "").strip()))
            self.assertNotEqual(second_state.active_chat_session_id, first_state.active_chat_session_id)

    def test_routes_mission_commands_into_orchestrator_roundtrip(self) -> None:
        with test_workdir("chat_mainline_mission_roundtrip") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
            service = ChatMainlineService()
            invocation_metadata = {
                "channel": "feishu",
                "message_id": "om_456",
                "session_id": "thread_456",
                "actor_id": "ou_456",
                "feishu.receive_id": "ou_456",
                "feishu.receive_id_type": "open_id",
                "workspace": str(root),
            }

            created = service.handle_prompt(
                "放进编排：整理月报并补上 blocker",
                invocation_metadata=invocation_metadata,
            )

            self.assertEqual(created.runtime_request.decision.route, "mission_ingress")
            self.assertIn("mission create:", created.output_bundle.summary)
            mission_id = str((created.metadata or {}).get("workflow_id") or "")
            self.assertTrue(mission_id.startswith("mission_"))
            self.assertIsNotNone(created.delivery_plan)

            status = service.handle_prompt(
                f"查询编排任务 mission_id={mission_id}",
                invocation_metadata=invocation_metadata,
            )

            self.assertEqual(status.runtime_request.decision.route, "mission_ingress")
            self.assertIn(mission_id, status.output_bundle.text_blocks[0].text)

            cancelled = service.handle_prompt(
                f"取消编排任务 mission_id={mission_id}",
                invocation_metadata=invocation_metadata,
            )

            self.assertEqual(cancelled.runtime_request.decision.route, "mission_ingress")
            self.assertIn("cancel", cancelled.output_bundle.text_blocks[0].text.lower())
            self.assertEqual(str((cancelled.metadata or {}).get("status") or ""), "cancelled")

    def test_mission_ingress_bypasses_campaign_negotiation(self) -> None:
        with test_workdir("chat_mainline_mission_priority") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            class _FailingNegotiation:
                def handle(self, **kwargs):
                    raise AssertionError("campaign negotiation should not run on mission_ingress")

            @dataclass
            class _StubReceipt:
                output_bundle: OutputBundle
                summary: str = "mission stub"
                delivery_request: object | None = None
                workflow_id: str = "mission_stub"
                status: str = "created"
                metadata: dict[str, Any] = field(default_factory=dict)

            class _StubOrchestrator:
                def orchestrate(self, request):
                    return _StubReceipt(
                        output_bundle=OutputBundle(
                            summary="mission create: stub",
                            text_blocks=[TextBlock(text="stub ok")],
                        ),
                        workflow_id="mission_stub",
                        status="created",
                        metadata={"mission_operation": "create"},
                    )

            service = ChatMainlineService(
                mission_orchestrator=_StubOrchestrator(),
                campaign_negotiation=_FailingNegotiation(),
            )
            result = service.handle_prompt(
                "放进编排：长期推进项目C",
                invocation_metadata={
                    "channel": "feishu",
                    "message_id": "om_789",
                    "session_id": "thread_789",
                    "actor_id": "ou_789",
                    "feishu.receive_id": "ou_789",
                    "feishu.receive_id_type": "open_id",
                    "workspace": str(root),
                },
            )

            self.assertEqual(result.runtime_request.decision.route, "mission_ingress")
            self.assertIn("mission create", result.output_bundle.summary)

    def test_mission_ingress_attempts_to_bootstrap_orchestrator(self) -> None:
        with test_workdir("chat_mainline_orchestrator_bootstrap") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            class _Bootstrap:
                def __init__(self) -> None:
                    self.calls = 0

                def ensure_online(self):
                    self.calls += 1
                    return type(
                        "BootstrapResult",
                        (),
                        {
                            "ok": False,
                            "running": False,
                            "changed": False,
                            "reason": "start_failed",
                            "command_hint": "./tools/butler restart orchestrator",
                            "fallback_command_hint": ".venv/bin/python -m butler_main.butler_bot_code.manager restart orchestrator",
                        },
                    )()

            class _ShouldNotRunOrchestrator:
                def orchestrate(self, request):
                    raise AssertionError("mission orchestrator should not run when bootstrap failed")

            bootstrap = _Bootstrap()
            service = ChatMainlineService(
                mission_orchestrator=_ShouldNotRunOrchestrator(),
                orchestrator_bootstrap=bootstrap,
            )
            result = service.handle_prompt(
                "放进编排：长期推进项目D",
                invocation_metadata={
                    "channel": "feishu",
                    "message_id": "om_999",
                    "session_id": "thread_999",
                    "actor_id": "ou_999",
                    "feishu.receive_id": "ou_999",
                    "feishu.receive_id_type": "open_id",
                    "workspace": str(root),
                },
            )

            self.assertEqual(bootstrap.calls, 1)
            self.assertEqual(result.runtime_request.decision.route, "mission_ingress")
            self.assertIn("orchestrator offline", result.output_bundle.summary)
            self.assertIn("./tools/butler restart orchestrator", result.text)

    def test_explicit_backend_task_enters_negotiation_before_mission(self) -> None:
        with test_workdir("chat_mainline_background_task_route") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            class _ShouldNotRunOrchestrator:
                def orchestrate(self, request):
                    raise AssertionError("mission orchestrator should not run for discussion-first task")

            service = ChatMainlineService(
                mission_orchestrator=_ShouldNotRunOrchestrator(),
            )
            observed_prompts = []
            result = service.handle_prompt(
                "给你一个后台任务：ssh 179服务器，进入 Transfer_Recovery 目录，整理文献并写论文背景。",
                invocation_metadata={
                    "channel": "feishu",
                    "message_id": "om_ssh_1",
                    "session_id": "thread_ssh_1",
                    "actor_id": "ou_ssh_1",
                    "feishu.receive_id": "ou_ssh_1",
                    "feishu.receive_id_type": "open_id",
                    "workspace": str(root),
                },
                talk_executor=lambda request: observed_prompts.append(request.invocation.user_text) or "这是模型生成的协商态回复",
            )

            self.assertEqual(result.runtime_request.decision.route, "chat")
            self.assertEqual(str((result.metadata or {}).get("negotiation_status") or ""), "backend_entry_required")
            self.assertEqual(str((result.metadata or {}).get("frontdoor_action") or ""), "background_entry")
            self.assertTrue(bool((result.metadata or {}).get("chat_execution_blocked")))
            self.assertIn("进入后台任务入口态", result.text)
            self.assertFalse(observed_prompts)

    def test_contextual_start_followup_uses_model_reply_instead_of_fixed_receipt(self) -> None:
        with test_workdir("chat_mainline_contextual_start_reply") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            metadata = {
                "channel": "feishu",
                "message_id": "om_start_ctx_1",
                "session_id": "thread_start_ctx_1",
                "actor_id": "ou_start_ctx_1",
                "feishu.receive_id": "ou_start_ctx_1",
                "feishu.receive_id_type": "open_id",
                "workspace": str(root),
            }
            service.handle_prompt(
                "给你一个后台任务：登录 179 服务器进入 Transfer_Recovery 目录，系统梳理不少于100篇文献并写 KDD 风格研究背景与现状。",
                invocation_metadata=metadata,
            )

            observed_prompts = []
            started = service.handle_prompt(
                "直接启动，需要英文、截止今天12点，核心是轨迹+还原/重构/地图匹配+跨城迁移。",
                invocation_metadata=metadata,
                talk_executor=lambda request: observed_prompts.append(request.invocation.user_text) or "任务已转入后台，我会按英文和今天12点前推进。",
            )

            self.assertEqual(started.text, "任务已转入后台，我会按英文和今天12点前推进。")
            self.assertEqual(str((started.metadata or {}).get("negotiation_status") or ""), "started")
            self.assertEqual(str((started.metadata or {}).get("startup_mode") or ""), "exploratory")
            self.assertTrue(observed_prompts)
            self.assertIn("后台入口协作协议", observed_prompts[0])
            self.assertIn("任务已进入后台推进", observed_prompts[0])
            self.assertEqual(
                str((started.runtime_request.invocation.metadata or {}).get("original_user_prompt") or ""),
                "直接启动，需要英文、截止今天12点，核心是轨迹+还原/重构/地图匹配+跨城迁移。",
            )
            self.assertNotIn("campaign started", started.text.lower())

    def test_started_campaign_query_uses_frontdoor_query_capability_before_negotiation(self) -> None:
        with test_workdir("chat_mainline_task_query_capability") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            metadata = {
                "channel": "feishu",
                "message_id": "om_query_1",
                "session_id": "thread_query_1",
                "actor_id": "ou_query_1",
                "feishu.receive_id": "ou_query_1",
                "feishu.receive_id_type": "open_id",
                "workspace": str(root),
            }
            service.handle_prompt(
                "后台任务：ssh 179服务器，进入 Transfer_Recovery 目录，整理不少于100篇文献并写研究背景。",
                invocation_metadata=metadata,
            )
            service.handle_prompt(
                "已确认 SSH 可连，Transfer_Recovery 目录存在，研究主题：Transfer Recovery for XXX，文献筛选边界已明确，输出为中文研究背景。",
                invocation_metadata=metadata,
            )
            service.handle_prompt(
                "确认启动",
                invocation_metadata=metadata,
            )

            observed_prompts = []
            result = service.handle_prompt(
                "看一下这个任务进度",
                invocation_metadata=metadata,
                talk_executor=lambda request: observed_prompts.append(request.invocation.user_text) or "模型生成的状态回复",
            )

            self.assertEqual(result.text, "模型生成的状态回复")
            self.assertEqual(str((result.metadata or {}).get("frontdoor_action") or ""), "query_status")
            self.assertTrue(bool((result.metadata or {}).get("task_query_hit")))
            self.assertTrue(observed_prompts)
            self.assertIn("前门协作协议", observed_prompts[0])
            self.assertIn("状态查询协作协议", observed_prompts[0])
            self.assertIn("ObservationPort / QueryService", observed_prompts[0])

    def test_slash_status_uses_frontdoor_query_capability(self) -> None:
        with test_workdir("chat_mainline_slash_status_query") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            metadata = {
                "channel": "feishu",
                "message_id": "om_query_status_1",
                "session_id": "thread_query_status_1",
                "actor_id": "ou_query_status_1",
                "feishu.receive_id": "ou_query_status_1",
                "feishu.receive_id_type": "open_id",
                "workspace": str(root),
            }
            service.handle_prompt(
                "我想长期持续推进项目A，进行多阶段迭代。材料: docs/plan.md",
                invocation_metadata=metadata,
            )

            observed_prompts = []
            result = service.handle_prompt(
                "/status",
                invocation_metadata=metadata,
                talk_executor=lambda request: observed_prompts.append(request.invocation.user_text) or "模型生成的状态回复",
            )

            self.assertEqual(result.text, "模型生成的状态回复")
            self.assertEqual(str((result.metadata or {}).get("frontdoor_action") or ""), "query_status")
            self.assertEqual(str((result.metadata or {}).get("mode_id") or ""), "delivery")
            self.assertTrue(observed_prompts)
            self.assertIn("状态查询协作协议", observed_prompts[0])

    def test_unresolved_campaign_query_uses_frontdoor_query_clarification(self) -> None:
        with test_workdir("chat_mainline_task_query_unresolved") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            observed_prompts = []
            result = service.handle_prompt(
                "看一下这个任务进度",
                invocation_metadata={
                    "channel": "feishu",
                    "message_id": "om_query_unresolved",
                    "session_id": "thread_query_unresolved",
                    "actor_id": "ou_query_unresolved",
                    "feishu.receive_id": "ou_query_unresolved",
                    "feishu.receive_id_type": "open_id",
                    "workspace": str(root),
                },
                talk_executor=lambda request: observed_prompts.append(request.invocation.user_text) or "模型生成的澄清回复",
            )

            self.assertEqual(result.text, "模型生成的澄清回复")
            self.assertEqual(str((result.metadata or {}).get("frontdoor_action") or ""), "query_status")
            self.assertEqual(str((result.metadata or {}).get("task_query_status") or ""), "unresolved")
            self.assertTrue(bool((result.metadata or {}).get("frontdoor_blocked")))
            self.assertTrue(observed_prompts)
            self.assertIn("状态查询协作协议", observed_prompts[0])
            self.assertIn("还没定位到当前会话关联的后台任务", observed_prompts[0])

    def test_missing_campaign_query_returns_frontdoor_clarification(self) -> None:
        with test_workdir("chat_mainline_task_query_missing") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            observed_prompts = []
            result = service.handle_prompt(
                "查一下 campaign_4040 的进度",
                invocation_metadata={
                    "channel": "feishu",
                    "message_id": "om_query_missing",
                    "session_id": "thread_query_missing",
                    "actor_id": "ou_query_missing",
                    "feishu.receive_id": "ou_query_missing",
                    "feishu.receive_id_type": "open_id",
                    "workspace": str(root),
                },
                talk_executor=lambda request: observed_prompts.append(request.invocation.user_text) or "模型生成的澄清回复",
            )

            self.assertEqual(result.text, "模型生成的澄清回复")
            self.assertEqual(str((result.metadata or {}).get("frontdoor_action") or ""), "query_status")
            self.assertEqual(str((result.metadata or {}).get("task_query_status") or ""), "not_found")
            self.assertTrue(bool((result.metadata or {}).get("frontdoor_blocked")))
            self.assertTrue(observed_prompts)
            self.assertIn("状态查询协作协议", observed_prompts[0])
            self.assertIn("campaign_id=campaign_4040", observed_prompts[0])
            self.assertIn("没有找到", observed_prompts[0])

    def test_large_task_without_backend_wording_enters_discussion_first_gate(self) -> None:
        with test_workdir("chat_mainline_background_task_real_gate") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "登录179服务器，进入 Transfer_Recovery 目录，系统梳理不少于100篇文献并写 KDD 风格研究背景与现状。",
                invocation_metadata={
                    "channel": "feishu",
                    "message_id": "om_ssh_real_1",
                    "session_id": "thread_ssh_real_1",
                    "actor_id": "ou_ssh_real_1",
                    "feishu.receive_id": "ou_ssh_real_1",
                    "feishu.receive_id_type": "open_id",
                    "workspace": str(root),
                },
            )

            self.assertEqual(result.runtime_request.decision.route, "chat")
            self.assertEqual(str((result.metadata or {}).get("negotiation_status") or ""), "backend_entry_required")
            self.assertTrue(bool((result.metadata or {}).get("chat_execution_blocked")))
            self.assertIn("进入后台任务入口态", result.text)

    def test_explicit_backend_task_falls_back_to_plain_chat_when_frontdoor_tasks_disabled(self) -> None:
        with test_workdir("chat_mainline_background_disabled") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            observed_prompts: list[str] = []
            user_text = "给你一个后台任务：ssh 179服务器，进入 Transfer_Recovery 目录，整理文献并写论文背景。"
            with patch.dict(os.environ, {"BUTLER_CHAT_FRONTDOOR_TASKS_ENABLED": "0"}):
                result = service.handle_prompt(
                    user_text,
                    invocation_metadata={
                        "channel": "feishu",
                        "message_id": "om_disabled_1",
                        "session_id": "thread_disabled_1",
                        "actor_id": "ou_disabled_1",
                        "feishu.receive_id": "ou_disabled_1",
                        "feishu.receive_id_type": "open_id",
                        "workspace": str(root),
                    },
                    talk_executor=lambda request: observed_prompts.append(str(request.invocation.user_text or "")) or "普通聊天回复",
                )

            self.assertEqual(result.runtime_request.decision.route, "chat")
            self.assertEqual(result.text, "普通聊天回复")
            self.assertEqual(str((result.metadata or {}).get("negotiation_status") or ""), "")
            self.assertEqual(str((result.metadata or {}).get("frontdoor_action") or ""), "")
            self.assertEqual(observed_prompts, [user_text])

    def test_slash_status_preserves_query_intent_when_frontdoor_tasks_disabled(self) -> None:
        with test_workdir("chat_mainline_status_disabled") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            observed_prompts: list[str] = []
            with patch.dict(os.environ, {"BUTLER_CHAT_FRONTDOOR_TASKS_ENABLED": "0"}):
                result = service.handle_prompt(
                    "/status",
                    invocation_metadata={
                        "channel": "feishu",
                        "message_id": "om_disabled_status_1",
                        "session_id": "thread_disabled_status_1",
                        "actor_id": "ou_disabled_status_1",
                        "feishu.receive_id": "ou_disabled_status_1",
                        "feishu.receive_id_type": "open_id",
                        "workspace": str(root),
                    },
                    talk_executor=lambda request: observed_prompts.append(str(request.invocation.user_text or "")) or "按普通聊天处理",
                )

            self.assertEqual(result.runtime_request.decision.route, "chat")
            self.assertEqual(result.text, "按普通聊天处理")
            self.assertEqual(str((result.metadata or {}).get("frontdoor_action") or ""), "query_status")
            self.assertEqual(len(observed_prompts), 1)
            self.assertIn("【状态查询协作协议】", observed_prompts[0])
            self.assertIn("还没定位到当前会话关联的后台任务", observed_prompts[0])


if __name__ == "__main__":
    unittest.main()
