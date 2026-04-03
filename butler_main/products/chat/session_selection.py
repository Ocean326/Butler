from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .session_modes import CHAT_MAIN_MODE, canonical_main_mode


CHAT_SESSION_STATE_FILE = "chat_session_state.json"
FOLLOWUP_CONTINUATION_HINTS = (
    "继续",
    "接着",
    "那就",
    "就这个",
    "这个",
    "那个",
    "这样",
    "按这个",
    "照这个",
    "改成",
    "换成",
    "用",
    "先",
    "然后",
    "再",
    "顺手",
    "顺便",
    "别",
    "不要",
    "不用",
    "还有",
    "以及",
    "另外",
    "刚才",
    "上一个",
    "上一轮",
    "上面",
)
NEW_TASK_HINTS = (
    "新任务",
    "全新任务",
    "全新情景",
    "重新开始",
    "从头开始",
    "切换话题",
    "换个话题",
    "另一个问题",
    "另一个任务",
    "忽略之前",
    "new task",
    "start over",
    "new topic",
    "reset context",
)
STANDALONE_SHORT_QUESTION_HINTS = (
    "今天",
    "明天",
    "后天",
    "下午",
    "上午",
    "晚上",
    "几点",
    "什么时候",
    "日程",
    "安排",
    "天气",
    "提醒",
    "会议",
)
_CJK_SEGMENT_RE = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]{2,}")


@dataclass(slots=True, frozen=True)
class ChatSessionState:
    active_chat_session_id: str = ""
    topic_anchor: str = ""
    last_user_prompt: str = ""
    last_mode: str = CHAT_MAIN_MODE
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class ChatSessionSelection:
    action: str = "continue_current"
    confidence: str = "medium"
    chat_session_id: str = ""
    reason_flags: tuple[str, ...] = field(default_factory=tuple)

    def reason_flags_text(self) -> str:
        return ",".join(flag for flag in self.reason_flags if str(flag).strip())


def load_chat_session_state(workspace: str, *, session_scope_id: str = "") -> ChatSessionState:
    path = _chat_session_state_path(workspace, session_scope_id=session_scope_id)
    if not path.exists():
        return ChatSessionState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ChatSessionState()
    if not isinstance(payload, Mapping):
        return ChatSessionState()
    return ChatSessionState(
        active_chat_session_id=str(payload.get("active_chat_session_id") or "").strip(),
        topic_anchor=str(payload.get("topic_anchor") or "").strip(),
        last_user_prompt=str(payload.get("last_user_prompt") or "").strip(),
        last_mode=canonical_main_mode(payload.get("last_mode")),
        updated_at=str(payload.get("updated_at") or "").strip(),
    )


def save_chat_session_state(
    workspace: str,
    *,
    session_scope_id: str = "",
    state: ChatSessionState,
) -> None:
    path = _chat_session_state_path(workspace, session_scope_id=session_scope_id)
    payload = {
        **state.to_dict(),
        "last_mode": canonical_main_mode(state.last_mode),
        "updated_at": str(state.updated_at or _now_text()),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_active_chat_session_id(workspace: str, *, session_scope_id: str = "") -> str:
    return str(load_chat_session_state(workspace, session_scope_id=session_scope_id).active_chat_session_id or "").strip()


def build_chat_session_state_after_turn(
    state: ChatSessionState | Mapping[str, Any] | None,
    *,
    user_text: str,
    main_mode: str,
    session_action: str = "continue_current",
    chat_session_id: str = "",
) -> ChatSessionState:
    current = _coerce_state(state)
    next_session_id = str(chat_session_id or current.active_chat_session_id or "").strip()
    if not next_session_id:
        next_session_id = new_chat_session_id()
    compact_user = compact_text(user_text, limit=180)
    topic_anchor = str(current.topic_anchor or "").strip()
    if session_action == "reopen_new_session" or not topic_anchor:
        topic_anchor = compact_user
    return ChatSessionState(
        active_chat_session_id=next_session_id,
        topic_anchor=topic_anchor,
        last_user_prompt=compact_user,
        last_mode=canonical_main_mode(main_mode),
        updated_at=_now_text(),
    )


def select_chat_session(
    user_text: str,
    *,
    current_state: ChatSessionState | Mapping[str, Any] | None,
    mode_state: Mapping[str, Any] | None = None,
    explicit_lock: bool = False,
) -> ChatSessionSelection:
    state = _coerce_state(current_state)
    compact = compact_text(user_text)
    current_session_id = str(state.active_chat_session_id or "").strip()
    selected_session_id = current_session_id or new_chat_session_id()
    if explicit_lock:
        return ChatSessionSelection(
            action="continue_current",
            confidence="high",
            chat_session_id=selected_session_id,
            reason_flags=("explicit_lock",) if current_session_id else ("explicit_lock", "bootstrap_session"),
        )
    if not compact:
        return ChatSessionSelection(
            action="continue_current",
            confidence="low",
            chat_session_id=selected_session_id,
            reason_flags=("empty_prompt",) if current_session_id else ("empty_prompt", "bootstrap_session"),
        )
    if is_new_task_prompt(compact):
        return ChatSessionSelection(
            action="reopen_new_session",
            confidence="high",
            chat_session_id=new_chat_session_id(),
            reason_flags=("explicit_new_task",),
        )
    reference_texts = _reference_texts(state, mode_state)
    if looks_like_followup_prompt(compact):
        return ChatSessionSelection(
            action="continue_current",
            confidence="high",
            chat_session_id=selected_session_id,
            reason_flags=("short_followup",) if current_session_id else ("short_followup", "bootstrap_session"),
        )
    if not reference_texts:
        return ChatSessionSelection(
            action="continue_current",
            confidence="medium",
            chat_session_id=selected_session_id,
            reason_flags=("no_reference_topic",) if current_session_id else ("no_reference_topic", "bootstrap_session"),
        )
    overlap = max(topic_overlap_score(compact, candidate) for candidate in reference_texts)
    if overlap >= 0.36:
        return ChatSessionSelection(
            action="continue_current",
            confidence="high",
            chat_session_id=selected_session_id,
            reason_flags=("topic_overlap_high",) if current_session_id else ("topic_overlap_high", "bootstrap_session"),
        )
    if overlap >= 0.18:
        return ChatSessionSelection(
            action="continue_current",
            confidence="medium",
            chat_session_id=selected_session_id,
            reason_flags=("topic_overlap_low",) if current_session_id else ("topic_overlap_low", "bootstrap_session"),
        )
    if looks_like_standalone_short_question(compact):
        return ChatSessionSelection(
            action="reopen_new_session",
            confidence="medium",
            chat_session_id=new_chat_session_id(),
            reason_flags=("standalone_short_question",),
        )
    if len(compact) <= 18:
        return ChatSessionSelection(
            action="continue_current",
            confidence="low",
            chat_session_id=selected_session_id,
            reason_flags=("short_ambiguous",) if current_session_id else ("short_ambiguous", "bootstrap_session"),
        )
    return ChatSessionSelection(
        action="reopen_new_session",
        confidence="medium",
        chat_session_id=new_chat_session_id(),
        reason_flags=("topic_shift_no_overlap",),
    )


def compact_text(text: str, *, limit: int = 280) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit]


