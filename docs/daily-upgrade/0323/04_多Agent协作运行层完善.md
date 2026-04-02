---
type: "note"
---
# 04 多 Agent 协作运行层完善

日期：2026-03-23\
时间标签：0323_0004\
状态：进行中

## 最新判断（2026-03-23 03:14:54）

1. `04 multi_agents_os` 当前已经不再是“概念占位层”，而是：

**typed collaboration substrate 的可用雏形**

2. 当前最准确的阶段判断是：

**session / shared state / artifact / mailbox / ownership / join / handoff 已经有对象和测试，但这层还没有完成与&#x20;**`research`**、**`orchestrator`**、future&#x20;**`agents_os`**&#x20;的统一投影与绑定。**

3. 当前最需要持续强调的边界是：

* 它不是 workflow VM

* 它不是第二 orchestrator

* 它不是 research runtime takeover 层

4. 因此这条线的路线纠偏应该明确为：

**不再继续把对象越补越多，而是先把 projection contract、typed collaboration primitives、上层消费接口固定下来。**

5. 这条 worker 的下一步重点不应是“抢执行权”，而应是：

* 固定 collaboration state plane 的边界

* 固定 `research -> multi_agents_os` 的投影口径

* 为 `0324/0325` 的 workflow compile / workflow VM 接入提前准备稳定 contract

## 今日重新定调

参照 `docs/concepts/外部多Agent框架调研与Butler长期架构规划_20260323.md`，今天需要先把一个误区彻底纠正：

`multi_agents_os` 不是 Butler 的执行内核，也不是 research scenario 的替代运行时；它的长期角色是 **Collaboration State Plane 的局部实现**。

换句话说：

* `orchestrator` 是 control plane / mission plane

* `agents_os` 未来是 workflow VM / execution kernel

* `multi_agents_os` 是 collaboration substrate / session-scoped shared collaboration state

* `research` 不是纯冷数据目录，它当前仍然包含 scenario-specific 的解释层与热状态线程

因此，今天推进 `multi_agents_os` 的正确方向，不是“把 research 运行态整包搬进来”，而是：

**先把 research / orchestrator / future workflow VM 都会消费的通用协作状态对象补出来。**

## 一句话边界

`multi_agents_os` 是 Butler 的 workflow-scoped collaboration substrate，不是系统级 orchestrator，不是 team supervisor，不是 research scenario engine，也不是 workflow VM。

## 参照长期架构后的新判断

### 1. `multi_agents_os` 的真实任务

它长期应承接的是：

1. workflow session identity

2. role binding

3. typed shared state

4. artifact registry

5. mailbox / inbox / outbox

6. ownership / claim / assignee

7. role handoff / join contract

8. session event log / collaboration trace

9. workflow-scoped collaboration memory

它不应承接的是：

1. mission intake

2. branch budget / dispatch policy

3. node graph orchestration

4. workflow step-by-step execution

5. approval / verification / recovery 的控制主逻辑

6. research-specific scenario 解释与业务热状态主真源

### 2. `research` 在系统中的真实角色

当前 `research` 不是“只保留冷数据”。

当前更准确的角色是：

1. `research/scenarios/*` 和 `research/units/*` 承接业务冷资产与场景定义。

2. `research_manager` 承接 scenario 解释、unit dispatch、structured receipts 输出。

3. `scenario_instance_store` 仍然保存 research-specific 的热状态线程：

   * `workflow_cursor`

   * `active_step`

   * `last_step_receipt`

   * `last_handoff_receipt`

   * `last_decision_receipt`

   * `scenario_instance_id`

因此，今天不能把 `research` 简化理解为“冷数据仓库”，也不能要求 `multi_agents_os` 立刻取代 `scenario_instance_store`。

### 3. `multi_agents_os` 与 `research` 的正确协作方式

正确关系不是：

`research cold data -> multi_agents_os 组装 -> orchestrator 运行`

更准确的长期链路应是：

`research package/scenario definition`\
-> `compile / bind into Butler workflow context`\
-> `orchestrator` 负责选择与派发\
-> `agents_os` 负责执行\
-> `multi_agents_os` 负责协作状态\
-> `research` 在需要时提供 scenario-specific interpreter 与 receipts

在今天这个阶段，更现实的过渡链路是：

`orchestrator`\
-> 创建 `workflow_session`\
-> 调用 `research_manager`\
-> `research` 维护自己的 `scenario_instance`\
-> 把可通用的状态与 receipts 投影回 `multi_agents_os`

### 4. 今日最重要的架构修正

今天不再把目标描述为：

“让 `multi_agents_os` 进入保持运行态并承接 research”

而改为：

