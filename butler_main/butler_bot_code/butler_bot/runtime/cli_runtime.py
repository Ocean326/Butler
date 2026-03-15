from __future__ import annotations

import json
import locale
import os
import re
import shutil
import subprocess
from typing import Callable

from memory_manager import build_cursor_cli_env, resolve_cursor_cli_cmd_path


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


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


def get_cli_runtime_settings(cfg: dict | None) -> dict:
    runtime, defaults, providers = _raw_runtime_settings(cfg)
    active = _canonical_cli_name(runtime.get("active") or "cursor")
    available = available_cli_modes(cfg)
    enabled = [name for name, provider in providers.items() if provider.get("enabled", True)]
    if active not in available:
        if "cursor" in available:
            active = "cursor"
        elif available:
            active = available[0]
        elif active not in enabled and providers:
            active = "cursor" if providers.get("cursor", {}).get("enabled", True) else next(iter(providers.keys()), "cursor")
    return {
        "active": active,
        "allow_runtime_override": bool(runtime.get("allow_runtime_override", True)),
        "defaults": defaults,
        "providers": providers,
    }


def _raw_runtime_settings(cfg: dict | None) -> tuple[dict, dict, dict]:
    snapshot = dict(cfg or {})
    runtime = snapshot.get("cli_runtime") if isinstance(snapshot.get("cli_runtime"), dict) else {}
    defaults = runtime.get("defaults") if isinstance(runtime.get("defaults"), dict) else {}
    providers = runtime.get("providers") if isinstance(runtime.get("providers"), dict) else {}
    normalized_providers = {str(name).strip().lower(): dict(provider or {}) for name, provider in providers.items()}
    if not normalized_providers:
        normalized_providers = {"cursor": {"enabled": True}, "codex": {"enabled": True}}
    return dict(runtime or {}), dict(defaults or {}), normalized_providers


def available_cli_modes(cfg: dict | None) -> list[str]:
    _, _, providers = _raw_runtime_settings(cfg)
    available = []
    for name in ("cursor", "codex"):
        provider = providers.get(name) if isinstance(providers, dict) else None
        if not isinstance(provider, dict):
            continue
        if provider.get("enabled", True) and cli_provider_available(name, cfg):
            available.append(name)
    if available:
        return available
    for name in ("cursor", "codex"):
        provider = providers.get(name) if isinstance(providers, dict) else None
        if not isinstance(provider, dict) or provider.get("enabled", True):
            available.append(name)
    return available


def normalize_cli_name(cli_name: str | None, cfg: dict | None) -> str:
    requested = _canonical_cli_name(cli_name)
    if requested in available_cli_modes(cfg):
        return requested
    active = str(get_cli_runtime_settings(cfg).get("active") or "cursor").strip().lower()
    return active if active in {"cursor", "codex"} else "cursor"


def normalize_model_name(model_name: str | None, cli_name: str | None) -> str:
    model = str(model_name or "").strip() or "auto"
    if _canonical_cli_name(cli_name) == "cursor":
        return "auto"
    return model


def _canonical_cli_name(cli_name: str | None) -> str:
    lowered = str(cli_name or "").strip().lower()
    return "codex" if lowered in {"codex", "codex-cli"} else "cursor"


def cli_provider_available(cli_name: str | None, cfg: dict | None) -> bool:
    requested = _canonical_cli_name(cli_name)
    _, _, providers = _raw_runtime_settings(cfg)
    provider = dict(providers.get(requested) or {})
    if provider and not provider.get("enabled", True):
        return False
    if requested == "cursor":
        return os.path.isfile(resolve_cursor_cli_cmd_path(cfg))
    command = str(provider.get("path") or "codex").strip() or "codex"
    return _command_exists(command)


def resolve_runtime_request(cfg: dict | None, runtime_request: dict | None = None, *, model_override: str | None = None) -> dict:
    settings = get_cli_runtime_settings(cfg)
    defaults = dict(settings.get("defaults") or {})
    request = dict(defaults)
    incoming = dict(runtime_request or {})
    if bool(settings.get("allow_runtime_override", True)):
        request.update({key: value for key, value in incoming.items() if value not in (None, "")})
    request["cli"] = normalize_cli_name(incoming.get("cli") or settings.get("active") or "cursor", cfg)
    request["model"] = normalize_model_name(model_override or request.get("model") or "auto", request.get("cli"))
    request["profile"] = str(request.get("profile") or "").strip()
    request["speed"] = str(request.get("speed") or "").strip()
    request["config_overrides"] = _normalize_str_list(request.get("config_overrides"))
    request["extra_args"] = _normalize_str_list(request.get("extra_args"))
    return request


def list_available_models(workspace: str, timeout: int, cfg: dict | None = None, runtime_request: dict | None = None) -> tuple[list[str], str | None]:
    resolved = resolve_runtime_request(cfg, runtime_request)
    cli_name = str(resolved.get("cli") or "cursor").strip()
    provider = _provider_config(cfg, cli_name)
    known_models = [str(item).strip() for item in provider.get("known_models") or [] if str(item).strip()]
    if cli_name == "codex":
        return (known_models or ["gpt-5.2", "gpt-5"]), None
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
        )
    except Exception as exc:
        return known_models, str(exc)
    output = strip_ansi((completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else ""))
    models = _parse_models_output(output)
    if not models:
        models = known_models
    return models, None if models else "未解析到可用模型"


