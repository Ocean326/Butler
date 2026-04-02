# 0330 Agent Harness 全景研究与 Butler 主线开发指南

日期：2026-03-30  
时间标签：0330_0002  
状态：已完成研究收口 / 子计划真源入口版（2026-03-31 已拆为 `02A/B/C/D/R/F/G`）

关联文档：

- [00_当日总纲.md](./00_当日总纲.md)
- [01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md](./01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md)
- [当前系统基线](../../project-map/00_current_baseline.md)
- [分层地图](../../project-map/01_layer_map.md)
- [功能地图](../../project-map/02_feature_map.md)
- [系统级审计与并行升级协议](../../project-map/06_system_audit_and_upgrade_loop.md)
- [Workflow IR 正式口径](../../runtime/WORKFLOW_IR.md)
- [0326 Harness 全系统稳定态运行梳理](../0326/03_Harness全系统稳定态运行梳理.md)
- [0327 Skill Exposure Plane 与 Codex 消费边界](../0327/02_SkillExposurePlane与Codex消费边界.md)
- [0329 Codex 主备默认自动切换](../0329/01_Codex主备默认自动切换.md)
- [02A_runtime层详情.md](./02A_runtime层详情.md)
- [02B_协议编排与能力包开发计划.md](./02B_协议编排与能力包开发计划.md)
- [02C_会话协作与事件模型开发计划.md](./02C_会话协作与事件模型开发计划.md)
- [02D_持久化恢复与产物环境开发计划.md](./02D_持久化恢复与产物环境开发计划.md)
- [02R_外部Harness映射与能力吸收开发计划.md](./02R_外部Harness映射与能力吸收开发计划.md)
- [02F_前门与Operator产品壳开发计划.md](./02F_前门与Operator产品壳开发计划.md)
- [02G_治理观测与验收闭环开发计划.md](./02G_治理观测与验收闭环开发计划.md)

---

## 一句话裁决

本轮结论不是“选一家框架替换 Butler”，而是把主流 Agent Harness 的稳定能力拆成可吸收原语，并按 Butler 现役分层收口为：

`Product Surface -> Domain & Control Plane -> L4 Session Runtime -> L3 Protocol -> L2 Durability -> L1 Execution Runtime`

外部框架只进入 Butler 的“映射层与能力包”，不反向成为 Butler 运行真源。

---

## 现役子计划矩阵（2026-03-31 补充）

1. [02R_外部Harness映射与能力吸收开发计划.md](./02R_外部Harness映射与能力吸收开发计划.md)
  - 负责 `framework catalog / framework mapping / compiler inputs / governance defaults` 的总翻译层。
2. [02A_runtime层详情.md](./02A_runtime层详情.md)
  - 负责 `L1 Agent Execution Runtime`、`RuntimeHost / RuntimeKernel / provider adapter / subagent governance`。
3. [02B_协议编排与能力包开发计划.md](./02B_协议编排与能力包开发计划.md)
  - 负责 `WorkflowTemplate / Workflow IR / compile chain / capability package`。
4. [02C_会话协作与事件模型开发计划.md](./02C_会话协作与事件模型开发计划.md)
  - 负责 `workflow session / mailbox / handoff / join / artifact registry / event model`。
5. [02D_持久化恢复与产物环境开发计划.md](./02D_持久化恢复与产物环境开发计划.md)
  - 负责 `checkpoint / writeback / recovery / artifact-workspace linkage`。
6. [02F_前门与Operator产品壳开发计划.md](./02F_前门与Operator产品壳开发计划.md)
  - 负责 chat/frontdoor、console、prompt/workflow authoring 等产品壳。
7. [02G_治理观测与验收闭环开发计划.md](./02G_治理观测与验收闭环开发计划.md)
  - 负责 `risk_level / autonomy_profile / approval / trace / receipt / acceptance`。
8. `02E` 当前不单开：
  - tool/plugin/resource/MCP/A2A 的吸收与治理分别落到 `02R` 和 `02G`，避免把计划群做重。

## 实现者默认阅读顺序

1. 先读本文的总裁决与“外部能力 -> Butler 吸收裁决”。
2. 再读 [02R_外部Harness映射与能力吸收开发计划.md](./02R_外部Harness映射与能力吸收开发计划.md)，先把 vendor 名词翻成 Butler target/package。
3. 再按主层级命中目标子计划：
  - `L1` 读 `02A`
  - `L3` 读 `02B`
  - `L4` 读 `02C`
  - `L2` 读 `02D`
  - `Product Surface` 读 `02F`
  - `Governance / Observability` 读 `02G`
4. 已进入代码实施时，不再把整份长文当作逐项施工单；本稿负责总图与裁决，实施细节以子计划为准。

---

## 这份文档现在怎么读（先读这个，再读后文）

这份文档原本更偏“研究裁决稿”，现在补成“学习资料 + 开发指南”的双用途版本。  
因此阅读顺序建议固定为三层：

1. **先读“名词层”**
  先把各家框架表面的术语压回少数几个母概念，避免被 vendor 词汇牵着走。
2. **再读“原语层”**
  也就是后文的统一 Harness 解剖法：对象、控制、持久化、委派、批准、工具边界、观测、产品壳。
3. **最后读“裁决层”**
  再去看 LangGraph、Deep Agents、OpenAI Agents SDK、Codex、DeerFlow、Dify 等各自到底强在哪一层，适不适合吸收到 Butler。

如果你已经进入实现阶段，请在读完这三层后直接跳到上面的 `02A/B/C/D/R/F/G` 子计划，而不是继续把本稿当成逐段施工说明。

请始终记住一个原则：

> 外部框架的术语只是“表面命名”；  
> Butler 真正关心的是：**它对应哪一层、解决什么问题、是否可吸收为内部原语**。

---

## 先把专有名词压成少数母概念

很多名词看起来多，其实都可以收口到下面 7 类“母概念”里。  
后面你看到任何框架的新词，先问它属于哪一类，再判断它值不值得单独记。

### A. 执行主体类：谁在做事

1. `Model`
  - 指大模型本体，是“会推理/会生成”的基础能力源。
  - 它**不是**完整 agent，因为它不天然带任务治理、工具调用、状态管理、恢复语义。
2. `Agent`
  - 指“带目标、可决策、可调工具、可推进步骤”的执行主体。
  - 它通常是“模型 + 指令 + 工具 + 状态 + 运行循环”的组合体。
3. `Assistant`
  - 更偏产品视角的人机角色名，强调“和人对话、为人服务”。
  - 它不一定说明底层编排能力有多强。
4. `Role`
  - 指一个 agent 在团队中的职责或身份，比如 planner、coder、reviewer。
  - 它强调“分工”，不是独立 runtime。
5. `Subagent`
  - 指由主 agent/主 runtime 派生出来、为一个子任务服务的代理。
  - 关键不在“更小”，而在于**它是被委派出来的、受上层治理约束的执行单元**。
6. `Remote Agent`
  - 指系统外部、通过协议协作的另一个 agent 应用。
  - 它不是本机内部的 subagent，而更接近“外部能力节点”。



### B. 任务与编排类：事情是怎么被拆和推进的

1. `Task`
  - 一个可被执行、可被完成、可被交付结果的具体子目标。
  - 它通常是最小的“要做什么”单位。
2. `Workflow`
  - 指多个步骤、多个状态迁移、多个节点之间的整体工作流。
  - 它强调“过程结构”。
3. `Graph`
  - 是 workflow 的一种表达形式：用 node / edge / state 来表达步骤和路由。
  - 它是**表示方法**，不自动等于 runtime。
4. `Flow`
  - 在很多产品里表示“更显式、更可控、更偏业务编排”的流程。
  - 常常和 crew/agent autonomy 相对。
