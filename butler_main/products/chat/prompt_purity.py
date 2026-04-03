"""`/pure` 档位与 PromptPurityPolicy：对默认厚 prompt 做逐项减法（非模式路由）。

治理真源：docs/daily-upgrade/0330/04_Chat默认厚Prompt分层治理真源.md
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


_PURE_MODE_PATTERN = re.compile(r"^/pure(?P<suffix>[1-3])?(?:\s+(?P<body>.*))?$", re.DOTALL)
_SKILL_TRIGGER_KEYWORDS = (
    "skill",
    "技能",
    "mcp",
    "调用",
    "抓取",
    "ocr",
    "检索",
    "搜索",
    "文档",
    "pdf",
    "网页",
    "链接",
    "截图",
    "图片",
    "文件",
    "飞书",
    "xhslink.com",
    "http://",
    "https://",
)
_MIN_PURE_LEVEL = 1
_MAX_PURE_LEVEL = 3


@dataclass(slots=True, frozen=True)
class PurePromptDirective:
    level: int = 1
    body: str = ""
    command_text: str = "/pure"


@dataclass(slots=True, frozen=True)
class PromptPurityPolicy:
    enabled: bool = False
    level: int = 0
    include_bootstrap: bool = True
    include_role_asset: bool = True
    include_dialogue_asset: bool = True
    include_conversation_rules: bool = True
    include_user_profile: bool = True
    include_local_memory: bool = True
    include_self_mind: bool = True
    include_soul_excerpt: bool = True
    include_soul_source_ref: bool = True
    include_extended_protocols: bool = True
    include_agent_capabilities: bool = True
    include_recent_in_prompt: bool = True
    skills_mode: str = "always"


def parse_pure_prompt_directive(user_text: str) -> PurePromptDirective | None:
    text = str(user_text or "").strip()
    if not text.startswith("/pure"):
        return None
    matched = _PURE_MODE_PATTERN.match(text)
    if matched is None:
        return None
    suffix = str(matched.group("suffix") or "").strip()
    body = str(matched.group("body") or "").strip()
    level = _parse_level_token(suffix) or _MIN_PURE_LEVEL
    if body:
        level_from_body, remainder = _extract_level_from_body(body)
        if level_from_body is not None:
            level = level_from_body
            body = remainder
    return PurePromptDirective(
        level=max(_MIN_PURE_LEVEL, min(level, _MAX_PURE_LEVEL)),
        body=body,
        command_text=f"/pure{level if level > 1 else ''}",
    )


def normalize_prompt_purity(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    level = _coerce_level(
        payload.get("level")
        or payload.get("pure_level")
        or payload.get("prompt_purity_level")
    )
    if level is None:
        return None
    command_text = str(payload.get("command_text") or f"/pure{level if level > 1 else ''}").strip()
    normalized = {
        "level": level,
        "command_text": command_text or f"/pure{level if level > 1 else ''}",
    }
    if str(payload.get("source") or "").strip():
        normalized["source"] = str(payload.get("source") or "").strip()
    return normalized


def resolve_prompt_purity_policy(payload: Mapping[str, Any] | None) -> PromptPurityPolicy:
    normalized = normalize_prompt_purity(payload)
    if normalized is None:
        return PromptPurityPolicy()
    level = int(normalized.get("level") or 0)
    if level <= 1:
        return PromptPurityPolicy(
            enabled=True,
            level=1,
            include_bootstrap=False,
            include_user_profile=False,
            include_local_memory=False,
            include_self_mind=False,
            include_soul_excerpt=False,
            include_soul_source_ref=False,
            include_extended_protocols=False,
            include_agent_capabilities=False,
            skills_mode="on_demand",
        )
    if level == 2:
        return PromptPurityPolicy(
            enabled=True,
            level=2,
            include_bootstrap=False,
            include_role_asset=False,
            include_dialogue_asset=False,
            include_user_profile=False,
            include_local_memory=False,
            include_self_mind=False,
            include_soul_excerpt=False,
            include_soul_source_ref=False,
            include_extended_protocols=False,
            include_agent_capabilities=False,
            skills_mode="never",
        )
    return PromptPurityPolicy(
        enabled=True,
        level=3,
        include_bootstrap=False,
        include_role_asset=False,
        include_dialogue_asset=False,
        include_conversation_rules=False,
        include_user_profile=False,
        include_local_memory=False,
        include_self_mind=False,
        include_soul_excerpt=False,
        include_soul_source_ref=False,
        include_extended_protocols=False,
        include_agent_capabilities=False,
        include_recent_in_prompt=False,
        skills_mode="never",
    )


def should_include_skills_for_purity(source_prompt: str, policy: PromptPurityPolicy) -> bool:
    if not policy.enabled:
        return True
    if policy.skills_mode == "never":
        return False
    if policy.skills_mode == "always":
        return True
    text = str(source_prompt or "").lower()
    return any(keyword in text for keyword in _SKILL_TRIGGER_KEYWORDS)


def render_prompt_purity_block(policy: PromptPurityPolicy) -> str:
    if not policy.enabled:
        return ""
    if policy.level <= 1:
        return (
            "【纯净模式】本轮启用 `/pure` level 1：保留当前对话与必要协议，默认不注入画像、长期记忆、self_mind"
            " 和大段 bootstrap；skills 仅在明显需要时再提示。"
        )
    if policy.level == 2:
        return (
            "【纯净模式】本轮启用 `/pure2`：进一步去掉 role / dialogue 资产与 skills 扩展，只保留较薄的对话骨架。"
        )
    return (
        "【纯净模式】本轮启用 `/pure3`：再去掉 recent 注入，只保留最小安全骨架与当前原始用户消息。"
    )


def _parse_level_token(value: Any) -> int | None:
    text = str(value or "").strip()
    if text in {"1", "2", "3"}:
        return int(text)
    return None


def _extract_level_from_body(body: str) -> tuple[int | None, str]:
    text = str(body or "").strip()
    if not text:
        return None, ""
    head, _, tail = text.partition(" ")
    if head in {"1", "2", "3"}:
        return int(head), tail.strip()
    return None, text


def _coerce_level(value: Any) -> int | None:
    if isinstance(value, bool):
        return _MIN_PURE_LEVEL if value else None
    if isinstance(value, int):
        if value < _MIN_PURE_LEVEL:
            return None
        return max(_MIN_PURE_LEVEL, min(int(value), _MAX_PURE_LEVEL))
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in {"true", "yes", "on"}:
        return _MIN_PURE_LEVEL
    if text in {"false", "no", "off"}:
        return None
    if text in {"1", "2", "3"}:
        return int(text)
    return None


__all__ = [
    "PromptPurityPolicy",
    "PurePromptDirective",
    "normalize_prompt_purity",
    "parse_pure_prompt_directive",
    "render_prompt_purity_block",
    "resolve_prompt_purity_policy",
    "should_include_skills_for_purity",
]
