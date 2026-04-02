from __future__ import annotations

import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from .session_registry import WeixinSessionRegistry


@dataclass(slots=True, frozen=True)
class WeixinDispatchResult:
    conversation_key: str
    message_id: str
    delivered_count: int = 0
    metadata: dict[str, Any] | None = None


class WeixinConversationDispatcher:
    def __init__(
        self,
        *,
        registry: WeixinSessionRegistry | None = None,
        max_workers: int = 4,
    ) -> None:
        self._registry = registry
        self._executor = ThreadPoolExecutor(
            max_workers=max(int(max_workers or 4), 1),
            thread_name_prefix="butler-weixin-conv",
        )
        self._lock = threading.Lock()
        self._queues: dict[str, deque[tuple[str, Future, Any]]] = {}
        self._running_keys: set[str] = set()

    def submit(self, conversation_key: str, message_id: str, fn) -> Future:
        key = str(conversation_key or "").strip() or "__default__"
        future: Future = Future()
        with self._lock:
            queue = self._queues.setdefault(key, deque())
            queue.append((str(message_id or "").strip(), future, fn))
            if key not in self._running_keys:
                self._running_keys.add(key)
                self._executor.submit(self._drain_conversation, key)
        return future

    def shutdown(self, *, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _drain_conversation(self, conversation_key: str) -> None:
        key = str(conversation_key or "").strip() or "__default__"
        while True:
            with self._lock:
                queue = self._queues.get(key)
                if not queue:
                    self._running_keys.discard(key)
                    self._queues.pop(key, None)
                    return
                message_id, future, fn = queue.popleft()
            if not future.set_running_or_notify_cancel():
                continue
            if self._registry is not None:
                self._registry.record_started(key)
            try:
                result = fn()
            except Exception as exc:
                if self._registry is not None:
                    self._registry.record_failed(key, f"{type(exc).__name__}: {exc}")
                future.set_exception(exc)
                continue
            if isinstance(result, WeixinDispatchResult):
                delivered_count = result.delivered_count
            else:
                delivered_count = 0
                result = WeixinDispatchResult(
                    conversation_key=key,
                    message_id=message_id,
                    delivered_count=delivered_count,
                )
            if self._registry is not None:
                self._registry.record_completed(key, delivered_count=delivered_count)
            future.set_result(result)


__all__ = ["WeixinConversationDispatcher", "WeixinDispatchResult"]
