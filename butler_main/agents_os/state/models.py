from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RuntimeStatusSnapshot:
    config_state: str = "unknown"
    process_state: str = "unknown"
    watchdog_state: str = "unknown"
    run_state: str = "unknown"
    progress_state: str = "unknown"
    pid: int = 0
    run_id: str = ""
    phase: str = ""
    updated_at: str = ""
    note: str = ""


@dataclass(slots=True)
class RunTraceSummary:
    run_id: str
    selected_task_ids: list[str] = field(default_factory=list)
    rejected_task_ids: list[str] = field(default_factory=list)
    fallback_count: int = 0
    retry_count: int = 0
    timeout_count: int = 0
    degrade_count: int = 0
    progress_counter: int = 0


@dataclass(slots=True)
class PromotionDecision:
    decision: str
    reason: str
    normalized_item: dict = field(default_factory=dict)
