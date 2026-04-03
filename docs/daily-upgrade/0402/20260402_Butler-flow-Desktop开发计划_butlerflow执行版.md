# Butler-flow-Desktop 开发计划（butler-flow 执行版）

- 日期：2026-04-02
- 文档类型：执行主计划 / 合成版
- 适用范围：**仅前台 `butler-flow`：CLI、Textual TUI、manage center、future Desktop**
- 目标：把 `0331 + 0401 + 0402 + V2.1` 的前台 flow 规划合成一版，形成适合 `butler-flow` 直接执行的单一开发计划

关联：

- [0331 前台 Workflow Shell 收口](../0331/02_前台WorkflowShell收口.md)
- [0331 前台 butler-flow 角色运行时与 role-session 绑定实施回写](../0331/06_前台butler-flow角色运行时与role-session绑定计划.md)
- [0401 前台 Butler Flow 入口收口与 New 向导 V1](../0401/01_前台ButlerFlow入口收口与New向导V1.md)
- [0401 Claude Code 对 Butler Flow 工作台化升级与 TUI 信息架构计划](../0401/02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)
- [0402 Butler Flow Manage Center 资产中心升级与会话式交互落地](./02_butler-flow_manage-center资产中心升级与会话式交互落地.md)
- [0402 Butler Flow 长流治理与 supervisor 可观测性升级](./11_butler-flow_长流治理与supervisor可观测性升级.md)
- [20260402_Butler-flow Desktop V2.1 PRD_main分支对齐_flow CLI入口与双轨实施_更新版.md](./20260402_Butler-flow%20Desktop%20V2.1%20PRD_main%E5%88%86%E6%94%AF%E5%AF%B9%E9%BD%90_flow%20CLI%E5%85%A5%E5%8F%A3%E4%B8%8E%E5%8F%8C%E8%BD%A8%E5%AE%9E%E6%96%BD_%E6%9B%B4%E6%96%B0%E7%89%88.md)

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 形成一版可以直接交给 `butler-flow` 执行的前台 Desktop/TUI 主计划，统一入口、状态真源、shared surface、TUI/Desktop 分工和验收。 |
| 所属层级 | 主落 L1 `Agent Execution Runtime`，辅用 L2 本地状态与 sidecars。 |
| 当前真源文档 | `0331/02`、`0331/06`、`0401/01`、`0401/02`、`0402/02`、`0402/11`。 |
| 计划查看的代码与测试 | `butler_main/butler_flow/`、`butler_main/butler_flow/tui/`、`tools/butler-flow`、`butler_main/__main__.py`，以及 `test_butler_flow.py`、`test_butler_flow_tui_controller.py`、`test_butler_flow_tui_app.py`。 |

## 一句话裁决

`Butler-flow-Desktop` 现在不应继续从后台 `orchestrator` 借对象，而应：

> **以前台 `butler-flow` CLI + sidecars + 现役 TUI payload 为真源，先抽 `butler_flow/surface`，再让 TUI 与 Desktop 共用。**

---

## 1. 执行边界

## 1.1 当前真源

当前前台 `butler-flow` 的真源固定是：

- `workflow_state.json`
- `flow_definition.json`
- `turns.jsonl`
- `actions.jsonl`
- `events.jsonl`
- `artifacts.json`
- `role_sessions.json`
- `handoffs.jsonl`
- `runtime_plan.json`
- `strategy_trace.jsonl`
- `mutations.jsonl`
- `prompt_packets.jsonl`

当前前台公开入口固定是：

- `butler-flow`
- `butler-flow new`
- `butler-flow resume`
- `butler-flow exec`
- `butler-flow status`
- `butler-flow list`
- `butler-flow preflight`
- `butler-flow action`
- `butler-flow tui`

当前现役产品壳固定是：

- `workspace`
- `single flow`
- `supervisor / workflow` 双流
- `/manage`
- `/settings`

## 1.2 明确不做

- 不进入 `campaign/orchestrator`
- 不以 `Mission / Branch / WorkflowSession` 作为 Butler-flow Desktop 主对象
- 不重做 `/flows` 卡片页
- 不把 `/manage` 退回 assets-only 面板
- 不在第一阶段直接做 Electron 重壳

