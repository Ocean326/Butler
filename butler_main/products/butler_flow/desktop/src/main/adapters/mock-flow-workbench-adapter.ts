import type {
  AgentFocusDTO,
  DesktopActionPayload,
  ManageCenterDTO,
  ManagerMessagePayload,
  ManagerMessageResult,
  ManagerThreadDTO,
  SingleFlowPayload,
  SupervisorThreadDTO,
  TemplateTeamDTO,
  ThreadHomeDTO,
  WorkspacePayload
} from "../../shared/dto";

const now = "2026-04-05 14:00:00";
const flowId = "flow_mock_desktop";
const managerSessionId = "manager_session_mock_01";
const secondaryFlowId = "flow_visual_refresh";
const secondaryManagerSessionId = "manager_session_mock_02";

function flowSummary() {
  return {
    flow_id: flowId,
    label: "Butler Flow Desktop",
    workflow_kind: "managed_flow",
    effective_status: "running",
    effective_phase: "implement",
    attempt_count: 2,
    max_attempts: 8,
    max_phase_attempts: 4,
    max_runtime_seconds: 1800,
    runtime_elapsed_seconds: 312,
    goal: "重构 Butler 桌面端为线程化单流工作台",
    guard_condition: "Desktop shell, thread bridge, and tests are verified",
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
      summary: "桌面线程壳已经可以开始实现"
    },
    updated_at: now
  };
}

function secondaryFlowSummary() {
  return {
    ...flowSummary(),
    flow_id: secondaryFlowId,
    label: "Visual Refresh Flow",
    goal: "验证历史线程切换后仍能回到正确的 Manager",
    updated_at: "2026-04-05 15:00:00"
  };
}

function managerThread(): ManagerThreadDTO {
  return {
    thread: {
      thread_id: `manager:${managerSessionId}`,
      thread_kind: "manager",
      title: "Desktop 线程工作台",
      subtitle: "先由 Manager 统一对齐 idea / requirements / delivery / test。",
      status: "active",
      created_at: "2026-04-05 13:20:00",
      updated_at: now,
      manager_session_id: managerSessionId,
      flow_id: flowId,
      active_role_id: "",
      current_phase: "team_draft",
      badge: "flow_create",
      tags: ["managed_flow", "team_draft"]
    },
    manager_session_id: managerSessionId,
    manage_target: `instance:${flowId}`,
    active_manage_target: `instance:${flowId}`,
    manager_stage: "launch",
    confirmation_scope: "",
    blocks: [
      {
        block_id: "manager:1",
        kind: "idea",
        title: "Idea 草案",
        summary: "把桌面端改成中文优先、核心 English 保留的线程化工作台。",
        created_at: "2026-04-05 13:21:00",
        status: "active",
        expanded_by_default: true,
        payload: {
          instruction: "butler 前端要改成线程化、中文优先",
          response: "我会先聚焦 Manager 入口和 Supervisor 单流布局。"
        },
        tags: ["brainstorm"]
      },
      {
        block_id: "manager:2",
        kind: "requirements",
        title: "Requirements 细化",
        summary: "左侧保留 Manager / History / New Flow / Templates，右侧主区全部单流展示。",
        created_at: "2026-04-05 13:31:00",
        status: "active",
        expanded_by_default: true,
        payload: {
          draft: {
            workflow_kind: "managed_flow",
            goal: "重构 Butler 桌面端为线程化单流工作台"
          }
        },
        tags: ["requirements"]
      },
      {
        block_id: "manager:3",
        kind: "team_draft",
        title: "Team / Supervisor 草案",
        summary: "创建 Team + Supervisor 后，默认直接切到 Supervisor 流式工作，再按 agent 打开 focus 页。",
        created_at: "2026-04-05 13:43:00",
        status: "ready",
        expanded_by_default: true,
        payload: {
          role_guidance: {
            planner: "负责拆解和边界收敛",
            implementer: "负责 desktop renderer 和 bridge 接线",
            reviewer: "负责回归和验收"
          }
        },
        tags: ["team"]
      },
      {
        block_id: "manager:4",
        kind: "launch",
        title: "Supervisor 已接管",
        summary: "Flow 已创建，继续在 Supervisor 流里看团队推进。",
        created_at: now,
        status: "launched",
        expanded_by_default: true,
        payload: { flow_id: flowId },
        action_label: "Open Supervisor",
        action_target: `flow:${flowId}`,
        tags: ["launched"]
      }
    ],
    draft: {
      label: "Desktop 线程工作台",
      workflow_kind: "managed_flow",
      goal: "重构 Butler 桌面端为线程化单流工作台",
      guard_condition: "桌面端线程 IA、日夜主题、bridge 和测试都完成"
    },
    pending_action: {},
    latest_response: "Flow 已创建，切到 Supervisor 继续。",
    linked_flow_id: flowId
  };
}

