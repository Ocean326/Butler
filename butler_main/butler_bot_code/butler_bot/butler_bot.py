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
import locale
import os
import re
import subprocess
import sys
import threading
from typing import Callable

from agent import (
    CONFIG,
    build_feishu_agent_prompt,
    get_config,
    load_config,
    run_feishu_bot,
)
from markdown_safety import safe_truncate_markdown, sanitize_markdown_structure
from memory_manager import MemoryManager, build_cursor_cli_env
from skill_registry import render_skill_catalog_for_prompt


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


def _cursor_cli_cmd_path() -> str:
    """Cursor IDE CLI 路径（外部依赖，非本 bot）"""
    return os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "cursor-agent", "versions", "dist-package", "cursor-agent.cmd",
    )


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")


def _decode_cli_payload(payload: bytes | str | None) -> str:
    if isinstance(payload, str):
        return payload
    if not payload:
        return ""

    encodings: list[str] = ["utf-8", "utf-8-sig"]
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


def _parse_runtime_control(user_prompt: str, cfg: dict) -> dict:
    text = (user_prompt or "").strip()
    lower = text.lower()

    if any(hint in text for hint in MODEL_LIST_HINTS):
        return {"kind": "list-models", "prompt": "", "model": ""}
    if any(hint in text for hint in CURRENT_MODEL_HINTS):
        return {"kind": "current-model", "prompt": "", "model": ""}

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
        }

    if lower.startswith("model:") or lower.startswith("模型:") or lower.startswith("模型："):
        _, _, rest = text.partition(":")
        raw_model, _, clean_prompt = rest.strip().partition(" ")
        return {
            "kind": "run",
            "prompt": clean_prompt.strip(),
            "model": _resolve_runtime_model(raw_model, cfg),
            "raw_model": raw_model,
        }

    return {"kind": "run", "prompt": text, "model": "", "raw_model": ""}


def _list_available_models(workspace: str, timeout: int, cfg: dict | None = None) -> tuple[list[str], str | None]:
    agent_cmd = _cursor_cli_cmd_path()
    if not os.path.isfile(agent_cmd):
        return [], f"未找到 Cursor CLI（管家bot 依赖）: {agent_cmd}"

    args = [agent_cmd, "models", "--trust", "--workspace", workspace]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(max(15, timeout), 60),
            cwd=workspace,
            env=build_cursor_cli_env(cfg),
        )
    except subprocess.TimeoutExpired:
        return [], "获取模型列表超时"
    except Exception as exc:
        return [], f"获取模型列表异常: {exc}"

    merged = "\n".join([result.stdout or "", result.stderr or ""]).strip()
    cleaned = _strip_ansi(merged)
    models: list[str] = []
    seen = set()
    token_pattern = re.compile(r"[A-Za-z][A-Za-z0-9._-]{1,}")
    for raw_line in cleaned.splitlines():
        line = raw_line.strip().strip("|-*` ")
        if not line:
            continue
        if any(ch in line for ch in "╭╰│▶⚠"):
            continue
        if line.lower().startswith(("usage:", "warning:", "ps ")):
            continue
        if "workspace trust required" in line.lower():
            continue
        dash_candidate = re.match(r"^(?P<model>[A-Za-z][A-Za-z0-9._-]{1,})\s+-\s+.+$", line)
        if dash_candidate:
            candidate = str(dash_candidate.group("model") or "").strip()
        elif token_pattern.fullmatch(line):
            candidate = line
        else:
            parts = re.findall(r"[A-Za-z][A-Za-z0-9._-]{1,}", line)
            if len(parts) != 1:
                continue
            candidate = parts[0]
        low = candidate.lower()
        if low in seen or low in {"model", "models", "default", "available", "cursor", "agent", "workspace", "trust"}:
            continue
        seen.add(low)
        models.append(candidate)
    if not models and result.returncode != 0:
        return [], cleaned[:400] or f"获取模型列表失败 (exit={result.returncode})"
    return models, None


def _format_model_list_reply(cfg: dict, workspace: str, timeout: int) -> str:
    models, error = _list_available_models(workspace, timeout, cfg)
    default_model = str((cfg or {}).get("agent_model", "auto") or "auto")
    alias_lines = []
    for alias, target in sorted(_runtime_model_aliases(cfg).items()):
        if alias == target.lower():
            continue
        alias_lines.append(f"- {alias} -> {target}")
    if error:
        base = f"当前默认模型：{default_model}\n模型列表获取失败：{error}"
        if alias_lines:
            base += "\n\n已配置别名：\n" + "\n".join(alias_lines[:12])
        return base
    lines = [f"当前默认模型：{default_model}", f"可用模型（{len(models)} 个）："]
    lines.extend(f"- {model}" for model in models)
    if alias_lines:
        lines.append("")
        lines.append("已配置别名：")
        lines.extend(alias_lines[:12])
    lines.append("")
    lines.append("本轮可直接这样写：用 gpt-5 回答：... 或 [模型=sonnet-4] ...")
    return "\n".join(lines)


