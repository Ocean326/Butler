# 0319 agents_os 抽核与重建承接清单

更新时间：2026-03-19 13:33
时间标签：0319_1333

> 最终收口与后续 adapter 指南，见：`docs/daily-upgrade/0319/1557_runtime完全解耦收口汇报与adapter指南.md`

## 一、这份清单要解决什么

当前 Butler 的核心问题不是“没有分层意识”，而是：

- runtime 事实已经存在，但散落在 `butler_bot_code/`、`butler_bot_agent/agents/`、`butle_bot_space/self_mind/`
- 业务、角色资产、接口适配、运行时状态、私有沉淀混在一起
- `memory_manager.py` 与 `heartbeat_orchestration.py` 仍然像两个超重总控

因此，`agents_os` 的任务不是“再造一个 Butler”，而是：

> 从 Butler 现有系统中抽出干净、通用、稳定、可复用的 runtime 内核；对缺失能力补最小新实现；对明显脏、冗余、陈旧的机制不迁移、不继承，直接在新内核中重建。

## 二、总边界

### 2.1 未来 `agents_os` 负责什么

- runtime contracts
- run / session / workflow / worker 内核
- runtime state / trace / artifact / context 等基础设施
- 调度、恢复、门控、执行器适配的通用壳层
- runtime 与 domain 之间的 protocol / interface hook

### 2.2 未来 Butler 本体只保留什么

- 业务域
- 角色 / prompt / bootstrap / skill / rule 资产
- 接口适配（talk / heartbeat / cli / feishu / api）
- 工作区与产物资产
- 私有 self_mind / life-space 沉淀

一句话：

> `agents_os` 负责 runtime；Butler 负责业务、人格、入口、工作区。

## 三、抽核判断标准

每个旧部件都按四档判断：

### A. 可直接抽取

特征：

- 职责单一
- 依赖方向干净
- 通用度高
- 不强绑 prompt / 业务语义 / 私有空间

处理：

- 直接迁入 `agents_os`
- 只做轻量命名与接口收口

### B. 可薄封装承接

特征：

- 本体有价值
- 但路径、字段、命名或输入输出明显带 Butler 历史痕迹

处理：

- 在 `agents_os` 定义 protocol / base contract
- 用 Butler 本体目录下的 `agents_os_adapters/` 承接旧实现
- 等核心稳定后再逐步去 Butler-specific

### C. 必须重写

特征：

- 总控过重
- 多职责粘连
- runtime / business / prompt / state 混写
- 即使搬走也只会把旧问题复制到新目录

处理：

- 不迁移整体文件
- 只参考其已有行为与下游依赖
- 在 `agents_os` 中按职责重新实现

### D. 不进入 `agents_os`

特征：

- 本质上属于业务域、角色资产、接口层、私有空间
- 或是明确的历史遗留、运行噪音、兼容副产物

处理：

- 留在 Butler
- 或直接标记为淘汰/兼容视图

## 四、推荐的 `agents_os` 内部结构

建议在当前 `runtime/` 最小骨架之上，逐步长出：

```text
butler_main/
  agents_os/
    runtime/
      contracts.py
      kernel.py
    execution/
      cli_runner.py
      worker_adapter.py
    state/
      run_state_store.py
      trace_store.py
      artifact_store.py
    tasking/
      task_store.py
      run_store.py
    context/
      context_store.py
      memory_backend.py
    scheduling/
      trigger.py
      scheduler.py
    guardrails/
      policy.py
    adapters/
      butler/
        paths.py
        task_ledger_store.py
        heartbeat_trigger.py
        recent_memory_store.py
        self_mind_state_adapter.py
        runtime_policy.py
```

这里的关键不是目录多少，而是：

- 核心层不直接知道 Butler 的 prompt 与业务
- Butler-specific 的承接统一放在 `butler_main/butler_bot_code/butler_bot/agents_os_adapters/`
- 以后抽核时，优先决定“进核心”还是“只进 adapter”

## 五、抽离总表

### 5.1 可直接抽取到 `agents_os`

#### 1. `butler_main/butler_bot_code/butler_bot/runtime/cli_runtime.py`

判断：**可直接抽取（小幅改名）**

