from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from butler_main.agents_os.runtime.local_memory_index import LocalMemoryIndexService
from butler_main.chat.pathing import LOCAL_MEMORY_DIR_REL, ensure_chat_data_layout
from butler_main.runtime_os.agent_runtime import cli_runner as cli_runtime_service


LOCAL_MEMORY_JOURNAL_FILE = "local_memory_write_journal.jsonl"
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", re.IGNORECASE)
_INVALID_FILENAME_RE = re.compile(r'[\\/:*?"<>|\r\n]+')
_URL_RE = re.compile(r"https?://\S+")
_PATH_RE = re.compile(r"(?:\.[/\\]|[/\\])[\w\-.\\/一-龥]+")
_COMMAND_RE = re.compile(r"(?:^|\n)\s*(?:python3?|pytest|git|rg|sed|cat|bash|pwsh|npm|pnpm|uv)\b[^\n]*")
_LEADING_PROCESS_ORDINAL_RE = re.compile(
    r"^\s*(?:(?:step|步骤)\s*)?(?:第\s*)?\d{1,2}(?:\s*[.:：、]\s*|\s*\)\s*)",
    re.IGNORECASE,
)


class ChatSummaryPipelineRuntime:
    def __init__(
        self,
        *,
        config_provider,
        prompt_runner=None,
    ) -> None:
        self._config_provider = config_provider
        self._prompt_runner = prompt_runner or cli_runtime_service.run_prompt

    def summarize_window(
        self,
        window_turns: list[dict],
        existing_summaries: list[dict],
        *,
        workspace: str,
        timeout: int,
        model: str,
        session_scope_id: str = "",
    ) -> dict[str, Any]:
        prompt = self._build_window_summary_prompt(window_turns, existing_summaries)
        payload = self._run_json_task(
            prompt,
            workspace=workspace,
            timeout=timeout,
            model=model,
            session_scope_id=session_scope_id,
            task_kind="window-summary",
        )
        if not isinstance(payload, dict):
            payload = {}
        window_summary = payload.get("window_summary") if isinstance(payload.get("window_summary"), dict) else {}
        patches = payload.get("summary_patches") if isinstance(payload.get("summary_patches"), list) else []
        if not window_summary:
            window_summary = self._fallback_window_summary(window_turns)
        return {"window_summary": window_summary, "summary_patches": [item for item in patches if isinstance(item, dict)]}

    def govern_long_term_summary(
        self,
        summary_entry: dict,
        *,
        workspace: str,
        timeout: int,
        model: str,
        session_scope_id: str = "",
    ) -> dict[str, Any]:
        prompt = self._build_long_term_governance_prompt(summary_entry)
        payload = self._run_json_task(
            prompt,
            workspace=workspace,
            timeout=timeout,
            model=model,
            session_scope_id=session_scope_id,
            task_kind="long-memory-governance",
        )
        if not isinstance(payload, dict):
            payload = {}
        should_write = bool(payload.get("should_write"))
        if not should_write:
            should_write = self._fallback_should_write(summary_entry)
        if not should_write:
            return {"status": "skipped", "reason": "not-selected"}
        memory_record = self._normalize_memory_record(payload, summary_entry)
        local_root = ensure_chat_data_layout(workspace) / LOCAL_MEMORY_DIR_REL
        write_result = self._write_local_memory_record(local_root, memory_record, source_summary=summary_entry)
        return {"status": "written", **write_result}

    def _run_json_task(
        self,
        prompt: str,
        *,
        workspace: str,
        timeout: int,
        model: str,
        session_scope_id: str,
        task_kind: str,
    ) -> dict[str, Any] | None:
        cfg = self._config_provider() or {}
        runtime_request: dict[str, Any] = {
            "channel": "memory-maintenance",
            "session_id": session_scope_id or f"memory:{task_kind}",
            "actor_id": "butler_memory",
            "task_kind": task_kind,
        }
        active_cli = str(((cfg.get("cli_runtime") or {}) if isinstance(cfg.get("cli_runtime"), dict) else {}).get("active") or "").strip()
        if active_cli:
            runtime_request["cli"] = active_cli
        effective_model = self._resolve_maintenance_model(cfg, fallback=model)
        if effective_model:
            runtime_request["model"] = effective_model
        output, ok = self._prompt_runner(prompt, workspace, timeout, cfg, runtime_request, stream=False)
        if not ok:
            return None
        return _extract_json_payload(output)

    def _resolve_maintenance_model(self, cfg: dict, *, fallback: str) -> str:
        memory_cfg = cfg.get("memory") if isinstance(cfg.get("memory"), dict) else {}
        talk_recent = memory_cfg.get("talk_recent") if isinstance(memory_cfg.get("talk_recent"), dict) else {}
        return str(talk_recent.get("summary_model") or fallback or cfg.get("agent_model") or "auto")

    def _build_window_summary_prompt(self, window_turns: list[dict], existing_summaries: list[dict]) -> str:
        turn_lines: list[str] = []
        for item in window_turns:
            turn_lines.append(
                json.dumps(
                    {
                        "memory_id": str(item.get("memory_id") or ""),
                        "turn_seq": int(item.get("turn_seq") or 0),
                        "timestamp": str(item.get("timestamp") or ""),
                        "user_prompt": str(item.get("user_prompt") or ""),
                        "assistant_reply_visible": str(item.get("assistant_reply_visible") or item.get("assistant_reply") or ""),
                        "process_events": _normalize_process_events_for_prompt(item.get("process_events")),
                        "raw_signals": _extract_turn_signals(item),
                    },
                    ensure_ascii=False,
                )
            )
        summary_lines: list[str] = []
        for item in existing_summaries[-5:]:
            summary_lines.append(
                json.dumps(
                    {
                        "summary_id": str(item.get("summary_id") or ""),
                        "title": str(item.get("title") or ""),
                        "summary_text": str(item.get("summary_text") or ""),
                        "user_summary": str(item.get("user_summary") or item.get("summary_text") or ""),
                        "process_reflection": str(item.get("process_reflection") or ""),
                        "requirements": [str(v) for v in item.get("requirements") or [] if str(v).strip()],
                        "open_loops": [str(v) for v in item.get("open_loops") or [] if str(v).strip()],
                        "user_preferences_updates": [str(v) for v in item.get("user_preferences_updates") or [] if str(v).strip()],
                    },
                    ensure_ascii=False,
                )
            )
        return (
            "你是 Butler 的 recent summary 维护器。"
            "基于最近关闭的一窗 10 轮对话，生成一条窗口摘要，并只在必要时给旧摘要打补丁。"
            "不要复述客套话，不要编造。输出严格 JSON。\n\n"
            "返回格式：\n"
            "{\n"
            '  "window_summary": {\n'
            '    "title": "简短标题",\n'
            '    "summary_text": "这 10 轮面向用户的连续主线摘要",\n'
            '    "user_summary": "和用户相关的主线、要求、结论摘要",\n'
            '    "process_reflection": "Butler 自己这 10 轮是怎么做的、卡在哪里、哪些做法值得保留或避免",\n'
            '    "topics": ["主题"],\n'
            '    "requirements": ["仍然有效的用户要求"],\n'
            '    "decisions": ["已经确定的决定"],\n'
            '    "open_loops": ["尚未完成或待确认事项"],\n'
            '    "user_preferences_updates": ["新发现或被修正的稳定偏好"]\n'
            "  },\n"
            '  "summary_patches": [\n'
            "    {\n"
            '      "summary_id": "要修补的旧摘要ID",\n'
            '      "requirements_add": ["新增要求"],\n'
            '      "requirements_remove": ["应移除的旧要求"],\n'
            '      "open_loops_add": ["新增未完项"],\n'
            '      "open_loops_remove": ["已关闭未完项"],\n'
            '      "preferences_add": ["新增稳定偏好"],\n'
            '      "preferences_remove": ["应移除的旧偏好"],\n'
            '      "summary_append": "如需补一小句用户主线说明，写这里，否则空串",\n'
            '      "process_reflection_append": "如需补一小句过程反思，写这里，否则空串"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "已有摘要（最近 5 条）：\n"
            + ("\n".join(summary_lines) if summary_lines else "[]")
            + "\n\n最近关闭窗口 turn：\n"
            + "\n".join(turn_lines)
        )

    def _build_long_term_governance_prompt(self, summary_entry: dict) -> str:
        return (
            "你是 Butler 的长期记忆治理器。"
            "请判断这条窗口摘要是否值得写入 local_memory。"
            "只保留稳定偏好、长期约束、持续任务状态、关系/表达偏好，排除一次性执行细节。"
            "输出严格 JSON。\n\n"
            "返回格式：\n"
            "{\n"
            '  "should_write": true,\n'
            '  "title": "长期记忆标题",\n'
            '  "category": "preferences|rules|projects|relationships|misc",\n'
            '  "current_conclusion": "一句当前结论",\n'
            '  "history_evolution": ["可选历史演化"],\n'
            '  "applicable_scenarios": ["适用情景"],\n'
            '  "keywords": ["关键词"]\n'
            "}\n\n"
            "待治理摘要：\n"
            + json.dumps(
                {
                    "title": str(summary_entry.get("title") or ""),
                    "summary_text": str(summary_entry.get("summary_text") or ""),
                    "user_summary": str(summary_entry.get("user_summary") or summary_entry.get("summary_text") or ""),
                    "process_reflection": str(summary_entry.get("process_reflection") or ""),
                    "topics": [str(v) for v in summary_entry.get("topics") or [] if str(v).strip()],
                    "requirements": [str(v) for v in summary_entry.get("requirements") or [] if str(v).strip()],
                    "decisions": [str(v) for v in summary_entry.get("decisions") or [] if str(v).strip()],
                    "open_loops": [str(v) for v in summary_entry.get("open_loops") or [] if str(v).strip()],
                    "user_preferences_updates": [str(v) for v in summary_entry.get("user_preferences_updates") or [] if str(v).strip()],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    def _fallback_window_summary(self, window_turns: list[dict]) -> dict[str, Any]:
        topics: list[str] = []
        requirements: list[str] = []
        open_loops: list[str] = []
        process_notes: list[str] = []
        for item in window_turns:
            topic = str(item.get("topic") or item.get("user_prompt") or "").strip()
            if topic:
                topics.append(topic[:60])
            prompt = re.sub(r"\s+", " ", str(item.get("user_prompt") or "").strip())
            if prompt:
                requirements.append(prompt[:120])
            reply = re.sub(r"\s+", " ", str(item.get("assistant_reply_visible") or item.get("assistant_reply") or "").strip())
            if reply:
                open_loops.append(reply[:100])
            process_note = _summarize_turn_process_events(item)
            if process_note:
                process_notes.append(process_note)
        lead_topic = topics[0] if topics else "最近对话"
        user_summary = f"这 10 轮主要围绕“{lead_topic[:40]}”推进，最近结论与要求已整理为可续接摘要。"
        return {
            "title": lead_topic[:40],
            "summary_text": user_summary,
            "user_summary": user_summary,
            "process_reflection": "；".join(_dedupe(process_notes)[-3:])[:320],
            "topics": _dedupe(topics)[:4],
            "requirements": _dedupe(requirements)[:6],
            "decisions": [],
            "open_loops": _dedupe(open_loops)[-3:],
            "user_preferences_updates": [],
        }

    def _fallback_should_write(self, summary_entry: dict) -> bool:
        haystack = "\n".join(
            [
                str(summary_entry.get("title") or ""),
                str(summary_entry.get("user_summary") or ""),
                str(summary_entry.get("summary_text") or ""),
                "\n".join(str(v) for v in summary_entry.get("requirements") or []),
                "\n".join(str(v) for v in summary_entry.get("user_preferences_updates") or []),
            ]
        )
        markers = ("默认", "以后", "偏好", "长期", "约束", "总是", "优先", "不要", "关系")
        return any(marker in haystack for marker in markers)

    def _normalize_memory_record(self, payload: dict, summary_entry: dict) -> dict[str, Any]:
        title = str(payload.get("title") or summary_entry.get("title") or "最近对话总结").strip()
        category = str(payload.get("category") or "").strip().lower() or _infer_memory_category(summary_entry)
        current_conclusion = str(payload.get("current_conclusion") or summary_entry.get("user_summary") or summary_entry.get("summary_text") or "").strip()
        history = [str(v).strip() for v in payload.get("history_evolution") or [] if str(v).strip()]
        scenarios = [str(v).strip() for v in payload.get("applicable_scenarios") or [] if str(v).strip()]
        keywords = [str(v).strip() for v in payload.get("keywords") or [] if str(v).strip()]
        if not history:
            history = [f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}：来自 recent summary pool 的治理写入"]
        return {
            "title": title[:80],
            "category": category,
            "current_conclusion": current_conclusion[:220],
            "history_evolution": history[:6],
            "applicable_scenarios": scenarios[:6],
            "keywords": keywords[:8] or _dedupe([str(v) for v in summary_entry.get("topics") or [] if str(v).strip()])[:6],
        }

    def _write_local_memory_record(self, local_root: Path, record: dict[str, Any], *, source_summary: dict) -> dict[str, Any]:
        service = LocalMemoryIndexService(local_root)
        service.ensure_layout()
        _, l1_dir, _ = service.layer_paths()
        filename = _sanitize_filename(str(record.get("title") or "最近对话总结")) + ".md"
        target_path = l1_dir / filename
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history_lines = [f"- {item}" for item in record.get("history_evolution") or [] if str(item).strip()]
        if not history_lines:
            history_lines = [f"- {timestamp}：来自 recent summary pool 的治理写入"]
        scenario_lines = [f"- {item}" for item in record.get("applicable_scenarios") or [] if str(item).strip()]
        keyword_lines = [f"- {item}" for item in record.get("keywords") or [] if str(item).strip()]
        content = [
            f"# {record['title']}",
            "",
            f"> 自动沉淀于 {timestamp}（summary_pool -> local_memory）",
            "",
            f"当前结论: {record['current_conclusion']}",
            "",
            "## 历史演化",
            *(history_lines or ["- 暂无"]),
            "",
            "## 适用情景",
            *(scenario_lines or ["- 最近对话治理"]),
            "",
            "## 关键词",
            *(keyword_lines or ["- recent_summary"]),
            "",
            "## 来源",
            f"- source_summary_id: {str(source_summary.get('summary_id') or '').strip()}",
            f"- source_turn_range: {int(source_summary.get('window_start_seq') or 0)}-{int(source_summary.get('window_end_seq') or 0)}",
        ]
        target_path.write_text("\n".join(content).strip() + "\n", encoding="utf-8")
        service.rebuild_index()
        journal_path = local_root / LOCAL_MEMORY_JOURNAL_FILE
        journal_payload = {
            "timestamp": timestamp,
            "action": "summary-pool-governed-write",
            "title": record["title"],
            "summary_preview": record["current_conclusion"][:240],
            "keywords": record.get("keywords") or [],
            "summary_path": f"L1_summaries/{filename}",
            "detail_path": "",
            "source_type": "summary-pool",
            "source_memory_id": "",
            "source_reason": "summary_pool_governed",
            "source_topic": str(source_summary.get("title") or "").strip(),
            "source_summary_id": str(source_summary.get("summary_id") or "").strip(),
        }
        with journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(journal_payload, ensure_ascii=False) + "\n")
        return {"title": record["title"], "summary_path": f"L1_summaries/{filename}"}


def _extract_json_payload(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    fenced = _JSON_BLOCK_RE.search(raw)
    if fenced:
        raw = fenced.group(1).strip()
    if raw.startswith("{") and raw.endswith("}"):
        try:
            payload = json.loads(raw)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            return payload
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(raw[start : end + 1])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_turn_signals(turn: dict) -> dict[str, list[str]]:
    raw_text = str(turn.get("assistant_reply_raw") or turn.get("assistant_reply_visible") or turn.get("assistant_reply") or "")
    process_text = "\n".join(
        str(item.get("text") or "").strip()
        for item in _normalize_process_events_for_prompt(turn.get("process_events"))
    )
    prompt_text = str(turn.get("user_prompt") or "")
    combined = f"{prompt_text}\n{raw_text}\n{process_text}"
    return {
        "urls": _dedupe(_URL_RE.findall(combined))[:4],
        "paths": _dedupe(_PATH_RE.findall(combined))[:4],
        "commands": _dedupe([item.strip() for item in _COMMAND_RE.findall(combined)])[:4],
    }


def _sanitize_filename(text: str) -> str:
    cleaned = _INVALID_FILENAME_RE.sub("_", str(text or "").strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    return cleaned[:80] or "最近对话总结"


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text and text not in deduped:
            deduped.append(text)
    return deduped


def _infer_memory_category(summary_entry: dict) -> str:
    haystack = "\n".join(
        [
            str(summary_entry.get("title") or ""),
            str(summary_entry.get("user_summary") or ""),
            str(summary_entry.get("summary_text") or ""),
            "\n".join(str(v) for v in summary_entry.get("requirements") or []),
            "\n".join(str(v) for v in summary_entry.get("user_preferences_updates") or []),
        ]
    ).lower()
    if any(token in haystack for token in ("偏好", "喜欢", "风格", "口吻", "emoji")):
        return "preferences"
    if any(token in haystack for token in ("规则", "约束", "默认", "必须", "不要")):
        return "rules"
    if any(token in haystack for token in ("项目", "任务", "推进", "组会", "论文")):
        return "projects"
    if any(token in haystack for token in ("关系", "陪伴", "朋友")):
        return "relationships"
    return "misc"


def _normalize_process_events_for_prompt(process_events: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in process_events or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        text = _LEADING_PROCESS_ORDINAL_RE.sub("", re.sub(r"\s+", " ", str(item.get("text") or "").strip())).strip()
        status = str(item.get("status") or "").strip().lower()
        if not kind and not text:
            continue
        payload = {"kind": kind or "event", "text": text[:180]}
        if status:
            payload["status"] = status[:40]
        if normalized and normalized[-1] == payload:
            continue
        normalized.append(payload)
    return normalized


def _summarize_turn_process_events(turn: dict) -> str:
    events = _normalize_process_events_for_prompt(turn.get("process_events"))
    if not events:
        return ""
    command_count = sum(1 for item in events if item.get("kind") == "command")
    error_count = sum(1 for item in events if item.get("kind") in {"stderr", "error"})
    latest = next((str(item.get("text") or "").strip() for item in reversed(events) if str(item.get("text") or "").strip()), "")
    parts: list[str] = []
    if command_count:
        parts.append(f"执行过 {command_count} 条过程命令")
    if error_count:
        parts.append(f"出现 {error_count} 条过程告警")
    if latest:
        parts.append(f"最近过程记录：{latest[:120]}")
    return "；".join(parts)


__all__ = ["ChatSummaryPipelineRuntime"]
