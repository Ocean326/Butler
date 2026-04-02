# 长运行应用 Harness 与多 Agent Workflow：从可持续执行到可持续交付的主线知识体系

> **主线定位**：这条主线不是重复讲“多 agent 很重要”或“long-running 很难”这些泛泛结论，而是专门回答一个更工程化的问题：**当任务从单轮执行变成跨 session、跨天、可恢复、可验收的软件开发或复杂交付时，harness 应该如何设计；而多 agent workflow 在这套系统里究竟处于什么位置？**
>
> **与既有主线的关系**：
> - 相比 `Anthropic_长运行应用与Harness设计_主线知识体系.md`，本文不只看 Anthropic 一家，而是把 Anthropic、OpenAI、LangChain、Google ADK 的公开解法放到同一条线上比较。
> - 相比 `多智能体系统_MAS_与协作模式_主线知识体系.md`，本文不把重点放在“如何拆 agent 团队”，而是放在“在长运行应用里，多 agent 何时有净收益、何时反而官僚化”。
>
> **整合来源**：
> - Anthropic `Effective harnesses for long-running agents`、`How we built our multi-agent research system`、`Demystifying evals for AI agents`、`Writing effective tools for agents — with agents`、`Beyond permission prompts: making Claude Code more secure and autonomous`、`Building effective agents`
> - OpenAI `Harness engineering: leveraging Codex in an agent-first world`、`Unrolling the Codex agent loop`、`Inside OpenAI’s in-house data agent`
> - LangChain 官方 `Multi-agent`
> - Google ADK 官方 `Multi-Agent Systems`
> - Butler 当前 `frontdoor / orchestrator / process runtime / agent runtime` 分层与 `0326` 长运行 harness 主线

---

## 一句话结论

**长运行应用的主问题不是“是否采用多 agent”，而是“系统能否在离散 session、持续漂移、局部失败和重复恢复中，依然保持目标、状态、验证与边界的一致性”。**

因此，成熟系统的正确顺序不是：

`single agent -> multi-agent`

而是：

`single run -> recoverable harness -> planner / generator / evaluator -> selective multi-agent -> eval-aware operating system`

翻成更工程化的话：

- 多 agent workflow 解决的是 **并行认知容量** 与 **上下文隔离**
- long-running harness 解决的是 **连续性、可恢复性、独立验收、环境可读性与边界治理**

这两者相关，但不是一回事。  
如果把多 agent 当成 long-running 的答案，系统很容易退化成内部协调机器。  
如果把 harness 只理解成 agent loop，系统又会在跨 session 和跨阶段推进时不断失忆、漂移和假完成。

---

## 一、什么叫长运行应用：从“连续聊天”到“连续交付”

过去很多 agent 讨论默认的任务单位是“单轮请求”或“单次 run”。  
但当任务变成：

- 连续编码数小时或数天
- 需要多次恢复和继续
- 中途不断接受新信息
- 必须在真实代码库、真实环境、真实测试上推进
- 最终还要通过独立验收

系统面对的就不再是“会不会做一步工具调用”，而是：

**能不能连续交付。**

长运行应用因此有五个与普通 agent 不同的本质特征：

1. **上下文离散性**  
   每个窗口、每次 session 天然断裂，不能假设“一直记得之前所有事”。

2. **状态漂移性**  
   任务目标、环境状态、文件状态、测试状态会在长链路中不断变化。

3. **失败累积性**  
   小错误不会立刻爆炸，但会在下一轮继续被放大。

4. **验收滞后性**  
   许多任务不是“说起来像完成了”就结束，而要等测试、review、运行结果、产品状态共同证明。

5. **恢复刚需性**  
   系统必须假设中断、重启、上下文压缩、人工接手、模型切换都会发生。

所以长运行应用的关键不是“让 agent 一直工作”，而是：

**让系统在不连续的会话里持续完成同一个交付目标。**

---

## 二、Anthropic 这条线真正教会我们的，不是“多 agent”，而是“continuity first”

### 2.1 `Effective harnesses for long-running agents` 的真正含义

Anthropic 在 `2025-11-26` 的公开文章里做了一个非常关键的动作：  
把长任务 coding 从“会不会继续 loop”重新定义成“如何跨 session 持续推进”。

他们采用的思路可以压成四个关键词：

- `bootstrap`
- `progress file`
- `structured handoff`
- `clean resume`

表面看是：

- 一个 initializer agent 先准备环境
- 生成 `init.sh`
- 维护 `claude-progress.txt`
- 后续 coding session 每轮只做增量推进

