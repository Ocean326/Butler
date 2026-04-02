# 多智能体 MAS 架构实践 — 从四件套到协调治理

> **综合类型**：跨主题深度综合（Cross-cutting Synthesis）
> **母本 Insight**：
> - `20260318_10_agent_projects_架构共性_insight.md`（四件套同构 + 差异轴）
> - `20260317_xiaohongshu_multi_agent_harness_engineering_Insight.md`（MAS Harness 四层）
> - `20260318_MAS_Harness四层架构_知乎深度拆解_insight.md`（知乎长文 × 四层细节 + 经验飞轮）
> - `20260318_subagent_vs_agentteam_双引擎架构_insight.md`（SubAgent vs AgentTeam 双引擎）
> - `20260318_agent_lifecycle_harness_自律_insight.md`（Agent 生命周期 × 收敛窗口 × 退役日志）
> - `20260318_Agent下属生命周期与一人公司架构_insight.md`（五层递归委托 × 杀与留决策）
> - `20260318_Agent产品生命周期_一次性vs长期_两种范式_insight.md`（Disposable vs Persistent）
> **辅助参考**：
> - `20260318_Agent评估安全自治_OpenAI_Anthropic_2026Q1_insight.md`（Section 4: 多 Agent 协作质量）
> - `20260318_OpenAI_Codex_Harness工程范式_Agent_Runtime_insight.md`（Agent Loop + 跨端协议抽象）
> - `20260317_simon_agent_harness_insights.md`（Ralph Loop 最小 Harness 单元）
> - `20260318_agent_harness_全网调研汇总_insight.md`（Context Durability + Action Space）
> **外部补充**：2026 MAS 编排模式综述（Tacnode / Zylos / AI Workflow Lab）、协调税研究（Towards Data Science 17× 错误陷阱 / Medium 协调开销量化）
> **提炼时间**：2026-03-18
> **主题轴**：多智能体架构、编排模式、协调税、双引擎设计、Agent 生命周期、四层 Harness、统一记忆、Butler MAS 演进

---

## 一、主题概述

72% 的企业 AI 项目已采用多智能体架构（2024 年仅 23%）。但"多 Agent"不等于"好 Agent"——独立多 Agent 系统的错误放大率可达单 Agent 的 17.2 倍，42% 的执行时间被协调开销吞掉。

这个矛盾构成了 2026 年 MAS 工程的核心张力：**能力需要拆分到多个 Agent 才能覆盖复杂场景，但拆分本身带来的协调税会吃掉甚至反超收益**。

对 Butler 而言，这不是理论问题。heartbeat 已经是一个事实上的 MAS：planner 做任务分解、executor 做分支执行、sub-agent 做具体操作。问题在于这套 MAS 是"自然生长"出来的，缺少显式的协调架构、生命周期治理和统一记忆层。

本文综合 7 篇已有 Insight、4 篇辅助参考和 2026 年前沿 MAS 研究，提炼出一套从基本架构到协调治理的完整 MAS 工程框架。

---

## 二、核心观点提炼

### 1. 四件套同构是 MAS 的基石，不是 MAS 的答案

**来源**：10 个 Agent 项目共性 Insight × 四层 Harness × 2026 MAS 综述

10 个 Agent 项目拆开看，底层都是同一套四件套：

| 模块 | 职责 | Butler 对应 |
|------|------|------------|
| **LLM** | 推理引擎 | Claude 系列 |
| **Tool System** | 能力边界 | skills/ + MCP |
| **Agent Loop** | 执行循环 | heartbeat planner → executor |
| **Memory** | 状态持久化 | local_memory + task_ledger + self_mind |

但四件套只回答"一个 Agent 长什么样"，不回答"多个 Agent 怎么协作"。当任务复杂度超过单 Agent 能力时，四件套需要叠加三层 MAS 特有设计：

1. **编排层**：谁做什么、什么时候做、怎么交接
2. **协调协议**：Agent 之间如何传递上下文和产出
3. **生命周期治理**：Agent 的 spawn、convergence check、retire 三阶段管理

**关键洞察**：先把单 Agent 的四件套打磨顺滑，再按需加 MAS。10 个项目的共性告诉我们——架构骨架几乎相同，真正的差异在 Tool 生态和任务规划能力两个维度。MAS 不是跳过四件套的捷径，而是四件套成熟之后的自然延伸。

