---
type: "note"
---
# 外部多 Agent 框架调研与 Butler 长期架构规划（2026-03-23）

状态：现役  
类型：长期架构规划  
最后核对日期：2026-03-26  
当前替代入口：与 `docs/daily-upgrade/0326/04_稳定Harness之后的下一阶段主线_Anthropic长运行Harness吸收版.md` 配套阅读  
是否允许作为改动依据：是，用于长期方向裁决，不直接替代当前功能索引

## 1. 文档目的

本文件用于把最近对外部多 Agent / Agentic Workflow / AI 软件开发平台项目的调研，收口为 Butler 的长期目标与架构规划。

这份文档不追求给出一轮就能全部实现的方案，而是回答三个更关键的问题：

1. Butler 未来到底要成为什么系统。

2. 外部框架里哪些经验值得吸收，哪些不该照搬。

3. 从当前 `agents_os + multi_agents_os + orchestrator` 现状出发，长期应如何演化。

***

## 2. 当前判断

### 2.1 对 Butler 当前状态的重新定位

结合仓库现状，当前 Butler 更准确的定位不是“已经具备通用多 Agent 运行时”，而是：

* 已经有 `mission / node / branch` 的编排账本雏形。

* 已经有 `workflow session / shared state / artifact registry` 的协作容器雏形。

* 已经有 `instance / checkpoint / workflow cursor / receipts` 的运行时协议雏形。

* 但还没有一个真正通用、可解释执行复杂协作图的 `workflow VM / team engine`。

换句话说，当前 Butler 已经从“单 Agent prompt 系统”迈向“多 Agent 系统骨架”，但仍处在：

**编排与状态模型先行，执行语义尚未完全落地** 的阶段。

### 2.2 当前最重要的缺口

当前距离“可持续吸收外部框架，并稳定执行复杂协作流”的关键缺口主要在六个方面：

1. 缺统一 `Workflow IR`，目前更多还是 mission/node/runtime_plan/open dict。

2. 缺真正的多步执行引擎，`ExecutionRuntime` 仍以 placeholder 为主。

3. 缺 typed collaboration substrate，当前 shared state / artifact 已有，但 mailbox / ownership / join contract 还没有。

4. 缺动态调度语义，现在主要是 ready -> dispatch，而不是 capability / budget / failure-aware scheduling。

5. 缺 verification / approval / recovery 的第一类执行语义，当前更多是字段和协议占位。

6. 缺 framework compiler，外部方法论还不能先编译成 Butler 内部统一语法再执行。

***

## 3. 本轮外部调研范围

本轮重点调研了三类项目。

### 3.1 软件工厂 / 开发流项目

* `gstack`

* `Superpowers`

* `OpenHands`

### 3.2 多 Agent 团队 / 协作框架

* `AutoGen`

* `CrewAI`

* `MetaGPT`

### 3.3 Agent OS / Autonomous Runtime 项目

* `OpenFang`

### 3.4 Workflow Runtime / Durable Execution 思路

* `LangGraph`

* `OpenAI Agents SDK`

* `Temporal`

调研目标不是“找一个照抄对象”，而是拆解这些项目分别在哪一层做对了事情：

* 软件工厂层

* 团队协作抽象层

* workflow runtime 层

* durable execution 层

* 产品化交付层

***

## 4. 外部项目带来的核心启发

## 4.1 gstack：软件工厂不是一堆 Agent，而是一套工程节奏

`gstack` 最有价值的地方，不是它有多少个 skill，而是它把开发节奏显式化了：

* `Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect`

* skill 有顺序、有衔接、有上游产物和下游消费关系

* review / qa / canary / deploy 都是第一类能力，而不是“做完代码后顺手看看”

对 Butler 的启发：

* Butler 不能只做“会分工的 agent team”。

* Butler 需要把开发节奏本身建模成 workflow，而不是只建模角色。

* `review / verify / release / observe` 必须进入主流程，而不是变成附属工具。

对 Butler 不应照搬的部分：

* `gstack` 强依赖 skill host、浏览器 daemon、slash command 交互习惯。

* Butler 不应把长期架构绑定到某个宿主或某种命令式交互协议上。

## 4.2 Superpowers：真正重要的是 hard gate，而不是 skill 目录

`Superpowers` 的强项在于它把 spec-first / plan-first / TDD / review-before-merge 等规则做成了 hard gate。

关键启发：

* “先 brainstorm 再 design approval 再 writing-plans 再 implementation” 是执行语义，不只是建议。

* subagent-driven-development 的重点不是“多开几个 agent”，而是：

  * fresh subagent per task

  * spec compliance review

  * code quality review

  * user review gate

对 Butler 的启发：

* verification、approval、acceptance 不应该只是 receipt 字段，而应该是 workflow VM 的停机点和过闸点。

* Butler 以后吸收外部开发方法论时，应该优先吸收 hard gate，而不是 prompt 风格。

## 4.3 OpenHands：产品化平台一定会分化为 SDK / CLI / GUI / Cloud

`OpenHands` 给出的经验不是“多 agent 编排”，而是一个 AI 软件工程平台最后会自然分裂出多个面：