function secondaryManagerThread(): ManagerThreadDTO {
  return {
    ...managerThread(),
    thread: {
      ...managerThread().thread,
      thread_id: `manager:${secondaryManagerSessionId}`,
      title: "视觉升级 Manager 线程",
      subtitle: "这是另一个 manager thread，用来验证上下文切换。",
      updated_at: "2026-04-05 15:00:00",
      manager_session_id: secondaryManagerSessionId,
      flow_id: secondaryFlowId,
      current_phase: "delivery"
    },
    manager_session_id: secondaryManagerSessionId,
    manage_target: `instance:${secondaryFlowId}`,
    active_manage_target: `instance:${secondaryFlowId}`,
    latest_response: "继续视觉升级。",
    linked_flow_id: secondaryFlowId,
    blocks: [
      {
        block_id: "manager:alt:1",
        kind: "requirements",
        title: "视觉升级要求",
        summary: "从 History 打开 supervisor 后，返回 Manager 必须回到这个上下文。",
        created_at: "2026-04-05 14:10:00",
        status: "active",
        expanded_by_default: true,
        payload: {}
      }
    ]
  };
}

function supervisorThread(): SupervisorThreadDTO {
  const summary = flowSummary();
  return {
    thread: {
      thread_id: `flow:${flowId}`,
      thread_kind: "supervisor",
      title: "Butler Flow Desktop",
      subtitle: "Supervisor 正在推进 renderer、bridge 和 tests。",
      status: "running",
      created_at: "2026-04-05 13:50:00",
      updated_at: now,
      manager_session_id: managerSessionId,
      flow_id: flowId,
      active_role_id: "implementer",
      current_phase: "implement",
      badge: "operator_required",
      tags: ["managed_flow", "medium", "role_bound"]
    },
    flow_id: flowId,
    summary,
    blocks: [
      {
        block_id: "supervisor:start",
        kind: "start",
        title: "Supervisor 启动",
        summary: "已接管 Desktop 线程工作台 flow，先实现 thread surface 和 renderer。",
        created_at: "2026-04-05 13:50:00",
        status: "running",
        expanded_by_default: true,
        payload: { summary },
        tags: ["implement", "implementer"]
      },
      {
        block_id: "supervisor:decision:1",
        kind: "decision",
        title: "实现 thread-home / manager-thread / supervisor-thread",
        summary: "先把桌面端 bridge 切到 thread-first API，再整体替换旧 UI。",
        created_at: "2026-04-05 13:54:00",
        status: "decision",
        expanded_by_default: true,
        payload: {
          role_id: "implementer",
          next_action: "rewrite_renderer"
        },
        role_id: "implementer",
        phase: "implement",
        action_label: "Open Agent",
        action_target: "role:implementer",
        tags: ["supervisor", "decision"]
      },
      {
        block_id: "supervisor:artifact:1",
        kind: "artifact",
        title: "Desktop mock shell snapshot",
        summary: "artifact://desktop/workbench",
        created_at: "2026-04-05 13:58:00",
        status: "artifact",
        expanded_by_default: false,
        payload: {
          artifact_ref: "artifact://desktop/workbench"
        },
        tags: ["workflow", "artifact"]
      }
    ],
    role_strip: {
      active_role_id: "implementer",
      role_sessions: {
        planner: { session_id: "sess-1" },
        implementer: { session_id: "sess-2" },
        reviewer: { session_id: "sess-3" }
      },
      pending_handoffs: [{ handoff_id: "handoff-8", to_role_id: "reviewer", summary: "等待回归" }],
      recent_handoffs: [
        { handoff_id: "handoff-7", from_role_id: "planner", to_role_id: "implementer", summary: "开始实现" }
      ],
      latest_handoff_summary: {
        handoff_id: "handoff-8",
        to_role_id: "reviewer",
        summary: "等待回归"
      },
      latest_role_handoffs: {},
      role_chips: [
        { role_id: "planner", state: "idle", is_active: false, session_id: "sess-1" },
        { role_id: "implementer", state: "active", is_active: true, session_id: "sess-2" },
        { role_id: "reviewer", state: "receiving_handoff", is_active: false, session_id: "sess-3" }
      ],
      roles: [
        { role_id: "planner", state: "idle", session_id: "sess-1" },
        { role_id: "implementer", state: "active", session_id: "sess-2" },
        { role_id: "reviewer", state: "receiving_handoff", session_id: "sess-3" }
      ],
      execution_mode: "medium",
      session_strategy: "role_bound",
      role_pack_id: "coding_flow"
    },
    operator_rail: {
      approval_state: "operator_required",
      latest_supervisor_decision: { decision: "continue" },
      latest_operator_action: { action_type: "append_instruction" },
      latest_judge_decision: { decision: "ADVANCE" }
    },
    latest_handoff: {
      handoff_id: "handoff-8",
      to_role_id: "reviewer",
      summary: "等待回归"
    }
  };
}

