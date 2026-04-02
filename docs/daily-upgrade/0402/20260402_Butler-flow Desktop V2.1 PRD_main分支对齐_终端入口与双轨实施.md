# Butler-flow Desktop V2.1 PRD（main 分支对齐 / 终端入口核对 / TUI + Desktop 双轨）

- 日期：2026-04-02
- 版本：V2.1
- 适用范围：**Butler-flow / orchestrator / workflow_session / terminal entry / Desktop**
- 分支基准：**main**
- 文档定位：在 V1 和 V2 的基础上，进一步用 `main` 分支的真实代码与当前可确认的终端入口来修正文档边界

---

## 0. V2.1 为什么存在

V1 的主要问题是：
- 页面和壳层想得比真实代码更快
- 默认按桌面端单线推进
- 没有严格贴住 `main` 分支里的现状
- 对“当前终端入口”和“未来 flow-native TUI”的关系没有拆清

V2 的主要改进是：
- 明确当前 Butler-flow 已经具备的真实对象与 service 能力
- 把未来方向改成 **shared flow surface + TUI / Desktop 双轨**

但 V2 还有一个缺口：
- 它虽然强调了双轨，却没有把 `main` 分支上**已经确认存在的终端入口**和**尚未在当前工具下明确定位的 flow-native TUI 模块**分开写清楚。

因此，V2.1 的目标是：

> **以 `main` 分支为唯一事实来源，分别确认 flow 真源、runner 真源、终端入口真源，再定义 Butler-flow 的 TUI / Desktop 双轨。**

---

## 1. main 分支已确认的真实入口

本节只写已经在 `main` 分支上成功读取到的文件。

## 1.1 仓库根入口

`README.md` 已明确说明：

- 主工程收口在 `butler_main/`
- 正式文档收口在 `docs/`
- 当前真实代码入口在 `butler_main/butler_bot_code/`
- 当前真实文档入口在 `docs/README.md`

这意味着：

1. V2.1 必须以 `main` 为准，不再参考默认分支的历史状态。
2. Butler 现在不是一个“前端 app 仓库”，它仍然是一个以 Python / PowerShell 主体为主的工程。
3. 任何新文档都要按 `docs/daily-upgrade/<MMDD>/` 归档。

## 1.2 当前正式文档入口

`docs/README.md` 已确认 `docs/` 是唯一正式文档入口，阶段性文档统一落在 `docs/daily-upgrade/<MMDD>/`。

这意味着：

- Butler-flow Desktop V2.1 的文档应该继续放在 `docs/daily-upgrade/0402/`
- 不再把新版本方案散落到其他路径

## 1.3 当前运行时身体层入口

`butler_main/butler_bot_code/README.md` 已明确：

- `butler_bot_code/` 是当前运行时身体层
- 负责对话主进程、heartbeat、配置、日志、测试与管理脚本
- 当前后台结构仍以 `talk 主进程 + heartbeat sidecar + self_mind` 为准
- 运行控制优先通过 `manager.ps1` 完成

这说明 Butler 当前**现役终端入口**不是一个纯 flow-app，而是先有统一的命令管理与状态面。

## 1.4 当前已确认终端入口：manager.ps1

`butler_main/butler_bot_code/manager.ps1` 在 `main` 分支上已经明确提供：

- `list`
- `status`
- `start`
- `stop`
- `restart`

并且它当前已经真实接管：

- 主进程启动 / 停止
- 状态检查
- PID 管理
- run / logs 路径
- 健康检查
- heartbeat 由主进程统一管理的现实

因此，V2.1 必须把这件事写清楚：

> **Butler 当前已经存在一个“终端管理/状态入口”，但它不是 flow-native TUI。**

它更接近：
- 运行控制面
- 进程/状态检查入口
- 运维型 terminal interface

而不是：
- flow list
- child drill-down
- workflow session detail
- contracts/runtime drawer 那种 flow workbench

这个区别必须明确，否则后续很容易把 `manager.ps1` 和未来的 Butler-flow TUI 混成一件事。

---

## 2. main 分支已确认的 Butler-flow 真源

## 2.1 OrchestratorService 已经是 flow 观察 / 控制真源

`butler_main/orchestrator/service.py` 在 `main` 上已确认存在，并且已经具备完整的 flow 消费面。

### 已确认能力

#### Flow / Mission
- `create_mission(...)`
- `get_mission(...)`
- `list_missions()`
- `list_mission_overview(...)`
- `summarize_mission(...)`
- `control_mission(...)`
- `append_user_feedback(...)`

#### Branch / Child
- `get_branch(...)`
- `list_branches(...)`
- `list_active_branches(...)`
- `summarize_branch(...)`
- `dispatch_ready_nodes(...)`
- `record_branch_result(...)`

