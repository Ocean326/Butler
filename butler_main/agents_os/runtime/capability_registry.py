from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from ..contracts import Invocation
from .subworkflow_interface import CapabilityBinding, CapabilityResolver


@dataclass(slots=True)
class CapabilityRegistry(CapabilityResolver):
    bindings: list[CapabilityBinding] = field(default_factory=list)

    def register(self, binding: CapabilityBinding) -> CapabilityBinding:
        self.bindings.append(binding)
        self.bindings.sort(key=lambda item: item.priority, reverse=True)
        return binding

    def extend(self, bindings: Sequence[CapabilityBinding]) -> None:
        for binding in bindings:
            self.register(binding)

    def resolve(
        self,
        invocation: Invocation | None = None,
        *,
        workflow_kind: str = "",
        required_policies: Sequence[str] = (),
    ) -> list[CapabilityBinding]:
        entrypoint = invocation.entrypoint if invocation is not None else ""
        required = set(required_policies)
        matches: list[CapabilityBinding] = []
        for binding in self.bindings:
            capability = binding.capability
            if not capability.supports(entrypoint=entrypoint, workflow_kind=workflow_kind):
                continue
            if required and not required.issubset(set(capability.required_policies)):
                continue
            matches.append(binding)
        return matches