5. `Orchestration`
  - 指“谁在决定下一步怎么走”的控制逻辑总称。
  - 它是控制模型，不是某一个具体对象。
6. `Runtime`
  - 指真正让任务持续运行、暂停、恢复、持久化、调用工具的执行环境。
  - 这是最容易被忽略、但也是最关键的一层：**图不等于 runtime，节点编辑器也不等于 runtime**。

### C. 会话与容器类：运行痕迹装在哪里

1. `Message`
  - 最小对话消息单位。
2. `Item`
  - 更通用的会话事件/内容单元，可能不只是 message。
3. `Turn`
  - 一次完整交互轮次，往往包含多个事件和输出。
4. `Thread`
  - 一个连续会话容器，强调“同一条任务线/同一上下文链”。
5. `Session`
  - 更偏 runtime 语义，表示一次正在进行且可恢复的执行会话。
  - `thread` 更像“会话线”，`session` 更像“执行实例”。

### D. 状态与长期化类：系统记住了什么

1. `Context`
  - 当前这一步能看到的上下文窗口，强调“眼前可见”。
2. `State`
  - runtime 当前的结构化状态，强调“机器可读、可更新、可路由”。
3. `Memory`
  - 系统跨轮保存、供后续使用的长期记忆，强调“跨当前窗口继续存在”。
4. `Artifact`
  - 执行过程产出的正式对象，如文件、报告、网页、图片、代码补丁。
5. `Checkpoint`
  - 某个时刻的可恢复状态快照。
6. `Durable Execution`
  - 指系统即使中断、重启、等待审批，也能继续跑下去的能力。
7. `Replay`
  - 基于 checkpoint / event log 再现运行过程或恢复执行。

### E. 能力暴露类：系统能调用什么

1. `Tool`
  - 可被 agent 调用的单个操作能力，如搜索、读文件、执行代码。
2. `Skill`
  - 通常是更高层的能力包，可能包含说明、流程、约束、子工具组合。
3. `Plugin`
  - 更偏产品/平台化扩展单元，常自带安装、启停、版本、权限治理。
4. `Resource`
  - 更偏“可读上下文”或“可引用材料”，不一定是可执行动作。
5. `Prompt`
  - 给模型的自然语言说明/模板，不等于工具，也不等于 runtime。
6. `MCP Server`
  - 是一种标准化能力提供端，向外暴露 tool/resource/prompt。
  - 它是“接入协议的一端”，不是 workflow 真源。

### F. 治理与人工介入类：系统什么时候该停、该问、该拒绝

1. `Policy`
  - 规则与策略集合，决定允许什么、阻止什么、何时升级人工介入。
2. `Guardrail`
  - 更靠近执行时的防护机制，用于限制风险、触发拦截、改写输出、终止流程。
3. `Approval`
  - 明确需要人工确认才能继续的动作切口。
4. `Interrupt`
  - runtime 主动暂停的正式语义，可能由人触发，也可能由系统策略触发。
5. `HITL`
  - Human-in-the-loop，人类在回路中。
  - 它不是“人工随便看看”，而是正式参与运行控制。
6. `Autonomy Profile`
  - 给 agent 指定的自治级别：能自主到什么程度、何时必须请示。

### G. 观测与产品壳类：人怎么理解和操作这个系统

1. `Tracing`
  - 细粒度执行轨迹，记录模型调用、工具调用、handoff、错误、策略触发等。
2. `Run History`
  - 面向产品/操作者的历史运行记录。
3. `Timeline`
  - 时间顺序视角的执行过程展示。
4. `Audit Log`
  - 强调“可追责、可复读、可审计”的正式日志。
5. `Console / Studio / UI`
  - 人用来观察和操作系统的前台壳。
6. `Gateway`
  - 对外聚合入口，常负责模型、工具、上传、artifact、配置等服务面。
7. `App Server`
  - 更偏运行协议主机，负责 client-facing 的事件流、会话推进和双向交互。
8. `Product Shell`
  - 一个系统的完整使用外壳，包含 UI、API、上传、管理、配置、日志等，不只是 runtime。

---

## 最容易混淆的 10 组概念（这部分最该反复看）

### 1. `Model` vs `Agent`

- `Model` 是“会思考/会生成”的能力源。
- `Agent` 是“带目标、带动作、带状态、带循环”的工作单元。
- 所以：**模型是脑，agent 是带手脚和任务约束的工作体**。

### 2. `Agent` vs `Assistant` vs `Role`

- `Agent` 强调执行主体。
- `Assistant` 强调产品角色。
- `Role` 强调团队分工。
- 所以：**assistant 是面向用户的叫法，role 是面向团队的叫法，agent 才是运行意义上的主体**。

### 3. `Workflow` vs `Graph` vs `Runtime`

- `Workflow` 是过程结构。
- `Graph` 是一种表达 workflow 的方式。
- `Runtime` 是真正把 workflow 跑起来、停下来、存下来、恢复起来的执行内核。
- 所以：**有图，不代表有 runtime；能画节点，不代表能 durable execution**。

### 4. `Thread` vs `Turn` vs `Item` vs `Session`

- `Item` 是最细粒度内容/事件对象。
- `Turn` 是一轮交互。
- `Thread` 是一条连续会话线。
- `Session` 是一次带运行语义的执行会话。
- 所以：**thread 更像“线”，session 更像“活着的执行实例”**。

### 5. `Context` vs `State` vs `Memory`

- `Context` 是当前可见内容。
- `State` 是 runtime 可操作的结构化状态。
- `Memory` 是跨轮长期保留的信息。
- 所以：**context 是眼前，state 是机器当前握着的结构，memory 是过后还能想起来的东西**。

### 6. `Tool` vs `Skill` vs `Plugin` vs `Resource`

- `Tool` 是单个动作。
- `Skill` 是能力包/能力说明与操作套路。
- `Plugin` 是平台扩展单元。
- `Resource` 是供读取或引用的内容对象。
- 所以：**skill 不等于 tool，plugin 不等于 tool market，resource 更不等于 executable action**。

### 7. `Handoff` vs `Subagent` vs `Crew` vs `Message Hub`

- `Handoff` 是把任务/控制权交给另一个主体的动作。
- `Subagent` 是被主 agent 派出来干子任务的执行体。
- `Crew` 是多个 agent 的组织形态。
- `Message Hub` 是它们彼此通信的拓扑或总线。
- 所以：**handoff 是动作，subagent 是对象，crew 是组织，hub 是通信结构**。

### 8. `Approval` vs `Guardrail` vs `Interrupt`

- `Approval` 是“要不要继续”的人工确认点。
- `Guardrail` 是风险控制规则。
- `Interrupt` 是 runtime 的正式暂停语义。
- 所以：**guardrail 可能触发 interrupt；interrupt 之后可能需要 approval；三者不是同义词**。

### 9. `Artifact` vs `FileSystem` vs `Workspace`

- `Artifact` 是正式产物。
- `FileSystem` 是文件组织与访问层。
- `Workspace` 是一个任务线程的工作空间。
- 所以：**文件系统是承载层，artifact 是产出物，workspace 是任务活动边界**。

### 10. `Gateway` vs `App Server` vs `Console`

- `Gateway` 负责统一接入与能力聚合。
- `App Server` 更偏运行协议宿主。
- `Console` 是给人用的操作和观测面。
- 所以：**不要把 API 入口、运行宿主、操作界面混成一层**。

---

## 专有名词统一翻译规则（读任何框架都先做这一步）

后面读到任何框架名词时，都建议先做下面这 4 步翻译：

1. **先问它属于哪一层**
  - 是执行主体？编排对象？持久化对象？治理对象？还是产品壳？
