# Butler-flow Desktop V2 PRD + 实现对齐 + TUI / Desktop 双轨 + Codex 执行计划

- 日期：2026-04-02
- 文档类型：V2 PRD / 架构对齐 / 实施计划 / Codex 执行底稿
- 适用范围：**仅 Butler-flow / orchestrator / workflow_session 这一条线**
- 目标：修正 V1 中“产品先行、接口后补”的偏差，改为以当前已提交的 flow 真源、运行时对象、已有 service / runner 能力为基准来定义 V2

---

## 0. 为什么需要 V2

上一版 Butler-flow Desktop V1 PRD 的主要问题，不在于总体方向错误，而在于：

1. 它更像“从 Proma / Codex 的产品形状反推 Butler-flow 页面”，而不是从 Butler-flow 当前已经存在的对象与接口反推前端。
2. 它把重点放在桌面壳、页面布局、线框图，却没有充分对齐当前 `orchestrator/service.py`、`runner.py`、`workflow_ir.py`、`workflow_vm.py` 已经提供的真实能力。
3. 它默认桌面端是主目标，但 Butler 接下来实际要走的是 **TUI + Desktop 双轨**，因此应该先抽一层共享 surface，而不是先绑死 Electron 专用 API。
4. 它虽然强调了 flow-first，但仍然过度借用了“agent 工作台”的表达方式，没有把 Butler-flow 现在已经成型的 `mission / node / branch / workflow_session / workflow_ir / workflow_vm` 关系用产品语言重新组织清楚。

因此，V2 的核心转向是：

> **不是继续讨论 Butler-flow 的桌面壳长什么样，而是先定义 Butler-flow 当前真实存在的能力面、共享 surface、前端消费对象，再定义 TUI 与 Desktop 两个前端如何共享这套能力。**

---

## 1. 当前已提交实现：Butler-flow 的真实能力面

本节只以当前仓库中已经提交的实现为准。

### 1.1 当前核心对象

当前 Butler-flow / orchestrator 这一层，实际已经形成了以下核心对象：

- `Mission`
- `MissionNode`
- `Branch`
- `WorkflowSession`
- `WorkflowIR`
- `WorkflowVMExecutionOutcome`
- `LedgerEvent`

从产品视角看，可映射为：

- `Flow` ≈ `Mission`
- `Flow Node` ≈ `MissionNode`
- `Child / Active Child / Run Slot` ≈ `Branch`
- `Child Session` ≈ `WorkflowSession`
- `Route / Runtime / Contracts / Inputs / Driver` ≈ `WorkflowIR`
- `Timeline / Audit / Delivery Feed` ≈ `LedgerEvent`

### 1.2 当前已存在的 service 能力

`butler_main/orchestrator/service.py` 已经不只是一个 mission CRUD 层，它已经具备比较完整的“前台消费面”：

#### Flow / Mission 侧
- `create_mission(...)`
- `get_mission(mission_id)`
- `list_missions()`
- `list_mission_overview(status="", limit=0)`
- `summarize_mission(mission_id)`
- `control_mission(mission_id, action)`
- `append_user_feedback(mission_id, feedback)`

#### Branch / Child 侧
- `get_branch(branch_id)`
- `list_branches(mission_id="", node_id="")`
- `list_active_branches(mission_id="", limit=0)`
- `summarize_branch(branch_id)`
- `dispatch_ready_nodes(mission_id, limit=0)`
- `record_branch_result(...)`

#### Workflow Session 侧
- `summarize_workflow_session(session_id)`

#### Event / 观察窗口侧
- `list_delivery_events(mission_id)`
- `list_recent_events(...)`
- `build_observation_window(mission_limit=8, branch_limit=8, event_limit=20)`
- `tick(mission_id="")`

这说明一件事：

> **Butler-flow V2 不需要重新发明一套“给前端看的后端真源”，因为当前 service.py 已经天然接近一个 flow observation / control surface。**

### 1.3 当前 workflow_ir 能提供什么

`butler_main/orchestrator/workflow_ir.py` 当前已经定义了稳定的 `WorkflowIR`，其中不仅有 `workflow_id / mission_id / node_id / branch_id`，还包含：