* SDK

* CLI

* Local GUI

* Cloud / Enterprise

它提示了一个很重要的长期边界：

* 内核必须是 SDK / runtime-first。

* CLI、GUI、Cloud 都只能是上层入口，不应反向绑死内核。

对 Butler 的启发：

* `agents_os` 应该承担长期 runtime core 的职责。

* 飞书、talk、background automation、future GUI、future dashboard 都是入口层，而不是系统真源。

## 4.4 AutoGen：消息传递、事件驱动、分层 API 是对的

`AutoGen` 的启发主要在体系分层：

* Core API

* 更高层的 AgentChat API

* Extensions API

* Studio / Bench 等开发工具

其价值不在于具体 group chat 样式，而在于：

* 先有 core runtime primitives

* 再有更 opinionated 的高层抽象

* 再有 tooling 和 studio

对 Butler 的启发：

* `agents_os`、`orchestrator`、`multi_agents_os` 不应彼此竞争，而应形成：

  * core runtime

  * collaboration substrate

  * mission/orchestration plane

  * tooling / product entry

## 4.5 CrewAI：Crew 与 Flow 分层值得借鉴，但不要只停在角色协作

`CrewAI` 一个很有价值的结构是：

* `Crews` 偏自治协作

* `Flows` 偏事件驱动和精确控制

这说明：

* team abstraction 本身不够

* 还需要更底层的 flow / event / state 机制

对 Butler 的启发：

* Butler 未来也需要同时支持：

  * `team-like autonomy`

  * `flow-like precision`

* 但 Butler 不应只做“role-playing team framework”，否则很容易停在 prompt 编排层。

## 4.6 MetaGPT：角色化软件公司很有启发，但 SOP 必须内核化

`MetaGPT` 的核心思想是：

* 把软件公司角色显式化

* 用 SOP 组织跨角色协作

这对 Butler 的启发很大：

* 吸收外部框架时，真正应该沉淀的是 SOP / Protocol / Contract。

* “角色名很多”本身没有价值。

* 真正有价值的是：每个角色何时触发、输入是什么、输出是什么、如何交接、谁负责验收。

对 Butler 的提醒：

* 不要把 Butler 变成“角色博物馆”。

* 角色必须和 capability、artifact、handoff 契约绑定。

## 4.7 LangGraph：真正缺的是 graph execution semantics

`LangGraph` 最值得借鉴的不是“图”本身，而是它把下面这些能力视为底层基础设施：

* durable execution

* pause / resume

* loops and branching

* human-in-the-loop

* state persistence

* memory

这恰好对应 Butler 当前最缺的一层：

**workflow VM / graph execution semantics**

对 Butler 的启发：

* 不是把 `workflow_template.steps[]` 再写得更复杂就够了。

* 必须有一个真正的执行内核来解释：

  * step

  * edge

  * condition

  * interrupt

  * resume

  * retry

  * join

## 4.8 OpenAI Agents SDK：handoff / guardrails / tracing 必须是第一类对象

`OpenAI Agents SDK` 在抽象上很简洁，但抓住了几个特别关键的第一类对象：

* agents

* handoffs

* guardrails

* sessions

* tracing

对 Butler 的启发：

* handoff 不能只是文本说明，应该是结构化 receipt。

* guardrail 不能只是口头规则，应该影响执行路径。

* tracing 不能只是日志，而是调试和优化入口。

这和 Butler 当前已经有的 `DecisionReceipt / HandoffReceipt / WorkflowCursor / RuntimeHost checkpoint` 方向是一致的，说明方向是对的，但执行层还要补满。

## 4.9 Temporal：Durable Execution 的工程纪律值得借鉴

`Temporal` 不是 agent 框架，但它对 Butler 的启发很直接：

* long-running workflow 不能靠“最好别挂”

* 必须靠 durable execution

* 状态恢复、重试、补偿、重放语义必须是系统内建能力

对 Butler 的启发：

* 如果 Butler 真想长期跑复杂多 Agent 流，就不能把恢复停在“有个 checkpoint 文件”。

* 必须定义：

  * step-level replay

  * branch-level replay

* workflow-level replay

* what is deterministic

* what is side-effecting

## 4.10 OpenFang：最值得吸收的是 Agent OS 化，而不是照搬一套大外壳

`OpenFang` 的最大价值，不在于它又做了一种多 Agent workflow 语法，而在于它非常明确地把自己定义为：

**The Agent Operating System**

从公开文档和仓库结构看，它真正强的地方主要有四个：

1. 把 runtime 当成 OS 来做，而不是把 orchestrator 当成一个大 prompt。

2. 把 scheduler、supervisor、background automation、RBAC、metering、trigger、background executor 做成第一类内核子系统。

3. 提出 `Hands` 这类自治能力包，把“agent”升级为“可安装、可调度、可治理、可交付的 autonomous capability package”。

4. 很强调安全与产品化边界，包括：

   * WASM sandbox

   * 审批闸门

   * 审计链

   * CLI / API / Desktop / channel 分层

对 Butler 的启发主要有三层。