2. **再问它是“对象”还是“动作”**
  - 例如 handoff 是动作，不是对象； subagent 是对象，不是动作。
3. **再问它是“内核真源”还是“外部接入壳”**
  - 例如 MCP 是接入协议，不是内部 workflow 真源。
4. **最后才问它的 vendor 名字值不值得记**
  - 大多数时候，不值得先记名字，值得先记它解决的问题。

---

## 为什么 Butler 一定要先做“术语收口”

Butler 现在做的是一个长周期、可演化的 agent harness。  
这种系统最怕的不是功能少，而是：

1. 外部术语直接回流成内部命名；
2. 一个词同时承担对象、动作、产品壳三种含义；
3. runtime、workflow、UI、插件、协议被混成一层。

所以 Butler 文档需要坚持两个纪律：

1. **内部真源名词尽量稳定**
  外部框架只通过 mapping 层进入 Butler，不反向改写主线命名。
2. **概念优先于品牌**
  先理解“它是哪一类原语”，再记“它在某一家里叫什么”。

---

## 研究范围与方法

本轮调研对象：

1. LangChain 预制件 Agents
2. Deep Agents
3. LangGraph
4. OpenAI Agents SDK
5. Codex 多 Agent 体系（Subagents + Harness/App Server 思路）
6. A2A
7. CrewAI
8. AgentScope
9. Dify
10. DeerFlow
11. MCP（作为互操作补轴）

研究口径：

1. 只用官方或一手技术资料作为裁决依据
2. 每个框架都按同一维度比较，避免“各说各话”
3. 每个能力都必须映射回 Butler 现役层级，不做悬空讨论
4. 输出“吸收什么 / 不吸收什么 / 何时吸收”
5. 截至 `2026-03-30`，涉及外部产品能力的判断以官方公开文档与官方仓库说明为准

比较维度：

1. 核心抽象
2. 编排模型
3. 状态与持久化
4. 多 agent 协作与 handoff
5. 工具与插件（含 MCP/A2A）
6. 治理与 guardrail
7. tracing 与 observability
8. 产品壳与运行内核边界

---

## 用 Butler 口径把各家框架重新排层（阅读后文的导航图）

在进入各家细节之前，可以先把它们粗分成 6 类。  
这样后面你看到某个项目很强，就不会误以为“它在所有层都强”。

### 1. 低层 Runtime 内核

- 代表：`LangGraph`
- 关心的问题：状态、节点、路由、中断、恢复、持久化、时间旅行。
- 这类系统最像“执行内核”。

### 2. 上层 Agent Harness / Agent Builder

- 代表：`LangChain Agents`、`Deep Agents`
- 关心的问题：怎么更方便地构 agent，怎么把 tools/memory/skills/filesystem/subagents 接进来。
- 这类系统更像“带工作环境的 agent 壳”。

### 3. 对象化 Agent SDK

- 代表：`OpenAI Agents SDK`
- 关心的问题：agent、tool、handoff、session、guardrail、tracing 这些对象怎样统一建模。
- 这类系统最像“可编程对象模型”。

### 4. 协议与互操作层

- 代表：`MCP`、`A2A`
- 关心的问题：外部工具和外部 agent 如何发现、协作、交换信息。
- 这类系统最像“连接协议”，不是内部真源。

### 5. 产品化编排与运营壳

- 代表：`CrewAI`、`AgentScope`、`Dify`
- 关心的问题：团队编排、流程控制、实验到生产、插件治理、工作台、观察面。
- 这类系统最像“产品平台”。

### 6. 全栈 SuperAgent Harness

- 代表：`DeerFlow`
- 关心的问题：把 runtime、gateway、frontend、sandbox、filesystem、artifacts、skills、memory 一起焊成一个完整系统。
- 这类系统既不是纯内核，也不是纯平台，而是“整套可跑系统的参考实现”。

---

## 后面看每一节时，建议固定问 3 个问题

1. **它最强的是哪一层？**
  - 是 runtime 语义，还是对象抽象，还是 product shell，还是协议接入？
2. **它的名词有没有混层？**
  - 有些框架喜欢把产品对象、运行对象、协议对象混在一起叫。
3. **它对 Butler 的价值是“直接吸收原语”，还是“只拿来参考组织方式”？**
  - 不是每个好框架都适合进入主线真源。

---

## 统一 Harness 解剖法

为了避免“每家框架都在讲不同词”，先固定一套 Butler 内部使用的统一解剖法。后面所有产品都按这套问题来拆：

1. `Object Model`
  - agent / tool / task / thread / workflow / session 的原生对象是什么
2. `Control Model`
  - 单 agent loop、manager-tool、graph orchestration、team/flow、client-server 协议，究竟哪一层在裁决“下一步做什么”
3. `Durability Model`
  - 状态存在内存、session、checkpointer、event log，还是产品数据库里
4. `Delegation Model`
  - 多 agent 是 handoff、subagent、message bus、crew、remote agent，还是 workflow 节点
5. `Approval / HITL`
  - 系统在哪个层级暂停，谁来批准，恢复靠什么继续
6. `Tool / Plugin Boundary`
  - 外部能力是 tool、MCP、plugin、strategy、trigger，还是 remote agent
7. `Observability Model`
  - trace / run history / timeline / studio / audit 各自落在哪层
8. `Product Shell`
  - 是否自带 operator UI、debug surface、web app、hosted runtime、API 壳

这套解剖法的意义是：

1. 不再把“有节点图”误判成“有 durable runtime”
2. 不再把“有 tool/plugin 市场”误判成“有多 agent session 语义”
3. 不再把“有 tracing”误判成“有 operator harness”

## 框架全景矩阵（重排后）

### A. LangChain 家族

1. `LangChain Agents`
  - 上层 agent builder
  - 强项是模型、工具、middleware、state 扩展的可编程性
2. `Deep Agents`
  - LangChain 自己明确称其为 “agent harness”
  - 强项是 planning、subagents、filesystem、memory、context engineering、sandbox、HITL 一体化
3. `LangGraph`
  - 低层 runtime
  - 强项是 state/nodes/edges、durable execution、interrupt/resume、subgraph、streaming、time-travel

### B. OpenAI 家族

1. `OpenAI Agents SDK`
  - agent / tool / handoff / guardrail / session / tracing 一体对象模型
2. `Codex CLI + Subagents`
  - 本地 coding agent 与显式 subagent 编排
3. `Codex Harness / App Server`
  - thread/turn/item 的产品级事件流协议
4. `Harness Engineering`
  - 更偏“如何为 agent 造工作环境”的工程方法，而不是纯 SDK 抽象

### C. 协议与互操作家族

1. `MCP`
  - 工具、资源、prompt 的 client-server 协议
2. `A2A`
  - agent-to-agent 的发现、协作、长任务、消息与流式协议

### D. 产品化编排家族

1. `CrewAI`
  - crew 与 flow 分离
2. `AgentScope`
  - message hub、多 agent workflow、OTel/Studio、实验到生产过渡
3. `Dify`
  - app shell、workflow/chatflow、plugins、run history、trigger、运营治理

### E. 全栈 SuperAgent Harness 家族

1. `DeerFlow`
  - LangGraph/LangChain 之上的全栈 super agent harness
  - 强项是 middleware 链、per-thread sandbox/filesystem、skills/memory/gateway 分层、研究/代码/制品一体

## 各家 Harness 具体知识（按产品逐一拆）

### 1. LangChain Agents（预制件 Agent）

#### 核心对象

