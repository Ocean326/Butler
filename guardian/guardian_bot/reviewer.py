from __future__ import annotations

from pathlib import Path

from guardian_bot.request_models import GuardianRequest, GuardianReviewResult


class GuardianReviewer:
    VALID_SOURCES = {"heartbeat", "butler", "guardian", "user"}
    VALID_TYPES = {"record-only", "auto-fix", "code-fix", "restart", "architecture"}
    VALID_RISK_LEVELS = {"low", "medium", "high"}

    def __init__(self, soul_path: Path | None = None) -> None:
        self._soul_path = Path(soul_path) if soul_path else Path(__file__).resolve().parent.parent / "SOUL.md"
        self._cached_motto: str | None = None

    def _soul_motto(self) -> str:
        if self._cached_motto is not None:
            return self._cached_motto
        try:
            text = self._soul_path.read_text(encoding="utf-8")
        except OSError:
            self._cached_motto = ""
            return self._cached_motto
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith(">"):
                self._cached_motto = line.lstrip(">").strip()
                return self._cached_motto
        self._cached_motto = ""
        return self._cached_motto

    def _baseline_note(self) -> str:
        motto = self._soul_motto()
        if motto:
            return f"按 Guardian 灵魂审阅：{motto}"
        return "按 Guardian 灵魂审阅：先看安全、可追溯、可回滚，再决定是否放行。"

    @staticmethod
    def _guardrail(note: str) -> str:
        return f"守门原则：{note}"

    def review(self, request: GuardianRequest) -> GuardianReviewResult:
        notes: list[str] = [self._baseline_note()]

        if request.source not in self.VALID_SOURCES:
            return GuardianReviewResult("reject", notes + [f"invalid source: {request.source or '(empty)'}"])
        if request.request_type not in self.VALID_TYPES:
            return GuardianReviewResult("reject", notes + [f"invalid request_type: {request.request_type or '(empty)'}"])
        if request.risk_level not in self.VALID_RISK_LEVELS:
            return GuardianReviewResult("reject", notes + [f"invalid risk_level: {request.risk_level or '(empty)'}"])
        if not request.title or not request.reason:
            return GuardianReviewResult("need-info", notes + [self._guardrail("缺少 title 或 reason，先补全再放行")])

        if request.request_type == "record-only":
            notes.append(self._guardrail("record-only 仅备案，可直接放行"))
            return GuardianReviewResult("approve", notes)

        if request.requires_code_change and not request.patch_plan:
            notes.append(self._guardrail("改代码前必须先给 patch_plan"))
        if request.request_type in {"code-fix", "restart", "architecture"} and not request.verification:
            notes.append(self._guardrail("缺少 verification，无法证明改动有效"))
        if request.risk_level == "high" and not request.rollback:
            notes.append(self._guardrail("高风险请求必须先给 rollback"))

        if len(notes) > 1:
            return GuardianReviewResult("need-info", notes)

        notes.append(self._guardrail("请求满足当前守门基线，允许放行"))
        return GuardianReviewResult("approve", notes)
