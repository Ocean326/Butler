import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { ButlerDesktopApi } from "../shared/ipc";
import App from "./App";
import { renderDesktopApp } from "../test/render-app";

const CONFIG_PATH = "/tmp/butler/butler_bot.json";

function mockDesktopApi(overrides: Partial<ButlerDesktopApi> = {}): ButlerDesktopApi {
  return {
    getHome: vi.fn().mockResolvedValue({
      preflight: {
        workspace_root: "/tmp/butler",
        launch_mode: "shared"
      },
      flows: {
        items: [
          {
            flow_id: "flow_mock_desktop",
            goal: "Ship Butler Desktop",
            effective_status: "running",
            effective_phase: "build",
            active_role_id: "implementer"
          }
        ]
      }
    }),
    getFlow: vi.fn().mockResolvedValue({
      flow_id: "flow_mock_desktop",
      status: {},
      summary: {
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
        latest_token_usage: {},
        context_governor: {},
        latest_handoff_summary: {},
        updated_at: "2026-04-03T14:00:00Z"
      },
      step_history: [],
      timeline: [],
      turns: [],
      actions: [],
      artifacts: [],
      handoffs: [],
      flow_definition: {},
      runtime_snapshot: {},
      navigator_summary: {
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
        latest_token_usage: {},
        context_governor: {},
        latest_handoff_summary: {},
        updated_at: "2026-04-03T14:00:00Z"
      },
      supervisor_view: {
        header: {
          flow_id: "flow_mock_desktop",
          status: "running",
          phase: "build",
          active_role_id: "implementer",
          approval_state: "operator_required",
          goal: "Ship Butler Desktop"
        },
        events: [],
        latest_supervisor_decision: {},
        latest_judge_decision: {},
        latest_operator_action: {},
        latest_handoff_summary: {},
        context_governor: {},
        latest_token_usage: {},
        pointers: {
          runtime_elapsed_seconds: 312,
          max_runtime_seconds: 1800
        }
      },
      workflow_view: {
        events: [],
        runtime_summary: {},
        artifact_refs: []
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
        role_sessions: {},
        pending_handoffs: [],
        recent_handoffs: [],
        latest_handoff_summary: {},
        latest_role_handoffs: {},
        role_chips: [],
        roles: [],
        execution_mode: "medium",
        session_strategy: "role_bound",
        role_pack_id: "coding_flow"
      },
      operator_rail: {
        approval_state: "operator_required",
        latest_supervisor_decision: {},
        latest_operator_action: {},
        latest_judge_decision: {},
        promoted_events: []
      },
      flow_console: {
        flow_id: "flow_mock_desktop",
        summary: {},
        recent_steps: [],
        step_history: []
      },
      surface: {}
    }),
    getDetail: vi.fn().mockResolvedValue({}),
    getManageCenter: vi.fn().mockResolvedValue({
      preflight: {},
      assets: {
        items: [
          {
            asset_id: "desktop-shell",
            title: "Desktop Shell V1",
            status: "active",
            summary: "Electron + React workbench shell"
          }
        ]
      },
      selected_asset: {
        asset_id: "desktop-shell",
        title: "Desktop Shell V1"
      },
      role_guidance: {
        implementer: "Keep the shell flow-first."
      },
      review_checklist: ["Shell launches"],
      bundle_manifest: {
        bundle_id: "desktop-v1"
      },
      manager_notes: "Promote the shell only after bridge and payload rendering are verified."
    }),
    getPreflight: vi.fn().mockResolvedValue({}),
    performAction: vi.fn().mockResolvedValue({
      ok: true,
      action_type: "pause"
    }),
    chooseConfigPath: vi.fn().mockResolvedValue({
      canceled: false,
      configPath: CONFIG_PATH
    }),
    openArtifact: vi.fn().mockResolvedValue({
      opened: true
    }),
    ...overrides
  };
}

describe("Desktop App", () => {
  it("invokes the native config picker from the empty state", async () => {
    const api = mockDesktopApi({
      chooseConfigPath: vi.fn().mockResolvedValue({ canceled: true })
    });
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: "Select Butler Config" }));

    expect(api.chooseConfigPath).toHaveBeenCalledTimes(1);
  });

  it("attaches a config path manually and loads workspace flows", async () => {
    window.butlerDesktop = mockDesktopApi();
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.type(screen.getByLabelText("Config Path Fallback"), CONFIG_PATH);
    await user.click(screen.getByRole("button", { name: "Attach Path" }));

    await waitFor(() => {
      expect(window.butlerDesktop.getHome).toHaveBeenCalledWith({ configPath: CONFIG_PATH });
    });
    expect(await screen.findByRole("button", { name: /flow_mock_desktop/i })).toBeInTheDocument();
    expect(screen.getByText(`Config attached: ${CONFIG_PATH}`)).toBeInTheDocument();
  });

  it("triggers pause from the workbench", async () => {
    const api = mockDesktopApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);

    const flowButton = await screen.findByRole("button", { name: /flow_mock_desktop/i });
    await user.click(flowButton);
    await user.click(await screen.findByRole("button", { name: "Pause" }));

    expect(api.performAction).toHaveBeenCalledWith({
      configPath: CONFIG_PATH,
      flowId: "flow_mock_desktop",
      type: "pause",
      instruction: undefined
    });
  });

  it("renders the manage page and selected asset details", async () => {
    const api = mockDesktopApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: "Manage" }));

    expect(await screen.findByRole("heading", { name: "Assets and execution guidance" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Desktop Shell V1/i })).toBeInTheDocument();
    expect(screen.getByText(/Promote the shell only after bridge/i)).toBeInTheDocument();
  });
});
