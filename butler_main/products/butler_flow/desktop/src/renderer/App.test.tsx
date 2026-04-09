import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { ButlerDesktopApi, ManagerMessageStreamListener } from "../shared/ipc";
import App from "./App";
import { renderDesktopApp } from "../test/render-app";

const CONFIG_PATH = "/tmp/butler/butler_bot.json";
const DEFAULT_CONFIG_PATH = "/Users/ocean/Documents/Playground/SuperButler/butler_main/butler_bot_code/configs/butler_bot.json";

function buildManagerThread(managerSessionId = "manager-session-1", flowId = "flow_mock_desktop") {
  return {
    thread: {
      thread_id: `manager:${managerSessionId}`,
      thread_kind: "manager",
      title: managerSessionId === "manager-session-1" ? "Desktop 线程工作台" : "视觉升级 Manager 线程",
      subtitle: managerSessionId === "manager-session-1" ? "先对齐骨架，再继续增量生长。" : "另一个 manager thread。",
      status: "active",
      created_at: "2026-04-05 13:00:00",
      updated_at: "2026-04-05 14:00:00",
      manager_session_id: managerSessionId,
      flow_id: flowId,
      active_role_id: "",
      current_phase: "requirements",
      badge: "flow_create",
      tags: ["managed_flow"]
    },
    manager_session_id: managerSessionId,
    manage_target: `instance:${flowId}`,
    active_manage_target: `instance:${flowId}`,
    manager_stage: "requirements",
    confirmation_scope: "",
    blocks: [
      {
        block_id: `${managerSessionId}:idea`,
        kind: "idea",
        title: "Idea 草案",
        summary: "先把桌面端的第一层骨架搭起来。",
        created_at: "2026-04-05 13:12:00",
        status: "active",
        expanded_by_default: true,
        payload: {
          instruction: "先搭 Manager conversation shell",
          response: "先把左 rail 和右侧主对话收住。"
        }
      }
    ],
    draft: {},
    pending_action: {},
    latest_response: "先把左 rail 和右侧主对话收住。",
    linked_flow_id: flowId
  };
}

