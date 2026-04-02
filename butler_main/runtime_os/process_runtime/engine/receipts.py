from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping
from uuid import uuid4

from butler_main.runtime_os.agent_runtime import (
    DeliveryRequest,
    DeliveryResult,
    ModelInput,
    OutputBundle,
    RouteProjection,
    WorkflowProjection,
)


_RUN_STATUSES: tuple[str, ...] = (
    "pending",
    "running",
    "blocked",
    "failed",
    "completed",
    "cancelled",
    "stale",
)

RUNTIME_VERDICT_STATUSES: tuple[str, ...] = (
    "pending",
    "running",
    "blocked",
    "failed",
    "completed",
    "cancelled",
    "stale",
    "awaiting_approval",
    "awaiting_verification",
    "awaiting_decision",
    "repair_scheduled",
    "resumable",
)

TERMINAL_RUNTIME_VERDICT_STATUSES: tuple[str, ...] = (
    "failed",
    "completed",
    "cancelled",
    "stale",
)

BRANCH_WRITEBACK_STATUSES: tuple[str, ...] = (
    "queued",
    "leased",
    "running",
    "succeeded",
    "failed",
    "timed_out",
    "cancelled",
)

NODE_WRITEBACK_STATUSES: tuple[str, ...] = (
    "pending",
    "ready",
    "dispatching",
    "running",
    "partial_ready",
    "awaiting_judge",
    "repairing",
    "blocked",
    "done",
    "failed",
    "skipped",
)

MISSION_WRITEBACK_STATUSES: tuple[str, ...] = (
    "draft",
    "ready",
    "running",
    "blocked",
    "awaiting_decision",
    "completed",
    "failed",
    "parked",
    "cancelled",
)

WORKFLOW_SESSION_WRITEBACK_STATUSES: tuple[str, ...] = (
    "pending",
    "active",
    "running",
    "verifying",
    "awaiting_approval",
    "awaiting_decision",
    "repairing",
    "completed",
    "failed",
    "stopped",
    "cancelled",
)


def _new_receipt_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _normalize_status(value: str, *, allowed: tuple[str, ...], default: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return default
    return normalized if normalized in allowed else default


def normalize_runtime_verdict_status(value: str, *, default: str = "pending") -> str:
    return _normalize_status(value, allowed=RUNTIME_VERDICT_STATUSES, default=str(default or "pending").strip() or "pending")


def normalize_branch_writeback_status(value: str, *, default: str = "queued") -> str:
    return _normalize_status(value, allowed=BRANCH_WRITEBACK_STATUSES, default=str(default or "queued").strip() or "queued")


def normalize_node_writeback_status(value: str, *, default: str = "pending") -> str:
    return _normalize_status(value, allowed=NODE_WRITEBACK_STATUSES, default=str(default or "pending").strip() or "pending")


def normalize_mission_writeback_status(value: str, *, default: str = "draft") -> str:
    return _normalize_status(value, allowed=MISSION_WRITEBACK_STATUSES, default=str(default or "draft").strip() or "draft")


def normalize_workflow_session_writeback_status(value: str, *, default: str = "pending") -> str:
    return _normalize_status(
        value,
        allowed=WORKFLOW_SESSION_WRITEBACK_STATUSES,
        default=str(default or "pending").strip() or "pending",
    )


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    execution_id: str = field(default_factory=lambda: _new_receipt_id("execution"))
    invocation_id: str = ""
    workflow_id: str = ""
    route: RouteProjection | None = None
    projection: WorkflowProjection | None = None
    agent_id: str = ""
    status: str = "pending"
    summary: str = ""
    model_input: ModelInput | None = None
    output_bundle: OutputBundle | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _normalize_status(self.status, allowed=_RUN_STATUSES, default="pending"))
        object.__setattr__(self, "summary", str(self.summary or "").strip())
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class WorkflowReceipt:
    receipt_id: str = field(default_factory=lambda: _new_receipt_id("workflow"))
    invocation_id: str = ""
    workflow_id: str = ""
    workflow_kind: str = ""
    status: str = "pending"
    route: RouteProjection | None = None
    projection: WorkflowProjection | None = None
    execution: ExecutionReceipt | None = None
    output_bundle: OutputBundle | None = None
    delivery_request: DeliveryRequest | None = None
    delivery_result: DeliveryResult | None = None
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _normalize_status(self.status, allowed=_RUN_STATUSES, default="pending"))
        object.__setattr__(self, "workflow_kind", str(self.workflow_kind or "").strip())
        object.__setattr__(self, "summary", str(self.summary or "").strip())
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def bundle(self) -> OutputBundle | None:
        if self.output_bundle is not None:
            return self.output_bundle
        if self.execution is not None:
            return self.execution.output_bundle
        return None