“让 `multi_agents_os` 成为 research / orchestrator / future workflow VM 之间共享的 typed collaboration projection layer”

这里的关键词是：

* projection

* contract

* typed substrate

而不是：

* takeover

* replace research runtime

* second orchestrator

## 当前进展重估

截至今天这一轮实现，`butler_main/multi_agents_os/` 已从“会话容器层”推进到“typed collaboration substrate 雏形”，已具备：

1. `WorkflowSession`

2. `SharedState`

3. `ArtifactRegistry`

4. artifact visibility contract

5. mailbox message

6. step ownership

7. join contract

8. role handoff

9. session-scoped event log

10. `WorkflowFactory` 统一消费面

这意味着今天的重点应从“先证明能存 session.json”转向：

**明确什么状态属于 collaboration substrate，什么状态仍属于 scenario/runtime-specific heat。**

补充：

当前 `orchestrator.research_bridge` 已开始把 research receipts 投影回 `multi_agents_os`，至少覆盖：

1. `step_receipt -> step ownership`

2. `handoff_receipt -> role handoff`

3. `handoff_receipt -> mailbox message`

4. `decision_receipt -> join contract`

5. `scenario_instance / acceptance artifacts -> artifact registry`

但上线前新增的一条硬要求也已经明确：

**同一 research checkpoint / receipts 重放到同一个 workflow session 时，projection 必须保持幂等，不能把 collaboration substrate 越放越厚。**

## 今日总目标（修正版）

1. 固定 `multi_agents_os` 的长期角色为 collaboration substrate，不与 `orchestrator`、`agents_os`、`research` 抢执行与解释主权。

2. 把 `multi_agents_os` 定义为 research / orchestrator / future workflow VM 共享的协作状态层，而不是“第二套 runtime”。

3. 明确 `research scenario instance` 到 `multi_agents_os collaboration substrate` 的投影边界。

4. 明确 Butler 下一轮中，哪些字段留在 `research`，哪些字段进入 `multi_agents_os`，哪些字段以后迁入 `agents_os`。

5. 为 `Workflow IR + Collaboration Contract + Workflow VM` 的后续衔接提前整理清楚接口面。

6. 为上线口径补齐 replay / retry / resume / 多轮推进所需的幂等 projection 语义。

## 今日核心问题

今天真正要回答的，不再只是“`multi_agents_os` 还缺哪些对象”，而是下面四个问题：

1. 什么是 Butler 的通用协作状态，什么是 research-specific 热状态？

2. `research` 输出的 `step/handoff/decision receipts` 应如何投影到 `multi_agents_os`？

3. 未来 `agents_os` 接入 workflow VM 后，哪些状态应从 `research` 回收到统一执行层？

4. `multi_agents_os` 要暴露什么最小 contract，才能同时服务 `orchestrator` 和 `research`？

## 今日计划（修正版）

### P0 先固定三层边界

1. 固定 `orchestrator` 负责 mission/control plane。

2. 固定 `multi_agents_os` 负责 collaboration state plane。

3. 固定 `research` 当前仍负责 scenario-specific interpreter + scenario-local hot state。

4. 固定 `agents_os` 才是未来 workflow VM / execution kernel 的归属层。

### P1 画清 research 与 collaboration substrate 的状态分界

把 `research scenario instance` 中的字段分成三类：

1. 继续留在 `research` 的 scenario-private 状态

2. 应投影到 `multi_agents_os` 的通用协作状态

3. 未来应由 `agents_os` 接管的执行态字段

建议先按下面的口径暂定：

* 投影到 `multi_agents_os`

  * `current_step_id`

  * `workflow_cursor` 的可协作部分

  * `last_step_receipt`

  * `last_handoff_receipt`

  * `last_decision_receipt`

  * `scenario_instance_id` 作为 artifact ref / metadata

* 继续留在 `research`

  * `thread_key`

  * `entrypoints_seen`

  * scenario-specific `state`

  * unit/scenario interpreter 内部细节

* 未来迁往 `agents_os`

  * 更完整的 cursor advancement

  * retry / replay / pause / resume 控制语义

  * approval / verification / recovery gate 的执行主逻辑

### P2 把“投影”而不是“迁移”作为近期实现策略

近期策略固定为：

1. `research` 继续保留 `scenario_instance_store`，不强行拔掉。

2. `research` 每次 dispatch 后输出结构化 checkpoint / receipts。

3. bridge 将这些结果投影到 `multi_agents_os`：

   * shared state

   * artifact registry

   * mailbox / handoff / ownership / join contract

   * collaboration event log

4. 等 `agents_os` workflow VM 真正形成后，再考虑把执行态主真源从 `research` 回收出去。

