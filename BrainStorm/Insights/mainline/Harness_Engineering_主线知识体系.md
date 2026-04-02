# Harness Engineering：Agent 工程的核心战场

> **主线定位**：这是 BrainStorm 中素材最密集的一条主线，整合了 12+ 篇 Raw/Working/Insight 文件 + 网络最新信息。目标是从零散帖子中提炼出一份可系统学习的知识体系。
>
> **整合来源**：小红书 Simon 系列、知乎 sunnyzhao 深度拆解、OpenAI 官方 3 篇工程博客、LangChain 实战、全网调研汇总、Dior Debby 一人公司案例

---

## 一、什么是 Harness Engineering

### 1.1 一句话定义

**模型是马，Harness 是缰绳。** 马决定往哪跑、跑多快，Harness 负责把力安全传导到车上、防止脱轨。在 AI 系统中，模型是推理引擎，Harness 是模型之外的一切——工具调度、上下文压缩、安全护栏、状态持久化、可观测性——与推理逻辑严格解耦。

### 1.2 为什么 2026 年它成了核心战场

- **Philipp Schmid 预判**："如果 2025 年是 Agent 元年，**2026 年将围绕 Agent Harness 展开**。"
- **Martin Fowler 定义**：Harness Engineering 聚焦于 AI 系统的**控制与引导**，强调**安全性和可预测性**。
- **模型是大宗商品，Harness 才是竞争壁垒**：OpenAI 用 Codex Agent 在 5 个月内写了 100 万行代码、0 行手工代码，3 名工程师起步——效率提升 10 倍的关键不是更强的模型，而是更好的 Harness。
- **LangChain 实证**：仅改 Harness、不换模型，在 Terminal Bench 2.0 上从 Top 30 跳到 Top 5（52.8% → 66.5%，+13.7pp）。

### 1.3 正式的四项功能（OpenAI 三大支柱框架的扩展）

| 功能 | 说明 |
|------|------|
| **Correct** | 在 Agent 出错时纠正 |
| **Verify** | 验证执行结果正确性 |
| **Inform** | 告诉 Agent 该做什么（上下文、目标、约束） |
| **Constrain** | 限制 Agent 能做什么（权限、工具白名单、预算） |

---

## 二、MAS Harness 四层架构（核心框架）

来源：知乎 sunnyzhao「multi-agent 系统 Harness Engineering 架构设计实践与思考」——所有素材中结构最完整的框架。

```
┌──────────────────────────────────────────┐
│  Layer 4: 治理运营层 (Governance)         │
│  ├ 任务案例库 / 协调模式库 / 失败模式库  │
│  └ 运行时观察仪表盘                      │
├──────────────────────────────────────────┤
│  Layer 3: 风险门控层 (Risk Guardrail)     │
│  ├ 权限/预算控制                         │
│  ├ 工具白名单/黑名单                     │
│  ├ Prompt 注入防御                       │
│  └ 数据合规检查                          │
├──────────────────────────────────────────┤
│  Layer 2: 执行编排层 (Orchestration)      │
│  ├ Orchestrator + Planner + Router       │
│  ├ 有状态工作流 (Stateful Workflow)       │
│  └ 策略运行时 (Policy Runtime)           │
├──────────────────────────────────────────┤
│  Layer 1: 知识供给层 (Knowledge Supply)   │
│  ├ 参数知识: 模型权重/世界知识            │
│  ├ 非参数知识: RAG / 文档 / 配置 / 代码  │
│  └ 经验知识: 工作流 / Playbook / 案例库  │
└──────────────────────────────────────────┘
```

### 2.1 Layer 1 — 知识供给层

三类知识：
- **参数知识**（Parametric）：模型权重中的世界知识
- **非参数知识**（Non-parametric）：RAG、文档仓库、配置、代码库、Wiki
- **经验知识**（Experiential）：工作流、Playbook、最佳实践、案例库

核心原则：**让隐性知识显性化**，使 MAS 能理解业务边界和领域语言。跨 Agent 的知识一致性治理是必须的。

### 2.2 Layer 2 — 执行编排层

三个子组件：**编排器 + 有状态工作流 + 策略运行时**。

决定：谁做什么、什么顺序、交接如何进行。将单 Agent 的"一长串对话"升级为多 Agent 的有状态工作流。

关键原语：Planner / Router / Orchestrator / SubAgents / Skills / Handoffs

### 2.3 Layer 3 — 风险门控层

**独立于编排层的安全中间件**——不嵌入单个 Agent 中。

核心原则：**MAS 越强大，Harness 越重要。** 门控层必须与编排层解耦，降低迭代耦合风险。