第一，Butler 必须继续坚定走 runtime-first，而不是回到“让一个 orchestrator agent 管所有事”的路线。

第二，Butler 以后吸收外部框架时，不应该只沉淀成 prompt 模板，还应该沉淀成：

* workflow 模板

* capability package

* governance policy

* runtime contract

第三，Butler 长期不只是 `Multi-Agent OS`，还应该是：

**Framework Compiler + Collaboration OS + Agent Runtime OS**

也就是说，Butler 不仅要让 agent 跑起来，还要让外部分工方法论、开发流、team protocol 都能先被编译成 Butler 自己的协作语言，再进入统一 runtime。

但 OpenFang 也有几处不适合 Butler 直接照搬：

1. 不应把“orchestrator 自身也是一个聊天 agent”作为 Butler 的终局控制面抽象。

2. 不应过早扩成“大而全产品壳层”并反向绑定内核。

3. 不应把 `Hands` 原样复制成 Butler 概念，而应抽象成更通用的 `capability package / team package / workflow package`。

4. 不应因为它强调 autonomous agents，就弱化 Butler 当前已经领先的 `mission / workflow / session / receipt / checkpoint` 这些可编排、可恢复、可治理的结构化设计。

所以对 Butler 来说，OpenFang 最应该吸收的是：

* OS 化 runtime 视角

* 自治能力包思路

* 安全治理一等公民化

* 内核与入口解耦的产品纪律

而 Butler 需要保留并继续强化的独立优势是：

* 用 `Workflow IR` 统一吸收外部框架

* 用 `Mission Plane + Workflow VM + Collaboration Substrate` 分层，而不是把一切折叠成一个超级 agent

* 用 receipt、artifact contract、approval / verification / recovery 语义，把多 Agent 协作提升到可解释执行层

* 用 framework catalog / compiler，把外部方法论变成 Butler 原生能力，而不是兼容壳

***

## 5. 调研后对 Butler 长期目标的重新定义

## 5.1 不再使用“支持任意形式多 Agent 协作流”作为口号

“任意形式”这个表述太宽，也容易让架构失去边界。

更好的长期目标表述应该是：

**Butler 要成为一个 framework-native、runtime-first 的 Multi-Agent OS。**

它可以把外部方法论、团队分工和开发流，统一编译成 Butler 自己的协作语法与运行时，再稳定执行、观测、恢复和治理。

更进一步说，Butler 的目标不应只停在 “Agent OS”，而应明确为：

**Framework-Native Agent OS + Collaboration OS**

其中：

* `Agent OS` 解决 agent、runtime、capability、safety、scheduling、durability 的问题。

* `Collaboration OS` 解决 team protocol、handoff contract、artifact routing、approval/verification gate、跨角色协作状态机的问题。

* `Framework-Native` 解决外部开发流和方法论如何被持续吸收、编译、治理的问题。

## 5.2 长期目标的核心特征

长期目标至少包含以下能力：

1. 外部框架可吸收，而不是只能手工复刻。

2. 协作流可编译，而不是只能靠 prompt 串起来。

3. 执行可恢复，而不是失败后从头人工接。

4. 状态可治理，而不是到处散落 metadata。

5. 入口可多样，而不是被某个 CLI / chat 宿主绑死。

## 5.3 保持 Butler 独立路线的原则

吸收外部项目经验时，Butler 必须坚持三个原则：

1. 先吸收架构思想，再决定 Butler 内部对象模型，不复刻外部术语表。

2. 先维护 Butler 现有的 `mission / workflow / session / receipt / artifact` 真源体系，再决定兼容层长什么样。

3. 先做统一编译与统一执行，再考虑“是否对外提供某种框架风格接口”。

这意味着：

* Butler 可以借鉴 `OpenFang` 的 Agent OS 化视角。

* 但 Butler 不会退化成 `OpenFang` 风格的壳层复制品。

* Butler 会继续保留自己的先进设计起点：用统一 IR、统一 receipt、统一 runtime contract 来承载不同框架和不同 team 流。

***

## 6. 目标架构

建议把 Butler 的长期架构固定为六层。

## 6.1 Package / Framework Definition Plane

职责：

* 外部框架画像

* 方法论索引

* framework profile / mapping spec 管理

* role / phase / SOP / protocol / guardrail 定义

* capability package / workflow package / governance policy package 定义

* artifact contract 模板

* 适用场景与限制记录

长期对象：

* `framework_catalog`

* `framework_profile`

* `framework_mapping_spec`

* `capability_package`

* `workflow_package`

* `governance_policy_package`

这层解决：

**系统知道哪些框架、哪些包、哪些规则。**

记忆归位：

* 这层承接的是定义型记忆 / 冷知识。

* 它是静态的、可编译的、可复用的，不属于某次运行态实例。

## 6.2 Mission / Control Plane

职责：

* mission intake

* node / branch 组织

* 选择 framework / package / template

* 触发编译

* 下发执行

* 跟踪整体进度

* 回写 mission / branch / node 状态

这层解决：

**这次要做什么、如何组织、如何回到任务账本。**

记忆归位：

