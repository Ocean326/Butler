from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4


MISSION_STATUSES: tuple[str, ...] = (
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

NODE_STATUSES: tuple[str, ...] = (
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

BRANCH_STATUSES: tuple[str, ...] = (
    "queued",
    "leased",
    "running",
    "succeeded",
    "failed",
    "timed_out",
    "cancelled",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def normalize_mission_status(value: str, *, default: str = "draft") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return default
    return normalized if normalized in MISSION_STATUSES else default


def normalize_node_status(value: str, *, default: str = "pending") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return default
    return normalized if normalized in NODE_STATUSES else default


def normalize_branch_status(value: str, *, default: str = "queued") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return default
    return normalized if normalized in BRANCH_STATUSES else default


def _as_string_list(values: list[Any] | tuple[Any, ...] | None) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for item in values:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


@dataclass(slots=True)
class MissionNode:
    node_id: str = field(default_factory=lambda: _new_id("node"))
    kind: str = "task"
    title: str = ""
    status: str = "pending"
    dependencies: list[str] = field(default_factory=list)
    inputs_ref: list[str] = field(default_factory=list)
    branch_policy: dict[str, Any] = field(default_factory=dict)
    runtime_plan: dict[str, Any] = field(default_factory=dict)
    judge_spec: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.status = normalize_node_status(self.status)
        self.dependencies = _as_string_list(self.dependencies)
        self.inputs_ref = _as_string_list(self.inputs_ref)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "MissionNode":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class Mission:
    mission_id: str = field(default_factory=lambda: _new_id("mission"))
    mission_type: str = "generic"
    title: str = ""
    goal: str = ""
    status: str = "draft"
    priority: int = 50
    inputs: dict[str, Any] = field(default_factory=dict)
    success_criteria: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    nodes: list[MissionNode] = field(default_factory=list)
    current_iteration: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.status = normalize_mission_status(self.status)
        self.priority = int(self.priority or 0)
        self.current_iteration = max(0, int(self.current_iteration or 0))
        self.success_criteria = _as_string_list(self.success_criteria)
        self.nodes = [
            item if isinstance(item, MissionNode) else MissionNode.from_dict(item)
            for item in (self.nodes or [])
        ]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["nodes"] = [node.to_dict() for node in self.nodes]
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "Mission":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        data["nodes"] = [MissionNode.from_dict(item) for item in data.get("nodes") or [] if isinstance(item, Mapping)]
        return cls(**data)

    def node_by_id(self, node_id: str) -> MissionNode | None:
        target = str(node_id or "").strip()
        for node in self.nodes:
            if node.node_id == target:
                return node
        return None


@dataclass(slots=True)
class Branch:
    branch_id: str = field(default_factory=lambda: _new_id("branch"))
    mission_id: str = ""
    node_id: str = ""
    status: str = "queued"
    worker_profile: str = ""
    input_payload: dict[str, Any] = field(default_factory=dict)
    result_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.status = normalize_branch_status(self.status)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "Branch":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class LedgerEvent:
    event_id: str = field(default_factory=lambda: _new_id("event"))
    mission_id: str = ""
    node_id: str = ""
    branch_id: str = ""
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "LedgerEvent":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))