1. 当前官方 `create_agent` 是主入口。
2. 官方文档明确说明：`create_agent` 构建的是一个“graph-based agent runtime”，底层跑在 `LangGraph` 上。
3. 其核心组合件是：
  - `model`
  - `tools`
  - `middleware`
  - `state_schema`

#### Harness 真正价值

1. LangChain Agents 不是独立 durable runtime，更像“上层 agent 预制壳”。
2. 它的 harness 价值不在 graph 本身，而在：
  - 让模型、工具、middleware、state 增量定制变简单
  - 让你先从上层 agent loop 启动，再按需要下钻 LangGraph
3. `middleware` 是这层最值得重视的点：
  - 不是只改 prompt
  - 而是把 state、tool、before/after model hook、logging/rate limit 等行为统一插到 agent loop 中

#### 对 Butler 的启发

1. Butler 不必吸收 LangChain 的全部 agent API 形态，但应吸收这种“上层易用壳 + 下层可下钻 runtime”的分层。
2. 对应映射：
  - `LangChain Agent shell` -> `L1 适配层 + Domain 上层 builder`
  - `middleware/state_schema` -> `Butler 的 runtime policy / prompt policy / tool policy 插桩点`
3. 不建议吸收：
  - 把 `create_agent` 直接当 Butler 主协议
  - 把 LangChain 自己的 agent state 命名强行并入 Butler 真源

### 2. Deep Agents（LangChain 的 Agent Harness）

#### 核心对象

1. 官方把 `deepagents` 明确定位成 “agent harness”。
2. 它是一个独立库，构建在 LangChain building blocks 之上，但 runtime 用的是 LangGraph。
3. 官方明确给出的 harness 能力包括：
  - `planning`
  - `virtual filesystem`
  - `task delegation (subagents)`
  - `context and token management`
  - `code execution`
  - `human-in-the-loop`
  - `skills`
  - `memory`

#### Harness 运行心智

1. Deep Agents 把“复杂多步任务”理解成一个带内建工作环境的 agent，而不是单纯 prompt loop。
2. 它把很多平时散落在产品外的能力前置为 harness 原语：
  - 文件系统
  - 子代理
  - 上下文压缩
  - 沙箱执行
  - 技能按需加载
  - 长期记忆
3. 其 subagent 机制不是 message swarm，而是：
  - 主 agent 有一个 `task` 工具
  - 调用后生成新 agent instance
  - subagent 在自己上下文里跑完
  - 只回一个最终报告
  - 默认强调 context isolation 和 token efficiency

#### Butler 应吸收什么

1. 把 Deep Agents 当作“harness 能力清单”参考，而不是当作要直接嵌入的 runtime。
2. 优先吸收：
  - `virtual filesystem` 对上下文治理的作用
  - `subagent as isolated task runner`
  - `interrupt_on` 这种 tool-level HITL 切口
  - `skills` 的 progressive disclosure 思路
  - `memory` 与 `skills` 的常驻/按需区分
3. 对 Butler 的直接映射：
  - `task delegation` -> `L4 session runtime` 的 handoff / subtask contract
  - `filesystem + sandbox` -> `L1/L2` 执行与持久化边界
  - `skills + memory` -> `Domain/Control` 的 exposure plane，而不是 provider-local 黑盒

### 3. LangGraph

#### 核心对象

1. LangGraph 把 agent workflow 建模为：
  - `State`
  - `Nodes`
  - `Edges`
2. 执行模型是 message passing + Pregel 风格 super-step。
3. compile 阶段不仅做结构校验，还能注入：
  - `checkpointer`
  - `breakpoints`
  - runtime args

#### Harness 关键语义

1. LangGraph 的真正核心不是“画图”，而是 stateful、durable、interruptible runtime。
2. 官方把这些明确列成一等能力：
  - `Persistence`
  - `Durable execution`
  - `Interrupts`
  - `Time travel`
  - `Memory`
  - `Subgraphs`
3. `Command` 是非常关键的运行时原语：
  - `update`
  - `goto`
  - `graph`
  - `resume`
4. 这意味着它把：
  - 状态更新
  - 路由跳转
  - 子图跃迁
  - 人工恢复
   统一收口到一个明确的 runtime contract

#### HITL / Durability 的工程含义

1. interrupt 不是调试断点，而是正式的 HITL 契约。
2. durable execution 文档明确要求：
  - 开启 persistence/checkpointer
  - 指定 thread identifier
  - 非确定性操作与 side effects 用任务包装，避免 resume 时重复执行
3. 这和 Butler 长任务语义是直接对齐的。

#### 对 Butler 的裁决

1. Butler 应重点吸收 LangGraph 的 runtime semantics，不吸收其 DSL 作为内部真源。
2. 优先吸收：
  - `interrupt -> resume`
  - `checkpoint -> replay`
  - `subgraph -> parent graph`
  - `update + goto`
3. 对应映射：
  - `State/Nodes/Edges/Command` -> `L4 + L2`
  - `thread identifier + checkpointer` -> `workflow_session_id + durability receipt`
4. 不建议做的事：
  - 直接把 LangGraph state schema 变成 Butler domain truth
  - 用“图编辑器节点结构”反向替代 `Workflow IR`

### 4. OpenAI Agents SDK

#### 核心对象

1. Agents SDK 的基础对象组合是：
  - `Agent`
  - `Runner`
  - `Tools`
  - `Handoffs`
  - `Guardrails`
  - `Sessions`
  - `Tracing`
2. 它的价值在于把单 agent 到多 agent 的常见运行元素对象化，而不是只给一个 loop helper。

#### 多 Agent / Delegation

1. `Runner.run(...)` 负责执行：
  - individual agents
  - handoffs
  - tool calls
2. `handoff` 明确被建模为：
  - delegate to another agent
  - represented as a tool to the LLM
3. 这说明 SDK 把 delegation 收口成“模型可调用的结构化操作”，而不是额外的隐式外部路由器。

#### Session / Guardrail / Trace

1. `Sessions` 提供自动记忆与会话存储层，官方内置：
  - `SQLiteSession`
  - `OpenAIConversationsSession`
2. `Guardrails` 明确支持 `tripwire`：
  - 一旦触发，立即抛出异常并停止 agent 执行
3. `Tracing` 默认开启，覆盖：
  - generations
  - tool calls
  - handoffs
  - guardrails
  - custom events

#### 对 Butler 的裁决

1. Butler 最应吸收的是其对象边界，而不是 API 形状。
2. 优先吸收：
  - `handoff as typed contract`
  - `guardrail as structured stop/replace/tripwire`
  - `session as explicit store`
  - `trace spans` 覆盖 handoff/tool/guardrail
3. 对应 Butler 层级：
  - `Agent/Tool` -> `L1`
  - `Handoff/Session` -> `L4`
  - `Guardrail` -> `Domain + Governance`
  - `Tracing` -> `Observability`

### 5. Codex CLI / Subagents / Harness / App Server

#### 5.1 Codex CLI 与 Subagents

1. Codex CLI 是本地 coding agent，能在选定目录：
  - 读代码
  - 改代码
  - 跑代码
2. Subagents 当前是显式多 agent 工作流：
  - 并行 spawn specialized agents
  - 主 agent 负责收集结果
  - 只有明确要求时才生成 subagent
3. Codex 会负责：
  - spawning
  - routing follow-up instructions
  - waiting for results
  - closing agent threads
4. subagent 继承当前 sandbox policy，这一点非常关键，说明它不是“自由自治”，而是受同一治理壳约束的代理分身。

#### 5.2 Codex Harness / App Server

1. OpenAI 公开拆出了 Codex harness 的四个关键部分：
  - `thread lifecycle and persistence`
  - `config and auth`
  - `tool execution and extensions`
  - `App Server` 作为 client-facing protocol/runtime host