#### Workflow Session
- `summarize_workflow_session(...)`

#### Event / Observation
- `list_delivery_events(...)`
- `list_recent_events(...)`
- `build_observation_window(...)`
- `tick(...)`

V2.1 的关键判断：

> **不管未来 TUI 还是 Desktop 长什么样，当前 flow 的真实消费入口都已经天然在 `OrchestratorService` 这一层。**

这意味着：
- 不应该再重新定义一个“给桌面端看的 flow 真源”
- 也不应该为 TUI 单独再造一套数据入口

---

## 2.2 WorkflowSession 已经足够支撑 drill-down

`service.py` 里的 `summarize_workflow_session(...)` 已经能输出：

- session_id
- template_id
- driver_kind
- status
- active_step
- session_root
- role_bindings
- metadata
- template summary
- shared_state summary
- artifact_registry summary
- collaboration summary
- event_log summary

所以，V2.1 进一步确认：

> **child detail / workflow session detail 不是未来才有的数据，而是当前代码已经具备的结构化展示对象。**

TUI 与 Desktop 都应直接围绕它设计 drill-down。

---

## 2.3 WorkflowIR 已经提供 route/runtime/contracts 结构化面

当前 Butler-flow 在 `workflow_ir` 层已经能提供：

- `workflow_kind`
- `driver_kind`
- `runtime_key`
- `agent_id`
- `worker_profile`
- `template_id`
- `workflow_session_id`
- `verification`
- `approval`
- `recovery`
- 以及 workflow template / role_bindings / workflow_inputs

这意味着：

- 未来 TUI 右侧详情区 / Desktop drawer 不应是“日志大杂烩”
- 它们应该是 `WorkflowIR` 的结构化投影

---

## 2.4 Runner 已经提供系统状态快照

当前 runner 层已经能提供：

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

这对 TUI / Desktop 都很重要，因为它决定了：

- 顶部状态条怎么做
- 系统当前 phase 如何表达
- 当前 flow workbench 如何接 runner summary

---

## 3. V2.1 对 TUI 的修正认识

这是本次版本最关键的部分。

## 3.1 先区分两个“终端层”

### A. 当前已确认存在的终端入口
也就是：
- `manager.ps1`
- 以及它背后的 run/log/state/status 体系

它的角色是：
- 运行控制
- 健康检查
- 进程管理
- 系统状态确认

### B. 未来要补齐的 flow-native TUI
它的角色才应该是：
- flow list
- flow detail
- active children
- workflow session detail
- route/runtime/contracts/events 的 flow-native 观察
- flow actions

V2.1 的结论是：

> **不要再把“当前 terminal entry”与“未来 flow-native TUI”混写。**

当前已经存在的是 terminal control plane；
未来要补的是 flow workbench in terminal。

---

## 3.2 V2.1 对“读 TUI”的现实结论

在当前可访问的 `main` 分支文件中，我已经明确读到了：

- 仓库正式入口
- 文档入口
- 运行时身体层入口
- manager.ps1 这套现役终端命令面
- orchestrator / service / workflow_session / workflow_ir / runner 这套 flow 真源

但在当前工具条件下，我**还没有成功定位到一个显式提交、可直接读取的 flow-native TUI 模块文件路径**。

因此 V2.1 采取的做法是：

1. **把已确认终端入口写进文档**，不再假装 Butler 当前已经有完整 flow TUI
2. **把 flow-native TUI 的目标明确挂在 shared flow surface 之上**
3. **后续若确认具体 TUI 文件路径，再继续做 V2.2 / 补丁文档，而不是在 V2.1 中编造它的现状**

这是为了避免再次出现“文档先行，但和真实代码脱节”的问题。

---

## 4. V2.1 的核心定义

### 一句话定义

**Butler-flow Desktop / TUI V2.1 = 以 `main` 分支上的 orchestrator 真源为核心、以当前 terminal control plane 为现实前提、以 shared flow surface 为中层、以 flow-native TUI 与 Desktop 为双前端的 Flow Workbench 计划。**

这个定义比 V2 多了两层约束：

1. `main` 分支优先
2. 当前 terminal control plane 与未来 flow-native TUI 分离

---

## 5. V2.1 的双轨结构

## 5.1 轨道 A：Terminal Control Plane（已存在）

即当前：
- manager.ps1
- run / logs / pid / state
- status / start / stop / restart

定位：
- Butler 系统级运行控制入口
- 运维、排障、进程管理

它不是：
- flow 浏览器
- session workbench
- child drill-down 界面

## 5.2 轨道 B：Flow-native TUI（待落实到明确模块）

定位：
- flow-first terminal workbench
- 读 `OrchestratorService` / runner / workflow_ir / workflow_session
- 面向开发、排障、SSH、远程机场景

