# 0319 runtime 完全解耦收口汇报与 adapter 指南

更新时间：2026-03-19 15:57
时间标签：0319_1557

---

## 第一部分：核心汇报 + 新架构

### 1. 当前结论

本轮收口后的结论是：

> Butler 主执行链已经完成 runtime 解耦。`agents_os` 负责 runtime core，Butler 只保留业务域、角色/prompt、接口适配、工作区资产，以及属于 Butler 自己的 manager-local adapters。

这里的“完全解耦”指的是：

- 主链不再直接依赖旧 `runtime/*` 实现
- 主链不再直接依赖旧 `heartbeat/runtime_state.py`、`heartbeat/run_trace.py`
- Butler-specific adapter 不再放进 `agents_os`
- `agents_os` 不再承载 Butler 私有业务语义
- 旧 runtime / heartbeat 壳已删除；剩余少量 legacy implementation 仅允许躲在 adapter 后面

### 2. 已经收口到哪里

#### 2.1 `agents_os` 现在承担的 runtime core

已抽入/建立的 runtime core 主要包括：

- `butler_main/agents_os/execution/cli_runner.py`
- `butler_main/agents_os/execution/cursor_cli_support.py`
- `butler_main/agents_os/execution/runtime_policy.py`
- `butler_main/agents_os/execution/logging.py`
- `butler_main/agents_os/state/run_state_store.py`
- `butler_main/agents_os/state/trace_store.py`
- `butler_main/agents_os/context/memory_backend.py`
- `butler_main/agents_os/tasking/task_store.py`

它们的定位是：

- CLI 执行器统一壳层
- runtime 状态 / trace 基础设施
- 通用 memory backend 协议
- 通用 task store 协议
- 为后续 `cursor_cli / codex_cli / claude_cli` 继续扩展预留 provider slot

#### 2.2 Butler 现在保留的 manager-local adapters

Butler 专属 adapter 已明确留在 Butler 自己目录，而不是进入 `agents_os`：

- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/runtime_policy.py`
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/task_ledger_store.py`
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/paths.py`
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_task_source.py`
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_truth.py`
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_scheduler.py`
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_runtime_state.py`
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_run_trace.py`
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/manager_blueprint.py`

这层的职责不是发明 runtime，而是：

- 把 Butler 现有真源、路径、调度、任务视图，映射到 `agents_os` 所需 contract
- 吞掉 Butler 历史文件名、路径约定、任务真源结构差异
- 保证以后新增 manager 时，adapter 跟 manager 本体走，而不是污染 runtime core

### 3. 主链现在怎么走

当前主链已经收口为：

```text
interface / manager entry
  -> Butler manager logic
    -> Butler-local agents_os_adapters
      -> agents_os runtime core
        -> cli worker/provider
```

在 Butler 主链中，关键接线点已经变成：

- `butler_main/butler_bot_code/butler_bot/butler_bot.py`
- `butler_main/butler_bot_code/butler_bot/agent.py`
- `butler_main/butler_bot_code/butler_bot/self_mind_bot.py`
- `butler_main/butler_bot_code/butler_bot/memory_manager.py`
- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`

这些主链文件现在统一经过：

- `agents_os.execution.*`
- `agents_os.state.*`
- `butler_bot/agents_os_adapters/*`

而不再直接走旧 runtime 主体。

### 4. Butler 现在应该只保留什么

收口后的 Butler 应只保留四类东西：

#### 4.1 业务域

- 任务语义
- 个人管家业务规则
- 心跳业务决策
- self_mind / personal memory / 角色协作逻辑

#### 4.2 角色与 prompt 资产

- role
- prompts
- bootstrap
- skills
- protocol 文本资产

#### 4.3 interface / adapter

- 飞书入口
- CLI 入口
- 任务真源 adapter
- scheduler / truth / task_source / runtime_state / run_trace 之类 manager-local adapter

#### 4.4 workspace / artifacts

- Butler 自己的 run 目录
- task workspace
- local memory
- self_mind 资产
- 各类 markdown / json 产物