def _format_current_model_reply(cfg: dict) -> str:
    default_model = str((cfg or {}).get("agent_model", "auto") or "auto")
    aliases = _runtime_model_aliases(cfg)
    lines = [f"当前默认模型：{default_model}"]
    visible_aliases = [(alias, target) for alias, target in sorted(aliases.items()) if alias != target.lower()]
    if visible_aliases:
        lines.append("可用别名：")
        for alias, target in visible_aliases:
            lines.append(f"- {alias} -> {target}")
    lines.append("本轮指定模型示例：用 gpt-5 回答：你的问题")
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
    agent_cmd = _cursor_cli_cmd_path()
    if not os.path.isfile(agent_cmd):
        return f"错误：未找到 Cursor CLI（管家bot 依赖），请检查路径 {agent_cmd}", False
    args = [
        agent_cmd, "-p", "--force", "--trust", "--approve-mcps",
        "--model", model or "auto", "--output-format", "json",
        "--workspace", workspace,
    ]
    try:
        result = subprocess.run(
            args,
            input=(prompt or "").encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            cwd=workspace,
            env=build_cursor_cli_env(get_config()),
        )
        out = ""
        stdout_text = _decode_cli_payload(result.stdout).strip()
        stderr_text = _decode_cli_payload(result.stderr).strip()
        if result.returncode == 0 and stdout_text:
            try:
                data = json.loads(stdout_text)
                out = (data.get("result") or "").strip()
            except (json.JSONDecodeError, TypeError):
                out = stdout_text
        if not out and stderr_text:
            out = stderr_text
        if out and result.returncode == 0:
            return out, True
        return out or f"管家bot 执行失败 (exit={result.returncode})", False
    except subprocess.TimeoutExpired:
        return "执行超时", False
    except Exception as e:
        return f"管家bot 执行异常: {e}", False


def _run_agent_streaming(
    prompt: str,
    workspace: str,
    timeout: int,
    model: str,
    on_segment: Callable[[str], None] | None = None,
) -> tuple[str, bool]:
    agent_cmd = _cursor_cli_cmd_path()
    if not os.path.isfile(agent_cmd):
        return f"错误：未找到 Cursor CLI（管家bot 依赖），请检查路径 {agent_cmd}", False

    assembler = _StreamAssembler()
    last_result = ""
    proc = None

    def _drain_stderr() -> None:
        if proc and proc.stderr:
            try:
                proc.stderr.read()
            except Exception:
                pass

    args = [
        agent_cmd, "-p", "--force", "--trust", "--approve-mcps",
        "--model", model or "auto",
        "--output-format", "stream-json", "--stream-partial-output",
        "--workspace", workspace,
    ]

    try:
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workspace,
            env=build_cursor_cli_env(get_config()),
        )
        proc.stdin.write((prompt or "").encode("utf-8"))
        proc.stdin.close()
        threading.Thread(target=_drain_stderr, daemon=True).start()

        try:
            for line in proc.stdout:
                line = _decode_cli_payload(line).rstrip("\r\n")
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ev_type = data.get("type")
                if ev_type == "assistant":
                    msg = data.get("message") or {}
                    blocks = msg.get("content") or []
                    text_parts = [b.get("text") for b in blocks if b.get("type") == "text" and b.get("text")]
                    if not text_parts:
                        continue
                    incoming = "".join(text_parts)
                    print(
                        f"[stream-assistant] incoming_len={len(incoming)} | incoming={_stream_preview(incoming)}",
                        flush=True,
                    )
                    visible_delta = assembler.ingest(incoming)
                    print(
                        f"[stream-delta] delta_len={len(visible_delta)} | emitted_len={len(assembler.final_text())} | unstable={assembler.unstable_stream} | delta={_stream_preview(visible_delta)}",
                        flush=True,
                    )
                    if not visible_delta:
                        continue
                    if on_segment:
                        # [已关闭] 按 markdown ## 拆成多张卡片，展示效果不好；改为流结束后整段一张卡片发送
                        # new_sections, sent_section_count, tail = _collect_unsent_markdown_sections(
                        #     emitted_text,
                        #     sent_section_count,
                        # )
                        # print(
                        #     f"[stream-sections] ready_titles={_section_titles(new_sections)} | sent_count={sent_section_count} | tail_len={len(tail)} | tail={_stream_preview(tail)}",
                        #     flush=True,
                        # )
                        # for section in new_sections:
                        #     on_segment(section)
                        pass
                    else:
                        print(visible_delta, end="", flush=True)
                elif ev_type == "result" and data.get("subtype") == "success":
                    last_result = (data.get("result") or "").strip()
                    print(
                        f"[stream-result] result_len={len(last_result)} | result={_stream_preview(last_result)}",
                        flush=True,
                    )

            final_snapshot = assembler.final_text().strip()
            if on_segment and final_snapshot:
                # [已关闭] 按 markdown 拆多段 + tail，改为整段一张卡片
                # new_sections, sent_section_count, tail = _collect_unsent_markdown_sections(
                #     emitted_text,
                #     sent_section_count,
                # )
                # print(
                #     f"[stream-finalize] new_titles={_section_titles(new_sections)} | sent_count={sent_section_count} | tail_len={len(tail)} | tail={_stream_preview(tail)}",
                #     flush=True,
                # )
                # for section in new_sections:
                #     on_segment(section)
                # if tail.strip():
                #     print(f"[stream-tail-send] tail={_stream_preview(tail)}", flush=True)
                #     on_segment(tail.strip())
                on_segment(final_snapshot)
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return "".join(full_result) or "执行超时", False

        out = (last_result or "").strip() or assembler.final_text().strip()
        out = out.strip()
        if proc.returncode == 0 and out:
            return out, True
        return out or f"管家bot 执行失败 (exit={proc.returncode})", False
    except Exception as e:
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
        raw = (last_result or "").strip() or assembler.final_text().strip()
        return raw or f"管家bot 执行异常: {e}", False