- `workflow_kind`
- `driver_kind`
- `entrypoint`
- `runtime_key`
- `agent_id`
- `worker_profile`
- `template_id`
- `workflow_template`
- `role_bindings`
- `workflow_inputs`
- `workflow_session_id`
- `workflow_template_id`
- `subworkflow_kind`
- `research_unit_id`
- `scenario_action`
- `verification`
- `approval`
- `recovery`
- `metadata`

这意味着前端现在已经有能力展示：

- 当前 child 到底属于什么 workflow kind
- 它走哪种 driver
- 它的 runtime / worker_profile / agent_id 是什么
- 它挂在哪个 workflow_session 下
- 它的 verification / approval / recovery contract 是什么
- 它有哪些 template / role_bindings / workflow_inputs

因此，V2 不应该再把 `Detail Drawer` 设计成“临时拼出来的调试面板”，而应该视为 **WorkflowIR 的结构化可视化入口**。

### 1.4 当前 workflow_vm 能提供什么

`butler_main/orchestrator/workflow_vm.py` 已经能根据 `WorkflowIR` 自动决定 branch 应该走：

- `research_bridge`
- `execution_bridge`

并会追加 `workflow_vm_executed` 事件，同时把执行结果回写到 `record_branch_result(...)`。

这意味着产品层并不是单纯“看 child 正在跑”，而是可以明确显示：

- 当前 child 走的是哪种执行引擎
- 为什么走这个引擎
- 结果状态 / ok / result_ref 是什么

也就是说，V2 中的 child card / runtime drawer 应该以 `workflow_vm + workflow_ir + result_payload` 作为真实来源，而不是只显示一个 running badge。

### 1.5 当前 execution_bridge 能提供什么

`butler_main/orchestrator/execution_bridge.py` 已经把 orchestrator branch 映射进 agent runtime contract，并在结果 payload 中提供：

- `status`
- `summary`
- `agent_id`
- `mission_id`
- `node_id`
- `branch_id`
- `worker_profile`
- `metadata`
- `runtime_debug`
- `workflow_ir`
- `output_bundle_summary`
- `output_text`

其中 `runtime_debug` 已经能暴露：

- `agent_id`
- `runtime_key`
- `worker_profile`
- `cli`
- `model`
- `reasoning_effort`
- `why`

因此，V2 不应该再把“运行时细节”当作未来才会补的内容；当前代码已经足以支撑：

- runtime badge
- model / cli / why
- output summary
- branch terminal state

### 1.6 当前 runner 能提供什么

`butler_main/orchestrator/runner.py` 已经具备常驻 runner 的控制逻辑：

- `run_orchestrator_cycle(...)`
- `run_orchestrator_service(...)`
- `build_orchestrator_runtime_state_store(...)`

并且已经输出：

- `mission_count`
- `mission_status_counts`
- `ready_node_count`
- `running_node_count`
- `activated_node_count`
- `dispatched_count`
- `executed_branch_count`
- `completed_branch_count`
- `failed_branch_count`
- `non_terminal_branch_count`
- `phase`
- `note`

这非常适合作为：

- TUI 顶部状态栏
- Desktop 状态托盘 / overview panel
- “系统当前相位”视图

结论：

> **Butler-flow 当前已经具备一套足够支撑 TUI 与 Desktop 共用的观测 / 控制 / 细节展示能力。V2 的重点不是再造后端，而是把这套能力整理为共享 surface。**

---

## 2. V2 的核心定义

### 2.1 一句话定义

**Butler-flow V2 = 以 current orchestrator service / workflow_ir / workflow_vm 为真源的 Flow Workbench；TUI 与 Desktop 是同一套 Flow Surface 的两个前端。**

### 2.2 核心原则

1. **flow-first，不是 agent-first**
2. **surface-first，不是 page-first**
3. **双轨前端共享接口，不各写一套后端适配**
4. **不发明第二真源，当前真源仍在 orchestrator service / stores / workflow_session**
5. **先让 TUI 和 Desktop 共用对象模型，再分别做 UI 表达优化**
6. **先补结构化消费层，再补美观布局**

