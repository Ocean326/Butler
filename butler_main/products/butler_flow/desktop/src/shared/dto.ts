export type FlowStatus = "running" | "paused" | "completed" | "failed" | "draft" | string;

export interface FlowSummaryDTO {
  flow_id: string;
  label: string;
  workflow_kind: string;
  effective_status: FlowStatus;
  effective_phase: string;
  attempt_count: number;
  max_attempts: number;
  max_phase_attempts: number;
  max_runtime_seconds: number;
  runtime_elapsed_seconds: number;
  goal: string;
  guard_condition: string;
  approval_state: string;
  execution_mode: string;
  session_strategy: string;
  active_role_id: string;
  role_pack_id: string;
  last_judge: string;
  latest_judge_decision: Record<string, unknown>;
  last_operator_action: string;
  latest_operator_action: Record<string, unknown>;
  queued_operator_updates: unknown[];
  latest_token_usage: Record<string, unknown>;
  context_governor: Record<string, unknown>;
  latest_handoff_summary: Record<string, unknown>;
  updated_at: string;
}

export interface TimelineEvent {
  event_id: string;
  kind: string;
  flow_id: string;
  phase: string;
  attempt_no: number;
  created_at: string;
  message: string;
  title?: string;
  lane?: string;
  family?: string;
  raw_text?: string;
  payload?: Record<string, unknown>;
}

export interface RoleRuntimeDTO {
  active_role_id: string;
  role_sessions: Record<string, unknown>;
  pending_handoffs: Array<Record<string, unknown>>;
  recent_handoffs: Array<Record<string, unknown>>;
  latest_handoff_summary: Record<string, unknown>;
  latest_role_handoffs: Record<string, unknown>;
  role_chips: Array<Record<string, unknown>>;
  roles: Array<Record<string, unknown>>;
  execution_mode: string;
  session_strategy: string;
  role_pack_id: string;
}

export interface SupervisorViewDTO {
  header: Record<string, unknown>;
  events: TimelineEvent[];
  latest_supervisor_decision: Record<string, unknown>;
  latest_judge_decision: Record<string, unknown>;
  latest_operator_action: Record<string, unknown>;
  latest_handoff_summary: Record<string, unknown>;
  context_governor: Record<string, unknown>;
  latest_token_usage: Record<string, unknown>;
  pointers: Record<string, unknown>;
}

export interface WorkflowViewDTO {
  events: TimelineEvent[];
  runtime_summary: Record<string, unknown>;
  artifact_refs: string[];
}

export interface ManageCenterDTO {
  preflight: Record<string, unknown>;
  assets: {
    items?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  selected_asset: Record<string, unknown>;
  role_guidance: Record<string, unknown>;
  review_checklist: string[];
  bundle_manifest: Record<string, unknown>;
  manager_notes: string;
}

export interface WorkspacePayload {
  preflight: Record<string, unknown>;
  flows: {
    items: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
}

export interface SingleFlowPayload {
  flow_id: string;
  status: Record<string, unknown>;
  summary: FlowSummaryDTO;
  step_history: Array<Record<string, unknown>>;
  timeline: TimelineEvent[];
  turns: Array<Record<string, unknown>>;
  actions: Array<Record<string, unknown>>;
  artifacts: Array<Record<string, unknown>>;
  handoffs: Array<Record<string, unknown>>;
  flow_definition: Record<string, unknown>;
  runtime_snapshot: Record<string, unknown>;
  navigator_summary: FlowSummaryDTO;
  supervisor_view: SupervisorViewDTO;
  workflow_view: WorkflowViewDTO;
  inspector: Record<string, unknown>;
  role_strip: RoleRuntimeDTO;
  operator_rail: Record<string, unknown>;
  flow_console: {
    step_history: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  surface: Record<string, unknown>;
}

export interface ThreadBlockDTO {
  block_id: string;
  kind: string;
  title: string;
  summary: string;
  created_at: string;
  status: string;
  expanded_by_default: boolean;
  payload: Record<string, unknown>;
  role_id?: string;
  phase?: string;
  action_label?: string;
  action_target?: string;
  tags?: string[];
}

export interface ThreadSummaryDTO {
  thread_id: string;
  thread_kind: string;
  title: string;
  subtitle: string;
  status: string;
  created_at: string;
  updated_at: string;
  manager_session_id: string;
  flow_id: string;
  active_role_id: string;
  current_phase: string;
  badge: string;
  tags: string[];
}

export interface ThreadHomeDTO {
  preflight: Record<string, unknown>;
  manager_entry: {
    default_manager_session_id: string;
    draft_summary: string;
    status: string;
    title: string;
    total_sessions: number;
    active_flow_id: string;
    active_thread_id: string;
  };
  history: ThreadSummaryDTO[];
  templates: ThreadSummaryDTO[];
}

export interface ManagerThreadDTO {
  thread: ThreadSummaryDTO;
  manager_session_id: string;
  manage_target: string;
  active_manage_target: string;
  manager_stage: string;
  confirmation_scope: string;
  blocks: ThreadBlockDTO[];
  draft: Record<string, unknown>;
  pending_action: Record<string, unknown>;
  latest_response: string;
  linked_flow_id: string;
}

export interface SupervisorThreadDTO {
  thread: ThreadSummaryDTO;
  flow_id: string;
  summary: FlowSummaryDTO;
  blocks: ThreadBlockDTO[];
  role_strip: RoleRuntimeDTO;
  operator_rail: Record<string, unknown>;
  latest_handoff: Record<string, unknown>;
}

export interface AgentFocusDTO {
  thread: ThreadSummaryDTO;
  flow_id: string;
  role_id: string;
  title: string;
  summary: FlowSummaryDTO;
  blocks: ThreadBlockDTO[];
  role: Record<string, unknown>;
  related_handoffs: Array<Record<string, unknown>>;
  artifacts: Array<Record<string, unknown>>;
}

export interface TemplateTeamDTO {
  thread: ThreadSummaryDTO;
  asset_id: string;
  blocks: ThreadBlockDTO[];
  assets: Array<Record<string, unknown>>;
  selected_asset: Record<string, unknown>;
  role_guidance: Record<string, unknown>;
  review_checklist: string[];
  bundle_manifest: Record<string, unknown>;
  manager_notes: string;
}

export interface DesktopActionPayload {
  configPath?: string;
  flowId: string;
  type: string;
  instruction?: string;
  repoContractPath?: string;
}

export interface ManagerMessagePayload {
  configPath?: string;
  instruction: string;
  managerSessionId?: string;
  manageTarget?: string;
}

export interface ManagerMessageResult {
  ok: boolean;
  manager_session_id: string;
  message: Record<string, unknown>;
  thread: ManagerThreadDTO;
  launched_flow: Record<string, unknown>;
}

export interface DesktopBridgeResult {
  ok: boolean;
  error_type?: string;
  message?: string;
}
