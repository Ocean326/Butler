from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from agents_os.contracts import Invocation

from .channel_profiles import resolve_channel_profile


MODE_STATE_FILE = "mode_state.json"
CHAT_MAIN_MODE = "chat"
SHARE_MAIN_MODE = "share"
BRAINSTORM_MAIN_MODE = "brainstorm"
PROJECT_MAIN_MODE = "project"
BACKGROUND_MAIN_MODE = "bg"
PROJECT_PHASES = ("plan", "imp", "review")
MAIN_SCENE_MODES = (
    CHAT_MAIN_MODE,
    SHARE_MAIN_MODE,
    BRAINSTORM_MAIN_MODE,
    PROJECT_MAIN_MODE,
    BACKGROUND_MAIN_MODE,
)
PROJECT_REVIEW_PASS_HINTS = (
    "通过",
    "passed",
    "pass",
    "ok",
    "已满足",
    "验收通过",
    "可以进入下一阶段",
    "可进入下一阶段",
)
PROJECT_REVIEW_FAIL_HINTS = (
    "未通过",
    "不通过",
    "blocker",
    "阻塞",
    "缺口",
    "需要修改",
    "需修正",
    "未满足",
)
PROJECT_PHASE_IMPLEMENT_HINTS = (
    "实现",
    "开发",
    "修改代码",
    "写代码",
    "修复",
    "落代码",
    "补测试",
    "patch",
    "debug",
    "排查",
    "开始做",
    "动手做",
)
PROJECT_PHASE_REVIEW_HINTS = (
    "review",
    "评审",
    "复核",
    "验收",
    "检查风险",
    "找问题",
    "code review",
    "blocker",
    "风险",
)

MODE_RECENT_PROFILES: dict[str, dict[str, int]] = {
    "default": {"visible_items": 10, "summary_items": 5, "prompt_max_chars": 10000},
    CHAT_MAIN_MODE: {"visible_items": 10, "summary_items": 5, "prompt_max_chars": 10000},
    SHARE_MAIN_MODE: {"visible_items": 6, "summary_items": 3, "prompt_max_chars": 7000},
    "content_share": {"visible_items": 6, "summary_items": 3, "prompt_max_chars": 7000},
    BRAINSTORM_MAIN_MODE: {"visible_items": 5, "summary_items": 3, "prompt_max_chars": 7000},
    PROJECT_MAIN_MODE: {"visible_items": 6, "summary_items": 4, "prompt_max_chars": 8000},
    BACKGROUND_MAIN_MODE: {"visible_items": 4, "summary_items": 3, "prompt_max_chars": 6000},
    "maintenance": {"visible_items": 6, "summary_items": 4, "prompt_max_chars": 8000},
    "companion": {"visible_items": 8, "summary_items": 4, "prompt_max_chars": 9000},
}


@dataclass(slots=True, frozen=True)
class ChatSessionModeState:
    main_mode: str = CHAT_MAIN_MODE
    project_phase: str = ""
    project_next_phase: str = ""
    active_role: str = ""
    injection_tier: str = "standard"
    auto_route_reason: str = ""
    last_explicit_override: str = ""
    mode_artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_session_scope_id_from_invocation(invocation: Invocation) -> str:
    profile = resolve_channel_profile(invocation.channel)
    channel = str(profile.channel or invocation.channel or "").strip().lower()
    metadata = dict(invocation.metadata or {})
    if channel == "weixin":
        raw_scope_id = (
            str(invocation.session_id or "").strip()
            or str(metadata.get("weixin.conversation_key") or "").strip()
            or str(metadata.get("weixin.raw_session_ref") or "").strip()
        )
    elif channel == "feishu":
        raw_scope_id = (
            str(invocation.session_id or "").strip()
            or str(metadata.get("feishu.raw_session_ref") or "").strip()
        )
    elif channel == "cli":
        raw_scope_id = str(invocation.session_id or "").strip()
    else:
        raw_scope_id = str(invocation.session_id or "").strip()
        channel = "cli" if raw_scope_id else ""
    if not raw_scope_id or not channel:
        return ""
    if raw_scope_id.lower().startswith(f"{channel}:"):
        return raw_scope_id
    return f"{channel}:{raw_scope_id}"