---

## 3. V2 纠偏：不再直接做 Electron 专属 PRD，而是先定义 Flow Surface

V2 的第一个产物，不应该是页面线框，而应该是：

## 3.1 Shared Flow Surface

建议新增一层共享 surface，例如：

```text
butler_main/
  flow_surface/
    dto.py
    service.py
    events.py
    mappers.py
    queries.py
    actions.py
```

这层的职责不是重写 orchestrator，而是把现有 orchestrator service 的返回值整理成前端友好的 DTO。

### 3.2 Shared DTO（建议）

#### FlowSummaryDTO
用于 flow 列表和 overview

字段建议：
- flow_id
- title
- mission_type
- status
- priority
- current_iteration
- node_count
- branch_count
- active_branch_count
- workflow_session_count
- node_status_counts
- branch_status_counts
- recent_event_types
- updated_at

#### FlowDetailDTO
用于主 flow 页面

字段建议：
- flow
- nodes
- branches
- delivery_events
- active_children
- recent_events

#### ChildDTO
用于 child card / active tray

字段建议：
- branch_id
- node_id
- node_title
- node_kind
- status
- worker_profile
- runtime_debug
- workflow_ir_summary
- workflow_session_summary
- result_ref
- updated_at

#### WorkflowSessionDTO
用于 child detail / drawer

字段建议：
- session_id
- template_id
- driver_kind
- status
- active_step
- role_bindings
- template
- shared_state_summary
- artifact_registry_summary
- collaboration_summary
- event_log_summary

#### FlowObservationDTO
用于 TUI / Desktop 首页概览

字段建议：
- missions
- active_branches
- recent_events
- runtime_snapshot

#### RunnerStatusDTO
从 runner summary 映射而来

字段建议：
- current_pid
- mission_count
- mission_status_counts
- ready_node_count
- running_node_count
- activated_node_count
- dispatched_count
- executed_branch_count
- completed_branch_count
- failed_branch_count
- non_terminal_branch_count
- phase
- note

---

## 4. TUI 与 Desktop 双轨应该如何分工

V2 不是“先做 Desktop，再顺手给 TUI 复用一点接口”；而应该是：

## 4.1 TUI 的角色

TUI 负责：

- 快速观察当前 flow 运行状态
- 快速切换 flow / branch / workflow session
- 快速查看 detail summary
- 快速执行 continue / pause / resume / cancel / append feedback 这类低成本控制动作
- 在终端中进行开发期调试与自检

TUI 的价值不是“比 Desktop 更酷”，而是：

- 更适合开发与运维
- 更适合在远程机 / SSH / Codex 协作时使用
- 更适合快速检视 flow 真相，不依赖桌面窗口

## 4.2 Desktop 的角色

Desktop 负责：

- 长时工作台
- 更丰富的 session stream 展示
- 更好的 artifact / markdown / result 打开体验
- 更好的 breadcrumb / tray / drawer 交互
- 更好的多面板信息密度

Desktop 不是取代 TUI，而是承接：

- 更复杂的流式会话体验
- 更好的视觉组织
- 更深的 child drill-down

## 4.3 双轨共享什么

TUI 与 Desktop 共享：

- 同一套 `flow_surface`
- 同一套 DTO
- 同一套 event schema
- 同一套 control actions
- 同一套 orchestrator 真源

TUI 与 Desktop 不共享：

- 具体 UI 布局
- 交互细节
- 渲染器

一句话：

> **共享数据面、动作面、事件面；不共享表现层。**

---

## 5. V2 的产品边界

### 5.1 V2 要做

#### Shared Surface
- flow surface DTO
- flow surface query service
- flow surface action service
- flow surface event schema

#### TUI
- Flow overview
- Flow detail
- Active children panel
- Workflow session detail
- Runtime / contracts / events quick view
- Control actions

#### Desktop
- Flow list
- Flow detail workbench
- Session stream
- Active children tray
- Detail drawer
- Child detail page

### 5.2 V2 不做

