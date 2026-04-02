# -*- coding: utf-8 -*-
r"""
chat engine（source of truth）

组合 agent（消息层）与 memory_manager（记忆层）：
- 消息：接收飞书命令、回复、分段展示
- 记忆：recent 注入、回复后持久化、启动/定时维护

使用:
  飞书长连接: .venv\Scripts\python.exe -m butler_main.chat --config butler_main/butler_bot_code/configs/butler_bot.json
  本地测试: .venv\Scripts\python.exe -m butler_main.chat --prompt "你是谁"
  本地测试（流式）: .venv\Scripts\python.exe -m butler_main.chat --prompt "你是谁" (默认)
  本地测试（一次性）: .venv\Scripts\python.exe -m butler_main.chat --prompt "你是谁" --no-stream
  交互式命令行: .venv\Scripts\python.exe -m butler_main.chat --interactive (等价于飞书多轮对话，含后台服务)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Callable

_THIS_FILE = Path(__file__).resolve()
if _THIS_FILE.parent.name == "chat":
    BUTLER_MAIN_DIR = _THIS_FILE.parents[1]
    REPO_ROOT = _THIS_FILE.parents[2]
    BODY_MODULE_DIR = BUTLER_MAIN_DIR / "butler_bot_code" / "butler_bot"
else:
    BODY_MODULE_DIR = _THIS_FILE.parent
    BUTLER_MAIN_DIR = BODY_MODULE_DIR.parents[1]
    REPO_ROOT = BODY_MODULE_DIR.parents[2]
for _path in (REPO_ROOT, BUTLER_MAIN_DIR, BODY_MODULE_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from butler_main.agents_os.runtime import (
    RequestIntakeService,
    ThreadLocalStateStore,
)
from butler_main.chat.mainline import ChatMainlineService
from butler_main.chat.config_runtime import CONFIG, get_config, load_config
from butler_main.chat.decide import parse_decide_from_reply
from butler_main.chat.light_memory import ChatLightBackgroundServices, ChatLightMemoryState
from butler_main.chat.memory_runtime import (
    ChatReplyPersistenceRuntime,
    ChatRecentPromptAssembler,
    ChatRecentTurnStore,
    ChatRuntimeRequestOverrideRuntime,
    ChatSummaryPipelineRuntime,
)
from butler_main.chat.runtime import ChatRuntimeService
from butler_main.chat.providers.butler_memory_provider import ButlerChatMemoryProvider
from butler_main.chat.providers.butler_prompt_provider import ButlerChatPromptProvider
from butler_main.chat.session_modes import resolve_session_scope_id_from_invocation
from butler_main.runtime_os.agent_runtime import cli_runner as cli_runtime_service, resolve_cursor_cli_cmd_path
from butler_main.chat.prompting import set_config_provider

MARKDOWN_H2_RE = re.compile(r"(?m)^##\s+")
MODEL_DIRECTIVE_PATTERNS = [
    re.compile(
        r"^\s*(?:请)?(?:用|改用|使用|换成|换到|切换到|本轮用|这次用)\s*(?P<model>[A-Za-z0-9._:-]+|auto|自动|默认|fast|quick|快|快速)\s*(?:模型)?(?:来|去)?(?:回答|回复|处理|运行)?[：:,，\s]*(?P<rest>[\s\S]*)$",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*\[(?:模型|model)\s*[=:：]\s*(?P<model>[^\]]+)\]\s*(?P<rest>[\s\S]*)$", re.IGNORECASE),
]
MODEL_LIST_HINTS = (
    "模型列表", "可用模型", "列出模型", "有哪些模型", "能切换的模型", "支持哪些模型",
)
CURRENT_MODEL_HINTS = (
    "当前模型", "现在用什么模型", "默认模型", "当前使用模型",
)
CLI_LIST_HINTS = (
    "cli列表", "命令行列表", "可用cli", "可用命令行", "有哪些cli", "支持哪些cli", "支持哪些命令行",
)
CURRENT_CLI_HINTS = (
    "当前cli", "当前命令行", "现在用哪个cli", "当前模式", "现在是什么cli模式",
)
CURRENT_PROFILE_HINTS = (
    "当前profile", "当前配置", "当前线路", "现在用哪个profile", "现在走哪条线路",
)
DEFAULT_MODEL_ALIASES = {
    "auto": "auto",
    "自动": "auto",
    "默认": "auto",
    "default": "auto",
    "fast": "auto",
    "quick": "auto",
    "快": "auto",
    "快速": "auto",
}
CLI_RUNTIME_REQUEST_START = "【cli_runtime_json】"
CLI_RUNTIME_REQUEST_END = "【/cli_runtime_json】"
CLI_DIRECTIVE_PATTERNS = [
    re.compile(
        r"^\s*(?:请)?(?:切换到|改用|使用|换成|换到|本轮用|这次用|用)\s*(?P<cli>cursor(?:-cli)?|codex(?:-cli)?|claude(?:-cli)?|anthropic)\s*(?:模式|命令行|cli)?\s*(?:来|去)?(?:回答|回复|处理|运行)?[：:,，\s]*(?P<rest>[\s\S]*)$",
        re.IGNORECASE,
    ),
]
PROFILE_DIRECTIVE_PATTERNS = [
    re.compile(
        r"^\s*(?:请)?(?:切换到|改用|使用|换成|换到|本轮用|这次用|用)\s*(?P<profile>openai|aixj|relay|default|默认)\s*(?:线路|配置|profile|provider)?\s*(?:来|去)?(?:回答|回复|处理|运行)?[：:,，\s]*(?P<rest>[\s\S]*)$",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*\[(?:profile|线路|provider)\s*[=:：]\s*(?P<profile>[^\]]+)\]\s*(?P<rest>[\s\S]*)$", re.IGNORECASE),
]

set_config_provider(get_config)



def _cursor_cli_cmd_path() -> str:
    """Cursor IDE CLI 路径（支持配置 cursor_cli_path、兼容 dist-package 与版本号子目录）"""
    return resolve_cursor_cli_cmd_path(get_config())


_strip_ansi = cli_runtime_service.strip_ansi
_decode_cli_payload = cli_runtime_service.decode_cli_payload
_cli_timeout_grace_seconds = cli_runtime_service.cli_timeout_grace_seconds


def _runtime_model_aliases(cfg: dict) -> dict[str, str]:
    aliases = dict(DEFAULT_MODEL_ALIASES)
    raw_aliases = (cfg or {}).get("model_aliases") or {}
    if isinstance(raw_aliases, dict):
        for key, value in raw_aliases.items():
            key_text = str(key or "").strip().lower()
            value_text = str(value or "").strip()
            if key_text and value_text:
                aliases[key_text] = value_text
    return aliases


def _resolve_runtime_model(raw_model: str, cfg: dict) -> str:
    model_text = str(raw_model or "").strip()
    if not model_text:
        return str((cfg or {}).get("agent_model", "auto") or "auto")
    aliases = _runtime_model_aliases(cfg)
    return aliases.get(model_text.lower(), model_text)


def _default_runtime_profile(cfg: dict, cli_name: str | None = None) -> str:
    return str(cli_runtime_service.current_runtime_profile(cfg, cli_name)).strip()


def _codex_config_path(cfg: dict) -> str:
    runtime = dict((cfg or {}).get("cli_runtime") or {})
    failover = dict(runtime.get("provider_failover") or {})
    raw = str(failover.get("codex_config_path") or "~/.codex/config.toml").strip()
    return os.path.abspath(os.path.expanduser(raw))


def _current_profile_model(cfg: dict, cli_name: str | None) -> str:
    if cli_runtime_service.normalize_cli_name(cli_name, cfg) != "codex":
        return ""
    config_path = _codex_config_path(cfg)
    if not os.path.isfile(config_path):
        return ""
    try:
        with open(config_path, "rb") as handle:
            payload = tomllib.load(handle)
    except Exception:
        return ""
    profile_name = _default_runtime_profile(cfg, "codex")
    profiles = payload.get("profiles") if isinstance(payload.get("profiles"), dict) else {}
    if profile_name:
        profile_payload = profiles.get(profile_name)
        if isinstance(profile_payload, dict):
            model = str(profile_payload.get("model") or "").strip()
            if model:
                return model
    return str(payload.get("model") or "").strip()


def _display_default_model(cfg: dict, cli_name: str | None) -> str:
    resolved_cli = cli_runtime_service.normalize_cli_name(cli_name, cfg)
    default_model = str(
        cli_runtime_service.resolve_runtime_request(
            cfg,
            {"cli": resolved_cli},
            model_override=(cfg or {}).get("agent_model"),
        ).get("model")
        or "auto"
    )
    current_profile_model = _current_profile_model(cfg, resolved_cli)
    if resolved_cli == "codex" and default_model == "auto" and current_profile_model:
        return f"auto（当前 profile 实际落点 {current_profile_model}）"
    return default_model


def _extract_cli_runtime_json_request(user_prompt: str) -> tuple[str, dict | None]:
    raw = str(user_prompt or "")
    start = raw.find(CLI_RUNTIME_REQUEST_START)
    if start < 0:
        stripped = raw.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                payload = json.loads(stripped)
            except Exception:
                return raw, None
            if isinstance(payload, dict) and any(key in payload for key in ("cli", "model", "profile", "speed", "prompt", "config_overrides", "extra_args")):
                prompt = str(payload.get("prompt") or "").strip()
                return prompt, payload
        return raw, None
    end = raw.find(CLI_RUNTIME_REQUEST_END, start + len(CLI_RUNTIME_REQUEST_START))
    if end < 0:
        return raw, None
    json_text = raw[start + len(CLI_RUNTIME_REQUEST_START):end].strip()
    cleaned = (raw[:start] + raw[end + len(CLI_RUNTIME_REQUEST_END):]).strip()
    try:
        payload = json.loads(json_text)
    except Exception:
        return cleaned, None
    if not isinstance(payload, dict):
        return cleaned, None
    embedded_prompt = str(payload.get("prompt") or "").strip()
    return embedded_prompt or cleaned, payload


def _parse_runtime_control(user_prompt: str, cfg: dict) -> dict:
    text, json_runtime = _extract_cli_runtime_json_request(user_prompt)
    text = (text or "").strip()
    lower = text.lower()
    runtime_request = dict(json_runtime or {})

    if any(hint in text for hint in MODEL_LIST_HINTS):
        return {"kind": "list-models", "prompt": "", "model": "", "cli": runtime_request.get("cli") or ""}
    if any(hint in text for hint in CURRENT_MODEL_HINTS):
        return {"kind": "current-model", "prompt": "", "model": "", "cli": runtime_request.get("cli") or ""}
    if any(hint in text.lower() for hint in CURRENT_PROFILE_HINTS):
        return {"kind": "current-profile", "prompt": "", "model": "", "cli": runtime_request.get("cli") or ""}
    if any(hint in text.lower() for hint in CLI_LIST_HINTS):
        return {"kind": "list-clis", "prompt": "", "model": "", "cli": ""}
    if any(hint in text.lower() for hint in CURRENT_CLI_HINTS):
        return {"kind": "current-cli", "prompt": "", "model": "", "cli": runtime_request.get("cli") or ""}

    for pattern in CLI_DIRECTIVE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        runtime_request["cli"] = cli_runtime_service.normalize_cli_name(match.group("cli"), cfg)
        text = str(match.group("rest") or "").strip()
        lower = text.lower()
        break

    for pattern in PROFILE_DIRECTIVE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        runtime_request["cli"] = "codex"
        runtime_request["profile"] = cli_runtime_service.normalize_runtime_profile(match.group("profile"), cfg)
        text = str(match.group("rest") or "").strip()
        lower = text.lower()
        break

    for pattern in MODEL_DIRECTIVE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        raw_model = str(match.group("model") or "").strip()
        clean_prompt = str(match.group("rest") or "").strip()
        return {
            "kind": "run",
            "prompt": clean_prompt,
            "model": _resolve_runtime_model(raw_model, cfg),
            "raw_model": raw_model,
            "cli": runtime_request.get("cli") or "",
            "runtime": runtime_request,
        }

    if lower.startswith("model:") or lower.startswith("模型:") or lower.startswith("模型："):
        _, _, rest = text.partition(":")
        raw_model, _, clean_prompt = rest.strip().partition(" ")
        return {
            "kind": "run",
            "prompt": clean_prompt.strip(),
            "model": _resolve_runtime_model(raw_model, cfg),
            "raw_model": raw_model,
            "cli": runtime_request.get("cli") or "",
            "runtime": runtime_request,
        }

    return {
        "kind": "run",
        "prompt": text,
        "model": str(runtime_request.get("model") or "").strip(),
        "raw_model": str(runtime_request.get("model") or "").strip(),
        "cli": runtime_request.get("cli") or "",
        "runtime": runtime_request,
    }


def _resolve_turn_runtime(user_prompt: str, cfg: dict) -> dict:
    control = _parse_runtime_control(user_prompt, cfg)
    runtime_request = dict(control.get("runtime") or {})
    if control.get("cli"):
        runtime_request["cli"] = control.get("cli")
    requested_model = str(control.get("model") or runtime_request.get("model") or cfg.get("agent_model", "auto") or "auto")
    resolved_runtime_request = cli_runtime_service.resolve_runtime_request(cfg, runtime_request, model_override=requested_model)
    return {
        "control": control,
        "runtime_request": dict(resolved_runtime_request),
        "effective_model": str(resolved_runtime_request.get("model") or "auto"),
        "effective_cli": str(resolved_runtime_request.get("cli") or "cursor"),
    }


def describe_runtime_target(user_prompt: str, invocation_metadata: dict | None = None) -> dict:
    _ = invocation_metadata
    cfg = get_config()
    resolved = _resolve_turn_runtime(user_prompt, cfg)
    control = dict(resolved.get("control") or {})
    return {
        "kind": str(control.get("kind") or "run"),
        "prompt": str(control.get("prompt") or "").strip(),
        "cli": str(resolved.get("effective_cli") or "cursor"),
        "model": str(resolved.get("effective_model") or "auto"),
    }


def _list_available_models(workspace: str, timeout: int, cfg: dict | None = None, cli_name: str | None = None) -> tuple[list[str], str | None]:
    request = {"cli": cli_name} if cli_name else None
    return cli_runtime_service.list_available_models(workspace, timeout, cfg, request)


def _format_cli_list_reply(cfg: dict) -> str:
    active = cli_runtime_service.get_cli_runtime_settings(cfg).get("active", "cursor")
    lines = [f"当前 CLI：{active}", "可用 CLI："]
    lines.extend(f"- {name}" for name in cli_runtime_service.available_cli_modes(cfg))
    profiles = cli_runtime_service.available_runtime_profiles(cfg)
    if profiles:
        lines.append("")
        lines.append("可用 Codex profile：")
        lines.extend(f"- {name}" for name in profiles)
    lines.append("")
    lines.append("本轮切换示例：")
    lines.append('【cli_runtime_json】{"cli":"codex","profile":"aixj","model":"gpt-5.4"}【/cli_runtime_json】')
    return "\n".join(lines)


def _format_model_list_reply(cfg: dict, workspace: str, timeout: int, cli_name: str | None = None) -> str:
    resolved_cli = cli_runtime_service.normalize_cli_name(cli_name, cfg)
    models, error = _list_available_models(workspace, timeout, cfg, resolved_cli)
    default_model = _display_default_model(cfg, resolved_cli)
    default_profile = _default_runtime_profile(cfg, resolved_cli)
    current_cli = cli_runtime_service.get_cli_runtime_settings(cfg).get("active", "cursor")
    alias_lines = []
    for alias, target in sorted(_runtime_model_aliases(cfg).items()):
        if alias == target.lower():
            continue
        alias_lines.append(f"- {alias} -> {target}")
    if error:
        base = f"当前 CLI：{resolved_cli or current_cli}\n当前默认模型：{default_model}"
        if default_profile:
            base += f"\n当前默认 profile：{default_profile}"
        base += f"\n模型列表获取失败：{error}"
        if alias_lines:
            base += "\n\n已配置别名：\n" + "\n".join(alias_lines[:12])
        return base
    lines = [f"当前 CLI：{resolved_cli or current_cli}", f"当前默认模型：{default_model}"]
    if default_profile:
        lines.append(f"当前默认 profile：{default_profile}")
    lines.append(f"可用模型（{len(models)} 个）：")
    lines.extend(f"- {model}" for model in models)
    if alias_lines:
        lines.append("")
        lines.append("已配置别名：")
        lines.extend(alias_lines[:12])
    lines.append("")
    lines.append("本轮可直接这样写：用 gpt-5.4 回答：... 或 [模型=gpt-5.4] ...")
    if resolved_cli == "codex":
        lines.append("切到 AixJ：用 aixj 回答：...")
    return "\n".join(lines)


def _format_current_model_reply(cfg: dict) -> str:
    active_cli = cli_runtime_service.get_cli_runtime_settings(cfg).get("active", "cursor")
    default_model = _display_default_model(cfg, active_cli)
    default_profile = _default_runtime_profile(cfg, active_cli)
    aliases = _runtime_model_aliases(cfg)
    lines = [f"当前 CLI：{active_cli}", f"当前默认模型：{default_model}"]
    if default_profile:
        lines.append(f"当前默认 profile：{default_profile}")
    visible_aliases = [(alias, target) for alias, target in sorted(aliases.items()) if alias != target.lower()]
    if visible_aliases:
        lines.append("可用别名：")
        for alias, target in visible_aliases:
            lines.append(f"- {alias} -> {target}")
    profiles = cli_runtime_service.available_runtime_profiles(cfg)
    if profiles and active_cli == "codex":
        lines.append("可用 profile：")
        for profile in profiles:
            lines.append(f"- {profile}")
    lines.append("本轮指定模型示例：用 gpt-5.4 回答：你的问题")
    return "\n".join(lines)


def _format_current_profile_reply(cfg: dict) -> str:
    active_cli = cli_runtime_service.get_cli_runtime_settings(cfg).get("active", "cursor")
    default_profile = _default_runtime_profile(cfg, active_cli)
    lines = [f"当前 CLI：{active_cli}", f"当前默认 profile：{default_profile or '-'}"]
    profiles = cli_runtime_service.available_runtime_profiles(cfg)
    if profiles:
        lines.append("可用 profile：")
        lines.extend(f"- {profile}" for profile in profiles)
    if active_cli == "codex":
        lines.append("本轮切到 AixJ：用 aixj 回答：你的问题")
        lines.append("本轮切回 OpenAI：用 openai 回答：你的问题")
    return "\n".join(lines)


def _format_current_cli_reply(cfg: dict) -> str:
    runtime = cli_runtime_service.get_cli_runtime_settings(cfg)
    active = runtime.get("active", "cursor")
    lines = [f"当前 CLI：{active}"]
    default_model = _display_default_model(cfg, active)
    if default_model:
        lines.append(f"默认模型：{default_model}")
    default_profile = _default_runtime_profile(cfg, active)
    if default_profile:
        lines.append(f"默认 profile：{default_profile}")
    lines.append("可用 CLI：")
    lines.extend(f"- {name}" for name in cli_runtime_service.available_cli_modes(cfg))
    profiles = cli_runtime_service.available_runtime_profiles(cfg)
    if profiles and active == "codex":
        lines.append("可用 Codex profile：")
        lines.extend(f"- {name}" for name in profiles)
    lines.append('本轮切换示例：【cli_runtime_json】{"cli":"codex","profile":"aixj","model":"gpt-5.4"}【/cli_runtime_json】')
    return "\n".join(lines)


def _stream_preview(text: str, limit: int = 120) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


def _section_titles(sections: list[str]) -> list[str]:
    titles = []
    for section in sections:
        first_line = ((section or "").strip().splitlines() or [""])[0].strip()
        if first_line.startswith("##"):
            titles.append(first_line)
        elif first_line:
            titles.append(first_line[:60])
        else:
            titles.append("(empty)")
    return titles


def _increment_from_stream(emitted: str, incoming: str) -> str:
    if not incoming:
        return ""
    if not emitted:
        return incoming
    if incoming.startswith(emitted):
        return incoming[len(emitted):]
    if emitted.startswith(incoming) or incoming in emitted or emitted.endswith(incoming):
        return ""
    max_overlap = min(len(emitted), len(incoming))
    for k in range(max_overlap, 0, -1):
        if emitted[-k:] == incoming[:k]:
            return incoming[k:]
    return incoming


def _plan_stream_increment(emitted: str, incoming: str) -> tuple[str, str]:
    delta = _increment_from_stream(emitted, incoming)
    if not delta:
        return "", emitted
    if incoming.startswith(emitted):
        return delta, incoming
    return delta, emitted + delta


def _longest_common_prefix_len(a: str, b: str) -> int:
    limit = min(len(a), len(b))
    idx = 0
    while idx < limit and a[idx] == b[idx]:
        idx += 1
    return idx


class _StreamAssembler:
    """流式快照拼接器：优先保持单调增长，回退重写时切到最新快照。"""

    def __init__(self, tail_rewrite_tolerance: int = 24):
        self._emitted = ""
        self._latest_snapshot = ""
        self._tail_rewrite_tolerance = max(4, int(tail_rewrite_tolerance))
        self.unstable_stream = False

    def ingest(self, incoming: str) -> str:
        text = str(incoming or "")
        if not text:
            return ""
        self._latest_snapshot = text
        if not self._emitted:
            self._emitted = text
            return text
        if text == self._emitted:
            return ""

        lcp = _longest_common_prefix_len(self._emitted, text)
        if lcp == len(self._emitted):
            delta = text[len(self._emitted):]
            self._emitted = text
            return delta

        rollback = len(self._emitted) - lcp
        if rollback <= self._tail_rewrite_tolerance:
            self._emitted = text
            return ""

        self.unstable_stream = True
        self._emitted = text
        return ""

    def final_text(self) -> str:
        return self._latest_snapshot or self._emitted


def _extract_ready_markdown_sections(text: str) -> tuple[list[str], str]:
    rest = text or ""
    matches = list(MARKDOWN_H2_RE.finditer(rest))
    if len(matches) < 2:
        return [], rest

    ready_sections: list[str] = []
    for idx in range(len(matches) - 1):
        start = matches[idx].start()
        end = matches[idx + 1].start()
        section = rest[start:end].strip()
        if section:
            ready_sections.append(section)
    tail = rest[matches[-1].start():]
    return ready_sections, tail


def _collect_unsent_markdown_sections(text: str, sent_count: int) -> tuple[list[str], int, str]:
    ready_sections, tail = _extract_ready_markdown_sections(text)
    if sent_count >= len(ready_sections):
        return [], sent_count, tail
    new_sections = ready_sections[sent_count:]
    return new_sections, len(ready_sections), tail


def _build_turn_runtime_request(workspace: str, model: str) -> dict:
    cfg = get_config()
    runtime_request = dict(TURN_STATE.get("turn_cli_request", {}) or {})
    session_scope_id = str(TURN_STATE.get("turn_session_scope_id") or "").strip()
    preferred_cli = str(runtime_request.get("cli") or "").strip()
    session_override_getter = getattr(_memory_provider(), "get_runtime_request_override_for_session", None)
    if callable(session_override_getter):
        runtime_request.update(
            session_override_getter(
                workspace=workspace,
                session_scope_id=session_scope_id,
                preferred_cli=preferred_cli,
            )
            or {}
        )
    else:
        runtime_request.update(_memory_provider().get_runtime_request_override())
    turn_invocation_metadata = dict(TURN_STATE.get("turn_invocation_metadata", {}) or {})
    for key in ("request_id", "session_id", "actor_id", "message_id", "channel"):
        value = str(turn_invocation_metadata.get(key) or "").strip()
        if value:
            runtime_request[key] = value
    if session_scope_id:
        runtime_request["session_scope_id"] = session_scope_id
    if model:
        runtime_request["model"] = model
    return cli_runtime_service.prepare_vendor_session_runtime_request(cfg, runtime_request)


def _run_agent_via_cli(prompt: str, workspace: str, timeout: int, model: str):
    cfg = get_config()
    runtime_request = _build_turn_runtime_request(workspace, model)
    return cli_runtime_service.run_prompt_receipt(prompt, workspace, timeout, cfg, runtime_request, stream=False)


def _run_agent_streaming(
    prompt: str,
    workspace: str,
    timeout: int,
    model: str,
    on_segment: Callable[[str], None] | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> object:
    cfg = get_config()
    runtime_request = _build_turn_runtime_request(workspace, model)
    return cli_runtime_service.run_prompt_receipt(
        prompt,
        workspace,
        timeout,
        cfg,
        runtime_request,
        stream=True,
        on_segment=on_segment,
        on_event=on_event,
    )


def _build_chat_memory_stack() -> tuple[object, ButlerChatMemoryProvider]:
    summary_runtime = ChatSummaryPipelineRuntime(config_provider=get_config)
    manager = ChatLightMemoryState(
        config_provider=get_config,
        window_summarizer=summary_runtime.summarize_window,
        long_memory_governor=summary_runtime.govern_long_term_summary,
    )
    turn_store = ChatRecentTurnStore(config_provider=get_config)
    provider = ButlerChatMemoryProvider(
        manager,
        background_services=ChatLightBackgroundServices(
            state=manager,
            config_provider=get_config,
        ),
        runtime_request_provider=ChatRuntimeRequestOverrideRuntime(
            state_source=manager,
        ),
        turn_lifecycle=turn_store,
        prompt_assembler=ChatRecentPromptAssembler(turn_store=turn_store),
        reply_persistence=ChatReplyPersistenceRuntime(
            config_provider=get_config,
            fallback_writer=manager.write_recent_completion_fallback,
            finalize_reply=manager.finalize_recent_memory,
        ),
    )
    return manager, provider


TURN_STATE = ThreadLocalStateStore()
TURN_CONTEXT = TURN_STATE.raw_context
_MEMORY_STACK: tuple[object, ButlerChatMemoryProvider] | None = None
_PROMPT_PROVIDER: ButlerChatPromptProvider | None = None
_REQUEST_INTAKE_SERVICE: RequestIntakeService | None = None
_CHAT_MAINLINE_SERVICE: ChatMainlineService | None = None
_CHAT_RUNTIME_SERVICE: ChatRuntimeService | None = None


def _memory_stack() -> tuple[object, ButlerChatMemoryProvider]:
    global _MEMORY_STACK
    if _MEMORY_STACK is None:
        _MEMORY_STACK = _build_chat_memory_stack()
    return _MEMORY_STACK


def _prompt_provider() -> ButlerChatPromptProvider:
    global _PROMPT_PROVIDER
    if _PROMPT_PROVIDER is None:
        _PROMPT_PROVIDER = ButlerChatPromptProvider()
    return _PROMPT_PROVIDER


def _request_intake_service() -> RequestIntakeService:
    global _REQUEST_INTAKE_SERVICE
    if _REQUEST_INTAKE_SERVICE is None:
        _REQUEST_INTAKE_SERVICE = RequestIntakeService()
    return _REQUEST_INTAKE_SERVICE


def _chat_mainline_service() -> ChatMainlineService:
    global _CHAT_MAINLINE_SERVICE
    if _CHAT_MAINLINE_SERVICE is None:
        _CHAT_MAINLINE_SERVICE = ChatMainlineService()
    return _CHAT_MAINLINE_SERVICE


def _chat_runtime_service() -> ChatRuntimeService:
    global _CHAT_RUNTIME_SERVICE
    if _CHAT_RUNTIME_SERVICE is None:
        memory, memory_provider = _memory_stack()
        prompt_provider = _prompt_provider()
        _CHAT_RUNTIME_SERVICE = ChatRuntimeService(
            memory_provider=memory_provider,
            prompt_provider=prompt_provider,
            memory_manager=memory,
            request_intake_service=_request_intake_service(),
            build_prompt_fn=lambda user_prompt, image_paths=None, **kwargs: prompt_provider.build_prompt(
                user_prompt,
                workspace=str(get_config().get("workspace_root") or "."),
                image_paths=image_paths,
                raw_user_prompt=kwargs.get("raw_user_prompt"),
                request_intake_prompt=kwargs.get("request_intake_prompt"),
                metadata={
                    "skills_prompt": kwargs.get("skills_prompt"),
                    "skill_exposure": kwargs.get("skill_exposure"),
                    "skill_collection_id": kwargs.get("skill_collection_id"),
                    "agent_capabilities_prompt": kwargs.get("agent_capabilities_prompt"),
                    "prompt_purity": kwargs.get("prompt_purity"),
                },
            ),
            render_skills_prompt_fn=prompt_provider.render_skills_prompt,
            render_agent_capabilities_prompt_fn=prompt_provider.render_agent_capabilities_prompt,
            run_agent_via_cli_fn=_run_agent_via_cli,
            run_agent_streaming_fn=_run_agent_streaming,
            parse_decide_fn=parse_decide_from_reply,
        )
    return _CHAT_RUNTIME_SERVICE


def _memory_provider() -> ButlerChatMemoryProvider:
    return _memory_stack()[1]


def _clear_turn_chat_delivery_state() -> None:
    TURN_STATE.delete("turn_output_bundle", "turn_delivery_session", "turn_delivery_plan")


def _get_turn_output_bundle():
    return TURN_STATE.get("turn_output_bundle")


def _get_turn_raw_reply() -> str:
    return str(TURN_STATE.get("turn_raw_reply") or "")


def _get_turn_delivery_session():
    return TURN_STATE.get("turn_delivery_session")


def _get_turn_delivery_plan():
    return TURN_STATE.get("turn_delivery_plan")


def _execute_chat_turn_runtime(
    runtime_request,
    *,
    effective_prompt: str,
    original_user_prompt: str,
    image_paths: list[str] | None,
    workspace: str,
    timeout: int,
    effective_model: str,
    max_len: int,
    stream_callback: Callable[[str], None] | None,
):
    TURN_STATE.set(turn_session_scope_id=resolve_session_scope_id_from_invocation(runtime_request.invocation))
    execution = _chat_runtime_service().execute(
        runtime_request,
        effective_prompt=effective_prompt,
        image_paths=image_paths,
        workspace=workspace,
        timeout=timeout,
        effective_model=effective_model,
        max_len=int(max_len),
        stream_callback=stream_callback,
    )
    remember_runtime_session = getattr(_memory_provider(), "remember_runtime_session", None)
    if callable(remember_runtime_session):
        remember_runtime_session(
            workspace=workspace,
            session_scope_id=str(execution.metadata.get("session_scope_id") or TURN_STATE.get("turn_session_scope_id") or "").strip(),
            runtime_request=dict(execution.metadata.get("runtime_request") or {}),
            execution_metadata=dict(execution.metadata.get("execution_metadata") or {}),
        )
    TURN_STATE.set(
        pending_memory_id=execution.pending_memory_id,
        turn_model=effective_model,
        turn_user_prompt=str(original_user_prompt or effective_prompt or "").strip(),
        turn_raw_reply=str(getattr(execution, "raw_reply_text", "") or ""),
        turn_process_events=[dict(item) for item in getattr(execution, "process_events", []) if isinstance(item, dict)],
        turn_session_scope_id=str(execution.metadata.get("session_scope_id") or "").strip(),
        turn_execution_metadata=dict(execution.metadata.get("execution_metadata") or {}),
    )
    return execution


def run_agent(
    user_prompt: str,
    stream_output: bool = False,
    stream_callback: Callable[[str], None] | None = None,
    image_paths: list[str] | None = None,
    invocation_metadata: dict | None = None,
) -> str:
    _clear_turn_chat_delivery_state()
    cfg = get_config()
    workspace = cfg.get("workspace_root", "")
    timeout = cfg.get("agent_timeout", 300)
    resolved_turn_runtime = _resolve_turn_runtime(user_prompt, cfg)
    control = dict(resolved_turn_runtime.get("control") or {})
    if control.get("kind") == "list-models":
        return _format_model_list_reply(cfg, workspace, timeout, control.get("cli"))
    if control.get("kind") == "current-model":
        return _format_current_model_reply(cfg)
    if control.get("kind") == "current-profile":
        return _format_current_profile_reply(cfg)
    if control.get("kind") == "list-clis":
        return _format_cli_list_reply(cfg)
    if control.get("kind") == "current-cli":
        return _format_current_cli_reply(cfg)

    runtime_request = dict(resolved_turn_runtime.get("runtime_request") or {})
    effective_model = str(resolved_turn_runtime.get("effective_model") or "auto")
    effective_cli = str(resolved_turn_runtime.get("effective_cli") or "cursor")
    effective_profile = str(runtime_request.get("profile") or "").strip()
    max_len = cfg.get("max_reply_len", 4000)
    use_stream = bool(stream_callback) or stream_output
    effective_prompt = str(control.get("prompt") or "").strip()
    if not effective_prompt:
        profile_hint = f"，profile 为 {effective_profile}" if effective_profile else ""
        example_profile = f',"profile":"{effective_profile}"' if effective_profile else ""
        return (
            f"已识别本轮 CLI 为 {effective_cli}{profile_hint}，模型为 {effective_model}。"
            f"请把问题和指令放在同一条消息里，例如："
            f'【cli_runtime_json】{{"cli":"{effective_cli}"{example_profile},"model":"{effective_model}"}}【/cli_runtime_json】你的问题'
        )

    TURN_STATE.set(turn_model=effective_model, turn_cli_request=runtime_request)
    TURN_STATE.set(turn_invocation_metadata=dict(invocation_metadata or {}))
    result = _chat_mainline_service().handle_prompt(
        effective_prompt,
        invocation_metadata={
            "workspace": workspace,
            "channel": "local",
            "runtime_cli": effective_cli,
            **dict(invocation_metadata or {}),
        },
        talk_executor=lambda talk_runtime_request: _execute_chat_turn_runtime(
            talk_runtime_request,
            effective_prompt=str(talk_runtime_request.invocation.user_text or ""),
            original_user_prompt=str(
                (talk_runtime_request.invocation.metadata or {}).get("original_user_prompt")
                or effective_prompt
                or talk_runtime_request.invocation.user_text
                or ""
            ).strip(),
            image_paths=image_paths,
            workspace=workspace,
            timeout=timeout,
            effective_model=effective_model,
            max_len=int(max_len),
            stream_callback=stream_callback if use_stream else None,
        ),
    )
    TURN_STATE.set(
        turn_output_bundle=result.output_bundle,
        turn_delivery_session=result.runtime_request.delivery_session,
        turn_delivery_plan=result.delivery_plan,
    )
    return result.text


run_agent.get_turn_output_bundle = _get_turn_output_bundle
run_agent.get_turn_raw_reply = _get_turn_raw_reply
run_agent.get_turn_delivery_session = _get_turn_delivery_session
run_agent.get_turn_delivery_plan = _get_turn_delivery_plan
run_agent.describe_runtime_target = describe_runtime_target
run_agent.cancel_active_execution = lambda **kwargs: {
    **cli_runtime_service.cancel_active_runs(
        request_id=str(kwargs.get("request_id") or "").strip(),
        session_id=str(kwargs.get("session_id") or "").strip(),
        actor_id=str(kwargs.get("actor_id") or "").strip(),
        message_id=str(kwargs.get("message_id") or "").strip(),
    ),
    "supported": True,
}


def _backfill_recent_feishu_messages(
    messages: list[dict],
    *,
    session_scope_id: str,
    chat_id: str = "",
) -> int:
    del chat_id
    if not messages:
        return 0
    cfg = get_config()
    workspace = str(cfg.get("workspace_root") or ".")
    memory, _ = _memory_stack()
    backfill_fn = getattr(memory, "backfill_recent_turns", None)
    if not callable(backfill_fn):
        return 0
    return int(
        backfill_fn(
            list(messages),
            workspace,
            session_scope_id=session_scope_id,
        )
        or 0
    )


run_agent.backfill_recent_feishu_messages = _backfill_recent_feishu_messages

def _after_reply_persist_memory_async(user_prompt: str, assistant_reply: str) -> None:
    pending_memory_id = TURN_STATE.get("pending_memory_id")
    turn_model = TURN_STATE.get("turn_model")
    turn_user_prompt = TURN_STATE.get("turn_user_prompt", user_prompt)
    turn_raw_reply = str(TURN_STATE.get("turn_raw_reply") or assistant_reply or "")
    turn_process_events = [dict(item) for item in (TURN_STATE.get("turn_process_events") or []) if isinstance(item, dict)]
    turn_session_scope_id = str(TURN_STATE.get("turn_session_scope_id") or "").strip()
    _memory_provider().persist_reply_async(
        turn_user_prompt,
        assistant_reply,
        raw_reply=turn_raw_reply,
        memory_id=pending_memory_id,
        model_override=turn_model,
        suppress_task_merge=False,
        session_scope_id=turn_session_scope_id,
        process_events=turn_process_events,
    )
    TURN_STATE.delete(
        "pending_memory_id",
        "turn_model",
        "turn_cli_request",
        "turn_invocation_metadata",
        "turn_raw_reply",
        "turn_process_events",
        "turn_session_scope_id",
        "turn_user_prompt",
        "turn_output_bundle",
        "turn_delivery_session",
        "turn_delivery_plan",
    )


def _on_bot_started() -> None:
    _memory_provider().start_background_services()


def __getattr__(name: str):
    if name == "PROMPT_PROVIDER":
        return _prompt_provider()
    if name == "MEMORY_PROVIDER":
        return _memory_provider()
    if name == "REQUEST_INTAKE_SERVICE":
        return _request_intake_service()
    if name == "CHAT_MAINLINE_SERVICE":
        return _chat_mainline_service()
    if name in {"CHAT_RUNTIME_SERVICE", "TALK_RUNTIME_SERVICE"}:
        return _chat_runtime_service()
    if name == "TALK_MAINLINE_SERVICE":
        return _chat_mainline_service()
    if name == "MEMORY":
        return _memory_stack()[0]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main():
    from butler_main.chat.app import main as chat_main

    return chat_main()


if __name__ == "__main__":
    sys.exit(main())