def load_chat_session_mode_state(workspace: str, *, session_scope_id: str = "") -> ChatSessionModeState:
    path = _mode_state_path(workspace, session_scope_id=session_scope_id)
    if not path.exists():
        return ChatSessionModeState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ChatSessionModeState()
    if not isinstance(payload, Mapping):
        return ChatSessionModeState()
    main_mode = canonical_main_mode(payload.get("main_mode"))
    project_phase = canonical_project_phase(payload.get("project_phase"))
    project_next_phase = canonical_project_phase(payload.get("project_next_phase"))
    raw_artifacts = payload.get("mode_artifacts")
    artifacts = {}
    if isinstance(raw_artifacts, Mapping):
        for key, value in raw_artifacts.items():
            if isinstance(value, Mapping):
                artifacts[str(key)] = dict(value)
    return ChatSessionModeState(
        main_mode=main_mode,
        project_phase=project_phase,
        project_next_phase=project_next_phase,
        active_role=str(payload.get("active_role") or "").strip(),
        injection_tier=str(payload.get("injection_tier") or "standard").strip() or "standard",
        auto_route_reason=str(payload.get("auto_route_reason") or "").strip(),
        last_explicit_override=str(payload.get("last_explicit_override") or "").strip(),
        mode_artifacts=artifacts,
        updated_at=str(payload.get("updated_at") or "").strip(),
    )