function buildApi(): ButlerDesktopApi {
  const listeners = new Set<ManagerMessageStreamListener>();
  let requestCounter = 0;
  const managerThreads = new Map([
    ["manager-session-1", buildManagerThread("manager-session-1", "flow_mock_desktop")],
    ["manager-session-2", buildManagerThread("manager-session-2", "flow_visual_refresh")]
  ]);

  const sendManagerMessage = vi.fn().mockImplementation(async (payload) => {
    const managerSessionId = payload.managerSessionId || "manager-session-1";
    const response = "好的，我先把无关层收掉，只保留 Manager shell。";
    const nextThread = buildManagerThread(
      managerSessionId || "manager-session-1",
      payload.manageTarget === "new" ? "flow_mock_desktop" : managerThreads.get(managerSessionId || "manager-session-1")?.linked_flow_id || "flow_mock_desktop"
    );
    nextThread.blocks = [
      ...nextThread.blocks,
      {
        block_id: `${managerSessionId}:streamed`,
        kind: "requirements",
        title: "Manager 回复",
        summary: response,
        created_at: "2026-04-05 14:02:00",
        status: "active",
        expanded_by_default: true,
        payload: {
          instruction: payload.instruction,
          response
        }
      }
    ];
    nextThread.latest_response = response;
    managerThreads.set(managerSessionId || "manager-session-1", nextThread);
    return {
      ok: true,
      manager_session_id: managerSessionId || "manager-session-1",
      message: { response },
      thread: nextThread,
      launched_flow: payload.manageTarget === "new" ? { flow_id: "flow_mock_desktop" } : {}
    };
  });

  const api: ButlerDesktopApi = {
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
          flow_id: "flow_mock_desktop",
          active_role_id: "",
          current_phase: "requirements",
          badge: "flow_create",
          tags: ["managed_flow"]
        },
        {
          thread_id: "manager:manager-session-2",
          thread_kind: "manager",
          title: "视觉升级 Manager 线程",
          subtitle: "另一个 manager thread",
          status: "active",
          created_at: "2026-04-05 12:00:00",
          updated_at: "2026-04-05 15:00:00",
          manager_session_id: "manager-session-2",
          flow_id: "flow_visual_refresh",
          active_role_id: "",
          current_phase: "delivery",
          badge: "managed_flow",
          tags: ["managed_flow"]
        }
      ],
      templates: []
    }),
    getManagerThread: vi.fn().mockImplementation(async ({ managerSessionId } = {}) => {
      return managerThreads.get(managerSessionId || "manager-session-1") || buildManagerThread();
    }),
    getSupervisorThread: vi.fn().mockResolvedValue({}),
    getAgentFocus: vi.fn().mockResolvedValue({}),
    getTemplateTeam: vi.fn().mockResolvedValue({}),
    getDefaultConfigPath: vi.fn().mockResolvedValue({
      configPath: CONFIG_PATH
    }),
    sendManagerMessage,
    sendManagerMessageStream: vi.fn().mockImplementation(async (payload) => {
      const requestId = `stream-${++requestCounter}`;
      setTimeout(async () => {
        listeners.forEach((listener) =>
          listener({
            requestId,
            type: "started",
            managerSessionId: payload.managerSessionId
          })
        );
        const result = await sendManagerMessage(payload);
        const response = String(result.message.response || "");
        const midpoint = Math.ceil(response.length / 2);
        const chunks = [response.slice(0, midpoint), response.slice(midpoint)].filter(Boolean);
        chunks.forEach((chunkText, index) => {
          setTimeout(() => {
            listeners.forEach((listener) =>
              listener({
                requestId,
                type: "chunk",
                managerSessionId: result.manager_session_id,
                chunkText
              })
            );
          }, 10 * (index + 1));
        });
        setTimeout(() => {
          listeners.forEach((listener) =>
            listener({
              requestId,
              type: "completed",
              managerSessionId: result.manager_session_id,
              finalResult: result
            })
          );
        }, 36);
      }, 0);
      return { requestId };
    }),
    onManagerMessageEvent: vi.fn().mockImplementation((listener: ManagerMessageStreamListener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
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
    })
  };

  return api;
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
  });

  it("auto-attaches the repo default config and renders the minimal manager shell", async () => {
    const api = buildApi();
    api.getDefaultConfigPath = vi.fn().mockResolvedValue({ configPath: DEFAULT_CONFIG_PATH });
    window.butlerDesktop = api;

    renderDesktopApp(<App />);

    await waitFor(() => {
      expect(api.getThreadHome).toHaveBeenCalledWith({ configPath: DEFAULT_CONFIG_PATH });
    });
    expect(await screen.findByRole("heading", { name: "Desktop 线程工作台" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New thread" })).toBeInTheDocument();
    expect(screen.getByText("History")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Runtime" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Studio" })).not.toBeInTheDocument();
  });

  it("still allows manual attachment when the repo default config is unavailable", async () => {
    const api = buildApi();
    api.getDefaultConfigPath = vi.fn().mockResolvedValue({ configPath: "" });
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.type(await screen.findByLabelText("Config Path Fallback"), CONFIG_PATH);
    await user.click(screen.getByRole("button", { name: "Attach Path" }));

    await waitFor(() => {
      expect(api.getThreadHome).toHaveBeenCalledWith({ configPath: CONFIG_PATH });
    });
    expect(await screen.findByText(`Config attached: ${CONFIG_PATH}`)).toBeInTheDocument();
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

  it("opens a blank manager thread and streams the first reply with manageTarget=new", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(screen.getByRole("button", { name: "New thread" }));
    expect(await screen.findByRole("heading", { name: "New thread" })).toBeInTheDocument();

    await user.type(await screen.findByLabelText("Start with Manager"), "从空白 manager thread 开始");
    await user.click(screen.getByRole("button", { name: /send to manager/i }));

    await waitFor(() => {
      expect(api.sendManagerMessageStream).toHaveBeenCalledWith({
        configPath: CONFIG_PATH,
        instruction: "从空白 manager thread 开始",
        managerSessionId: "",
        manageTarget: "new"
      });
    });
    expect(await screen.findByText("好的，我先把无关层收掉，只保留 Manager shell。")).toBeInTheDocument();
  });

  it("streams manager output inside the same shell without surfacing runtime pages", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.type(await screen.findByLabelText("Continue with Manager"), "继续往下搭最小前端壳");
    await user.click(screen.getByRole("button", { name: /send to manager/i }));

    expect(await screen.findByText("Streaming...")).toBeInTheDocument();
    expect(await screen.findByText("继续往下搭最小前端壳")).toBeInTheDocument();
    expect(await screen.findByText("好的，我先把无关层收掉，只保留 Manager shell。")).toBeInTheDocument();
    expect(screen.queryByText("Runtime Lens")).not.toBeInTheDocument();
  });

  it("keeps the left rail focused on history cards and opens alternate history in the same shell", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(await screen.findByRole("button", { name: /视觉升级 manager 线程/i }));

    expect(await screen.findByRole("heading", { name: "视觉升级 Manager 线程" })).toBeInTheDocument();
    expect(screen.queryByText("Runtime Lens")).not.toBeInTheDocument();
  });

  it("toggles theme and persists the latest choice", async () => {
    const api = buildApi();
    window.localStorage.setItem("butler.desktop.configPath", CONFIG_PATH);
    window.butlerDesktop = api;
    const user = userEvent.setup();

    renderDesktopApp(<App />);
    await user.click(await screen.findByRole("button", { name: "Switch to day mode" }));

    expect(window.localStorage.getItem("butler.desktop.theme")).toBe("day");
    expect(document.querySelector(".desktop-root")).toHaveAttribute("data-theme", "day");
    expect(screen.getByRole("button", { name: "Switch to night mode" })).toBeInTheDocument();
  });
});