function secondarySupervisorThread(): SupervisorThreadDTO {
  const summary = secondaryFlowSummary();
  return {
    ...supervisorThread(),
    thread: {
      ...supervisorThread().thread,
      thread_id: `flow:${secondaryFlowId}`,
      title: "Visual Refresh Flow",
      subtitle: "Supervisor 正在验证历史线程与 manager 上下文同步。",
      updated_at: "2026-04-05 15:00:00",
      manager_session_id: secondaryManagerSessionId,
      flow_id: secondaryFlowId
    },
    flow_id: secondaryFlowId,
    summary,
    blocks: [
      {
        block_id: "supervisor:alt:start",
        kind: "decision",
        title: "Validate thread round-trip",
        summary: "先从 History 打开 supervisor，再回 Manager，确认上下文没漂移。",
        created_at: "2026-04-05 14:20:00",
        status: "decision",
        expanded_by_default: true,
        payload: { summary },
        role_id: "implementer",
        phase: "implement",
        action_label: "Open Agent",
        action_target: "role:implementer",
        tags: ["supervisor", "decision"]
      }
    ],
    latest_handoff: {
      handoff_id: "handoff-visual-refresh",
      to_role_id: "implementer",
      summary: "验证 history -> supervisor -> manager round-trip"
    }
  };
}

function agentFocus(nextFlowId: string, roleId: string): AgentFocusDTO {
  const isSecondaryFlow = nextFlowId === secondaryFlowId;
  const summary = isSecondaryFlow ? secondaryFlowSummary() : flowSummary();
  const focusFlowId = isSecondaryFlow ? secondaryFlowId : flowId;
  const focusManagerSessionId = isSecondaryFlow ? secondaryManagerSessionId : managerSessionId;
  const focusUpdatedAt = isSecondaryFlow ? "2026-04-05 15:00:00" : now;
  const focusSummary =
    roleId === "implementer"
      ? isSecondaryFlow
        ? "正在验证历史线程切换后的 manager 上下文。"
        : "正在实现 renderer 和 IPC。"
      : isSecondaryFlow
        ? "准备接收视觉升级回归 handoff。"
        : "准备接收 handoff 并做验证。";

  return {
    thread: {
      thread_id: `agent:${focusFlowId}:${roleId}`,
      thread_kind: "agent",
      title: roleId,
      subtitle: "Agent focus stream",
      status: "running",
      created_at: "2026-04-05 13:56:00",
      updated_at: focusUpdatedAt,
      manager_session_id: focusManagerSessionId,
      flow_id: focusFlowId,
      active_role_id: roleId,
      current_phase: "implement",
      badge: roleId === "implementer" ? "active" : "idle",
      tags: ["managed_flow"]
    },
    flow_id: focusFlowId,
    role_id: roleId,
    title: `${roleId} · focus`,
    summary,
    blocks: [
      {
        block_id: `agent:${roleId}:brief`,
        kind: "role_brief",
        title: `Agent · ${roleId}`,
        summary: focusSummary,
        created_at: "2026-04-05 13:56:00",
        status: roleId === "implementer" ? "active" : "idle",
        expanded_by_default: true,
        payload: {
          role_id: roleId
        },
        role_id: roleId
      },
      {
        block_id: `agent:${roleId}:progress`,
        kind: "progress",
        title: "Progress 更新",
        summary: isSecondaryFlow
          ? roleId === "implementer"
            ? "secondary flow 正在验证 history -> supervisor -> manager 回跳。"
            : "等待 secondary flow 的实现结论后做收口。"
          : roleId === "implementer"
            ? "thread API 已接线，准备重写单流页面。"
            : "等待实现完成后接手回归。",
        created_at: focusUpdatedAt,
        status: "progress",
        expanded_by_default: true,
        payload: {
          role_id: roleId
        },
        role_id: roleId,
        phase: "implement"
      }
    ],
    role: {
      role_id: roleId,
      state: roleId === "implementer" ? "active" : "receiving_handoff",
      session_id: roleId === "implementer" ? "sess-2" : "sess-3"
    },
    related_handoffs: [
      roleId === "reviewer"
        ? {
            handoff_id: isSecondaryFlow ? "handoff-visual-refresh-review" : "handoff-8",
            to_role_id: "reviewer",
            summary: isSecondaryFlow ? "等待视觉升级回归" : "等待回归"
          }
        : {
            handoff_id: isSecondaryFlow ? "handoff-visual-refresh" : "handoff-7",
            to_role_id: "implementer",
            summary: isSecondaryFlow ? "验证 history -> supervisor -> manager round-trip" : "开始实现"
          }
    ],
    artifacts: [{ artifact_ref: "artifact://desktop/workbench", title: "Desktop shell" }]
  };
}

