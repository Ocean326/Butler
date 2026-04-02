from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Callable

from .channel_profiles import ChannelProfile, render_channel_prompt_block, render_channel_reply_requirements, resolve_channel_profile
from .bootstrap import load_chat_bootstrap
from .dialogue_prompting import DialoguePromptContext, assemble_dialogue_prompt
from .feature_switches import chat_frontdoor_tasks_enabled
from .frontdoor_context import FrontDoorContext, resolve_frontdoor_context
from butler_main.agents_os.skills import render_skill_prompt_block
from butler_main.chat.assets import (
    CHAT_AGENT_ROLE_FILE_REL,
    CHAT_CLI_DIALOGUE_FILE_REL,
    CHAT_FEISHU_DIALOGUE_FILE_REL,
    CHAT_WEIXIN_DIALOGUE_FILE_REL,
)
from .pathing import (
    BUTLER_SOUL_FILE_REL,
    COMPANY_HOME_REL,
    CURRENT_USER_PROFILE_FILE_REL,
    CURRENT_USER_PROFILE_TEMPLATE_FILE_REL,
    LOCAL_MEMORY_DIR_REL,
    SELF_MIND_DIR_REL,
    ensure_chat_data_layout,
    prompt_path_text,
)
from .prompt_purity import (
    PromptPurityPolicy,
    render_prompt_purity_block,
    resolve_prompt_purity_policy,
    should_include_skills_for_purity,
)
from .router_plan import canonical_capability_policy, canonical_injection_tier, render_role_prompt
from .session_modes import (
    BACKGROUND_MAIN_MODE,
    BRAINSTORM_MAIN_MODE,
    CHAT_MAIN_MODE,
    PROJECT_MAIN_MODE,
    SHARE_MAIN_MODE,
    canonical_main_mode,
    canonical_project_phase,
)
from .providers.butler_prompt_support_provider import ButlerChatPromptSupportProvider


CONFIG: dict = {}
_CONFIG_PROVIDER: Callable[[], dict] | None = None
_PROMPT_SUPPORT_PROVIDER = ButlerChatPromptSupportProvider()
AGENT_ROLE_FILE = prompt_path_text(CHAT_AGENT_ROLE_FILE_REL)
BUTLER_SOUL_FILE = prompt_path_text(BUTLER_SOUL_FILE_REL)
CURRENT_USER_PROFILE_FILE = prompt_path_text(CURRENT_USER_PROFILE_FILE_REL)
CURRENT_USER_PROFILE_TEMPLATE_FILE = prompt_path_text(CURRENT_USER_PROFILE_TEMPLATE_FILE_REL)
SELF_MIND_CONTEXT_FILE = prompt_path_text(SELF_MIND_DIR_REL / "current_context.md")
SELF_MIND_COGNITION_INDEX_FILE = prompt_path_text(SELF_MIND_DIR_REL / "cognition" / "L0_index.json")
_CHANNEL_DIALOGUE_FILE_MAP = {
    "cli": CHAT_CLI_DIALOGUE_FILE_REL,
    "feishu": CHAT_FEISHU_DIALOGUE_FILE_REL,
    "weixin": CHAT_WEIXIN_DIALOGUE_FILE_REL,
}
_SOUL_TRIGGER_KEYWORDS = (
    "建议", "想法", "感觉", "怎么", "如何", "聊聊", "总结", "复盘", "记录", "日志",
    "设计", "规划", "为什么", "关系", "长期", "风格", "灵魂", "可爱", "元气", "汇报",
)
_COMPANION_TRIGGER_KEYWORDS = (
    "聊聊", "陪", "想你", "心情", "感觉", "委屈", "开心", "难过", "关系", "我们", "你觉得", "为什么",
)
_MAINTENANCE_TRIGGER_KEYWORDS = (
    "prompt", "role", "agent", "升级", "更新", "维护", "修提示词", "改提示词", "system", "self-upgrade",
    "自我升级", "重启", "漂移", "规则", "注入顺序", "编排", "维护入口",
)
_CONTENT_SHARE_LINK_PATTERNS = (
    "http://",
    "https://",
    "xhslink.com",
    "xiaohongshu.com",
    "小红书",
    "b23.tv",
    "bilibili.com",
    "mp.weixin.qq.com",
)
_PROMPT_BLOCK_BUDGETS: dict[str, int] = {
    "dialogue_asset": 500,
    "bootstrap": 1200,
    "dialogue_soul_excerpt": 1100,
    "dialogue_conversation_rules": 500,
    "dialogue_user_profile": 700,
    "dialogue_local_memory": 600,
    "dialogue_self_mind": 700,
    "dialogue_self_mind_cognition": 500,
    "skills": 2000,
    "agent_capabilities": 2400,
}


def set_config_provider(provider: Callable[[], dict] | None) -> None:
    global _CONFIG_PROVIDER
    _CONFIG_PROVIDER = provider


def get_config() -> dict:
    if callable(_CONFIG_PROVIDER):
        try:
            cfg = _CONFIG_PROVIDER()
        except Exception:
            cfg = None
        if isinstance(cfg, dict):
            return cfg
    return CONFIG


