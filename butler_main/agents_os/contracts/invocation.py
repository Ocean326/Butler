from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


def _new_invocation_id() -> str:
    return f"invocation_{uuid4().hex[:12]}"


@dataclass(frozen=True, slots=True)
class Invocation:
    entrypoint: str
    channel: str
    session_id: str
    actor_id: str
    user_text: str = ""
    invocation_id: str = field(default_factory=_new_invocation_id)
    correlation_id: str = ""
    source_event_id: str = ""
    subject_id: str = ""
    attachments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    @property
    def request_text(self) -> str:
        return self.user_text
