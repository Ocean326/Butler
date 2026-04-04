from __future__ import annotations

import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from agents_os.contracts import DeliverySession, Invocation
from agents_os.runtime import RouteProjection, RuntimeRequest
from butler_main.butler_bot_code.tests._tmpdir import test_workdir
from butler_main.chat import ChatRouter
from butler_main.orchestrator import ButlerMissionOrchestrator, build_orchestrator_service_for_workspace


class TalkRouterAndMissionOrchestratorTests(unittest.TestCase):
    def test_talk_router_builds_agent_spec_backed_runtime_request(self) -> None:
        router = ChatRouter()
        invocation = Invocation(
            entrypoint="talk",
            channel="feishu",
            session_id="session_1",
            actor_id="user_open_id",
            user_text="帮我整理一下今天的升级进度",
            metadata={"feishu.receive_id": "user_open_id", "feishu.receive_id_type": "open_id"},
        )

        request = router.build_runtime_request(invocation)

        self.assertEqual(request.decision.route, "chat")
        self.assertIsNotNone(request.agent_spec)
        assert request.agent_spec is not None
        self.assertEqual(request.agent_spec.agent_id, "butler.chat")
        self.assertEqual(request.agent_spec.profile.prompt_profile_id, "butler.chat")
        self.assertEqual(request.prompt_profile.bootstrap_refs[0], "persona:butler_chat")
        self.assertEqual(request.memory_policy.visibility_flags[0], "chat_visible")
        self.assertEqual(request.prompt_context.dynamic_metadata["product_surface"], "chat")
        self.assertEqual(request.prompt_context.blocks[0].name, "route")
        self.assertTrue(request.agent_spec.capabilities.retrieval_enabled)
        self.assertEqual(request.agent_spec.runtime_key, "agent_runtime")
        self.assertEqual(request.delivery_session.target, "user_open_id")

    def test_mission_orchestrator_creates_product_mission_from_runtime_request(self) -> None:
        with test_workdir("mission_orchestrator_create") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            orchestrator = ButlerMissionOrchestrator()
            request = RuntimeRequest(
                invocation=Invocation(
                    entrypoint="mission_ingress",
                    channel="feishu",
                    session_id="session_1",
                    actor_id="user_open_id",
                    user_text="为 talk 主链最小接线建立一个 mission",
                ),
                route=RouteProjection(route_key="mission_ingress", workflow_kind="mission"),
                delivery_session=DeliverySession(platform="feishu", mode="reply", target="user_open_id"),
                metadata={"workspace": str(root)},
            )

            receipt = orchestrator.orchestrate(request)

            self.assertEqual(receipt.workflow_kind, "mission")
            self.assertEqual(receipt.status, "pending")
            self.assertEqual(receipt.projection.status, "ready")
            self.assertTrue(receipt.workflow_id.startswith("mission_"))
            self.assertIsNotNone(receipt.output_bundle)
            assert receipt.output_bundle is not None
            self.assertIn("mission create:", receipt.output_bundle.summary)
            self.assertIsNotNone(receipt.delivery_request)

    def test_mission_orchestrator_can_query_existing_mission_status(self) -> None:
        with test_workdir("mission_orchestrator_status") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            orchestrator = ButlerMissionOrchestrator()
            create_receipt = orchestrator.orchestrate(
                RuntimeRequest(
                    invocation=Invocation(
                        entrypoint="mission_ingress",
                        channel="feishu",
                        session_id="session_1",
                        actor_id="user_open_id",
                        user_text="为 mission status 测试建一个 mission",
                    ),
                    metadata={"workspace": str(root)},
                )
            )
            mission_id = create_receipt.workflow_id

            status_receipt = orchestrator.orchestrate(
                RuntimeRequest(
                    invocation=Invocation(
                        entrypoint="mission_ingress",
                        channel="feishu",
                        session_id="session_1",
                        actor_id="user_open_id",
                        user_text="/mission status",
                    ),
                    metadata={
                        "workspace": str(root),
                        "mission_operation": "status",
                        "mission_id": mission_id,
                    },
                )
            )

            self.assertEqual(status_receipt.workflow_id, mission_id)
            self.assertEqual(status_receipt.status, "pending")
            self.assertEqual(status_receipt.projection.status, "ready")
            self.assertIsNotNone(status_receipt.output_bundle)
            assert status_receipt.output_bundle is not None
            self.assertIn(mission_id, status_receipt.output_bundle.text_blocks[0].text)

    def test_mission_orchestrator_parses_status_and_control_from_user_text(self) -> None:
        with test_workdir("mission_orchestrator_text_commands") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            orchestrator = ButlerMissionOrchestrator()
            create_receipt = orchestrator.orchestrate(
                RuntimeRequest(
                    invocation=Invocation(
                        entrypoint="mission_ingress",
                        channel="feishu",
                        session_id="session_1",
                        actor_id="user_open_id",
                        user_text="/mission create 整理月报并补上 blocker",
                    ),
                    metadata={"workspace": str(root)},
                )
            )
            mission_id = create_receipt.workflow_id

            status_receipt = orchestrator.orchestrate(
                RuntimeRequest(
                    invocation=Invocation(
                        entrypoint="mission_ingress",
                        channel="feishu",
                        session_id="session_1",
                        actor_id="user_open_id",
                        user_text=f"查询编排任务 mission_id={mission_id}",
                    ),
                    metadata={"workspace": str(root)},
                )
            )
            self.assertEqual(status_receipt.workflow_id, mission_id)
            self.assertIn(mission_id, status_receipt.output_bundle.text_blocks[0].text)

            cancel_receipt = orchestrator.orchestrate(
                RuntimeRequest(
                    invocation=Invocation(
                        entrypoint="mission_ingress",
                        channel="feishu",
                        session_id="session_1",
                        actor_id="user_open_id",
                        user_text=f"取消编排任务 mission_id={mission_id}",
                    ),
                    metadata={"workspace": str(root)},
                )
            )
            self.assertEqual(cancel_receipt.workflow_id, mission_id)
            self.assertEqual(cancel_receipt.status, "cancelled")
            self.assertIn("cancelled", cancel_receipt.output_bundle.text_blocks[0].text)

    def test_mission_orchestrator_appends_feedback_from_user_text(self) -> None:
        with test_workdir("mission_orchestrator_feedback_text") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            orchestrator = ButlerMissionOrchestrator()
            create_receipt = orchestrator.orchestrate(
                RuntimeRequest(
                    invocation=Invocation(
                        entrypoint="mission_ingress",
                        channel="feishu",
                        session_id="session_1",
                        actor_id="user_open_id",
                        user_text="放进编排：整理周报",
                    ),
                    metadata={"workspace": str(root)},
                )
            )
            mission_id = create_receipt.workflow_id

            feedback_receipt = orchestrator.orchestrate(
                RuntimeRequest(
                    invocation=Invocation(
                        entrypoint="mission_ingress",
                        channel="feishu",
                        session_id="session_1",
                        actor_id="user_open_id",
                        user_text=f"补充编排反馈 mission_id={mission_id} 请加上本周项目风险和 blocker。",
                    ),
                    metadata={"workspace": str(root)},
                )
            )

            self.assertEqual(feedback_receipt.workflow_id, mission_id)
            self.assertEqual(feedback_receipt.status, "pending")
            self.assertEqual(feedback_receipt.projection.status, "ready")
            service = build_orchestrator_service_for_workspace(str(root))
            event_types = {str(item.get("event_type") or "") for item in service.list_delivery_events(mission_id)}
            self.assertIn("user_feedback_appended", event_types)


if __name__ == "__main__":
    unittest.main()