原因：

- 这是比较干净的 CLI provider 调用层
- 核心职责明确：provider settings、availability、run prompt、fallback
- 不依赖 `memory_manager.py`
- 基本不带业务语义

承接方式：

- 进入 `agents_os/execution/cli_runner.py`
- 保留现有 `cursor / codex` provider 能力
- 把 `resolve_runtime_request()`、`run_prompt()` 变成 worker adapter 底层能力

需要改造：

- 去掉模块名里的旧 `runtime` 历史语义
- 把“cli runtime 配置”映射到 `WorkerAdapter` 概念
- 后续把 provider config 与 branch policy 分离

#### 2. `butler_main/butler_bot_code/butler_bot/heartbeat/runtime_state.py`

判断：**可直接抽取**

原因：

- 这是一个相对纯的文件态 runtime state store
- 只有路径和文件名带 Butler 语义
- `pid / watchdog / run_state / stale probe / lock` 这些都属于 runtime 基础设施

承接方式：

- 进入 `agents_os/state/run_state_store.py`
- 抽成更中性的 file-based runtime state store
- Butler-specific 文件名通过 adapter 或配置注入

#### 3. `butler_main/butler_bot_code/butler_bot/heartbeat/run_trace.py`

判断：**可直接抽取**

原因：

- 本质是 file trace store
- 跟具体 heartbeat prompt 没强绑定
- 事件追加、summary、compact 都是通用 runtime tracing 能力

承接方式：

- 进入 `agents_os/state/trace_store.py`
- 保留 file-backed 实现
- 后续让 `HeartbeatRunTraceService` 退化成 Butler adapter

#### 4. `butler_main/butler_bot_code/butler_bot/heartbeat/models.py`

判断：**可直接抽取（部分合并）**

原因：

- dataclass 比较干净
- `RuntimeStatusSnapshot`、`RunTraceSummary` 可直接成为 runtime 侧模型

承接方式：

- 与 `agents_os/runtime/contracts.py` 合并或拆为 `agents_os/state/models.py`
- `PromotionDecision` 先不急着进核心，必要时放到 adapter

#### 5. `butler_main/butler_bot_code/butler_bot/services/memory_backend.py`

判断：**可直接抽协议，文件实现走薄封装**

原因：

- `EpisodicStore / SemanticStore / SelfModelStore / ProspectiveStore / MemoryBackend` 这些 protocol 很适合作为内核抽象
- `FileJsonCollection` 也是干净的小组件
- 但 `FileMemoryBackend` 当前路径和源目录强绑 Butler

承接方式：

- protocol 和 `FileJsonCollection` 进入 `agents_os/context/memory_backend.py`
- `FileMemoryBackend` 如需 Butler-specific 落地，先放 Butler 本体目录下的 `agents_os_adapters/` 一类位置

### 5.2 可薄封装承接到 Butler 本体 `agents_os_adapters/`

#### 6. `butler_main/butler_bot_code/butler_bot/services/task_ledger_service.py`

判断：**可薄封装承接，但不能整块当内核**

原因：

优点：

- 已经是 machine-readable truth
- 有 schema、load/save、normalize、run 应用能力
- 是当前最接近任务真源的正式实现

问题：

- 同时混了 task workspace materialization
- 同时混了 markdown detail/progress/final report 投影
- 同时兼容 legacy payload 导出
- task item 字段仍强带 Butler 历史业务语义

承接方式：

- 在 `agents_os/tasking/task_store.py` 先定义 `TaskStore` protocol
- 把现有 `TaskLedgerService` 包成 `butler_main/butler_bot_code/butler_bot/agents_os_adapters/task_ledger_store.py`
- 先复用 load/save/normalize truth 的核心逻辑
- 把 `workspace markdown projection` 分离为 Butler projection service
- 把 `export_legacy_payloads()` 明确打成兼容层，不算核心

结论：

> 它是必须承接的真源，但不能原样当作 `agents_os` 内核。

#### 7. `butler_main/butler_bot_code/butler_bot/runtime/runtime_router.py`

判断：**只抽通用壳，策略留 Butler adapter**

原因：

