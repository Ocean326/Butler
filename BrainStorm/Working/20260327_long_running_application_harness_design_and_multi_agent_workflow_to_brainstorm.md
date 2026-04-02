# 长运行应用的 Harness Design × 多 Agent Workflow：扩充脑暴稿

## 来源与挂钩

- 外部资料：
  - Anthropic `Effective harnesses for long-running agents` `2025-11-26`
  - Anthropic `How we built our multi-agent research system` `2025-06-13`
  - Anthropic `Demystifying evals for AI agents` `2026-01-09`
  - Anthropic `Writing effective tools for agents — with agents` `2025-09-11`
  - Anthropic `Beyond permission prompts: making Claude Code more secure and autonomous` `2025-10-20`
  - Anthropic `Building effective agents` `2024-12-19`
  - OpenAI `Harness engineering: leveraging Codex in an agent-first world` `2026-02-11`
  - OpenAI `Unrolling the Codex agent loop` `2026-01-23`
  - OpenAI `Inside OpenAI’s in-house data agent` `2026-01-29`
  - LangChain 官方 `Multi-agent` 文档
  - Google ADK 官方 `Multi-Agent Systems` 文档
- 当前项目挂钩：
  - `BrainStorm/Insights/mainline/Anthropic_长运行应用与Harness设计_主线知识体系.md`
  - `BrainStorm/Insights/mainline/多智能体系统_MAS_与协作模式_主线知识体系.md`
  - `BrainStorm/Working/20260326_anthropic_recent_blogs_and_agent_frontier_docs_to_brainstorm.md`
  - `docs/daily-upgrade/0326/04_稳定Harness之后的下一阶段主线_Anthropic长运行Harness吸收版.md`
  - `docs/project-map/00_current_baseline.md`
  - `docs/runtime/WORKFLOW_IR.md`

---

## 一句话结论

**长运行应用的核心问题，不是“要不要多 agent”，而是“系统如何在多次上下文切换、长时程状态漂移、重复恢复、独立验收和有限自治之间维持连续性”。**

更具体地说：

- 多 agent workflow 解决的是**并行认知容量**和**上下文隔离**
- long-running harness 解决的是**状态连续性**、**可恢复性**、**验收闭环**和**环境 legibility**

如果把多 agent 当成 long-running 的答案，系统很容易官僚化。  
如果把 harness 只理解成 agent loop，系统又会在跨 session、跨天、跨目标时失忆、漂移和假完成。

所以真正成熟的方向不是：

`single agent -> multi-agent`

而是：

`single run agent -> recoverable harness -> planner/generator/evaluator -> selective multi-agent -> eval-aware operating system`

---

## 一、先把问题讲清楚：什么叫 long-running application development

Anthropic `2025-11-26` 的公开文章把这个问题定义得很准确：  
随着 agent 开始承担持续数小时甚至数天的任务，系统就必须面对一个硬现实：

- 每次上下文窗口都是离散 session
- 新 session 天然失忆
- 复杂任务无法在单窗口完成
- 轻微错误会在长链路中累积并放大

因此，long-running app development 的本质不是“让模型一直说下去”，而是：

**如何让系统在多次离散 session 中持续推进同一个软件目标。**

这个定义一旦成立，很多工程判断都会变：

1. 主存不再是聊天历史，而是外部 artifact
2. 成功标准不再是“像是完成了”，而是 outcome 可验证
3. 恢复机制不是附属能力，而是系统骨架
4. agent loop 只是最内层，外层必须有 session/handoff/eval/runtime

---

## 二、Anthropic 这条线真正贡献了什么

### 2.1 `Effective harnesses for long-running agents` 的核心抽象

Anthropic 在 `2025-11-26` 这篇里给出了一组非常重要的稳定判断：

- 长任务的核心难点是跨 context window 连续工作
- 解决思路不是硬撑历史，而是做“session 间桥接”
- 他们采用了 `initializer agent + coding agent` 双段式结构
- 初始化阶段负责建环境、建 `init.sh`、建 `claude-progress.txt`
- 后续 coding session 每轮都只做增量推进，并留下结构化痕迹

这意味着 Anthropic 已经把 long-running harness 定义成了：

`bootstrap + incremental progress + structured handoff + clean state`

### 2.2 它最重要的隐含判断：环境必须对 agent 可读

这篇文章里真正有力量的一点，不是“进度文件”本身，而是它所代表的思想：