* 这层承接的是 mission 级控制记忆。

* 包括 mission ledger、node / branch 状态、预算、阶段推进记录。

## 6.3 Workflow Compile Plane

这是 Butler 长期最关键的一层。

职责：

* 把外部框架、Butler 原生流、research 流、开发流、治理流统一编译为 Butler 内部运行对象

* 生成 Workflow IR

* 生成 Collaboration Contract

* 生成 runtime binding

* 插入 review / verify / approval / recovery 节点

* 根据风险、预算、宿主能力裁剪 workflow

建议 IR 最少包含：

* `workflow_id`

* `workflow_kind`

* `intent`

* `roles`

* `steps`

* `edges`

* `entry_contract`

* `exit_contract`

* `artifacts`

* `handoff_rules`

* `verification_rules`

* `approval_rules`

* `failure_policy`

* `parallelism_policy`

* `resource_policy`

这层解决：

**外部方法论和任务意图，如何被翻译成 Butler 可运行对象。**

记忆归位：

* 这层承接的是编译态记忆。

* 包括 IR 中间产物、binding 决策、模板展开结果、裁剪记录。

## 6.4 Execution Kernel Plane

这是 Butler 当前最缺的一层，也是未来必须重点建设的一层。

职责：

* workflow VM

* step execution

* cursor advancement

* checkpoint / resume

* retry / repair / recovery

* approval gate / verification gate

* runtime binding 解析

* capability runtime 装载

* 工具执行与 side-effect boundary 控制

必须原生支持：

* serial

* parallel fan-out

* join / barrier

* conditional branch

* loop / retry

* repair path

* approval gate

* verification gate

* dynamic expansion

* partial completion

* replay / resume

这层解决：

**这个 workflow 具体怎么跑、怎么停、怎么恢复。**

记忆归位：

* 这层承接的是执行短期记忆 / working memory。

* 包括 step 输入、局部上下文、临时结果、运行中间态。

## 6.5 Collaboration State Plane

职责：

* typed shared state

* artifact registry

* mailbox / inbox / outbox

* blackboard

* ownership / claim 机制

* session event log

* workflow-scoped memory

这层解决：

**多 agent 在运行时如何共享上下文、交接产物、声明所有权并维持协作状态。**

记忆归位：

* 这层承接的是协作共享记忆 / collaboration memory。

* 它属于 workflow / session / team，而不属于某个 agent 私有上下文。

## 6.6 Governance / Observability Plane

职责：

* approval

* verification

* acceptance

* tracing

* metrics

* audit

* policy enforcement

* experience record / postmortem

补充说明：

* `recovery` 的执行动作主要落在 `Execution Kernel Plane`。

* `recovery` 的治理规则、授权边界、审计记录落在本层。

这层解决：

**系统如何可控、可查、可复盘、可持续调优。**

记忆归位：

* 这层承接的是治理记忆 / 审计记忆 / 经验记忆。

* 包括 approval record、verification record、trace、audit、acceptance、postmortem。

### 6.7 关于 memory 的统一约束

Butler 不单独再抽一层 `Memory Plane`。

不同层次的 memory 归不同层管理：

* 定义型记忆归 `Package / Framework Definition Plane`

* mission 控制记忆归 `Mission / Control Plane`

* 编译态记忆归 `Workflow Compile Plane`

* 执行短期记忆归 `Execution Kernel Plane`

* 协作共享记忆归 `Collaboration State Plane`

* 治理与审计记忆归 `Governance / Observability Plane`

这比额外抽一个大而泛的 `Memory Plane` 更适合 Butler，因为它能避免把静态知识、任务账本、执行上下文、协作状态、审计经验混在一起。

### 6.8 关于 skill / capability 的长期维护原则

在 Butler 的六层体系里，`skill` 不应再被理解为“运行时直接执行对象”，而应固定为：

**定义层静态资产 / package asset**

更具体地说：

1. `skill` 的真源归 `Package / Framework Definition Plane`

2. `skill` 首先是方法包、能力说明、tool 组合定义、输入输出约束、风险与策略声明

3. `skill` 不直接等于 `agents_os` 里的运行时 capability

长期建议固定如下二段式链路：

`skill/package definition`\
-> `compile in Workflow Compile Plane`\
-> `CapabilityPackage / CapabilityBinding`\
-> `Execution Kernel Plane` 消费

也就是说：

* 定义层维护的是 `skill/package`

* 编译层生成的是 `capability/binding`

* 执行层真正执行的是 `capability invocation`

而不是：

`agents_os` 直接扫描 `SKILL.md`\
-> 直接把 skill 当执行对象\
-> 再由 chat prompt 拼接出 shortlist

### skill 的长期维护口径

`skill` 进入长期架构后，应优先按“静态定义资产”维护，而不是按“prompt 文本碎片”维护。

建议长期至少具备以下字段：

* `package_id`

* `name`

* `version`

* `kind`

* `description`

* `entry_contract`

* `expected_outputs`

* `required_tools`

* `required_policies`

* `risk_level`

* `executor_ref`

* `host_kind`

* `tags`

* `applicable_scenarios`