- provider availability、quota guard、fallback 思路是有价值的
- 但 `acceptance/test/team/default executor` 这些选择逻辑，本质上是 Butler branch policy
- 它不是纯 runtime core，而是 Butler 的 runtime selection policy

承接方式：

- `agents_os` 只定义 worker selection / provider availability 的接口
- 现有 routing policy 暂时放 `butler_main/butler_bot_code/butler_bot/agents_os_adapters/runtime_policy.py`
- 后续如果 Research / Project 需要不同策略，再由 Butler domain 自己提供 policy

#### 8. `butler_main/butler_bot_code/butler_bot/heartbeat/task_source.py`

判断：**保留为 Butler heartbeat adapter**

原因：

- 它很干净
- 但它做的是 heartbeat 白名单、污染检测、governance task 筛选
- 这些不是 runtime 普适规则，而是 Butler heartbeat 入口规则

承接方式：

- 进入 Butler 本体目录下的 `agents_os_adapters/heartbeat_task_source.py`
- 不进 runtime core
- 后续可作为 `HeartbeatTriggerAdapter` 的一部分

#### 9. `butler_main/butler_bot_code/butler_bot/heartbeat/truth.py`

判断：**可薄封装承接**

原因：

- 它本质是 `TaskLedgerService` facade
- 语义清楚：heartbeat truth = task ledger truth
- 但它本身没有提供新的 runtime 核心抽象

承接方式：

- 不单独升级成核心模块
- 合并进 Butler adapter 层，作为 `task truth facade`

#### 10. `butler_main/butler_bot_code/butler_bot/heartbeat/scheduler.py`

判断：**保留为 Butler heartbeat trigger adapter**

原因：

- 它提供的是当前 heartbeat 入口如何 fallback / normalize plan
- 仍明显是 Butler heartbeat 专用调度
- 不是通用 scheduler kernel

承接方式：

- 放 Butler 本体目录下的 `agents_os_adapters/heartbeat_trigger.py`
- 真正通用 scheduler 以后在 `agents_os/scheduling/` 重建

#### 11. `butler_main/butler_bot_code/butler_bot/services/self_mind_state_service.py`

判断：**只作为 Butler private-domain adapter**

原因：

- 它很干净，路径与 state 访问都比较清晰
- 但对象服务的是 `self_mind` 私有空间
- `self_mind` 不应变成 runtime core

承接方式：

- 暂不放进 runtime core
- 可进入 Butler 本体目录下的 `agents_os_adapters/self_mind_state_adapter.py`
- 仅作为 Butler 私有 domain 的 state adapter

### 5.3 明确保留在 Butler 本体

#### 12. `butler_main/butler_bot_code/butler_bot/services/request_intake_service.py`

判断：**保留 Butler**

原因：

- 它是前台入口分诊
- 强依赖用户表达风格、接口语境、输出偏好
- 属于 interface intelligence，而不是 runtime core

#### 13. `butler_main/butler_bot_code/butler_bot/services/prompt_assembly_service.py`

判断：**保留 Butler**

原因：

- 这是角色 / prompt / memory 投影装配层
- 本质属于 Butler prompt asset adapter
- 不应进入 runtime core

#### 14. `butler_main/butler_bot_code/butler_bot/registry/agent_capability_registry.py`

判断：**保留 Butler**

原因：

- 这是 agent/team/public library 资产注册表
- 本质属于角色资产层
- 不是 runtime 内核

#### 15. `butler_main/butler_bot_code/butler_bot/execution/agent_team_executor.py`

判断：**暂留 Butler，后续包成 worker adapter**

原因：

- 它有执行价值
- 但现在强绑角色文件、workspace hint、subagent prompt 结构
- 更像 Butler agent asset executor，而不是纯 worker engine

承接方式：

- 先保留在 Butler
- 未来作为 `ButlerTeamWorkerAdapter` 接到 `agents_os`

#### 16. `butler_main/butler_bot_code/butler_bot/agent.py`
#### 17. `butler_main/butler_bot_code/butler_bot/butler_bot.py`
#### 18. `butler_main/butler_bot_code/manager.ps1`

判断：**全部保留 Butler**

原因：