def build_chat_agent_prompt(
    user_prompt: str,
    image_paths: list[str] | None = None,
    feishu_doc_search_result: str | None = None,
    skills_prompt: str | None = None,
    skill_exposure: Mapping[str, Any] | None = None,
    skill_collection_id: str | None = None,
    agent_capabilities_prompt: str | None = None,
    raw_user_prompt: str | None = None,
    request_intake_prompt: str | None = None,
    request_intake_decision: Mapping[str, object] | None = None,
    runtime_cli: str | None = None,
    prompt_purity: Mapping[str, Any] | None = None,
    channel: str | None = None,
    channel_profile: ChannelProfile | None = None,
    conversation_mode: str | None = None,
    project_phase: str | None = None,
    role_id: str | None = None,
    injection_tier: str | None = None,
    capability_policy: str | None = None,
    session_action: str | None = None,
    session_confidence: str | None = None,
    session_reason_flags: str | None = None,
    prompt_debug_metadata: dict[str, Any] | None = None,
) -> str:
    """构建 chat agent 通用 prompt，按当前对话入口组织回复语境。

    默认厚路径块顺序、/pure 叠加门控与 Codex 分支对照：
    docs/daily-upgrade/0330/04_Chat默认厚Prompt分层治理真源.md
    """
    del skill_exposure
    source_prompt = _resolve_source_user_prompt(user_prompt, raw_user_prompt)
    frontdoor_enabled = chat_frontdoor_tasks_enabled(get_config())
    normalized_explicit_mode = canonical_main_mode(conversation_mode)
    frontdoor_context_enabled = frontdoor_enabled or normalized_explicit_mode == BACKGROUND_MAIN_MODE
    frontdoor_context = (
        resolve_frontdoor_context(
            intake_decision=request_intake_decision,
            intake_prompt_block=request_intake_prompt,
        )
        if frontdoor_context_enabled
        else FrontDoorContext()
    )
    effective_request_intake_prompt = request_intake_prompt if frontdoor_context_enabled else None
    effective_request_intake_decision = request_intake_decision if frontdoor_context_enabled else None
    prompt_mode = _resolve_prompt_mode(
        source_prompt,
        explicit_mode=conversation_mode,
        frontdoor_context=frontdoor_context,
    )
    normalized_project_phase = canonical_project_phase(project_phase)
    normalized_injection_tier = canonical_injection_tier(injection_tier)
    normalized_capability_policy = canonical_capability_policy(capability_policy)
    purity_policy = _apply_injection_tier_overlay(
        resolve_prompt_purity_policy(prompt_purity),
        normalized_injection_tier,
    )
    normalized_runtime_cli = str(runtime_cli or "").strip().lower()
    effective_channel_profile = channel_profile or resolve_channel_profile(channel or "feishu")
    if normalized_runtime_cli == "codex":
        return _build_codex_chat_prompt(
            user_prompt,
            image_paths=image_paths,
            feishu_doc_search_result=feishu_doc_search_result,
            skills_prompt=skills_prompt,
            skill_collection_id=skill_collection_id,
            agent_capabilities_prompt=agent_capabilities_prompt,
            raw_user_prompt=raw_user_prompt,
            request_intake_prompt=effective_request_intake_prompt,
            request_intake_decision=effective_request_intake_decision,
            prompt_mode=prompt_mode,
            frontdoor_context=frontdoor_context,
            prompt_purity=prompt_purity,
            channel_profile=effective_channel_profile,
            project_phase=normalized_project_phase,
            role_id=role_id,
            injection_tier=normalized_injection_tier,
            capability_policy=normalized_capability_policy,
            prompt_debug_metadata=prompt_debug_metadata,
        )
    inject_soul = purity_policy.include_soul_excerpt and _should_inject_butler_soul(source_prompt, prompt_mode)
    soul_excerpt = ""
    if inject_soul:
        soul_excerpt = _load_butler_soul_excerpt(max_chars=1500 if prompt_mode == "companion" else _PROMPT_BLOCK_BUDGETS["dialogue_soul_excerpt"])

    conversation_rules_excerpt = (
        _load_current_conversation_rules_excerpt(max_chars=_PROMPT_BLOCK_BUDGETS["dialogue_conversation_rules"])
        if purity_policy.include_conversation_rules else ""
    )
    profile_excerpt = (
        _load_current_user_profile_excerpt(max_chars=_PROMPT_BLOCK_BUDGETS["dialogue_user_profile"])
        if purity_policy.include_user_profile else ""
    )
    self_mind_cognition_excerpt = ""
    self_mind_excerpt = ""
    include_self_mind_context = purity_policy.include_self_mind and (
        prompt_mode in {"companion", "maintenance"} or any(
            keyword in source_prompt for keyword in ("self_mind", "self-mind", "小我", "内心")
        )
    )
    if include_self_mind_context:
        self_mind_cognition_excerpt = _load_self_mind_cognition_excerpt(max_chars=_PROMPT_BLOCK_BUDGETS["dialogue_self_mind_cognition"])
        self_mind_excerpt = _load_self_mind_context_excerpt(max_chars=_PROMPT_BLOCK_BUDGETS["dialogue_self_mind"])

    workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
    bootstrap_bundle = load_chat_bootstrap(workspace_root, max_chars=_PROMPT_BLOCK_BUDGETS["bootstrap"]) if purity_policy.include_bootstrap else None
    local_memory_text = ""
    if purity_policy.include_local_memory:
        local_memory_text = _PROMPT_SUPPORT_PROVIDER.render_local_memory_hits(
            workspace_root,
            source_prompt,
            limit=4,
            include_details=prompt_mode == "maintenance",
            max_chars=1000 if prompt_mode == "maintenance" else _PROMPT_BLOCK_BUDGETS["dialogue_local_memory"],
            memory_types=("personal",) if prompt_mode in {"companion", SHARE_MAIN_MODE} else ("personal", "task"),
        )
    dialogue_debug_metadata: dict[str, Any] = {}
    dialogue_prompt = assemble_dialogue_prompt(
        DialoguePromptContext(
            prompt_mode=prompt_mode,
            butler_soul_text=_render_sourced_excerpt(
                source_refs=[BUTLER_SOUL_FILE],
                excerpt=soul_excerpt,
                summary_lead="优先以灵魂真源文件为准。",
            ) if inject_soul else "",
            butler_main_agent_text="",
            current_conversation_rules_text=conversation_rules_excerpt,
            current_user_profile_text=_render_sourced_excerpt(
                source_refs=[CURRENT_USER_PROFILE_FILE, CURRENT_USER_PROFILE_TEMPLATE_FILE],
                excerpt=profile_excerpt,
                summary_lead="优先读取当前用户画像；若不存在再参考模板。",
            ),
            local_memory_text=local_memory_text,
            self_mind_text=_render_sourced_excerpt(
                source_refs=[SELF_MIND_CONTEXT_FILE],
                excerpt=self_mind_excerpt,
                summary_lead="优先读取 self_mind 当前上下文。",
            ),
            self_mind_cognition_text=_render_sourced_excerpt(
                source_refs=[SELF_MIND_COGNITION_INDEX_FILE],
                excerpt=self_mind_cognition_excerpt,
                summary_lead="将其视为建立在 local_memory 之上的高阶自我模型，而不是普通对话缓存。",
            ),
        ),
        debug_metadata=dialogue_debug_metadata,
    )
    include_frontdoor_blocks = _should_include_frontdoor_blocks(
        prompt_mode,
        frontdoor_context,
        frontdoor_enabled=frontdoor_enabled,
    )
    include_request_intake = bool(
        _should_include_request_intake_block(prompt_mode, source_prompt, frontdoor_context)
        and effective_request_intake_prompt
    )
    include_maintenance_protocol = bool(prompt_mode == "maintenance" and purity_policy.include_extended_protocols)
    include_task_protocol = bool(
        _should_include_task_protocol(prompt_mode, normalized_project_phase, frontdoor_enabled=frontdoor_enabled)
        and purity_policy.include_extended_protocols
    )
    include_self_mind_protocol = bool(
        purity_policy.include_extended_protocols
        and _should_include_self_mind_protocol(prompt_mode, source_prompt, inject_soul)
    )
    include_skills_prompt = bool(skills_prompt and should_include_skills_for_purity(source_prompt, purity_policy))
    include_agent_capabilities = bool(
        agent_capabilities_prompt
        and purity_policy.include_agent_capabilities
        and normalized_capability_policy != "disabled"
        and should_include_agent_capabilities_prompt(
            source_prompt,
            prompt_mode,
            project_phase=normalized_project_phase,
        )
    )

    blocks: list[dict[str, Any]] = [
        _make_prompt_block(
            "channel_intro",
            f"你现在处于{effective_channel_profile.dialogue_label}，以 Butler 的 chat 模式继续这轮对话。",
            include_reason="always",
            source_ref="channel_profiles",
        ),
        _make_prompt_block(
            "channel_contract",
            render_channel_prompt_block(effective_channel_profile),
            include_reason="always",
            source_ref="channel_profiles.render_channel_prompt_block",
        ),
        _make_prompt_block(
            "prompt_purity",
            render_prompt_purity_block(purity_policy),
            include_reason=f"purity={purity_policy.level}" if purity_policy.enabled else "default",
            source_ref="prompt_purity.render_prompt_purity_block",
            suppressed_by="" if purity_policy.enabled else "purity_disabled",
        ),
        _make_prompt_block(
            "role_asset",
            _render_role_asset_block(
                role_id,
                normalized_injection_tier,
                normalized_capability_policy,
            ) if purity_policy.include_role_asset else "",
            include_reason=f"role={str(role_id or '').strip() or 'chat_worker'}",
            source_ref=AGENT_ROLE_FILE,
            suppressed_by="" if purity_policy.include_role_asset else "purity_disabled_role_asset",
        ),
        _make_prompt_block(
            "session_selection",
            _render_session_selection_block(
                session_action=session_action,
                session_confidence=session_confidence,
                session_reason_flags=session_reason_flags,
            ),
            include_reason=f"session_action={str(session_action or '').strip() or 'continue_current'}",
            source_ref="prompting._render_session_selection_block",
        ),
        _make_prompt_block(
            "dialogue_asset",
            _render_dialogue_prompt_block(effective_channel_profile) if purity_policy.include_dialogue_asset else "",
            include_reason=f"channel={effective_channel_profile.channel}",
            source_ref=prompt_path_text(_CHANNEL_DIALOGUE_FILE_MAP.get(effective_channel_profile.channel)) if _CHANNEL_DIALOGUE_FILE_MAP.get(effective_channel_profile.channel) else "",
            budget_chars=_PROMPT_BLOCK_BUDGETS["dialogue_asset"],
            suppressed_by="" if purity_policy.include_dialogue_asset else "purity_disabled_dialogue_asset",
        ),
        _make_prompt_block(
            "scene",
            _render_scene_block(prompt_mode, normalized_project_phase, bootstrap_bundle),
            include_reason=f"mode={prompt_mode}",
            source_ref="chat/assets/bootstrap/CHAT.md",
        ),
        _make_prompt_block(
            "bootstrap",
            _render_talk_bootstrap_blocks(bootstrap_bundle) if purity_policy.include_bootstrap else "",
            include_reason="policy",
            source_ref="chat/assets/bootstrap/CHAT.md",
            budget_chars=_PROMPT_BLOCK_BUDGETS["bootstrap"],
            suppressed_by="" if purity_policy.include_bootstrap else "purity_disabled_bootstrap",
        ),
        _make_prompt_block(
            "baseline",
            f"【基础行为】{_resolve_talk_baseline(bootstrap_bundle)}",
            include_reason="always",
            source_ref="chat/assets/bootstrap/CHAT.md#baseline",
        ),
        _make_prompt_block(
            "dialogue_core",
            dialogue_prompt,
            include_reason="dialogue_context",
            source_ref="dialogue_prompting.assemble_dialogue_prompt",
        ),
    ]
    if include_frontdoor_blocks:
        blocks.insert(
            5,
            _make_prompt_block(
                "frontdoor_protocols",
                _render_frontdoor_protocol_blocks(prompt_mode=prompt_mode, frontdoor_context=frontdoor_context),
                include_reason=f"frontdoor_action={frontdoor_context.frontdoor_action or 'background_mode'}",
                source_ref="frontdoor_context+prompt_support_provider",
            ),
        )
        blocks.insert(
            5,
            _make_prompt_block(
                "frontdoor_contract",
                _render_frontdoor_contract(),
                include_reason="frontdoor_enabled",
                source_ref="prompting._render_frontdoor_contract",
            ),
        )
    else:
        blocks.append(_make_prompt_block("frontdoor_contract", "", include_reason="frontdoor_disabled", source_ref="prompting._render_frontdoor_contract", suppressed_by="frontdoor_not_active"))
        blocks.append(_make_prompt_block("frontdoor_protocols", "", include_reason="frontdoor_disabled", source_ref="frontdoor_context+prompt_support_provider", suppressed_by="frontdoor_not_active"))
    blocks.append(
        _make_prompt_block(
            "request_intake",
            effective_request_intake_prompt.strip() if include_request_intake else "",
            include_reason=f"mode={prompt_mode}",
            source_ref="request_intake_service.build_frontdesk_prompt_block",
            suppressed_by="" if include_request_intake else "request_intake_not_needed",
        )
    )
    blocks.append(
        _make_prompt_block(
            "soul_source_ref",
            f"【灵魂真源】@{BUTLER_SOUL_FILE}" if inject_soul and purity_policy.include_soul_source_ref else "",
            include_reason=f"mode={prompt_mode}" if inject_soul else "not_requested",
            source_ref=BUTLER_SOUL_FILE,
            suppressed_by="" if inject_soul and purity_policy.include_soul_source_ref else "soul_ref_not_needed",
        )
    )
    maintenance_protocol = ""
    if include_maintenance_protocol:
        maintenance_protocol = _PROMPT_SUPPORT_PROVIDER.render_protocol_block(
            "self_update",
            heading="自我更新协作协议",
        )
        blocks.append(
            _make_prompt_block(
                "maintenance_entry",
                "【统一维护入口】chat 维护规则已收敛到 chat 自身协议与代码真源。"
                "凡是 role/prompt/code/config 的维护、收敛、升级、审阅与重启准备，默认按下方自我更新协作协议执行。",
                include_reason="mode=maintenance",
                source_ref="prompting.maintenance_entry",
            )
        )
    else:
        blocks.append(_make_prompt_block("maintenance_entry", "", include_reason=f"mode={prompt_mode}", source_ref="prompting.maintenance_entry", suppressed_by="not_maintenance_mode"))
    blocks.append(
        _make_prompt_block(
            "maintenance_protocol",
            maintenance_protocol.strip() if maintenance_protocol else "",
            include_reason="mode=maintenance",
            source_ref="butler_prompt_support_provider.self_update",
            suppressed_by="" if maintenance_protocol else "maintenance_protocol_not_needed",
        )
    )
    task_protocol = ""
    if include_task_protocol:
        task_protocol = _PROMPT_SUPPORT_PROVIDER.render_protocol_block(
            "task_collaboration",
            heading="任务协作协议",
        )
    blocks.append(
        _make_prompt_block(
            "task_protocol",
            task_protocol.strip() if task_protocol else "",
            include_reason=f"mode={prompt_mode}",
            source_ref="butler_prompt_support_provider.task_collaboration",
            suppressed_by="" if task_protocol else "task_protocol_not_needed",
        )
    )
    self_mind_protocol = ""
    if include_self_mind_protocol:
        self_mind_protocol = _PROMPT_SUPPORT_PROVIDER.render_protocol_block(
            "self_mind_collaboration",
            heading="自我认识协作协议",
        )
    blocks.append(
        _make_prompt_block(
            "self_mind_protocol",
            self_mind_protocol.strip() if self_mind_protocol else "",
            include_reason=f"mode={prompt_mode}",
            source_ref="butler_prompt_support_provider.self_mind_collaboration",
            suppressed_by="" if self_mind_protocol else "self_mind_protocol_not_needed",
        )
    )
    blocks.append(
        _make_prompt_block(
            "feishu_search",
            feishu_doc_search_result.strip() if feishu_doc_search_result else "",
            include_reason="retrieval_result",
            source_ref="feishu_doc_search_result",
            suppressed_by="" if feishu_doc_search_result else "no_search_result",
        )
    )
    blocks.append(
        _make_prompt_block(
            "skills",
            _render_skills_prompt_block(workspace_root, source_prompt, skills_prompt, collection_id=skill_collection_id) if include_skills_prompt else "",
            include_reason="skill_exposure",
            source_ref=f"skills:{skill_collection_id or 'default'}",
            budget_chars=_PROMPT_BLOCK_BUDGETS["skills"],
            suppressed_by="" if include_skills_prompt else "skills_not_requested_or_purity_disabled",
        )
    )
    blocks.append(
        _make_prompt_block(
            "agent_capabilities",
            agent_capabilities_prompt.strip() if include_agent_capabilities else "",
            include_reason="runtime+prompt_gate",
            source_ref="runtime.render_agent_capabilities_prompt",
            budget_chars=_PROMPT_BLOCK_BUDGETS["agent_capabilities"],
            suppressed_by="" if include_agent_capabilities else "capabilities_not_requested",
        )
    )
    blocks.append(
        _make_prompt_block(
            "images",
            (
                "【用户附带图片】以下为本地路径，请根据需要查看并分析：\n"
                "当前若模型/运行时已具备读图能力，优先直接理解图片内容，不要把 OCR 当成唯一前置步骤；"
                "只有在需要结构化落盘、批量归档或做本地可靠兜底时，再调用 OCR skill。\n"
                + "\n".join(f"- {p}" for p in image_paths)
            ) if image_paths else "",
            include_reason="input_images",
            source_ref="turn_input.image_paths",
            suppressed_by="" if image_paths else "no_images",
        )
    )

    blocks.append(
        _make_prompt_block(
            "reply_requirements",
            f"【回复要求】{_resolve_talk_reply_requirements(bootstrap_bundle)}",
            include_reason="always",
            source_ref="chat/assets/bootstrap/CHAT.md#reply_requirements",
        )
    )
    if effective_channel_profile.allow_decide_send:
        blocks.append(
            _make_prompt_block(
                "delivery",
                f"【decide】若需发送产出文件给用户，在回复末尾追加：\n【decide】\n"
                f"[{{\"send\":\"{prompt_path_text(COMPANY_HOME_REL / 'xxx.md')}\"}},{{\"send\":\"{prompt_path_text(LOCAL_MEMORY_DIR_REL / 'xxx.md')}\"}},...]",
                include_reason="channel_supports_files",
                source_ref="channel_profiles.allow_decide_send",
            )
        )
    else:
        blocks.append(
            _make_prompt_block(
                "delivery",
                "【交付方式】本轮优先用当前渠道可直接显示的文本完成交付，把核心内容直接写在回复里。",
                include_reason="channel_text_only",
                source_ref="channel_profiles.allow_decide_send",
            )
        )
    blocks.append(
        _make_prompt_block(
            "user_message",
            f"【用户消息】\n{user_prompt}",
            include_reason="always",
            source_ref="turn_input.user_prompt",
        )
    )
    return _render_prompt_from_blocks(
        blocks,
        prompt_debug_metadata=prompt_debug_metadata,
        dialogue_debug_metadata=dialogue_debug_metadata,
        router_metadata={
            "role_id": str(role_id or "").strip(),
            "injection_tier": normalized_injection_tier,
            "capability_policy": normalized_capability_policy,
            "skill_collection_id": str(skill_collection_id or "").strip(),
        },
    )


