# 多 Agent 协作运行层（V0 设计稿）

日期：2026-03-21
时间标签：0321_2348

本文用于落一版 **单 agent 之上的多 agent 协作运行层** 设计。

目标是把这层的定位、最小职责和必要对象先收住，不一步到位，不把它做成第二个 `agent_os`，也不把它做成第二个 `orchestrator`。

---

## 1. 一句话定位

这层的定位是：

> **位于 `AgentRuntime` 之上、`Orchestrator` 之下的局部协作运行层。**

它负责：

- 把静态 workflow / team template 装配成可运行的协作环境
- 绑定多个 agent / capability 到不同角色位
- 维护一个协作会话级 runtime
- 为上层 driver 提供局部推进与恢复能力

它不负责：

- 系统级 mission 调度
- 产品入口路由
- 全局 watchdog / daemon
- Feishu delivery
- 长期任务优先级和全局 quota

一句话：

> `agent_os` 解决单 agent 执行底座，`多 agent 协作运行层` 解决局部协作环境，`orchestrator` 解决系统级长期控制。

---

## 2. 为什么现在需要这层

当前系统已经逐渐形成三类东西：

1. `agent_os`
   - 有 contracts、receipts、runtime、factory、workflow substrate
   - 适合承接单 agent 执行底座和中性契约

2. `research scenarios`
   - 有静态 `workflow.spec.json`
   - 有 `ScenarioRunner`
   - 有 `ScenarioInstanceStore`

3. `orchestrator`
   - 有 `Mission / Node / Branch / Ledger`
   - 有 `OrchestratorService`
   - 有产品层 `MissionOrchestrator gateway`

当前缺的不是更多 agent，而是中间这层：

- 单个 agent 怎么跑，已有
- 系统级 mission 怎么调度，已有方向
- **多个 agent / role / step 如何在一个局部环境里被装起来并持续运行，当前还没有统一层**

如果没有这层，后面会出现两个坏结果：

1. `orchestrator` 被迫直接理解每种 workflow 内部细节
2. `research`、`subagent`、`team` 各自私有地重复实现装配逻辑

所以这层存在的目的不是“多搞一层抽象”，而是：

> **把“协作环境装配”和“系统级任务调度”分开。**

---

## 3. 它在总分层里的位置

推荐总关系式：

```text
Entrypoint / Adapter
  -> Router / Gateway
    -> Driver
      -> MultiAgent Runtime
        -> AgentRuntime
          -> agent_os substrate
```

其中：

- `TalkRouter` / `MissionOrchestrator gateway` 属于 `Router / Gateway`
- `ScenarioRunner` / `OrchestratorService` 属于 `Driver`
- 本文定义的层属于 `MultiAgent Runtime`
- `AgentRuntime` 负责单 agent 执行
- `agent_os` 提供 contracts / receipts / state / runtime substrate

### 3.1 与 `agent_os` 的关系

这层 **站在 `agent_os` 之上**，而不是塞回 `agent_os`。

它应复用：

- `Invocation`
- `PromptContext / MemoryPolicy / OutputBundle`
- `ExecutionReceipt / WorkflowReceipt / RouteProjection`
- `AgentSpec`
- runtime state / checkpoint / artifact 基础设施

但不应把自己的语义直接沉到底层：

- workflow role binding
- shared state schema
- team session 协调逻辑
- scene-specific runtime policy

原因：

- 这些东西还偏产品级、场景级
- 当前阶段还没有足够稳定，不应过早固化进中性 substrate

### 3.2 与 `orchestrator` 的关系

`orchestrator` 是这层的上层调用者，不是这层的实现者。

推荐关系：

- `orchestrator` 决定要不要起一个局部协作环境
- 这层负责把环境装起来并维护它的局部运行态
- `orchestrator` 只监督 session 级结果，不深入每个 role 内部细节

### 3.3 与 `research` 的关系

`research` 是这层最适合的第一批消费者，但不应该先把 research 重做成大而全 multi-agent 平台。

更稳的关系：

- `brainstorm / paper_discovery / idea_loop` 继续保留静态模板
- `ScenarioInstanceStore` 继续作为线程态存储
- 需要多角色协作时，由这层把模板 + instance state 装成一个协作 session
- `ScenarioRunner` 仍是 driver

---

## 4. 本层的最小职责

V0 只承担四件事：

1. `装载`
- 从静态模板装载 workflow / team 定义

2. `绑定`
- 把 role 与 `AgentSpec / capability / policy` 绑定起来

