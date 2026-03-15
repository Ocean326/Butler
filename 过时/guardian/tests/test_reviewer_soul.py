import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from guardian_bot.request_models import GuardianRequest
from guardian_bot.reviewer import GuardianReviewer


class GuardianReviewerSoulTests(unittest.TestCase):
    def test_review_uses_soul_motto_in_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            soul_path = Path(tmp) / "SOUL.md"
            soul_path.write_text("> 我不做聪明的事，只做可靠的事。\n", encoding="utf-8")
            reviewer = GuardianReviewer(soul_path=soul_path)
            request = GuardianRequest(
                request_id="req-1",
                source="user",
                request_type="record-only",
                title="备案一次检查",
                reason="只需要入账",
                risk_level="low",
            )

            review = reviewer.review(request)

            self.assertEqual(review.decision, "approve")
            self.assertTrue(any("我不做聪明的事，只做可靠的事。" in note for note in review.notes))
            self.assertTrue(any("record-only" in note for note in review.notes))


if __name__ == "__main__":
    unittest.main()