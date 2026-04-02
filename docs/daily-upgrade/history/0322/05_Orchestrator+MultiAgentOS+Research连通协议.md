# 05 Orchestrator + MultiAgentOS + Research 连通协议

日期：2026-03-22
时间标签：0322_1008
状态：进行中

## 主线

1. 本文用于收一版 `orchestrator + multi_agents_os + research` 的连通协议，避免三边继续各自扩展后字段、真源、调用顺序对不上。
2. 目标不是再长一层平台，而是把三边的职责、入口对象、回写边界、最小字段集先钉死。
3. 本协议优先保证“通用、稳定、可恢复”，而不是为了追求一步到位把三边逻辑互相侵入。

## 三方定位

1. `orchestrator`
- 系统级长期控制者。
- 负责 `Mission / MissionNode / Branch / LedgerEvent` 真源、dispatch、collect、judge、runner。
- 不负责 research workflow 细节本体，也不负责局部协作会话协议本体。

2. `multi_agents_os`
- 位于 `AgentRuntime` 之上、`orchestrator` 之下的局部协作运行层。
- 负责 `WorkflowTemplate / RoleBinding / WorkflowSession / SharedState / ArtifactRegistry / WorkflowFactory / SessionStore / EventLog`。
- 不负责 mission scheduler、global ledger、后台治理、统一控制面。

3. `research`
- application / scenario 层。
- 负责 `ResearchInvocation / ResearchUnitSpec / ScenarioDispatch / ScenarioInstanceStore / scenario workflow semantics`。
- 不负责 orchestrator 的 mission graph，也不负责 multi-agent session 基础设施。

## 真源边界

1. `Mission / MissionNode / Branch / LedgerEvent` 的真源在 `orchestrator`。
2. `WorkflowSession / SharedState / ArtifactRegistry / session event log` 的真源在 `multi_agents_os`。
3. `scenario_instance / workflow_cursor / step_receipt / handoff_receipt / decision_receipt / output_template` 的真源在 `research`。
4. 三边只允许通过明确字段引用彼此真源，不允许复制一份“影子真源”长期并行。

## 连通主链 V1

推荐主链固定为：

```text
MissionNode
  -> Orchestrator dispatch_ready_nodes()
    -> WorkflowFactory.create_session()
      -> ResearchManager.invoke()
        -> ScenarioInstanceStore.apply_dispatch()
          -> branch result / session writeback / mission collect
```

### V1 运行顺序

1. `orchestrator` 负责选择要执行的 `MissionNode`。
2. 如果该 node 声明要进入 `research_scenario`，则 `orchestrator` 先通过 `multi_agents_os.WorkflowFactory` 创建一个局部 `WorkflowSession`。
3. `WorkflowSession` 只作为“局部会话容器”，负责提供：session identity、shared state、artifact registry、local event log。
4. `research` 通过 `ResearchInvocation` 消费这次调用，并继续把具体 step 语义、workflow cursor、scenario dispatch、scenario instance 落到自己的真源里。
5. `research` 返回结构化 dispatch / result 后：
- `multi_agents_os` 负责更新 session 级 shared state / artifact / local event
- `orchestrator` 负责更新 branch / node / mission / ledger
6. 任一侧恢复时，都优先回到自己的真源：
- mission 相关回 `orchestrator`
- session 相关回 `multi_agents_os`
- scenario 相关回 `research`

## 字段协议 V1

### A. MissionNode -> MultiAgentOS

当一个 node 需要接到 research，最小字段统一为：

1. `node.kind = research_scenario` 或 `node.metadata.subworkflow_kind = research_scenario`
2. `node.metadata.research_unit_id`
3. `node.metadata.scenario_action`
4. `node.runtime_plan.workflow_template` 或等价 `workflow_template_id`
5. `node.runtime_plan.workflow_inputs`

约束：
- `orchestrator` 只声明“要调用哪个 research unit / 场景”，不在 node 内部复制完整 research workflow spec。
- `workflow_template` 只描述局部会话装配信息，不描述 orchestrator 的调度规则。

### B. MultiAgentOS Session Metadata

新建 session 后，最小 metadata 统一为：

1. `session_id`
2. `template_id`
3. `driver_kind`
4. `mission_id`
5. `node_id`
6. `branch_id`
7. `research_unit_id` 若这是 research 场景
8. `scenario_instance_id` 若 research 已完成 bind

