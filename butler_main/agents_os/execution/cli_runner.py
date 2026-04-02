from __future__ import annotations

import json
import locale
import os
import re
import signal
import time
import shutil
import subprocess
import threading
from typing import Any, Callable

from butler_main.agents_os.runtime import KNOWN_CAPABILITIES, build_default_vendor_registry, canonical_vendor_name
from butler_main.agents_os.skills import normalize_skill_exposure_payload, skill_exposure_provider_override

from .cursor_cli_support import apply_project_python_env, build_cursor_cli_env, resolve_cursor_cli_cmd_path
from . import codex_cursor_switchover
from . import provider_failover


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
CLI_PROVIDER_ORDER = ("codex", "cursor", "claude")
# 配置与 UI 的默认 active；实际执行在无显式 cli 时仍优先 Codex（见 resolve_runtime_request）。
DEFAULT_CLI_PROVIDER = "cursor"
CLI_PROVIDER_ALIASES = {
    "cursor": "cursor",
    "cursor-cli": "cursor",
    "codex": "codex",
    "codex-cli": "codex",
    "claude": "claude",
    "claude-cli": "claude",
    "anthropic": "claude",
}
CLI_PROVIDER_DEFAULTS = {
    "cursor": {"enabled": True},
    "codex": {
        "enabled": True,
        "path": "codex",
        "inherit_proxy_env": True,
        "sandbox": "danger-full-access",
        "ask_for_approval": "never",
        "skip_git_repo_check": True,
        "ephemeral": False,
        "search": True,
    },
    "claude": {"enabled": False},
}
CLI_PROVIDER_KNOWN_MODELS = {
    "codex": ["gpt-5.4", "gpt-5.2", "gpt-5"],
    "claude": ["claude-sonnet-4", "claude-opus-4"],
}
DEFAULT_RUNTIME_PROFILE_ALIASES = {
    "default": "openai",
    "默认": "openai",
    "openai": "openai",
    "aixj": "aixj",
    "aixj_vip": "aixj",
    "relay": "aixj",
}
_ACTIVE_PROCESS_LOCK = threading.Lock()
_ACTIVE_PROCESSES: dict[str, dict] = {}
_VENDOR_CAPABILITY_REGISTRY = build_default_vendor_registry()

# Codex 流式输出里常见 “Reconnecting... n/m” 与 child 超时文案；用于提前 kill 并判失败以触发 Cursor 回退。
_CODEX_RECONNECT_PROGRESS_RE = re.compile(r"reconnecting\.\.\.\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)


_DEFAULT_CURSOR_CONTINUE_PREFIX = (
    "[上下文：上一阶段 Codex 执行已被用户终止，请直接接续完成下列用户需求。]\n\n"
)


def _cursor_continue_after_codex_cancel_settings(cfg: dict | None) -> dict:
    runtime = dict((cfg or {}).get("cli_runtime") or {})
    raw = dict(runtime.get("cursor_continue_after_codex_cancel") or {})
    prefix = str(raw.get("prompt_prefix") or "").strip()
    return {
        "enabled": bool(raw.get("enabled", True)),
        "prompt_prefix": prefix if prefix else _DEFAULT_CURSOR_CONTINUE_PREFIX,
    }


def _codex_stall_settings(cfg: dict | None) -> dict:
    runtime = dict((cfg or {}).get("cli_runtime") or {})
    raw = dict(runtime.get("codex_stall_detection") or {})
    return {
        "enabled": bool(raw.get("enabled", True)),
        "abort_on_reconnect_exhausted": bool(raw.get("abort_on_reconnect_exhausted", True)),
        "abort_on_child_process_timeout_message": bool(raw.get("abort_on_child_process_timeout_message", True)),
        "stall_wall_seconds": max(20, int(raw.get("stall_wall_seconds") or 150)),
        "min_reconnect_markers_for_stall": max(2, int(raw.get("min_reconnect_markers_for_stall") or 4)),
        "poll_interval_seconds": min(2.0, max(0.15, float(raw.get("poll_interval_seconds") or 0.35))),
    }


def _codex_stall_abort_blob(blob: str, stall_cfg: dict) -> str | None:
    if not str(blob or "").strip():
        return None
    if not stall_cfg.get("enabled", True):
        return None
    low = str(blob).lower()
    if stall_cfg.get("abort_on_child_process_timeout_message", True):
        if "timeout waiting for child process to exit" in low:
            return "Codex 子进程退出超时（timeout waiting for child process to exit），已由 Butler 中止"
    if stall_cfg.get("abort_on_reconnect_exhausted", True):
        last: tuple[int, int] | None = None
        for m in _CODEX_RECONNECT_PROGRESS_RE.finditer(str(blob)):
            last = (int(m.group(1)), int(m.group(2)))
        if last is not None:
            cur, out_of = last
            if out_of >= 1 and cur >= out_of:
                return f"Codex 重连次数已用尽（{cur}/{out_of}），已由 Butler 中止"
    return None


def _codex_output_force_failed(output: str, stall_cfg: dict) -> bool:
    """进程已结束但 returncode==0 且正文仍为重连耗尽等情况时，强制视为失败。"""
    if not stall_cfg.get("enabled", True):
        return False
    return _codex_stall_abort_blob(output, stall_cfg) is not None


def _halt_codex_stream_and_terminate(
    proc: subprocess.Popen | None,
    stream_halt: threading.Event | None,
) -> None:
    if stream_halt is not None:
        stream_halt.set()
    _terminate_codex_subprocess_tree(proc)


def _wait_codex_process_with_stall_detection(
    proc: subprocess.Popen,
    stdout_chunks: list[str],
    stderr_chunks: list[str],
    deadline_monotonic: float,
    stall_cfg: dict,
    *,
    stream_halt: threading.Event | None = None,
) -> tuple[str, bool]:
    """等待 Codex 子进程结束。返回 (中止原因文案, 是否触发整体超时 deadline)。"""
    poll_iv = float(stall_cfg.get("poll_interval_seconds") or 0.35)
    run_start = time.monotonic()
    wall = int(stall_cfg.get("stall_wall_seconds") or 150)
    min_m = int(stall_cfg.get("min_reconnect_markers_for_stall") or 4)
    stall_enabled = bool(stall_cfg.get("enabled", True))

    while proc.poll() is None:
        now = time.monotonic()
        if now >= deadline_monotonic:
            _halt_codex_stream_and_terminate(proc, stream_halt)
            try:
                proc.wait(timeout=8)
            except Exception:
                pass
            return "", True
        if stall_enabled:
            blob = "".join(stdout_chunks) + "".join(stderr_chunks)
            reason = _codex_stall_abort_blob(blob, stall_cfg)
            if reason:
                _halt_codex_stream_and_terminate(proc, stream_halt)
                try:
                    proc.wait(timeout=8)
                except Exception:
                    pass
                return reason, False
            if now - run_start >= wall:
                if len(_CODEX_RECONNECT_PROGRESS_RE.findall(blob)) >= min_m:
                    msg = (
                        "Codex 长时间停留在重连/流恢复状态（"
                        f"≥{min_m} 次 Reconnecting 进度且持续 ≥{wall}s），已由 Butler 中止"
                    )
                    _halt_codex_stream_and_terminate(proc, stream_halt)
                    try:
                        proc.wait(timeout=8)
                    except Exception:
                        pass
                    return msg, False
        time.sleep(poll_iv)
    return "", False


def _windows_hidden_subprocess_kwargs() -> dict:
    if os.name != "nt":
        return {}
    kwargs: dict = {}
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if creationflags:
        kwargs["creationflags"] = creationflags
    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    if callable(startupinfo_factory):
        startupinfo = startupinfo_factory()
        startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0))
        startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
        kwargs["startupinfo"] = startupinfo
    return kwargs


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", str(text or ""))


def decode_cli_payload(payload: bytes | str | None) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    encodings = ["utf-8", "utf-8-sig"]
    preferred = str(locale.getpreferredencoding(False) or "").strip()
    if preferred:
        encodings.append(preferred)
    encodings.extend(["gbk", "cp936"])
    seen: set[str] = set()
    for encoding_name in encodings:
        key = encoding_name.lower()
        if not encoding_name or key in seen:
            continue
        seen.add(key)
        try:
            return payload.decode(encoding_name)
        except Exception:
            continue
    return payload.decode("utf-8", errors="replace")


