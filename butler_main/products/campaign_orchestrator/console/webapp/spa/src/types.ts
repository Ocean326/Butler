export type ScopeMode = "global" | "campaign" | "drafts";
export type BoardMode = "graph" | "preview";
export type ContextTab = "artifacts" | "records" | "runtime" | "operator" | "drafts";
export type AgentTab = "records" | "planned" | "artifacts" | "raw";

export interface RuntimeStatus {
  process_state?: string;
  run_state?: string;
  phase?: string;
  note?: string;
  updated_at?: string;
  is_stale?: boolean;
  [key: string]: unknown;
}

export interface CampaignSummary {
  campaign_id: string;
  title?: string;
  status?: string;
  mode_id?: string;
  canonical_session_id?: string;
  task_summary?: Record<string, unknown>;
  current_phase?: string;
  next_phase?: string;
  updated_at?: string;
  bundle_root?: string;
  latest_acceptance_decision?: string;
}

export interface GraphNodeView {
  id: string;
  title: string;
  kind: string;
  status: string;
  phase?: string;
  role_id?: string;
  badges?: string[];
  artifact_refs?: string[];
  handoff_refs?: string[];
  action_state?: {
    can_retry?: boolean;
    can_reroute?: boolean;
  };
}

export interface GraphEdgeView {
  id: string;
  source: string;
  target: string;
  kind: string;
  condition?: string;
  active?: boolean;
}

export interface GraphSnapshot {
  graph_level: string;
  revision_id: string;
  campaign_id: string;
  workflow_id?: string;
  workflow_session_id?: string;
  phase_path: string[];
  active_path: string[];
  nodes: GraphNodeView[];
  edges: GraphEdgeView[];
  inspector_defaults?: {
    selected_node_id?: string;
  };
  available_actions?: string[];
  metadata?: Record<string, unknown>;
}

export interface AgentExecutionView {
  id: string;
  title: string;
  role_id?: string;
  role_label?: string;
  agent_spec_id?: string;
  status?: string;
  queue_state?: string;
  phase?: string;
  step_id?: string;
  source?: string;
  summary?: string;
  badges?: string[];
  metadata?: Record<string, unknown>;
}

export interface BoardNodeView {
  id: string;
  title: string;
  display_title?: string;
  display_brief?: string;
  subtitle?: string;
  role_label?: string;
  iteration_label?: string;
  updated_at_label?: string;
  visual_state?: string;
  status?: string;
  lane?: string;
  phase?: string;
  step_id?: string;
  role_id?: string;
  agent_spec_id?: string;
  source?: string;
  badges?: string[];
  artifact_refs?: string[];
  detail_available?: boolean;
  detail_campaign_id?: string;
  detail_node_id?: string;
  position?: { x?: number; y?: number };
  size?: { w?: number; h?: number };
  metadata?: Record<string, unknown>;
}

export interface BoardEdgeView {
  id: string;
  source: string;
  target: string;
  kind: string;
  active?: boolean;
  label?: string;
  visual_kind?: string;
  emphasis?: string;
}

export interface ArtifactListItem {
  artifact_id: string;
  label: string;
  kind?: string;
  phase?: string;
  iteration?: number;
  created_at?: string;
  ref?: string;
  previewable?: boolean;
  metadata?: Record<string, unknown>;
}

export interface RecordListItem {
  record_id: string;
  title: string;
  kind?: string;
  created_at?: string;
  summary?: string;
  preview_kind?: string;
  preview_title?: string;
  preview_language?: string;
  preview_content?: string;
  metadata?: Record<string, unknown>;
}

export interface TimelineItem {
  id: string;
  kind: string;
  timestamp?: string;
  anchor_timestamp?: string;
  display_time?: string;
  display_title?: string;
  display_brief?: string;
  campaign_id?: string;
  node_id?: string;
  step_id?: string;
  status?: string;
  is_future?: boolean;
  detail_available?: boolean;
  detail_campaign_id?: string;
  detail_node_id?: string;
  anchor_x?: number;
  layout_x?: number;
  detail_payload?: Record<string, unknown>;
}

export interface BoardSnapshot {
  scope: ScopeMode extends infer _ ? string : string;
  scope_id: string;
  snapshot_id: string;
  title: string;
  status?: string;
  summary?: string;
  idle_reason?: string;
  current_agent?: AgentExecutionView | null;
  next_agent?: AgentExecutionView | null;
  running_agents: AgentExecutionView[];
  next_agents: AgentExecutionView[];
  queued_agents: AgentExecutionView[];
  nodes: BoardNodeView[];
  edges: BoardEdgeView[];
  artifacts: ArtifactListItem[];
  records: RecordListItem[];
  timeline_items: TimelineItem[];
  timeline_bounds?: {
    min_x?: number;
    max_x?: number;
    stage_width?: number;
  };
  preview_defaults?: {
    selected_node_id?: string;
    preview_artifact_id?: string;
    mode?: BoardMode;
  };
  metadata?: Record<string, unknown>;
}

export interface PreviewEnvelope {
  scope: string;
  scope_id: string;
  item_id: string;
  title: string;
  kind?: string;
  preview_kind?: string;
  language?: string;
  content?: string;
  content_path?: string;
  metadata?: Record<string, unknown>;
}

