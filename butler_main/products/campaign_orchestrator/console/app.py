from __future__ import annotations

from typing import Any

from .service import ConsoleControlService, ConsoleQueryService
from .types import ControlActionRequest


def create_console_app() -> Any:
    """Create the optional FastAPI app when the dependency is available."""

    try:
        from fastapi import FastAPI, HTTPException
    except Exception as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("FastAPI is required to run the Butler console app") from exc

    query_service = ConsoleQueryService()
    control = ConsoleControlService()
    app = FastAPI(title="Butler Console", version="0.1.0")

    @app.get("/console/api/runtime")
    def get_runtime(workspace: str = ".", stale_seconds: int = 120) -> dict[str, Any]:
        return query_service.get_runtime_status(workspace, stale_seconds=stale_seconds)

    @app.get("/console/api/access")
    def get_access(workspace: str = ".") -> dict[str, Any]:
        return query_service.get_access_diagnostics(workspace).to_dict()

    @app.get("/console/api/global/board")
    def get_global_board(workspace: str = ".", limit: int = 12) -> dict[str, Any]:
        return query_service.build_global_scheduler_board(workspace, limit=limit).to_dict()

    @app.get("/console/api/campaigns")
    def list_campaigns(workspace: str = ".", status: str = "", limit: int = 20) -> list[dict[str, Any]]:
        return query_service.list_campaigns(workspace, status=status, limit=limit)

    @app.get("/console/api/campaigns/{campaign_id}")
    def get_campaign_detail(campaign_id: str, workspace: str = ".") -> dict[str, Any]:
        return query_service.get_campaign_detail(workspace, campaign_id)

    @app.get("/console/api/campaigns/{campaign_id}/graph")
    def get_campaign_graph(campaign_id: str, workspace: str = ".") -> dict[str, Any]:
        return query_service.build_campaign_graph_snapshot(workspace, campaign_id).to_dict()

    @app.get("/console/api/campaigns/{campaign_id}/board")
    def get_campaign_board(campaign_id: str, workspace: str = ".") -> dict[str, Any]:
        return query_service.build_project_board(workspace, campaign_id).to_dict()

    @app.get("/console/api/campaigns/{campaign_id}/artifacts/{artifact_id}/preview")
    def get_campaign_artifact_preview(campaign_id: str, artifact_id: str, workspace: str = ".") -> dict[str, Any]:
        return query_service.build_artifact_preview(workspace, campaign_id, artifact_id).to_dict()

    @app.get("/console/api/campaigns/{campaign_id}/events")
    def get_campaign_events(campaign_id: str, workspace: str = ".", limit: int = 20) -> list[dict[str, Any]]:
        return [item.to_dict() for item in query_service.list_campaign_events(workspace, campaign_id, limit=limit)]

    @app.post("/console/api/campaigns/{campaign_id}/actions")
    def post_campaign_action(campaign_id: str, body: dict[str, Any], workspace: str = ".") -> dict[str, Any]:
        request = ControlActionRequest(
            action=str(body.get("action") or "").strip(),
            target_kind=str(body.get("target_kind") or "campaign").strip() or "campaign",
            target_id=campaign_id,
            reason=str(body.get("reason") or "").strip(),
            payload=dict(body.get("payload") or {}),
            operator_id=str(body.get("operator_id") or "").strip(),
            source_surface=str(body.get("source_surface") or "console").strip() or "console",
        )
        result = control.apply(workspace, request)
        if not result.ok:
            status_code = 409 if "stale" in str(result.result_summary).lower() else 400
            raise HTTPException(status_code=status_code, detail=result.to_dict())
        return result.to_dict()

    @app.get("/console/api/drafts")
    def list_drafts(workspace: str = ".", limit: int = 20) -> list[dict[str, Any]]:
        return [item.to_dict() for item in query_service.list_drafts(workspace, limit=limit)]

    @app.get("/console/api/skills/collections")
    def get_skill_collections(workspace: str = ".") -> list[dict[str, Any]]:
        return query_service.list_skill_collections(workspace)

    @app.get("/console/api/skills/collections/{collection_id}")
    def get_skill_collection(collection_id: str, workspace: str = ".") -> dict[str, Any]:
        payload = query_service.get_skill_collection_detail(workspace, collection_id)
        if payload is None:
            raise HTTPException(status_code=404, detail={"collection_id": collection_id, "error": "not_found"})
        return payload

    @app.get("/console/api/skills/families/{family_id}")
    def get_skill_family(family_id: str, workspace: str = ".", collection_id: str = "") -> dict[str, Any]:
        payload = query_service.get_skill_family_detail(workspace, family_id=family_id, collection_id=collection_id)
        if payload is None:
            raise HTTPException(status_code=404, detail={"family_id": family_id, "error": "not_found"})
        return payload

    @app.get("/console/api/skills/search")
    def search_skills(workspace: str = ".", query: str = "", collection_id: str = "") -> dict[str, Any]:
        return query_service.search_skills(workspace, query=query, collection_id=collection_id)

    @app.get("/console/api/skills/diagnostics")
    def get_skill_diagnostics(workspace: str = ".") -> dict[str, Any]:
        return query_service.get_skill_diagnostics(workspace)

    @app.get("/console/api/drafts/{draft_id}")
    def get_draft(draft_id: str, workspace: str = ".") -> dict[str, Any]:
        item = query_service.get_draft(workspace, draft_id)
        if item is None:
            raise HTTPException(status_code=404, detail={"draft_id": draft_id, "error": "not_found"})
        return item.to_dict()

    @app.patch("/console/api/drafts/{draft_id}")
    def patch_draft(draft_id: str, body: dict[str, Any], workspace: str = ".") -> dict[str, Any]:
        try:
            return query_service.patch_draft(workspace, draft_id, body).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"draft_id": draft_id, "error": "not_found"}) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail={"draft_id": draft_id, "error": str(exc)}) from exc

    @app.post("/console/api/drafts/{draft_id}/launch")
    def launch_draft(draft_id: str, workspace: str = ".") -> dict[str, Any]:
        try:
            return query_service.launch_draft(workspace, draft_id).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"draft_id": draft_id, "error": "not_found"}) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail={"draft_id": draft_id, "error": str(exc)}) from exc

    @app.get("/console/api/channels/{session_id}")
    def get_channel_summary(session_id: str, workspace: str = ".") -> dict[str, Any]:
        return query_service.get_channel_thread_summary(workspace, session_id).to_dict()

    return app