**如果环境对 agent 不可读，agent 就只能反复猜。**

Anthropic 发现：

- 用 git commit 留痕能让 agent 利用版本回滚
- 用 progress file 留痕能让后继 session 快速进入上下文
- 每轮先验证环境是否还健康，再推进新特性，能显著降低越修越坏

这其实已经不是 prompt engineering，而是：

**把软件工程环境改造成 agent 可消费的执行现场。**

### 2.3 它仍然是“单 agent 优先”的

Anthropic 在 `Future work` 明说，仍不确定通用单 agent 是否在所有长任务场景下都优于多 agent；他们认为 testing、QA、cleanup 这类角色未来可能值得分拆。

这个措辞很值得重视：

- 说明 Anthropic 并没有把多 agent 当默认答案
- 说明他们对多 agent 的态度是“按子任务增量引入”
- 说明 long-running harness 的主体仍然是 session continuity，而不是团队编制

这和很多社区“有复杂问题就上多 agent”的直觉是相反的。

---

## 三、Anthropic 多 agent 公开方案到底解决了什么

### 3.1 `How we built our multi-agent research system`

Anthropic 在 `2025-06-13` 的 Research 文章给出的，是另一类问题的解法：

- 任务是开放式研究
- 优势来自 breadth-first parallel exploration
- 主体模式是 `orchestrator-worker`
- lead agent 负责规划、综合
- subagents 负责并行搜索和局部推理

它在内部 eval 上比单 agent 高很多，但它自己也明确说了几个边界：

- token 消耗显著增加
- 适合高价值任务
- 不适合强依赖共享上下文或高耦合协同的任务
- coding 类任务未必像 research 那样容易并行化

### 3.2 这篇文章给 long-running harness 的真正启发

这篇 Research 文最有价值的地方，不是“多 agent 更强”，而是它指出了多 agent 真正成立的条件：

1. 任务可以拆出多个相对独立方向
2. 每个 worker 可以在隔离上下文中工作
3. 中央 orchestrator 只收轻量结果，而不是来回传全文
4. 有 memory / artifact 体系承接结果

因此，对 long-running app development 的启发不是“全面多 agent 化”，而是：

**只有当长任务内部出现真实可并行子问题时，多 agent 才应作为 harness 的可选增量。**

---

## 四、Anthropic 公开材料合起来，真正稳定下来的骨架是什么

把 `Building effective agents`、`Writing tools for agents`、`Effective harnesses for long-running agents`、`Demystifying evals for AI agents`、`multi-agent research system` 这几篇拼起来，Anthropic 其实已经给出一个稳定总结构：

```text
User Goal
  -> Planner / Decomposition
  -> Tooling + Action Space
  -> Generator / Worker Execution
  -> External Artifacts / Memory / Progress
  -> Evaluator / Judge
  -> Retry / Resume / Recovery
  -> Optional Parallel Subagents
```

这里最重要的不是组件名，而是顺序：

1. 先建 action space
2. 再建长任务 continuity
3. 再建 evaluator
4. 最后才考虑 selective multi-agent

这说明：

**多 agent 在公开最佳实践里并不处于第一优先级，harness 和 eval 才是。**

---

## 五、OpenAI 这条线提供了另一种补强：把 repository 本身变成 harness

### 5.1 `Harness engineering: leveraging Codex in an agent-first world`

OpenAI `2026-02-11` 这篇最关键的地方，不是“0 行手写代码”，而是它把工程团队的工作重定义为：

- 设计环境
- 组织仓库知识
- 编码边界与品味
- 建立 review/eval/cleanup 循环
- 把 human taste 变成长期可执行规则

OpenAI 这里最强的一个信号是：

**repository knowledge store 是系统真源。**

他们公开展示了类似这种结构：

- `AGENTS.md`
- `ARCHITECTURE.md`
- `design-docs/`
- `exec-plans/`
- `product-specs/`
- `references/*.llms.txt`
- `QUALITY_SCORE.md`
- `RELIABILITY.md`
- `SECURITY.md`

这和 Anthropic 的 progress file 路线本质一致，只是更系统化：

- Anthropic 侧重 session continuity
- OpenAI 侧重 repository legibility

### 5.2 OpenAI 最关键的贡献：环境 legibility 和 architectural enforcement

OpenAI 强调：