### 六层中的具体归位

1. `Package / Framework Definition Plane`

   * 维护 `skill/package` 真源

2. `Mission / Control Plane`

   * 选择这次任务使用哪类 package / capability

3. `Workflow Compile Plane`

   * 把 skill/package 编译成 `CapabilityPackage / CapabilityBinding`

4. `Execution Kernel Plane`

   * 执行 capability invocation

5. `Collaboration State Plane`

   * 让多个 capability/agent 在 workflow 中共享产物与状态

6. `Governance / Observability Plane`

   * 对 skill/capability 的 policy、approval、trace、receipt 做治理

### 对 chat 与 agents_os 的直接约束

因此长期边界应固定为：

* `chat` 可以展示 skill/capability，但不拥有其真源

* `agents_os` 可以执行 capability，但不直接维护 skill 真源

* skill 真源长期应从 prompt 注入物升级为正式 package 资产

这条原则对后续迁移非常关键，因为它能避免 Butler 再次把：

* skill 定义

* prompt 展示

* runtime invocation

三件不同层次的事情混写在同一个目录和同一组对象里。

***

## 7. 对现有模块的长期角色重定义

## 7.1 `agents_os`

长期角色：

**Runtime Core**

应该重点承接：

* instance

* run

* workflow VM

* checkpoint / resume

* receipts

* governance

* recovery

不应继续停留在“协议层和占位运行时”。

## 7.2 `orchestrator`

长期角色：

**Mission Plane / Portfolio Plane**

应该重点承接：

* mission intake

* node graph

* branch budget

* cross-workflow orchestration

* observation window

* dispatch policy

它更像上层任务组织面，而不是底层 workflow VM。

## 7.3 `multi_agents_os`

长期角色：

**Collaboration Substrate 子模块**

应重点承接：

* workflow session

* role binding

* shared state

* artifact registry

* event log

* mailbox / ownership / blackboard

不建议把它继续长成第二套“平行运行时”。

## 7.4 `agent_team_executor`

长期角色：

**兼容层 / fallback team adapter**

它当前的价值在于：

* 快速把本地 subagent/team 定义跑起来

* 为上层提供临时团队执行能力

但长期不应作为核心 team engine，因为它本质上仍偏 prompt fan-out 与文本汇总。

***

## 7.5 一组更准确的系统认知类比

为了避免后续讨论中把 `orchestrator`、`agents_os`、`multi_agents_os` 的职责混掉，可以先固定一组简化类比。

### 可以接受的粗类比

* 外部框架冷知识 / framework catalog / mapping spec / package 定义

  * 更接近“硬盘上的静态数据”

* `multi_agents_os`

  * 更接近“运行中的共享内存 / 协作内存”

* `orchestrator`

  * 更接近“调度控制器 / control plane”

* `agents_os`

  * 更接近“CPU + 执行内核 / workflow runtime”

### 这组类比背后的真实职责

#### 外部框架冷知识不是运行态实例

所谓“冷知识”，更准确地说是：

* framework profile

* SOP / protocol

* roles / phases

* guardrails

* package 定义

* mapping spec

它们首先应留在 `Framework Knowledge Plane`，作为可查询、可编译、可复用的静态对象存在，而不是一上来就生成一个“运行中的多 Agent 框架实例”。

#### `multi_agents_os` 不是执行器，而是协作底座

`multi_agents_os` 长期更适合承接：

* shared state

* artifact registry

* mailbox

* ownership

* blackboard

* workflow-scoped memory

* collaboration session

也就是说，它解决的是：

**多 agent 在运行时如何共享上下文、交接产物、声明所有权、持续保持协作状态。**

它更像“协作内存与协作状态层”，而不是最终负责逐步执行 workflow 的处理器。

#### `orchestrator` 不是超级 agent，也不是 workflow CPU

`orchestrator` 长期角色仍然应该是：

**Mission Plane / Control Plane**

它主要负责：

* mission intake

* node / branch 组织

* 选择 framework profile 或 workflow template

* 触发编译

* 下发执行

* 观察状态

* 回写 mission / branch / node 状态

换句话说，`orchestrator` 决定：

**这次该跑什么、由谁来跑、结果如何进入上层任务账本。**

但它不应成为：

* 超级聊天 agent

* workflow 逐步解释器

* collaboration substrate 的替代物

#### `agents_os` 才是最接近执行内核的一层

长期看，真正承接以下职责的应该是 `agents_os`：

* workflow VM

* cursor advancement

* checkpoint / resume

* step execution

* retry / repair / recovery

* approval gate / verification gate

* runtime binding

* durable execution

也就是说，真正让系统进入“保持运行态”的不是 `orchestrator` 单独完成的，而是：

`orchestrator` 负责控制面，`agents_os` 负责执行面，`multi_agents_os` 负责协作状态面。

### 推荐记忆的一句话版本

如果要用最简短的话来记：

**框架冷知识像硬盘，**`multi_agents_os`**&#x20;像协作内存，**`agents_os`**&#x20;像执行内核，**`orchestrator`**&#x20;像调度控制器。**

