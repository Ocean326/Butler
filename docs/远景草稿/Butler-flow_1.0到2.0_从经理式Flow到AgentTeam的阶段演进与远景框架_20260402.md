# Butler-flow 1.0 到 2.0：从经理式 Flow 到 Agent Team 的阶段演进与远景框架

- 日期：2026-04-02
- 文档类型：远景草稿 / 概念学习资料 / Butler 开发参考
- 适用范围：**仅 Butler-flow 这条线**
- 当前定位：用于明确 `1.0` 与 `2.0` 的阶段边界，不讨论细节实现，不替代阶段性开发计划

---

## 0. 这份文档要解决什么问题

Butler-flow 当前已经从“单 agent + 工具调用”的形态，推进到一个更接近 **flow-first workbench** 的系统：

- 有 `mission / node / branch / workflow_ir / workflow_session`
- 有 `role_bindings / workflow_template / verification / approval / recovery`
- 有 `shared_state / artifact_registry / collaboration / mailbox / handoff / join_contract`
- 有 `supervisor` 作为顶级 flow 主体
- 有 child session / child agent / run 的层级表达

但这并不自动等于“真正的 agent team”。

因此，Butler-flow 接下来需要明确两个阶段：

1. **1.0 阶段**：把桌面端 + TUI + 成熟可靠的经理式 flow 做扎实，确保中长任务稳定推进。
2. **2.0 阶段**：在 1.0 之后，再推进真正的 agent team 形态，让系统从“经理主导的 flow 编排”逐步演进到“全局监督 + 局部自治”的 team-native runtime。

这份文档的目标，就是把这两个阶段之间的 **概念边界、过渡形态、学习框架、Butler 远景方向** 说清楚。

---

## 1. 一句话总判断

### 1.1 当前 Butler-flow 的准确定位

当前 Butler-flow 更准确的定位不是“真正的 agent team”，而是：

> **supervisor-led flow orchestration + team-capable session substrate**

也就是：

- 上层仍然是 **supervisor 主导的 flow 编排**
- 底层已经开始具备 **走向 team 协作的 session 容器与协作骨架**

这意味着：

- 你已经明显超过“单 agent + sub-agent”的阶段
- 你不是从 0 开始做 team
- 你差的不是“再多几个 agent”
- 你差的是：

> **把协作能力从“可展示、可记录的 metadata”，升级成真正驱动运行时推进的机制。**

### 1.2 1.0 与 2.0 的核心分界

可以先用一句最简短的话概括：

- **1.0**：成熟可靠的经理式 flow
- **2.0**：真正具备局部自治与协作协议驱动的 agent team

---

## 2. Butler-flow 1.0 与 2.0 的阶段边界

## 2.1 1.0：成熟可靠的经理式 Flow

### 1.0 的一句话定义

**Butler-flow 1.0 = 以 supervisor 为主 flow、以 manager 为创建入口、以桌面端 + TUI 为工作台表达的成熟可靠经理式 flow 系统。**

### 1.0 的核心目标

1. 桌面端与 TUI 都能稳定承载 flow 工作台
2. Flow-first 的命名、对象、视图表达彻底站稳
3. supervisor 能稳定推进中长任务
4. branch / session / artifact / approval / runtime 的结构化表达清晰
5. 中长任务可以在经理式模式下稳定运行、可恢复、可验收、可追踪

### 1.0 的关键词

- flow-first
- supervisor
- manager
- child session / child agent / run
- contracts
- runtime transparency
- structured observation
- durable medium-length task execution

### 1.0 不追求什么

1. 不追求真正意义上的 team-native runtime
2. 不追求局部小组的完全自治
3. 不追求节点之间复杂的协作协议自动驱动
4. 不追求把所有 child 都变成独立 team
5. 不追求多层 supervisor 嵌套

### 1.0 最适合解决什么问题

- 一项任务需要中长时间推进
- 需要 supervisor 持续规划和收口
- 需要有 child session / artifact / approval / status 可视化
- 需要桌面和 TUI 两种工作方式
- 需要产品级的 flow 工作台体验

### 1.0 的风险提醒

1. 若继续把所有局部动作都压给顶层 supervisor，容易形成单点瓶颈
2. 若 flow UI 退化回 agent UI，会模糊系统边界
3. 若把 1.0 的目标误解成“现在就做真正 team”，会导致系统复杂度失控

