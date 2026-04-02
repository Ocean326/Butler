from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from ..contracts import Invocation


@dataclass(frozen=True, slots=True)
class SubworkflowCapability:
    capability_id: str
    name: str = ""
    supported_entrypoints: list[str] = field(default_factory=list)
    supported_workflow_kinds: list[str] = field(default_factory=list)
    required_policies: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports(self, *, entrypoint: str = "", workflow_kind: str = "") -> bool:
        entrypoint_ok = not self.supported_entrypoints or entrypoint in self.supported_entrypoints
        workflow_ok = not self.supported_workflow_kinds or workflow_kind in self.supported_workflow_kinds
        return entrypoint_ok and workflow_ok


@dataclass(frozen=True, slots=True)
class CapabilityBinding:
    capability: SubworkflowCapability
    agent_id: str
    agent_spec_id: str = ""
    priority: int = 0
    default_route_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityResolver(Protocol):
    def resolve(
        self,
        invocation: Invocation | None = None,
        *,
        workflow_kind: str = "",
        required_policies: Sequence[str] = (),
    ) -> list[CapabilityBinding]:
        ...
