from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from butler_main.agents_os.runtime.provider_interfaces import PromptRuntimeProvider
from butler_main.chat.channel_profiles import resolve_channel_profile
from butler_main.chat.prompt_purity import resolve_prompt_purity_policy, should_include_skills_for_purity
from butler_main.chat.prompting import build_chat_agent_prompt
from .butler_prompt_support_provider import ButlerChatPromptSupportProvider


_SUPPORT_PROVIDER = ButlerChatPromptSupportProvider()


class ButlerChatPromptProvider(PromptRuntimeProvider):
    """Transitional Butler-backed prompt provider for the chat app."""

    def render_skills_prompt(self, workspace: str) -> str:
        return self.render_skills_prompt_for_collection(workspace, collection_id="chat_default")

    def render_skills_prompt_for_collection(self, workspace: str, *, collection_id: str | None = None) -> str:
        return _SUPPORT_PROVIDER.render_skills_prompt(
            workspace,
            collection_id=collection_id,
            max_skills=100,
            max_chars=2000,
        )

    def render_agent_capabilities_prompt(self, workspace: str) -> str:
        return _SUPPORT_PROVIDER.render_agent_capabilities_prompt(workspace, max_chars=2400)

    def build_prompt(
        self,
        user_prompt: str,
        *,
        workspace: str,
        image_paths: Sequence[str] | None = None,
        raw_user_prompt: str | None = None,
        request_intake_prompt: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        metadata = dict(metadata or {})
        skills_prompt = str(metadata.get("skills_prompt") or "").strip()
        skill_exposure = metadata.get("skill_exposure") if isinstance(metadata.get("skill_exposure"), Mapping) else None
        skill_collection_id = str(metadata.get("skill_collection_id") or "").strip() or None
        agent_capabilities_prompt = str(metadata.get("agent_capabilities_prompt") or "").strip()
        feishu_doc_search_result = str(metadata.get("feishu_doc_search_result") or "").strip() or None
        runtime_cli = str(metadata.get("runtime_cli") or "").strip() or None
        prompt_purity = metadata.get("prompt_purity") if isinstance(metadata.get("prompt_purity"), Mapping) else None
        purity_policy = resolve_prompt_purity_policy(prompt_purity)
        channel = str(metadata.get("channel") or "").strip() or None
        request_intake_decision = metadata.get("request_intake_decision")
        channel_profile = metadata.get("channel_profile")
        conversation_mode = str(metadata.get("conversation_mode") or "").strip() or None
        project_phase = str(metadata.get("project_phase") or "").strip() or None
        role_id = str(metadata.get("role_id") or "").strip() or None
        injection_tier = str(metadata.get("injection_tier") or "").strip() or None
        capability_policy = str(metadata.get("capability_policy") or "").strip() or None
        session_action = str(metadata.get("session_action") or "").strip() or None
        session_confidence = str(metadata.get("session_confidence") or "").strip() or None
        session_reason_flags = str(metadata.get("session_reason_flags") or "").strip() or None
        prompt_debug_metadata = metadata.get("prompt_debug_metadata")
        if channel_profile is None:
            channel_profile = resolve_channel_profile(channel)
        if not skills_prompt and skill_exposure and should_include_skills_for_purity(
            str(raw_user_prompt or user_prompt or ""),
            purity_policy,
        ):
            skills_prompt = _SUPPORT_PROVIDER.render_skill_exposure_prompt(
                workspace,
                exposure=dict(skill_exposure),
                source_prompt=str(raw_user_prompt or user_prompt or ""),
                runtime_name="chat",
                max_skills=100,
                max_chars=2000,
            )
        return build_chat_agent_prompt(
            user_prompt,
            list(image_paths or []) or None,
            feishu_doc_search_result=feishu_doc_search_result,
            skills_prompt=skills_prompt or None,
            skill_collection_id=skill_collection_id,
            agent_capabilities_prompt=agent_capabilities_prompt or None,
            raw_user_prompt=raw_user_prompt,
            request_intake_prompt=request_intake_prompt,
            request_intake_decision=request_intake_decision if isinstance(request_intake_decision, Mapping) else None,
            runtime_cli=runtime_cli,
            prompt_purity=prompt_purity,
            channel=channel,
            channel_profile=channel_profile,
            conversation_mode=conversation_mode,
            project_phase=project_phase,
            role_id=role_id,
            injection_tier=injection_tier,
            capability_policy=capability_policy,
            session_action=session_action,
            session_confidence=session_confidence,
            session_reason_flags=session_reason_flags,
            prompt_debug_metadata=prompt_debug_metadata if isinstance(prompt_debug_metadata, dict) else None,
        )


__all__ = ["ButlerChatPromptProvider"]
