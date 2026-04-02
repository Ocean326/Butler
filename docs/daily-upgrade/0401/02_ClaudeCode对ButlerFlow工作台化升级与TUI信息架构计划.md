# 0401 Claude Code 对 Butler Flow 工作台化升级与 TUI 信息架构计划

日期：2026-04-01  
状态：规划完成 + 第一轮实现已落地 / 当前真源  
所属层级：主落 L1 `Agent Execution Runtime`，辅用 L2 本地状态与 sidecars

关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [01_前台ButlerFlow入口收口与New向导V1.md](./01_前台ButlerFlow入口收口与New向导V1.md)
- [04_butler-flow工作流分级与FlowsStudio升级草稿.md](./04_butler-flow工作流分级与FlowsStudio升级草稿.md)
- [0331 前台WorkflowShell收口.md](../0331/02_前台WorkflowShell收口.md)
- [0331 04c-butler-flow完备升级与视觉设计计划.md](../0331/04c_butler-flow完备升级与视觉设计计划.md)
- [0331 前台butler-flow角色运行时与role-session绑定计划.md](../0331/06_前台butler-flow角色运行时与role-session绑定计划.md)
- [真源矩阵](../../project-map/03_truth_matrix.md)

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 系统性整理 Claude Code 的 UI / 交互 / runtime 外显逻辑，并把 `butler-flow` 升级成面向 `agent workflow cli` 的 `workspace / single flow 单栏双流 console`。 |
| 所属层级 | 主落 L1 `Agent Execution Runtime`；状态真源继续以本地 `workflow_state.json / turns.jsonl / actions.jsonl / events.jsonl / artifacts.json / role_sessions.json / handoffs.jsonl` 为准。 |
| 当前真源文档 | `0401/01` 继续定义 `new/resume/exec + setup picker` 入口口径；本文定义 `workspace`、single flow runtime、`/manage`、`supervisor/workflow` 单栏双流 console 的产品边界。 |
| 计划查看的代码与测试 | `butler_main/butler_flow/{app,runtime,events,models,state,tui/controller,tui/app}.py`，以及 `test_butler_flow.py`、`test_butler_flow_tui_controller.py`、`test_butler_flow_tui_app.py`。 |

## 一句话裁决

Butler 不照搬 Claude Code 的视觉，而是吸收它的 operator pattern：

- `task lifecycle`
- `agent / subagent lifecycle`
- `permission / approval explanation`
- `hook / tool / runtime events`
- `setup / session / preferences` 的显式分层

本轮落到 Butler 的产品面后，固定收口成四条边界：

1. `workspace` 是实例流的默认 home，也是当前 runtime browser。
2. `single flow page` 是聚焦后的 runtime console，可只读看 instance definition，但不承担 shared asset 管理。
3. `/manage` 只管理 `builtin + template` 两层 shared assets。
4. `/history` 与 `/flows` 都不再是产品级主入口：
   - `/history` 仅保留静默兼容 alias，语义折叠回 workspace/archive
   - `/flows` 仅保留迁移提示，统一导向 `/manage`

## 0. 参考对象与边界

### 0.1 本轮参考对象

本轮参考对象是本地已安装的 `Claude Code` bundle 与其可观察到的 operator vocabulary、settings、task/agent/permission/hook 信号。

本轮不再使用此前错误产出的外部研究稿；相关误产文档已删除，不作为任何当前裁决依据。

### 0.2 参考边界

- 当前可见的是本地安装包与 bundle signal，不是完整可导航的官方源码树。
- 因此本轮吸收的是：
  - 名词面
  - operator 面
  - 信息架构面
  - 事件外显面
- 不是源码级复刻，也不是 UI 仿制。

### 0.3 对 Butler 的落点

本轮只改 `butler-flow` 前台 L1/L2，不进入 `campaign/orchestrator` 主链。

## 1. 从 Claude Code 吸收什么

### 1.1 吸收 `task lifecycle`，不要只盯 transcript

Claude Code 最值得吸收的点，不是 transcript 本身，而是 transcript 之外还有一层更稳定的 task/operator 视图：

- task created
- task completed
- agent stop / subagent stop
- permission request
- tool use before / after
- setup / compact / preference flags

对 Butler 的直接启发：

- `flow` 不能只被看作“长对话”
- `flow` 必须被看作“有生命周期、有审批、有操作、有阶段推进、有角色切换”的 operator 对象

### 1.2 吸收 `agent/subagent lifecycle`，但翻译成 Butler 术语

Claude Code 的 `agent / subagent / task output` 到 Butler 的翻译固定为：

- `flow`
- `role`
- `role session`
- `handoff`
- `phase`
- `operator action`

因此 Butler 主屏必须显式露出：

- 当前 active role
- 当前 execution mode / session strategy
- 最新 handoff
- 角色是否切换

但不要求把全部 role 轨道永久塞进主屏。

### 1.3 吸收 `permission / approval explanation`

Claude Code 里，approval 不是一个附属命令，而是 operator 能理解的状态与解释面。

Butler 固定吸收为：

- `approval_state` 成为主屏显式状态
- `latest operator receipt` 必须可见
- `why paused / why ask operator / why resumed` 必须有固定外显位

