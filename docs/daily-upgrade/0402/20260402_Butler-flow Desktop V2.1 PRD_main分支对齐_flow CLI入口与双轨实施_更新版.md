# Butler-flow Desktop V2.1 PRD（main 分支对齐 / flow CLI 入口分析 / TUI + Desktop 双轨）

- 日期：2026-04-02
- 版本：V2.1 更新版
- 适用范围：**Butler-flow / orchestrator / workflow_session / flow CLI / TUI / Desktop**
- 分支基准：**main**
- 文档目标：在此前 V2.1 的基础上，进一步确认 `main` 分支下 **flow CLI 的真实操作入口**，并据此修正 Butler-flow 的终端与桌面双轨计划

---

## 0. 本次更新的关键结论

相比上一版 V2.1，这次最重要的新结论是：

> **Butler 当前的终端链路不是“两层”，而是“三层”。**

### 第一层：系统级 terminal control plane（已存在）
即：
- `butler_main/butler_bot_code/manager.ps1`

职责：
- 主进程 / 心跳 / 状态 / PID / 日志的启动、停止、重启、查看
- 系统级运维与排障

### 第二层：flow runtime CLI（已存在）
即：
- `butler_main/orchestrator/runner.py`
- 真实逻辑位于 `butler_main/orchestrator/interfaces/runner.py`

职责：
- 启动 orchestrator runner
- 执行 tick / dispatch / execute / recover
- 推进 mission / node / branch 的生命周期
- 写 run_state / watchdog_state / pid / note

### 第三层：flow-native interactive TUI（待补齐）
也就是未来要实现的：
- flow list
- active children
- workflow session detail
- runtime / contracts / events quick view
- flow actions

因此，V2.1 更新版最核心的修正是：

> **不要再把 `manager.ps1` 和未来的 TUI 之间缺失的那一层忽略掉。当前真正会推进 flow 的 CLI 入口，其实已经存在，并且就是 orchestrator runner CLI。**

---

## 1. main 分支上已确认的 flow CLI 入口

## 1.1 runner.py 现在只是薄入口

在 `main` 分支上，`butler_main/orchestrator/runner.py` 已经不再承载主要实现，而是一个薄转发入口：

- 从 `butler_main/orchestrator/interfaces/runner.py` 导入：
  - `main`
  - `run_orchestrator_cycle`
  - `run_orchestrator_service`
  - runtime state 相关常量与 builder
- 最后通过 `if __name__ == "__main__": sys.exit(main())` 作为脚本入口

这说明：

1. `runner.py` 仍然是 CLI 可调用入口
2. 真实 CLI 协议和行为已经被整理进 `interfaces/runner.py`
3. `main` 分支的 orchestrator 正在向“接口层 + 入口薄壳”收口

---

## 1.2 真正的 flow CLI 协议在 interfaces/runner.py

`butler_main/orchestrator/interfaces/runner.py` 已确认提供了完整 CLI 行为。

### 直接可见的 CLI 参数

当前 `main()` 里通过 argparse 暴露：

- `--config`（必填）
- `--once`（可选）

这说明 runner CLI 至少支持两种运行模式：

### A. 单次循环模式
- 通过 `--once`
- 用于：
  - 单轮 tick / dispatch / execute 检查
  - 调试
  - 冒烟测试
  - 未来 TUI 的“手动 refresh / 单次推进”后端支撑

### B. 常驻服务模式
- 不带 `--once`
- 进入循环执行 `run_orchestrator_service(...)`
- 用于：
  - 后台常驻推进 flow
  - 周期性调度
  - 自动恢复
  - 自动派发
  - 自动执行

这意味着当前 flow CLI 本质上不是“交互式命令菜单”，而是：

> **一个 daemon-style / runner-style 的执行入口。**

---

## 1.3 当前 runner 默认已经是“主动推进型”而不是“只观察型”

这是本次分析里最关键的技术事实之一。

在 `interfaces/runner.py` 中：

- `_auto_dispatch_enabled(config_snapshot)` 默认值是 `True`
- `_auto_execute_enabled(config_snapshot)` 默认值也是 `True`

这意味着：

### 当前默认行为不是：
- 只看有哪些 mission
- 只做 observation
- 只打印状态

### 当前默认行为实际上是：
- tick
- 找 ready nodes
- dispatch branches
- 根据 workflow_vm / execution_bridge / research_bridge 自动执行
- 回写结果
- 生成 summary/note/run_state/watchdog_state

换句话说：

> **当前 flow CLI 的现实形态，是“会主动跑 flow 的后台 runner”，不是“只供人观察的 flow console”。**

这对后续产品规划影响非常大：

- 未来 TUI 不应该和 runner CLI 混成一个进程
- TUI 主要做观察 + 控制
- runner CLI 继续做后台推进

