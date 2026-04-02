from __future__ import annotations

import json
import re
import threading
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from butler_main.agents_os.runtime import RuntimeRequestState
from butler_main.agents_os.runtime.writeback import AsyncWritebackRunner

from .memory_runtime import (
    ChatRecentPromptAssembler,
    ChatRecentTurnStore,
    iter_recent_scope_dirs,
    load_scope_metadata,
    resolve_recent_scope_dir,
)
from .session_selection import (
    resolve_active_chat_session_id,
)


RECENT_MEMORY_FILE = "recent_memory.json"
RECENT_RAW_TURNS_FILE = "recent_raw_turns.json"
RECENT_RAW_TURN_MAX_ITEMS = 40
RECENT_SUMMARY_POOL_FILE = "recent_summary_pool.json"
LONG_MEMORY_QUEUE_FILE = "long_memory_queue.json"
RUNTIME_SESSION_FILE = "runtime_session.json"
RECENT_SUMMARY_POOL_MAX_ITEMS = 5
_LEADING_PROCESS_ORDINAL_RE = re.compile(
    r"^\s*(?:(?:step|步骤)\s*)?(?:第\s*)?\d{1,2}(?:\s*[.:：、]\s*|\s*\)\s*)",
    re.IGNORECASE,
)


class ChatLightMemoryState:
    """Chat-only recent-memory runtime scoped by conversation/session."""

    def __init__(self, *, config_provider, window_summarizer=None, long_memory_governor=None) -> None:
        self._config_provider = config_provider
        self._window_summarizer = window_summarizer
        self._long_memory_governor = long_memory_governor
        self._memory_lock = threading.Lock()
        self._runtime_request_state = RuntimeRequestState()
        self._startup_recovered = False
        self._startup_lock = threading.Lock()
        self._turn_store = ChatRecentTurnStore(config_provider=config_provider)
        self._prompt_assembler = ChatRecentPromptAssembler(turn_store=self._turn_store)

    def get_runtime_request_override(self, *, workspace: str = "", session_scope_id: str = "", preferred_cli: str = "") -> dict:
        override = self._runtime_request_state.get_override()
        if override:
            return override
        return self.get_runtime_request_override_for_session(
            workspace=workspace,
            session_scope_id=session_scope_id,
            preferred_cli=preferred_cli,
        )

    def get_runtime_request_override_for_session(
        self,
        *,
        workspace: str = "",
        session_scope_id: str = "",
        preferred_cli: str = "",
    ) -> dict:
        scope_id = str(session_scope_id or "").strip()
        if not workspace or not scope_id:
            return {}
        binding = self._load_runtime_session_binding(workspace, session_scope_id=scope_id, provider=preferred_cli)
        return {"_butler_session_binding": binding} if binding else {}

    def remember_runtime_session(
        self,
        *,
        workspace: str,
        session_scope_id: str,
        runtime_request: dict[str, Any] | None,
        execution_metadata: dict[str, Any] | None,
    ) -> None:
        scope_id = str(session_scope_id or "").strip()
        if not workspace or not scope_id:
            return
        metadata = dict(execution_metadata or {})
        external_session = dict(metadata.get("external_session") or {})
        provider = str(
            external_session.get("provider")
            or metadata.get("provider")
            or dict(runtime_request or {}).get("cli")
            or ""
        ).strip()
        if not provider:
            return
        binding = {
            "provider": provider,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "thread_id": str(external_session.get("thread_id") or "").strip(),
            "resume_capable": bool(external_session.get("resume_capable")),
            "resume_durable": bool(external_session.get("resume_durable")),
            "external_session": external_session,
            "recovery_state": dict(metadata.get("recovery_state") or {}),
            "runtime_request": {
                "cli": str(dict(runtime_request or {}).get("cli") or metadata.get("provider") or "").strip(),
                "model": str(dict(runtime_request or {}).get("model") or "").strip(),
                "profile": str(dict(runtime_request or {}).get("profile") or "").strip(),
            },
        }
        self._save_runtime_session_binding(workspace, session_scope_id=scope_id, provider=provider, payload=binding)

    def begin_pending_turn(self, user_prompt: str, workspace: str, session_scope_id: str = ""):
        return self._turn_store.begin_turn(user_prompt, workspace, session_scope_id=session_scope_id)

    def prepare_user_prompt_with_recent(
        self,
        user_prompt: str,
        *,
        exclude_memory_id: str,
        previous_pending=None,
        recent_mode: str = "default",
        session_scope_id: str = "",
        mode_state_override=None,
        chat_session_state_override=None,
    ) -> str:
        return self._prompt_assembler.prepare_turn_input(
            user_prompt,
            exclude_memory_id=exclude_memory_id,
            previous_pending=previous_pending,
            recent_mode=recent_mode,
            session_scope_id=session_scope_id,
            mode_state_override=mode_state_override,
            chat_session_state_override=chat_session_state_override,
        )

    def recover_pending_recent_entries_on_startup(self, workspace: str) -> None:
        with self._startup_lock:
            if self._startup_recovered:
                return
            session_scopes = self._iter_known_session_scopes(workspace)
            with self._memory_lock:
                recovered_count = 0
                for session_scope_id in session_scopes:
                    entries = self._load_recent_entries(workspace, session_scope_id=session_scope_id)
                    changed = False
                    for item in entries:
                        if not isinstance(item, dict):
                            continue
                        if str(item.get("status") or "").strip() != "replying":
                            continue
                        topic = str(item.get("topic") or item.get("raw_user_prompt") or "本轮对话").strip()
                        summary = str(item.get("summary") or "").strip()
                        item["status"] = "interrupted"
                        if not summary or "正在回复中" in summary:
                            item["summary"] = f"状态：上一轮对话在写回前中断，主题：{topic[:40]}"[:160]
                        changed = True
                        recovered_count += 1
                    if changed:
                        self._save_recent_entries(workspace, entries, session_scope_id=session_scope_id)
                if recovered_count > 0:
                    print(f"[recent-recover] 启动时已修复 pending 记忆，共 {recovered_count} 条", flush=True)
            cfg = self._config_provider() or {}
            timeout = int(cfg.get("agent_timeout", 300))
            model = str(cfg.get("agent_model") or "auto")
            for session_scope_id in session_scopes:
                self._maintain_summary_pipeline(
                    workspace,
                    timeout=timeout,
                    model=model,
                    session_scope_id=session_scope_id,
                )
                self._process_long_memory_queue(
                    workspace,
                    timeout=timeout,
                    model=model,
                    session_scope_id=session_scope_id,
                )
            self._startup_recovered = True

    def write_recent_completion_fallback(
        self,
        memory_id: str | None,
        user_prompt: str,
        assistant_reply: str,
        raw_reply: str,
        workspace: str,
        session_scope_id: str = "",
        process_events: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        active_chat_session_id = resolve_active_chat_session_id(workspace, session_scope_id=session_scope_id)
        entry_id = str(memory_id or uuid.uuid4())
        entry = self._build_recent_entry(
            entry_id,
            user_prompt,
            assistant_reply,
            status="completed",
            session_scope_id=session_scope_id,
            chat_session_id=active_chat_session_id,
        )
        with self._memory_lock:
            entries = self._load_recent_entries(workspace, session_scope_id=session_scope_id)
            if not self._replace_recent_entry(entries, entry_id, entry):
                entries.append(entry)
            self._save_recent_entries(workspace, entries, session_scope_id=session_scope_id)
            self._upsert_recent_raw_turn(
                workspace,
                entry_id,
                entry,
                user_prompt,
                assistant_reply,
                raw_reply,
                session_scope_id=session_scope_id,
                process_events=process_events,
            )
        print(f"[recent-fallback] memory_id={entry_id} | summary={str(entry.get('summary') or '')[:120]}", flush=True)

    def finalize_recent_memory(
        self,
        memory_id: str | None,
        user_prompt: str,
        assistant_reply: str,
        raw_reply: str,
        workspace: str,
        timeout: int,
        model: str,
        suppress_task_merge: bool = False,
        session_scope_id: str = "",
        process_events: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        del suppress_task_merge
        active_chat_session_id = resolve_active_chat_session_id(workspace, session_scope_id=session_scope_id)
        entry_id = str(memory_id or uuid.uuid4())
        entry = self._build_recent_entry(
            entry_id,
            user_prompt,
            assistant_reply,
            status="completed",
            session_scope_id=session_scope_id,
            chat_session_id=active_chat_session_id,
        )
        with self._memory_lock:
            entries = self._load_recent_entries(workspace, session_scope_id=session_scope_id)
            if not self._replace_recent_entry(entries, entry_id, entry):
                entries.append(entry)
            self._save_recent_entries(workspace, entries, session_scope_id=session_scope_id)
            self._upsert_recent_raw_turn(
                workspace,
                entry_id,
                entry,
                user_prompt,
                assistant_reply,
                raw_reply,
                session_scope_id=session_scope_id,
                process_events=process_events,
            )
            current_count = len(entries)
        self._maintain_summary_pipeline(
            workspace,
            timeout=timeout,
            model=model,
            session_scope_id=session_scope_id,
        )
        self._process_long_memory_queue(
            workspace,
            timeout=timeout,
            model=model,
            session_scope_id=session_scope_id,
        )
        print(f"[记忆] 短期记忆已更新，当前 {current_count} 条, result_text={'有' if assistant_reply.strip() else '无'}", flush=True)
        print(
            f"[recent-finalized] memory_id={entry_id} | topic={str(entry.get('topic') or '')[:60]} | summary={str(entry.get('summary') or '')[:120]}",
            flush=True,
        )

    def backfill_recent_turns(
        self,
        turns: list[dict],
        workspace: str,
        *,
        session_scope_id: str = "",
    ) -> int:
        normalized_turns = self._normalize_backfill_turns(turns, session_scope_id=session_scope_id)
        if not normalized_turns:
            return 0
        with self._memory_lock:
            entries = self._load_recent_entries(workspace, session_scope_id=session_scope_id)
            raw_turns = self._load_recent_raw_turns(workspace, session_scope_id=session_scope_id)
            active_chat_session_id = resolve_active_chat_session_id(workspace, session_scope_id=session_scope_id)
            upserted = 0
            for turn in normalized_turns:
                memory_id = str(turn.get("memory_id") or "").strip()
                user_prompt = str(turn.get("user_prompt") or "")
                assistant_visible = str(turn.get("assistant_reply_visible") or "")
                assistant_raw = str(turn.get("assistant_reply_raw") or assistant_visible)
                if not memory_id or not assistant_visible:
                    continue
                if not self._has_equivalent_recent_raw_turn(
                    raw_turns,
                    memory_id=memory_id,
                    user_prompt=user_prompt,
                    assistant_reply_visible=assistant_visible,
                ):
                    entry = self._build_recent_entry(
                        memory_id,
                        user_prompt,
                        assistant_visible,
                        status=str(turn.get("status") or "completed").strip() or "completed",
                        session_scope_id=session_scope_id,
                        chat_session_id=active_chat_session_id,
                    )
                    timestamp_text = str(turn.get("timestamp") or "").strip()
                    if timestamp_text:
                        entry["timestamp"] = timestamp_text
                    topic_text = str(turn.get("topic") or "").strip()
                    if topic_text:
                        entry["topic"] = topic_text[:18]
                    summary_text = str(turn.get("summary") or "").strip()
                    if summary_text:
                        entry["summary"] = summary_text[:160]
                    if not self._replace_recent_entry(entries, memory_id, entry):
                        entries.append(entry)
                    raw_turn = self._build_backfill_raw_turn(
                        entry=entry,
                        turn=turn,
                        session_scope_id=session_scope_id,
                        chat_session_id=active_chat_session_id,
                    )
                    self._replace_or_append_recent_raw_turn(raw_turns, raw_turn)
                    upserted += 1
                    continue
                existing = self._find_recent_raw_turn(raw_turns, memory_id=memory_id)
                if existing is not None:
                    existing["assistant_reply_raw"] = assistant_raw
                    existing["assistant_reply_visible"] = assistant_visible
                    existing["assistant_reply"] = assistant_visible
                    existing["process_events"] = self._normalize_process_events(turn.get("process_events"))
                    if str(turn.get("timestamp") or "").strip():
                        existing["timestamp"] = str(turn.get("timestamp") or "").strip()
                    if str(turn.get("source_kind") or "").strip():
                        existing["source_kind"] = str(turn.get("source_kind") or "").strip()
                    if str(turn.get("source_chat_id") or "").strip():
                        existing["source_chat_id"] = str(turn.get("source_chat_id") or "").strip()
                    source_ids = [
                        str(item).strip()
                        for item in (turn.get("source_message_ids") or [])
                        if str(item).strip()
                    ]
                    if source_ids:
                        existing["source_message_ids"] = source_ids
            self._save_recent_entries(workspace, entries, session_scope_id=session_scope_id)
            self._save_recent_raw_turns(workspace, raw_turns, session_scope_id=session_scope_id)
        if upserted:
            print(
                f"[recent-backfill] session_scope_id={session_scope_id or '-'} turns={upserted}",
                flush=True,
            )
        return upserted

    def _recent_file(self, workspace: str, *, session_scope_id: str = ""):
        return resolve_recent_scope_dir(workspace, session_scope_id=session_scope_id) / RECENT_MEMORY_FILE

    def _recent_raw_turns_file(self, workspace: str, *, session_scope_id: str = ""):
        return resolve_recent_scope_dir(workspace, session_scope_id=session_scope_id) / RECENT_RAW_TURNS_FILE

    def _recent_summary_pool_file(self, workspace: str, *, session_scope_id: str = ""):
        return resolve_recent_scope_dir(workspace, session_scope_id=session_scope_id) / RECENT_SUMMARY_POOL_FILE

    def _long_memory_queue_file(self, workspace: str, *, session_scope_id: str = ""):
        return resolve_recent_scope_dir(workspace, session_scope_id=session_scope_id) / LONG_MEMORY_QUEUE_FILE

    def _runtime_session_file(self, workspace: str, *, session_scope_id: str = ""):
        return resolve_recent_scope_dir(workspace, session_scope_id=session_scope_id) / RUNTIME_SESSION_FILE

    def _load_recent_entries(self, workspace: str, *, session_scope_id: str = "") -> list[dict]:
        path = self._recent_file(workspace, session_scope_id=session_scope_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    def _save_recent_entries(self, workspace: str, entries: list[dict], *, session_scope_id: str = "") -> None:
        max_items = self._recent_store_max_items()
        trimmed = [dict(item) for item in entries if isinstance(item, dict)][-max_items:]
        self._recent_file(workspace, session_scope_id=session_scope_id).write_text(
            json.dumps(trimmed, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_recent_raw_turns(self, workspace: str, *, session_scope_id: str = "") -> list[dict]:
        path = self._recent_raw_turns_file(workspace, session_scope_id=session_scope_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    def _save_recent_raw_turns(self, workspace: str, payload: list[dict], *, session_scope_id: str = "") -> None:
        trimmed = [dict(item) for item in payload if isinstance(item, dict)][-RECENT_RAW_TURN_MAX_ITEMS:]
        self._recent_raw_turns_file(workspace, session_scope_id=session_scope_id).write_text(
            json.dumps(trimmed, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_recent_summary_pool(self, workspace: str, *, session_scope_id: str = "") -> list[dict]:
        path = self._recent_summary_pool_file(workspace, session_scope_id=session_scope_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    def _save_recent_summary_pool(self, workspace: str, payload: list[dict], *, session_scope_id: str = "") -> None:
        trimmed = [dict(item) for item in payload if isinstance(item, dict)][-RECENT_SUMMARY_POOL_MAX_ITEMS:]
        self._recent_summary_pool_file(workspace, session_scope_id=session_scope_id).write_text(
            json.dumps(trimmed, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_long_memory_queue(self, workspace: str, *, session_scope_id: str = "") -> list[dict]:
        path = self._long_memory_queue_file(workspace, session_scope_id=session_scope_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    def _save_long_memory_queue(self, workspace: str, payload: list[dict], *, session_scope_id: str = "") -> None:
        normalized = [dict(item) for item in payload if isinstance(item, dict)]
        self._long_memory_queue_file(workspace, session_scope_id=session_scope_id).write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_runtime_session_payload(self, workspace: str, *, session_scope_id: str = "") -> dict[str, Any]:
        path = self._runtime_session_file(workspace, session_scope_id=session_scope_id)
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return dict(payload) if isinstance(payload, dict) else {}

    def _load_runtime_session_binding(self, workspace: str, *, session_scope_id: str = "", provider: str = "") -> dict[str, Any]:
        payload = self._load_runtime_session_payload(workspace, session_scope_id=session_scope_id)
        providers = dict(payload.get("providers") or {})
        requested = str(provider or "").strip().lower()
        if requested:
            binding = providers.get(requested)
            return dict(binding or {}) if isinstance(binding, dict) else {}
        for preferred in ("codex", "claude", "cursor"):
            binding = providers.get(preferred)
            if isinstance(binding, dict):
                return dict(binding)
        return {}

    def _save_runtime_session_binding(
        self,
        workspace: str,
        *,
        session_scope_id: str = "",
        provider: str,
        payload: dict[str, Any],
    ) -> None:
        scope_id = str(session_scope_id or "").strip()
        provider_name = str(provider or "").strip().lower()
        if not scope_id or not provider_name:
            return
        path = self._runtime_session_file(workspace, session_scope_id=scope_id)
        existing = self._load_runtime_session_payload(workspace, session_scope_id=scope_id)
        providers = dict(existing.get("providers") or {})
        providers[provider_name] = dict(payload or {})
        envelope = {
            "session_scope_id": scope_id,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "providers": providers,
        }
        path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")

    def _recent_store_max_items(self) -> int:
        cfg = self._config_provider() or {}
        memory_cfg = cfg.get("memory") if isinstance(cfg.get("memory"), dict) else {}
        talk_recent = memory_cfg.get("talk_recent") if isinstance(memory_cfg.get("talk_recent"), dict) else {}
        raw_value = talk_recent.get("store_max_items", talk_recent.get("prompt_visible_items", 40))
        try:
            return max(10, min(200, int(raw_value)))
        except Exception:
            return 40

    def _build_recent_entry(
        self,
        memory_id: str,
        user_prompt: str,
        assistant_reply: str,
        *,
        status: str,
        session_scope_id: str = "",
        chat_session_id: str = "",
    ) -> dict:
        prompt_text = re.sub(r"\s+", " ", str(user_prompt or "").strip())
        reply_text = re.sub(r"\s+", " ", str(assistant_reply or "").strip())
        topic_source = prompt_text or reply_text or "本轮对话"
        if reply_text:
            summary = f"用户：{prompt_text[:60]}；助手：{reply_text[:90]}"
        elif prompt_text:
            summary = f"用户：{prompt_text[:120]}"
        else:
            summary = "本轮对话"
        entry = {
            "memory_id": memory_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "topic": topic_source[:18] or "本轮对话",
            "summary": summary[:160],
            "memory_scope": "talk",
            "memory_stream": "talk",
            "event_type": "conversation_turn",
            "raw_user_prompt": prompt_text[:500],
            "status": status,
            "next_actions": [],
            "salience": 0.4 if reply_text else 0.2,
            "confidence": 0.5 if reply_text else 0.2,
            "derived_from": ["chat-light-memory"],
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
        if str(chat_session_id or "").strip():
            entry["chat_session_id"] = str(chat_session_id).strip()
        return entry

    def _replace_recent_entry(self, entries: list[dict], entry_id: str, new_entry: dict) -> bool:
        for index, item in enumerate(entries):
            if isinstance(item, dict) and str(item.get("memory_id") or "") == entry_id:
                entries[index] = new_entry
                return True
        return False

    def _upsert_recent_raw_turn(
        self,
        workspace: str,
        memory_id: str,
        entry: dict,
        user_prompt: str,
        assistant_reply: str,
        raw_reply: str,
        *,
        session_scope_id: str = "",
        process_events: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        active_chat_session_id = resolve_active_chat_session_id(workspace, session_scope_id=session_scope_id)
        payload = self._load_recent_raw_turns(workspace, session_scope_id=session_scope_id)
        existing_turn = next(
            (
                dict(item)
                for item in payload
                if isinstance(item, dict) and str(item.get("memory_id") or "") == memory_id
            ),
            {},
        )
        raw_turn = {
            "memory_id": memory_id,
            "timestamp": str(entry.get("timestamp") or ""),
            "topic": str(entry.get("topic") or ""),
            "summary": str(entry.get("summary") or ""),
            "user_prompt": str(user_prompt or ""),
            "assistant_reply": str(assistant_reply or ""),
            "assistant_reply_visible": str(assistant_reply or ""),
            "assistant_reply_raw": str(raw_reply or assistant_reply or ""),
            "process_events": self._normalize_process_events(process_events),
            "status": str(entry.get("status") or "completed"),
            "turn_seq": int(existing_turn.get("turn_seq") or 0),
        }
        if str(session_scope_id or "").strip():
            raw_turn["session_scope_id"] = str(session_scope_id).strip()
        if active_chat_session_id:
            raw_turn["chat_session_id"] = active_chat_session_id
        replaced = False
        for index, item in enumerate(payload):
            if isinstance(item, dict) and str(item.get("memory_id") or "") == memory_id:
                payload[index] = raw_turn
                replaced = True
                break
        if not replaced:
            raw_turn["turn_seq"] = self._next_turn_seq(payload)
            payload.append(raw_turn)
        self._save_recent_raw_turns(workspace, payload, session_scope_id=session_scope_id)

    def _build_backfill_raw_turn(
        self,
        *,
        entry: dict,
        turn: dict,
        session_scope_id: str,
        chat_session_id: str = "",
    ) -> dict:
        raw_turn = {
            "memory_id": str(turn.get("memory_id") or ""),
            "timestamp": str(turn.get("timestamp") or entry.get("timestamp") or ""),
            "topic": str(turn.get("topic") or entry.get("topic") or ""),
            "summary": str(turn.get("summary") or entry.get("summary") or ""),
            "user_prompt": str(turn.get("user_prompt") or ""),
            "assistant_reply": str(turn.get("assistant_reply_visible") or ""),
            "assistant_reply_visible": str(turn.get("assistant_reply_visible") or ""),
            "assistant_reply_raw": str(turn.get("assistant_reply_raw") or turn.get("assistant_reply_visible") or ""),
            "process_events": self._normalize_process_events(turn.get("process_events")),
            "status": str(turn.get("status") or "completed").strip() or "completed",
            "source_kind": str(turn.get("source_kind") or "history_backfill").strip() or "history_backfill",
            "source_chat_id": str(turn.get("source_chat_id") or "").strip(),
            "source_message_ids": [
                str(item).strip()
                for item in (turn.get("source_message_ids") or [])
                if str(item).strip()
            ],
            "turn_seq": 0,
        }
        if str(session_scope_id or "").strip():
            raw_turn["session_scope_id"] = str(session_scope_id).strip()
        if str(chat_session_id or "").strip():
            raw_turn["chat_session_id"] = str(chat_session_id).strip()
        return raw_turn

    def _replace_or_append_recent_raw_turn(self, payload: list[dict], raw_turn: dict) -> None:
        memory_id = str(raw_turn.get("memory_id") or "").strip()
        if not memory_id:
            return
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                continue
            if str(item.get("memory_id") or "").strip() != memory_id:
                continue
            current = dict(raw_turn)
            current["turn_seq"] = int(item.get("turn_seq") or raw_turn.get("turn_seq") or 0)
            payload[index] = current
            return
        current = dict(raw_turn)
        current["turn_seq"] = self._next_turn_seq(payload)
        payload.append(current)

    @staticmethod
    def _find_recent_raw_turn(payload: list[dict], memory_id: str) -> dict | None:
        target = str(memory_id or "").strip()
        if not target:
            return None
        for item in payload:
            if isinstance(item, dict) and str(item.get("memory_id") or "").strip() == target:
                return item
        return None

    @staticmethod
    def _has_equivalent_recent_raw_turn(
        payload: list[dict],
        *,
        memory_id: str,
        user_prompt: str,
        assistant_reply_visible: str,
    ) -> bool:
        target_id = str(memory_id or "").strip()
        normalized_user = re.sub(r"\s+", " ", str(user_prompt or "").strip())
        normalized_reply = re.sub(r"\s+", " ", str(assistant_reply_visible or "").strip())
        if not normalized_reply:
            return False
        for item in payload:
            if not isinstance(item, dict):
                continue
            current_id = str(item.get("memory_id") or "").strip()
            if current_id and current_id == target_id:
                return True
            current_user = re.sub(r"\s+", " ", str(item.get("user_prompt") or "").strip())
            current_reply = re.sub(
                r"\s+",
                " ",
                str(item.get("assistant_reply_visible") or item.get("assistant_reply") or "").strip(),
            )
            if current_user == normalized_user and current_reply == normalized_reply:
                return True
        return False

    def _normalize_backfill_turns(self, turns: list[dict], *, session_scope_id: str) -> list[dict]:
        normalized: list[dict] = []
        for index, item in enumerate(turns or []):
            if not isinstance(item, dict):
                continue
            memory_id = str(item.get("memory_id") or "").strip()
            assistant_visible = str(item.get("assistant_reply_visible") or item.get("assistant_reply") or "").strip()
            assistant_raw = str(item.get("assistant_reply_raw") or assistant_visible).strip()
            if not memory_id or not assistant_visible:
                continue
            turn = {
                "memory_id": memory_id,
                "timestamp": str(item.get("timestamp") or "").strip(),
                "topic": str(item.get("topic") or "").strip(),
                "summary": str(item.get("summary") or "").strip(),
                "user_prompt": str(item.get("user_prompt") or "").strip(),
                "assistant_reply_visible": assistant_visible,
                "assistant_reply_raw": assistant_raw,
                "process_events": self._normalize_process_events(item.get("process_events")),
                "status": str(item.get("status") or "completed").strip() or "completed",
                "source_kind": str(item.get("source_kind") or "history_backfill").strip() or "history_backfill",
                "source_chat_id": str(item.get("source_chat_id") or "").strip(),
                "source_message_ids": [
                    str(value).strip()
                    for value in (item.get("source_message_ids") or [])
                    if str(value).strip()
                ],
                "_input_order": index,
            }
            if str(session_scope_id or "").strip():
                turn["session_scope_id"] = str(session_scope_id).strip()
            normalized.append(turn)
        normalized.sort(key=lambda item: (str(item.get("timestamp") or ""), int(item.get("_input_order") or 0)))
        for item in normalized:
            item.pop("_input_order", None)
        return normalized

    @staticmethod
    def _next_turn_seq(payload: list[dict]) -> int:
        current_max = 0
        for item in payload:
            if isinstance(item, dict):
                try:
                    current_max = max(current_max, int(item.get("turn_seq") or 0))
                except Exception:
                    continue
        return current_max + 1

    @staticmethod
    def _normalize_process_events(process_events: Sequence[Mapping[str, Any]] | None) -> list[dict]:
        normalized: list[dict] = []
        for item in process_events or []:
            if not isinstance(item, Mapping):
                continue
            kind = str(item.get("kind") or "").strip().lower()
            text = _LEADING_PROCESS_ORDINAL_RE.sub("", re.sub(r"\s+", " ", str(item.get("text") or "").strip())).strip()
            status = str(item.get("status") or "").strip().lower()
            source = str(item.get("source") or "").strip().lower()
            event_type = str(item.get("event_type") or "").strip().lower()
            if not kind and not text:
                continue
            payload = {"kind": kind or "event", "text": text[:240]}
            if status:
                payload["status"] = status[:40]
            if source:
                payload["source"] = source[:40]
            if event_type:
                payload["event_type"] = event_type[:80]
            if normalized and normalized[-1] == payload:
                continue
            normalized.append(payload)
        return normalized

    def _maintain_summary_pipeline(self, workspace: str, *, timeout: int, model: str, session_scope_id: str = "") -> None:
        if not callable(self._window_summarizer):
            return
        window_size = self._turn_store.recent_summary_window_size()
        active_chat_session_id = resolve_active_chat_session_id(workspace, session_scope_id=session_scope_id)
        all_summary_pool = self._load_recent_summary_pool(workspace, session_scope_id=session_scope_id)
        summary_pool = self._filter_payload_for_chat_session(
            all_summary_pool,
            chat_session_id=active_chat_session_id,
        )
        recent_raw_turns = self._filter_payload_for_chat_session(
            self._load_recent_raw_turns(workspace, session_scope_id=session_scope_id),
            chat_session_id=active_chat_session_id,
        )
        completed_turns = sorted(
            [
                dict(item)
                for item in recent_raw_turns
                if isinstance(item, dict) and str(item.get("status") or "completed").strip() == "completed"
            ],
            key=lambda item: int(item.get("turn_seq") or 0),
        )
        if not completed_turns:
            return
        pending_turns = self._pending_window_turns(completed_turns, summary_pool)
        if len(pending_turns) < window_size:
            return
        pool_changed = False
        while len(pending_turns) >= window_size:
            window_turns = pending_turns[:window_size]
            summary_result = self._window_summarizer(
                window_turns,
                list(summary_pool),
                workspace=workspace,
                timeout=timeout,
                model=model,
                session_scope_id=session_scope_id,
            )
            window_payload = summary_result.get("window_summary") if isinstance(summary_result, dict) else {}
            summary_entry = self._normalize_window_summary(window_turns, window_payload)
            if active_chat_session_id:
                summary_entry["chat_session_id"] = active_chat_session_id
            summary_pool = self._apply_summary_patches(
                summary_pool,
                summary_result.get("summary_patches") if isinstance(summary_result, dict) else None,
            )
            summary_pool.append(summary_entry)
            if len(summary_pool) > self._turn_store.recent_summary_items():
                popped = summary_pool.pop(0)
                self._enqueue_long_memory_candidate(workspace, popped, session_scope_id=session_scope_id)
            pending_turns = pending_turns[window_size:]
            pool_changed = True
        if pool_changed:
            merged_pool = [
                dict(item)
                for item in all_summary_pool
                if isinstance(item, dict)
                and str(item.get("chat_session_id") or "").strip() != str(active_chat_session_id or "").strip()
            ]
            merged_pool.extend(summary_pool)
            self._save_recent_summary_pool(workspace, merged_pool, session_scope_id=session_scope_id)

    def _process_long_memory_queue(self, workspace: str, *, timeout: int, model: str, session_scope_id: str = "") -> None:
        if not callable(self._long_memory_governor):
            return
        queue = self._load_long_memory_queue(workspace, session_scope_id=session_scope_id)
        if not queue:
            return
        changed = False
        for item in queue:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "pending").strip() != "pending":
                continue
            try:
                result = self._long_memory_governor(
                    dict(item.get("summary_entry") or {}),
                    workspace=workspace,
                    timeout=timeout,
                    model=model,
                    session_scope_id=session_scope_id,
                )
            except Exception as exc:
                item["status"] = "failed"
                item["error"] = f"{type(exc).__name__}: {exc}"
            else:
                item["status"] = str((result or {}).get("status") or "processed")
                item["result"] = dict(result or {})
                item["processed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            changed = True
        if changed:
            self._save_long_memory_queue(workspace, queue, session_scope_id=session_scope_id)

    def _pending_window_turns(self, completed_turns: list[dict], summary_pool: list[dict]) -> list[dict]:
        last_end_seq = 0
        for item in summary_pool:
            if not isinstance(item, dict):
                continue
            try:
                last_end_seq = max(last_end_seq, int(item.get("window_end_seq") or 0))
            except Exception:
                continue
        return [dict(item) for item in completed_turns if int(item.get("turn_seq") or 0) > last_end_seq]

    def _normalize_window_summary(self, window_turns: list[dict], payload: dict | None) -> dict:
        normalized = dict(payload or {})
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        topics = self._normalize_string_list(normalized.get("topics"))
        requirements = self._normalize_string_list(normalized.get("requirements"))
        decisions = self._normalize_string_list(normalized.get("decisions"))
        open_loops = self._normalize_string_list(normalized.get("open_loops"))
        preferences = self._normalize_string_list(normalized.get("user_preferences_updates"))
        title = str(normalized.get("title") or "").strip() or str(window_turns[0].get("topic") or "最近对话摘要").strip()
        user_summary = str(normalized.get("user_summary") or normalized.get("summary_text") or "").strip()
        if not user_summary:
            user_summary = f"围绕“{title[:40]}”的最近窗口摘要。"
        process_reflection = str(normalized.get("process_reflection") or "").strip()
        return {
            "summary_id": str(normalized.get("summary_id") or uuid.uuid4().hex[:12]),
            "created_at": str(normalized.get("created_at") or now_text),
            "updated_at": now_text,
            "title": title[:80],
            "summary_text": user_summary[:600],
            "user_summary": user_summary[:600],
            "process_reflection": process_reflection[:320],
            "topics": topics[:6],
            "requirements": requirements[:8],
            "decisions": decisions[:8],
            "open_loops": open_loops[:8],
            "user_preferences_updates": preferences[:8],
            "window_turn_ids": [str(item.get("memory_id") or "").strip() for item in window_turns if str(item.get("memory_id") or "").strip()],
            "window_start_seq": int(window_turns[0].get("turn_seq") or 0),
            "window_end_seq": int(window_turns[-1].get("turn_seq") or 0),
        }

    def _apply_summary_patches(self, summary_pool: list[dict], patches: list[dict] | None) -> list[dict]:
        if not isinstance(patches, list) or not patches:
            return [dict(item) for item in summary_pool if isinstance(item, dict)]
        patched_pool = [dict(item) for item in summary_pool if isinstance(item, dict)]
        for patch in patches:
            if not isinstance(patch, dict):
                continue
            summary_id = str(patch.get("summary_id") or "").strip()
            if not summary_id:
                continue
            for item in patched_pool:
                if str(item.get("summary_id") or "").strip() != summary_id:
                    continue
                item["requirements"] = self._merge_string_list(
                    item.get("requirements"),
                    patch.get("requirements_add"),
                    patch.get("requirements_remove"),
                )
                item["open_loops"] = self._merge_string_list(
                    item.get("open_loops"),
                    patch.get("open_loops_add"),
                    patch.get("open_loops_remove"),
                )
                item["user_preferences_updates"] = self._merge_string_list(
                    item.get("user_preferences_updates"),
                    patch.get("preferences_add"),
                    patch.get("preferences_remove"),
                )
                summary_append = str(patch.get("summary_append") or "").strip()
                if summary_append:
                    current_summary = str(item.get("summary_text") or "").strip()
                    item["summary_text"] = (current_summary + " " + summary_append).strip()[:600]
                    item["user_summary"] = item["summary_text"]
                process_reflection_append = str(patch.get("process_reflection_append") or "").strip()
                if process_reflection_append:
                    current_reflection = str(item.get("process_reflection") or "").strip()
                    item["process_reflection"] = (current_reflection + " " + process_reflection_append).strip()[:320]
                item["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        return patched_pool

    def _enqueue_long_memory_candidate(self, workspace: str, summary_entry: dict, *, session_scope_id: str = "") -> None:
        queue = self._load_long_memory_queue(workspace, session_scope_id=session_scope_id)
        summary_id = str(summary_entry.get("summary_id") or "").strip()
        if any(isinstance(item, dict) and str(item.get("summary_id") or "").strip() == summary_id for item in queue):
            return
        queue.append(
            {
                "summary_id": summary_id,
                "title": str(summary_entry.get("title") or "").strip(),
                "queued_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "pending",
                "summary_entry": dict(summary_entry),
            }
        )
        self._save_long_memory_queue(workspace, queue, session_scope_id=session_scope_id)

    @staticmethod
    def _filter_payload_for_chat_session(payload: list[dict], *, chat_session_id: str = "") -> list[dict]:
        target = str(chat_session_id or "").strip()
        if not target:
            return [dict(item) for item in payload if not str(item.get("chat_session_id") or "").strip()]
        return [
            dict(item)
            for item in payload
            if isinstance(item, dict) and str(item.get("chat_session_id") or "").strip() == target
        ]

    @staticmethod
    def _normalize_string_list(values: Any) -> list[str]:
        normalized: list[str] = []
        for item in values or []:
            text = str(item or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    def _merge_string_list(self, current: Any, added: Any, removed: Any) -> list[str]:
        values = self._normalize_string_list(current)
        for item in self._normalize_string_list(removed):
            if item in values:
                values.remove(item)
        for item in self._normalize_string_list(added):
            if item not in values:
                values.append(item)
        return values[:8]

    @staticmethod
    def _iter_known_session_scopes(workspace: str) -> list[str]:
        scope_ids = [""]
        for scope_dir in iter_recent_scope_dirs(workspace):
            metadata = load_scope_metadata(scope_dir)
            scope_id = str(metadata.get("session_scope_id") or "").strip()
            if scope_id:
                scope_ids.append(scope_id)
        return scope_ids


class ChatLightBackgroundServices:
    def __init__(self, *, state: ChatLightMemoryState, config_provider, task_runner: AsyncWritebackRunner | None = None) -> None:
        self._state = state
        self._config_provider = config_provider
        self._task_runner = task_runner or AsyncWritebackRunner()
        self._started = False
        self._lock = threading.Lock()

    def start_background_services(self) -> None:
        if self._started:
            return
        with self._lock:
            if self._started:
                return
            cfg = self._config_provider() or {}
            workspace = str(cfg.get("workspace_root") or ".")
            self._task_runner.submit(
                self._state.recover_pending_recent_entries_on_startup,
                workspace,
                name="chat-recent-recover",
            )
            self._started = True
            print("[后台服务] chat CLI 当前仅保留 recent memory", flush=True)


__all__ = ["ChatLightBackgroundServices", "ChatLightMemoryState"]
