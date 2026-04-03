from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


JUDGE_DECISIONS: tuple[str, ...] = ("accept", "repair", "reject", "escalate", "expand")


@dataclass(slots=True)
class JudgeVerdict:
    decision: str = "accept"
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class OrchestratorJudgeAdapter:
    def evaluate_node(self, mission_id: str, node_id: str, artifacts: list[dict] | None = None) -> JudgeVerdict:
        return JudgeVerdict(
            decision="accept",
            reason="default_stub_accept",
            metadata={"artifact_count": len(artifacts or [])},
        )
