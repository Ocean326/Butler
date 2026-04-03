from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
import json
from pathlib import Path
import socket
from typing import Any, Iterable, Mapping
from uuid import uuid4

from butler_main.agents_os.skills import (
    build_skill_exposure_observation,
    build_skill_registry_diagnostics,
    expand_skill_family,
    get_skill_collection_detail,
    list_skill_collections,
    normalize_skill_exposure_payload,
    render_skill_exposure_prompt,
    search_skill_catalog,
)
from butler_main.chat.negotiation import CampaignNegotiationDraft, CampaignNegotiationStore
from butler_main.domains.campaign.template_registry import CampaignTemplateRegistry
from butler_main.orchestrator.interfaces.campaign_service import OrchestratorCampaignService
from butler_main.orchestrator.interfaces.query_service import OrchestratorQueryService
from butler_main.orchestrator.workspace import resolve_orchestrator_root

from .types import (
    AccessDiagnostics,
    AgentDetailEnvelope,
    AgentExecutionView,
    ArtifactListItem,
    BoardEdgeView,
    BoardNodeView,
    BoardSnapshot,
    ChannelThreadSummary,
    ConsoleEventEnvelope,
    ControlActionRequest,
    ControlActionResult,
    FrontdoorDraftView,
    GraphEdgeView,
    GraphNodeActionState,
    GraphNodeView,
    GraphSnapshot,
    PreviewEnvelope,
    RecordListItem,
    TimelineItem,
)


