from __future__ import annotations

import os
import random
import shutil
import time
import uuid
from pathlib import Path

try:
    from runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from butler_main.runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children


def resolve_butler_root(workspace: str | Path | None = None) -> Path:
    candidate = Path(workspace or os.getcwd()).resolve()
    parts_lower = [part.lower() for part in candidate.parts]
    if "butler_main" in parts_lower:
        idx = parts_lower.index("butler_main")
        if idx > 0:
            return Path(*candidate.parts[:idx])
    for base in (candidate, candidate / "Butler"):
        resolved = base.resolve()
        if (resolved / "butler_main" / "butler_bot_code").exists():
            return resolved
    return candidate


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


def resolve_project_python_executable(workspace: str | Path | None = None) -> Path | None:
    root = resolve_butler_root(workspace)
    candidates = (
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return None


def apply_project_python_env(env: dict, workspace: str | Path | None = None) -> dict:
    python_exe = resolve_project_python_executable(workspace)
    if python_exe is None:
        return env

    scripts_dir = str(python_exe.parent)
    venv_root = str(python_exe.parent.parent)
    existing_path = str(env.get("PATH") or "")
    path_parts = [part for part in existing_path.split(os.pathsep) if part]
    normalized_scripts = os.path.normcase(os.path.normpath(scripts_dir))
    filtered_parts = [
        part
        for part in path_parts
        if os.path.normcase(os.path.normpath(part)) != normalized_scripts
    ]
    env["PATH"] = os.pathsep.join([scripts_dir, *filtered_parts]) if filtered_parts else scripts_dir
    env["VIRTUAL_ENV"] = venv_root
    env["BUTLER_PROJECT_PYTHON"] = str(python_exe)
    return env


def build_cursor_cli_env(cfg: dict | None = None, base_env: dict | None = None) -> dict:
    env = dict(base_env or os.environ.copy())
    env.pop("NO_PROXY", None)
    for proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "GIT_HTTP_PROXY", "GIT_HTTPS_PROXY", "NO_PROXY"):
        raw_value = str(env.get(proxy_key) or "").strip()
        if raw_value and any(marker in raw_value for marker in ("127.0.0.1:9", "localhost:9")):
            env.pop(proxy_key, None)

    workspace_root = resolve_butler_root(str((cfg or {}).get("workspace_root") or os.getcwd()))
    runtime_root = workspace_root / "butler_main" / "agents_os" / "run" / "cursor_runtime_env"
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
    apply_project_python_env(env, workspace_root)

    key_pool = _configured_cursor_api_keys(cfg)
    if key_pool:
        env["CURSOR_API_KEY"] = random.choice(key_pool)
    return env


def _cleanup_cursor_runtime_sessions(runtime_root: Path, *, max_age_seconds: int = DEFAULT_RETENTION_DAYS * 24 * 60 * 60) -> None:
    sessions_root = runtime_root / "sessions"
    retention_days = max(1, int(max(600, int(max_age_seconds or 0)) / (24 * 60 * 60)))
    prune_path_children(
        sessions_root,
        retention_days=retention_days,
        include_files=False,
        include_dirs=True,
    )


def _resolve_cli_executable(candidate: str | None) -> str | None:
    text = str(candidate or "").strip()
    if not text:
        return None
    expanded = os.path.expanduser(os.path.expandvars(text))
    if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
        return expanded
    which_hit = shutil.which(expanded)
    if which_hit and os.path.isfile(which_hit):
        return which_hit
    base = os.path.basename(expanded)
    if base == expanded or (os.path.sep not in expanded and not (os.altsep and os.altsep in expanded)):
        which_base = shutil.which(base)
        if which_base and os.path.isfile(which_base):
            return which_base
    return None


def _posix_cursor_agent_binaries() -> list[str]:
    """Linux/macOS：官方安装脚本使用 ~/.local/bin/agent 与 ~/.local/share/cursor-agent/versions/*/cursor-agent。"""
    out: list[str] = []
    seen: set[str] = set()
    home = Path.home()

    agent_link = home / ".local" / "bin" / "agent"
    if agent_link.is_file() or agent_link.is_symlink():
        try:
            resolved = str(agent_link.resolve())
            if resolved not in seen and os.path.isfile(resolved):
                seen.add(resolved)
                out.append(resolved)
        except OSError:
            pass

    versions_dir = home / ".local" / "share" / "cursor-agent" / "versions"
    if versions_dir.is_dir():
        try:
            subs = sorted(
                (p for p in versions_dir.iterdir() if p.is_dir() and not p.name.startswith(".")),
                key=lambda p: p.name,
                reverse=True,
            )
            for sub in subs:
                candidate = sub / "cursor-agent"
                if candidate.is_file() and os.access(str(candidate), os.X_OK):
                    s = str(candidate.resolve())
                    if s not in seen:
                        seen.add(s)
                        out.append(s)
        except OSError:
            pass

    for name in ("agent", "cursor-agent"):
        w = shutil.which(name)
        if w and os.path.isfile(w) and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def resolve_cursor_cli_cmd_path(cfg: dict | None = None) -> str:
    snapshot = dict(cfg or {})
    hit = _resolve_cli_executable(snapshot.get("cursor_cli_path"))
    if hit:
        return hit

    try:
        rt = dict(snapshot.get("cli_runtime") or {})
        prov = dict((rt.get("providers") or {}).get("cursor") or {})
        hit = _resolve_cli_executable(str(prov.get("path") or ""))
        if hit:
            return hit
    except Exception:
        pass

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

    if os.name != "nt":
        for candidate in _posix_cursor_agent_binaries():
            if candidate and os.path.isfile(candidate):
                return candidate
        return str(Path.home() / ".local" / "bin" / "agent")

    return legacy