export interface AgentDetailEnvelope {
  campaign_id: string;
  node_id: string;
  title: string;
  status?: string;
  execution_state?: string;
  role_id?: string;
  role_label?: string;
  agent_spec_id?: string;
  subtitle?: string;
  updated_at?: string;
  overview?: Record<string, unknown>;
  planned_input?: Record<string, unknown>;
  live_records?: Array<Record<string, unknown>>;
  artifacts?: Array<Record<string, unknown>>;
  raw_records?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
}

export interface FrontdoorDraftView {
  draft_id: string;
  session_id: string;
  mode_id: string;
  goal: string;
  materials: string[];
  hard_constraints: string[];
  acceptance_criteria: string[];
  recommended_template_id?: string;
  selected_template_id?: string;
  composition_mode?: string;
  skill_selection?: Record<string, unknown>;
  pending_confirmation?: boolean;
  linked_campaign_id?: string;
  frontdoor_ref?: Record<string, string>;
  governance_defaults?: Record<string, string>;
  metadata?: Record<string, unknown>;
}

export interface AccessDiagnostics {
  listen_host: string;
  port: number;
  base_path: string;
  local_urls: string[];
  lan_urls: string[];
  note?: string;
  hints?: string[];
  metadata?: Record<string, unknown>;
}

export interface ChannelThreadSummary {
  channel: string;
  session_id: string;
  thread_id: string;
  latest_user_message?: string;
  latest_system_message?: string;
  jump_link?: string;
  metadata?: Record<string, unknown>;
}

export interface ControlActionRequest {
  action: string;
  target_kind?: "campaign";
  target_scope?: string;
  target_node_id?: string;
  transition_to?: string;
  resume_from?: string;
  check_ids?: string[];
  feedback?: string;
  prompt_patch?: Record<string, unknown>;
  workflow_patch?: Record<string, unknown>;
  reason?: string;
  operator_reason?: string;
  policy_source?: string;
  payload?: Record<string, unknown>;
  operator_id?: string;
  source_surface?: string;
}

export interface ControlActionResult {
  ok: boolean;
  campaign_id?: string;
  mission_id?: string;
  applied_at?: string;
  result_summary?: string;
  audit_event_id?: string;
  trace_id?: string;
  receipt_id?: string;
  recovery_decision_id?: string;
  updated_state?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface ConsoleEventEnvelope {
  scope: string;
  scope_id: string;
  event_id: string;
  event_type: string;
  created_at: string;
  severity?: string;
  payload?: Record<string, unknown>;
}

export interface ControlPlaneEnvelope {
  campaign_id: string;
  mission_id?: string;
  canonical_session_id?: string;
  macro_state?: string;
  narrative_summary?: string;
  execution_state?: string;
  closure_state?: string;
  progress_reason?: string;
  closure_reason?: string;
  operator_next_action?: string;
  latest_stage_summary?: string;
  latest_acceptance_decision?: string;
  latest_turn_receipt?: Record<string, unknown>;
  latest_delivery_refs?: string[];
  harness_summary?: Record<string, unknown>;
  acceptance_requirements_remaining?: string[];
  operational_checks_pending?: string[];
  closure_checks_pending?: string[];
  resolved_checks?: string[];
  waived_checks?: string[];
  approval_state?: string;
  risk_level?: string;
  autonomy_profile?: string;
  available_actions?: string[];
  transition_options?: AuditActionRecord[];
  recovery_candidates?: AuditActionRecord[];
  audit_summary?: Record<string, unknown>;
}

export interface PromptSurfaceEnvelope {
  campaign_id: string;
  node_id?: string;
  phase_id?: string;
  structured_contract?: Record<string, unknown>;
  preview?: {
    body?: string;
    final_prompt?: string;
    prompt_length?: number;
    phase_id?: string;
    [key: string]: unknown;
  };
  policy_sources?: Record<string, unknown>;
  audit_summary?: Record<string, unknown>;
}

export interface WorkflowAuthoringEnvelope {
  scope: string;
  scope_id: string;
  title?: string;
  template_id?: string;
  template_label?: string;
  composition_mode?: string;
  skeleton_changed?: boolean;
  phase_plan?: string[];
  role_plan?: string[];
  governance_plan?: Record<string, unknown>;
  diff_summary?: string[];
  transition_rules?: Array<Record<string, unknown>>;
  recovery_entries?: Array<Record<string, unknown>>;
  current_phase?: string;
  next_phase?: string;
  linked_campaign_id?: string;
}

export interface CompilePreviewEnvelope {
  scope: string;
  scope_id: string;
  goal?: string;
  template_id?: string;
  compile_result?: string;
  validation_errors?: string[];
  warnings?: string[];
  risk_hints?: string[];
  compiled_contract?: Record<string, unknown>;
}

export interface AuditActionRecord {
  action_id?: string;
  action?: string;
  action_type?: string;
  transition_to?: string;
  resume_from?: string;
  label?: string;
  reason?: string;
  target_scope?: string;
  target_node_id?: string;
  result_summary?: string;
  created_at?: string;
  patch_receipt?: Record<string, unknown>;
  recovery_decision?: Record<string, unknown>;
  [key: string]: unknown;
}
