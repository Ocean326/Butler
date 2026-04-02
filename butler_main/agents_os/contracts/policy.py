from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    policy_id: str = ""
    mode: str = "allowlist"
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    max_calls: int = 0
    rate_limit_per_minute: int = 0
    restrictions: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OutputPolicy:
    policy_id: str = ""
    allow_text: bool = True
    allow_card: bool = True
    allow_images: bool = False
    allow_files: bool = False
    allow_artifacts: bool = True
    max_text_length: int = 4000
    require_review: bool = False
    allowed_delivery_modes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