### 1.4 吸收 `hook / tool / runtime event`

Claude Code 的另一个启发是：

- runtime event 不应该隐藏
- 但 runtime event 也不等于 transcript

对 Butler 的固定裁决：

- transcript 继续承担主叙事
- runtime event 作为审计与状态解释流独立存在
- judge / operator / promoted runtime event 必须被 controller 提升成结构化 rail

## 2. `butler-flow` 的目标产品壳

### 2.1 默认 home：`workspace`

当前 `single flow + /history + /flows + /settings` 的旧壳层，对单 flow 会话够用，但对 `agent workflow cli` 不够。

升级后的默认 home 固定为 `workspace`。  
它不是 archive 列表，而是“当前实例流 runtime browser”。

### 2.2 `workspace` 的职责

`workspace` 左侧只承载 instance list：

- recent instance flows
- 当前 focus
- `status / phase / approval badge`
- `workflow_kind / execution_mode / active_role`
- quick actions：`resume + inspect + manage`

`workspace` 右侧只承载 runtime preview：

- focused instance 的运行态摘要
- 最近 runtime steps
- latest signals
- raw runtime timeline 切换

它不负责 shared asset mutation；最多只显示：

- 当前 instance 来自哪个 builtin/template
- 如需改 shared definition，请跳 `/manage`

### 2.3 `single flow page` 的职责

`single flow page` 是聚焦实例后的 runtime console。

常驻：

- `flow_id / workflow_kind / effective_status / effective_phase`
- `attempt_count / max_attempts`
- `goal / guard`
- `execution_mode / session_strategy`
- `active_role`
- transcript 主线
- slash input / action bar

允许只读显示：

- instance definition 摘要
- source template / builtin 来源
- 当前 materialized phase plan

不负责：

- 直接改 builtin/template
- 把 `/manage` 资产操作混进 runtime console

### 2.4 `single flow console` 的现役子视图

`single flow page` 不再是“中心 transcript + 固定 operator rail”。  
现役结构改成：

- 单栏：单一主 console，在 `supervisor` 与 `workflow` 两个子视图间切换
- 切换方式：`Shift+Tab`
- 切换提示：并入底部现有 `mode=...` action bar 状态行，不再单独占一个右下角 widget

其中：

- `supervisor` 相关主信息不再单独占顶部区域，而是写进流开头
- `supervisor` 主体显示结构化的决定、审批、operator action、handoff、phase 等流式事件
- `workflow` 视图显示实时 workflow 输出，混合 raw execution 与 workflow 事件
- `handoff / role / operator` 等结构化对象优先进入流式事件，不再依赖固定 JSON 面板或独立 inspector

## 3. resident vs workspace vs detail

### 3.1 常驻信息

#### workspace 常驻

- flow list
- focused flow basic badges
- approval badge
- active role
- quick actions

#### single flow 常驻

- `supervisor` 结构化流
- `workflow` 实时流
- `supervisor` 流首主信息块
- `mode=...` action bar 内嵌的 `Shift+Tab` 切换提示

### 3.2 detail 收什么

detail 不再理解成“另一个主屏”，而是后续若需要 overlay/topic drilldown 时的兼容概念；当前单 flow 主面不再常驻右侧 inspector。

进入 detail 的内容固定包括：

- full step history
- full event timeline
- role sessions
- handoffs
- artifacts
- instance definition / phase plan
- runtime snapshot
- raw status payload

### 3.3 `/history` 的当前口径

`/history` 不再是产品级主入口。  
兼容期它只保留两层语义：

- 静默 alias：等价回到 workspace runtime browser
- archive / recovery 语义：未来若保留独立画面，也只承载终态、归档、恢复入口

因此不能再把 `/history` 写成“用户日常切 flow 的主导航面”。

## 4. `supervisor` 流 / `workflow` 流的视觉层级

### 4.1 一级：`supervisor` 结构化流

主控制台的 `supervisor` 视图固定承载：

- flow 主信息前导块
- approval / supervisor decision / judge verdict
- latest operator receipt
- handoff / role / phase / warning 等结构化事件

它回答的是“主脑为什么这么决定，当前卡在哪，下一步要谁做什么”。

### 4.2 一级：`workflow` 实时流

`workflow` 视图承载：

- codex segment / runtime event
- artifact 注册
- workflow 侧 handoff / phase 推进
- start / done / failed 等运行态标记

它回答的是“flow 此刻实际跑出了什么”。

### 4.3 兼容 detail / overlay

当前主面不再给 inspector 常驻位置。  
若后续需要展开，仍可从结构化事件二次钻取：

- role sessions / pending handoffs / recent handoffs
- artifacts
- flow definition / phase plan / runtime snapshot
- raw status payload 与结构化 sidecars

## 5. `workspace`、`/manage`、setup picker 的状态迁移与用户心智

### 5.1 setup picker

现役步骤固定为：

`goal -> mode -> level -> flow -> guard -> confirm`

进入后心智应是：

- 我在准备启动一个新的 instance flow
- 我还没进入运行态

离开后只允许三种结果：