- 不把 Butler 重新做成 chat-first app
- 不把主视图做成 DAG 编辑器
- 不引入新的数据库真源
- 不做复杂多人协作
- 不做飞书远程入口
- 不把 TUI / Desktop 分别接不同后端
- 不先做花哨动效再补接口

---

## 6. V2 的页面 / 终端结构定义（实现导向版）

## 6.1 TUI 最小结构

### TUI Home
- 顶部：Runner 状态栏
- 左列：Flows 列表
- 中列：当前 flow summary
- 右列：Recent events / active children
- 底部：快捷操作提示

### TUI Flow Detail
- 上半：Flow summary + node / branch 状态统计
- 中间：Selected child / selected node / selected event
- 下半：Actions（pause/resume/cancel/feedback/refresh）

### TUI Workflow Session Detail
- session metadata
- template summary
- role bindings
- shared state keys
- artifact refs by step
- collaboration summary
- event log path / line count

注意：
TUI V2 不追求完整复刻 Desktop 的“流式 chat 气质”，重点是把当前 flow 的结构化真相看清楚。

## 6.2 Desktop 最小结构

### Desktop Home / Workbench
- 左侧：Flow list
- 中间：Flow detail + session stream
- 底部：Active children tray
- 右侧：Detail drawer

### Desktop Child Detail
- Breadcrumb
- Child summary
- Workflow session detail
- Branch runtime detail
- Events tab

### Desktop Drawer Tabs
- Summary
- Route
- Runtime
- Contracts
- Session
- Events
- Artifacts

---

## 7. 事件模型建议（TUI 与 Desktop 共用）

当前 service / workflow_vm / runner 已经天然是事件驱动的，因此 V2 应该定义统一事件模型。

建议新增：

```text
butler_main/flow_surface/events.py
```

事件建议：

- `flow.created`
- `flow.updated`
- `flow.controlled`
- `flow.tick`
- `child.dispatched`
- `child.updated`
- `child.completed`
- `workflow_ir.compiled`
- `workflow_session.created`
- `workflow_session.updated`
- `workflow_vm.executed`
- `judge.verdict`
- `runner.status`

注意：
当前仓库中很多事件名已经存在于 `LedgerEvent` 中，因此 V2 不应该推翻旧事件名，而应该做一层归一化映射。

---

## 8. 代码结构建议（实现导向）

## 8.1 共享 surface 层

```text
butler_main/
  flow_surface/
    __init__.py
    dto.py
    events.py
    mappers.py
    service.py
    queries.py
    actions.py
    runtime.py
```

职责：

- 调用 `orchestrator.service.OrchestratorService`
- 生成 DTO
- 为 TUI / Desktop 输出一致对象结构
- 提供 observation / control / detail 查询
- 提供 runner summary 归一化

## 8.2 TUI 层

```text
butler_main/
  flow_tui/
    __init__.py
    app.py
    state.py
    queries.py
    actions.py
    widgets/
      flow_list.py
      flow_summary.py
      child_list.py
      runner_status.py
      event_feed.py
      session_detail.py
```

注意：
这里的 TUI 技术栈在本文件中不强制；若现有本地未提交实现已选定 Textual，则沿用该方向；若没有明确提交，则以最轻量、最利于复用 `flow_surface` 的方案为准。

## 8.3 Desktop 层

```text
apps/
  butler-flow-desktop/
    electron/
    renderer/
      src/
        app/
        pages/
        modules/
        store/
        api/
        types/
```

但 V2 的重点不再是“先搭 Electron 壳”，而是：

1. 先有 shared surface
2. 再有 TUI 验证
3. 再有 Desktop 复用

---

## 9. V2 开发顺序（非常重要）

V1 的隐患之一就是默认了“先定桌面页面，再补后端”。

V2 必须按以下顺序：

### Phase 0：冻结真实对象边界

目标：
- 基于当前仓库确认真实对象：mission / node / branch / workflow_session / workflow_ir / runner summary
- 冻结 Flow Surface DTO 草案

产出：
- 本文档
- DTO 草案
- 事件草案

### Phase 1：抽 Shared Flow Surface