- agent 环境越可读，杠杆越大
- 文档不够，必须用 lint 和 invariant 编码边界
- 人类不是退出系统，而是上移一层抽象：
  - prioritization
  - acceptance criteria
  - outcome validation

这是 long-running app harness 非常重要的一层补充：

**单靠 session handoff 不够，系统还必须有一个稳定的知识平面和边界平面。**

---

## 六、OpenAI 进一步补了两个东西：agent loop 和 internal workflow grounding

### 6.1 `Unrolling the Codex agent loop`

OpenAI `2026-01-22` 这篇把“harness”重新压回一个核心事实：

- harness 最底层仍然是 agent loop
- 用户输入、模型推理、工具调用、观察、更新计划、返回结果，这条 loop 不会消失

这提醒我们：

**long-running harness 不是替代 agent loop，而是把 agent loop 包进更大的 runtime。**

### 6.2 `Inside OpenAI’s in-house data agent`

OpenAI `2026-02` 的数据 agent 文章又补了一个对长任务系统很有价值的点：

- 系统能力来自 layered grounding
- 不是只给 schema，而是叠加
  - metadata
  - human annotations
  - code-level enrichment
  - reusable workflows
- 还要用 systematic evaluation 防止质量漂移

这篇虽然不是 coding harness，但对 long-running application development 有直接映射：

**长运行 agent 不能只靠“当前任务 prompt”，它必须扎根在结构化知识层和复用工作流层。**

---

## 七、社区与框架方现在怎么讲 multi-agent workflow

### 7.1 LangChain/LangGraph 的口径

LangChain 近两周的官方文档很清楚地把多 agent pattern 分成：

- `Subagents`
- `Handoffs`
- `Skills`
- `Router`
- `Custom workflow`

它还给出了一条很关键的总判断：

- 多 agent 特别适合
  - 单 agent 工具过多
  - 需要专门知识和长上下文
  - 需要顺序约束
- 设计中心是 context engineering

这个表述非常成熟，因为它没有把多 agent 神化，而是把它压回：

**context distribution + control-flow choice**

### 7.2 Google ADK 的口径

Google ADK 的官方文档则更工程化：

- Multi-Agent System 是由多个 `BaseAgent` 组合而成
- 核心 primitive 包括：
  - hierarchy
  - workflow agents
  - interaction mechanisms
- 明确把
  - `SequentialAgent`
  - `ParallelAgent`
  - `LoopAgent`
  视作 workflow orchestrators

ADK 这条线的价值在于：

**它把“agent 智能体”和“workflow orchestration”显式区分开了。**

这对 Butler 这类系统特别重要，因为它说明：

- 并不是所有协调节点都该由 LLM 承担
- 很多长任务控制流更适合 deterministic workflow agent
- LLM agent 应该承担不确定性高的判断，而不是吞下全部流程控制

---

## 八、把这些解法放到一起，看出什么共识

### 8.1 共识一：真正的主战场是 harness，不是单个模型

Anthropic、OpenAI、LangChain、Google ADK 的共同点是：

- 都在强调 orchestration、memory、artifact、tooling、context、evaluation
- 没有人把最终答案收口为“换更强模型就行”

所以这个行业的真实成熟路径是：

`model-first` 正在转向 `harness-first`

### 8.2 共识二：long-running 问题优先由 artifact continuity 解决

Anthropic 用：

- `init.sh`
- `claude-progress.txt`
- git commit

OpenAI 用：

- repository knowledge store
- plans/specs/reliability docs

它们的共同点是：

**把记忆从对话里挪到工件里。**

### 8.3 共识三：多 agent 不是默认答案，而是条件升级

Anthropic 的 Research 文、LangChain 文档、Google ADK 文档都没有把 MAS 说成默认模式，而是都附带了条件：

- 有并行价值
- 有上下文隔离价值
- 有控制流结构化收益
- 有经济性

这说明：

**多 agent 的设计边界已经越来越清楚：它是一种按条件引入的认知扩容技术。**

### 8.4 共识四：evaluator 已经变成一等基础设施

Anthropic `Demystifying evals` 直接说明：

- 没有 eval，系统会“flying blind”
- transcript 成功不等于 outcome 成功
- eval 是模型升级和产品迭代加速器

OpenAI 数据 agent 也直接把“systematic evaluation”作为信任底座。

因此：

**long-running harness = execution runtime + evaluation runtime**

