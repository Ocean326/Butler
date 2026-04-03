from __future__ import annotations

import re

from ..session_selection import (
    ChatSessionState,
    is_new_task_prompt,
    load_chat_session_state,
    looks_like_followup_prompt,
)
from ..session_modes import (
    ChatSessionModeState,
    load_chat_session_mode_state,
    render_mode_artifact_block,
    resolve_recent_mode,
)

_LEADING_PROCESS_ORDINAL_RE = re.compile(
    r"^\s*(?:(?:step|步骤)\s*)?(?:第\s*)?\d{1,2}(?:\s*[.:：、]\s*|\s*\)\s*)",
    re.IGNORECASE,
)

class ChatRecentPromptAssembler:
    """Chat-owned assembler for recent-memory prompt projection."""

    def __init__(self, *, turn_store) -> None:
        self._turn_store = turn_store

    def prepare_turn_input(
        self,
        user_prompt: str,
        *,
        exclude_memory_id: str,
        previous_pending=None,
        recent_mode: str = "default",
        session_scope_id: str = "",
        mode_state_override: ChatSessionModeState | dict | None = None,
        chat_session_state_override: ChatSessionState | dict | None = None,
    ) -> str:
        cfg = self._turn_store._config_provider() or {}
        workspace = cfg.get("workspace_root") or "."
        effective_recent_mode = resolve_recent_mode(explicit_mode=recent_mode)
        chat_session_state = (
            ChatSessionState(**dict(chat_session_state_override))
            if isinstance(chat_session_state_override, dict)
            else chat_session_state_override
        ) or load_chat_session_state(str(workspace), session_scope_id=session_scope_id)
        active_chat_session_id = str(chat_session_state.active_chat_session_id or "").strip()
        recent_entries = self._turn_store.load_recent_entries(
            str(workspace),
            session_scope_id=session_scope_id,
            chat_session_id=active_chat_session_id,
        )
        recent_raw_turns = self._turn_store.load_recent_raw_turns(
            str(workspace),
            session_scope_id=session_scope_id,
            chat_session_id=active_chat_session_id,
        )
        recent_summary_pool = self._turn_store.load_recent_summary_pool(
            str(workspace),
            session_scope_id=session_scope_id,
            chat_session_id=active_chat_session_id,
        )
        mode_state = (
            ChatSessionModeState(**dict(mode_state_override))
            if isinstance(mode_state_override, dict)
            else mode_state_override
        ) or load_chat_session_mode_state(str(workspace), session_scope_id=session_scope_id)
        if exclude_memory_id:
            recent_entries = [
                item for item in recent_entries
                if str((item or {}).get("memory_id") or "") != str(exclude_memory_id)
            ]
            recent_raw_turns = [
                item for item in recent_raw_turns
                if str((item or {}).get("memory_id") or "") != str(exclude_memory_id)
            ]
        recent_text = self._render_recent_context(
            recent_entries,
            recent_raw_turns,
            recent_summary_pool,
            max_chars=self._turn_store.recent_max_chars(effective_recent_mode),
            recent_mode=effective_recent_mode,
        )
        followup_text = self._render_pending_followup_context(previous_pending, user_prompt)
        continuation_text = self._render_recent_continuation_hint(recent_entries, recent_raw_turns, recent_summary_pool, user_prompt)
        requirement_text = self._render_recent_requirement_context(recent_summary_pool, recent_entries, max_items=6)
        artifact_text = render_mode_artifact_block(mode_state, recent_mode=effective_recent_mode)
        if not recent_text:
            lead_blocks = [block for block in (artifact_text, followup_text, continuation_text) if block]
            lead = "\n\n".join(lead_blocks).strip()
            return (lead + "\n\n" + user_prompt).strip() if lead else user_prompt
        requirement_block = f"【最近显式要求与未完约束】\n{requirement_text}\n\n" if requirement_text else ""
        followup_block = f"{followup_text}\n\n" if followup_text else ""
        continuation_block = f"{continuation_text}\n\n" if continuation_text else ""
        artifact_block = f"{artifact_text}\n\n" if artifact_text else ""
        return (
            f"{artifact_block}"
            f"【recent_memory（最近{self._turn_store.recent_visible_items(effective_recent_mode)}条可见对话 + 最近{self._turn_store.recent_summary_items(effective_recent_mode)}个窗口摘要，供上下文续接）】\n"
            f"{recent_text}\n\n"
            f"{requirement_block}"
            "【使用规则】默认沿用 recent_memory 做上下文续接。"
            "若当前消息很短、像补充意见、像引用回复或像对上一轮方案的修正，默认先按同一主线续接，主动补全省略主语与对象；"
            "只有 recent 指向多个高概率解释时才要求澄清。\n\n"
            f"{followup_block}"
            f"{continuation_block}"
            f"{user_prompt}"
        )

    def _render_pending_followup_context(self, previous_pending: dict | None, user_prompt: str) -> str:
        if not previous_pending:
            return ""
        pending_title = str(previous_pending.get("topic") or previous_pending.get("raw_user_prompt") or "").strip()
        if not pending_title:
            return ""
        current_text = re.sub(r"\s+", " ", (user_prompt or "").strip())
        return (
            "【追问上下文】上一问仍在回复中。\n"
            f"- 上一个问题：{pending_title[:120]}\n"
            f"- 用户又追问：{current_text[:160]}\n"
            "请优先回答当前追问；若当前追问依赖上一问，请带上必要衔接。"
        )

    def _looks_like_continuation_prompt(self, user_prompt: str) -> bool:
        return looks_like_followup_prompt(user_prompt)

    def _render_recent_continuation_hint(
        self,
        recent_entries: list[dict],
        recent_raw_turns: list[dict],
        recent_summary_pool: list[dict],
        user_prompt: str,
    ) -> str:
        if not self._looks_like_continuation_prompt(user_prompt):
            return ""
        latest_topic = ""
        latest_summary = ""
        completed_raw_turns = [
            dict(item)
            for item in recent_raw_turns
            if isinstance(item, dict) and str(item.get("status") or "completed").strip() == "completed"
        ]
        if completed_raw_turns:
            latest_turn = completed_raw_turns[-1]
            latest_topic = str(latest_turn.get("topic") or latest_turn.get("user_prompt") or "").strip()
            latest_summary = re.sub(
                r"\s+",
                " ",
                str(latest_turn.get("assistant_reply_visible") or latest_turn.get("assistant_reply") or "").strip(),
            )[:180]
        if not latest_topic and not latest_summary and recent_summary_pool:
            latest_summary_entry = dict(recent_summary_pool[-1])
            latest_topic = str(latest_summary_entry.get("title") or "").strip()
            latest_summary = str(latest_summary_entry.get("user_summary") or latest_summary_entry.get("summary_text") or "").strip()
        for item in reversed(recent_entries or []):
            if latest_topic or latest_summary:
                break
            if not isinstance(item, dict):
                continue
            if str(item.get("memory_stream") or "talk").strip() != "talk":
                continue
            latest_topic = str(item.get("topic") or item.get("raw_user_prompt") or "").strip()
            latest_summary = str(item.get("summary") or "").strip()
            if latest_topic or latest_summary:
                break
        if not latest_topic and not latest_summary:
            return ""
        lines = ["【续接提示】当前这句更像对上一轮主线的补充/修改，不要当成全新任务。"]
        if latest_topic:
            lines.append(f"- 最近主线：{latest_topic[:120]}")
        if latest_summary:
            lines.append(f"- 最近结论/进展：{latest_summary[:180]}")
        lines.append("- 优先把省略的主语、对象、文件、方案选择从 recent_memory 或引用内容里补全后再回答。")
        return "\n".join(lines)

    def _render_recent_requirement_context(self, recent_summary_pool: list[dict], recent_entries: list[dict], max_items: int = 4) -> str:
        lines: list[str] = []
        seen: set[str] = set()
        for item in reversed(recent_summary_pool or []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            for requirement in [str(v).strip() for v in item.get("requirements") or [] if str(v).strip()]:
                key = requirement.lower()
                if key in seen:
                    continue
                seen.add(key)
                prefix = f"- {title[:24]}：" if title else "- "
                lines.append(f"{prefix}{requirement[:120]}")
                if len(lines) >= max_items:
                    return "\n".join(lines)
            for loop in [str(v).strip() for v in item.get("open_loops") or [] if str(v).strip()]:
                key = f"loop:{loop.lower()}"
                if key in seen:
                    continue
                seen.add(key)
                prefix = f"- {title[:24]} 未完点：" if title else "- 未完点："
                lines.append(f"{prefix}{loop[:120]}")
                if len(lines) >= max_items:
                    return "\n".join(lines)
        for item in reversed(recent_entries or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("memory_stream") or "talk").strip() != "talk":
                continue
            summary = re.sub(r"\s+", " ", str(item.get("summary") or "").strip())
            topic = re.sub(r"\s+", " ", str(item.get("topic") or "").strip())
            requirement = summary or topic
            if not requirement:
                continue
            key = requirement.lower()
            if key in seen:
                continue
            seen.add(key)
            next_actions = [re.sub(r"\s+", " ", str(v).strip())[:60] for v in (item.get("next_actions") or []) if str(v).strip()]
            line = f"- 最近要求/约束：{requirement[:120]}"
            if next_actions:
                line += f"；未完点/下一步：{' / '.join(next_actions[:2])}"
            lines.append(line)
            if len(lines) >= max_items:
                break
        return "\n".join(lines)

    def _is_new_task_prompt(self, user_prompt: str) -> bool:
        return is_new_task_prompt(user_prompt)

    def _render_recent_context(
        self,
        entries: list[dict],
        recent_raw_turns: list[dict],
        recent_summary_pool: list[dict],
        max_chars: int,
        recent_mode: str,
    ) -> str:
        visible_block = self._render_visible_recent_context(recent_raw_turns, recent_mode=recent_mode)
        summary_block = self._render_summary_pool_context(recent_summary_pool, recent_mode=recent_mode)
        if visible_block or summary_block:
            text = self._fit_recent_blocks(
                [visible_block, summary_block],
                max_chars=max_chars,
            )
            if text:
                return text
        return self._render_legacy_recent_context(entries, max_chars=max_chars)

    def _render_visible_recent_context(self, recent_raw_turns: list[dict], *, recent_mode: str) -> str:
        completed_turns = [
            dict(item)
            for item in recent_raw_turns
            if isinstance(item, dict) and str(item.get("status") or "completed").strip() == "completed"
        ]
        visible_items = self._turn_store.recent_visible_items(recent_mode)
        lines: list[str] = []
        for item in completed_turns[-visible_items:]:
            ts = str(item.get("timestamp") or "").strip()
            user_prompt = re.sub(r"\s+", " ", str(item.get("user_prompt") or "").strip())[:80]
            assistant_reply = re.sub(
                r"\s+",
                " ",
                str(item.get("assistant_reply_visible") or item.get("assistant_reply") or "").strip(),
            )[:120]
            process_summary = self._render_process_event_summary(item.get("process_events"))
            if not user_prompt and not assistant_reply:
                continue
            line = f"- [{ts}] 用户：{user_prompt}；助手：{assistant_reply}"
            if process_summary:
                line += f"；过程：{process_summary[:100]}"
            lines.append(line)
        if not lines:
            return ""
        return "【最近可见对话】\n" + "\n".join(lines)

    def _render_summary_pool_context(self, recent_summary_pool: list[dict], *, recent_mode: str) -> str:
        summary_items = self._turn_store.recent_summary_items(recent_mode)
        lines: list[str] = []
        for item in (recent_summary_pool or [])[-summary_items:]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "最近窗口摘要").strip()
            summary_text = re.sub(r"\s+", " ", str(item.get("user_summary") or item.get("summary_text") or "").strip())
            process_reflection = re.sub(r"\s+", " ", str(item.get("process_reflection") or "").strip())
            start_seq = int(item.get("window_start_seq") or 0)
            end_seq = int(item.get("window_end_seq") or 0)
            if not summary_text and not title:
                continue
            line = f"- [窗口 {start_seq}-{end_seq}] {title[:40]}：{summary_text[:140]}"
            if process_reflection:
                line += f"；过程反思：{process_reflection[:100]}"
            lines.append(line)
        if not lines:
            return ""
        return "【最近窗口摘要】\n" + "\n".join(lines)

    @staticmethod
    def _render_process_event_summary(process_events: list[dict] | None) -> str:
        if not isinstance(process_events, list):
            return ""
        pieces: list[str] = []
        for item in process_events:
            if not isinstance(item, dict):
                continue
            text = _LEADING_PROCESS_ORDINAL_RE.sub("", re.sub(r"\s+", " ", str(item.get("text") or "").strip())).strip()
            if not text:
                continue
            pieces.append(text[:60])
            if len(pieces) >= 2:
                break
        return " / ".join(pieces)

    def _fit_recent_blocks(self, blocks: list[str], *, max_chars: int) -> str:
        kept: list[str] = []
        current_len = 0
        for block in blocks:
            text = str(block or "").strip()
            if not text:
                continue
            sep_len = 2 if kept else 0
            allowed = max_chars - current_len - sep_len
            if allowed <= 0:
                break
            if len(text) > allowed:
                suffix = "\n..." if allowed > 4 else ""
                keep_len = max(0, allowed - len(suffix))
                text = text[:keep_len].rstrip()
                if suffix:
                    text = text.rstrip(".") + suffix
            kept.append(text)
            current_len += len(text) + sep_len
            if current_len >= max_chars:
                break
        return "\n\n".join(kept).strip()

    def _render_legacy_recent_context(self, entries: list[dict], max_chars: int) -> str:
        talk_lines = []
        mental_lines = []
        relation_lines = []
        other_lines = []
        recent_window = self._turn_store.recent_max_items()
        for item in entries[-(recent_window * 2):]:
            ts = str(item.get("timestamp") or "").strip()
            topic = str(item.get("topic") or "").strip()
            summary = str(item.get("summary") or "").strip()
            status = str(item.get("status") or "").strip()
            stream = str(item.get("memory_stream") or "talk").strip()
            if not summary and not topic:
                continue
            head = f"[{ts}] {topic}".strip()
            suffix = "（正在回复中）" if status == "replying" else ""
            line = f"- {head}{suffix}: {summary}" if summary and head else (f"- {summary}" if summary else f"- {head}{suffix}")
            if summary:
                if stream == "mental":
                    mental_lines.append(line)
                elif stream == "relationship_signal":
                    relation_lines.append(line)
                elif stream != "talk":
                    other_lines.append(line)
                else:
                    talk_lines.append(line)
            elif head:
                talk_lines.append(f"- {head}{suffix}")
        sections = []
        if talk_lines:
            sections.append("【对话短期记忆】\n" + "\n".join(talk_lines[-self._turn_store.recent_max_items():]))
        if mental_lines:
            sections.append("【最近在想什么】\n" + "\n".join(mental_lines[-4:]))
        if relation_lines:
            sections.append("【关系与情绪信号】\n" + "\n".join(relation_lines[-3:]))
        if other_lines:
            sections.append("【任务与其他信号】\n" + "\n".join(other_lines[-4:]))
        text = "\n\n".join(sections).strip()
        return text[-max_chars:] if len(text) > max_chars else text


__all__ = ["ChatRecentPromptAssembler"]