---

### 2. 五种编排模式各有适用区间，不存在银弹

**来源**：2026 MAS 编排综述（Tacnode / Zylos）× SubAgent vs AgentTeam Insight

2026 年产业实践收敛出五种主流编排模式：

| 模式 | 运作方式 | 最佳场景 | 核心风险 |
|------|---------|---------|---------|
| **层级式（Supervisor/Worker）** | 协调者拆任务 → 分派给专家 | 内容管线、报告生成 | 协调者理解偏差 → 全链路走偏 |
| **流水线（Sequential Pipeline）** | 固定顺序，每步依赖前步输出 | 文档审阅、结构化处理 | 慢；中间步骤出错阻塞全链 |
| **并行/集成（Parallel/Ensemble）** | 多 Agent 同时处理同一问题，结果聚合 | 头脑风暴、多视角推理 | 结果可能矛盾，聚合策略是瓶颈 |
| **事件驱动（Pub/Sub）** | Agent 订阅事件流 | 实时、高吞吐系统 | 事件顺序风险 |
| **对等网格（Peer-to-Peer）** | Agent 直接通信，无中心 | 高容错场景 | 调试困难；无断路器则反馈环失控 |

SubAgent vs AgentTeam 双引擎 Insight 进一步把这五种模式收缩为两大执行引擎：

- **SubAgent（工兵模式）**：进程内毫秒级启动，子代理间无直接通信，像"工具小工"—— 对应层级式和流水线
- **AgentTeam（项目组模式）**：独立进程，通过 mailbox 通信，成员间可自主分工 —— 对应并行/集成和对等网格

**关键洞察**：不是选 A 或 B，而是在同一系统中保留双引擎，按任务复杂度动态路由。简单任务走 SubAgent（快、轻、隔离），复杂任务走 AgentTeam（协作、汇总、多视角）。

**→ Butler 映射**：Butler heartbeat 当前是层级式（planner → executor 分支），接近 SubAgent 模式。当任务需要多分支并行 + 结果汇总时，已经在向 AgentTeam 模式过渡，但缺少显式的引擎路由逻辑和 branch 间通信协议。

---

### 3. 协调税是真实的物理约束，不是可忽略的开销

**来源**：协调税研究（Towards Data Science / Medium）× 知乎 Harness 深度 × 全网调研

三条硬数据彻底打碎了"多 Agent 一定更强"的直觉：

1. **17.2× 错误放大**：独立 MAS 的错误率是单 Agent 的 17.2 倍；即使中心化架构也有 4.4× 放大（Towards Data Science 2026 研究）
2. **42% 协调开销**：真实工作流中 42% 的时间花在 Agent 间协调而非实际工作上；Agent 间 handoff 延迟 2-8 秒
3. **4+ Agent 后收益递减**：当单 Agent 准确率达 45% 时，继续加 Agent 反而降低整体表现；5-7 个专家 Agent 是最优配置

知乎长文同样提到"协调税"现象：4+ agent 后收益递减甚至下降。Brooks 法则（通信路径 = n(n-1)/2）在 MAS 中同样适用。

**对抗协调税的三条策略**：

| 策略 | 做法 | 预期效果 |
|------|------|---------|
| **层级化管理** | 引入中间管理层，将 O(n²) 通信复杂度降为 O(n) | 减少 Agent 间直接通信量 |
| **handoff 标准化** | JSON Schema 校验 handoff 数据完整性，像 API 契约一样对待 | 降低信息损耗（39-70% 的性能退化源于有损 handoff） |
| **共享上下文而非共享状态** | 所有 Agent 查询同一个权威上下文层，禁止各自维护独立缓存 | 消除数据不一致和同步冲突 |

**→ Butler 映射**：Butler heartbeat 当前 branch 数量通常 2-4 个，还在安全区间内。但 branch 间的 handoff 是非结构化的文本回执——这正是"有损 handoff"的典型表现。一旦 branch 数量增加或任务链拉长，协调税会快速增长。

---

### 4. Agent 生命周期需要"招聘-考核-裁员-交接"的完整治理

**来源**：Agent 生命周期 × 一人公司 × 两种范式 × Anthropic 并行 Claude 研究

"一人公司五层构架"的实录揭示了 MAS 中被严重忽视的一面——**Agent 的生杀予夺不是边角问题，而是系统级治理问题**：