## 1.3 Desktop 主技术选型裁决

这次 Desktop 的选型不再是“直接选 Codex 壳”或“直接选 Proma 壳”，而是拆成三层：

- **Butler 内核**：继续使用现有 `Python + butler-flow + sidecars`
- **Desktop 壳技术栈**：优先采用 `Electron + React + TypeScript + Vite`
- **状态层**：优先采用轻量状态方案，Desktop 首选 `Jotai`
- **UI 层**：优先采用 `Tailwind CSS + Radix/shadcn 风格基础组件`
- **交互范式**：参考 Codex 的 `workbench / drill-down / runtime visible`，但不复制其 runtime

一句话：

> **Butler Desktop 更适合“Proma 式壳技术栈 + Codex 式交互心智 + Butler 自己的 Python foreground runtime”。**

---

## 2. 目标架构

## 2.1 入口分层

### A. 命令暴露层

- `tools/install-butler-flow`
- `tools/butler-flow`
- `python -m butler_main`

### B. foreground flow CLI

- `new`
- `resume`
- `exec`
- `status`
- `list`
- `preflight`
- `action`

### C. interactive shells

- 当前：Textual launcher / workspace / single flow / manage
- 未来：Desktop shell

## 2.2 shared surface

新增目标目录：

```text
butler_main/
  butler_flow/
    surface/
      __init__.py
      dto.py
      queries.py
      details.py
      manage.py
      mappers.py
      service.py
```

职责：

- 从前台 sidecars 读取真源
- 生成稳定 DTO
- 为 TUI 与 Desktop 提供统一 payload
- 吸收当前 `FlowTuiController` 的取数逻辑

## 2.3 推荐 DTO

### `FlowSummaryDTO`

- `flow_id`
- `workflow_kind`
- `effective_status`
- `effective_phase`
- `goal`
- `approval_state`
- `execution_mode`
- `session_strategy`
- `active_role_id`
- `role_pack_id`
- `latest_handoff_summary`
- `updated_at`

### `FlowDetailDTO`

- `summary`
- `step_history`
- `timeline`
- `turns`
- `actions`
- `artifacts`
- `handoffs`
- `flow_definition`
- `runtime_snapshot`

### `SupervisorViewDTO`

- `header`
- `events`
- `latest_supervisor_decision`
- `latest_judge_decision`
- `latest_operator_action`
- `latest_handoff_summary`
- `context_governor`
- `latest_token_usage`

### `WorkflowViewDTO`

- `events`
- `runtime_summary`
- `artifact_refs`

### `ManageCenterDTO`

- `assets`
- `selected_asset`
- `role_guidance`
- `review_checklist`
- `bundle_manifest`
- `manager_notes`

### `RoleRuntimeDTO`

- `active_role_id`
- `role_sessions`
- `pending_handoffs`
- `recent_handoffs`
- `latest_handoff_summary`

---

## 3. TUI 与 Desktop 分工

## 3.1 TUI

TUI 继续承担：

- `workspace` runtime browser
- `single flow` 主控制台
- `supervisor / workflow` 双流切换
- `/manage` transcript-first shell
- slash command / quick action

TUI 第一阶段重点：

- 不改大外观
- 先把当前 controller 的 payload 抽到 shared surface
- 让 TUI 成为第一消费方

## 3.2 Desktop

Desktop 第二阶段承担：

- 更高信息密度
- artifact / markdown / result preview
- detail drawer / side panel
- richer manage center
- 更顺滑的 flow drill-down

Desktop 不承担：

- 替代 CLI
- 替代 foreground runtime
- 引入第二真源

## 3.3 Desktop 壳推荐栈

当前推荐顺序：

1. `Electron`
2. `React`
3. `TypeScript`
4. `Vite`
5. `Jotai`
6. `Tailwind CSS`
7. `Radix UI / shadcn 风格基础组件`

当前不建议引入为 Butler Desktop 主前提的内容：

- 不要求跟随 `Proma` 使用 `Bun workspace monorepo`
- 不要求把 Butler 前台 runtime 改写成 TypeScript 或 Node 主进程服务
- 不要求把 Butler flow 状态迁移成前端 store 真源
- 不要求先接入 vendor agent SDK 再做桌面