目标：
- 新增 `butler_main/flow_surface/`
- 封装 orchestrator service 到统一 DTO
- 不改动 orchestrator 真源语义

必须完成：
- FlowSummaryDTO
- FlowDetailDTO
- ChildDTO
- WorkflowSessionDTO
- FlowObservationDTO
- RunnerStatusDTO

### Phase 2：用 TUI 先消费 Shared Surface

目标：
- 先让终端前端把 DTO 跑通
- 用最小交互验证 shared surface 是否足够

必须完成：
- flow list
- flow detail
- active children
- workflow session detail
- actions
- refresh / polling

理由：
TUI 更轻、更快、更适合暴露 surface 设计问题。

### Phase 3：补 Desktop API / adapter

目标：
- 在 shared surface 之上补 Desktop consumption layer
- 若需要 HTTP/SSE，再做一层轻 API

注意：
这层不应该直接从 orchestrator service 生对象，而应该从 shared surface 走。

### Phase 4：Desktop Workbench

目标：
- flow list
- main workbench
- detail drawer
- active children tray
- child detail

### Phase 5：体验打磨

目标：
- breadcrumb
- better cards
- artifact open
- session drill-down
- runtime badges
- loading / empty / error states

---

## 10. 对 Codex 的执行要求

以下部分是给本地 Codex / 工程代理使用的实施要求。

## 10.1 总体要求

1. **禁止重新定义业务真源**
   - 不要新增另一套 flow store / desktop store / UI cache 真源
2. **禁止 TUI 与 Desktop 各自直接啃 orchestrator 原始对象**
   - 必须先抽 shared flow surface
3. **禁止把 Flow UI 做回 Agent UI**
   - 命名坚持 Flow / Node / Child / Branch / Workflow Session / Contracts
4. **禁止在 Phase 1 就引入 Electron 细节污染共享层**
   - 共享层必须纯 Python 业务适配
5. **禁止过早引入复杂 graph editor**
6. **禁止把 V2 扩张成全 Butler 总控台**

## 10.2 实现优先级

### P0
- flow_surface DTO
- flow_surface queries/actions
- TUI basic consumption

### P1
- Desktop adapter / API
- Desktop basic workbench

### P2
- richer event / runtime rendering
- artifact UX
- layout polish

## 10.3 每阶段完成后必须自检

### Shared Surface 自检
- DTO 字段是否只来自当前 orchestrator 真源
- 是否遗漏 workflow_ir / workflow_session / runtime_debug / recent events
- 是否把 raw objects 暴露给前端过多

### TUI 自检
- 是否能完整看见 flow 列表
- 是否能看见 active children
- 是否能 drill-down 到 workflow session summary
- 是否能做 pause/resume/cancel/feedback

### Desktop 自检
- 是否仍然是 flow-first
- 是否没有退化成 chat-first
- 是否没有把 drawer 变成杂乱 debug panel
- 是否能消费 shared surface，而不是绕过它

---

## 11. Codex 执行计划（建议一次请求内完成的大纲）

下面是一版适合直接交给 Codex 的实施任务书。

---

# 任务：实现 Butler-flow V2 的 shared surface，并以此支撑 TUI / Desktop 双轨

## 目标

基于当前仓库已经存在的：
- `butler_main/orchestrator/service.py`
- `butler_main/orchestrator/runner.py`
- `butler_main/orchestrator/workflow_ir.py`
- `butler_main/orchestrator/workflow_vm.py`
- `butler_main/orchestrator/execution_bridge.py`

实现一版 **Butler-flow V2 shared flow surface**，并优先让 TUI 消费它，再为 Desktop 预留 adapter / API。

## 实施要求

### 1. 新增 shared surface 目录

创建：

```text
butler_main/flow_surface/
  __init__.py
  dto.py
  mappers.py
  queries.py
  actions.py
  service.py
  events.py
  runtime.py
```

### 2. 在 dto.py 中定义 DTO

至少定义：
- FlowSummaryDTO
- FlowDetailDTO
- ChildDTO
- WorkflowSessionDTO
- FlowObservationDTO
- RunnerStatusDTO