2. App Server 是双向 JSON-RPC 风格协议，不只是 request/response。
3. 它的 conversation primitives 非常值得 Butler 参考：
  - `Item`
  - `Turn`
  - `Thread`
4. 一个 request 对应很多 event update，server 还可以主动发“approval needed”请求并暂停 turn，直到 client 返回。

#### 5.3 Harness Engineering 方法论

1. OpenAI 对 harness engineering 的核心总结非常直接：
  - `Humans steer. Agents execute.`
2. 这不是提示词技巧，而是工程组织方式：
  - 人负责造环境
  - 人负责指定 intent
  - 人负责建立 feedback loops
  - agent 负责执行
3. 文中反复强调的几个方法论，非常适合 Butler：
  - repository knowledge as system of record
  - progressive disclosure，而不是一份巨大 `AGENTS.md`
  - 让 UI / logs / metrics / traces 对 agent 可读
  - worktree 级隔离环境
  - doc-gardening agent 负责清理失真文档

#### 对 Butler 的裁决

1. Butler 现在最值得吸收的不是 Codex CLI 命令，而是：
  - `thread/turn/item` 这套产品级事件边界
  - approval/ask-human 的双向协议心智
  - subagent 的继承式治理
  - repo/doc/observability 对 agent legibility 的设计原则
2. 直接映射：
  - `Codex App Server primitives` -> `Product Surface + Domain projection/event contract`
  - `Subagent governance` -> `L4 + Governance`
  - `Harness engineering` -> `Butler 的 operator harness 开发方法`

### 6. MCP

#### 核心对象

1. MCP 明确是 client-server architecture：
  - host
  - client
  - server
2. data layer 基于 `JSON-RPC 2.0`。
3. server features 明确分三类：
  - `tools`
  - `resources`
  - `prompts`
4. client features 还包括：
  - sampling
  - user elicitation
  - logging

#### Harness 含义

1. MCP 的核心价值不是多 agent runtime，而是统一外部能力接入面。
2. 它解决的是：
  - 工具如何被声明和发现
  - 资源如何暴露
  - prompt template 如何传递
  - host 如何和多个 server 建连接
3. 因此 MCP 更像：
  - `tool/context transport layer`
  - 而不是 `workflow/session truth layer`

#### 对 Butler 的裁决

1. Butler 应把 MCP 定位成：
  - tool exposure adapter
  - context/resource bridge
2. 不应把 MCP 直接升级为：
  - campaign truth
  - workflow runtime
  - approval/recovery 主协议

### 7. A2A

#### 核心对象

1. A2A 官方仓库把自己定义为：
  - open protocol
  - enabling communication and interoperability between opaque agentic applications
2. 它要解决的是不同框架、不同公司、不同服务器上的 agent 之间协作，而不是单机内部 orchestrator。
3. 官方明确给出的能力包括：
  - capability discovery
  - modality negotiation
  - secure long-running task collaboration
  - opaque collaboration without exposing internal memory/tools
4. 技术特征包括：
  - `JSON-RPC 2.0 over HTTP(S)`
  - `Agent Cards`
  - synchronous / streaming / async push notification
  - text / file / structured JSON exchange

#### Harness 含义

1. A2A 是 remote-agent 协议，不是 local-task harness。
2. 它适合解决：
  - 外部 agent 发现
  - 能力宣告
  - 跨系统长任务协同
  - 对等 agent 协作
3. 它不负责：
  - 单系统内部 workflow session 真源
  - 本地代码执行与沙箱
  - 产品侧 operator UI

#### 对 Butler 的裁决

1. A2A 适合进入 Butler 的：
  - `gateway`
  - `adapter`
  - `external federation`
2. 当前不应进入 Butler 的：
  - 内部 session runtime 真源
  - 内部协议命名
3. 一个稳妥路径是：
  - Butler 内部继续 `Workflow IR + Session Runtime`
  - Butler 对外再暴露 `A2A server/client facade`

### 8. CrewAI

#### 核心对象

1. CrewAI 的两个关键词非常重要：
  - `Crews`
  - `Flows`
2. 官方对 `Crew` 的定义是：
  - collaborative group of agents
  - 定义 task execution strategy、agent collaboration、overall workflow
3. 官方对 `Flows` 的定义是：
  - structured
  - event-driven
  - stateful
  - 支持 conditional logic、loops、branching

#### Harness 含义

1. CrewAI 最值得学的不是“agent 人设”，而是自治团队和精确流程控制的二分。
2. `Crew` 更像：
  - autonomy group
  - 协作团队
3. `Flow` 更像：
  - control-plane orchestration
  - 状态与事件驱动的精确流程
4. CrewAI 还把 tracing 做成正式能力，能看到：
  - agent decisions
  - task timelines
  - tool usage
  - LLM calls

#### 对 Butler 的裁决

1. Butler 非常适合吸收这条分离原则：
  - `crew/autonomy` 不等于 `flow/control`
2. 对应 Butler：
  - `crew` -> `L4 role binding / team runtime`
  - `flow` -> `Domain + L3/L4 compile/runtime linkage`
3. 不建议吸收：
  - 直接照搬 CrewAI 的术语作为 Butler 现役命名

### 9. AgentScope

#### 核心对象

1. AgentScope 当前官方自我定位是：
  - production-ready
  - easy-to-use
  - design for increasingly agentic LLMs
2. 它明确强调：
  - leverage model reasoning and tool use abilities
  - rather than constrain them with strict prompts and opinionated orchestrations
3. 其能力包很完整：
  - built-in ReAct agent
  - tools / skills
  - HITL steering
  - memory / planning
  - realtime voice
  - evaluation / finetuning
  - MCP / A2A support
  - message hub for flexible multi-agent orchestration
  - OTel support

#### Harness 含义

1. AgentScope 的特色不是单一 runtime 语义，而是“实验到生产”的连续面。
2. `MsgHub` 很关键：
  - 不是简单 handoff
  - 而是可管理 participant 的 message bus
  - 适合做多 agent 对话拓扑和 workflow 实验
3. AgentScope Studio 还支持按 OTLP ingest trace，这说明它把 runtime observability 视为一等公民，而不只是在框架里 print log。

#### 对 Butler 的裁决

1. Butler 最值得吸收的是：
  - `message hub / topology` 作为实验形态参考
  - OTel / trace ingestion 的观测面标准化
  - HITL steering 的实时性思路
2. 不建议吸收：
  - 把 AgentScope 的全能力包直接搬进 Butler 主线
3. 更好的用法：
  - 作为 `multi-agent lab` 参考系
  - 帮 Butler 设计 `session mailbox / event bus / studio trace` 的目标状态

### 10. Dify

#### 核心对象

1. Dify 本质上不是一个纯 runtime 框架，而是一个产品化应用工作台。
2. 官方对 application orchestration 的定义非常清楚：应用同时提供
  - backend/frontend 可直接调用的 API
  - hosted WebApp
  - prompt/context/log/annotation 管理界面
3. Dify 把 app types 做成了稳定产品分类：
  - `Chatbot`
  - `Text Generator`
  - `Agent`
  - `Chatflow`
  - `Workflow`

#### Harness 含义

1. `Workflow` / `Chatflow` 的核心心智是 node-based orchestration。
2. 官方明确强调工作流通过节点分解降低系统复杂度，并提升：
  - interpretability
  - stability
  - fault tolerance
3. Dify 很值得学的不是 node graph 本身，而是产品壳的完整度：
  - `Run History`
  - app-level result/detail/tracing
  - node run history
  - plugin marketplace
  - trigger plugins
  - workspace-scoped plugin governance
  - error handling with retry/default/fail branch/partial success

#### Plugin / Trigger / Strategy 体系