TEXT_PREVIEW_SUFFIXES = {
    ".json",
    ".md",
    ".txt",
    ".log",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".css",
    ".html",
    ".yaml",
    ".yml",
}
DEFAULT_CANVAS_NODE_WIDTH = 256.0
DEFAULT_CANVAS_NODE_HEIGHT = 156.0
TIMELINE_CARD_WIDTH = 142.0
TIMELINE_CARD_GAP = 18.0
TIMELINE_STAGE_PADDING = 48.0
TIMELINE_MIN_STAGE_WIDTH = 860.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list_of_text(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return [item for item in (_text(value) for value in values) if item]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_of_mapping(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _title_from_step_id(step_id: str) -> str:
    text = _text(step_id).replace("_", " ").replace("-", " ")
    return " ".join(part.capitalize() for part in text.split()) or "Step"


def _phase_index_map(phase_path: Iterable[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, item in enumerate(phase_path):
        if item not in mapping:
            mapping[item] = index
    return mapping


def _safe_slug(value: str, fallback: str) -> str:
    normalized = "".join(ch for ch in _text(value) if ch.isalnum() or ch in {"_", "-"})
    return normalized or fallback


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


CN_TZ = timezone(timedelta(hours=8))


def _parse_datetime(value: Any) -> datetime | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        candidate = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(candidate)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                parsed = datetime.strptime(raw, fmt).replace(tzinfo=UTC)
                break
            except Exception:
                parsed = None
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _display_time_cn(value: Any) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return _text(value)
    return parsed.astimezone(CN_TZ).strftime("%m-%d %H:%M")


def _clip_text(value: Any, limit: int = 72) -> str:
    text = " ".join(_text(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _merge_nested(base: Mapping[str, Any] | None, patch: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(patch or {}).items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge_nested(merged.get(key), value)
        else:
            merged[key] = value
    return merged


class ConsoleQueryService:
    """Build console-facing views from existing orchestrator/query and frontdoor draft objects."""

    def __init__(
        self,
        *,
        query_service: OrchestratorQueryService | None = None,
        campaign_service: OrchestratorCampaignService | None = None,
        negotiation_store: CampaignNegotiationStore | None = None,
        console_host: str = "127.0.0.1",
        console_port: int = 8765,
        console_base_path: str = "/console/",
    ) -> None:
        self._campaign_service = campaign_service or OrchestratorCampaignService()
        self._query_service = query_service or OrchestratorQueryService(campaign_service=self._campaign_service)
        self._store = negotiation_store or CampaignNegotiationStore()
        self._template_registry = CampaignTemplateRegistry()
        self._console_host = _text(console_host) or "127.0.0.1"
        self._console_port = max(1, int(console_port or 8765))
        base_path = f"/{_text(console_base_path).strip('/')}/" if _text(console_base_path) else "/console/"
        self._console_base_path = base_path

    def get_runtime_status(self, workspace: str, *, stale_seconds: int = 120) -> dict[str, Any]:
        return self._query_service.get_runtime_status(workspace, stale_seconds=stale_seconds)

    def list_campaigns(self, workspace: str, *, status: str = "", limit: int = 20) -> list[dict[str, Any]]:
        return self._query_service.list_campaigns(workspace, status=status, limit=limit)

    def get_campaign_detail(self, workspace: str, campaign_id: str) -> dict[str, Any]:
        return self._query_service.get_campaign_status(workspace, campaign_id)

    def list_skill_collections(self, workspace: str) -> list[dict[str, Any]]:
        return [dict(item) for item in list_skill_collections(workspace)]

    def get_skill_collection_detail(self, workspace: str, collection_id: str) -> dict[str, Any] | None:
        payload = get_skill_collection_detail(workspace, collection_id=collection_id)
        return dict(payload) if isinstance(payload, Mapping) else None

    def get_skill_family_detail(
        self,
        workspace: str,
        *,
        family_id: str,
        collection_id: str = "",
    ) -> dict[str, Any] | None:
        family = expand_skill_family(
            workspace,
            family_id=_text(family_id),
            collection_id=_text(collection_id) or None,
        )
        if family is None:
            return None
        return {
            "family_id": family.family_id,
            "label": family.label,
            "summary": family.summary,
            "category": family.category,
            "risk_level": family.risk_level,
            "trigger_examples": list(family.trigger_examples),
            "collection_id": _text(collection_id),
            "items": [
                {
                    "name": item.name,
                    "description": item.description,
                    "path": item.relative_dir,
                    "skill_file": item.relative_skill_file,
                    "risk_level": item.risk_level,
                    "automation_safe": item.automation_safe,
                    "requires_skill_read": item.requires_skill_read,
                }
                for item in family.members
            ],
        }

    def search_skills(self, workspace: str, *, query: str, collection_id: str = "") -> dict[str, Any]:
        families, skills = search_skill_catalog(
            workspace,
            query=_text(query),
            collection_id=_text(collection_id) or None,
        )
        return {
            "query": _text(query),
            "collection_id": _text(collection_id),
            "families": [
                {
                    "family_id": family.family_id,
                    "label": family.label,
                    "summary": family.summary,
                    "category": family.category,
                    "risk_level": family.risk_level,
                    "member_count": len(family.members),
                }
                for family in families
            ],
            "skills": [
                {
                    "name": item.name,
                    "description": item.description,
                    "family_id": item.family_id,
                    "family_label": item.family_label,
                    "category": item.category,
                    "path": item.relative_dir,
                    "risk_level": item.risk_level,
                    "requires_skill_read": item.requires_skill_read,
                }
                for item in skills
            ],
        }

    def get_skill_diagnostics(self, workspace: str) -> dict[str, Any]:
        return dict(build_skill_registry_diagnostics(workspace))

    def build_campaign_graph_snapshot(self, workspace: str, campaign_id: str) -> GraphSnapshot:
        payload = self.get_campaign_detail(workspace, campaign_id)
        return self._graph_snapshot_from_payload(payload)

    def build_global_scheduler_board(self, workspace: str, *, limit: int = 12) -> BoardSnapshot:
        runtime = self.get_runtime_status(workspace, stale_seconds=120)
        campaigns = self.list_campaigns(workspace, limit=max(1, int(limit or 12)))
        projections = [self._project_campaign_runtime(self.get_campaign_detail(workspace, item.get("campaign_id", ""))) for item in campaigns]

        running_agents = [item["current_agent"] for item in projections if item.get("current_agent") is not None]
        next_agents = [item["next_agent"] for item in projections if item.get("next_agent") is not None]
        queued_agents: list[AgentExecutionView] = []
        for item in projections:
            queued_agents.extend(item.get("queued_agents") or [])

        nodes: list[BoardNodeView] = []
        edges: list[BoardEdgeView] = []
        lane_x = {"running": 80.0, "next": 380.0, "queued": 680.0, "completed": 980.0}
        lane_y = {"running": 96.0, "next": 96.0, "queued": 96.0, "completed": 96.0}
        ordered_nodes: list[str] = []
        for projection in projections:
            campaign_view = projection["campaign_view"]
            node_status = projection["board_status"]
            lane = projection["board_lane"]
            node_id = f"campaign:{campaign_view.get('campaign_id')}"
            campaign_title = self._campaign_display_title(_text(campaign_view.get("title") or campaign_view.get("campaign_id")))
            campaign_brief = self._global_node_brief(projection)
            nodes.append(
                BoardNodeView(
                    id=node_id,
                    title=campaign_title,
                    display_title=campaign_title,
                    display_brief=campaign_brief,
                    subtitle=self._global_node_subtitle(projection),
                    role_label=self._role_label(_text((projection.get("current_agent") or projection.get("next_agent") or AgentExecutionView(id="", title="")).role_id)),
                    iteration_label=self._iteration_label(projection.get("campaign_view")),
                    updated_at_label=_display_time_cn(campaign_view.get("updated_at")),
                    visual_state=node_status,
                    status=node_status,
                    lane=lane,
                    phase=_text(campaign_view.get("current_phase") or campaign_view.get("next_phase")),
                    step_id=_text(projection.get("active_step") or projection.get("next_step")),
                    role_id=_text((projection.get("current_agent") or projection.get("next_agent") or AgentExecutionView(id="", title="")).role_id),
                    agent_spec_id=_text((projection.get("current_agent") or projection.get("next_agent") or AgentExecutionView(id="", title="")).agent_spec_id),
                    source=_text((projection.get("current_agent") or projection.get("next_agent") or AgentExecutionView(id="", title="")).source or "inferred"),
                    badges=[
                        f"campaign:{_text(campaign_view.get('campaign_id'))}",
                        f"phase:{_text(campaign_view.get('current_phase') or '-')}",
                        f"source:{_text((projection.get('current_agent') or projection.get('next_agent') or AgentExecutionView(id='', title='')).source or 'inferred')}",
                    ],
                    detail_available=bool(_text(campaign_view.get("campaign_id")) and _text(projection.get("active_step") or projection.get("next_step"))),
                    detail_campaign_id=_text(campaign_view.get("campaign_id")),
                    detail_node_id=_text(projection.get("active_step") or projection.get("next_step")),
                    position={"x": lane_x.get(lane, 680.0), "y": lane_y.get(lane, 96.0)},
                    size={"w": DEFAULT_CANVAS_NODE_WIDTH, "h": DEFAULT_CANVAS_NODE_HEIGHT},
                    metadata={
                        "campaign_id": _text(campaign_view.get("campaign_id")),
                        "campaign_status": _text(campaign_view.get("status")),
                        "display_brief": campaign_brief,
                        "current_agent": projection["current_agent"].to_dict() if projection.get("current_agent") else None,
                        "next_agent": projection["next_agent"].to_dict() if projection.get("next_agent") else None,
                    },
                )
            )
            lane_y[lane] = lane_y.get(lane, 96.0) + 170.0
            ordered_nodes.append(node_id)

        for index in range(len(ordered_nodes) - 1):
            edges.append(
                BoardEdgeView(
                    id=f"{ordered_nodes[index]}__queue__{ordered_nodes[index + 1]}",
                    source=ordered_nodes[index],
                    target=ordered_nodes[index + 1],
                    kind="queue",
                    active=index == 0,
                    label="scheduler",
                    visual_kind="scheduler",
                    emphasis="active" if index == 0 else "normal",
                )
            )

        idle_reason = ""
        if not running_agents and not next_agents and not queued_agents:
            idle_reason = (
                "orchestrator online, but there are no active campaigns or ready agents. "
                "The backend is idle, not offline."
            )
        summary = (
            f"running {len(running_agents)} · next {len(next_agents)} · queued {len(queued_agents)}"
            if not idle_reason
            else "running 0 · next 0 · queued 0"
        )
        timeline_items = self._layout_timeline_items(self._global_timeline_items(runtime=runtime, projections=projections))
        return BoardSnapshot(
            scope="global",
            scope_id="global_scheduler",
            snapshot_id=f"global_{uuid4().hex[:12]}",
            title="Global Scheduler",
            status=_text(runtime.get("process_state") or runtime.get("run_state")),
            summary=summary,
            idle_reason=idle_reason,
            current_agent=running_agents[0] if running_agents else None,
            next_agent=next_agents[0] if next_agents else None,
            running_agents=running_agents,
            next_agents=next_agents,
            queued_agents=queued_agents,
            nodes=nodes,
            edges=edges,
            timeline_items=timeline_items,
            timeline_bounds=self._timeline_bounds(timeline_items),
            records=[
                RecordListItem(
                    record_id="runtime_note",
                    title="Runtime note",
                    kind="runtime",
                    created_at=_text(runtime.get("updated_at")),
                    summary=_text(runtime.get("note")),
                    preview_kind="text",
                    preview_title="Runtime note",
                    preview_language="text",
                    preview_content=_text(runtime.get("note")),
                    metadata={"runtime": runtime},
                )
            ],
            preview_defaults={"selected_node_id": nodes[0].id if nodes else "", "mode": "graph"},
            metadata={
                "runtime": runtime,
                "campaign_count": len(campaigns),
                "access": self.get_access_diagnostics(workspace).to_dict(),
            },
        )

    def build_project_board(self, workspace: str, campaign_id: str) -> BoardSnapshot:
        payload = self.get_campaign_detail(workspace, campaign_id)
        projection = self._project_campaign_runtime(payload)
        current_agent = projection["current_agent"]
        next_agent = projection["next_agent"]
        artifacts = projection["artifacts"]
        records = projection["records"]
        timeline_items = self._layout_timeline_items(projection["timeline_items"])
        return BoardSnapshot(
            scope="campaign",
            scope_id=_text(campaign_id),
            snapshot_id=f"campaign_{_safe_slug(campaign_id, 'campaign')}_{uuid4().hex[:8]}",
            title=self._campaign_display_title(_text(projection["campaign_view"].get("title") or campaign_id)),
            status=_text(projection["campaign_view"].get("status")),
            summary=projection["summary"],
            idle_reason=projection["idle_reason"],
            current_agent=current_agent,
            next_agent=next_agent,
            running_agents=[current_agent] if current_agent else [],
            next_agents=[next_agent] if next_agent else [],
            queued_agents=projection["queued_agents"],
            nodes=projection["nodes"],
            edges=projection["edges"],
            artifacts=artifacts,
            records=records,
            timeline_items=timeline_items,
            timeline_bounds=self._timeline_bounds(timeline_items),
            preview_defaults=projection["preview_defaults"],
            metadata={
                "campaign": payload,
                "runtime_projection": {
                    "active_step": projection["active_step"],
                    "next_step": projection["next_step"],
                    "role_bindings": projection["role_bindings"],
                },
            },
        )

    def build_agent_detail(self, workspace: str, campaign_id: str, node_id: str) -> AgentDetailEnvelope:
        payload = self.get_campaign_detail(workspace, campaign_id)
        projection = self._project_campaign_runtime(payload)
        target_node_id = _text(node_id)
        node = next((item for item in projection["nodes"] if item.id == target_node_id), None)
        if node is None:
            raise KeyError(f"agent node not found: {target_node_id}")

        campaign_view = _mapping(payload.get("campaign_view"))
        task_summary = _mapping(payload.get("task_summary"))
        working_contract = _mapping(payload.get("working_contract"))
        latest_verdict = _mapping(payload.get("latest_verdict") or _mapping(payload.get("evaluation_summary")).get("latest_verdict"))
        planning_summary = _mapping(payload.get("planning_summary"))
        phase_runtime = _mapping(payload.get("phase_runtime"))
        session_view = _mapping(payload.get("session_view"))
        workflow_session = _mapping(payload.get("workflow_session"))
        session_evidence = _mapping(payload.get("session_evidence"))

        related_artifacts = [
            item.to_dict()
            for item in projection["artifacts"]
            if _text(item.phase or item.metadata.get("phase") or item.metadata.get("step_id")) == target_node_id
        ]

        live_records = self._detail_live_records(payload, node_id=target_node_id)
        raw_records = self._detail_raw_records(payload, node_id=target_node_id)
        planned_input = {
            "goal": _text(
                latest_verdict.get("next_iteration_goal")
                or task_summary.get("next_action")
                or working_contract.get("working_goal")
                or _mapping(task_summary.get("spec")).get("goal")
            ),
            "acceptance": _list_of_text(working_contract.get("working_acceptance")),
            "materials": _list_of_text(_mapping(task_summary.get("spec")).get("materials") or payload.get("materials")),
            "hard_constraints": _list_of_text(_mapping(task_summary.get("spec")).get("hard_constraints") or payload.get("hard_constraints")),
            "pending_checks": _list_of_text(phase_runtime.get("pending_checks") or payload.get("pending_checks")),
            "operational_checks_pending": _list_of_text(
                phase_runtime.get("operational_checks_pending") or payload.get("operational_checks_pending")
            ),
            "closure_checks_pending": _list_of_text(payload.get("closure_checks_pending")),
            "resolved_checks": _list_of_text(phase_runtime.get("resolved_checks") or payload.get("resolved_checks")),
            "waived_checks": _list_of_text(phase_runtime.get("waived_checks") or payload.get("waived_checks")),
            "plan_ref": _text(planning_summary.get("plan_ref")),
            "spec_ref": _text(planning_summary.get("spec_ref")),
            "progress_ref": _text(planning_summary.get("progress_ref")),
            "bundle_root": _text(phase_runtime.get("bundle_root") or payload.get("bundle_root")),
            "prompt_surface": self._prompt_surface_from_payload(workspace, payload, node_id=target_node_id),
            "workflow_authoring": self._campaign_workflow_authoring_payload(payload),
        }
        return AgentDetailEnvelope(
            campaign_id=_text(campaign_id),
            node_id=target_node_id,
            title=node.display_title or node.title or target_node_id,
            status=node.status,
            execution_state=self._detail_execution_state(node.status),
            role_id=node.role_id,
            role_label=node.role_label,
            agent_spec_id=node.agent_spec_id,
            subtitle=node.subtitle,
            updated_at=_text(campaign_view.get("updated_at") or workflow_session.get("updated_at")),
            overview={
                "campaign_title": self._campaign_display_title(_text(campaign_view.get("title") or campaign_id)),
                "campaign_status": _text(campaign_view.get("status")),
                "phase": target_node_id,
                "current_phase": _text(campaign_view.get("current_phase")),
                "next_phase": _text(campaign_view.get("next_phase")),
                "node_status": _text(node.status),
                "display_brief": _text(node.display_brief),
                "iteration_label": _text(node.iteration_label),
                "updated_at_label": _text(node.updated_at_label),
                "session_status": _text(session_view.get("status") or workflow_session.get("status")),
                "workflow_session_id": _text(session_view.get("workflow_session_id") or workflow_session.get("session_id")),
                "active_step": _text(session_view.get("active_step") or workflow_session.get("active_step")),
                "runtime_mode": _text(payload.get("runtime_mode") or phase_runtime.get("runtime_mode")),
                "bundle_root": _text(payload.get("bundle_root") or phase_runtime.get("bundle_root")),
                "execution_state": _text(payload.get("execution_state")),
                "closure_state": _text(payload.get("closure_state")),
                "progress_reason": _text(payload.get("progress_reason")),
                "closure_reason": _text(payload.get("closure_reason")),
                "latest_acceptance_decision": _text(payload.get("latest_acceptance_decision")),
                "not_done_reason": _text(payload.get("not_done_reason")),
                "session_event_count": _coerce_int(session_evidence.get("session_event_count")),
                "artifact_count": _coerce_int(session_evidence.get("artifact_count") or campaign_view.get("artifact_count")),
            },
            planned_input=planned_input,
            live_records=live_records,
            artifacts=related_artifacts,
            raw_records=raw_records,
            metadata={
                "campaign_view": campaign_view,
                "task_summary": task_summary,
                "working_contract": working_contract,
                "session_evidence": session_evidence,
            },
        )

    def build_artifact_preview(self, workspace: str, campaign_id: str, artifact_id: str) -> PreviewEnvelope:
        item = self._find_artifact(workspace, campaign_id, artifact_id)
        file_path = self._campaign_root(workspace, campaign_id) / _text(item.get("ref"))
        title = _text(item.get("label") or item.get("artifact_id") or artifact_id)
        if not file_path.exists():
            return PreviewEnvelope(
                scope="campaign",
                scope_id=_text(campaign_id),
                item_id=_text(item.get("artifact_id") or artifact_id),
                title=title,
                kind=_text(item.get("kind") or "artifact"),
                preview_kind="missing",
                language="text",
                content="artifact file is missing on disk",
                content_path=str(file_path),
                metadata={"artifact": item},
            )

        suffix = file_path.suffix.lower()
        if suffix not in TEXT_PREVIEW_SUFFIXES:
            stat = file_path.stat()
            return PreviewEnvelope(
                scope="campaign",
                scope_id=_text(campaign_id),
                item_id=_text(item.get("artifact_id") or artifact_id),
                title=title,
                kind=_text(item.get("kind") or "artifact"),
                preview_kind="unsupported",
                language="text",
                content="binary or unsupported artifact; open it from the workspace when needed",
                content_path=str(file_path),
                metadata={"artifact": item, "size_bytes": stat.st_size},
            )

        raw_text = file_path.read_text(encoding="utf-8", errors="replace")
        language = "json" if suffix == ".json" else suffix.lstrip(".") or "text"
        content = raw_text
        if suffix == ".json":
            try:
                parsed = json.loads(raw_text)
            except Exception:
                parsed = None
            if isinstance(parsed, Mapping):
                content = self._best_effort_preview_text(parsed)
            elif isinstance(parsed, list):
                content = json.dumps(parsed, ensure_ascii=False, indent=2)
        return PreviewEnvelope(
            scope="campaign",
            scope_id=_text(campaign_id),
            item_id=_text(item.get("artifact_id") or artifact_id),
            title=title,
            kind=_text(item.get("kind") or "artifact"),
            preview_kind="text",
            language=language,
            content=content,
            content_path=str(file_path),
            metadata={"artifact": item},
        )

    def get_access_diagnostics(self, workspace: str) -> AccessDiagnostics:
        runtime = self.get_runtime_status(workspace, stale_seconds=120)
        local_urls = [f"http://127.0.0.1:{self._console_port}{self._console_base_path}"]
        if self._console_host not in {"127.0.0.1", "localhost"}:
            local_urls.append(f"http://{self._console_host}:{self._console_port}{self._console_base_path}")
        lan_urls = [
            f"http://{address}:{self._console_port}{self._console_base_path}"
            for address in self._lan_ipv4_addresses()
            if address not in {"127.0.0.1", self._console_host}
        ]
        note = "console host binding only allows local access"
        hints = [
            "If another device cannot open the LAN URL, check campus firewall policy, AP isolation, or cross-subnet restrictions.",
            "If you are using a reverse proxy later, keep the standalone console port available for direct diagnostics.",
        ]
        if self._console_host in {"0.0.0.0", "::"}:
            note = "console is listening on all interfaces; cross-device failures are likely caused by network policy outside Butler"
        return AccessDiagnostics(
            listen_host=self._console_host,
            port=self._console_port,
            base_path=self._console_base_path,
            local_urls=local_urls,
            lan_urls=lan_urls,
            note=note,
            hints=hints,
            metadata={
                "runtime_process_state": _text(runtime.get("process_state")),
                "runtime_phase": _text(runtime.get("phase")),
                "runtime_note": _text(runtime.get("note")),
                "workspace": _text(workspace),
            },
        )

    def list_campaign_events(
        self,
        workspace: str,
        campaign_id: str,
        *,
        limit: int = 20,
    ) -> list[ConsoleEventEnvelope]:
        items = self._query_service.list_campaign_events(workspace, campaign_id, limit=limit)
        envelopes = [self._event_envelope_from_payload(campaign_id, item) for item in items if isinstance(item, Mapping)]
        envelopes.sort(key=lambda item: (item.created_at, item.event_id))
        return envelopes

    def list_drafts(self, workspace: str, *, limit: int = 20) -> list[FrontdoorDraftView]:
        items = [self._draft_view_from_draft(item) for item in self._iter_drafts(workspace)]
        return items[: max(1, int(limit or 20))]

    def get_draft(self, workspace: str, draft_id: str) -> FrontdoorDraftView | None:
        target = _text(draft_id)
        if not target:
            return None
        for draft in self._iter_drafts(workspace):
            if draft.draft_id == target:
                return self._draft_view_from_draft(draft)
        return None

    def get_channel_thread_summary(self, workspace: str, session_id: str) -> ChannelThreadSummary:
        draft = self._store.load(workspace=workspace, session_id=session_id)
        latest_system_message = ""
        linked_campaign_id = ""
        if draft is not None:
            linked_campaign_id = _text(draft.started_campaign_id)
        if linked_campaign_id:
            try:
                payload = self.get_campaign_detail(workspace, linked_campaign_id)
                task_summary = _mapping(payload.get("task_summary"))
                latest_system_message = _text(task_summary.get("next_action"))
            except Exception:
                latest_system_message = ""
        return ChannelThreadSummary(
            channel="external_chat",
            session_id=_text(session_id),
            thread_id=_text(session_id),
            latest_user_message="",
            latest_system_message=latest_system_message,
            jump_link="",
            metadata={"linked_campaign_id": linked_campaign_id},
        )

    def get_campaign_control_plane(self, workspace: str, campaign_id: str) -> dict[str, Any]:
        payload = self.get_campaign_detail(workspace, campaign_id)
        task_summary = _mapping(payload.get("task_summary"))
        governance_summary = _mapping(payload.get("governance_summary"))
        progress = _mapping(task_summary.get("progress"))
        closure = _mapping(task_summary.get("closure"))
        risk = _mapping(task_summary.get("risk"))
        output = _mapping(task_summary.get("output"))
        latest_turn_receipt = _mapping(payload.get("latest_turn_receipt"))
        session_evidence = _mapping(payload.get("session_evidence"))
        canonical_session_id = _text(
            payload.get("canonical_session_id")
            or _mapping(payload.get("metadata")).get("canonical_session_id")
            or _mapping(_mapping(payload.get("metadata")).get("control_plane_refs")).get("canonical_session_id")
        )
        return {
            "campaign_id": _text(campaign_id),
            "mission_id": _text(payload.get("mission_id") or _mapping(payload.get("campaign_view")).get("mission_id")),
            "canonical_session_id": canonical_session_id,
            "macro_state": _text(payload.get("status") or progress.get("status")),
            "execution_state": _text(payload.get("execution_state")),
            "closure_state": _text(payload.get("closure_state")),
            "narrative_summary": _text(progress.get("latest_summary") or latest_turn_receipt.get("summary") or payload.get("progress_reason")),
            "progress_reason": _text(progress.get("latest_summary") or latest_turn_receipt.get("summary") or payload.get("progress_reason")),
            "closure_reason": _text(closure.get("final_summary") or payload.get("closure_reason")),
            "operator_next_action": _text(task_summary.get("next_action") or payload.get("operator_next_action")),
            "latest_stage_summary": _text(progress.get("latest_summary") or payload.get("latest_stage_summary")),
            "latest_acceptance_decision": _text(_mapping(closure.get("latest_verdict")).get("decision") or payload.get("latest_acceptance_decision")),
            "acceptance_requirements_remaining": _list_of_text(payload.get("acceptance_requirements_remaining")),
            "operational_checks_pending": _list_of_text(payload.get("operational_checks_pending")),
            "closure_checks_pending": _list_of_text(payload.get("closure_checks_pending")),
            "resolved_checks": _list_of_text(payload.get("resolved_checks")),
            "waived_checks": _list_of_text(payload.get("waived_checks")),
            "approval_state": _text(risk.get("approval_state") or governance_summary.get("approval_state")),
            "risk_level": _text(risk.get("risk_level") or governance_summary.get("risk_level")),
            "autonomy_profile": _text(risk.get("autonomy_profile") or governance_summary.get("autonomy_profile")),
            "latest_turn_receipt": latest_turn_receipt,
            "latest_delivery_refs": _list_of_text(output.get("latest_delivery_refs") or payload.get("latest_delivery_refs")),
            "harness_summary": {
                "turn_count": _coerce_int(progress.get("turn_count")),
                "artifact_count": _coerce_int(output.get("artifact_count") or session_evidence.get("artifact_count")),
                "session_event_count": _coerce_int(session_evidence.get("session_event_count")),
                "blackboard_entry_count": _coerce_int(session_evidence.get("blackboard_entry_count")),
                "turn_id": _text(latest_turn_receipt.get("turn_id")),
                "yield_reason": _text(latest_turn_receipt.get("yield_reason")),
                "continue_token": _text(latest_turn_receipt.get("continue_token")),
            },
            "available_actions": self._available_operator_actions(payload),
            "transition_options": self._transition_options_from_payload(payload),
            "recovery_candidates": self._recovery_candidates_from_payload(payload),
            "audit_summary": self._audit_summary_from_payload(payload),
        }

    def get_campaign_transition_options(self, workspace: str, campaign_id: str) -> dict[str, Any]:
        payload = self.get_campaign_detail(workspace, campaign_id)
        return {
            "campaign_id": _text(campaign_id),
            "options": self._transition_options_from_payload(payload),
        }

    def get_campaign_recovery_candidates(self, workspace: str, campaign_id: str) -> dict[str, Any]:
        payload = self.get_campaign_detail(workspace, campaign_id)
        return {
            "campaign_id": _text(campaign_id),
            "execution_state": _text(payload.get("execution_state")),
            "closure_state": _text(payload.get("closure_state")),
            "candidates": self._recovery_candidates_from_payload(payload),
        }

    def list_audit_actions(self, workspace: str, campaign_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        payload = self.get_campaign_detail(workspace, campaign_id)
        operator_plane = self._operator_plane_from_payload(payload)
        receipts = {
            _text(item.get("action_id")): dict(item)
            for item in operator_plane.get("patch_receipts") or []
            if isinstance(item, Mapping) and _text(item.get("action_id"))
        }
        recoveries = {
            _text(item.get("action_id")): dict(item)
            for item in operator_plane.get("recovery_decisions") or []
            if isinstance(item, Mapping) and _text(item.get("action_id"))
        }
        items: list[dict[str, Any]] = []
        for action in operator_plane.get("actions") or []:
            if not isinstance(action, Mapping):
                continue
            action_id = _text(action.get("action_id"))
            receipt = receipts.get(action_id, {})
            recovery = recoveries.get(action_id, {})
            items.append(
                {
                    **dict(action),
                    "patch_receipt": receipt,
                    "recovery_decision": recovery,
                }
            )
        items.sort(key=lambda item: (_text(item.get("created_at")), _text(item.get("action_id"))), reverse=True)
        target_limit = max(0, int(limit or 0))
        if target_limit > 0:
            return items[:target_limit]
        return items

    def get_audit_action_detail(self, workspace: str, campaign_id: str, action_id: str) -> dict[str, Any]:
        return self._campaign_service.get_operator_action_detail(workspace, campaign_id, action_id)

    def get_prompt_surface(self, workspace: str, campaign_id: str, *, node_id: str = "") -> dict[str, Any]:
        payload = self.get_campaign_detail(workspace, campaign_id)
        return self._prompt_surface_from_payload(workspace, payload, node_id=node_id)

    def patch_prompt_surface(
        self,
        workspace: str,
        campaign_id: str,
        *,
        patch: Mapping[str, Any] | None = None,
        node_id: str = "",
    ) -> dict[str, Any]:
        self._assert_mutations_allowed(workspace)
        patch_map = dict(patch or {})
        before = self.get_prompt_surface(workspace, campaign_id, node_id=node_id)
        payload = self.get_campaign_detail(workspace, campaign_id)
        metadata = _mapping(payload.get("metadata"))
        metadata_patch: dict[str, Any] = {}

        raw_skill_exposure = _mapping(metadata.get("skill_exposure"))
        if "skill_exposure" in patch_map:
            normalized = normalize_skill_exposure_payload(
                _mapping(patch_map.get("skill_exposure")),
                provider_skill_source="butler",
                default_collection_id="codex_default",
            )
            metadata_patch["skill_exposure"] = dict(normalized or {})
        elif any(key in patch_map for key in ("collection_id", "family_hints", "direct_skill_names", "direct_skill_paths", "provider_overrides")):
            merged_skill = _merge_nested(
                raw_skill_exposure,
                {
                    "collection_id": patch_map.get("collection_id"),
                    "family_hints": patch_map.get("family_hints"),
                    "direct_skill_names": patch_map.get("direct_skill_names"),
                    "direct_skill_paths": patch_map.get("direct_skill_paths"),
                    "provider_overrides": patch_map.get("provider_overrides"),
                },
            )
            normalized = normalize_skill_exposure_payload(
                merged_skill,
                provider_skill_source="butler",
                default_collection_id="codex_default",
            )
            metadata_patch["skill_exposure"] = dict(normalized or {})

        governance_patch = {
            key: patch_map.get(key)
            for key in ("risk_level", "autonomy_profile", "approval_state")
            if key in patch_map
        }
        if governance_patch:
            metadata_patch["governance_contract"] = governance_patch

        if node_id:
            overlays = _mapping(metadata.get("operator_prompt_overlays"))
            current_overlay = _mapping(overlays.get(node_id))
            merged_overlay = _merge_nested(current_overlay, _mapping(patch_map.get("node_overlay")))
            for key in ("prompt_profile", "phase_overlay", "governance_blocks", "provider_overrides", "notes"):
                if key in patch_map:
                    merged_overlay[key] = patch_map.get(key)
            overlays[_text(node_id)] = merged_overlay
            metadata_patch["operator_prompt_overlays"] = overlays
        else:
            current_surface = _mapping(metadata.get("operator_prompt_surface"))
            surface_patch = _mapping(patch_map.get("surface"))
            for key in ("prompt_profile", "phase_overlays", "governance_blocks", "notes"):
                if key in patch_map:
                    surface_patch[key] = patch_map.get(key)
            metadata_patch["operator_prompt_surface"] = _merge_nested(current_surface, surface_patch)

        self._campaign_service.update_campaign_metadata(workspace, campaign_id, metadata_patch)
        after = self.get_prompt_surface(workspace, campaign_id, node_id=node_id)
        self._record_operator_audit(
            workspace,
            campaign_id,
            action_type="prompt_surface_patch",
            target_scope="agent" if _text(node_id) else "campaign",
            target_node_id=node_id,
            result_summary="prompt surface updated",
            operator_reason=_text(patch_map.get("operator_reason") or patch_map.get("reason")),
            policy_source=_text(patch_map.get("policy_source") or "console.prompt_surface"),
            patch_payload=patch_map,
            before_summary=self._prompt_surface_summary(before),
            after_summary=self._prompt_surface_summary(after),
            patch_kind="prompt_surface",
            effective_timing="future_execution",
        )
        return after

    def get_draft_workflow_authoring(self, workspace: str, draft_id: str) -> dict[str, Any]:
        draft = self._require_draft(workspace, draft_id)
        return self._draft_workflow_authoring_payload(draft)

    def get_campaign_workflow_authoring(self, workspace: str, campaign_id: str) -> dict[str, Any]:
        payload = self.get_campaign_detail(workspace, campaign_id)
        return self._campaign_workflow_authoring_payload(payload)

    def patch_draft_workflow_authoring(
        self,
        workspace: str,
        draft_id: str,
        patch: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        patch_map = dict(patch or {})
        draft_patch = {
            key: patch_map.get(key)
            for key in ("selected_template_id", "composition_mode")
            if key in patch_map
        }
        if "composition_plan" in patch_map:
            draft_patch["composition_plan"] = _mapping(patch_map.get("composition_plan"))
        if "skeleton_changed" in patch_map:
            draft_patch["skeleton_changed"] = bool(patch_map.get("skeleton_changed"))
        self.patch_draft(workspace, draft_id, draft_patch)
        return self.get_draft_workflow_authoring(workspace, draft_id)

    def patch_campaign_workflow_authoring(
        self,
        workspace: str,
        campaign_id: str,
        patch: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._assert_mutations_allowed(workspace)
        patch_map = dict(patch or {})
        before = self.get_campaign_workflow_authoring(workspace, campaign_id)
        payload = self.get_campaign_detail(workspace, campaign_id)
        metadata = _mapping(payload.get("metadata"))
        spec_payload = _mapping(metadata.get("spec"))
        spec_metadata = _mapping(spec_payload.get("metadata"))
        template_contract = _mapping(metadata.get("template_contract") or spec_metadata.get("template_contract"))
        live_patch = _mapping(metadata.get("live_workflow_patch"))
        composition_plan = _merge_nested(
            _mapping(template_contract.get("composition_plan")),
            _mapping(patch_map.get("composition_plan")),
        )
        if "phase_plan" in patch_map:
            composition_plan["phase_plan"] = _list_of_text(patch_map.get("phase_plan"))
        if "role_plan" in patch_map:
            composition_plan["role_plan"] = _list_of_text(patch_map.get("role_plan"))
        if "governance_plan" in patch_map:
            composition_plan["governance_plan"] = _mapping(patch_map.get("governance_plan"))
        if "diff_summary" in patch_map:
            composition_plan["diff_summary"] = _list_of_text(patch_map.get("diff_summary"))
        updated_contract = _merge_nested(
            template_contract,
            {
                "template_origin": _text(patch_map.get("template_id") or template_contract.get("template_origin")),
                "composition_mode": _text(patch_map.get("composition_mode") or template_contract.get("composition_mode") or "template"),
                "skeleton_changed": bool(patch_map.get("skeleton_changed", template_contract.get("skeleton_changed"))),
                "composition_plan": composition_plan,
            },
        )
        metadata_patch = {
            "template_contract": updated_contract,
            "spec": {
                **spec_payload,
                "template_origin": updated_contract.get("template_origin"),
                "composition_mode": updated_contract.get("composition_mode"),
                "skeleton_changed": bool(updated_contract.get("skeleton_changed")),
                "composition_plan": composition_plan,
                "metadata": {
                    **spec_metadata,
                    "template_contract": updated_contract,
                },
            },
            "live_workflow_patch": {
                "updated_at": _utc_now_iso(),
                "phase_plan": _list_of_text(composition_plan.get("phase_plan")),
                "role_plan": _list_of_text(composition_plan.get("role_plan")),
                "transition_rules": (
                    _list_of_mapping(patch_map.get("transition_rules"))
                    if "transition_rules" in patch_map
                    else _list_of_mapping(live_patch.get("transition_rules"))
                ),
                "recovery_entries": (
                    _list_of_mapping(patch_map.get("recovery_entries"))
                    if "recovery_entries" in patch_map
                    else _list_of_mapping(live_patch.get("recovery_entries"))
                ),
            },
        }
        self._campaign_service.update_campaign_metadata(workspace, campaign_id, metadata_patch)
        after = self.get_campaign_workflow_authoring(workspace, campaign_id)
        self._record_operator_audit(
            workspace,
            campaign_id,
            action_type="workflow_authoring_patch",
            target_scope="campaign",
            target_node_id="",
            result_summary="workflow authoring updated",
            operator_reason=_text(patch_map.get("operator_reason") or patch_map.get("reason")),
            policy_source=_text(patch_map.get("policy_source") or "console.workflow_authoring"),
            patch_payload=patch_map,
            before_summary=self._workflow_authoring_summary(before),
            after_summary=self._workflow_authoring_summary(after),
            patch_kind="workflow_authoring",
            effective_timing="future_execution",
        )
        return after

    def get_draft_compile_preview(self, workspace: str, draft_id: str) -> dict[str, Any]:
        draft = self._require_draft(workspace, draft_id)
        authoring = self._draft_workflow_authoring_payload(draft)
        return self._compile_preview_from_authoring(
            scope="draft",
            scope_id=draft.draft_id,
            goal=draft.goal,
            authoring=authoring,
        )

    def patch_draft(self, workspace: str, draft_id: str, patch: Mapping[str, Any] | None = None) -> FrontdoorDraftView:
        self._assert_mutations_allowed(workspace)
        draft = self._require_draft(workspace, draft_id)
        patch_map = dict(patch or {})
        updated = replace(draft)
        if "goal" in patch_map:
            updated.goal = _text(patch_map.get("goal"))
        if "materials" in patch_map:
            updated.materials = _list_of_text(patch_map.get("materials"))
        if "hard_constraints" in patch_map:
            updated.hard_constraints = _list_of_text(patch_map.get("hard_constraints"))
        if "acceptance_criteria" in patch_map:
            updated.acceptance_criteria = _list_of_text(patch_map.get("acceptance_criteria"))
        if "selected_template_id" in patch_map:
            updated.selected_template_id = _text(patch_map.get("selected_template_id"))
        if "skill_selection" in patch_map:
            raw_skill_selection = patch_map.get("skill_selection")
            normalized_selection = normalize_skill_exposure_payload(
                dict(raw_skill_selection) if isinstance(raw_skill_selection, Mapping) else None,
                provider_skill_source="butler",
            )
            updated.skill_selection = dict(normalized_selection or {})
        if "recommended_template_id" in patch_map:
            updated.recommended_template_id = _text(patch_map.get("recommended_template_id"))
        if "composition_mode" in patch_map:
            updated.composition_mode = _text(patch_map.get("composition_mode"))
        if "composition_plan" in patch_map:
            updated.composition_plan = _mapping(patch_map.get("composition_plan"))
        if "skeleton_changed" in patch_map:
            updated.skeleton_changed = bool(patch_map.get("skeleton_changed"))
        if "frontdoor_mode_id" in patch_map:
            updated.frontdoor_mode_id = _text(patch_map.get("frontdoor_mode_id")).lower()
        if "task_mode" in patch_map:
            updated.task_mode = _text(patch_map.get("task_mode"))
        if "pending_confirmation" in patch_map:
            updated.pending_confirmation = bool(patch_map.get("pending_confirmation"))
        updated.touch()
        self._store.save(workspace=workspace, draft=updated)
        return self._draft_view_from_draft(updated)

    def launch_draft(self, workspace: str, draft_id: str) -> FrontdoorDraftView:
        self._assert_mutations_allowed(workspace)
        draft = self._require_draft(workspace, draft_id)
        if _text(draft.started_campaign_id):
            return self._draft_view_from_draft(draft)
        template_id = _text(draft.selected_template_id or draft.recommended_template_id)
        mode_id = _text(draft.frontdoor_mode_id or ("research" if "research" in template_id else "delivery")) or "delivery"
        draft_ref = f"negotiations/campaign/{_text(draft.session_id)}.json"
        spec = {
            "top_level_goal": _text(draft.goal) or "Console draft launch",
            "materials": list(draft.materials),
            "hard_constraints": list(draft.hard_constraints),
            "template_origin": template_id,
            "composition_mode": _text(draft.composition_mode or ("composition" if draft.skeleton_changed else "template")),
            "skeleton_changed": bool(draft.skeleton_changed),
            "composition_plan": _mapping(draft.composition_plan),
            "created_from": "console_draft_board",
            "negotiation_session_id": draft.session_id,
            "metadata": {
                "planning_contract": {
                    "mode_id": mode_id,
                    "plan_only": False,
                    "draft_ref": draft_ref,
                },
                "governance_contract": {
                    "autonomy_profile": "reviewed_delivery",
                    "risk_level": "medium",
                    "approval_state": "none",
                },
                "console_contract": {
                    "draft_id": draft.draft_id,
                    "frontdoor_ref": {"session_id": draft.session_id},
                    "launch_source": "console_draft_board",
                },
                "template_contract": {
                    "template_origin": template_id,
                    "composition_mode": _text(draft.composition_mode or ("composition" if draft.skeleton_changed else "template")),
                    "skeleton_changed": bool(draft.skeleton_changed),
                    "composition_plan": _mapping(draft.composition_plan),
                    "created_from": "console_draft_board",
                    "negotiation_session_id": draft.session_id,
                },
            },
        }
        normalized_skill_selection = normalize_skill_exposure_payload(
            dict(draft.skill_selection) if isinstance(draft.skill_selection, Mapping) else None,
            default_collection_id="codex_default" if mode_id in {"delivery", "research"} else "",
            provider_skill_source="butler",
        )
        if normalized_skill_selection is not None:
            spec.setdefault("metadata", {})["skill_exposure"] = normalized_skill_selection
        created = self._campaign_service.create_campaign(workspace, spec)
        self._campaign_service.resume_campaign(workspace, created["campaign_id"])
        launched = replace(draft)
        launched.started_campaign_id = _text(created.get("campaign_id"))
        launched.status = "started"
        launched.frontdoor_mode_id = mode_id
        launched.touch()
        self._store.save(workspace=workspace, draft=launched)
        return self._draft_view_from_draft(launched)

    @staticmethod
    def _operator_plane_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        metadata = _mapping(payload.get("metadata"))
        operator_plane = _mapping(metadata.get("operator_plane"))
        return {
            "actions": _list_of_mapping(operator_plane.get("actions")),
            "patch_receipts": _list_of_mapping(operator_plane.get("patch_receipts")),
            "recovery_decisions": _list_of_mapping(operator_plane.get("recovery_decisions")),
            "latest_action_id": _text(operator_plane.get("latest_action_id")),
        }

    def _audit_summary_from_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        operator_plane = self._operator_plane_from_payload(payload)
        actions = operator_plane["actions"]
        latest = actions[-1] if actions else {}
        return {
            "action_count": len(actions),
            "patch_receipt_count": len(operator_plane["patch_receipts"]),
            "recovery_decision_count": len(operator_plane["recovery_decisions"]),
            "latest_action": latest,
        }

    @staticmethod
    def _phase_path_from_payload(payload: Mapping[str, Any]) -> list[str]:
        task_summary = _mapping(payload.get("task_summary"))
        plan = _mapping(task_summary.get("plan"))
        macro_path = _list_of_text(plan.get("macro_path"))
        if macro_path:
            return macro_path
        phase_runtime = _mapping(payload.get("phase_runtime"))
        path = _list_of_text(phase_runtime.get("phase_path"))
        if path:
            return path
        return ["ledger", "turn", "delivery", "harness"]

    def _available_operator_actions(self, payload: Mapping[str, Any]) -> list[str]:
        status = _text(payload.get("status") or _mapping(payload.get("campaign_view")).get("status")).lower()
        actions = ["append_feedback", "annotate_governance", "abort", "force_recover_from_snapshot"]
        if status in {"running", "waiting"}:
            actions.append("pause")
        if status in {"draft", "paused", "waiting"}:
            actions.append("resume")
        pending_checks = _list_of_text(payload.get("operational_checks_pending")) + _list_of_text(payload.get("closure_checks_pending"))
        if pending_checks:
            actions.extend(["resolve_checks", "waive_checks"])
        if _text(_mapping(payload.get("governance_summary")).get("approval_state")) in {"requested", "approved", "rejected"}:
            actions.extend(["request_approval", "resolve_approval"])
        return sorted({item for item in actions if item})

    def _transition_options_from_payload(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        latest_turn_receipt = _mapping(payload.get("latest_turn_receipt"))
        task_summary = _mapping(payload.get("task_summary"))
        progress = _mapping(task_summary.get("progress"))
        return [
            {
                "option_id": "resume:turn",
                "action": "resume",
                "transition_to": "turn",
                "label": "Resume Turn",
                "recommended": _text(payload.get("status")) in {"paused", "waiting", "draft"},
                "reason": _text(task_summary.get("next_action") or "run the next re-entrant supervisor turn"),
            },
            {
                "option_id": "recover:snapshot",
                "action": "force_recover_from_snapshot",
                "transition_to": "harness",
                "label": "Recover From Snapshot",
                "recommended": bool(_text(latest_turn_receipt.get("turn_id"))),
                "reason": _text(latest_turn_receipt.get("yield_reason") or progress.get("latest_summary") or "reload the canonical session snapshot"),
            },
        ]

    def _recovery_candidates_from_payload(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        task_summary = _mapping(payload.get("task_summary"))
        progress = _mapping(task_summary.get("progress"))
        latest_turn_receipt = _mapping(payload.get("latest_turn_receipt"))
        control_plane_refs = _mapping(_mapping(payload.get("metadata")).get("control_plane_refs"))
        canonical_session_id = _text(payload.get("canonical_session_id") or control_plane_refs.get("canonical_session_id"))
        candidates: list[dict[str, Any]] = []
        if canonical_session_id:
            candidates.append(
                {
                    "candidate_id": "recover:snapshot",
                    "action": "force_recover_from_snapshot",
                    "resume_from": "snapshot",
                    "target_node_id": "harness",
                    "label": "Recover canonical session",
                    "reason": _text(latest_turn_receipt.get("yield_reason") or "reload the session snapshot without changing campaign identity"),
                    "canonical_session_id": canonical_session_id,
                }
            )
        candidates.append(
            {
                "candidate_id": "resume:turn",
                "action": "resume",
                "resume_from": "turn",
                "target_node_id": "turn",
                "label": "Run one supervisor turn",
                "reason": _text(task_summary.get("next_action") or progress.get("latest_summary") or "continue the agent supervisor loop"),
            }
        )
        for check_id in _list_of_text(payload.get("operational_checks_pending"))[:4]:
            candidates.append(
                {
                    "candidate_id": f"resolve:{check_id}",
                    "action": "resolve_checks",
                    "check_ids": [check_id],
                    "label": f"Resolve {check_id}",
                    "reason": "close the blocking operational check and continue",
                }
            )
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for item in candidates:
            candidate_id = _text(item.get("candidate_id"))
            if not candidate_id or candidate_id in seen:
                continue
            seen.add(candidate_id)
            result.append(item)
        return result

    def _prompt_surface_from_payload(
        self,
        workspace: str,
        payload: Mapping[str, Any],
        *,
        node_id: str = "",
    ) -> dict[str, Any]:
        metadata = _mapping(payload.get("metadata"))
        spec_payload = _mapping(metadata.get("spec"))
        spec_metadata = _mapping(spec_payload.get("metadata"))
        skill_exposure = normalize_skill_exposure_payload(
            _mapping(metadata.get("skill_exposure") or spec_metadata.get("skill_exposure")),
            provider_skill_source="butler",
            default_collection_id="codex_default",
        ) or {}
        governance_contract = _merge_nested(
            _mapping(spec_metadata.get("governance_contract")),
            _mapping(metadata.get("governance_contract")),
        )
        planning_contract = _merge_nested(
            _mapping(spec_metadata.get("planning_contract")),
            _mapping(metadata.get("planning_contract")),
        )
        template_contract = _merge_nested(
            _mapping(spec_metadata.get("template_contract")),
            _mapping(metadata.get("template_contract")),
        )
        operator_surface = _mapping(metadata.get("operator_prompt_surface"))
        node_overlay = _mapping(_mapping(metadata.get("operator_prompt_overlays")).get(node_id))
        current_phase = _text(node_id or payload.get("current_phase") or _mapping(payload.get("session_view")).get("active_step"))
        materialized = self._materialize_prompt_preview(
            workspace,
            payload,
            phase_id=current_phase,
            skill_exposure=skill_exposure,
            operator_surface=operator_surface,
            node_overlay=node_overlay,
        )
        observation = build_skill_exposure_observation(
            workspace,
            exposure=skill_exposure,
            materialization_mode="prompt_block",
        )
        return {
            "campaign_id": _text(payload.get("campaign_id") or _mapping(payload.get("campaign_view")).get("campaign_id")),
            "node_id": _text(node_id),
            "phase_id": current_phase,
            "structured_contract": {
                "skill_exposure": skill_exposure,
                "skill_observation": observation,
                "governance_contract": governance_contract,
                "planning_contract": planning_contract,
                "template_contract": template_contract,
                "prompt_surface": operator_surface,
                "node_overlay": node_overlay,
            },
            "preview": materialized,
            "policy_sources": {
                "skill_exposure": "metadata.skill_exposure",
                "governance_contract": "metadata.governance_contract",
                "template_contract": "metadata.template_contract",
                "prompt_surface": "metadata.operator_prompt_surface",
                "node_overlay": "metadata.operator_prompt_overlays",
            },
            "audit_summary": self._audit_summary_from_payload(payload),
        }

    def _materialize_prompt_preview(
        self,
        workspace: str,
        payload: Mapping[str, Any],
        *,
        phase_id: str,
        skill_exposure: Mapping[str, Any],
        operator_surface: Mapping[str, Any],
        node_overlay: Mapping[str, Any],
    ) -> dict[str, Any]:
        goal = _text(payload.get("top_level_goal") or _mapping(payload.get("campaign_view")).get("title"))
        working_contract = _mapping(payload.get("working_contract"))
        materials = ", ".join(_list_of_text(payload.get("materials"))) or "none"
        constraints = ", ".join(_list_of_text(payload.get("hard_constraints"))) or "none"
        acceptance = ", ".join(_list_of_text(working_contract.get("working_acceptance"))) or "none"
        phase = _text(phase_id or payload.get("current_phase") or "discover")
        body_lines = [
            f"Phase: {phase or 'discover'}",
            f"Goal: {goal or 'n/a'}",
            f"Working goal: {_text(working_contract.get('working_goal')) or goal or 'n/a'}",
            f"Materials: {materials}",
            f"Hard constraints: {constraints}",
            f"Acceptance: {acceptance}",
        ]
        if operator_surface:
            body_lines.append(f"Campaign prompt surface: {json.dumps(operator_surface, ensure_ascii=False)}")
        if node_overlay:
            body_lines.append(f"Node overlay: {json.dumps(node_overlay, ensure_ascii=False)}")
        body_lines.append("Return a concise, operator-auditable result for this phase.")
        body = "\n".join(body_lines)
        exposure_block = render_skill_exposure_prompt(
            workspace,
            exposure=dict(skill_exposure or {}),
            source_prompt=goal,
            runtime_name="console_preview",
            max_catalog_skills=24,
            max_catalog_chars=1800,
        )
        final_prompt = f"{exposure_block}\n\n{body}" if exposure_block else body
        return {
            "preview_kind": "estimated_materialization",
            "body": body,
            "final_prompt": final_prompt,
            "prompt_length": len(final_prompt),
            "phase_id": phase,
        }

    @staticmethod
    def _prompt_surface_summary(surface: Mapping[str, Any]) -> dict[str, Any]:
        structured = _mapping(surface.get("structured_contract"))
        preview = _mapping(surface.get("preview"))
        skill_exposure = _mapping(structured.get("skill_exposure"))
        governance = _mapping(structured.get("governance_contract"))
        return {
            "phase_id": _text(surface.get("phase_id")),
            "node_id": _text(surface.get("node_id")),
            "collection_id": _text(skill_exposure.get("collection_id")),
            "family_hints": _list_of_text(skill_exposure.get("family_hints")),
            "risk_level": _text(governance.get("risk_level")),
            "autonomy_profile": _text(governance.get("autonomy_profile")),
            "prompt_length": _coerce_int(preview.get("prompt_length")),
        }

    def _draft_workflow_authoring_payload(self, draft: CampaignNegotiationDraft) -> dict[str, Any]:
        template_id = _text(draft.selected_template_id or draft.recommended_template_id)
        template = self._template_registry.get_template(template_id)
        default_plan = self._template_registry.build_default_composition(template_id)
        composition_plan = _merge_nested(default_plan, _mapping(draft.composition_plan))
        phase_plan = _list_of_text(composition_plan.get("phase_plan")) or list(template.default_phase_ids if template else [])
        role_plan = _list_of_text(composition_plan.get("role_plan")) or list(template.default_role_ids if template else [])
        governance_plan = _mapping(composition_plan.get("governance_plan"))
        if template is not None:
            governance_plan.setdefault("profile", template.governance_profile)
        return {
            "scope": "draft",
            "scope_id": draft.draft_id,
            "title": _text(draft.goal) or draft.draft_id,
            "template_id": template_id,
            "template_label": template.display_name if template is not None else template_id,
            "composition_mode": _text(draft.composition_mode or composition_plan.get("composition_mode") or "template"),
            "skeleton_changed": bool(draft.skeleton_changed or composition_plan.get("skeleton_changed")),
            "phase_plan": phase_plan,
            "role_plan": role_plan,
            "governance_plan": governance_plan,
            "diff_summary": _list_of_text(composition_plan.get("diff_summary")),
            "linked_campaign_id": _text(draft.started_campaign_id),
        }

    def _campaign_workflow_authoring_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        metadata = _mapping(payload.get("metadata"))
        spec_payload = _mapping(metadata.get("spec"))
        spec_metadata = _mapping(spec_payload.get("metadata"))
        template_contract = _merge_nested(
            _mapping(spec_metadata.get("template_contract")),
            _mapping(metadata.get("template_contract")),
        )
        template_id = _text(template_contract.get("template_origin") or spec_payload.get("template_origin"))
        template = self._template_registry.get_template(template_id)
        default_plan = self._template_registry.build_default_composition(template_id)
        composition_plan = _merge_nested(default_plan, _mapping(template_contract.get("composition_plan")))
        live_patch = _mapping(metadata.get("live_workflow_patch"))
        phase_plan = _list_of_text(live_patch.get("phase_plan")) or _list_of_text(composition_plan.get("phase_plan")) or self._phase_path_from_payload(payload)
        role_plan = _list_of_text(live_patch.get("role_plan")) or _list_of_text(composition_plan.get("role_plan")) or list(template.default_role_ids if template else [])
        return {
            "scope": "campaign",
            "scope_id": _text(payload.get("campaign_id") or _mapping(payload.get("campaign_view")).get("campaign_id")),
            "title": _text(_mapping(payload.get("campaign_view")).get("title") or payload.get("campaign_title")),
            "template_id": template_id,
            "template_label": template.display_name if template is not None else template_id,
            "composition_mode": _text(template_contract.get("composition_mode") or "template"),
            "skeleton_changed": bool(template_contract.get("skeleton_changed")),
            "phase_plan": phase_plan,
            "role_plan": role_plan,
            "governance_plan": _mapping(composition_plan.get("governance_plan")),
            "diff_summary": _list_of_text(composition_plan.get("diff_summary")),
            "transition_rules": _list_of_mapping(live_patch.get("transition_rules")),
            "recovery_entries": _list_of_mapping(live_patch.get("recovery_entries")),
            "current_phase": _text(payload.get("current_phase")),
            "next_phase": _text(payload.get("next_phase")),
        }

    def _compile_preview_from_authoring(
        self,
        *,
        scope: str,
        scope_id: str,
        goal: str,
        authoring: Mapping[str, Any],
    ) -> dict[str, Any]:
        phase_plan = _list_of_text(authoring.get("phase_plan"))
        role_plan = _list_of_text(authoring.get("role_plan"))
        governance_plan = _mapping(authoring.get("governance_plan"))
        validation_errors: list[str] = []
        warnings: list[str] = []
        if not _text(authoring.get("template_id")):
            validation_errors.append("missing template_id")
        if not phase_plan:
            validation_errors.append("phase_plan is empty")
        if not role_plan:
            validation_errors.append("role_plan is empty")
        if bool(authoring.get("skeleton_changed")) and not _list_of_text(authoring.get("diff_summary")):
            warnings.append("skeleton_changed is true but diff_summary is empty")
        if governance_plan.get("profile") == "guarded_autonomy":
            warnings.append("guarded_autonomy requires explicit approval checkpoints before launch")
        return {
            "scope": scope,
            "scope_id": scope_id,
            "goal": _text(goal),
            "template_id": _text(authoring.get("template_id")),
            "compile_result": "ready" if not validation_errors else "invalid",
            "validation_errors": validation_errors,
            "warnings": warnings,
            "risk_hints": [
                f"phase_count={len(phase_plan)}",
                f"role_count={len(role_plan)}",
                f"governance_profile={_text(governance_plan.get('profile') or 'reviewed_delivery')}",
            ],
            "compiled_contract": {
                "composition_mode": _text(authoring.get("composition_mode")),
                "phase_plan": phase_plan,
                "role_plan": role_plan,
                "governance_plan": governance_plan,
                "diff_summary": _list_of_text(authoring.get("diff_summary")),
            },
        }

    @staticmethod
    def _workflow_authoring_summary(authoring: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "template_id": _text(authoring.get("template_id")),
            "composition_mode": _text(authoring.get("composition_mode")),
            "phase_plan": _list_of_text(authoring.get("phase_plan")),
            "role_plan": _list_of_text(authoring.get("role_plan")),
            "skeleton_changed": bool(authoring.get("skeleton_changed")),
        }

    def _record_operator_audit(
        self,
        workspace: str,
        campaign_id: str,
        *,
        action_type: str,
        target_scope: str,
        target_node_id: str,
        result_summary: str,
        operator_reason: str,
        policy_source: str,
        patch_payload: Mapping[str, Any] | None,
        before_summary: Mapping[str, Any],
        after_summary: Mapping[str, Any],
        patch_kind: str,
        effective_timing: str,
        recovery_payload: Mapping[str, Any] | None = None,
        status: str = "applied",
    ) -> dict[str, str]:
        action_id = f"operator_action_{uuid4().hex[:12]}"
        trace_id = f"trace_{uuid4().hex[:12]}"
        receipt_id = f"operator_receipt_{uuid4().hex[:12]}"
        recovery_decision = None
        if isinstance(recovery_payload, Mapping) and recovery_payload:
            recovery_decision = {
                "decision_id": f"recovery_decision_{uuid4().hex[:12]}",
                "action_id": action_id,
                "resume_from": _text(recovery_payload.get("resume_from")),
                "recovery_candidate_id": _text(recovery_payload.get("recovery_candidate_id")),
                "decision_summary": _text(recovery_payload.get("decision_summary") or result_summary),
                "result_state": _text(recovery_payload.get("result_state") or status),
                "metadata": dict(recovery_payload),
            }
        self._campaign_service.record_operator_action(
            workspace,
            campaign_id,
            action={
                "action_id": action_id,
                "campaign_id": campaign_id,
                "target_scope": target_scope,
                "target_node_id": _text(target_node_id),
                "action_type": _text(action_type),
                "operator_id": "console_user",
                "operator_reason": _text(operator_reason),
                "policy_source": _text(policy_source),
                "trace_id": trace_id,
                "status": _text(status) or "applied",
                "result_summary": _text(result_summary),
                "payload": dict(patch_payload or {}),
                "receipt_id": receipt_id,
                "recovery_decision_id": _text((recovery_decision or {}).get("decision_id")),
            },
            patch_receipt={
                "receipt_id": receipt_id,
                "action_id": action_id,
                "patch_kind": _text(patch_kind),
                "before_summary": dict(before_summary or {}),
                "after_summary": dict(after_summary or {}),
                "effective_scope": _text(target_scope),
                "effective_timing": _text(effective_timing) or "future_execution",
                "target_node_id": _text(target_node_id),
                "changed_fields": sorted({*before_summary.keys(), *after_summary.keys()}),
                "metadata": {"policy_source": _text(policy_source)},
            },
            recovery_decision=recovery_decision,
        )
        return {
            "action_id": action_id,
            "trace_id": trace_id,
            "receipt_id": receipt_id,
            "recovery_decision_id": _text((recovery_decision or {}).get("decision_id")),
        }

    def _project_campaign_runtime(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        campaign_view = _mapping(payload.get("campaign_view"))
        workflow_session = _mapping(payload.get("workflow_session"))
        collaboration = _mapping(workflow_session.get("collaboration"))
        task_summary = _mapping(payload.get("task_summary"))
        progress = _mapping(task_summary.get("progress"))
        output = _mapping(task_summary.get("output"))
        session_evidence = _mapping(payload.get("session_evidence"))
        latest_turn_receipt = _mapping(payload.get("latest_turn_receipt"))
        status = _text(campaign_view.get("status") or payload.get("status")).lower()
        step_ids = ["ledger", "turn", "delivery", "harness"]
        active_step = "turn" if status not in {"completed", "failed", "cancelled"} else ""
        next_step = "harness" if status not in {"completed", "failed", "cancelled"} else ""
        role_bindings = self._role_bindings_by_role_id(workflow_session)
        current_agent = None
        if active_step:
            current_status = "paused" if status == "paused" else "running"
            current_agent = self._agent_for_step(
                campaign_view=campaign_view,
                role_bindings=role_bindings,
                step_id=active_step,
                status=current_status,
                queue_state=current_status,
                source="exact",
                summary=self._agent_summary(payload, active_step),
            )
        next_agent = None
        if next_step:
            next_agent = self._agent_for_step(
                campaign_view=campaign_view,
                role_bindings=role_bindings,
                step_id=next_step,
                status="next",
                queue_state="next",
                source="inferred",
                summary=self._agent_summary(payload, next_step),
            )

        queued_agents: list[AgentExecutionView] = []
        if status not in {"completed", "failed", "cancelled"} and not _list_of_text(output.get("latest_delivery_refs")):
            queued_agents.append(
                self._agent_for_step(
                    campaign_view=campaign_view,
                    role_bindings=role_bindings,
                    step_id="delivery",
                    status="queued",
                    queue_state="queued",
                    source="inferred",
                    summary=self._agent_summary(payload, "delivery"),
                )
            )

        nodes = self._build_project_nodes(payload, role_bindings=role_bindings, active_step=active_step, next_step=next_step)
        edges = self._build_project_edges(step_ids=step_ids, active_step=active_step)
        artifacts = self._artifact_list_from_payload(payload)
        records = self._record_list_from_payload(payload)
        timeline_items = self._project_timeline_items(
            payload,
            current_agent=current_agent,
            next_agent=next_agent,
            queued_agents=queued_agents,
        )
        idle_reason = ""
        if status in {"completed", "done", "succeeded"}:
            idle_reason = "campaign completed; no running or queued agents remain"
        elif status == "paused":
            idle_reason = "campaign is paused; canonical session and latest turn receipt remain available for recovery"
        elif status == "waiting":
            idle_reason = "campaign is waiting on harness or operator input before the next supervisor turn"
        summary = _text(progress.get("latest_summary") or latest_turn_receipt.get("summary") or task_summary.get("next_action"))
        board_status = "completed" if status == "completed" else ("paused" if status == "paused" else "running")
        board_lane = "completed" if status == "completed" else ("queued" if status == "paused" else "running")
        preview_defaults = {
            "selected_node_id": active_step or (nodes[0].id if nodes else ""),
            "preview_artifact_id": artifacts[0].artifact_id if artifacts else "",
            "mode": "graph",
        }
        return {
            "campaign_view": campaign_view,
            "active_step": active_step,
            "next_step": next_step,
            "current_agent": current_agent,
            "next_agent": next_agent,
            "queued_agents": queued_agents,
            "nodes": nodes,
            "edges": edges,
            "artifacts": artifacts,
            "records": records,
            "timeline_items": timeline_items,
            "summary": summary or _text(task_summary.get("next_action")),
            "idle_reason": idle_reason,
            "role_bindings": role_bindings,
            "board_status": board_status,
            "board_lane": board_lane,
            "collaboration": collaboration,
            "latest_turn_receipt": latest_turn_receipt,
            "session_evidence": session_evidence,
            "preview_defaults": preview_defaults,
        }

    def _build_project_nodes(
        self,
        payload: Mapping[str, Any],
        *,
        role_bindings: dict[str, dict[str, Any]],
        active_step: str,
        next_step: str,
    ) -> list[BoardNodeView]:
        campaign_view = _mapping(payload.get("campaign_view"))
        task_summary = _mapping(payload.get("task_summary"))
        status = _text(campaign_view.get("status") or payload.get("status")).lower()
        progress = _mapping(task_summary.get("progress"))
        output = _mapping(task_summary.get("output"))
        latest_turn_receipt = _mapping(payload.get("latest_turn_receipt"))
        session_evidence = _mapping(payload.get("session_evidence"))
        delivery_refs = _list_of_text(output.get("latest_delivery_refs") or payload.get("latest_delivery_refs"))
        artifact_count = _coerce_int(output.get("artifact_count") or session_evidence.get("artifact_count"))
        step_ids = ["ledger", "turn", "delivery", "harness"]
        artifact_refs_by_step = {
            "turn": _list_of_text(latest_turn_receipt.get("delivery_refs")),
            "delivery": delivery_refs,
            "harness": [],
            "ledger": [],
        }
        nodes: list[BoardNodeView] = []
        for index, step_id in enumerate(step_ids):
            role_id = self._role_for_step(step_id)
            binding = role_bindings.get(role_id, {})
            node_status = "queued"
            if step_id == "ledger":
                node_status = "completed" if status != "draft" or _coerce_int(progress.get("turn_count")) > 0 else "running"
            elif step_id == "turn":
                node_status = "completed" if status in {"completed", "failed", "cancelled"} else "paused" if status == "paused" else "running"
            elif step_id == "delivery":
                if delivery_refs or artifact_count > 0:
                    node_status = "completed"
                elif status in {"running", "waiting"}:
                    node_status = "next"
            elif step_id == "harness":
                if status in {"completed", "failed", "cancelled"}:
                    node_status = "completed"
                elif status in {"paused", "waiting"}:
                    node_status = "running"
                else:
                    node_status = "next"
            display_title = self._step_display_title(step_id)
            display_brief = self._step_display_brief(payload, step_id=step_id, node_status=node_status)
            nodes.append(
                BoardNodeView(
                    id=step_id,
                    title=display_title,
                    display_title=display_title,
                    display_brief=display_brief,
                    subtitle=f"{role_id} · {_text(binding.get('agent_spec_id') or 'agent n/a')}",
                    role_label=self._role_label(role_id),
                    iteration_label=self._iteration_label(campaign_view),
                    updated_at_label=_display_time_cn(campaign_view.get("updated_at") or task_summary.get("updated_at")),
                    visual_state=node_status,
                    status=node_status,
                    lane="flow",
                    phase=step_id,
                    step_id=step_id,
                    role_id=role_id,
                    agent_spec_id=_text(binding.get("agent_spec_id")),
                    source="exact" if step_id == active_step else "inferred",
                    badges=[
                        self._node_primary_badge(node_status),
                        self._node_secondary_badge(step_id, artifact_refs_by_step.get(step_id, [])),
                    ],
                    artifact_refs=artifact_refs_by_step.get(step_id, []),
                    detail_available=bool(_text(campaign_view.get("campaign_id")) and step_id),
                    detail_campaign_id=_text(campaign_view.get("campaign_id")),
                    detail_node_id=step_id,
                    position={"x": 80.0 + index * 300.0, "y": 120.0 + (index % 2) * 48.0},
                    size={"w": DEFAULT_CANVAS_NODE_WIDTH, "h": DEFAULT_CANVAS_NODE_HEIGHT},
                    metadata={
                        "campaign_id": _text(campaign_view.get("campaign_id")),
                        "step_index": index,
                        "display_brief": display_brief,
                    },
                )
            )
        return nodes

    def _build_project_edges(self, *, step_ids: list[str], active_step: str) -> list[BoardEdgeView]:
        edges: list[BoardEdgeView] = []
        for index in range(len(step_ids) - 1):
            source = step_ids[index]
            target = step_ids[index + 1]
            edges.append(
                BoardEdgeView(
                    id=f"{source}__next__{target}",
                    source=source,
                    target=target,
                    kind="next",
                    active=source == "turn" and active_step == "turn",
                    label="next",
                    visual_kind="flow",
                    emphasis="active" if source == "turn" and active_step == "turn" else "normal",
                    is_back_edge=False,
                )
            )
        if "harness" in step_ids and "turn" in step_ids:
            edges.append(
                BoardEdgeView(
                    id="harness__loop__turn",
                    source="harness",
                    target="turn",
                    kind="loop",
                    active=active_step == "turn",
                    label="loop",
                    visual_kind="loop",
                    emphasis="active" if active_step == "turn" else "normal",
                    is_back_edge=True,
                )
            )
        return edges

    def _step_status(
        self,
        *,
        step_ids: list[str],
        step_id: str,
        active_step: str,
        next_step: str,
        campaign_status: str,
        artifact_refs_by_step: dict[str, list[str]],
    ) -> str:
        if step_id == active_step:
            return "running"
        if active_step and active_step in step_ids and step_id in step_ids:
            if step_ids.index(step_id) < step_ids.index(active_step):
                return "completed"
        if step_id == next_step:
            return "next"
        if campaign_status == "completed" and artifact_refs_by_step.get(step_id):
            return "completed"
        if artifact_refs_by_step.get(step_id) and not active_step:
            return "completed"
        return "queued"

    def _artifact_list_from_payload(self, payload: Mapping[str, Any]) -> list[ArtifactListItem]:
        items = _list_of_mapping(payload.get("artifacts"))
        rendered: list[ArtifactListItem] = []
        for item in items:
            ref = _text(item.get("ref"))
            previewable = Path(ref).suffix.lower() in TEXT_PREVIEW_SUFFIXES
            rendered.append(
                ArtifactListItem(
                    artifact_id=_text(item.get("artifact_id") or ref),
                    label=_text(item.get("label") or item.get("artifact_id") or ref),
                    kind=_text(item.get("kind")),
                    phase=_text(item.get("phase") or item.get("step_id")),
                    iteration=_coerce_int(item.get("iteration")),
                    created_at=_text(item.get("created_at")),
                    ref=ref,
                    previewable=previewable,
                    metadata=_mapping(item.get("metadata")),
                )
            )
        rendered.sort(key=lambda item: (item.iteration, item.created_at, item.artifact_id), reverse=True)
        return rendered

    def _record_list_from_payload(self, payload: Mapping[str, Any]) -> list[RecordListItem]:
        items: list[RecordListItem] = []
        campaign_view = _mapping(payload.get("campaign_view"))
        working_contract = _mapping(payload.get("working_contract"))
        latest_verdict = _mapping(payload.get("latest_verdict") or _mapping(payload.get("evaluation_summary")).get("latest_verdict"))
        task_summary = _mapping(payload.get("task_summary"))
        latest_turn_receipt = _mapping(payload.get("latest_turn_receipt"))
        if working_contract:
            items.append(
                RecordListItem(
                    record_id="working_contract",
                    title="Working contract",
                    kind="contract",
                    created_at=_text(working_contract.get("updated_at") or working_contract.get("created_at")),
                    summary=_text(working_contract.get("working_goal")),
                    preview_kind="json",
                    preview_title="Working contract",
                    preview_language="json",
                    preview_content=json.dumps(working_contract, ensure_ascii=False, indent=2),
                    metadata={"campaign_id": _text(campaign_view.get("campaign_id"))},
                )
            )
        if latest_turn_receipt:
            items.append(
                RecordListItem(
                    record_id="latest_turn_receipt",
                    title="Latest turn receipt",
                    kind="turn_receipt",
                    created_at=_text(latest_turn_receipt.get("created_at")),
                    summary=_text(latest_turn_receipt.get("summary") or latest_turn_receipt.get("yield_reason")),
                    preview_kind="json",
                    preview_title="Latest turn receipt",
                    preview_language="json",
                    preview_content=json.dumps(latest_turn_receipt, ensure_ascii=False, indent=2),
                    metadata={"campaign_id": _text(campaign_view.get("campaign_id"))},
                )
            )
        if latest_verdict:
            items.append(
                RecordListItem(
                    record_id="latest_verdict",
                    title="Latest verdict",
                    kind="verdict",
                    created_at=_text(latest_verdict.get("created_at")),
                    summary=_text(latest_verdict.get("rationale") or latest_verdict.get("decision")),
                    preview_kind="json",
                    preview_title="Latest verdict",
                    preview_language="json",
                    preview_content=json.dumps(latest_verdict, ensure_ascii=False, indent=2),
                    metadata={"campaign_id": _text(campaign_view.get("campaign_id"))},
                )
            )
        if task_summary:
            items.append(
                RecordListItem(
                    record_id="task_summary",
                    title="Task summary",
                    kind="summary",
                    created_at=_text(payload.get("updated_at") or campaign_view.get("updated_at")),
                    summary=_text(task_summary.get("next_action") or task_summary.get("headline")),
                    preview_kind="json",
                    preview_title="Task summary",
                    preview_language="json",
                    preview_content=json.dumps(task_summary, ensure_ascii=False, indent=2),
                    metadata={"campaign_id": _text(campaign_view.get("campaign_id"))},
                )
            )
        for event in _list_of_mapping(payload.get("campaign_events"))[:8]:
            body = {
                "event_type": _text(event.get("event_type")),
                "phase": _text(event.get("phase")),
                "iteration": _coerce_int(event.get("iteration")),
                "payload": _mapping(event.get("payload")),
            }
            items.append(
                RecordListItem(
                    record_id=_text(event.get("event_id") or f"event_{uuid4().hex[:8]}"),
                    title=_text(event.get("event_type") or "campaign_event"),
                    kind="event",
                    created_at=_text(event.get("created_at")),
                    summary=_text(event.get("phase") or event.get("event_type")),
                    preview_kind="json",
                    preview_title=_text(event.get("event_type") or "campaign_event"),
                    preview_language="json",
                    preview_content=json.dumps(body, ensure_ascii=False, indent=2),
                    metadata={"campaign_id": _text(campaign_view.get("campaign_id"))},
                )
            )
        return items

    def _graph_snapshot_from_payload(self, payload: Mapping[str, Any]) -> GraphSnapshot:
        campaign_view = _mapping(payload.get("campaign_view"))
        session_view = _mapping(payload.get("session_view"))
        workflow_session = _mapping(payload.get("workflow_session"))
        projection = self._project_campaign_runtime(payload)
        step_ids = [item.id for item in projection["nodes"]]
        nodes = [
            GraphNodeView(
                id=item.id,
                kind="campaign_surface_node",
                title=item.display_title or item.title,
                status="active" if item.status == "running" else item.status,
                phase=item.phase,
                role_id=item.role_id,
                artifact_refs=list(item.artifact_refs or []),
                badges=list(item.badges or []),
                action_state=GraphNodeActionState(
                    can_retry=item.id == "turn" and _text(campaign_view.get("status")) in {"running", "paused", "waiting"},
                    can_reroute=False,
                ),
            )
            for item in projection["nodes"]
        ]
        edges = [
            GraphEdgeView(
                id=item.id,
                source=item.source,
                target=item.target,
                kind=item.kind,
                condition=item.label or item.kind,
                active=bool(item.active),
            )
            for item in projection["edges"]
        ]
        active_path = [item.id for item in projection["nodes"] if item.status in {"completed", "running", "paused"}]
        revision_id = _text(payload.get("updated_at") or workflow_session.get("updated_at") or campaign_view.get("campaign_id")) or f"snapshot_{uuid4().hex[:10]}"
        return GraphSnapshot(
            graph_level="campaign",
            revision_id=revision_id,
            campaign_id=_text(campaign_view.get("campaign_id") or payload.get("campaign_id")),
            workflow_id=_text(campaign_view.get("workflow_id") or payload.get("branch_id")),
            workflow_session_id=_text(session_view.get("workflow_session_id") or workflow_session.get("session_id")),
            phase_path=step_ids,
            active_path=active_path,
            nodes=nodes,
            edges=edges,
            inspector_defaults={"selected_node_id": projection["active_step"] or (step_ids[0] if step_ids else "")},
            available_actions=self._available_operator_actions(payload),
            metadata={
                "campaign_view": campaign_view,
                "task_summary": _mapping(payload.get("task_summary")),
                "governance_summary": _mapping(payload.get("governance_summary")),
            },
        )

    def _iter_drafts(self, workspace: str) -> list[CampaignNegotiationDraft]:
        root = Path(resolve_orchestrator_root(workspace)) / "negotiations" / "campaign"
        if not root.exists():
            return []
        items: list[tuple[float, CampaignNegotiationDraft]] = []
        for path in root.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            draft = CampaignNegotiationDraft.from_dict(data)
            items.append((path.stat().st_mtime, draft))
        items.sort(key=lambda item: item[0], reverse=True)
        return [draft for _, draft in items]

    def _require_draft(self, workspace: str, draft_id: str) -> CampaignNegotiationDraft:
        target = _text(draft_id)
        for draft in self._iter_drafts(workspace):
            if draft.draft_id == target:
                return draft
        raise KeyError(f"draft not found: {target}")

    def _assert_mutations_allowed(self, workspace: str, *, stale_seconds: int = 120) -> None:
        runtime = self.get_runtime_status(workspace, stale_seconds=stale_seconds)
        if _text(runtime.get("process_state")).lower() == "stale":
            raise RuntimeError("runtime is stale; mutating actions are blocked")

    @staticmethod
    def _draft_view_from_draft(draft: CampaignNegotiationDraft) -> FrontdoorDraftView:
        mode_id = _text(draft.frontdoor_mode_id or ("plan" if draft.status == "planned" else draft.task_mode or "delivery")).lower() or "delivery"
        return FrontdoorDraftView(
            draft_id=draft.draft_id,
            session_id=draft.session_id,
            mode_id=mode_id,
            goal=_text(draft.goal),
            materials=list(draft.materials),
            hard_constraints=list(draft.hard_constraints),
            acceptance_criteria=list(draft.acceptance_criteria),
            recommended_template_id=_text(draft.recommended_template_id),
            selected_template_id=_text(draft.selected_template_id),
            composition_mode=_text(draft.composition_mode or "template"),
            skill_selection=normalize_skill_exposure_payload(
                dict(draft.skill_selection) if isinstance(draft.skill_selection, Mapping) else None,
                provider_skill_source="butler",
            ) or {},
            pending_confirmation=bool(draft.pending_confirmation),
            linked_campaign_id=_text(draft.started_campaign_id),
            frontdoor_ref={"channel": "", "thread_id": draft.session_id, "session_id": draft.session_id},
            governance_defaults={"risk_level": "medium", "autonomy_profile": "reviewed_delivery"},
            metadata={
                "status": draft.status,
                "background_reason": draft.background_reason,
                "startup_mode": draft.startup_mode,
                "minimal_correctness_checks": list(draft.minimal_correctness_checks),
                "confirmed_correctness_checks": list(draft.confirmed_correctness_checks),
            },
        )

    @staticmethod
    def _campaign_display_title(value: str) -> str:
        text = _clip_text(value, limit=36)
        return text or "Untitled campaign"

    @staticmethod
    def _step_display_title(step_id: str) -> str:
        labels = {
            "ledger": "Campaign Ledger",
            "turn": "Supervisor Turn",
            "delivery": "Deliverables",
            "harness": "Harness Recovery",
            "discover": "Discovery Brief",
            "implement": "Execution Pass",
            "evaluate": "Reviewer Check",
            "iterate": "Recovery Loop",
        }
        return labels.get(_text(step_id), _title_from_step_id(step_id))

    @staticmethod
    def _role_label(role_id: str) -> str:
        labels = {
            "campaign_ledger": "Ledger",
            "campaign_harness": "Harness",
            "campaign_supervisor": "Supervisor",
            "campaign_reviewer": "Reviewer",
        }
        return labels.get(_text(role_id), _title_from_step_id(role_id))

    @staticmethod
    def _iteration_label(payload: Mapping[str, Any] | None) -> str:
        current_iteration = _coerce_int(_mapping(payload).get("current_iteration"))
        if current_iteration <= 0:
            return ""
        return f"Iteration {current_iteration}"

    @staticmethod
    def _node_primary_badge(node_status: str) -> str:
        mapping = {
            "running": "Running",
            "next": "Up Next",
            "queued": "Queued",
            "pending": "Pending",
            "paused": "Paused",
            "completed": "Completed",
            "failed": "Failed",
            "blocked": "Blocked",
        }
        return mapping.get(_text(node_status), _title_from_step_id(node_status))

    @staticmethod
    def _node_secondary_badge(step_id: str, artifact_refs: list[str]) -> str:
        artifact_count = len(artifact_refs or [])
        if artifact_count > 0:
            return f"{artifact_count} outputs"
        return _title_from_step_id(step_id)

    def _step_display_brief(self, payload: Mapping[str, Any], *, step_id: str, node_status: str) -> str:
        task_summary = _mapping(payload.get("task_summary"))
        progress = _mapping(task_summary.get("progress"))
        output = _mapping(task_summary.get("output"))
        closure = _mapping(task_summary.get("closure"))
        working_contract = _mapping(payload.get("working_contract"))
        latest_verdict = _mapping(payload.get("latest_verdict") or _mapping(payload.get("evaluation_summary")).get("latest_verdict"))
        latest_turn_receipt = _mapping(payload.get("latest_turn_receipt"))
        session_evidence = _mapping(payload.get("session_evidence"))
        pending_checks = _list_of_text(_mapping(payload.get("phase_runtime")).get("pending_checks") or payload.get("pending_checks"))
        if step_id == "ledger":
            return _clip_text(
                progress.get("latest_summary")
                or latest_turn_receipt.get("summary")
                or _mapping(task_summary.get("spec")).get("goal")
                or working_contract.get("working_goal"),
                limit=96,
            )
        if step_id == "turn":
            return _clip_text(
                task_summary.get("next_action")
                or progress.get("latest_next_action")
                or latest_turn_receipt.get("next_action")
                or working_contract.get("working_goal"),
                limit=96,
            )
        if step_id == "delivery":
            delivery_refs = _list_of_text(output.get("latest_delivery_refs") or latest_turn_receipt.get("delivery_refs"))
            if delivery_refs:
                return _clip_text(f"{len(delivery_refs)} delivery refs ready for handoff", limit=96)
            return _clip_text(output.get("bundle_root") or "No delivery refs have been committed yet.", limit=96)
        if step_id == "harness":
            return _clip_text(
                latest_turn_receipt.get("yield_reason")
                or f"{_coerce_int(session_evidence.get('session_event_count'))} session events · {_coerce_int(output.get('artifact_count') or session_evidence.get('artifact_count'))} artifacts"
                or closure.get("state"),
                limit=96,
            )
        if step_id == "implement":
            if node_status == "running":
                return _clip_text(task_summary.get("next_action") or working_contract.get("working_goal"), limit=96)
            return _clip_text(latest_verdict.get("next_iteration_goal") or task_summary.get("next_action"), limit=96)
        if step_id == "evaluate":
            return _clip_text(latest_verdict.get("rationale") or "Review the latest outputs and decide whether to converge or recover.", limit=96)
        if step_id == "iterate":
            if pending_checks:
                return _clip_text(f"Close correctness checks: {', '.join(pending_checks[:3])}", limit=96)
            return _clip_text(working_contract.get("working_goal") or task_summary.get("next_action"), limit=96)
        return _clip_text(working_contract.get("working_goal") or task_summary.get("next_action"), limit=96)

    def _global_node_brief(self, projection: Mapping[str, Any]) -> str:
        current_agent = projection.get("current_agent")
        next_agent = projection.get("next_agent")
        if isinstance(current_agent, AgentExecutionView) and current_agent.summary:
            return _clip_text(current_agent.summary, limit=96)
        if isinstance(next_agent, AgentExecutionView) and next_agent.summary:
            return _clip_text(next_agent.summary, limit=96)
        return _clip_text(_mapping(projection.get("campaign_view")).get("title"), limit=96)

    def _project_timeline_items(
        self,
        payload: Mapping[str, Any],
        *,
        current_agent: AgentExecutionView | None,
        next_agent: AgentExecutionView | None,
        queued_agents: list[AgentExecutionView],
    ) -> list[TimelineItem]:
        campaign_view = _mapping(payload.get("campaign_view"))
        campaign_id = _text(campaign_view.get("campaign_id"))
        items: list[TimelineItem] = []
        latest_turn_receipt = _mapping(payload.get("latest_turn_receipt"))
        if latest_turn_receipt:
            created_at = _text(latest_turn_receipt.get("created_at")) or _text(campaign_view.get("updated_at"))
            items.append(
                TimelineItem(
                    id=_text(latest_turn_receipt.get("turn_id") or f"{campaign_id}:turn"),
                    kind="turn_receipt",
                    timestamp=created_at,
                    anchor_timestamp=created_at,
                    display_time=_display_time_cn(created_at),
                    display_title=_clip_text(latest_turn_receipt.get("summary") or "Supervisor turn", limit=28),
                    display_brief=_clip_text(latest_turn_receipt.get("next_action") or latest_turn_receipt.get("yield_reason"), limit=92),
                    campaign_id=campaign_id,
                    node_id="turn",
                    step_id="turn",
                    status=_text(latest_turn_receipt.get("macro_state") or campaign_view.get("status")),
                    is_future=False,
                    detail_available=bool(campaign_id),
                    detail_campaign_id=campaign_id,
                    detail_node_id="turn",
                    detail_payload=latest_turn_receipt,
                )
            )
        for event in _list_of_mapping(payload.get("campaign_events")):
            envelope = self._event_envelope_from_payload(campaign_id, event)
            phase = _text(envelope.payload.get("phase"))
            items.append(
                TimelineItem(
                    id=envelope.event_id,
                    kind="event",
                    timestamp=envelope.created_at,
                    anchor_timestamp=envelope.created_at,
                    display_time=_display_time_cn(envelope.created_at),
                    display_title=_clip_text(self._timeline_event_title(envelope), limit=28),
                    display_brief=_clip_text(self._timeline_event_brief(envelope), limit=92),
                    campaign_id=campaign_id,
                    node_id=phase,
                    step_id=phase,
                    status=envelope.severity,
                    is_future=False,
                    detail_available=bool(campaign_id and phase),
                    detail_campaign_id=campaign_id,
                    detail_node_id=phase,
                    detail_payload=envelope.to_dict(),
                )
            )
        anchor = self._latest_timestamp_from_items(items) or _parse_datetime(campaign_view.get("updated_at")) or datetime.now(UTC)
        future_offset = 1
        for agent, kind in (
            (current_agent, "running"),
            (next_agent, "next"),
            *((agent, "queued") for agent in queued_agents),
        ):
            if not isinstance(agent, AgentExecutionView):
                continue
            if kind == "running":
                timestamp = anchor
                is_future = False
            else:
                timestamp = anchor + timedelta(minutes=5 * future_offset)
                future_offset += 1
                is_future = True
            items.append(
                TimelineItem(
                    id=f"{campaign_id}:{agent.step_id}:{kind}",
                    kind=kind,
                    timestamp=timestamp.isoformat(),
                    anchor_timestamp=timestamp.isoformat(),
                    display_time=_display_time_cn(timestamp.isoformat()),
                    display_title=_clip_text(agent.title or agent.step_id, limit=28),
                    display_brief=_clip_text(agent.summary or agent.phase, limit=92),
                    campaign_id=campaign_id,
                    node_id=agent.step_id,
                    step_id=agent.step_id,
                    status=kind,
                    is_future=is_future,
                    detail_available=bool(campaign_id and agent.step_id),
                    detail_campaign_id=campaign_id,
                    detail_node_id=agent.step_id,
                    detail_payload=agent.to_dict(),
                )
            )
        items.sort(key=lambda item: (_text(item.timestamp), item.id))
        return items

    def _global_timeline_items(self, *, runtime: Mapping[str, Any], projections: list[dict[str, Any]]) -> list[TimelineItem]:
        items: list[TimelineItem] = []
        runtime_timestamp = _text(runtime.get("updated_at")) or _utc_now_iso()
        items.append(
            TimelineItem(
                id="runtime",
                kind="runtime",
                timestamp=runtime_timestamp,
                anchor_timestamp=runtime_timestamp,
                display_time=_display_time_cn(runtime_timestamp),
                display_title="Runtime Snapshot",
                display_brief=_clip_text(runtime.get("note"), limit=92),
                status=_text(runtime.get("phase") or runtime.get("run_state")),
                is_future=False,
                detail_payload={"runtime": dict(runtime)},
            )
        )
        anchor = _parse_datetime(runtime_timestamp) or datetime.now(UTC)
        future_offset = 1
        for projection in projections:
            campaign_view = _mapping(projection.get("campaign_view"))
            campaign_id = _text(campaign_view.get("campaign_id"))
            current_agent = projection.get("current_agent")
            next_agent = projection.get("next_agent")
            queued_agents = list(projection.get("queued_agents") or [])
            if isinstance(current_agent, AgentExecutionView):
                items.append(
                    TimelineItem(
                        id=f"{campaign_id}:{current_agent.step_id}:running",
                        kind="running",
                        timestamp=runtime_timestamp,
                        anchor_timestamp=runtime_timestamp,
                        display_time=_display_time_cn(runtime_timestamp),
                        display_title=self._campaign_display_title(_text(campaign_view.get("title") or campaign_id)),
                        display_brief=_clip_text(current_agent.summary or current_agent.phase, limit=92),
                        campaign_id=campaign_id,
                        node_id=f"campaign:{campaign_id}",
                        step_id=current_agent.step_id,
                        status="running",
                        is_future=False,
                        detail_available=bool(campaign_id and current_agent.step_id),
                        detail_campaign_id=campaign_id,
                        detail_node_id=current_agent.step_id,
                        detail_payload=current_agent.to_dict(),
                    )
                )
            if isinstance(next_agent, AgentExecutionView):
                future_timestamp = (anchor + timedelta(minutes=5 * future_offset)).isoformat()
                future_offset += 1
                items.append(
                    TimelineItem(
                        id=f"{campaign_id}:{next_agent.step_id}:next",
                        kind="next",
                        timestamp=future_timestamp,
                        anchor_timestamp=future_timestamp,
                        display_time=_display_time_cn(future_timestamp),
                        display_title=self._campaign_display_title(_text(campaign_view.get("title") or campaign_id)),
                        display_brief=_clip_text(next_agent.summary or next_agent.phase, limit=92),
                        campaign_id=campaign_id,
                        node_id=f"campaign:{campaign_id}",
                        step_id=next_agent.step_id,
                        status="next",
                        is_future=True,
                        detail_available=bool(campaign_id and next_agent.step_id),
                        detail_campaign_id=campaign_id,
                        detail_node_id=next_agent.step_id,
                        detail_payload=next_agent.to_dict(),
                    )
                )
            for queued_agent in queued_agents[:3]:
                if not isinstance(queued_agent, AgentExecutionView):
                    continue
                future_timestamp = (anchor + timedelta(minutes=5 * future_offset)).isoformat()
                future_offset += 1
                items.append(
                    TimelineItem(
                        id=f"{campaign_id}:{queued_agent.step_id}:queued",
                        kind="queued",
                        timestamp=future_timestamp,
                        anchor_timestamp=future_timestamp,
                        display_time=_display_time_cn(future_timestamp),
                        display_title=self._campaign_display_title(_text(campaign_view.get("title") or campaign_id)),
                        display_brief=_clip_text(queued_agent.summary or queued_agent.phase, limit=92),
                        campaign_id=campaign_id,
                        node_id=f"campaign:{campaign_id}",
                        step_id=queued_agent.step_id,
                        status="queued",
                        is_future=True,
                        detail_available=bool(campaign_id and queued_agent.step_id),
                        detail_campaign_id=campaign_id,
                        detail_node_id=queued_agent.step_id,
                        detail_payload=queued_agent.to_dict(),
                    )
                )
        items.sort(key=lambda item: (_text(item.timestamp), item.id))
        return items

    @staticmethod
    def _latest_timestamp_from_items(items: list[TimelineItem]) -> datetime | None:
        parsed = [_parse_datetime(item.timestamp) for item in items]
        values = [item for item in parsed if item is not None]
        if not values:
            return None
        return max(values)

    @staticmethod
    def _timeline_bounds(items: list[TimelineItem]) -> dict[str, Any]:
        parsed = [_parse_datetime(item.anchor_timestamp or item.timestamp) for item in items]
        values = [item for item in parsed if item is not None]
        if not values:
            return {
                "timezone": "+08:00",
                "min_timestamp": "",
                "max_timestamp": "",
                "default_anchor_timestamp": "",
                "stage_width": TIMELINE_MIN_STAGE_WIDTH,
                "card_width": TIMELINE_CARD_WIDTH,
                "card_gap": TIMELINE_CARD_GAP,
            }
        return {
            "timezone": "+08:00",
            "min_timestamp": min(values).isoformat(),
            "max_timestamp": max(values).isoformat(),
            "default_anchor_timestamp": max(values).isoformat(),
            "stage_width": max(
                TIMELINE_MIN_STAGE_WIDTH,
                max((float(item.layout_x or 0.0) + TIMELINE_CARD_WIDTH + TIMELINE_STAGE_PADDING) for item in items),
            ),
            "card_width": TIMELINE_CARD_WIDTH,
            "card_gap": TIMELINE_CARD_GAP,
        }

    @staticmethod
    def _detail_execution_state(node_status: Any) -> str:
        status = _text(node_status).lower()
        if status in {"running", "current", "active"}:
            return "running"
        if status in {"completed", "done", "succeeded"}:
            return "completed"
        if status in {"next", "queued", "pending", "waiting", "paused", "blocked"}:
            return "pending"
        return "idle_unknown"

    @staticmethod
    def _layout_timeline_items(items: list[TimelineItem]) -> list[TimelineItem]:
        if not items:
            return []
        ordered = sorted(items, key=lambda item: (_text(item.anchor_timestamp or item.timestamp), item.id))
        timestamps = [_parse_datetime(item.anchor_timestamp or item.timestamp) for item in ordered]
        valid = [value for value in timestamps if value is not None]
        if not valid:
            laid_out: list[TimelineItem] = []
            cursor = TIMELINE_STAGE_PADDING
            for item in ordered:
                laid_out.append(replace(item, anchor_x=cursor + TIMELINE_CARD_WIDTH / 2.0, layout_x=cursor))
                cursor += TIMELINE_CARD_WIDTH + TIMELINE_CARD_GAP
            return laid_out

        min_ts = min(valid)
        max_ts = max(valid)
        span_ms = max(1.0, (max_ts - min_ts).total_seconds() * 1000.0)
        base_width = max(
            TIMELINE_MIN_STAGE_WIDTH,
            TIMELINE_STAGE_PADDING * 2.0 + (len(ordered) * (TIMELINE_CARD_WIDTH + TIMELINE_CARD_GAP)),
        )
        lane_width = max(1.0, base_width - TIMELINE_STAGE_PADDING * 2.0)
        laid_out = []
        previous_right = TIMELINE_STAGE_PADDING - TIMELINE_CARD_GAP
        for index, item in enumerate(ordered):
            parsed = timestamps[index]
            if parsed is None:
                anchor_x = TIMELINE_STAGE_PADDING + (index / max(1, len(ordered) - 1)) * lane_width
            else:
                ratio = ((parsed - min_ts).total_seconds() * 1000.0) / span_ms
                anchor_x = TIMELINE_STAGE_PADDING + ratio * lane_width
            ideal_left = anchor_x - TIMELINE_CARD_WIDTH / 2.0
            layout_x = max(TIMELINE_STAGE_PADDING, ideal_left, previous_right + TIMELINE_CARD_GAP)
            previous_right = layout_x + TIMELINE_CARD_WIDTH
            laid_out.append(replace(item, anchor_x=round(anchor_x, 2), layout_x=round(layout_x, 2)))
        return laid_out

    @staticmethod
    def _timeline_event_title(event: ConsoleEventEnvelope) -> str:
        event_type = _text(event.event_type)
        labels = {
            "artifact_recorded": "Artifact Added",
            "codex_runtime_completed": "Codex Finished",
            "implement_completed": "Implement Done",
            "evaluate_completed": "Review Done",
            "working_contract_rewritten": "Contract Rewritten",
            "campaign_recovery_scheduled": "Recovery Scheduled",
            "campaign_created": "Campaign Created",
            "discover_completed": "Discovery Done",
        }
        return labels.get(event_type, _title_from_step_id(event_type))

    @staticmethod
    def _timeline_event_brief(event: ConsoleEventEnvelope) -> str:
        payload = _mapping(event.payload)
        for key in ("label", "reason", "decision", "phase", "artifact_id", "verdict_id"):
            value = payload.get(key)
            if _text(value):
                return _text(value)
        return _text(event.event_type)

    def _detail_live_records(self, payload: Mapping[str, Any], *, node_id: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for event in _list_of_mapping(payload.get("campaign_events")):
            if not self._record_matches_node(event, node_id=node_id):
                continue
            records.append(
                {
                    "kind": "campaign_event",
                    "title": _text(event.get("event_type") or "campaign_event"),
                    "created_at": _text(event.get("created_at")),
                    "summary": _text(event.get("phase") or _mapping(event.get("payload")).get("reason") or event.get("event_type")),
                    "payload": dict(event),
                }
            )
        workflow_session = _mapping(payload.get("workflow_session"))
        for event in _list_of_mapping(workflow_session.get("events")):
            if not self._record_matches_node(event, node_id=node_id):
                continue
            records.append(
                {
                    "kind": "session_event",
                    "title": _text(event.get("event_type") or event.get("kind") or "session_event"),
                    "created_at": _text(event.get("created_at") or event.get("timestamp")),
                    "summary": _text(event.get("message") or event.get("text") or event.get("event_type") or event.get("kind")),
                    "payload": dict(event),
                }
            )
        blackboard = _mapping(workflow_session.get("blackboard"))
        for entry in _list_of_mapping(blackboard.get("entries")):
            if not self._record_matches_node(entry, node_id=node_id):
                continue
            records.append(
                {
                    "kind": "blackboard_entry",
                    "title": _text(entry.get("title") or entry.get("key") or "blackboard_entry"),
                    "created_at": _text(entry.get("created_at") or entry.get("updated_at")),
                    "summary": _text(entry.get("value") or entry.get("summary") or entry.get("text")),
                    "payload": dict(entry),
                }
            )
        records.sort(key=lambda item: (_text(item.get("created_at")), _text(item.get("title"))))
        return records

    def _detail_raw_records(self, payload: Mapping[str, Any], *, node_id: str) -> list[dict[str, Any]]:
        raw: list[dict[str, Any]] = []
        workflow_session = _mapping(payload.get("workflow_session"))
        for source_name, items in (
            ("campaign_event", _list_of_mapping(payload.get("campaign_events"))),
            ("workflow_event", _list_of_mapping(workflow_session.get("events"))),
            ("blackboard_entry", _list_of_mapping(_mapping(workflow_session.get("blackboard")).get("entries"))),
        ):
            for item in items:
                if not self._record_matches_node(item, node_id=node_id):
                    continue
                raw.append({"title": source_name, **dict(item)})
        raw.sort(key=lambda item: (_text(item.get("created_at") or item.get("updated_at") or item.get("timestamp")), _text(item.get("title"))))
        return raw

    @staticmethod
    def _record_matches_node(record: Mapping[str, Any], *, node_id: str) -> bool:
        target = _text(node_id)
        if not target:
            return False
        if target == "turn":
            return True
        payload = _mapping(record.get("payload"))
        candidates = {
            _text(record.get("phase")),
            _text(record.get("step_id")),
            _text(record.get("active_step")),
            _text(record.get("producer_step_id")),
            _text(record.get("node_id")),
            _text(record.get("key")),
            _text(payload.get("phase")),
            _text(payload.get("step_id")),
            _text(payload.get("active_step")),
            _text(payload.get("producer_step_id")),
            _text(payload.get("node_id")),
        }
        return target in candidates

    @staticmethod
    def _event_envelope_from_payload(campaign_id: str, payload: Mapping[str, Any]) -> ConsoleEventEnvelope:
        event_type = _text(payload.get("event_type")) or "campaign_event"
        severity = "info"
        if event_type.endswith("failed"):
            severity = "error"
        elif "approval" in event_type or event_type.endswith("blocked"):
            severity = "warning"
        body = _mapping(payload.get("payload"))
        phase = _text(payload.get("phase"))
        iteration = int(payload.get("iteration") or 0)
        if phase:
            body.setdefault("phase", phase)
        if iteration > 0:
            body.setdefault("iteration", iteration)
        body.setdefault("campaign_id", campaign_id)
        return ConsoleEventEnvelope(
            scope="campaign",
            scope_id=_text(campaign_id),
            event_id=_text(payload.get("event_id")) or f"console_event_{uuid4().hex[:12]}",
            event_type=event_type,
            created_at=_text(payload.get("created_at")) or _utc_now_iso(),
            severity=severity,
            payload=body,
        )

    @staticmethod
    def _role_for_step(step_id: str) -> str:
        normalized = _text(step_id)
        if normalized == "evaluate":
            return "campaign_reviewer"
        if normalized == "ledger":
            return "campaign_ledger"
        if normalized == "harness":
            return "campaign_harness"
        return "campaign_supervisor"

    def _role_bindings_by_role_id(self, workflow_session: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        bindings: dict[str, dict[str, Any]] = {}
        for item in workflow_session.get("role_bindings") or []:
            if not isinstance(item, Mapping):
                continue
            role_id = _text(item.get("role_id"))
            if role_id:
                bindings[role_id] = dict(item)
        return bindings

    def _agent_for_step(
        self,
        *,
        campaign_view: Mapping[str, Any],
        role_bindings: dict[str, dict[str, Any]],
        step_id: str,
        status: str,
        queue_state: str,
        source: str,
        summary: str,
    ) -> AgentExecutionView:
        role_id = self._role_for_step(step_id)
        binding = role_bindings.get(role_id, {})
        title = f"{_title_from_step_id(step_id)}"
        return AgentExecutionView(
            id=f"{_text(campaign_view.get('campaign_id'))}:{step_id}:{queue_state}",
            title=title,
            role_id=role_id,
            agent_spec_id=_text(binding.get("agent_spec_id")),
            status=status,
            queue_state=queue_state,
            phase=step_id,
            step_id=step_id,
            source=source,
            summary=summary,
            badges=[f"campaign:{_text(campaign_view.get('campaign_id'))}", f"source:{source}"],
            metadata={"campaign_id": _text(campaign_view.get("campaign_id")), "campaign_title": _text(campaign_view.get("title"))},
        )

    def _agent_summary(self, payload: Mapping[str, Any], step_id: str) -> str:
        campaign_view = _mapping(payload.get("campaign_view"))
        task_summary = _mapping(payload.get("task_summary"))
        progress = _mapping(task_summary.get("progress"))
        latest_turn_receipt = _mapping(payload.get("latest_turn_receipt"))
        if step_id == "turn":
            return _clip_text(task_summary.get("next_action") or progress.get("latest_summary") or latest_turn_receipt.get("summary"), limit=120)
        if step_id == "delivery":
            refs = _list_of_text(_mapping(task_summary.get("output")).get("latest_delivery_refs") or latest_turn_receipt.get("delivery_refs"))
            return f"{len(refs)} delivery refs" if refs else "waiting for committed delivery refs"
        if step_id == "harness":
            return _clip_text(latest_turn_receipt.get("yield_reason") or "keep session, artifacts, and recovery anchors durable", limit=120)
        if step_id == "ledger":
            return _clip_text(progress.get("latest_summary") or _mapping(task_summary.get("spec")).get("goal"), limit=120)
        return f"{_text(campaign_view.get('title') or campaign_view.get('campaign_id'))} · {_title_from_step_id(step_id)}"

    @staticmethod
    def _next_step_id(step_ids: list[str], *, active_step: str, next_phase: str) -> str:
        if active_step and active_step in step_ids:
            index = step_ids.index(active_step)
            if index + 1 < len(step_ids):
                return step_ids[index + 1]
            return ""
        if next_phase and next_phase in step_ids:
            return next_phase
        return ""

    @staticmethod
    def _best_effort_preview_text(payload: Mapping[str, Any]) -> str:
        for key in ("output_text", "report", "summary", "working_goal", "execution_summary"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return json.dumps(dict(payload), ensure_ascii=False, indent=2)

    def _find_artifact(self, workspace: str, campaign_id: str, artifact_id: str) -> dict[str, Any]:
        target = _text(artifact_id)
        for item in self._query_service.list_campaign_artifacts(workspace, campaign_id):
            candidate = _text(item.get("artifact_id") or item.get("ref"))
            ref = _text(item.get("ref"))
            if target in {candidate, ref, Path(ref).name}:
                return dict(item)
        raise KeyError(f"artifact not found: {target}")

    def _campaign_root(self, workspace: str, campaign_id: str) -> Path:
        return Path(resolve_orchestrator_root(workspace)) / "campaigns" / _text(campaign_id)

    def _global_node_subtitle(self, projection: Mapping[str, Any]) -> str:
        current_agent = projection.get("current_agent")
        next_agent = projection.get("next_agent")
        campaign_view = _mapping(projection.get("campaign_view"))
        if isinstance(current_agent, AgentExecutionView):
            return f"running · {current_agent.phase} · {current_agent.role_id}"
        if isinstance(next_agent, AgentExecutionView):
            return f"next · {next_agent.phase} · {next_agent.role_id}"
        return f"{_text(campaign_view.get('status') or 'unknown')} · idle"

    @staticmethod
    def _lan_ipv4_addresses() -> list[str]:
        addresses: set[str] = set()
        try:
            host_info = socket.gethostbyname_ex(socket.gethostname())
            for item in host_info[2]:
                if item and not item.startswith("127."):
                    addresses.add(item)
        except Exception:
            pass
        try:
            for family, _, _, _, sockaddr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                if family == socket.AF_INET:
                    address = _text((sockaddr or [""])[0])
                    if address and not address.startswith("127."):
                        addresses.add(address)
        except Exception:
            pass
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.connect(("8.8.8.8", 80))
                address = _text(sock.getsockname()[0])
                if address and not address.startswith("127."):
                    addresses.add(address)
            finally:
                sock.close()
        except Exception:
            pass
        return sorted(addresses)


class ConsoleControlService:
    """Apply console control actions through existing orchestrator/query services."""

    def __init__(
        self,
        *,
        query_service: OrchestratorQueryService | None = None,
        campaign_service: OrchestratorCampaignService | None = None,
    ) -> None:
        self._campaign_service = campaign_service or OrchestratorCampaignService()
        self._query_service = query_service or OrchestratorQueryService(campaign_service=self._campaign_service)

    def apply(self, workspace: str, request: ControlActionRequest) -> ControlActionResult:
        campaign_id = _text(request.target_id)
        runtime = self._query_service.get_runtime_status(workspace, stale_seconds=120)
        if _text(runtime.get("process_state")).lower() == "stale":
            return self._blocked_result(campaign_id, "", "runtime is stale; mutating actions are blocked")
        payload = self._query_service.get_campaign_status(workspace, campaign_id)
        mission_id = _text(payload.get("mission_id") or _mapping(payload.get("campaign_view")).get("mission_id"))
        action = _text(request.action).lower()
        request_payload = _merge_nested(_mapping(request.payload), {
            "transition_to": request.transition_to,
            "resume_from": request.resume_from,
            "check_ids": list(request.check_ids),
            "feedback": request.feedback if _text(request.feedback) else _mapping(request.payload).get("feedback"),
            "prompt_patch": _mapping(request.prompt_patch),
            "workflow_patch": _mapping(request.workflow_patch),
            "target_scope": request.target_scope,
            "target_node_id": request.target_node_id,
        })
        operator_reason = _text(request.operator_reason or request.reason or request_payload.get("reason"))
        policy_source = _text(request.policy_source or request_payload.get("policy_source") or "console.action")
        target_scope = _text(request.target_scope or request_payload.get("target_scope") or "campaign")
        target_node_id = _text(request.target_node_id or request_payload.get("target_node_id"))
        before_summary = self._control_state_summary(payload)
        result_summary = ""
        recovery_payload: dict[str, Any] | None = None
        skip_followup_audit = False
        if action == "pause":
            if mission_id:
                self._query_service.control_mission(workspace, mission_id, "pause")
            else:
                self._campaign_service.apply_operator_patch(
                    workspace,
                    campaign_id,
                    status="paused",
                    reason=operator_reason or "pause campaign",
                )
            result_summary = "paused"
        elif action == "resume":
            self._campaign_service.apply_operator_patch(
                workspace,
                campaign_id,
                status="running",
                reason=operator_reason or "resume campaign",
            )
            result_summary = "resumed"
        elif action == "abort":
            self._campaign_service.apply_operator_patch(
                workspace,
                campaign_id,
                status="cancelled",
                reason=operator_reason or "abort campaign",
            )
            result_summary = "aborted"
        elif action == "append_feedback":
            feedback = _text(request_payload.get("feedback") or request.reason)
            if not feedback:
                return self._blocked_result(campaign_id, mission_id, "append_feedback blocked: missing feedback")
            if mission_id:
                self._query_service.append_user_feedback(workspace, mission_id, feedback)
            else:
                self._campaign_service.append_campaign_feedback(workspace, campaign_id, feedback)
            result_summary = "feedback appended"
        elif action == "annotate_governance":
            governance_patch = {
                key: value
                for key, value in {
                    "risk_level": request_payload.get("risk_level"),
                    "autonomy_profile": request_payload.get("autonomy_profile"),
                    "approval_state": request_payload.get("approval_state"),
                }.items()
                if _text(value)
            }
            note = _text(request_payload.get("note") or operator_reason)
            metadata_patch: dict[str, Any] = {}
            if governance_patch:
                metadata_patch["governance_contract"] = governance_patch
            if note:
                metadata_patch["operator_governance_annotation"] = {
                    "note": note,
                    "updated_at": _utc_now_iso(),
                }
            if not metadata_patch:
                return self._blocked_result(campaign_id, mission_id, "annotate_governance blocked: missing governance patch")
            self._campaign_service.update_campaign_metadata(workspace, campaign_id, metadata_patch)
            result_summary = "governance annotated"
        elif action == "request_approval":
            self._campaign_service.update_campaign_metadata(
                workspace,
                campaign_id,
                {"governance_contract": {"approval_state": "requested"}},
            )
            result_summary = "approval requested"
        elif action == "resolve_approval":
            state = _text(_mapping(request.payload).get("approval_state") or "resolved").lower() or "resolved"
            self._campaign_service.update_campaign_metadata(
                workspace,
                campaign_id,
                {"governance_contract": {"approval_state": state}},
            )
            result_summary = f"approval {state}"
        elif action in {"resolve_checks", "waive_checks"}:
            metadata = _mapping(payload.get("metadata"))
            pending = _list_of_text(metadata.get("pending_correctness_checks"))
            resolved = _list_of_text(metadata.get("resolved_correctness_checks"))
            waived = _list_of_text(metadata.get("waived_correctness_checks"))
            target_checks = _list_of_text(request_payload.get("check_ids")) or _list_of_text(payload.get("operational_checks_pending")) or _list_of_text(payload.get("closure_checks_pending"))
            if not target_checks:
                return self._blocked_result(campaign_id, mission_id, f"{action} blocked: missing check_ids")
            pending = [item for item in pending if item not in set(target_checks)]
            if action == "resolve_checks":
                resolved = _list_of_text(resolved + target_checks)
                result_summary = f"resolved {len(target_checks)} checks"
            else:
                waived = _list_of_text(waived + target_checks)
                result_summary = f"waived {len(target_checks)} checks"
            self._campaign_service.update_campaign_metadata(
                workspace,
                campaign_id,
                {
                    "pending_correctness_checks": pending,
                    "resolved_correctness_checks": resolved,
                    "waived_correctness_checks": waived,
                },
            )
        elif action in {"force_recover_from_snapshot", "recover", "retry_step", "skip_to_step", "force_transition"}:
            transition_to = _text(request_payload.get("transition_to") or request_payload.get("resume_from") or target_node_id or "snapshot")
            self._campaign_service.apply_operator_patch(
                workspace,
                campaign_id,
                status="running",
                metadata_patch={
                    "operator_runtime_overrides": {
                        "last_action": "force_recover_from_snapshot" if action == "force_transition" else action,
                        "resume_from": transition_to,
                        "target_node_id": target_node_id or "turn",
                    }
                },
                reason=operator_reason or action,
            )
            result_summary = "recovery requested"
            recovery_payload = {
                "resume_from": transition_to,
                "recovery_candidate_id": _text(request_payload.get("recovery_candidate_id") or f"force_recover_from_snapshot:{transition_to}"),
                "decision_summary": result_summary,
                "result_state": "running",
            }
        elif action == "prompt_patch":
            patch = _mapping(request_payload.get("prompt_patch"))
            if not patch:
                return self._blocked_result(campaign_id, mission_id, "prompt_patch blocked: missing prompt patch payload")
            query = ConsoleQueryService(query_service=self._query_service, campaign_service=self._campaign_service)
            query.patch_prompt_surface(workspace, campaign_id, patch={**patch, "operator_reason": operator_reason, "policy_source": policy_source}, node_id=target_node_id)
            result_summary = "prompt patch applied"
            skip_followup_audit = True
        elif action == "workflow_patch":
            patch = _mapping(request_payload.get("workflow_patch"))
            if not patch:
                return self._blocked_result(campaign_id, mission_id, "workflow_patch blocked: missing workflow patch payload")
            query = ConsoleQueryService(query_service=self._query_service, campaign_service=self._campaign_service)
            query.patch_campaign_workflow_authoring(workspace, campaign_id, {**patch, "operator_reason": operator_reason, "policy_source": policy_source})
            result_summary = "workflow patch applied"
            skip_followup_audit = True
        else:
            return self._blocked_result(campaign_id, mission_id, f"unsupported action: {action}")
        updated = self._query_service.get_campaign_status(workspace, campaign_id)
        after_summary = self._control_state_summary(updated)
        if skip_followup_audit:
            audit_ids = self._latest_audit_ids(updated)
        else:
            audit_ids = self._record_action_audit(
                workspace,
                campaign_id,
                action_type=action,
                target_scope=target_scope,
                target_node_id=target_node_id,
                result_summary=result_summary,
                operator_reason=operator_reason,
                policy_source=policy_source,
                payload=request_payload,
                before_summary=before_summary,
                after_summary=after_summary,
                recovery_payload=recovery_payload,
            )
        return ControlActionResult(
            ok=True,
            campaign_id=campaign_id,
            mission_id=mission_id,
            applied_at=_utc_now_iso(),
            result_summary=result_summary,
            audit_event_id=audit_ids["action_id"],
            trace_id=audit_ids["trace_id"],
            receipt_id=audit_ids["receipt_id"],
            recovery_decision_id=audit_ids["recovery_decision_id"],
            updated_state={
                "campaign_view": _mapping(updated.get("campaign_view")),
                "task_summary": _mapping(updated.get("task_summary")),
                "governance_summary": _mapping(updated.get("governance_summary")),
                "user_feedback": _mapping(updated.get("user_feedback")),
                "latest_turn_receipt": _mapping(updated.get("latest_turn_receipt")),
            },
            metadata={"action": action, "source_surface": request.source_surface, "target_scope": target_scope, "target_node_id": target_node_id},
        )

    @staticmethod
    def _blocked_result(campaign_id: str, mission_id: str, summary: str) -> ControlActionResult:
        return ControlActionResult(
            ok=False,
            campaign_id=campaign_id,
            mission_id=mission_id,
            applied_at=_utc_now_iso(),
            result_summary=summary,
            audit_event_id=f"console_action_{uuid4().hex[:12]}",
        )

    @staticmethod
    def _control_state_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
        task_summary = _mapping(payload.get("task_summary"))
        progress = _mapping(task_summary.get("progress"))
        latest_turn_receipt = _mapping(payload.get("latest_turn_receipt"))
        return {
            "status": _text(_mapping(payload.get("campaign_view")).get("status") or payload.get("status")),
            "current_phase": _text(payload.get("current_phase") or "turn"),
            "next_phase": _text(payload.get("next_phase") or "harness"),
            "execution_state": _text(payload.get("execution_state")),
            "closure_state": _text(payload.get("closure_state")),
            "approval_state": _text(_mapping(payload.get("governance_summary")).get("approval_state")),
            "operational_checks_pending": _list_of_text(payload.get("operational_checks_pending")),
            "closure_checks_pending": _list_of_text(payload.get("closure_checks_pending")),
            "turn_id": _text(latest_turn_receipt.get("turn_id")),
            "turn_count": _coerce_int(progress.get("turn_count")),
        }

    @staticmethod
    def _next_phase_from_payload(payload: Mapping[str, Any], current_phase: str) -> str:
        phase_path = _list_of_text(_mapping(payload.get("phase_runtime")).get("phase_path")) or ["discover", "implement", "evaluate", "iterate"]
        target = _text(current_phase)
        if target in phase_path:
            index = phase_path.index(target)
            if index + 1 < len(phase_path):
                return phase_path[index + 1]
        return target

    def _record_action_audit(
        self,
        workspace: str,
        campaign_id: str,
        *,
        action_type: str,
        target_scope: str,
        target_node_id: str,
        result_summary: str,
        operator_reason: str,
        policy_source: str,
        payload: Mapping[str, Any] | None,
        before_summary: Mapping[str, Any],
        after_summary: Mapping[str, Any],
        recovery_payload: Mapping[str, Any] | None,
    ) -> dict[str, str]:
        action_id = f"operator_action_{uuid4().hex[:12]}"
        trace_id = f"trace_{uuid4().hex[:12]}"
        receipt_id = f"operator_receipt_{uuid4().hex[:12]}"
        recovery_decision = None
        if isinstance(recovery_payload, Mapping) and recovery_payload:
            recovery_decision = {
                "decision_id": f"recovery_decision_{uuid4().hex[:12]}",
                "action_id": action_id,
                "resume_from": _text(recovery_payload.get("resume_from")),
                "recovery_candidate_id": _text(recovery_payload.get("recovery_candidate_id")),
                "decision_summary": _text(recovery_payload.get("decision_summary") or result_summary),
                "result_state": _text(recovery_payload.get("result_state") or "active"),
                "metadata": dict(recovery_payload),
            }
        self._campaign_service.record_operator_action(
            workspace,
            campaign_id,
            action={
                "action_id": action_id,
                "campaign_id": campaign_id,
                "target_scope": target_scope,
                "target_node_id": _text(target_node_id),
                "action_type": _text(action_type),
                "operator_id": "console_user",
                "operator_reason": _text(operator_reason),
                "policy_source": _text(policy_source),
                "trace_id": trace_id,
                "status": "applied",
                "result_summary": _text(result_summary),
                "payload": dict(payload or {}),
                "receipt_id": receipt_id,
                "recovery_decision_id": _text((recovery_decision or {}).get("decision_id")),
            },
            patch_receipt={
                "receipt_id": receipt_id,
                "action_id": action_id,
                "patch_kind": _text(action_type),
                "before_summary": dict(before_summary or {}),
                "after_summary": dict(after_summary or {}),
                "effective_scope": _text(target_scope) or "campaign",
                "effective_timing": "future_execution",
                "target_node_id": _text(target_node_id),
                "changed_fields": sorted({*before_summary.keys(), *after_summary.keys()}),
                "metadata": {"policy_source": _text(policy_source)},
            },
            recovery_decision=recovery_decision,
        )
        return {
            "action_id": action_id,
            "trace_id": trace_id,
            "receipt_id": receipt_id,
            "recovery_decision_id": _text((recovery_decision or {}).get("decision_id")),
        }

    @staticmethod
    def _latest_audit_ids(payload: Mapping[str, Any]) -> dict[str, str]:
        metadata = _mapping(payload.get("metadata"))
        operator_plane = _mapping(metadata.get("operator_plane"))
        actions = _list_of_mapping(operator_plane.get("actions"))
        latest = actions[-1] if actions else {}
        receipts = {
            _text(item.get("action_id")): dict(item)
            for item in _list_of_mapping(operator_plane.get("patch_receipts"))
            if _text(item.get("action_id"))
        }
        recoveries = {
            _text(item.get("action_id")): dict(item)
            for item in _list_of_mapping(operator_plane.get("recovery_decisions"))
            if _text(item.get("action_id"))
        }
        action_id = _text(latest.get("action_id"))
        receipt = receipts.get(action_id, {})
        recovery = recoveries.get(action_id, {})
        return {
            "action_id": action_id,
            "trace_id": _text(latest.get("trace_id")),
            "receipt_id": _text(receipt.get("receipt_id") or latest.get("receipt_id")),
            "recovery_decision_id": _text(recovery.get("decision_id") or latest.get("recovery_decision_id")),
        }
