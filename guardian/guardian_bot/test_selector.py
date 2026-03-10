from __future__ import annotations

from guardian_bot.request_models import GuardianRequest


class GuardianTestSelector:
    def select_tests(self, request: GuardianRequest) -> list[str]:
        if request.requested_tests:
            return list(request.requested_tests)
        if request.requires_code_change:
            return ["targeted-regression"]
        return ["runtime-health-check"]