这组认知比“`orchestrator` 是处理器、`multi_agents_os` 是内存”更完整，因为它把 Butler 长期最关键的 `agents_os` 执行层单独保留了出来。

### 对应到 Butler 的真实运行链路

建议固定为如下理解：

`Framework Knowledge / Cold Data`\
-> `Framework Catalog / Mapping Spec`\
-> `Compile to Butler Workflow IR + Collaboration Contract + Package Refs`\
-> `orchestrator` 负责 mission/control plane 选择与派发\
-> `agents_os` 负责 workflow 执行与恢复\
-> `multi_agents_os` 负责协作状态、共享上下文与 artifact 路由\
-> 回写 receipts / checkpoints / artifacts / mission state

这个链路比“框架 -> multi_agents_os 组装 -> orchestrator 运行”更准确，也更符合 Butler 的长期目标。

### 关于“合龙”的长期原则

Butler 的长期推进，不应理解为“每个 worker 最后都彼此直接合龙”。

更准确的原则应固定为：

1. 下层先形成稳定 contract，再逐层上交给上一层消费。

2. 不要求 `chat`、`orchestrator`、`multi_agents_os`、`agents_os`、`research` 彼此全部直接互调。

3. 最终用户可见的产品验收，应由最上层控制面与入口面承接。

也就是说：

* `agents_os` 主要向上提供执行能力与运行时 contract

* `multi_agents_os` 主要向上提供协作状态 contract

* `research` 主要向上提供场景解释与结构化产物

* `orchestrator` 负责把这些能力组织成可被验收的任务主线

* `chat` 负责把最终结果交付给用户

因此，Butler 的“成功合龙”更适合理解为：

**层层上交，而不是层层互相揉成一体。**

最终验收口径也应固定为：

* 后台主验收口在 `orchestrator`

* 前台用户验收口在 `chat`

这条原则非常重要，因为它能避免 Butler 后续继续走向：

* 每层都想自己成为主控

* 每个 worker 都试图直接对接所有其他 worker

* 最后系统边界越来越乱

而改为：

* 下层交 contract

* 上层做编排与验收

* 顶层负责用户可见交付

### 关于 `agents_os` 的长期维护线

Butler 长期应明确保留一条常驻的 `agents_os` 维护主线。

原因不是因为它要吞并所有能力，而是因为：

`agents_os`**&#x20;是 Execution Kernel Plane 的长期 owner，需要持续维护运行时内核，而不是阶段性做完一次就结束。**

它长期应负责的内容主要包括：

* execution contract

* runtime binding

* capability invocation

* checkpoint / resume

* approval / verification / recovery 的执行侧接口

* receipt / tracing / runtime observability 的内核接线

但它不应被误解为：

* 产品总包方

* 最终验收层

* `chat` 的替代者

* `orchestrator` 的替代者

* `research` 场景解释层

* `multi_agents_os` 协作状态层

因此，对 `agents_os` 更准确的长期定义应是：

**Kernel / Runtime Owner**

而不是：

**All-in-one Agent Owner**

它的长期验收方式也应固定为：

1. 是否稳定向上交付 execution kernel contract

2. 是否支撑 `orchestrator` 消费这些能力

3. 是否支撑 `chat` 通过上层链路完成最终交付

也就是说：

* `agents_os` 需要一条长期 worker 线

* 但这条线的成功标准不是“自己做完产品闭环”

* 而是“持续提供稳定内核能力，供上层控制面和入口面消费”

***

## 7.6 截至 2026-03-23 的现状映射快照

本节是一个带时间戳的“现状模块 -> 六层目标架构”对照表，后续更新时建议保留旧日期并追加新快照，而不是覆盖历史判断。

快照时间：

* `as_of`: 2026-03-23

* 参考上下文：

  * 当前仓库结构

  * 当前系统架构_20260314.md

  * 本文当前版本中的长期六层定义

### 先说明一个边界

飞书、talk、future GUI、dashboard 这类前台入口，不属于 Butler 的“长期六层内核”，它们更适合作为：

**Product Entry / Interface Surface**

也就是说，下面的映射表重点讨论的是 Butler 的内核和后台主线，不把所有入口都硬塞进六层。

### 现状模块 -> 六层目标架构对应表