### 2.4 Layer 4 — 治理运营层

三大资产库：
1. **任务案例库**（Task Case Library）
2. **协调模式库**（Coordination Pattern Library）
3. **失败模式库**（Failure Pattern Library）

核心问题：**系统是越跑越强，还是越跑越乱？** 治理层把日志转化为可复用的经验资产。

### 2.5 关键反模式

> **把四层混进一个编排器** → "规则越多、自主性越差"。

---

## 三、经验飞轮（Experience Flywheel）

三阶段演进路径——Harness 的**长期护城河**：

| 阶段 | 重点 | 标志 |
|------|------|------|
| **Stage 1: 闭环** | 完整记录和可追溯，不急着做自适应调度 | 每次执行有结构化回执 |
| **Stage 2: 经验反馈** | 编排器和门控层开始引用历史成功路径、自动推导规则 | 开始有"这类任务走路径 A 成功率更高" |
| **Stage 3: 飞轮成型** | 新任务越来越多地受益于历史经验，"越跑越强" | 经验资产跨模型升级存活 |

**为什么这是护城河**：任务级案例库、协调模式、失败模式只能从真实运行中积累——投入时间越长，优势越大。这些资产**不随模型换代而丢失**。

---

## 四、Agent Loop — OpenAI Codex 工程实践

### 4.1 Agent Loop 的四个原子步骤

来源：OpenAI「Unrolling the Codex agent loop」(2026-01-23)

```
 ┌─────────────────────────────────────┐
 │  1. Model Reasoning                 │
 │     基于当前上下文决定下一步        │
 │              ↓                      │
 │  2. Tool Definition & Invocation    │
 │     指定工具接口和参数              │
 │              ↓                      │
 │  3. Result Injection                │
 │     将工具输出注入下一轮上下文      │
 │              ↓                      │
 │  4. Re-planning                     │
 │     基于结果修订计划或决定终止      │
 │              ↓                      │
 │         (回到 1)                    │
 └─────────────────────────────────────┘
```

**关键认知**：Agent 不是一个 Prompt，而是一个**循环执行系统**。Prompt 只是其中一个组件。

### 4.2 Ralph Loop 模式

每轮获得**新鲜上下文** + 文件持久化的进度 + 自动验收检查。使用 guardrails 和 checkpoints 代替无限累积的对话历史。

**最小 Harness 单元**：接收长任务 → 拆分为幂等的多次尝试循环 → 每步通过 Git/文件系统保留轨迹。

### 4.3 Codex App Server 架构

来源：OpenAI「Unlocking the Codex harness」(2026-02-04)

**双向 JSON-RPC 协议**，统一服务 CLI / VS Code / Web / Desktop / JetBrains / Xcode：

四大组件：
1. **Stdio reader** — 处理传入 JSON-RPC 消息
2. **Codex message processor** — 将客户端请求翻译为核心操作
3. **Thread manager** — 每个 thread 管理一个核心 session
4. **Protocol design** — 基于对话原语

三层对话原语：
- **Item**（原子单元）：用户消息 / Agent 消息 / 工具执行 / 审批请求 / Diff → 生命周期：started → delta → completed
- **Turn**（轮次）：由一次用户输入触发的一组 Items
- **Thread**（会话）：持久容器，支持创建、恢复、分叉、归档

**设计选择**：拒绝了 MCP，选择自定义 JSON-RPC，因为 Agent 交互需要结构化动作序列而非简单的请求/响应。

### 4.4 五项 Agent-First 开发工程活动

来源：OpenAI「Harness engineering」(2026-02-11)

| 活动 | 说明 |
|------|------|
| **Repository Knowledge** | 让 Agent 理解代码库结构、约定和上下文 |
| **Agent Legibility** | 让 Agent 行为对人类可读、可审计 |
| **Architectural Constraints** | 通过约束而非指令引导输出 |
| **Merge Philosophy** | Agent 产出进主分支的质量门控 |
| **Entropy Governance** | 对抗 Agent 持续输出导致的代码熵增 |

核心范式转变：人类角色从"写代码"转向**设计环境 + 表达意图 + 构建反馈循环**。

---

## 五、LangChain 实战：Harness 优化的具体方法

来源：LangChain 博客「Improving Deep Agents with harness engineering」(2026)

### 5.1 效果数据

在 Terminal Bench 2.0（89 个任务，覆盖 ML / Debug / 生物学等领域）上：
- 仅改 Harness，**同一模型从 52.8% → 66.5%**（+13.7pp）
- 排名从 Top 30 → Top 5

### 5.2 三个优化抓手

