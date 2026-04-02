# 0319 runtime 概念分层：参考 OpenAI Agents SDK 与 Butler 映射

更新时间：2026-03-19 12:04
时间标签：0319_1204

## 一、目的

本文件用于把 Butler 当前讨论中的几个高频概念收口成一套更稳定的分层语言：

- runtime
- session
- run
- workflow
- worker
- agent
- guardrails
- tracing

本文件参考 OpenAI Agents SDK 的公开概念划分，但不把 Butler 绑定到 OpenAI API 或 OpenAI SDK 实现上。

本轮核心判断是：

> Butler 应把 `runtime` 作为系统本体，把 `run` 作为执行单位，把 `workflow` 作为控制流，把 `worker` 作为执行器，把 `agent` 视为带角色语义的 worker，而不是把 agent 当成整个系统中心。

---

## 二、参考基线：OpenAI Agents SDK 给出的概念启发

从 OpenAI Agents SDK 的公开文档看，它实际上已经给出一套比较清晰的 agent runtime 最小闭环：

- `Agent`
  - 一个带指令、工具、handoff 能力的执行单元
- `Runner` / `run()`
  - 一次受控执行的启动器
- `Session`
  - 跨多轮的连续性容器
- `Context`
  - 不一定直接给模型看的本地运行上下文
- `Result` / `Run state`
  - 一次执行的结果、状态与可恢复信息
- `Guardrails`
  - 输入、输出、工具调用等运行期约束
- `Tracing`
  - 对 agent、tool、handoff、guardrail 的运行期观测

对 Butler 最重要的启发不是“多 agent 很方便”，而是：

1. 系统中心不一定是 agent，而可以是 `run/runtime`。
2. session、context、result、guardrails、tracing 都应视为 runtime 内建能力，而不是 prompt 约定。
3. handoff、agent-as-tool、本地上下文、恢复状态这些概念，适合进入 runtime，而不适合散落在单个 agent 定义里。

但 Butler 也不能直接照搬 OpenAI Agents SDK，因为 Butler 当前目标是：

- 不绑定 OpenAI API
- 继续兼容 `codex`、`claude`、`cursor` 与任意 CLI 执行器
- 在 agent runtime 之外，还要托管任务真源、工作区、产物沉淀与长期恢复

因此，Butler 应采纳的是“概念与边界”，而不是“具体 SDK 接口”。

---

## 三、Butler 推荐概念分层

## 3.1 `runtime`：系统底座 / 宿主层

`runtime` 是 Butler 的运行底座，负责把任务、流程、执行器、上下文、产物、门控和观测组织成一个可运行系统。

它至少应管理：

- run 的创建、推进、结束、恢复
- workflow 的装配与调度
- worker / agent 的注册与调用
- 工具网关、记忆上下文、产物回写
- guardrails 与 tracing
- 心跳、定时器、事件触发、恢复逻辑

一句话：

> runtime 不是某一轮 loop，本质上是 Butler 的“操作系统 + 调度器 + 执行壳层”。

## 3.2 `session`：跨多次执行的连续性容器

`session` 是比单次 run 更长的连续关系容器。

它适合表示：

- 一段连续对话
- 一个长期科研课题
- 一个项目实例的长期推进链路

它的职责是：

- 维持身份与上下文连续性
- 绑定多次 run
- 提供恢复入口与长期关联索引

在 Butler 里，未来 `session` 不应等于聊天线程，也不应等于 task ledger；它更像“某条长期链路的逻辑壳”。

## 3.3 `run`：runtime 中的一次执行单位

`run` 是 runtime 最核心的执行对象。

它表示一次具体执行，例如：

- heartbeat 的一轮推进
- 一次“整理 5 篇论文”的任务执行
- 一次“提交实验并监控日志”的执行

一个 run 通常有：

- 输入
- 当前状态
- 选定 workflow
- 调用的 worker
- 过程事件
- 结果与产物
- 中断点 / 恢复点