### 5. 旧壳删除后的剩余情况

本轮进一步收口后，以下旧壳已经删除：

- 旧 `runtime/` 目录整体
- 旧 `heartbeat/runtime_state.py`
- 旧 `heartbeat/run_trace.py`
- 旧 `heartbeat/task_source.py`
- 旧 `heartbeat/truth.py`
- 旧 `heartbeat/scheduler.py`
- 旧 `heartbeat/models.py`

现在剩下的 legacy 成分，主要只有两类：

- `services/task_ledger_service.py`：仍作为 Butler 任务真源底层实现，被 `agents_os_adapters/task_ledger_store.py` 包裹
- 文档与历史产物中的旧命名：仅作为迁移记录，不参与主链运行

因此当前状态不是“主链不用旧壳，但旧壳还在”，而是：

> 主链已完成切换，且大部分旧 runtime / heartbeat 壳已经实际删除；剩余 legacy 只保留在少数被 adapter 吞掉的底层实现中。

### 6. 当前新架构

建议把 Butler / `agents_os` 的关系固定为下面这套结构：

```text
butler_main/
  agents_os/
    execution/
    state/
    context/
    tasking/

  butler_bot_code/
    butler_bot/
      agents_os_adapters/
      services/
      prompts / role / bootstrap / interface
```

边界规则固定为：

#### Rule A：`agents_os` 只放 core

只允许放：

- runtime contracts
- generic execution
- generic state / trace
- generic memory/task protocol
- generic runtime utility

不允许放：

- Butler 专属路径
- Butler 专属任务 schema 细节
- Butler 专属 prompt / role / workspace 习惯

#### Rule B：adapter 跟 manager 走

哪个 manager 在用，adapter 就放哪个 manager 目录里。

因此未来如果有：

- `butler`
- `research_manager`
- `ops_manager`

那么每个 manager 都各自维护自己的：

- `agents_os_adapters/`
- prompts
- interface

#### Rule C：Butler 不再自己内嵌 runtime core

Butler 负责使用 runtime，不再继续长出新的 runtime 黑箱。

### 7. 当前验证结果

截至 2026-03-19，本轮收口验证结果为：

- 主链扫描已确认不再直接依赖旧 runtime 主体
- 语法编译已通过
- 目标回归测试已通过：`101 passed`

因此这一轮可以视为：

> runtime 主链解耦完成；legacy 残留已降级为兼容层；新架构边界已经成形。

---

## 第二部分：给后续 Codex 看 —— 现状 + 怎么 adapter runtime

### 1. 先认清现在的现状

后续如果再接着做，不要把现在误判成“两边都还有一半 runtime，所以继续在 Butler 里补洞”。

正确判断是：

- `agents_os` 已经是 runtime core 的正式落点
- Butler 侧只允许保留 manager-local adapters
- Butler 主链已经改到通过 adapter + core 运行
- 旧 runtime / heartbeat 壳已删除，不要再恢复回来

尤其要注意：

- 不要再把 Butler-specific adapter 塞回 `agents_os`
- 不要再让 `memory_manager.py` 直接依赖旧 runtime 文件
- 不要再让新 manager 复制 `memory_manager.py` / `heartbeat_orchestration.py` 成为新黑洞

### 2. 当前哪些地方仍是“承接层”，不是终局

以下部位属于“必要承接层”，不是终局核心：

#### 2.1 `task_ledger_store.py`

`butler_main/butler_bot_code/butler_bot/agents_os_adapters/task_ledger_store.py`

当前仍然包着 Butler 历史任务真源实现。

这没有问题，因为它现在的位置已经正确：它属于 Butler adapter，不属于 `agents_os` core。

后续如需继续净化，应做的是：

- 保持 `agents_os/tasking/task_store.py` 只定义通用 contract
- 在 Butler adapter 内逐步减少 legacy service 包袱
- 不要把 Butler 的任务 schema 反向推进 `agents_os`

#### 2.2 heartbeat 旧壳已删除

