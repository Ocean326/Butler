from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict


class FlowDecision(TypedDict, total=False):
    decision: Literal["COMPLETE", "RETRY", "ABORT", "ADVANCE"]
    next_phase: NotRequired[str]
    reason: str
    next_codex_prompt: str
    completion_summary: str
    issue_kind: Literal["agent_cli_fault", "bug", "service_fault", "plan_gap", "none"]
    followup_kind: Literal["fix", "retry", "replan", "none"]


class FlowState(TypedDict, total=False):
    workflow_id: str
    task_contract_id: str
    workflow_kind: str
    launch_mode: str
    catalog_flow_id: str
    workspace_root: str
    goal: str
    guard_condition: str
    status: str
    current_phase: str
    attempt_count: int
    phase_attempt_count: int
    max_attempts: int
    max_phase_attempts: int
    max_runtime_seconds: int
    runtime_started_at: str
    runtime_elapsed_seconds: int
    codex_session_id: str
    pending_codex_prompt: str
    queued_operator_updates: list[dict[str, Any]]
    last_cursor_decision: dict[str, Any]
    last_completion_summary: str
    last_codex_receipt: dict[str, Any]
    last_cursor_receipt: dict[str, Any]
    current_phase_artifact: dict[str, Any]
    phase_history: list[dict[str, Any]]
    auto_fix_round_count: int
    resume_source: str
    trace_run_id: str
    phase_plan: list[dict[str, Any]]
    entry_mode: str
    manage_handoff: dict[str, Any]
    phase_snapshots: list[dict[str, Any]]
    context_governor: dict[str, Any]
    session_epoch: int
    service_fault_streak: int
    latest_token_usage: dict[str, Any]
    control_profile: dict[str, Any]
    doctor_policy: dict[str, Any]
    supervisor_profile: dict[str, Any]
    execution_mode: str
    session_strategy: str
    active_role_id: str
    active_role_turn_no: int
    role_pack_id: str
    role_sessions: dict[str, Any]
    latest_role_handoffs: dict[str, str]
    role_turn_counts: dict[str, int]
    flow_version: str
    created_at: str
    updated_at: str


class FlowRuntimePlanV1(TypedDict, total=False):
    plan_id: str
    flow_id: str
    workflow_kind: str
    phase: str
    attempt_no: int
    phase_attempt_no: int
    plan_stage: str
    active_role_id: str
    execution_mode: str
    session_strategy: str
    goal: str
    guard_condition: str
    risk_level: str
    autonomy_profile: str
    control_profile: dict[str, Any]
    summary: str
    flow_board: dict[str, Any]
    active_turn_task: dict[str, Any]
    latest_mutation: dict[str, Any]
    updated_at: str


class FlowStrategyEventV1(TypedDict, total=False):
    event_id: str
    flow_id: str
    phase: str
    attempt_no: int
    created_at: str
    lane: str
    family: str
    kind: str
    title: str
    summary: str
    payload: dict[str, Any]


class FlowMutationV1(TypedDict, total=False):
    mutation_id: str
    flow_id: str
    phase: str
    role_id: str
    created_at: str
    mutation_kind: str
    summary: str
    payload: dict[str, Any]


class PromptPacketV1(TypedDict, total=False):
    packet_id: str
    flow_id: str
    workflow_kind: str
    phase: str
    role_id: str
    target_role: str
    attempt_no: int
    phase_attempt_no: int
    session_mode: str
    load_profile: str
    prompt_kind: str
    packet_kind: str
    packet_summary: dict[str, Any]
    packet: dict[str, Any]
    prompt_text: str
    created_at: str
    refs: dict[str, Any]


class FlowBoardV1(TypedDict, total=False):
    flow_id: str
    workflow_kind: str
    goal: str
    guard_condition: str
    current_phase: str
    phase_plan: list[dict[str, Any]]
    current_phase_context: dict[str, Any]
    status: str
    approval_state: str
    active_role_id: str
    execution_mode: str
    session_strategy: str
    role_pack_id: str
    recent_phase_history: list[dict[str, Any]]
    latest_supervisor_decision: dict[str, Any]
    latest_judge_decision: dict[str, Any]
    latest_operator_action: dict[str, Any]
    latest_handoff_summary: dict[str, Any]
    risk_level: str
    autonomy_profile: str
    pending_codex_prompt: str
    queued_operator_updates: list[dict[str, Any]]
    max_runtime_seconds: int
    runtime_elapsed_seconds: int
    context_governor: dict[str, Any]
    latest_token_usage: dict[str, Any]
    control_profile: dict[str, Any]
    source_asset_key: str
    source_asset_kind: str
    source_asset_version: str
    review_checklist: list[str]
    role_guidance: dict[str, Any]
    doctor_policy: dict[str, Any]
    supervisor_profile: dict[str, Any]
    bundle_manifest: dict[str, Any]


