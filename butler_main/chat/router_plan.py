from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from butler_main.agents_os.skills import resolve_skill_collection_id

from .session_selection import (
    compact_text,
    is_new_task_prompt,
    looks_like_followup_prompt,
)
from .session_modes import (
    BACKGROUND_MAIN_MODE,
    BRAINSTORM_MAIN_MODE,
    CHAT_MAIN_MODE,
    PROJECT_MAIN_MODE,
    SHARE_MAIN_MODE,
    canonical_main_mode,
    canonical_project_phase,
    project_phase_from_state,
)


INJECTION_TIERS = ("minimal", "standard", "extended")
CAPABILITY_POLICIES = ("disabled", "conditional", "enabled")

_SHARE_HINTS = (
    "润色",
    "改写",
    "转述",
    "转成",
    "整理成",
    "总结成",
    "提炼",
    "分享",
    "转发",
    "发给",
    "发出去",
    "朋友圈",
    "文案",
    "摘要",
    "纪要",
)
_BRAINSTORM_HINTS = (
    "brainstorm",
    "头脑风暴",
    "发散",
    "想法",
    "方向",
    "灵感",
    "创意",
    "点子",
    "备选方案",
    "可能性",
    "路线",
)
_PROJECT_HINTS = (
    "项目",
    "方案",
    "规划",
    "计划",
    "排期",
    "里程碑",
    "拆解",
    "实现",
    "开发",
    "修复",
    "review",
    "评审",
    "复核",
    "验收",
    "迭代",
)
_PROJECT_PLAN_HINTS = (
    "规划",
    "计划",
    "拆解",
    "roadmap",
    "里程碑",
    "排期",
    "先做什么",
    "下一步怎么做",
)
_PROJECT_IMPLEMENT_HINTS = (
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
)
_PROJECT_REVIEW_HINTS = (
    "review",
    "评审",
    "复核",
    "验收",
    "检查风险",
    "找问题",
    "code review",
)
_BACKGROUND_HINTS = (
    "后台任务",
    "后台推进",
    "持续推进",
    "长任务",
    "异步",
    "挂后台",
    "启动任务",
    "先协商",
)
_EXTENDED_HINTS = (
    "并行",
    "协作",
    "拆任务",
    "subagent",
    "sub-agent",
    "agent team",
    "代码",
    "仓库",
    "文件",
    "目录",
    "命令",
    "测试",
    "报错",
    "http://",
    "https://",
    "pdf",
    "图片",
    "截图",
)
_ROLE_DEFINITIONS: dict[str, dict[str, str]] = {
    "chat_worker": {
        "title": "通用工作聊天",
        "summary": "默认工作聊天角色，优先直接回答、收敛问题、推进当前轮决策。",
        "style": "保持务实、直接、少术语暴露；没有执行过的动作不能假装已执行。",
    },
    "share_editor": {
        "title": "分享整理编辑",
        "summary": "面向分享、转发、提炼、润色和结构化整理，不默认展开工程执行。",
        "style": "优先产出可直接发送的文本、提纲、摘要或改写稿。",
    },
    "brainstorm_facilitator": {
        "title": "发散与方向生成",
        "summary": "面向发散、迁移和方向生成，先给方向簇，再收敛值得继续推进的少数选项。",
        "style": "优先比较路线与取舍，不急着假定唯一实现路径。",
    },
    "project_planner": {
        "title": "项目规划",
        "summary": "把目标拆成阶段、约束、风险和下一步，默认先规划再进入实现。",
        "style": "优先输出阶段目标、边界和可执行下一步。",
    },
    "project_implementer": {
        "title": "项目实现",
        "summary": "面向落地与推进，允许进入较强执行语境，并保留工程协作能力入口。",
        "style": "优先给出可执行方案、关键变更点、验证路径和阻塞项。",
    },
    "project_reviewer": {
        "title": "项目复核",
        "summary": "面向 review、验收、风险与缺口识别，优先找问题和残余风险。",
        "style": "先判断完成度与风险，再给是否通过和后续建议。",
    },
    "bg_clarifier": {
        "title": "后台入口澄清",
        "summary": "面向后台协商、边界澄清和启动条件整理，不直接展开长链执行。",
        "style": "优先澄清目标、边界、验收和启动条件。",
    },
}