| 抓手 | 具体做法 |
|------|---------|
| **System Prompt** | 精心设计的系统提示，而非堆砌说明 |
| **Tools** | 任务相关工具精选，而非工具越多越好 |
| **Middleware** | 围绕模型和工具调用的 hooks：自验证循环、循环检测、上下文工程 |

### 5.3 关键技术

- **自验证循环**（Self-verification loops）：完成前跑 pre-completion checklist
- **上下文工程**（Context engineering）：启动时映射目录结构，让 Agent 理解项目全貌
- **循环检测**（Loop detection）：防止 Agent 反复编辑同一文件（"doom loops"）
- **推理三明治**（Reasoning sandwich）：规划/验证用高推理模型，实现用中等推理模型
- **自动化 trace 分析**：spawn 并行 error-analysis agents 来合成发现并建议改进

### 5.4 工具链

- **LangSmith**：trace 和调试
- **Harbor**：编排框架
- **Daytona**：隔离沙箱运行环境

---

## 六、上下文持久性——新瓶颈

### 6.1 上下文腐烂（Context Rot）

- 上下文越长，性能越不稳定
- 关键信息被埋在中段（"Lost-in-the-middle" 现象）
- 需要上下文工程 + 分段重启

### 6.2 Schmid 判断

> "训练和推理环境正在趋同；新瓶颈是**上下文持久性**；**Harness 将成为对抗模型漂移的主要工具**。"

具体策略：
- 上下文新鲜度评分（freshness scoring）
- 关键上下文衰减时主动持久化
- 保留最近 2 轮 + 长期记忆，压缩中间轮次

### 6.3 OpenAI 的上下文压缩机制

Agent Runtime = 完整计算环境（Shell + 容器工作区 + 网络访问控制 + Skills），当对话过长时自动触发 **Context Compaction**。

---

## 七、Agent 生命周期管理

来源：小红书 Dior Debby「五层一人公司」案例 + MAST 失败框架

### 7.1 核心观察

真实 MAS 行为：Agent 产生子 Agent（Dalton, Helmholtz），给它们命名，等 5 分钟，因不收敛而杀掉，再产生新的（Kepler, Pauli）。**这不是 Bug，这是自然 MAS 模式。**

### 7.2 Kill vs Keep 决策框架

成熟 Harness 需要：
- **收敛窗口**：产生时分配最大等待时间 + 中间检查点
- **降级策略**：评估"部分输出能否抢救？"和"新 Agent 应该继承上下文还是从头开始？"
- **退役日志**：被杀 Agent 做了什么、哪里失败、半成品产物在哪——自动持久化，不随杀掉而丢失

### 7.3 两类正交 Agent 角色

| 类型 | 特征 | 适用场景 |
|------|------|---------|
| **一次性工人**（Disposable Worker） | 无状态、fire-and-forget | 批量并行探索 |
| **持久伙伴**（Persistent Partner） | 有记忆、有关系、有连续性 | 长期上下文和信任 |

### 7.4 MAST 失败框架

MAS 三类失败：
- **FC1: 系统设计问题**（拓扑缺陷）
- **FC2: 协调失败**（交接/同步问题）
- **FC3: 验证缺口**（缺少验收标准）

> 大多数失败不是 Prompt 问题，而是**结构性/拓扑性缺陷**。

### 7.5 协调税（Coordination Tax）

超过 4+ 个 Agent，收益递减甚至下降。系统需要硬限制或自动合并机制。

### 7.6 Agent 管理 ≈ 组织管理

| 传统组织 | Agent Harness | 时间尺度 |
|---------|--------------|---------|
| 招聘 | Spawn | 毫秒 |
| 绩效考核 | 收敛检查 | 分钟 |
| 裁员 | Kill | 秒 |
| 交接 | Context Transfer | 秒 |
| 组织记忆 | Retirement Log | 持久化 |

---

## 八、行动空间构建——最难的部分

来源：Anthropic + Rohit(@rohit4verse) + 全网调研

### 8.1 Anthropic 的核心判断

> "构建 Agent Harness 最难的部分是**构建它的行动空间**。"

行动空间不是"工具越多越好"，需要精心策划每个 Agent 在每个特定任务中可用的工具集。

### 8.2 平衡点

**能力覆盖 vs. 爆炸式搜索空间**

演进路径：从静态白名单 → **上下文感知的动态行动空间**

### 8.3 Rohit 的三步观察法

> "构建 Agent Harness 不是比工作量，而是比**观察力**。像 Agent 一样看：**Watch the logs, Catch the loops, Tweak the tools.**"

**观察先于体量**：先有高质量的日志可观测性，再加框架和 Agent。