```
spawn（招聘）→ converge check（考核）→ retire / replace（裁员/换人）→ handoff（交接）
```

四个环节各有工程要求：

**spawn 阶段**：
- 每个 sub-agent 在分派时必须携带：角色定义、收敛窗口（最大等待时长）、降级策略
- 应区分 Disposable Worker（无状态、可替换）和 Persistent Partner（有记忆、有连续性）

**converge check 阶段**：
- 定时检查 sub-agent 是否在向目标收敛
- Anthropic 并行 Claude 实验表明：迭代评审循环捕获的缺陷是单次评审的 3-5 倍，但 3-4 轮后收益递减

**retire 阶段**：
- 超时后不是简单 kill → respawn，先评估"部分产出是否可回收"
- 被关闭的 agent 必须输出结构化退役日志（做了什么、卡在哪、半成品在哪）
- 失败经验是最有价值的学习信号——Dalton/Helmholtz 被 kill 后，它们"为什么没收敛"的信息不应随进程一起消失

**handoff 阶段**：
- 替代 agent（如 Kepler/Pauli）是否继承前任的上下文？
- 继承过多 → 上下文污染；继承过少 → 重复劳动
- 需要结构化的交接摘要而非全量上下文转移

**→ Butler 映射**：Butler heartbeat 的 executor 是 disposable agent，但当前处置方式粗暴——branch 超时直接丢弃，没有部分产出回收、没有退役日志、没有"是否继承上下文"的决策逻辑。这是 MAS 治理的最大缺口。

---

### 5. 四层 Harness 是 MAS 从"一堆 Agent"升级为"可治理系统"的分水岭

**来源**：Simon MAS Harness × 知乎四层架构 × 全网调研 × Codex Harness 工程

知乎长文和 Simon 系列从不同角度收敛到同一个架构——MAS 的可控性不取决于 Agent 数量，而取决于 Harness 层的完备度：

```
┌────────────────────────────────────────┐
│  知识供给层（Knowledge）                 │
│  参数化知识 / RAG / 经验知识 / 跨 agent 一致性 │
├────────────────────────────────────────┤
│  执行编排层（Orchestration）              │
│  Orchestrator / Stateful Workflow / 策略运行时 │
├────────────────────────────────────────┤
│  风险门控层（Guardrail）                  │
│  权限 / 预算 / 动作拦截 / injection 防御   │
├────────────────────────────────────────┤
│  治理运营层（Governance）                 │
│  案例库 / 失败模式库 / 协调模式库 / Dashboard │
└────────────────────────────────────────┘
```

四层的核心原则：**让知识、编排、风控、治理各自独立演进，而不是混在一个 orchestrator 里**。混在一起只会导致 "more rules, less autonomous"。

MAST 失败框架从另一个方向验证了四层设计的必要性——MAS 的三类失败根因分别对应不同层的缺陷：
- **FC1 系统设计问题** → 知识层 + 编排层缺陷
- **FC2 协调失败** → 编排层 + 门控层缺陷
- **FC3 验证缺失** → 治理层缺陷

**→ Butler 映射**：

| 四层架构 | Butler 现有对应 | 成熟度 | 差距 |
|---------|---------------|--------|------|
| 知识供给层 | skills/ + BrainStorm/ + MEMORY.md + SOUL | ★★★ | 缺跨 agent 知识一致性机制 |
| 执行编排层 | heartbeat planner → executor 分层 | ★★☆ | Workflow 和策略运行时未分离 |
| 风险门控层 | 工具白名单 + heartbeat_upgrade_request | ★☆☆ | 需升级为独立中间件层 |
| 治理运营层 | task_ledger + BrainStorm Insights | ★★☆ | 缺"执行→案例卡片→经验库"自动化流程 |

---

### 6. 统一记忆是 MAS 的粘合剂，"各自维护状态"是系统退化的起点

**来源**：SubAgent vs AgentTeam × 2026 MAS 最佳实践 × Butler 记忆架构分析

两种 Agent 模式如果各自维护独立状态，系统将退化为两套互不相干的工具集。2026 年行业共识进一步强化了这个判断：

**"共享上下文，而非共享状态"** 是最关键的 MAS 设计原则之一。每个 Agent 不应维护独立的状态缓存，而应查询同一个权威上下文层。否则会出现经典的一致性灾难——Agent A 给的定价和 Agent B 承诺的交付不一致。

