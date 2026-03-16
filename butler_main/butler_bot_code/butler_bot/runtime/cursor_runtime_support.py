from __future__ import annotations

import os
import random
import time
import uuid
from pathlib import Path

from butler_paths import resolve_butler_root


def _configured_cursor_api_keys(cfg: dict | None) -> list[str]:
    snapshot = cfg if isinstance(cfg, dict) else {}
    raw_keys = snapshot.get("cursor_api_keys") if isinstance(snapshot, dict) else None
    if isinstance(raw_keys, str):
        raw_keys = [raw_keys]
    if not isinstance(raw_keys, list):
        raw_keys = []

    keys: list[str] = []
    seen: set[str] = set()
    for raw in raw_keys:
        key = str(raw or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def build_cursor_cli_env(cfg: dict | None = None, base_env: dict | None = None) -> dict:
    env = dict(base_env or os.environ.copy())
    env.pop("NO_PROXY", None)
    for proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "GIT_HTTP_PROXY", "GIT_HTTPS_PROXY", "NO_PROXY"):
        raw_value = str(env.get(proxy_key) or "").strip()
        if raw_value and any(marker in raw_value for marker in ("127.0.0.1:9", "localhost:9")):
            env.pop(proxy_key, None)

    workspace_root = resolve_butler_root(str((cfg or {}).get("workspace_root") or os.getcwd()))
    runtime_root = workspace_root / "butler_main" / "butler_bot_code" / "run" / "cursor_runtime_env"
    session_root = runtime_root / "sessions" / f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    roaming_root = session_root / "Roaming"
    local_root = session_root / "Local"
    profile_root = session_root / "Profile"
    temp_root = session_root / "Temp"
    _cleanup_cursor_runtime_sessions(runtime_root)
    roaming_root.mkdir(parents=True, exist_ok=True)
    local_root.mkdir(parents=True, exist_ok=True)
    profile_root.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    env["APPDATA"] = str(roaming_root)
    env["LOCALAPPDATA"] = str(local_root)
    env["USERPROFILE"] = str(profile_root)
    env["HOME"] = str(profile_root)
    env["TMP"] = str(temp_root)
    env["TEMP"] = str(temp_root)
    env["XDG_CONFIG_HOME"] = str(roaming_root)
    env["CURSOR_CONFIG_HOME"] = str(roaming_root)

    key_pool = _configured_cursor_api_keys(cfg)
    if not key_pool:
        return env
    env["CURSOR_API_KEY"] = random.choice(key_pool)
    return env


def _cleanup_cursor_runtime_sessions(runtime_root: Path, *, max_age_seconds: int = 12 * 60 * 60) -> None:
    sessions_root = runtime_root / "sessions"
    if not sessions_root.exists():
        return
    cutoff = time.time() - max(600, int(max_age_seconds or 0))
    try:
        for candidate in sessions_root.iterdir():
            try:
                if not candidate.is_dir():
                    continue
                stat = candidate.stat()
                if stat.st_mtime >= cutoff:
                    continue
                for nested in sorted(candidate.rglob("*"), reverse=True):
                    if nested.is_file():
                        nested.unlink(missing_ok=True)
                    elif nested.is_dir():
                        nested.rmdir()
                candidate.rmdir()
            except Exception:
                continue
    except Exception:
        return


def resolve_cursor_cli_cmd_path(cfg: dict | None = None) -> str:
    snapshot = dict(cfg or {})
    configured = str(snapshot.get("cursor_cli_path") or "").strip()
    if configured and os.path.isfile(configured):
        return configured
    base = os.environ.get("LOCALAPPDATA", "")
    legacy = os.path.join(base, "cursor-agent", "versions", "dist-package", "cursor-agent.cmd")
    if os.path.isfile(legacy):
        return legacy
    versions_dir = os.path.join(base, "cursor-agent", "versions")
    if os.path.isdir(versions_dir):
        try:
            subs = [item for item in os.listdir(versions_dir) if os.path.isdir(os.path.join(versions_dir, item))]
            subs.sort(reverse=True)
            for version in subs:
                candidate = os.path.join(versions_dir, version, "cursor-agent.cmd")
                if os.path.isfile(candidate):
                    return candidate
        except OSError:
            pass
    return legacy