但更深的判断是：

**长运行系统的主存不再是 transcript，而是外部 artifact。**

### 2.2 这条线最重要的不是“进度文件”，而是“环境可读性”

Anthropic 公开方案的真正价值不在某个具体文件名，而在于它要求环境满足两个条件：

1. **对 agent 可读**  
   当前目标、当前状态、上一步结果、已知问题要能快速读取。

2. **对新 session 可恢复**  
   即使换一个干净窗口，也能在短时间内恢复足够多的执行语义。

这意味着：

- Git 提交不是单纯版本控制，而是恢复点
- Progress log 不是流水账，而是 session bridge
- Init script 不是脚本便利，而是环境再现机制

因此，Anthropic 长运行 harness 的第一教训是：

**不要试图用更长的上下文去替代更好的状态对象。**

### 2.3 Anthropic 在这条线上的态度其实很克制

从公开表述看，Anthropic 并没有得出“复杂任务默认多 agent 更好”的结论。  
他们更像是在说：

- 长运行首先要解决 continuity
- evaluator 必须独立
- 某些高价值子环节未来适合拆成专门角色
- 但多 agent 只应在收益明确时增量加入

这点非常关键，因为它说明公开最佳实践并没有走向“先组一个很复杂的 agent 团队”，而是在走：

**先让单线程长任务系统可靠，再按需要拆出高收益角色。**

---

## 三、Anthropic 多 agent 公开方案解决的是另一类问题：parallel exploration

### 3.1 `How we built our multi-agent research system` 回答的不是 continuity

Anthropic `2025-06-13` 的 research system 文章，核心场景是开放式研究，而不是长时程软件交付。

它成立的前提是：

- 问题可以拆出多个并行探索方向
- 子任务之间上下文可以部分隔离
- orchestrator 能消费轻量结果而非整个上下文历史
- 多个 subagent 的收益主要来自 breadth-first search

它因此很适合：

- 文献调研
- 多方向证据搜索
- 并行方案对比
- 开放式信息收集与综合

但它天然不等于“长运行应用开发系统”。

### 3.2 这类多 agent 系统给 long-running harness 的真正启发

研究型多 agent 系统最值得吸收的，不是“多开几个 worker”，而是下面这些稳定经验：

1. **上下文隔离真有价值**  
   并行 worker 不被彼此污染，能明显提升探索质量。

2. **lead / orchestrator 必须消费摘要，而不是消费所有中间过程**  
   否则多 agent 的复杂度会重新回流到中心节点。

3. **worker 产出要进入 artifact / memory，而不是只停留在消息层**  
   否则 handoff 退化成转述游戏。

4. **多 agent 必须有经济性前提**  
   适合高价值任务，不适合把所有任务都升级成团队模式。

因此它对 long-running harness 的真实贡献是：

**让我们知道，只有当长任务内部出现真实可并行的子问题时，多 agent 才是正确增量。**

---

## 四、OpenAI 补上的关键维度：把 repository 本身变成 harness

### 4.1 `Harness engineering` 这条线最重要的不是“0 行手写代码”

OpenAI `2026-02-11` 的 `Harness engineering: leveraging Codex in an agent-first world`，真正强的点是把工程团队的维护对象重新定义了。

不是只维护：

- prompt
- model choice
- tool list

而是维护：

- `AGENTS.md`
- `ARCHITECTURE.md`
- `design-docs/`
- `exec-plans/`
- `product-specs/`
- `references/*.llms.txt`
- `QUALITY_SCORE.md`
- `RELIABILITY.md`
- `SECURITY.md`

也就是：

**repository knowledge store 本身就是 harness。**

### 4.2 它补的是 Anthropic 路线里偏弱的一层：legibility layer

Anthropic 更强调：

- progress continuity
- session handoff
- evaluator separation

OpenAI 更强调：

- 仓库知识可读
- 设计资料可读
- 质量边界显式化
- 品味和标准长期编码化

这两者合起来，才构成长运行应用真正完整的认知平面：

1. **session continuity**
2. **repository legibility**

如果只有前者，系统能续跑但容易失去全局工程感。  
如果只有后者，系统懂架构但未必能跨 session 稳定推进。  
因此：

**长运行 harness 既要有 progress plane，也要有 knowledge plane。**

### 4.3 OpenAI 对 long-running 应用的另一个补充：grounding 是分层的

`Inside OpenAI’s in-house data agent` 这篇虽然不是 coding harness，但它对长运行系统的启发很强：

- 不能只给 schema 或少量上下文
- 要有 layered grounding：
  - metadata
  - annotations
  - code-level enrichment
  - reusable workflows

