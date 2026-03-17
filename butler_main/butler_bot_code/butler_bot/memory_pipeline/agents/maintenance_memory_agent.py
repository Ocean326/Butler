from __future__ import annotations

from pathlib import Path

from ..models import MaintenanceMemoryInput, MaintenanceMemoryResult, MemoryWriteRequest


class MaintenanceMemoryAgent:
    def __init__(self) -> None:
        self.prompt = (Path(__file__).resolve().parents[1] / "prompts" / "maintenance_memory_agent.md").read_text(encoding="utf-8")

    def run(self, payload: MaintenanceMemoryInput) -> MaintenanceMemoryResult:
        notes: list[str] = []
        dedupe_writes: list[MemoryWriteRequest] = []
        if payload.scope in {"local", "full"} and len(payload.local_memory_hits) >= 2:
            duplicate = self._find_duplicate(payload.local_memory_hits)
            if duplicate:
                notes.append("duplicate local memory candidate detected")
                dedupe_writes.append(
                    MemoryWriteRequest(
                        channel="local_memory",
                        title=str(duplicate.get("title") or "长期记忆整理")[:40],
                        summary=str(duplicate.get("summary") or "")[:220],
                        keywords=tuple(str(x).strip() for x in (duplicate.get("keywords") or []) if str(x).strip()),
                        source_type="maintenance-agent",
                        source_reason="canonical_rewrite",
                        source_topic=str(duplicate.get("title") or "长期记忆整理")[:40],
                    )
                )

        run_recent_prune = payload.scope in {"recent", "full"} and bool(payload.recent_entries)
        run_recent_compact = payload.scope in {"recent", "full"} and len(payload.recent_entries) > 12
        run_local_rewrite = payload.scope in {"local", "full"}
        if run_recent_prune:
            notes.append("recent prune requested")
        if run_local_rewrite:
            notes.append("local rewrite requested")

        return MaintenanceMemoryResult(
            run_recent_prune=run_recent_prune,
            run_recent_compact=run_recent_compact,
            run_local_rewrite=run_local_rewrite,
            dedupe_writes=tuple(dedupe_writes),
            audit_notes=tuple(notes),
        )

    def _find_duplicate(self, local_hits: tuple[dict, ...]) -> dict | None:
        seen: dict[str, dict] = {}
        for item in local_hits:
            current = str((item or {}).get("current_conclusion") or (item or {}).get("summary") or "").strip()
            if not current:
                continue
            key = current[:80].lower()
            if key in seen:
                return item
            seen[key] = item
        return None
