from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MemoryWriteRequest:
    channel: str
    title: str
    summary: str
    keywords: tuple[str, ...] = ()
    source_type: str = ""
    source_memory_id: str = ""
    source_reason: str = ""
    source_topic: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProfileWriteRequest:
    action: str
    category: str
    content: str
    reason: str = ""


@dataclass(frozen=True)
class SummaryCandidate:
    channel: str
    title: str
    summary: str
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class SummaryBlock:
    title: str
    summary: str
    bullets: tuple[str, ...] = ()
    source_memory_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PostTurnMemoryInput:
    workspace: str
    memory_id: str
    user_prompt: str
    assistant_reply: str
    candidate_memory: dict
    recent_entries: tuple[dict, ...]
    local_memory_hits: tuple[dict, ...]
    profile_excerpt: str
    suppress_task_merge: bool = False


@dataclass(frozen=True)
class PostTurnMemoryResult:
    local_writes: tuple[MemoryWriteRequest, ...] = ()
    profile_writes: tuple[ProfileWriteRequest, ...] = ()
    mark_promoted: bool = False
    should_merge_tasks: bool = False
    audit_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompactMemoryInput:
    workspace: str
    reason: str
    pool: str
    old_entries: tuple[dict, ...]
    keep_entries: tuple[dict, ...]


@dataclass(frozen=True)
class CompactMemoryResult:
    summary_block: SummaryBlock | None = None
    summary_candidates: tuple[SummaryCandidate, ...] = ()
    audit_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaintenanceMemoryInput:
    workspace: str
    reason: str
    scope: str
    recent_entries: tuple[dict, ...] = ()
    local_memory_hits: tuple[dict, ...] = ()
    profile_excerpt: str = ""


@dataclass(frozen=True)
class MaintenanceMemoryResult:
    run_recent_prune: bool = False
    run_recent_compact: bool = False
    run_local_rewrite: bool = False
    dedupe_writes: tuple[MemoryWriteRequest, ...] = ()
    audit_notes: tuple[str, ...] = ()
