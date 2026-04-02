from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VERIFICATION_DECISIONS: tuple[str, ...] = (
    "pass",
    "refine",
    "pivot",
    "reject",
    "defer",
)


def normalize_verification_decision(value: str, *, default: str = "pass") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "pass").strip() or "pass"
    return normalized if normalized in VERIFICATION_DECISIONS else (str(default or "pass").strip() or "pass")


@dataclass(slots=True)
class VerificationReceipt:
    verified: bool = False
    decision: str = "pass"
    summary: str = ""
    checks: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    retryable: bool = False
    rollback_hint: str = ""
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.decision = normalize_verification_decision(self.decision)
