from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..contracts import MemoryPolicy, OutputPolicy, PromptProfile, ToolPolicy


@dataclass(frozen=True, slots=True)
class AgentCapabilities:
    memory_mode: str = "default"
    retrieval_enabled: bool = False
    tool_access: bool = False
    delivery_target: str = "generic"
    capability_ids: Sequence[str] = field(default_factory=tuple)
    supported_workflow_kinds: Sequence[str] = field(default_factory=tuple)
    extras: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentProfile:
    profile_id: str
    prompt_profile_id: str = ""
    policy_ids: Sequence[str] = field(default_factory=tuple)
    description: str = ""
    prompt_profile: PromptProfile | None = None
    memory_policy: MemoryPolicy | None = None
    tool_policy: ToolPolicy | None = None
    output_policy: OutputPolicy | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.prompt_profile_id and self.prompt_profile is not None:
            object.__setattr__(self, "prompt_profile_id", self.prompt_profile.profile_id)


@dataclass(frozen=True, slots=True)
class AgentSpec:
    agent_id: str
    profile: AgentProfile
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    spec_id: str = ""
    runtime_key: str = "default"
    entrypoints: Sequence[str] = field(default_factory=tuple)
    labels: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.spec_id:
            object.__setattr__(self, "spec_id", self.agent_id)
