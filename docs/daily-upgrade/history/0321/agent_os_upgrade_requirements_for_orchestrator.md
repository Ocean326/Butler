# agent_os 升级需求与计划（面向新 Orchestrator Core）

更新时间：2026-03-21
时间标签：0321_agent_os_upgrade_for_orchestrator

## 1. 这份文档解决什么

路线 B 的目标不是重写 `agent_os`，而是新起一个独立的 `orchestrator core`，并把 `agent_os` 作为底层支撑复用。

但在梳理现状后可以明确看到：

- `agent_os` 当前已经具备 runtime / protocol / workflow / state 的底座
- 但它还没有完全准备好直接承接一个以 `MissionGraph` 为真源的后台任务编排器

因此需要一份清晰的升级需求与计划，回答两个问题：

1. 哪些是路线 B 落地时必须补的
2. 哪些是后续增强，不必阻塞新 orchestrator 起步

---

## 2. 总体判断

总体判断如下：

### 2.1 不需要重写 agent_os

当前 `agent_os` 已经有价值且应继续复用的层：

- `runtime`
- `protocol`
- `state`
- `workflow`

因此不应把路线 B 变成“顺手再把 agent_os 也重写一遍”。

### 2.2 但需要一轮收敛式升级

当前 `agent_os` 还存在三类不足：

- 偏 heartbeat 兼容的接口还不够中性
- workflow 更适合线性 step 投影，不适合直接表达 MissionGraph
- tasking/store 层还太薄，不足以直接承接新 orchestrator 的 mission/node/branch 生命周期

所以更准确的结论是：

> **agent_os 不需要推翻，但需要补一轮“为 orchestrator 服务”的接口升级。**

---

## 3. 当前已足够稳定、可直接复用的部分

这些能力建议直接复用，不作为 blocker：

### 3.1 runtime contracts / host / kernel

已有价值：

- `RunInput / Run / WorkerRequest / WorkerResult / RunResult`
- artifact / trace 最小结构
- runtime host / kernel / instance store

这些能力已经足够支撑：

- worker dispatch
- run 生命周期
- 结果回收
- 执行层与编排层分离

### 3.2 protocol receipts

已有价值：

- `StepReceipt`
- `HandoffReceipt`
- `DecisionReceipt`
- `AcceptanceReceipt`

这些对象已经适合继续作为：

- branch 执行结果表达
- judge 回执表达
- projection / ledger 的跨层契约

### 3.3 state store

已有价值：

- runtime state
- pid / lock / run state / watchdog state

这些能力对新 orchestrator 仍然有直接价值。

---

## 4. 当前需要升级的地方

## 4.1 升级点 A：Tasking 抽象过窄

当前 `agents_os.tasking.task_store.TaskStore` 只有：

- `load`
- `save`
- `bootstrap`
- `apply_runtime_result(plan, execution_result, branch_results)`

这明显仍然带有旧 heartbeat 语义：

- 输入假设是 `plan + execution_result + branch_results`
- 默认执行粒度是 heartbeat round
- 没有 mission / node / branch 的显式读写接口

这对新 orchestrator 不够，因为新 orchestrator 需要：

- mission 级持久化
- node 级状态流转
- branch 级运行记录
- event ledger
- partial readiness / repair / escalate 等显式状态

### 结论

`TaskStore` 现在不能直接作为新 orchestrator 的主 store 协议。

### 建议升级

新增中性接口，而不是继续扩写旧 `TaskStore`：

- `MissionStore`
- `MissionEventStore`
- `BranchResultStore` 或 `ExecutionRecordStore`

保留 `TaskStore` 作为 legacy / compatibility 协议。

---

## 4.2 升级点 B：Workflow 更适合投影，不适合主编排

当前 `agents_os.workflow` 提供：

- `WorkflowSpec`
- `WorkflowStepSpec`
- `WorkflowCursor`
- `WorkflowCheckpoint`
- `WorkflowRunProjection`

这些对象很适合：

- 线性 step 流程
- checkpoint
- step receipt 汇总
- projection

但对新 orchestrator 来说，还不够直接表达：

- node dependency graph
- 多 branch 并行与 quorum
- branch timeout
- `partial_ready`
- mission 级 repair / escalate / park

### 结论

`WorkflowSpec` 仍然应该保留，但不应成为新 orchestrator 的真源模型。

### 建议升级

短期：

- 保持 `workflow` 作为投影层，不改成主编排模型

中期：

- 增加更中性的 projection helpers
- 支持从 Mission/Node/Branch 投影到 workflow/checkpoint/receipts

长期：

- 如果未来需要，可增加 graph-aware workflow projection
- 但不要在当前阶段把 `workflow` 直接膨胀成通用 DAG orchestrator

---

## 4.3 升级点 C：Run/Status 枚举偏执行态，缺少编排态

当前 `runtime.contracts` 中的状态更偏 run 级别：

- `pending`
- `running`
- `blocked`
- `failed`
- `completed`
- `cancelled`
- `stale`

这对单次 run 足够，但对于 orchestrator 级别对象还不够。

例如 mission/node 常见状态还有：

- `ready`
- `partial_ready`
- `awaiting_judge`
- `repairing`
- `awaiting_decision`
- `parked`
- `skipped`

### 结论

这些状态不一定要直接塞进 `runtime.contracts`，但 agent_os 至少要允许上层使用更丰富的 orchestrator-level state，而不误导成 run status。