@dataclass(slots=True, frozen=True)
class RouterCompilePlan:
    intent_id: str
    main_mode: str
    role_id: str
    injection_tier: str
    project_phase: str = ""
    recent_profile_key: str = CHAT_MAIN_MODE
    skill_collection_id: str = ""
    capability_policy: str = "conditional"
    explicit_override_source: str = ""
    auto_route_reason: str = ""
    router_session_action: str = "continue_current"
    router_session_confidence: str = "medium"
    router_session_reason_flags: str = ""
    chat_session_id: str = ""

    def to_metadata(self) -> dict[str, str]:
        return {
            "router_intent_id": self.intent_id,
            "chat_main_mode": self.main_mode,
            "chat_role_id": self.role_id,
            "chat_injection_tier": self.injection_tier,
            "chat_project_phase": self.project_phase,
            "chat_recent_mode": self.recent_profile_key,
            "skill_collection_id": self.skill_collection_id,
            "chat_capability_policy": self.capability_policy,
            "router_explicit_override_source": self.explicit_override_source,
            "router_auto_route_reason": self.auto_route_reason,
            "router_session_action": self.router_session_action,
            "router_session_confidence": self.router_session_confidence,
            "router_session_reason_flags": self.router_session_reason_flags,
            "chat_session_id": self.chat_session_id,
        }


def resolve_router_compile_plan(
    user_text: str,
    *,
    mode_state: Mapping[str, Any] | None = None,
    explicit_main_mode: str = "",
    explicit_project_phase: str = "",
    explicit_override_source: str = "",
    runtime_cli: str = "",
    router_session_action: str = "",
    router_session_confidence: str = "",
    router_session_reason_flags: str = "",
    chat_session_id: str = "",
) -> RouterCompilePlan:
    text = compact_text(user_text)
    sticky_mode = canonical_main_mode((mode_state or {}).get("main_mode"))
    sticky_phase = project_phase_from_state(mode_state or {})
    override_source = str(explicit_override_source or "").strip()
    selected_mode = CHAT_MAIN_MODE
    selected_phase = ""
    route_reason = ""

    if override_source == "slash_command":
        selected_mode = canonical_main_mode(explicit_main_mode) or sticky_mode or CHAT_MAIN_MODE
        selected_phase = canonical_project_phase(explicit_project_phase) or (
            sticky_phase if selected_mode == PROJECT_MAIN_MODE else ""
        )
        route_reason = f"explicit:{override_source}"
    elif override_source == "sticky_mode":
        if sticky_mode != CHAT_MAIN_MODE and not is_new_task_prompt(text):
            selected_mode = sticky_mode
            selected_phase = (
                canonical_project_phase(explicit_project_phase)
                or sticky_phase
                or ("plan" if sticky_mode == PROJECT_MAIN_MODE else "")
            )
            route_reason = "sticky_mode_continuation"
        else:
            selected_mode, selected_phase, route_reason = _auto_route_mode(
                text,
                sticky_mode=sticky_mode,
                sticky_phase=sticky_phase,
            )
    else:
        selected_mode, selected_phase, route_reason = _auto_route_mode(
            text,
            sticky_mode=sticky_mode,
            sticky_phase=sticky_phase,
        )

    selected_mode = canonical_main_mode(selected_mode)
    selected_phase = canonical_project_phase(selected_phase)
    role_id = _role_id_for_mode(selected_mode, selected_phase)
    capability_policy = _capability_policy_for_mode(selected_mode, selected_phase)
    injection_tier = _injection_tier_for_mode(
        text,
        main_mode=selected_mode,
        project_phase=selected_phase,
        capability_policy=capability_policy,
    )
    recent_profile_key = selected_mode or CHAT_MAIN_MODE
    skill_collection_id = str(
        resolve_skill_collection_id(recent_mode=recent_profile_key, runtime_cli=str(runtime_cli or "").strip())
        or ""
    ).strip()
    return RouterCompilePlan(
        intent_id=_intent_id_for_mode(selected_mode, selected_phase),
        main_mode=selected_mode,
        role_id=role_id,
        injection_tier=injection_tier,
        project_phase=selected_phase,
        recent_profile_key=recent_profile_key,
        skill_collection_id=skill_collection_id,
        capability_policy=capability_policy,
        explicit_override_source=override_source,
        auto_route_reason=route_reason,
        router_session_action=str(router_session_action or "continue_current").strip() or "continue_current",
        router_session_confidence=str(router_session_confidence or "medium").strip() or "medium",
        router_session_reason_flags=str(router_session_reason_flags or "").strip(),
        chat_session_id=str(chat_session_id or "").strip(),
    )


def render_role_prompt(role_id: str) -> str:
    definition = dict(_ROLE_DEFINITIONS.get(str(role_id or "").strip()) or {})
    if not definition:
        return ""
    return "\n".join(
        [
            f"【本轮角色】{role_id}",
            f"- 标题：{definition.get('title') or role_id}",
            f"- 职责：{definition.get('summary') or ''}",
            f"- 输出方式：{definition.get('style') or ''}",
        ]
    ).strip()