---

## 2.2 2.0：从经理式 Flow 走向真正 Agent Team

### 2.0 的一句话定义

**Butler-flow 2.0 = 在保留 global supervisor 的前提下，引入自治小组（cell / pod）与局部协议调度，使协作能力成为运行时真源的系统。**

### 2.0 的核心目标

1. 仍保留全局 supervisor 负责总目标、跨组协调、对外汇报、预算与验收门
2. 把复杂子 flow 升级成可自治推进的 cell
3. 让 mailbox / handoff / join contract / ownership / shared state 真正参与调度
4. 让局部 acceptance / recovery / retry 在 cell 内闭环
5. 让系统从“中心化逐个 dispatch”过渡到“全局监督 + 局部自治”

### 2.0 的关键词

- global supervisor
- autonomous cell
- local protocol runtime
- mailbox
- handoff
- join contract
- step ownership
- ready set
- local recovery / local acceptance

### 2.0 与 1.0 最本质的区别

1. **1.0 中**：推进主语仍然是 supervisor
2. **2.0 中**：推进主语逐步转向 cell 内的协作协议

换句话说：

- 1.0 的 child 更像被管理的执行单元
- 2.0 的 child 更像自治小组

---

## 3. 从“经理式 + 逐个调用”到“真正 Agent Team”的中间形态

下面这部分，是理解 Butler 远景最重要的框架之一。

---

## 3.1 形态 A：单经理 + 工具调用

### 特征
- 一个主 agent
- 通过 tools/function calling 扩展能力
- 所有认知与决策都压在一个 prompt 里

### 优点
- 简单
- 成本低
- 容易起步

### 缺点
- 上下文容易膨胀
- 复杂任务很快失控
- 难以长期维护

### 对 Butler 的意义
这是已经越过的阶段，不再是主方向。

---

## 3.2 形态 B：经理 + sub-agents / specialist workers

### 特征
- 主 agent 负责理解与总控
- specialist agent 负责专项任务
- specialist 主要向主 agent 汇报，不构成真正组织关系

### 优点
- 上下文隔离更好
- 可做专项 prompt
- 并行能力增强

### 缺点
- 本质仍是中心化
- specialists 之间通常不直接协作
- 对长任务仍容易由主 agent 过载

### 对 Butler 的意义
Butler 也已明显超过这一阶段，因为当前不只是调用几个专家 agent，而已经有了 workflow_session、contracts、collaboration 等结构。

---

## 3.3 形态 C：经理 + 多节点 workflow

### 特征
- 顶层 manager / supervisor 维护任务真源
- 将任务拆成 node / branch
- 通过状态、路由、模板、契约推进执行

### 优点
- 结构化强
- 适合产品化表达
- 很适合 flow-first 工作台

### 缺点
- 如果所有推进都要回顶层决策，容易瓶颈化
- 容易成为“中心化 workflow machine”

### 对 Butler 的意义
当前 Butler-flow 已经处于这一阶段的中高位。

---

## 3.4 形态 D：经理 + 多节点 workflow + team-capable session

### 特征
在形态 C 基础上，开始出现：

- shared state
- artifact registry
- mailbox
- handoff
- join contract
- role bindings
- collaboration summary

### 优点
- 为 team 协作提供底层载体
- 可从“节点执行”走向“角色协作”
- 支持长时任务与局部自治的前置条件

### 缺点
- 如果这些东西只是 metadata，就还不是真 team
- 需要把 collaboration 提升为调度真源

### 对 Butler 的意义
当前 Butler-flow 已经开始进入这个阶段。

也正因为如此，Butler 的问题不再是“能不能做 team”，而是：

> **什么时候、以什么方式，把 team 形态从远景概念推进到真正 runtime。**

---

## 3.5 形态 E：global supervisor + autonomous cells

### 特征
- 顶层保留一个 global supervisor
- 每个复杂子 flow 变成一个自治 cell
- cell 内由轻量协议推进，而不是再套一个重型 supervisor

### 优点
- 避免 supervisor 一层套一层
- 局部问题局部闭环
- 更适合长任务
- 顶层只看 milestone，不管每一步细节

### 缺点
- 需要更成熟的协议设计
- 需要显式定义 ready / ownership / handoff / join / retry / stop 条件

