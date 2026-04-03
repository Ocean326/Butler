from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from butler_main.agents_os.runtime.writeback import AsyncWritebackRunner


class ChatReplyPersistenceRuntime:
    """Chat-owned reply persistence slice over injected writeback hooks."""

    def __init__(
        self,
        *,
        config_provider,
        fallback_writer,
        finalize_reply,
        writeback_runner: AsyncWritebackRunner | None = None,
    ) -> None:
        self._config_provider = config_provider
        self._fallback_writer = fallback_writer
        self._finalize_reply = finalize_reply
        self._writeback_runner = writeback_runner or AsyncWritebackRunner()

    def persist_reply_async(
        self,
        user_prompt: str,
        assistant_reply: str,
        *,
        raw_reply: str | None = None,
        memory_id: str | None = None,
        model_override: str | None = None,
        suppress_task_merge: bool = False,
        session_scope_id: str = "",
        process_events: Sequence[Mapping[str, object]] | None = None,
    ) -> None:
        cfg = self._config_provider() or {}
        workspace = str(cfg.get("workspace_root") or os.getcwd())
        timeout = int(cfg.get("agent_timeout", 300))
        model = str(model_override or cfg.get("agent_model", "auto") or "auto")
        effective_raw_reply = str(raw_reply if raw_reply is not None else assistant_reply or "")
        normalized_process_events = [dict(item) for item in (process_events or []) if isinstance(item, Mapping)]
        self._fallback_writer(
            memory_id,
            user_prompt,
            assistant_reply,
            effective_raw_reply,
            workspace,
            session_scope_id,
            process_events=normalized_process_events,
        )
        print(f"[记忆] 收到 on_reply_sent，启动短期记忆持久化线程 (workspace={workspace[:50]}...)", flush=True)
        self._writeback_runner.submit(
            self._finalize_reply,
            memory_id,
            user_prompt,
            assistant_reply,
            effective_raw_reply,
            workspace,
            timeout,
            model,
            suppress_task_merge,
            session_scope_id,
            process_events=normalized_process_events,
            name="recent-memory-writer",
        )


__all__ = ["ChatReplyPersistenceRuntime"]
