from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


RUN_STATUSES: tuple[str, ...] = (
    "pending",
    "running",
    "blocked",
    "failed",
    "completed",
    "cancelled",
    "stale",
)

FAILURE_CLASSES: tuple[str, ...] = (
    "policy_blocked",
    "context_missing",
    "worker_error",
    "tool_error",
    "acceptance_failed",
    "stale_loop",
    "invalid_plan",
    "degraded_status_only",
)

PROCESS_ROLES: tuple[str, ...] = (
    "planner",
    "executor",
    "test",
    "acceptance",
    "approval",
    "manager",
)

STEP_KINDS: tuple[str, ...] = (
    "prepare",
    "plan",
    "dispatch",
    "verify",
    "approve",
    "join",
    "finalize",
    "promote",
    "recover",
)

EDGE_KINDS: tuple[str, ...] = (
    "next",
    "on_success",
    "on_failure",
    "resume_from",
)


def normalize_run_status(value: str, *, default: str = "pending") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "pending").strip() or "pending"
    return normalized if normalized in RUN_STATUSES else (str(default or "pending").strip() or "pending")


def normalize_failure_class(value: str, *, default: str = "") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "").strip()
    return normalized if normalized in FAILURE_CLASSES else str(default or "").strip()


def normalize_process_role(value: str, *, default: str = "executor") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "executor").strip() or "executor"
    return normalized if normalized in PROCESS_ROLES else (str(default or "executor").strip() or "executor")


def normalize_step_kind(value: str, *, default: str = "dispatch") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "dispatch").strip() or "dispatch"
    return normalized if normalized in STEP_KINDS else (str(default or "dispatch").strip() or "dispatch")


def normalize_edge_kind(value: str, *, default: str = "next") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "next").strip() or "next"
    return normalized if normalized in EDGE_KINDS else (str(default or "next").strip() or "next")


@dataclass(slots=True)
class Session:
    session_id: str = field(default_factory=lambda: _new_id("session"))
    topic: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)


@dataclass(slots=True)
class RunInput:
    payload: Any = None
    worker: str = ""
    workflow: str = "single_worker"
    session_id: str = ""
    task_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Run:
    input: RunInput
    run_id: str = field(default_factory=lambda: _new_id("run"))
    status: str = "pending"
    created_at: str = field(default_factory=_utc_now_iso)
    started_at: str = ""
    finished_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.status = normalize_run_status(self.status)


@dataclass(slots=True)
class Artifact:
    kind: str
    content: Any = None
    artifact_id: str = field(default_factory=lambda: _new_id("artifact"))
    uri: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TraceEvent:
    run_id: str
    kind: str
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: _new_id("trace"))
    created_at: str = field(default_factory=_utc_now_iso)


@dataclass(slots=True)
class GuardrailDecision:
    allowed: bool
    reason: str = ""
    code: str = "allow"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkerRequest:
    run: Run
    payload: Any = None
    context: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)


@dataclass(slots=True)
class AcceptanceReceipt:
    goal_achieved: bool = False
    summary: str = ""
    evidence: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    next_action: str = ""
    failure_class: str = ""

    def __post_init__(self) -> None:
        self.failure_class = normalize_failure_class(self.failure_class)


@dataclass(slots=True)
class WorkerResult:
    status: str = "completed"
    output: Any = None
    message: str = ""
    artifacts: list[Artifact] = field(default_factory=list)
    context_updates: dict[str, Any] = field(default_factory=dict)
    acceptance: AcceptanceReceipt | None = None
    failure_class: str = ""

    def __post_init__(self) -> None:
        self.status = normalize_run_status(self.status, default="completed")
        self.failure_class = normalize_failure_class(self.failure_class)


@dataclass(slots=True)
class RunResult:
    run_id: str
    status: str
    output: Any = None
    error: str = ""
    artifacts: list[Artifact] = field(default_factory=list)
    trace_count: int = 0
    acceptance: AcceptanceReceipt | None = None
    failure_class: str = ""

    def __post_init__(self) -> None:
        self.status = normalize_run_status(self.status, default="failed")
        self.failure_class = normalize_failure_class(self.failure_class)