没有 evaluator 的 long-running system，只是能持续运行，不是能持续可信运行。

### 8.5 共识五：安全正在从 approval prompt 转向 runtime boundary

Anthropic `2025-10-20` 的 sandboxing 文章给出的信号非常明确：

- 目标不是让用户点更多批准
- 目标是通过 filesystem/network 边界减少 permission prompts，同时提升 autonomy

这对长运行应用至关重要，因为长任务里“每步都弹窗审批”会严重拖垮用户与 agent 协作质量。

所以真正成熟的安全方向是：

- permission prompt 不是核心
- runtime boundary 才是核心

---

## 九、因此我们应该怎样重新定义“长运行应用 harness”

我建议把 long-running application harness 定义成下面这套：

```text
Long-Running Application Harness
├── Goal Contract Layer
│   ├── user intent
│   ├── spec
│   ├── acceptance criteria
│   └── risk profile
├── Runtime Continuity Layer
│   ├── session bootstrap
│   ├── progress log
│   ├── artifact graph
│   ├── checkpoint / resume
│   └── recovery
├── Legibility Layer
│   ├── repo knowledge store
│   ├── references
│   ├── plans
│   ├── architecture docs
│   └── runtime-readable status
├── Execution Layer
│   ├── agent loop
│   ├── tools / MCP / sandbox
│   ├── workflow nodes
│   └── optional multi-agent branches
├── Evaluation Layer
│   ├── review packet
│   ├── acceptance verdict
│   ├── regression evals
│   └── production quality monitoring
└── Governance Layer
    ├── autonomy ladder
    ├── approval policy
    ├── boundary enforcement
    └── audit / risk records
```

这一定义和一般“agent loop”最大的不同是：

**它把 continuity、legibility、evaluation、governance 都提成了一等公民。**

---

## 十、什么情况下应该引入多 agent，什么情况下不该

### 10.1 适合引入多 agent 的情况

1. 存在明确的并行子问题  
   例如多源研究、横向对比、候选方案并发探索。

2. 存在强上下文隔离收益  
   例如不同代码域、不同证据域、不同方法域分别工作更稳定。

3. 存在独立复核需要  
   例如 generator 与 evaluator 必须解耦。

4. 存在可被 workflow 承接的合流点  
   否则分出去的 agent 结果无法稳定收束。

### 10.2 不适合引入多 agent 的情况

1. 问题本身高度串行  
   例如必须严格沿一个状态机推进。

2. 所有角色都必须共享同一大上下文  
   这时拆分只会增加同步税。

3. 没有独立 evaluator  
   那么更多 agent 只会更快地产生更多未验证结果。

4. 没有 artifact graph  
   那么多 agent 的 handoff 最终只能退化成“消息转述游戏”。

### 10.3 长运行应用的默认策略

对 long-running app development，我认为默认策略应该是：

1. 先建单线程 recoverable harness
2. 再建独立 evaluator
3. 再对特定阶段引入 selective multi-agent

而不是：

1. 先搭很复杂的多 agent 团队
2. 再想怎么恢复、怎么验收、怎么治理

后者非常容易官僚化。

---

## 十一、对 Butler 的最直接启发

### 11.1 Butler 现在其实已经有 long-running harness 骨架

你现在的：

- `frontdoor / domain plane`
- `orchestrator / control plane`
- `process runtime`
- `agent runtime`

已经比很多“agent framework”更接近真正 long-running harness 的形态。

问题不在于有没有骨架，而在于几个真源对象还没彻底提级。

### 11.2 最该补齐的四块真源

#### 1. Goal Contract 真源

现在 Butler 有协商与 negotiation，但还缺更硬的：

- `TaskDraft`
- `WorkingSpec`
- `ExecutionPlan`
- `AcceptanceCriteria`
- `RiskProfile`

这决定“为什么跑”和“什么算完成”。

#### 2. Continuity 真源

Butler 已有 `workflow session`、`artifact registry`、`blackboard` 等骨架，但还需要更明确地把它们抬成：

- progress log
- checkpoint
- resumable handoff
- stable session memory

这决定“怎么跨 session 活下来”。

#### 3. Evaluation 真源

现在 Butler 有 acceptance / smoke / evidence，但仍偏“阶段性证明”。

下一步应更正式地提成：

- `ReviewPacket`
- `AcceptanceVerdict`
- `OutcomeEval`
- `RegressionBank`

