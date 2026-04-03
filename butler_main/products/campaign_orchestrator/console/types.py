from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class GraphNodeActionState:
    can_retry: bool = False
    can_reroute: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GraphNodeView:
    id: str
    kind: str
    title: str
    status: str
    phase: str = ""
    role_id: str = ""
    artifact_refs: list[str] = field(default_factory=list)
    handoff_refs: list[str] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)
    action_state: GraphNodeActionState = field(default_factory=GraphNodeActionState)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["action_state"] = self.action_state.to_dict()
        return payload


@dataclass(slots=True)
class GraphEdgeView:
    id: str
    source: str
    target: str
    kind: str = "next"
    condition: str = "next"
    active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GraphSnapshot:
    graph_level: str
    revision_id: str
    campaign_id: str
    workflow_id: str = ""
    workflow_session_id: str = ""
    phase_path: list[str] = field(default_factory=list)
    active_path: list[str] = field(default_factory=list)
    nodes: list[GraphNodeView] = field(default_factory=list)
    edges: list[GraphEdgeView] = field(default_factory=list)
    inspector_defaults: dict[str, Any] = field(default_factory=dict)
    available_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_level": self.graph_level,
            "revision_id": self.revision_id,
            "campaign_id": self.campaign_id,
            "workflow_id": self.workflow_id,
            "workflow_session_id": self.workflow_session_id,
            "phase_path": list(self.phase_path),
            "active_path": list(self.active_path),
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [item.to_dict() for item in self.edges],
            "inspector_defaults": dict(self.inspector_defaults),
            "available_actions": list(self.available_actions),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class AgentExecutionView:
    execution_id: str
    campaign_id: str = ""
    mission_id: str = ""
    branch_id: str = ""
    workflow_id: str = ""
    workflow_session_id: str = ""
    step_id: str = ""
    role_id: str = ""
    status: str = ""
    queue_state: str = ""
    projection_kind: str = "inferred"
    inferred: bool = True
    reason: str = ""
    source: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentExecutionQueueView:
    current: list[AgentExecutionView] = field(default_factory=list)
    next: list[AgentExecutionView] = field(default_factory=list)
    queued: list[AgentExecutionView] = field(default_factory=list)
    idle_reason: str = ""
    has_exact: bool = False
    has_inferred: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "current": [item.to_dict() for item in self.current],
            "next": [item.to_dict() for item in self.next],
            "queued": [item.to_dict() for item in self.queued],
            "idle_reason": self.idle_reason,
            "has_exact": self.has_exact,
            "has_inferred": self.has_inferred,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class GlobalSchedulerBoardSnapshot:
    board_kind: str
    revision_id: str
    runtime: dict[str, Any] = field(default_factory=dict)
    queue: AgentExecutionQueueView = field(default_factory=AgentExecutionQueueView)
    campaigns: list[dict[str, Any]] = field(default_factory=list)
    active_branches: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_kind": self.board_kind,
            "revision_id": self.revision_id,
            "runtime": dict(self.runtime),
            "queue": self.queue.to_dict(),
            "campaigns": list(self.campaigns),
            "active_branches": list(self.active_branches),
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ProjectBoardSnapshot:
    board_kind: str
    revision_id: str
    campaign_id: str
    graph: GraphSnapshot
    campaign_view: dict[str, Any] = field(default_factory=dict)
    queue: AgentExecutionQueueView = field(default_factory=AgentExecutionQueueView)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    events: list[ConsoleEventEnvelope] = field(default_factory=list)
    session_plane: dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_kind": self.board_kind,
            "revision_id": self.revision_id,
            "campaign_id": self.campaign_id,
            "graph": self.graph.to_dict(),
            "campaign_view": dict(self.campaign_view),
            "queue": self.queue.to_dict(),
            "artifacts": list(self.artifacts),
            "events": [item.to_dict() for item in self.events],
            "session_plane": dict(self.session_plane),
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ArtifactPreviewEnvelope:
    campaign_id: str
    artifact_id: str
    artifact_ref: str = ""
    artifact_kind: str = ""
    label: str = ""
    created_at: str = ""
    preview_kind: str = "unsupported"
    content_type: str = ""
    encoding: str = "utf-8"
    content: str = ""
    content_truncated: bool = False
    byte_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AccessDiagnostics:
    bind_host: str
    bind_port: int
    detected_ipv4: list[str] = field(default_factory=list)
    suggested_urls: list[str] = field(default_factory=list)
    loopback_url: str = ""
    lan_urls: list[str] = field(default_factory=list)
    request_host: str = ""
    request_port: int = 0
    hints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentExecutionView:
    id: str
    title: str
    role_id: str = ""
    agent_spec_id: str = ""
    status: str = "queued"
    queue_state: str = "queued"
    phase: str = ""
    step_id: str = ""
    source: str = "inferred"
    summary: str = ""
    badges: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BoardNodeView:
    id: str
    title: str
    display_title: str = ""
    display_brief: str = ""
    subtitle: str = ""
    role_label: str = ""
    iteration_label: str = ""
    updated_at_label: str = ""
    visual_state: str = ""
    status: str = "queued"
    lane: str = "queued"
    phase: str = ""
    step_id: str = ""
    role_id: str = ""
    agent_spec_id: str = ""
    source: str = "inferred"
    badges: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    detail_available: bool = False
    detail_campaign_id: str = ""
    detail_node_id: str = ""
    position: dict[str, float] = field(default_factory=dict)
    size: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BoardEdgeView:
    id: str
    source: str
    target: str
    kind: str = "next"
    active: bool = False
    label: str = ""
    visual_kind: str = "flow"
    emphasis: str = "normal"
    is_back_edge: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ArtifactListItem:
    artifact_id: str
    label: str
    kind: str = ""
    phase: str = ""
    iteration: int = 0
    created_at: str = ""
    ref: str = ""
    previewable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RecordListItem:
    record_id: str
    title: str
    kind: str = ""
    created_at: str = ""
    summary: str = ""
    preview_kind: str = "text"
    preview_title: str = ""
    preview_language: str = "text"
    preview_content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TimelineItem:
    id: str
    kind: str
    timestamp: str = ""
    anchor_timestamp: str = ""
    display_time: str = ""
    display_title: str = ""
    display_brief: str = ""
    campaign_id: str = ""
    node_id: str = ""
    step_id: str = ""
    status: str = ""
    is_future: bool = False
    detail_available: bool = False
    detail_campaign_id: str = ""
    detail_node_id: str = ""
    anchor_x: float = 0.0
    layout_x: float = 0.0
    detail_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentDetailEnvelope:
    campaign_id: str
    node_id: str
    title: str
    status: str = ""
    execution_state: str = ""
    role_id: str = ""
    role_label: str = ""
    agent_spec_id: str = ""
    subtitle: str = ""
    updated_at: str = ""
    overview: dict[str, Any] = field(default_factory=dict)
    planned_input: dict[str, Any] = field(default_factory=dict)
    live_records: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    raw_records: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PreviewEnvelope:
    scope: str
    scope_id: str
    item_id: str
    title: str
    kind: str = "text"
    preview_kind: str = "text"
    language: str = "text"
    content: str = ""
    content_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AccessDiagnostics:
    listen_host: str
    port: int
    base_path: str = "/console/"
    local_urls: list[str] = field(default_factory=list)
    lan_urls: list[str] = field(default_factory=list)
    note: str = ""
    hints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BoardSnapshot:
    scope: str
    scope_id: str
    snapshot_id: str
    title: str
    status: str = ""
    summary: str = ""
    idle_reason: str = ""
    current_agent: AgentExecutionView | None = None
    next_agent: AgentExecutionView | None = None
    running_agents: list[AgentExecutionView] = field(default_factory=list)
    next_agents: list[AgentExecutionView] = field(default_factory=list)
    queued_agents: list[AgentExecutionView] = field(default_factory=list)
    nodes: list[BoardNodeView] = field(default_factory=list)
    edges: list[BoardEdgeView] = field(default_factory=list)
    artifacts: list[ArtifactListItem] = field(default_factory=list)
    records: list[RecordListItem] = field(default_factory=list)
    timeline_items: list[TimelineItem] = field(default_factory=list)
    timeline_bounds: dict[str, Any] = field(default_factory=dict)
    preview_defaults: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "scope_id": self.scope_id,
            "snapshot_id": self.snapshot_id,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "idle_reason": self.idle_reason,
            "current_agent": self.current_agent.to_dict() if self.current_agent is not None else None,
            "next_agent": self.next_agent.to_dict() if self.next_agent is not None else None,
            "running_agents": [item.to_dict() for item in self.running_agents],
            "next_agents": [item.to_dict() for item in self.next_agents],
            "queued_agents": [item.to_dict() for item in self.queued_agents],
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [item.to_dict() for item in self.edges],
            "artifacts": [item.to_dict() for item in self.artifacts],
            "records": [item.to_dict() for item in self.records],
            "timeline_items": [item.to_dict() for item in self.timeline_items],
            "timeline_bounds": dict(self.timeline_bounds),
            "preview_defaults": dict(self.preview_defaults),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class FrontdoorDraftView:
    draft_id: str
    session_id: str
    mode_id: str
    goal: str
    materials: list[str] = field(default_factory=list)
    hard_constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    recommended_template_id: str = ""
    selected_template_id: str = ""
    composition_mode: str = ""
    skill_selection: dict[str, Any] = field(default_factory=dict)
    pending_confirmation: bool = False
    linked_campaign_id: str = ""
    frontdoor_ref: dict[str, str] = field(default_factory=dict)
    governance_defaults: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChannelThreadSummary:
    channel: str
    session_id: str
    thread_id: str
    latest_user_message: str = ""
    latest_system_message: str = ""
    jump_link: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ControlActionRequest:
    action: str
    target_kind: str = "campaign"
    target_id: str = ""
    target_scope: str = "campaign"
    target_node_id: str = ""
    transition_to: str = ""
    resume_from: str = ""
    check_ids: list[str] = field(default_factory=list)
    feedback: str = ""
    prompt_patch: dict[str, Any] = field(default_factory=dict)
    workflow_patch: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    operator_reason: str = ""
    policy_source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    operator_id: str = ""
    source_surface: str = "console"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ControlActionResult:
    ok: bool
    campaign_id: str = ""
    mission_id: str = ""
    applied_at: str = ""
    result_summary: str = ""
    audit_event_id: str = ""
    trace_id: str = ""
    receipt_id: str = ""
    recovery_decision_id: str = ""
    updated_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ConsoleEventEnvelope:
    scope: str
    scope_id: str
    event_id: str
    event_type: str
    created_at: str
    severity: str = "info"
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