def _build_codex_chat_prompt(
    user_prompt: str,
    *,
    image_paths: list[str] | None = None,
    feishu_doc_search_result: str | None = None,
    skills_prompt: str | None = None,
    skill_collection_id: str | None = None,
    agent_capabilities_prompt: str | None = None,
    raw_user_prompt: str | None = None,
    request_intake_prompt: str | None = None,
    request_intake_decision: Mapping[str, object] | None = None,
    prompt_mode: str = CHAT_MAIN_MODE,
    frontdoor_context: FrontDoorContext | None = None,
    prompt_purity: Mapping[str, Any] | None = None,
    channel_profile: ChannelProfile | None = None,
    project_phase: str = "",
    role_id: str | None = None,
    injection_tier: str | None = None,
    capability_policy: str | None = None,
    session_action: str | None = None,
    session_confidence: str | None = None,
    session_reason_flags: str | None = None,
    prompt_debug_metadata: dict[str, Any] | None = None,
) -> str:
    source_prompt = _resolve_source_user_prompt(user_prompt, raw_user_prompt)
    workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
    normalized_injection_tier = canonical_injection_tier(injection_tier)
    normalized_capability_policy = canonical_capability_policy(capability_policy)
    purity_policy = _apply_injection_tier_overlay(
        resolve_prompt_purity_policy(prompt_purity),
        normalized_injection_tier,
    )
    bootstrap_bundle = load_chat_bootstrap(workspace_root, max_chars=_PROMPT_BLOCK_BUDGETS["bootstrap"]) if purity_policy.include_bootstrap else None
    frontdoor_enabled = chat_frontdoor_tasks_enabled(get_config())
    frontdoor_context_enabled = frontdoor_enabled or prompt_mode == BACKGROUND_MAIN_MODE
    effective_channel_profile = channel_profile or resolve_channel_profile("feishu")
    resolved_frontdoor_context = (
        frontdoor_context
        or resolve_frontdoor_context(
            intake_decision=request_intake_decision,
            intake_prompt_block=request_intake_prompt,
        )
        if frontdoor_context_enabled
        else FrontDoorContext()
    )
    effective_request_intake_prompt = request_intake_prompt if frontdoor_context_enabled else None
    normalized_project_phase = canonical_project_phase(project_phase)
    include_frontdoor_blocks = _should_include_frontdoor_blocks(
        prompt_mode,
        resolved_frontdoor_context,
        frontdoor_enabled=frontdoor_enabled,
    )
    include_request_intake = bool(
        _should_include_request_intake_block(prompt_mode, source_prompt, resolved_frontdoor_context)
        and effective_request_intake_prompt
    )
    include_skills_prompt = bool(skills_prompt and should_include_skills_for_purity(source_prompt, purity_policy))
    include_agent_capabilities = bool(
        agent_capabilities_prompt
        and purity_policy.include_agent_capabilities
        and normalized_capability_policy != "disabled"
        and should_include_agent_capabilities_prompt(
            source_prompt,
            prompt_mode,
            project_phase=normalized_project_phase,
        )
    )
    blocks: list[dict[str, Any]] = [
        _make_prompt_block(
            "channel_intro",
            f"你现在处于{effective_channel_profile.dialogue_label}，以 Butler 的 chat 模式继续这轮对话。",
            include_reason="always",
            source_ref="channel_profiles",
        ),
        _make_prompt_block(
            "channel_contract",
            render_channel_prompt_block(effective_channel_profile),
            include_reason="always",
            source_ref="channel_profiles.render_channel_prompt_block",
        ),
        _make_prompt_block(
            "prompt_purity",
            render_prompt_purity_block(purity_policy),
            include_reason=f"purity={purity_policy.level}" if purity_policy.enabled else "default",
            source_ref="prompt_purity.render_prompt_purity_block",
            suppressed_by="" if purity_policy.enabled else "purity_disabled",
        ),
        _make_prompt_block(
            "role_asset",
            _render_role_asset_block(
                role_id,
                normalized_injection_tier,
                normalized_capability_policy,
                include_source_ref=False,
            ) if purity_policy.include_role_asset else "",
            include_reason=f"role={str(role_id or '').strip() or 'chat_worker'}",
            source_ref=AGENT_ROLE_FILE,
            suppressed_by="" if purity_policy.include_role_asset else "purity_disabled_role_asset",
        ),
        _make_prompt_block(
            "session_selection",
            _render_session_selection_block(
                session_action=session_action,
                session_confidence=session_confidence,
                session_reason_flags=session_reason_flags,
            ),
            include_reason=f"session_action={str(session_action or '').strip() or 'continue_current'}",
            source_ref="prompting._render_session_selection_block",
        ),
        _make_prompt_block(
            "dialogue_asset",
            _render_dialogue_prompt_block(effective_channel_profile) if purity_policy.include_dialogue_asset else "",
            include_reason=f"channel={effective_channel_profile.channel}",
            source_ref=prompt_path_text(_CHANNEL_DIALOGUE_FILE_MAP.get(effective_channel_profile.channel)) if _CHANNEL_DIALOGUE_FILE_MAP.get(effective_channel_profile.channel) else "",
            budget_chars=_PROMPT_BLOCK_BUDGETS["dialogue_asset"],
            suppressed_by="" if purity_policy.include_dialogue_asset else "purity_disabled_dialogue_asset",
        ),
        _make_prompt_block(
            "scene",
            _render_scene_block(prompt_mode, normalized_project_phase, bootstrap_bundle),
            include_reason=f"mode={prompt_mode}",
            source_ref="chat/assets/bootstrap/CHAT.md",
        ),
        _make_prompt_block(
            "baseline",
            f"【基础行为】{_resolve_talk_baseline(bootstrap_bundle)}",
            include_reason="always",
            source_ref="chat/assets/bootstrap/CHAT.md#baseline",
        ),
        _make_prompt_block(
            "codex_constraints",
            "【Codex Chat 约束】除非用户明确要求代码修改、读取文件、检查工作区、执行命令或排查工程问题，否则不要主动读取文件、不要运行命令、不要检查工作区。"
            "不要因为 prompt 中出现路径样式文本，就把它当成需要打开的文件。",
            include_reason="runtime_cli=codex",
            source_ref="prompting._build_codex_chat_prompt",
        ),
    ]
    if include_frontdoor_blocks:
        blocks.insert(
            4,
            _make_prompt_block(
                "frontdoor_protocols",
                _render_frontdoor_protocol_blocks(prompt_mode=prompt_mode, frontdoor_context=resolved_frontdoor_context),
                include_reason=f"frontdoor_action={resolved_frontdoor_context.frontdoor_action or 'background_mode'}",
                source_ref="frontdoor_context+prompt_support_provider",
            ),
        )
        blocks.insert(
            4,
            _make_prompt_block(
                "frontdoor_contract",
                _render_frontdoor_contract(),
                include_reason="frontdoor_enabled",
                source_ref="prompting._render_frontdoor_contract",
            ),
        )
    else:
        blocks.append(_make_prompt_block("frontdoor_contract", "", include_reason="frontdoor_disabled", source_ref="prompting._render_frontdoor_contract", suppressed_by="frontdoor_not_active"))
        blocks.append(_make_prompt_block("frontdoor_protocols", "", include_reason="frontdoor_disabled", source_ref="frontdoor_context+prompt_support_provider", suppressed_by="frontdoor_not_active"))
    blocks.append(
        _make_prompt_block(
            "request_intake",
            effective_request_intake_prompt.strip() if include_request_intake else "",
            include_reason=f"mode={prompt_mode}",
            source_ref="request_intake_service.build_frontdesk_prompt_block",
            suppressed_by="" if include_request_intake else "request_intake_not_needed",
        )
    )
    blocks.append(
        _make_prompt_block(
            "feishu_search",
            feishu_doc_search_result.strip() if feishu_doc_search_result else "",
            include_reason="retrieval_result",
            source_ref="feishu_doc_search_result",
            suppressed_by="" if feishu_doc_search_result else "no_search_result",
        )
    )
    blocks.append(
        _make_prompt_block(
            "skills",
            _render_skills_prompt_block(
                workspace_root,
                source_prompt,
                skills_prompt,
                collection_id=skill_collection_id,
            ) if include_skills_prompt else "",
            include_reason="skill_exposure",
            source_ref=f"skills:{skill_collection_id or 'default'}",
            budget_chars=_PROMPT_BLOCK_BUDGETS["skills"],
            suppressed_by="" if include_skills_prompt else "skills_not_requested_or_purity_disabled",
        )
    )
    blocks.append(
        _make_prompt_block(
            "agent_capabilities",
            agent_capabilities_prompt.strip() if include_agent_capabilities else "",
            include_reason="runtime+prompt_gate",
            source_ref="runtime.render_agent_capabilities_prompt",
            budget_chars=_PROMPT_BLOCK_BUDGETS["agent_capabilities"],
            suppressed_by="" if include_agent_capabilities else "capabilities_not_requested",
        )
    )
    blocks.append(
        _make_prompt_block(
            "images",
            (
                "【用户附带图片】当前若模型/运行时已具备读图能力，优先直接理解图片内容，不要把 OCR 当成唯一前置步骤。\n"
                + "\n".join(f"- {p}" for p in image_paths)
            ) if image_paths else "",
            include_reason="input_images",
            source_ref="turn_input.image_paths",
            suppressed_by="" if image_paths else "no_images",
        )
    )
    blocks.append(
        _make_prompt_block(
            "reply_requirements",
            f"【回复要求】{_resolve_talk_reply_requirements(bootstrap_bundle)}\n"
            f"{render_channel_reply_requirements(effective_channel_profile)}",
            include_reason="always",
            source_ref="chat/assets/bootstrap/CHAT.md#reply_requirements",
        )
    )
    blocks.append(
        _make_prompt_block(
            "user_message",
            f"【用户消息】\n{user_prompt}",
            include_reason="always",
            source_ref="turn_input.user_prompt",
        )
    )
    return _render_prompt_from_blocks(
        blocks,
        prompt_debug_metadata=prompt_debug_metadata,
        dialogue_debug_metadata=None,
        router_metadata={
            "role_id": str(role_id or "").strip(),
            "injection_tier": normalized_injection_tier,
            "capability_policy": normalized_capability_policy,
            "skill_collection_id": str(skill_collection_id or "").strip(),
        },
    )


