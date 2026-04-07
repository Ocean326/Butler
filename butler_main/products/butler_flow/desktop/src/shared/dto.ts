export type FlowStatus = "running" | "paused" | "completed" | "failed" | "draft" | string;

export interface SurfaceMetaDTO {
  surface_id?: string;
  canonical_surface?: string;
  projection_kind?: string;
  display_title?: string;
  legacy_aliases?: string[];
  truth_basis?: string[];
  title?: string;
}

export interface FlowSummaryDTO {
  flow_id: string;
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

export interface FlowDetailDTO {
  summary: FlowSummaryDTO;
  step_history: Array<Record<string, unknown>>;
  timeline: TimelineEvent[];
  turns: Array<Record<string, unknown>>;
  actions: Array<Record<string, unknown>>;
  artifacts: Array<Record<string, unknown>>;
  handoffs: Array<Record<string, unknown>>;
  flow_definition: Record<string, unknown>;
  runtime_snapshot: Record<string, unknown>;
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

export interface ManageCenterDTO {
  surface_meta?: SurfaceMetaDTO;
  preflight: Record<string, unknown>;
  assets: {
    items?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  selected_asset: Record<string, unknown>;
  contract_studio?: Record<string, unknown>;
  role_guidance: Record<string, unknown>;
  review_checklist: string[];
  bundle_manifest: Record<string, unknown>;
  manager_notes: string;
}

export interface WorkspacePayload {
  surface_meta?: SurfaceMetaDTO;
  preflight: Record<string, unknown>;
  flows: {
    items: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
}

export interface SingleFlowPayload extends FlowDetailDTO {
  flow_id: string;
  surface_meta?: SurfaceMetaDTO;
  status: Record<string, unknown>;
  task_contract?: Record<string, unknown>;
  task_contract_summary?: Record<string, unknown>;
  governance_summary?: Record<string, unknown>;
  mission_console?: Record<string, unknown>;
  latest_receipt_summary?: Record<string, unknown>;
  latest_governance_receipt_summary?: Record<string, unknown>;
  latest_artifact_ref?: string;
  accepted_receipt_count?: number;
  recovery_cursor?: Record<string, unknown>;
  recovery_state?: string;
  navigator_summary: FlowSummaryDTO;
  supervisor_view: SupervisorViewDTO;
  workflow_view: WorkflowViewDTO;
  inspector: Record<string, unknown>;
  role_strip: RoleRuntimeDTO;
  operator_rail: Record<string, unknown>;
  flow_console: Record<string, unknown>;
  surface: Record<string, unknown>;
}

export interface DesktopActionPayload {
  configPath?: string;
  flowId: string;
  type: string;
  instruction?: string;
  repoContractPath?: string;
}

export interface DesktopBridgeResult {
  ok: boolean;
  error_type?: string;
  message?: string;
}
