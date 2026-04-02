from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from ..contracts import MemoryPolicy, OutputPolicy, PromptProfile, ToolPolicy
from .agent_spec import AgentProfile


def build_agent_profile(
    profile_id: str,
    *,
    prompt_profile: PromptProfile | None = None,
    memory_policy: MemoryPolicy | None = None,
    tool_policy: ToolPolicy | None = None,
    output_policy: OutputPolicy | None = None,
    prompt_profile_id: str = "",
    policy_ids: Sequence[str] = (),
    description: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> AgentProfile:
    return AgentProfile(
        profile_id=profile_id,
        prompt_profile_id=prompt_profile_id,
        policy_ids=tuple(policy_ids),
        description=description,
        prompt_profile=prompt_profile,
        memory_policy=memory_policy,
        tool_policy=tool_policy,
        output_policy=output_policy,
        metadata=dict(metadata or {}),
    )


@dataclass(slots=True)
class AgentProfileRegistry:
    profiles: dict[str, AgentProfile] = field(default_factory=dict)

    def register(self, profile: AgentProfile) -> AgentProfile:
        self.profiles[profile.profile_id] = profile
        return profile

    def extend(self, profiles: Iterable[AgentProfile]) -> None:
        for profile in profiles:
            self.register(profile)

    def get(self, profile_id: str) -> AgentProfile | None:
        return self.profiles.get(profile_id)

    def require(self, profile_id: str) -> AgentProfile:
        profile = self.get(profile_id)
        if profile is None:
            raise LookupError(f"agent profile not found: {profile_id}")
        return profile
