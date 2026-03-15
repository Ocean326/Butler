from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Protocol

from butler_paths import LOCAL_MEMORY_DIR_REL, RECENT_MEMORY_DIR_REL, SELF_MIND_DIR_REL, TASK_LEDGER_REL, resolve_butler_root


@dataclass(frozen=True)
class MemoryRecordEnvelope:
    record_id: str
    scope: str
    record_type: str
    status: str
    stability: str
    confidence: float
    source_event_ids: tuple[str, ...]
    truth_owner: str
    relations: tuple[str, ...]
    updated_at: str
    render_profile: str


@dataclass(frozen=True)
class MemoryQuery:
    scope: str
    query_text: str = ""
    record_type: str = ""
    limit: int = 20


class EpisodicStore(Protocol):
    def append(self, event: dict) -> None: ...

    def query(self, query: MemoryQuery) -> list[dict]: ...


class SemanticStore(Protocol):
    def upsert(self, entry_id: str, payload: dict) -> None: ...

    def get(self, entry_id: str) -> dict | None: ...

    def query(self, query: MemoryQuery) -> list[dict]: ...


class SelfModelStore(Protocol):
    def upsert_thread(self, thread_id: str, payload: dict) -> None: ...

    def query(self, query: MemoryQuery) -> list[dict]: ...


class ProspectiveStore(Protocol):
    def upsert_intention(self, intention_id: str, payload: dict) -> None: ...

    def query(self, query: MemoryQuery) -> list[dict]: ...


class MemoryBackend(Protocol):
    @property
    def episodic(self) -> EpisodicStore: ...

    @property
    def semantic(self) -> SemanticStore: ...

    @property
    def self_model(self) -> SelfModelStore: ...

    @property
    def prospective(self) -> ProspectiveStore: ...


class FileJsonCollection:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _save(self, rows: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def append(self, row: dict, *, max_items: int = 2000) -> None:
        rows = self._load()
        rows.append(dict(row or {}))
        self._save(rows[-max_items:])

    def upsert(self, key: str, key_field: str, row: dict, *, max_items: int = 2000) -> None:
        key_text = str(key or "").strip()
        rows = self._load()
        replaced = False
        for index, item in enumerate(rows):
            if str(item.get(key_field) or "").strip() == key_text:
                rows[index] = dict(row or {})
                replaced = True
                break
        if not replaced:
            rows.append(dict(row or {}))
        self._save(rows[-max_items:])

    def get(self, key: str, key_field: str) -> dict | None:
        key_text = str(key or "").strip()
        if not key_text:
            return None
        for item in reversed(self._load()):
            if str(item.get(key_field) or "").strip() == key_text:
                return dict(item)
        return None

    def query(self, query: MemoryQuery) -> list[dict]:
        text = str(query.query_text or "").strip().lower()
        record_type = str(query.record_type or "").strip().lower()
        tokens = [token for token in re.split(r"\s+", text) if token] if text else []
        matched: list[dict] = []
        for item in reversed(self._load()):
            if record_type and str(item.get("record_type") or "").strip().lower() != record_type:
                continue
            if tokens:
                haystack = json.dumps(item, ensure_ascii=False).lower()
                if not all(token in haystack for token in tokens):
                    continue
            matched.append(dict(item))
            if len(matched) >= max(1, int(query.limit or 20)):
                break
        return matched


class FileEpisodicStore(EpisodicStore):
    def __init__(self, root: Path) -> None:
        self._collection = FileJsonCollection(root / "backend_episodic_events.json")

    def append(self, event: dict) -> None:
        row = dict(event or {})
        row.setdefault("scope", "recent")
        row.setdefault("record_type", "event")
        row.setdefault("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._collection.append(row)

    def query(self, query: MemoryQuery) -> list[dict]:
        return self._collection.query(query)


class FileSemanticStore(SemanticStore):
    def __init__(self, root: Path) -> None:
        self._collection = FileJsonCollection(root / "backend_semantic_entries.json")

    def upsert(self, entry_id: str, payload: dict) -> None:
        row = dict(payload or {})
        row.setdefault("entry_id", str(entry_id or "").strip())
        row.setdefault("record_type", "semantic")
        row.setdefault("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._collection.upsert(str(entry_id or "").strip(), "entry_id", row)

    def get(self, entry_id: str) -> dict | None:
        return self._collection.get(str(entry_id or "").strip(), "entry_id")

    def query(self, query: MemoryQuery) -> list[dict]:
        return self._collection.query(query)


class FileSelfModelStore(SelfModelStore):
    def __init__(self, root: Path) -> None:
        self._collection = FileJsonCollection(root / "backend_self_model_threads.json")

    def upsert_thread(self, thread_id: str, payload: dict) -> None:
        row = dict(payload or {})
        row.setdefault("thread_id", str(thread_id or "").strip())
        row.setdefault("record_type", "self_model")
        row.setdefault("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._collection.upsert(str(thread_id or "").strip(), "thread_id", row)

    def query(self, query: MemoryQuery) -> list[dict]:
        return self._collection.query(query)


class FileProspectiveStore(ProspectiveStore):
    def __init__(self, root: Path) -> None:
        self._collection = FileJsonCollection(root / "backend_prospective_intentions.json")

    def upsert_intention(self, intention_id: str, payload: dict) -> None:
        row = dict(payload or {})
        row.setdefault("intention_id", str(intention_id or "").strip())
        row.setdefault("record_type", "prospective")
        row.setdefault("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._collection.upsert(str(intention_id or "").strip(), "intention_id", row)

    def query(self, query: MemoryQuery) -> list[dict]:
        return self._collection.query(query)


class FileMemoryBackend(MemoryBackend):
    def __init__(self, workspace: str | Path | None = None) -> None:
        self.root = resolve_butler_root(workspace)
        self._backend_root = self.root / "butler_main" / "butler_bot_agent" / "agents" / "state" / "memory_backend"
        self._backend_root.mkdir(parents=True, exist_ok=True)
        self._episodic = FileEpisodicStore(self._backend_root)
        self._semantic = FileSemanticStore(self._backend_root)
        self._self_model = FileSelfModelStore(self._backend_root)
        self._prospective = FileProspectiveStore(self._backend_root)

    @property
    def episodic(self) -> EpisodicStore:
        return self._episodic

    @property
    def semantic(self) -> SemanticStore:
        return self._semantic

    @property
    def self_model(self) -> SelfModelStore:
        return self._self_model

    @property
    def prospective(self) -> ProspectiveStore:
        return self._prospective

    def describe_sources(self) -> dict:
        return {
            "recent_dir": str((self.root / RECENT_MEMORY_DIR_REL).resolve()),
            "local_memory_dir": str((self.root / LOCAL_MEMORY_DIR_REL).resolve()),
            "self_mind_dir": str((self.root / SELF_MIND_DIR_REL).resolve()),
            "task_ledger": str((self.root / TASK_LEDGER_REL).resolve()),
            "backend_root": str(self._backend_root.resolve()),
        }


def build_default_memory_backend(workspace: str | Path | None = None) -> FileMemoryBackend:
    return FileMemoryBackend(workspace)