function templateTeam(assetId = "desktop-template"): TemplateTeamDTO {
  return {
    thread: {
      thread_id: `template:${assetId}`,
      thread_kind: "template",
      title: "Desktop Shell Template",
      subtitle: "Template + agent team management",
      status: "active",
      created_at: "2026-04-05 12:10:00",
      updated_at: now,
      manager_session_id: "",
      flow_id: "",
      active_role_id: "",
      current_phase: "",
      badge: "template",
      tags: ["managed_flow", "coding_flow"]
    },
    asset_id: assetId,
    blocks: [
      {
        block_id: "template:overview",
        kind: "overview",
        title: "Templates / Team",
        summary: "管理可复用模板，以及默认 agent team / supervisor 标准。",
        created_at: now,
        status: "active",
        expanded_by_default: true,
        payload: {}
      },
      {
        block_id: "template:team",
        kind: "team",
        title: "Default Team",
        summary: "planner / implementer / reviewer 三角色默认协作。",
        created_at: now,
        status: "configured",
        expanded_by_default: true,
        payload: {
          planner: "负责需求收敛",
          implementer: "负责实现",
          reviewer: "负责验收"
        }
      }
    ],
    assets: [
      {
        asset_id: assetId,
        label: "Desktop Shell Template",
        asset_kind: "template",
        workflow_kind: "managed_flow",
        goal: "线程化 desktop shell"
      }
    ],
    selected_asset: {
      asset_id: assetId,
      label: "Desktop Shell Template",
      description: "Electron + React thread workbench shell"
    },
    role_guidance: {
      planner: "先对齐 thread-first 信息架构",
      implementer: "保留 Python bridge 作为真源",
      reviewer: "验证 renderer + bridge + tests"
    },
    review_checklist: ["Manager 先于 Supervisor", "单流布局", "日夜主题可切换"],
    bundle_manifest: {
      bundle_id: "desktop-thread-template"
    },
    manager_notes: "先固定 thread contract，再写 UI。"
  };
}

export class MockFlowWorkbenchAdapter {
  async getHome(): Promise<WorkspacePayload> {
    return {
      preflight: {
        workspace_root: "/tmp/butler-demo",
        config_path: "/tmp/butler-demo/config.json"
      },
      flows: {
        items: [flowSummary(), secondaryFlowSummary()]
      }
    };
  }