一句话：

> `run` 是 Butler 里最接近 OpenAI SDK `run/result/state` 的对象，也是最适合成为 runtime 第一执行单位的对象。

## 3.4 `workflow`：一次 run 的控制流模板

`workflow` 不负责具体干活，而负责定义 run 如何推进。

例如：

- `single_loop`
- `planner_executor`
- `planner_executor_reviewer`
- `manager_worker`
- `pub_sub`
- `human_in_the_loop`

它负责回答：

- 这次 run 分几步
- 先调谁，后调谁
- 失败怎么处理
- 什么时候暂停等待人工
- 什么时候完成

因此：

> workflow 是运行时的控制流，而不是某个 agent 的 prompt 习惯。

## 3.5 `worker`：执行器接口

`worker` 是 runtime 统一调度的执行器。

Butler 的 worker 不应绑定某家模型厂商，而应面向统一接口。

未来典型 worker 可能包括：

- `codex_cli_worker`
- `claude_cli_worker`
- `cursor_cli_worker`
- `shell_worker`
- `python_worker`
- `doc_worker`

它们共同特点是：

- 接收任务输入
- 接收上下文
- 执行动作
- 返回结果、状态、日志与产物引用

一句话：

> worker 是 runtime 的执行器抽象，而不是特指某个 LLM agent。

## 3.6 `agent`：带角色语义的 worker

在 Butler 里，更适合把 `agent` 理解成 worker 的一个特化子类。

agent 与普通 worker 的区别在于：

- 有角色语义
- 有指令 / 风格 / 规则
- 可能带专属工具集
- 可能带领域知识与记忆边界

因此：

- 每个 agent 都可以被视为 worker
- 但不是每个 worker 都需要被包装成 agent

这能避免 Butler 再次回到“所有东西都长成 agent”的结构。

## 3.7 `guardrails`：runtime 的横切约束系统

`guardrails` 不是业务层，也不是 workflow。

它是 runtime 的基础设施，用于处理：

- 高风险动作审批
- 输入 / 输出约束
- 工具调用权限
- 自动 / 人工切换
- token / 时间 / 并发预算
- 升级与写代码权限边界

一句话：

> guardrails 是运行时约束系统，不应主要靠 prompt 记忆或人工提醒维持。

## 3.8 `tracing`：runtime 的横切观测系统

`tracing` 也不是业务层，而是 runtime 的观测基础设施。

它负责：

- 记录 run 的每一步
- 记录 workflow 选择
- 记录 worker 调用
- 记录工具调用与返回
- 记录失败、重试、暂停、恢复
- 为 replay、debug、audit 提供材料

一句话：

> tracing 是 Butler 未来从“能运行”走向“可验证、可治理、可恢复”的关键壳层。

---

## 四、这些概念与 runtime 的关系

如果把关系压缩成一句话：

> runtime 是宿主；session 是连续性；run 是执行单位；workflow 是控制流；worker 是执行器；agent 是带角色语义的 worker；guardrails 与 tracing 是 runtime 的横切基础设施。

可以进一步写成一张关系图：

```text
Runtime
  ├─ Session
  │    └─ Run
  │         ├─ Workflow
  │         │    └─ dispatch Worker / Agent
  │         ├─ Guardrails
  │         ├─ Tracing
  │         ├─ Context / Memory
  │         └─ Artifacts / Events / Result
  └─ Scheduler / Recovery / Policies
```

需要特别强调两点：

1. `workflow` 属于 run 的推进结构，不是 runtime 的替代品。
2. `agent` 属于 worker 语义层，不是 runtime 的替代品。

---

## 五、Butler 当前架构 / 现状映射

以下映射基于 `docs/concepts/当前系统架构_20260314.md` 与 `docs/daily-upgrade/0319/0049_现状分析--项目健康.md`。