---

## 1.4 当前 runner 还负责“恢复中断 branch”

`interfaces/runner.py` 里还有一层非常重要的逻辑：

- `_recover_interrupted_branches(...)`

它会：
- 扫描状态为 `queued / leased / running` 的 branch
- 判断是否需要恢复
- 将其置为失败并把 node 拉回 `ready`
- 根据是否有 session 决定 `recovery_action = resume / retry`
- 追加 `branch_recovered_after_restart` 事件

这说明 runner CLI 不只是执行器，还承担：

- 启动时修复现场
- 重启后续跑
- 中断恢复

因此，当前 flow CLI 更准确的定义不是“命令行工具”，而是：

> **orchestrator runtime service entry**

---

## 1.5 当前 runner 还负责进度 note / 状态文件输出

`interfaces/runner.py` 明确维护：

- PID
- watchdog state
- run state
- phase
- note

并通过 `_write_progress(...)` 持续写入运行状态。

它输出的 note 会反映：
- cycle started
- dispatch 了哪些 branches
- execute 了哪些 branches
- recovered branches
- missions / ready_nodes / running_nodes / executed / failed / completed 等统计

这件事对未来 TUI / Desktop 很重要，因为它意味着：

### 未来前端不一定要直接把 runner 当黑盒
而是可以消费：
- runner state file
- runner summary DTO
- progress note

因此，V2.1 更新后应当把 `RunnerStatusDTO` 的优先级进一步提高。

---

## 2. flow CLI 的现实分层：V2.1 更新版定义

本节是对上一版 V2.1 的正式修订。

## 2.1 现在 Butler 的终端链路应拆成三层

### Layer A：System Control Plane（已存在）
入口：
- `butler_main/butler_bot_code/manager.ps1`

职责：
- start / stop / restart / status
- Butler 系统进程级控制
- 主链路健康检查
- 日志 / pid / run 状态排障

### Layer B：Flow Runtime CLI（已存在）
入口：
- `butler_main/orchestrator/runner.py`
- `butler_main/orchestrator/interfaces/runner.py`

职责：
- 加载 orchestrator config
- build runtime stack / service
- tick / dispatch / execute
- 恢复中断 branches
- 写 run/watchdog state
- 输出 phase/note

### Layer C：Flow-native Interactive TUI（待实现或待继续核对）
目标：
- 面向人交互的 flow 观察与控制界面
- flow list
- active children
- workflow session detail
- runtime / contracts / events
- flow actions

这个三层结构是 V2.1 的核心修正。

---

## 2.2 现在真正缺的不是“flow CLI”，而是“interactive flow CLI / TUI”

过去容易产生一种误判：
- 以为 Butler 还没有 flow CLI 入口

但从 `main` 上的代码看，这个判断已经不准确。

更准确的说法应该是：

### 已经有：
- system CLI / process CLI
- flow runtime CLI / runner CLI

### 还缺：
- interactive flow CLI / flow TUI

所以规划上不能再写成：
- “先做 TUI，补一个 flow CLI”

而应该写成：
- “在已有 system CLI 与 flow runtime CLI 基础上，补 flow-native interactive TUI”

---

## 3. V2.1 对 shared flow surface 的修正

有了 flow runtime CLI 这一层后，shared flow surface 的定位更清楚了。

## 3.1 shared flow surface 不只是给 Desktop 用

它要同时服务三类消费方：

### A. Flow-native TUI
需要：
- flow list
- flow detail
- child detail
- workflow session detail
- runner summary
- actions

### B. Desktop
需要：
- richer cards
- session stream
- drawer
- child drill-down

### C. Runtime status readers
需要：
- runner 状态摘要
- progress/note
- phase

因此，shared flow surface 里除了 mission / branch / session DTO 外，还应明确包括：

- `RunnerStatusDTO`
- `RuntimeProgressDTO`

---

## 3.2 shared flow surface 的输入源现在应写成“双真源输入”

V2 里更偏向写成 orchestrator service 单源；
V2.1 更新后应改为：

### 业务对象真源
- `OrchestratorService`
- `WorkflowSession`
- `WorkflowIR`
- `LedgerEvent`

### 运行状态真源
- `interfaces/runner.py` 输出的 run_state / watchdog_state / summary / note

因此，shared flow surface 应承担两件事：

1. 业务对象 DTO 化
2. runner 状态 DTO 化

---

## 4. 对 flow-native TUI 的计划修正

## 4.1 TUI 不负责“跑 flow”

这是 V2.1 最重要的规划修正之一。

既然现在已经存在 runner CLI，并且默认主动 dispatch + execute，那么未来的 TUI 就不应承担：

- 后台循环推进 flow
- 直接替代 runner
- 混合运行控制与交互展示