  async getFlow(): Promise<SingleFlowPayload> {
    const summary = flowSummary();
    return {
      flow_id: flowId,
      status: { flow_id: flowId },
      summary,
      step_history: [],
      timeline: [],
      turns: [],
      actions: [],
      artifacts: [{ artifact_ref: "artifact://desktop/workbench", title: "Desktop shell" }],
      handoffs: [],
      flow_definition: {},
      runtime_snapshot: {},
      navigator_summary: summary,
      supervisor_view: {
        header: {},
        events: [],
        latest_supervisor_decision: {},
        latest_judge_decision: {},
        latest_operator_action: {},
        latest_handoff_summary: {},
        context_governor: {},
        latest_token_usage: {},
        pointers: {}
      },
      workflow_view: {
        events: [],
        runtime_summary: {},
        artifact_refs: ["artifact://desktop/workbench"]
      },
      inspector: {},
      role_strip: supervisorThread().role_strip,
      operator_rail: supervisorThread().operator_rail,
      flow_console: {
        step_history: []
      },
      surface: {}
    };
  }

  async getDetail(): Promise<Record<string, unknown>> {
    return {
      flow_id: flowId,
      plan: { flow_definition: {} },
      artifacts: [{ artifact_ref: "artifact://desktop/workbench" }]
    };
  }

  async getManageCenter(): Promise<ManageCenterDTO> {
    return {
      preflight: { config_path: "/tmp/butler-demo/config.json" },
      assets: {
        items: templateTeam().assets
      },
      selected_asset: templateTeam().selected_asset,
      role_guidance: templateTeam().role_guidance,
      review_checklist: templateTeam().review_checklist,
      bundle_manifest: templateTeam().bundle_manifest,
      manager_notes: templateTeam().manager_notes
    };
  }

  async getPreflight(): Promise<Record<string, unknown>> {
    return {
      workspace_root: "/tmp/butler-demo",
      config_path: "/tmp/butler-demo/config.json",
      provider_state: "mock"
    };
  }

  async getThreadHome(): Promise<ThreadHomeDTO> {
    return {
      preflight: {
        workspace_root: "/tmp/butler-demo",
        config_path: "/tmp/butler-demo/config.json"
      },
      manager_entry: {
        default_manager_session_id: managerSessionId,
        draft_summary: "先用 Manager 对齐需求，再切到 Supervisor。",
        status: "active",
        title: "Manager 管理台",
        total_sessions: 2,
        active_flow_id: flowId,
        active_thread_id: `manager:${managerSessionId}`
      },
      history: [managerThread().thread, supervisorThread().thread, secondaryManagerThread().thread, secondarySupervisorThread().thread],
      templates: [templateTeam().thread]
    };
  }

  async getManagerThread(sessionId?: string): Promise<ManagerThreadDTO> {
    if (sessionId === "") {
      return {
        ...managerThread(),
        manager_session_id: "",
        thread: {
          ...managerThread().thread,
          thread_id: "manager:draft",
          manager_session_id: "",
          flow_id: "",
          title: "Manager 管理台",
          subtitle: "从这里开始一个新的 flow。",
          status: "draft"
        },
        linked_flow_id: "",
        blocks: [
          {
            block_id: "starter:1",
            kind: "opening",
            title: "Manager 入口",
            summary: "描述你的 idea，我们会先对齐 brainstorm，再沉淀 requirements 和 standards。",
            created_at: now,
            status: "idle",
            expanded_by_default: true,
            payload: {}
          }
        ]
      };
    }
    if (sessionId === secondaryManagerSessionId) {
      return secondaryManagerThread();
    }
    return managerThread();
  }

  async getSupervisorThread(nextFlowId?: string): Promise<SupervisorThreadDTO> {
    if (nextFlowId === secondaryFlowId) {
      return secondarySupervisorThread();
    }
    return supervisorThread();
  }

  async getAgentFocus(nextFlowId: string, roleId: string): Promise<AgentFocusDTO> {
    return agentFocus(nextFlowId, roleId);
  }

  async getTemplateTeam(assetId?: string): Promise<TemplateTeamDTO> {
    return templateTeam(assetId);
  }

  async sendManagerMessage(payload: ManagerMessagePayload): Promise<ManagerMessageResult> {
    const shouldLaunch = payload.instruction.includes("创建") || payload.instruction.toLowerCase().includes("create");
    return {
      ok: true,
      manager_session_id: managerSessionId,
      message: {
        response: shouldLaunch ? "Flow 已创建，切到 Supervisor。" : "已更新 Manager 草案，继续细化。",
        manager_session_id: managerSessionId
      },
      thread: managerThread(),
      launched_flow: shouldLaunch ? { flow_id: flowId, summary: "Flow created." } : {}
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