def canonical_injection_tier(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in INJECTION_TIERS:
        return text
    return "standard"


def canonical_capability_policy(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in CAPABILITY_POLICIES:
        return text
    return "conditional"


def _auto_route_mode(text: str, *, sticky_mode: str, sticky_phase: str) -> tuple[str, str, str]:
    lowered = str(text or "").lower()
    if sticky_mode != CHAT_MAIN_MODE and looks_like_followup_prompt(text):
        return sticky_mode, (sticky_phase if sticky_mode == PROJECT_MAIN_MODE else ""), "sticky_short_followup"
    if any(token in lowered for token in _BACKGROUND_HINTS):
        return BACKGROUND_MAIN_MODE, "", "auto:bg_keywords"
    if any(token in lowered for token in _PROJECT_REVIEW_HINTS):
        return PROJECT_MAIN_MODE, "review", "auto:project_review_keywords"
    if any(token in lowered for token in _PROJECT_IMPLEMENT_HINTS):
        return PROJECT_MAIN_MODE, "imp", "auto:project_implement_keywords"
    if any(token in lowered for token in _PROJECT_PLAN_HINTS):
        return PROJECT_MAIN_MODE, "plan", "auto:project_plan_keywords"
    if any(token in lowered for token in _BRAINSTORM_HINTS):
        return BRAINSTORM_MAIN_MODE, "", "auto:brainstorm_keywords"
    if any(token in lowered for token in _SHARE_HINTS):
        return SHARE_MAIN_MODE, "", "auto:share_keywords"
    if any(token in lowered for token in _PROJECT_HINTS):
        return PROJECT_MAIN_MODE, (sticky_phase if sticky_mode == PROJECT_MAIN_MODE else "plan"), "auto:project_keywords"
    if sticky_mode != CHAT_MAIN_MODE and not is_new_task_prompt(text):
        return sticky_mode, (sticky_phase if sticky_mode == PROJECT_MAIN_MODE else ""), "sticky_mode_fallback"
    return CHAT_MAIN_MODE, "", "auto:default_chat"


def _role_id_for_mode(main_mode: str, project_phase: str) -> str:
    if main_mode == SHARE_MAIN_MODE:
        return "share_editor"
    if main_mode == BRAINSTORM_MAIN_MODE:
        return "brainstorm_facilitator"
    if main_mode == BACKGROUND_MAIN_MODE:
        return "bg_clarifier"
    if main_mode == PROJECT_MAIN_MODE:
        phase = canonical_project_phase(project_phase) or "plan"
        if phase == "imp":
            return "project_implementer"
        if phase == "review":
            return "project_reviewer"
        return "project_planner"
    return "chat_worker"


def _intent_id_for_mode(main_mode: str, project_phase: str) -> str:
    if main_mode == PROJECT_MAIN_MODE:
        return f"project_{canonical_project_phase(project_phase) or 'plan'}"
    return main_mode or CHAT_MAIN_MODE


def _capability_policy_for_mode(main_mode: str, project_phase: str) -> str:
    if main_mode in {SHARE_MAIN_MODE, BRAINSTORM_MAIN_MODE, BACKGROUND_MAIN_MODE}:
        return "disabled"
    if main_mode == PROJECT_MAIN_MODE:
        return "enabled" if canonical_project_phase(project_phase) == "imp" else "disabled"
    return "conditional"


def _injection_tier_for_mode(
    text: str,
    *,
    main_mode: str,
    project_phase: str,
    capability_policy: str,
) -> str:
    lowered = str(text or "").lower()
    if main_mode in {SHARE_MAIN_MODE, BACKGROUND_MAIN_MODE}:
        return "minimal" if len(lowered) <= 160 else "standard"
    if main_mode == PROJECT_MAIN_MODE and canonical_project_phase(project_phase) in {"imp", "review"}:
        return "extended"
    if capability_policy == "enabled":
        return "extended"
    if len(lowered) >= 280 or any(token in lowered for token in _EXTENDED_HINTS):
        return "extended"
    if looks_like_followup_prompt(text):
        return "minimal"
    return "standard"


__all__ = [
    "CAPABILITY_POLICIES",
    "INJECTION_TIERS",
    "RouterCompilePlan",
    "canonical_capability_policy",
    "canonical_injection_tier",
    "render_role_prompt",
    "resolve_router_compile_plan",
]