要求：
- 使用 dataclass 或 pydantic-lite 风格
- 字段命名统一、稳定
- 不直接泄露太多底层 raw object

### 3. 在 mappers.py 中实现映射

把当前 orchestrator service / runner summary 映射到 DTO：

- `list_mission_overview` -> `list[FlowSummaryDTO]`
- `summarize_mission` -> `FlowDetailDTO`
- `list_active_branches` -> `list[ChildDTO]`
- `summarize_branch` -> `ChildDTO or BranchDetailDTO`
- `summarize_workflow_session` -> `WorkflowSessionDTO`
- `build_observation_window` -> `FlowObservationDTO`
- `run_orchestrator_cycle` / runner summary -> `RunnerStatusDTO`

### 4. 在 queries.py / actions.py 中整理统一入口

建议暴露：
- `list_flows(...)`
- `get_flow_detail(flow_id)`
- `list_active_children(flow_id)`
- `get_child_detail(branch_id)`
- `get_workflow_session_detail(session_id)`
- `get_observation_window(...)`
- `control_flow(flow_id, action)`
- `append_flow_feedback(flow_id, feedback)`

### 5. 在 service.py 中组装 FlowSurfaceService

封装当前 `OrchestratorService`，提供统一高层接口。

### 6. 若仓库已有 TUI 代码

要求：
- 不要推翻原 TUI
- 改为通过 `FlowSurfaceService` 取数
- 尽量薄改

### 7. 若仓库当前没有明确提交的 TUI 模块

则新增最小 TUI 骨架：

```text
butler_main/flow_tui/
  app.py
  state.py
  views/
```

要求：
- 只做最小 flow list / detail / child / session detail
- 先跑通 shared surface
- 不做花哨 UI

### 8. 先不要实现 Electron 细节

如果要为 Desktop 预埋，只允许：
- 预留 adapter / API 目录
- 定义接口
- 不要大规模实现桌面端壳层

### 9. 测试

新增测试，至少覆盖：
- DTO mapping
- observation window mapping
- workflow session mapping
- runner summary mapping
- control / feedback action wiring

### 10. 文档

新增一份短文档，说明：
- shared surface 的职责
- 为什么 TUI / Desktop 都必须走它
- 当前 V2 的边界

## 禁止事项

- 不要把 FlowSurfaceService 写成新的真源
- 不要把 orchestrator 逻辑复制一遍到 flow_surface
- 不要让 Desktop 直接吃 orchestrator raw payload
- 不要让命名退化成 agent/team/subagent-first
- 不要引入无必要依赖

## 完成标准

- shared flow surface 目录存在并可用
- TUI 能通过 shared surface 看 flow / child / session
- 后续 Desktop 能明确复用 shared surface
- 当前 flow 真源不被破坏

---

## 12. V2 验收标准

### 架构层
- 已存在 `flow_surface` 共享层
- TUI 与 Desktop 不再各自直连原始 orchestrator payload
- shared surface 不成为第二真源

### 产品层
- Flow list 与 Flow detail 来自真实 DTO
- Active children 可直接展示 branch / workflow_session / runtime 信息
- Workflow session detail 能展示 template / shared state / artifacts / collaboration / event log 摘要
- Contracts / runtime / events 可被结构化展示

### 过程层
- TUI 可以先跑通
- Desktop 在 shared surface 之上实现
- 后续页面设计不再脱离真实代码面

---

## 13. 最终结论

**Butler-flow Desktop V2 不应该继续被定义为“参考 Proma 做一个桌面壳”，而应该被定义为：在当前 orchestrator / workflow_ir / workflow_vm / runner / workflow_session 真源之上，抽出 shared flow surface，并让 TUI 与 Desktop 作为两个前端共用它。**

也就是说：

- V1 更偏“产品设想”
- V2 必须转成“实现对齐”

V2 的第一里程碑不是漂亮的 Electron 页面，而是：

1. 真实对象对齐
2. shared surface 成型
3. TUI 先跑通
4. Desktop 再复用

只有这样，Butler-flow 才不会再次滑回“看起来像 agent 产品，但没贴住自身 flow 真相”的老问题。
