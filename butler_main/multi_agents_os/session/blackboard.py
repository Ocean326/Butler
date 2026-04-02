from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping

from .artifact_registry import ArtifactVisibility


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _normalize_strings(values: list[Any] | tuple[Any, ...] | set[Any] | None) -> list[str]:
    normalized: list[str] = []
    for item in values or []:
        value = str(item or "").strip()
        if value:
            normalized.append(value)
    return normalized


@dataclass(slots=True)
class BlackboardEntry:
    """One workflow-scoped blackboard slot for shared collaboration notes."""

    entry_key: str = ""
    entry_kind: str = "note"
    payload: dict[str, Any] = field(default_factory=dict)
    step_id: str = ""
    author_role_id: str = ""
    tags: list[str] = field(default_factory=list)
    visibility: ArtifactVisibility = field(default_factory=ArtifactVisibility)
    dedupe_key: str = ""
    updated_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.entry_key = str(self.entry_key or "").strip()
        self.entry_kind = str(self.entry_kind or "note").strip() or "note"
        self.payload = dict(self.payload or {})
        self.step_id = str(self.step_id or "").strip()
        self.author_role_id = str(self.author_role_id or "").strip()
        self.tags = _normalize_strings(self.tags)
        self.visibility = (
            self.visibility
            if isinstance(self.visibility, ArtifactVisibility)
            else ArtifactVisibility.from_dict(self.visibility if isinstance(self.visibility, Mapping) else {})
        )
        self.dedupe_key = str(self.dedupe_key or "").strip()
        self.updated_at = str(self.updated_at or _utc_now_iso()).strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_key": self.entry_key,
            "entry_kind": self.entry_kind,
            "payload": dict(self.payload or {}),
            "step_id": self.step_id,
            "author_role_id": self.author_role_id,
            "tags": list(self.tags),
            "visibility": self.visibility.to_dict(),
            "dedupe_key": self.dedupe_key,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "BlackboardEntry":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        if isinstance(data.get("visibility"), Mapping):
            data["visibility"] = ArtifactVisibility.from_dict(data.get("visibility"))
        return cls(**data)

    def visible_to(self, role_id: str = "", step_id: str = "") -> bool:
        normalized_step_id = str(step_id or "").strip()
        if normalized_step_id and self.step_id and self.step_id != normalized_step_id:
            return False
        return self.visibility.allows_role(role_id)


@dataclass(slots=True)
class WorkflowBlackboard:
    """Typed collaboration blackboard persisted per workflow session."""

    session_id: str = ""
    entries: dict[str, BlackboardEntry] = field(default_factory=dict)
    last_updated_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.session_id = str(self.session_id or "").strip()
        normalized_entries: dict[str, BlackboardEntry] = {}
        for entry_key, payload in dict(self.entries or {}).items():
            normalized_key = str(entry_key or "").strip()
            if not normalized_key or not isinstance(payload, (BlackboardEntry, Mapping)):
                continue
            entry = payload if isinstance(payload, BlackboardEntry) else BlackboardEntry.from_dict(payload)
            if not entry.entry_key:
                entry.entry_key = normalized_key
            normalized_entries[normalized_key] = entry
        self.entries = normalized_entries
        self.last_updated_at = str(self.last_updated_at or _utc_now_iso()).strip()

    def upsert_entry(
        self,
        *,
        entry_key: str,
        payload: Mapping[str, Any] | None = None,
        entry_kind: str = "note",
        step_id: str = "",
        author_role_id: str = "",
        tags: list[str] | None = None,
        visibility_scope: str = "session",
        consumer_role_ids: list[str] | None = None,
        visibility_metadata: Mapping[str, Any] | None = None,
        dedupe_key: str = "",
    ) -> tuple[BlackboardEntry, bool]:
        entry = BlackboardEntry(
            entry_key=entry_key,
            entry_kind=entry_kind,
            payload=dict(payload or {}),
            step_id=step_id,
            author_role_id=author_role_id,
            tags=list(tags or []),
            visibility=ArtifactVisibility(
                scope=visibility_scope,
                producer_role_id=author_role_id,
                owner_role_id=author_role_id,
                consumer_role_ids=list(consumer_role_ids or []),
                metadata=dict(visibility_metadata or {}),
            ),
            dedupe_key=dedupe_key,
        )
        existing = self.entries.get(entry.entry_key)
        if existing is not None:
            comparison = BlackboardEntry.from_dict(entry.to_dict())
            comparison.updated_at = existing.updated_at
            if existing.to_dict() == comparison.to_dict():
                return existing, False
        self.entries[entry.entry_key] = entry
        self.touch()
        return entry, True

    def get_entry(self, entry_key: str) -> BlackboardEntry | None:
        return self.entries.get(str(entry_key or "").strip())

    def visible_entries(self, *, role_id: str = "", step_id: str = "") -> list[BlackboardEntry]:
        return [
            entry
            for entry in self.entries.values()
            if entry.visible_to(role_id=role_id, step_id=step_id)
        ]

    def touch(self) -> None:
        self.last_updated_at = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "entries": {
                entry_key: entry.to_dict()
                for entry_key, entry in self.entries.items()
            },
            "last_updated_at": self.last_updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowBlackboard":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        entries_payload = data.get("entries") if isinstance(data.get("entries"), Mapping) else {}
        data["entries"] = {
            str(entry_key or "").strip(): (
                item if isinstance(item, BlackboardEntry) else BlackboardEntry.from_dict(item)
            )
            for entry_key, item in dict(entries_payload).items()
            if str(entry_key or "").strip() and isinstance(item, (BlackboardEntry, Mapping))
        }
        return cls(**data)