## 3.4 Proma 下载落位与复用边界

本轮已把 `Proma` 下载到：

- `MyWorkSpace/TargetProjects/Proma`

当前核验提交：

- `c53a48c80f5afda965ba97e2536a4cd7be316973`

基于当前仓库结构，Proma 对 Butler 的价值主要是 **Desktop shell 工程壳**，不是其 Agent 主进程编排层。

### A. 可以大段拷贝 / 复用的部分

前提：仅限样式层、壳层、通用组件层；实际落代码前仍要做许可证与 attribution 核验。

- `apps/electron/src/renderer/components/ui/` 下的通用基础组件包装
- `apps/electron/src/renderer/components/app-shell/` 中不含业务语义的 panel/shell 布局骨架
- 通用 `dialog / sheet / popover / tabs / tooltip / button / badge / input` 这类基础 UI 包装
- 纯样式 token、暗色主题、玻璃感 panel、圆角容器、sidebar/detail drawer 的视觉组织方式

这些部分与 Butler 的 flow 语义耦合弱，适合在 Desktop 阶段作为快速起壳材料。

### B. 适合参考着写的部分

- `AppShell / LeftSidebar / MainArea / RightSidePanel` 的多栏工作台布局思路
- `Jotai atoms` 的分层组织方式，但状态字段要改成 Butler 的 `surface DTO`
- `preload -> IPC -> renderer` 的 Electron 安全桥接模式
- 文件预览、Markdown 渲染、Tab / Split View、搜索弹层等交互组织
- 设置页、渠道管理页、工作区选择器的交互节奏

这些部分可以借 Proma 的工程手法，但必须把对象面改成：

- `FlowSummaryDTO`
- `FlowDetailDTO`
- `SupervisorViewDTO`
- `WorkflowViewDTO`
- `ManageCenterDTO`

也就是说，**参考它的壳，不参考它的数据对象和 Agent 语义。**

### C. 明确要避免的部分

- `apps/electron/src/main/lib/agent-orchestrator.ts`
- `apps/electron/src/main/lib/agent-session-manager.ts`
- `apps/electron/src/main/lib/agent-prompt-builder.ts`
- `apps/electron/src/main/lib/agent-workspace-manager.ts`
- `apps/electron/src/main/ipc.ts` 里整套以 `Proma Chat / Agent / Workspace` 为核心的 IPC 面
- 飞书 / 钉钉 / 微信桥接、记忆、渠道管理、自动更新等 Proma 自有产品线
- `@anthropic-ai/claude-agent-sdk` 驱动的 Agent runtime 假设
- `~/.proma/` 本地目录结构、session 持久化格式、workspace 目录约定

这些部分不是 Butler Desktop 的“壳”，而是 Proma 自己的产品内核；一旦拷进去，就会把 Butler Desktop 拉回 `chat-first / general-agent-first` 路线，冲掉当前 `flow-first` 裁决。

### D. Butler Desktop 的正确吸收方式

正确顺序应是：

1. 先在 `butler_main/butler_flow/surface/` 抽 DTO 和查询层
2. 让 TUI 成为第一消费方
3. 再在 Desktop 层引入 `Electron + React + TypeScript`
4. Desktop UI 只消费 `surface`，不直接读 raw sidecars
5. 优先复用 Proma 的 **基础 UI 和壳层结构**，不复用其主进程 Agent 服务层

一句话收口：

> **Proma 可以用来加速 Butler Desktop 的“壳子”，但不能成为 Butler Desktop 的运行时真源。**

---

## 4. 代码落点

## 4.1 第一批主改目录

- `butler_main/butler_flow/tui/controller.py`
- `butler_main/butler_flow/tui/app.py`
- `butler_main/butler_flow/tui/manage_interaction.py`
- `butler_main/butler_flow/state.py`
- `butler_main/butler_flow/models.py`
- `butler_main/butler_flow/runtime.py`
- `butler_main/butler_flow/compiler.py`
- `butler_main/butler_flow/manage_agent.py`
- `butler_main/butler_flow/role_runtime.py`
- `tools/butler-flow`
- `butler_main/__main__.py`

