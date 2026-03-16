# -*- coding: utf-8 -*-
"""
飞书 管家bot（butler_bot）

组合 agent（消息层）与 memory_manager（记忆层）：
- 消息：接收飞书命令、回复、分段展示
- 记忆：recent 注入、回复后持久化、启动/定时维护

使用:
  飞书长连接: python butler_bot.py --config ../configs/butler_bot.json
  本地测试: python butler_bot.py --prompt "你是谁"
  本地测试（流式）: python butler_bot.py --prompt "你是谁" (默认)
  本地测试（一次性）: python butler_bot.py --prompt "你是谁" --no-stream
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import textwrap
from typing import Callable

from agent import (
    CONFIG,
    build_feishu_agent_prompt,
    get_config,
    load_config,
    render_available_agent_capabilities_prompt,
    run_feishu_bot,
)
from execution.agent_team_executor import AgentTeamExecutor
from utils.markdown_safety import safe_truncate_markdown, sanitize_markdown_structure
from memory_manager import MemoryManager
from services.request_intake_service import RequestIntakeService
from registry.skill_registry import render_skill_catalog_for_prompt
from runtime import cli_runtime as cli_runtime_service
from runtime.cursor_runtime_support import resolve_cursor_cli_cmd_path


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
AGENT_RUNTIME_REQUEST_START = "【agent_runtime_request_json】"
AGENT_RUNTIME_REQUEST_END = "【/agent_runtime_request_json】"
CLI_RUNTIME_REQUEST_START = "【cli_runtime_json】"
CLI_RUNTIME_REQUEST_END = "【/cli_runtime_json】"
CLI_DIRECTIVE_PATTERNS = [
    re.compile(
        r"^\s*(?:请)?(?:切换到|改用|使用|换成|换到|本轮用|这次用|用)\s*(?P<cli>cursor(?:-cli)?|codex(?:-cli)?)\s*(?:模式|命令行|cli)?[：:,，\s]*(?P<rest>[\s\S]*)$",
        re.IGNORECASE,
    ),
]
SELF_MIND_CHAT_PATTERNS = [
    re.compile(r"^\s*(?:@?self[-_\s]?mind|selfmind|sm|小我|内心)\s*[:：,，]\s*(?P<rest>[\s\S]*)$", re.IGNORECASE),
    re.compile(r"^\s*(?:跟|和)?\s*(?:@?self[-_\s]?mind|selfmind|小我|内心)\s*(?:聊聊|说|讲|对话)?\s*[:：,，]\s*(?P<rest>[\s\S]*)$", re.IGNORECASE),
]


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


def _extract_self_mind_chat_request(user_prompt: str) -> tuple[str, bool]:
    raw = str(user_prompt or "").strip()
    if not raw:
        return "", False
    for pattern in SELF_MIND_CHAT_PATTERNS:
        match = pattern.match(raw)
        if match:
            return str(match.group("rest") or "").strip(), True
    return raw, False


def _list_available_models(workspace: str, timeout: int, cfg: dict | None = None, cli_name: str | None = None) -> tuple[list[str], str | None]:
    request = {"cli": cli_name} if cli_name else None
    return cli_runtime_service.list_available_models(workspace, timeout, cfg, request)


def _format_cli_list_reply(cfg: dict) -> str:
    active = cli_runtime_service.get_cli_runtime_settings(cfg).get("active", "cursor")
    lines = [f"当前 CLI：{active}", "可用 CLI："]
    lines.extend(f"- {name}" for name in cli_runtime_service.available_cli_modes(cfg))
    lines.append("")
    lines.append("本轮切换示例：")
    lines.append('【cli_runtime_json】{"cli":"codex","model":"gpt-5"}【/cli_runtime_json】')
    return "\n".join(lines)


def _format_model_list_reply(cfg: dict, workspace: str, timeout: int, cli_name: str | None = None) -> str:
    resolved_cli = cli_runtime_service.normalize_cli_name(cli_name, cfg)
    models, error = _list_available_models(workspace, timeout, cfg, resolved_cli)
    default_model = str(cli_runtime_service.resolve_runtime_request(cfg, {"cli": resolved_cli}, model_override=(cfg or {}).get("agent_model")).get("model") or "auto")
    current_cli = cli_runtime_service.get_cli_runtime_settings(cfg).get("active", "cursor")
    alias_lines = []
    for alias, target in sorted(_runtime_model_aliases(cfg).items()):
        if alias == target.lower():
            continue
        alias_lines.append(f"- {alias} -> {target}")
    if error:
        base = f"当前 CLI：{resolved_cli or current_cli}\n当前默认模型：{default_model}\n模型列表获取失败：{error}"
        if alias_lines:
            base += "\n\n已配置别名：\n" + "\n".join(alias_lines[:12])
        return base
    lines = [f"当前 CLI：{resolved_cli or current_cli}", f"当前默认模型：{default_model}", f"可用模型（{len(models)} 个）："]
    lines.extend(f"- {model}" for model in models)
    if alias_lines:
        lines.append("")
        lines.append("已配置别名：")
        lines.extend(alias_lines[:12])
    lines.append("")
    lines.append("本轮可直接这样写：用 gpt-5 回答：... 或 [模型=sonnet-4] ...")
    return "\n".join(lines)


def _format_current_model_reply(cfg: dict) -> str:
    active_cli = cli_runtime_service.get_cli_runtime_settings(cfg).get("active", "cursor")
    default_model = str(cli_runtime_service.resolve_runtime_request(cfg, {"cli": active_cli}, model_override=(cfg or {}).get("agent_model")).get("model") or "auto")
    aliases = _runtime_model_aliases(cfg)
    lines = [f"当前 CLI：{active_cli}", f"当前默认模型：{default_model}"]
    visible_aliases = [(alias, target) for alias, target in sorted(aliases.items()) if alias != target.lower()]
    if visible_aliases:
        lines.append("可用别名：")
        for alias, target in visible_aliases:
            lines.append(f"- {alias} -> {target}")
    lines.append("本轮指定模型示例：用 gpt-5 回答：你的问题")
    return "\n".join(lines)


def _format_current_cli_reply(cfg: dict) -> str:
    runtime = cli_runtime_service.get_cli_runtime_settings(cfg)
    active = runtime.get("active", "cursor")
    lines = [f"当前 CLI：{active}"]
    defaults = runtime.get("defaults") or {}
    default_model = cli_runtime_service.resolve_runtime_request(cfg, {"cli": active}, model_override=defaults.get("model") or (cfg or {}).get("agent_model")).get("model")
    if default_model:
        lines.append(f"默认模型：{default_model}")
    lines.append("可用 CLI：")
    lines.extend(f"- {name}" for name in cli_runtime_service.available_cli_modes(cfg))
    lines.append('本轮切换示例：【cli_runtime_json】{"cli":"codex","model":"gpt-5"}【/cli_runtime_json】')
    return "\n".join(lines)


def _render_available_skills_prompt(workspace: str) -> str:
    return render_skill_catalog_for_prompt(workspace)


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


def _run_agent_via_cli(prompt: str, workspace: str, timeout: int, model: str) -> tuple[str, bool]:
    cfg = get_config()
    runtime_request = dict(getattr(TURN_CONTEXT, "turn_cli_request", {}) or {})
    runtime_request.update(MEMORY.get_runtime_request_override())
    if model:
        runtime_request["model"] = model
    return cli_runtime_service.run_prompt(prompt, workspace, timeout, cfg, runtime_request, stream=False)


def _run_agent_streaming(
    prompt: str,
    workspace: str,
    timeout: int,
    model: str,
    on_segment: Callable[[str], None] | None = None,
) -> tuple[str, bool]:
    cfg = get_config()
    runtime_request = dict(getattr(TURN_CONTEXT, "turn_cli_request", {}) or {})
    runtime_request.update(MEMORY.get_runtime_request_override())
    if model:
        runtime_request["model"] = model
    return cli_runtime_service.run_prompt(prompt, workspace, timeout, cfg, runtime_request, stream=True, on_segment=on_segment)


MEMORY = MemoryManager(config_provider=get_config, run_model_fn=_run_agent_via_cli)
AGENT_RUNTIME_EXECUTOR = AgentTeamExecutor(_run_agent_via_cli)
TURN_CONTEXT = threading.local()
REQUEST_INTAKE_SERVICE = RequestIntakeService()


def _render_available_agent_capabilities_prompt(workspace: str) -> str:
    return render_available_agent_capabilities_prompt(workspace, max_chars=2400)


def _extract_agent_runtime_request(text: str) -> tuple[str, dict | None]:
    raw = str(text or "")
    start = raw.find(AGENT_RUNTIME_REQUEST_START)
    if start < 0:
        return raw.strip(), None
    end = raw.find(AGENT_RUNTIME_REQUEST_END, start + len(AGENT_RUNTIME_REQUEST_START))
    if end < 0:
        return raw.strip(), None
    json_text = raw[start + len(AGENT_RUNTIME_REQUEST_START):end].strip()
    cleaned = (raw[:start] + raw[end + len(AGENT_RUNTIME_REQUEST_END):]).strip()
    try:
        payload = json.loads(json_text)
    except Exception:
        return cleaned, None
    if not isinstance(payload, dict):
        return cleaned, None
    return cleaned, payload


def _execute_agent_runtime_request(
    request: dict,
    *,
    workspace: str,
    timeout: int,
    model: str,
) -> dict:
    return AGENT_RUNTIME_EXECUTOR.execute_request(request, workspace, timeout, model)


def _build_runtime_followup_prompt(
    original_user_prompt: str,
    assistant_preface: str,
    runtime_result: dict,
    *,
    workspace: str,
) -> str:
    runtime_output = str(runtime_result.get("output") or "").strip() or "(空)"
    summary = textwrap.dedent(
        f"""
        你刚刚发起了一次内部协作请求，现在协作结果已经返回。
        这次结果只能直接汇总给用户，禁止再次输出 `agent_runtime_request_json`。

        原始用户请求：
        {original_user_prompt}

        你先前准备给用户的前置回应：
        {assistant_preface or '(空)'}

        内部协作结果：
        {runtime_output}

        请直接输出最终用户可读版本：
        - 先给结论
        - 再给关键信息
        - 如有风险或未解项，明确写出
        """
    ).strip()
    return build_feishu_agent_prompt(
        summary,
        skills_prompt=_render_available_skills_prompt(workspace),
        agent_capabilities_prompt=_render_available_agent_capabilities_prompt(workspace),
        raw_user_prompt=original_user_prompt,
    )


def run_agent(
    user_prompt: str,
    stream_output: bool = False,
    stream_callback: Callable[[str], None] | None = None,
    image_paths: list[str] | None = None,
) -> str:
    cfg = get_config()
    workspace = cfg.get("workspace_root", "")
    timeout = cfg.get("agent_timeout", 300)
    control = _parse_runtime_control(user_prompt, cfg)
    if control.get("kind") == "list-models":
        return _format_model_list_reply(cfg, workspace, timeout, control.get("cli"))
    if control.get("kind") == "current-model":
        return _format_current_model_reply(cfg)
    if control.get("kind") == "list-clis":
        return _format_cli_list_reply(cfg)
    if control.get("kind") == "current-cli":
        return _format_current_cli_reply(cfg)

    runtime_request = dict(control.get("runtime") or {})
    if control.get("cli"):
        runtime_request["cli"] = control.get("cli")
    requested_model = str(control.get("model") or runtime_request.get("model") or cfg.get("agent_model", "auto") or "auto")
    resolved_runtime_request = cli_runtime_service.resolve_runtime_request(cfg, runtime_request, model_override=requested_model)
    runtime_request = dict(resolved_runtime_request)
    effective_model = str(resolved_runtime_request.get("model") or "auto")
    effective_cli = str(resolved_runtime_request.get("cli") or "cursor")
    max_len = cfg.get("max_reply_len", 4000)
    use_stream = bool(stream_callback) or stream_output
    effective_prompt = str(control.get("prompt") or "").strip()
    self_mind_prompt, self_mind_chat = _extract_self_mind_chat_request(effective_prompt)
    if not effective_prompt:
        return (
            f"已识别本轮 CLI 为 {effective_cli}，模型为 {effective_model}。"
            f"请把问题和指令放在同一条消息里，例如："
            f'【cli_runtime_json】{{"cli":"{effective_cli}","model":"{effective_model}"}}【/cli_runtime_json】你的问题'
        )

    upgrade_decision = MEMORY.inspect_pending_upgrade_request_prompt(workspace, effective_prompt)
    if upgrade_decision:
        decision = str(upgrade_decision.get("decision") or "").strip()
        if decision == "approve-restart":
            approved_request = dict(upgrade_decision.get("request") or {})
            TURN_CONTEXT.post_reply_action = lambda req=approved_request, ws=workspace: MEMORY.execute_approved_upgrade_request(ws, req)
            return str(upgrade_decision.get("reply") or "已收到批准，聊天主进程将执行重启。")
        if decision == "approve-execute":
            effective_prompt = str(upgrade_decision.get("execute_prompt") or effective_prompt).strip() or effective_prompt
        else:
            return str(upgrade_decision.get("reply") or "已处理该升级申请。")

    runtime_control_result = MEMORY.handle_runtime_control_command(workspace, effective_prompt)
    if runtime_control_result and runtime_control_result.get("handled"):
        pending_memory_id, _ = MEMORY.begin_pending_turn(effective_prompt, workspace)
        TURN_CONTEXT.pending_memory_id = pending_memory_id
        TURN_CONTEXT.turn_model = effective_model
        TURN_CONTEXT.turn_cli_request = runtime_request
        TURN_CONTEXT.turn_user_prompt = effective_prompt
        TURN_CONTEXT.turn_suppress_task_merge = bool(runtime_control_result.get("suppress_task_merge"))
        return str(runtime_control_result.get("reply") or "已处理后台控制指令。")

    explicit_task_result = MEMORY.handle_explicit_heartbeat_task_command(workspace, effective_prompt)
    if explicit_task_result and explicit_task_result.get("handled"):
        pending_memory_id, _ = MEMORY.begin_pending_turn(effective_prompt, workspace)
        TURN_CONTEXT.pending_memory_id = pending_memory_id
        TURN_CONTEXT.turn_model = effective_model
        TURN_CONTEXT.turn_cli_request = runtime_request
        TURN_CONTEXT.turn_user_prompt = effective_prompt
        TURN_CONTEXT.turn_suppress_task_merge = True
        return str(explicit_task_result.get("reply") or "已处理心跳任务指令。")

    if self_mind_chat:
        effective_self_mind_prompt = self_mind_prompt or "你现在在想什么？"
        pending_memory_id, previous_pending = MEMORY.begin_pending_turn(f"[self_mind_chat] {effective_self_mind_prompt}", workspace)
        TURN_CONTEXT.pending_memory_id = pending_memory_id
        TURN_CONTEXT.turn_model = effective_model
        TURN_CONTEXT.turn_cli_request = runtime_request
        TURN_CONTEXT.turn_user_prompt = f"[self_mind_chat] {effective_self_mind_prompt}"
        del previous_pending
        prompt = MEMORY._build_self_mind_chat_prompt(workspace, effective_self_mind_prompt)
        if use_stream:
            out, ok = _run_agent_streaming(prompt, workspace, timeout, effective_model, on_segment=stream_callback)
        else:
            out, ok = _run_agent_via_cli(prompt, workspace, timeout, effective_model)
        final_text = sanitize_markdown_structure(out if ok and out else (out or "self_mind 这轮没组织出有效回复。"))
        return safe_truncate_markdown(final_text, int(max_len))

    intake_decision = REQUEST_INTAKE_SERVICE.classify(effective_prompt)
    recent_mode = "content_share" if str((intake_decision or {}).get("mode") or "").strip() == "content_share" else "default"

    pending_memory_id, previous_pending = MEMORY.begin_pending_turn(effective_prompt, workspace)
    TURN_CONTEXT.pending_memory_id = pending_memory_id
    TURN_CONTEXT.turn_model = effective_model
    TURN_CONTEXT.turn_cli_request = runtime_request
    TURN_CONTEXT.turn_user_prompt = effective_prompt
    user_prompt_with_recent = MEMORY.prepare_user_prompt_with_recent(
        effective_prompt,
        exclude_memory_id=pending_memory_id,
        previous_pending=previous_pending,
        recent_mode=recent_mode,
    )
    print(
        f"[agent-run] pending_memory_id={pending_memory_id} | model={effective_model} | user={re.sub(r'\s+', ' ', (effective_prompt or '').strip())[:100]}"
        + (f" | previous_pending={str((previous_pending or {}).get('topic') or '')[:80]}" if previous_pending else ""),
        flush=True,
    )
    print(f"[agent-prompt] {re.sub(r'\s+', ' ', user_prompt_with_recent)[:200]}", flush=True)
    skills_prompt = "" if recent_mode == "content_share" else _render_available_skills_prompt(workspace)
    capabilities_prompt = "" if recent_mode == "content_share" else _render_available_agent_capabilities_prompt(workspace)
    prompt = build_feishu_agent_prompt(
        user_prompt_with_recent,
        image_paths,
        skills_prompt=skills_prompt,
        agent_capabilities_prompt=capabilities_prompt,
        raw_user_prompt=effective_prompt,
        request_intake_prompt=REQUEST_INTAKE_SERVICE.build_frontdesk_prompt_block(intake_decision),
    )
    print(
        f"[agent-prompt-stats] user_len={len(effective_prompt)} | recent_len={len(user_prompt_with_recent)} | skills_len={len(skills_prompt)} | capabilities_len={len(capabilities_prompt)} | full_len={len(prompt)}",
        flush=True,
    )
    # 根据是否提供 stream_callback 或 stream_output 选择流式或一次性调用 Cursor CLI。
    # stream_callback：飞书等会传，用于最后一段推送；stream_output=True 且无 callback 时流式打印到 stdout。
    buffered_segments: list[str] = []
    if use_stream:
        def _capture_segment(segment: str) -> None:
            buffered_segments.append(segment)

        out, ok = _run_agent_streaming(
            prompt,
            workspace,
            timeout,
            effective_model,
            on_segment=_capture_segment if stream_callback else None,  # None 时在 _run_agent_streaming 内 print(visible_delta) 流式输出文字
        )
    else:
        out, ok = _run_agent_via_cli(prompt, workspace, timeout, effective_model)

    clean_out = sanitize_markdown_structure(out)
    clean_out, runtime_request = _extract_agent_runtime_request(clean_out)
    if ok and runtime_request:
        runtime_result = _execute_agent_runtime_request(
            runtime_request,
            workspace=workspace,
            timeout=timeout,
            model=effective_model,
        )
        followup_prompt = _build_runtime_followup_prompt(
            effective_prompt,
            clean_out,
            runtime_result,
            workspace=workspace,
        )
        final_out, final_ok = _run_agent_via_cli(followup_prompt, workspace, timeout, effective_model)
        final_clean = sanitize_markdown_structure(final_out)
        final_clean, _ = _extract_agent_runtime_request(final_clean)
        final_text = final_clean if final_ok and final_clean else str(runtime_result.get("output") or clean_out or "").strip()
        final_text = safe_truncate_markdown(final_text, int(max_len))
        if stream_callback:
            stream_callback(final_text)
        return final_text
    if ok:
        if stream_callback:
            for segment in buffered_segments:
                stream_callback(segment)
        return safe_truncate_markdown(clean_out, int(max_len))
    if not out:
        out = "管家bot 执行失败（可能 API 暂不可用）。"
    return safe_truncate_markdown(sanitize_markdown_structure(out), int(max_len))


def _after_reply_persist_memory_async(user_prompt: str, assistant_reply: str) -> None:
    pending_memory_id = getattr(TURN_CONTEXT, "pending_memory_id", None)
    turn_model = getattr(TURN_CONTEXT, "turn_model", None)
    turn_user_prompt = getattr(TURN_CONTEXT, "turn_user_prompt", user_prompt)
    post_reply_action = getattr(TURN_CONTEXT, "post_reply_action", None)
    suppress_task_merge = bool(getattr(TURN_CONTEXT, "turn_suppress_task_merge", False))
    MEMORY.on_reply_sent_async(
        turn_user_prompt,
        assistant_reply,
        memory_id=pending_memory_id,
        model_override=turn_model,
        suppress_task_merge=suppress_task_merge,
    )
    if callable(post_reply_action):
        try:
            post_reply_action()
        except Exception as exc:
            print(f"[upgrade-approval] post reply action failed: {exc}", flush=True)
    for attr_name in ("pending_memory_id", "turn_model", "turn_cli_request", "turn_user_prompt", "post_reply_action", "turn_suppress_task_merge"):
        if hasattr(TURN_CONTEXT, attr_name):
            delattr(TURN_CONTEXT, attr_name)


def _on_bot_started() -> None:
    MEMORY.start_background_services()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-stream", action="store_true", help="本地测试：一次性输出（默认）")
    parser.add_argument("--stream", action="store_true", help="本地测试：流式输出文字到终端")

    def local_test(prompt: str, args: argparse.Namespace) -> str:
        if getattr(args, "stream", False):
            return run_agent(prompt, stream_output=True)
        return run_agent(prompt)

    return run_feishu_bot(
        config_path="",
        default_config_name="butler_bot",
        bot_name="管家bot",
        run_agent_fn=run_agent,
        supports_images=True,
        supports_stream_segment=True,
        args_extra=parser,
        local_test_fn=local_test,
        on_bot_started=_on_bot_started,
        on_reply_sent=_after_reply_persist_memory_async,
    )


if __name__ == "__main__":
    sys.exit(main())