class RoleBoardV1(TypedDict, total=False):
    role_id: str
    role_kind: str
    base_role_id: str
    role_pack_id: str
    role_turn_no: int
    role_session_id: str
    role_charter: str
    role_charter_addendum: str
    latest_inbound_handoff: dict[str, Any]
    visible_artifacts: list[dict[str, Any]]
    session_binding: dict[str, Any]


class TurnTaskPacketV1(TypedDict, total=False):
    turn_kind: str
    task_brief: str
    attempt_no: int
    phase_attempt_no: int
    control_mode: str
    packet_size: str
    evidence_level: str
    gate_cadence: str
    repo_binding_policy: str
    gate_required: bool
    success_criteria: list[str]
    input_refs: list[str]
    output_contract: list[str]
    next_instruction: str
    constraints: list[str]


class CompiledPromptPacketV1(TypedDict, total=False):
    packet_kind: str
    target_role: str
    session_mode: str
    load_profile: str
    flow_board: FlowBoardV1
    role_board: RoleBoardV1
    turn_task_packet: TurnTaskPacketV1
    governance_policy: dict[str, Any]
    role_charter: dict[str, Any]
    asset_context: dict[str, Any]
    supervisor_knowledge: dict[str, Any]
    rendered_prompt: str


class SupervisorDecisionV1(TypedDict, total=False):
    decision: str
    turn_kind: str
    reason: str
    confidence: float
    next_action: str
    attempt_no: int
    phase: str
    instruction: str
    issue_kind: str
    followup_kind: str
    fix_round_no: int
    active_role_id: str
    control_mode: str
    packet_size: str
    evidence_level: str
    gate_cadence: str
    gate_required: bool
    repo_binding_policy: str
    execution_mode: str
    session_strategy: str
    session_mode: str
    load_profile: str
    mutation: dict[str, Any]
    ephemeral_role: dict[str, Any]


class FlowDraftV1(TypedDict, total=False):
    draft_id: str
    workflow_kind: str
    goal: str
    guard_condition: str
    materials: list[str]
    skill_exposure: list[str]
    risk_level: str
    autonomy_profile: str
    approval_mode: str
    launch_intent: str
    workspace_root: str


class FlowRunV1(TypedDict, total=False):
    flow_id: str
    draft_id: str
    workflow_kind: str
    goal: str
    guard_condition: str
    status: str
    current_phase: str
    current_turn_id: str
    supervisor_thread_id: str
    primary_executor_session_id: str
    execution_mode: str
    session_strategy: str
    active_role_id: str
    role_pack_id: str
    latest_judge_decision: dict[str, Any]
    latest_supervisor_decision: dict[str, Any]
    risk_level: str
    autonomy_profile: str
    approval_state: str
    workspace_root: str
    artifact_index_ref: str
    trace_refs: list[str]
    receipt_refs: list[str]
    created_at: str
    updated_at: str


class FlowTurnRecordV1(TypedDict, total=False):
    turn_id: str
    flow_id: str
    phase: str
    turn_kind: str
    role_id: str
    role_session_id: str
    source_handoff_id: str
    target_handoff_id: str
    attempt_no: int
    supervisor_decision: dict[str, Any]
    executor_agent_id: str
    judge_agent_id: str
    decision: str
    reason: str
    confidence: float
    artifact_refs: list[str]
    trace_id: str
    receipt_id: str
    started_at: str
    completed_at: str


class FlowActionReceiptV1(TypedDict, total=False):
    action_id: str
    flow_id: str
    action_type: str
    operator_id: str
    policy_source: str
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    trace_id: str
    receipt_id: str
    result_summary: str
    created_at: str


class TaskReceiptV1(TypedDict, total=False):
    receipt_id: str
    receipt_kind: str
    flow_id: str
    task_contract_id: str
    status: str
    phase: str
    attempt_no: int
    active_role_id: str
    artifact_ref: str
    decision: str
    action_type: str
    source_ref: str
    summary: str
    authority_snapshot: dict[str, Any]
    policy_snapshot: dict[str, Any]
    recovery_state: str
    payload: dict[str, Any]
    created_at: str


class RecoveryCursorV1(TypedDict, total=False):
    flow_id: str
    task_contract_id: str
    latest_accepted_receipt_id: str
    latest_artifact_ref: str
    current_phase: str
    active_role_id: str
    codex_session_id: str
    recovery_state: str
    updated_at: str


