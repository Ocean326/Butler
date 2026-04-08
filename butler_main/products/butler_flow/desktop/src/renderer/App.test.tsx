import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ButlerDesktopApi } from "../shared/ipc";
import App from "./App";
import { renderDesktopApp } from "../test/render-app";

const CONFIG_PATH = "/tmp/butler/butler_bot.json";

function mockDesktopApi(overrides: Partial<ButlerDesktopApi> = {}): ButlerDesktopApi {
  const baseSummary = {
    flow_id: "flow_mock_desktop",
    task_contract_id: "task_contract_flow_mock_desktop",
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
    latest_token_usage: {},
    context_governor: {},
    latest_handoff_summary: {
      from_role_id: "planner",
      to_role_id: "implementer",
      summary: "UI shell ready for implementation",
    },
    task_contract_summary: {
      goal: "Ship Butler Desktop",
      acceptance_summary: {
        guard_condition: "desktop launch verified",
      },
    },
    latest_receipt_summary: {
      receipt_kind: "turn_acceptance",
      summary: "Desktop shell accepted into build lane",
    },
    latest_artifact_ref: "/tmp/butler/artifacts/desktop-shell.md",
    accepted_receipt_count: 3,
    recovery_state: "resume_existing_session",
    updated_at: "2026-04-03T14:00:00Z",
  };

  return {
    getHome: vi.fn().mockResolvedValue({
      surface_meta: {
        canonical_surface: "mission_index",
        display_title: "Mission Index",
        projection_kind: "mission_index",
      },
      preflight: {
        workspace_root: "/tmp/butler",
        launch_mode: "shared",
      },
      flows: {
        items: [baseSummary],
      },
    }),
    getFlow: vi.fn().mockResolvedValue({
      flow_id: "flow_mock_desktop",
      surface_meta: {
        canonical_surface: "run_console",
        display_title: "Run Console",
        projection_kind: "run_console",
      },
      status: {},
      mission_console: {
        task_contract_id: "task_contract_flow_mock_desktop",
        goal: "Ship Butler Desktop",
      },
      task_contract_summary: baseSummary.task_contract_summary,
      latest_receipt_summary: baseSummary.latest_receipt_summary,
      latest_artifact_ref: baseSummary.latest_artifact_ref,
      accepted_receipt_count: baseSummary.accepted_receipt_count,
      recovery_state: baseSummary.recovery_state,
      recovery_cursor: {
        flow_id: "flow_mock_desktop",
        task_contract_id: "task_contract_flow_mock_desktop",
        latest_accepted_receipt_id: "receipt-7",
        latest_artifact_ref: baseSummary.latest_artifact_ref,
        current_phase: "build",
        active_role_id: "implementer",
        recovery_state: "resume_existing_session",
        updated_at: "2026-04-03T14:01:00Z",
      },
      governance_summary: {
        authority_summary: { operator: "ocean" },
        policy_summary: { repo_binding_policy: "explicit" },
      },
      summary: baseSummary,
      step_history: [],
      timeline: [],
      turns: [],
      actions: [],
      artifacts: [
        {
          artifact_ref: baseSummary.latest_artifact_ref,
          absolute_path: baseSummary.latest_artifact_ref,
          phase: "build",
        },
      ],
      handoffs: [],
      flow_definition: {},
      runtime_snapshot: {},
      navigator_summary: baseSummary,
      supervisor_view: {
        header: {
          flow_id: "flow_mock_desktop",
          status: "running",
          phase: "build",
          active_role_id: "implementer",
          approval_state: "operator_required",
          goal: "Ship Butler Desktop",
        },
        events: [
          {
            event_id: "evt-supervisor-1",
            kind: "supervisor_output",
            flow_id: "flow_mock_desktop",
            phase: "build",
            attempt_no: 2,
            created_at: "2026-04-03T14:00:30Z",
            message: "Implement desktop shell and bridge next.",
            title: "Implement desktop shell and bridge next.",
            lane: "supervisor",
            family: "output",
            raw_text: "Implement desktop shell and bridge next.",
          },
        ],
        latest_supervisor_decision: {},
        latest_judge_decision: {},
        latest_operator_action: {},
        latest_handoff_summary: baseSummary.latest_handoff_summary,
        context_governor: {},
        latest_token_usage: {},
        pointers: {
          runtime_elapsed_seconds: 312,
          max_runtime_seconds: 1800,
        },
      },
      workflow_view: {
        events: [
          {
            event_id: "evt-workflow-1",
            kind: "artifact_registered",
            flow_id: "flow_mock_desktop",
            phase: "build",
            attempt_no: 2,
            created_at: "2026-04-03T14:00:45Z",
            message: "artifact://desktop/workbench",
            title: "artifact://desktop/workbench",
            lane: "workflow",
            family: "artifact",
            raw_text: "artifact://desktop/workbench",
          },
        ],
        runtime_summary: {},
        artifact_refs: ["/tmp/butler/artifacts/desktop-shell.md"],
      },
      inspector: {
        runtime: {
          runtime_plan: {
            plan_stage: "implementation",
            summary: "Desktop shell and bridge are in progress.",
          },
        },
      },
      role_strip: {
        active_role_id: "implementer",
        role_sessions: {},
        pending_handoffs: [],
        recent_handoffs: [],
        latest_handoff_summary: baseSummary.latest_handoff_summary,
        latest_role_handoffs: {},
        role_chips: [],
        roles: [],
        execution_mode: "medium",
        session_strategy: "role_bound",
        role_pack_id: "coding_flow",
      },
      operator_rail: {
        approval_state: "operator_required",
        latest_supervisor_decision: {},
        latest_operator_action: {},
        latest_judge_decision: {},
        promoted_events: [],
      },
      flow_console: {
        flow_id: "flow_mock_desktop",
        summary: baseSummary,
        recent_steps: [],
        step_history: [],
      },
      surface: {},
    }),
    getDetail: vi.fn().mockResolvedValue({}),
    getManageCenter: vi.fn().mockResolvedValue({
      surface_meta: {
        canonical_surface: "contract_studio",
        display_title: "Contract Studio",
        projection_kind: "contract_studio",
      },
      preflight: {},
      assets: {
        items: [
          {
            asset_id: "desktop-shell",
            title: "Desktop Shell V1",
            status: "active",
            summary: "Electron + React mission console shell",
          },
        ],
      },
      selected_asset: {
        asset_id: "desktop-shell",
        title: "Desktop Shell V1",
      },
      contract_studio: {
        asset_key: "template:desktop-shell",
        projection_kind: "contract_studio",
      },
      role_guidance: {
        implementer: "Keep the run console contract-first.",
      },
      review_checklist: ["Shell launches"],
      bundle_manifest: {
        bundle_id: "desktop-v1",
      },
      manager_notes: "Promote the shell only after bridge and payload rendering are verified.",
    }),
    getPreflight: vi.fn().mockResolvedValue({}),
    performAction: vi.fn().mockResolvedValue({
      ok: true,
      action_type: "pause",
    }),
    chooseConfigPath: vi.fn().mockResolvedValue({
      canceled: false,
      configPath: CONFIG_PATH,
    }),
    openArtifact: vi.fn().mockResolvedValue({
      opened: true,
    }),
    ...overrides,
  };
}