3. `实例化`
- 生成一个可持续的协作 session

4. `维护`
- 维护这个 session 的 shared state、artifact registry 和局部推进状态

注意：

- 这里只负责 **局部协作环境**
- 不负责全局任务队列
- 不负责产品入口
- 不负责 delivery transport

---

## 5. V0 的必要对象

这一版只保留 6 个对象。

要求是：

- 每个对象都必要
- 每个对象都尽量简洁
- 没有对象只是为了“显得架构完整”

### 5.1 `WorkflowTemplate`

作用：

- 表示一份静态协作模板
- 描述角色位、阶段骨架、输入输出约束、停止条件

为什么必要：

- 没有 template，就没有统一的静态真源
- research scenario / future mission subworkflow 都需要这种静态定义

V0 最小字段建议：

- `template_id`
- `kind`
- `roles`
- `steps`
- `entry_contract`
- `exit_contract`
- `defaults`

说明：

- 它是静态对象
- 不保存运行态

### 5.2 `RoleBinding`

作用：

- 把 template 里的角色位绑定到具体 `AgentSpec` 或 capability

为什么必要：

- 多 agent 协作最容易漂移的就是“谁来干什么”
- 没有显式 binding，就只能靠 prompt 猜角色

V0 最小字段建议：

- `role_id`
- `agent_spec_id`
- `capability_id`
- `policy_refs`
- `metadata`

说明：

- 一个 role 对应一个绑定
- 先不做复杂优先级仲裁

### 5.3 `WorkflowSession`

作用：

- 表示一份正在运行的协作实例
- 承载 session 身份和局部运行态引用

为什么必要：

- 没有 session，就没有恢复点、没有 checkpoint、没有真正的“协作实例”

V0 最小字段建议：

- `session_id`
- `template_id`
- `driver_kind`
- `status`
- `active_step`
- `role_bindings`
- `shared_state_ref`
- `artifact_registry_ref`
- `event_log_ref`

说明：

- 这是这层最核心的运行态对象
- 先把它当成“局部协作会话”来理解，不要当系统级任务

### 5.4 `SharedState`

作用：

- 保存多 agent 共享的最小状态
- 不是长期记忆，而是局部协作上下文

为什么必要：

- 多 agent 如果没有共享状态，就只有消息传话，没有真正协作环境

V0 最小字段建议：

- `session_id`
- `state`
- `state_version`
- `last_updated_at`

说明：

- 先支持 patch/update
- 不做复杂 CRDT 或 merge engine

### 5.5 `ArtifactRegistry`

作用：

- 为一个 session 统一登记中间产物和最终产物

为什么必要：

- handoff、judge、resume 都离不开 artifact 索引
- 没有 registry，协作状态就只能塞在自然语言里

V0 最小字段建议：

- `session_id`
- `artifacts`
- `latest_outputs`
- `refs_by_step`

说明：

- 它只做索引，不做大而全文件系统

### 5.6 `WorkflowFactory`

作用：

- 本层的装配入口
- 从 `WorkflowTemplate + RoleBinding + initial state` 生成 `WorkflowSession`

为什么必要：

- 这层如果没有统一装配入口，很快会在 research / orchestrator / talk 各自复制装配逻辑

V0 最小职责：

- load template
- resolve role bindings
- create session
- initialize shared state
- initialize artifact registry

说明：

- V0 中它只做 assemble，不做推进
- 它不是 orchestrator

---

## 6. V0 明确不引入的对象

为了保持克制，这一版刻意不引入下面这些对象。

### 6.1 不单独引入 `TeamRuntime`

原因：

- 它很容易和 `WorkflowSession` 重叠
- V0 先让 `WorkflowSession` 兼任局部 runtime 容器

### 6.2 不单独引入 `WorkflowSessionStore`

原因：

- 当前可先复用现有 scenario instance / mission store 风格
- 等结构稳定再抽统一 store 协议

### 6.3 不单独引入 `Mailbox`

原因：

- 这是重型 MAS 功能
- 当前先用 shared state + receipts + artifact refs 足够

### 6.4 不单独引入 `Coordinator Engine`

原因：

- V0 不追求复杂局部调度
- 当前局部推进仍由上层 driver 承担
- 后续如果真的需要，再从 `WorkflowSession` 中抽 `LocalCoordinator`

一句话：

> V0 先把环境装起来，先不把局部调度引擎也做出来。

---

## 7. V0 的调用方式

### 7.1 research 场景

