from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryPipelineConfig:
    enabled: bool = False
    enable_post_turn_agent: bool = False
    enable_compact_agent: bool = False
    enable_maintenance_agent: bool = False
    recent_compact_min_entries: int = 6
    maintenance_duplicate_query_limit: int = 24

    @classmethod
    def from_runtime_config(cls, cfg: dict | None) -> "MemoryPipelineConfig":
        memory_cfg = (cfg or {}).get("memory") if isinstance(cfg, dict) else {}
        memory_cfg = memory_cfg if isinstance(memory_cfg, dict) else {}
        raw = memory_cfg.get("pipeline")
        payload = raw if isinstance(raw, dict) else {}
        enabled = bool(payload.get("enabled"))
        return cls(
            enabled=enabled,
            enable_post_turn_agent=bool(payload.get("enable_post_turn_agent", enabled)),
            enable_compact_agent=bool(payload.get("enable_compact_agent", enabled)),
            enable_maintenance_agent=bool(payload.get("enable_maintenance_agent", enabled)),
            recent_compact_min_entries=max(1, int(payload.get("recent_compact_min_entries", 6) or 6)),
            maintenance_duplicate_query_limit=max(4, int(payload.get("maintenance_duplicate_query_limit", 24) or 24)),
        )