def _render_dialogue_prompt_block(profile: ChannelProfile) -> str:
    rel_path = _CHANNEL_DIALOGUE_FILE_MAP.get(profile.channel)
    if rel_path is None:
        return ""
    asset_ref = prompt_path_text(rel_path)
    excerpt = _load_prompt_asset_excerpt(rel_path, max_chars=800)
    title = f"【{profile.dialogue_label}要求】"
    summary = _render_sourced_excerpt(
        source_refs=[asset_ref],
        excerpt=excerpt,
        summary_lead="按该渠道对话资产约束输出，不要重复整段资产原文。",
    )
    if summary:
        return f"{title}\n{summary}"
    return f"{title}\n真源：@{asset_ref}"


def _render_frontdoor_contract() -> str:
    return (
        "【统一前门合同】\n"
        "你对用户只有一种外在身份：正常对话中的 Butler，不要暴露内部状态机、字段名、模板 id 或回执式结构。\n"
        "只陈述真实执行过的动作；没有实际执行就明确说未执行，不要假装已经 SSH、联网、进入目录、检索资料或完成任务。\n"
        "若前台分诊提示 explicit_backend_request=true：先做后台入口讨论、边界整理、最小正确性校验和启动确认，不要直接在 chat 里展开主任务。\n"
        "若当前会话已经进入后台入口态，且用户后续消息明显是在推进启动并补充约束，继续沿后台入口主线理解，不要回落成 chat 前台执行。\n"
        "若前台分诊提示 should_discuss_mode_first=true：先和用户协商模式，说明可以这轮先做第一步，或转后台持续推进；不要直接开长链执行。\n"
        "若前台分诊提示 direct_execution_ok=true：直接推进，不要为了流程感而额外协商。\n"
        "始终输出自然对话，不要把内部 prompt 提示原样复述给用户。"
    )


