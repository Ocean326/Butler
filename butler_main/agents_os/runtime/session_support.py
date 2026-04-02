from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp-{uuid4().hex[:8]}")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _coerce_counter(value: Any) -> tuple[int | None, str]:
    text = str(value or "").strip()
    if not text:
        return None, ""
    try:
        return int(text), text
    except Exception:
        return None, text


def merge_session_snapshots(local_session: Mapping[str, Any] | None, persisted_session: Mapping[str, Any] | None) -> tuple[dict[str, Any], bool]:
    local = dict(local_session or {})
    persisted = dict(persisted_session or {})
    local_counter, _ = _coerce_counter(local.get("conversation_cursor"))
    persisted_counter, _ = _coerce_counter(persisted.get("conversation_cursor"))

    if local_counter is not None and persisted_counter is not None:
        if persisted_counter > local_counter:
            return persisted, True
        if local_counter > persisted_counter:
            return local, False

    local_updated = str(local.get("updated_at") or "").strip()
    persisted_updated = str(persisted.get("updated_at") or "").strip()
    if persisted_updated > local_updated:
        return persisted, True
    return local or persisted, False


@dataclass(slots=True)
class RuntimeSessionCheckpoint:
    checkpoint_id: str = field(default_factory=lambda: _new_id("checkpoint"))
    instance_id: str = ""
    session_id: str = ""
    status: str = ""
    run_input: dict[str, Any] = field(default_factory=dict)
    session: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "RuntimeSessionCheckpoint":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


class FileSessionCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, checkpoint: RuntimeSessionCheckpoint) -> RuntimeSessionCheckpoint:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(checkpoint.to_dict(), ensure_ascii=False) + "\n")
        return checkpoint

    def get(self, checkpoint_id: str) -> RuntimeSessionCheckpoint | None:
        if not self.path.exists():
            return None
        target = str(checkpoint_id or "").strip()
        if not target:
            return None
        with self.path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
        for line in reversed(lines):
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if str(payload.get("checkpoint_id") or "").strip() == target:
                return RuntimeSessionCheckpoint.from_dict(payload)
        return None

    def latest(self) -> RuntimeSessionCheckpoint | None:
        if not self.path.exists():
            return None
        latest_payload: dict[str, Any] | None = None
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    latest_payload = json.loads(line)
                except Exception:
                    continue
        return RuntimeSessionCheckpoint.from_dict(latest_payload) if latest_payload else None

    def write_current(self, checkpoint: RuntimeSessionCheckpoint) -> None:
        current_path = self.path.with_name("current.json")
        _write_text_atomic(current_path, json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=2))
