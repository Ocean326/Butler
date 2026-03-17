from __future__ import annotations

from .adapters.local_writer_adapter import LocalMemoryWriterAdapter
from .adapters.profile_writer import UserProfileWriterAdapter
from .adapters.recent_adapter import RecentMemoryAdapter
from .agents import CompactMemoryAgent, MaintenanceMemoryAgent, PostTurnMemoryAgent
from .config import MemoryPipelineConfig
from .feature_flags import MemoryPipelineFeatureFlags
from .models import CompactMemoryInput, MaintenanceMemoryInput, MemoryWriteRequest, PostTurnMemoryInput, ProfileWriteRequest
from .policies import COMPACT_POLICY, MAINTENANCE_POLICY, POST_TURN_POLICY


class MemoryPipelineOrchestrator:
    """Coordinate memory agents and adapters without owning governance logic."""

    def __init__(self, manager) -> None:
        self._manager = manager
        self._recent_adapter = RecentMemoryAdapter(manager)
        self._local_writer = LocalMemoryWriterAdapter(manager)
        self._profile_writer = UserProfileWriterAdapter(manager)
        self._post_turn_agent = PostTurnMemoryAgent()
        self._compact_agent = CompactMemoryAgent()
        self._maintenance_agent = MaintenanceMemoryAgent()

    def flags(self) -> MemoryPipelineFeatureFlags:
        return MemoryPipelineFeatureFlags.from_runtime_config(self._manager._config_provider() or {})

    def config(self) -> MemoryPipelineConfig:
        return MemoryPipelineConfig.from_runtime_config(self._manager._config_provider() or {})

    def run_post_turn(
        self,
        *,
        workspace: str,
        memory_id: str,
        user_prompt: str,
        assistant_reply: str,
        candidate_memory: dict,
        suppress_task_merge: bool,
        allow_local_write: bool = True,
        allow_profile_write: bool = True,
    ):
        result = self._post_turn_agent.run(
            PostTurnMemoryInput(
                workspace=workspace,
                memory_id=memory_id,
                user_prompt=user_prompt,
                assistant_reply=assistant_reply,
                candidate_memory=candidate_memory,
                recent_entries=tuple(self._recent_adapter.load_recent_entries(workspace)),
                local_memory_hits=tuple(
                    self._recent_adapter.query_local_memory(
                        workspace,
                        query_text=" ".join(
                            part for part in (
                                str(candidate_memory.get("topic") or "").strip(),
                                str(candidate_memory.get("summary") or "").strip(),
                            )
                            if part
                        ),
                        limit=6,
                    )
                ),
                profile_excerpt=self._recent_adapter.load_profile_excerpt(workspace, max_chars=800),
                suppress_task_merge=suppress_task_merge,
            )
        )
        local_actions: list[str] = []
        profile_actions: list[str] = []
        if POST_TURN_POLICY.allow_local_write and allow_local_write:
            for request in result.local_writes:
                local_actions.append(self._local_writer.apply(workspace, request))
        if POST_TURN_POLICY.allow_profile_write and allow_profile_write:
            for request in result.profile_writes:
                profile_actions.append(self._profile_writer.apply(workspace, request))
        return result, local_actions, profile_actions

    def run_compact(self, *, workspace: str, reason: str, pool: str, old_entries: list[dict], keep_entries: list[dict]):
        result = self._compact_agent.run(
            CompactMemoryInput(
                workspace=workspace,
                reason=reason,
                pool=pool,
                old_entries=tuple(old_entries),
                keep_entries=tuple(keep_entries),
            )
        )
        actions: list[str] = []
        if COMPACT_POLICY.allow_local_write:
            for candidate in result.summary_candidates:
                if candidate.channel not in COMPACT_POLICY.allowed_channels:
                    continue
                actions.append(
                    self._local_writer.apply(
                        workspace,
                        MemoryWriteRequest(
                            channel=candidate.channel,
                            title=candidate.title,
                            summary=candidate.summary,
                            keywords=candidate.keywords,
                            source_type="compact-agent",
                            source_reason=f"compact:{candidate.channel}",
                            source_topic=candidate.title,
                        ),
                    )
                )
        return result, actions

    def run_maintenance(self, *, workspace: str, reason: str, scope: str):
        config = self.config()
        local_hits = self._recent_adapter.query_local_memory(workspace, query_text="长期记忆 偏好 默认 规则 项目", limit=config.maintenance_duplicate_query_limit)
        result = self._maintenance_agent.run(
            MaintenanceMemoryInput(
                workspace=workspace,
                reason=reason,
                scope=scope,
                recent_entries=tuple(self._recent_adapter.load_recent_entries(workspace)),
                local_memory_hits=tuple(local_hits),
                profile_excerpt=self._recent_adapter.load_profile_excerpt(workspace, max_chars=600),
            )
        )
        actions: list[str] = []
        if MAINTENANCE_POLICY.allow_local_write:
            for request in result.dedupe_writes:
                if request.channel not in MAINTENANCE_POLICY.allowed_channels:
                    continue
                actions.append(self._local_writer.apply(workspace, request))
        return result, actions

    def apply_profile_write(self, workspace: str, request: ProfileWriteRequest) -> str:
        return self._profile_writer.apply(workspace, request)