## 4.2 新增目录

```text
butler_main/butler_flow/surface/
```

第一波只做 Python shared surface，不引入桌面壳细节。

---

## 5. 实施波次

## Phase 0：冻结现役口径

目标：

- 明确前台真源
- 明确入口以 `butler-flow` 为准
- 明确 `workspace / single flow / /manage` 不回退

完成标准：

- 文档口径一致
- 计划中不再出现 `orchestrator mission/branch` 作为主对象

## Phase 1：抽 shared surface

目标：

- 新增 `butler_flow/surface`
- 吸收 controller 当前 payload builder
- 定义稳定 DTO

完成标准：

- TUI 取数不再散落在 controller
- `workspace/single_flow/manage/detail` 都有对应 surface 接口

## Phase 2：TUI 薄改接 surface

目标：

- `workspace` 改接 `FlowSummaryDTO`
- `single flow` 改接 `FlowDetailDTO + SupervisorViewDTO + WorkflowViewDTO`
- `/manage` 改接 `ManageCenterDTO`

完成标准：

- 现有交互不回退
- 兼容层仅保留必要字段

## Phase 3：Desktop adapter

目标：

- 增加桌面消费层接口
- 只复用 shared surface

完成标准：

- 明确 desktop home / workbench / manage center 的 payload 合同
- 不直接吃 raw sidecars

## Phase 4：Desktop shell

目标：

- Home
- Flow Workbench
- Manage Center
- Detail Drawer
- Artifact Preview

完成标准：

- flow-first，不退化成 chat-first
- UI 只复用 surface，不绕过 surface
- 允许优先吸收 `Proma` 的通用 UI 壳层与基础组件
- 禁止把 `Proma main/lib` 的 Agent 编排层直接搬成 Butler 主逻辑

---

## 6. 波次内执行清单

## 6.1 Wave 1：surface + TUI 对齐

建议任务拆分：

1. 从 `controller.py` 抽 `workspace/single_flow/manage/detail` query
2. 建 `surface/dto.py`
3. 建 `surface/service.py`
4. TUI 改接 surface
5. 跑前台 flow 回归

## 6.2 Wave 2：Desktop readiness

建议任务拆分：

1. 抽 desktop adapter contract
2. 定义 desktop page payload
3. 先从 `Proma` 吸收可复用 shell/ui 材料
4. 建立 desktop shell 占位实现
5. 补 artifact preview / detail drill-down

---

## 7. 验收

## 7.1 最小测试

- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow.py -q`
- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py -q`
- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_tui_app.py -q`

## 7.2 架构验收

- Desktop/TUI 都不直接吃 raw sidecars
- `butler_flow/surface` 存在并可用
- 当前前台 flow 真源未被替换
- 没有把后台 `orchestrator` 混回 Butler-flow Desktop

## 7.3 产品验收

- `workspace` 仍是默认 home
- `single flow` 仍是 `supervisor / workflow` 双流
- `/manage` 仍是 transcript-first shell
- `free` 仍走 `setup -> /manage template:new -> template:<id> -> launch instance`

---

## 8. 给 butler-flow 的执行要求

1. 先抽 surface，再动 UI
2. 先守住当前信息架构，再谈 Desktop 壳
3. 不改前台 / 后台边界
4. 不把 shared surface 变成新的状态真源
5. 每波都先跑最小前台 flow 回归

---

## 9. 最终结论

这版主计划把此前几个版本收口成了一条明确路线：

1. `0331/02` 负责入口与前台边界
2. `0331/06` 负责 role runtime 与 medium 语义
3. `0401/01` 负责 `new/resume/exec` 与 setup picker
4. `0401/02` 负责 `workspace / single flow / /manage` 信息架构
5. `0402/02` 负责 manage center 与 shared asset bundle
6. `0402/11` 负责 supervisor 可观测性
7. 本文负责把它们合成 **butler-flow 可直接执行的开发主计划**

一句话收口：

> **Butler-flow-Desktop 的正确开发顺序是：冻结前台真源 → 抽 `butler_flow/surface` → 让 TUI 先接入 → 再做 Desktop。**
