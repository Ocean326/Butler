from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from ..contracts import Invocation
from ..runtime.orchestrator import AgentRuntime, RuntimeRequest
from .agent_spec import AgentCapabilities, AgentSpec
from .profiles import AgentProfileRegistry


class AgentRuntimeFactory(Protocol):
    def create_runtime(self, spec: AgentSpec) -> AgentRuntime:
        ...


@dataclass(slots=True)
class AgentFactory:
    default_runtime: AgentRuntime
    runtime_builders: Mapping[str, AgentRuntimeFactory] = field(default_factory=dict)
    profile_registry: AgentProfileRegistry | None = None

    def create_runtime(self, spec: AgentSpec) -> AgentRuntime:
        builder = self.runtime_builders.get(spec.runtime_key)
        if builder is None:
            return self.default_runtime
        return builder.create_runtime(spec)

    def create_spec(
        self,
        agent_id: str,
        profile_id: str,
        *,
        capabilities: AgentCapabilities | None = None,
        runtime_key: str = "default",
        metadata: Mapping[str, Any] | None = None,
    ) -> AgentSpec:
        if self.profile_registry is None:
            raise LookupError("profile_registry is required to build AgentSpec from profile_id")
        profile = self.profile_registry.require(profile_id)
        return AgentSpec(
            agent_id=agent_id,
            profile=profile,
            capabilities=capabilities or AgentCapabilities(),
            runtime_key=runtime_key,
            metadata=dict(metadata or {}),
        )

    def build_request(
        self,
        invocation: Invocation,
        spec: AgentSpec,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> RuntimeRequest:
        return RuntimeRequest(invocation=invocation, agent_spec=spec, metadata=dict(metadata or {}))
