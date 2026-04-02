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

from agents_os.contracts import DeliverySession
from butler_main.chat import ChatMainlineService
from butler_main.chat.negotiation import (
    CampaignNegotiationDraft,
    CampaignNegotiationService,
    CampaignNegotiationStore,
)
from butler_main.butler_bot_code.tests._tmpdir import test_workdir
from butler_main.orchestrator import OrchestratorCampaignService
from butler_main.orchestrator.workspace import resolve_orchestrator_root


class ChatCampaignNegotiationTests(unittest.TestCase):
    def _invocation_meta(self, *, workspace: Path, session_id: str) -> dict:
        return {
            "channel": "feishu",
            "message_id": f"om_{session_id}",
            "session_id": session_id,
            "actor_id": "ou_123",
            "feishu.receive_id": "ou_123",
            "feishu.receive_id_type": "open_id",
            "workspace": str(workspace),
        }

    def test_campaign_negotiation_auto_starts_on_high_confidence_template(self) -> None:
        with test_workdir("chat_campaign_auto_start") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "我想长期持续推进项目A，进行多阶段迭代。材料: docs/plan.md",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_auto"),
            )

            self.assertIn("campaign started", result.output_bundle.summary.lower())
            campaign_id = str((result.metadata or {}).get("campaign_id") or "")
            self.assertTrue(campaign_id.startswith("campaign_"))
            self.assertEqual(result.output_bundle.metadata.get("composition_mode"), "template")
            self.assertFalse(bool(result.output_bundle.metadata.get("skeleton_changed")))
            template_id = str(result.output_bundle.metadata.get("template_id") or "")
            self.assertTrue(template_id.startswith("campaign."))

            status = OrchestratorCampaignService().get_campaign_status(str(root), campaign_id)
            contract = dict(status.get("metadata", {}).get("template_contract") or {})
            self.assertEqual(contract.get("template_origin"), template_id)
            self.assertEqual(contract.get("composition_mode"), "template")
            self.assertFalse(bool(contract.get("skeleton_changed")))
            self.assertEqual(contract.get("created_from"), "campaign_negotiation")
            self.assertEqual(contract.get("negotiation_session_id"), "thread_auto")
            self.assertEqual(status.get("materials"), ["docs/plan.md"])

    def test_campaign_negotiation_requires_confirmation_on_custom_skeleton(self) -> None:
        with test_workdir("chat_campaign_confirm") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            first = service.handle_prompt(
                "我要长期推进项目B，但要改阶段顺序并新增角色。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_custom"),
            )
            self.assertIn("confirmation", first.output_bundle.summary.lower())
            self.assertFalse(bool((first.metadata or {}).get("campaign_id")))
            draft_path = (
                Path(resolve_orchestrator_root(str(root)))
                / "negotiations"
                / "campaign"
                / "thread_custom.json"
            )
            self.assertTrue(draft_path.exists())

            service2 = ChatMainlineService()
            confirmed = service2.handle_prompt(
                "确认启动",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_custom"),
            )
            self.assertIn("campaign started", confirmed.output_bundle.summary.lower())
            campaign_id = str((confirmed.metadata or {}).get("campaign_id") or "")
            self.assertTrue(campaign_id.startswith("campaign_"))
            status = OrchestratorCampaignService().get_campaign_status(str(root), campaign_id)
            contract = dict(status.get("metadata", {}).get("template_contract") or {})
            self.assertEqual(contract.get("composition_mode"), "composition")
            self.assertTrue(bool(contract.get("skeleton_changed")))
            self.assertEqual(contract.get("negotiation_session_id"), "thread_custom")

    def test_campaign_negotiation_respects_explicit_template_choice(self) -> None:
        with test_workdir("chat_campaign_template_choice") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "使用模板 campaign.guarded_autonomy 启动一个长期campaign。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_template"),
            )

            self.assertIn("campaign started", result.output_bundle.summary.lower())
            template_id = str(result.output_bundle.metadata.get("template_id") or "")
            self.assertEqual(template_id, "campaign.guarded_autonomy")

    def test_campaign_negotiation_attempts_to_bootstrap_orchestrator_before_start(self) -> None:
        with test_workdir("chat_campaign_bootstrap") as root:
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

            class _ShouldNotCreateCampaign:
                def create_campaign(self, workspace, spec):
                    raise AssertionError("campaign should not be created when orchestrator bootstrap failed")

            bootstrap = _Bootstrap()
            negotiation = CampaignNegotiationService(
                orchestrator_bootstrap=bootstrap,
                campaign_service=_ShouldNotCreateCampaign(),
            )
            service = ChatMainlineService(
                campaign_negotiation=negotiation,
                orchestrator_bootstrap=bootstrap,
            )
            result = service.handle_prompt(
                "我想长期持续推进项目E，进行多阶段迭代。材料: docs/plan.md",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_bootstrap"),
            )

            self.assertEqual(bootstrap.calls, 1)
            self.assertIn("orchestrator offline", result.output_bundle.summary)
            self.assertIn("./tools/butler restart orchestrator", result.text)

    def test_explicit_backend_research_task_requires_discussion_before_start(self) -> None:
        with test_workdir("chat_campaign_discussion_first") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "给你一个后台任务：登录 179 服务器进入 Transfer_Recovery 目录，基于项目现有材料确认研究主题；随后系统梳理不少于 100 篇高相关文献，并写一版 KDD 风格研究背景与现状。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_discuss"),
            )

            self.assertIn("backend entry required", result.output_bundle.summary.lower())
            self.assertEqual(str((result.metadata or {}).get("negotiation_status") or ""), "backend_entry_required")
            self.assertTrue(bool((result.metadata or {}).get("chat_execution_blocked")))
            self.assertEqual(str((result.metadata or {}).get("task_mode") or ""), "background_entry")
            self.assertFalse(bool((result.metadata or {}).get("minimal_correctness_ready")))
            self.assertFalse(bool((result.metadata or {}).get("campaign_id")))

    def test_started_campaign_does_not_swallow_unrelated_plain_chat_as_feedback(self) -> None:
        with test_workdir("chat_campaign_started_plain_chat_escape") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            store = CampaignNegotiationStore()
            draft = CampaignNegotiationDraft(
                draft_id="draft_thread_started_escape",
                session_id="thread_started_escape",
                status="started",
                goal="旧后台任务",
                task_mode="background_entry",
                started_campaign_id="campaign_existing",
            )
            store.save(workspace=str(root), draft=draft)

            class _QueryService:
                def get_campaign_status(self, workspace, campaign_id):
                    raise AssertionError("unrelated plain chat should not query started campaign feedback flow")

                def append_user_feedback(self, workspace, mission_id, feedback):
                    raise AssertionError("unrelated plain chat should not append feedback")

            service = CampaignNegotiationService(store=store, query_service=_QueryService())
            result = service.handle(
                workspace=str(root),
                session_id="thread_started_escape",
                user_text="航天与二阶控制论内核：拆了十三个 Agent，把这个系统完整提取出来，形成脑暴。",
            )

            self.assertIsNone(result)

    def test_started_campaign_still_appends_constraint_followup_feedback(self) -> None:
        with test_workdir("chat_campaign_started_feedback_append") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            store = CampaignNegotiationStore()
            draft = CampaignNegotiationDraft(
                draft_id="draft_thread_started_feedback",
                session_id="thread_started_feedback",
                status="started",
                goal="旧后台任务",
                task_mode="background_entry",
                started_campaign_id="campaign_existing",
            )
            store.save(workspace=str(root), draft=draft)

            class _QueryService:
                def get_campaign_status(self, workspace, campaign_id):
                    return {"mission_id": "mission_existing"}

                def append_user_feedback(self, workspace, mission_id, feedback):
                    return {"event_id": "evt_feedback"}

            service = CampaignNegotiationService(store=store, query_service=_QueryService())
            result = service.handle(
                workspace=str(root),
                session_id="thread_started_feedback",
                user_text="另外也需要英文输出，截止今天12点。",
            )

            self.assertIsNotNone(result)
            self.assertEqual(str((result.metadata or {}).get("frontdoor_action") or ""), "append_feedback")
            self.assertEqual(str((result.metadata or {}).get("feedback_event_id") or ""), "evt_feedback")

    def test_confirmation_without_minimal_correctness_can_start_exploratory_background_task(self) -> None:
        with test_workdir("chat_campaign_needs_minimal_correctness") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            service.handle_prompt(
                "后台任务：ssh 179服务器，进入 Transfer_Recovery 目录，整理不少于100篇文献并写 KDD 风格研究背景与现状。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_gate"),
            )
            confirmed = service.handle_prompt(
                "确认启动",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_gate"),
            )

            self.assertEqual(str((confirmed.metadata or {}).get("negotiation_status") or ""), "started")
            self.assertEqual(str((confirmed.metadata or {}).get("startup_mode") or ""), "exploratory")
            self.assertFalse(bool((confirmed.metadata or {}).get("minimal_correctness_ready")))
            self.assertTrue(str((confirmed.metadata or {}).get("campaign_id") or "").startswith("campaign_"))

    def test_background_task_can_start_after_minimal_correctness_and_confirmation(self) -> None:
        with test_workdir("chat_campaign_background_after_verification") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            first = service.handle_prompt(
                "后台任务：ssh 179服务器，进入 Transfer_Recovery 目录，整理不少于100篇文献并写 KDD 风格研究背景与现状。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_ready"),
            )
            self.assertEqual(str((first.metadata or {}).get("negotiation_status") or ""), "backend_entry_required")

            verified = service.handle_prompt(
                "已确认 SSH 可连，Transfer_Recovery 目录存在可访问，研究主题：Transfer Recovery for XXX，文献筛选边界已明确，输出为中文 KDD 风格研究背景与现状。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_ready"),
            )
            self.assertEqual(str((verified.metadata or {}).get("negotiation_status") or ""), "backend_entry_required")
            self.assertTrue(bool((verified.metadata or {}).get("minimal_correctness_ready")))

            started = service.handle_prompt(
                "确认启动",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_ready"),
            )
            self.assertIn("campaign started", started.output_bundle.summary.lower())
            self.assertEqual(str((started.metadata or {}).get("negotiation_status") or ""), "started")
            self.assertTrue(str((started.metadata or {}).get("campaign_id") or "").startswith("campaign_"))

    def test_slash_plan_returns_plan_only_summary_without_campaign(self) -> None:
        with test_workdir("chat_campaign_plan_mode") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "/plan 梳理 Butler 下一步交付计划。材料: docs/plan.md",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_plan"),
            )

            self.assertEqual(str((result.metadata or {}).get("frontdoor_action") or ""), "plan_only")
            self.assertEqual(str((result.metadata or {}).get("negotiation_status") or ""), "planned")
            self.assertFalse(bool((result.metadata or {}).get("campaign_id")))
            planning_contract = dict((result.metadata or {}).get("planning_contract") or {})
            self.assertTrue(bool(planning_contract.get("plan_only")))
            self.assertEqual(planning_contract.get("mode_id"), "plan")

    def test_slash_research_uses_research_template_and_planning_contract(self) -> None:
        with test_workdir("chat_campaign_research_mode") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "/research 系统梳理现有资料并形成研究结论。材料: docs/research.md",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_research"),
            )

            self.assertIn("campaign started", result.output_bundle.summary.lower())
            campaign_id = str((result.metadata or {}).get("campaign_id") or "")
            status = OrchestratorCampaignService().get_campaign_status(str(root), campaign_id)
            planning_contract = dict(status.get("metadata", {}).get("planning_contract") or {})
            self.assertEqual(planning_contract.get("mode_id"), "research")
            self.assertEqual(status.get("metadata", {}).get("template_contract", {}).get("template_origin"), "campaign.research_then_implement")
            self.assertEqual(status.get("runtime_mode"), "codex")
            self.assertTrue(bool(status.get("metadata", {}).get("strict_acceptance_required")))
            self.assertIn("background_tasks", str(status.get("bundle_root") or ""))

    def test_governance_slash_command_updates_current_campaign_contract(self) -> None:
        with test_workdir("chat_campaign_govern_mode") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            started = service.handle_prompt(
                "我想长期持续推进项目A，进行多阶段迭代。材料: docs/plan.md",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_govern"),
            )
            campaign_id = str((started.metadata or {}).get("campaign_id") or "")
            self.assertTrue(campaign_id.startswith("campaign_"))

            govern = service.handle_prompt(
                "/govern set_risk_level high",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_govern"),
            )
            self.assertEqual(str((govern.metadata or {}).get("frontdoor_action") or ""), "govern")
            self.assertEqual(
                str((((govern.metadata or {}).get("governance_summary") or {}).get("risk_level") or "")),
                "high",
            )

            status = OrchestratorCampaignService().get_campaign_status(str(root), campaign_id)
            self.assertEqual(
                str((status.get("metadata", {}).get("governance_contract") or {}).get("risk_level") or ""),
                "high",
            )

    def test_long_goal_with_confirm_word_does_not_count_as_start_confirmation(self) -> None:
        negotiation = CampaignNegotiationService()
        self.assertFalse(
            negotiation._is_confirmation(
                "给你一次大任务：先确认研究主题，再系统梳理文献并写论文背景。"
            )
        )
        self.assertTrue(negotiation._is_confirmation("确认启动"))
        self.assertFalse(
            negotiation._is_confirmation("直接启动，需要英文、截止今天12点，核心是轨迹+还原/重构/地图匹配+跨城迁移")
        )
        self.assertFalse(negotiation._is_confirmation("开始整理不少于100篇文献并写研究背景。"))

    def test_general_large_research_task_without_backend_wording_does_not_open_negotiation(self) -> None:
        negotiation = CampaignNegotiationService()

        self.assertFalse(
            negotiation._should_open_negotiation(
                "登录 179 服务器进入 Transfer_Recovery 目录，然后系统梳理不少于 100 篇文献并写 KDD 风格背景。"
            )
        )

    def test_campaign_negotiation_forwards_feedback_contract_from_delivery_session(self) -> None:
        class _RecordingCampaignService:
            def __init__(self) -> None:
                self.last_spec = None

            def create_campaign(self, workspace, spec):
                self.last_spec = dict(spec)
                return {
                    "campaign_id": "campaign_feedback",
                    "feedback_doc": {
                        "document_id": "doxc_feedback",
                        "url": "https://feishu.cn/docx/doxc_feedback",
                        "title": "Task - feedback",
                    },
                }

        with test_workdir("chat_campaign_feedback_contract") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            recording = _RecordingCampaignService()
            negotiation = CampaignNegotiationService(campaign_service=recording)

            result = negotiation.handle(
                workspace=str(root),
                session_id="thread_feedback",
                user_text="我想长期持续推进项目F，进行多阶段迭代。",
                delivery_session=DeliverySession(
                    platform="feishu",
                    mode="reply",
                    target="ou_feedback",
                    target_type="open_id",
                    thread_id="feishu:thread_feedback",
                    metadata={"feishu.message_id": "om_feedback"},
                ),
            )

            self.assertIsNotNone(result)
            assert result is not None
            feedback_contract = dict((recording.last_spec or {}).get("metadata", {}).get("feedback_contract") or {})
            self.assertEqual(feedback_contract.get("platform"), "feishu")
            self.assertEqual(feedback_contract.get("target"), "ou_feedback")
            self.assertTrue(bool(feedback_contract.get("doc_enabled")))
            self.assertEqual(len(result.output_bundle.doc_links), 1)
            self.assertEqual(result.output_bundle.doc_links[0].url, "https://feishu.cn/docx/doxc_feedback")


if __name__ == "__main__":
    unittest.main()