- 它们分别属于 talk / frontdoor / process manager
- 是明确的接口适配与运维外壳
- 未来应该更薄，但不应进入 `agents_os` 核心

### 5.4 必须重写，禁止整块迁移

#### 19. `butler_main/butler_bot_code/butler_bot/memory_manager.py`

判断：**必须重写，不迁移整体文件**

原因：

- 这是最大的黑洞
- 它把 heartbeat、runtime state、memory backend、self_mind、delivery、governance、CLI runtime、approval、subprocess 全吸进来了
- 把它搬进 `agents_os`，等于把旧耦合整体复制过去

承接策略：

- 完全不迁移 `MemoryManager` 作为类
- 只把其中已经拆出来的 clean service 作为参考来源
- 在 `agents_os` 中分别重建：
  - context store
  - trace / state store
  - worker execution bridge
  - task store adapter
  - guardrail / governance hook
- 旧 `MemoryManager` 未来退化为 Butler compatibility facade

#### 20. `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`

判断：**必须重写，不迁移整体文件**

原因：

- 它仍然同时承担 planner prompt 组织、branch runtime 选择、team 执行、skill 注入、task 处理等多职责
- 它是 Butler 当前 heartbeat 业务总控，不是可直接复用的 workflow engine

承接策略：

- 不迁移整个 orchestrator
- 只参考其行为边界与输入输出
- 在 `agents_os` 重建：
  - workflow engine
  - run dispatch
  - branch/step execution abstraction
- 在 Butler 侧保留 `HeartbeatInterfaceAdapter`，把 heartbeat 计划转成 agents_os run

## 六、`agent / state / recent / local / self_mind` 的错位清单

### 6.1 `butler_bot_agent/agents/state/`

判断：**这是运行态，不是角色资产**

其中至少包括：

- `task_ledger.json`
- `task_workspaces/`
- `heartbeat_plan_output.json`
- `guardian_ledger/`

处理原则：

- `task_ledger.json`：作为任务真源，未来由 `agents_os` 承接
- `task_workspaces/`：属于 workspace projection / report materialization，不是核心 truth，应降为 Butler projection
- `heartbeat_plan_output.json`：临时运行中间态，不应长期作为 agent 资产
- `guardian_ledger/`：历史强、噪音大、遗留重，默认不迁移进新内核

### 6.2 `butler_bot_agent/agents/local_memory/`

判断：**稳定认知资产与运行态混放**

应保留为 Butler 资产的：

- `Butler_SOUL.md`
- `Current_User_Profile.*`
- 人格 / 规则 / 说明类 markdown
- 稳定长期认知摘要

应迁出或降级为 projection / runtime state 的：

- `heartbeat_tasks.md`
- `heartbeat_tasks/`
- `heartbeat_long_tasks.json`
- `heartbeat_planner_state.json`
- `local_memory_write_journal.jsonl`

结论：

> `local_memory/` 不能再被视为纯角色资产目录；必须拆出“稳定认知”与“运行时派生物”。

### 6.3 `butler_bot_agent/agents/recent_memory/`

判断：**这是运行时上下文缓存，不是 agent 资产**

如：

- `recent_memory.json`
- `recent_raw_turns.json`
- `recent_summary_pool.json`
- `heartbeat_last_sent.json`
- `self_mind_talk_state.json`
- `startup_maintenance_status.json`

处理原则：

- 未来应由 `agents_os` 的 context/runtime adapter 读写
- Butler 只消费其投影结果，不再把它放在“agent 资产”名义下

### 6.4 `butle_bot_space/self_mind/`

判断：**大部分属于 Butler 私有 domain 数据，不属于 runtime core**

应保留在 Butler/space 的：

- `daily/`
- `logs/`
- `explore/`
- `cognition/`
- `listener_history/`
- 各类心理活动、认知、生活沉淀文件

仅作为状态适配读取的：

- `mind_loop_state.json`
- `mind_body_bridge.json`
- `current_context.md`
- `perception_snapshot.md`

结论：

> `self_mind` 是 Butler 私有 domain，不应升格为 `agents_os` 核心；`agents_os` 只通过 adapter 访问其少数状态文件。

## 七、推荐的抽离顺序

### Wave 1：先抽最干净的 runtime 基建

