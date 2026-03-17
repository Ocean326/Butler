from __future__ import annotations

from dataclasses import dataclass

from .config import MemoryPipelineConfig


@dataclass(frozen=True)
class MemoryPipelineFeatureFlags:
    enabled: bool
    post_turn_agent: bool
    compact_agent: bool
    maintenance_agent: bool

    @classmethod
    def from_runtime_config(cls, cfg: dict | None) -> "MemoryPipelineFeatureFlags":
        pipeline = MemoryPipelineConfig.from_runtime_config(cfg)
        return cls(
            enabled=pipeline.enabled,
            post_turn_agent=bool(pipeline.enabled and pipeline.enable_post_turn_agent),
            compact_agent=bool(pipeline.enabled and pipeline.enable_compact_agent),
            maintenance_agent=bool(pipeline.enabled and pipeline.enable_maintenance_agent),
        )
