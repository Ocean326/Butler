from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
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

from agents_os.contracts import Invocation
from butler_main.chat import ChatRouter
from butler_main.chat.frontdoor_cli_router import FrontDoorCliRouter
from butler_main.chat.session_selection import ChatSessionSelection


class ChatRouterFrontdoorTests(unittest.TestCase):
    def test_orchestrator_alias_now_folds_into_chat(self) -> None:
        router = ChatRouter()
        decision = router.route(
            Invocation(
                entrypoint="orchestrator",
                channel="feishu",
                session_id="session-1",
                actor_id="user-1",
                user_text="请创建一个编排任务",
            )
        )

        self.assertEqual(decision.route, "chat")
        self.assertEqual(decision.runtime_owner, "AgentRuntime")

    def test_opaque_legacy_marker_stays_on_chat_frontdoor(self) -> None:
        router = ChatRouter()
        decision = router.route(
            Invocation(
                entrypoint="chat",
                channel="feishu",
                session_id="session-2",
                actor_id="user-2",
                user_text='【legacy_task_blob】{"task":"整理"}',
            )
        )

        self.assertEqual(decision.route, "chat")
        self.assertEqual(decision.runtime_owner, "AgentRuntime")

    def test_explicit_mission_command_routes_to_mission_ingress(self) -> None:
        router = ChatRouter()
        decision = router.route(
            Invocation(
                entrypoint="chat",
                channel="feishu",
                session_id="session-3",
                actor_id="user-3",
                user_text="/mission create 整理今天的编排任务",
            )
        )

        self.assertEqual(decision.route, "mission_ingress")
        self.assertEqual(decision.runtime_owner, "MissionOrchestrator")

    def test_explicit_mission_command_stays_on_chat_when_frontdoor_tasks_disabled(self) -> None:
        router = ChatRouter()
        with patch.dict(os.environ, {"BUTLER_CHAT_FRONTDOOR_TASKS_ENABLED": "0"}):
            decision = router.route(
                Invocation(
                    entrypoint="chat",
                    channel="feishu",
                    session_id="session-3-disabled",
                    actor_id="user-3-disabled",
                    user_text="/mission create 整理今天的编排任务",
                )
            )

        self.assertEqual(decision.route, "chat")
        self.assertEqual(decision.runtime_owner, "AgentRuntime")

    def test_obvious_background_ssh_task_stays_on_chat_for_negotiation(self) -> None:
        router = ChatRouter()
        decision = router.route(
            Invocation(
                entrypoint="chat",
                channel="feishu",
                session_id="session-ssh-1",
                actor_id="user-ssh-1",
                user_text="ssh 179服务器，登录目录后整理至少100篇文献并写论文背景。",
            )
        )

        self.assertEqual(decision.route, "chat")
        self.assertEqual(decision.runtime_owner, "AgentRuntime")

    def test_build_delivery_session_uses_weixin_metadata_when_channel_is_weixin(self) -> None:
        router = ChatRouter()
        invocation = Invocation(
            entrypoint="chat",
            channel="weixin",
            session_id="wx-session-1",
            actor_id="wx-actor-fallback",
            user_text="你好",
            source_event_id="wx-mid-1",
            metadata={
                "weixin.receive_id": "wx-user-1",
                "weixin.receive_id_type": "open_id",
                "weixin.conversation_key": "weixin:bot-1:dm:wx-user-1",
                "weixin.raw_session_ref": "wx-thread-1",
            },
        )

        delivery_session = router.build_delivery_session(invocation, router.route(invocation))

        self.assertEqual(delivery_session.platform, "weixin")
        self.assertEqual(delivery_session.target, "wx-user-1")
        self.assertEqual(delivery_session.target_type, "open_id")
        self.assertEqual(delivery_session.thread_id, "wx-thread-1")
        self.assertEqual(delivery_session.metadata["weixin.conversation_key"], "weixin:bot-1:dm:wx-user-1")
        self.assertEqual(delivery_session.metadata["weixin.message_id"], "wx-mid-1")

    def test_build_runtime_request_attaches_cli_channel_profile(self) -> None:
        router = ChatRouter()
        invocation = Invocation(
            entrypoint="chat",
            channel="cli",
            session_id="cli-session-1",
            actor_id="cli-user-1",
            user_text="请直接给我命令",
        )

        runtime_request = router.build_runtime_request(invocation)

        self.assertEqual(runtime_request.channel_profile.channel, "cli")
        self.assertFalse(runtime_request.channel_profile.can_send_images)
        self.assertFalse(runtime_request.channel_profile.can_send_files)

    def test_build_runtime_request_normalizes_weixi_alias_to_weixin_profile(self) -> None:
        router = ChatRouter()
        invocation = Invocation(
            entrypoint="chat",
            channel="weixi",
            session_id="wx-session-2",
            actor_id="wx-user-2",
            user_text="发我一句短回复",
            source_event_id="wx-mid-2",
            metadata={
                "weixin.receive_id": "wx-user-2",
                "weixin.receive_id_type": "open_id",
                "weixin.raw_session_ref": "wx-thread-2",
            },
        )

        runtime_request = router.build_runtime_request(invocation)

        self.assertEqual(runtime_request.channel_profile.channel, "weixin")
        self.assertTrue(runtime_request.channel_profile.can_send_images)
        self.assertTrue(runtime_request.channel_profile.can_send_files)
        self.assertEqual(runtime_request.delivery_session.platform, "weixin")
        self.assertEqual(runtime_request.delivery_session.metadata["channel"], "weixin")

    def test_build_runtime_request_compiles_auto_project_review_plan(self) -> None:
        router = ChatRouter()
        invocation = Invocation(
            entrypoint="chat",
            channel="feishu",
            session_id="session-auto-review",
            actor_id="user-auto-review",
            user_text="请帮我 review 这个实现方案并找风险",
        )

        runtime_request = router.build_runtime_request(invocation)

        self.assertEqual(runtime_request.compile_plan.main_mode, "project")
        self.assertEqual(runtime_request.compile_plan.project_phase, "review")
        self.assertEqual(runtime_request.compile_plan.role_id, "project_reviewer")
        self.assertEqual(runtime_request.compile_plan.injection_tier, "extended")
        self.assertEqual(runtime_request.invocation.metadata["chat_role_id"], "project_reviewer")
        self.assertEqual(runtime_request.invocation.metadata["chat_injection_tier"], "extended")

    def test_build_runtime_request_reuses_sticky_project_mode_for_short_followup(self) -> None:
        router = ChatRouter()
        invocation = Invocation(
            entrypoint="chat",
            channel="feishu",
            session_id="session-sticky-plan",
            actor_id="user-sticky-plan",
            user_text="继续，把 blocker 也列出来",
            metadata={
                "chat_main_mode": "project",
                "chat_project_phase": "plan",
                "router_explicit_override_source": "sticky_mode",
            },
        )

        runtime_request = router.build_runtime_request(
            invocation,
            mode_state={"main_mode": "project", "project_phase": "plan", "project_next_phase": "plan"},
        )

        self.assertEqual(runtime_request.compile_plan.main_mode, "project")
        self.assertEqual(runtime_request.compile_plan.project_phase, "plan")
        self.assertEqual(runtime_request.compile_plan.role_id, "project_planner")
        self.assertEqual(runtime_request.compile_plan.auto_route_reason, "sticky_mode_continuation")

    def test_frontdoor_cli_router_defaults_simple_chat_to_cursor_fast_lane(self) -> None:
        router = ChatRouter()
        frontdoor_router = FrontDoorCliRouter(chat_router=router)
        invocation = Invocation(
            entrypoint="chat",
            channel="feishu",
            session_id="session-router-fast",
            actor_id="user-router-fast",
            user_text="帮我简单总结一下今天要做什么",
        )

        result = frontdoor_router.compile(
            invocation=invocation,
            workspace=str(REPO_ROOT),
            mode_state={},
            explicit_main_mode="chat",
            explicit_project_phase="",
            explicit_override_source="",
            session_selection=ChatSessionSelection(chat_session_id="chat_session_1"),
            intake_decision={"mode": "sync_quick_task", "frontdoor_action": "normal_chat"},
            legacy_route_decision=router.route(invocation),
            explicit_frontdoor_mode="",
        )

        self.assertEqual(result.compile_plan.runtime_lane, "cursor_fast")
        self.assertEqual(result.compile_plan.runtime_cli, "cursor")
        self.assertEqual(result.compile_plan.runtime_model, "composer-2-fast")
        self.assertEqual(result.compile_plan.runtime_extra_args, ("--mode", "ask"))

    def test_frontdoor_cli_router_promotes_background_entry_to_codex_lane(self) -> None:
        router = ChatRouter()
        frontdoor_router = FrontDoorCliRouter(chat_router=router)
        invocation = Invocation(
            entrypoint="chat",
            channel="feishu",
            session_id="session-router-deep",
            actor_id="user-router-deep",
            user_text="给你一个后台任务：ssh 179服务器，长期推进这个研究任务",
        )

        result = frontdoor_router.compile(
            invocation=invocation,
            workspace=str(REPO_ROOT),
            mode_state={},
            explicit_main_mode="chat",
            explicit_project_phase="",
            explicit_override_source="",
            session_selection=ChatSessionSelection(chat_session_id="chat_session_2"),
            intake_decision={
                "mode": "async_program",
                "frontdoor_action": "discuss_backend_entry",
                "explicit_backend_request": True,
                "external_execution_risk": True,
            },
            legacy_route_decision=router.route(invocation),
            explicit_frontdoor_mode="",
        )

        self.assertEqual(result.compile_plan.frontdoor_action, "background_entry")
        self.assertEqual(result.compile_plan.runtime_lane, "codex_deep")
        self.assertEqual(result.compile_plan.runtime_cli, "codex")
        self.assertEqual(result.compile_plan.runtime_model, "gpt-5.4")


if __name__ == "__main__":
    unittest.main()