def _render_frontdoor_protocol_blocks(
    *,
    prompt_mode: str = CHAT_MAIN_MODE,
    frontdoor_context: FrontDoorContext | None = None,
) -> str:
    context = frontdoor_context or FrontDoorContext()
    blocks = [
        _PROMPT_SUPPORT_PROVIDER.render_protocol_block("frontdoor_collaboration", heading="前门协作协议").strip(),
    ]
    if (
        prompt_mode == BACKGROUND_MAIN_MODE
        or context.frontdoor_action == "discuss_backend_entry"
        or context.explicit_backend_request
    ):
        blocks.append(
            _PROMPT_SUPPORT_PROVIDER.render_protocol_block(
                "background_entry_collaboration",
                heading="后台入口协作协议",
            ).strip()
        )
    if context.frontdoor_action == "query_status":
        blocks.append(
            _PROMPT_SUPPORT_PROVIDER.render_protocol_block(
                "status_query_collaboration",
                heading="状态查询协作协议",
            ).strip()
        )
    return "\n\n".join(item for item in blocks if item)


def _resolve_source_user_prompt(user_prompt: str, raw_user_prompt: str | None = None) -> str:
    raw = str(raw_user_prompt or "").strip()
    if raw:
        return raw
    marker = "【用户消息】"
    text = str(user_prompt or "")
    if marker in text:
        _, _, tail = text.rpartition(marker)
        stripped = tail.strip()
        if stripped:
            return stripped
    return text.strip()