## 5.1 当前哪些部分已经接近 runtime

### A. 调度与经理层

当前最接近 runtime 的部分是：

- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`
- `butler_main/butler_bot_code/butler_bot/runtime_router.py`
- `butler_main/butler_bot_code/butler_bot/task_ledger_service.py`
- `butler_main/butler_bot_code/butler_bot/acceptance_service.py`
- `butler_main/butler_bot_code/manager.ps1`

这些模块已经在承担：

- 任务推进
- 运行时选择
- 回执落盘
- 主进程与 sidecar 管理

也就是说，Butler 当前的 runtime 雏形已经存在，只是仍然散落在多个地方，并且混有较多业务语义与历史兼容逻辑。

### B. 执行层

当前最接近 worker 层的是：

- `butler_main/butler_bot_code/butler_bot/cli_runtime.py`
- `butler_main/butler_bot_code/butler_bot/agent_team_executor.py`
- `butler_main/butler_bot_code/butler_bot/agent_capability_registry.py`
- `butler_main/butler_bot_code/butler_bot/prompt_assembly_service.py`

这一层已经在承担：

- CLI 执行器适配
- 团队 agent 执行
- 能力注册
- prompt / capability 装配

这说明 Butler 已经有 worker / agent 执行层的雏形，只是还没有被明确统一抽象成 `worker_adapter`。

### C. 记忆与上下文层

当前最接近 `context / memory service` 的是：

- `butler_main/butler_bot_code/butler_bot/memory_manager.py`
- `butler_main/butler_bot_code/butler_bot/memory_backend.py`
- `butler_main/butler_bot_code/butler_bot/local_memory_index_service.py`
- `butler_main/butle_bot_space/self_mind/`
- `butler_main/butler_bot_agent/agents/recent_memory/`
- `butler_main/butler_bot_agent/agents/local_memory/`

这一层已经承担共享认知底座，但 0319 健康分析也指出：

- 真源仍偏多
- 运行态与知识态仍相邻
- `memory_manager.py` 仍然过重

因此，这一块是 Butler runtime 抽象中最需要继续“从大总控里抽出来”的部分之一。

### D. guardrails 与 tracing 雏形

当前 guardrails 雏形主要散落在：

- `standards/` 与规则文档
- 测试与工程约束
- 自我升级审批链路
- `manager.ps1` 运行边界
- prompt 中的高风险动作约定

当前 tracing / observer 雏形主要散落在：

- `butler_main/butler_bot_code/run/`
- `butler_main/butler_bot_code/logs/`
- `butler_main/butler_bot_code/run/traces/`
- `butler_main/butler_bot_code/watch_stack.ps1`

这说明 Butler 并不是没有 guardrails / tracing，而是它们还没有正式升格成 runtime 的一级部件。

## 5.2 当前哪些部分更接近 interface，而不是 runtime

以下更适合理解为 interface 层：

- `butler_main/butler_bot_code/butler_bot/agent.py`
- `butler_main/butler_bot_code/butler_bot/butler_bot.py`
- `butler_main/butler_bot_code/butler_bot/request_intake_service.py`

这些模块更像：

- 对话入口
- 前台请求接入
- 同步回复与分诊

因此，未来不应再把它们作为系统中心，而应把它们降到 `interfaces/talk/` 一类位置。

## 5.3 当前哪些部分更接近 agent 资产，而不是 runtime

以下更接近 `agent` 资产层：

- `butler_main/butler_bot_agent/bootstrap/`
- `butler_main/butler_bot_agent/agents/`
- `butler_main/butler_bot_agent/skills/`
- `butler_main/butler_bot_agent/rules/`

这一层更适合承载：

- 角色定义
- prompt 真源
- 规则与技能
- 认知资产

而不应继续承担高频运行态与过多 runtime 事实。

---

## 六、Butler 当前最核心的错位

结合上面的映射，Butler 当前最核心的结构问题可以压缩成四条：

1. `runtime` 事实已经存在，但还没有正式命名和收口。
2. `agent` 资产、`runtime` 逻辑、`memory` 真源、`interface` 入口仍然交织。
3. `workflow` 仍有相当部分隐含在 heartbeat 与 prompt 习惯中，还没正式模块化。
4. guardrails 与 tracing 已经存在雏形，但还没有升级为 runtime 的正式一级部件。

这也是为什么 0319 健康分析会得出：

- 边界已被说清，但未完全制度化
- 运行时真相很多，仓库内噪音也很多
- 下一阶段重点应是收口、验证、降噪，而不是继续堆功能

---

## 七、面向 Butler 的推荐目标结构

如果参考 OpenAI Agents SDK 的概念边界，并结合 Butler 自己的 CLI-agnostic 目标，更适合的结构是：

```text
Runtime
  ├─ SessionManager
  ├─ RunManager
  ├─ WorkflowEngine
  ├─ WorkerRegistry / WorkerAdapter
  ├─ ContextService
  ├─ ArtifactStore
  ├─ GuardrailEngine
  ├─ TraceObserver
  ├─ Scheduler / Trigger
  └─ Recovery / Resume