---

## 九、Bitter Lesson 张力

### 9.1 知识结构 vs. 通用计算的张力

如果 Agent Harness 主要通过**添加更多人类编写的结构**来扩展，它可能在对抗 Rich Sutton 的 Bitter Lesson——通用计算和方法最终胜过手工知识。

### 9.2 平衡点

Harness 结构应该是**模型可以学会替代的中间状态**，而非永久硬化的约束。

### 9.3 实践含义

新能力优先进入 skills/config/docs，而非硬编码到核心逻辑。核心代码保持干净和收敛。

---

## 十、十条可执行设计原则（全主线浓缩）

1. **观察先于体量**：先建高质量日志可观测性，再加框架和 Agent
2. **四层分离**：知识 / 编排 / 门控 / 治理——不要混为一体
3. **循环为原语**：先构建"死循环壳"（Ralph Loop），再扩展到多角色
4. **结构化回执**：每轮执行输出机器可读的结构化结果，而非仅人类可读的 Markdown
5. **动态行动空间**：按任务、按上下文策划工具集——不是静态白名单
6. **上下文压缩**：上下文超长时自动压缩——保留最近 2 轮 + 长期记忆，压缩中间轮次
7. **退役日志**：被杀 Agent 自动输出结构化事后分析
8. **经验资产 > 日志**：构建管线：执行 → 案例卡片 → 可搜索的经验库
9. **熵治理**：系统化清理 Agent 产生的制品，防止工作区/代码库熵增
10. **约束 > 指令**：通过环境约束引导 Agent 行为，而非冗长的 Prompt 指令

---

## 十一、企业现状与趋势（2026 网络补充）

- 企业平均部署 **12 个 AI Agent**，预计 2027 年达到 20 个
- 但只有 **27% 连接到了其余技术栈**
- 2026 工程焦点：构建集中化治理基础设施（即 Agent Harness），管理生命周期、上下文、工具访问和安全边界
- **Autonomy Ladder**（自主性阶梯）：从 Bug 复现到自主 PR 合并的 11 步渐进式提升

---

## 十二、学习路径建议

### 从零开始的阅读顺序

1. **概念入门**：先理解"马与缰绳"比喻 → 四层架构全景（本文第一、二节）
2. **工程实践**：Agent Loop 四步 + Ralph Loop 模式 → Codex App Server 架构（本文第四节）
3. **实战参考**：LangChain 的三个优化抓手 + 具体技术（本文第五节）
4. **深水区**：上下文持久性问题 + Agent 生命周期管理 + MAST 失败框架（本文第六、七节）
5. **哲学反思**：行动空间构建 + Bitter Lesson 张力（本文第八、九节）

### 推荐精读原文

| 优先级 | 文章 | 核心价值 |
|--------|------|---------|
| ★★★ | OpenAI「Harness engineering」 | Agent-first 范式转变的定义性文章 |
| ★★★ | 知乎 sunnyzhao 四层架构 | 中文社区最完整的架构拆解 |
| ★★★ | LangChain「Improving Deep Agents」 | 唯一有量化效果数据的 Harness 优化案例 |
| ★★☆ | OpenAI「Unrolling the Codex agent loop」 | 理解 Agent Loop 原子操作 |
| ★★☆ | OpenAI「Unlocking the Codex harness」 | 跨客户端协议设计的工程参考 |
| ★☆☆ | 全网调研汇总 | 多视角综述，快速了解不同声音 |

---

## 十三、2026-03-18 新增：两个开源项目的 Harness 实践映射

> 来源：`Insights/20260318_AutoResearchClaw_全自主科研管线架构拆解_insight.md` + `Insights/20260318_agency_agents_Persona框架与Swarm编排_insight.md`

### 13.1 AutoResearchClaw —— 完整 Harness 在科研领域的极致实现

AutoResearchClaw 的 23-Stage Pipeline 本质上是一个**完整的 Agent Runtime / Harness**，其设计精确映射了本文第二节的四层架构：

| Harness 四层 | AutoResearchClaw 实现 | 关键特征 |
|-------------|---------------------|---------|
| **知识供给层** | Literature Discovery (Stage 3-6) + MetaClaw skills 注入 | 自动文献检索 + 跨轮 lesson→skill 迁移 |
| **执行编排层** | 23 Stage DAG + PROCEED/REFINE/PIVOT 三路决策 (Stage 15) | Stage-gated pipeline + 自适应重规划 |
| **风险门控层** | Sentinel Watchdog (NaN检测/反编造/4层引用验证) + 3个人类审批 Gate | 正交横切巡检 + 分级自治度控制 |
| **治理运营层** | MetaClaw 跨轮学习 (lesson→skill→overlay→prompt注入) | 实测：重试率 -24.8%，refine 周期 -40% |