### P3 今日剩余工作重点

今天后续应优先做的不是继续发散功能，而是把接口和迁移口径写清：

1. 明确 `scenario_instance -> collaboration projection` 的字段映射表。

2. 明确 `multi_agents_os` 当前对 `research` 的最小消费 contract。

3. 明确下一轮哪些 receipt 应直接沉淀为 `collaboration event`。

4. 明确哪些内容现在不要做，避免层次继续打架。

## 今日施工顺序（修正版）

1. 先重写今天这页，固定系统认知。

2. 再整理 `research scenario instance` 到 `multi_agents_os` 的映射口径。

3. 再决定是否需要补一份单独的 `projection contract` 草案。

4. 暂不继续扩展 `multi_agents_os` 为执行器、调度器或 supervisor。

## 最小接口冻结 V0.1

本节先冻结今天要承认的最小接口，避免后续继续一边写代码一边改词义。

补充草案见：

`docs/daily-upgrade/0323/04A_multi_agents_os_最小接口草案.md`

research 三场景与上线前链路设计补充见：

`docs/daily-upgrade/0323/04B_research三场景运行语义与上线前链路设计.md`

### A. `multi_agents_os` 对上层暴露的最小消费面

当前对 `orchestrator` / `research bridge` / future `agents_os` 只承认下面这些稳定入口：

1. `create_session(...)`

2. `load_session(session_id)`

3. `patch_shared_state(session_id, payload)`

4. `add_artifact(session_id, step_id, ref, payload, producer_role_id, owner_role_id, visibility_scope, consumer_role_ids, visibility_metadata)`

5. `post_mailbox_message(session_id, recipient_role_id, sender_role_id, step_id, message_kind, summary, artifact_refs, payload, status)`

6. `assign_step_owner(session_id, step_id, owner_role_id, assignee_id, output_key, status, metadata)`

7. `declare_join_contract(session_id, step_id, source_role_ids, target_role_id, join_kind, merge_strategy, required_artifact_refs, status, metadata)`

8. `record_role_handoff(session_id, step_id, source_role_id, target_role_id, summary, handoff_kind, artifact_refs, payload, status)`

9. `update_active_step(session_id, active_step, status)`

10. `list_events(session_id, event_type="")`

这里的含义是：

* 上层通过 `WorkflowFactory` 消费协作层，不直接读写文件布局。

* 上层默认以 `WorkflowSessionBundle` 作为读取单位，而不是自己拼 `session.json + shared_state.json + artifact_registry.json + collaboration.json`。

* `multi_agents_os` 当前承诺的是 session-scoped collaboration contract，不承诺 workflow execution semantics。

### B. `WorkflowSessionBundle` 的最小读取面

上层读取时当前只应依赖下面五块：

1. `template`

2. `session`

3. `shared_state`

4. `artifact_registry`

5. `collaboration`

其中：

* `session` 负责 identity / active_step / role_bindings / refs

* `shared_state` 负责 workflow-scoped shared facts

* `artifact_registry` 负责 artifact index 与 visibility

* `collaboration` 负责 mailbox / ownership / join / handoff

### C. `research -> multi_agents_os` 的最小投影输入

对 `research` 来说，近期不要求直接操作 `multi_agents_os` 的全部对象，先冻结最小投影输入面。

`research` 每轮 dispatch / scenario update 后，最少只需要对外提供：

1. `workflow_session_id`

2. `research_unit_id`

3. `scenario_action`

4. `scenario_instance_id`

5. `scenario_id`

6. `workflow_id`

7. `current_step_id`

8. `workflow_cursor`

9. `latest_decision`

10. `last_step_receipt`

11. `last_handoff_receipt`

12. `last_decision_receipt`

13. `acceptance.artifacts`

14. `summary`

15. `next_action`

### D. `research -> multi_agents_os` 的最小投影动作

在今天的 contract 下，bridge 最少只需要执行下面四类动作：

1. patch shared state

   * 写入 `research_unit_id`

   * `scenario_action`

   * `scenario_instance_id`

   * `scenario_id`

   * `workflow_id`

   * `workflow_cursor`

   * `current_step_id`

   * `latest_decision`

   * `research_summary`

   * `next_action`

2. update active step

   * 用 `current_step_id` 同步 `session.active_step`

3. add artifact

   * 至少追加 `scenario_instance:{id}` 这类稳定 ref

   * 后续再扩到 step output artifact / receipt artifact

4. append collaboration trace

   * 当前至少写 `event_log`

   * 下一轮再把 `last_handoff_receipt / last_decision_receipt` 显式投影为 `handoff/join/mailbox`

### E. 当前刻意不冻结的接口

下面这些今天明确不承诺，避免误判成已经定型：

