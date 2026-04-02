# 0319 runtime 阶段性总结与后续治理计划

更新时间：2026-03-19 16:48
时间标签：0319_1648

## 一、写这份文档的目的

本文件基于以下两组材料做交叉判断：

1. `docs/daily-upgrade/0319/` 下本轮 runtime 相关文档
2. `BrainStorm/Insights/` 中 Harness Engineering 主线知识与 OpenAI / MAS / Agent Harness 设计启发

目标不是重复 0319 已有结论，而是回答两个更直接的问题：

1. **截至当前，Butler runtime 是否已经具备相对完备的功能与稳定的规范？**
2. **如果还没有，后续 Butler 应如何继续划分与治理，才能真正走向可验证、可扩展、可持续演进的 runtime 系统？**

---

## 二、结论先行

### 2.1 一句话结论

> **Butler runtime 已经具备“边界基本成形、最小闭环可运行、核心抽象已落地”的阶段性成果，但还不能判定为“功能相对完备、规范相对稳定”的成熟 runtime。**

更准确地说，当前状态是：

> **它已经从“散落在 Butler 各处的运行事实”进化成“有独立 core、adapter 边界和最小 kernel 的 runtime 雏形”；但距离一个成熟的 Harness Runtime，还差验证壳层、统一状态机、治理运营层、上下文耐久性和经验飞轮。**

### 2.2 当前应如何定性

如果借用 Harness Engineering 语言，Butler runtime 当前更接近：

- **不是 0 到 1 的混沌期**
- **也不是 1 到 N 的成熟平台期**
- 而是处在 **“1 的骨架已经立住，但还没被验证与治理系统包起来”** 的阶段

所以它现在最适合的判断不是“已经完工”，而是：

> **runtime core 初步收口完成，接下来应从“结构解耦”转向“协议固化 + 验证闭环 + 治理运营”。**

---

## 三、为什么说它已经有了阶段性完成度

这部分说的是：当前 Butler runtime 已经具备哪些真实成果，不能再把它视为“只有想法，没有内核”。

### 3.1 runtime core 已经有了正式落点

现在 `agents_os/` 已经不只是概念目录，而是有明确职责的 runtime core：

- `butler_main/agents_os/runtime/contracts.py`
- `butler_main/agents_os/runtime/kernel.py`
- `butler_main/agents_os/execution/cli_runner.py`
- `butler_main/agents_os/execution/runtime_policy.py`
- `butler_main/agents_os/state/run_state_store.py`
- `butler_main/agents_os/state/trace_store.py`
- `butler_main/agents_os/context/memory_backend.py`
- `butler_main/agents_os/tasking/task_store.py`

这说明 Butler 已经不再把 runtime 仅仅理解为 `heartbeat_orchestration.py` 或某个巨型 manager 文件，而是开始以：

- contracts
- kernel
- execution
- state
- context
- tasking

这些稳定抽象组织运行时能力。

### 3.2 运行边界已经从“口头边界”变成“目录边界”

0319 文档和当前代码都表明：

- `agents_os` 负责 runtime core
- Butler 本体保留业务域、角色资产、接口入口、workspace 与 manager-local adapters
- Butler-specific 承接层已经明确放入 `butler_main/butler_bot_code/butler_bot/agents_os_adapters/`

这一步非常关键，因为它意味着：

1. 后续新 manager 不必复制 Butler 黑洞总控
2. 通用 runtime 不再继续被 Butler 私有路径和历史语义污染
3. 新增能力时可以先判断“进 core 还是进 adapter”，而不是继续堆进大文件

### 3.3 最小 runtime 闭环已经能跑通

从 `agents_os/runtime/kernel.py` 和对应测试看，当前最小闭环已经成立：

- `RunInput`
- `Run`
- `Worker`
- `Workflow`
- `Guardrails`
- `ContextStore`
- `ArtifactStore`
- `TraceObserver`
- `RunResult`

`RuntimeKernel` 已经可以完成：

1. 创建 run
2. 按 workflow 调度 worker
3. 在 dispatch 前做 guardrail inspect
4. 注入 session context
5. 收集 artifacts
6. 记录 trace event
7. 回写上下文更新
8. 返回结构化结果

这意味着 Butler 已经不再只是“通过 prompt 调一个 CLI”，而是拥有了一个最小但真实的 runtime 执行内核。

### 3.4 runtime 的抽核不是停留在文档，而是已经有测试护栏

当前已有至少三组直接相关测试：

- `butler_main/butler_bot_code/tests/test_agents_os_runtime.py`
- `butler_main/butler_bot_code/tests/test_agents_os_wave2_adapters.py`
- `butler_main/butler_bot_code/tests/test_agents_os_wave3_manager_bootstrap.py`

