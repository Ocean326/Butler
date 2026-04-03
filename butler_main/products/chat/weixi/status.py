from __future__ import annotations

from copy import deepcopy
import threading
from typing import Any


_LOCK = threading.Lock()
_DEFAULT_BINDING_ID = "default"
_EMPTY_SNAPSHOT: dict[str, Any] = {
    "connected": False,
    "login_state": "idle",
    "account_id": "",
    "user_id": "",
    "cursor": "",
    "longpoll_timeout_ms": 0,
    "last_poll_at": 0.0,
    "last_received_count": 0,
    "last_delivered_count": 0,
    "active_conversation_count": 0,
    "running_conversation_count": 0,
    "recent_conversations": [],
    "last_error": "",
}
_BINDING_SNAPSHOTS: dict[str, dict[str, Any]] = {}


def _empty_snapshot() -> dict[str, Any]:
    return deepcopy(_EMPTY_SNAPSHOT)


def _normalize_binding_id(binding_id: str | None) -> str:
    text = str(binding_id or "").strip()
    return text or _DEFAULT_BINDING_ID


def set_weixin_runtime_status(snapshot: dict[str, Any] | None, *, binding_id: str = "") -> None:
    payload = deepcopy(dict(snapshot or {}))
    with _LOCK:
        _BINDING_SNAPSHOTS[_normalize_binding_id(binding_id)] = payload


def _binding_snapshot(binding_id: str) -> dict[str, Any]:
    payload = _empty_snapshot()
    payload.update(deepcopy(dict(_BINDING_SNAPSHOTS.get(binding_id) or {})))
    payload["binding_id"] = binding_id
    payload["connected"] = bool(payload.get("connected"))
    payload["active_conversation_count"] = max(int(payload.get("active_conversation_count") or 0), 0)
    payload["running_conversation_count"] = max(int(payload.get("running_conversation_count") or 0), 0)
    payload["last_received_count"] = max(int(payload.get("last_received_count") or 0), 0)
    payload["last_delivered_count"] = max(int(payload.get("last_delivered_count") or 0), 0)
    payload["recent_conversations"] = list(payload.get("recent_conversations") or [])
    return payload


def _aggregate_snapshots() -> dict[str, Any]:
    binding_ids = sorted(_BINDING_SNAPSHOTS)
    if not binding_ids:
        aggregate = _empty_snapshot()
        aggregate.update(
            {
                "binding_count": 0,
                "active_binding_count": 0,
                "bindings": [],
            }
        )
        return aggregate
    bindings = [_binding_snapshot(binding_id) for binding_id in binding_ids]
    active_bindings = [item for item in bindings if item.get("connected")]
    aggregate = _empty_snapshot()
    aggregate.update(
        {
            "binding_count": len(bindings),
            "active_binding_count": len(active_bindings),
            "bindings": bindings,
            "connected": bool(active_bindings),
            "login_state": "ready" if active_bindings else ("error" if any(item.get("last_error") for item in bindings) else "idle"),
            "active_conversation_count": sum(int(item.get("active_conversation_count") or 0) for item in bindings),
            "running_conversation_count": sum(int(item.get("running_conversation_count") or 0) for item in bindings),
            "last_received_count": sum(int(item.get("last_received_count") or 0) for item in bindings),
            "last_delivered_count": sum(int(item.get("last_delivered_count") or 0) for item in bindings),
            "recent_conversations": [
                {
                    **dict(conversation),
                    "binding_id": str(item.get("binding_id") or ""),
                }
                for item in bindings
                for conversation in list(item.get("recent_conversations") or [])
                if isinstance(conversation, dict)
            ],
        }
    )
    if len(bindings) == 1:
        only = bindings[0]
        aggregate["account_id"] = str(only.get("account_id") or "").strip()
        aggregate["user_id"] = str(only.get("user_id") or "").strip()
        aggregate["cursor"] = str(only.get("cursor") or "").strip()
        aggregate["longpoll_timeout_ms"] = int(only.get("longpoll_timeout_ms") or 0)
        aggregate["last_poll_at"] = float(only.get("last_poll_at") or 0.0)
        aggregate["last_error"] = str(only.get("last_error") or "").strip()
    else:
        aggregate["account_ids"] = [str(item.get("account_id") or "").strip() for item in bindings if str(item.get("account_id") or "").strip()]
        aggregate["binding_errors"] = [
            {"binding_id": str(item.get("binding_id") or ""), "last_error": str(item.get("last_error") or "").strip()}
            for item in bindings
            if str(item.get("last_error") or "").strip()
        ]
        aggregate["last_poll_at"] = max(float(item.get("last_poll_at") or 0.0) for item in bindings) if bindings else 0.0
    return aggregate


def get_weixin_runtime_status_snapshot(*, binding_id: str = "") -> dict[str, Any]:
    with _LOCK:
        if str(binding_id or "").strip():
            return _binding_snapshot(_normalize_binding_id(binding_id))
        return _aggregate_snapshots()


def reset_weixin_runtime_status(*, binding_id: str = "") -> None:
    with _LOCK:
        if str(binding_id or "").strip():
            _BINDING_SNAPSHOTS[_normalize_binding_id(binding_id)] = _empty_snapshot()
            return
        _BINDING_SNAPSHOTS.clear()


__all__ = [
    "_DEFAULT_BINDING_ID",
    "get_weixin_runtime_status_snapshot",
    "reset_weixin_runtime_status",
    "set_weixin_runtime_status",
]