```text
ResearchManager / ScenarioRunner
  -> WorkflowFactory
    -> WorkflowSession
      -> AgentRuntime
```

含义：

- `brainstorm / paper_discovery / idea_loop` 仍然是静态模板
- 由 `WorkflowFactory` 装成 session
- `ScenarioRunner` 继续做场景 driver

### 7.2 orchestrator 场景

```text
OrchestratorService
  -> WorkflowFactory
    -> WorkflowSession
      -> AgentRuntime
```

含义：

- `orchestrator` 可以把某个 node 绑定到一个 workflow template
- 它不需要理解模板内部的所有 role 细节
- 它只看 session 的局部结果、receipt 和 artifact

### 7.3 单 agent 场景

```text
TalkRouter / Driver
  -> AgentRuntime
```

含义：

- 不是所有任务都要进这层
- 单 agent 任务继续直接走 `AgentRuntime`
- 本层只在确实需要多角色 / 多步骤协作时启用

---

## 8. 推荐落点

因为这层目前还偏产品级、上层级，我建议 **先不要直接塞进 `agents_os`**。

更稳的建议是：

```text
butler_main/
  workflow_runtime/
    templates/
    session/
    factory/
```

或者：

```text
butler_main/
  collaboration_runtime/
    templates/
    session/
    factory/
```

推荐理由：

- 明确它是 `agent_os` 之上的共享层
- 同时可被 `research` 和 `orchestrator` 消费
- 避免过早把产品语义沉到 substrate

如果后续这层稳定了，再考虑把部分 contract 下沉到 `agents_os`。

---

## 9. 第一阶段实施顺序

V0 推荐按下面顺序推进：

1. 先定义 `WorkflowTemplate`
- 只支持静态模板读取

2. 再定义 `RoleBinding`
- 只支持显式绑定

3. 再定义 `WorkflowSession`
- 先只保留 session identity 和最小状态

4. 再做 `SharedState` 与 `ArtifactRegistry`
- 先支持简单 patch 和 artifact refs

5. 最后做 `WorkflowFactory`
- 只负责装配，不负责推进

这个顺序的好处是：

- 可以先用在 research 场景
- 不会立刻逼着 orchestrator 重构
- 不会一步做成大平台

---

## 10. 一句话结论

当前最稳的设计不是“再做一个更大的 workflowFactory”，而是：

> **在 `AgentRuntime` 之上增加一个最小的 `多 Agent 协作运行层`：它只负责装配和维护协作会话级 runtime；`WorkflowFactory` 是其入口，`WorkflowSession` 是其核心运行态对象，而 `Orchestrator` 仍然是系统级长期控制者。**

这就是 V0 应该守住的边界。

---

## 11. 对应代码骨架（V0）

当前已先把这层按 V0 设计落成一个独立包：

```text
butler_main/
  Muti_Agents_os/
    __init__.py
    README.md
    templates/
      __init__.py
      workflow_template.py
    bindings/
      __init__.py
      role_binding.py
    session/
      __init__.py
      workflow_session.py
      shared_state.py
      artifact_registry.py
    factory/
      __init__.py
      workflow_factory.py
```

对象到文件的映射如下：

- `WorkflowTemplate`
  - `butler_main/Muti_Agents_os/templates/workflow_template.py`
- `RoleBinding`
  - `butler_main/Muti_Agents_os/bindings/role_binding.py`
- `WorkflowSession`
  - `butler_main/Muti_Agents_os/session/workflow_session.py`
- `SharedState`
  - `butler_main/Muti_Agents_os/session/shared_state.py`
- `ArtifactRegistry`
  - `butler_main/Muti_Agents_os/session/artifact_registry.py`
- `WorkflowFactory`
  - `butler_main/Muti_Agents_os/factory/workflow_factory.py`

### 11.1 当前代码状态

这一轮代码文件只保留职责注释，不写实现。

目的：

- 先把层级边界和对象落点钉死
- 先让 `research`、`orchestrator`、`talk` 后续接线时有明确 import 位置
- 避免在对象设计尚未稳定前提前堆实现细节

### 11.2 当前包边界

`Muti_Agents_os` 当前被刻意放在 `butler_main/` 下，而不是直接塞进 `agents_os/`。

理由：

- 当前它仍属于 `agent_os` 之上的共享层
- 语义还偏产品级 / 场景级
- 还不适合直接沉到中性 substrate

如果未来对象和协议稳定，再考虑把部分 contracts 或 session protocol 下沉到 `agents_os`。
