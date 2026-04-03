import type {
  DesktopActionPayload,
  ManageCenterDTO,
  SingleFlowPayload,
  WorkspacePayload
} from "../../shared/dto";

const now = "2026-04-03T14:00:00Z";

export class MockFlowWorkbenchAdapter {
  async getHome(): Promise<WorkspacePayload> {
    return {
      preflight: {
        workspace_root: "/tmp/butler-demo",
        config_path: "/tmp/butler-demo/config.json"
      },
      flows: {
        items: [
          {
            flow_id: "flow_mock_desktop",
            workflow_kind: "managed_flow",
            effective_status: "running",
            effective_phase: "build",
            goal: "Ship Butler Desktop",
            approval_state: "operator_required",
            active_role_id: "implementer",
            execution_mode: "medium",
            session_strategy: "role_bound",
            updated_at: now
          }
        ]
      }
    };
  }

  async getFlow(): Promise<SingleFlowPayload> {
    const summary = {
      flow_id: "flow_mock_desktop",
      workflow_kind: "managed_flow",
      effective_status: "running",
      effective_phase: "build",
      attempt_count: 2,
      max_attempts: 8,
      max_phase_attempts: 4,
      max_runtime_seconds: 1800,
      runtime_elapsed_seconds: 312,
      goal: "Ship Butler Desktop",
      guard_condition: "desktop launch verified",
      approval_state: "operator_required",
      execution_mode: "medium",
      session_strategy: "role_bound",
      active_role_id: "implementer",
      role_pack_id: "coding_flow",
      last_judge: "ADVANCE",
      latest_judge_decision: { decision: "ADVANCE" },
      last_operator_action: "append_instruction",
      latest_operator_action: { action_type: "append_instruction" },
      queued_operator_updates: [],
      latest_token_usage: { input_tokens: 2221, output_tokens: 861 },
      context_governor: { mode: "balanced" },
      latest_handoff_summary: {
        handoff_id: "handoff-7",
        from_role_id: "planner",
        to_role_id: "implementer",
        summary: "UI shell ready for implementation"
      },
      updated_at: now
    };
    return {
      flow_id: "flow_mock_desktop",
      status: { flow_id: "flow_mock_desktop" },
      summary,
      step_history: [
        { step_id: "plan-1", phase: "plan", decision: "ADVANCE", summary: "layout locked", created_at: now },
        { step_id: "build-2", phase: "build", decision: "RUNNING", summary: "renderer shell active", created_at: now }
      ],
      timeline: [],
      turns: [],
      actions: [],
      artifacts: [{ artifact_ref: "artifact://desktop/workbench", title: "Desktop shell" }],
      handoffs: [],
      flow_definition: {},
      runtime_snapshot: {},
      navigator_summary: summary,
      supervisor_view: {
        header: {
          flow_id: "flow_mock_desktop",
          status: "running",
          phase: "build",
          active_role_id: "implementer",
          approval_state: "operator_required"
        },
        events: [
          {
            event_id: "evt-supervisor-1",
            kind: "supervisor_output",
            flow_id: "flow_mock_desktop",
            phase: "build",
            attempt_no: 2,
            created_at: now,
            message: "Implement desktop shell and bridge next.",
            lane: "supervisor",
            family: "output",
            title: "Implement desktop shell and bridge next.",
            raw_text: ""
          }
        ],
        latest_supervisor_decision: { decision: "continue", next_action: "implement" },
        latest_judge_decision: { decision: "ADVANCE" },
        latest_operator_action: { action_type: "append_instruction" },
        latest_handoff_summary: summary.latest_handoff_summary,
        context_governor: { mode: "balanced" },
        latest_token_usage: { input_tokens: 2221, output_tokens: 861 },
        pointers: {
          approval_state: "operator_required",
          runtime_elapsed_seconds: 312,
          max_runtime_seconds: 1800,
          latest_handoff_summary: summary.latest_handoff_summary
        }
      },
      workflow_view: {
        events: [
          {
            event_id: "evt-workflow-1",
            kind: "artifact_registered",
            flow_id: "flow_mock_desktop",
            phase: "build",
            attempt_no: 2,
            created_at: now,
            message: "artifact://desktop/workbench",
            lane: "workflow",
            family: "artifact",
            title: "artifact://desktop/workbench",
            raw_text: ""
          }
        ],
        runtime_summary: { process_state: "running" },
        artifact_refs: ["artifact://desktop/workbench"]
      },
      inspector: {
        runtime: {
          runtime_plan: {
            plan_stage: "implementation",
            summary: "Desktop shell and bridge are in progress."
          }
        }
      },
      role_strip: {
        active_role_id: "implementer",
        role_sessions: {
          planner: { session_id: "sess-1" },
          implementer: { session_id: "sess-2" }
        },
        pending_handoffs: [],
        recent_handoffs: [],
        latest_handoff_summary: summary.latest_handoff_summary,
        latest_role_handoffs: {},
        role_chips: [
          { role_id: "planner", state: "idle", is_active: false },
          { role_id: "implementer", state: "active", is_active: true }
        ],
        roles: [
          { role_id: "planner", session_id: "sess-1", state: "idle", is_active: false },
          { role_id: "implementer", session_id: "sess-2", state: "active", is_active: true }
        ],
        execution_mode: "medium",
        session_strategy: "role_bound",
        role_pack_id: "coding_flow"
      },
      operator_rail: {
        approval_state: "operator_required",
        latest_supervisor_decision: { decision: "continue" },
        latest_operator_action: { action_type: "append_instruction" },
        latest_judge_decision: { decision: "ADVANCE" },
        promoted_events: []
      },
      flow_console: {
        flow_id: "flow_mock_desktop",
        summary,
        recent_steps: [{ phase: "build", summary: "renderer shell active" }],
        step_history: [
          { phase: "plan", summary: "layout locked" },
          { phase: "build", summary: "renderer shell active" }
        ]
      },
      surface: {}
    };
  }

  async getDetail(): Promise<Record<string, unknown>> {
    const flow = await this.getFlow();
    return {
      flow_id: flow.flow_id,
      plan: { flow_definition: {} },
      artifacts: flow.artifacts
    };
  }

  async getManageCenter(): Promise<ManageCenterDTO> {
    return {
      preflight: { config_path: "/tmp/butler-demo/config.json" },
      assets: {
        items: [
          {
            asset_id: "desktop-shell",
            title: "Desktop Shell V1",
            status: "active"
          }
        ]
      },
      selected_asset: {
        asset_id: "desktop-shell",
        title: "Desktop Shell V1",
        synopsis: "Electron + React workbench shell"
      },
      role_guidance: {
        planner: "Keep the workbench flow-first.",
        implementer: "Preserve Python bridge as source of truth."
      },
      review_checklist: ["Shell launches", "Bridge responds", "Details drawer reads artifacts"],
      bundle_manifest: {
        bundle_id: "desktop-v1"
      },
      manager_notes: "Promote the shell only after bridge and real payloads render cleanly."
    };
  }

  async getPreflight(): Promise<Record<string, unknown>> {
    return {
      workspace_root: "/tmp/butler-demo",
      config_path: "/tmp/butler-demo/config.json",
      provider_state: "mock"
    };
  }

  async performAction(payload: DesktopActionPayload): Promise<Record<string, unknown>> {
    return {
      ok: true,
      receipt_id: "mock-action-1",
      action_type: payload.type,
      flow_id: payload.flowId
    };
  }
}
