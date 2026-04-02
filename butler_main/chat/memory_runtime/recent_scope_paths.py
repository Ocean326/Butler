from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from butler_main.chat.pathing import RECENT_MEMORY_DIR_REL, ensure_chat_data_layout
from butler_main.runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children


SCOPES_DIR_NAME = "scopes"
SCOPE_METADATA_FILE = "scope.json"


def resolve_recent_scope_dir(workspace: str, session_scope_id: str = "") -> Path:
    root = ensure_chat_data_layout(workspace)
    base_dir = root / RECENT_MEMORY_DIR_REL
    base_dir.mkdir(parents=True, exist_ok=True)
    scope_id = str(session_scope_id or "").strip()
    if not scope_id:
        return base_dir
    scopes_root = base_dir / SCOPES_DIR_NAME
    prune_path_children(
        scopes_root,
        retention_days=DEFAULT_RETENTION_DAYS,
        include_files=False,
        include_dirs=True,
    )
    scope_dir = scopes_root / scope_hash_text(scope_id)
    scope_dir.mkdir(parents=True, exist_ok=True)
    _touch_scope_metadata(scope_dir, session_scope_id=scope_id)
    return scope_dir


def iter_recent_scope_dirs(workspace: str) -> list[Path]:
    root = ensure_chat_data_layout(workspace)
    scopes_root = root / RECENT_MEMORY_DIR_REL / SCOPES_DIR_NAME
    if not scopes_root.is_dir():
        return []
    return [item for item in sorted(scopes_root.iterdir()) if item.is_dir()]


def scope_hash_text(session_scope_id: str) -> str:
    normalized = str(session_scope_id or "").strip()
    if not normalized:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def load_scope_metadata(scope_dir: Path) -> dict[str, str]:
    target = scope_dir / SCOPE_METADATA_FILE
    if not target.is_file():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _touch_scope_metadata(scope_dir: Path, *, session_scope_id: str) -> None:
    target = scope_dir / SCOPE_METADATA_FILE
    existing = load_scope_metadata(scope_dir)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scope_id = str(session_scope_id or "").strip()
    channel = ""
    if ":" in scope_id:
        prefix = scope_id.split(":", 1)[0].strip().lower()
        if prefix in {"weixin", "feishu", "cli"}:
            channel = prefix
    payload = {
        "session_scope_id": scope_id,
        "channel": channel,
        "created_at": str(existing.get("created_at") or timestamp),
        "last_seen_at": timestamp,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "SCOPES_DIR_NAME",
    "SCOPE_METADATA_FILE",
    "iter_recent_scope_dirs",
    "load_scope_metadata",
    "resolve_recent_scope_dir",
    "scope_hash_text",
]