在 MAS 中，记忆系统需要满足三个特殊要求：

| 要求 | 含义 | 实现路径 |
|------|------|---------|
| **跨 Agent 可读** | Agent B 能读到 Agent A 写入的关键产出 | 统一的文件系统 + 结构化索引 |
| **写入原子性** | 多 Agent 并行时不互相覆盖 | 每 Agent 写独立文件 → 汇总层合并 |
| **生命周期解耦** | Disposable Agent 退出后其产出仍可被 Persistent Agent 访问 | 产出写入持久存储而非 Agent 内存 |

**→ Butler 映射**：Butler 的 memory_manager + task_ledger 已经在充当统一记忆层的角色。但 executor 的产出（回执文本）主要存在于对话上下文中，并非结构化地持久化到文件系统——这意味着如果 executor 的回执过长或被上下文截断，下游 branch 就会丢失信息。需要让 executor 的关键产出同时落盘为持久文件。

---

### 7. 编排者不执行、执行者不编排——职责分离是 MAS 稳定性的前提

**来源**：2026 Towards AI 研究 × Agent 架构四原则 × Codex Agent Loop

"为什么你的 AI 编排者不应该写代码"——2026 年一篇广泛传播的文章直指 MAS 的常见反模式：**让 orchestrator 同时做任务分解和任务执行**。

当 orchestrator 直接参与执行时：
- 实现细节污染了它的战略推理上下文（context pollution）
- 它在执行中遇到的错误会干扰它对全局任务的判断
- 单点故障：orchestrator 卡住 = 整个系统卡住

正确的分离：
- **Orchestrator**：只做分解、分派、验收、升级——不碰具体工具调用
- **Worker**：只做执行——不自行决定任务优先级或跳过步骤
- **Reviewer（可选）**：独立于 orchestrator 和 worker 的第三方评审

**→ Butler 映射**：Butler 的 planner/executor 分离在方向上正确。但当前 planner 在"汇总"阶段实际上会做一些类似执行的事（如组织回执、决定下一轮策略），这部分逻辑可能随着复杂度增加而膨胀。值得考虑引入独立的 reviewer 角色——在 planner 汇总前、先对 executor 产出做一轮独立评审。

---

## 三、与 Butler 的映射关系总览

| MAS 维度 | 行业最佳实践 | Butler 当前状态 | 差距评级 | 改进方向 |
|---|---|---|---|---|
| 基础架构 | 四件套（LLM+Tool+Loop+Memory）打磨顺滑 | 四件套齐全 | 🟢 低 | 持续打磨 Tool 生态和规划能力 |
| 编排模式 | 双引擎（SubAgent + AgentTeam）按需路由 | 单一层级式 | 🟡 中 | 引入任务复杂度 → 引擎路由 |
| 协调开销 | 5-7 专家 Agent、结构化 handoff、共享上下文 | 2-4 branch、非结构化回执 | 🟡 中 | handoff 标准化为 JSON 契约 |
| 生命周期 | spawn + converge check + retire + handoff 四阶段 | spawn + 超时 kill | 🔴 高 | 增加收敛检查、退役日志、产出回收 |
| Harness 四层 | 知识/编排/门控/治理各自独立 | 混合在 planner/executor 中 | 🔴 高 | 显式标注每个模块所属层 |
| 统一记忆 | 共享上下文层、产出持久化 | task_ledger + 对话上下文 | 🟡 中 | 关键产出同时落盘为文件 |
| 职责分离 | 编排者不执行、执行者不编排 | planner/executor 基本分离 | 🟢 低 | 考虑引入独立 reviewer |

---

## 四、可执行启示（按优先级排序）

### P0：branch handoff 标准化

**做什么**：为 heartbeat branch 之间的信息传递定义结构化契约——

```json
{
  "from_branch": "branch_id",
  "artifacts": [
    {"type": "file", "path": "工作区/xxx.md", "summary": "一句话描述"},
    {"type": "conclusion", "content": "关键结论文本"}
  ],
  "context_for_next": "下游 branch 需要知道的最小上下文",
  "warnings": ["已知风险或不确定性"]
}
```