1. `research` 直接写 `collaboration.mailbox_messages` 的最终规则

2. `last_step_receipt / last_handoff_receipt / last_decision_receipt` 到 `ownership/join/handoff` 的一一映射算法

3. `blackboard` 对象模型

4. workflow-scoped memory 的正式 schema

5. approval / verification / recovery gate 的执行级接口

6. 面向 framework compiler 的完整 `Collaboration Contract` schema

### F. 一句话记忆版

今天冻结的最小接口不是“`research` 把全部运行态搬进 `multi_agents_os`”，而是：

`research` 输出结构化 receipts 与 scenario checkpoint，bridge 把其中通用部分投影到 `multi_agents_os` 的 session / state / artifact / collaboration contract 上。

## 明确暂缓

1. 暂缓把 `research` 热状态主真源整个迁入 `multi_agents_os`。

2. 暂缓把 `multi_agents_os` 长成第二套 workflow runtime。

3. 暂缓 team supervisor / manager loop 的完整实现。

4. 暂缓全局 mailbox bus / 全局消息总线。

5. 暂缓 approval / verification / recovery 的执行主逻辑迁移。

6. 暂缓 mission scheduler、branch governor 等控制面事项。

## 今日验收标准（修正版）

1. 必须能一句话说清：

`multi_agents_os` 是 collaboration substrate，不是 orchestrator，不是 workflow VM，不是 research scenario engine。

1. 必须能一句话说清：

`research` 当前仍保留 scenario-specific 热状态，不是纯冷数据仓库。

1. 必须能说明：

`research` 与 `multi_agents_os` 的近期正确关系是 projection，而不是 runtime takeover。

1. 必须能列出：

哪些 research 状态应投影到 `multi_agents_os`，哪些应继续留在 `research`，哪些未来迁往 `agents_os`。

1. 今日新增判断不得把 `orchestrator`、`multi_agents_os`、`research`、`agents_os` 四层职责重新搅混。

## 追加记录

### 2026-03-23 00:04

* 本页作为 `0323` 的多 agent 协作运行层入口建立。

* 初始定位从“薄中间层完善”提升为“可执行协作层落地准备”。

### 2026-03-23 当前轮修正

* 参照长期架构规划，确认 `multi_agents_os` 的正确定位应为 `Collaboration State Plane` 的局部实现。

* 确认 `research` 当前仍包含 scenario-specific interpreter 与热状态线程，不能被误写成纯冷数据层。

* 确认近期主线应是 `scenario_instance -> collaboration substrate` 的投影对齐，而不是直接 runtime 接管。

### 2026-03-23 03:14:54 进度复核

1. 结合当前仓库检查，这条主线已经明显超出“纯概念讨论”阶段：

   * `multi_agents_os/session/*` 已有 `WorkflowSession`、`SharedState`、`ArtifactRegistry`、`collaboration`、`event_log`

   * `multi_agents_os/factory/workflow_factory.py` 已形成统一消费面

   * `tests/test_multi_agents_os_factory.py` 已覆盖 session、state、artifact、mailbox、ownership、join contract、handoff 等最小闭环

2. 因此当前最准确的判断不是“还没开始”，而是：

**typed collaboration substrate 已形成可用雏形，但尚未完成与&#x20;**`research`**&#x20;/&#x20;**`orchestrator`**&#x20;/ future&#x20;**`agents_os`**&#x20;的统一投影与绑定。**

1. 当前仍需强力防止的误判有两个：

   * 把 `multi_agents_os` 误当第二执行器

   * 把 `research` 的全部热状态直接机械迁入 `multi_agents_os`

2. 所以这条 worker 下一步最该做的不是继续扩对象数量，而是：

   * 固定 projection contract

   * 固定 typed collaboration primitives

   * 明确哪些状态现在只投影、不接管

### 2026-03-23 装配层复核补记

1. 对照 `orchestrator` 当前装配状态，`multi_agents_os` 这层的进度判断可以再收紧一句：

**它已经不是“只有 session.json 的壳”，而是有 session / shared state / artifact / mailbox / ownership / handoff / join contract 的 typed collaboration substrate。**

1. 但它现在仍然只是被 `orchestrator` 与 `research_bridge` 消费的协作状态层，\
   还没有变成：

   * execution runtime

   * workflow VM

   * 第二个 orchestrator

2. 所以从装配层看，今天最合理的系统读法是：

   * `orchestrator` 负责默认运行入口与 control plane

   * `multi_agents_os` 负责 workflow-scoped collaboration projection

   * `research` 继续保留 scenario-specific interpreter / hot state

   * `agents_os` 未来再承接真正 execution kernel

⠀