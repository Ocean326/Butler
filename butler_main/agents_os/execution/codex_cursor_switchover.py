from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    import fcntl
except Exception:  # pragma: no cover - Windows fallback
    fcntl = None


DEFAULT_SWITCHOVER_SETTINGS = {
    "enabled": True,
    "cooldown_seconds": 3600,
    "probes_per_hour": 2,
    "state_path": "~/.butler/codex_cursor_switchover_state.json",
}


def load_switchover_settings(cfg: dict | None) -> dict[str, Any]:
    runtime = dict((cfg or {}).get("cli_runtime") or {})
    raw = dict(runtime.get("codex_cursor_switchover") or {})
    settings = dict(DEFAULT_SWITCHOVER_SETTINGS)
    settings.update(raw)
    settings["enabled"] = bool(settings.get("enabled", True))
    settings["cooldown_seconds"] = max(60, int(settings.get("cooldown_seconds") or 3600))
    settings["probes_per_hour"] = max(1, int(settings.get("probes_per_hour") or 2))
    settings["state_path"] = str(
        Path(os.path.expanduser(str(settings.get("state_path") or DEFAULT_SWITCHOVER_SETTINGS["state_path"]))).resolve()
    )
    return settings


def _default_state() -> dict[str, Any]:
    return {
        "phase": "normal",
        "cooldown_until": 0.0,
        "probe_hour_bucket": -1,
        "probe_attempts": 0,
        "updated_at": 0.0,
    }


def _normalize_state(payload: dict[str, Any]) -> dict[str, Any]:
    base = _default_state()
    base.update({k: v for k, v in dict(payload or {}).items() if v is not None})
    phase = str(base.get("phase") or "normal").strip().lower()
    if phase not in {"normal", "cooldown", "probing"}:
        phase = "normal"
    base["phase"] = phase
    base["cooldown_until"] = float(base.get("cooldown_until") or 0)
    base["probe_hour_bucket"] = int(base.get("probe_hour_bucket") or -1)
    base["probe_attempts"] = max(0, int(base.get("probe_attempts") or 0))
    base["updated_at"] = float(base.get("updated_at") or 0)
    return base


@contextlib.contextmanager
def _state_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(str(path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_unlocked(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return _normalize_state(dict(payload or {}))


def _write_unlocked(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = _normalize_state(state)
    state["updated_at"] = time.time()
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def read_state(cfg: dict | None) -> dict[str, Any]:
    settings = load_switchover_settings(cfg)
    path = Path(settings["state_path"])
    with _state_lock(path):
        return _read_unlocked(path)


def _mutate_state(cfg: dict | None, mutator) -> dict[str, Any]:
    settings = load_switchover_settings(cfg)
    path = Path(settings["state_path"])
    with _state_lock(path):
        state = _read_unlocked(path)
        next_state = mutator(dict(state), settings)
        _write_unlocked(path, next_state)
        return _normalize_state(next_state)


def _advance_cooldown_to_probing(state: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    if state.get("phase") != "cooldown":
        return state
    until = float(state.get("cooldown_until") or 0)
    if now < until:
        return state
    return {
        **state,
        "phase": "probing",
        "cooldown_until": 0.0,
        "probe_hour_bucket": -1,
        "probe_attempts": 0,
    }


def _eval_skip_codex_first(state: dict[str, Any], s: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    state = _advance_cooldown_to_probing(dict(state), s)
    now = time.time()
    phase = str(state.get("phase") or "normal")

    if phase == "normal":
        return state, False

    if phase == "cooldown":
        until = float(state.get("cooldown_until") or 0)
        if now < until:
            return state, True
        state = {
            **state,
            "phase": "probing",
            "cooldown_until": 0.0,
            "probe_hour_bucket": -1,
            "probe_attempts": 0,
        }
        phase = "probing"

    if phase == "probing":
        bucket = int(now // 3600)
        pb = int(state.get("probe_hour_bucket") or -1)
        attempts = int(state.get("probe_attempts") or 0)
        if pb != bucket:
            pb = bucket
            attempts = 0
        limit = int(s.get("probes_per_hour") or 2)
        state = {**state, "probe_hour_bucket": pb, "probe_attempts": attempts}
        if attempts >= limit:
            return state, True
        return state, False

    return state, False


def resolve_codex_first_switchover(cfg: dict | None) -> tuple[bool, bool]:
    """返回 (是否跳过 Codex 优先, 若本次升级为 Codex 是否计入每小时试探次数)。"""
    settings = load_switchover_settings(cfg)
    if not settings["enabled"]:
        return False, False
    path = Path(settings["state_path"])
    with _state_lock(path):
        before = _read_unlocked(path)
        new_state, skip = _eval_skip_codex_first(dict(before), settings)
        if new_state != before:
            _write_unlocked(path, new_state)
        count_probe = str(new_state.get("phase") or "") == "probing" and not skip
        return skip, count_probe


def should_skip_codex_first(cfg: dict | None) -> bool:
    """为 True 时不做「默认先 Codex」升级，保持 Cursor。"""
    skip, _ = resolve_codex_first_switchover(cfg)
    return skip


def note_probe_attempt(cfg: dict | None) -> None:
    """记录一次由策略触发的 Codex 试探（每小时最多 probes_per_hour 次）。"""

    def _bump(state: dict[str, Any], s: dict[str, Any]) -> dict[str, Any]:
        state = _advance_cooldown_to_probing(dict(state), s)
        if state.get("phase") != "probing":
            return state
        now = time.time()
        bucket = int(now // 3600)
        pb = int(state.get("probe_hour_bucket") or -1)
        attempts = int(state.get("probe_attempts") or 0)
        if pb != bucket:
            pb = bucket
            attempts = 0
        return {**state, "probe_hour_bucket": pb, "probe_attempts": attempts + 1}

    _mutate_state(cfg, lambda st, s: _bump(st, s))


def record_codex_primary_failure(cfg: dict | None) -> None:
    """Codex 作为主执行失败：进入 cooldown，接下来优先 Cursor。"""

    def _trip(state: dict[str, Any], s: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        cool = float(s.get("cooldown_seconds") or 3600)
        return {
            **state,
            "phase": "cooldown",
            "cooldown_until": now + cool,
            "probe_hour_bucket": -1,
            "probe_attempts": 0,
        }

    _mutate_state(cfg, _trip)


def record_codex_primary_success(cfg: dict | None) -> None:
    """Codex 主执行成功：恢复正常（优先 Codex）。"""

    def _clear(state: dict[str, Any], _s: dict[str, Any]) -> dict[str, Any]:
        return _default_state()

    _mutate_state(cfg, _clear)