### 对 Butler 的意义
这是 2.0 最值得追求的目标形态。

---

## 3.6 形态 F：真正的 team-native runtime

### 特征
- global supervisor 只负责全局治理
- 组内顺序由协议与事件驱动
- collaboration state 成为运行真源
- 局部 acceptance / recovery / retry 闭环成立

### 优点
- 真正适合长时自动完成任务
- 更接近成熟的 agent team
- 不再完全依赖中心化逐个调度

### 缺点
- 设计复杂度高
- trace / replay / evaluation 更难
- 需要更强的 runtime discipline

### 对 Butler 的意义
这是中长期方向，但不应在 1.0 阶段硬上。

---

## 4. 为什么 1.0 不应该急着直接做“真正 team”

这是很重要的阶段裁决。

### 4.1 因为 1.0 当前最重要的是把 flow 工作台做扎实
Butler-flow 当前最重要的是：

- 对象表达清晰
- 运行状态清晰
- runtime 可见
- artifact / approval / child drill-down 清晰
- 桌面端与 TUI 工作台都可靠可用

这些是 1.0 的真正主线。

### 4.2 因为中长任务的稳定推进，不必然需要真正 team
一个成熟可靠的经理式 flow 系统，已经足以完成大量中长任务。只要它具备：

- supervisor 稳定推进
- child session 明确
- contracts 明确
- runtime 透明
- recovery / acceptance 稳定

那么它就足以成为一个非常有价值的 1.0。

### 4.3 因为过早做真正 team，容易在 1.0 阶段把系统搞散
过早引入真正 team，通常会带来：

- 协作状态复杂化
- tracing 复杂化
- 调试复杂化
- 人机交互复杂化
- 顶层边界模糊化

这对 1.0 并不划算。

---

## 5. 真正的 agent team 与经理式 flow 的本质区别

### 5.1 经理式 flow
推进逻辑更像：

- supervisor 观察状态
- supervisor 规划下一步
- supervisor 派发 child
- child 返回结果
- supervisor 综合与收口

也就是：

> **推进主语是 supervisor。**

### 5.2 真正 agent team
推进逻辑更像：

- 全局 supervisor 给目标与边界
- cell 内角色基于协议自推进
- mailbox / handoff / join contract / ownership 决定下一步谁 ready
- 局部问题在 cell 内闭环
- 只有重要 milestone 再上浮给 global supervisor

也就是：

> **推进主语转移到局部协作协议。**

### 5.3 最凝练的区别

- **经理式 flow**：监督者驱动推进
- **agent team**：协作协议驱动推进

---

## 6. 组内自治时，节点先后顺序该怎么决定

这部分是 2.0 规划的关键理论基础。

成熟系统里，组内顺序通常不是：

- 谁级别高谁先说
- 谁模型强谁先跑
- 单纯固定死的 DAG
- 让 LLM 临场拍脑袋决定

更成熟的做法是：

> **依赖 + 事件 + 契约 + ready set 排序**

### 6.1 依赖顺序
谁具备了必要输入、artifact、前置结果，谁才有资格 ready。

### 6.2 事件顺序
谁被 mailbox、handoff、test fail、artifact create 等事件激活，谁进入 ready 集。

### 6.3 契约门槛
不是“前一步 done”就一定推进，而是：

- entry contract 满足了吗？
- join contract 满足了吗？
- approval gate 开了吗？
- recovery gate 是否触发？

### 6.4 ready set 内的优先级排序
当多个节点同时 ready 时，再按策略选谁先跑。例如：

- critical-path first
- risk-first
- information-gain first
- cheap-test first
- staleness/deadline first

### 6.5 为什么这对 Butler 重要
因为 Butler 当前已经有：

- role_bindings
- workflow_template
- verification / approval / recovery
- workflow_session
- collaboration summary
- mailbox / handoff / join contract 的语义基础

所以 Butler 未来不需要从零构造“组内自治理论”，而是要把现有这些对象，逐渐变成真正参与运行时推进的依据。

---

## 7. 为什么不建议“supervisor 套 supervisor”

如果未来复杂任务默认继续往下叠 supervisor，会出现几个典型问题：

### 7.1 汇报链太长
每层都要重新总结、重建上下文、再解释一次任务，成本很高。