再加上 `0319` 收口文档里提到的目标回归通过，说明这一轮不是纯文档重构，而是：

> **架构收口 + 接线切换 + 测试兜底**

这在 Harness Engineering 视角里，是从“结构感”迈向“工程感”的关键一步。

---

## 四、为什么它还不能被称为“相对完备、规范稳定”的 runtime

这一部分更重要，因为它解释了：为什么当前不能过早宣布 runtime 已经成熟。

### 4.1 `session / run / workflow` 概念已经提出，但还没有全部变成强真源

0319 文档已经明确提出：

- runtime 是系统宿主
- session 是连续性容器
- run 是执行单位
- workflow 是控制流模板

但从当前实现看：

- `session` 还主要是轻量数据结构，而不是强持久化对象
- `workflow` 目前仍偏最小实现，距离多种稳定工作流模板还有差距
- `run state` 还没有形成完整、统一、跨 manager 共识的状态字典
- `run -> result -> artifact -> next step` 的机器可读反馈链还不够强

所以当前的情况更像：

> **概念模型已对，最小代码也已出现，但尚未全部固化为 runtime 的唯一正式语言。**

### 4.2 当前强的是“能跑”，弱的是“能验证”

Harness Engineering 的核心不是只让 agent 跑起来，而是同时做到：

- Correct
- Verify
- Inform
- Constrain

Butler 当前在以下两项上已明显进步：

- `Inform`：文档、工作区、prompt、skills 已经形成较强的信息供给
- `Constrain`：adapter、路径、provider policy、部分审批与权限边界已有雏形

但在另外两项上仍然偏弱：

- `Verify`：缺少统一的 smoke scenarios、场景回放、标准化验收回执、失败分类与 replay 壳层
- `Correct`：缺少循环检测、自动降级、重试策略、质量门控与恢复逻辑的统一 runtime 中间件

换句话说：

> 当前 Butler runtime 更像“可运行的执行内核”，还不是“可验证的 Harness Runtime”。

### 4.3 guardrails 还是初级能力，不是独立成熟层

当前 `RuntimeKernel` 已支持 guardrail inspect，这是正确方向。  
但如果对照 BrainStorm 里的 Harness 四层架构，Butler 目前的 guardrails 仍然更接近：

- 单次 dispatch 前的判断点
- 零散散落在执行前后的约束逻辑

还没有成长为真正独立的风险门控层，例如：

- 统一的权限/预算/审批模型
- 动态 action space 裁剪
- prompt 注入 / 高风险写入 / 外部副作用的策略中间件
- 全 manager 共享的 policy runtime

所以目前 guardrails 是“接口能力”，还不是“治理层能力”。

### 4.4 tracing 还是记录层，不是观察与分析层

当前已有：

- `trace_store`
- run trace file-backed store
- 事件追加与读取能力

这证明 tracing 基础设施已经有了。  
但在 Harness Engineering 里，tracing 的价值不只是“记下来”，而是：

- 看日志
- 抓循环
- 分析失败模式
- 形成回放基准
- 反馈到 action space / prompt / policy 优化

Butler 当前还没有形成这一层闭环，所以 tracing 现在仍以“存储能力”为主，而不是“观察操作系统”。

### 4.5 context / memory 仍然是最大不稳定来源之一

0319 系列文档已经反复指出：

- `memory_manager.py` 仍然很重
- 真源仍偏多
- `recent_memory / local_memory / self_mind` 的边界仍处在过渡期
- 上下文注入更多依赖 prompt 组织，而不是统一的 runtime context policy

如果结合 Harness Engineering 对 **context durability** 的判断，当前 Butler 最大的结构性短板之一就是：

> **runtime 已经开始抽离，但 context durability 还没有同时被抽成一等公民。**

这会直接影响：

1. 长链路任务的稳定性
2. 跨 session 的恢复质量
3. 不同 manager 之间的 context 复用能力
4. context compaction 的可治理性

### 4.6 治理运营层几乎还没真正建立

如果用 BrainStorm 的 MAS Harness 四层看当前 Butler：

- Layer 1 知识供给层：已明显存在
- Layer 2 执行编排层：已进入抽核期
- Layer 3 风险门控层：有雏形，但未成熟
- Layer 4 治理运营层：基本还没系统成形

尤其缺少：

- 任务案例库
- 协调模式库
- 失败模式库
- 运行时仪表盘/巡检视图
- 经验沉淀回灌到 runtime policy 的飞轮

这意味着系统虽然已经不再原始，但还没有进入“越跑越强”的阶段。

---

