from __future__ import annotations

import re
import threading
import time
from math import ceil
from datetime import datetime
from argparse import Namespace
from typing import Any

from .controller import FlowTuiController
from .manage_interaction import (
    FlowCommandSuggester,
    ManageMentionPickerState,
    ManagePromptRequest,
    has_manage_prompt_token,
    manage_prompt_token,
    parse_manage_prompt,
    replace_manage_prompt_token,
    split_manage_prompt,
)
from .theme import FLOW_TUI_CSS
from .transcript import TranscriptFormatter

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual import events
from textual.message import Message
from textual.screen import ModalScreen
from textual.suggester import SuggestionReady
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, RichLog, Static, TextArea

from butler_main.butler_flow.constants import (
    EXECUTION_MODE_COMPLEX,
    EXECUTION_MODE_MEDIUM,
    EXECUTION_MODE_SIMPLE,
    PROJECT_LOOP_KIND,
    SINGLE_GOAL_KIND,
)
from butler_main.butler_flow.events import FlowUiEvent
from butler_main.butler_flow.models import PreparedFlowRun

TRANSCRIPT_FILTERS = ("all", "assistant", "system", "judge", "operator", "supervisor")
HISTORY_STEP_PREVIEW_LIMIT = 6
WORKING_DOT_FRAMES = ("·", "•", "◦", "∙", "•", "·")
WORKING_WORD_FRAMES = ("Working", "WOrking", "WoRking", "WorKing", "WorkIng", "WorkiNg", "WorkinG")


class UiEventMessage(Message):
    def __init__(self, event: FlowUiEvent) -> None:
        super().__init__()
        self.event = event


class RunFinishedMessage(Message):
    def __init__(self, flow_id: str, return_code: int) -> None:
        super().__init__()
        self.flow_id = str(flow_id or "").strip()
        self.return_code = int(return_code or 0)


class RunErroredMessage(Message):
    def __init__(self, flow_id: str, error_text: str) -> None:
        super().__init__()
        self.flow_id = str(flow_id or "").strip()
        self.error_text = str(error_text or "").strip()


class DesignBuildMessage(Message):
    def __init__(self, *, payload: dict[str, Any], error_text: str = "") -> None:
        super().__init__()
        self.payload = dict(payload or {})
        self.error_text = str(error_text or "").strip()


class ManageChatMessage(Message):
    def __init__(self, *, request: ManagePromptRequest, payload: dict[str, Any], error_text: str = "") -> None:
        super().__init__()
        self.request = request
        self.payload = dict(payload or {})
        self.error_text = str(error_text or "").strip()


class ManageFlowMessage(Message):
    def __init__(self, *, manage_target: str, payload: dict[str, Any], error_text: str = "") -> None:
        super().__init__()
        self.manage_target = str(manage_target or "").strip()
        self.payload = dict(payload or {})
        self.error_text = str(error_text or "").strip()


class ConfirmScreen(ModalScreen[bool]):
    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = str(prompt or "").strip()

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._prompt, classes="panel-title"),
            Horizontal(
                Button("Confirm", variant="primary", id="confirm"),
                Button("Cancel", variant="default", id="cancel"),
            ),
            id="confirm-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


class PasteAwareInput(TextArea):
    paste_char_threshold = 200
    min_visible_rows = 1
    max_visible_rows = 6
    wrap_reserve_chars = 2
    _PASTE_PLACEHOLDER_RE = re.compile(r"\[\d+ characters(?: #\d+)?\]")

    def __init__(self, text: str = "", *, placeholder: str = "", suggester=None, **kwargs) -> None:
        super().__init__(
            text=text,
            soft_wrap=True,
            tab_behavior="focus",
            show_line_numbers=False,
            **kwargs,
        )
        self.placeholder = str(placeholder or "").strip()
        self.tooltip = self.placeholder or None
        self.suggester = suggester
        self._suggestion = ""
        self._pending_pastes: dict[str, str] = {}

    def resolved_value(self) -> str:
        text = str(self.value or "")
        if not text or not self._pending_pastes:
            return text
        return self._PASTE_PLACEHOLDER_RE.sub(lambda match: self._pending_pastes.get(match.group(0), match.group(0)), text)

    def _next_paste_placeholder(self, char_count: int) -> str:
        base = f"[{char_count} characters]"
        existing = set(self._pending_pastes)
        candidate = base
        suffix = 2
        while candidate in existing or candidate in self.value:
            candidate = f"{base} #{suffix}"
            suffix += 1
        return candidate

    @property
    def value(self) -> str:
        return str(self.text or "")

    @value.setter
    def value(self, value: str) -> None:
        self.load_text(str(value or ""))
        self.cursor_position = len(self.value)

    @property
    def cursor_position(self) -> int:
        row, column = self.cursor_location
        lines = self.value.split("\n")
        return sum(len(line) + 1 for line in lines[:row]) + column

    @cursor_position.setter
    def cursor_position(self, value: int) -> None:
        target = max(0, int(value or 0))
        offset = 0
        lines = self.value.split("\n")
        for row, line in enumerate(lines):
            line_length = len(line)
            if target <= offset + line_length:
                self.move_cursor((row, target - offset), select=False)
                return
            offset += line_length + 1
        last_row = max(0, len(lines) - 1)
        self.move_cursor((last_row, len(lines[last_row]) if lines else 0), select=False)

    def insert_text_at_cursor(self, text: str) -> None:
        self.insert(str(text or ""))

    def action_cursor_right(self) -> None:
        if self.cursor_position >= len(self.value) and self._suggestion:
            self.value = self._suggestion
            self.cursor_position = len(self.value)
            return
        row, column = self.cursor_location
        current_line = self.document[row] if row < self.document.line_count else ""
        if column < len(current_line):
            self.move_cursor((row, column + 1), select=False)
            return
        if row + 1 < self.document.line_count:
            self.move_cursor((row + 1, 0), select=False)

    def _prune_pending_pastes(self) -> None:
        current = self.value
        if self._pending_pastes:
            self._pending_pastes = {
                placeholder: actual
                for placeholder, actual in self._pending_pastes.items()
                if placeholder in current
            }

    def _wrapped_line_count(self) -> int:
        width = int(getattr(self.content_size, "width", 0) or getattr(self.size, "width", 0) or 0)
        wrap_width = max(8, width - self.wrap_reserve_chars)
        lines = self.value.split("\n") or [""]
        return max(1, sum(max(1, ceil(max(len(line), 1) / wrap_width)) for line in lines))

    def _refresh_visual_height(self) -> None:
        if not self.is_mounted:
            return
        rows = max(self.min_visible_rows, min(self.max_visible_rows, self._wrapped_line_count()))
        self.styles.height = rows + 2
        if rows >= self.max_visible_rows:
            self.scroll_cursor_visible(animate=False)

    def _on_paste(self, event: events.Paste) -> None:
        text = str(event.text or "").replace("\r\n", "\n").replace("\r", "\n")
        char_count = len(text)
        if text and char_count > self.paste_char_threshold:
            placeholder = self._next_paste_placeholder(char_count)
            self._pending_pastes[placeholder] = text
            self.insert_text_at_cursor(placeholder)
            event.stop()
            return
        self.insert_text_at_cursor(text)
        event.stop()

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            if self._delegate_enter_to_app():
                return
            event.prevent_default()
            event.stop()
            self.post_message(Input.Submitted(self, self.value, None).set_sender(self))
            return
        if event.key in {"up", "down", "escape"} and self._delegate_navigation_to_app():
            return
        await super()._on_key(event)

    def _delegate_navigation_to_app(self) -> bool:
        app = getattr(self, "app", None)
        if app is None:
            return False
        if getattr(app, "_view_mode", "") == "flows" and getattr(app, "_flows_screen_mode", "") == "manage" and app._manage_picker.is_open:
            return True
        if getattr(app, "_view_mode", "") == "history":
            return True
        return False

    def _delegate_enter_to_app(self) -> bool:
        app = getattr(self, "app", None)
        if app is None:
            return False
        return bool(getattr(app, "_view_mode", "") == "flows" and getattr(app, "_flows_screen_mode", "") == "manage" and app._manage_picker.is_open)

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh_visual_height)

    def on_resize(self, event: events.Resize) -> None:
        self.call_after_refresh(self._refresh_visual_height)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area is not self:
            return
        self._prune_pending_pastes()
        self._refresh_visual_height()
        self._suggestion = ""
        if self.suggester and self.value:
            self.run_worker(self.suggester._get_suggestion(self, self.value))
        self.post_message(Input.Changed(self, self.value, None).set_sender(self))

    async def _on_suggestion_ready(self, event: SuggestionReady) -> None:
        if event.value == self.value:
            self._suggestion = event.suggestion