describe("Desktop App", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("invokes the native config picker from the empty state", async () => {
    const api = mockDesktopApi({
      chooseConfigPath: vi.fn().mockResolvedValue({ canceled: true }),
    });
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: "Select Butler Config" }));

    expect(api.chooseConfigPath).toHaveBeenCalledTimes(1);
  });

  it("attaches a config path manually and loads mission threads", async () => {
    window.butlerDesktop = mockDesktopApi();
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.type(screen.getByLabelText("Config Path Fallback"), CONFIG_PATH);
    await user.click(screen.getByRole("button", { name: "Attach Path" }));

    await waitFor(() => {
      expect(window.butlerDesktop.getHome).toHaveBeenCalledWith({ configPath: CONFIG_PATH });
    });
    expect(await screen.findByRole("button", { name: /Ship Butler Desktop/i })).toBeInTheDocument();
    expect(screen.getByText(`Config attached: ${CONFIG_PATH}`)).toBeInTheDocument();
  });

  it("opens the manager thread and can trigger pause", async () => {
    const api = mockDesktopApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);

    const threadButton = await screen.findByRole("button", { name: /Ship Butler Desktop/i });
    await user.click(threadButton);
    expect(await screen.findByRole("button", { name: "Pause" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Pause" }));

    expect(api.performAction).toHaveBeenCalledWith({
      configPath: CONFIG_PATH,
      flowId: "flow_mock_desktop",
      type: "pause",
      instruction: undefined,
    });
  });

  it("switches into the studio lens inside the same manager thread", async () => {
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = mockDesktopApi();
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(await screen.findByRole("button", { name: /Ship Butler Desktop/i }));
    await user.click(screen.getByRole("button", { name: "Studio" }));

    expect((await screen.findAllByText("Desktop Shell V1")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Promote the shell only after bridge and payload rendering are verified/i).length).toBeGreaterThan(0);
  });

  it("opens the supervisor drilldown stream from the main conversation", async () => {
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = mockDesktopApi();
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(await screen.findByRole("button", { name: /Ship Butler Desktop/i }));
    await user.click(screen.getByRole("button", { name: "Open Supervisor stream" }));

    expect(await screen.findByRole("heading", { name: "Supervisor stream" })).toBeInTheDocument();
    expect(screen.getAllByText(/Implement desktop shell and bridge next/i).length).toBeGreaterThan(0);
  });
});
