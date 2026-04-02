from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


def _new_projection_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass(frozen=True, slots=True)
class RouteProjection:
    route_id: str = field(default_factory=lambda: _new_projection_id("route"))
    route_key: str = ""
    target_agent_id: str = ""
    workflow_kind: str = ""
    capability_id: str = ""
    delivery_mode: str = ""
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkflowProjection:
    workflow_id: str
    workflow_kind: str = ""
    invocation_id: str = ""
    status: str = "pending"
    route: RouteProjection | None = None
    agent_id: str = ""
    agent_spec_id: str = ""
    current_step_id: str = ""
    required_capability_ids: list[str] = field(default_factory=list)
    resolved_capability_ids: list[str] = field(default_factory=list)
    memory_policy_id: str = ""
    output_policy_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