这说明成熟系统不会把 grounding 全压在一个 prompt 里，而会把知识沉到多个层面。  
这正是长运行应用最需要的能力，因为长任务必须不断从外部环境重新取回正确上下文。

---

## 五、LangChain 和 Google ADK 的框架口径，说明了什么

### 5.1 LangChain 的表述：多 agent 本质是 context distribution + control flow

LangChain 最近的官方 `Multi-agent` 文档把多 agent pattern 拆成：

- `Subagents`
- `Handoffs`
- `Supervisor`
- `Router`
- `Skills`
- `Custom workflow`

它强调多 agent 特别适合：

- 单 agent 工具太多
- 需要专门知识和长上下文
- 需要顺序控制

这说明 LangChain 也没有把多 agent 视作默认答案，而是把它压回：

**对 context 和 control-flow 的工程性重构。**

### 5.2 Google ADK 的表述：workflow orchestration 和 agent intelligence 必须区分

Google ADK 官方则给出另一种很重要的分解：

- `SequentialAgent`
- `ParallelAgent`
- `LoopAgent`

这些在 ADK 里更接近 workflow orchestrators，而不是“更聪明的大 agent”。

这带来一个重要结论：

**不是所有协调动作都应该交给 LLM。**

很多长运行应用里：

- 顺序推进
- 并行 fan-out/fan-in
- 失败重试
- 固定 gate

这些更适合 workflow runtime 负责，而不是让 LLM 角色承担全部流程控制。

这与 Butler 当前 `orchestrator / process runtime / agent runtime` 分层天然同构。

---

## 六、到这里可以收敛出一个更成熟的行业共识

把 Anthropic、OpenAI、LangChain、Google ADK 放在一起，会出现五条非常清晰的共识。

### 6.1 共识一：主战场已经从 model 迁到 harness

所有官方公开材料都在强调：

- orchestration
- tool design
- context engineering
- memory / artifacts
- evaluation
- sandbox / policy

没有任何一家把最终系统优势归结为“换更强模型就够了”。

因此真正成熟的行业判断是：

**model-first 正在转向 harness-first。**

### 6.2 共识二：long-running 先解决 continuity，再考虑 collaboration

Anthropic 的长运行文章和 OpenAI 的 repository knowledge store 共同指向：

- 先让系统能跨 session 连续活下来
- 再考虑是否需要多 agent 协作

这意味着 continuity 是更基础的系统能力。

### 6.3 共识三：evaluator 已经是一等基础设施

Anthropic `Demystifying evals for AI agents` 说得很清楚：

- transcript success 不等于 outcome success
- 没有 eval，系统就是 blind

OpenAI 内部 data agent 也把 systematic evaluation 作为信任基座。  
所以：

**长运行 harness 不是只有 execution runtime，它还必须有 evaluation runtime。**

### 6.4 共识四：多 agent 是条件升级，不是默认答案

无论 Anthropic 还是框架方，都在给多 agent 加条件：

- 有并行价值
- 有上下文隔离价值
- 有控制流收益
- 有经济性

这意味着：

**多 agent 的工程成熟，恰恰体现为“知道什么时候不该上多 agent”。**

### 6.5 共识五：安全正在从 permission prompt 转向 runtime boundary

Anthropic sandboxing 和 OpenAI 安全文章都在强调：

- 不要把安全理解成“多点几次确认”
- 更成熟的方向是 filesystem / network / tool side-effect boundary

这对长运行系统尤其关键，因为长任务里每一步都等人工许可，基本等于把自治能力打碎。

所以：

**真正好的 long-running harness，应该通过边界设计减少高频打扰，而不是通过不断审批维持表面安全。**

---

## 七、因此，长运行应用 harness 应该怎么定义

我建议把它正式定义成下面这套结构：

```text
Long-Running Application Harness
├── Goal Contract Layer
│   ├── user intent
│   ├── working spec
│   ├── execution plan
│   ├── acceptance criteria
│   └── risk profile
├── Continuity Layer
│   ├── session bootstrap
│   ├── progress log
│   ├── artifact graph
│   ├── checkpoint / resume
│   └── recovery
├── Legibility Layer
│   ├── repository knowledge store
│   ├── references
│   ├── architecture docs
│   ├── status projections
│   └── runtime-readable summaries
├── Execution Layer
│   ├── agent loop
│   ├── tools / MCP / sandbox
│   ├── workflow nodes
│   └── optional multi-agent branches
├── Evaluation Layer
│   ├── review packet
│   ├── acceptance verdict
│   ├── regression evals
│   └── outcome monitoring
└── Governance Layer
    ├── autonomy ladder
    ├── approval policy
    ├── boundary enforcement
    └── audit / risk records
```

