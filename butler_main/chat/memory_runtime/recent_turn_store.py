from __future__ import annotations

from datetime import datetime
import json
import re
import uuid
from pathlib import Path

from ..session_selection import resolve_active_chat_session_id
from .recent_scope_paths import resolve_recent_scope_dir
from ..session_modes import resolve_recent_profile


RECENT_MEMORY_FILE = "recent_memory.json"
RECENT_RAW_TURNS_FILE = "recent_raw_turns.json"
RECENT_SUMMARY_POOL_FILE = "recent_summary_pool.json"
PENDING_FOLLOWUP_MAX_AGE_SECONDS = 10 * 60
RECENT_MAX_ITEMS = 20
RECENT_VISIBLE_MAX_ITEMS = 10
RECENT_SUMMARY_MAX_ITEMS = 5
RECENT_SUMMARY_WINDOW_SIZE = 10
RECENT_INJECTION_MAX_CHARS = 10000


class ChatRecentTurnStore:
    """Chat-owned recent-turn lifecycle storage.

    This intentionally covers only the front-door talk pending-turn lifecycle,
    so chat can stop relying on the legacy manager for simple turn bookkeeping.
    """

    def __init__(self, *, config_provider) -> None:
        self._config_provider = config_provider

    def begin_turn(
        self,
        user_prompt: str,
        workspace: str,
        *,
        session_scope_id: str = "",
    ) -> tuple[str, dict | None]:
        entry_id = str(uuid.uuid4())
        active_chat_session_id = resolve_active_chat_session_id(workspace, session_scope_id=session_scope_id)
        entries = self._load_recent_entries(workspace, session_scope_id=session_scope_id)
        self._expire_stale_pending_entries(entries)
        previous_pending = self._find_latest_pending_entry(
            self._filter_chat_session_payload(entries, chat_session_id=active_chat_session_id)
        )
        entries.append(
            self._build_provisional_recent_entry(
                entry_id,
                user_prompt,
                workspace=workspace,
                session_scope_id=session_scope_id,
            )
        )
        self._save_recent_entries(workspace, entries[-RECENT_MAX_ITEMS:], session_scope_id=session_scope_id)
        return entry_id, previous_pending

    def load_recent_entries(
        self,
        workspace: str,
        *,
        session_scope_id: str = "",
        chat_session_id: str | None = None,
    ) -> list[dict]:
        return self._filter_chat_session_payload(
            self._load_recent_entries(workspace, session_scope_id=session_scope_id),
            chat_session_id=chat_session_id,
        )

    def load_recent_raw_turns(
        self,
        workspace: str,
        *,
        session_scope_id: str = "",
        chat_session_id: str | None = None,
    ) -> list[dict]:
        path = self._raw_turns_file(workspace, session_scope_id=session_scope_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return self._filter_chat_session_payload(
            [dict(item) for item in payload if isinstance(item, dict)],
            chat_session_id=chat_session_id,
        )

    def load_recent_summary_pool(
        self,
        workspace: str,
        *,
        session_scope_id: str = "",
        chat_session_id: str | None = None,
    ) -> list[dict]:
        path = self._summary_pool_file(workspace, session_scope_id=session_scope_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return self._filter_chat_session_payload(
            [dict(item) for item in payload if isinstance(item, dict)],
            chat_session_id=chat_session_id,
        )

    def pending_followup_max_age_seconds(self) -> int:
        cfg = self._config_provider() or {}
        memory_cfg = cfg.get("memory") if isinstance(cfg.get("memory"), dict) else {}
        talk_recent = memory_cfg.get("talk_recent") if isinstance(memory_cfg.get("talk_recent"), dict) else {}
        try:
            return max(60, int(talk_recent.get("pending_followup_max_age_seconds", PENDING_FOLLOWUP_MAX_AGE_SECONDS)))
        except Exception:
            return PENDING_FOLLOWUP_MAX_AGE_SECONDS

    def recent_max_items(self) -> int:
        cfg = self._config_provider() or {}
        memory_cfg = cfg.get("memory") if isinstance(cfg.get("memory"), dict) else {}
        talk_recent = memory_cfg.get("talk_recent") if isinstance(memory_cfg.get("talk_recent"), dict) else {}
        try:
            return max(1, min(200, int(talk_recent.get("prompt_visible_items", RECENT_MAX_ITEMS))))
        except Exception:
            return RECENT_MAX_ITEMS

    def recent_visible_items(self, recent_mode: str = "default") -> int:
        cfg = self._config_provider() or {}
        profile = resolve_recent_profile(recent_mode, cfg)
        try:
            return max(1, min(50, int(profile.get("visible_items", RECENT_VISIBLE_MAX_ITEMS))))
        except Exception:
            return RECENT_VISIBLE_MAX_ITEMS

    def recent_summary_items(self, recent_mode: str = "default") -> int:
        cfg = self._config_provider() or {}
        profile = resolve_recent_profile(recent_mode, cfg)
        try:
            return max(1, min(20, int(profile.get("summary_items", RECENT_SUMMARY_MAX_ITEMS))))
        except Exception:
            return RECENT_SUMMARY_MAX_ITEMS

    def recent_summary_window_size(self) -> int:
        cfg = self._config_provider() or {}
        memory_cfg = cfg.get("memory") if isinstance(cfg.get("memory"), dict) else {}
        talk_recent = memory_cfg.get("talk_recent") if isinstance(memory_cfg.get("talk_recent"), dict) else {}
        try:
            return max(2, min(50, int(talk_recent.get("summary_window_size", RECENT_SUMMARY_WINDOW_SIZE))))
        except Exception:
            return RECENT_SUMMARY_WINDOW_SIZE

    def recent_max_chars(self, recent_mode: str = "default") -> int:
        cfg = self._config_provider() or {}
        profile = resolve_recent_profile(recent_mode, cfg)
        try:
            return max(1000, min(200000, int(profile.get("prompt_max_chars", RECENT_INJECTION_MAX_CHARS))))
        except Exception:
            return RECENT_INJECTION_MAX_CHARS

    def _recent_file(self, workspace: str, *, session_scope_id: str = "") -> Path:
        path = resolve_recent_scope_dir(workspace, session_scope_id=session_scope_id) / RECENT_MEMORY_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _raw_turns_file(self, workspace: str, *, session_scope_id: str = "") -> Path:
        path = resolve_recent_scope_dir(workspace, session_scope_id=session_scope_id) / RECENT_RAW_TURNS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _summary_pool_file(self, workspace: str, *, session_scope_id: str = "") -> Path:
        path = resolve_recent_scope_dir(workspace, session_scope_id=session_scope_id) / RECENT_SUMMARY_POOL_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _load_recent_entries(self, workspace: str, *, session_scope_id: str = "") -> list[dict]:
        path = self._recent_file(workspace, session_scope_id=session_scope_id)
        scoped_entries = self._read_recent_entries_from_path(path)
        if scoped_entries or path.exists():
            return scoped_entries
        if not self._should_bootstrap_from_legacy_global(session_scope_id):
            return []
        legacy_entries = self._read_recent_entries_from_path(self._recent_file(workspace, session_scope_id=""))
        if any(str((item or {}).get("session_scope_id") or "").strip() for item in legacy_entries):
            return []
        return legacy_entries

    def _save_recent_entries(self, workspace: str, entries: list[dict], *, session_scope_id: str = "") -> None:
        path = self._recent_file(workspace, session_scope_id=session_scope_id)
        scope_id = str(session_scope_id or "").strip()
        normalized: list[dict] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            current = dict(item)
            if scope_id and not str(current.get("session_scope_id") or "").strip():
                current["session_scope_id"] = scope_id
            normalized.append(current)
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_provisional_recent_entry(
        self,
        entry_id: str,
        user_prompt: str,
        *,
        workspace: str,
        session_scope_id: str = "",
    ) -> dict:
        prompt_text = re.sub(r"\s+", " ", str(user_prompt or "").strip())
        topic_source = prompt_text or "本轮对话"
        entry = {
            "memory_id": entry_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "topic": topic_source[:18] or "本轮对话",
            "summary": "状态：正在回复中",
            "memory_scope": "talk",
            "memory_stream": "talk",
            "event_type": "conversation_turn",
            "raw_user_prompt": prompt_text[:500],
            "status": "replying",
            "next_actions": [],
            "salience": 0.2,
            "confidence": 0.2,
            "derived_from": ["pending-turn"],
            "context_tags": [],
            "mental_notes": [],
            "relationship_signals": [],
            "relation_signal": {},
            "active_window": "current",
            "subconscious": {"trigger_level": 0},
            "long_term_candidate": {
                "should_write": False,
                "title": "",
                "summary": "",
                "keywords": [],
            },
        }
        scope_id = str(session_scope_id or "").strip()
        if scope_id:
            entry["session_scope_id"] = scope_id
            active_chat_session_id = resolve_active_chat_session_id(
                workspace=workspace,
                session_scope_id=scope_id,
            )
            if active_chat_session_id:
                entry["chat_session_id"] = active_chat_session_id
        return entry

    def _find_latest_pending_entry(self, entries: list[dict]) -> dict | None:
        for item in reversed(entries or []):
            if isinstance(item, dict) and str(item.get("status") or "") == "replying":
                return item
        return None

    def _expire_stale_pending_entries(self, entries: list[dict]) -> None:
        now = datetime.now()
        for item in entries or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "").strip() != "replying":
                continue
            entry_time = self._parse_entry_time(item)
            if not entry_time:
                continue
            if (now - entry_time).total_seconds() < self.pending_followup_max_age_seconds():
                continue
            topic = str(item.get("topic") or item.get("raw_user_prompt") or "本轮对话").strip()
            summary = str(item.get("summary") or "").strip()
            item["status"] = "interrupted"
            if not summary or "正在回复中" in summary:
                item["summary"] = f"状态：上一轮对话未完成并已按超时中断处理，主题：{topic[:40]}"[:160]

    def _parse_entry_time(self, entry: dict) -> datetime | None:
        raw = str((entry or {}).get("timestamp") or "").strip()
        if not raw:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _read_recent_entries_from_path(path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    @staticmethod
    def _should_bootstrap_from_legacy_global(session_scope_id: str) -> bool:
        scope_id = str(session_scope_id or "").strip().lower()
        return scope_id.startswith("feishu:") or scope_id.startswith("cli:")

    @staticmethod
    def _filter_chat_session_payload(payload: list[dict], *, chat_session_id: str | None = None) -> list[dict]:
        if chat_session_id is None:
            return [dict(item) for item in payload if isinstance(item, dict)]
        target = str(chat_session_id or "").strip()
        if not target:
            return [dict(item) for item in payload if not str(item.get("chat_session_id") or "").strip()]
        filtered: list[dict] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            if str(item.get("chat_session_id") or "").strip() == target:
                filtered.append(dict(item))
        return filtered


__all__ = ["ChatRecentTurnStore"]
