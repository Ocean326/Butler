# Agent 评估·安全·自治度量 — OpenAI × Anthropic 2026Q1 前沿实践

> 母本：`BrainStorm/Working/openai_anthropic_recent_tech_posts_2026q1/` 下 8 篇
> - Anthropic 2026-01-09 Demystifying evals for AI agents
> - Anthropic 2026-02-18 Measuring AI agent autonomy in practice
> - Anthropic 2026-01-21 Designing AI-resistant technical evaluations
> - Anthropic 2026-02-05 Parallel Claudes building a C compiler
> - Anthropic 2026-02-05 LLM-discovered 0-days
> - Anthropic 2026-03-06 Firefox security partnership
> - Anthropic 2026-03-06 Reverse engineering CVE-2026-2796
> - OpenAI 2026-03-11 Designing agents to resist prompt injection
> 提炼时间：2026-03-18
> 主题轴：Agent Eval、自治度量、安全工程、多 Agent 协作质量、AI 抗性评估
> 区别于：`20260318_Anthropic前沿研究_Butler自省对齐设计启发_insight.md`（聚焦 Anthropic 15 篇研究论文的自省/对齐/人格主题）；本篇聚焦 **2026Q1 工程博客中的评估、安全与自治实践**。

---

## 核心观点

### 1. Agent Eval ≠ 模型 Eval：多轮、工具、状态变化让评估复杂度陡增

**来源**：Demystifying evals for AI agents（Anthropic, 2026-01-09）

Agent 的评估比单轮模型评测难在三个维度：
- **多轮累积误差**：第 3 轮的错误可能源于第 1 轮工具调用的微小偏差
- **工具副作用**：agent 的动作改变了环境状态，后续评估基线也跟着变
- **Grader 设计**：评判 agent 表现不能只看最终输出，需要 trace-level 的过程评估

**关键提炼**：
- eval 需要和系统复杂度一起升级——系统加了新工具，eval 必须同步覆盖
- 单点正确率指标对 agent 几乎无意义，需要 trajectory-level 的成功率
- grader 本身也是一个需要迭代的组件，不是写好就不动的

**→ Butler 映射**：Butler 当前的"验收"主要靠 executor 自报告，没有独立的 grader 机制。可参考 Anthropic 的 eval 框架，为 heartbeat 设计一个轻量 grader——至少能回答"这轮执行的 trajectory 是否合理"而非只看"最终文件是否存在"。

---

### 2. 真实自治度与实验室能力不等价，用户信任是关键变量

**来源**：Measuring AI agent autonomy in practice（Anthropic, 2026-02-18）

Anthropic 用 Claude Code 的真实 session 数据发现：
- **经验用户** 更愿意 auto-approve，自治度更高——但这是信任导致的，不是能力导致的
- **Turn duration**（每轮停留时间）和 **人工介入次数** 是比 benchmark 分数更真实的自治指标
- 部署中的自治度受 **产品设计**（确认弹窗的频率）、**用户习惯**（是否仔细审查）和 **工作流约束**（是否允许自动执行）三重影响

**→ Butler 映射**：Butler heartbeat 的自治等级不应只由能力决定，还应考虑用户信任积累。可设计一个渐进式信任机制——新用户/新任务类型默认低自治（需确认），历史成功率高的任务类型逐步提升自治等级。这比硬编码"哪些任务可以自动做"更合理。

---

### 3. Prompt Injection 的本质是社会工程，防御重点在限制危险动作而非完美检测

**来源**：Designing AI agents to resist prompt injection（OpenAI, 2026-03-11）

OpenAI 的核心论点：
- **不能寄希望于"识别所有恶意输入"**——这和反垃圾邮件一样，是一个持续对抗的过程
- 更有效的路径是 **限制 agent 的危险动作能力**：即使 agent 被注入成功，它也做不了什么致命的事
- 三层防线设计：
  1. **动作限制**：高危操作需人工确认
  2. **信息外传限制**：agent 不能随意把上下文发送到外部
  3. **系统约束**：文件系统隔离、网络访问白名单

**→ Butler 映射**：Butler 通过飞书接收用户消息，理论上存在 injection 入口（恶意文本通过飞书消息到达 Butler）。当前的 `heartbeat_upgrade_request.json` 审批机制就是一种"高危操作需人工确认"的实践。应考虑将这种思路扩展到更多场景——比如 Butler 永远不应在无确认情况下删除文件或修改核心配置。

---

### 4. 多 Agent 协作的质量取决于任务分解和 handoff 设计，而非 agent 数量

