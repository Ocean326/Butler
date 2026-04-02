from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from ..protocol.receipts import DecisionReceipt, HandoffReceipt, StepReceipt
from ..runtime.contracts import (
    AcceptanceReceipt,
    normalize_edge_kind,
    normalize_process_role,
    normalize_run_status,
    normalize_step_kind,
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp-{uuid4().hex[:8]}")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


@dataclass(slots=True)
class WorkflowStepSpec:
    step_id: str
    step_kind: str = "dispatch"
    process_role: str = "executor"
    worker_hint: str = ""
    requires_verification: bool = False
    requires_approval: bool = False
    allow_parallel: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.step_kind = normalize_step_kind(self.step_kind)
        self.process_role = normalize_process_role(self.process_role)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowStepSpec":
        if not isinstance(payload, Mapping):
            return cls(step_id="")
        return cls(**dict(payload))


@dataclass(slots=True)
class WorkflowEdgeSpec:
    source_step_id: str
    target_step_id: str = ""
    edge_kind: str = "next"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.edge_kind = normalize_edge_kind(self.edge_kind)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowEdgeSpec":
        if not isinstance(payload, Mapping):
            return cls(source_step_id="")
        data = dict(payload)
        source_step_id = str(data.get("source_step_id") or data.get("source") or data.get("from_step_id") or "").strip()
        target_step_id = str(data.get("target_step_id") or data.get("target") or data.get("to_step_id") or "").strip()
        edge_kind = str(data.get("edge_kind") or data.get("kind") or "next").strip() or "next"
        metadata = dict(data.get("metadata") or {})
        return cls(
            source_step_id=source_step_id,
            target_step_id=target_step_id,
            edge_kind=edge_kind,
            metadata=metadata,
        )


@dataclass(slots=True)
class WorkflowSpec:
    workflow_id: str
    run_type: str = ""
    title: str = ""
    scenario_id: str = ""
    steps: list[WorkflowStepSpec] = field(default_factory=list)
    edges: list[WorkflowEdgeSpec] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [step.to_dict() for step in self.steps]
        payload["edges"] = [edge.to_dict() for edge in self.edges]
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowSpec":
        if not isinstance(payload, Mapping):
            return cls(workflow_id="")
        data = dict(payload)
        data["steps"] = [WorkflowStepSpec.from_dict(item) for item in data.get("steps") or [] if isinstance(item, Mapping)]
        data["edges"] = [WorkflowEdgeSpec.from_dict(item) for item in data.get("edges") or [] if isinstance(item, Mapping)]
        return cls(**data)

    def step_by_id(self, step_id: str) -> WorkflowStepSpec | None:
        target = str(step_id or "").strip()
        if not target:
            return self.steps[0] if self.steps else None
        for step in self.steps:
            if step.step_id == target:
                return step
        return None

    def outgoing_edges(self, step_id: str, *, edge_kind: str = "") -> list[WorkflowEdgeSpec]:
        target_step_id = str(step_id or "").strip()
        target_kind = normalize_edge_kind(edge_kind) if str(edge_kind or "").strip() else ""
        matched: list[WorkflowEdgeSpec] = []
        for edge in self.edges:
            if edge.source_step_id != target_step_id:
                continue
            if target_kind and edge.edge_kind != target_kind:
                continue
            matched.append(edge)
        return matched

    def first_step_id(self) -> str:
        return self.steps[0].step_id if self.steps else ""


@dataclass(slots=True)
class WorkflowCursor:
    workflow_id: str = ""
    current_step_id: str = ""
    status: str = "pending"
    iteration: int = 0
    pending_handoff_id: str = ""
    latest_decision: str = ""
    resume_from: str = ""
    updated_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.status = normalize_run_status(self.status, default="pending")
        self.iteration = max(0, int(self.iteration or 0))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowCursor":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class WorkflowCheckpoint:
    checkpoint_id: str = field(default_factory=lambda: _new_id("workflow_checkpoint"))
    instance_id: str = ""
    session_id: str = ""
    run_id: str = ""
    workflow_id: str = ""
    cursor: WorkflowCursor = field(default_factory=WorkflowCursor)
    step_receipt: StepReceipt | None = None
    handoff_receipt: HandoffReceipt | None = None
    decision_receipt: DecisionReceipt | None = None
    acceptance: AcceptanceReceipt | None = None
    created_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "instance_id": self.instance_id,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "cursor": self.cursor.to_dict(),
            "step_receipt": self.step_receipt.to_dict() if self.step_receipt else {},
            "handoff_receipt": self.handoff_receipt.to_dict() if self.handoff_receipt else {},
            "decision_receipt": self.decision_receipt.to_dict() if self.decision_receipt else {},
            "acceptance": asdict(self.acceptance) if self.acceptance else {},
            "created_at": self.created_at,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowCheckpoint":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        data["cursor"] = WorkflowCursor.from_dict(data.get("cursor"))
        data["step_receipt"] = StepReceipt.from_dict(data.get("step_receipt")) if isinstance(data.get("step_receipt"), Mapping) and data.get("step_receipt") else None
        data["handoff_receipt"] = HandoffReceipt.from_dict(data.get("handoff_receipt")) if isinstance(data.get("handoff_receipt"), Mapping) and data.get("handoff_receipt") else None
        data["decision_receipt"] = DecisionReceipt.from_dict(data.get("decision_receipt")) if isinstance(data.get("decision_receipt"), Mapping) and data.get("decision_receipt") else None
        data["acceptance"] = AcceptanceReceipt(**dict(data.get("acceptance") or {})) if isinstance(data.get("acceptance"), Mapping) and data.get("acceptance") else None
        return cls(**data)


@dataclass(slots=True)
class WorkflowRunProjection:
    spec: WorkflowSpec
    cursor: WorkflowCursor = field(default_factory=WorkflowCursor)
    step_receipts: list[StepReceipt] = field(default_factory=list)
    handoff_receipts: list[HandoffReceipt] = field(default_factory=list)
    decision_receipts: list[DecisionReceipt] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "cursor": self.cursor.to_dict(),
            "step_receipts": [item.to_dict() for item in self.step_receipts],
            "handoff_receipts": [item.to_dict() for item in self.handoff_receipts],
            "decision_receipts": [item.to_dict() for item in self.decision_receipts],
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowRunProjection":
        if not isinstance(payload, Mapping):
            return cls(spec=WorkflowSpec(workflow_id=""))
        data = dict(payload)
        return cls(
            spec=WorkflowSpec.from_dict(data.get("spec")),
            cursor=WorkflowCursor.from_dict(data.get("cursor")),
            step_receipts=[
                StepReceipt.from_dict(item)
                for item in data.get("step_receipts") or []
                if isinstance(item, Mapping)
            ],
            handoff_receipts=[
                HandoffReceipt.from_dict(item)
                for item in data.get("handoff_receipts") or []
                if isinstance(item, Mapping)
            ],
            decision_receipts=[
                DecisionReceipt.from_dict(item)
                for item in data.get("decision_receipts") or []
                if isinstance(item, Mapping)
            ],
            metadata=dict(data.get("metadata") or {}),
        )


class FileWorkflowCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(checkpoint.to_dict(), ensure_ascii=False) + "\n")
        return checkpoint

    def get(self, checkpoint_id: str) -> WorkflowCheckpoint | None:
        if not self.path.exists():
            return None
        target = str(checkpoint_id or "").strip()
        if not target:
            return None
        with self.path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
        for line in reversed(lines):
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if str(payload.get("checkpoint_id") or "").strip() == target:
                return WorkflowCheckpoint.from_dict(payload)
        return None

    def latest(self) -> WorkflowCheckpoint | None:
        if not self.path.exists():
            return None
        latest_payload: dict[str, Any] | None = None
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    latest_payload = json.loads(line)
                except Exception:
                    continue
        return WorkflowCheckpoint.from_dict(latest_payload) if latest_payload else None

    def write_current(self, checkpoint: WorkflowCheckpoint) -> None:
        current_path = self.path.with_name("current.json")
        _write_text_atomic(current_path, json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=2))
