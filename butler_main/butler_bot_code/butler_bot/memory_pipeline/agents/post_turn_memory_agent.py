from __future__ import annotations

from pathlib import Path

from ..models import MemoryWriteRequest, PostTurnMemoryInput, PostTurnMemoryResult, ProfileWriteRequest


class PostTurnMemoryAgent:
    def __init__(self) -> None:
        self.prompt = (Path(__file__).resolve().parents[1] / "prompts" / "post_turn_memory_agent.md").read_text(encoding="utf-8")

    def run(self, payload: PostTurnMemoryInput) -> PostTurnMemoryResult:
        candidate = payload.candidate_memory if isinstance(payload.candidate_memory, dict) else {}
        topic = str(candidate.get("topic") or "本轮对话").strip()[:40] or "本轮对话"
        summary = str(candidate.get("summary") or "").strip()
        long_term = candidate.get("long_term_candidate") if isinstance(candidate.get("long_term_candidate"), dict) else {}
        relation_signal = candidate.get("relation_signal") if isinstance(candidate.get("relation_signal"), dict) else {}
        local_writes: list[MemoryWriteRequest] = []
        profile_writes: list[ProfileWriteRequest] = []
        notes: list[str] = []

        if bool(long_term.get("should_write")) and str(long_term.get("summary") or "").strip():
            deduped = self._is_duplicate_local_candidate(payload.local_memory_hits, str(long_term.get("summary") or ""))
            if deduped:
                notes.append("long_term_candidate deduped against local memory")
            else:
                local_writes.append(
                    MemoryWriteRequest(
                        channel="local_memory",
                        title=str(long_term.get("title") or topic)[:40],
                        summary=str(long_term.get("summary") or "")[:220],
                        keywords=tuple(str(x).strip()[:20] for x in (long_term.get("keywords") or []) if str(x).strip()),
                        source_type="post-turn-agent",
                        source_memory_id=payload.memory_id,
                        source_reason="long_term_candidate_governed",
                        source_topic=topic,
                        metadata={"source_entry": candidate},
                    )
                )

        preference_shift = str(relation_signal.get("preference_shift") or "").strip()
        if preference_shift:
            profile_writes.append(
                ProfileWriteRequest(
                    action="remember",
                    category="preferences",
                    content=preference_shift[:160],
                    reason="post_turn_relation_signal",
                )
            )
            notes.append("relation_signal.preference_shift promoted to user_profile")

        return PostTurnMemoryResult(
            local_writes=tuple(local_writes),
            profile_writes=tuple(profile_writes),
            mark_promoted=bool(local_writes),
            should_merge_tasks=not payload.suppress_task_merge,
            audit_notes=tuple(notes),
        )

    def _is_duplicate_local_candidate(self, local_hits: tuple[dict, ...], summary: str) -> bool:
        summary_text = str(summary or "").strip()
        if not summary_text:
            return True
        for item in local_hits or ():
            current = str((item or {}).get("current_conclusion") or (item or {}).get("summary") or "").strip()
            if current and (summary_text in current or current in summary_text):
                return True
        return False
