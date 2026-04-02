from __future__ import annotations

import argparse
import calendar
import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

try:
    import fcntl
except Exception:  # pragma: no cover - Windows fallback
    fcntl = None


DEFAULT_FAILOVER_SETTINGS = {
    "enabled": False,
    "cli": "codex",
    "primary_profile": "aixj",
    "fallback_profile": "openai",
    "trip_timeout_seconds": 30,
    "cooldown_seconds": 1800,
    "probe_interval_seconds": 900,
    "probe_timeout_seconds": 30,
    "recovery_success_threshold": 2,
    "probe_model": "gpt-5.4",
    "probe_prompt": "Reply with exactly OK.",
    "trip_on_timeout": True,
    "trip_on_network_error": True,
    "trip_on_http_429": True,
    "trip_on_http_5xx": True,
    "state_path": "~/.codex/provider_failover_state.json",
    "codex_config_path": "~/.codex/config.toml",
}

_HTTP_429_RE = re.compile(r"(?<!\d)429(?!\d)")
_HTTP_5XX_RE = re.compile(r"(?<!\d)(5\d{2})(?!\d)")
_TOP_LEVEL_PROFILE_RE = re.compile(r'^\s*profile\s*=\s*"([^"]*)"\s*$')
_NETWORK_MARKERS = (
    "connection error",
    "connection reset",
    "connection refused",
    "connection aborted",
    "network error",
    "dns",
    "ssl",
    "tls",
    "name or service not known",
    "temporary failure in name resolution",
    "econn",
    "ehost",
    "socket hang up",
    "upstream connect error",
    "api error",
)
_TIMEOUT_MARKERS = (
    "执行超时",
    "timed out",
    "timeout",
    "deadline exceeded",
)