1. Dify 把几乎所有外部能力都插件化：
  - model providers
  - tools
  - agent strategies
  - extensions
2. 插件是 workspace-scoped：
  - 安装一次
  - 整个 workspace 复用
3. Trigger 插件可以直接驱动 workflow 起跑，支持：
  - 自动订阅
  - webhook
  - 并行 trigger branches
4. Error Handling 则把 fallback 设计成正式节点能力：
  - retry
  - default value
  - fail branch
  - partial success

#### 对 Butler 的裁决

1. Butler 最应该吸收的是它的产品治理面，而不是把 Dify 当内部 runtime。
2. 优先吸收：
  - `workspace-scoped plugin governance`
  - `run history + node history`
  - `trigger -> workflow` 产品入口
  - `partial success / fail branch` 的 operator 语义
3. 不建议吸收：
  - 直接把 Dify 节点 DSL 当 Butler 协议层真源
4. 对应映射：
  - `Dify app shell` -> `Product Surface`
  - `plugin governance` -> `Domain/Control`
  - `workflow node UI` -> `Butler console authoring/inspection inspiration`

### 11. DeerFlow（ByteDance 开源 SuperAgent Harness）

#### 核心对象

1. DeerFlow 2.0 不是 DeerFlow 1.x 的小修小补，而是官方明确声明的 `ground-up rewrite`；原始 Deep Research 版本保留在 `1.x` 分支，主线开发已经切到 2.0。
2. 官方对 2.0 的定位不是“一个需要你自己拼装的 agent framework”，而是一个 `super agent harness`：能 research、code、create，并且默认带 filesystem、memory、skills、sandbox-aware execution、sub-agents 等完整工作环境。
3. DeerFlow 后端本身就是一个完整系统，而不是单一 SDK。官方文档把它定义为 `LangGraph-based AI super agent system with a full-stack architecture`，并强调其“super agent”运行在 `per-thread isolated environments` 中。

#### Harness 系统结构

1. DeerFlow 最值得重视的是它把 runtime、gateway、frontend、thread filesystem、artifacts 这些东西都前置进同一套 harness，而不是只提供 agent loop。
2. 官方架构文档给出的主路径是：
  - `Nginx (2026)` 作为统一入口
  - `LangGraph Server (2024)` 负责 agent runtime / thread management / SSE streaming / checkpointing
  - `Gateway API (8001)` 负责 models / MCP / skills / uploads / artifacts
  - `Frontend (3000)` 提供 Next.js Web UI
3. DeerFlow 近期还显式推进了 `Harness / App Split`：把 `packages/harness/deerflow/` 作为可发布、可复用的 harness 内核，把 `app/` 留给 FastAPI Gateway 和 IM channel 集成。这一刀对 Butler 非常有参考价值，因为它把“运行时真源”和“产品接入壳”做了严格依赖切分。

#### 关键运行原语

1. DeerFlow 的 lead agent 不是“大 prompt + 一堆 tools”的松散结构，而是严格 middleware 链：
  - `ThreadDataMiddleware`
  - `UploadsMiddleware`
  - `SandboxMiddleware`
  - `GuardrailMiddleware`
  - `SummarizationMiddleware`
  - `TodoListMiddleware`
  - `TitleMiddleware`
  - `MemoryMiddleware`
  - `ViewImageMiddleware`
  - `SubagentLimitMiddleware`
  - `ClarificationMiddleware`
2. 这条链本质上已经是一个 runtime policy plane：
  - thread data 初始化 thread 级 `workspace/uploads/outputs`
  - uploads 与 artifact 做线程局部注入与可视化
  - summarization 控制 token 压力
  - guardrail 在 tool call 前裁决
  - clarification 通过 `ask_clarification` + interrupt 形成正式的 HITL 切口
3. DeerFlow 的 thread state 也不是只存 message，它显式扩展了：
  - `sandbox`
  - `artifacts`
  - `thread_data`
  - `title`
  - `todos`
  - `uploaded_files`
  - `viewed_images`
4. 这说明 DeerFlow 真正把“会话运行环境”建模成了状态对象，而不是把上下文治理都塞回 prompt。

#### Filesystem / Artifact / Sandbox 心智

1. DeerFlow 的 thread 不是抽象 chat id，而是和本地工作目录、上传文件、输出文件绑定的。
2. `ThreadDataMiddleware` 会为每个 thread 初始化 `workspace/uploads/outputs`；API 里也直接暴露了 uploads list、artifact path、thread cleanup 等正式接口。
3. 这套设计的价值在于：中间过程不必全部回灌 prompt，很多产物可以沉到 filesystem / artifacts，再按需回读。
4. 官方同时明确给出安全警告：DeerFlow 默认是面向本地可信环境设计的高权限 agent，不应把“能跑 bash / 文件操作 / 业务调用”误判成“默认适合裸暴露到不可信网络”。

#### Skills / Memory / Subagent 的组织方式

1. Skills 在 DeerFlow 里不是随意散落的 prompt 片段，而是 `skills/{public,custom}/.../SKILL.md` 这种结构化能力包；系统会自动扫描、解析元数据、读取启用状态，并把已启用技能注入 agent。
2. Memory 不是同步写提示词，而是由 `MemoryMiddleware` 过滤用户输入和最终 AI 回复，进入异步队列，再由后台抽取 context/facts，原子更新本地 memory 文件，并在后续交互中注入精简记忆。
3. Subagent 也有明确治理边界：
  - 内置 `general-purpose` 与 `bash` 两类子代理
  - 通过 `task()` 工具发起
  - 受 `SubagentLimitMiddleware` 的最大并发限制
  - 结果通过事件流与最终报告回收
4. 这说明 DeerFlow 不是 message swarm 式自由放养，而是“受统一 policy shell 约束的 delegation runtime”。

#### DeerFlow 在全景矩阵中的准确定位

1. DeerFlow 不是纯低层 runtime；这点和 LangGraph 不同。
2. DeerFlow 也不是纯 app shell；这点又和 Dify 不同。
3. 它更接近“把 Deep Agents 的 harness 能力清单，落成一个可运行、可访问、可扩展、可观测的全栈样板”。
4. 如果说：
  - `LangGraph` 提供 durable runtime 语义
  - `Deep Agents` 提供 harness 能力清单
  - `Dify` 提供产品壳与运营治理视角
  - `Codex Harness` 提供 thread/turn/item 与 approval 协议心智
   那 DeerFlow 的价值就在于：把其中相当一部分真实地焊接成了一套可跑系统。

#### 对 Butler 的裁决

1. Butler 不应把 DeerFlow 当成“替换性底座”，而应把它当作“全栈 harness 参考实现”。
2. Butler 最应吸收的，不是 DeerFlow 的具体目录结构，而是它的几条组织原则：
  - `runtime 与 gateway/front-end 分层`
  - `middleware chain 作为 runtime policy plane`
  - `thread -> filesystem -> artifacts` 的环境壳
  - `skills / memory / uploads / MCP` 的统一暴露面
  - `clarification / guardrail / subagent limit` 这类正式治理切口
3. 直接映射建议：
  - `LangGraph Server + Gateway API` -> `L1 Execution Runtime + Product Surface`
  - `per-thread workspace/uploads/outputs` -> `L2 Durability + L4 artifact/session environment`
  - `middleware chain` -> `Domain/Control 的策略插桩平面`
  - `embedded client` -> `同一运行内核多消费面`
4. 不建议吸收的部分：
  - 不把 DeerFlow 的 thread/path/middleware 命名直接回流为 Butler 真源
  - 不把本地目录语义直接提升成 Butler 的 campaign/session 主协议
  - 不把 DeerFlow 当前 API surface 直接等价成 Butler 的内部合同
