from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .memory import MemoryWritebackRequest


def _new_bundle_id() -> str:
    return f"bundle_{uuid4().hex[:12]}"


def _new_artifact_id() -> str:
    return f"artifact_{uuid4().hex[:12]}"


@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str
    style: str = "plain"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CardBlock:
    title: str
    body: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ImageAsset:
    path: str
    caption: str = ""
    media_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FileAsset:
    path: str
    description: str = ""
    media_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocLink:
    url: str
    title: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    name: str
    uri: str
    artifact_id: str = field(default_factory=_new_artifact_id)
    kind: str = "generic"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OutputBundle:
    bundle_id: str = field(default_factory=_new_bundle_id)
    status: str = "ready"
    summary: str = ""
    text_blocks: list[TextBlock] = field(default_factory=list)
    cards: list[CardBlock] = field(default_factory=list)
    images: list[ImageAsset] = field(default_factory=list)
    files: list[FileAsset] = field(default_factory=list)
    doc_links: list[DocLink] = field(default_factory=list)
    state_updates: list[dict[str, Any]] = field(default_factory=list)
    memory_writebacks: list[MemoryWritebackRequest] = field(default_factory=list)
    artifacts: list[ArtifactRef] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not any(
            (
                self.text_blocks,
                self.cards,
                self.images,
                self.files,
                self.doc_links,
                self.state_updates,
                self.memory_writebacks,
                self.artifacts,
            )
        )
