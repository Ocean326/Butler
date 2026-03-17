from __future__ import annotations

from pathlib import Path

from ..models import CompactMemoryInput, CompactMemoryResult, SummaryBlock, SummaryCandidate


class CompactMemoryAgent:
    def __init__(self) -> None:
        self.prompt = (Path(__file__).resolve().parents[1] / "prompts" / "compact_memory_agent.md").read_text(encoding="utf-8")

    def run(self, payload: CompactMemoryInput) -> CompactMemoryResult:
        if not payload.old_entries:
            return CompactMemoryResult(audit_notes=("no old entries to compact",))

        bullets: list[str] = []
        source_ids: list[str] = []
        candidates: list[SummaryCandidate] = []
        for entry in payload.old_entries[-8:]:
            topic = str(entry.get("topic") or "").strip()
            summary = str(entry.get("summary") or "").strip()
            if topic or summary:
                bullets.append(f"{topic}: {summary}".strip(": ")[:180])
            memory_id = str(entry.get("memory_id") or "").strip()
            if memory_id:
                source_ids.append(memory_id)

        summary_text = "\n".join(f"- {item}" for item in bullets[:6]).strip()
        block = SummaryBlock(
            title=f"recent compact {payload.pool}",
            summary=summary_text[:1200],
            bullets=tuple(bullets[:6]),
            source_memory_ids=tuple(source_ids[:12]),
        )

        lowered = " ".join(bullets)
        if any(token in lowered for token in ("项目", "任务", "进度", "heartbeat", "规划", "方案")):
            candidates.append(
                SummaryCandidate(
                    channel="project_state",
                    title="recent compact project state",
                    summary=summary_text[:220],
                    keywords=("recent", "project_state"),
                )
            )
        if any(token in lowered for token in ("文档", "链接", "路径", "参考", "资料", "OCR")):
            candidates.append(
                SummaryCandidate(
                    channel="reference",
                    title="recent compact reference",
                    summary=summary_text[:220],
                    keywords=("recent", "reference"),
                )
            )
        if not candidates:
            candidates.append(
                SummaryCandidate(
                    channel="archive",
                    title="recent compact archive",
                    summary=summary_text[:220],
                    keywords=("recent", "archive"),
                )
            )

        return CompactMemoryResult(
            summary_block=block,
            summary_candidates=tuple(candidates),
            audit_notes=("compact summary generated",),
        )