Interfaces
  ├─ Talk
  ├─ Heartbeat
  ├─ CLI
  ├─ Feishu
  └─ API

Agent Assets
  ├─ Bootstrap
  ├─ Agents
  ├─ Skills
  └─ Rules

Domains
  ├─ Research
  ├─ Project
  ├─ Secretary
  └─ Governance
```

这里最关键的一条是：

> `heartbeat` 不是 runtime 本身，而是 runtime 的 trigger / scheduler 入口之一。

---

## 八、对 Butler 下一步最有价值的抽离顺序

如果你接下来准备“先从 Butler runtime 入手，将藏在其他地方的 runtime 与 agent 本身逻辑解耦，搭好 runtime 底架”，我建议顺序如下：

### Step 1：先定义 runtime 对象边界

先明确以下对象及其最小字段：

- `Session`
- `Run`
- `RunResult`
- `Workflow`
- `Worker`
- `GuardrailDecision`
- `TraceEvent`

### Step 2：先从现有代码里抽出 runtime 核心接口

优先抽：

- `run_manager`
- `workflow_engine`
- `worker_adapter`
- `context_service`
- `trace_observer`

### Step 3：再把 `talk` 与 `heartbeat` 降到入口层

目标不是删掉它们，而是把它们重新放回：

- `talk` = interface adapter
- `heartbeat` = scheduler / trigger

### Step 4：最后再让 `research / project` 长在 runtime 之上

也就是说，先有：

- runtime
- worker
- workflow

再有：

- research domain
- project domain

而不是反过来。

---

## 九、一句话总结

参考 OpenAI Agents SDK 后，对 Butler 最有价值的不是“采用 OpenAI agent 体系”，而是：

> 学会把 `run / session / guardrails / tracing / context` 这些对象从 agent 身上剥离出来，提升为 runtime 一级部件；然后再把 Butler 现有的 heartbeat、task ledger、CLI 执行、memory、logs、审批、恢复能力统一收进这套 runtime 底架里。

这条路既能保留 Butler 当前“兼容任意 CLI / 任意厂商”的优势，又能让系统真正从“有架构意识”进入“runtime 边界清晰、对象稳定、可持续扩展”的阶段。

## 十、当前落地决定：在 `butler_main/agents_os/` 抽 Butler 内核

这里需要修正一个定位：

`agents_os` 不是默认“从零另起一套系统”，而是：

> 先完整审视 Butler 当前已有的 `code / agent / space` 三层，找出其中干净、通用、稳定、可复用的 runtime 内核，把它们抽出来、封装好、搬进 `agents_os`；只有当 Butler 现有体系里没有合适部件时，才重新造新的实现。

也就是说：

- `agents_os` 不是旧 runtime 目录的继续堆叠
- `agents_os` 也不是无视 Butler 历史、完全白地重写
- `agents_os` 是 Butler 的 **抽核层 / 收口层 / 新内核承接层**

这一定位更符合 Butler 当前现实，因为：

- `butler_bot_code/` 里已经存在大量 runtime 雏形
- `butler_bot_agent/agents/` 里混有一部分运行时真源与状态资产
- `butle_bot_space/self_mind/` 里也承载了部分运行态和高频状态文件

因此更稳的路线不是“完全推倒重来”，而是：

> 从 Butler 现有系统里抽出可复用内核，沉淀到 `agents_os`；让 `agents_os` 成为 Butler 今后的 runtime 真源，而让 Butler 本体逐步退回到业务与资产层。

## 十一、未来边界：Butler 本体只保留什么

当 `agents_os` 逐步成型后，Butler 本体的目标边界应收敛为：

- 业务域（`research / project / secretary / governance` 等）
- 角色与 prompt 资产
- 接口适配层（talk / heartbeat / cli / feishu / api 等）
- 工作区与产物资产

换句话说：

> 以后 `agents_os` 负责 runtime；Butler 自己只保留：业务域、角色/prompt、接口适配、工作区资产。

这条边界非常关键，因为它决定了：

- 运行时不再继续散落在 `memory_manager`、`heartbeat_orchestration`、`agents/state/`、`self_mind/` 多处
- 业务和人格资产不再反向定义 runtime 结构
- 接口层不再充当系统中心

## 十二、`agents_os` 的设计原则

### 12.1 简洁原则

- 先抽最小必要内核，不预造复杂框架
- 先收口已有干净模块，再补缺失实现
- 一个模块只承载一种职责，不复制旧总控形态

### 12.2 高效原则

- 优先复用 Butler 中已经可用的干净部分
- 只在旧实现明显脏、冗余、耦合过深时才重写
- 先支持最小 `run -> workflow -> worker -> result -> trace` 闭环

### 12.3 必要原则

- 不把历史兼容层、废弃机制、陈旧实验一起搬进新内核
- 不为了未来假想需求提前做重型抽象
- 不把 domain、prompt 资产、space 私有沉淀重新塞回 runtime

### 12.4 抽核原则

每遇到一个旧部件，都先问四个问题：

1. 它是不是 runtime 内核职责
2. 它是不是足够干净、通用、稳定
3. 它是应该直接复用、薄封装，还是应该重写
4. 它迁走后，旧 Butler 是否能明确变薄

只有通过这四个问题，才进入 `agents_os`。

## 十三、`agents_os` 的推荐最小结构

第一阶段仍然保持最小结构，但语义改为“承接抽出的内核”：

```text
butler_main/
  agents_os/
    README.md
    __init__.py
    runtime/
      __init__.py
      contracts.py
      kernel.py