| 当前对象                                                           | 截至 2026-03-23 的当前定位                                                             | 长期目标归属层                                                            | 当前判断            | 后续更新关注点                                                             |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------ | --------------- | ------------------------------------------------------------------- |
| `framework research / concepts docs / 外部框架调研材料`                | 主要以文档和调研笔记形式存在，尚未形成正式 catalog/schema                                            | `Package / Framework Definition Plane`                             | 已有概念基础，未形成正式对象层 | 先补 `framework_catalog`、`framework_profile`、`framework_mapping_spec` |
| `future capability/team/workflow package`                      | 目前更多还是概念与 prompt/team 定义，尚未成为正式 package 对象                                      | `Package / Framework Definition Plane`                             | 明显缺位            | 把 package 从 prompt 级约定升级成正式定义对象                                     |
| `orchestrator`                                                 | 已有 mission / node / branch 组织能力，开始像控制面，但仍未完全 workflow-backed                    | `Mission / Control Plane`                                          | 方向正确，控制面语义未完全收口 | 从 branch 调用器推进为 mission/control plane                               |
| `task ledger / mission-node-branch 账本`                         | 已承担上层任务真源雏形                                                                     | `Mission / Control Plane`                                          | 已有真源雏形          | 明确 mission / workflow / branch 边界，避免混写运行态字段                         |
| `workflow IR` 相关对象                                             | 目前仍分散在 mission/node/runtime_plan/open dict 中                                    | `Workflow Compile Plane`                                           | 关键缺口            | 固化 Butler 统一 IR 与 Collaboration Contract                            |
| `planner/compiler` 能力                                          | 目前以散落逻辑和人工概念映射为主，尚无正式 compiler                                                  | `Workflow Compile Plane`                                           | 关键缺口            | 建立 `framework -> Butler IR` 编译路径                                    |
| `agents_os`                                                    | 已有 instance/checkpoint/receipts 等协议雏形，但 workflow VM 仍未真正补齐                      | `Execution Kernel Plane`                                           | 关键主线，仍偏骨架       | 补 step execution、resume、retry、approval/verification gate            |
| `ExecutionRuntime`                                             | 仍偏 placeholder / 协议占位                                                           | `Execution Kernel Plane`                                           | 明显未完成           | 必须成为真实 workflow execution engine                                    |
| `cli_runtime / runtime_router / runtime adapters`              | 已承担运行时选择和执行接线，但仍偏适配层                                                            | `Execution Kernel Plane`                                           | 局部存在            | 需要纳入 runtime binding 的正式模型，而不只是散装分支决策                               |
| `agent_team_executor`                                          | 当前可快速拉起本地 team/subagent，但本质仍偏 prompt fan-out                                    | `Execution Kernel Plane` 的兼容层 / fallback adapter                   | 过渡性价值明显         | 长期不作为核心 team engine，只保留兼容价值                                         |
| `multi_agents_os`                                              | 已有 workflow session / shared state / artifact registry 雏形，但 typed primitives 不足 | `Collaboration State Plane`                                        | 方向正确，层内能力不完整    | 继续补 mailbox、ownership、join contract、workflow-scoped memory          |
| `workflow session / shared state / artifact registry`          | 已构成协作容器雏形                                                                       | `Collaboration State Plane`                                        | 已有地基            | 从“能存”升级到“能协作、能路由、能声明所有权”                                            |
| `memory_manager / memory_backend / local_memory_index_service` | 当前更像跨层基础设施，定义记忆、运行记忆、长期记忆尚未完全分流                                                 | 跨层支撑；最终分别归六层内不同 memory 类型                                          | 暂时混合态           | 后续不要抽大而泛的 Memory Plane，而是按层拆归属                                      |
| `acceptance_service / verification/approval/recovery 协议`       | 已有 receipt 和字段雏形，但执行化不足                                                         | `Governance / Observability Plane` 与 `Execution Kernel Plane` 共同承担 | 方向对，执行语义弱       | 治理规则留在治理层，恢复动作进入执行内核                                                |
| `tracing / audit / postmortem / metrics`                       | 目前分散、不成体系                                                                       | `Governance / Observability Plane`                                 | 仍明显缺位           | 需要从日志升级到 tracing、audit、experience record                            |
| `butler_bot / 飞书入口 / talk`                                     | 当前是主要产品入口和同步交互面                                                                 | 六层之外的 `Product Entry / Interface Surface`                          | 重要但不应反向定义内核     | 继续作为入口层，不与 runtime 真源混同                                             |

### 关于 memory 的现状补充判断

截至 `2026-03-23`，Butler 的 memory 体系仍偏混合态，尚未完全按六层拆开。更准确的现状理解是：

* 定义型记忆已经开始存在，但主要散落在 concepts / docs / prompt / team 定义中。

* mission 控制记忆已经开始存在于 task ledger / mission-node-branch 账本中。

* 执行短期记忆目前更多隐含在 runtime 上下文和 step 传参中。

* 协作共享记忆已经开始存在于 workflow session / shared state / artifact registry 中。

* 治理记忆则主要还停留在 receipts、acceptance、日志与人工判断中。

这意味着当前 Butler 不是“没有 memory”，而是：

**memory 已经出现，但仍然没有完全按长期六层目标完成职责归位。**

### 建议的后续更新方式

以后更新这一节时，建议每次按同一格式追加一版：

1. 写明 `as_of` 日期。

2. 只更新“当前定位 / 当前判断 / 后续更新关注点”三列。

3. 如果某个模块跨层，明确写“当前混合态，长期拆分到哪几层”。

4. 不删除旧判断，保留演化轨迹。

这样这张表就可以持续充当 Butler 的阶段性架构对照基线。

***

## 8. Butler 应吸收什么，不应吸收什么

## 8.1 应吸收的部分

* `gstack` 的开发节奏建模

* `Superpowers` 的 hard gate 与 spec/plan discipline

* `OpenHands` 的 SDK / CLI / GUI / Cloud 分层