这决定“怎么知道真的做成了”。

#### 4. Governance 真源

现在你已有一些前门阻断和治理摘要，但还应进一步对象化：

- `AutonomyProfile`
- `ApprovalState`
- `RiskRecord`
- `BoundaryPolicy`

这决定“系统能在多大范围内自主行动”。

### 11.3 对多 agent 的建议不是“再多加几个角色”

Butler 现在如果要吸收多 agent workflow，最稳的路径不是再继续发散角色，而是按收益最明确的三类来加：

1. `Planner`
   - 负责任务合同和阶段分解
2. `Generator / Worker`
   - 负责受控执行
3. `Evaluator / Reviewer`
   - 负责独立验收

只有当某些任务天然需要并发探索时，再加：

4. `Parallel Research Workers`
5. `Parallel Candidate Solvers`

但这些都应该是 **runtime 分支**，不是系统永久官僚编制。

---

## 十二、我现在对“长运行 harness × 多 agent workflow”的最终判断

### 判断一

**长运行应用的第一问题是 continuity，不是 collaboration。**

先活下来，先不断线，先能恢复，再谈多人协作。

### 判断二

**多 agent 的主要价值是上下文隔离和并行认知，不是角色排场。**

如果没有明确并行收益，MAS 很容易退化成内部管理系统。

### 判断三

**真正成熟的 harness 必须把 artifact、legibility、evaluation、boundary 全部对象化。**

否则系统只能“看起来很会干活”，无法长期稳定。

### 判断四

**行业公开最佳实践已经在收敛：模型负责智能，workflow 负责控制，artifact 负责连续性，evaluator 负责信任。**

### 判断五

**Butler 的下一阶段不该再理解成“加一点前门、加一点后台、加一点 agent 编排”，而应该理解成：把现有骨架升级为真正的 long-running application harness。**

---

## 十三、可直接承接到后续设计的草案

### P0：定义 long-running harness 的 8 个真源对象

- `TaskDraft`
- `WorkingSpec`
- `ExecutionPlan`
- `ProgressLog`
- `Artifact`
- `ReviewPacket`
- `AcceptanceVerdict`
- `RiskRecord`

### P1：把 `process runtime` 提升为 continuity runtime

关键不是改名，而是明确它负责：

- checkpoint / resume
- handoff
- progress persistence
- evaluation receipt
- recovery

### P2：把多 agent 限定为三种官方使用形态

1. `orchestrator-worker`
2. `parallel candidate search`
3. `independent evaluator`

除此之外的角色扩张默认不鼓励。

### P3：建立 eval-aware frontdoor

也就是前门不仅决定“要不要启动”，还决定：

- 成功标准是什么
- 风险级别是什么
- 是否允许自动执行
- 最终必须由谁来验收

---

## 十四、资料链接

- Anthropic `Effective harnesses for long-running agents`  
  https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic `How we built our multi-agent research system`  
  https://www.anthropic.com/engineering/multi-agent-research-system
- Anthropic `Demystifying evals for AI agents`  
  https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Anthropic `Writing effective tools for agents — with agents`  
  https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic `Beyond permission prompts: making Claude Code more secure and autonomous`  
  https://www.anthropic.com/engineering/claude-code-sandboxing
- Anthropic `Building effective agents`  
  https://www.anthropic.com/research/building-effective-agents
- OpenAI `Harness engineering: leveraging Codex in an agent-first world`  
  https://openai.com/index/harness-engineering/
- OpenAI `Unrolling the Codex agent loop`  
  https://openai.com/index/unrolling-the-codex-agent-loop/
- OpenAI `Inside OpenAI’s in-house data agent`  
  https://openai.com/index/inside-our-in-house-data-agent/
- LangChain `Multi-agent`  
  https://docs.langchain.com/oss/python/langchain/multi-agent
- Google ADK `Multi-Agent Systems`  
  https://google.github.io/adk-docs/agents/multi-agents/

---

## 备注

- 你现有主线里提到的 `Harness design for long-running application development`，我这轮没有在公开官方站点上检索到对应公开页面；这篇扩充稿因此以可验证的公开近邻材料为主，并结合你仓库内已有主线总结做收束。
- 如果后续你手头有这篇文章的正式链接或原文，我建议再做一轮“对照增补”，把这篇 brainstorm 从“高可信扩充稿”升级成“精确对读稿”。