def is_new_task_prompt(user_text: str) -> bool:
    text = str(user_text or "").strip().lower()
    return bool(text) and any(hint in text for hint in NEW_TASK_HINTS)


def looks_like_followup_prompt(user_text: str) -> bool:
    compact = compact_text(user_text)
    if not compact or is_new_task_prompt(compact):
        return False
    lowered = compact.lower()
    if len(lowered) <= 40 and any(hint in lowered for hint in FOLLOWUP_CONTINUATION_HINTS):
        return True
    return bool(
        len(lowered) <= 24
        and re.match(r"^(那|就|先|再|按|照|把|改成|换成|用|别|不要|不用|继续|接着|然后|另外|刚才|上面)", compact)
    )


def looks_like_standalone_short_question(user_text: str) -> bool:
    compact = compact_text(user_text)
    if not compact or looks_like_followup_prompt(compact) or is_new_task_prompt(compact):
        return False
    lowered = compact.lower()
    if len(lowered) > 32:
        return False
    if "?" in lowered or "？" in lowered:
        return True
    return any(hint in lowered for hint in STANDALONE_SHORT_QUESTION_HINTS)


def topic_overlap_score(left: str, right: str) -> float:
    left_tokens = _extract_topic_tokens(left)
    right_tokens = _extract_topic_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    denominator = max(1, min(len(left_tokens), len(right_tokens)))
    return overlap / denominator


def new_chat_session_id() -> str:
    return f"chat_{uuid.uuid4().hex[:12]}"


def _chat_session_state_path(workspace: str, *, session_scope_id: str = "") -> Path:
    from .memory_runtime.recent_scope_paths import resolve_recent_scope_dir

    return resolve_recent_scope_dir(workspace, session_scope_id=session_scope_id) / CHAT_SESSION_STATE_FILE


def _coerce_state(state: ChatSessionState | Mapping[str, Any] | None) -> ChatSessionState:
    if isinstance(state, ChatSessionState):
        return state
    if isinstance(state, Mapping):
        return ChatSessionState(
            active_chat_session_id=str(state.get("active_chat_session_id") or "").strip(),
            topic_anchor=str(state.get("topic_anchor") or "").strip(),
            last_user_prompt=str(state.get("last_user_prompt") or "").strip(),
            last_mode=canonical_main_mode(state.get("last_mode")),
            updated_at=str(state.get("updated_at") or "").strip(),
        )
    return ChatSessionState()


def _reference_texts(state: ChatSessionState, mode_state: Mapping[str, Any] | None) -> list[str]:
    candidates: list[str] = []
    for item in (
        state.topic_anchor,
        state.last_user_prompt,
    ):
        text = compact_text(item, limit=220)
        if text and text not in candidates:
            candidates.append(text)
    artifacts = dict((mode_state or {}).get("mode_artifacts") or {})
    for payload in artifacts.values():
        if not isinstance(payload, Mapping):
            continue
        for key in ("goal", "latest_user_prompt", "latest_conclusion", "summary", "open_question", "next_action"):
            text = compact_text(str(payload.get(key) or ""), limit=220)
            if text and text not in candidates:
                candidates.append(text)
    return candidates


def _extract_topic_tokens(text: str) -> set[str]:
    normalized = compact_text(text, limit=320).lower()
    tokens: set[str] = set()
    for token in _LATIN_TOKEN_RE.findall(normalized):
        if len(token) >= 2:
            tokens.add(token)
    for segment in _CJK_SEGMENT_RE.findall(normalized):
        if len(segment) <= 4:
            tokens.add(segment)
        for index in range(len(segment) - 1):
            tokens.add(segment[index : index + 2])
    return tokens


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


__all__ = [
    "CHAT_SESSION_STATE_FILE",
    "ChatSessionSelection",
    "ChatSessionState",
    "FOLLOWUP_CONTINUATION_HINTS",
    "NEW_TASK_HINTS",
    "build_chat_session_state_after_turn",
    "compact_text",
    "is_new_task_prompt",
    "load_chat_session_state",
    "looks_like_followup_prompt",
    "looks_like_standalone_short_question",
    "new_chat_session_id",
    "resolve_active_chat_session_id",
    "save_chat_session_state",
    "select_chat_session",
    "topic_overlap_score",
]