### 7.2 局部问题被升级成全局问题
很多本来 tester / implementer 在组内能闭环的问题，最后都变成上层重规划问题。

### 7.3 上层容易成为单点瓶颈
随着 child 越来越多，global supervisor 的认知负担会指数上升。

### 7.4 语义容易漂移
一层层 summary / 汇报 / 重规划，很容易让系统在长任务中逐渐跑偏。

### 7.5 对 Butler 的阶段裁决
因此，Butler 的更优方向不是“supervisor + supervisor + supervisor”，而是：

> **global supervisor + 若干自治小组 + 组内协议推进**

但这件事放在 **2.0**，而不是 1.0。

---

## 8. Butler 1.0 的推荐目标结构

### 8.1 全局结构

Butler-flow 1.0 更适合收束成：

- manager：作为 template 选择与 flow 创建入口
- supervisor：作为主 flow 主体与对外工作台中心
- child sessions / child agents / runs：作为结构化执行与展示单元
- desktop + TUI：作为双工作台表达

### 8.2 1.0 的产品关键词

- flow list
- supervisor 主 session
- child card
- active children tray
- detail drawer
- runtime transparency
- contracts
- artifacts
- approvals
- flow drill-down

### 8.3 1.0 的架构关键词

- flow-first
- manager entry
- supervisor-led orchestration
- stable runtime
- observation / control surface
- desktop + TUI 双轨

### 8.4 1.0 的成功标准

- 能稳定完成中长任务
- supervisor 推进链路清晰
- child session / child agent / artifact / approval 结构清晰
- runtime / route / contracts / events 可见
- 桌面端和 TUI 都可以成为可靠工作台

---

## 9. Butler 2.0 的推荐目标结构

### 9.1 顶层：Global Supervisor
职责：

- 维护全局目标
- 阶段切换
- 跨组协调
- 对用户同步进度
- 管预算 / 超时 / 人机接管 / 最终验收门

### 9.2 中层：Autonomous Cells
典型 cell：

- research cell
- recovery cell
- delivery cell
- evaluation cell

每个 cell：

- 有局部 shared state
- 有 mailbox / handoff / join contract
- 有局部 acceptance / retry / repair
- 对外只暴露 milestone / risk / outputs

### 9.3 底层：Role Agents
典型角色：

- analyzer
- implementer
- tester / critic
- synthesizer / reporter
- recovery
- acceptance

### 9.4 2.0 的关键转折
真正的 2.0，不是“多了更多 child agent”，而是：

> **局部小组的推进，不再主要依赖 global supervisor 每步派工，而是由 cell 内部协议和状态驱动。**

---

## 10. 开源项目与技术脉络给 Butler 的启发

下面这部分不是为了“照抄框架”，而是为了建立学习坐标。

---

## 10.1 OpenAI Swarm

### 代表意义
- 极简 agent primitive
- handoff 作为核心协作原语
- coordination and execution lightweight / controllable / testable

### 对 Butler 的启发
- 适合借鉴“handoff 作为原语”的思路
- 但不适合作为 Butler 长时复杂 flow 的终局形态
- 更像是“从 manager 式系统走向多 agent”的轻量中间层

---

## 10.2 OpenAI Agents SDK

### 代表意义
- agents / handoffs / guardrails / tools / sessions / tracing
- 更 production-ready 的多 agent workflow 框架

### 对 Butler 的启发
- session
- tracing
- human-in-the-loop
- guardrails

这些都说明：真正成熟系统的重点不只是“多 agent”，而是：

- 会话
- 追踪
- 人机介入
- 运行边界

---

## 10.3 Microsoft AutoGen

### 代表意义
- Core API / AgentChat / Extensions 分层
- event-driven agents
- local/distributed runtime

### 对 Butler 的启发
AutoGen 最值得学的不是“群聊”，而是：

> **多 agent 需要分层 runtime，而不是所有能力都混在一个大框架里。**

---

## 10.4 LangGraph

### 代表意义
- long-running
- stateful
- durable execution
- human-in-the-loop
- memory
- tracing / deployment

### 对 Butler 的启发
如果 Butler 追求的是长期任务与可靠运行，那么：

> **长时 agent 系统首先是状态机与持久化执行系统。**

---

## 10.5 LangChain Deep Agents