**来源**：Building a C compiler with parallel Claudes（Anthropic, 2026-02-05）

Anthropic 用并行 Claude 团队构建 C 编译器的实验表明：
- 成功的多 agent 协作依赖 **清晰的任务边界** 和 **定义良好的接口**
- agent 之间的 handoff 协议决定了协作效率的上限
- 并行不等于高效——如果任务拆分不当，并行反而引入协调开销

**→ Butler 映射**：与已有的 `20260318_subagent_vs_agentteam_双引擎架构_insight.md` 形成互补。Butler heartbeat 当前的 branch 机制本质上就是"并行任务分解 + 独立执行 + 结果汇总"。关键改进点是 branch 之间的 handoff 协议——当一个 branch 的产出是另一个 branch 的输入时，如何高效传递？

---

### 5. AI 抗性任务设计揭示了人机能力边界的真实移动

**来源**：Designing AI-resistant technical evaluations（Anthropic, 2026-01-21）

Anthropic 发现自己的工程招聘 take-home 题被 Claude 一代代"打穿"——模型每升级一版，更多标准工程题变得不再能区分人的能力。这迫使他们重新思考：
- **哪些能力是 AI 短期内不会替代的**：系统级架构决策、跨领域约束协调、模糊需求澄清
- **什么样的评估仍然有效**：需要理解大量隐式上下文、涉及多方利益权衡、没有标准答案的开放问题

**→ Butler 映射**：这直接影响 Butler 的协作定位——Butler 应该把精力放在 AI 已经能做好的事上（结构化整理、信息检索、代码生成、格式转换），而把需要"模糊判断 + 隐式上下文"的决策留给用户。`deliver-not-guide` 规则需要与此校准：不是所有事情都应该直接交付，有些事需要先暴露决策点。

---

### 6. Agent 安全能力是双刃剑——发现漏洞的能力 = 制造漏洞的能力

**来源**：LLM-discovered 0-days + Firefox security + CVE exploit（Anthropic, 2026-02/03）

Anthropic RED 团队的三篇安全研究形成一个完整闭环：
- Claude Opus 4.6 在两周内发现 22 个 Firefox 漏洞（14 个高危）
- 同时能从漏洞发现推进到 exploit 构造（在受控环境中）
- 核心矛盾：**能力增长的同时，滥用风险同步增长**

缓解思路不是限制能力，而是：
- 明确的使用场景约束（合作方授权）
- 受控实验环境
- 能力使用的完整审计链

**→ Butler 映射**：Butler 当前不涉及安全研究场景，但"能力 × 风险同增"的原则通用——Butler 能操作文件系统、调用 API、修改配置，这些能力本身就是风险源。审计链（heartbeat 回执 + task_ledger）是第一道防线。

---

## 与 Butler 架构的映射总览

| 前沿实践主题 | Butler 对应机制 | 当前状态 | 可执行改进方向 |
|---|---|---|---|
| Agent eval / grader | executor 自报告 | 无独立 grader | 引入轻量 trajectory grader |
| 自治度量 | heartbeat 自治等级 | 硬编码规则 | 渐进式信任机制（基于历史成功率） |
| Prompt injection 防御 | heartbeat_upgrade_request 审批 | 仅覆盖代码修改 | 扩展到文件删除、外部 API 调用等高危动作 |
| 多 Agent handoff | branch 机制 | 独立执行为主 | 增加 branch 间结构化传递协议 |
| AI 抗性任务 | deliver-not-guide 规则 | 全局适用 | 区分"可直接交付"和"需暴露决策点"的场景 |
| 安全审计链 | heartbeat 回执 + task_ledger | 基础 | 强化为完整的动作审计日志 |

---

## 可执行的下一步

1. **轻量 trajectory grader 原型**：在 heartbeat planner 汇总阶段，增加一个"独立于 executor 的评判 prompt"——读取 executor 回执和实际文件变更，输出 `pass/fail/partial` + 理由。不需要复杂框架，先用一个额外的 LLM 调用实现。

2. **渐进式信任表**：在 `task_ledger.json` 中为每种任务类型维护 `success_count / total_count`，当成功率 > 80% 且总量 > 5 时，自动提升该类任务的自治等级（减少确认步骤）。

3. **高危动作白名单**：梳理 Butler 能执行的所有有副作用的动作（文件写入、文件删除、API 调用、配置修改），按风险分级，高风险动作强制走审批流程。

---

## 主题标签

`#AgentEval` `#自治度量` `#PromptInjection` `#安全工程` `#多Agent协作` `#AI抗性` `#OpenAI` `#Anthropic` `#Butler安全演进`
