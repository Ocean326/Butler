import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { ButlerDesktopApi } from "../shared/ipc";
import App from "./App";
import { renderDesktopApp } from "../test/render-app";

const CONFIG_PATH = "/tmp/butler/butler_bot.json";

function buildApi(overrides: Partial<ButlerDesktopApi> = {}): ButlerDesktopApi {
  return {
    getHome: vi.fn().mockResolvedValue({ preflight: {}, flows: { items: [] } }),
    getFlow: vi.fn().mockResolvedValue({
      flow_id: "flow_mock_desktop",
      status: {},
      summary: {},
      step_history: [],
      timeline: [],
      turns: [],
      actions: [],
      artifacts: [],
      handoffs: [],
      flow_definition: {},
      runtime_snapshot: {},
      navigator_summary: {},
      supervisor_view: {},
      workflow_view: {},
      inspector: {},
      role_strip: {
        active_role_id: "",
        role_sessions: {},
        pending_handoffs: [],
        recent_handoffs: [],
        latest_handoff_summary: {},
        latest_role_handoffs: {},
        role_chips: [],
        roles: [],
        execution_mode: "",
        session_strategy: "",
        role_pack_id: ""
      },
      operator_rail: {},
      flow_console: {},
      surface: {}
    }),
    getDetail: vi.fn().mockResolvedValue({}),
    getManageCenter: vi.fn().mockResolvedValue({
      preflight: {},
      assets: { items: [] },
      selected_asset: {},
      role_guidance: {},
      review_checklist: [],
      bundle_manifest: {},
      manager_notes: ""
    }),
    getPreflight: vi.fn().mockResolvedValue({}),
    getThreadHome: vi.fn().mockResolvedValue({
      preflight: {
        workspace_root: "/tmp/butler",
        config_path: CONFIG_PATH
      },
      manager_entry: {
        default_manager_session_id: "manager-session-1",
        draft_summary: "先由 Manager 对齐需求",
        status: "active",
        title: "Manager 管理台",
        total_sessions: 1,
        active_flow_id: "flow_mock_desktop",
        active_thread_id: "manager:manager-session-1"
      },
      history: [
        {
          thread_id: "manager:manager-session-1",
          thread_kind: "manager",
          title: "Desktop 线程工作台",
          subtitle: "Manager 默认入口",
          status: "active",
          created_at: "2026-04-05 13:00:00",
          updated_at: "2026-04-05 14:00:00",
          manager_session_id: "manager-session-1",
          flow_id: "flow_mock_desktop",
          active_role_id: "",
          current_phase: "requirements",
          badge: "flow_create",
          tags: ["managed_flow"]
        },
        {
          thread_id: "flow:flow_mock_desktop",
          thread_kind: "supervisor",
          title: "Butler Flow Desktop",
          subtitle: "Supervisor 正在推进 renderer",
          status: "running",
          created_at: "2026-04-05 13:30:00",
          updated_at: "2026-04-05 14:00:00",
          manager_session_id: "manager-session-1",
          flow_id: "flow_mock_desktop",
          active_role_id: "implementer",
          current_phase: "implement",
          badge: "operator_required",
          tags: ["managed_flow"]
        }
      ],
      templates: [
        {
          thread_id: "template:desktop-template",
          thread_kind: "template",
          title: "Desktop Shell Template",
          subtitle: "Template + agent team",
          status: "active",
          created_at: "",
          updated_at: "2026-04-05 11:00:00",
          manager_session_id: "",
          flow_id: "",
          active_role_id: "",
          current_phase: "",
          badge: "template",
          tags: ["managed_flow"]
        }
      ]
    }),
    getManagerThread: vi.fn().mockResolvedValue({
      thread: {
        thread_id: "manager:manager-session-1",
        thread_kind: "manager",
        title: "Desktop 线程工作台",
        subtitle: "先对齐 idea，再进入 Supervisor。",
        status: "active",
        created_at: "2026-04-05 13:00:00",
        updated_at: "2026-04-05 14:00:00",
        manager_session_id: "manager-session-1",
        flow_id: "flow_mock_desktop",
        active_role_id: "",
        current_phase: "requirements",
        badge: "flow_create",
        tags: ["managed_flow"]
      },
      manager_session_id: "manager-session-1",
      manage_target: "instance:flow_mock_desktop",
      active_manage_target: "instance:flow_mock_desktop",
      manager_stage: "requirements",
      confirmation_scope: "",
      blocks: [
        {
          block_id: "manager-idea",
          kind: "idea",
          title: "Idea 草案",
          summary: "线程化单流 Desktop shell。",
          created_at: "2026-04-05 13:12:00",
          status: "active",
          expanded_by_default: true,
          payload: {
            response: "先做 thread-first IA。"
          }
        }
      ],
      draft: {},
      pending_action: {},
      latest_response: "先做 thread-first IA。",
      linked_flow_id: "flow_mock_desktop"
    }),
    getSupervisorThread: vi.fn().mockResolvedValue({
      thread: {
        thread_id: "flow:flow_mock_desktop",
        thread_kind: "supervisor",
        title: "Butler Flow Desktop",
        subtitle: "Supervisor 正在推进 renderer",
        status: "running",
        created_at: "2026-04-05 13:30:00",
        updated_at: "2026-04-05 14:00:00",
        manager_session_id: "manager-session-1",
        flow_id: "flow_mock_desktop",
        active_role_id: "implementer",
        current_phase: "implement",
        badge: "operator_required",
        tags: ["managed_flow"]
      },
      flow_id: "flow_mock_desktop",
      summary: {
        flow_id: "flow_mock_desktop",
        label: "Butler Flow Desktop",
        workflow_kind: "managed_flow",
        effective_status: "running",
        effective_phase: "implement",
        attempt_count: 1,
        max_attempts: 8,
        max_phase_attempts: 4,
        max_runtime_seconds: 1800,
        runtime_elapsed_seconds: 120,
        goal: "Ship thread-first desktop",
        guard_condition: "verified",
        approval_state: "operator_required",
        execution_mode: "medium",
        session_strategy: "role_bound",
        active_role_id: "implementer",
        role_pack_id: "coding_flow",
        last_judge: "ADVANCE",
        latest_judge_decision: {},
        last_operator_action: "",
        latest_operator_action: {},
        queued_operator_updates: [],
        latest_token_usage: {},
        context_governor: {},
        latest_handoff_summary: {},
        updated_at: "2026-04-05 14:00:00"
      },
      blocks: [
        {
          block_id: "supervisor-decision",
          kind: "decision",
          title: "实现 thread-first renderer",
          summary: "先改 shared surface，再换 UI。",
          created_at: "2026-04-05 13:40:00",
          status: "decision",
          expanded_by_default: true,
          payload: {},
          role_id: "implementer",
          action_label: "Open Agent",
          action_target: "role:implementer",
          tags: ["supervisor"]
        }
      ],
      role_strip: {
        active_role_id: "implementer",
        role_sessions: {},
        pending_handoffs: [],
        recent_handoffs: [],
        latest_handoff_summary: {},
        latest_role_handoffs: {},
        role_chips: [
          { role_id: "implementer", state: "active", is_active: true },
          { role_id: "reviewer", state: "receiving_handoff", is_active: false }
        ],
        roles: [],
        execution_mode: "medium",
        session_strategy: "role_bound",
        role_pack_id: "coding_flow"
      },
      operator_rail: {},
      latest_handoff: {}
    }),
    getAgentFocus: vi.fn().mockResolvedValue({
      thread: {
        thread_id: "agent:flow_mock_desktop:implementer",
        thread_kind: "agent",
        title: "implementer",
        subtitle: "Agent focus stream",
        status: "running",
        created_at: "2026-04-05 13:45:00",
        updated_at: "2026-04-05 14:00:00",
        manager_session_id: "manager-session-1",
        flow_id: "flow_mock_desktop",
        active_role_id: "implementer",
        current_phase: "implement",
        badge: "active",
        tags: ["managed_flow"]
      },
      flow_id: "flow_mock_desktop",
      role_id: "implementer",
      title: "implementer · focus",
      summary: {
        flow_id: "flow_mock_desktop",
        label: "Butler Flow Desktop",
        workflow_kind: "managed_flow",
        effective_status: "running",
        effective_phase: "implement",
        attempt_count: 1,
        max_attempts: 8,
        max_phase_attempts: 4,
        max_runtime_seconds: 1800,
        runtime_elapsed_seconds: 120,
        goal: "Ship thread-first desktop",
        guard_condition: "verified",
        approval_state: "operator_required",
        execution_mode: "medium",
        session_strategy: "role_bound",
        active_role_id: "implementer",
        role_pack_id: "coding_flow",
        last_judge: "ADVANCE",
        latest_judge_decision: {},
        last_operator_action: "",
        latest_operator_action: {},
        queued_operator_updates: [],
        latest_token_usage: {},
        context_governor: {},
        latest_handoff_summary: {},
        updated_at: "2026-04-05 14:00:00"
      },
      blocks: [
        {
          block_id: "agent-progress",
          kind: "progress",
          title: "Progress 更新",
          summary: "thread API 已接线。",
          created_at: "2026-04-05 13:50:00",
          status: "progress",
          expanded_by_default: true,
          payload: {}
        }
      ],
      role: {
        role_id: "implementer",
        state: "active"
      },
      related_handoffs: [],
      artifacts: []
    }),
    getTemplateTeam: vi.fn().mockResolvedValue({
      thread: {
        thread_id: "template:desktop-template",
        thread_kind: "template",
        title: "Desktop Shell Template",
        subtitle: "Template + agent team",
        status: "active",
        created_at: "2026-04-05 11:00:00",
        updated_at: "2026-04-05 14:00:00",
        manager_session_id: "",
        flow_id: "",
        active_role_id: "",
        current_phase: "",
        badge: "template",
        tags: ["managed_flow"]
      },
      asset_id: "desktop-template",
      blocks: [
        {
          block_id: "template-overview",
          kind: "overview",
          title: "Templates / Team",
          summary: "管理模板与默认 team。",
          created_at: "2026-04-05 11:00:00",
          status: "active",
          expanded_by_default: true,
          payload: {}
        }
      ],
      assets: [{ asset_id: "desktop-template", label: "Desktop Shell Template" }],
      selected_asset: { asset_id: "desktop-template", label: "Desktop Shell Template" },
      role_guidance: {},
      review_checklist: ["single-stream"],
      bundle_manifest: {},
      manager_notes: "先固定 thread contract。"
    }),
    sendManagerMessage: vi.fn().mockResolvedValue({
      ok: true,
      manager_session_id: "manager-session-1",
      message: { response: "Flow 已创建，切到 Supervisor。" },
      thread: {
        thread: {
          thread_id: "manager:manager-session-1",
          thread_kind: "manager",
          title: "Desktop 线程工作台",
          subtitle: "Manager 默认入口",
          status: "active",
          created_at: "2026-04-05 13:00:00",
          updated_at: "2026-04-05 14:00:00",
          manager_session_id: "manager-session-1",
          flow_id: "",
          active_role_id: "",
          current_phase: "launch",
          badge: "flow_create",
          tags: ["managed_flow"]
        },
        manager_session_id: "manager-session-1",
        manage_target: "instance:flow_mock_desktop",
        active_manage_target: "instance:flow_mock_desktop",
        manager_stage: "launch",
        confirmation_scope: "",
        blocks: [],
        draft: {},
        pending_action: {},
        latest_response: "Flow 已创建，切到 Supervisor。",
        linked_flow_id: "flow_mock_desktop"
      },
      launched_flow: { flow_id: "flow_mock_desktop" }
    }),
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
  it("renders a bridge-missing state instead of throwing preload errors", async () => {
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    Object.defineProperty(window, "butlerDesktop", {
      value: undefined,
      configurable: true,
      writable: true
    });

    renderDesktopApp(<App />);

    expect(await screen.findByRole("heading", { name: "Desktop bridge 未连接" })).toBeInTheDocument();
    expect(screen.queryByText(/Manager thread load failed/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Manager message failed/i)).not.toBeInTheDocument();
  });

  it("invokes the native config picker from the empty state", async () => {
    const api = buildApi({
      chooseConfigPath: vi.fn().mockResolvedValue({ canceled: true })
    });
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: /选择 config/i }));

    expect(api.chooseConfigPath).toHaveBeenCalledTimes(1);
  });

  it("attaches a config path manually and renders manager as the default page", async () => {
    const api = buildApi();
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.type(screen.getByLabelText("Config Path Fallback"), CONFIG_PATH);
    await user.click(screen.getByRole("button", { name: "Attach Path" }));

    await waitFor(() => {
      expect(api.getThreadHome).toHaveBeenCalledWith({ configPath: CONFIG_PATH });
    });
    expect(await screen.findByRole("heading", { name: "Desktop 线程工作台" })).toBeInTheDocument();
    expect(screen.getByText(`Config attached: ${CONFIG_PATH}`)).toBeInTheDocument();
    expect(document.querySelector(".manager-surface")).toBeInTheDocument();
    expect(document.querySelector(".manager-dock")).toBeInTheDocument();
  });

  it("renders the manager composer as a dock after the thread stream", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;

    renderDesktopApp(<App />);

    const surface = await waitFor(() => {
      const node = document.querySelector(".manager-surface");
      expect(node).toBeTruthy();
      return node as HTMLElement;
    });
    const dock = await waitFor(() => {
      const node = document.querySelector(".manager-dock");
      expect(node).toBeTruthy();
      return node as HTMLElement;
    });

    expect(surface.lastElementChild).toBe(dock);
    expect(dock.closest(".thread-stream-panel")).toBeNull();
  });

  it("caps manager composer growth to one third of the viewport", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();
    const originalInnerHeight = window.innerHeight;

    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 900
    });

    renderDesktopApp(<App />);

    const textarea = (await screen.findByLabelText("Continue with Manager")) as HTMLTextAreaElement;
    Object.defineProperty(textarea, "scrollHeight", {
      configurable: true,
      get: () => 1200
    });

    await user.type(textarea, "需要一段会把 manager composer 顶到上限的长文本。");

    await waitFor(() => {
      expect(textarea.style.height).toBe("300px");
      expect(textarea.style.overflowY).toBe("auto");
    });

    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: originalInnerHeight
    });
  });

  it("opens a blank manager thread from New Flow and sends the first prompt with manageTarget=new", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: /new flow 新建/i }));
    expect(await screen.findByRole("heading", { name: "新建 Flow" })).toBeInTheDocument();

    await user.type(await screen.findByLabelText("Start with Manager"), "从空白 manager thread 开始");
    await user.click(screen.getByRole("button", { name: /send to manager/i }));

    await waitFor(() => {
      expect(api.sendManagerMessage).toHaveBeenCalledWith({
        configPath: CONFIG_PATH,
        instruction: "从空白 manager thread 开始",
        managerSessionId: "",
        manageTarget: "new"
      });
    });
  });

  it("sends a manager message and jumps into supervisor when flow is launched", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.type(
      await screen.findByLabelText("Continue with Manager"),
      "请把当前方案创建成 flow，并启动 supervisor"
    );
    await user.click(screen.getByRole("button", { name: /send to manager/i }));

    await waitFor(() => {
      expect(api.sendManagerMessage).toHaveBeenCalledWith({
        configPath: CONFIG_PATH,
        instruction: "请把当前方案创建成 flow，并启动 supervisor",
        managerSessionId: "manager-session-1",
        manageTarget: undefined
      });
    });
    expect(await screen.findByRole("heading", { name: "Butler Flow Desktop" })).toBeInTheDocument();
  });

  it("opens templates from the rail", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: /templates 模板/i }));

    expect(await screen.findByRole("heading", { name: "Desktop Shell Template" })).toBeInTheDocument();
    expect(screen.getByText("管理模板与默认 team。")).toBeInTheDocument();
  });

  it("opens history as a Butler-native project thread list", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: /threads 历史/i }));

    expect(await screen.findByRole("heading", { name: "Project Threads" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Desktop 线程工作台/i })).not.toHaveLength(0);
    expect(screen.getAllByRole("button", { name: /Butler Flow Desktop/i })).not.toHaveLength(0);
  });

  it("opens launched manager history rows as manager threads even when they carry flow ids", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: /threads 历史/i }));
    const flowButtons = screen.getAllByRole("button", { name: /Butler Flow Desktop/i });
    await user.click(flowButtons[flowButtons.length - 1]);
    expect(await screen.findByRole("heading", { name: "Butler Flow Desktop" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /threads 历史/i }));
    const managerButtons = screen.getAllByRole("button", { name: /Desktop 线程工作台/i });
    await user.click(managerButtons[managerButtons.length - 1]);

    expect(await screen.findByRole("heading", { name: "Desktop 线程工作台" })).toBeInTheDocument();
    await waitFor(() => {
      expect(api.getManagerThread).toHaveBeenCalledWith({
        configPath: CONFIG_PATH,
        managerSessionId: "manager-session-1"
      });
    });
  });

  it("enters agent focus from supervisor role chips", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(await screen.findByRole("button", { name: /Butler Flow Desktop/i }));
    const implementerButtons = await screen.findAllByRole("button", { name: /implementer/i });
    await user.click(implementerButtons[implementerButtons.length - 1]);

    expect(await screen.findByRole("heading", { name: "implementer · focus" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back to supervisor/i })).toBeInTheDocument();
  });

  it("toggles theme and persists the latest choice", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: "Day" }));

    expect(window.localStorage.getItem("butler.desktop.theme")).toBe("day");
    expect(document.querySelector(".desktop-root")).toHaveAttribute("data-theme", "day");
    expect(screen.getByRole("button", { name: "Night" })).toBeInTheDocument();
  });

  it("keeps manager context aligned when opening a supervisor thread from history", async () => {
    const alternateManagerSessionId = "manager-session-2";
    const alternateFlowId = "flow_visual_refresh";
    const alternateManagerTitle = "视觉升级 Manager 线程";
    const alternateSupervisorTitle = "Visual Refresh Flow";

    const api = buildApi({
      getThreadHome: vi.fn().mockResolvedValue({
        preflight: {
          workspace_root: "/tmp/butler",
          config_path: CONFIG_PATH
        },
        manager_entry: {
          default_manager_session_id: "manager-session-1",
          draft_summary: "先由 Manager 对齐需求",
          status: "active",
          title: "Manager 管理台",
          total_sessions: 2,
          active_flow_id: "flow_mock_desktop",
          active_thread_id: "manager:manager-session-1"
        },
        history: [
          {
            thread_id: "manager:manager-session-1",
            thread_kind: "manager",
            title: "Desktop 线程工作台",
            subtitle: "Manager 默认入口",
            status: "active",
            created_at: "2026-04-05 13:00:00",
            updated_at: "2026-04-05 14:00:00",
            manager_session_id: "manager-session-1",
            flow_id: "",
            active_role_id: "",
            current_phase: "requirements",
            badge: "flow_create",
            tags: ["managed_flow"]
          },
          {
            thread_id: `manager:${alternateManagerSessionId}`,
            thread_kind: "manager",
            title: alternateManagerTitle,
            subtitle: "另一个 manager thread",
            status: "active",
            created_at: "2026-04-05 12:00:00",
            updated_at: "2026-04-05 15:00:00",
            manager_session_id: alternateManagerSessionId,
            flow_id: "",
            active_role_id: "",
            current_phase: "delivery",
            badge: "managed_flow",
            tags: ["managed_flow"]
          },
          {
            thread_id: `flow:${alternateFlowId}`,
            thread_kind: "supervisor",
            title: alternateSupervisorTitle,
            subtitle: "Supervisor for the visual refresh",
            status: "running",
            created_at: "2026-04-05 12:30:00",
            updated_at: "2026-04-05 15:00:00",
            manager_session_id: alternateManagerSessionId,
            flow_id: alternateFlowId,
            active_role_id: "implementer",
            current_phase: "implement",
            badge: "operator_required",
            tags: ["managed_flow"]
          }
        ],
        templates: []
      }),
      getManagerThread: vi.fn().mockImplementation(({ managerSessionId }) => {
        if (managerSessionId === alternateManagerSessionId) {
          return Promise.resolve({
            thread: {
              thread_id: `manager:${alternateManagerSessionId}`,
              thread_kind: "manager",
              title: alternateManagerTitle,
              subtitle: "另一个 manager thread",
              status: "active",
              created_at: "2026-04-05 12:00:00",
              updated_at: "2026-04-05 15:00:00",
              manager_session_id: alternateManagerSessionId,
              flow_id: alternateFlowId,
              active_role_id: "",
              current_phase: "delivery",
              badge: "managed_flow",
              tags: ["managed_flow"]
            },
            manager_session_id: alternateManagerSessionId,
            manage_target: `instance:${alternateFlowId}`,
            active_manage_target: `instance:${alternateFlowId}`,
            manager_stage: "delivery",
            confirmation_scope: "",
            blocks: [
              {
                block_id: "manager-alt",
                kind: "requirements",
                title: "视觉升级要求",
                summary: "确保 history -> supervisor -> manager 仍对回原来的上下文。",
                created_at: "2026-04-05 12:05:00",
                status: "active",
                expanded_by_default: true,
                payload: {}
              }
            ],
            draft: {},
            pending_action: {},
            latest_response: "继续视觉升级。",
            linked_flow_id: alternateFlowId
          });
        }
        return buildApi().getManagerThread({ managerSessionId });
      }),
      getSupervisorThread: vi.fn().mockImplementation(({ flowId }) => {
        if (flowId === alternateFlowId) {
          return Promise.resolve({
            thread: {
              thread_id: `flow:${alternateFlowId}`,
              thread_kind: "supervisor",
              title: alternateSupervisorTitle,
              subtitle: "Supervisor for the visual refresh",
              status: "running",
              created_at: "2026-04-05 12:30:00",
              updated_at: "2026-04-05 15:00:00",
              manager_session_id: alternateManagerSessionId,
              flow_id: alternateFlowId,
              active_role_id: "implementer",
              current_phase: "implement",
              badge: "operator_required",
              tags: ["managed_flow"]
            },
            flow_id: alternateFlowId,
            summary: {
              flow_id: alternateFlowId,
              label: alternateSupervisorTitle,
              workflow_kind: "managed_flow",
              effective_status: "running",
              effective_phase: "implement",
              attempt_count: 1,
              max_attempts: 8,
              max_phase_attempts: 4,
              max_runtime_seconds: 1800,
              runtime_elapsed_seconds: 120,
              goal: "Ship the visual refresh",
              guard_condition: "verified",
              approval_state: "operator_required",
              execution_mode: "medium",
              session_strategy: "role_bound",
              active_role_id: "implementer",
              role_pack_id: "coding_flow",
              last_judge: "ADVANCE",
              latest_judge_decision: {},
              last_operator_action: "",
              latest_operator_action: {},
              queued_operator_updates: [],
              latest_token_usage: {},
              context_governor: {},
              latest_handoff_summary: {},
              updated_at: "2026-04-05 15:00:00"
            },
            blocks: [],
            role_strip: {
              active_role_id: "implementer",
              role_sessions: {},
              pending_handoffs: [],
              recent_handoffs: [],
              latest_handoff_summary: {},
              latest_role_handoffs: {},
              role_chips: [{ role_id: "implementer", state: "active", is_active: true }],
              roles: [],
              execution_mode: "medium",
              session_strategy: "role_bound",
              role_pack_id: "coding_flow"
            },
            operator_rail: {},
            latest_handoff: {}
          });
        }
        return buildApi().getSupervisorThread({ flowId });
      })
    });
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: /threads 历史/i }));
    const flowButtons = screen.getAllByRole("button", { name: /visual refresh flow/i });
    await user.click(flowButtons[flowButtons.length - 1]);
    expect(await screen.findByRole("heading", { name: alternateSupervisorTitle })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /manager 管理台/i }));
    expect(await screen.findByRole("heading", { name: alternateManagerTitle })).toBeInTheDocument();
  });
});
