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

from butler_main.chat import ChatMainlineService
from butler_main.butler_bot_code.tests._tmpdir import test_workdir


class ChatLongTaskFrontdoorRegressionTests(unittest.TestCase):
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

    def test_explicit_backend_enters_backend_entry(self) -> None:
        with test_workdir("chat_longtask_explicit_backend") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "后台任务：登录 179 服务器进入 Transfer_Recovery 目录，整理不少于100篇文献并写研究背景。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_explicit"),
            )

            self.assertEqual(result.runtime_request.decision.route, "chat")
            self.assertEqual(str((result.metadata or {}).get("negotiation_status") or ""), "backend_entry_required")
            self.assertTrue(bool((result.metadata or {}).get("chat_execution_blocked")))
            self.assertFalse(bool((result.metadata or {}).get("campaign_id")))

    def test_explicit_backend_can_start_exploratory_after_confirmation(self) -> None:
        with test_workdir("chat_longtask_explicit_backend_exploratory") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            service.handle_prompt(
                "后台任务：登录 179 服务器进入 Transfer_Recovery 目录，整理不少于100篇文献并写研究背景。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_explicit_exploratory"),
            )
            confirmed = service.handle_prompt(
                "确认启动",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_explicit_exploratory"),
            )

            self.assertEqual(confirmed.runtime_request.decision.route, "chat")
            self.assertEqual(str((confirmed.metadata or {}).get("negotiation_status") or ""), "started")
            self.assertEqual(str((confirmed.metadata or {}).get("startup_mode") or ""), "exploratory")
            self.assertTrue(str((confirmed.metadata or {}).get("campaign_id") or "").startswith("campaign_"))

    def test_direct_start_followup_starts_background_instead_of_falling_back_to_chat(self) -> None:
        with test_workdir("chat_longtask_direct_start_followup") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            metadata = self._invocation_meta(workspace=root, session_id="thread_direct_start")
            service.handle_prompt(
                "给你一个后台任务：登录 179 服务器进入 Transfer_Recovery 目录，系统梳理不少于100篇文献并写 KDD 风格研究背景与现状。",
                invocation_metadata=metadata,
            )

            started = service.handle_prompt(
                "直接启动，需要英文、截止今天12点，核心是轨迹+还原/重构/地图匹配+跨城迁移。",
                invocation_metadata=metadata,
            )

            self.assertEqual(str((started.metadata or {}).get("negotiation_status") or ""), "started")
            self.assertEqual(str((started.metadata or {}).get("startup_mode") or ""), "exploratory")
            self.assertTrue(str((started.metadata or {}).get("campaign_id") or "").startswith("campaign_"))

    def test_non_explicit_long_chain_enters_backend_entry_via_request_intake(self) -> None:
        with test_workdir("chat_longtask_non_explicit") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "登录 179 服务器进入 Transfer_Recovery 目录，系统梳理不少于100篇文献并写研究背景。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_non_explicit"),
            )

            self.assertEqual(result.runtime_request.decision.route, "chat")
            self.assertEqual(str((result.metadata or {}).get("negotiation_status") or ""), "backend_entry_required")
            self.assertTrue(bool((result.metadata or {}).get("chat_execution_blocked")))
            self.assertIn("进入后台任务入口态", result.text)
            self.assertFalse(bool((result.metadata or {}).get("campaign_id")))

    def test_explicit_no_backend_wording_does_not_enter_negotiation(self) -> None:
        with test_workdir("chat_longtask_no_backend") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "现在直接先给我一个论文背景提纲，不要放后台。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_no_backend"),
                talk_executor=lambda request: "直接执行",
            )

            self.assertEqual(result.runtime_request.decision.route, "chat")
            self.assertEqual(str((result.metadata or {}).get("negotiation_status") or ""), "")
            self.assertFalse(bool((result.metadata or {}).get("campaign_id")))

    def test_external_environment_task_does_not_auto_start(self) -> None:
        with test_workdir("chat_longtask_external_env") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "后台任务：ssh 到远程服务器，进入 data 目录并整理实验记录。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_external_env"),
            )

            self.assertEqual(str((result.metadata or {}).get("negotiation_status") or ""), "backend_entry_required")
            self.assertTrue(bool((result.metadata or {}).get("chat_execution_blocked")))
            self.assertFalse(bool((result.metadata or {}).get("campaign_id")))

    def test_minimal_correctness_requires_confirmation_to_start(self) -> None:
        with test_workdir("chat_longtask_min_correctness") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            service.handle_prompt(
                "后台任务：ssh 179服务器，进入 Transfer_Recovery 目录，整理不少于100篇文献并写研究背景。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_min_correct"),
            )

            verified = service.handle_prompt(
                "已确认 SSH 可连，Transfer_Recovery 目录存在，研究主题：Transfer Recovery for XXX，"
                "文献筛选边界已明确，输出为中文研究背景。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_min_correct"),
            )
            self.assertEqual(str((verified.metadata or {}).get("negotiation_status") or ""), "backend_entry_required")
            self.assertTrue(bool((verified.metadata or {}).get("minimal_correctness_ready")))

            confirmed = service.handle_prompt(
                "确认启动",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_min_correct"),
            )
            self.assertEqual(str((confirmed.metadata or {}).get("negotiation_status") or ""), "started")
            self.assertTrue(str((confirmed.metadata or {}).get("campaign_id") or "").startswith("campaign_"))

    def test_scope_change_requires_reconfirmation(self) -> None:
        with test_workdir("chat_longtask_scope_change") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            first = service.handle_prompt(
                "后台任务：整理调研结果，但要改阶段顺序并新增角色。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_scope_change"),
            )
            self.assertEqual(str((first.metadata or {}).get("negotiation_status") or ""), "confirmation_required")
            self.assertFalse(bool((first.metadata or {}).get("campaign_id")))

            second = service.handle_prompt(
                "再新增一个阶段并调整角色职责。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_scope_change"),
            )
            self.assertEqual(str((second.metadata or {}).get("negotiation_status") or ""), "confirmation_required")
            self.assertFalse(bool((second.metadata or {}).get("campaign_id")))

    def test_explicit_campaign_with_deferred_start_stays_in_collecting(self) -> None:
        with test_workdir("chat_longtask_defer_start") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            result = service.handle_prompt(
                "给我持续推进这个项目，先别启动，先说你的理解和验收。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_defer_start"),
            )

            self.assertEqual(result.runtime_request.decision.route, "chat")
            self.assertEqual(str((result.metadata or {}).get("negotiation_status") or ""), "collecting")
            self.assertFalse(bool((result.metadata or {}).get("campaign_id")))

    def test_followup_after_campaign_started_keeps_same_campaign(self) -> None:
        with test_workdir("chat_longtask_followup_started") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            service.handle_prompt(
                "后台任务：ssh 179服务器，进入 Transfer_Recovery 目录，整理不少于100篇文献并写研究背景。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_followup"),
            )
            service.handle_prompt(
                "已确认 SSH 可连，Transfer_Recovery 目录存在，研究主题：Transfer Recovery for XXX，"
                "文献筛选边界已明确，输出为中文研究背景。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_followup"),
            )
            started = service.handle_prompt(
                "确认启动",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_followup"),
            )
            campaign_id = str((started.metadata or {}).get("campaign_id") or "")
            self.assertTrue(campaign_id.startswith("campaign_"))

            followup = service.handle_prompt(
                "这个后台任务进展如何？",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_followup"),
            )
            self.assertEqual(str((followup.metadata or {}).get("frontdoor_action") or ""), "query_status")
            self.assertTrue(bool((followup.metadata or {}).get("task_query_hit")))
            self.assertEqual(str((followup.metadata or {}).get("task_query_kind") or ""), "campaign")
            self.assertEqual(str((followup.metadata or {}).get("campaign_id") or ""), campaign_id)
            self.assertIn("status:", followup.text)
            self.assertIn("execution_state:", followup.text)
            self.assertIn("closure_state:", followup.text)
            self.assertIn("bundle_root:", followup.text)
            self.assertNotIn("campaign started", followup.text.lower())

    def test_non_progress_followup_after_campaign_started_appends_feedback(self) -> None:
        with test_workdir("chat_longtask_followup_fallback") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            service = ChatMainlineService()
            service.handle_prompt(
                "后台任务：ssh 179服务器，进入 Transfer_Recovery 目录，整理不少于100篇文献并写研究背景。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_followup_fallback"),
            )
            service.handle_prompt(
                "已确认 SSH 可连，Transfer_Recovery 目录存在，研究主题：Transfer Recovery for XXX，"
                "文献筛选边界已明确，输出为中文研究背景。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_followup_fallback"),
            )
            service.handle_prompt(
                "确认启动",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_followup_fallback"),
            )

            followup = service.handle_prompt(
                "顺便把风险点也列一下。",
                invocation_metadata=self._invocation_meta(workspace=root, session_id="thread_followup_fallback"),
            )

            self.assertEqual(str((followup.metadata or {}).get("frontdoor_action") or ""), "append_feedback")
            self.assertTrue(bool((followup.metadata or {}).get("feedback_appended")))
            self.assertEqual(str((followup.metadata or {}).get("negotiation_status") or ""), "started")
            self.assertIn("campaign feedback appended", followup.output_bundle.summary)


if __name__ == "__main__":
    unittest.main()