5. 更准确的结论是：DeerFlow 证明了“super agent harness”可以不是概念拼图，而是一个具备 runtime、gateway、filesystem、skills、memory、guardrail、subagent、artifact 的工程化系统；这对 Butler 的长期主线非常有启发。

## 跨框架共识：Harness 真正由什么构成

把这些产品拆开后，会发现成熟 harness 反复收敛到下面 10 个原语：

1. `Task / Turn / Thread / Session` 的稳定容器
2. `State update + next-step routing` 的显式契约
3. `Tool / Plugin / Remote agent` 的边界区分
4. `Handoff / Subagent / Crew / MsgHub` 的 delegation 模型
5. `Interrupt / Approval / Resume` 的人工介入切口
6. `Checkpoint / Durable receipt / Replay` 的恢复基础
7. `Trace / Timeline / Run history / Audit log` 的可复读观测
8. `Sandbox / Filesystem / Execution backend` 的环境壳
9. `Knowledge / Skills / Memory` 的上下文治理
10. `Product Shell / API / App Server / UI` 的可用性壳

一个系统只要缺其中两三块，就不能叫完整 harness，只能叫：

- prompt app
- graph editor
- tool runner
- multi-agent demo

## 对 Butler 的再裁决：哪些知识是“具体可开发”的

### 应直接进入 Butler 主线设计的知识

1. `LangGraph`
  - interrupt/resume
  - checkpoint/replay
  - update/goto
  - parent/subgraph 跳转
2. `OpenAI Agents SDK`
  - handoff as tool
  - guardrail tripwire
  - session object
  - spanized tracing
3. `Codex Harness`
  - thread/turn/item 事件模型
  - bidirectional approval 请求
  - subagent 继承式治理
4. `CrewAI`
  - autonomy 与 flow 分离
5. `Dify`
  - workspace-scoped plugin governance
  - run/node history
  - trigger-based product frontdoor
6. `AgentScope`
  - msg hub / topology 参考
  - OTel-first trace ingestion
7. `DeerFlow`
  - middleware chain 作为 runtime policy plane
  - thread/filesystem/artifact 一体运行环境
  - runtime 与 gateway/frontdoor 的严格分层
8. `MCP + A2A`
  - 外部工具与外部 agent 的双协议分层

### 只能作为参考，不宜直接并入真源的知识

1. 各家特定 DSL
2. 各家 UI 节点命名
3. vendor-specific SDK 的对象名
4. 把“框架支持某能力”误判成“适合作为 Butler 内部真源”

---

## Butler 现状对齐（按层级）

### Product Surface（产品表面层）

已具备：

1. chat/frontdoor 协商、启动、查询主链
2. console/draft board 的基础观测与部分控制入口

缺口：

1. operator 操作面不完整（recovery、prompt/surface、workflow patch 面不足）
2. 多 agent 运行态产品语义仍偏“观测”，还不是“治理+编排”

### Domain & Control Plane（领域与控制平面）

已具备：

1. campaign/mission/orchestrator 基础控制链路
2. query/projection/feedback 的统一组装方向
3. framework catalog/mapping 的外部能力吸收壳

缺口：

1. 把外部能力映射为“可执行治理包/能力包”的闭环不够强
2. operator patch、transition policy、audit receipt 的正式面仍偏薄

### L4 Multi-Agent Session Runtime

已具备：

1. workflow_session/event log/handoff 基础形态
2. session bridge 已进入 orchestrator 主链

缺口：

1. session 级人机协同中断/恢复策略还可继续体系化
2. mailbox/role_binding/artifact registry 需要更稳定外显合同

### L3 Multi-Agent Protocol

已具备：

1. workflow template 与 Workflow IR compile 链路
2. role spec/handoff spec/approval/recovery 等字段骨架

缺口：

1. 协议层“稳定合同与版本策略”需要更明确
2. 外部框架映射到协议对象的自动化编译约束还不足

### L2 Durability Substrate

已具备：

1. checkpoint/writeback/recovery 方向性接口
2. workflow_ir 的 durability boundary 表达

缺口：

1. operator 介入后的 durable receipt 与审计回放仍可加强
2. 多来源恢复证据链仍需标准化

### L1 Agent Execution Runtime

已具备：

1. provider/CLI 适配与 codex runtime 主备切换
2. skill exposure contract 注入主链

缺口：

1. agent runtime 仍有兼容壳包袱
2. guardrail/tracing 在跨 provider 的统一合同仍需增强

---

## 外部能力 -> Butler 吸收裁决

### 应优先吸收（P0/P1）

1. `LangGraph` 的中断/恢复、checkpoint 心智与状态更新纪律
2. `OpenAI Agents SDK` 的 handoff/guardrail/tracing/session 对象化抽象
3. `Codex Harness` 的多 agent 治理思路（继承策略、审批策略、线程与事件统一）
4. `CrewAI` 的 flow 与 autonomy 分离思路
5. `DeerFlow` 的全栈 harness 分层（runtime / gateway / thread filesystem / artifacts / middleware）
6. `MCP` 的工具暴露契约化能力

### 可作为中期吸收（P2）

1. `AgentScope` 的 pipeline/MsgHub 实验化拓扑表达
2. `Dify` 的插件治理与运营可观测产品形态
3. `A2A` 的跨系统 agent 协议（先网关化，后主线化）

### 当前明确不吸收

1. 不照抄任何框架的产品术语当 Butler 真源命名
2. 不直接搬外部 graph DSL 作为 Butler 内部协议真源
3. 不让 UI 节点图反向控制 runtime 真源对象
4. 不把 vendor-specific API surface 写死到 Butler 主合同

---

## Butler 开发指南（面向实现者）

### 1) 抽象与边界

1. Butler 内部真源固定：`Mission/Campaign + Workflow IR + Session Runtime + Durability`
2. 外部框架能力只允许进入：
  - `framework_catalog`
  - `framework_mapping`
  - `compiler inputs / policy package`
3. 产品面只能消费投影，不得直接改写 runtime 真源

### 2) 协议与编排

1. 所有多 agent 编排都应落 `template -> ir -> vm -> session` 链路
2. handoff、approval、verification、recovery 统一走协议字段，不做散落私有参数
3. 新增编排能力先扩协议层，再扩产品操作面

### 3) 状态与恢复

1. 每个可恢复动作必须有：
  - 触发原因
  - 前后状态
  - durable receipt
  - 操作人和策略来源
2. resume/retry/skip/force_transition 必须走同一 action contract
3. query 面只读组装，恢复判断基于 control plane + durability 事实

### 4) 工具与互操作

1. 内部工具面统一走 skill exposure / tool contract
2. MCP 作为工具适配桥，不越权成为任务真源
3. A2A 先做网关/adapter，不改 Butler 内部对象模型

### 5) 治理与观测

1. guardrail、approval、risk_level、autonomy_profile 必须结构化
2. tracing 至少覆盖：
  - route decision
  - workflow compile
  - session transition
  - execution receipt
  - recovery/approval action
3. console 必须可见“策略为何触发”而非只显示结果

### 6) 交付与文档

1. 每轮系统升级必须带 acceptance 证据，不接受只口头“已支持”
2. 当日总纲 + 专题正文 + project-map 入口要同步回写
3. 历史术语只做映射，不回流到现役命名

---

## 并行研究与实施建议（两波）

### 第一波并行（建议 3 lane）

1. `lane-a/runtime`
  - 抽取中断/恢复/审批/回放的统一 action contract
2. `lane-b/control-plane`
  - 做 framework mapping -> compiler inputs -> governance package 的闭环验证
