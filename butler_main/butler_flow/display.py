from __future__ import annotations

import json
from typing import Any

from .events import FlowUiEventCallback, build_flow_ui_event


class FlowDisplay:
    supports_terminal_stream = True

    def __init__(self, stdout, stderr) -> None:
        self._stdout = stdout
        self._stderr = stderr

    def write(self, text: str = "", *, err: bool = False) -> None:
        stream = self._stderr if err else self._stdout
        stream.write(text)
        if not text.endswith("\n"):
            stream.write("\n")
        stream.flush()

    def write_json(self, payload: dict[str, Any]) -> None:
        self._stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        self._stdout.flush()

    def write_jsonl(self, payload: dict[str, Any]) -> None:
        self._stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._stdout.flush()

    @staticmethod
    def truncate(value: str, *, limit: int = 88) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        head = max(16, (limit - 3) // 2)
        tail = max(12, limit - head - 3)
        return f"{text[:head]}...{text[-tail:]}"


class RichFlowDisplay(FlowDisplay):
    def write_status_block(self, *, title: str, rows: list[str]) -> None:
        safe_title = str(title or "").strip() or "butler-flow"
        self.write(f"┌─ {safe_title} " + "─" * 16)
        for row in list(rows or []):
            self.write(f"│ {row}")
        self.write("└" + "─" * 30)


class EventFlowDisplay(FlowDisplay):
    supports_terminal_stream = False

    def __init__(self, *, event_callback: FlowUiEventCallback | None = None) -> None:
        super().__init__(stdout=None, stderr=None)
        self._event_callback = event_callback

    def write(self, text: str = "", *, err: bool = False) -> None:
        callback = self._event_callback
        if not callable(callback):
            return
        message = str(text or "").rstrip("\n")
        if not message:
            return
        callback(
            build_flow_ui_event(
                kind="error" if err else "warning",
                message=message,
                payload={"text": message, "stream": "stderr" if err else "stdout"},
            )
        )

    def write_json(self, payload: dict[str, Any]) -> None:
        callback = self._event_callback
        if not callable(callback):
            return
        callback(
            build_flow_ui_event(
                kind="warning",
                message=json.dumps(dict(payload or {}), ensure_ascii=False),
                payload=dict(payload or {}),
            )
        )


class JsonlFlowDisplay(FlowDisplay):
    supports_terminal_stream = False

    def write(self, text: str = "", *, err: bool = False) -> None:
        message = str(text or "").rstrip("\n")
        if not message:
            return
        self.write_jsonl(
            build_flow_ui_event(
                kind="error" if err else "warning",
                message=message,
                payload={"text": message, "stream": "stderr" if err else "stdout"},
            ).to_dict()
        )

    def write_json(self, payload: dict[str, Any]) -> None:
        self.write_jsonl(payload)
