import unittest
from pathlib import Path
import sys


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from services.request_intake_service import RequestIntakeService  # noqa: E402


class RequestIntakeServiceTests(unittest.TestCase):
    def test_short_followup_is_marked_high_and_frontdesk_requires_continuation(self):
        service = RequestIntakeService()

        decision = service.classify("用PaddleOCR吧")
        block = service.build_frontdesk_prompt_block(decision)

        self.assertEqual(decision["followup_likelihood"], "high")
        self.assertEqual(decision["inferred_intent"], "adjust_previous_plan")
        self.assertIn("默认先按同一主线续接", block)
        self.assertIn("followup_likelihood=high", block)


if __name__ == "__main__":
    unittest.main()