def _read_text_lossy(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def load_failover_settings(cfg: dict | None) -> dict[str, Any]:
    runtime = dict((cfg or {}).get("cli_runtime") or {})
    raw = dict(runtime.get("provider_failover") or {})
    settings = dict(DEFAULT_FAILOVER_SETTINGS)
    settings.update(raw)
    settings["enabled"] = bool(settings.get("enabled", False))
    settings["cli"] = str(settings.get("cli") or "codex").strip().lower() or "codex"
    settings["primary_profile"] = str(settings.get("primary_profile") or "aixj").strip() or "aixj"
    settings["fallback_profile"] = str(settings.get("fallback_profile") or "openai").strip() or "openai"
    settings["trip_timeout_seconds"] = max(5, int(settings.get("trip_timeout_seconds") or 30))
    settings["cooldown_seconds"] = max(60, int(settings.get("cooldown_seconds") or 1800))
    settings["probe_interval_seconds"] = max(60, int(settings.get("probe_interval_seconds") or 900))
    settings["probe_timeout_seconds"] = max(5, int(settings.get("probe_timeout_seconds") or 30))
    settings["recovery_success_threshold"] = max(1, int(settings.get("recovery_success_threshold") or 2))
    settings["probe_model"] = str(settings.get("probe_model") or (cfg or {}).get("agent_model") or "gpt-5.4").strip() or "gpt-5.4"
    settings["probe_prompt"] = str(settings.get("probe_prompt") or "Reply with exactly OK.").strip() or "Reply with exactly OK."
    settings["trip_on_timeout"] = bool(settings.get("trip_on_timeout", True))
    settings["trip_on_network_error"] = bool(settings.get("trip_on_network_error", True))
    settings["trip_on_http_429"] = bool(settings.get("trip_on_http_429", True))
    settings["trip_on_http_5xx"] = bool(settings.get("trip_on_http_5xx", True))
    settings["state_path"] = str(Path(os.path.expanduser(str(settings.get("state_path") or DEFAULT_FAILOVER_SETTINGS["state_path"]))).resolve())
    settings["codex_config_path"] = str(
        Path(os.path.expanduser(str(settings.get("codex_config_path") or DEFAULT_FAILOVER_SETTINGS["codex_config_path"]))).resolve()
    )
    return settings


def default_state(settings: dict[str, Any]) -> dict[str, Any]:
    now = _utc_now()
    return {
        "active_profile": settings["primary_profile"],
        "primary_profile": settings["primary_profile"],
        "fallback_profile": settings["fallback_profile"],
        "circuit_state": "closed",
        "cooldown_until_utc": "",
        "last_probe_at_utc": "",
        "last_success_at_utc": now,
        "last_failure_at_utc": "",
        "last_error_class": "",
        "consecutive_failures": 0,
        "consecutive_probe_successes": 0,
        "updated_at_utc": now,
    }


def current_profile(cfg: dict | None) -> str:
    settings = load_failover_settings(cfg)
    if not settings["enabled"]:
        return ""
    return str(read_state(cfg).get("active_profile") or settings["primary_profile"]).strip() or settings["primary_profile"]


def read_state(cfg: dict | None) -> dict[str, Any]:
    settings = load_failover_settings(cfg)
    with _state_lock(settings):
        return _read_state_unlocked(settings)


def prepare_runtime_request(cfg: dict | None, runtime_request: dict | None, *, explicit_profile: bool) -> dict[str, Any]:
    request = dict(runtime_request or {})
    settings = load_failover_settings(cfg)
    if not settings["enabled"]:
        return request
    if str(request.get("cli") or "").strip().lower() != settings["cli"]:
        return request
    if explicit_profile:
        return request
    state = read_state(cfg)
    request["_provider_failover_managed"] = True
    request["_provider_failover_active_profile"] = (
        str(state.get("active_profile") or settings["primary_profile"]).strip() or settings["primary_profile"]
    )
    return request


def managed_timeout_seconds(cfg: dict | None, timeout: int, runtime_request: dict | None) -> int:
    from . import cli_runner

    settings = load_failover_settings(cfg)
    request = dict(runtime_request or {})
    if not settings["enabled"] or not bool(request.get("_provider_failover_managed")):
        return max(5, int(timeout or 0))
    if cli_runner._managed_failover_profile(settings, request) != settings["primary_profile"]:
        return max(5, int(timeout or 0))
    configured = settings["trip_timeout_seconds"]
    requested = max(5, int(timeout or 0))
    return min(requested, configured)


def record_execution_result(cfg: dict | None, runtime_request: dict | None, output: str, ok: bool) -> dict[str, Any]:
    from . import cli_runner

    settings = load_failover_settings(cfg)
    request = dict(runtime_request or {})
    if not settings["enabled"]:
        return {"tripped": False, "error_class": "", "state": default_state(settings)}
    if not bool(request.get("_provider_failover_managed")):
        return {"tripped": False, "error_class": "", "state": read_state(cfg)}
    profile = cli_runner._managed_failover_profile(settings, request)
    if profile != settings["primary_profile"]:
        return {"tripped": False, "error_class": "", "state": read_state(cfg)}
    if ok:
        state = update_state(
            cfg,
            lambda state, settings: {
                **state,
                "active_profile": settings["primary_profile"],
                "circuit_state": "closed",
                "last_success_at_utc": _utc_now(),
                "updated_at_utc": _utc_now(),
                "consecutive_failures": 0,
                "consecutive_probe_successes": 0,
                "last_error_class": "",
            },
        )
        sync_system_codex_profile(cfg, state)
        return {"tripped": False, "error_class": "", "state": state}
    error_class = classify_failure(output)
    if not should_trip(settings, error_class):
        return {"tripped": False, "error_class": error_class, "state": read_state(cfg)}
    now = _utc_now()
    cooldown_until = _utc_after_seconds(settings["cooldown_seconds"])

    def _trip(state: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
        failures = int(state.get("consecutive_failures") or 0) + 1
        return {
            **state,
            "active_profile": settings["fallback_profile"],
            "circuit_state": "open",
            "cooldown_until_utc": cooldown_until,
            "last_failure_at_utc": now,
            "updated_at_utc": now,
            "consecutive_failures": failures,
            "consecutive_probe_successes": 0,
            "last_error_class": error_class,
        }

    state = update_state(cfg, _trip)
    sync_system_codex_profile(cfg, state)
    return {"tripped": True, "error_class": error_class, "state": state}


def reconcile_failover(cfg: dict | None, *, force_probe: bool = True) -> dict[str, Any]:
    settings = load_failover_settings(cfg)
    state = read_state(cfg)
    if not settings["enabled"]:
        return state
    should_probe = bool(force_probe)
    if not should_probe:
        sync_system_codex_profile(cfg, state)
        return state
    probe_ok, error_class = run_primary_probe(cfg)
    now = _utc_now()
    if probe_ok:
        def _recover_or_hold(state: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
            success_count = int(state.get("consecutive_probe_successes") or 0) + 1
            base = {
                **state,
                "last_probe_at_utc": now,
                "last_success_at_utc": now,
                "updated_at_utc": now,
                "consecutive_failures": 0,
                "last_error_class": "",
                "consecutive_probe_successes": success_count,
            }
            if success_count < int(settings.get("recovery_success_threshold") or 1):
                base["active_profile"] = settings["fallback_profile"]
                base["circuit_state"] = "probing"
                return base
            base["active_profile"] = settings["primary_profile"]
            base["circuit_state"] = "closed"
            base["cooldown_until_utc"] = ""
            base["consecutive_probe_successes"] = 0
            return base

        state = update_state(
            cfg,
            _recover_or_hold,
        )
    else:
        cooldown_until = _utc_after_seconds(settings["cooldown_seconds"])
        state = update_state(
            cfg,
            lambda state, settings: {
                **state,
                "active_profile": settings["fallback_profile"],
                "circuit_state": "open",
                "cooldown_until_utc": cooldown_until,
                "last_probe_at_utc": now,
                "last_failure_at_utc": now,
                "updated_at_utc": now,
                "consecutive_failures": int(state.get("consecutive_failures") or 0) + 1,
                "consecutive_probe_successes": 0,
                "last_error_class": error_class,
            },
        )
    sync_system_codex_profile(cfg, state)
    return state


def run_primary_probe(cfg: dict | None) -> tuple[bool, str]:
    settings = load_failover_settings(cfg)
    if not settings["enabled"]:
        return True, ""
    runtime = dict((cfg or {}).get("cli_runtime") or {})
    providers = dict(runtime.get("providers") or {})
    codex_provider = dict(providers.get("codex") or {})
    command = str(codex_provider.get("path") or "codex").strip() or "codex"
    resolved_command = shutil.which(command)
    if not resolved_command:
        return False, "network_error"
    args = [resolved_command]
    if bool(codex_provider.get("search")):
        args.append("--search")
    if bool(codex_provider.get("skip_git_repo_check", True)):
        skip_git_repo_check = True
    else:
        skip_git_repo_check = False
    args.extend(["exec", "--json", "--color", "never", "-C", str(Path.home())])
    if settings["probe_model"]:
        args.extend(["--model", settings["probe_model"]])
    if skip_git_repo_check:
        args.append("--skip-git-repo-check")
    args.extend(["--profile", settings["primary_profile"], "-"])
    env = dict(os.environ.copy())
    try:
        completed = subprocess.run(
            args,
            input=settings["probe_prompt"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings["probe_timeout_seconds"],
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception:
        return False, "network_error"
    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    combined = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
    if completed.returncode == 0 and "OK" in combined:
        return True, ""
    error_class = classify_failure(combined)
    return False, error_class or "network_error"


def sync_system_codex_profile(cfg: dict | None, state: dict[str, Any] | None = None) -> str:
    settings = load_failover_settings(cfg)
    if not settings["enabled"]:
        return ""
    target = str((state or {}).get("active_profile") or settings["primary_profile"]).strip() or settings["primary_profile"]
    config_path = Path(settings["codex_config_path"])
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        content = _read_text_lossy(config_path)
        lines = content.splitlines()
    else:
        lines = []
    updated_lines = list(lines)
    section_index = next((idx for idx, line in enumerate(updated_lines) if str(line).lstrip().startswith("[")), len(updated_lines))
    replaced = False
    for idx in range(section_index):
        if _TOP_LEVEL_PROFILE_RE.match(updated_lines[idx] or ""):
            updated_lines[idx] = f'profile = "{target}"'
            replaced = True
            break
    if not replaced:
        insertion = [f'profile = "{target}"', ""]
        updated_lines = insertion + updated_lines
    rendered = "\n".join(updated_lines).rstrip() + "\n"
    _atomic_write_text(config_path, rendered)
    return target


def update_state(cfg: dict | None, updater) -> dict[str, Any]:
    settings = load_failover_settings(cfg)
    with _state_lock(settings):
        state = _read_state_unlocked(settings)
        next_state = updater(dict(state), settings)
        normalized = _normalize_state(dict(next_state or state), settings)
        _write_state_unlocked(settings, normalized)
        return normalized


def classify_failure(output: str) -> str:
    normalized = str(output or "").strip().lower()
    if not normalized:
        return "network_error"
    if any(marker in normalized for marker in _TIMEOUT_MARKERS):
        return "timeout"
    if _HTTP_429_RE.search(normalized):
        return "http_429"
    if _HTTP_5XX_RE.search(normalized):
        return "http_5xx"
    if any(marker in normalized for marker in _NETWORK_MARKERS):
        return "network_error"
    return ""


def should_trip(settings: dict[str, Any], error_class: str) -> bool:
    if error_class == "timeout":
        return bool(settings.get("trip_on_timeout", True))
    if error_class == "network_error":
        return bool(settings.get("trip_on_network_error", True))
    if error_class == "http_429":
        return bool(settings.get("trip_on_http_429", True))
    if error_class == "http_5xx":
        return bool(settings.get("trip_on_http_5xx", True))
    return False


def _read_state_unlocked(settings: dict[str, Any]) -> dict[str, Any]:
    path = Path(settings["state_path"])
    if not path.exists():
        state = _normalize_state(default_state(settings), settings)
        _write_state_unlocked(settings, state)
        return state
    try:
        payload = json.loads(_read_text_lossy(path))
    except Exception:
        payload = {}
    return _normalize_state(dict(payload or {}), settings)


def _write_state_unlocked(settings: dict[str, Any], state: dict[str, Any]) -> None:
    path = Path(settings["state_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def _normalize_state(state: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    base = default_state(settings)
    base.update({key: value for key, value in dict(state or {}).items() if value is not None})
    active = str(base.get("active_profile") or settings["primary_profile"]).strip()
    if active not in {settings["primary_profile"], settings["fallback_profile"]}:
        active = settings["primary_profile"]
    circuit_state = str(base.get("circuit_state") or "closed").strip().lower()
    if circuit_state not in {"closed", "open", "probing"}:
        circuit_state = "closed"
    base["active_profile"] = active
    base["primary_profile"] = settings["primary_profile"]
    base["fallback_profile"] = settings["fallback_profile"]
    base["circuit_state"] = circuit_state
    base["consecutive_failures"] = max(0, int(base.get("consecutive_failures") or 0))
    base["consecutive_probe_successes"] = max(0, int(base.get("consecutive_probe_successes") or 0))
    base["updated_at_utc"] = _utc_now()
    return base


@contextlib.contextmanager
def _state_lock(settings: dict[str, Any]):
    lock_path = Path(settings["state_path"] + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _utc_after_seconds(seconds: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + max(0, int(seconds or 0))))


def _parse_utc(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ")))
    except Exception:
        return None


def _default_config_path() -> str:
    return str((Path(__file__).resolve().parents[2] / "butler_bot_code" / "configs" / "butler_bot.json").resolve())


def _load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return dict(payload or {})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Butler Codex provider failover helper")
    parser.add_argument("--config", default=_default_config_path(), help="Path to butler_bot.json")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("show-state", help="Print current failover state")
    reconcile_parser = subparsers.add_parser("reconcile", help="Probe primary profile and sync system config")
    reconcile_parser.add_argument("--no-probe", action="store_true", help="Only sync config from current state")
    args = parser.parse_args(argv)
    cfg = _load_config(str(args.config))
    if args.command == "show-state":
        print(json.dumps(read_state(cfg), ensure_ascii=False, indent=2))
        return 0
    if args.command == "reconcile":
        state = reconcile_failover(cfg, force_probe=not bool(args.no_probe))
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