3. `lane-c/operator-surface`
  - 做 console 的 recovery/prompt/workflow 三面只读+受控写入口

第一波目标：统一合同与观测，避免“先做 UI 再补真源”。

### 中途 replan

只保留 P0/P1：

1. 身份和状态真源冲突
2. 恢复路径不可审计
3. 策略与执行分离不彻底

### 第二波并行（建议 3 lane）

1. `lane-d/interoperability`
  - MCP 稳定消费面和 A2A 网关最小样板
2. `lane-e/policy`
  - guardrail/approval/risk 的策略包化
3. `lane-f/acceptance`
  - 链路矩阵证据与回归集补全

---

## 头脑风暴池（按优先级）

### 近程可落地（1-2 周）

1. 增加 `campaign action ledger` 标准事件模型
2. 增加 `prompt surface` 结构化只读与 patch diff
3. 增加 `transition options` 与 `recovery candidates` API
4. 增加 `trace id` 贯穿 query/feedback/console

### 中程专题（2-6 周）

1. 建立 `policy package` 与 `governance default` 注册体系
2. 建立 `framework mapping` 的自动校验和回归样板
3. 建立 `operator runbook` 与可回放审计板

### 远程探索（6 周+）

1. A2A 对外多代理协作网关
2. 多租户策略层与跨工作区治理
3. 研究型与交付型 campaign 的差异化 runtime profile

---

## 风险与反模式

1. 反模式：先堆 UI，再找真源

规避：先定 contract，再开 API，再做 UI。

1. 反模式：把外部术语直接当内部模型

规避：统一走 framework mapping 翻译层。

1. 反模式：把 observability 当 projection

规避：诊断面与产品投影面严格分层。

1. 反模式：跨层直接读私有实现

规避：只能走公开接口与合同对象。

---

## 附：一手参考来源（本轮引用）

1. LangChain Agents 官方文档
  用于 `create_agent`、`middleware`、`state_schema`、graph-based runtime 判断。  
   [https://docs.langchain.com/oss/python/langchain/agents](https://docs.langchain.com/oss/python/langchain/agents)
2. Deep Agents 官方文档
  用于 `agent harness`、planning、filesystem、subagents、memory、HITL、durable execution 判断。  
   [https://docs.langchain.com/oss/python/deepagents/overview](https://docs.langchain.com/oss/python/deepagents/overview)  
   [https://docs.langchain.com/oss/python/deepagents/subagents](https://docs.langchain.com/oss/python/deepagents/subagents)  
   [https://docs.langchain.com/oss/javascript/deepagents/harness](https://docs.langchain.com/oss/javascript/deepagents/harness)
3. LangGraph 官方文档
  用于 `State/Nodes/Edges`、Pregel super-step、persistence、interrupt/resume、time travel、subgraph、Command 语义判断。  
   [https://docs.langchain.com/oss/python/langgraph](https://docs.langchain.com/oss/python/langgraph)
4. OpenAI Agents SDK 官方文档
  用于 `Agent/Runner/Tools/Handoffs/Guardrails/Sessions/Tracing` 的对象边界判断。  
   [https://openai.github.io/openai-agents-python/](https://openai.github.io/openai-agents-python/)
5. OpenAI Codex / Harness Engineering 官方文档与文章
  用于 subagents、approval、thread/turn/item、App Server、operator harness 方法论判断。  
   [https://developers.openai.com/codex/multi-agent](https://developers.openai.com/codex/multi-agent)  
   [https://openai.com/index/harness-engineering/](https://openai.com/index/harness-engineering/)  
   [https://openai.com/index/unlocking-the-codex-harness/](https://openai.com/index/unlocking-the-codex-harness/)
6. MCP 官方文档
  用于 host/client/server、JSON-RPC 2.0 data layer、tools/resources/prompts 判断。  
   [https://modelcontextprotocol.io/docs/learn/architecture](https://modelcontextprotocol.io/docs/learn/architecture)
7. A2A 官方规范/社区文档
  用于 Agent Card、JSON-RPC over HTTP、长任务协作、外部 agent federation 判断。  
   [https://a2a-protocol.org/v0.2.4/specification](https://a2a-protocol.org/v0.2.4/specification)
8. CrewAI 官方文档
  用于 crews/flows 分离、event-driven stateful flow、human feedback、tracing 判断。  
   [https://docs.crewai.com/en](https://docs.crewai.com/en)  
   [https://docs.crewai.com/en/concepts/flows](https://docs.crewai.com/en/concepts/flows)  
   [https://docs.crewai.com/en/observability](https://docs.crewai.com/en/observability)  
   [https://docs.crewai.com/en/learn/human-feedback-in-flows](https://docs.crewai.com/en/learn/human-feedback-in-flows)
9. AgentScope 官方文档
  用于 ReAct、skills、MsgHub、memory/planning、tracing/studio 判断。  
   [https://doc.agentscope.io/tutorial/quickstart_agent.html](https://doc.agentscope.io/tutorial/quickstart_agent.html)  
   [https://doc.agentscope.io/tutorial/task_agent_skill.html](https://doc.agentscope.io/tutorial/task_agent_skill.html)  
   [https://doc.agentscope.io/tutorial/task_pipeline.html](https://doc.agentscope.io/tutorial/task_pipeline.html)  
   [https://doc.agentscope.io/tutorial/task_plan.html](https://doc.agentscope.io/tutorial/task_plan.html)  
   [https://doc.agentscope.io/tutorial/task_tracing.html](https://doc.agentscope.io/tutorial/task_tracing.html)
10. Dify 官方文档
  用于 app shell、workflow/chatflow、plugin governance、trigger、monitoring/run history 判断。  
      [https://docs.dify.ai/](https://docs.dify.ai/)  
      [https://docs.dify.ai/versions/3-7-x/en/user-guide/workflow/node/trigger/plugin-trigger](https://docs.dify.ai/versions/3-7-x/en/user-guide/workflow/node/trigger/plugin-trigger)
11. DeerFlow 官方仓库与后端文档
  用于 2.0 定位、full-stack architecture、middleware chain、thread isolation、skills/memory/subagent/gateway 判断。  
      [https://github.com/bytedance/deer-flow](https://github.com/bytedance/deer-flow)  
      [https://github.com/bytedance/deer-flow/blob/main/backend/CLAUDE.md](https://github.com/bytedance/deer-flow/blob/main/backend/CLAUDE.md)  
      [https://github.com/bytedance/deer-flow/blob/main/backend/docs/ARCHITECTURE.md](https://github.com/bytedance/deer-flow/blob/main/backend/docs/ARCHITECTURE.md)  
      [https://github.com/bytedance/deer-flow/blob/main/backend/docs/API.md](https://github.com/bytedance/deer-flow/blob/main/backend/docs/API.md)  
      [https://github.com/bytedance/deer-flow/blob/main/backend/docs/GUARDRAILS.md](https://github.com/bytedance/deer-flow/blob/main/backend/docs/GUARDRAILS.md)  
      [https://github.com/bytedance/deer-flow/blob/main/backend/docs/plan_mode_usage.md](https://github.com/bytedance/deer-flow/blob/main/backend/docs/plan_mode_usage.md)  
      [https://github.com/bytedance/deer-flow/issues/1130](https://github.com/bytedance/deer-flow/issues/1130)

---

## 最终结论

Butler 的下一步不是“换框架”，而是继续做“能力吸收工程”：

1. 用现役分层守住真源边界
2. 用映射层吸收外部成熟能力，其中 DeerFlow 更适合作为“全栈 harness 参考实现”，而不是替换性底座
3. 用 operator harness 把治理与恢复做成产品化能力
4. 用可追溯证据链确保每次升级都可复读、可验收、可回滚
