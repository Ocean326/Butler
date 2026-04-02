from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass(slots=True)
class WorkflowSessionEvent:
    session_id: str = ""
    event_id: str = field(default_factory=lambda: _new_id("workflow_event"))
    event_type: str = ""
    layer: str = "L4.multi_agent_runtime"
    subject_ref: str = ""
    causation_ref: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.session_id = str(self.session_id or "").strip()
        self.event_type = str(self.event_type or "").strip()
        self.layer = str(self.layer or "L4.multi_agent_runtime").strip() or "L4.multi_agent_runtime"
        self.subject_ref = str(self.subject_ref or self.session_id).strip()
        self.causation_ref = str(self.causation_ref or "").strip()
        self.payload = dict(self.payload or {})
        self.created_at = str(self.created_at or _utc_now_iso()).strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowSessionEvent":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


class FileWorkflowEventLog:
    """Session-scoped local event log for workflow collaboration runtime."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        session_id: str,
        event_type: str,
        layer: str = "L4.multi_agent_runtime",
        subject_ref: str = "",
        causation_ref: str = "",
        payload: Mapping[str, Any] | None = None,
    ) -> WorkflowSessionEvent:
        event = WorkflowSessionEvent(
            session_id=str(session_id or "").strip(),
            event_type=str(event_type or "").strip(),
            layer=str(layer or "L4.multi_agent_runtime").strip() or "L4.multi_agent_runtime",
            subject_ref=str(subject_ref or session_id or "").strip(),
            causation_ref=str(causation_ref or "").strip(),
            payload=dict(payload or {}),
        )
        path = self.event_log_path(event.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def list_events(self, session_id: str, *, event_type: str = "") -> list[WorkflowSessionEvent]:
        path = self.event_log_path(session_id)
        if not path.exists():
            return []
        target_type = str(event_type or "").strip()
        events: list[WorkflowSessionEvent] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                event = WorkflowSessionEvent.from_dict(payload if isinstance(payload, Mapping) else {})
                if target_type and event.event_type != target_type:
                    continue
                events.append(event)
        return events

    def event_log_path(self, session_id: str) -> Path:
        normalized = str(session_id or "").strip()
        if not normalized:
            raise ValueError("session_id is required")
        return self.root_dir / normalized / "events.jsonl"
