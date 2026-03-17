from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryAgentPolicy:
    agent_name: str
    allow_local_write: bool
    allow_profile_write: bool
    allowed_channels: tuple[str, ...]


POST_TURN_POLICY = MemoryAgentPolicy(
    agent_name="post_turn_memory_agent",
    allow_local_write=True,
    allow_profile_write=True,
    allowed_channels=("local_memory", "user_profile"),
)

COMPACT_POLICY = MemoryAgentPolicy(
    agent_name="compact_memory_agent",
    allow_local_write=True,
    allow_profile_write=False,
    allowed_channels=("project_state", "reference", "archive"),
)

MAINTENANCE_POLICY = MemoryAgentPolicy(
    agent_name="maintenance_memory_agent",
    allow_local_write=True,
    allow_profile_write=False,
    allowed_channels=("local_memory", "project_state", "reference", "archive"),
)
