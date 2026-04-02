from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MemoryScope:
    name: str
    description: str = ""
    scope_type: str = "general"
    retention_days: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryPolicy:
    policy_id: str = ""
    session_read: bool = False
    session_write: bool = False
    retrieval_scopes: list[str] = field(default_factory=list)
    writeback_scopes: list[str] = field(default_factory=list)
    long_term_write: str = "none"
    visibility_flags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryHit:
    scope: str
    excerpt: str
    source_id: str
    score: float = 0.0
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryWritebackRequest:
    target_scope: str
    content: str
    write_mode: str = "append"
    dedupe_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryContext:
    hits: list[MemoryHit] = field(default_factory=list)
    scope: str | None = None
    scopes: list[str] = field(default_factory=list)
    pending_writebacks: list[MemoryWritebackRequest] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