### 代表意义
- batteries-included harness
- planning
- sub-agents
- filesystem / shell / context management

### 对 Butler 的启发
Butler 不只是做 runtime，也需要逐渐形成：

- planning
- context management
- sub-agent harness
- 文件与执行环境边界

这说明“工作台 / harness 层”同样重要。

---

## 10.6 CrewAI

### 代表意义
- Crews = 自治协作
- Flows = 精确控制
- 强调 Crews 与 Flows 可以组合

### 对 Butler 的启发
这和 Butler 的阶段划分非常贴近：

- 1.0 更接近 **Flow** 的成熟化
- 2.0 更接近 **Flow 之上容纳 Crews / cells**

也就是说：

> **自治靠 team / crews，可靠生产控制靠 flows。**

---

## 10.7 Proma

### 代表意义
- 本地优先桌面工作台
- Chat / Agent / Agent Teams / Skills / MCP 的产品组合
- 团队运行状态可视化

### 对 Butler 的启发
Proma 更值得 Butler 学的，不一定是 runtime，而是：

- 工作台表达层
- 右侧活动区 / 状态区
- 桌面端本地优先体验
- agent / teams 的产品可视化方式

---

## 10.8 Codex CLI

### 代表意义
- 本地 coding agent
- CLI / app / IDE 三形态
- 会话式工作流表达

### 对 Butler 的启发
对 Butler-flow 1.0 来说，Codex 这类产品很适合作为：

- TUI / desktop workbench 的参考
- 流式执行反馈的参考
- coding task 工作台体验的参考

---

## 10.9 The AI Scientist

### 代表意义
- 长链科学研究任务
- 模板化
- 自动实验 / 写作 / review 链条
- sandbox / containerization 意识

### 对 Butler 的启发
这类系统提醒 Butler：

- 长时自动任务不只是“多 agent”
- 还包括模板、环境、review、风险、收口

对于未来 2.0 尤其重要。

---

## 11. Butler 1.0 -> 2.0 的远景主线

## 11.1 1.0 的主线

> **把 flow 工作台做成熟，把 supervisor 主导的中长任务推进做可靠。**

重点放在：

- desktop + TUI
- flow-first 表达
- manager / supervisor 边界
- child drill-down
- contracts / runtime / artifacts / approvals
- 中长任务稳定执行

## 11.2 2.0 的主线

> **在 flow 成熟基础上，引入全局监督 + 局部自治，让 collaboration 成为 runtime truth。**

重点放在：

- autonomous cells
- mailbox / handoff / join contract
- local ready set
- local acceptance / local recovery
- role ownership
- team-native runtime

## 11.3 最核心的阶段原则

### 1.0 不越界
不要在 1.0 阶段就把系统拉到真正 team-native runtime。

### 2.0 不推翻 1.0
2.0 不是推翻经理式 flow，而是建立在 1.0 之上的升级。

### 正确关系
不是：

- flow 错了，team 才是对的

而是：

- **flow 是控制面基础**
- **team 是 2.0 的协作组织升级**

---

## 12. 最终收束

### 12.1 对当前系统的定位
当前 Butler-flow 已经不是普通 agent shell，而是一个 **flow-first orchestrator / workbench**。

### 12.2 对 1.0 的定位
1.0 的任务不是“抢跑做真正 team”，而是：

> **把桌面端 + TUI + 成熟可靠的经理式 flow 做出来，用它稳定完成中长任务。**

### 12.3 对 2.0 的定位
2.0 的任务才是：

> **在保留 global supervisor 的前提下，把复杂 child flow 升级成自治 cell，让局部协作协议成为推进主语。**

### 12.4 对 Butler 的一句建议

> **先把 1.0 做成可靠的 flow OS，再把 2.0 做成真正的 team runtime。**

也就是说：

- 1.0 先站稳经理式 flow
- 2.0 再迈向真正 agent team

---

## 13. 建议与本草稿配套阅读的方向

1. `docs/daily-upgrade/0402/` 中 Butler-flow 当日文档
2. `docs/project-map/` 中当前真源与分层地图
3. `docs/runtime/WORKFLOW_IR.md`
4. 各类 agent framework / harness / flow 系统的开源项目与官方技术博客

本稿用于远景判断，不替代具体阶段开发计划。