**对本主线的增量价值**：

- **经验飞轮的生产级实证**：MetaClaw 是本文第三节"经验飞轮"概念的最完整实现——从"知道应该做"到"已经做出来且有量化效果"
- **Sentinel 横切模式**：独立于编排层的质量守护，印证了第二节"Layer 3 与 Layer 2 解耦"的设计原则
- **ACP 协议**：LLM 后端可插拔（支持 Claude Code / Codex CLI / Gemini CLI 等），让管线核心逻辑与推理引擎完全解耦——这是 Harness 可移植性的一个工程实践

### 13.2 MetaClaw 经验管线——经验飞轮的具象化

MetaClaw 把本文第三节描述的三阶段飞轮推进到了可落地的具体设计：

```
Run N 失败/次优 → 结构化 Lesson 提取
        ↓
Lesson → Skill 转化（文件级，存入 ~/.metaclaw/skills/arc-*/SKILL.md）
        ↓
Run N+1 → build_overlay() 把 skills 注入全部 23 Stage 的 LLM prompt
        ↓
LLM 避开已知坑 → 更高质量、更少重试
```

三个关键设计选择对 Butler 有直接参考价值：
1. **Skill 粒度是文件级**——不是全局配置，每个 skill 是独立的 `SKILL.md`（与 Butler skill 体系同构）
2. **时间衰减 30 天**——避免过时 lessons 永久污染（Butler 的 self_mind 认知层当前缺少此机制）
3. **默认关闭、opt-in 启用**——不增加核心管线复杂度

### 13.3 agency-agents —— "纯约束层 Harness"的极端案例

agency-agents 用纯 Markdown 系统提示词实现了一个**静态 Harness 层**——没有运行时、没有记忆、没有编排，仅靠约束层就创造了 52K★ 的实用价值：

| Harness 四层 | agency-agents 覆盖 | 实现方式 |
|-------------|-------------------|---------|
| **知识供给层** | 部分覆盖 | 每个 Persona 的 Identity + Mission 描述携带领域知识 |
| **执行编排层** | 实验中 | Swarm Builder + Nexus Exercise (PR #117) |
| **风险门控层** | ✅ 充分覆盖 | Critical Rules 三级约束（✅ Always / ⚠️ Ask first / 🚫 Never） |
| **治理运营层** | ❌ 完全缺失 | 无运行时观测、无反馈闭环 |

**对 Harness 理论的启示**：这个案例证明——在强模型时代，仅靠精心设计的约束层（不需要运行时编排和观测）就能产生巨大实用价值。但也清晰暴露了天花板：没有记忆就没有成长，没有编排就没有真正协作，没有观测就没有质量闭环。

### 13.4 Harness 重量级光谱

结合已有框架，可以画出 Harness 实现的完整重量级光谱：

```
极轻 ─────────────────────────────────────────────────── 极重
  │                          │                           │
  ↓                          ↓                           ↓
agency-agents           autoresearch              AutoResearchClaw
(纯约束层:              (约束+循环:                (全管线:
 112个MD文件             3文件/630行                23 Stage/8 Phase
 无运行时)               5分钟Loop)                 3 Agent+MetaClaw)
```

**设计启示**：不存在"正确的 Harness 重量"——应该根据任务的时序复杂度、质量门控需求和自学习需要，在光谱上选择合适的位置。Butler 当前在中间偏左位置（约束 + 循环 + 记忆），可以按需向右扩展。

---

## 附：Butler 项目对标

Butler 的现有架构已经触及了 Harness 四层中的多个层面：

| Harness 层 | Butler 对标 |
|-----------|------------|
| 知识供给 | `local_memory` / `BrainStorm` / `skills` |
| 执行编排 | `heartbeat_orchestration` / `agent.py` / skill 调度 |
| 风险门控 | Guardian / 权限检查（初步） |
| 治理运营 | `task_ledger` / `heartbeat_tasks` / `self_mind`（经验飞轮雏形） |

下一步可以对照这个框架做差距分析，看哪一层最薄弱、优先补强。

---

> **文档版本**：v1.1 (2026-03-18)
> **整合素材**：12 篇 Raw/Working/Insight 文件 + 3 次网络搜索 + v1.1 新增 AutoResearchClaw (#16) + agency-agents (#17) 两篇调研
> **状态**：v1.1 整合完成——新增第十三节"两个开源项目的 Harness 实践映射"（含 MetaClaw 经验飞轮实证 + Harness 重量级光谱）
