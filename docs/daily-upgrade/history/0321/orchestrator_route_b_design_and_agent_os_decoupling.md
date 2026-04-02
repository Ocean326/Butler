# Route B：新 Orchestrator Core 设计与 agent_os 解耦边界

更新时间：2026-03-21
时间标签：0321_route_b_orchestrator

## 1. 这份文档解决什么

这份文档用于明确路线 B 的目标：

- 新起一个真正独立的 `orchestrator core`
- 不继续在旧 `heartbeat` 主循环上做主升级
- 明确新 orchestrator 与当前 `agent_os` 的关系
- 明确哪些层复用，哪些层不再绑定
- 给后续最小落地顺序提供统一边界

本文不讨论 legacy heartbeat 的接口化细节，那部分属于路线 A。

---

## 2. 一句话工程决策

路线 B 的工程决策是：

> **新建一个独立的后台任务运行时编排器，以 `Mission / Node / Branch / Ledger` 为核心对象；底层复用 `agent_os` 的 runtime / protocol / state / receipt 能力，但不再让 orchestrator 依赖旧 heartbeat adapter、MemoryManager 驱动链、或 talk recent/local memory 拼装链。**

再压缩一点：

> **复用 agent_os 的底座，不复用旧 heartbeat 的大脑。**

---

## 3. 现状判断

结合当前代码和已有文档，可以把现状理解成：

### 3.1 当前 heartbeat 已部分接入 agent_os

已有接入层包括：

- `agents_os.protocol`
- `agents_os.workflow`
- `agents_os.state`
- `agents_os.tasking`
- `butler_bot/agents_os_adapters/*`

这意味着系统并不是“完全没有抽象”，而是已经有一层 agent_os 底座。

### 3.2 但当前接法仍然偏 legacy heartbeat 中心

目前主要问题不是“没有 agent_os”，而是：

- `heartbeat` 仍然是主真源
- `agents_os` 主要以 adapter 方式被挂进去
- 旧 heartbeat 的 plan / branch_result / task ledger 仍然是核心语义
- research / subworkflow 仍然主要被 heartbeat 当作一种特殊 branch

也就是说：

> 当前是“heartbeat 吸收 agent_os”，而不是“orchestrator 建立在 agent_os 底座上”。

### 3.3 这导致路线 B 不能直接复用旧 adapter 结构当 core

例如当前这些文件都更接近 legacy compatibility，而不是新 core：

- `butler_bot/agents_os_adapters/heartbeat_workflow.py`
- `butler_bot/agents_os_adapters/heartbeat_scheduler.py`
- `butler_bot/agents_os_adapters/heartbeat_task_v2_store.py`
- `butler_bot/agents_os_adapters/research_heartbeat.py`

这些模块有价值，但价值主要在：

- 兼容协议
- 数据迁移
- 旧系统过渡

而不是成为新 orchestrator 的核心域模型。

---

## 4. 路线 B 的目标系统

路线 B 目标系统应当是：

- `talk` 只做前台入口
- `legacy heartbeat` 只做兼容运行
- `orchestrator core` 作为独立后台任务运行时
- `agent_os` 提供下层运行设施和跨层契约

目标结构：

- `butlerbot_talk`
  - 前台解释
  - mission 创建 / 查询
  - direct branch invoke
- `legacy_heartbeat_adapter`
  - 封装旧 heartbeat
  - 仅供兼容
- `orchestrator`
  - mission store
  - node / branch runtime
  - scheduler
  - judge interface
  - ledger / event store
- `agents_os`
  - runtime
  - protocol
  - workflow
  - state
  - governance / verification / recovery
- `research`
  - scenario / subworkflow capability
  - 不直接承担总编排职责

---

## 5. 新 orchestrator 的最小职责

新 orchestrator 只负责后台任务运行时，不承担对话或长期知识总管职责。

最小职责：

- 维护 mission 状态
- 根据依赖关系激活 node
- 为 node 派发 branch
- 异步收割 branch 结果
- 触发 judge
- 依据 verdict 执行 continue / repair / finish / escalate
- 写入 ledger
- 处理 timeout / retry / quorum / policy