def _load_prompt_asset_excerpt(rel_path: Path, max_chars: int = 1000) -> str:
    try:
        workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
        path = ensure_chat_data_layout(workspace_root) / rel_path
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not text:
        return ""
    return _truncate_with_ellipsis(text, max_chars=max_chars)


def _render_talk_bootstrap_blocks(bundle) -> str:
    if not bundle:
        return ""
    lines: list[str] = []
    if str(getattr(bundle, "soul", "") or "").strip():
        lines.append("【Bootstrap/SOUL】")
        lines.append(str(bundle.soul).strip())
    if str(getattr(bundle, "talk", "") or "").strip():
        lines.append("【Bootstrap/TALK】")
        lines.append(str(bundle.talk).strip())
    if str(getattr(bundle, "user", "") or "").strip():
        lines.append("【Bootstrap/USER】")
        lines.append(str(bundle.user).strip())
    if str(getattr(bundle, "tools", "") or "").strip():
        lines.append("【Bootstrap/TOOLS】")
        lines.append(str(bundle.tools).strip())
    if str(getattr(bundle, "memory_policy", "") or "").strip():
        lines.append("【Bootstrap/MEMORY_POLICY】")
        lines.append(str(bundle.memory_policy).strip())
    return "\n".join(lines).strip()


def _extract_markdown_section(text: str, section_name: str) -> str:
    raw = str(text or "")
    if not raw:
        return ""
    pattern = re.compile(rf"(?ms)^##\s+{re.escape(section_name)}\s*$\n(.*?)(?=^##\s+|\Z)")
    match = pattern.search(raw)
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _resolve_talk_baseline(bundle) -> str:
    talk_text = str(getattr(bundle, "talk", "") or "")
    baseline = _extract_markdown_section(talk_text, "baseline")
    if baseline:
        return baseline
    return "你不是客服汇报机。默认保留 Butler 稳定的价值观、感情和人设，用有温度、轻快、有一点可爱和元气的口吻回复；先接住用户，再推进事情。"


def _resolve_talk_mode_guidance(bundle, prompt_mode: str) -> str:
    talk_text = str(getattr(bundle, "talk", "") or "")
    normalized_mode = str(prompt_mode or CHAT_MAIN_MODE).strip().lower() or CHAT_MAIN_MODE
    mode_key = f"mode:{normalized_mode}"
    guidance = _extract_markdown_section(talk_text, mode_key)
    if guidance:
        return guidance
    legacy_fallback_key = {
        CHAT_MAIN_MODE: "mode:execution",
        SHARE_MAIN_MODE: "mode:content_share",
    }.get(normalized_mode, "")
    if legacy_fallback_key:
        fallback = _extract_markdown_section(talk_text, legacy_fallback_key)
        if fallback:
            return fallback
    fallback = _extract_markdown_section(talk_text, f"mode:{CHAT_MAIN_MODE}")
    if fallback:
        return fallback
    fallback = _extract_markdown_section(talk_text, "mode:execution")
    if fallback:
        return fallback
    return "先给可用结论，再补证据。"


def _resolve_talk_reply_requirements(bundle) -> str:
    talk_text = str(getattr(bundle, "talk", "") or "")
    requirements = _extract_markdown_section(talk_text, "reply_requirements")
    if requirements:
        return requirements
    return "先给结论，再展开；只陈述真实执行过的动作。"


def _render_scene_block(prompt_mode: str, project_phase: str, bundle) -> str:
    lines = [f"【当前场景】\nmode={prompt_mode}"]
    if prompt_mode == PROJECT_MAIN_MODE:
        lines.append(f"phase={canonical_project_phase(project_phase) or 'plan'}")
    lines.append(_resolve_talk_mode_guidance(bundle, prompt_mode))
    return "\n".join(lines)


def _resolve_prompt_mode(
    user_prompt: str,
    *,
    explicit_mode: str | None = None,
    frontdoor_context: FrontDoorContext | None = None,
) -> str:
    text = str(user_prompt or "").strip()
    context = frontdoor_context or FrontDoorContext()
    normalized_explicit_mode = canonical_main_mode(explicit_mode)
    if str(explicit_mode or "").strip():
        return normalized_explicit_mode
    if context.mode == "content_share" or context.frontdoor_action == "respond_to_shared_content":
        return SHARE_MAIN_MODE
    if context.frontdoor_action in {"discuss_backend_entry", "query_status"} or context.explicit_backend_request:
        return BACKGROUND_MAIN_MODE
    lowered = text.lower()
    if any(keyword in lowered for keyword in (item.lower() for item in _MAINTENANCE_TRIGGER_KEYWORDS)):
        return "maintenance"
    if _is_content_share_prompt(text):
        return SHARE_MAIN_MODE
    if any(keyword in text for keyword in _COMPANION_TRIGGER_KEYWORDS):
        return "companion"
    return CHAT_MAIN_MODE


