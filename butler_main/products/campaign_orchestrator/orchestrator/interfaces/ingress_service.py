from __future__ import annotations

from ..templates import build_mission_payload_from_template
from ..workspace import build_orchestrator_service_for_workspace


class OrchestratorIngressService:
    """Thin ingress boundary for creating orchestrator-backed missions."""

    def create_mission(self, workspace: str, request: dict) -> dict:
        payload = dict(request or {})
        template_id = str(payload.get("template_id") or "").strip()
        if template_id:
            mission_payload = build_mission_payload_from_template(
                template_id,
                dict(payload.get("template_inputs") or {}),
            )
        else:
            mission_payload = dict(payload.get("mission") or payload)
        service = build_orchestrator_service_for_workspace(workspace)
        mission = service.create_mission(**mission_payload)
        return {
            "ok": True,
            "ingress_kind": "orchestrator_mission",
            "mission_id": mission.mission_id,
            "mission_type": mission.mission_type,
            "status": mission.status,
            "title": mission.title,
        }


__all__ = ["OrchestratorIngressService"]
