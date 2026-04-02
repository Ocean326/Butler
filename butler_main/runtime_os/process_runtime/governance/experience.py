from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass(slots=True)
class ExperienceRecord:
    experience_id: str = field(default_factory=lambda: _new_id("experience"))
    run_type: str = ""
    workflow: str = ""
    task_shape: str = ""
    failure_class: str = ""
    pattern: str = ""
    what_worked: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    recommended_path: list[str] = field(default_factory=list)
    confidence: float = 0.0
    applicable_scope: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(float(self.confidence or 0.0), 1.0))


__all__ = ["ExperienceRecord"]
