from __future__ import annotations

from pathlib import Path

from guardian_bot.executor import GuardianExecutor
from guardian_bot.ledger_store import GuardianLedgerStore
from guardian_bot.request_inbox import GuardianRequestInbox
from guardian_bot.reviewer import GuardianReviewer
from guardian_bot.test_selector import GuardianTestSelector


class GuardianRuntime:
    def __init__(
        self,
        inbox_dir: Path,
        ledger_dir: Path,
        workspace_root: Path | None = None,
    ) -> None:
        self.inbox = GuardianRequestInbox(inbox_dir)
        self.ledger = GuardianLedgerStore(ledger_dir)
        self.reviewer = GuardianReviewer(Path(__file__).resolve().parent.parent / "SOUL.md")
        self.workspace_root = workspace_root or inbox_dir
        self.executor = GuardianExecutor(
            ledger=self.ledger,
            workspace_root=self.workspace_root,
            test_selector=GuardianTestSelector(),
        )

    def process_pending_requests(self) -> dict:
        pending_files = self.inbox.list_pending_files()
        summary = {"pending": len(pending_files), "approve": 0, "reject": 0, "need-info": 0, "executed": 0}
        for path in pending_files:
            request = self.inbox.load_request(path)
            review = self.reviewer.review(request)
            request.review_status = review.decision
            request.review_notes = list(review.notes)
            self.ledger.write_review_event(request.request_id, review.decision, review.notes, request.to_dict())
            self.inbox.persist_reviewed_request(path, request, review.decision)
            summary[review.decision] += 1
            if review.decision == "approve" and self.executor.should_execute(request):
                self.executor.execute(request)
                summary["executed"] += 1
        return summary