最小核心对象：

- `Mission`
- `Node`
- `Branch`
- `Artifact`
- `LedgerEvent`
- `OrchestratorService`

---

## 6. 新 orchestrator 与 agent_os 的关系

这里必须分层，不然新 orchestrator 还是会被拖回旧 heartbeat 语义。

### 6.1 应复用的 agent_os 层

路线 B 应明确复用这些层：

#### L0 Runtime Core

来源：

- `agents_os.runtime.contracts`
- `agents_os.runtime.kernel`
- `agents_os.runtime.host`
- `agents_os.runtime.instance_store`

用途：

- worker/run/session 的最小运行抽象
- artifact / trace / context 最小设施
- 可恢复执行

一句话：

> orchestrator 负责“调度什么”，runtime 负责“怎么跑出去”。

#### L1 Protocol

来源：

- `agents_os.protocol.receipts`
- `agents_os.verification`
- `agents_os.governance`
- `agents_os.recovery`

用途：

- step / handoff / decision / acceptance 表达
- judge / approval / recovery 的统一契约

一句话：

> orchestrator 可以自定义 mission/node 语义，但 step 结果表达尽量复用统一 receipt。

#### L1.5 State

来源：

- `agents_os.state`

用途：

- run / watchdog / checkpoint / runtime 状态读写

#### L2 Workflow

来源：

- `agents_os.workflow.models`

用途：

- 用作 step projection / checkpoint / compatibility output
- 不是路线 B 的主域模型

一句话：

> workflow 在路线 B 中更适合当投影层，而不是总控层。

### 6.2 不应直接复用为 core 的层

路线 B 不应把这些东西直接当作新 orchestrator 的核心：

- `butler_bot/agents_os_adapters/heartbeat_*`
- `heartbeat_orchestration.py` 的旧 plan / dispatch 主循环
- `MemoryManager` 驱动 heartbeat 的方式
- talk recent/local memory 拼装链
- 基于旧 `short_tasks / long_tasks` 思维的流程中心

原因：

- 这些模块已经深度带有 legacy heartbeat 语义
- 继续复用会把新 orchestrator 拉回旧结构

---

## 7. 路线 B 的解耦原则

### 7.1 从 MemoryManager 解耦

新 orchestrator 不应依赖：

- `MemoryManager` 私有方法
- talk recent/local memory prompt 组装
- 总编排类驱动 runtime

允许的关系应当是：

- orchestrator 可以消费显式输入
- orchestrator 可以读写 mission-scoped store
- orchestrator 可以读 receipt / artifact / state

但不应：

- 从 MemoryManager 直接请求“给我当前思考上下文”
- 通过 MemoryManager 间接驱动计划、分支、交付

### 7.2 从旧 heartbeat adapter 解耦

旧 adapter 仍可用于：

- 兼容导出
- ledger 迁移
- 协议映射

但不应让新 core 依赖它们来表达内部模型。

正确关系应当是：

- 新 core 产出自己的 MissionGraph / runtime state
- 如有需要，再投影成 workflow receipt / compatibility payload

而不是：

- 先按旧 heartbeat payload 建模，再反推 mission runtime

### 7.3 从 talk 语义解耦

新 orchestrator 只接受明确接口输入，例如：

- `create_mission`
- `append_user_feedback`
- `get_mission_status`
- `control_mission`

它不应知道：

- 当前对话怎么渲染
- 用户这一轮说话的语气
- talk recent summary 怎么拼 prompt

---

## 8. 路线 B 的主域模型

路线 B 应以 MissionGraph 为主域模型，而不是 workflow projection。

### 8.1 Mission

表示一个长期后台任务。

包含：

- `mission_id`
- `mission_type`
- `goal`
- `status`
- `priority`
- `constraints`
- `success_criteria`
- `current_iteration`

### 8.2 Node

表示 mission 中一个可调度节点。

包含：

- `node_id`
- `kind`
- `dependencies`
- `status`
- `branch_policy`
- `judge_spec`
- `runtime_plan`

