# 0321 research / agents_os / protocol / workflow / application 系统梳理

更新时间：2026-03-21 01:12
时间标签：0321_0112

## 一、这份文档解决什么

现在 Butler 已经同时有：

- `agents_os.runtime`
- `agents_os.protocol`
- `agents_os.workflow`
- `heartbeat` 的应用侧 workflow adapter
- `research` 的 scenario runner / scenario instance

如果不系统梳理，很容易出现两个问题：

1. 抽象层级混淆
2. 不知道 `heartbeat` 和 `brainstorm / paper_discovery / idea_loop` 分别落在哪一层

这份文档的目标就是把当前系统按“抽象等级”重新排平，并明确当前状态。

---

## 二、一句话总图

当前最适合理解 Butler 的方式不是“一套大平台”，而是五层：

1. `Runtime Core`
2. `Protocol`
3. `Workflow`
4. `Application / Scenario`
5. `Entrypoint / Adapter`

对应一句话：

> `agents_os.runtime` 负责运行时，`protocol` 负责契约，`workflow` 负责控制流，`application/scenario` 负责业务语义，`entrypoint/adapter` 负责接到 heartbeat / talk / codex。

---

## 三、按抽象等级梳理

## 3.1 L0: Runtime Core

位置：

- `butler_main/agents_os/runtime/contracts.py`
- `butler_main/agents_os/runtime/kernel.py`
- `butler_main/agents_os/runtime/instance.py`
- `butler_main/agents_os/runtime/instance_store.py`
- `butler_main/agents_os/runtime/host.py`
- `butler_main/agents_os/runtime/session_support.py`

负责什么：

- `RunInput / Run / RunResult`
- worker dispatch
- `AgentRuntimeInstance`
- run/session checkpoint
- resume
- artifact / trace / context 最小设施

它不负责什么：

- 业务场景语义
- 具体 research step 含义
- heartbeat 任务业务判断
- 三个 research 应用的业务输出定义

当前状态：

- 已落地
- 已有 `RuntimeHost + AgentRuntimeInstance + session/workflow checkpoint`
- 已可支撑基础执行与恢复

一句话：

> 这一层回答“怎么跑”，不回答“跑什么业务”。

---

## 3.2 L1: Protocol

位置：

- `butler_main/agents_os/protocol/receipts.py`
- `butler_main/agents_os/runtime/contracts.py`
- `butler_main/agents_os/verification/*`
- `butler_main/agents_os/governance/*`
- `butler_main/agents_os/recovery/*`

当前核心对象：

- `AcceptanceReceipt`
- `StepReceipt`
- `HandoffReceipt`
- `DecisionReceipt`
- `VerificationReceipt`
- `ApprovalTicket`
- `RecoveryDirective`

负责什么：

- 统一 step/handoff/decision/acceptance 等横切契约
- 让 workflow、adapter、manager、store 能通过同一种结构接力

它不负责什么：

- step 顺序
- 场景生命周期
- 文件落盘位置
- 业务内容生成

当前状态：

- `Step / Handoff / Decision` 最小主链已落地
- `Acceptance / Verification / Approval / Recovery` 仍是并行对象，还没完全统一到单主链语义

一句话：

> 这一层回答“运行结果怎么表达和传递”，不回答“当前该走哪一步”。

---

## 3.3 L2: Workflow

位置：

- `butler_main/agents_os/workflow/models.py`
- `butler_main/agents_os/runtime/workflows.py`（兼容导出）

当前核心对象：

- `WorkflowStepSpec`
- `WorkflowSpec`
- `WorkflowCursor`
- `WorkflowCheckpoint`
- `WorkflowRunProjection`
- `FileWorkflowCheckpointStore`

负责什么：

- step 序列和 step 元信息
- cursor
- checkpoint
- projection
- handoff/decision 的工作流位置

它不负责什么：

- 具体研究主题内容
- 检索或实验的业务细节
- 具体能力包执行

当前状态：

- 轻量 workflow 层已落地
- 已支持 cursor/checkpoint/projection
- 仍不是通用 orchestrator

一句话：

