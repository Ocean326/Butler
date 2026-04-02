from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _normalize_artifact_map(values: Mapping[str, Any] | None) -> dict[str, list[str]]:
    if not isinstance(values, Mapping):
        return {}
    normalized: dict[str, list[str]] = {}
    for key, items in values.items():
        step_id = str(key or "").strip()
        if not step_id or not isinstance(items, list):
            continue
        refs: list[str] = []
        for item in items:
            ref = str(item or "").strip()
            if ref:
                refs.append(ref)
        if refs:
            normalized[step_id] = refs
    return normalized


def _normalize_strings(values: list[Any] | tuple[Any, ...] | set[Any] | None) -> list[str]:
    normalized: list[str] = []
    for item in values or []:
        value = str(item or "").strip()
        if value:
            normalized.append(value)
    return normalized


@dataclass(slots=True)
class ArtifactVisibility:
    """Local artifact visibility contract within a workflow session."""

    scope: str = "session"
    producer_role_id: str = ""
    owner_role_id: str = ""
    consumer_role_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.scope = str(self.scope or "session").strip() or "session"
        self.producer_role_id = str(self.producer_role_id or "").strip()
        self.owner_role_id = str(self.owner_role_id or "").strip()
        self.consumer_role_ids = _normalize_strings(self.consumer_role_ids)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "producer_role_id": self.producer_role_id,
            "owner_role_id": self.owner_role_id,
            "consumer_role_ids": list(self.consumer_role_ids),
            "metadata": dict(self.metadata or {}),
        }

    def allows_role(self, role_id: str = "") -> bool:
        normalized_role_id = str(role_id or "").strip()
        if not normalized_role_id:
            return self.scope not in {"role_scoped", "private", "owner_only"}
        allowed_roles = {
            str(self.producer_role_id or "").strip(),
            str(self.owner_role_id or "").strip(),
            *[str(item or "").strip() for item in self.consumer_role_ids],
        }
        allowed_roles.discard("")
        if self.scope in {"role_scoped", "private", "owner_only"}:
            return normalized_role_id in allowed_roles
        return True

    def consumer_view(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "ArtifactVisibility":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class ArtifactRecord:
    """Typed artifact descriptor produced by one workflow step."""

    step_id: str = ""
    ref: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    visibility: ArtifactVisibility = field(default_factory=ArtifactVisibility)
    dedupe_key: str = ""
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.step_id = str(self.step_id or "").strip()
        self.ref = str(self.ref or "").strip()
        self.payload = dict(self.payload or {})
        self.visibility = (
            self.visibility
            if isinstance(self.visibility, ArtifactVisibility)
            else ArtifactVisibility.from_dict(self.visibility if isinstance(self.visibility, Mapping) else {})
        )
        self.dedupe_key = str(self.dedupe_key or "").strip()
        self.created_at = str(self.created_at or _utc_now_iso()).strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "ref": self.ref,
            "payload": dict(self.payload or {}),
            "visibility": self.visibility.to_dict(),
            "dedupe_key": self.dedupe_key,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "ArtifactRecord":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        if isinstance(data.get("visibility"), Mapping):
            data["visibility"] = ArtifactVisibility.from_dict(data.get("visibility"))
        else:
            data["visibility"] = ArtifactVisibility(
                scope=str(data.pop("visibility_scope", "session") or "session").strip() or "session",
                producer_role_id=str(data.pop("producer_role_id", "") or "").strip(),
                owner_role_id=str(data.pop("owner_role_id", "") or "").strip(),
                consumer_role_ids=list(data.pop("consumer_role_ids", []) or []),
            )
        return cls(**data)


@dataclass(slots=True)
class ArtifactRegistry:
    """Index of artifacts produced by one collaboration session."""

    session_id: str = ""
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    latest_outputs: dict[str, Any] = field(default_factory=dict)
    refs_by_step: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.session_id = str(self.session_id or "").strip()
        self.artifacts = [
            item if isinstance(item, ArtifactRecord) else ArtifactRecord.from_dict(item)
            for item in self.artifacts
            if isinstance(item, (ArtifactRecord, Mapping))
        ]
        normalized_latest_outputs: dict[str, dict[str, Any]] = {}
        for step_id, payload in dict(self.latest_outputs or {}).items():
            normalized_step_id = str(step_id or "").strip()
            if not normalized_step_id or not isinstance(payload, Mapping):
                continue
            normalized_latest_outputs[normalized_step_id] = ArtifactRecord.from_dict(payload).to_dict()
        self.latest_outputs = normalized_latest_outputs
        self.refs_by_step = _normalize_artifact_map(self.refs_by_step)
        if not self.latest_outputs and self.artifacts:
            for artifact in self.artifacts:
                self.latest_outputs[artifact.step_id] = artifact.to_dict()
        if not self.refs_by_step and self.artifacts:
            for artifact in self.artifacts:
                self.refs_by_step.setdefault(artifact.step_id, []).append(artifact.ref)

    def add_artifact(
        self,
        *,
        step_id: str,
        ref: str,
        payload: Mapping[str, Any] | None = None,
        producer_role_id: str = "",
        owner_role_id: str = "",
        visibility_scope: str = "session",
        consumer_role_ids: list[str] | None = None,
        visibility_metadata: Mapping[str, Any] | None = None,
        dedupe_key: str = "",
    ) -> tuple[ArtifactRecord | None, bool]:
        normalized_step_id = str(step_id or "").strip()
        normalized_ref = str(ref or "").strip()
        if not normalized_step_id or not normalized_ref:
            return None, False
        artifact = ArtifactRecord(
            step_id=normalized_step_id,
            ref=normalized_ref,
            payload=dict(payload or {}),
            visibility=ArtifactVisibility(
                scope=visibility_scope,
                producer_role_id=producer_role_id,
                owner_role_id=owner_role_id,
                consumer_role_ids=list(consumer_role_ids or []),
                metadata=dict(visibility_metadata or {}),
            ),
            dedupe_key=str(dedupe_key or "").strip(),
        )
        existing_index = self._find_artifact_index(artifact)
        if existing_index >= 0:
            existing = self.artifacts[existing_index]
            artifact.created_at = existing.created_at
            if existing.to_dict() == artifact.to_dict():
                return existing, False
            self.artifacts[existing_index] = artifact
            self._rebuild_indexes()
            return artifact, True
        self.artifacts.append(artifact)
        self._rebuild_indexes()
        return artifact, True

    def _find_artifact_index(self, artifact: ArtifactRecord) -> int:
        dedupe_key = artifact.dedupe_key or f"{artifact.step_id}::{artifact.ref}"
        for index, existing in enumerate(self.artifacts):
            existing_key = existing.dedupe_key or f"{existing.step_id}::{existing.ref}"
            if existing_key == dedupe_key:
                return index
        return -1

    def _rebuild_indexes(self) -> None:
        self.latest_outputs = {}
        self.refs_by_step = {}
        for artifact in self.artifacts:
            self.latest_outputs[artifact.step_id] = artifact.to_dict()
            refs = self.refs_by_step.setdefault(artifact.step_id, [])
            if artifact.ref not in refs:
                refs.append(artifact.ref)

    def visible_records(self, *, role_id: str = "", step_id: str = "") -> list[ArtifactRecord]:
        normalized_step_id = str(step_id or "").strip()
        visible: list[ArtifactRecord] = []
        for artifact in self.artifacts:
            if normalized_step_id and artifact.step_id != normalized_step_id:
                continue
            if artifact.visibility.allows_role(role_id):
                visible.append(artifact)
        return visible

    def visibility_index(self, *, role_id: str = "", step_id: str = "") -> list[dict[str, Any]]:
        return [
            {
                "step_id": artifact.step_id,
                "ref": artifact.ref,
                "visibility": artifact.visibility.consumer_view(),
            }
            for artifact in self.visible_records(role_id=role_id, step_id=step_id)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "latest_outputs": {step_id: dict(payload) for step_id, payload in self.latest_outputs.items()},
            "refs_by_step": {step_id: list(refs) for step_id, refs in self.refs_by_step.items()},
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "ArtifactRegistry":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        data["artifacts"] = [
            item if isinstance(item, ArtifactRecord) else ArtifactRecord.from_dict(item)
            for item in (data.get("artifacts") or [])
            if isinstance(item, (ArtifactRecord, Mapping))
        ]
        return cls(**data)