未来 TUI 的职责应收束为：

### 观察
- 当前有哪些 flows
- 哪些 children active
- 哪些 workflow sessions 在运行
- 当前 phase / note 是什么

### 控制
- pause / resume / cancel flow
- append user feedback
- 可能的 dispatch / single-step action（后续可选）

### 深入
- 查看 workflow session
- 查看 runtime / contracts / recent events

简言之：

> **runner CLI 是 engine，TUI 是 console。**

---

## 4.2 TUI 第一阶段最该做的是“读 runner + 读 service”

第一版 interactive TUI 的最小闭环应是：

### 左侧
- flows

### 顶部
- runner status bar
- phase
- note
- executed / failed / completed counters

### 中间
- selected flow summary
- nodes / branches / active children

### 右侧或下方
- selected child / selected workflow session detail
- recent events
- contracts / runtime summary

注意：
第一版 TUI 不追求模拟 ChatGPT / Codex 的会话感，而是优先做：
- 状态清晰
- drill-down 清晰
- 远程机上可用
- 与 runner 职责不冲突

---

## 5. 对 Desktop 的计划修正

Desktop 的定位不变，但优先级继续后移一步。

此前 V1 很容易让人以为：
- 桌面端是 flow 的第一前台

但现在从 `main` 看，更合理的顺序应是：

1. system control plane 已存在
2. flow runtime CLI 已存在
3. 先补 interactive flow TUI
4. 再让 Desktop 复用 shared flow surface

因此，Desktop 的实施前提现在更明确了：

### 必须先有
- RunnerStatusDTO
- FlowSurfaceService
- TUI 验证过的 object model

### 再做
- richer session stream
- cards / tray / drawer
- artifact UX
- breadcrumb / drill-down

---

## 6. V2.1 更新后的实施顺序

### Phase 0：对齐 main 分支入口
冻结以下三个事实：

- `manager.ps1` = system control plane
- `interfaces/runner.py` = flow runtime CLI
- `OrchestratorService` = flow business truth source

### Phase 1：抽 shared flow surface
新增：
- mission / branch / session DTO
- runner status DTO
- runtime progress DTO

### Phase 2：先补 interactive flow TUI
目标：
- 不取代 runner
- 读取 service + runner status
- 提供 flow 观察与 flow 控制

### Phase 3：Desktop 复用 shared flow surface
目标：
- richer workbench
- session stream
- detail drawer
- active children tray

### Phase 4：体验增强
- artifact open
- route/runtime/contracts 更丰富表达
- 更好的 recovery / feedback 可视化

---

## 7. 给 Codex 的更新版执行要求

本节用于替换此前较模糊的执行描述。

## 7.1 必须明确三层入口，不允许混写

在实现文档、注释、PR 描述里，必须明确区分：

### system control plane
- manager.ps1

### flow runtime CLI
- orchestrator runner / interfaces.runner

### interactive flow TUI
- 新实现的终端工作台

禁止把这三者写成同一个“CLI”。

---

## 7.2 先补 shared flow surface，再补 TUI

shared flow surface 现在至少应包含：

- `FlowSummaryDTO`
- `FlowDetailDTO`
- `ChildDTO`
- `WorkflowSessionDTO`
- `FlowObservationDTO`
- `RunnerStatusDTO`
- `RuntimeProgressDTO`

其中：
- 前五个主要来自 `OrchestratorService`
- 后两个来自 runner summary / state file / note

---

## 7.3 TUI 不能直接嵌 runner 主循环

Codex 实现时应遵守：

### 可以做
- 读取 runner 状态
- 调 service 查询详情
- 发 control_mission / append_user_feedback
- 未来发单步动作

### 不应做
- 在 TUI 进程里接管常驻 `run_orchestrator_service(...)`
- 把 TUI 变成新的 daemon
- 让 UI 生命周期和 runner 生命周期强耦合

---

## 8. V2.1 更新版结论

**现在 Butler-flow 的终端入口已经不是空白。**

在 `main` 分支上，已经可以明确拆成三层：

1. **manager.ps1**：系统级 terminal control plane
2. **orchestrator runner CLI**：flow runtime CLI，负责真正推进 flow
3. **未来 interactive TUI**：flow-native 观察与控制界面

所以，V2.1 更新后的正确路线是：

> **main 对齐 -> 明确三层 CLI/terminal 结构 -> 抽 shared flow surface -> 先补 interactive TUI -> Desktop 复用**

而不是：

> 继续把“终端入口”笼统写成 TUI，或者继续把桌面端当第一落点。

这版更新的意义在于，它终于把 Butler 当前已经存在的 runtime CLI 能力写进了规划，从而让后续的 TUI / Desktop 设计真正贴住现实代码。