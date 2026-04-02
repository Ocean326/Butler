from __future__ import annotations

from .models import Mission, MissionNode, normalize_node_status


class OrchestratorScheduler:
    def ready_nodes(self, mission: Mission) -> list[MissionNode]:
        ready: list[MissionNode] = []
        for node in mission.nodes:
            status = normalize_node_status(node.status)
            if status not in {"pending", "repairing"}:
                continue
            if self._dependencies_satisfied(mission, node):
                ready.append(node)
        return ready

    def activate_ready_nodes(self, mission: Mission) -> list[str]:
        activated: list[str] = []
        for node in self.ready_nodes(mission):
            node.status = "ready"
            activated.append(node.node_id)
        return activated

    def _dependencies_satisfied(self, mission: Mission, node: MissionNode) -> bool:
        if not node.dependencies:
            return True
        for dependency_id in node.dependencies:
            dependency = mission.node_by_id(dependency_id)
            if dependency is None:
                return False
            if normalize_node_status(dependency.status) != "done":
                return False
        return True
