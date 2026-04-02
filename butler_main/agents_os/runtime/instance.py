from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


INSTANCE_STATUSES: tuple[str, ...] = (
    "idle",
    "running",
    "blocked",
    "waiting_input",
    "failed",
    "retired",
)


def normalize_instance_status(value: str, *, default: str = "idle") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return str(default or "idle").strip() or "idle"
    return normalized if normalized in INSTANCE_STATUSES else (str(default or "idle").strip() or "idle")


def build_instance_roots(instance_root: str | Path) -> dict[str, str]:
    root = Path(instance_root).resolve()
    return {
        "instance_root": str(root),
        "session_root": str(root / "session"),
        "workflow_root": str(root / "workflow"),
        "workflow_checkpoint_root": str(root / "workflow" / "checkpoints"),
        "context_root": str(root / "context"),
        "trace_root": str(root / "traces"),
        "artifact_root": str(root / "artifacts"),
        "handoff_root": str(root / "artifacts" / "handoff"),
        "draft_root": str(root / "artifacts" / "drafts"),
        "publish_root": str(root / "artifacts" / "published"),
        "approval_root": str(root / "approvals"),
        "recovery_root": str(root / "recovery"),
        "workspace_root": str(root / "workspace"),
        "inbox_root": str(root / "inbox"),
        "outbox_root": str(root / "outbox"),
    }


@dataclass(slots=True)
class AgentRuntimeInstance:
    instance_id: str = field(default_factory=lambda: _new_id("instance"))
    agent_id: str = ""
    agent_kind: str = "executor"
    manager_id: str = ""
    owner_domain: str = ""
    status: str = "idle"
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    prompt_profile_id: str = ""
    memory_profile_id: str = ""
    governance_profile_id: str = ""
    handoff_profile_id: str = ""
    tool_policy_profile_id: str = ""
    runtime_profile: dict[str, Any] = field(default_factory=dict)
    model_preferences: dict[str, Any] = field(default_factory=dict)

    session_id: str = field(default_factory=lambda: _new_id("session"))
    parent_session_id: str = ""
    active_run_id: str = ""
    active_workflow_id: str = ""
    current_step_id: str = ""
    conversation_cursor: str = "0"
    last_checkpoint_id: str = ""
    last_workflow_checkpoint_id: str = ""
    resume_token: str = ""
    current_goal: str = ""
    current_handoff_id: str = ""
    latest_decision: str = ""

    recent_context_refs: list[str] = field(default_factory=list)
    memory_refs: list[str] = field(default_factory=list)
    overlay_refs: list[str] = field(default_factory=list)
    frozen_scope: list[str] = field(default_factory=list)
    working_summary: str = ""
    context_budget: dict[str, Any] = field(default_factory=dict)

    approval_mode: str = "human_gate"
    risk_level: str = "medium"
    permission_set: dict[str, Any] = field(default_factory=dict)
    trust_level: str = "local"
    upgrade_policy: dict[str, Any] = field(default_factory=dict)
    verification_required: bool = True
    maker_checker_required: bool = False

    roots: dict[str, str] = field(default_factory=dict)
    last_artifact_ids: list[str] = field(default_factory=list)
    last_handoff_receipt_id: str = ""

    trace_path: str = ""
    event_stream_path: str = ""
    metrics_path: str = ""
    last_activity_at: str = ""
    last_error: str = ""
    health_state: str = "healthy"

    recovery_policy_id: str = ""
    retry_budget: int = 0
    backoff_policy: dict[str, Any] = field(default_factory=dict)
    stale_after_seconds: int = 0
    degrade_strategy: str = ""
    replayable: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.status = normalize_instance_status(self.status)
        self.retry_budget = max(0, int(self.retry_budget or 0))
        self.stale_after_seconds = max(0, int(self.stale_after_seconds or 0))
        if not self.roots:
            self.roots = {}

    def touch(self, *, status: str | None = None) -> None:
        if status is not None:
            self.status = normalize_instance_status(status, default=self.status)
        self.updated_at = _utc_now_iso()

    def ensure_roots(self, instance_root: str | Path) -> None:
        defaults = build_instance_roots(instance_root)
        merged = dict(defaults)
        merged.update({str(key): str(value) for key, value in (self.roots or {}).items() if str(key).strip() and str(value).strip()})
        self.roots = merged
        self.trace_path = self.trace_path or str(Path(merged["trace_root"]) / "latest_trace.json")
        self.event_stream_path = self.event_stream_path or str(Path(merged["trace_root"]) / "events.jsonl")
        self.metrics_path = self.metrics_path or str(Path(merged["trace_root"]) / "metrics.json")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def profile_snapshot(self) -> dict[str, Any]:
        return {
            "prompt_profile_id": self.prompt_profile_id,
            "memory_profile_id": self.memory_profile_id,
            "governance_profile_id": self.governance_profile_id,
            "handoff_profile_id": self.handoff_profile_id,
            "tool_policy_profile_id": self.tool_policy_profile_id,
            "runtime_profile": dict(self.runtime_profile or {}),
            "model_preferences": dict(self.model_preferences or {}),
            "approval_mode": self.approval_mode,
            "risk_level": self.risk_level,
            "permission_set": dict(self.permission_set or {}),
            "trust_level": self.trust_level,
            "upgrade_policy": dict(self.upgrade_policy or {}),
            "verification_required": bool(self.verification_required),
            "maker_checker_required": bool(self.maker_checker_required),
            "recovery_policy_id": self.recovery_policy_id,
            "retry_budget": int(self.retry_budget or 0),
            "backoff_policy": dict(self.backoff_policy or {}),
            "stale_after_seconds": int(self.stale_after_seconds or 0),
            "degrade_strategy": self.degrade_strategy,
            "replayable": bool(self.replayable),
        }

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "active_run_id": self.active_run_id,
            "current_goal": self.current_goal,
            "current_handoff_id": self.current_handoff_id,
            "last_checkpoint_id": self.last_checkpoint_id,
            "last_activity_at": self.last_activity_at,
            "last_error": self.last_error,
            "health_state": self.health_state,
            "updated_at": self.updated_at,
        }

    def session_snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "parent_session_id": self.parent_session_id,
            "active_run_id": self.active_run_id,
            "active_workflow_id": self.active_workflow_id,
            "current_step_id": self.current_step_id,
            "conversation_cursor": self.conversation_cursor,
            "last_checkpoint_id": self.last_checkpoint_id,
            "last_workflow_checkpoint_id": self.last_workflow_checkpoint_id,
            "resume_token": self.resume_token,
            "current_goal": self.current_goal,
            "current_handoff_id": self.current_handoff_id,
            "latest_decision": self.latest_decision,
            "updated_at": self.updated_at,
        }

    def context_snapshot(self) -> dict[str, Any]:
        return {
            "recent_context_refs": list(self.recent_context_refs or []),
            "memory_refs": list(self.memory_refs or []),
            "overlay_refs": list(self.overlay_refs or []),
            "frozen_scope": list(self.frozen_scope or []),
            "working_summary": self.working_summary,
            "context_budget": dict(self.context_budget or {}),
        }

    def workflow_snapshot(self) -> dict[str, Any]:
        return {
            "active_workflow_id": self.active_workflow_id,
            "current_step_id": self.current_step_id,
            "current_handoff_id": self.current_handoff_id,
            "latest_decision": self.latest_decision,
            "last_workflow_checkpoint_id": self.last_workflow_checkpoint_id,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "AgentRuntimeInstance":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))