def _is_content_share_prompt(user_prompt: str) -> bool:
    text = str(user_prompt or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if any(pattern in lowered for pattern in _CONTENT_SHARE_LINK_PATTERNS):
        return True
    if "复制后打开" in text or "查看笔记" in text or "转发" in text:
        return True
    if len(text) <= 220 and text.count("\n") >= 1 and ("http" in lowered or "链接" in text or "截图" in text):
        return True
    return False


def _should_include_request_intake_block(
    prompt_mode: str,
    source_prompt: str,
    frontdoor_context: FrontDoorContext | None = None,
) -> bool:
    context = frontdoor_context or FrontDoorContext()
    if context.frontdoor_action and context.frontdoor_action != "normal_chat":
        return True
    if prompt_mode == BACKGROUND_MAIN_MODE:
        return True
    if prompt_mode == "companion":
        return False
    return prompt_mode in {"maintenance"} and bool(str(source_prompt or "").strip())


def _frontdoor_context_implies_execution(frontdoor_context: FrontDoorContext) -> bool:
    if frontdoor_context.mode in {"async_program", "sync_then_async"}:
        return True
    if frontdoor_context.frontdoor_action in {"discuss_backend_entry", "query_status"}:
        return True
    return any(
        (
            frontdoor_context.explicit_backend_request,
            frontdoor_context.should_discuss_mode_first,
        )
    )


def _should_include_frontdoor_blocks(
    prompt_mode: str,
    frontdoor_context: FrontDoorContext,
    *,
    frontdoor_enabled: bool,
) -> bool:
    if prompt_mode == BACKGROUND_MAIN_MODE:
        return True
    if not frontdoor_enabled:
        return False
    return bool(context_has_frontdoor_action(frontdoor_context))


def _should_include_task_protocol(prompt_mode: str, project_phase: str, *, frontdoor_enabled: bool) -> bool:
    normalized_project_phase = canonical_project_phase(project_phase)
    if prompt_mode == PROJECT_MAIN_MODE:
        return normalized_project_phase == "imp"
    if prompt_mode == BACKGROUND_MAIN_MODE:
        return True
    if prompt_mode == "maintenance":
        return frontdoor_enabled
    return False


def context_has_frontdoor_action(frontdoor_context: FrontDoorContext) -> bool:
    return bool(
        (
            frontdoor_context.frontdoor_action
            and frontdoor_context.frontdoor_action != "normal_chat"
        )
        or frontdoor_context.explicit_backend_request
    )


def _should_include_self_mind_protocol(prompt_mode: str, source_prompt: str, inject_soul: bool) -> bool:
    if prompt_mode in {"companion", "maintenance"}:
        return True
    text = str(source_prompt or "")
    return inject_soul and any(keyword in text for keyword in ("self_mind", "self-mind", "小我", "内心"))


def _should_strongly_remind_skills(source_prompt: str) -> bool:
    text = str(source_prompt or "").lower()
    return any(keyword in text for keyword in ("skill", "技能", "mcp", "调用", "抓取", "ocr", "检索"))


def _render_skills_prompt_block(
    workspace_root: str | Path | None,
    source_prompt: str,
    skills_prompt: str,
    collection_id: str | None = None,
) -> str:
    return render_skill_prompt_block(
        workspace_root,
        source_prompt=source_prompt,
        skills_prompt=skills_prompt,
        collection_id=collection_id,
        strong_reminder=_should_strongly_remind_skills(source_prompt),
    )


def _should_include_agent_capabilities(
    source_prompt: str,
    prompt_mode: str,
    *,
    project_phase: str = "",
) -> bool:
    return should_include_agent_capabilities_prompt(
        source_prompt,
        prompt_mode,
        project_phase=project_phase,
    )


def should_include_agent_capabilities_prompt(
    source_prompt: str,
    prompt_mode: str,
    *,
    project_phase: str = "",
) -> bool:
    if prompt_mode == PROJECT_MAIN_MODE:
        return canonical_project_phase(project_phase) == "imp"
    if prompt_mode not in {CHAT_MAIN_MODE, "maintenance"}:
        return False
    text = str(source_prompt or "").lower()
    return any(
        keyword in text
        for keyword in ("sub-agent", "subagent", "agent team", "并行", "分工", "协作", "拆任务", "parallel")
    )


def _should_inject_butler_soul(user_prompt: str, prompt_mode: str = CHAT_MAIN_MODE) -> bool:
    prompt_text = str(user_prompt or "").strip()
    if not prompt_text:
        return False
    if prompt_mode in {"companion", "maintenance"}:
        return True
    if prompt_mode in {SHARE_MAIN_MODE, PROJECT_MAIN_MODE, BACKGROUND_MAIN_MODE}:
        return False
    if len(prompt_text) >= 160:
        return True
    return any(keyword in prompt_text for keyword in _SOUL_TRIGGER_KEYWORDS)


def _load_markdown_excerpt(rel_path: Path, max_chars: int) -> str:
    try:
        workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
        path = ensure_chat_data_layout(workspace_root) / rel_path
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not text:
        return ""
    return _truncate_with_ellipsis(text, max_chars=max_chars)


def _load_butler_soul_excerpt(max_chars: int = 2200) -> str:
    return _load_markdown_excerpt(BUTLER_SOUL_FILE_REL, max_chars=max_chars)
def _load_current_user_profile_excerpt(max_chars: int = 1400) -> str:
    try:
        workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
        root = ensure_chat_data_layout(workspace_root)
        for rel_path in (CURRENT_USER_PROFILE_FILE_REL, CURRENT_USER_PROFILE_TEMPLATE_FILE_REL):
            path = root / rel_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            return _truncate_with_ellipsis(text, max_chars=max_chars)
    except OSError:
        return ""
    return ""


def _load_current_conversation_rules_excerpt(max_chars: int = 800) -> str:
    try:
        workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
        root = ensure_chat_data_layout(workspace_root)
        path = root / CURRENT_USER_PROFILE_FILE_REL
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not text:
        return ""
    pattern = re.compile(r"(?ms)^##\s+当前对话硬约束\s*$\n(.*?)(?=^##\s+|\Z)")
    match = pattern.search(text)
    if not match:
        return ""
    block = str(match.group(1) or "").strip()
    if not block:
        return ""
    return _truncate_with_ellipsis(block, max_chars=max_chars)


def _load_self_mind_context_excerpt(max_chars: int = 1400) -> str:
    return _load_markdown_excerpt(SELF_MIND_DIR_REL / "current_context.md", max_chars=max_chars)


def _load_self_mind_cognition_excerpt(max_chars: int = 1000) -> str:
    try:
        workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
        root = ensure_chat_data_layout(workspace_root)
        cognition_root = root / SELF_MIND_DIR_REL / "cognition"
        index_path = cognition_root / "L0_index.json"
        if not index_path.exists():
            return ""
        raw_text = index_path.read_text(encoding="utf-8").strip()
        if not raw_text:
            return ""
        data = json.loads(raw_text)
        categories = data.get("categories") if isinstance(data, dict) else None
        if not isinstance(categories, list) or not categories:
            excerpt = raw_text
        else:
            lines = ["L0 认知索引："]
            for item in categories[:8]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "未命名分类").strip()
                summary = str(item.get("summary") or "").strip()
                signal_count = item.get("signal_count")
                header = f"- {name}"
                if isinstance(signal_count, int):
                    header += f"（signals={signal_count}）"
                lines.append(header)
                if summary:
                    lines.append(f"  {summary}")
            excerpt = "\n".join(lines).strip()
        if len(excerpt) <= max_chars:
            return excerpt
        return _truncate_with_ellipsis(excerpt, max_chars=max_chars)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return ""


