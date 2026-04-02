import unittest
from pathlib import Path
import sys


from butler_main.agents_os.runtime.request_intake import RequestIntakeService  # noqa: E402


class RequestIntakeServiceTests(unittest.TestCase):
    def test_short_followup_is_marked_high_and_frontdesk_requires_continuation(self):
        service = RequestIntakeService()

        decision = service.classify("用PaddleOCR吧")
        block = service.build_frontdesk_prompt_block(decision)

        self.assertEqual(decision["followup_likelihood"], "high")
        self.assertEqual(decision["inferred_intent"], "adjust_previous_plan")
        self.assertIn("默认先按同一主线续接", block)
        self.assertIn("followup_likelihood=high", block)

    def test_explicit_backend_request_prefers_backend_entry_discussion(self):
        service = RequestIntakeService()

        decision = service.classify("给你一个后台任务：持续推进这个项目，分阶段完成。")
        block = service.build_frontdesk_prompt_block(decision)

        self.assertEqual(decision["mode"], "async_program")
        self.assertEqual(decision["frontdoor_action"], "discuss_backend_entry")
        self.assertTrue(decision["explicit_backend_request"])
        self.assertIn("explicit_backend_request=true", block)
        self.assertIn("后台启动前讨论", block)

    def test_large_external_research_task_discusses_mode_before_execution(self):
        service = RequestIntakeService()

        decision = service.classify("ssh 到服务器后系统梳理至少 100 篇文献，形成分类矩阵并写论文现状。")
        block = service.build_frontdesk_prompt_block(decision)

        self.assertEqual(decision["mode"], "sync_then_async")
        self.assertEqual(decision["frontdoor_action"], "choose_execution_mode")
        self.assertTrue(decision["should_discuss_mode_first"])
        self.assertFalse(decision["explicit_backend_request"])
        self.assertIn("should_discuss_mode_first=true", block)
        self.assertIn("先自然地和用户协商模式", block)

    def test_forced_frontdoor_modes_override_heuristic_modes(self):
        service = RequestIntakeService()

        status_decision = service.classify("campaign_123", forced_frontdoor_mode="status")
        self.assertEqual(status_decision["mode"], "status")
        self.assertEqual(status_decision["frontdoor_action"], "query_status")
        self.assertTrue(status_decision["direct_execution_ok"])

        govern_decision = service.classify("set_risk_level high", forced_frontdoor_mode="govern")
        self.assertEqual(govern_decision["mode"], "govern")
        self.assertEqual(govern_decision["frontdoor_action"], "govern")

        plan_decision = service.classify("梳理执行计划", forced_frontdoor_mode="plan")
        self.assertEqual(plan_decision["mode"], "plan")
        self.assertEqual(plan_decision["frontdoor_action"], "plan_only")


if __name__ == "__main__":
    unittest.main()
