from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from butler_paths import resolve_butler_root
from services.local_memory_index_service import LocalMemoryIndexService


@dataclass(frozen=True)
class DialoguePromptContext:
    prompt_mode: str
    butler_soul_text: str
    butler_main_agent_text: str
    current_user_profile_text: str
    local_memory_text: str
    self_mind_text: str
    self_mind_cognition_text: str


@dataclass(frozen=True)
class PlannerPromptContext:
    base_prompt_text: str
    json_schema: str
    now_text: str
    soul_text: str
    role_text: str
    max_parallel: str
    max_serial_per_group: str
    autonomous_mode_text: str
    fixed_metabolism_text: str
    background_growth_text: str
    tasks_context: str
    recent_memory_text: str
    local_memory_text: str
    skills_text: str
    task_workspace_context: str
    subagents_text: str
    teams_text: str
    public_library_text: str
    maintenance_entry_text: str
    runtime_context_text: str


class PromptAssemblyService:
    def render_local_memory_hits(
        self,
        workspace_root: str | Path,
        query_text: str,
        *,
        limit: int = 4,
        include_details: bool = False,
        max_chars: int = 2400,
        memory_types: tuple[str, ...] = (),
    ) -> str:
        normalized_query = str(query_text or "").strip()
        if not normalized_query:
            return ""
        local_dir = self._resolve_local_memory_dir(workspace_root)
        service = LocalMemoryIndexService(local_dir)
        return service.render_prompt_hits(
            normalized_query,
            limit=limit,
            include_details=include_details,
            max_chars=max_chars,
            memory_types=memory_types,
        )

    def assemble_dialogue_prompt(self, context: DialoguePromptContext) -> str:
        blocks = [self._render_base_role_block()]
        if context.butler_main_agent_text.strip():
            blocks.append("【主意识摘录】\n" + context.butler_main_agent_text.strip())
        if context.butler_soul_text.strip():
            blocks.append("【灵魂摘录】\n" + context.butler_soul_text.strip())
        if context.current_user_profile_text.strip():
            blocks.append("【当前用户画像】\n" + context.current_user_profile_text.strip())
        if context.local_memory_text.strip():
            blocks.append("【长期记忆命中】\n" + context.local_memory_text.strip())
        if context.self_mind_text.strip():
            blocks.append("【self_mind 当前上下文】\n" + context.self_mind_text.strip())
        if context.self_mind_cognition_text.strip():
            blocks.append("【self_mind 认知体系】\n" + context.self_mind_cognition_text.strip())
        return "\n\n".join(block for block in blocks if block.strip()).strip()

    def assemble_planner_prompt(self, context: PlannerPromptContext) -> str:
        replacements = {
            "{json_schema}": context.json_schema.strip(),
            "{now_text}": context.now_text.strip(),
            "{soul_text}": context.soul_text.strip(),
            "{role_text}": context.role_text.strip(),
            "{max_parallel}": context.max_parallel.strip(),
            "{max_serial_per_group}": context.max_serial_per_group.strip(),
            "{autonomous_mode_text}": context.autonomous_mode_text.strip(),
            "{fixed_metabolism_text}": context.fixed_metabolism_text.strip(),
            "{background_growth_text}": context.background_growth_text.strip(),
            "{tasks_context}": context.tasks_context.strip(),
            "{short_tasks_json}": context.tasks_context.strip(),
            "{long_tasks_json}": context.tasks_context.strip(),
            "{context_text}": context.runtime_context_text.strip(),
            "{agent_prompt}": context.runtime_context_text.strip(),
            "{{RECENT_MEMORY}}": context.recent_memory_text.strip(),
            "{{LOCAL_MEMORY}}": context.local_memory_text.strip(),
            "{recent_text}": context.recent_memory_text.strip(),
            "{local_memory_text}": context.local_memory_text.strip(),
            "{skills_text}": context.skills_text.strip(),
            "{task_workspace_text}": context.task_workspace_context.strip(),
            "{subagents_text}": context.subagents_text.strip(),
            "{teams_text}": context.teams_text.strip(),
            "{public_library_text}": context.public_library_text.strip(),
            "{maintenance_entry_text}": context.maintenance_entry_text.strip(),
        }
        rendered = context.base_prompt_text
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        return rendered.strip()

    def _resolve_local_memory_dir(self, workspace_root: str | Path) -> Path:
        root = resolve_butler_root(Path(workspace_root))
        return root / "butler_main" / "butler_bot_agent" / "agents" / "local_memory"

    def _render_base_role_block(self) -> str:
        return (
            "你是 Butler。\n"
            "优先给出真实、可执行、面向当下任务的回应。\n"
            "若长期记忆与当前上下文冲突，以当前用户明确表达和当前任务事实为准。"
        )