```

其中：

- `contracts.py`
  - 承接被抽象稳定后的运行时对象协议
- `kernel.py`
  - 承接被抽离出来的最小执行内核与必要默认实现

这两个文件当前可以先有少量新实现，但后续重点是持续吸收 Butler 现有系统中真正值得保留的干净内核。

## 十四、`agents_os` 第一阶段只解决什么

第一阶段只解决 5 件事：

1. 建立 `run` 作为第一执行单位
2. 建立 `worker` 作为统一执行器抽象
3. 建立 `workflow` 作为控制流抽象
4. 建立 `trace / artifact / context` 作为 runtime 配套对象
5. 建立“旧 Butler -> 新内核”的抽离判断标准

第一阶段仍然**不解决**：

- 完整 heartbeat 替换
- 完整 memory 替换
- self_mind 重构
- research / project domain 落地
- talk / Feishu / API 接口统一

## 十五、`agents_os` 的详细实施计划

### Phase A：先盘点 Butler 现有可抽内核

盘点范围必须覆盖整个 `butler_main/`：

- `butler_bot_code/`
- `butler_bot_agent/`
- `butle_bot_space/`

重点不是“看哪里最乱”，而是找：

- 干净的
- 通用的
- 可复用的
- 适合脱离业务语义的 runtime 部件

验收：

- 形成一份“可直接复用 / 可薄封装 / 必须重写 / 应直接淘汰”的抽离清单

### Phase B：把抽出的共性先沉到 `contracts + kernel`

优先沉淀：

- 统一运行对象
- 统一 worker 协议
- 统一 workflow 协议
- 最小 trace / artifact / context 壳层

这里允许少量新写，但目的不是另起炉灶，而是给抽出的内核一个稳定落点。

验收：

- `agents_os` 内核能表达旧 Butler 中多个 runtime 事实，而不是只服务一条新 demo 链路

### Phase C：优先接“干净执行器”，再接“脏业务总控”

优先考虑抽 / 封装：

- `cli_runtime`
- `runtime_router` 中可泛化部分
- `task_ledger_service` 中机器真源协议部分
- `heartbeat` 子目录中已经干净的状态 / policy / trace 模型

谨慎处理：

- `memory_manager.py`
- `heartbeat_orchestration.py`
- `self_mind` 运行链路
- 散落在 `agents/state/`、`local_memory/`、`recent_memory/` 的混合真源

原则是：先拿干净的，再包脏的，最后重写最脏的。

### Phase D：让旧 Butler 逐步退回“业务与资产层”

随着 `agents_os` 成型，旧 Butler 逐步只保留：

- domain packs
- agents / bootstrap / skills / rules
- talk / heartbeat / feishu / api 等接口适配
- workspace / reports / notes / artifacts

验收：

- 新增一个业务域时，主要工作发生在 Butler 本体
- 新增一个 runtime 能力时，主要工作发生在 `agents_os`

### Phase E：再迁最短主链路

建议第一条迁移链路仍是：

`heartbeat 单轮任务推进 -> runtime run -> worker -> result/trace`

但这里的前提变成：

- 先用 Butler 现有可用部件组装
- 不够干净的点再补新实现
- 不允许为了迁移一条链路，把旧脏结构整体复制进 `agents_os`

## 十六、对旧系统的处理原则

在 `agents_os` 建设过程中，对旧系统坚持四条：

1. **先判断是否值得抽**
   - 不是所有旧代码都值得迁移
2. **先抽干净通用件**
   - 先拿内核，再碰脏总控
3. **没有就补，有毒就重写**
   - 缺失能力可以新造，脏能力不要硬搬
4. **迁走后旧 Butler 必须变薄**
   - 否则就不算真正抽核成功

## 十七、当前起步动作

当前起步动作应修正为：

1. 先盘点整个 `butler_main/` 里哪些是可抽 runtime 内核
2. 把已确认干净、通配、可复用的部分收口进 `agents_os`
3. 对缺失能力做最小新实现补位
4. 让 Butler 未来逐步只保留：业务域、角色/prompt、接口适配、工作区资产

这意味着 Butler 下一步不是“从零再造一个新系统”，而是：

> 从 Butler 里抽出真正的 runtime 内核，让 `agents_os` 成为新内核承接层。


## 参考资料

- OpenAI Agents SDK guide: https://platform.openai.com/docs/guides/agents-sdk/
- OpenAI Agents SDK Python docs: https://openai.github.io/openai-agents-python/
- Agents: https://openai.github.io/openai-agents-python/agents/
- Sessions: https://openai.github.io/openai-agents-python/sessions/
- Context: https://openai.github.io/openai-agents-python/context/
- Results: https://openai.github.io/openai-agents-python/results/
- Guardrails: https://openai.github.io/openai-agents-python/guardrails/
- Tracing: https://openai.github.io/openai-agents-python/tracing/