class ButlerFlowTuiApp(App[int]):
    CSS = FLOW_TUI_CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_snapshot", "Refresh"),
        Binding("enter", "open_selected", "Open"),
        Binding("ctrl+p", "pause_flow", "Pause"),
        Binding("ctrl+r", "resume_flow", "Resume"),
        Binding("ctrl+t", "retry_phase", "Retry"),
        Binding("ctrl+x", "abort_flow", "Abort"),
    ]

    def __init__(self, *, run_prompt_receipt_fn, initial_args: Namespace, initial_mode: str) -> None:
        super().__init__()
        self._initial_args = initial_args
        self._initial_mode = str(initial_mode or "launcher").strip() or "launcher"
        self._controller = FlowTuiController(run_prompt_receipt_fn=run_prompt_receipt_fn, event_callback=self._emit_from_thread)
        self._current_config = str(getattr(initial_args, "config", "") or "").strip() or None
        self._manage_picker = ManageMentionPickerState(visible_limit=7)
        self._command_suggester = FlowCommandSuggester(
            command_provider=self._controller.command_suggestions,
            asset_provider=self._manage_asset_keys,
            asset_index_provider=lambda: self._manage_picker.selected_index,
            case_sensitive=False,
        )
        self._selected_flow_id = ""
        self._current_flow_id = ""
        self._view_mode = "history"
        self._workspace_detail_mode = "preview"
        self._setup_stage = ""
        self._setup_cursor_key = ""
        self._setup_goal = ""
        self._setup_guard = ""
        self._setup_mode = ""
        self._setup_level = ""
        self._setup_catalog_flow = ""
        self._setup_free_flow_id = ""
        self._setup_error = ""
        self._design_stage = ""
        self._design_busy = False
        self._design_request = ""
        self._design_payload: dict[str, Any] = {}
        self._design_flow_id = ""
        self._design_origin = ""
        self._design_error = ""
        self._design_cursor_key = ""
        self._flows_screen_mode = "manage"
        self._manage_cursor_asset_key = ""
        self._manage_return_to_setup = False
        self._manage_seed_instruction = ""
        self._manage_notes: list[dict[str, str]] = []
        self._manage_flow_busy = False
        self._manage_chat_busy = False
        self._manage_chat_queue: list[ManagePromptRequest] = []
        self._manage_chat_session_id = ""
        self._manage_chat_started_at = 0.0
        self._attached_run_active = False
        self._history_cursor_flow_id = ""
        self._flow_view_mode = "supervisor"
        self._inspector_open = False
        self._inspector_event_id = ""
        self._settings_cursor_key = "auto_follow"
        self._session_preferences: dict[str, Any] = {
            "auto_follow": True,
            "show_runtime_events": True,
            "transcript_filter": "all",
        }
        self._transcript_formatter = TranscriptFormatter()
        self._manage_transcript_formatter = TranscriptFormatter()
        self._transcript_event_ids: set[str] = set()
        self._flow_transcript_scroll_positions: dict[tuple[str, str], int] = {}
        self._ui_tick_index = 0
        self._latest_segment = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Vertical(
            Horizontal(
                Horizontal(
                    VerticalScroll(
                        Static("", id="workspace-header"),
                        Static("", id="workspace-list"),
                        id="flow-sidebar",
                    ),
                    Vertical(
                        Static("", id="flow-header"),
                        RichLog(id="transcript", wrap=True, highlight=True, markup=False),
                        id="flow-console",
                    ),
                    VerticalScroll(
                        Static("", id="inspector-header"),
                        Static("", id="inspector-body"),
                        id="inspector-panel",
                    ),
                    id="flow-screen",
                ),
                Horizontal(
                    Vertical(
                        Static("", id="setup-header"),
                        ListView(id="setup-list"),
                        Static("", id="setup-hint"),
                        id="setup-left",
                    ),
                    VerticalScroll(
                        Static("", id="setup-detail"),
                        id="setup-right",
                    ),
                    id="setup-screen",
                ),
                Horizontal(
                    Vertical(
                        Static("", id="history-header"),
                        ListView(id="history-list"),
                        Static("", id="history-hint"),
                        id="history-left",
                    ),
                    VerticalScroll(
                        Static("", id="history-detail"),
                        id="history-right",
                    ),
                    id="history-screen",
                ),
                Horizontal(
                    Vertical(
                        Static("", id="manage-header"),
                        RichLog(id="manage-transcript", wrap=True, highlight=True, markup=False),
                        Static("", id="manage-hint"),
                        id="manage-screen",
                    ),
                    Horizontal(
                        Vertical(
                            Static("", id="flows-header"),
                            ListView(id="flows-list"),
                            Static("", id="flows-hint"),
                            id="flows-left",
                        ),
                        VerticalScroll(
                            Static("", id="flows-detail"),
                            id="flows-right",
                        ),
                        id="flows-design-screen",
                    ),
                    id="flows-screen",
                ),
                Horizontal(
                    Vertical(
                        Static("", id="settings-status"),
                        ListView(id="settings-list"),
                        Static("", id="settings-hint"),
                        id="settings-left",
                    ),
                    VerticalScroll(
                        Static("", id="settings-preview"),
                        id="settings-right",
                    ),
                    id="settings-screen",
                ),
                id="body",
            ),
            Vertical(
                Static("", id="action-bar"),
                PasteAwareInput(
                    placeholder="Slash commands: /new | /manage | /resume [flow_id|last] | /inspect <flow_id> | /back | /settings · Manage: $template:<id> <instruction>",
                    id="command-input",
                    suggester=self._command_suggester,
                ),
                Static("", id="mention-picker"),
                id="composer",
            ),
            id="root",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.title = "butler-flow"
        self.sub_title = "operator shell"
        self.query_one("#flow-header", Static).display = False
        self.query_one("#transcript", RichLog).styles.height = "1fr"
        self.query_one("#manage-transcript", RichLog).styles.height = "1fr"
        self.query_one("#mention-picker", Static).display = False
        inspector_panel = self.query_one("#inspector-panel", VerticalScroll)
        inspector_panel.styles.width = 42
        inspector_panel.styles.min_width = 34
        self._refresh_snapshot()
        self._set_view_mode(self._view_mode)
        if self._selected_flow_id:
            self._focus_flow(self._selected_flow_id)
        self.set_interval(1.0, self._poll_runtime_surface)
        self.call_after_refresh(self._start_initial_route)

    def _start_initial_route(self) -> None:
        if self._initial_mode in {"manage", "flows"}:
            self._open_manage_center()
            return
        if self._initial_mode in {"run", "new"}:
            self._reset_setup_state()
            goal = str(getattr(self._initial_args, "goal", "") or "").strip()
            guard = str(getattr(self._initial_args, "guard_condition", "") or "").strip()
            kind = str(getattr(self._initial_args, "kind", "") or "").strip()
            execution_mode = str(getattr(self._initial_args, "execution_mode", "") or "").strip()
            if goal:
                self._setup_goal = goal
            if guard:
                self._setup_guard = guard
            if kind == SINGLE_GOAL_KIND:
                self._setup_mode = "single"
            elif kind:
                self._setup_mode = "flow"
                self._setup_catalog_flow = kind
            if execution_mode in {EXECUTION_MODE_SIMPLE, EXECUTION_MODE_MEDIUM, EXECUTION_MODE_COMPLEX}:
                self._setup_level = execution_mode
            self._set_view_mode("setup")
            self._refresh_setup_screen()
            self.call_after_refresh(self._focus_active_view_control)
            return
        if self._initial_mode == "resume":
            prepared = self._controller.prepare_resume(
                config=self._current_config,
                flow_id=str(getattr(self._initial_args, "flow_id", "") or getattr(self._initial_args, "workflow_id", "") or "").strip(),
                use_last=bool(getattr(self._initial_args, "last", False)),
                codex_session_id=str(getattr(self._initial_args, "codex_session_id", "") or "").strip(),
                kind=str(getattr(self._initial_args, "kind", "") or "single_goal").strip() or "single_goal",
                goal=str(getattr(self._initial_args, "goal", "") or "").strip(),
                guard_condition=str(getattr(self._initial_args, "guard_condition", "") or "").strip(),
                execution_mode=str(getattr(self._initial_args, "execution_mode", "") or "").strip() or None,
                role_pack=str(getattr(self._initial_args, "role_pack", "") or "").strip() or None,
                max_attempts=getattr(self._initial_args, "max_attempts", None),
                max_phase_attempts=getattr(self._initial_args, "max_phase_attempts", None),
            )
            self._begin_run(prepared, stream_enabled=not bool(getattr(self._initial_args, "no_stream", False)))

    def _poll_runtime_surface(self) -> None:
        self._ui_tick_index += 1
        try:
            if self._view_mode == "flow" and self._target_flow_id():
                self._refresh_snapshot()
                return
            if self._view_mode == "history" and self._selected_flow_id:
                self._refresh_snapshot()
                return
            self._set_action_bar()
        except NoMatches:
            return

    def _working_dot(self) -> str:
        return WORKING_DOT_FRAMES[self._ui_tick_index % len(WORKING_DOT_FRAMES)]

    def _working_word(self) -> str:
        return WORKING_WORD_FRAMES[self._ui_tick_index % len(WORKING_WORD_FRAMES)]

    def _format_elapsed(self, elapsed_seconds: int) -> str:
        total = max(0, int(elapsed_seconds or 0))
        minutes, seconds = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}h {minutes:02d}m {seconds:02d}s"
        return f"{minutes}m {seconds:02d}s"

    def _parse_clock_text(self, value: str) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def _flow_working_badge(self) -> str:
        flow_id = self._target_flow_id()
        if not flow_id:
            return ""
        try:
            payload = self._controller.status_payload(config=self._current_config, flow_id=flow_id)
        except Exception:
            return ""
        effective_status = str(payload.get("effective_status") or "").strip().lower()
        if effective_status != "running":
            return ""
        runtime_snapshot = dict(payload.get("runtime_snapshot") or {})
        started_at = self._parse_clock_text(str(runtime_snapshot.get("updated_at") or ""))
        if started_at is None:
            started_at = self._parse_clock_text(str(dict(payload.get("flow_state") or {}).get("updated_at") or ""))
        elapsed_seconds = 0
        if started_at is not None:
            elapsed_seconds = max(0, int((datetime.now() - started_at).total_seconds()))
        return f"{self._working_dot()}{self._working_word()} ({self._format_elapsed(elapsed_seconds)})"

    def _manage_working_badge(self) -> str:
        if not self._manage_chat_busy:
            return ""
        elapsed_seconds = 0
        if self._manage_chat_started_at > 0:
            elapsed_seconds = max(0, int(time.time() - self._manage_chat_started_at))
        return f"{self._working_dot()}{self._working_word()} ({self._format_elapsed(elapsed_seconds)})"

    def _active_working_badge(self) -> str:
        if self._view_mode == "flow":
            return self._flow_working_badge()
        if self._view_mode == "flows" and self._flows_screen_mode == "manage":
            return self._manage_working_badge()
        return ""

    def _set_action_bar(self) -> None:
        try:
            action_bar = self.query_one("#action-bar", Static)
        except NoMatches:
            return
        working_badge = self._active_working_badge()
        if self._view_mode in {"setup", "flows"}:
            hint = "enter select"
            if self._view_mode == "flows" and self._flows_screen_mode == "manage":
                hint = "enter send"
            text = f"q quit  r refresh  {hint}"
            mode_label = "manage" if self._view_mode == "flows" and self._flows_screen_mode == "manage" else self._view_mode
            suffix = f"  {working_badge}" if working_badge else ""
            action_bar.update(f"mode={mode_label}  {text}{suffix}")
            return
        enter_hint = {
            "flow": "refresh",
            "history": "open",
            "settings": "toggle",
        }.get(self._view_mode, "open")
        current = self._controller.action_bar_text(
            config=self._current_config,
            flow_id=self._target_flow_id(),
            enter_hint=enter_hint,
        )
        if self._view_mode == "history":
            mode = "workspace"
        else:
            mode = self._view_mode
        suffix = ""
        if self._view_mode == "flow":
            hint = self._flow_view_hint_text(flow_id=self._target_flow_id())
            suffix = f"  view={self._flow_view_mode}"
            if hint:
                suffix = f"{suffix}  {hint}"
        if working_badge:
            suffix = f"{suffix}  {working_badge}"
        action_bar.update(f"mode={mode}  {current}{suffix}")

    def _set_view_mode(self, mode: str) -> None:
        target = str(mode or "flow").strip().lower() or "flow"
        if target not in {"flow", "history", "flows", "settings", "setup"}:
            target = "flow"
        if self._view_mode == "flow" and target != "flow":
            self._remember_flow_transcript_scroll()
        self._view_mode = target
        self.query_one("#flow-screen", Horizontal).display = target == "flow"
        self.query_one("#setup-screen", Horizontal).display = target == "setup"
        self.query_one("#history-screen", Horizontal).display = target == "history"
        self.query_one("#flows-screen", Horizontal).display = target == "flows"
        self.query_one("#settings-screen", Horizontal).display = target == "settings"
        self._set_action_bar()

    def _set_flows_screen_mode(self, mode: str) -> None:
        target = str(mode or "manage").strip().lower() or "manage"
        if target not in {"manage", "design"}:
            target = "manage"
        self._flows_screen_mode = target
        self.query_one("#manage-screen", Vertical).display = target == "manage"
        self.query_one("#flows-design-screen", Horizontal).display = target == "design"

    def _focus_command_input(self) -> None:
        self._command_input().focus()

    def _command_input(self) -> PasteAwareInput:
        return self.query_one("#command-input", PasteAwareInput)

    def _focus_command_input_with_text(self, text: str = "") -> None:
        command_input = self._command_input()
        command_input.focus()
        if text:
            command_input.insert_text_at_cursor(text)

    def _command_input_has_focus(self) -> bool:
        return self.screen.focused is self._command_input()

    def _focus_history_list(self) -> None:
        self.query_one("#history-list", ListView).focus()

    def _focus_setup_list(self) -> None:
        self.query_one("#setup-list", ListView).focus()

    def _focus_settings_list(self) -> None:
        self.query_one("#settings-list", ListView).focus()

    def _focus_flows_list(self) -> None:
        self.query_one("#flows-list", ListView).focus()

    def _focus_active_view_control(self) -> None:
        if self._view_mode == "history":
            self._focus_history_list()
            return
        if self._view_mode == "settings":
            self._focus_settings_list()
            return
        if self._view_mode == "setup":
            if self._setup_stage in {"goal", "guard"}:
                self._focus_command_input()
            else:
                self._focus_setup_list()
            return
        if self._view_mode == "flows":
            if self._flows_screen_mode == "manage":
                self._focus_command_input()
                return
            if (self._design_stage or "proposal") == "proposal":
                self._focus_command_input()
            else:
                self._focus_flows_list()
            return
        self._focus_command_input()

    def _flow_rows(self) -> list[dict[str, Any]]:
        snapshot = self._controller.workspace_payload(config=self._current_config)
        return list((snapshot.get("flows") or {}).get("items") or [])

    def _manage_rows(self) -> list[dict[str, Any]]:
        snapshot = self._controller.manage_center_payload(config=self._current_config)
        return list((snapshot.get("assets") or {}).get("items") or [])

    def _manage_asset_keys(self) -> list[str]:
        keys = []
        for row in self._manage_rows():
            asset_key = str(row.get("asset_key") or "").strip()
            if asset_key:
                keys.append(asset_key)
        return keys

    def _selected_flow_status(self, flow_id: str) -> str:
        target = str(flow_id or "").strip()
        if not target:
            return ""
        payload = self._controller.status_payload(config=self._current_config, flow_id=target)
        return str(
            payload.get("effective_status")
            or dict(payload.get("status") or {}).get("effective_status")
            or dict(payload.get("status") or {}).get("status")
            or payload.get("status")
            or ""
        ).strip()

    def _update_manage_picker(self, text: str | None = None) -> None:
        value = self._command_input().value if text is None else str(text or "")
        self._manage_picker.update(text=value, asset_keys=self._manage_asset_keys())
        picker = self.query_one("#mention-picker", Static)
        if not self._manage_picker.is_open:
            picker.display = False
            picker.update("")
            picker.styles.height = 0
            return
        picker.display = True
        picker.styles.height = self._manage_picker.visible_height
        picker.update(self._manage_picker.render_text())

    def _apply_manage_picker_selection(self) -> bool:
        asset_key = self._manage_picker.selected_candidate
        if not asset_key:
            return False
        command_input = self._command_input()
        updated, changed = replace_manage_prompt_token(command_input.value, asset_key, trailing_space=True)
        if not changed:
            return False
        command_input.value = updated
        command_input.cursor_position = len(command_input.value)
        self._update_manage_picker(command_input.value)
        return True

    def _render_workspace_header(self, *, rows: list[dict[str, Any]]) -> str:
        focused = self._selected_flow_id or self._current_flow_id or "-"
        return "\n".join(
            [
                "Workspace",
                f"focused={focused}",
                f"flows={len(rows)}",
            ]
        )

    def _render_workspace_list(self, *, rows: list[dict[str, Any]], limit: int = 8) -> str:
        if not rows:
            return "No flows found."
        focused = self._selected_flow_id or self._current_flow_id
        lines = ["Recent Flows"]
        for row in list(rows)[: max(1, int(limit or 0))]:
            flow_id = str(row.get("flow_id") or "").strip()
            badge = "*" if flow_id and flow_id == focused else " "
            status = str(row.get("effective_status") or row.get("status") or "-").strip()
            phase = str(row.get("effective_phase") or row.get("current_phase") or "-").strip()
            role_id = str(row.get("active_role_id") or "-").strip()
            approval = str(row.get("approval_state") or "").strip()
            approval_suffix = f" approval={approval}" if approval else ""
            lines.append(f"{badge} {flow_id or '-'}  {status} / {phase}  role={role_id}{approval_suffix}")
        return "\n".join(lines)

    def _render_step_history(self, payload: dict[str, Any], *, limit: int | None = None, title: str = "History Steps") -> str:
        steps = list(payload.get("step_history") or [])
        if isinstance(limit, int) and limit > 0:
            steps = steps[-limit:]
        if not steps:
            return f"{title}\nNo historical steps yet."
        lines = [title]
        for index, step in enumerate(steps, start=1):
            phase = str(step.get("phase") or "-").strip() or "-"
            attempt = int(step.get("attempt_no") or 0)
            decision = str(step.get("decision") or "-").strip() or "-"
            summary = str(step.get("summary") or "-").strip() or "-"
            created_at = str(step.get("created_at") or "").strip()
            stamp = f" @ {created_at}" if created_at else ""
            lines.append(f"{index}. {phase}  attempt={attempt or '-'}  decision={decision}{stamp}")
            lines.append(f"   {summary}")
        return "\n".join(lines)

    def _manage_handoff_lines(self, manage_handoff: dict[str, Any]) -> list[str]:
        manage = dict(manage_handoff or {})
        summary = str(manage.get("summary") or "").strip()
        if not summary:
            return []
        lines = ["", "Manage Handoff", f"manage_summary={summary}"]
        guidance = str(manage.get("operator_guidance") or "").strip()
        if guidance:
            lines.append(f"manage_guidance={guidance}")
        confirmation = str(manage.get("confirmation_prompt") or "").strip()
        if confirmation:
            lines.append(f"manage_confirm={confirmation}")
        managed_at = str(manage.get("managed_at") or "").strip()
        if managed_at:
            lines.append(f"managed_at={managed_at}")
        return lines

    def _format_role_strip(self, payload: dict[str, Any]) -> str:
        role_chips = list(payload.get("role_chips") or [])
        if not role_chips:
            role_chips = list(payload.get("roles") or [])
        if not role_chips:
            return "role_strip=-"
        tokens: list[str] = []
        for role in role_chips:
            item = dict(role or {})
            role_id = str(item.get("role_id") or "").strip()
            if not role_id:
                continue
            state = str(item.get("state") or "").strip()
            marker = "*" if bool(item.get("is_active")) or state == "active" else ""
            suffix = ""
            if state == "receiving_handoff":
                suffix = "[in]"
            elif state == "handoff_source":
                suffix = "[out]"
            tokens.append(f"{role_id}{marker}{suffix}")
        if not tokens:
            return "role_strip=-"
        return "role_strip=" + " ".join(tokens)

    def _format_handoff_summary(self, payload: dict[str, Any]) -> str:
        if not payload:
            return "latest_handoff=-"
        summary = str(payload.get("summary") or "").strip()
        from_role = str(payload.get("from_role_id") or "").strip()
        to_role = str(payload.get("to_role_id") or "").strip()
        status = str(payload.get("status") or "").strip()
        handoff_id = str(payload.get("handoff_id") or "").strip()
        route = " -> ".join(part for part in (from_role, to_role) if part)
        parts = []
        if route:
            parts.append(route)
        if status:
            parts.append(status)
        if summary:
            parts.append(summary)
        detail = " | ".join(parts) if parts else "-"
        if handoff_id:
            detail = f"{detail} ({handoff_id})"
        return f"latest_handoff={detail}"

    def _event_lane(self, entry: dict[str, Any]) -> str:
        return str(entry.get("lane") or "").strip().lower()

    def _event_matches_flow_view(self, entry: dict[str, Any]) -> bool:
        lane = self._event_lane(entry)
        if self._view_mode != "flow":
            return True
        if self._flow_view_mode == "supervisor":
            return lane in {"supervisor", "system", ""}
        return lane in {"workflow", "system", ""}

    def _current_flow_payload(self, flow_id: str) -> dict[str, Any]:
        return self._controller.single_flow_payload(config=self._current_config, flow_id=flow_id)

    def _current_flow_events(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(entry or {}) for entry in list(payload.get("timeline") or []) if self._event_matches_flow_view(dict(entry or {}))]

    def _render_supervisor_header(self, payload: dict[str, Any]) -> str:
        supervisor_view = dict(payload.get("supervisor_view") or {})
        header = dict(supervisor_view.get("header") or {})
        pointers = dict(supervisor_view.get("pointers") or {})
        if not header:
            return "Supervisor View\nNo flow selected."
        lines = [
            "Supervisor View",
            f"flow_id={header.get('flow_id') or '-'}",
            f"kind={header.get('workflow_kind') or '-'}",
            f"status={header.get('status') or '-'}",
            f"phase={header.get('phase') or '-'}",
            f"goal={header.get('goal') or '-'}",
            f"guard={header.get('guard_condition') or '-'}",
            f"active_role={header.get('active_role_id') or '-'}",
            f"approval_state={header.get('approval_state') or '-'}",
        ]
        risk_level = str(pointers.get("risk_level") or "").strip()
        if risk_level:
            lines.append(f"risk_level={risk_level}")
        autonomy = str(pointers.get("autonomy_profile") or "").strip()
        if autonomy:
            lines.append(f"autonomy_profile={autonomy}")
        latest_handoff = dict(pointers.get("latest_handoff_summary") or {})
        if latest_handoff:
            lines.append(self._format_handoff_summary(latest_handoff))
        return "\n".join(lines)

    def _render_supervisor_prelude(self, payload: dict[str, Any]) -> str:
        supervisor_view = dict(payload.get("supervisor_view") or {})
        header = dict(supervisor_view.get("header") or {})
        pointers = dict(supervisor_view.get("pointers") or {})
        inspector = dict(payload.get("inspector") or {})
        roles = dict(inspector.get("roles") or {})
        latest_handoff = dict(pointers.get("latest_handoff_summary") or roles.get("latest_handoff_summary") or {})
        lines = [
            f"flow_id={header.get('flow_id') or '-'}",
            f"status={header.get('status') or '-'}",
            f"phase={header.get('phase') or '-'}",
            f"active_role={header.get('active_role_id') or '-'}",
            f"approval_state={header.get('approval_state') or '-'}",
        ]
        supervisor_thread_id = str(header.get("supervisor_thread_id") or "").strip()
        if supervisor_thread_id:
            lines.append(f"supervisor_thread={supervisor_thread_id}")
        if latest_handoff:
            lines.append(self._format_handoff_summary(latest_handoff))
        supervisor_session_mode = str(pointers.get("supervisor_session_mode") or "").strip()
        if supervisor_session_mode:
            lines.append(f"supervisor_session_mode={supervisor_session_mode}")
        supervisor_load_profile = str(pointers.get("supervisor_load_profile") or "").strip()
        if supervisor_load_profile:
            lines.append(f"supervisor_load_profile={supervisor_load_profile}")
        runtime_elapsed = int(pointers.get("runtime_elapsed_seconds") or 0)
        max_runtime = int(pointers.get("max_runtime_seconds") or 0)
        if max_runtime > 0:
            lines.append(f"runtime_budget={runtime_elapsed}s/{max_runtime}s")
        governor = dict(pointers.get("context_governor") or {})
        governor_mode = str(governor.get("mode") or "").strip()
        if governor_mode:
            lines.append(f"context_governor={governor_mode}")
        queued_updates = list(pointers.get("queued_operator_updates") or [])
        if queued_updates:
            lines.append(f"queued_operator_updates={len(queued_updates)}")
        latest_usage = dict(pointers.get("latest_token_usage") or {})
        input_tokens = int(latest_usage.get("input_tokens") or 0)
        output_tokens = int(latest_usage.get("output_tokens") or 0)
        if input_tokens or output_tokens:
            lines.append(f"latest_tokens=in:{input_tokens} out:{output_tokens}")
        latest_mutation = dict(pointers.get("latest_mutation") or {})
        if latest_mutation:
            lines.append(
                "latest_mutation="
                f"{str(latest_mutation.get('mutation_kind') or latest_mutation.get('kind') or '-').strip() or '-'}"
            )
        return "\n".join(lines)

    def _render_workflow_prelude(self, payload: dict[str, Any]) -> str:
        flow_id = str(payload.get("flow_id") or "-").strip() or "-"
        return "\n".join([f"flow_id={flow_id}"])

    def _render_workflow_header(self, payload: dict[str, Any]) -> str:
        flow_id = str(payload.get("flow_id") or "-").strip() or "-"
        return "\n".join(
            [
                "Workflow View",
                f"flow_id={flow_id}",
                "mixed timeline for workflow events + raw execution output",
            ]
        )

    def _render_inspector(self, payload: dict[str, Any]) -> tuple[str, str]:
        if not self._inspector_open:
            return "Inspector", "closed"
        inspector = dict(payload.get("inspector") or {})
        runtime = dict(inspector.get("runtime") or {})
        roles = dict(inspector.get("roles") or {})
        latest_handoff = dict(roles.get("latest_handoff_summary") or {})
        runtime_plan = dict(runtime.get("runtime_plan") or {})
        strategy_trace = list(runtime.get("strategy_trace") or [])
        prompt_packets = list(runtime.get("prompt_packets") or [])
        mutations = list(runtime.get("mutations") or [])
        lines = [
            "Inspector",
            f"mode={self._flow_view_mode}",
            f"selected_event={self._inspector_event_id or '-'}",
            f"runtime_plan_stage={runtime_plan.get('plan_stage') or '-'}",
            f"runtime_plan_summary={runtime_plan.get('summary') or '-'}",
            self._format_handoff_summary(latest_handoff),
            f"strategy_trace={len(strategy_trace)}",
            f"prompt_packets={len(prompt_packets)}",
            f"mutations={len(mutations)}",
        ]
        return "Inspector", "\n".join(lines)

    def _flow_view_hint_text(self, *, flow_id: str) -> str:
        if not str(flow_id or "").strip():
            return ""
        if self._flow_view_mode == "supervisor":
            return "Shift+Tab: Workflow"
        return "Shift+Tab: Supervisor"

    def _set_flow_view_mode(self, mode: str) -> None:
        token = str(mode or "supervisor").strip().lower() or "supervisor"
        if token not in {"supervisor", "workflow"}:
            token = "supervisor"
        if self._flow_view_mode == token:
            return
        self._remember_flow_transcript_scroll()
        self._flow_view_mode = token
        self._reload_transcript(self._target_flow_id())
        self._refresh_flow_view()
        self._set_action_bar()

    def _latest_handoff_summary(self, handoffs: list[dict[str, Any]]) -> dict[str, Any]:
        if not handoffs:
            return {}

        def _sort_key(row: dict[str, Any]) -> str:
            return str(row.get("consumed_at") or row.get("created_at") or "")

        normalized = sorted((dict(item or {}) for item in handoffs), key=_sort_key)
        pending = [row for row in normalized if str(row.get("status") or "").strip() == "pending"]
        latest = pending[-1] if pending else normalized[-1]
        return {
            "handoff_id": str(latest.get("handoff_id") or "").strip(),
            "from_role_id": str(latest.get("from_role_id") or latest.get("source_role_id") or "").strip(),
            "to_role_id": str(latest.get("to_role_id") or latest.get("target_role_id") or "").strip(),
            "status": str(latest.get("status") or "").strip(),
            "summary": str(latest.get("summary") or "").strip(),
            "created_at": str(latest.get("created_at") or "").strip(),
            "consumed_at": str(latest.get("consumed_at") or "").strip(),
        }

    def _refresh_flow_view(self) -> None:
        workspace_header = self.query_one("#workspace-header", Static)
        workspace_list = self.query_one("#workspace-list", Static)
        flow_header = self.query_one("#flow-header", Static)
        flow_sidebar = self.query_one("#flow-sidebar", VerticalScroll)
        inspector_panel = self.query_one("#inspector-panel", VerticalScroll)
        inspector_header = self.query_one("#inspector-header", Static)
        inspector_body = self.query_one("#inspector-body", Static)
        rows = self._flow_rows()
        workspace_header.update(self._render_workspace_header(rows=rows))
        workspace_list.update(self._render_workspace_list(rows=rows))
        flow_sidebar.display = False
        flow_header.display = False
        flow_id = self._selected_flow_id or self._current_flow_id
        inspector_header.update("")
        inspector_body.update("")
        inspector_panel.display = False
        if not flow_id:
            flow_header.update("")
            return
        flow_header.update("")

    def _render_history_header(self, *, rows: list[dict[str, Any]]) -> str:
        return "\n".join(
            [
                "Workspace Browser",
                f"focused={self._selected_flow_id or '-'}",
                f"items={len(rows)}",
                f"detail={self._workspace_detail_mode}",
                "enter=inspect  left/right=preview|timeline",
            ]
        )

    def _history_detail_payload(self, *, flow_id: str) -> dict[str, Any]:
        target = str(flow_id or "").strip()
        if not target:
            return {}
        return self._controller.detail_payload(config=self._current_config, flow_id=target)

    def _render_history_detail(self, *, row: dict[str, Any], payload: dict[str, Any]) -> str:
        status = dict(payload.get("status") or {})
        flow_state = dict(status.get("flow_state") or {})
        flow_id = str(row.get("flow_id") or "").strip() or "-"
        effective_status = status.get("effective_status") or flow_state.get("status") or row.get("effective_status") or row.get("status") or "-"
        effective_phase = status.get("effective_phase") or flow_state.get("current_phase") or row.get("effective_phase") or row.get("current_phase") or "-"
        workflow_kind = flow_state.get("workflow_kind") or row.get("flow_kind") or "-"
        latest_judge = dict(flow_state.get("latest_judge_decision") or {})
        latest_operator = dict(flow_state.get("last_operator_action") or {})
        role_payload = dict(payload.get("roles") or {})
        handoffs = list(role_payload.get("handoffs") or [])
        latest_handoff = dict(payload.get("multi_agent", {}).get("latest_handoff_summary") or self._latest_handoff_summary(handoffs))
        payload_for_steps = dict(payload)
        receipts = dict(payload.get("receipts") or {})
        payload_for_steps["turns"] = list(receipts.get("turns") or [])
        source_kind = str(flow_state.get("catalog_flow_id") or row.get("catalog_flow_id") or "").strip() or "-"
        completion_summary = str(flow_state.get("last_completion_summary") or "").strip()
        cursor_receipt = dict(flow_state.get("last_cursor_receipt") or {})
        cursor_status = str(cursor_receipt.get("status") or "").strip()
        cursor_summary = str(cursor_receipt.get("summary") or cursor_receipt.get("output_text") or "").strip()
        active_role = str(payload.get("multi_agent", {}).get("active_role_id") or flow_state.get("active_role_id") or "-").strip() or "-"
        timeline = list(payload.get("timeline") or [])
        if self._workspace_detail_mode == "timeline":
            lines = [
                "Runtime Timeline",
                f"flow_id={flow_id}",
                f"status={effective_status}",
                f"phase={effective_phase}",
                f"source={source_kind}",
            ]
            if not timeline:
                lines.append("timeline=empty")
            else:
                for entry in timeline:
                    item = dict(entry or {})
                    stamp = str(item.get("created_at") or "").strip()
                    kind = str(item.get("kind") or "-").strip() or "-"
                    message = str(item.get("message") or "").strip()
                    if not message:
                        payload_text = dict(item.get("payload") or {})
                        message = str(payload_text.get("summary") or payload_text.get("text") or "").strip()
                    if stamp:
                        lines.append(f"{stamp}  [{kind}] {message or '-'}")
                    else:
                        lines.append(f"[{kind}] {message or '-'}")
            return "\n".join(lines)
        terminal_lines = [
            "Terminal Receipt",
            f"terminal_status={effective_status}",
        ]
        if completion_summary:
            terminal_lines.append(f"completion_summary={completion_summary}")
        if cursor_status:
            terminal_lines.append(f"cursor_status={cursor_status}")
        if cursor_summary:
            terminal_lines.append(f"cursor_summary={cursor_summary}")
        recovery_lines = [
            "Recovery",
            f"resume=/resume {flow_id}",
            f"inspect=/inspect {flow_id}",
        ]
        codex_session_id = str(flow_state.get("codex_session_id") or "").strip()
        if codex_session_id:
            recovery_lines.append(f"codex_session_id={codex_session_id}")
        lines = [
            "Runtime Preview",
            f"flow_id={flow_id}",
            f"status={effective_status}",
            f"phase={effective_phase}",
            f"kind={workflow_kind}",
            f"source={source_kind}",
            f"updated_at={row.get('updated_at') or '-'}",
            f"goal={flow_state.get('goal') or row.get('goal') or '-'}",
            f"guard={flow_state.get('guard_condition') or row.get('guard') or '-'}",
            "",
            "Latest Signals",
            f"active_role={active_role}",
            f"last_judge={str(latest_judge.get('decision') or '-').strip() or '-'}",
            f"last_operator={str(latest_operator.get('action_type') or '-').strip() or '-'}",
            "",
            *recovery_lines,
            "",
            *terminal_lines,
            "",
            self._format_handoff_summary(latest_handoff),
            *self._manage_handoff_lines(dict(flow_state.get("manage_handoff") or {})),
            "",
            self._render_step_history(
                payload_for_steps,
                limit=HISTORY_STEP_PREVIEW_LIMIT,
                title="Recent Runtime Steps",
            ),
        ]
        return "\n".join(lines)

    def _update_history_detail(self, *, rows: list[dict[str, Any]]) -> None:
        history_detail = self.query_one("#history-detail", Static)
        selected_row = next((row for row in rows if str(row.get("flow_id") or "").strip() == self._history_cursor_flow_id), rows[0] if rows else {})
        if not selected_row:
            history_detail.update("No flow history available.")
            return
        try:
            payload = self._history_detail_payload(flow_id=str(selected_row.get("flow_id") or "").strip())
        except Exception as exc:
            history_detail.update(f"Workspace detail unavailable: {type(exc).__name__}: {exc}")
            return
        history_detail.update(self._render_history_detail(row=selected_row, payload=payload))

    def _refresh_history_screen(self, *, rows: list[dict[str, Any]]) -> None:
        if not self._history_cursor_flow_id:
            self._history_cursor_flow_id = self._selected_flow_id or (str(rows[0].get("flow_id") or "").strip() if rows else "")
        history_header = self.query_one("#history-header", Static)
        history_list = self.query_one("#history-list", ListView)
        history_hint = self.query_one("#history-hint", Static)
        history_list.clear()
        selected_index = 0
        for index, row in enumerate(rows):
            flow_id = str(row.get("flow_id") or "").strip()
            badge = "*" if flow_id == self._selected_flow_id else " "
            label = Label(
                f"{badge} {flow_id}\n{row.get('effective_status') or row.get('status') or '-'}"
                f" · {row.get('effective_phase') or row.get('current_phase') or '-'}"
                f" · {row.get('flow_kind') or '-'}"
            )
            history_list.append(ListItem(label, name=flow_id))
            if flow_id == self._history_cursor_flow_id:
                selected_index = index
        if rows:
            history_list.index = selected_index
        history_header.update(self._render_history_header(rows=rows))
        history_hint.update("workspace runtime browser · /resume <flow_id>  /inspect <flow_id>  /manage  /back")
        self._update_history_detail(rows=rows)

    def _setup_stage_order(self) -> tuple[str, ...]:
        return ("mode", "catalog", "level", "goal", "guard", "confirm")

    def _set_setup_stage(self, stage: str) -> None:
        self._setup_stage = str(stage or "mode").strip().lower() or "mode"
        self._setup_cursor_key = ""
        self._refresh_setup_screen()
        self.call_after_refresh(self._focus_active_view_control)

    def _setup_preview_lines(self) -> list[str]:
        mode = self._setup_mode or "-"
        if self._setup_level == EXECUTION_MODE_SIMPLE:
            level = "low"
        elif self._setup_level == EXECUTION_MODE_MEDIUM:
            level = "medium"
        elif self._setup_level == EXECUTION_MODE_COMPLEX:
            level = "high"
        else:
            level = "-"
        catalog = self._setup_catalog_flow or "-"
        goal = self._setup_goal or "-"
        guard = self._setup_guard or "-"
        lines = [
            "Setup Preview",
            f"mode={mode}",
            f"catalog={catalog}",
            f"level={level}",
            f"goal={goal}",
            f"guard={guard}",
        ]
        if mode == "single":
            lines.append("note=single mode uses fixed catalog/level")
        if self._setup_catalog_flow == "free":
            lines.append("note=free first creates a shared template in /manage")
        elif self._setup_catalog_flow.startswith("template:"):
            lines.append(f"template_asset={self._setup_catalog_flow}")
        if self._setup_error:
            lines.append("")
            lines.append(f"error={self._setup_error}")
        return lines

    def _setup_options(self) -> list[dict[str, Any]]:
        stage = self._setup_stage
        if stage == "mode":
            return [
                {"id": "single", "label": "single  (single_goal + simple)"},
                {"id": "flow", "label": "flow  (project/managed flow)"},
            ]
        if stage == "level":
            return [
                {"id": EXECUTION_MODE_SIMPLE, "label": "low  (shared session)"},
                {"id": EXECUTION_MODE_MEDIUM, "label": "medium  (role + session)"},
                {"id": EXECUTION_MODE_COMPLEX, "label": "high  (coming soon)", "disabled": True},
            ]
        if stage == "catalog":
            if self._setup_mode == "single":
                return [{"id": SINGLE_GOAL_KIND, "label": "single_goal  (fixed for single)", "disabled": True}]
            return [
                {"id": PROJECT_LOOP_KIND, "label": "project_loop  (built-in)"},
                {"id": "free", "label": "free  (create template in /manage)"},
            ]
        if stage == "confirm":
            return [
                {"id": "start", "label": "start  (run with current setup)"},
                {"id": "edit_goal", "label": "edit goal"},
                {"id": "edit_guard", "label": "edit guard"},
                {"id": "back", "label": "back"},
                {"id": "cancel", "label": "cancel"},
            ]
        return [{"id": "input", "label": "enter value in command input"}]

    def _refresh_setup_screen(self) -> None:
        setup_header = self.query_one("#setup-header", Static)
        setup_list = self.query_one("#setup-list", ListView)
        setup_hint = self.query_one("#setup-hint", Static)
        setup_list.clear()
        options = self._setup_options()
        option_ids = {str(option.get("id") or "").strip() for option in options}
        if self._setup_cursor_key and self._setup_cursor_key not in option_ids:
            self._setup_cursor_key = ""
        selected_index = 0
        for index, option in enumerate(options):
            label = str(option.get("label") or option.get("id") or "").strip()
            if option.get("disabled"):
                label = f"{label}  [disabled]"
            setup_list.append(ListItem(Label(label), name=str(option.get("id") or "").strip()))
            if str(option.get("id") or "") == self._setup_cursor_key:
                selected_index = index
        if options:
            if not self._setup_cursor_key:
                self._setup_cursor_key = str(options[0].get("id") or "").strip()
            setup_list.index = selected_index
        setup_header.update(
            "\n".join(
                [
                    "New Setup",
                    f"stage={self._setup_stage or '-'}",
                    "enter=select",
                ]
            )
        )
        if self._setup_stage in {"goal", "guard"}:
            setup_hint.update("type in the command input, press enter")
        else:
            setup_hint.update("arrows=move  enter=select  /back=exit")
        self._update_setup_detail()

    def _update_setup_detail(self) -> None:
        self.query_one("#setup-detail", Static).update("\n".join(self._setup_preview_lines()))

    def _reset_setup_state(self) -> None:
        self._setup_stage = "mode"
        self._setup_cursor_key = ""
        self._setup_goal = ""
        self._setup_guard = ""
        self._setup_mode = ""
        self._setup_level = EXECUTION_MODE_SIMPLE
        self._setup_catalog_flow = PROJECT_LOOP_KIND
        self._setup_error = ""

    def _open_setup(self) -> None:
        self._reset_setup_state()
        self._set_view_mode("setup")
        self._refresh_setup_screen()
        self.call_after_refresh(self._focus_active_view_control)

    def _settings_rows(self) -> list[tuple[str, str]]:
        prefs = self._session_preferences
        return [
            ("auto_follow", f"auto_follow={'on' if prefs.get('auto_follow') else 'off'}"),
            ("show_runtime_events", f"runtime_events={'on' if prefs.get('show_runtime_events') else 'off'}"),
            ("transcript_filter", f"filter={prefs.get('transcript_filter') or 'all'}"),
        ]

    def _render_settings_preview(self) -> str:
        key = self._settings_cursor_key
        prefs = self._session_preferences
        if key == "auto_follow":
            return "\n".join(["Auto Follow", f"current={'on' if prefs.get('auto_follow') else 'off'}", "Enter toggles transcript auto-follow."])
        if key == "show_runtime_events":
            return "\n".join(["Runtime Events", f"current={'on' if prefs.get('show_runtime_events') else 'off'}", "Enter toggles codex runtime event visibility."])
        return "\n".join(
            [
                "Transcript Filter",
                f"current={prefs.get('transcript_filter') or 'all'}",
                "Enter cycles all -> assistant -> system -> judge -> operator -> supervisor.",
            ]
        )

    def _refresh_settings_screen(self) -> None:
        rows = self._settings_rows()
        settings_status = self.query_one("#settings-status", Static)
        settings_list = self.query_one("#settings-list", ListView)
        settings_hint = self.query_one("#settings-hint", Static)
        settings_preview = self.query_one("#settings-preview", Static)
        settings_list.clear()
        valid_keys = {key for key, _ in rows}
        if self._settings_cursor_key not in valid_keys:
            self._settings_cursor_key = rows[0][0]
        for key, text in rows:
            settings_list.append(ListItem(Label(text), name=key))
        settings_status.update(
            "\n".join(
                [
                    "Settings",
                    "scope=session",
                    "enter=toggle/cycle",
                    "/back=return",
                ]
            )
        )
        settings_hint.update("/follow on|off  /filter ...  /runtime-events on|off")
        settings_preview.update(self._render_settings_preview())

    def _design_options(self) -> list[dict[str, Any]]:
        stage = self._design_stage or "proposal"
        if stage == "proposal":
            return [{"id": "proposal", "label": "enter proposal in command input"}]
        if stage == "build":
            label = "building flow definition..." if self._design_busy else "generate flow definition"
            return [{"id": "build", "label": label, "disabled": bool(self._design_busy)}]
        if stage == "review":
            return [
                {"id": "approve", "label": "approve and continue"},
                {"id": "revise", "label": "revise (back to build)"},
            ]
        return [{"id": "proposal", "label": "enter proposal in command input"}]

    def _design_preview_lines(self) -> list[str]:
        summary = str(dict(self._design_payload or {}).get("manage_handoff", {}).get("summary") or "").strip()
        lines = [
            "Flow Designer",
            f"stage={self._design_stage or 'proposal'}",
            f"request={self._design_request or '-'}",
            f"flow_id={self._design_flow_id or '-'}",
        ]
        if summary:
            lines.append(f"summary={summary}")
        if self._design_error:
            lines.append("")
            lines.append(f"error={self._design_error}")
        return lines

    def _render_manage_header(self, *, rows: list[dict[str, Any]]) -> str:
        template_count = len([row for row in rows if str(row.get("asset_kind") or "") == "template"])
        builtin_count = len([row for row in rows if str(row.get("asset_kind") or "") == "builtin"])
        return "\n".join(
            [
                "Manage Center",
                f"assets={len(rows)}",
                f"templates={template_count}",
                f"builtin={builtin_count}",
                "enter=open",
            ]
        )

    def _render_manage_detail(self, row: dict[str, Any]) -> str:
        asset = dict(row or {})
        if not asset:
            return "No managed asset selected."
        definition = dict(asset.get("definition") or {})
        asset_state = dict(asset.get("asset_state") or definition.get("asset_state") or {})
        lineage = dict(asset.get("lineage") or definition.get("lineage") or {})
        bundle_manifest = dict(asset.get("bundle_manifest") or definition.get("bundle_manifest") or {})
        review_checklist = list(asset.get("review_checklist") or definition.get("review_checklist") or [])
        role_guidance = dict(asset.get("role_guidance") or definition.get("role_guidance") or {})
        lines = [
            "Managed Asset",
            f"asset={asset.get('asset_key') or '-'}",
            f"asset_kind={asset.get('asset_kind') or '-'}",
            f"kind={asset.get('workflow_kind') or '-'}",
            f"label={asset.get('label') or '-'}",
            f"goal={asset.get('goal') or '-'}",
            f"guard={asset.get('guard_condition') or '-'}",
            f"path={asset.get('asset_path') or '-'}",
        ]
        if asset.get("description"):
            lines.append(f"description={asset.get('description')}")
        manage_handoff = dict(definition.get("manager_handoff") or asset.get("manage_handoff") or {})
        lines.extend(
            [
                f"role_pack={asset.get('role_pack_id') or '-'}",
                f"updated_at={asset.get('updated_at') or '-'}",
                f"catalog_flow={definition.get('catalog_flow_id') or '-'}",
                f"asset_stage={asset_state.get('stage') or '-'}",
                f"asset_status={asset_state.get('status') or '-'}",
            ]
        )
        source_asset_key = str(definition.get("source_asset_key") or "").strip()
        if source_asset_key:
            lines.append(f"source_asset={source_asset_key}")
        if review_checklist:
            lines.extend(["", "Review Checklist", *[f"- {item}" for item in review_checklist]])
        if role_guidance:
            lines.extend(["", "Role Guidance"])
            suggested_roles = list(role_guidance.get("suggested_roles") or [])
            suggested_specialists = list(role_guidance.get("suggested_specialists") or [])
            activation_hints = list(role_guidance.get("activation_hints") or [])
            promotion_candidates = list(role_guidance.get("promotion_candidates") or [])
            manager_notes = str(role_guidance.get("manager_notes") or "").strip()
            if suggested_roles:
                lines.append(f"suggested_roles={', '.join(str(item) for item in suggested_roles)}")
            if suggested_specialists:
                lines.append(f"suggested_specialists={', '.join(str(item) for item in suggested_specialists)}")
            if activation_hints:
                lines.extend(["activation_hints"] + [f"- {item}" for item in activation_hints])
            if promotion_candidates:
                lines.append(f"promotion_candidates={', '.join(str(item) for item in promotion_candidates)}")
            if manager_notes:
                lines.append(f"manager_notes={manager_notes}")
        if lineage:
            lines.extend(["", "Lineage"] + [f"{key}={value}" for key, value in lineage.items() if str(value).strip()])
        if bundle_manifest:
            lines.extend(["", "Bundle"] + [f"{key}={value}" for key, value in bundle_manifest.items() if not isinstance(value, dict)])
        if manage_handoff:
            lines.extend(
                [
                    "",
                    "Manager Handoff",
                    f"summary={manage_handoff.get('summary') or '-'}",
                ]
            )
            guidance = str(manage_handoff.get("operator_guidance") or "").strip()
            if guidance:
                lines.append(f"guidance={guidance}")
        lines.extend(
            [
                "",
                "Input Examples",
                "$template:new create a new reusable research flow",
                "$template:my_flow refine the review checklist",
                "$builtin:project_loop clone make a team-specific variant",
                "$builtin:project_loop edit update the builtin in place",
            ]
        )
        if self._manage_return_to_setup:
            lines.extend(
                [
                    "",
                    "Setup Seed",
                    f"instruction={self._manage_seed_instruction or '-'}",
                    "Create a template, then return to setup confirm.",
                ]
            )
        return "\n".join(lines)

    def _refresh_manage_screen(self) -> None:
        rows = self._manage_rows()
        header = self.query_one("#manage-header", Static)
        hint = self.query_one("#manage-hint", Static)
        header.update("Manage Center")
        hint.update("plain text → manager · $template:<id> opens picker · /manage keeps direct asset edits · /back")
        if not self._manage_cursor_asset_key and rows:
            self._manage_cursor_asset_key = str(rows[0].get("asset_key") or "").strip()
        self._reset_manage_transcript()
        self._manage_transcript_formatter.write_section(
            self._manage_transcript(),
            title="Manage Center",
            body=self._render_manage_overview(rows=rows),
        )
        self._manage_transcript_formatter.write_section(
            self._manage_transcript(),
            title="Assets",
            body=self._render_manage_assets(rows=rows),
        )
        selected = next(
            (row for row in rows if str(row.get("asset_key") or "").strip() == self._manage_cursor_asset_key),
            rows[0] if rows else {},
        )
        if selected:
            self._manage_transcript_formatter.write_section(
                self._manage_transcript(),
                title="Selected Asset",
                body=self._render_manage_detail(selected),
            )
        if self._manage_return_to_setup:
            self._manage_transcript_formatter.write_note(
                self._manage_transcript(),
                lane="system",
                family="manage",
                body=f"setup_seed={self._manage_seed_instruction or '-'}",
                tone="muted",
            )
        for record in list(self._manage_notes):
            body = str(record.get("body") or "").strip()
            if not body:
                continue
            self._manage_transcript_formatter.write_note(
                self._manage_transcript(),
                lane=str(record.get("lane") or "system"),
                family=str(record.get("family") or "manage"),
                body=body,
                tone=str(record.get("tone") or "system"),
            )
        self._update_manage_picker(self._command_input().value)

    def _refresh_design_screen(self) -> None:
        flows_header = self.query_one("#flows-header", Static)
        flows_list = self.query_one("#flows-list", ListView)
        flows_hint = self.query_one("#flows-hint", Static)
        flows_list.clear()
        options = self._design_options()
        option_ids = {str(option.get("id") or "").strip() for option in options}
        if self._design_cursor_key and self._design_cursor_key not in option_ids:
            self._design_cursor_key = ""
        selected_index = 0
        for index, option in enumerate(options):
            label = str(option.get("label") or option.get("id") or "").strip()
            if option.get("disabled"):
                label = f"{label}  [disabled]"
            flows_list.append(ListItem(Label(label), name=str(option.get("id") or "").strip()))
            if str(option.get("id") or "") == self._design_cursor_key:
                selected_index = index
        if options:
            if not self._design_cursor_key:
                self._design_cursor_key = str(options[0].get("id") or "").strip()
            flows_list.index = selected_index
        flows_header.update(
            "\n".join(
                [
                    "Flow Designer",
                    f"stage={self._design_stage or 'proposal'}",
                    "enter=select",
                ]
            )
        )
        if self._design_stage == "proposal":
            flows_hint.update("type the proposal in command input, press enter")
        elif self._design_stage == "build":
            flows_hint.update("enter=generate  /back=exit")
        else:
            flows_hint.update("enter=select  /back=exit")
        self._update_design_detail()

    def _update_design_detail(self) -> None:
        self.query_one("#flows-detail", Static).update("\n".join(self._design_preview_lines()))

    def _open_flows(self, *, origin: str = "") -> None:
        self._set_flows_screen_mode("design")
        self._design_origin = str(origin or "").strip()
        if origin:
            self._design_stage = "proposal"
            self._design_request = ""
            self._design_payload = {}
            self._design_flow_id = ""
            self._design_error = ""
            self._design_busy = False
            self._design_cursor_key = ""
        elif not self._design_stage:
            self._design_stage = "proposal"
        self._set_view_mode("flows")
        self._refresh_design_screen()
        self.call_after_refresh(self._focus_active_view_control)

    def _current_manage_focus_asset_key(self) -> str:
        flow_id = str(self._selected_flow_id or self._current_flow_id or "").strip()
        if not flow_id:
            return ""
        try:
            payload = self._controller.status_payload(config=self._current_config, flow_id=flow_id)
        except Exception:
            return ""
        flow_state = dict(payload.get("flow_state") or {})
        source_kind = str(flow_state.get("catalog_flow_id") or "").strip()
        if source_kind.startswith("template:"):
            template_id = str(source_kind.split(":", 1)[1] or "").strip()
            return f"template:{template_id}" if template_id else ""
        if source_kind and source_kind not in {"free", "single_goal"}:
            return f"builtin:{source_kind}"
        return ""

    def _open_manage_center(self) -> None:
        self._set_flows_screen_mode("manage")
        focus_asset_key = self._current_manage_focus_asset_key()
        if focus_asset_key:
            self._manage_cursor_asset_key = focus_asset_key
        self._set_view_mode("flows")
        self._refresh_manage_screen()
        self.call_after_refresh(self._focus_active_view_control)

    def _advance_setup_stage(self) -> None:
        order = list(self._setup_stage_order())
        if not order:
            self._set_setup_stage("mode")
            return
        if self._setup_stage not in order:
            self._set_setup_stage(order[0])
            return
        idx = order.index(self._setup_stage)
        next_index = min(idx + 1, len(order) - 1)
        while self._setup_mode == "single" and order[next_index] in {"catalog", "level"}:
            if order[next_index] == "catalog":
                self._setup_catalog_flow = SINGLE_GOAL_KIND
            if order[next_index] == "level":
                self._setup_level = EXECUTION_MODE_SIMPLE
            next_index = min(next_index + 1, len(order) - 1)
        self._set_setup_stage(order[next_index])

    def _retreat_setup_stage(self) -> None:
        order = list(self._setup_stage_order())
        if not order or self._setup_stage not in order:
            self._set_setup_stage("mode")
            return
        idx = max(0, order.index(self._setup_stage) - 1)
        while self._setup_mode == "single" and idx > 0 and order[idx] in {"catalog", "level"}:
            idx -= 1
        self._set_setup_stage(order[idx])

    def _handle_setup_input(self, text: str) -> None:
        value = str(text or "").strip()
        if self._setup_stage == "goal":
            if not value:
                self.notify("Goal is required.", severity="warning")
                return
            self._setup_goal = value
            self._advance_setup_stage()
            return
        if self._setup_stage == "guard":
            if not value:
                default_guard = (
                    "If Codex is interrupted, continue until the goal is satisfied."
                    if self._setup_mode == "single"
                    else "If Codex is interrupted, continue; advance until review passes."
                )
                value = default_guard
            self._setup_guard = value
            self._advance_setup_stage()
            return
        self.notify("Use the picker for this step.", severity="warning")

    def _apply_setup_selection(self, target: str) -> None:
        stage = self._setup_stage
        token = str(target or "").strip()
        self._setup_error = ""
        if stage == "mode":
            if token not in {"single", "flow"}:
                self.notify("Choose single or flow.", severity="warning")
                return
            self._setup_mode = token
            if self._setup_mode == "single":
                self._setup_level = EXECUTION_MODE_SIMPLE
                self._setup_catalog_flow = SINGLE_GOAL_KIND
            elif not self._setup_catalog_flow:
                self._setup_catalog_flow = PROJECT_LOOP_KIND
            self._advance_setup_stage()
            return
        if stage == "level":
            if token == EXECUTION_MODE_COMPLEX:
                self.notify("High mode is coming soon.", severity="warning")
                return
            if token not in {EXECUTION_MODE_SIMPLE, EXECUTION_MODE_MEDIUM}:
                self.notify("Choose low or medium.", severity="warning")
                return
            self._setup_level = token
            self._advance_setup_stage()
            return
        if stage == "catalog":
            if self._setup_mode == "single" and token == SINGLE_GOAL_KIND:
                self._advance_setup_stage()
                return
            if token not in {PROJECT_LOOP_KIND, "free"} and not token.startswith("template:"):
                self.notify("Choose project_loop, free, or a prepared template.", severity="warning")
                return
            self._setup_catalog_flow = token
            self._advance_setup_stage()
            return
        if stage == "confirm":
            if token == "edit_goal":
                self._set_setup_stage("goal")
                return
            if token == "edit_guard":
                self._set_setup_stage("guard")
                return
            if token == "back":
                self._retreat_setup_stage()
                return
            if token == "cancel":
                self._back_to_flow()
                return
            if token == "start":
                self._start_setup_flow()
                return
        self.notify("Use the input box for this step.", severity="warning")

    def _start_setup_flow(self) -> None:
        if not self._setup_mode:
            self.notify("Select a launch mode first.", severity="warning")
            self._set_setup_stage("mode")
            return
        if not self._setup_goal:
            self.notify("Goal is required.", severity="warning")
            self._set_setup_stage("goal")
            return
        if self._setup_mode == "single":
            kind = SINGLE_GOAL_KIND
            execution_mode = EXECUTION_MODE_SIMPLE
        else:
            kind = PROJECT_LOOP_KIND
            execution_mode = self._setup_level or EXECUTION_MODE_SIMPLE
        guard_condition = self._setup_guard or (
            "If Codex is interrupted, continue until the goal is satisfied."
            if self._setup_mode == "single"
            else "If Codex is interrupted, continue; advance until review passes."
        )
        if self._setup_mode != "single" and self._setup_catalog_flow == "free":
            self._manage_return_to_setup = True
            self._manage_seed_instruction = f"create a reusable template for goal={self._setup_goal or '-'} guard={guard_condition or '-'}"
            self._open_manage_center()
            self.call_after_refresh(
                self._focus_command_input_with_text,
                f"/manage template:new {self._manage_seed_instruction}",
            )
            return
        prepared = self._controller.prepare_run(
            config=self._current_config,
            kind=kind,
            catalog_flow_id="" if self._setup_mode == "single" else self._setup_catalog_flow,
            goal=self._setup_goal,
            guard_condition=guard_condition,
            execution_mode=execution_mode,
        )
        self._begin_run(prepared, stream_enabled=True)
        self._back_to_flow()

    def _begin_design_build(self) -> None:
        if self._design_busy:
            return
        if not self._design_request:
            self.notify("Design proposal is required.", severity="warning")
            return
        self._design_busy = True
        self._design_error = ""
        self._refresh_design_screen()

        def _target() -> None:
            try:
                payload = self._controller.manage_flow(
                    config=self._current_config,
                    manage_target="new",
                    instruction=self._design_request,
                )
            except Exception as exc:
                self.call_from_thread(
                    self.post_message,
                    DesignBuildMessage(payload={}, error_text=f"{type(exc).__name__}: {exc}"),
                )
                return
            self.call_from_thread(self.post_message, DesignBuildMessage(payload=payload))

        threading.Thread(target=_target, daemon=True).start()

    def _apply_design_selection(self, target: str) -> None:
        stage = self._design_stage or "proposal"
        token = str(target or "").strip()
        if stage == "build":
            if self._design_busy:
                self.notify("Design build in progress.", severity="warning")
                return
            self._begin_design_build()
            return
        if stage == "review":
            if token == "approve":
                if not self._design_flow_id:
                    self.notify("No draft flow to approve.", severity="warning")
                    return
                if self._design_origin == "setup":
                    self._setup_free_flow_id = self._design_flow_id
                    self._set_setup_stage("confirm")
                    self._set_view_mode("setup")
                    self._refresh_setup_screen()
                    self.call_after_refresh(self._focus_active_view_control)
                    return
                self.notify("Free design approved.", severity="information")
                return
            if token == "revise":
                self._design_stage = "proposal"
                self._design_payload = {}
                self._design_flow_id = ""
                self._design_error = ""
                self._refresh_design_screen()
                self.call_after_refresh(self._focus_active_view_control)
                return
        self.notify("Provide proposal input in the command box.", severity="warning")

    def _refresh_snapshot(self) -> None:
        rows = self._flow_rows()
        if not self._selected_flow_id and rows:
            self._selected_flow_id = str(rows[0].get("flow_id") or "").strip()
        self._refresh_flow_view()
        self._refresh_history_screen(rows=rows)
        if self._view_mode == "setup":
            self._refresh_setup_screen()
        if self._view_mode == "flows":
            if self._flows_screen_mode == "manage":
                self._refresh_manage_screen()
            else:
                self._refresh_design_screen()
        self._refresh_settings_screen()
        self._apply_transcript_preferences()
        self._set_action_bar()

    def _apply_transcript_preferences(self) -> None:
        auto_follow = bool(self._session_preferences.get("auto_follow", True))
        self.query_one("#transcript", RichLog).auto_scroll = auto_follow
        self.query_one("#manage-transcript", RichLog).auto_scroll = auto_follow

    def _transcript(self) -> RichLog:
        return self.query_one("#transcript", RichLog)

    def _manage_transcript(self) -> RichLog:
        return self.query_one("#manage-transcript", RichLog)

    def _flow_transcript_scroll_key(self, *, flow_id: str | None = None, view_mode: str | None = None) -> tuple[str, str] | None:
        target_flow_id = str(flow_id or self._target_flow_id() or "").strip()
        if not target_flow_id:
            return None
        mode = str(view_mode or self._flow_view_mode or "supervisor").strip().lower() or "supervisor"
        return (target_flow_id, mode)

    def _remember_flow_transcript_scroll(self, *, flow_id: str | None = None, view_mode: str | None = None) -> None:
        key = self._flow_transcript_scroll_key(flow_id=flow_id, view_mode=view_mode)
        if key is None:
            return
        transcript = self._transcript()
        if self._transcript_formatter.is_near_bottom(transcript):
            self._flow_transcript_scroll_positions.pop(key, None)
            return
        scroll_offset = getattr(transcript, "scroll_offset", None)
        self._flow_transcript_scroll_positions[key] = int(getattr(scroll_offset, "y", 0) or 0)

    def _restore_flow_transcript_scroll(self, *, flow_id: str | None = None, view_mode: str | None = None) -> None:
        key = self._flow_transcript_scroll_key(flow_id=flow_id, view_mode=view_mode)
        if key is None:
            return
        saved_y = self._flow_transcript_scroll_positions.get(key)
        if saved_y is None:
            return
        transcript = self._transcript()
        transcript.scroll_to(
            y=max(0, min(saved_y, int(getattr(transcript, "max_scroll_y", 0) or 0))),
            animate=False,
            immediate=True,
        )

    def _active_scroll_transcript(self) -> RichLog | None:
        if self._view_mode == "flow":
            return self._transcript()
        if self._view_mode == "flows" and self._flows_screen_mode == "manage":
            return self._manage_transcript()
        return None

    def _transcript_page_delta(self, transcript: RichLog) -> int:
        container = getattr(transcript, "container_size", None)
        height = int(getattr(container, "height", 0) or 0)
        if height <= 0:
            size = getattr(transcript, "size", None)
            height = int(getattr(size, "height", 0) or 0)
        return max(4, height - 2)

    def _scroll_active_transcript(self, key: str) -> bool:
        transcript = self._active_scroll_transcript()
        if transcript is None:
            return False
        token = str(key or "").strip().lower()
        page_delta = self._transcript_page_delta(transcript)
        if token == "home":
            transcript.scroll_home(animate=False, immediate=True, x_axis=False)
        elif token == "end":
            transcript.scroll_end(animate=False, immediate=True, x_axis=False)
        elif token == "up":
            transcript.scroll_relative(y=-1, animate=False, immediate=True)
        elif token == "down":
            transcript.scroll_relative(y=1, animate=False, immediate=True)
        elif token == "pageup":
            transcript.scroll_relative(y=-page_delta, animate=False, immediate=True)
        elif token == "pagedown":
            transcript.scroll_relative(y=page_delta, animate=False, immediate=True)
        else:
            return False
        if token in {"down", "pagedown", "end"} and self._transcript_formatter.is_near_bottom(transcript):
            transcript.scroll_end(animate=False, immediate=True, x_axis=False)
        if transcript is self._transcript():
            self._remember_flow_transcript_scroll()
        return True

    def _transcript_tone_for_entry(self, entry: dict[str, Any]) -> str:
        kind = str(entry.get("kind") or "").strip().lower()
        family = str(entry.get("family") or "").strip().lower()
        lane = str(entry.get("lane") or "").strip().lower()
        title = str(entry.get("title") or "").strip().lower()
        message = str(entry.get("message") or "").strip().lower()
        raw_text = str(entry.get("raw_text") or "").strip()
        payload = dict(entry.get("payload") or {})
        raw_kind = str(payload.get("kind") or payload.get("stream") or payload.get("event") or "").strip().lower()
        raw_summary = " ".join(part for part in (title, message, raw_kind) if part)
        if kind in {"error", "run_failed"} or family == "error":
            return "error"
        if kind in {"warning"}:
            return "warning"
        if kind == "codex_segment":
            return "raw_output"
        if family == "raw_execution":
            if any(token in raw_summary for token in ("stderr", "error", "failed", "exception", "traceback")):
                return "raw_error"
            if any(token in raw_summary for token in ("success", "completed", "finished", "done", "ok")):
                return "raw_success"
            if raw_text and (title in {"stdout", "output"} or raw_kind in {"stdout", "output"}):
                return "raw_output"
            if raw_text and raw_text != str(entry.get("title") or "").strip():
                return "raw_output"
            return "raw_meta"
        if family == "input":
            return "action"
        if family == "output":
            return "raw_output"
        if family == "decision" or kind == "judge_result":
            return "decision"
        if family == "approval":
            return "approval"
        if family == "handoff":
            return "handoff"
        if family in {"action", "run"}:
            return "action"
        if family == "artifact":
            return "artifact"
        if family == "phase":
            return "phase"
        if family == "raw_execution" or lane == "workflow":
            return "workflow"
        if lane == "system":
            return "system"
        return "default"

    def _write_transcript_note(self, *, family: str, body: str, tone: str = "system", lane: str = "system") -> None:
        self._transcript_formatter.write_note(
            self._transcript(),
            lane=lane,
            family=family,
            body=body,
            tone=tone,
        )

    def _write_manage_note(self, *, family: str, body: str, tone: str = "system", lane: str = "system") -> None:
        record = {
            "family": str(family or "").strip() or "manage",
            "body": str(body or "").strip(),
            "tone": str(tone or "").strip() or "system",
            "lane": str(lane or "").strip() or "system",
        }
        if record["body"]:
            self._manage_notes.append(record)
        if self._view_mode == "flows" and self._flows_screen_mode == "manage":
            self._manage_transcript_formatter.write_note(
                self._manage_transcript(),
                lane=record["lane"],
                family=record["family"],
                body=record["body"],
                tone=record["tone"],
            )

    def _write_transcript_section(self, *, title: str, body: str, tone: str = "default") -> None:
        self._transcript_formatter.write_section(
            self._transcript(),
            title=title,
            body=body,
            tone=tone,
        )

    def _reset_manage_transcript(self) -> None:
        transcript = self._manage_transcript()
        transcript.clear()
        self._manage_transcript_formatter.reset()

    def _render_manage_overview(self, *, rows: list[dict[str, Any]]) -> str:
        template_count = len([row for row in rows if str(row.get("asset_kind") or "") == "template"])
        builtin_count = len([row for row in rows if str(row.get("asset_kind") or "") == "builtin"])
        lines = [
            f"assets={len(rows)}",
            f"templates={template_count}",
            f"builtin={builtin_count}",
            "use $template:<id> or $builtin:<id> to target an asset",
            "use $template:new to create a new template",
            "builtin edits require explicit clone or edit wording",
        ]
        if self._manage_cursor_asset_key:
            lines.append(f"active_asset={self._manage_cursor_asset_key}")
        return "\n".join(lines)

    def _render_manage_assets(self, *, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "No shared assets yet."
        lines: list[str] = []
        for row in rows:
            asset_key = str(row.get("asset_key") or "").strip() or "-"
            kind = str(row.get("workflow_kind") or "-").strip() or "-"
            label = str(row.get("label") or row.get("asset_id") or "-").strip() or "-"
            asset_kind = str(row.get("asset_kind") or "-").strip() or "-"
            lines.append(f"{asset_key} · {asset_kind} · {kind} · {label}")
        return "\n".join(lines)

    def _manage_prompt_token(self, text: str) -> str:
        return manage_prompt_token(text)

    def _manage_asset_candidates(self, text: str) -> list[str]:
        if not has_manage_prompt_token(text):
            return []
        token = manage_prompt_token(text)
        assets = self._manage_asset_keys()
        if not token:
            return assets
        folded = token.casefold()
        return [asset for asset in assets if asset.casefold().startswith(folded)]

    def _refresh_manage_suggestion(self) -> None:
        command_input = self._command_input()
        suggester = command_input.suggester
        if suggester is None:
            return
        command_input.run_worker(suggester._get_suggestion(command_input, command_input.value))

    def _split_manage_prompt(self, text: str) -> tuple[str, str]:
        return split_manage_prompt(text)

    def _event_category(self, entry: dict[str, Any]) -> str:
        token = str(entry.get("kind") or "").strip()
        lane = self._event_lane(entry)
        if token == "judge_result":
            return "judge"
        if token == "operator_action_applied":
            return "operator"
        if lane == "supervisor":
            return "supervisor"
        if token == "codex_segment":
            return "assistant"
        return "system"

    def _event_visible(self, entry: dict[str, Any]) -> bool:
        kind = str(entry.get("kind") or "").strip()
        if not self._event_matches_flow_view(entry):
            return False
        if kind == "codex_runtime_event" and not bool(self._session_preferences.get("show_runtime_events", True)):
            return False
        current_filter = str(self._session_preferences.get("transcript_filter") or "all").strip().lower() or "all"
        if current_filter == "all":
            return True
        return self._event_category(entry) == current_filter

    def _render_timeline_entry(self, entry: dict[str, Any]) -> None:
        event_id = str(entry.get("event_id") or "").strip()
        if event_id and event_id in self._transcript_event_ids:
            return
        if not self._event_visible(entry):
            if event_id:
                self._transcript_event_ids.add(event_id)
            return
        kind = str(entry.get("kind") or "").strip()
        message = str(entry.get("message") or "")
        payload = dict(entry.get("payload") or {})
        lane = self._event_lane(entry)
        family = str(entry.get("family") or "").strip().lower()
        if kind == "codex_segment" and lane == "supervisor":
            family = "output"
        title = str(entry.get("title") or "").strip()
        transcript = self._transcript()
        if kind == "codex_segment":
            snapshot = str(entry.get("raw_text") or payload.get("segment") or message or "")
            if snapshot.startswith(self._latest_segment):
                delta = snapshot[len(self._latest_segment) :]
                if delta:
                    self._transcript_formatter.write_group(
                        transcript,
                        lane=lane or "workflow",
                        family=family or "raw_execution",
                        body=delta.rstrip("\n"),
                        tone="raw_output",
                    )
            elif snapshot and snapshot != self._latest_segment:
                self._transcript_formatter.write_group(
                    transcript,
                    lane=lane or "workflow",
                    family=family or "raw_execution",
                    body=snapshot.rstrip("\n"),
                    tone="raw_output",
                )
            self._latest_segment = snapshot
        else:
            if family == "raw_execution":
                line = str(entry.get("raw_text") or message or payload.get("text") or title or payload.get("summary") or payload.get("kind") or "")
            else:
                line = title or message or str(payload.get("summary") or payload.get("text") or payload.get("kind") or "")
            if line:
                self._transcript_formatter.write_group(
                    transcript,
                    lane=lane or "system",
                    family=family or kind or "event",
                    body=line,
                    tone=self._transcript_tone_for_entry(entry),
                )
        if event_id:
            self._transcript_event_ids.add(event_id)

    def _reload_transcript(self, flow_id: str) -> None:
        transcript = self._transcript()
        transcript.clear()
        self._transcript_formatter.reset()
        self._transcript_event_ids.clear()
        self._latest_segment = ""
        if not flow_id:
            return
        try:
            payload = self._current_flow_payload(flow_id)
        except Exception as exc:
            self._write_transcript_note(
                family="timeline",
                body=f"failed to load {flow_id}: {type(exc).__name__}: {exc}",
                tone="error",
            )
            return
        if self._flow_view_mode == "supervisor":
            self._write_transcript_section(title="Supervisor Stream", body=self._render_supervisor_prelude(payload))
        else:
            self._write_transcript_section(title="Workflow Stream", body=self._render_workflow_prelude(payload))
        timeline = self._current_flow_events(payload)
        if not timeline:
            self._write_transcript_note(family="timeline", body=f"no events for {flow_id}", tone="muted")
            self.call_after_refresh(lambda: self._restore_flow_transcript_scroll(flow_id=flow_id))
            return
        for entry in timeline:
            self._render_timeline_entry(dict(entry or {}))
        self.call_after_refresh(lambda: self._restore_flow_transcript_scroll(flow_id=flow_id))

    def _focus_flow(self, flow_id: str) -> None:
        target = str(flow_id or "").strip()
        if not target:
            return
        current = str(self._target_flow_id() or "").strip()
        if current and current != target:
            self._remember_flow_transcript_scroll(flow_id=current)
        self._selected_flow_id = target
        self._history_cursor_flow_id = target
        self._reload_transcript(target)
        self._refresh_flow_view()
        self._set_action_bar()

    def _open_history(self) -> None:
        rows = self._flow_rows()
        if not self._selected_flow_id and rows:
            self._selected_flow_id = str(rows[0].get("flow_id") or "").strip()
        self._history_cursor_flow_id = self._selected_flow_id or self._history_cursor_flow_id
        self._workspace_detail_mode = "preview"
        self._set_view_mode("history")
        self._refresh_history_screen(rows=rows)
        self.call_after_refresh(self._focus_history_list)

    def _open_settings(self) -> None:
        self._set_view_mode("settings")
        self._refresh_settings_screen()
        self.call_after_refresh(self._focus_settings_list)

    def _back_to_flow(self) -> None:
        self._set_view_mode("flow")
        if self._target_flow_id():
            self._reload_transcript(self._target_flow_id())
        self._refresh_flow_view()
        self.call_after_refresh(self._focus_command_input)

    def _commit_history_selection(self) -> None:
        target = str(self._history_cursor_flow_id or "").strip()
        if not target:
            self.notify("No flow selected in history.", severity="warning")
            return
        self._focus_flow(target)
        self._back_to_flow()

    def _toggle_setting(self, key: str) -> None:
        if key == "auto_follow":
            self._session_preferences["auto_follow"] = not bool(self._session_preferences.get("auto_follow", True))
        elif key == "show_runtime_events":
            self._session_preferences["show_runtime_events"] = not bool(self._session_preferences.get("show_runtime_events", True))
            self._remember_flow_transcript_scroll()
            self._reload_transcript(self._target_flow_id())
        elif key == "transcript_filter":
            current = str(self._session_preferences.get("transcript_filter") or "all").strip().lower() or "all"
            try:
                index = TRANSCRIPT_FILTERS.index(current)
            except ValueError:
                index = 0
            self._session_preferences["transcript_filter"] = TRANSCRIPT_FILTERS[(index + 1) % len(TRANSCRIPT_FILTERS)]
            self._remember_flow_transcript_scroll()
            self._reload_transcript(self._target_flow_id())
        self._refresh_settings_screen()
        self._apply_transcript_preferences()

    def _begin_run(self, prepared: PreparedFlowRun, *, stream_enabled: bool) -> None:
        if self._attached_run_active:
            self.notify("A flow is already running.", severity="warning")
            return
        self._attached_run_active = True
        self._set_view_mode("flow")
        flow_id = str(prepared.flow_state.get("workflow_id") or "").strip()
        self._current_flow_id = flow_id
        self._focus_flow(flow_id or self._selected_flow_id)
        self._write_transcript_note(family="launcher", body=f"attached run started for {flow_id}")
        self._refresh_snapshot()

        def _target() -> None:
            try:
                rc = self._controller.execute_prepared_flow(prepared, stream_enabled=stream_enabled)
            except Exception as exc:
                self.call_from_thread(self.post_message, RunErroredMessage(flow_id, f"{type(exc).__name__}: {exc}"))
                return
            self.call_from_thread(self.post_message, RunFinishedMessage(flow_id, rc))

        threading.Thread(target=_target, daemon=True).start()

    def _emit_from_thread(self, event: FlowUiEvent) -> None:
        self.call_from_thread(self.post_message, UiEventMessage(event))

    def on_ui_event_message(self, message: UiEventMessage) -> None:
        event = message.event
        if event.flow_id:
            self._current_flow_id = event.flow_id
            if not self._selected_flow_id:
                self._selected_flow_id = event.flow_id
        if self._view_mode == "flow" and event.flow_id and event.flow_id == self._selected_flow_id:
            self._render_timeline_entry(event.to_dict())
        self._refresh_flow_view()
        self._refresh_snapshot()

    def on_run_finished_message(self, message: RunFinishedMessage) -> None:
        self._attached_run_active = False
        self._write_transcript_note(family="run", body=f"flow={message.flow_id} return_code={message.return_code}")
        self._refresh_snapshot()

    def on_run_errored_message(self, message: RunErroredMessage) -> None:
        self._attached_run_active = False
        self._write_transcript_note(
            family="error",
            body=f"flow={message.flow_id or '-'} {message.error_text or 'unknown error'}",
            tone="error",
        )
        self.notify(message.error_text or "run failed", severity="error")
        self._refresh_snapshot()

    def on_design_build_message(self, message: DesignBuildMessage) -> None:
        self._design_busy = False
        if message.error_text:
            self._design_error = message.error_text
            self._design_stage = "build"
            self._refresh_design_screen()
            self.notify(message.error_text, severity="error")
            return
        payload = dict(message.payload or {})
        self._design_payload = payload
        self._design_flow_id = str(payload.get("flow_id") or "").strip()
        self._design_error = ""
        self._design_stage = "review"
        if self._design_origin == "setup":
            goal = str(payload.get("goal") or "").strip()
            guard = str(payload.get("guard_condition") or "").strip()
            if goal:
                self._setup_goal = goal
            if guard:
                self._setup_guard = guard
        self._refresh_design_screen()

    def on_manage_chat_message(self, message: ManageChatMessage) -> None:
        self._manage_chat_busy = False
        self._manage_chat_started_at = 0.0
        if message.error_text:
            self._write_manage_note(family="error", body=message.error_text, tone="error")
            self.notify(message.error_text, severity="error")
        else:
            payload = dict(message.payload or {})
            session_id = str(payload.get("manager_session_id") or "").strip()
            if session_id:
                self._manage_chat_session_id = session_id
            manage_target = str(payload.get("manage_target") or message.request.manage_target or "").strip()
            if manage_target:
                self._manage_cursor_asset_key = manage_target
            response = str(payload.get("response") or payload.get("summary") or "").strip()
            if response:
                self._write_manage_note(family="manager", body=response, tone="system")
            next_action = str(payload.get("suggested_next_action") or "").strip()
            if next_action:
                self._write_manage_note(family="hint", body=f"next · {next_action}", tone="action")
            edit_hint = str(payload.get("edit_hint") or "").strip()
            if edit_hint:
                self._write_manage_note(family="hint", body=edit_hint, tone="action")
            action = str(payload.get("action") or "").strip().lower()
            action_ready = bool(payload.get("action_ready"))
            action_manage_target = str(payload.get("action_manage_target") or manage_target or "").strip()
            action_instruction = str(payload.get("action_instruction") or "").strip()
            action_stage = str(payload.get("action_stage") or "").strip()
            action_builtin_mode = str(payload.get("action_builtin_mode") or "").strip()
            if action == "manage_flow" and action_ready and action_manage_target and action_instruction:
                try:
                    self._run_manage_flow(
                        action_manage_target,
                        action_instruction,
                        stage=action_stage,
                        builtin_mode=action_builtin_mode,
                    )
                except Exception as exc:
                    error_text = f"{type(exc).__name__}: {exc}"
                    self._write_manage_note(family="error", body=error_text, tone="error")
                    self.notify(error_text, severity="error")
            if self._view_mode == "flows" and self._flows_screen_mode == "manage":
                self._refresh_manage_screen()
        if self._manage_chat_queue:
            next_request = self._manage_chat_queue.pop(0)
            self._begin_manage_chat(next_request)

    def on_manage_flow_message(self, message: ManageFlowMessage) -> None:
        self._manage_flow_busy = False
        if message.error_text:
            self._write_manage_note(family="error", body=message.error_text, tone="error")
            self.notify(message.error_text, severity="error")
            return
        payload = dict(message.payload or {})
        asset_key = str(payload.get("asset_key") or message.manage_target or "").strip()
        if asset_key:
            self._manage_cursor_asset_key = asset_key
        summary = str(dict(payload.get("manage_handoff") or {}).get("summary") or "managed flow updated").strip()
        self._write_transcript_note(
            family="manage",
            body=f"{asset_key or message.manage_target} {summary}",
        )
        self._write_manage_note(
            family="manage",
            body=f"{asset_key or message.manage_target} {summary}",
        )
        if self._manage_return_to_setup and str(payload.get("asset_kind") or "") == "template":
            asset_id = str(payload.get("asset_id") or "").strip()
            if asset_id:
                self._setup_catalog_flow = f"template:{asset_id}"
                self._manage_return_to_setup = False
                self._manage_seed_instruction = ""
                self._set_setup_stage("confirm")
                self._set_view_mode("setup")
                self._refresh_setup_screen()
                self.call_after_refresh(self._focus_active_view_control)
                return
        self._open_manage_center()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return
        target = str(event.item.name or event.item.id or "").strip()
        if self._view_mode == "history":
            self._history_cursor_flow_id = target
            self._workspace_detail_mode = "preview"
            self._update_history_detail(rows=self._flow_rows())
            return
        if self._view_mode == "setup":
            self._setup_cursor_key = target
            self._update_setup_detail()
            return
        if self._view_mode == "flows":
            if self._flows_screen_mode == "manage":
                self._manage_cursor_asset_key = target
                asset = next((row for row in self._manage_rows() if str(row.get("asset_key") or "").strip() == target), {})
                self.query_one("#flows-detail", Static).update(self._render_manage_detail(asset))
            else:
                self._design_cursor_key = target
                self._update_design_detail()
            return
        if self._view_mode == "settings":
            self._settings_cursor_key = target
            self.query_one("#settings-preview", Static).update(self._render_settings_preview())

    def on_key(self, event: events.Key) -> None:
        if isinstance(self.screen, ConfirmScreen):
            return
        if (
            self._view_mode == "flows"
            and self._flows_screen_mode == "manage"
            and self._command_input_has_focus()
            and event.key in {"up", "down", "enter", "escape"}
        ):
            if self._manage_picker.is_open:
                if event.key == "up":
                    self._manage_picker.move(-1)
                    self._refresh_manage_suggestion()
                    self._update_manage_picker()
                elif event.key == "down":
                    self._manage_picker.move(1)
                    self._refresh_manage_suggestion()
                    self._update_manage_picker()
                elif event.key == "enter":
                    if self._apply_manage_picker_selection():
                        event.prevent_default()
                        event.stop()
                        return
                else:
                    self._manage_picker.close()
                    self._update_manage_picker("")
                event.prevent_default()
                event.stop()
                return
        if self._view_mode == "history" and self._command_input_has_focus() and event.key in {"up", "down"}:
            event.prevent_default()
            event.stop()
            history_list = self.query_one("#history-list", ListView)
            history_list.focus()
            if event.key == "up":
                history_list.action_cursor_up()
            else:
                history_list.action_cursor_down()
            return
        if self._view_mode == "history" and not self._command_input_has_focus() and event.key in {"left", "right"}:
            event.prevent_default()
            event.stop()
            self._workspace_detail_mode = "timeline" if event.key == "right" else "preview"
            self._update_history_detail(rows=self._flow_rows())
            self._set_action_bar()
            return
        if self._view_mode == "flow" and event.key in {"shift+tab", "backtab"}:
            event.prevent_default()
            event.stop()
            self._set_flow_view_mode("workflow" if self._flow_view_mode == "supervisor" else "supervisor")
            return
        if event.key in {"up", "down", "pageup", "pagedown", "home", "end"} and self._scroll_active_transcript(event.key):
            event.prevent_default()
            event.stop()
            return
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            command_input = self._command_input()
            if not self._command_input_has_focus():
                command_input.focus()
            if getattr(command_input, "_suggestion", "") and command_input.cursor_position >= len(command_input.value):
                command_input.action_cursor_right()
            return
        if event.is_printable and event.character and not self._command_input_has_focus():
            event.prevent_default()
            event.stop()
            self._focus_command_input_with_text(event.character)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is None:
            return
        target = str(event.item.name or event.item.id or "").strip()
        if self._view_mode == "history":
            self._history_cursor_flow_id = target
            self._workspace_detail_mode = "preview"
            self._commit_history_selection()
            return
        if self._view_mode == "setup":
            self._setup_cursor_key = target
            self._apply_setup_selection(target)
            return
        if self._view_mode == "flows":
            if self._flows_screen_mode == "manage":
                self._manage_cursor_asset_key = target
                return
            self._design_cursor_key = target
            self._apply_design_selection(target)
            return
        if self._view_mode == "settings":
            self._settings_cursor_key = target
            self._toggle_setting(self._settings_cursor_key)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if isinstance(event.input, PasteAwareInput):
            raw = str(event.input.resolved_value() or "").strip()
        else:
            raw = str(event.value or "").strip()
        event.input.value = ""
        self._update_manage_picker("")
        if not raw:
            return
        if self._view_mode == "setup" and not raw.startswith("/"):
            self._handle_setup_input(raw)
            return
        if self._view_mode == "history" and not raw.startswith("/"):
            self.notify("History view only accepts slash commands.", severity="warning")
            return
        if self._view_mode == "flow" and not raw.startswith("/"):
            self._handle_flow_prompt(raw)
            return
        if self._view_mode == "flows" and not raw.startswith("/"):
            if self._flows_screen_mode == "manage":
                self._handle_manage_prompt(raw)
                return
            if (self._design_stage or "proposal") == "proposal":
                self._design_request = raw
                self._design_stage = "build"
                self._begin_design_build()
                return
            self.notify("Use the picker for this step.", severity="warning")
            return
        try:
            command = self._controller.parse_command(raw)
        except Exception as exc:
            self.notify(str(exc), severity="error")
            return
        try:
            self._handle_command(command.name, command.args)
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            self._write_transcript_note(family="error", body=error_text, tone="error")
            self.notify(error_text, severity="error")

    def on_input_changed(self, event: Input.Changed) -> None:
        if getattr(event.input, "id", "") != "command-input":
            return
        if self._view_mode == "flows" and self._flows_screen_mode == "manage":
            self._update_manage_picker(event.value)
            self._refresh_manage_suggestion()
            return
        if self._manage_picker.is_open:
            self._manage_picker.close()
            self._update_manage_picker("")

    def _handle_command(self, name: str, args: list[str]) -> None:
        target_flow_id = self._command_target_flow_id(name=name, args=args)
        availability = self._controller.command_availability(
            config=self._current_config,
            flow_id=target_flow_id,
            command_name=name,
        )
        if not availability.enabled:
            self.notify(availability.reason or f"/{name} is unavailable", severity="warning")
            return
        if name == "help":
            self._write_transcript_note(
                family="command",
                body=self._controller.help_text(config=self._current_config, flow_id=self._target_flow_id()),
            )
            return
        if name == "history":
            self._open_history()
            return
        if name == "flows":
            self.notify("/flows is deprecated; opening /manage.", severity="warning")
            self._open_manage_center()
            return
        if name == "settings":
            self._open_settings()
            return
        if name == "back":
            self._open_history()
            return
        if name == "list":
            self._open_manage_center()
            return
        if name == "preflight":
            snapshot = self._controller.launcher_snapshot(config=self._current_config)
            self._write_transcript_note(family="preflight", body=str(snapshot.get("preflight") or {}))
            return
        if name == "focus":
            flow_id = str(args[0] if args else "").strip()
            if not flow_id:
                self.notify("/focus requires a flow_id", severity="warning")
                return
            self._focus_flow(flow_id)
            self._back_to_flow()
            return
        if name == "manage":
            if not args:
                self._open_manage_center()
                return
            raw_first = str(args[0] if args else "").strip()
            if ":" in raw_first or raw_first in {"new", "last"}:
                manage_target = raw_first
                instruction = " ".join(args[1:]).strip()
            else:
                self.notify("/manage now targets shared assets; use template:<id> or builtin:<id>.", severity="warning")
                self._open_manage_center()
                return
            if str(manage_target or "").startswith("instance:") or str(manage_target or "").startswith("flow_") or manage_target == "last":
                self.notify("Instance definitions now belong to the single-flow page, not /manage.", severity="warning")
                if self._target_flow_id():
                    self._focus_flow(self._target_flow_id())
                    self._back_to_flow()
                else:
                    self._open_history()
                return
            self._run_manage_flow(manage_target, instruction)
            return
        if name == "new":
            self._open_setup()
            return
        if name == "follow":
            if args:
                token = str(args[0] or "").strip().lower()
                if token not in {"on", "off"}:
                    self.notify("/follow accepts on|off", severity="warning")
                    return
                self._session_preferences["auto_follow"] = token == "on"
                self._apply_transcript_preferences()
            self._write_transcript_note(
                family="settings",
                body=f"auto_follow={'on' if self._session_preferences.get('auto_follow') else 'off'}",
            )
            self._refresh_settings_screen()
            return
        if name == "filter":
            token = str(args[0] if args else "").strip().lower()
            if token not in TRANSCRIPT_FILTERS:
                self.notify(f"/filter accepts {'|'.join(TRANSCRIPT_FILTERS)}", severity="warning")
                return
            self._session_preferences["transcript_filter"] = token
            self._reload_transcript(self._target_flow_id())
            self._refresh_settings_screen()
            return
        if name == "runtime-events":
            token = str(args[0] if args else "").strip().lower()
            if token not in {"on", "off"}:
                self.notify("/runtime-events accepts on|off", severity="warning")
                return
            self._session_preferences["show_runtime_events"] = token == "on"
            self._reload_transcript(self._target_flow_id())
            self._refresh_settings_screen()
            return
        if name == "status":
            flow_id = target_flow_id
            self._write_transcript_note(
                family="status",
                body=str(self._controller.status_payload(config=self._current_config, flow_id=flow_id)),
            )
            return
        if name == "inspect":
            flow_id = target_flow_id
            self._focus_flow(flow_id)
            self._back_to_flow()
            return
        if name == "artifacts":
            flow_id = target_flow_id
            artifacts = self._controller.artifacts_payload(config=self._current_config, flow_id=flow_id)
            self._write_transcript_note(family="artifact", body=str(artifacts))
            return
        if name == "resume":
            raw_target = str(args[0] if args else (self._selected_flow_id or self._current_flow_id or "last")).strip()
            prepared = self._controller.prepare_resume(
                config=self._current_config,
                flow_id="" if raw_target == "last" else raw_target,
                use_last=raw_target == "last",
            )
            self._begin_run(prepared, stream_enabled=True)
            return
        if name == "pause":
            self.action_pause_flow()
            return
        if name == "append":
            instruction = " ".join(args).strip()
            if not instruction:
                self.notify("/append requires text", severity="warning")
                return
            self._apply_action("append_instruction", instruction=instruction)
            return
        if name == "resume-flow":
            self.action_resume_flow()
            return
        if name == "retry":
            self.action_retry_phase()
            return
        if name == "abort":
            self.action_abort_flow()
            return
        self.notify(f"Unknown command: /{name}", severity="warning")

    def _handle_flow_prompt(self, text: str) -> None:
        instruction = str(text or "").strip()
        flow_id = self._target_flow_id()
        if not flow_id:
            self.notify("No flow selected.", severity="warning")
            return
        availability = self._controller.command_availability(
            config=self._current_config,
            flow_id=flow_id,
            command_name="append",
        )
        if not availability.enabled:
            self.notify(availability.reason or "Current flow cannot accept supervisor input.", severity="warning")
            return
        status = self._selected_flow_status(flow_id)
        receipt = self._apply_action("append_instruction", instruction=instruction)
        if status == "running":
            self._write_transcript_note(
                family="action",
                body=f"queued to running session {flow_id}: {instruction}",
                tone="action",
            )
        if not receipt:
            self.notify("Supervisor instruction queued.", severity="information")

    def _handle_manage_prompt(self, text: str) -> None:
        request = parse_manage_prompt(text)
        if not request.raw_text:
            return
        if request.manage_target.startswith("instance:") or request.manage_target.startswith("flow_") or request.manage_target == "last":
            self.notify("Instance definitions now belong to the single-flow page, not /manage.", severity="warning")
            return
        if not request.instruction:
            self.notify("Add a question after selecting an asset.", severity="warning")
            return
        self._enqueue_manage_prompt(request)

    def _enqueue_manage_prompt(self, request: ManagePromptRequest) -> None:
        if self._manage_chat_busy:
            self._manage_chat_queue.append(request)
            target = request.manage_target or "manager"
            self._write_manage_note(
                family="queue",
                body=f"{target} queued · {request.instruction}",
                tone="action",
            )
            self.notify("Manager request queued to the current session.", severity="information")
            return
        self._begin_manage_chat(request)

    def _begin_manage_chat(self, request: ManagePromptRequest) -> None:
        if self._manage_chat_busy:
            return
        self._manage_chat_busy = True
        self._manage_chat_started_at = time.time()
        target = request.manage_target or self._manage_cursor_asset_key or "manager"
        self._write_manage_note(family="user", body=f"{target} · {request.instruction}", tone="default")

        def _target() -> None:
            try:
                payload = self._controller.manage_chat(
                    config=self._current_config,
                    manage_target=request.manage_target,
                    instruction=request.instruction,
                    manager_session_id=self._manage_chat_session_id,
                )
            except Exception as exc:
                self.call_from_thread(
                    self.post_message,
                    ManageChatMessage(request=request, payload={}, error_text=f"{type(exc).__name__}: {exc}"),
                )
                return
            self.call_from_thread(self.post_message, ManageChatMessage(request=request, payload=payload))

        threading.Thread(target=_target, daemon=True).start()

    def _run_manage_flow(
        self,
        manage_target: str,
        instruction: str,
        *,
        stage: str = "",
        builtin_mode: str = "",
    ) -> None:
        target = str(manage_target or "new").strip() or "new"
        instruction_text = str(instruction or "").strip()
        stage_text = str(stage or "").strip()
        builtin_mode_text = str(builtin_mode or "").strip()
        if self._manage_flow_busy:
            self.notify("Manager build already in progress.", severity="warning")
            return
        self._manage_flow_busy = True
        self._write_manage_note(
            family="user",
            body=f"{target} · {instruction_text}",
            tone="default",
        )

        def _target() -> None:
            try:
                payload = self._controller.manage_flow(
                    config=self._current_config,
                    manage_target=target,
                    instruction=instruction_text,
                    stage=stage_text,
                    builtin_mode=builtin_mode_text,
                )
            except Exception as exc:
                self.call_from_thread(
                    self.post_message,
                    ManageFlowMessage(manage_target=target, payload={}, error_text=f"{type(exc).__name__}: {exc}"),
                )
                return
            self.call_from_thread(self.post_message, ManageFlowMessage(manage_target=target, payload=payload))

        threading.Thread(target=_target, daemon=True).start()

    def _target_flow_id(self) -> str:
        return self._selected_flow_id or self._current_flow_id

    def _command_target_flow_id(self, *, name: str, args: list[str]) -> str:
        if name in {"status", "inspect", "artifacts"} and args:
            return str(args[0] or "").strip()
        return self._target_flow_id()

    def _apply_action(self, action_type: str, *, instruction: str = "") -> dict[str, Any]:
        flow_id = self._target_flow_id()
        if not flow_id:
            self.notify("No flow selected.", severity="warning")
            return {}
        receipt = self._controller.apply_action(
            config=self._current_config,
            flow_id=flow_id,
            action_type=action_type,
            instruction=instruction,
        )
        self._write_transcript_note(family="action", body=str(receipt))
        self._refresh_snapshot()
        return receipt

    def _confirm_and_apply(self, action_type: str, prompt: str) -> None:
        flow_id = self._target_flow_id()
        if not flow_id:
            self.notify("No flow selected.", severity="warning")
            return

        def _after(result: bool) -> None:
            if not result:
                return
            self._apply_action(action_type)

        self.push_screen(ConfirmScreen(prompt), _after)

    def action_refresh_snapshot(self) -> None:
        self._refresh_snapshot()

    def action_open_selected(self) -> None:
        if self._view_mode == "history":
            self._commit_history_selection()
            return
        if self._view_mode == "setup":
            self._apply_setup_selection(self._setup_cursor_key)
            return
        if self._view_mode == "flows":
            if self._flows_screen_mode == "manage":
                self._focus_command_input()
                return
            self._apply_design_selection(self._design_cursor_key)
            return
        if self._view_mode == "settings":
            self._toggle_setting(self._settings_cursor_key)
            return
        if self._view_mode == "flow":
            self._remember_flow_transcript_scroll()
            self._reload_transcript(self._target_flow_id())
            self._refresh_flow_view()
            self._set_action_bar()
            return
        self._refresh_flow_view()

    def action_pause_flow(self) -> None:
        availability = self._controller.command_availability(
            config=self._current_config,
            flow_id=self._target_flow_id(),
            command_name="pause",
        )
        if not availability.enabled:
            self.notify(availability.reason or "/pause is unavailable", severity="warning")
            return
        self._confirm_and_apply("pause", "Pause the current flow?")

    def action_resume_flow(self) -> None:
        availability = self._controller.command_availability(
            config=self._current_config,
            flow_id=self._target_flow_id(),
            command_name="resume-flow",
        )
        if not availability.enabled:
            self.notify(availability.reason or "/resume-flow is unavailable", severity="warning")
            return
        self._apply_action("resume")

    def action_retry_phase(self) -> None:
        availability = self._controller.command_availability(
            config=self._current_config,
            flow_id=self._target_flow_id(),
            command_name="retry",
        )
        if not availability.enabled:
            self.notify(availability.reason or "/retry is unavailable", severity="warning")
            return
        self._confirm_and_apply("retry_current_phase", "Retry the current phase?")

    def action_abort_flow(self) -> None:
        availability = self._controller.command_availability(
            config=self._current_config,
            flow_id=self._target_flow_id(),
            command_name="abort",
        )
        if not availability.enabled:
            self.notify(availability.reason or "/abort is unavailable", severity="warning")
            return
        self._confirm_and_apply("abort", "Abort the current flow?")