* `AutoGen` 的 core vs higher-level API 分层

* `CrewAI` 的 crew 与 flow 分离

* `MetaGPT` 的 SOP-first 思路

* `LangGraph` 的 graph execution + durable state

* `OpenAI Agents SDK` 的 handoff / guardrails / tracing 第一类建模

* `Temporal` 的 durable execution 工程纪律

* `OpenFang` 的 Agent OS 化视角、自治能力包思路、安全治理与内核显式分层

## 8.2 不应照搬的部分

* 把宿主交互协议当成系统内核

* 把角色命名当成能力本身

* 把 prompt 目录数量误当系统成熟度

* 把“能并发调几个 agent”误当 runtime 成熟度

* 为兼容外部框架而复制外部术语和目录结构

* 把外部项目的大一统产品壳层误当 Butler 当前阶段的优先级

* 把 “orchestrator 即超级 agent” 误当 Butler 的长期控制面

***

## 9. 长期实施路线图

## 9.1 P0：统一语言与真源

目标：

* 定义 Butler 的 Workflow IR

* 定义 framework catalog / framework mapping spec

* 明确 mission / workflow / session / artifact / receipt 各自真源

交付物：

* workflow schema

* role schema

* artifact schema

* framework catalog schema

* verification / approval / recovery schema

这一步不追求复杂执行，只追求：

**先把内部语言统一。**

## 9.2 P1：补齐 Workflow VM

目标：

* 把 `agents_os` 变成真正的 workflow execution engine

至少补齐：

* multi-step execution

* branching

* join

* retry

* approval pause

* verification gate

* cursor advancement

* deterministic checkpoint / resume

这一步完成后，Butler 才从“骨架”进入“系统”。

## 9.3 P2：升级 Collaboration Substrate

目标：

* 把 `multi_agents_os` 从 session store 升级成协作底座

至少补齐：

* mailbox

* ownership

* blackboard

* step output contract

* cross-role artifact routing

这一步完成后，team 才不再只是 prompt 级分工。

## 9.4 P3：形成 Framework Compiler

目标：

* 外部方法论先编译成 Butler IR，再执行

优先接入类型：

* software-factory flow

* coding team flow

* research workflow

* approval-heavy governance workflow

这一步完成后，Butler 才真正具备“吸收外部框架”的长期能力。

## 9.5 P4：入口产品化

目标：

* 飞书 / talk

* CLI

* dashboard / GUI

* research manager / project manager

* future cloud / remote workers

统一基于同一 runtime core，而不是各写一套流程。

***

## 10. 建议的长期北极星

建议把 Butler 的长期北极星写成：

> Butler 不是一个会分工的聊天 Agent，也不是某个外部框架的兼容壳。\
> Butler 的长期目标，是成为一个 framework-native、runtime-first 的 Agent OS + Collaboration OS：\
> 它能吸收外部方法论，将其编译成统一的 Butler Workflow IR / Collaboration Contract，\
> 再由自己的执行内核稳定运行、恢复、治理和演化。\
> 它参考外部框架，但不依附任何单一框架，不复制任何单一项目的产品壳层。

***

## 11. 本轮建议的近期动作

在真正进入下一轮实现前，建议先把近期工作限制在以下三件事：

1. 固化 `Workflow IR` 草案。

2. 固化 `framework catalog + mapping spec` 草案。

3. 设计 `workflow VM` 的最小执行语义，而不是先继续扩 team / skill 数量。

如果这三件事不先收口，后面无论接更多 team、更多 role、更多 framework，都会继续堆在 prompt 层，无法形成真正的长期能力。

考虑到 `OpenFang` 的启发，近期动作还应额外补一条执行原则：

4. 任何新增能力、外部框架接入或 team 模板沉淀，都优先以 `package + contract + runtime binding` 形式设计，而不是只新增 prompt、角色名或命令入口。

***

## 12. 参考项目

本轮主要参考以下 GitHub 项目与其公开 README / 文档说明：

* gstack\
  <https://github.com/garrytan/gstack>

* Superpowers\
  <https://github.com/obra/superpowers>

* OpenHands\
  <https://github.com/All-Hands-AI/OpenHands>

* AutoGen\
  <https://github.com/microsoft/autogen>

* CrewAI\
  <https://github.com/crewAIInc/crewAI>

* MetaGPT\
  <https://github.com/FoundationAgents/MetaGPT>

* OpenFang\
  <https://github.com/RightNow-AI/openfang>

* LangGraph\
  <https://github.com/langchain-ai/langgraph>

* OpenAI Agents SDK\
  <https://github.com/openai/openai-agents-python>

* Temporal\
  <https://github.com/temporalio/temporal>

这些项目对 Butler 的价值，不在于“哪一个最像 Butler”，而在于它们分别证明了：

* 软件工厂节奏可以被结构化。

* 多 Agent 协作需要 runtime，而不只是角色。

* durable execution 与 human-in-the-loop 必须进入系统内核。

* Agent OS 化、安全治理与自治能力包可以先于“大而全编排语法”成立。

* 产品化平台最终都会要求内核与入口解耦。

⠀