def run_prompt(
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None = None,
    runtime_request: dict | None = None,
    *,
    stream: bool = False,
    on_segment: Callable[[str], None] | None = None,
) -> tuple[str, bool]:
    resolved = resolve_runtime_request(cfg, runtime_request)
    if str(resolved.get("cli") or "cursor").strip() == "codex":
        return _run_codex(prompt, workspace, timeout, cfg, resolved, on_segment=on_segment)
    return _run_cursor(prompt, workspace, timeout, cfg, resolved, stream=stream, on_segment=on_segment)


def _provider_config(cfg: dict | None, cli_name: str) -> dict:
    providers = get_cli_runtime_settings(cfg).get("providers") or {}
    return dict(providers.get(cli_name) or {})


def _build_codex_env(provider: dict) -> dict:
    env = dict(os.environ.copy())
    for env_key, provider_key in (
        ("HTTP_PROXY", "http_proxy"),
        ("HTTPS_PROXY", "https_proxy"),
        ("ALL_PROXY", "all_proxy"),
        ("NO_PROXY", "no_proxy"),
    ):
        value = str(provider.get(provider_key) or "").strip()
        if value:
            env[env_key] = value
    return env


def _command_exists(command: str) -> bool:
    candidate = str(command or "").strip()
    if not candidate:
        return False
    if os.path.isfile(candidate):
        return True
    return shutil.which(candidate) is not None


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


def _run_cursor(
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None,
    runtime_request: dict,
    *,
    stream: bool,
    on_segment: Callable[[str], None] | None,
) -> tuple[str, bool]:
    agent_cmd = resolve_cursor_cli_cmd_path(cfg)
    if not os.path.isfile(agent_cmd):
        return f"错误：未找到 Cursor CLI，请检查路径 {agent_cmd}", False
    args = [
        agent_cmd, "-p", "--force", "--trust", "--approve-mcps",
        "--model", str(runtime_request.get("model") or "auto"),
        "--output-format", "json",
        "--workspace", workspace,
    ]
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
        )
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
        output = _extract_cursor_output(stdout_text, stderr_text)
        clean = strip_ansi(output).strip()
        if clean and on_segment:
            on_segment(clean)
        return clean or ("执行超时" if timed_out else ""), bool(clean) and proc.returncode == 0
    except Exception as exc:
        return f"管家bot 执行异常: {exc}", False


def _run_codex(
    prompt: str,
    workspace: str,
    timeout: int,
    cfg: dict | None,
    runtime_request: dict,
    *,
    on_segment: Callable[[str], None] | None,
) -> tuple[str, bool]:
    provider = _provider_config(cfg, "codex")
    command = str(provider.get("path") or "codex").strip() or "codex"
    resolved_command = _resolve_command_path(command)
    if not resolved_command:
        return f"错误：未找到 Codex CLI，请检查 path 配置: {command}", False
    args = [resolved_command]
    approval = str(provider.get("ask_for_approval") or "").strip()
    if approval:
        args.extend(["--ask-for-approval", approval])
    if bool(provider.get("search")):
        args.append("--search")
    args.extend([
        "exec", "--json", "--color", "never", "--full-auto", "-C", workspace,
    ])
    model_name = str(runtime_request.get("model") or "").strip()
    if model_name and model_name != "auto":
        args.extend(["--model", model_name])
    if bool(provider.get("skip_git_repo_check", True)):
        args.append("--skip-git-repo-check")
    sandbox = str(provider.get("sandbox") or "").strip()
    if sandbox:
        args.extend(["--sandbox", sandbox])
    profile = str(runtime_request.get("profile") or provider.get("profile") or "").strip()
    if profile:
        args.extend(["--profile", profile])
    for override in _build_codex_overrides(provider, runtime_request):
        args.extend(["-c", override])
    args.extend(_normalize_str_list(provider.get("extra_args")))
    args.extend(_normalize_str_list(runtime_request.get("extra_args")))
    args.append("-")
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            input=prompt or "",
            timeout=max(10, int(timeout or 0)),
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
            env=_build_codex_env(provider),
        )
    except subprocess.TimeoutExpired:
        return "执行超时", False
    except Exception as exc:
        return f"管家bot 执行异常: {exc}", False
    output = _extract_codex_output(completed.stdout or "", completed.stderr or "")
    clean = strip_ansi(output).strip()
    if clean and on_segment:
        on_segment(clean)
    return clean, bool(clean) and completed.returncode == 0


def _build_codex_overrides(provider: dict, runtime_request: dict) -> list[str]:
    overrides = _normalize_str_list(runtime_request.get("config_overrides"))
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


def _extract_codex_output(stdout_text: str, stderr_text: str) -> str:
    collected: list[str] = []
    for line in str(stdout_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except Exception:
            collected.append(stripped)
            continue
        if not isinstance(payload, dict):
            continue
        for key in ("output_text", "text", "content", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                collected.append(value.strip())
                break
        if str(payload.get("event") or payload.get("type") or "").strip().lower() in {"error", "failed"}:
            error_text = str(payload.get("error") or payload.get("detail") or "").strip()
            if error_text:
                collected.append(error_text)
    return "\n".join(collected).strip() or str(stderr_text or "").strip()