def save_chat_session_mode_state(
    workspace: str,
    *,
    session_scope_id: str = "",
    state: ChatSessionModeState,
) -> None:
    path = _mode_state_path(workspace, session_scope_id=session_scope_id)
    payload = {
        **state.to_dict(),
        "main_mode": canonical_main_mode(state.main_mode),
        "project_phase": canonical_project_phase(state.project_phase),
        "project_next_phase": canonical_project_phase(state.project_next_phase),
        "updated_at": str(state.updated_at or _now_text()),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_chat_session_mode_state(workspace: str, *, session_scope_id: str = "") -> ChatSessionModeState:
    state = ChatSessionModeState(updated_at=_now_text())
    save_chat_session_mode_state(workspace, session_scope_id=session_scope_id, state=state)
    return state


def canonical_main_mode(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"", "default", "execution"}:
        return CHAT_MAIN_MODE
    if text in {"content_share"}:
        return SHARE_MAIN_MODE
    if text in MAIN_SCENE_MODES:
        return text
    return CHAT_MAIN_MODE


def canonical_project_phase(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in PROJECT_PHASES:
        return text
    return ""


def resolve_recent_mode(
    *,
    explicit_mode: str = "",
    intake_decision: Mapping[str, Any] | None = None,
) -> str:
    normalized_explicit = canonical_main_mode(explicit_mode)
    if normalized_explicit != CHAT_MAIN_MODE or str(explicit_mode or "").strip():
        return normalized_explicit
    intake_mode = str((intake_decision or {}).get("mode") or "").strip().lower()
    if intake_mode == "content_share":
        return SHARE_MAIN_MODE
    return CHAT_MAIN_MODE


def resolve_recent_profile(recent_mode: str, config: Mapping[str, Any] | None = None) -> dict[str, int]:
    normalized_mode = str(recent_mode or CHAT_MAIN_MODE).strip().lower() or CHAT_MAIN_MODE
    base = dict(MODE_RECENT_PROFILES.get(normalized_mode) or MODE_RECENT_PROFILES["default"])
    if not isinstance(config, Mapping):
        return base
    memory_cfg = config.get("memory") if isinstance(config.get("memory"), Mapping) else {}
    talk_recent = memory_cfg.get("talk_recent") if isinstance(memory_cfg.get("talk_recent"), Mapping) else {}
    mode_recent = memory_cfg.get("mode_recent_profiles") if isinstance(memory_cfg.get("mode_recent_profiles"), Mapping) else {}
    overrides = mode_recent.get(normalized_mode) if isinstance(mode_recent.get(normalized_mode), Mapping) else {}
    merged = {**base, **{str(k): v for k, v in dict(talk_recent).items() if k in {"inject_visible_items", "inject_summary_items", "prompt_max_chars"}}}
    if overrides:
        merged.update({str(k): v for k, v in dict(overrides).items()})
    visible_items = _bounded_int(
        overrides.get("inject_visible_items", overrides.get("visible_items", merged.get("inject_visible_items", merged.get("visible_items", base["visible_items"])))),
        default=base["visible_items"],
        minimum=1,
        maximum=50,
    )
    summary_items = _bounded_int(
        overrides.get("inject_summary_items", overrides.get("summary_items", merged.get("inject_summary_items", merged.get("summary_items", base["summary_items"])))),
        default=base["summary_items"],
        minimum=1,
        maximum=20,
    )
    prompt_max_chars = _bounded_int(
        overrides.get("prompt_max_chars", merged.get("prompt_max_chars", base["prompt_max_chars"])),
        default=base["prompt_max_chars"],
        minimum=1000,
        maximum=200000,
    )
    return {
        "visible_items": visible_items,
        "summary_items": summary_items,
        "prompt_max_chars": prompt_max_chars,
    }


def render_mode_artifact_block(
    state: ChatSessionModeState | Mapping[str, Any] | None,
    *,
    recent_mode: str,
) -> str:
    resolved_state = _coerce_state(state)
    mode_key = canonical_main_mode(recent_mode)
    artifacts = dict(resolved_state.mode_artifacts or {})
    artifact = dict(artifacts.get(mode_key) or {})
    if not artifact:
        return ""
    if mode_key == PROJECT_MAIN_MODE:
        lines = ["【project_artifact】"]
        phase = canonical_project_phase(
            artifact.get("next_phase") or resolved_state.project_phase or resolved_state.project_next_phase
        ) or "plan"
        lines.append(f"- 当前默认阶段：{phase}")
        goal = str(artifact.get("goal") or "").strip()
        if goal:
            lines.append(f"- 目标：{goal[:180]}")
        latest_conclusion = str(artifact.get("latest_conclusion") or "").strip()
        if latest_conclusion:
            lines.append(f"- 最近结论：{latest_conclusion[:220]}")
        open_question = str(artifact.get("open_question") or "").strip()
        if open_question:
            lines.append(f"- 未决点：{open_question[:180]}")
        next_action = str(artifact.get("next_action") or "").strip()
        if next_action:
            lines.append(f"- 下一步：{next_action[:180]}")
        return "\n".join(lines)
    summary = str(artifact.get("summary") or artifact.get("latest_conclusion") or "").strip()
    if not summary:
        return ""
    labels = {
        SHARE_MAIN_MODE: "【share_artifact】",
        BRAINSTORM_MAIN_MODE: "【brainstorm_artifact】",
        BACKGROUND_MAIN_MODE: "【bg_artifact】",
    }
    title = labels.get(mode_key)
    if not title:
        return ""
    lines = [title, f"- 最近结论：{summary[:220]}"]
    next_action = str(artifact.get("next_action") or "").strip()
    if next_action:
        lines.append(f"- 下一步：{next_action[:180]}")
    return "\n".join(lines)


def update_state_after_turn(
    state: ChatSessionModeState | Mapping[str, Any] | None,
    *,
    user_text: str,
    assistant_reply: str,
    explicit_mode: str = "",
    explicit_project_phase: str = "",
    active_role: str = "",
    injection_tier: str = "standard",
    auto_route_reason: str = "",
    explicit_override_source: str = "",
) -> ChatSessionModeState:
    resolved = _coerce_state(state)
    main_mode = canonical_main_mode(explicit_mode or resolved.main_mode)
    project_phase = canonical_project_phase(explicit_project_phase or resolved.project_phase or resolved.project_next_phase)
    artifacts = {str(key): dict(value) for key, value in dict(resolved.mode_artifacts or {}).items()}
    compact_user = _compact_text(user_text, limit=220)
    lead = _extract_reply_lead(assistant_reply, max_chars=260)
    next_action = _infer_next_action(assistant_reply)
    open_question = _infer_open_question(assistant_reply)
    next_phase = resolved.project_next_phase

    if main_mode == PROJECT_MAIN_MODE:
        current_phase = project_phase or "plan"
        next_phase = _advance_project_phase(current_phase, user_text, assistant_reply)
        existing = dict(artifacts.get(PROJECT_MAIN_MODE) or {})
        goal = str(existing.get("goal") or "").strip()
        if not goal:
            goal = compact_user
        artifacts[PROJECT_MAIN_MODE] = {
            **existing,
            "goal": goal[:180],
            "current_phase": current_phase,
            "next_phase": next_phase,
            "latest_conclusion": lead,
            "latest_user_prompt": compact_user,
            "open_question": open_question,
            "next_action": next_action,
            "updated_at": _now_text(),
        }
        return ChatSessionModeState(
            main_mode=PROJECT_MAIN_MODE,
            project_phase=next_phase,
            project_next_phase=next_phase,
            active_role=active_role or resolved.active_role,
            injection_tier=str(injection_tier or resolved.injection_tier or "standard"),
            auto_route_reason=auto_route_reason or resolved.auto_route_reason,
            last_explicit_override=explicit_override_source or resolved.last_explicit_override,
            mode_artifacts=artifacts,
            updated_at=_now_text(),
        )

    if main_mode in {SHARE_MAIN_MODE, BRAINSTORM_MAIN_MODE, BACKGROUND_MAIN_MODE}:
        existing = dict(artifacts.get(main_mode) or {})
        artifacts[main_mode] = {
            **existing,
            "summary": lead,
            "latest_user_prompt": compact_user,
            "next_action": next_action,
            "updated_at": _now_text(),
        }
    return ChatSessionModeState(
        main_mode=main_mode,
        project_phase=canonical_project_phase(resolved.project_phase),
        project_next_phase=canonical_project_phase(next_phase),
        active_role=active_role or resolved.active_role,
        injection_tier=str(injection_tier or resolved.injection_tier or "standard"),
        auto_route_reason=auto_route_reason or resolved.auto_route_reason,
        last_explicit_override=explicit_override_source or resolved.last_explicit_override,
        mode_artifacts=artifacts,
        updated_at=_now_text(),
    )


def describe_mode_switch(main_mode: str, project_phase: str = "") -> str:
    mode = canonical_main_mode(main_mode)
    if mode == CHAT_MAIN_MODE:
        return "已回到默认 `chat` 模式，后续按普通工作聊天处理。发送 `/share`、`/brainstorm`、`/project` 或 `/bg` 可切换。"
    if mode == SHARE_MAIN_MODE:
        return "已切到 `share` 模式，后续默认按分享承接和整理处理。发送 `/reset` 返回默认 `chat`。"
    if mode == BRAINSTORM_MAIN_MODE:
        return "已切到 `brainstorm` 模式，后续默认按发散和迁移思考处理。发送 `/reset` 返回默认 `chat`。"
    if mode == PROJECT_MAIN_MODE:
        phase = canonical_project_phase(project_phase) or "plan"
        return (
            f"已进入 `project` 模式，当前默认阶段是 `{phase}`。"
            "后续会按 `plan -> imp -> review` 循环推进；发送 `/plan`、`/imp`、`/review` 可显式覆盖。"
        )
    return "已切到 `bg` 模式，后续默认按后台入口协商处理。发送 `/status` 查询进度，发送 `/reset` 返回默认 `chat`。"


def project_phase_from_state(state: ChatSessionModeState | Mapping[str, Any] | None) -> str:
    resolved = _coerce_state(state)
    return canonical_project_phase(resolved.project_phase or resolved.project_next_phase) or "plan"


def _mode_state_path(workspace: str, *, session_scope_id: str = "") -> Path:
    from .memory_runtime.recent_scope_paths import resolve_recent_scope_dir

    return resolve_recent_scope_dir(workspace, session_scope_id=session_scope_id) / MODE_STATE_FILE


def _coerce_state(state: ChatSessionModeState | Mapping[str, Any] | None) -> ChatSessionModeState:
    if isinstance(state, ChatSessionModeState):
        return state
    if isinstance(state, Mapping):
        return ChatSessionModeState(
            main_mode=canonical_main_mode(state.get("main_mode")),
            project_phase=canonical_project_phase(state.get("project_phase")),
            project_next_phase=canonical_project_phase(state.get("project_next_phase")),
            active_role=str(state.get("active_role") or "").strip(),
            injection_tier=str(state.get("injection_tier") or "standard").strip() or "standard",
            auto_route_reason=str(state.get("auto_route_reason") or "").strip(),
            last_explicit_override=str(state.get("last_explicit_override") or "").strip(),
            mode_artifacts={
                str(key): dict(value)
                for key, value in dict(state.get("mode_artifacts") or {}).items()
                if isinstance(value, Mapping)
            },
            updated_at=str(state.get("updated_at") or "").strip(),
        )
    return ChatSessionModeState()


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except Exception:
        return default


def _extract_reply_lead(text: str, *, max_chars: int = 240) -> str:
    lines = [str(item).strip(" -*\t") for item in str(text or "").splitlines()]
    for line in lines:
        compact = _compact_text(line, limit=max_chars)
        if not compact:
            continue
        if compact.startswith("#"):
            continue
        if compact.startswith("【") and compact.endswith("】"):
            continue
        return compact
    return _compact_text(text, limit=max_chars)


def _infer_next_action(text: str) -> str:
    patterns = (
        r"(?:下一步|接下来|建议下一轮|后续)\s*[：:]\s*([^\n]+)",
        r"(?:下一步|接下来|后续)\s*[-*]\s*([^\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, str(text or ""), flags=re.IGNORECASE)
        if match:
            return _compact_text(match.group(1), limit=180)
    return ""


def _infer_open_question(text: str) -> str:
    patterns = (
        r"(?:未决点|未解决|待确认|开放问题)\s*[：:]\s*([^\n]+)",
        r"(?:问题|风险)\s*[-*]\s*([^\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, str(text or ""), flags=re.IGNORECASE)
        if match:
            return _compact_text(match.group(1), limit=180)
    return ""


def _advance_project_phase(current_phase: str, user_text: str, assistant_reply: str) -> str:
    phase = canonical_project_phase(current_phase) or "plan"
    normalized_user = str(user_text or "").lower()
    normalized_reply = str(assistant_reply or "").lower()
    review_requested = any(token in normalized_user for token in (item.lower() for item in PROJECT_PHASE_REVIEW_HINTS))
    implement_requested = any(token in normalized_user for token in (item.lower() for item in PROJECT_PHASE_IMPLEMENT_HINTS))
    if phase == "plan":
        if implement_requested and not review_requested:
            return "imp"
        return "plan"
    if phase == "imp":
        if review_requested:
            return "review"
        return "imp"
    if any(token in normalized_reply for token in (item.lower() for item in PROJECT_REVIEW_FAIL_HINTS)):
        return "imp"
    if any(token in normalized_reply for token in (item.lower() for item in PROJECT_REVIEW_PASS_HINTS)):
        return "plan"
    if review_requested:
        return "review"
    if implement_requested:
        return "imp"
    return "review"


def _compact_text(text: str, *, limit: int = 220) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


__all__ = [
    "BACKGROUND_MAIN_MODE",
    "BRAINSTORM_MAIN_MODE",
    "CHAT_MAIN_MODE",
    "ChatSessionModeState",
    "MAIN_SCENE_MODES",
    "MODE_RECENT_PROFILES",
    "PROJECT_MAIN_MODE",
    "PROJECT_PHASES",
    "SHARE_MAIN_MODE",
    "canonical_main_mode",
    "canonical_project_phase",
    "describe_mode_switch",
    "load_chat_session_mode_state",
    "project_phase_from_state",
    "render_mode_artifact_block",
    "reset_chat_session_mode_state",
    "resolve_recent_mode",
    "resolve_recent_profile",
    "resolve_session_scope_id_from_invocation",
    "save_chat_session_mode_state",
    "update_state_after_turn",
]