**为什么优先**：39-70% 的 MAS 性能退化源于有损 handoff。Butler branch 之间的信息传递当前是非结构化文本，是可预见的第一瓶颈。

**落地路径**：先在 heartbeat 协议文档中以 Markdown 模板形式引入，executor 按模板格式化回执；不改代码。

### P1：退役日志 + 部分产出回收

**做什么**：heartbeat branch 失败或超时时，自动生成结构化退役日志——

```
- branch_id: xxx
- goal: 原始目标
- reached: 走到了哪一步
- failure_reason: 根因分类（FC1 设计/FC2 协调/FC3 验证）
- partial_output: 半成品路径
- reusable: 新 branch 是否应继承上下文（yes/no + 理由）
```

**为什么重要**：失败 branch 的经验是最有价值的学习信号。当前 Butler 对失败 branch 的处理是"静默丢弃"。

**落地路径**：在 executor 回执协议中增加 `retirement_log` 字段（仅失败/超时时填写）。退役日志可同时追加到 `工作区/mas_retirement_logs.md` 做经验积累。

### P2：任务复杂度 → 引擎路由

**做什么**：在 heartbeat planner 的任务评估阶段，增加一个轻量的复杂度判断——

| 复杂度 | 特征 | 路由 |
|--------|------|------|
| 低 | 单文件操作、单次查询、单步执行 | 直接走单 executor branch（SubAgent 模式） |
| 中 | 跨 2-3 文件、需对比/汇总 | 2-3 branch 并行 + planner 汇总 |
| 高 | 跨多领域的研究整理、需多角色协作 | 多 branch + branch 间交叉传递 + 独立评审 |

**为什么重要**：避免对简单任务过度编排（浪费协调税），也避免对复杂任务编排不足（质量不够）。

**落地路径**：在 planner prompt 中增加"复杂度评估"环节，输出 `complexity: low/medium/high`，然后按对应模板分派 branch。

### P3：四层 Harness 映射文档

**做什么**：在 Butler 架构文档中新增一节"四层 Harness × Butler 模块映射"，显式标注：

| Butler 模块 | Harness 层 | 职责边界 |
|------------|-----------|---------|
| skills/ + BrainStorm/ + MEMORY.md | 知识供给层 | 提供知识资产，不做执行决策 |
| heartbeat planner + 分支管理 | 执行编排层 | 任务分解与分派，不直接执行 |
| heartbeat_upgrade_request + 工具白名单 | 风险门控层 | 审批与拦截，与编排逻辑解耦 |
| task_ledger + Insights + 退役日志 | 治理运营层 | 经验沉淀与回溯，不干预运行时 |

**为什么重要**：后续所有新能力都应声明自己挂在哪一层，避免职责混在一起导致 "more rules, less autonomous"。

**落地路径**：写入 `butler_bot_agent/agents/docs/AGENTS_ARCHITECTURE.md` 或独立文档。

---

## 五、Butler MAS 演进路径

```
阶段 0（当前）
  单 Agent 四件套 + heartbeat 层级式编排
  → "有 MAS 雏形，但缺显式治理"

阶段 1（近期可达）
  + branch handoff 标准化 + 退役日志 + 复杂度路由
  → "结构化的 SubAgent MAS"

阶段 2（中期目标）
  + 双引擎路由 + 四层 Harness 分离 + 经验飞轮启动
  → "可治理的混合编排 MAS"

阶段 3（长期愿景）
  + 自组织团队 + 跨平台 Agent 协作（A2A/MCP）
  → "自适应 MAS"
```

Butler 当前处于阶段 0 → 1 的过渡期。P0-P1 两个改进可以在不改核心代码的前提下（通过修改 heartbeat 协议文档和 prompt）落地。

---

## 六、一句话带走

> 多 Agent 的价值不在于"更多 Agent"，而在于"更好的协调"。Butler 已有 MAS 雏形，**branch handoff 标准化和退役日志**是从"自然生长的 MAS"走向"可治理的 MAS"的两个最小可行改进——前者降低信息损耗，后者将失败转化为学习信号。

---

## 主题标签

`#多智能体` `#MAS架构` `#编排模式` `#协调税` `#双引擎` `#SubAgent` `#AgentTeam` `#生命周期治理` `#四层Harness` `#统一记忆` `#HandoffProtocol` `#退役日志` `#Butler架构演进` `#跨主题综合`
