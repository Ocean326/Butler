from __future__ import annotations

from dataclasses import dataclass

from rich.padding import Padding
from rich.text import Text
from textual.widgets import RichLog

PALETTE_WHITE = "#c0caf5"
PALETTE_BLUE = "#7aa2f7"
PALETTE_BLUE_SOFT = "#7dcfff"
PALETTE_GREEN = "#9ece6a"
PALETTE_PINK = "#bb9af7"
PALETTE_PINK_SOFT = "#f7768e"
PALETTE_MUTED = "#565f89"

DEFAULT_BODY_STYLE = PALETTE_WHITE
SECTION_TITLE_STYLE = f"bold {PALETTE_BLUE}"
GROUP_TITLE_STYLE = f"dim {PALETTE_BLUE}"
BODY_STYLE_BY_TONE = {
    "default": DEFAULT_BODY_STYLE,
    "system": PALETTE_BLUE,
    "input": PALETTE_BLUE_SOFT,
    "output": DEFAULT_BODY_STYLE,
    "workflow": DEFAULT_BODY_STYLE,
    "raw_output": DEFAULT_BODY_STYLE,
    "raw_meta": PALETTE_BLUE_SOFT,
    "raw_success": PALETTE_GREEN,
    "raw_error": PALETTE_PINK_SOFT,
    "decision": PALETTE_GREEN,
    "approval": PALETTE_PINK,
    "handoff": PALETTE_PINK,
    "action": PALETTE_BLUE,
    "artifact": PALETTE_BLUE_SOFT,
    "phase": PALETTE_BLUE,
    "warning": PALETTE_PINK,
    "error": PALETTE_PINK_SOFT,
    "muted": PALETTE_MUTED,
}
NEAR_BOTTOM_MIN_LINES = 6
NEAR_BOTTOM_HEIGHT_DIVISOR = 3


@dataclass(frozen=True)
class TranscriptGroupKey:
    lane: str
    family: str

    @property
    def title(self) -> str:
        lane = self.lane or "system"
        family = self.family or "event"
        return f"[{lane}/{family}]"


class TranscriptFormatter:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._active_group: TranscriptGroupKey | None = None
        self._has_content = False

    def _group_title_style(self, key: TranscriptGroupKey) -> str:
        if key.family == "decision":
            return f"dim {PALETTE_GREEN}"
        if key.family in {"approval", "handoff"}:
            return f"dim {PALETTE_PINK}"
        if key.family in {"artifact", "action", "phase", "run", "status", "settings", "manage", "command", "preflight", "launcher"}:
            return f"dim {PALETTE_BLUE}"
        if key.family == "raw_execution":
            return f"dim {PALETTE_MUTED}"
        if key.family in {"error", "risk"}:
            return f"dim {PALETTE_PINK_SOFT}"
        if key.lane == "system":
            return f"dim {PALETTE_MUTED}"
        return GROUP_TITLE_STYLE

    def group_title_text(self, key: TranscriptGroupKey) -> Text:
        return Text(key.title, style=self._group_title_style(key))

    def section_title_text(self, title: str) -> Text:
        return Text(str(title or "").strip(), style=SECTION_TITLE_STYLE)

    def body_text(self, body: str, *, tone: str = "default") -> Text:
        return Text(str(body or ""), style=BODY_STYLE_BY_TONE.get(str(tone or "").strip(), DEFAULT_BODY_STYLE))

    def _write_blank_line(self, transcript: RichLog) -> None:
        transcript.write(Text(""))

    def near_bottom_threshold(self, transcript: RichLog) -> int:
        height = 0
        container = getattr(transcript, "container_size", None)
        if container is not None:
            height = int(getattr(container, "height", 0) or 0)
        if height <= 0:
            size = getattr(transcript, "size", None)
            height = int(getattr(size, "height", 0) or 0)
        return max(NEAR_BOTTOM_MIN_LINES, height // NEAR_BOTTOM_HEIGHT_DIVISOR)

    def is_near_bottom(self, transcript: RichLog) -> bool:
        scroll_offset = getattr(transcript, "scroll_offset", None)
        max_scroll_y = int(getattr(transcript, "max_scroll_y", 0) or 0)
        current_scroll_y = int(getattr(scroll_offset, "y", 0) or 0)
        return max_scroll_y - current_scroll_y <= self.near_bottom_threshold(transcript)

    def _should_snap_to_end(self, transcript: RichLog) -> bool:
        if not bool(getattr(transcript, "auto_scroll", False)):
            return False
        if bool(getattr(transcript, "is_vertical_scrollbar_grabbed", False)):
            return False
        return self.is_near_bottom(transcript)

    def _snap_to_end(self, transcript: RichLog, *, should_snap: bool) -> None:
        if not should_snap:
            return
        transcript.scroll_end(animate=False, immediate=True, x_axis=False)

    def write_section(self, transcript: RichLog, *, title: str, body: str, tone: str = "default") -> None:
        title_text = str(title or "").strip()
        body_text = str(body or "").rstrip()
        if not title_text and not body_text:
            return
        should_snap = self._should_snap_to_end(transcript)
        if self._has_content:
            self._write_blank_line(transcript)
        if title_text:
            transcript.write(self.section_title_text(title_text))
        if body_text:
            transcript.write(Padding(self.body_text(body_text, tone=tone), (0, 0, 0, 1)))
        self._active_group = None
        self._has_content = True
        self._snap_to_end(transcript, should_snap=should_snap)

    def write_group(self, transcript: RichLog, *, lane: str, family: str, body: str, tone: str = "default") -> None:
        body_text = str(body or "").rstrip("\n")
        if not body_text:
            return
        should_snap = self._should_snap_to_end(transcript)
        key = TranscriptGroupKey(
            lane=str(lane or "").strip().lower() or "system",
            family=str(family or "").strip().lower() or "event",
        )
        if self._has_content and key != self._active_group:
            self._write_blank_line(transcript)
        if key != self._active_group:
            transcript.write(self.group_title_text(key))
        transcript.write(Padding(self.body_text(body_text, tone=tone), (0, 0, 0, 1)))
        self._active_group = key
        self._has_content = True
        self._snap_to_end(transcript, should_snap=should_snap)

    def write_note(self, transcript: RichLog, *, family: str, body: str, tone: str = "default", lane: str = "system") -> None:
        self.write_group(transcript, lane=lane, family=family, body=body, tone=tone)