这里最关键的变化是：

- continuity 不再是“记忆附属品”，而是正式一层
- legibility 不再是“文档顺手写写”，而是正式一层
- evaluation 不再是“最后测一下”，而是正式一层
- multi-agent 不再是骨架中心，而是 execution 层中的可选分支机制

这套定义比一般 agent loop 更接近一个真正的操作系统。

---

## 八、那么多 agent 应该放在这套系统的哪里

### 8.1 它应该是 execution layer 的可选扩容机制

在这套结构里，多 agent 不该吞掉整个系统，而应被限制在：

- `parallel research workers`
- `parallel candidate solvers`
- `independent evaluator / reviewer`
- `specialist subagents`

也就是说，多 agent 应该承担：

- 并行探索
- 局部专家任务
- 独立复核

而不是承担：

- 全部状态管理
- 全部控制流协调
- 全部恢复逻辑
- 全部治理语义

这些应该回到 harness 的 continuity / evaluation / governance 层。

### 8.2 什么时候适合上多 agent

1. 子任务天然可并行
2. 上下文拆开后更干净
3. 每个角色有独立认知收益
4. 有 artifact graph 承接 handoff
5. 有 evaluator 保证结果不会只越跑越偏

### 8.3 什么时候不适合上多 agent

1. 问题高度串行
2. 大部分角色必须共享同一重上下文
3. 中间产物不能结构化
4. 没有独立 evaluator
5. 只是为了“显得更先进”

这时引入多 agent 往往会带来：

- 解释税
- handoff 税
- 状态同步税
- 组织税

也就是我们前面说的官僚化风险。

---

## 九、对 Butler 的直接翻译：你真正该升格的，不是 agent 数量，而是真源对象

Butler 当前已经有很强的骨架基础：

- `frontdoor / domain plane`
- `orchestrator / control plane`
- `process runtime`
- `agent runtime`

所以 Butler 的下一阶段，不应该理解成“再多加几个 agent 角色”，而应该理解成：

**把现有骨架升级成真正的 long-running application harness。**

### 9.1 最先该提级的 8 个真源对象

1. `TaskDraft`
2. `WorkingSpec`
3. `ExecutionPlan`
4. `ProgressLog`
5. `Artifact`
6. `ReviewPacket`
7. `AcceptanceVerdict`
8. `RiskRecord`

其中：

- `TaskDraft / WorkingSpec / ExecutionPlan` 决定 goal contract
- `ProgressLog / Artifact` 决定 continuity
- `ReviewPacket / AcceptanceVerdict` 决定 evaluation
- `RiskRecord` 决定 governance

### 9.2 `process runtime` 应从“过程层”进一步明确为 continuity runtime

Butler 已经有：

- workflow session
- artifact registry
- blackboard
- collaboration substrate

下一步更准确的收口应该是：

`process runtime = continuity runtime + evaluation receipt runtime`

也就是明确它负责：

- checkpoint / resume
- progress persistence
- handoff
- recovery
- verification / acceptance receipts

### 9.3 对多 agent 的最小建议不是扩角色，而是固定三类官方模式

1. `planner -> worker`
2. `parallel candidate search`
3. `independent evaluator`

除了这三类，其他角色扩张默认不鼓励。  
这样可以把多 agent 限制在收益最明确的几类用途上，而不是滑向结构性膨胀。

---

## 十、最终结论：真正成熟的长运行系统，不是“能一直跑”，而是“能一直被信任”

到这里，这条主线可以压成五条最终判断。

### 判断 1

**长运行应用的第一问题是 continuity，不是 collaboration。**

先活下来，先不断线，先能恢复，再谈多人协作。

### 判断 2

**多 agent 的主要价值是上下文隔离和并行认知，不是角色排场。**

没有明确并行收益时，MAS 很容易变成组织系统。

### 判断 3

**成熟 harness 必须把 continuity、legibility、evaluation、governance 都提成正式层。**

否则系统只能“看起来会干活”，无法长期稳定交付。

### 判断 4

**行业公开最佳实践已经在收敛：模型负责智能，workflow 负责控制，artifact 负责连续性，evaluator 负责信任。**

### 判断 5

**Butler 的下一阶段，不应再被理解成“继续拼 agent 功能”，而应被理解成：把现有骨架升级为真正的 long-running application harness。**

---

## 资料来源

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