class FlowExecReceiptV1(TypedDict, total=False):
    receipt_id: str
    kind: str
    flow_id: str
    task_contract_id: str
    workflow_kind: str
    status: str
    terminal: bool
    return_code: int
    flow_dir: str
    current_phase: str
    active_role_id: str
    launch_mode: str
    catalog_flow_id: str
    execution_mode: str
    session_strategy: str
    role_pack_id: str
    execution_context: str
    execution_workspace_root: str
    task_contract_summary: dict[str, Any]
    attempt_count: int
    codex_session_id: str
    summary: str
    last_judge_decision: dict[str, Any]
    latest_supervisor_decision: dict[str, Any]
    last_codex_receipt: dict[str, Any]
    last_cursor_receipt: dict[str, Any]
    trace_refs: list[str]
    receipt_refs: list[str]
    recovery_state: str
    created_at: str


class FlowWorkspaceViewV1(TypedDict, total=False):
    flow_id: str
    workspace_root: str
    uploads_dir: str
    outputs_dir: str
    artifacts_manifest_path: str
    codex_home: str
    trace_root: str


class FlowDefinitionV1(TypedDict, total=False):
    definition_id: str
    flow_id: str
    task_contract_id: str
    task_contract_summary: dict[str, Any]
    truth_owner: str
    materialized_from_task_contract: bool
    workflow_kind: str
    entry_mode: str
    launch_mode: str
    catalog_flow_id: str
    execution_mode: str
    session_strategy: str
    role_pack_id: str
    execution_context: str
    goal: str
    guard_condition: str
    phase_plan: list[dict[str, Any]]
    risk_level: str
    autonomy_profile: str
    manager_handoff: dict[str, Any]
    role_guidance: dict[str, Any]
    doctor_policy: dict[str, Any]
    supervisor_profile: dict[str, Any]
    control_profile: dict[str, Any]
    version: str
    created_at: str
    updated_at: str


class TaskContractV1(TypedDict, total=False):
    task_contract_id: str
    flow_id: str
    goal: str
    repo_scope: dict[str, Any]
    acceptance: dict[str, Any]
    owner: dict[str, Any]
    authority: dict[str, Any]
    policy: dict[str, Any]
    execution_context: str
    source_surface: str
    truth_owner: str
    materialization: dict[str, Any]
    created_at: str
    updated_at: str


class TaskContractSummaryV1(TypedDict, total=False):
    task_contract_id: str
    goal: str
    execution_context: str
    source_surface: str
    repo_scope: dict[str, Any]
    acceptance_summary: dict[str, Any]
    owner_summary: dict[str, Any]
    authority_summary: dict[str, Any]
    policy_summary: dict[str, Any]
    responsibility_summary: dict[str, Any]
    truth_owner: str


class FlowManageSessionV1(TypedDict, total=False):
    session_id: str
    flow_id: str
    manage_target: str
    status: str
    instruction: str
    result_summary: str
    created_at: str
    updated_at: str


class FlowManageHandoffV1(TypedDict, total=False):
    handoff_id: str
    flow_id: str
    summary: str
    operator_guidance: str
    confirmation_prompt: str
    risk_level: str
    autonomy_profile: str
    created_at: str


class FlowLaunchDraftV1(TypedDict, total=False):
    launch_mode: Literal["single", "flow"]
    execution_level: Literal["simple", "medium", "high"]
    catalog_flow_id: str
    goal: str
    guard_condition: str
    max_attempts: int
    max_phase_attempts: int
    workflow_kind: str
    phase_plan: list[dict[str, Any]]
    role_pack_id: str
    execution_mode: str
    session_strategy: str


class FlowCatalogEntryV1(TypedDict, total=False):
    flow_id: str
    label: str
    description: str
    workflow_kind: str
    phase_plan: list[dict[str, Any]]
    default_role_pack: str
    allowed_execution_modes: list[str]
    role_guidance: dict[str, Any]


class FlowDesignSessionV1(TypedDict, total=False):
    flow_id: str
    designer_session_id: str
    design_stage: Literal["proposal", "build", "review", "approved"]
    design_status: Literal["drafting", "waiting_user", "needs_build_revision", "approved"]
    selected_mode: str
    selected_level: str
    source_kind: str
    active_draft_ref: str
    last_review_summary: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class PreparedFlowRun:
    cfg: dict[str, Any]
    config_path: str
    workspace_root: str
    flow_path: Path
    flow_state: dict[str, Any]
