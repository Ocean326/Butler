from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PromptBlock:
    name: str
    content: str
    role: str = "system"
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PromptProfile:
    profile_id: str
    display_name: str = ""
    bootstrap_refs: list[str] = field(default_factory=list)
    policy_refs: list[str] = field(default_factory=list)
    block_order: list[str] = field(default_factory=list)
    render_mode: str = "dialogue"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PromptContext:
    profile: PromptProfile
    blocks: list[PromptBlock] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    dynamic_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def metadata(self) -> dict[str, Any]:
        return self.dynamic_metadata


@dataclass(frozen=True, slots=True)
class ModelInput:
    context: PromptContext
    rendered_prompt: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    additional_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
