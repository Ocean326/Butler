from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RECOVERY_ACTIONS: tuple[str, ...] = (
    "continue",
    "retry_step",
    "retry_run",
    "degrade_status_only",
    "pause_waiting_input",
    "escalate_to_human",
    "abort",
)


def normalize_recovery_action(value: str, *, default: str = "continue") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "continue").strip() or "continue"
    return normalized if normalized in RECOVERY_ACTIONS else (str(default or "continue").strip() or "continue")


@dataclass(slots=True)
class RecoveryDirective:
    action: str = "continue"
    reason: str = ""
    retry_budget: int = 0
    backoff_seconds: int = 0
    next_wake_at: str = ""
    target_step_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.action = normalize_recovery_action(self.action)
        self.retry_budget = max(0, int(self.retry_budget or 0))
        self.backoff_seconds = max(0, int(self.backoff_seconds or 0))


__all__ = [
    "RECOVERY_ACTIONS",
    "RecoveryDirective",
    "normalize_recovery_action",
]
