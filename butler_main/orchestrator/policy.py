from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OrchestratorPolicy:
    max_parallel_branches_per_node: int = 4
    max_total_branches_per_mission: int = 20
    max_auto_expand_nodes_per_mission: int = 2
    max_repair_attempts_per_node: int = 2