旧 `heartbeat/runtime_state.py`、`heartbeat/run_trace.py`、`heartbeat/task_source.py`、`heartbeat/truth.py`、`heartbeat/scheduler.py` 已删除。

后续不要再恢复同类文件名和旧分层。

如果需要类似能力，只允许：

- 进 `agents_os` core
- 或进 manager-local `agents_os_adapters/`

### 3. 后续如果要接入一个新 manager，正确做法是什么

假设你现在要新起一个与 Butler 并行的 `research_manager`。

正确搭法不是复制 Butler 黑洞，而是按下面四层来：

#### 3.1 直接复用 `agents_os` core

至少直接复用：

- `execution/cli_runner.py`
- `execution/runtime_policy.py`
- `execution/logging.py`
- `state/run_state_store.py`
- `state/trace_store.py`
- `context/memory_backend.py`
- `tasking/task_store.py`

如果未来要补 `codex_cli`、`claude_cli`，优先补在 `agents_os/execution/cli_runner.py` 这一层，而不是塞回某个 manager 私有文件。

#### 3.2 在 manager 自己目录下建 `agents_os_adapters/`

例如：

```text
research_manager/
  agents_os_adapters/
    runtime_policy.py
    task_store.py
    truth.py
    task_source.py
    scheduler.py
    runtime_state.py
    run_trace.py
```

这层只负责把新 manager 自己的：

- 路径
- 任务真源
- scheduler
- workspace 约定
- 兼容视图

映射成 `agents_os` 所需协议。

#### 3.3 prompts / role / interface 继续跟 manager 自己走

新 manager 应自己拥有：

- prompts
- roles
- bootstrap
- interface

不要把这些搬进 `agents_os`。

#### 3.4 manager 本体只做 orchestration，不做 runtime 发明

新的 manager 文件只应该负责：

- 收请求
- 组装 planning context
- 调 adapter
- 调 runtime core
- 汇总结果

不应该再次在 manager 内部私造：

- runtime state 格式
- CLI 执行框架
- tracing 文件协议
- provider 切换逻辑

### 4. 以后 adapter runtime 的标准步骤

如果后续 Codex 要给某个 manager 接 runtime，按下面步骤做：

#### Step 1：先找 Butler 现有可复用部分

先判断已有代码属于哪一类：

- 干净通用：进 `agents_os`
- Butler 私有但有价值：放 manager-local adapter
- 又脏又重：不迁移，直接重写

#### Step 2：先定 contract，再接旧实现

不要先搬代码。

先确认它要落在哪个 contract 上，例如：

- `task store`
- `runtime state`
- `trace store`
- `runtime policy`
- `scheduler`
- `truth`

然后再决定是封装旧实现，还是重做。

#### Step 3：只允许 manager 通过 adapter 接 core

manager 主链里不允许直接出现：

- 旧 runtime import
- 旧 heartbeat state/trace import
- 旧 task ledger 直连

必须走：

```text
manager -> agents_os_adapters -> agents_os
```

#### Step 4：保留 legacy 时，必须标明定位

凡是暂时删不掉的旧文件，都要明确标注为：

- legacy compatibility
- migration reference
- not for new logic

否则后面的人会继续往里面加功能，耦合会回流。

### 5. 后续 Codex 必须遵守的硬规则

#### 硬规则 1

`agents_os` 内禁止出现 Butler-specific adapter。

#### 硬规则 2

Butler / future manager 主链禁止直接 import 旧 runtime 主体。

#### 硬规则 3

新 manager 一律按：

> `core + adapters + prompts + interface`

四层搭，不复制 Butler 黑洞总控。

#### 硬规则 4

遇到非必要、冗余、陈旧、脏逻辑时，不做“迁移保真”，优先做：

- 删
- 截断
- 重写最小必要壳层

而不是把旧问题平移到新目录。

### 6. 一句话给后续 Codex 的行动指令

后续继续建设时，请始终按下面这句话执行：

> 把 `agents_os` 当 runtime core，把 Butler 当 manager 实例；adapter 跟 manager 走；prompt 与 interface 跟业务走；旧 runtime 只许降级，不许回流。