约束：
- `driver_kind` 用来表达谁来消费这个 session，例如 `orchestrator_node`、`research_scenario`。
- `multi_agents_os` 只保留引用，不复制 `scenario_instance` 全量状态。

### C. Orchestrator -> ResearchInvocation

当 orchestrator 真正调用 research 时，最小 `ResearchInvocation` 建议统一为：

1. `entrypoint = codex` 或未来专门的 `orchestrator`
2. `unit_id = research_unit_id`
3. `task_id = branch_id`
4. `session_id = workflow_session_id`
5. `workspace`
6. `metadata.scenario_action`
7. `metadata.scenario_instance_id` 若已有
8. `metadata.workflow_cursor` 若这是 resume/recover
9. `payload.workflow_session_id`
10. `payload.workflow_inputs`

约束：
- `research` 不直接读取 orchestrator 的 branch store 作为主真源。
- `ResearchInvocation` 只接必要引用，不接 orchestrator 私有状态机全集。

### D. Research -> Writeback

`research` 返回后，建议最小 writeback 分两层：

1. 写回 `multi_agents_os`
- `shared_state` 增量 patch
- `artifact_registry` 追加 artifact ref
- `event_log` 记录 `state_patched` / `artifact_added` / `active_step_changed`

2. 写回 `orchestrator`
- `branch.result_ref`
- `branch.metadata.result_payload`
- `node / branch` 上的 `workflow_session_status`
- 需要时再进入 `judge`

约束：
- `research` 不直接改 mission 状态。
- `multi_agents_os` 不直接决定 branch 成败。
- `orchestrator` 不直接篡改 `scenario_instance` 真源。

## 推荐字段映射

### Session 侧统一保留

1. `workflow_session_id`
2. `workflow_template_id`
3. `workflow_driver_kind`
4. `research_unit_id`
5. `scenario_instance_id`
6. `workflow_session_status`

### Research 侧统一保留

1. `unit_id`
2. `scenario_id`
3. `scenario_instance_id`
4. `workflow_id`
5. `workflow_cursor`
6. `active_step.step_id`
7. `last_step_receipt`
8. `last_handoff_receipt`
9. `last_decision_receipt`

### Branch Result Payload 建议统一保留

1. `summary`
2. `output_text` 或 `output_bundle_summary`
3. `artifact_refs`
4. `scenario_instance_id`
5. `workflow_session_id`
6. `next_action`
7. `failure_class`

## 明确禁止

1. 禁止 `orchestrator` 在 node metadata 里复制完整 `research` workflow spec 长期保存。
2. 禁止 `multi_agents_os` 长出 mission ledger、branch scheduler、global governor。
3. 禁止 `research` 自己接管 branch / mission 状态机。
4. 禁止三边各自定义不同的 `session_id / scenario_instance_id / subworkflow_ref` 口径。
5. 禁止为了方便而把另一侧真源整包镜像进本侧 store。

## 先落哪一段

V1 推荐按下面顺序实施：

1. 先固定 research 场景 node 的最小字段集：`subworkflow_kind / research_unit_id / scenario_action / workflow_session_id`。
2. 再补一条 `orchestrator -> ResearchInvocation` 的适配桥。
3. 再补一条 `research result -> multi_agents_os writeback -> orchestrator collect` 的回写链。
4. 最后再谈 runner 如何持续推进 `research_scenario` node，而不是先上复杂调度。

## 验收标准

1. 必须能一句话说清：三边谁是哪类真源。
2. 必须能一句话说清：research 场景 node 创建后，`workflow_session_id`、`scenario_instance_id`、`branch_id` 如何互相引用。
3. 必须能一句话说清：谁负责 session 写回，谁负责 mission 写回，谁负责 scenario 写回。
4. 任一侧单独扩展时，不能要求另外两侧同时重写真源模型才能配合。

## 当前结论

1. `orchestrator` 继续做系统级控制，不吞并 research workflow 细节。
2. `multi_agents_os` 继续做薄中间层，只提供通用会话基础设施与装配。
3. `research` 继续做场景 workflow 真源与 dispatch 真源。
4. 三边的正确连法不是“谁做得快谁多接一层”，而是通过稳定引用字段和最小 writeback 协议连通。