> 这一层回答“业务控制流如何推进”，但不直接执行业务内容。

---

## 3.4 L3: Application / Scenario

这一层要分成两类看。

### A. Butler 应用侧

当前已明确的应用是：

- `heartbeat`

位置：

- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_workflow.py`
- `butler_main/butler_bot_code/butler_bot/services/task_ledger_service.py`

负责什么：

- 把 heartbeat 的任务编排投影成 generic workflow/protocol
- 把 branch 结果转成 receipts
- 把 workflow projection 落进 task ledger

### B. Research 场景侧

当前已明确的三个应用场景是：

- `brainstorm`
- `paper_discovery`
- `idea_loop`

位置：

- `butler_main/research/scenarios/*`
- `butler_main/research/manager/code/research_manager/services/scenario_runner.py`
- `butler_main/research/manager/code/research_manager/services/scenario_instance_store.py`

负责什么：

- 提供场景级 workflow spec
- 提供 step 语义
- 提供 output contract
- 提供当前 active step / output_template / scenario instance

当前状态：

- 三个 scenario 都已具备：
  - spec
  - runner
  - instance/state store
- 但还没有真正的“step 执行层”

一句话：

> 这一层回答“当前应用/场景在业务上到底是什么”。

---

## 3.5 L4: Entrypoint / Adapter

位置：

- Butler heartbeat 主链
- `research_manager/interfaces/heartbeat_entry.py`
- `research_manager/interfaces/talk_bridge.py`
- `research_manager/interfaces/codex_cli_entry.py`

负责什么：

- 接住不同入口
- 统一成 `Invocation`
- 送到 manager 或 adapter

它不负责什么：

- 状态真源
- workflow 真源
- 业务真源

一句话：

> 这一层回答“谁在调用系统”，不回答“系统内部怎么表达语义”。

---

## 四、两类 instance / state 的区别

当前系统里已经有两类运行态，不应该混掉。

## 4.1 `AgentRuntimeInstance`

位置：

- `butler_main/agents_os/runtime/instance.py`

它是什么：

- 通用 runtime 层的 agent instance

它保存：

- run/session/workflow checkpoint 指针
- 当前 goal
- 当前 handoff
- runtime roots
- health/recovery 状态

适用范围：

- 通用运行时执行
- Butler heartbeat runtime host
- 未来通用 agent execution

## 4.2 `ResearchScenarioInstance`

位置：

- `butler_main/research/manager/code/research_manager/services/scenario_instance_store.py`

它是什么：

- research 场景线程运行态

它保存：

- `scenario_instance_id`
- `unit_id / scenario_id / workflow_id`
- `session_id / task_id / workspace`
- `workflow_cursor`
- `active_step`
- `output_template`
- `last receipts`
- `state`

适用范围：

- `brainstorm / paper_discovery / idea_loop`
- `talk / heartbeat / codex` 跨入口共享

## 4.3 关系

当前关系应理解为：

- `AgentRuntimeInstance` 是通用执行容器
- `ResearchScenarioInstance` 是 research 业务线程状态

现在这两者是并行层，不是一一映射层。

一句话：

> runtime instance 管“执行态”，scenario instance 管“业务场景态”。

---

## 五、heartbeat 和三个应用的系统对应表

## 5.1 heartbeat

业务定位：

- Butler 自身调度应用

对应层级：

- `Application`：heartbeat 任务编排
- `Workflow`：`heartbeat_round`
- `Protocol`：branch 级 receipts
- `Runtime`：可接 `RuntimeHost`

当前状态：

- workflow projection 已落地
- receipts 已落地
- task ledger 已接上
- 但 heartbeat 仍主要是 Butler 私有应用，不是 research scenario

一句话：

> heartbeat 是 Butler 系统自有应用，不是 research 三场景之一。

## 5.2 brainstorm

业务定位：

- 头脑风暴 / 项目下一步收敛

对应层级：

- `Application/Scenario`：`brainstorm`
- `Workflow`：`brainstorm_session`
- `Protocol`：scenario step/handoff/decision receipts
- `State`：`ResearchScenarioInstance`

当前 step：

- `capture -> cluster -> expand -> converge -> archive`

当前状态：

- 已有 scenario spec
- 已有 runner
- 已有 instance/state store
- 还没有真实执行器

## 5.3 paper_discovery

业务定位：

- 自动搜索 / 文献候选集 / digest

对应层级：

- `Application/Scenario`：`paper_discovery`
- `Workflow`：`paper_discovery_round`
- `Protocol`：scenario step/handoff/decision receipts
- `State`：`ResearchScenarioInstance`

当前 step：

- `topic_lock -> query_plan -> search -> screen -> digest`

当前状态：

- 已有 scenario spec
- 已有 runner
- 已有 instance/state store
- 还没接真实搜索与筛选执行层

## 5.4 idea_loop

业务定位：

- idea -> code -> result 的迭代闭环

对应层级：

- `Application/Scenario`：`idea_loop`
- `Workflow`：`idea_loop_round`
- `Protocol`：scenario step/handoff/decision receipts
- `State`：`ResearchScenarioInstance`

当前 step：

- `idea_lock -> plan_lock -> iterate -> final_verify -> archive`
- 失败/收敛不足时：
  - `final_verify + retry/refine -> recover`

当前状态：

- 已有 scenario spec
- 已有 runner
- 已有 instance/state store
- 还没接真实实验/代码改进执行层

---

## 六、application 层现在到底是什么状态

这是最容易混淆的地方。

当前“应用层”并不是一个统一的 `application_platform`，而是两种不同成熟度的东西：

### A. 已工程化应用

- `heartbeat`

特点：

- 已 deeply wired into Butler
- 已有真实任务账本和业务状态
- 已有 workflow/protocol 投影

### B. 已有场景骨架的 research 应用

- `brainstorm`
- `paper_discovery`
- `idea_loop`

特点：

- 已有 scenario asset + runner + instance store
- 还没有完整 step execution 层

### C. 仍然只是概念位

- `application_flow`

当前定义：

- `application_flow = 场景资产包 + workflow 规格 + 出口格式`

当前状态：

- 只是概念维护
- 还没有独立 registry / compiler / generator

一句话：

> 现在真正落到代码里的“应用层”，实质上是 heartbeat 应用和三个 research scenario，而不是一个统一的平台层。

---

## 七、当前系统成熟度判断

如果按成熟度看，当前大致是：

## 7.1 已稳定

- `agents_os.runtime`
- `protocol` 最小主链
- `workflow` 最小 cursor/checkpoint/projection
- heartbeat adapter 投影

## 7.2 已成型但仍轻量

- `ResearchManager`
- `scenario_runner`
- `scenario_instance_store`
- 三个 research scenario

## 7.3 仍未完成

- research step 真执行层
- state patch 真回灌
- application_flow 平台化
- protocol 的更完整统一

---

## 八、当前最合理的理解方式

截至现在，最不容易走偏的理解方式是：

1. `agents_os.runtime`
   - 是通用运行时底座
2. `agents_os.protocol`
   - 是横切契约层
3. `agents_os.workflow`
   - 是通用轻量控制流层
4. `heartbeat`
   - 是 Butler 自有应用，已经用上 workflow/protocol
5. `research scenarios`
   - 是三类业务场景应用，已经用上 workflow/protocol + scenario instance
6. `application_flow`
   - 目前只是未来术语，不是现有正式代码层

---

## 九、最终结论

如果把现在整个系统压成一句话：

> Butler 当前不是“一个已经完成的多 agent 平台”，而是“一个以 `agents_os.runtime` 为底、以 `protocol/workflow` 为中层、以 heartbeat 和 research scenarios 为应用层的逐步成型系统”。

再压缩成更工程的话：

- `runtime` 管执行
- `protocol` 管契约
- `workflow` 管推进
- `scenario/application` 管业务
- `entrypoint/adapter` 管接线

而在这之上：

- `heartbeat` 是当前最成熟的系统内应用
- `brainstorm / paper_discovery / idea_loop` 是当前最重要的 research 应用骨架
- `application_flow` 还不是正式层，只是未来概念位