@dataclass(frozen=True, slots=True)
class RuntimeVerdict:
    status: str = "pending"
    terminal: bool = False
    result_ok: bool | None = None
    result_ref: str = ""
    result_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_status = normalize_runtime_verdict_status(self.status)
        object.__setattr__(self, "status", normalized_status)
        object.__setattr__(self, "terminal", bool(self.terminal))
        if self.result_ok is not None:
            object.__setattr__(self, "result_ok", bool(self.result_ok))
        object.__setattr__(self, "result_ref", str(self.result_ref or "").strip())
        object.__setattr__(self, "result_payload", dict(self.result_payload or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def ok(self) -> bool:
        if self.result_ok is not None:
            return bool(self.result_ok)
        return self.status == "completed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "terminal": self.terminal,
            "result_ok": self.result_ok,
            "result_ref": self.result_ref,
            "result_payload": dict(self.result_payload or {}),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "RuntimeVerdict":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(
            status=str(payload.get("status") or "pending").strip() or "pending",
            terminal=bool(payload.get("terminal")),
            result_ok=payload.get("result_ok") if payload.get("result_ok") is None else bool(payload.get("result_ok")),
            result_ref=str(payload.get("result_ref") or "").strip(),
            result_payload=dict(payload.get("result_payload") or {}),
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_legacy(
        cls,
        *,
        ok: bool,
        result_ref: str = "",
        result_payload: Mapping[str, Any] | None = None,
        status: str = "",
        terminal: bool | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "RuntimeVerdict":
        normalized_status = normalize_runtime_verdict_status(
            status or ("completed" if ok else "failed"),
            default="completed" if ok else "failed",
        )
        resolved_terminal = bool(terminal) if terminal is not None else normalized_status in TERMINAL_RUNTIME_VERDICT_STATUSES
        return cls(
            status=normalized_status,
            terminal=resolved_terminal,
            result_ok=bool(ok),
            result_ref=str(result_ref or "").strip(),
            result_payload=dict(result_payload or {}),
            metadata=dict(metadata or {}),
        )

    def with_updates(
        self,
        *,
        status: str | None = None,
        terminal: bool | None = None,
        result_ok: bool | None = None,
        result_ref: str | None = None,
        result_payload: Mapping[str, Any] | None = None,
        metadata_merge: Mapping[str, Any] | None = None,
    ) -> "RuntimeVerdict":
        merged_metadata = dict(self.metadata or {})
        if metadata_merge:
            merged_metadata.update(dict(metadata_merge))
        return replace(
            self,
            status=self.status if status is None else status,
            terminal=self.terminal if terminal is None else bool(terminal),
            result_ok=self.result_ok if result_ok is None else bool(result_ok),
            result_ref=self.result_ref if result_ref is None else str(result_ref or "").strip(),
            result_payload=self.result_payload if result_payload is None else dict(result_payload or {}),
            metadata=merged_metadata,
        )


@dataclass(frozen=True, slots=True)
class ProcessExecutionOutcome:
    status: str = "pending"
    terminal: bool = False
    result_ok: bool | None = None
    result_ref: str = ""
    result_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", normalize_runtime_verdict_status(self.status))
        object.__setattr__(self, "terminal", bool(self.terminal))
        if self.result_ok is not None:
            object.__setattr__(self, "result_ok", bool(self.result_ok))
        object.__setattr__(self, "result_ref", str(self.result_ref or "").strip())
        object.__setattr__(self, "result_payload", dict(self.result_payload or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def ok(self) -> bool:
        if self.result_ok is not None:
            return bool(self.result_ok)
        return self.status == "completed"

    def to_runtime_verdict(self) -> RuntimeVerdict:
        return RuntimeVerdict(
            status=self.status,
            terminal=self.terminal,
            result_ok=self.result_ok,
            result_ref=self.result_ref,
            result_payload=self.result_payload,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.to_runtime_verdict().to_dict()

    @classmethod
    def from_runtime_verdict(cls, verdict: RuntimeVerdict | Mapping[str, Any] | None) -> "ProcessExecutionOutcome":
        if isinstance(verdict, RuntimeVerdict):
            payload = verdict.to_dict()
        elif isinstance(verdict, Mapping):
            payload = RuntimeVerdict.from_dict(verdict).to_dict()
        else:
            return cls()
        return cls(
            status=str(payload.get("status") or "pending").strip() or "pending",
            terminal=bool(payload.get("terminal")),
            result_ok=payload.get("result_ok") if payload.get("result_ok") is None else bool(payload.get("result_ok")),
            result_ref=str(payload.get("result_ref") or "").strip(),
            result_payload=dict(payload.get("result_payload") or {}),
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_legacy(
        cls,
        *,
        ok: bool,
        result_ref: str = "",
        result_payload: Mapping[str, Any] | None = None,
        status: str = "",
        terminal: bool | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "ProcessExecutionOutcome":
        return cls.from_runtime_verdict(
            RuntimeVerdict.from_legacy(
                ok=ok,
                result_ref=result_ref,
                result_payload=result_payload,
                status=status,
                terminal=terminal,
                metadata=metadata,
            )
        )


@dataclass(frozen=True, slots=True)
class ProcessWritebackProjection:
    runtime_status: str = "pending"
    terminal: bool = False
    branch_status: str = "queued"
    node_status: str = "pending"
    mission_status: str = "draft"
    workflow_session_status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_status", normalize_runtime_verdict_status(self.runtime_status))
        object.__setattr__(self, "terminal", bool(self.terminal))
        object.__setattr__(self, "branch_status", normalize_branch_writeback_status(self.branch_status))
        object.__setattr__(self, "node_status", normalize_node_writeback_status(self.node_status))
        object.__setattr__(self, "mission_status", normalize_mission_writeback_status(self.mission_status))
        object.__setattr__(
            self,
            "workflow_session_status",
            normalize_workflow_session_writeback_status(self.workflow_session_status),
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_status": self.runtime_status,
            "terminal": self.terminal,
            "branch_status": self.branch_status,
            "node_status": self.node_status,
            "mission_status": self.mission_status,
            "workflow_session_status": self.workflow_session_status,
            "metadata": dict(self.metadata or {}),
        }

    def apply_to_runtime_verdict(self, verdict: RuntimeVerdict | Mapping[str, Any]) -> RuntimeVerdict:
        base = verdict if isinstance(verdict, RuntimeVerdict) else RuntimeVerdict.from_dict(verdict)
        return base.with_updates(
            status=self.runtime_status,
            terminal=self.terminal,
            metadata_merge={
                "writeback": {
                    "branch_status": self.branch_status,
                    "node_status": self.node_status,
                    "mission_status": self.mission_status,
                    "workflow_session_status": self.workflow_session_status,
                },
                **dict(self.metadata or {}),
            },
        )

    @classmethod
    def from_runtime_state(
        cls,
        *,
        verdict: RuntimeVerdict | Mapping[str, Any],
        branch_status: str,
        node_status: str,
        mission_status: str,
        workflow_session_status: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> "ProcessWritebackProjection":
        base = verdict if isinstance(verdict, RuntimeVerdict) else RuntimeVerdict.from_dict(verdict)
        session_status = str(workflow_session_status or "").strip()
        if not session_status:
            session_status = "completed" if base.ok else "failed"
        runtime_status = base.status
        terminal = bool(base.terminal)
        normalized_node = normalize_node_writeback_status(node_status)
        normalized_mission = normalize_mission_writeback_status(mission_status)
        if normalized_node == "awaiting_judge":
            runtime_status = "awaiting_verification"
            terminal = False
        elif normalized_node == "repairing":
            runtime_status = "repair_scheduled"
            terminal = False
        elif normalized_node == "blocked" and normalized_mission == "awaiting_decision":
            normalized_session = normalize_workflow_session_writeback_status(
                session_status,
                default="awaiting_decision",
            )
            if normalized_session == "awaiting_approval":
                runtime_status = "awaiting_approval"
            else:
                runtime_status = "awaiting_decision"
            terminal = False
        elif normalized_node == "done":
            runtime_status = "completed"
            terminal = True
        elif normalized_node == "failed":
            runtime_status = "failed"
            terminal = True
        return cls(
            runtime_status=runtime_status,
            terminal=terminal,
            branch_status=branch_status,
            node_status=node_status,
            mission_status=mission_status,
            workflow_session_status=session_status,
            metadata=dict(metadata or {}),
        )


__all__ = [
    "BRANCH_WRITEBACK_STATUSES",
    "ExecutionReceipt",
    "MISSION_WRITEBACK_STATUSES",
    "NODE_WRITEBACK_STATUSES",
    "ProcessExecutionOutcome",
    "ProcessWritebackProjection",
    "RUNTIME_VERDICT_STATUSES",
    "RuntimeVerdict",
    "TERMINAL_RUNTIME_VERDICT_STATUSES",
    "WORKFLOW_SESSION_WRITEBACK_STATUSES",
    "WorkflowReceipt",
    "normalize_branch_writeback_status",
    "normalize_mission_writeback_status",
    "normalize_node_writeback_status",
    "normalize_runtime_verdict_status",
    "normalize_workflow_session_writeback_status",
]