它要承接：
- flow list
- flow detail
- active children
- workflow session detail
- contracts / runtime / event quick view
- flow actions

## 5.3 轨道 C：Desktop Workbench（未来桌面端）

定位：
- 更长时、更高密度的 flow 工作台
- 更好的会话流展示
- 更好的 artifact / markdown / detail drawer 表达

---

## 6. V2.1 的架构修订

## 6.1 不再直接写“桌面 API 层”

相比 V1，V2.1 更明确：

先有：
- `orchestrator` 真源
- `runner` 真源
- `manager.ps1` 终端控制入口

然后抽：
- `flow_surface`

再让：
- flow-native TUI
- Desktop

共同消费它。

## 6.2 Shared Flow Surface 仍然是第一优先级

建议目录继续保持：

```text
butler_main/
  flow_surface/
    __init__.py
    dto.py
    mappers.py
    queries.py
    actions.py
    service.py
    events.py
    runtime.py
```

职责：
- 把 `OrchestratorService` 变成稳定 DTO
- 把 runner summary 归一化
- 给终端 TUI 与 Desktop 提供一致对象结构

---

## 7. V2.1 对 TUI 的实现要求

## 7.1 TUI 第一阶段不追求“漂亮”

TUI 的第一价值不是像桌面 app，而是：
- 在终端里把 flow 真相看清楚
- 远程机 / SSH / 运维时能快速定位状态
- 开发者在最短反馈链路里验证 shared surface 是否够用

## 7.2 TUI 第一阶段必须有的界面

### TUI Home
- runner status bar
- flow list
- selected flow summary
- active children list
- recent events

### TUI Flow Detail
- flow summary
- node / branch status counts
- selected child detail
- quick actions

### TUI Workflow Session Detail
- session summary
- template summary
- role bindings
- shared state keys
- artifact refs by step
- collaboration summary
- event log summary

## 7.3 TUI 第一阶段与 terminal control plane 的关系

- 不替代 `manager.ps1`
- 不负责 start / stop 整个 Butler 系统级流程
- 优先专注于 flow 观察与 flow 控制
- 系统级操作仍可留在 manager.ps1

也就是说：

> **manager.ps1 管系统运行，flow-native TUI 管 flow 观察与 flow 控制。**

---

## 8. V2.1 对 Desktop 的实现要求

Desktop 的定位不变，但必须服从以下顺序：

1. 先确认 `main` 的 flow 真源
2. 先抽 `flow_surface`
3. 先让 terminal flow workbench 跑通
4. 再让 Desktop 复用

Desktop 仍建议保留：
- flow list
- main workbench
- session stream
- active children tray
- detail drawer
- child detail page

但它不再是第一优先级。

---

## 9. V2.1 的实施顺序

### Phase 0：main 分支对齐
- 以 `main` 为唯一事实来源
- 冻结当前已确认终端入口与 flow 真源

### Phase 1：抽 shared flow surface
- DTO
- mappers
- queries/actions
- runner summary mapping

### Phase 2：补 flow-native TUI
- 先最小 terminal workbench
- 明确与 `manager.ps1` 的边界

### Phase 3：Desktop 复用 shared surface
- 不直连 raw orchestrator payload
- 不重造真源

### Phase 4：体验增强
- breadcrumb
- artifact 打开
- better runtime rendering
- better drill-down

---

## 10. V2.1 给 Codex 的附加要求

相比 V2，这里增加两条强约束：

1. **以 `main` 分支为准，不要再拿默认分支历史文件当现状**
2. **不要把 `manager.ps1` 误写成 flow-native TUI，也不要假设 flow-native TUI 已经完整存在**

### Codex 必须执行的边界判断

#### 已确认存在
- terminal control plane：manager.ps1
- flow 真源：orchestrator service / workflow_session / workflow_ir / runner

#### 需要新建或补齐
- shared flow surface
- flow-native TUI
- Desktop 对 flow_surface 的消费层

---

## 11. V2.1 最终结论

**Butler-flow Desktop V2.1 的核心，不是“再写一版桌面 PRD”，而是先把 `main` 分支上的真实入口拆清楚：**

- 现在已经存在的，是 terminal control plane（manager.ps1 这一套）
- 现在已经存在的，还有 flow 真源（orchestrator / workflow_session / workflow_ir / runner）
- 现在还需要补齐的，是 flow-native TUI
- 之后 Desktop 再复用 shared flow surface

所以，V2.1 的正确路线是：

> **main 对齐 -> shared flow surface -> flow-native TUI -> Desktop 复用**

而不是：

> 继续先按 Proma / Codex 的壳子想页面，再倒推 Butler-flow。

这也是 Butler-flow 后续要避免再次脱离真实代码面的关键。