from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from .state import now_text


@dataclass(slots=True)
class FlowUiEvent:
    kind: str
    lane: str = ""
    family: str = ""
    title: str = ""
    flow_id: str = ""
    phase: str = ""
    attempt_no: int = 0
    created_at: str = field(default_factory=now_text)
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    refs: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    display_priority: int = 0
    event_id: str = field(default_factory=lambda: f"flow_ui_evt_{uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": str(self.kind or "").strip(),
            "lane": str(self.lane or "").strip(),
            "family": str(self.family or "").strip(),
            "title": str(self.title or "").strip(),
            "flow_id": str(self.flow_id or "").strip(),
            "phase": str(self.phase or "").strip(),
            "attempt_no": int(self.attempt_no or 0),
            "created_at": str(self.created_at or "").strip(),
            "message": str(self.message or ""),
            "payload": dict(self.payload or {}),
            "refs": dict(self.refs or {}),
            "raw_text": str(self.raw_text or ""),
            "display_priority": int(self.display_priority or 0),
        }


FlowUiEventCallback = Callable[[FlowUiEvent], None]
FlowLifecycleHook = Callable[[str, FlowUiEvent], None]


def build_flow_ui_event(
    *,
    kind: str,
    lane: str = "",
    family: str = "",
    title: str = "",
    flow_id: str = "",
    phase: str = "",
    attempt_no: int = 0,
    message: str = "",
    payload: dict[str, Any] | None = None,
    refs: dict[str, Any] | None = None,
    raw_text: str = "",
    display_priority: int = 0,
) -> FlowUiEvent:
    return FlowUiEvent(
        kind=str(kind or "").strip(),
        lane=str(lane or "").strip(),
        family=str(family or "").strip(),
        title=str(title or "").strip(),
        flow_id=str(flow_id or "").strip(),
        phase=str(phase or "").strip(),
        attempt_no=int(attempt_no or 0),
        message=str(message or ""),
        payload=dict(payload or {}),
        refs=dict(refs or {}),
        raw_text=str(raw_text or ""),
        display_priority=int(display_priority or 0),
    )


def invoke_flow_hook(hook: FlowLifecycleHook | None, hook_name: str, event: FlowUiEvent) -> None:
    if not callable(hook):
        return
    try:
        hook(str(hook_name or "").strip(), event)
    except Exception:
        return