### 8.3 Branch

表示节点派生出的一个执行分支。

包含：

- `branch_id`
- `node_id`
- `status`
- `worker_profile`
- `input_payload`
- `result_ref`

### 8.4 LedgerEvent

表示关键审计事件。

包含：

- `event_id`
- `mission_id`
- `node_id`
- `branch_id`
- `event_type`
- `payload`
- `ts`

---

## 9. MissionGraph 与 agent_os workflow 的关系

这里必须明确：

> `MissionGraph` 是路线 B 的主编排模型，`agent_os.workflow` 是兼容投影模型。

也就是说：

- orchestrator 内部推进不应该依赖 `WorkflowSpec` 作为真源
- `WorkflowSpec / WorkflowCursor / WorkflowProjection` 更适合：
  - 对外展示 step 轨迹
  - 做 checkpoint / projection
  - 兼容 research / receipt 流转

当前 `agent_os.workflow` 更适合表示：

- step 序列
- cursor
- checkpoint

但还不适合直接承载：

- node dependency graph
- branch quorum
- branch timeout
- partial readiness
- mission-level repair / escalate

因此路线 B 不应“硬把 MissionGraph 塞进 WorkflowSpec”，而应：

1. 先以内建 Mission/Node/Branch 运行
2. 再把关键步骤投影到 workflow / receipt

---

## 10. 与 research / subworkflow 的关系

路线 B 下，research 不再是旧 heartbeat dispatch 中的一个特殊 branch 类型。

正确关系应当是：

- orchestrator 调度 `subworkflow mission` 或 `subworkflow node`
- research scenario 作为独立 capability / scenario runtime 被调用
- research 产出：
  - artifact
  - receipts
  - scenario instance state
- orchestrator 再把这些结果纳入 ledger 和 node 判定

也就是说：

> research 继续是“场景能力层”，但不再承担总编排职责。

---

## 11. 路线 B 的最小落地顺序

### 第一阶段：起新目录和最小对象

建议新建：

- `butler_bot/orchestrator/`
  - `models.py`
  - `mission_store.py`
  - `event_store.py`
  - `service.py`
  - `scheduler.py`
  - `judge_adapter.py`
  - `policy.py`

第一阶段只定义：

- Mission / Node / Branch / LedgerEvent
- 最小 store
- 最小状态机

### 第二阶段：实现最小 runtime loop

实现：

- `tick`
- `dispatch_ready_nodes`
- `collect_branch_results`
- `judge_ready_nodes`
- `apply_verdict`

### 第三阶段：只跑一个最小 mission 模板

先只支持一个最小模板，例如：

- `brainstorm_topic`
  或
- 一个最小 `research_subworkflow_task`

目的不是功能覆盖，而是验证：

- mission 驱动
- branch 收敛
- judge 回路
- ledger 持久化

### 第四阶段：接统一接口

让新 orchestrator 实现与路线 A 相同的入口契约：

- `create_mission`
- `get_mission_status`
- `append_user_feedback`
- `control_mission`
- `list_delivery_events`

这一步之后，talk 才能开始切换底层实现。

---

## 12. 路线 B 中 agent_os 的定位总结

一句话分层：

- `agent_os.runtime`：执行底座
- `agent_os.protocol`：回执契约
- `agent_os.workflow`：工作流投影和 checkpoint
- `orchestrator`：后台任务编排真源

所以路线 B 不是替代 `agent_os`，而是把 `agent_os` 放回它更合适的位置。

---

## 13. 当前结论

路线 B 的最稳做法不是：

- 继续改旧 heartbeat 的 plan / dispatch 主循环
- 也不是把当前 `heartbeat_* adapter` 包一层就叫 orchestrator

而是：

> **建立一个以 MissionGraph 为真源的新 orchestrator core，并只把 agent_os 当作底层 runtime/protocol/workflow 能力提供者。**

这是当前最符合：

- talk / heartbeat 解耦目标
- harness 保持轻量目标
- future complex mission 支持目标
- agent_os 已有积累复用目标

的路线。
