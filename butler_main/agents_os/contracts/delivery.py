from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .output import ArtifactRef, OutputBundle


def _new_session_id() -> str:
    return f"delivery_session_{uuid4().hex[:12]}"


def _new_request_id() -> str:
    return f"delivery_request_{uuid4().hex[:12]}"


@dataclass(frozen=True, slots=True)
class DeliverySession:
    platform: str
    mode: str
    target: str
    session_id: str = field(default_factory=_new_session_id)
    target_type: str = "channel"
    thread_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeliveryRequest:
    session: DeliverySession
    bundle_ref: str = ""
    request_id: str = field(default_factory=_new_request_id)
    bundle: OutputBundle | None = None
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    delivered: bool
    session: DeliverySession
    request_id: str = ""
    delivery_id: str = ""
    log: list[str] = field(default_factory=list)
    artifact_refs: list[ArtifactRef] = field(default_factory=list)
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return "delivered" if self.delivered and not self.error else "failed"