优先：

- `cli_runtime.py`
- `heartbeat/runtime_state.py`
- `heartbeat/run_trace.py`
- `heartbeat/models.py`
- `memory_backend.py` 的 protocol 部分

目标：

- 先让 `agents_os` 拥有执行器、状态、trace、memory protocol 的最小骨架

### Wave 2：接 Butler adapter，而不是碰黑洞

优先：

- `task_ledger_service.py` -> `TaskStore + ButlerTaskLedgerAdapter`
- `runtime_router.py` -> `ButlerRuntimePolicyAdapter`
- `heartbeat/task_source.py` / `truth.py` / `scheduler.py` -> `ButlerHeartbeatTriggerAdapter`
- `self_mind_state_service.py` -> `ButlerSelfMindStateAdapter`

目标：

- 新内核开始能借用旧 Butler 的真源与触发器
- 但仍不把旧总控搬进去

### Wave 3：让旧 Butler 先“挂”在新内核上跑

目标链路：

`heartbeat 单轮 -> Butler heartbeat adapter -> agents_os run -> cli worker -> trace/result -> 回写 Butler task ledger`

重点：

- 先证明新内核能承接旧链路
- 不急着替换 talk / self_mind / research domain

### Wave 4：重写黑洞总控

重写目标：

- `heartbeat_orchestration.py` -> workflow engine + heartbeat adapter
- `memory_manager.py` -> Butler compatibility facade + agents_os services composition

### Wave 5：收口 Butler 本体

最后让 Butler 只剩：

- domain
- prompt / role / skill / rules
- interfaces
- workspace assets

## 八、最重要的三条铁律

### 1. 不迁移黑洞

`memory_manager.py`、`heartbeat_orchestration.py` 这种文件，绝不能整体搬进 `agents_os`。

### 2. 不把资产当内核

`agents/`、`bootstrap/`、`skills/`、`self_mind/` 这些目录里的稳定资产，不应反向定义 runtime 结构。

### 3. 迁走后旧 Butler 必须变薄

如果某块能力迁到 `agents_os` 后，旧 Butler 里仍然保留一份同级主逻辑，那不算抽核成功。

## 九、当前最值得立刻开始的动作

下一步最值钱的不是继续大谈概念，而是立刻形成四张表：

1. `可直接抽取清单`
2. `可薄封装清单`
3. `必须重写清单`
4. `不进入 agents_os 清单`

而基于本轮分析，首批建议就是：

### 立刻抽

- `cli_runtime.py`
- `runtime_state.py`
- `run_trace.py`
- `heartbeat/models.py`
- `memory_backend.py` 协议层

### 立刻包 adapter

- `task_ledger_service.py`
- `runtime_router.py`
- `task_source.py`
- `truth.py`
- `scheduler.py`
- `self_mind_state_service.py`

### 明确禁止整体迁移

- `memory_manager.py`
- `heartbeat_orchestration.py`

### 明确保留在 Butler

- `agent.py`
- `butler_bot.py`
- `manager.ps1`
- `request_intake_service.py`
- `prompt_assembly_service.py`
- `agent_capability_registry.py`
- `butler_bot_agent/bootstrap/`
- `butler_bot_agent/agents/` 中的角色资产
- `butle_bot_space/self_mind/` 中的私有沉淀

## 十、一句话结论

Butler 现在不是要“再做一个新系统”，而是要：

> 先把现有系统里真正属于 runtime 的干净骨头抽出来，让 `agents_os` 承接它们；再让旧 Butler 逐步退回业务域、角色资产、接口适配和工作区资产。
## 十一、Wave 1 当前落地（2026-03-19）

已完成：

- `butler_main/agents_os/execution/cli_runner.py`
  - 统一收口 CLI provider 选择、availability、fallback、model/runtime request 归一化
  - 当前优先承接 `cursor`
  - 同时为未来 `codex_cli`、`claude_cli` 保留 canonical provider 名与执行入口
- `butler_main/agents_os/state/run_state_store.py`
  - 从 Butler heartbeat runtime state 抽出通用 file-based state store
- `butler_main/agents_os/state/trace_store.py`
  - 从 Butler heartbeat trace 抽出通用 file-based trace store
