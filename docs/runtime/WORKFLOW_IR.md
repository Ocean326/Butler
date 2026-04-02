# Butler Workflow IR

更新时间：2026-03-27

这份文档定义 Butler 当前统一的 `Workflow IR（工作流中间表示）` 口径。

## 落点

- 文档真源：`docs/runtime/WORKFLOW_IR.md`
- 分层真源：[`docs/runtime/System_Layering_and_Event_Contracts.md`](./System_Layering_and_Event_Contracts.md)
- 代码真源：`butler_main/orchestrator/workflow_ir.py`
- 编译入口：`butler_main/orchestrator/compiler.py`
- 当前核心测试：`butler_main/butler_bot_code/tests/test_orchestrator_workflow_ir.py`

## 一句话定义

`Workflow IR（工作流中间表示）` 是 Butler 用来承接：

`mission/node -> protocol compile -> session runtime dispatch -> durability writeback`

这条链路的统一中间表示。

它不是：

1. `Mission（任务）` 本身
2. `Projection（投影读模型）`
3. `Execution Receipt（执行回执）`

它是 `Domain & Control Plane（领域与控制平面）` 编译后交给 `L3/L4/L2/L1` 协作消费的稳定对象。

## 字段分层

### L3 Multi-Agent Protocol（多 Agent 协议层）

这些字段属于 compile-time protocol 真源：

- `workflow`
- `steps`
- `edges`
- `roles`
- `artifacts`
- `handoffs`
- `verification`
- `approval`
- `recovery`
- `capability_package_ref`
- `team_package_ref`
- `governance_policy_ref`
- `runtime_binding`
- `input_contract`
- `output_contract`

这里的 `roles` 当前应理解为 `RoleSpec（角色规格）` 的载体，而不是 `RoleBinding（角色绑定）`。

### L4 Multi-Agent Session Runtime（多 Agent 会话运行时）

这些字段属于 session/runtime linkage：

- `workflow_session_id`
- `workflow_inputs`
- `role_bindings`
- `entry_step_id`
- `runtime.current_step_id`
- `runtime.status`
- `subworkflow_kind`
- `research_unit_id`
- `scenario_action`

这里的 `role_bindings` 当前应理解为 `RoleBinding（角色绑定）`，不再与 `roles / RoleSpec（角色规格）` 混说。

### L2 Durability Substrate（持久化基座）

当前 `Workflow IR` 不直接内嵌完整 checkpoint 或 writeback record，但会稳定暴露 durability linkage：

- `gate_policies.*.canonical_target_owner`
- `execution_boundary.durability_owner`
- `execution_boundary.governance_target_owner`
- 后续桥接层 materialize 出来的 checkpoint / writeback / recovery linkage

当前规则是：

1. `Workflow IR` 可以声明 durability 目标边界。
2. `Workflow IR` 不直接代替 `CheckpointRecord（检查点记录）` 或 `WritebackRecord（回写记录）`。

### Observability（可观测性）

当前保留在 `Workflow IR` 内的 observability 字段包括：

- `metadata`
- `observability.tags`
- `observability.lineage`
- `gate_policies`
- `execution_boundary`

这里的 `Observability（可观测性）` 只面向诊断和 lineage，不等于 `Projection（投影读模型）`。

## 对象口径

### `workflow`

`workflow` 是 compile-time 外壳，负责承载模板、step 图、package refs、contracts、runtime binding。

### `step`

最小可执行单元。当前至少稳定承载：

- `step_id`
- `step_kind`
- `title`
- `role_id`
- `artifact_refs`
- `handoff_refs`
- `runtime_binding`

### `edge`

流程推进关系。当前稳定字段：

- `edge_id`
- `source_step_id`
- `target_step_id`
- `condition`
- `resume_from`

### `role`

当前 `role` 应视为 `RoleSpec（角色规格）`，稳定字段包括：

- `role_id`
- `capability_id`
- `agent_spec_id`
- `package_ref`
- `policy_refs`

### `artifact`

流程产物声明，不等于 registry 中的运行态 artifact 实例。当前稳定字段：

- `artifact_id`
- `artifact_kind`
- `producer_step_id`
- `owner_role_id`
- `contract_ref`

### `handoff`

角色或步骤之间的交接声明。当前稳定字段：

- `handoff_id`
- `source_step_id`
- `target_step_id`
- `source_role_id`
- `target_role_id`
- `artifact_refs`
- `handoff_kind`

### `verification / approval / recovery`

它们属于 compile-time governance contract，但当前会被降解为跨层 gate policy，并显式标出：

- 兼容目标：`target_owner=runtime_os.process_runtime`
- 当前正式目标：`canonical_target_owner=runtime_os.durability_substrate`

## Event 关系

`Workflow IR` 本身不是事件流，但必须和事件分层兼容。

当前统一约束：

1. `L1 Execution Events（执行事件）` 产出执行 receipt
2. `L4 Session Events（会话事件）` 承接 handoff/join/evidence/mailbox
3. `L2 Durability Events（持久化事件）` 承接 checkpoint/writeback/recovery
4. `Domain Events（领域事件）` 最终在控制面提交 verdict 和状态迁移
5. `Projection Refresh Events（投影刷新事件）` 只能刷新读模型

当前第一版最小事件封套为：

- `event_id`
- `event_type`
- `layer`
- `subject_ref`
- `causation_ref`
- `created_at`
- `payload`

## 边界约束

### Mission（任务）

- 负责用户目标、优先级、node graph、外部状态
- 不负责持有 workflow cursor、gate policy 细节、receipt 细节

### Workflow IR（工作流中间表示）

- 负责表达“某个 node 被编译成什么流程”
- 负责承载 compile-time 结构、runtime linkage、durability 边界、observability 摘要
- 不直接替代 mission 的产品级状态
- 不直接替代 artifact registry
- 不直接替代 projection

### Workflow Session（工作流会话）

- 是 workflow 的运行态实例
- 负责 active step、shared state、协作底座、session 生命周期
- 不是 compile-time schema 真源

### Artifact Registry（产物注册表）

- 负责保存实际产物实例与可见性
- `Workflow IR.artifacts` 只声明流程期望产物，不直接充当 registry

### Receipt（回执）

- `Execution Receipt（执行回执）` 是一次执行结果的事实记录
- `Workflow IR` 只声明流程与治理口径，不负责代替单次执行 receipt

### Projection（投影读模型）

- 由 `Domain & Control Plane（领域与控制平面）` 组装
- 不落在 `Workflow IR` 真源里
- 不反向充当恢复或判定依据

## 当前兼容策略

- 保留 `runtime_key`、`agent_id`、`worker_profile`、`workflow_template`、`role_bindings` 等旧顶层字段
- 新增 `workflow / compile_time / runtime / observability` 结构化出口
- 新增 `execution_boundary.protocol_owner / session_runtime_owner / durability_owner`
- `WorkflowIR.from_dict()` 同时兼容旧扁平 payload 和新结构化 payload
- `target_owner=runtime_os.process_runtime` 继续保留兼容字段，直到现有调用面完全切到新分层公开面