MEMORY = MemoryManager(config_provider=get_config, run_model_fn=_run_agent_via_cli)
TURN_CONTEXT = threading.local()


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
        return _format_model_list_reply(cfg, workspace, timeout)
    if control.get("kind") == "current-model":
        return _format_current_model_reply(cfg)

    effective_model = str(control.get("model") or cfg.get("agent_model", "auto") or "auto")
    effective_prompt = str(control.get("prompt") or "").strip()
    if not effective_prompt:
        return f"已识别本轮模型为 {effective_model}。请把问题和模型指令放在同一条消息里，例如：用 {effective_model} 回答：你的问题"

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

    pending_memory_id, previous_pending = MEMORY.begin_pending_turn(effective_prompt, workspace)
    TURN_CONTEXT.pending_memory_id = pending_memory_id
    TURN_CONTEXT.turn_model = effective_model
    TURN_CONTEXT.turn_user_prompt = effective_prompt
    user_prompt_with_recent = MEMORY.prepare_user_prompt_with_recent(
        effective_prompt,
        exclude_memory_id=pending_memory_id,
        previous_pending=previous_pending,
    )
    print(
        f"[agent-run] pending_memory_id={pending_memory_id} | model={effective_model} | user={re.sub(r'\s+', ' ', (effective_prompt or '').strip())[:100]}"
        + (f" | previous_pending={str((previous_pending or {}).get('topic') or '')[:80]}" if previous_pending else ""),
        flush=True,
    )
    print(f"[agent-prompt] {re.sub(r'\s+', ' ', user_prompt_with_recent)[:200]}", flush=True)
    skills_prompt = _render_available_skills_prompt(workspace)
    prompt = build_feishu_agent_prompt(
        user_prompt_with_recent,
        image_paths,
        skills_prompt=skills_prompt,
    )
    print(
        f"[agent-prompt-stats] user_len={len(effective_prompt)} | recent_len={len(user_prompt_with_recent)} | skills_len={len(skills_prompt)} | full_len={len(prompt)}",
        flush=True,
    )
    max_len = cfg.get("max_reply_len", 4000)

    # 根据是否提供 stream_callback 选择流式或一次性调用 Cursor CLI。
    use_stream = bool(stream_callback)
    if use_stream:
        out, ok = _run_agent_streaming(
            prompt,
            workspace,
            timeout,
            effective_model,
            on_segment=stream_callback,
        )
    else:
        out, ok = _run_agent_via_cli(prompt, workspace, timeout, effective_model)

    clean_out = sanitize_markdown_structure(out)
    if ok:
        return safe_truncate_markdown(clean_out, int(max_len))
    if not out:
        out = "管家bot 执行失败（可能 API 暂不可用）。"
    return safe_truncate_markdown(sanitize_markdown_structure(out), int(max_len))


def _after_reply_persist_memory_async(user_prompt: str, assistant_reply: str) -> None:
    pending_memory_id = getattr(TURN_CONTEXT, "pending_memory_id", None)
    turn_model = getattr(TURN_CONTEXT, "turn_model", None)
    turn_user_prompt = getattr(TURN_CONTEXT, "turn_user_prompt", user_prompt)
    post_reply_action = getattr(TURN_CONTEXT, "post_reply_action", None)
    MEMORY.on_reply_sent_async(turn_user_prompt, assistant_reply, memory_id=pending_memory_id, model_override=turn_model)
    if callable(post_reply_action):
        try:
            post_reply_action()
        except Exception as exc:
            print(f"[upgrade-approval] post reply action failed: {exc}", flush=True)
    for attr_name in ("pending_memory_id", "turn_model", "turn_user_prompt", "post_reply_action"):
        if hasattr(TURN_CONTEXT, attr_name):
            delattr(TURN_CONTEXT, attr_name)


def _on_bot_started() -> None:
    MEMORY.start_background_services()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-stream", action="store_true", help="本地测试：禁用流式输出")

    def local_test(prompt: str, args: argparse.Namespace) -> str:
        if not getattr(args, "no_stream", False):
            return run_agent(prompt)
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