def cli_timeout_grace_seconds(timeout: int) -> int:
    value = int(timeout or 0)
    return min(300, max(30, value // 2 if value > 0 else 60))


def _register_active_process(proc: subprocess.Popen, runtime_request: dict | None) -> str:
    token = f"proc_{id(proc)}"
    payload = dict(runtime_request or {})
    with _ACTIVE_PROCESS_LOCK:
        _ACTIVE_PROCESSES[token] = {
            "proc": proc,
            "request_id": str(payload.get("request_id") or "").strip(),
            "session_id": str(payload.get("session_id") or "").strip(),
            "actor_id": str(payload.get("actor_id") or "").strip(),
            "message_id": str(payload.get("message_id") or "").strip(),
            "channel": str(payload.get("channel") or "").strip(),
            "cancelled": False,
        }
    return token


def _unregister_active_process(token: str) -> dict:
    with _ACTIVE_PROCESS_LOCK:
        return dict(_ACTIVE_PROCESSES.pop(token, {}) or {})


def _is_active_process_cancelled(token: str) -> bool:
    with _ACTIVE_PROCESS_LOCK:
        return bool((_ACTIVE_PROCESSES.get(token) or {}).get("cancelled"))


def _terminate_codex_subprocess_tree(proc: subprocess.Popen | None) -> None:
    """终止 Codex 及其子进程（Linux 上仅 kill 父进程时常遗留子进程，导致流式输出继续灌入）。"""
    if proc is None:
        return
    if os.name == "nt":
        _terminate_process_tree(proc)
        return
    pid = getattr(proc, "pid", None)
    if not pid:
        try:
            proc.kill()
        except Exception:
            pass
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except Exception:
            pass


def _terminate_process_tree(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    pid = getattr(proc, "pid", None)
    if pid:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                capture_output=True,
                timeout=5,
                **_windows_hidden_subprocess_kwargs(),
            )
        except Exception:
            pass
    for method_name in ("terminate", "kill"):
        method = getattr(proc, method_name, None)
        if not callable(method):
            continue
        try:
            method()
            break
        except Exception:
            continue


def cancel_active_runs(*, request_id: str = "", session_id: str = "", actor_id: str = "", message_id: str = "") -> dict:
    normalized_request = str(request_id or "").strip()
    normalized_session = str(session_id or "").strip()
    normalized_actor = str(actor_id or "").strip()
    normalized_message = str(message_id or "").strip()
    if not any((normalized_request, normalized_session, normalized_actor, normalized_message)):
        return {"cancelled_count": 0, "matched_count": 0}
    matched_records: list[dict] = []
    with _ACTIVE_PROCESS_LOCK:
        for record in _ACTIVE_PROCESSES.values():
            record_request = str(record.get("request_id") or "").strip()
            record_session = str(record.get("session_id") or "").strip()
            record_actor = str(record.get("actor_id") or "").strip()
            record_message = str(record.get("message_id") or "").strip()
            if normalized_request:
                matched = record_request == normalized_request
            elif normalized_message:
                matched = record_message == normalized_message
            elif normalized_session and normalized_actor:
                matched = record_session == normalized_session and record_actor == normalized_actor
            elif normalized_session:
                matched = record_session == normalized_session
            else:
                matched = bool(normalized_actor and record_actor == normalized_actor)
            if not matched:
                continue
            record["cancelled"] = True
            matched_records.append(dict(record))
    for record in matched_records:
        _terminate_process_tree(record.get("proc"))
    count = len(matched_records)
    return {"cancelled_count": count, "matched_count": count}


def get_cli_runtime_settings(cfg: dict | None) -> dict:
    runtime, defaults, providers = _raw_runtime_settings(cfg)
    active = _canonical_cli_name(runtime.get("active") or DEFAULT_CLI_PROVIDER)
    available = available_cli_modes(cfg)
    enabled = [name for name, provider in providers.items() if provider.get("enabled", True)]
    if active not in available:
        if available:
            active = available[0]
        elif active not in enabled and providers:
            active = next((name for name in CLI_PROVIDER_ORDER if providers.get(name, {}).get("enabled", True)), next(iter(providers.keys()), DEFAULT_CLI_PROVIDER))
    return {
        "active": active,
        "allow_runtime_override": bool(runtime.get("allow_runtime_override", True)),
        "defaults": defaults,
        "providers": providers,
    }


def runtime_profile_aliases(cfg: dict | None) -> dict[str, str]:
    runtime, _, _ = _raw_runtime_settings(cfg)
    aliases = dict(DEFAULT_RUNTIME_PROFILE_ALIASES)
    raw_aliases = runtime.get("profile_aliases") if isinstance(runtime.get("profile_aliases"), dict) else {}
    for raw_alias, raw_profile in raw_aliases.items():
        alias = str(raw_alias or "").strip().lower()
        profile = str(raw_profile or "").strip()
        if alias and profile:
            aliases[alias] = profile
    return aliases


def normalize_runtime_profile(profile_name: str | None, cfg: dict | None) -> str:
    profile = str(profile_name or "").strip()
    if not profile:
        return ""
    aliases = runtime_profile_aliases(cfg)
    return aliases.get(profile.lower(), profile)


def available_runtime_profiles(cfg: dict | None) -> list[str]:
    aliases = runtime_profile_aliases(cfg)
    return list(dict.fromkeys(str(profile).strip() for profile in aliases.values() if str(profile).strip()))


def current_runtime_profile(cfg: dict | None, cli_name: str | None = None) -> str:
    resolved_cli = normalize_cli_name(cli_name, cfg)
    if resolved_cli == "codex":
        active = provider_failover.current_profile(cfg)
        if active:
            return active
    resolved = resolve_runtime_request(cfg, {"cli": resolved_cli}, model_override=(cfg or {}).get("agent_model"))
    return str(resolved.get("profile") or "").strip()


def _raw_runtime_settings(cfg: dict | None) -> tuple[dict, dict, dict]:
    snapshot = dict(cfg or {})
    runtime = snapshot.get("cli_runtime") if isinstance(snapshot.get("cli_runtime"), dict) else {}
    defaults = runtime.get("defaults") if isinstance(runtime.get("defaults"), dict) else {}
    providers = runtime.get("providers") if isinstance(runtime.get("providers"), dict) else {}
    normalized_providers = {name: dict(CLI_PROVIDER_DEFAULTS.get(name, {})) for name in CLI_PROVIDER_ORDER}
    for raw_name, provider in providers.items():
        canonical = _canonical_cli_name(raw_name)
        normalized_providers[canonical] = {**normalized_providers.get(canonical, {}), **dict(provider or {})}
    return dict(runtime or {}), dict(defaults or {}), normalized_providers


def available_cli_modes(cfg: dict | None) -> list[str]:
    _, _, providers = _raw_runtime_settings(cfg)
    available = []
    for name in CLI_PROVIDER_ORDER:
        provider = providers.get(name) if isinstance(providers, dict) else None
        if not isinstance(provider, dict):
            continue
        if provider.get("enabled", True) and cli_provider_available(name, cfg):
            available.append(name)
    if available:
        return available
    for name in CLI_PROVIDER_ORDER:
        provider = providers.get(name) if isinstance(providers, dict) else None
        if isinstance(provider, dict) and provider.get("enabled", True):
            available.append(name)
    return available


def normalize_cli_name(cli_name: str | None, cfg: dict | None) -> str:
    requested = _canonical_cli_name(cli_name)
    if requested in available_cli_modes(cfg):
        return requested
    active = str(get_cli_runtime_settings(cfg).get("active") or DEFAULT_CLI_PROVIDER).strip().lower()
    return active if active in CLI_PROVIDER_ORDER else DEFAULT_CLI_PROVIDER


def normalize_model_name(model_name: str | None, cli_name: str | None) -> str:
    model = str(model_name or "").strip() or "auto"
    if _canonical_cli_name(cli_name) == "cursor":
        return "auto"
    return model


def _canonical_cli_name(cli_name: str | None) -> str:
    lowered = str(cli_name or "").strip().lower()
    if not lowered:
        return DEFAULT_CLI_PROVIDER
    return CLI_PROVIDER_ALIASES.get(lowered, "cursor")


def cli_provider_available(cli_name: str | None, cfg: dict | None) -> bool:
    requested = _canonical_cli_name(cli_name)
    _, _, providers = _raw_runtime_settings(cfg)
    provider = dict(providers.get(requested) or {})
    if provider and not provider.get("enabled", True):
        return False
    if requested == "cursor":
        return os.path.isfile(resolve_cursor_cli_cmd_path(cfg))
    command = str(provider.get("path") or requested).strip() or requested
    return _command_exists(command)


def resolve_runtime_request(cfg: dict | None, runtime_request: dict | None = None, *, model_override: str | None = None) -> dict:
    settings = get_cli_runtime_settings(cfg)
    defaults = dict(settings.get("defaults") or {})
    request = dict(defaults)
    incoming = dict(runtime_request or {})
    if "_profile_explicit" in incoming:
        explicit_profile = bool(incoming.get("_profile_explicit"))
    else:
        explicit_profile = bool(str(incoming.get("profile") or "").strip())
    if bool(settings.get("allow_runtime_override", True)):
        request.update({key: value for key, value in incoming.items() if value not in (None, "")})
    cli_explicit = bool(str(incoming.get("cli") or "").strip())
    request["cli"] = normalize_cli_name(incoming.get("cli") or settings.get("active") or DEFAULT_CLI_PROVIDER, cfg)
    request["model"] = normalize_model_name(model_override or request.get("model") or "auto", request.get("cli"))
    skip_codex_first, count_switchover_probe = codex_cursor_switchover.resolve_codex_first_switchover(cfg)
    if (
        not cli_explicit
        and str(request.get("cli") or "").strip().lower() == "cursor"
        and cli_provider_available("codex", cfg)
        and bool(dict(_provider_config(cfg, "codex") or {}).get("enabled", True))
        and not skip_codex_first
    ):
        request["cli"] = "codex"
        request["model"] = normalize_model_name(model_override or defaults.get("model") or request.get("model") or "auto", "codex")
        if count_switchover_probe:
            request["_codex_switchover_count_probe"] = True
    request["profile"] = normalize_runtime_profile(request.get("profile"), cfg)
    request["speed"] = str(request.get("speed") or "").strip()
    if str(request.get("cli") or "").strip().lower() == "codex":
        if not explicit_profile:
            request["profile"] = ""
        if "speed" not in incoming:
            request["speed"] = ""
        if "config_overrides" not in incoming:
            request["config_overrides"] = []
        if "extra_args" not in incoming:
            request["extra_args"] = []
    skill_exposure = normalize_skill_exposure_payload(request.get("skill_exposure"))
    if skill_exposure is not None:
        request["skill_exposure"] = skill_exposure
        provider_override = skill_exposure_provider_override(skill_exposure, provider_name=str(request.get("cli") or ""))
        if provider_override:
            if not request["profile"]:
                request["profile"] = str(provider_override.get("profile") or "").strip()
            if not request["speed"]:
                request["speed"] = str(provider_override.get("speed") or "").strip()
            if not str(request.get("model") or "").strip() or str(request.get("model") or "").strip() == "auto":
                override_model = str(provider_override.get("model") or "").strip()
                if override_model:
                    request["model"] = normalize_model_name(override_model, request.get("cli"))
    request["config_overrides"] = _normalize_str_list(request.get("config_overrides"))
    request["extra_args"] = _normalize_str_list(request.get("extra_args"))
    if skill_exposure is not None:
        provider_override = skill_exposure_provider_override(skill_exposure, provider_name=str(request.get("cli") or ""))
        request["config_overrides"].extend(_normalize_str_list(provider_override.get("config_overrides")))
        request["extra_args"].extend(_normalize_str_list(provider_override.get("extra_args")))
    request["_profile_explicit"] = explicit_profile
    return request


def list_available_models(workspace: str, timeout: int, cfg: dict | None = None, runtime_request: dict | None = None) -> tuple[list[str], str | None]:
    workspace = _normalize_workspace_path(workspace)
    resolved = resolve_runtime_request(cfg, runtime_request)
    cli_name = str(resolved.get("cli") or DEFAULT_CLI_PROVIDER).strip()
    provider = _provider_config(cfg, cli_name)
    known_models = [str(item).strip() for item in provider.get("known_models") or [] if str(item).strip()]
    if cli_name in {"codex", "claude"}:
        return (known_models or CLI_PROVIDER_KNOWN_MODELS.get(cli_name, [])), None
    agent_cmd = resolve_cursor_cli_cmd_path(cfg)
    if not os.path.isfile(agent_cmd):
        return known_models, f"未找到 Cursor CLI: {agent_cmd}"
    try:
        completed = subprocess.run(
            [agent_cmd, "models", "--trust", "--workspace", workspace],
            capture_output=True,
            timeout=max(10, int(timeout or 0)),
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
            env=build_cursor_cli_env(cfg),
            **_windows_hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return known_models, str(exc)
    output = strip_ansi((completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else ""))
    models = _parse_models_output(output)
    if not models:
        models = known_models
    return models, None if models else "未解析到可用模型"


def _execution_result_output(result: dict[str, Any] | None) -> str:
    if not isinstance(result, dict):
        return ""
    output = str(result.get("output") or "").strip()
    if output:
        return output
    return str((result.get("metadata") or {}).get("summary") or "").strip()


def _path_fingerprint(path: str, *, allow_dir: bool = False) -> str:
    candidate = str(path or "").strip()
    if not candidate:
        return ""
    try:
        target = os.path.abspath(candidate)
        if allow_dir:
            if not os.path.isdir(target):
                return ""
        elif not os.path.isfile(target):
            return ""
        stat = os.stat(target)
    except OSError:
        return ""
    return f"{target}|{int(stat.st_mtime)}|{int(stat.st_size)}"


def _default_codex_home() -> str:
    configured = str(os.environ.get("CODEX_HOME") or "").strip()
    if configured:
        return configured
    return os.path.join(os.path.expanduser("~"), ".codex")


def _resolve_codex_session_store_path(provider: dict | None, runtime_request: dict | None) -> str:
    explicit = str(dict(runtime_request or {}).get("codex_home") or dict(provider or {}).get("codex_home") or "").strip()
    return explicit or _default_codex_home()


def _vendor_capabilities_payload(provider: str) -> dict[str, Any]:
    vendor = canonical_vendor_name(provider)
    capabilities: dict[str, Any] = {}
    for capability in KNOWN_CAPABILITIES:
        spec = _VENDOR_CAPABILITY_REGISTRY.get_spec(vendor, capability)
        capabilities[capability] = {
            "layer": str(spec.layer.value),
            "ownership": str(spec.ownership.value),
        }
    return {"vendor": vendor, "capabilities": capabilities}


def prepare_vendor_session_runtime_request(cfg: dict | None, runtime_request: dict | None) -> dict[str, Any]:
    request = dict(runtime_request or {})
    binding = dict(request.get("_butler_session_binding") or {})
    if not binding:
        return request
    resolved = resolve_runtime_request(cfg, request, model_override=request.get("model"))
    provider_name = canonical_vendor_name(resolved.get("cli"))
    binding_provider = canonical_vendor_name(binding.get("provider"))
    recovery_state = dict(request.get("_butler_recovery") or {})
    recovery_state.setdefault("resume_requested", False)
    recovery_state.setdefault("degraded", False)
    recovery_state.setdefault("reason", "")
    if provider_name != binding_provider:
        recovery_state.update({"reason": "provider_switched", "binding_provider": binding_provider})
        request["_butler_recovery"] = recovery_state
        return request
    if provider_name != "codex":
        request["_butler_recovery"] = recovery_state
        return request
    explicit_resume = bool(
        str(request.get("codex_mode") or "").strip().lower() == "resume"
        or str(request.get("codex_session_id") or request.get("thread_id") or "").strip()
    )
    if explicit_resume:
        recovery_state.update({"resume_requested": True, "reason": recovery_state.get("reason") or "explicit_resume"})
        request["_butler_recovery"] = recovery_state
        return request
    stored_external = dict(binding.get("external_session") or {})
    thread_id = str(binding.get("thread_id") or stored_external.get("thread_id") or "").strip()
    if not thread_id:
        request["_butler_recovery"] = recovery_state
        return request
    if not bool(binding.get("resume_durable")):
        recovery_state.update({"resume_requested": True, "degraded": True, "reason": "resume_not_durable"})
        request["_butler_recovery"] = recovery_state
        return request
    provider_cfg = _provider_config(cfg, "codex")
    current_store_fp = _path_fingerprint(_resolve_codex_session_store_path(provider_cfg, request), allow_dir=True)
    current_binary_fp = _path_fingerprint(_resolve_command_path(str(provider_cfg.get("path") or "codex").strip() or "codex"))
    stored_store_fp = str(binding.get("session_store_fingerprint") or stored_external.get("session_store_fingerprint") or "").strip()
    stored_binary_fp = str(binding.get("cli_binary_fingerprint") or stored_external.get("cli_binary_fingerprint") or "").strip()
    if stored_store_fp and current_store_fp and stored_store_fp != current_store_fp:
        recovery_state.update({"resume_requested": True, "degraded": True, "reason": "session_store_changed"})
        request["_butler_recovery"] = recovery_state
        return request
    if stored_binary_fp and current_binary_fp and stored_binary_fp != current_binary_fp:
        recovery_state.update({"resume_requested": True, "degraded": True, "reason": "cli_binary_changed"})
        request["_butler_recovery"] = recovery_state
        return request
    request["codex_mode"] = "resume"
    request["codex_session_id"] = thread_id
    recovery_state.update(
        {
            "resume_requested": True,
            "degraded": False,
            "reason": "vendor_resume",
            "binding_thread_id": thread_id,
        }
    )
    request["_butler_recovery"] = recovery_state
    return request


def _coerce_execution_result(provider: str, value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        result = dict(value)
    elif isinstance(value, tuple) and len(value) == 2:
        output, ok = value
        result = {"output": str(output or "").strip(), "ok": bool(ok)}
    else:
        result = {"output": str(value or "").strip(), "ok": False}
    output_text = str(result.get("output") or "").strip()
    ok = bool(result.get("ok"))
    metadata = dict(result.get("metadata") or {})
    stderr_text = str(result.get("stderr") or "").strip()
    failure_class = str(result.get("failure_class") or "").strip()
    if not failure_class and not ok:
        failure_blob = "\n".join(part for part in (output_text, stderr_text) if part).strip()
        failure_class = provider_failover.classify_failure(failure_blob)
        if str(metadata.get("cancelled") or "").strip():
            failure_class = "cancelled"
    result["provider"] = str(result.get("provider") or provider).strip() or provider
    result["output"] = output_text
    result["ok"] = ok
    result["returncode"] = result.get("returncode")
    result["stderr"] = stderr_text
    result["failure_class"] = failure_class
    result["usage"] = dict(result.get("usage") or {})
    result["external_session"] = dict(result.get("external_session") or {})
    result["command_events"] = list(result.get("command_events") or [])
    external_session = result["external_session"]
    if external_session:
        external_session.setdefault("provider", result["provider"])
        external_session.setdefault("resume_capable", bool(external_session.get("thread_id")))
        external_session.setdefault(
            "resume_durable",
            bool(external_session.get("resume_capable")) and bool(str(external_session.get("thread_id") or "").strip()),
        )
        if str(external_session.get("thread_id") or "").strip() and not str(external_session.get("durable_resume_id") or "").strip():
            external_session["durable_resume_id"] = str(external_session.get("thread_id") or "").strip()
    metadata.setdefault("vendor_capabilities", _vendor_capabilities_payload(provider))
    metadata.setdefault("recovery_state", dict(external_session.get("recovery_state") or result.get("recovery_state") or {}))
    result["metadata"] = metadata
    return result


def _execution_result_to_receipt(
    result: dict[str, Any],
    *,
    workspace: str,
    runtime_request: dict | None = None,
) -> "ExecutionReceipt":
    from butler_main.agents_os.contracts import OutputBundle, TextBlock
    from butler_main.runtime_os.process_runtime import ExecutionReceipt

    request = dict(runtime_request or {})
    provider = str(result.get("provider") or request.get("cli") or DEFAULT_CLI_PROVIDER).strip() or DEFAULT_CLI_PROVIDER
    output_text = str(result.get("output") or "").strip()
    failure_class = str(result.get("failure_class") or "").strip()
    ok = bool(result.get("ok"))
    status = "completed" if ok else ("cancelled" if failure_class == "cancelled" else "failed")
    default_summary = f"{provider} execution {'completed' if ok else 'failed'}"
    summary = (output_text or str((result.get("metadata") or {}).get("summary") or "").strip() or default_summary).strip()
    cli_events = {
        "usage": dict(result.get("usage") or {}),
        "command_events": list(result.get("command_events") or []),
    }
    result_metadata = dict(result.get("metadata") or {})
    bundle = OutputBundle(
        status="ready" if ok else "failed",
        summary=summary[:500],
        text_blocks=[TextBlock(text=output_text)] if output_text else [],
        metadata={
            "provider": provider,
            "external_session": dict(result.get("external_session") or {}),
            "usage": dict(cli_events["usage"]),
        },
    )
    metadata = {
        "workspace": workspace,
        "provider": provider,
        "provider_returncode": result.get("returncode"),
        "returncode": result.get("returncode"),
        "failure_class": failure_class,
        "runtime_request": dict(request),
        "cli_events": cli_events,
        "usage": dict(cli_events["usage"]),
        "external_session": dict(result.get("external_session") or {}),
        "recovery_state": dict(result_metadata.get("recovery_state") or {}),
        "vendor_capabilities": dict(result_metadata.get("vendor_capabilities") or {}),
        "command_events": list(cli_events["command_events"]),
        "stderr": str(result.get("stderr") or "").strip(),
        **result_metadata,
    }
    return ExecutionReceipt(
        invocation_id=str(request.get("invocation_id") or "").strip(),
        workflow_id=str(request.get("workflow_id") or "").strip(),
        agent_id=str(request.get("agent_id") or "").strip(),
        status=status,
        summary=summary[:500],
        output_bundle=bundle,
        metadata=metadata,
    )


def _receipt_text(receipt: "ExecutionReceipt") -> str:
    bundle = getattr(receipt, "output_bundle", None)
    if bundle is not None:
        for block in list(getattr(bundle, "text_blocks", []) or [])[::-1]:
            text = str(getattr(block, "text", "") or "").strip()
            if text:
                return text
    return str(getattr(receipt, "summary", "") or "").strip()


def _fallback_metadata(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": str(result.get("provider") or "").strip(),
        "ok": bool(result.get("ok")),
        "summary": _execution_result_output(result)[:500],
        "provider_returncode": result.get("returncode"),
        "returncode": result.get("returncode"),
        "failure_class": str(result.get("failure_class") or "").strip(),
        "external_session": dict(result.get("external_session") or {}),
        "cli_events": {
            "usage": dict(result.get("usage") or {}),
            "command_events": list(result.get("command_events") or []),
        },
        "usage": dict(result.get("usage") or {}),
        "command_events": list(result.get("command_events") or []),
    }


def _run_provider_detailed(
    preferred_cli: str,
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None,
    runtime_request: dict,
    *,
    stream: bool = False,
    on_segment: Callable[[str], None] | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> dict[str, Any]:
    if preferred_cli == "cursor":
        runner = _run_cursor
        if runner is _ORIGINAL_RUNNERS["cursor"]:
            return _run_cursor_detailed(prompt, workspace, timeout, cfg, runtime_request, stream=stream, on_segment=on_segment)
        return _coerce_execution_result(
            "cursor",
            runner(prompt, workspace, timeout, cfg, runtime_request, stream=stream, on_segment=on_segment),
        )
    if preferred_cli == "claude":
        runner = _run_claude
        if runner is _ORIGINAL_RUNNERS["claude"]:
            return _run_claude_detailed(prompt, workspace, timeout, cfg, runtime_request, on_segment=on_segment, on_event=on_event)
        return _coerce_execution_result(
            "claude",
            runner(prompt, workspace, timeout, cfg, runtime_request, on_segment=on_segment, on_event=on_event),
        )
    runner = _run_codex
    if runner is _ORIGINAL_RUNNERS["codex"]:
        return _run_codex_detailed(prompt, workspace, timeout, cfg, runtime_request, on_segment=on_segment, on_event=on_event)
    return _coerce_execution_result(
        "codex",
        runner(prompt, workspace, timeout, cfg, runtime_request, on_segment=on_segment, on_event=on_event),
    )


def run_prompt_receipt(
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None = None,
    runtime_request: dict | None = None,
    *,
    stream: bool = False,
    on_segment: Callable[[str], None] | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> "ExecutionReceipt":
    workspace = _normalize_workspace_path(workspace)
    incoming_request = prepare_vendor_session_runtime_request(cfg, runtime_request)
    resolved = resolve_runtime_request(cfg, incoming_request)
    explicit_profile = bool(resolved.get("_profile_explicit"))
    resolved = provider_failover.prepare_runtime_request(cfg, resolved, explicit_profile=explicit_profile)
    if resolved.pop("_codex_switchover_count_probe", None):
        codex_cursor_switchover.note_probe_attempt(cfg)
    preferred_cli = str(resolved.get("cli") or DEFAULT_CLI_PROVIDER).strip().lower()
    effective_timeout = timeout
    if preferred_cli == "codex":
        effective_timeout = provider_failover.managed_timeout_seconds(cfg, timeout, resolved)
    initial_result = _coerce_execution_result(
        preferred_cli,
        _run_provider_detailed(
            preferred_cli,
            prompt,
            workspace,
            effective_timeout,
            cfg,
            resolved,
            stream=stream,
            on_segment=on_segment,
            on_event=on_event,
        ),
    )
    output = _execution_result_output(initial_result)
    ok = bool(initial_result.get("ok"))
    if preferred_cli == "codex":
        if ok:
            codex_cursor_switchover.record_codex_primary_success(cfg)
        elif not _is_codex_user_cancelled_output(output):
            codex_cursor_switchover.record_codex_primary_failure(cfg)
    provider_failover.record_execution_result(cfg, resolved, output, ok)

    disable_fallback = bool(incoming_request.get("_disable_runtime_fallback") or resolved.get("_disable_runtime_fallback"))
    if ok or disable_fallback:
        return _execution_result_to_receipt(initial_result, workspace=workspace, runtime_request=resolved)

    fallback_cli = ""
    fallback_prompt = prompt
    if preferred_cli == "codex":
        if _is_codex_user_cancelled_output(output):
            cont = _cursor_continue_after_codex_cancel_settings(cfg)
            if cont["enabled"] and cli_provider_available("cursor", cfg):
                fallback_cli = "cursor"
                fallback_prompt = str(cont.get("prompt_prefix") or _DEFAULT_CURSOR_CONTINUE_PREFIX) + (prompt or "")
            else:
                return _execution_result_to_receipt(initial_result, workspace=workspace, runtime_request=resolved)
        else:
            fallback_cli = _fallback_cli_name(preferred_cli, cfg)
    elif _should_fallback_runtime(preferred_cli, output, cfg):
        fallback_cli = _fallback_cli_name(preferred_cli, cfg)

    if not fallback_cli:
        if preferred_cli == "codex" and not ok and not cli_provider_available("cursor", cfg):
            cpath = resolve_cursor_cli_cmd_path(cfg)
            hint = f"\n\n[butler] Cursor CLI 不可用（路径: {cpath}），无法自动切换到 Cursor 接续回复。"
            merged = (output + hint).strip() if output else hint.strip()
            result = dict(initial_result)
            result["output"] = merged
            return _execution_result_to_receipt(result, workspace=workspace, runtime_request=resolved)
        return _execution_result_to_receipt(initial_result, workspace=workspace, runtime_request=resolved)

    fallback_request = dict(resolved)
    fallback_request["cli"] = fallback_cli
    fallback_request["model"] = normalize_model_name(fallback_request.get("model"), fallback_cli)
    fallback_request["fallback_from"] = preferred_cli
    if _is_codex_user_cancelled_output(output) and fallback_cli == "cursor":
        fallback_request["fallback_reason"] = "user-cancel-cursor-continue"
    else:
        fallback_request["fallback_reason"] = "codex-failed" if preferred_cli == "codex" else "provider-unavailable"
    fallback_result = _coerce_execution_result(
        fallback_cli,
        _run_provider_detailed(
            fallback_cli,
            fallback_prompt,
            workspace,
            timeout,
            cfg,
            fallback_request,
            stream=stream,
            on_segment=on_segment,
            on_event=on_event,
        ),
    )
    fallback_meta = dict(fallback_result.get("metadata") or {})
    fallback_meta["fallback"] = {
        "from": preferred_cli,
        "reason": str(fallback_request.get("fallback_reason") or "").strip(),
        "initial_execution": _fallback_metadata(initial_result),
    }
    fallback_result["metadata"] = fallback_meta
    if not bool(fallback_result.get("ok")):
        fallback_result["metadata"]["fallback"]["fallback_execution"] = _fallback_metadata(fallback_result)
        return _execution_result_to_receipt(initial_result, workspace=workspace, runtime_request=resolved)
    return _execution_result_to_receipt(fallback_result, workspace=workspace, runtime_request=fallback_request)


def run_prompt(
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None = None,
    runtime_request: dict | None = None,
    *,
    stream: bool = False,
    on_segment: Callable[[str], None] | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> tuple[str, bool]:
    receipt = run_prompt_receipt(
        prompt,
        workspace,
        timeout,
        cfg,
        runtime_request,
        stream=stream,
        on_segment=on_segment,
        on_event=on_event,
    )
    return _receipt_text(receipt), str(getattr(receipt, "status", "") or "").strip() == "completed"


def _provider_config(cfg: dict | None, cli_name: str) -> dict:
    providers = get_cli_runtime_settings(cfg).get("providers") or {}
    return dict(providers.get(_canonical_cli_name(cli_name)) or {})


def _build_codex_env(provider: dict, workspace: str | None = None, runtime_request: dict | None = None) -> dict:
    env = dict(os.environ.copy())
    proxy_keys = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
        "GIT_HTTP_PROXY",
        "GIT_HTTPS_PROXY",
        "git_http_proxy",
        "git_https_proxy",
    )
    if not bool(provider.get("inherit_proxy_env", False)):
        for proxy_key in proxy_keys:
            env.pop(proxy_key, None)
    for transient_key in (
        "CODEX_SANDBOX_NETWORK_DISABLED",
        "CODEX_THREAD_ID",
    ):
        env.pop(transient_key, None)
    for env_key, provider_key in (("HTTP_PROXY", "http_proxy"), ("HTTPS_PROXY", "https_proxy"), ("ALL_PROXY", "all_proxy"), ("NO_PROXY", "no_proxy")):
        value = str(provider.get(provider_key) or "").strip()
        if value:
            env[env_key] = value
    codex_home = str(dict(runtime_request or {}).get("codex_home") or provider.get("codex_home") or "").strip()
    if codex_home:
        env["CODEX_HOME"] = codex_home
    return apply_project_python_env(env, workspace)


def _command_exists(command: str) -> bool:
    candidate = str(command or "").strip()
    if not candidate:
        return False
    if os.path.isfile(candidate):
        return True
    return shutil.which(candidate) is not None


def _normalize_workspace_path(workspace: str | None) -> str:
    candidate = str(workspace or "").strip()
    if candidate:
        try:
            resolved = os.path.abspath(candidate)
            if os.path.isdir(resolved):
                return resolved
        except Exception:
            pass
    try:
        return os.getcwd()
    except Exception:
        return "."


def _resolve_command_path(command: str) -> str:
    candidate = str(command or "").strip()
    if not candidate:
        return ""
    if os.path.isfile(candidate):
        return candidate
    return str(shutil.which(candidate) or "").strip()


def _normalize_str_list(values) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _parse_models_output(output: str) -> list[str]:
    models: list[str] = []
    for line in strip_ansi(output).splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("available models"):
            continue
        match = re.match(r"^(?P<model>[A-Za-z0-9._:-]+)\s+-\s+.+$", stripped)
        token = str(match.group("model") or "").strip() if match else (stripped.split()[0] if stripped.split() else "")
        if token and re.fullmatch(r"[A-Za-z0-9._:-]+", token) and token not in models:
            models.append(token)
    return models


def _run_cursor_detailed(
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None,
    runtime_request: dict,
    *,
    stream: bool,
    on_segment: Callable[[str], None] | None,
) -> dict[str, Any]:
    del stream
    agent_cmd = resolve_cursor_cli_cmd_path(cfg)
    if not os.path.isfile(agent_cmd):
        return _coerce_execution_result(
            "cursor",
            {
                "provider": "cursor",
                "output": f"错误：未找到 Cursor CLI，请检查路径 {agent_cmd}",
                "ok": False,
                "failure_class": "unavailable",
            },
        )
    args = [agent_cmd, "-p", "--force", "--trust", "--approve-mcps", "--model", str(runtime_request.get("model") or "auto"), "--output-format", "json", "--workspace", workspace]
    args.extend(_normalize_str_list(runtime_request.get("extra_args")))
    try:
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
            env=build_cursor_cli_env(cfg),
            **_windows_hidden_subprocess_kwargs(),
        )
        run_token = _register_active_process(proc, runtime_request)
        stdout_text = ""
        stderr_text = ""
        timed_out = False
        try:
            stdout_text, stderr_text = proc.communicate(input=prompt or "", timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            stdout_text = exc.stdout or ""
            stderr_text = exc.stderr or ""
            timed_out = True
            try:
                more_out, more_err = proc.communicate(timeout=cli_timeout_grace_seconds(timeout))
                stdout_text += more_out or ""
                stderr_text += more_err or ""
            except subprocess.TimeoutExpired:
                proc.kill()
                final_out, final_err = proc.communicate()
                stdout_text += final_out or ""
                stderr_text += final_err or ""
        finally:
            cancelled = _is_active_process_cancelled(run_token)
            _unregister_active_process(run_token)
        if cancelled:
            return _coerce_execution_result(
                "cursor",
                {
                    "provider": "cursor",
                    "output": "已终止当前执行。",
                    "ok": False,
                    "returncode": proc.returncode,
                    "failure_class": "cancelled",
                    "metadata": {"cancelled": True},
                },
            )
        output = _extract_cursor_output(stdout_text, stderr_text)
        clean = strip_ansi(output).strip()
        stderr_clean = strip_ansi(stderr_text).strip()
        if clean and on_segment:
            on_segment(clean)
        merged = clean or ("执行超时" if timed_out else stderr_clean)
        return _coerce_execution_result(
            "cursor",
            {
                "provider": "cursor",
                "output": merged,
                "ok": bool(clean) and proc.returncode == 0,
                "returncode": proc.returncode,
                "stderr": stderr_clean,
                "failure_class": "timeout" if timed_out else "",
                "metadata": {"timed_out": timed_out},
            },
        )
    except Exception as exc:
        return _coerce_execution_result(
            "cursor",
            {
                "provider": "cursor",
                "output": f"管家bot 执行异常: {exc}",
                "ok": False,
                "metadata": {"error_type": type(exc).__name__},
            },
        )


def _run_cursor(prompt: str, workspace: str, timeout: int, cfg: dict | None, runtime_request: dict, *, stream: bool, on_segment: Callable[[str], None] | None) -> tuple[str, bool]:
    result = _run_cursor_detailed(prompt, workspace, timeout, cfg, runtime_request, stream=stream, on_segment=on_segment)
    return _execution_result_output(result), bool(result.get("ok"))


def _run_codex_detailed(
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None,
    runtime_request: dict,
    *,
    on_segment: Callable[[str], None] | None,
    on_event: Callable[[dict], None] | None = None,
) -> dict[str, Any]:
    provider = _provider_config(cfg, "codex")
    command = str(provider.get("path") or "codex").strip() or "codex"
    resolved_command = _resolve_command_path(command)
    if not resolved_command:
        return _coerce_execution_result(
            "codex",
            {
                "provider": "codex",
                "output": f"错误：未找到 Codex CLI，请检查 path 配置: {command}",
                "ok": False,
                "failure_class": "unavailable",
            },
        )
    args = [resolved_command]
    if bool(provider.get("search")):
        args.append("--search")
    if _should_bypass_codex_sandbox(provider):
        args.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        approval = str(provider.get("ask_for_approval") or "").strip()
        if approval:
            args.extend(["--ask-for-approval", approval])
        sandbox = str(provider.get("sandbox") or "").strip()
        if sandbox:
            args.extend(["--sandbox", sandbox])
    args.extend(["exec", "--json", "--color", "never", "-C", workspace])
    model_name = str(runtime_request.get("model") or "").strip()
    if model_name and model_name != "auto":
        args.extend(["--model", model_name])
    if bool(provider.get("skip_git_repo_check", True)):
        args.append("--skip-git-repo-check")
    is_ephemeral = bool(provider.get("ephemeral", False))
    if is_ephemeral:
        args.append("--ephemeral")
    profile = str(runtime_request.get("profile") or provider.get("profile") or "").strip()
    if profile:
        args.extend(["--profile", profile])
    for override in _build_codex_overrides(provider, runtime_request):
        args.extend(["-c", override])
    args.extend(_normalize_str_list(provider.get("extra_args")))
    args.extend(_normalize_str_list(runtime_request.get("extra_args")))
    codex_mode = str(runtime_request.get("codex_mode") or "exec").strip().lower() or "exec"
    codex_session_id = str(runtime_request.get("codex_session_id") or runtime_request.get("thread_id") or "").strip()
    input_text = prompt or ""
    if codex_mode == "resume":
        args.append("resume")
        if codex_session_id:
            args.append(codex_session_id)
        if input_text:
            args.append("-")
    else:
        args.append("-")
    try:
        popen_kwargs = dict(
            args=args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
            env=_build_codex_env(provider, workspace, runtime_request),
            **_windows_hidden_subprocess_kwargs(),
        )
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen(**popen_kwargs)
        run_token = _register_active_process(proc, runtime_request)
    except Exception as exc:
        return _coerce_execution_result(
            "codex",
            {
                "provider": "codex",
                "output": f"管家bot 执行异常: {exc}",
                "ok": False,
                "metadata": {
                    "error_type": type(exc).__name__,
                    "recovery_state": dict(runtime_request.get("_butler_recovery") or {}),
                    "vendor_capabilities": _vendor_capabilities_payload("codex"),
                },
            },
        )

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    command_events: list[dict[str, Any]] = []
    usage_payload: dict[str, Any] = {}
    recovery_state = dict(runtime_request.get("_butler_recovery") or {})
    session_store_path = _resolve_codex_session_store_path(provider, runtime_request)
    external_session = {
        "provider": "codex",
        "thread_id": "",
        "resume_capable": False,
        "resume_durable": False,
        "mode": codex_mode,
        "requested_session_id": codex_session_id,
        "durable_resume_id": "",
        "session_persistence": "ephemeral" if is_ephemeral else "codex_home",
        "session_store_path": session_store_path,
        "session_store_fingerprint": _path_fingerprint(session_store_path, allow_dir=True),
        "cli_binary_path": resolved_command,
        "cli_binary_fingerprint": _path_fingerprint(resolved_command),
        "vendor_session_state": "resume_requested" if codex_mode == "resume" and codex_session_id else "fresh_exec",
        "recovery_state": recovery_state,
    }
    stream_emitted = {"value": False}
    stream_halt = threading.Event()

    def _emit_stdout_line(raw_line: str) -> None:
        stdout_chunks.append(raw_line)
        if stream_halt.is_set():
            return
        event = _extract_codex_json_event(raw_line)
        if not event:
            return
        if str(event.get("kind") or "") == "thread":
            thread_id = str(event.get("thread_id") or "").strip()
            if thread_id:
                external_session["thread_id"] = thread_id
                external_session["resume_capable"] = True
                external_session["resume_durable"] = bool(thread_id) and not is_ephemeral
                external_session["durable_resume_id"] = thread_id if not is_ephemeral else ""
                external_session["vendor_session_state"] = "resumed" if codex_mode == "resume" and codex_session_id else (
                    "reseeded" if recovery_state.get("degraded") else "started"
                )
            return
        if str(event.get("kind") or "") == "command":
            command_events.append(dict(event))
        if str(event.get("kind") or "") == "usage":
            usage_payload.update(dict(event.get("usage") or {}))
        if on_event and str(event.get("kind") or "") in {"command", "usage", "stderr", "error"}:
            on_event(event)
        if not on_segment:
            return
        if str(event.get("kind") or "") != "assistant":
            return
        segment = str(event.get("text") or "")
        if not segment:
            return
        stream_emitted["value"] = True
        on_segment(segment)

    def _drain_stdout() -> None:
        stdout = proc.stdout
        if stdout is None:
            return
        try:
            for raw_line in stdout:
                _emit_stdout_line(raw_line)
        finally:
            close_fn = getattr(stdout, "close", None)
            if callable(close_fn):
                close_fn()

    def _drain_stderr() -> None:
        stderr = proc.stderr
        if stderr is None:
            return
        try:
            try:
                iterator = iter(stderr)
            except TypeError:
                iterator = None
            if iterator is not None:
                for raw_line in iterator:
                    stderr_chunks.append(raw_line)
                    if stream_halt.is_set():
                        continue
                    text = strip_ansi(str(raw_line or "")).strip()
                    if text and on_event:
                        on_event({"kind": "stderr", "text": text, "source": "codex"})
            else:
                payload = stderr.read() or ""
                if payload:
                    stderr_chunks.append(payload)
                    if on_event and not stream_halt.is_set():
                        for line in str(payload).splitlines():
                            text = strip_ansi(line).strip()
                            if text:
                                on_event({"kind": "stderr", "text": text, "source": "codex"})
        finally:
            stderr.close()

    stdout_thread = threading.Thread(target=_drain_stdout, daemon=True)
    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    stall_cfg = _codex_stall_settings(cfg)
    deadline = time.monotonic() + max(10, int(timeout or 0))
    stall_abort_reason = ""
    hit_deadline = False

    try:
        if proc.stdin is not None:
            if input_text:
                proc.stdin.write(input_text)
            proc.stdin.close()
        if stall_cfg.get("enabled", True):
            stall_abort_reason, hit_deadline = _wait_codex_process_with_stall_detection(
                proc, stdout_chunks, stderr_chunks, deadline, stall_cfg, stream_halt=stream_halt
            )
        else:
            try:
                proc.wait(timeout=max(10, int(timeout or 0)))
            except subprocess.TimeoutExpired:
                hit_deadline = True
                _halt_codex_stream_and_terminate(proc, stream_halt)
    except Exception as exc:
        _halt_codex_stream_and_terminate(proc, stream_halt)
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        _unregister_active_process(run_token)
        return _coerce_execution_result(
            "codex",
            {
                "provider": "codex",
                "output": f"管家bot 执行异常: {exc}",
                "ok": False,
                "external_session": external_session,
                "command_events": command_events,
                "usage": usage_payload,
                "metadata": {
                    "error_type": type(exc).__name__,
                    "recovery_state": recovery_state,
                    "vendor_capabilities": _vendor_capabilities_payload("codex"),
                },
            },
        )

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)

    if hit_deadline:
        if _is_active_process_cancelled(run_token):
            _unregister_active_process(run_token)
            return _coerce_execution_result(
                "codex",
                {
                    "provider": "codex",
                    "output": "已终止当前执行。",
                    "ok": False,
                    "returncode": proc.returncode,
                    "failure_class": "cancelled",
                    "external_session": external_session,
                    "command_events": command_events,
                    "usage": usage_payload,
                    "metadata": {
                        "cancelled": True,
                        "recovery_state": recovery_state,
                        "vendor_capabilities": _vendor_capabilities_payload("codex"),
                    },
                },
            )
        output = _extract_codex_output("".join(stdout_chunks), "".join(stderr_chunks))
        clean = strip_ansi(output).strip()
        stderr_clean = strip_ansi("".join(stderr_chunks)).strip()
        _unregister_active_process(run_token)
        return _coerce_execution_result(
            "codex",
            {
                "provider": "codex",
                "output": clean or "执行超时",
                "ok": False,
                "returncode": proc.returncode,
                "stderr": stderr_clean,
                "failure_class": "timeout",
                "external_session": external_session,
                "command_events": command_events,
                "usage": usage_payload,
                "metadata": {
                    "timed_out": True,
                    "recovery_state": recovery_state,
                    "vendor_capabilities": _vendor_capabilities_payload("codex"),
                },
            },
        )

    cancelled = _is_active_process_cancelled(run_token)
    _unregister_active_process(run_token)
    if cancelled:
        return _coerce_execution_result(
            "codex",
            {
                "provider": "codex",
                "output": "已终止当前执行。",
                "ok": False,
                "returncode": proc.returncode,
                "failure_class": "cancelled",
                "external_session": external_session,
                "command_events": command_events,
                "usage": usage_payload,
                "metadata": {
                    "cancelled": True,
                    "recovery_state": recovery_state,
                    "vendor_capabilities": _vendor_capabilities_payload("codex"),
                },
            },
        )
    output = _extract_codex_output("".join(stdout_chunks), "".join(stderr_chunks))
    clean = strip_ansi(output).strip()
    stderr_clean = strip_ansi("".join(stderr_chunks)).strip()
    if stall_abort_reason:
        suffix = f"\n\n[butler] {stall_abort_reason}"
        clean = (clean + suffix).strip() if clean else stall_abort_reason.strip()
    if clean and on_segment and not stream_emitted["value"] and not stall_abort_reason:
        on_segment(clean)
    base_ok = bool(clean) and proc.returncode == 0
    if stall_abort_reason or _codex_output_force_failed(clean, stall_cfg):
        base_ok = False
    failure_class = ""
    if not base_ok:
        failure_blob = "\n".join(part for part in (clean, stderr_clean, stall_abort_reason) if part).strip()
        failure_class = provider_failover.classify_failure(failure_blob)
    return _coerce_execution_result(
        "codex",
        {
            "provider": "codex",
            "output": clean,
            "ok": base_ok,
            "returncode": proc.returncode,
            "stderr": stderr_clean,
            "failure_class": failure_class,
            "external_session": external_session,
            "command_events": command_events,
            "usage": usage_payload,
            "metadata": {
                "stall_abort_reason": stall_abort_reason,
                "recovery_state": recovery_state,
                "vendor_capabilities": _vendor_capabilities_payload("codex"),
            },
        },
    )


def _run_codex(
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None,
    runtime_request: dict,
    *,
    on_segment: Callable[[str], None] | None,
    on_event: Callable[[dict], None] | None = None,
) -> tuple[str, bool]:
    result = _run_codex_detailed(
        prompt,
        workspace,
        timeout,
        cfg,
        runtime_request,
        on_segment=on_segment,
        on_event=on_event,
    )
    return _execution_result_output(result), bool(result.get("ok"))


def _managed_failover_profile(settings: dict[str, Any], runtime_request: dict | None) -> str:
    request = dict(runtime_request or {})
    return str(
        request.get("profile")
        or request.get("_provider_failover_active_profile")
        or settings.get("primary_profile")
        or ""
    ).strip()


def _should_bypass_codex_sandbox(provider: dict) -> bool:
    if bool(provider.get("dangerously_bypass_approvals_and_sandbox")):
        return True
    sandbox = str(provider.get("sandbox") or "").strip().lower()
    approval = str(provider.get("ask_for_approval") or "").strip().lower()
    return sandbox == "danger-full-access" and approval == "never"


def _run_claude_detailed(
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None,
    runtime_request: dict,
    *,
    on_segment: Callable[[str], None] | None,
    on_event: Callable[[dict], None] | None = None,
) -> dict[str, Any]:
    del on_event
    provider = _provider_config(cfg, "claude")
    command = str(provider.get("path") or "claude").strip() or "claude"
    resolved_command = _resolve_command_path(command)
    if not resolved_command:
        return _coerce_execution_result(
            "claude",
            {
                "provider": "claude",
                "output": f"错误：未找到 Claude CLI，请检查 path 配置: {command}",
                "ok": False,
                "failure_class": "unavailable",
            },
        )
    args = [resolved_command]
    subcommand = str(provider.get("subcommand") or "").strip()
    if subcommand:
        args.append(subcommand)
    model_name = str(runtime_request.get("model") or "").strip()
    model_flag = str(provider.get("model_flag") or "--model").strip()
    if model_name and model_name != "auto" and model_flag:
        args.extend([model_flag, model_name])
    workspace_flag = str(provider.get("workspace_flag") or "").strip()
    if workspace_flag:
        args.extend([workspace_flag, workspace])
    args.extend(_normalize_str_list(provider.get("extra_args")))
    args.extend(_normalize_str_list(runtime_request.get("extra_args")))
    prompt_flag = str(provider.get("prompt_flag") or "").strip()
    prompt_via_stdin = bool(provider.get("prompt_via_stdin", True))
    input_text = prompt or ""
    if not prompt_via_stdin and prompt_flag:
        args.extend([prompt_flag, input_text])
        input_text = None
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            input=input_text,
            timeout=max(10, int(timeout or 0)),
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
            env=dict(os.environ.copy()),
            **_windows_hidden_subprocess_kwargs(),
        )
    except subprocess.TimeoutExpired:
        return _coerce_execution_result(
            "claude",
            {
                "provider": "claude",
                "output": "执行超时",
                "ok": False,
                "failure_class": "timeout",
            },
        )
    except Exception as exc:
        return _coerce_execution_result(
            "claude",
            {
                "provider": "claude",
                "output": f"管家bot 执行异常: {exc}",
                "ok": False,
                "metadata": {"error_type": type(exc).__name__},
            },
        )
    output = _extract_generic_output(completed.stdout or "", completed.stderr or "")
    clean = strip_ansi(output).strip()
    stderr_clean = strip_ansi(completed.stderr or "").strip()
    if clean and on_segment:
        on_segment(clean)
    return _coerce_execution_result(
        "claude",
        {
            "provider": "claude",
            "output": clean or stderr_clean,
            "ok": bool(clean) and completed.returncode == 0,
            "returncode": completed.returncode,
            "stderr": stderr_clean,
            "external_session": {
                "provider": "claude",
                "thread_id": "",
                "resume_capable": False,
                "resume_durable": False,
                "cli_binary_path": resolved_command,
                "cli_binary_fingerprint": _path_fingerprint(resolved_command),
                "vendor_session_state": "ephemeral_exec",
            },
            "metadata": {
                "recovery_state": dict(runtime_request.get("_butler_recovery") or {}),
                "vendor_capabilities": _vendor_capabilities_payload("claude"),
            },
        },
    )


def _run_claude(
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None,
    runtime_request: dict,
    *,
    on_segment: Callable[[str], None] | None,
    on_event: Callable[[dict], None] | None = None,
) -> tuple[str, bool]:
    result = _run_claude_detailed(
        prompt,
        workspace,
        timeout,
        cfg,
        runtime_request,
        on_segment=on_segment,
        on_event=on_event,
    )
    return _execution_result_output(result), bool(result.get("ok"))


_ORIGINAL_RUNNERS = {
    "cursor": _run_cursor,
    "codex": _run_codex,
    "claude": _run_claude,
}


def _build_codex_overrides(provider: dict, runtime_request: dict) -> list[str]:
    overrides = _normalize_str_list(provider.get("config_overrides"))
    overrides.extend(_normalize_str_list(runtime_request.get("config_overrides")))
    config_map = provider.get("config_overrides_map") if isinstance(provider.get("config_overrides_map"), dict) else {}
    speed = str(runtime_request.get("speed") or "").strip()
    if speed:
        mapped_key = str(config_map.get("speed") or "").strip()
        if mapped_key:
            overrides.append(f"{mapped_key}={speed}")
    return overrides


def _extract_cursor_output(stdout_text: str, stderr_text: str) -> str:
    text = str(stdout_text or "").strip()
    if text:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return str(payload.get("result") or payload.get("output") or "").strip() or text
        except Exception:
            pass
    return text or str(stderr_text or "").strip()


def _should_fallback_runtime(cli_name: str, output: str, cfg: dict | None) -> bool:
    """非 Codex 主路径：仅在典型「不可用」载荷时切换到下一 CLI（Codex 见 run_prompt 任意失败回退）。"""
    if not bool(_fallback_cli_name(cli_name, cfg)):
        return False
    if not output:
        return True
    if _canonical_cli_name(cli_name) == "codex" and _is_codex_unusable_output(output):
        return True
    return _is_unavailable_payload(output)


def _fallback_cli_name(cli_name: str, cfg: dict | None) -> str:
    current = _canonical_cli_name(cli_name)
    for candidate in CLI_PROVIDER_ORDER:
        if candidate == current:
            continue
        if cli_provider_available(candidate, cfg):
            return candidate
    return ""


def _is_unavailable_payload(output: str) -> bool:
    normalized = strip_ansi(output).strip().lower()
    if not normalized:
        return True
    return normalized in {"s: [unavailable]", "[unavailable]", "unavailable", "status: unavailable", "s:[unavailable]"}


def _is_codex_unusable_output(output: str) -> bool:
    """Codex 二进制缺失或明确不可用时，触发向 Cursor 等后备 CLI 切换。"""
    normalized = strip_ansi(output).strip().lower()
    if not normalized:
        return False
    markers = (
        "未找到 codex cli",
        "未找到codex cli",
        "codex: command not found",
        "'codex' is not recognized",
        "is not recognized as an internal or external command",
    )
    return any(marker in normalized for marker in markers)


def _is_codex_user_cancelled_output(output: str) -> bool:
    text = strip_ansi(str(output or "")).strip()
    return text == "已终止当前执行。"


def _extract_codex_output(stdout_text: str, stderr_text: str) -> str:
    final_text = ""
    collected_errors: list[str] = []
    for line in str(stdout_text or "").splitlines():
        event = _extract_codex_json_event(line)
        if not event:
            continue
        kind = str(event.get("kind") or "").strip()
        text = str(event.get("text") or "").strip()
        if not text:
            continue
        if kind == "assistant":
            final_text = text
            continue
        if kind in {"error", "stderr"}:
            collected_errors.append(text)
            continue
    if collected_errors:
        blob = "\n".join(collected_errors).strip()
        if final_text:
            return f"{blob}\n{final_text}".strip()
        return blob
    if final_text:
        return final_text
    return str(stderr_text or "").strip()


def _extract_stream_segment(raw_line: str, *, keys: tuple[str, ...]) -> str:
    stripped = str(raw_line or "").strip()
    if not stripped:
        return ""
    payload = _json_object_from_line(raw_line)
    if payload is None:
        return stripped
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    event_type = str(payload.get("event") or payload.get("type") or "").strip().lower()
    if event_type in {"error", "failed"}:
        return str(payload.get("error") or payload.get("detail") or "").strip()
    return ""


def _json_object_from_line(raw_line: str) -> dict[str, Any] | None:
    stripped = str(raw_line or "").strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_codex_json_event(raw_line: str) -> dict | None:
    stripped = str(raw_line or "").strip()
    if not stripped:
        return None
    payload = _json_object_from_line(raw_line)
    if payload is None:
        return {"kind": "stderr", "text": stripped, "source": "codex"}
    event_type = str(payload.get("type") or payload.get("event") or "").strip().lower()
    if event_type == "thread.started":
        thread_payload = payload.get("thread") if isinstance(payload.get("thread"), dict) else {}
        thread_id = str(
            payload.get("thread_id")
            or payload.get("id")
            or thread_payload.get("thread_id")
            or thread_payload.get("id")
            or ""
        ).strip()
        if thread_id:
            return {"kind": "thread", "thread_id": thread_id, "event_type": event_type, "source": "codex"}
        return None
    text = _extract_stream_segment(raw_line, keys=("output_text", "text", "content", "message", "result", "output"))
    if text:
        return {"kind": "assistant", "text": text, "event_type": event_type}
    item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
    item_type = str(item.get("type") or "").strip().lower()
    if item_type == "agent_message":
        message_text = str(item.get("text") or "").strip()
        if message_text:
            return {"kind": "assistant", "text": message_text, "event_type": event_type}
        return None
    if item_type == "command_execution":
        command = strip_ansi(str(item.get("command") or "")).strip()
        status = str(item.get("status") or "").strip().lower() or ("started" if event_type.endswith("started") else "completed")
        exit_code = item.get("exit_code")
        aggregated_output = strip_ansi(str(item.get("aggregated_output") or "")).strip()
        detail = command
        if status == "completed" and exit_code is not None:
            detail = f"exit={exit_code} | {command}" if command else f"exit={exit_code}"
        elif status == "failed":
            detail = f"exit={exit_code} | {command}" if command else f"exit={exit_code}"
        if aggregated_output and status in {"failed", "completed"}:
            detail = f"{detail} | output={aggregated_output[:120]}"
        return {
            "kind": "command",
            "text": detail.strip(),
            "event_type": event_type,
            "status": status,
            "source": "codex",
        }
    if event_type == "turn.completed":
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        parts = []
        if usage.get("input_tokens") is not None:
            parts.append(f"in={usage.get('input_tokens')}")
        if usage.get("cached_input_tokens") is not None:
            parts.append(f"cached={usage.get('cached_input_tokens')}")
        if usage.get("output_tokens") is not None:
            parts.append(f"out={usage.get('output_tokens')}")
        if parts:
            return {
                "kind": "usage",
                "text": " | ".join(parts),
                "event_type": event_type,
                "source": "codex",
                "usage": dict(usage),
            }
    if event_type in {"error", "failed"}:
        error_text = str(payload.get("error") or payload.get("detail") or "").strip()
        if error_text:
            return {"kind": "error", "text": error_text, "event_type": event_type, "source": "codex"}
    return None


def _extract_generic_output(stdout_text: str, stderr_text: str) -> str:
    text = str(stdout_text or "").strip()
    if not text:
        return str(stderr_text or "").strip()
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except Exception:
            lines.append(stripped)
            continue
        if isinstance(payload, dict):
            for key in ("output_text", "text", "content", "message", "result", "output"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    lines.append(value.strip())
                    break
    return "\n".join(lines).strip() or text