## 五、当前最准确的阶段判断

如果给当前 runtime 做一个阶段判断，我会这样定性：

### 5.1 已经完成的阶段

#### 阶段 A：runtime 事实识别

已经完成。  
Butler 已经识别出哪些东西属于 runtime，哪些不应该再混进业务与 prompt。

#### 阶段 B：runtime 抽核与边界收口

大体完成。  
`agents_os`、`agents_os_adapters/`、主链切换、旧壳删除，这一轮已经把“结构解耦”做到了一个可以成立的程度。

### 5.2 正在进行的阶段

#### 阶段 C：runtime 协议固化

正在进行，但尚未完成。  
概念已经提出，部分 contracts 已落地，但 `session / run / workflow / result / policy / context` 还没有完全变成跨 manager 的强共识。

### 5.3 尚未真正启动完成的阶段

#### 阶段 D：Harness 化验证壳层

尚未完成。  
当前最缺的是：

- 结构化回执
- 场景回放
- 自动验收
- 循环检测
- 失败模式沉淀
- 可重复 benchmark

#### 阶段 E：治理运营层与经验飞轮

尚未完成。  
当前 Butler 还没有把 tracing / failures / cases / pattern 真正组织成可复用资产库。

---

## 六、后续 Butler 应如何继续划分

接下来 Butler 不应再按“模块多少”扩张，而应按 **层次职责** 继续收口。

### 6.1 推荐固定为五层结构

#### 第一层：`agents_os` runtime core

只放：

- run/session/workflow/worker contracts
- runtime kernel
- generic execution
- generic state / trace / artifact
- generic context / memory protocol
- generic task store protocol
- generic guardrail / policy runtime

这一层不放：

- Butler 私有路径
- Butler 任务 schema 细节
- Butler prompt / role / workspace 习惯

#### 第二层：manager domain layer

每个 manager 各自一层，例如：

- Butler manager
- research_manager
- ops_manager

这一层负责：

- 业务语义
- manager-specific orchestration
- 角色协作与产物定义
- domain-specific acceptance logic

这一层不再发明新的 runtime。

#### 第三层：manager-local adapters

例如 Butler 的：

- `task_ledger_store.py`
- `runtime_policy.py`
- `heartbeat_truth.py`
- `heartbeat_scheduler.py`
- `heartbeat_runtime_state.py`
- `heartbeat_run_trace.py`

它们只负责把 manager 自己的历史真源和路径约定映射到 `agents_os` contract。  
以后任何 manager 新增长的兼容层都应该放在这一层，而不是回流 runtime core。

#### 第四层：workspace / artifact layer

这一层应明确独立出来，统一承载：

- task workspace
- artifacts
- reports
- local memory / self_mind 等私有沉淀
- logs / traces / snapshots / run states

关键原则是：

> **运行副产物、私有认知资产、正式源码资产，不应继续彼此渗透。**

#### 第五层：governance / harness ops layer

这是 Butler 现在最缺的一层，后续必须补上。  
它负责：

- 场景库
- 回放基准
- 失败模式库
- 协调模式库
- 观测指标
- 熵增治理
- 文档真源维护

这一层本质上不是业务，也不是 runtime 内核，而是：

> **让系统可持续变强的运营壳层。**

---

## 七、后续 Butler 应如何继续治理

### 7.1 治理总纲

后续治理不应再以“再拆一个大文件”为主线，而应变成下面三件事：

1. **把 runtime 的正式语言定死**
2. **把 harness 的验证闭环补齐**
3. **把经验资产沉淀成治理飞轮**

### 7.2 具体治理原则

#### 原则 1：一类运行事实只认一个 machine-readable 真源

至少应继续统一：

- run state
- task truth
- trace event
- acceptance result
- artifact manifest
- context snapshot

不要让“人类能看懂的 markdown”继续承担 machine truth 角色。

#### 原则 2：业务流程和 runtime 基础设施彻底分开

- “怎么调 worker / 记录 trace / 管 run state” 属于 runtime
- “科研任务分几阶段、Butler 心跳怎么取任务” 属于 domain / manager

后续任何新增逻辑，都先判断是 **runtime concern** 还是 **manager concern**。

#### 原则 3：新能力优先进入 contract / adapter / skill，而不是回到黑洞总控

如果以后新增：

- 新 provider
- 新 manager
- 新 approval policy
- 新 task source
- 新 trace backend

优先落在：

- `agents_os` contract
- manager-local adapter
- skill / docs / config

而不是继续写进 `memory_manager.py` 或新的超级 orchestrator。

#### 原则 4：验证机制与执行机制并列建设

每补一个执行能力，都应同时问：