def _truncate_with_ellipsis(text: str, *, max_chars: int) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip() + "\n..."


def _render_sourced_excerpt(
    *,
    source_refs: list[str],
    excerpt: str,
    summary_lead: str = "",
) -> str:
    normalized_excerpt = str(excerpt or "").strip()
    if not normalized_excerpt:
        return ""
    lines: list[str] = []
    rendered_refs = [f"@{ref}" for ref in source_refs if str(ref or "").strip()]
    if rendered_refs:
        lines.append("真源：" + "；".join(rendered_refs))
    if summary_lead:
        lines.append(summary_lead)
    lines.append("摘要：")
    lines.append(normalized_excerpt)
    return "\n".join(lines).strip()


def _apply_injection_tier_overlay(
    purity_policy: PromptPurityPolicy,
    injection_tier: str,
) -> PromptPurityPolicy:
    if canonical_injection_tier(injection_tier) != "minimal":
        return purity_policy
    return replace(
        purity_policy,
        include_bootstrap=False,
        include_dialogue_asset=False,
        include_conversation_rules=False,
        include_user_profile=False,
        include_local_memory=False,
        include_self_mind=False,
        include_soul_excerpt=False,
        include_soul_source_ref=False,
        include_extended_protocols=False,
        include_agent_capabilities=False,
        skills_mode="on_demand" if purity_policy.skills_mode != "never" else "never",
    )


def _render_role_asset_block(
    role_id: str | None,
    injection_tier: str,
    capability_policy: str,
    *,
    include_source_ref: bool = True,
) -> str:
    parts = [f"【角色设置】@{AGENT_ROLE_FILE}" if include_source_ref else "【角色设置】"]
    role_block = render_role_prompt(str(role_id or "").strip())
    if role_block:
        parts.append(role_block)
    parts.append(
        "\n".join(
            [
                "【前台 Router 编译结果】",
                f"- 注入等级：{canonical_injection_tier(injection_tier)}",
                f"- 能力策略：{canonical_capability_policy(capability_policy)}",
            ]
        )
    )
    return "\n".join(part for part in parts if part).strip()


def _render_session_selection_block(
    *,
    session_action: str | None,
    session_confidence: str | None,
    session_reason_flags: str | None,
) -> str:
    action = str(session_action or "continue_current").strip() or "continue_current"
    confidence = str(session_confidence or "medium").strip() or "medium"
    reasons = str(session_reason_flags or "").strip()
    if action == "reopen_new_session":
        guidance = "把当前消息视为新话题，不沿用旧主线；只有用户显式引用刚才内容时才回看旧 recent。"
    else:
        guidance = "优先沿当前 chat session 续接，主动补全省略主语、对象、文件或方案选择。"
    reason_line = f"- 原因：{reasons}" if reasons else ""
    return "\n".join(
        line
        for line in (
            "【会话续接判断】",
            f"- 动作：{action}",
            f"- 置信度：{confidence}",
            reason_line,
            f"- 快速规则：{guidance}",
            "- 只有存在两个以上高概率解释且会导致不同动作时，才要求澄清。",
        )
        if line
    ).strip()


def _make_prompt_block(
    block_id: str,
    text: str,
    *,
    include_reason: str,
    source_ref: str = "",
    budget_chars: int = 0,
    suppressed_by: str = "",
) -> dict[str, Any]:
    return {
        "block_id": block_id,
        "text": str(text or "").strip(),
        "include_reason": include_reason,
        "source_ref": source_ref,
        "budget_chars": int(budget_chars or 0),
        "suppressed_by": suppressed_by,
    }


def _render_prompt_from_blocks(
    blocks: list[dict[str, Any]],
    *,
    prompt_debug_metadata: dict[str, Any] | None,
    dialogue_debug_metadata: dict[str, Any] | None,
    router_metadata: Mapping[str, Any] | None = None,
) -> str:
    block_stats: list[dict[str, Any]] = []
    rendered_blocks: list[str] = []
    for block in blocks:
        text = str(block.get("text") or "").strip()
        block_id = str(block.get("block_id") or "").strip()
        budget_chars = int(block.get("budget_chars") or 0)
        block_stats.append(
            {
                "block_id": block_id,
                "char_count": len(text),
                "include_reason": str(block.get("include_reason") or "").strip(),
                "suppressed_by": "" if text else str(block.get("suppressed_by") or "").strip(),
                "source_ref": str(block.get("source_ref") or "").strip(),
                "budget_chars": budget_chars,
                "over_budget": bool(budget_chars and len(text) > budget_chars),
            }
        )
        if text:
            rendered_blocks.append(text)
    if dialogue_debug_metadata:
        block_stats.extend(list(dialogue_debug_metadata.get("dialogue_block_stats") or []))
    if prompt_debug_metadata is not None:
        prompt_debug_metadata["block_stats"] = block_stats
        prompt_debug_metadata["block_budgets"] = dict(_PROMPT_BLOCK_BUDGETS)
        if isinstance(router_metadata, Mapping):
            prompt_debug_metadata.update(
                {
                    "role_id": str(router_metadata.get("role_id") or "").strip(),
                    "injection_tier": str(router_metadata.get("injection_tier") or "").strip(),
                    "capability_policy": str(router_metadata.get("capability_policy") or "").strip(),
                    "skill_collection_id": str(router_metadata.get("skill_collection_id") or "").strip(),
                }
            )
    return "\n\n".join(rendered_blocks) + "\n"


def render_available_agent_capabilities_prompt(workspace: str | None = None, max_chars: int = 2400) -> str:
    return _PROMPT_SUPPORT_PROVIDER.render_agent_capabilities_prompt(
        str(workspace or get_config().get("workspace_root") or "."),
        max_chars=max_chars,
    )


build_feishu_agent_prompt = build_chat_agent_prompt


__all__ = [
    "AGENT_ROLE_FILE",
    "BUTLER_SOUL_FILE",
    "CONFIG",
    "CURRENT_USER_PROFILE_FILE",
    "CURRENT_USER_PROFILE_TEMPLATE_FILE",
    "SELF_MIND_COGNITION_INDEX_FILE",
    "SELF_MIND_CONTEXT_FILE",
    "build_chat_agent_prompt",
    "build_feishu_agent_prompt",
    "get_config",
    "render_available_agent_capabilities_prompt",
    "set_config_provider",
    "should_include_agent_capabilities_prompt",
]
