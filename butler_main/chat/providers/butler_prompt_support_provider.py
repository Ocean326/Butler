from __future__ import annotations

from pathlib import Path

from butler_main.agents_os.runtime.local_memory_index import LocalMemoryIndexService
from butler_main.agents_os.skills import render_skill_catalog_for_prompt, render_skill_exposure_prompt
from butler_main.chat.pathing import LOCAL_MEMORY_DIR_REL, ensure_chat_data_layout
from butler_main.chat.prompt_support import (
    get_protocol_registry,
    render_agent_capability_catalog_for_prompt,
)


class ButlerChatPromptSupportProvider:
    """Chat-side adapter over legacy definition/prompt support sources."""

    def __init__(self) -> None:
        self._protocol_registry = get_protocol_registry()

    def render_skills_prompt(
        self,
        workspace: str,
        *,
        collection_id: str | None = None,
        max_skills: int = 100,
        max_chars: int = 2000,
    ) -> str:
        return render_skill_catalog_for_prompt(
            workspace,
            collection_id=collection_id,
            max_skills=max_skills,
            max_chars=max_chars,
        )

    def render_agent_capabilities_prompt(self, workspace: str, *, max_chars: int = 2400) -> str:
        return render_agent_capability_catalog_for_prompt(workspace, max_chars=max_chars)

    def render_skill_exposure_prompt(
        self,
        workspace: str,
        *,
        exposure: dict | None,
        source_prompt: str,
        runtime_name: str = "",
        max_skills: int = 100,
        max_chars: int = 2000,
    ) -> str:
        return render_skill_exposure_prompt(
            workspace,
            exposure=exposure,
            source_prompt=source_prompt,
            runtime_name=runtime_name,
            max_catalog_skills=max_skills,
            max_catalog_chars=max_chars,
        )

    def render_protocol_block(self, protocol_id: str, *, heading: str | None = None) -> str:
        return self._protocol_registry.render_prompt_block(protocol_id, heading=heading).strip()

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
        local_dir = ensure_chat_data_layout(Path(workspace_root)) / LOCAL_MEMORY_DIR_REL
        service = LocalMemoryIndexService(local_dir)
        return service.render_prompt_hits(
            normalized_query,
            limit=limit,
            include_details=include_details,
            max_chars=max_chars,
            memory_types=memory_types,
        )


__all__ = ["ButlerChatPromptSupportProvider"]
