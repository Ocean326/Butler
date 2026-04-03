from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DialoguePromptContext:
    prompt_mode: str
    butler_soul_text: str
    butler_main_agent_text: str
    current_conversation_rules_text: str
    current_user_profile_text: str
    local_memory_text: str
    self_mind_text: str
    self_mind_cognition_text: str

def assemble_dialogue_prompt(
    context: DialoguePromptContext,
    *,
    debug_metadata: dict[str, Any] | None = None,
) -> str:
    entries: list[dict[str, Any]] = []
    _append_dialogue_entry(
        entries,
        block_id="dialogue_base",
        title="【对话骨架】",
        body=_render_base_role_block(),
        include_reason="always",
        source_ref="dialogue_prompting._render_base_role_block",
    )
    _append_dialogue_entry(
        entries,
        block_id="dialogue_main_agent",
        title="【主意识摘录】",
        body=context.butler_main_agent_text,
        include_reason="context",
        suppressed_by="empty_excerpt",
    )
    _append_dialogue_entry(
        entries,
        block_id="dialogue_soul_excerpt",
        title="【灵魂摘录】",
        body=context.butler_soul_text,
        include_reason="policy+mode",
        suppressed_by="purity_or_mode_gate",
    )
    _append_dialogue_entry(
        entries,
        block_id="dialogue_conversation_rules",
        title="【当前对话硬约束 / 最近确认规则】",
        body=context.current_conversation_rules_text,
        include_reason="policy",
        suppressed_by="purity_or_missing_rules",
    )
    _append_dialogue_entry(
        entries,
        block_id="dialogue_user_profile",
        title="【当前用户画像】",
        body=context.current_user_profile_text,
        include_reason="policy",
        suppressed_by="purity_or_missing_profile",
    )
    _append_dialogue_entry(
        entries,
        block_id="dialogue_local_memory",
        title="【长期记忆命中】",
        body=context.local_memory_text,
        include_reason="retrieval",
        suppressed_by="purity_or_no_memory_hits",
    )
    _append_dialogue_entry(
        entries,
        block_id="dialogue_self_mind",
        title="【self_mind 当前上下文】",
        body=context.self_mind_text,
        include_reason="mode_or_keyword",
        suppressed_by="purity_or_not_relevant",
    )
    _append_dialogue_entry(
        entries,
        block_id="dialogue_self_mind_cognition",
        title="【self_mind 认知体系】",
        body=context.self_mind_cognition_text,
        include_reason="mode_or_keyword",
        suppressed_by="purity_or_not_relevant",
    )
    rendered_blocks = [str(entry.get("text") or "").strip() for entry in entries if str(entry.get("text") or "").strip()]
    if debug_metadata is not None:
        debug_metadata["dialogue_block_stats"] = [
            {
                "block_id": str(entry.get("block_id") or "").strip(),
                "char_count": len(str(entry.get("text") or "").strip()),
                "include_reason": str(entry.get("include_reason") or "").strip(),
                "suppressed_by": (
                    ""
                    if str(entry.get("text") or "").strip()
                    else str(entry.get("suppressed_by") or "").strip()
                ),
                "source_ref": str(entry.get("source_ref") or "").strip(),
            }
            for entry in entries
        ]
    return "\n\n".join(rendered_blocks).strip()


def _render_base_role_block() -> str:
    return (
        "你是 Butler。\n"
        "优先给出真实、可执行、面向当下任务的回应。\n"
        "若长期记忆与当前上下文冲突，以当前用户明确表达和当前任务事实为准。"
    )


def _append_dialogue_entry(
    entries: list[dict[str, Any]],
    *,
    block_id: str,
    title: str,
    body: str,
    include_reason: str,
    source_ref: str = "",
    suppressed_by: str = "",
) -> None:
    normalized_body = str(body or "").strip()
    text = f"{title}\n{normalized_body}" if normalized_body else ""
    entries.append(
        {
            "block_id": block_id,
            "text": text,
            "include_reason": include_reason,
            "source_ref": source_ref,
            "suppressed_by": suppressed_by,
        }
    )

__all__ = ["DialoguePromptContext", "assemble_dialogue_prompt"]