1. 直接启动 builtin/template 对应的 instance
2. `free` 跳到 `/manage template:new ...` 先创建模板，再返回 confirm
3. 取消并回到 workspace

### 5.2 `/manage`

`/manage` 的现役定位不是 runtime 控制台，也不是“包含 instance 的全资产中心”。  
它只负责 shared flow assets：

- `builtin`
- `template`

它负责：

- shared asset list
- inspect definition
- create template
- edit builtin/template definition
- archive / redesign shared asset

它不负责：

- live instance lifecycle
- 单个 flow 的 pause / resume / retry / abort
- instance definition 日常编辑

### 5.3 `/flows`

`/flows` 从产品面完全移除。  
兼容期只保留：

- migration hint
- 自动跳转 `/manage`

不要再把 `/flows` 写成真实设计页、真实列表页或 setup 的正式下一跳。

### 5.4 用户心智统一

三者的用户心智固定为：

- setup：我要准备启动一个新的 instance
- workspace / single flow：我要看 runtime、继续执行、处理 operator 动作
- `/manage`：我要维护 shared builtin/template definitions

## 6. approval_state / action receipt / event timeline 的统一外显

### 6.1 统一原则

这三类对象不再各自找地方展示，而统一进入 `supervisor` 结构化流。

### 6.2 `supervisor` 视图常驻字段

- flow 主要信息头
- `approval_state`
- latest `supervisor decision`
- latest `operator receipt`
- latest `judge decision`
- promoted structured events

### 6.3 detail topic

- `approval`：显示完整审批上下文与 pending prompt
- `receipt`：显示最近 operator action receipts
- `timeline`：显示全量事件

### 6.4 controller 新投影

后续实现固定新增以下 UI 投影，不再让 Textual 直接拼 raw state：

- `workspace_payload`
- `single_flow_payload`
- `single_flow_payload.navigator_summary`
- `single_flow_payload.supervisor_view`
- `single_flow_payload.workflow_view`

`single_flow_payload.inspector`、`flow_console_payload / operator_rail_payload / role_strip_payload / detail_payload` 只保留兼容读取，不再代表现役单 flow 页结构。

### 6.5 事件统一要求

现有 `FlowUiEvent` shape 保持兼容，但允许新增 kind：

- `approval_state_changed`
- `role_handoff_created`
- `role_handoff_consumed`
- `manage_handoff_ready`

`timeline_payload()` 需要统一投影：

- `events.jsonl`
- `actions.jsonl`
- `turns.jsonl`
- `artifacts.json`
- `handoffs.jsonl`
- 当前 `flow_state`

## 7. 多 agent / flow 特有展示与操作

### 7.1 主屏只做紧凑摘要

主屏常驻：

- `execution_mode`
- `session_strategy`
- `active_role_id`
- compact role chips
- latest handoff summary

### 7.2 detail 再展开

展开后查看：

- `role_sessions`
- `role_turn_counts`
- handoff packet 全文
- role artifact visibility

### 7.3 flow 产品而非单 agent 会话产品

因此 Butler 主屏必须始终优先展示：

- flow 当前在哪个 phase
- flow 现在卡在谁身上
- operator 是否需要做动作
- 下一步是继续、重试、暂停还是等待审批

而不是只展示“最新一段 assistant 文本”。

## 8. 当前实施落点

本轮已落一版实现：

- 默认 home 已切到 workspace 语义的 runtime browser
- `/manage` 的 TUI 内容已收口到 shared builtin/template assets
- `/flows` 已退化为迁移提示并跳转 `/manage`
- `setup -> free` 已改成经 `/manage template:new ...` 创建模板再回到 setup
- `catalog_flow_id=template:<id>` 已支持直接启动 instance
- 单 flow 页已改成 `supervisor/workflow` 单栏双流 console；approval / judge / operator receipt / role handoff 进入结构化流式事件，主信息并入 `supervisor` 流开头

## 9. 实施约束

- 不重写 runtime，不引入新前台技术栈
- 不破坏 `exec new / exec resume` JSONL 与 `flow_exec_receipt`
- 不把 `campaign/orchestrator` 拉进本轮
- 不把多 agent 细节一次性塞满主屏
- 不把 approval / judge / operator 继续散落在 transcript、`/status`、raw actions 之间
- 不再把 `instance` 与 shared asset 管理心智混写

## 10. 对旧文档的覆盖关系

- `0401/01` 继续定义入口与 setup picker 基础口径
- `0331/06` 继续定义 role runtime / role session / handoff sidecar 基础合同
- `0331/04c` 继续作为 Textual TUI 的前序总计划
- 本文新增定义：
  - `workspace` 作为实例流 home
  - `single flow runtime console`
  - `supervisor/workflow` 单栏双流 console
  - `/manage` 只管 `builtin + template`
  - `/history` `/flows` 的退位规则
  - 多 agent 在主屏的紧凑摘要策略

因此，凡是涉及：

- single flow 与 workspace 的关系
- transcript / runtime / judge / operator 层级
- `/manage`、`/flows`、setup picker 的状态迁移
- approval / receipt / timeline 统一外显
- flow / role / handoff 的前台产品面

都以本文为先。