### 建议升级

短期：

- 不修改底层 `Run.status` 语义
- 新增 orchestrator-level state model，放在新 orchestrator 自己的 models 中

中期：

- 在 agent_os 中增加 `orchestration/contracts.py` 或类似模块
- 明确区分：
  - run-level status
  - mission-level status
  - node-level status

---

## 4.4 升级点 D：Receipt 与 MissionGraph 的映射缺少标准投影器

当前 heartbeat adapter 已经在做一件事：

- 将旧 heartbeat 结果映射为 `StepReceipt / HandoffReceipt / DecisionReceipt`

但这个逻辑目前主要落在：

- `butler_bot/agents_os_adapters/heartbeat_workflow.py`

这有两个问题：

- 映射逻辑仍绑在 legacy heartbeat 语义上
- 新 orchestrator 如果要复用 receipts，还需要再写一套新的 mapping

### 结论

receipt 映射应从 heartbeat adapter 中抽出一层中性逻辑。

### 建议升级

新增中性投影器，例如：

- `agents_os.workflow.projection`
  或
- `agents_os.protocol.projection`

负责：

- branch result -> `StepReceipt`
- node verdict -> `DecisionReceipt`
- node handoff -> `HandoffReceipt`
- mission/node -> `WorkflowProjection`

这样新 orchestrator 与 legacy heartbeat 都能共用。

---

## 4.5 升级点 E：Subworkflow / Scenario 接口还偏应用侧

当前 research scenario 已有：

- scenario spec
- runner
- instance store

但 orchestrator 如果要统一调 subworkflow，需要一个更标准的能力接口。

现在的风险是：

- research scenario 仍然更像 research manager 的内部能力
- heartbeat 侧只能把它作为特殊 branch 或 payload 处理

### 结论

如果路线 B 要尽快接一个最小 research 场景，agent_os / research 之间需要一个更稳定的 subworkflow capability 接口。

### 建议升级

抽出中性接口，例如：

- `SubworkflowCapability`
- `SubworkflowRunRequest`
- `SubworkflowRunResult`
- `ScenarioProjection`

让 orchestrator 看到的是：

- 一个可调度能力
- 一个 instance id
- 一组 receipts / artifacts / state snapshot

而不是 research 私有 payload 细节。

---

## 5. 哪些是路线 B 的 blocker

不是所有升级项都要先做完。

路线 B 真正的 blocker 只有这些：

### Blocker 1

必须允许新 orchestrator 自己维护 mission/node/branch store，而不被迫套进旧 `TaskStore.apply_runtime_result(plan, execution_result, branch_results)`。

意味着：

- 不需要先改好 agent_os
- 但要允许新 orchestrator 自己定义最小 store

### Blocker 2

必须允许新 orchestrator 直接复用 runtime/protocol，而不依赖旧 `heartbeat_* adapter`。

### Blocker 3

必须至少约定一种把 mission/node/branch 结果投影成 receipt 的路径。

这条可以先在 orchestrator 内部自己做，后续再抽回 agent_os。

---

## 6. 哪些不是 blocker

这些不该阻塞路线 B 起步：

- 让 `workflow` 直接支持 DAG
- 重做整个 `agents_os.tasking`
- 统一所有 scenario 接口
- 完整的 decision layer 协议
- 通用化所有 approval / recovery / verification

这些都可以在新 orchestrator 起步后逐步收敛。

---

## 7. 建议的升级顺序

## Phase 0：不阻塞路线 B 起步

允许新 orchestrator 先在自己的目录里定义：

- mission models
- mission store
- event store
- receipt 投影器

此阶段 agent_os 不必先改代码。

## Phase 1：补 agent_os 中性扩展点

建议新增：

- `agents_os/orchestration/` 或同级目录

用于放：

- mission/node/branch contracts
- projection helpers
- orchestration state contracts

目的不是把 orchestrator 塞回 agent_os，而是把“可复用中性层”补齐。

## Phase 2：抽 receipt / workflow 投影公共层

将当前 heartbeat adapter 中有普适价值的投影逻辑抽成公共模块。

## Phase 3：收敛 subworkflow capability 接口

让 research / future app flow 都以统一 capability 形式被 orchestrator 调度。

---

## 8. 推荐的最小升级清单

建议同步记录以下最小升级项：

### P0

- 新增 orchestrator 自有 store，不强行复用 `TaskStore`
- 新 orchestrator 自行定义 mission/node/branch 状态模型
- 新 orchestrator 内部先自行完成 receipt 映射

### P1

- 在 `agent_os` 中补 `orchestration contracts`
- 抽公共 `projection helpers`
- 抽中性 `subworkflow capability` 接口

### P2

- 评估是否需要 graph-aware workflow projection
- 评估是否需要在 tasking 中增加 mission/event store 抽象

---

## 9. 最终结论

最终结论可以收敛为三句话：

1. `agent_os` 当前已经足够作为新 orchestrator 的底层执行与协议底座，不需要整体重写。
2. 但 `tasking / workflow / projection / subworkflow capability` 这几块还需要补一轮中性升级，才能更自然地承接 MissionGraph runtime。
3. 这些升级不应阻塞路线 B 起步，应采取“新 orchestrator 先落地，公共部分再回抽进 agent_os”的顺序。

一句话总结：

> **先让新 orchestrator 跑起来，再把真正有复用价值的那部分能力反向沉淀回 agent_os。**