- `butler_main/agents_os/context/memory_backend.py`
  - 抽出 memory protocol 与 file backend 最小实现
- `butler_main/butler_bot_code/butler_bot/butler_bot.py`
  - 主入口已切到 `agents_os.execution.cli_runner`
  - CLI 指令控制面已纳入 `claude-cli` 预留 alias

当前仍刻意不动：

- `memory_manager.py` 整体不迁
- `heartbeat_orchestration.py` 整体不迁
- `task_ledger_service.py` 等 Butler 真源先留待 Wave 2 做 adapter 承接

这意味着 Wave 1 的目标已经从“概念层抽核”推进到“执行层 + 状态层 + context 协议层已可落地复用”，并且没有把旧黑洞文件整体搬入 `agents_os`。
## 十二、Wave 2 当前落地（2026-03-19）

已完成：

- `butler_main/agents_os/tasking/task_store.py`
  - 把任务真源承接先收成最小协议，而不是直接把旧账本服务升格成内核
- `butler_main/agents_os/execution/runtime_policy.py`
  - 把 branch runtime 选择策略先收成最小协议，而不是把 Butler 路由规则直接写死在 core
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/task_ledger_store.py`
  - 对旧 `TaskLedgerService` 做薄封装承接
  - 当前保留 `load/save/bootstrap/apply_heartbeat_result` 等旧入口，方便旧链路平滑挂接
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/runtime_policy.py`
  - 对旧 `runtime_router` 负责的 branch policy 做 adapter 化重建
  - provider availability / cli normalization 改为直接复用 `agents_os/execution/cli_runner.py`
  - `codex` 选择配额统计已迁到 Butler 的 `butler_main/butler_bot_code/run/agents_os_runtime_policy_codex_usage.json`
- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`
  - 已切到新的 `ButlerTaskLedgerStore` 与 `ButlerRuntimePolicyAdapter`
  - 旧 orchestrator 本体暂不重写，只先替换真源与 policy 接缝

这一步的意义：

- `task_ledger` 与 `runtime_router` 已经不再直接定义未来抽核方向
- 它们现在先降级为 Butler-specific adapter 背后的 legacy source
- 新的真源边界开始转移到 `agents_os` 的 protocol + Butler 侧 adapter 结构上

仍然刻意不做：

- 不把 `task_workspaces` 投影逻辑升格成 core
- 不把 `memory_manager.py` 的 runtime / memory / governance / prompt 总控直接搬进 `agents_os`
- 不把 `heartbeat_orchestration.py` 的 planner prompt 组织、branch prompt 拼装、业务语义直接升级成 workflow core


## 十三、边界修正（2026-03-19）

本轮重新审视后，明确修正一条边界：

- `agents_os` 只放 runtime core、protocol、通用基础设施
- 凡是 Butler-specific 的 adapter，一律放回 `butler_main/butler_bot_code/butler_bot/agents_os_adapters/`
- 这样 `agents_os` 不会被 Butler 私有承接层反向污染，Butler 也保留自己的接口适配自主权
## 十四、Wave 3 当前落地（2026-03-19）

已完成：

- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_task_source.py`
  - heartbeat 显式任务 / 到期任务 / 治理任务筛选已迁到 Butler 侧 adapter
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_truth.py`
  - heartbeat truth 通过 Butler 侧 adapter 收口到 task ledger
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_scheduler.py`
  - heartbeat fallback 选择、planner normalize 迁到 Butler 侧 adapter
- `butler_main/butler_bot_code/butler_bot/memory_manager.py`
  - heartbeat task source / scheduler / truth 入口已切到 Butler 侧 adapter
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/manager_blueprint.py`
  - 抽出一个并行 manager 的最小启动蓝图
  - 用于验证未来 `research_manager` 能否靠 adapter + prompts + interface 快速搭建

这一步的意义：

- heartbeat 触发链里最 Butler-specific 的三块，已经不再挂在 `agents_os` 或误当 core
- `research_manager` 这类并行主管也已经有了清晰公式：
  - 复用 `agents_os` core
  - 自己维护 adapter
  - 自己维护 prompt 资产
  - 自己维护 interface 壳层
