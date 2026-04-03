from __future__ import annotations

import json
from pathlib import Path

from .models import LedgerEvent


class FileLedgerEventStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def events_path(self) -> Path:
        return self.root / "ledger_events.jsonl"

    def append(self, event: LedgerEvent) -> LedgerEvent:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def list_events(self, mission_id: str = "", event_type: str = "") -> list[LedgerEvent]:
        if not self.events_path.exists():
            return []
        target_mission_id = str(mission_id or "").strip()
        target_event_type = str(event_type or "").strip()
        events: list[LedgerEvent] = []
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                event = LedgerEvent.from_dict(payload)
                if target_mission_id and event.mission_id != target_mission_id:
                    continue
                if target_event_type and event.event_type != target_event_type:
                    continue
                events.append(event)
        return events