- 它怎么被验证？
- 它怎么被 replay？
- 它失败后怎么分类？
- 它如何触发自动降级？

否则系统会继续增长，但验证壳层永远补不齐。

---

## 八、建议的后续计划：Runtime Wave 4 ~ Wave 6

为了避免计划过散，后续更适合按三波推进。

## 8.1 Wave 4：Runtime 协议固化

目标：**把“概念正确”升级为“正式协议正确”。**

### 本波要做什么

1. 固化 `session / run / workflow / worker / artifact / trace / acceptance` 的正式 schema
2. 定义统一 run state 字典，例如：`pending / running / blocked / failed / completed / stale / cancelled`
3. 让 `run result` 默认带结构化字段，而不只是文本结论
4. 为 manager blueprint 增加更明确的 contract 校验
5. 明确哪些 state 属于 runtime，哪些属于 manager-local view

### 本波完成标志

- 新 manager 可只靠 contract + adapter 启动
- `run` 生命周期在代码、trace、文档里使用同一套状态语言
- 主链中不再出现新的临时状态命名

## 8.2 Wave 5：Harness 验证壳层建设

目标：**让 runtime 不只是能跑，而是能系统验证。**

### 本波要做什么

1. 设计结构化回执 schema
   - `goal_achieved`
   - `evidence`
   - `artifacts`
   - `uncertainties`
   - `next_action`
2. 建立标准 smoke scenarios
   - talk
   - heartbeat
   - restart / recovery
   - task dispatch
   - memory read/write
3. 建立 trace replay / regression baseline
4. 加入 loop detection 与自动降级机制
5. 将 acceptance 与 failure class 纳入统一回执

### 本波完成标志

- 每个关键场景都有可重复跑的 baseline
- 失败能进入统一 failure taxonomy
- trace 不只是存下来，而能被回放和分析

## 8.3 Wave 6：Governance 与经验飞轮

目标：**让 Butler 从“持续改”变成“越跑越强”。**

### 本波要做什么

1. 建任务案例库、协调模式库、失败模式库
2. 建 context durability 治理机制
   - freshness scoring
   - compaction policy
   - cross-session persistence
3. 建动态 action space
   - 根据任务类型裁剪工具与 skill 空间
4. 建 entropy governance
   - 工作区清理策略
   - traces/logs 保留策略
   - 过时文档归档策略
5. 建 manager / runtime 观测面板或巡检报告

### 本波完成标志

- 新任务可复用历史路径而不是从零摸索
- 长链路 context 不再主要靠人工救火
- runtime 调优开始基于案例与数据，而不是凭感觉

---

## 九、最值得优先推进的 10 个动作

如果只看优先级，我建议下一阶段优先做下面 10 项：

1. **固化 run state 字典**
2. **定义结构化执行回执 schema**
3. **把 acceptance result 纳入 runtime 正式产物**
4. **补 session 持久化与恢复协议**
5. **建立标准 smoke scenario 集**
6. **给 trace 增加 replay 与 failure 分类能力**
7. **在 runtime policy 前增加动态 action space 裁剪**
8. **给 memory / context 建 freshness 与 compaction 策略**
9. **建立案例库 / 失败模式库**
10. **继续清空 `memory_manager.py` 的 runtime 残留职责**

这 10 项里，真正最关键的不是“再拆文件”，而是：

> **把 run、trace、acceptance、context 这四个横切要素，从零散能力提升为一套正式 runtime 语言。**

---

## 十、最终判断

回到最开始的问题：

### 10.1 runtime 到如今是否已经具备了相对完备的功能和稳定的规范？

我的判断是：

**还没有完全达到。**

但它已经：

- 具备了较清晰的 core / adapter 边界
- 具备了最小 kernel 与 dispatch 闭环
- 具备了继续扩展为多 manager runtime 的结构基础
- 具备了从“系统解耦”转入“harness 化治理”的资格

所以更准确的表述是：

> **Butler runtime 已经具备“相对成型的骨架与正确的演进方向”，但还没有具备“相对完备的功能与稳定的治理规范”。**

### 10.2 Butler 接下来最该做什么

不是再发明一层新概念，也不是回去堆更大的 orchestrator。  
而是把当前已经抽出来的 runtime，继续推进到三件事：

1. **协议固化**
2. **验证闭环**
3. **治理飞轮**

当这三件事建立起来以后，Butler 才能真正从“正在变强的个人系统”进入“可持续演进的 Harness Runtime 系统”。

---

## 主题标签

`#Runtime` `#HarnessEngineering` `#AgentsOS` `#Butler治理` `#RunState` `#TraceReplay` `#ContextDurability` `#经验飞轮`
