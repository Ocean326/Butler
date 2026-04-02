# Anthropic 近期开源博客与 Agent 前沿技术文档补充脑暴

## 来源与挂钩

- 外部材料范围：
  - `Anthropic` 官方 `News / Engineering`
  - `OpenAI` 官方 agent/security/harness 文档
  - `Google Research / DeepMind` 官方 agent system 文档
  - `Cognition` 官方 Devin 工程博客
  - `Simon Willison`、`Martin Fowler` 等行业高信号技术作者
- 当前项目主线挂钩：
  - `docs/daily-upgrade/0326/00_当日总纲.md`
  - `docs/runtime/README.md`
  - `butler_main/orchestrator/`
  - `butler_main/domains/campaign/`
  - `BrainStorm/Insights/mainline/Harness_Engineering_主线知识体系.md`
  - `BrainStorm/Insights/mainline/Agent_评估_安全_自治度_主线知识体系.md`

---

## 一句话结论

**过去一年真正成熟下来的共识，不是“模型更强了”，而是 agent 系统的真源已经逐步从 prompt 转向 harness、eval、context、trace、sandbox 和 governance。**

如果把这句话翻译成 Butler 的下一阶段路线，就是：

**Butler 不应继续把“长任务产品化”理解成 chat 接前门 + orchestrator 能启动后台就够了，而应把 `frontdoor decision / control plane / process runtime / agent runtime / evaluation / risk governance` 收成一套可持续升级的操作系统。**

---

## 1. 材料地图

### 1.1 一级材料：Anthropic 近几个月最值得看的

1. [Introducing The Anthropic Institute](https://www.anthropic.com/news/the-anthropic-institute) `2026-03-11`
   - 重点不是功能，而是把 `frontier red team / economic impacts / policy communication` 固化成长期治理层。
2. [Partnering with Mozilla to improve Firefox’s security](https://www.anthropic.com/news/mozilla-firefox-security) `2026-03-06`
   - 展示的是一条完整安全工作流：发现漏洞、独立复现、人工验证、向维护方提报，而不是“模型找到 bug”这么简单。
3. [Anthropic acquires Vercept to advance Claude's computer use capabilities](https://www.anthropic.com/news/acquires-vercept) `2026-02-25`
   - 明确押注 `computer use`，说明 GUI/桌面/真实软件交互已被视为 agent 主战场。
4. [Anthropic’s Responsible Scaling Policy: Version 3.0](https://www.anthropic.com/news/responsible-scaling-policy-v3) `2026-02-24`
   - 把治理升级成 `frontier safety roadmap + risk reports + external review`。
5. [Detecting and preventing distillation attacks](https://www.anthropic.com/news/detecting-and-preventing-distillation-attacks) `2026-02-23`
   - 把对“能力抽取/系统偷学”的防御，提升到平台级策略问题。
6. [Introducing Claude Sonnet 4.6](https://www.anthropic.com/news/claude-sonnet-4-6) `2026-02-17`
   - 重点不只是性能，而是 `adaptive/extended thinking + context compaction + long-context + agent reliability`。
7. [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) `2026-01-09`
   - 明确区分 `outcome / transcript / harness / suite / pass@k / pass^k`。
8. [Designing AI-resistant technical evaluations](https://www.anthropic.com/engineering/AI-resistant-technical-evaluations) `2026-01-21`
   - 说明评测会被模型打穿，eval 必须持续升级为 AI-resistant。

### 1.2 一级材料：与之形成互证的官方文档

1. [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/) `2026-02-11`
   - 证明 `harness` 本身已经是产品工程主战场。
2. [Designing AI agents to resist prompt injection](https://openai.com/index/designing-agents-to-resist-prompt-injection/) `2026-03-11`
   - 把 prompt injection 重新理解为 `social engineering + source/sink control`。
3. [Keeping your data safe when an AI agent clicks a link](https://openai.com/index/ai-agent-link-safety/) `2026-01-28`
   - 进一步说明 exfiltration 防线应落在系统机制，而不是只靠模型自觉。
4. [A practical guide to building AI agents](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/) `2025`
   - 给出较通用的 agent 设计与模型分层策略。
5. [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) `2025-06-13`
   - 说明 `orchestrator-worker`、并行搜索、memory/handoff/artifact 如何真实落地。
6. [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) `2025-09-29`
   - 把 context 作为稀缺资源和工程对象，而不是“多塞点上下文”。
7. [Accelerating scientific breakthroughs with an AI co-scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/) `2025-02-19`
   - 展示多 agent 系统如何围绕科研目标做 `generation / reflection / ranking / evolution / meta-review`。
8. [How Cognition Uses Devin to Build Devin](https://cognition.ai/blog/how-cognition-uses-devin-to-build-devin) `2026-02-27`
   - 最有价值的是 `Ask Devin -> Session -> Review -> Autofix -> Playbook -> MCP -> API` 这一条闭环。
9. [Closing the Agent Loop: Devin Autofixes Review Comments](https://cognition.ai/blog/closing-the-agent-loop-devin-autofixes-review-comments) `2026-02-10`
   - 把“写代码”和“修 review/CI/lint/security comment”收成自动反馈闭环。
10. [Agent Trace: Capturing the Context Graph of Code](https://cognition.ai/blog/agent-trace) `2026-01-29`
   - 强调新一代真源不只是代码 diff，而是 `change -> conversation -> context` 的映射。

### 1.3 二级材料：高启发行业文档

1. [Living dangerously with Claude](https://simonwillison.net/2025/Oct/22/living-dangerously-with-claude/) `2025-10-22`
   - 提出 `lethal trifecta`：私有数据、非可信内容、外部通信三者合一时，prompt injection 风险暴增。
2. [Agentic AI and Security](https://martinfowler.com/articles/agentic-ai-security.html) `2025`
   - 从传统安全工程视角把 agent 风险翻译成工程治理清单。
3. [My fireside chat about agentic engineering at the Pragmatic Summit](https://simonwillison.net/2026/Mar/14/pragmatic-summit/) `2026-03-14`
   - 对 `模板、代码风格、sandbox、并行 agent、质量模式继承` 的总结很实用。

---

## 2. 理论轴：这些材料背后的共同收敛

### 2.1 Harness 已经从“测试脚手架”升级成“产品真源”

Anthropic、OpenAI、Cognition 都在指向同一个事实：

- 单看模型能力，已经无法解释最终系统质量。
- 真正被交付给用户的，是 `model + tools + prompts + memory + runtime policy + guardrails + evals` 的组合体。
- 因此，团队真正维护的对象，不该只是提示词或模型选择，而是 `harness`。

对 Butler 的翻译：

**你现在的 `chat/frontdoor -> mission/campaign facade -> orchestrator -> process runtime -> agent runtime -> writeback -> observe/query -> feedback`，本质上已经是 harness。下一步不是继续把它当“实现细节”，而是要把它当产品真源。**

### 2.2 Eval 不是验收附件，而是持续运营资产

Anthropic 在 agent eval 上最重要的提醒有三条：

1. `transcript success != outcome success`
2. `agent eval = harness eval + model eval`
3. eval 一旦建立，会反过来定义研发沟通和升级速度

这和 Butler 当前状态高度相关：

- 你已经有 acceptance evidence、smoke、黄金对话集
- 但它们还更像“阶段性证明”
- 下一步应该升格为长期的 `outcome eval suite`

也就是说，要从“这次跑通了”升级成“以后每次改模型、改前门、改 runtime、改模板库，都能自动知道哪些边界退化了”。

### 2.3 Context engineering 正在取代 prompt engineering，成为长任务核心学科

Anthropic 2025-09 的 context engineering 和 2026-02 Sonnet 4.6 的 context compaction，和 Cognition 的 Agent Trace，实际上在说同一件事：

- 长任务系统的瓶颈，越来越不是单步推理，而是上下文组织。
- 真正值钱的是 `让 agent 在正确时刻看到正确上下文`。
- 因此需要：
  - compaction
  - notes / memory
  - artifact reference
  - trace / context graph
  - subagent clean context

对 Butler 的翻译：

**不能继续把“最近对话 + 一些补充 prompt”视为长任务主存。长任务真正的主存应是 `session summary + draft/spec + campaign artifact + workflow/session trace + query projection`。**

### 2.4 多 Agent 不再是“多叫几个模型”，而是“受约束的并行认知结构”

Google AI co-scientist、Anthropic Research system、Cognition 的 Review/Autofix，都说明多 agent 只有在以下场景才真正有收益：

- 可以并行探索
- 需要独立复核
- 需要角色隔离
- 需要不同上下文窗口

没有这些条件时，多 agent 很容易退化成内部协调成本。

这与 Butler 最近对 `orchestrator 官僚化风险` 的担心正好互证：

**多 agent 有效的前提，不是角色变多，而是每个角色都必须新增独立认知收益、隔离收益或验证收益。**

### 2.5 Security 的重心已经从“识别恶意 prompt”转到“限制错误后果”

OpenAI、Simon、Martin Fowler 基本达成共识：

- 不要幻想能完美识别一切注入
- 要把防御重心放在
  - sandbox
  - tool permission
  - source/sink control
  - sensitive action approval
  - exfiltration guard

对 Butler 的翻译非常直接：

**`chat_execution_blocked`、`should_discuss_mode_first` 只是第一步。真正成熟的安全体系需要把“前门判断”继续延伸到 `tool call`、`filesystem`、`network`、`writeback` 和 `feedback`。**

### 2.6 Governance 正在从抽象原则转为周期性产物

Anthropic Institute、RSP 3.0、distillation policy 的共同特点是：

- 治理不再只是“原则”
- 而是要产出周期性的
  - risk report
  - roadmap
  - threshold
  - external review
  - observability summary

这对 Butler 的启发是：

**Butler 的 governance 不应只存在于 prompt 约束或隐藏逻辑里，而应周期性输出可读报告。**

---

## 3. Butler 的理论 + 实践体系草案

### 3.1 建议的总结构

可以把 Butler 后续体系临时收成六层：

1. `Product / FrontDoor`
   - 负责用户协商、后台意图判断、任务草案、确认边界
2. `Control Plane`
   - 负责 mission/campaign 编排、调度、状态推进
3. `Process Runtime`
   - 负责 dispatch / resume / verify / recover / writeback contract
4. `Agent Runtime`
   - 负责单 agent/tool/provider/computer-use 执行
5. `Evaluation System`
   - 负责 golden dialogues、outcome eval、trace grading、regression
6. `Governance System`
   - 负责 risk report、autonomy ladder、approval policy、security audit

这六层里，`5` 和 `6` 现在还没有在主线中被明确提级，但从行业演化看，它们已经不该被视为附属层。

### 3.2 对应的七个基础对象

后续 Butler 的“系统真源”建议至少围绕这七类对象建模：

1. `Draft / Spec`
   - 用户协商态、模板推荐、确认差异、启动依据
2. `Mission / Campaign`
   - 控制面真源
3. `Execution Receipt`
   - process runtime 的标准执行回执
4. `Artifact`
   - 结构化产物与轻量引用
5. `Trace`
   - 过程轨迹、关键决策、tool/branch/session 上下文
6. `Eval Verdict`
   - 对 outcome 的系统评价，不依赖 agent 自述
7. `Risk Record`
   - 风险等级、审批轨迹、阻断原因、异常行为

### 3.3 五条长期设计原则

1. **以 outcome 为主，不以 agent 自述为主**
   - 所有“完成了”“成功了”“已修复”都应尽可能映射到可检查 outcome。
2. **以 artifact 和 reference 为主，不以长上下文堆叠为主**
   - 长任务不应主要靠聊天历史维持一致性。
3. **以分层 contract 为主，不以内隐 prompt 习惯为主**
   - 关键边界必须是对象和字段，不只是提示词。
4. **以闭环反馈为主，不以单次执行为主**
   - `write -> review -> autofix -> verify -> report` 才是稳定系统。
5. **以可运营治理为主，不以一次性 guardrail 为主**
   - 风险体系必须能持续观察、统计、调整。

---

## 4. 对当前 Butler 的直接启发

### 4.1 第 4 层产品面：从“会协商”升级到“有显式自治梯度”

当前你已经补出：

- `campaign negotiation`
- 自动启动与需确认边界
- 同会话补料回灌后台
- 前台执行阻断

下一步建议不是只补更多 prompt，而是新增一个正式对象：

- `AutonomyProfile`
  - 任务类型
  - 风险等级
  - 历史成功率
  - 是否需要显式确认
  - 是否允许自动 dispatch
  - 是否允许 tool side-effects

这样 Butler 的“协商态”才不会永远只是一次性 prompt 判断，而会变成可学习、可解释、可升级的自治系统。

### 4.2 第 3 层 control plane：从 mission/campaign 编排走向 eval-aware orchestration

下一阶段的 orchestrator 不该只做：

- create
- dispatch
- observe
- recover

还应知道：

- 本次任务属于哪个 eval suite
- 哪些 phase 需要 verifier / reviewer
- 哪些 branch 的产物进入 artifact store
- 哪些结果应触发 risk record

也就是：`orchestrator` 不该吞执行细节，但应该消费 eval/governance 的正式 verdict。

### 4.3 第 2 层 process runtime：把“验证、恢复、回执”彻底收成标准合同

你已经在 `0326` 把 `ProcessExecutionOutcome / ProcessWritebackProjection` 收口了一轮，这是对的。

接下来建议继续推进：

- 把 `approval / verification / recovery` 彻底当作 runtime contract，而不是散在 façade 或 domain 里。
- 明确 `side-effect class`
  - read-only
  - local write
  - repo mutation
  - network egress
  - external system action
- 让不同 side-effect class 自动映射到不同审批与审计级别。

这一步会直接把“安全工程”接回 process runtime，而不是停留在 chat 层。

### 4.4 第 1 层 agent runtime：正式预留 computer-use / sandbox / tool-risk 模型

Anthropic 和 OpenAI 都在明确一件事：

**真正有生产价值的 agent，迟早要触达 GUI、浏览器、外部系统和真实工具。**

所以 Butler 即使今天还没大规模上 `computer use`，也建议现在就为 agent runtime 预留三个槽位：

1. `execution mode`
   - chat-only
   - tool-only
   - browser-use
   - computer-use
2. `sandbox profile`
   - local trusted
   - local restricted
   - remote isolated
3. `egress policy`
   - no network
   - allowlist only
   - reviewed external comms

否则以后 computer-use 一接进来，很容易直接把现有 runtime contract 撞穿。

### 4.5 Evaluation System：把黄金对话和 acceptance 升格成正式系统

建议 Butler 单独形成四类 eval：

1. `FrontDoor Outcome Eval`
   - 测“该不该进后台”“该不该先协商”“补料是否回流正确”
2. `Runtime Contract Eval`
   - 测 dispatch / recovery / writeback / projection 的一致性
3. `Campaign Quality Eval`
   - 测模板选择、composition plan、artifact completeness
4. `Security / Safety Eval`
   - 测 prompt injection、越权写入、异常外联、错误自动执行

这些 eval 的长期价值在于：它们会成为后续模型切换、prompt 升级、template 扩容时的统一护栏。

### 4.6 Governance System：从隐性约束升级为公开治理面

建议后续定期产出一份轻量 `Butler Risk Report`，至少包含：

- 自动启动任务总量
- 需确认任务占比
- 前门误判样例
- 被阻断的高风险执行
- recovery 触发次数
- 执行失败后人工接管率
- 不同任务类型的自治成功率

这份报告的意义不是“做报告”，而是让自治策略可以被迭代，而不是永远依赖开发者记忆。

---

## 5. 可执行 backlog 草案

### 5.1 P0：一到两周内最值得补的

1. 建一个 `frontdoor outcome eval` 套件
   - 先覆盖 `should_discuss_mode_first`
   - 覆盖 `chat_execution_blocked`
   - 覆盖“创建后补料默认走后台反馈”
2. 为 process runtime 增加 `side_effect_class`
   - 让审批/阻断逻辑不再只挂在 chat 层
3. 建一份 `Butler Risk Report` 原型
   - 先从现有 acceptance/run-data 自动汇总
4. 建一个 `artifact + trace index`
   - 至少能把 `mission / campaign / workflow_session / artifact / verdict` 串起来

### 5.2 P1：下个阶段最值得做的

1. `AutonomyProfile` 正式化
   - 任务类型、风险等级、信任分、默认执行模式
2. `reviewer/verifier` phase 正式化
   - 不再只在 smoke 或测试里存在
3. `model / effort routing policy`
   - 前门协商、普通后台、复杂审阅、最终裁决走不同模型档位
4. `computer-use runtime contract`
   - 即使先不接 GUI，也先把 contract 立住

### 5.3 P2：适合并回长期主线的

1. `Agent Trace / Context Graph` 风格的 trace 设计
2. 针对模板库和 negotiation 的滥用/抽取防护
3. 将 `Risk Report + Eval Report + Acceptance Evidence` 收成统一治理面板

---

## 6. 对 Butler 当前阶段的判断

### 6.1 现在最不缺的是什么

当前 Butler 最不缺的是：

- 又一版 prompt 文案
- 又一个平行目录
- 又一层中间协调对象

因为你已经进入“主链路成立后”的阶段，真正的瓶颈已经不是缺功能名词，而是缺把系统长期跑稳的 `eval / trace / governance / safety contract`。

### 6.2 现在最该提级的是什么

最该提级的有四个：

1. `Outcome Eval`
2. `Risk Governance`
3. `Context / Artifact / Trace`
4. `Runtime-level Safety Contract`

### 6.3 这轮 Anthropic 等材料给出的总裁决

**2026 年的 agent 系统竞争，已经不只是“谁会调模型”，而是“谁先把 agent 做成一套能稳定升级的工程操作系统”。**

Butler 现在已经有进入这条路的基础，但要继续往前，重点不该只是扩更多任务，而是把：

- 长任务协商
- orchestration
- runtime
- eval
- trace
- governance

真正接成同一个系统。

---

## 7. 后续可继续追的材料线

1. Anthropic `Effective harnesses for long-running agents`
2. Anthropic `Building agents with the Claude Agent SDK`
3. OpenAI 更多关于 tracing / eval / sandbox 的产品化文档
4. Cognition 后续关于 `Manage Devins / Schedule Devins` 的工程经验
5. Agent Trace 规范本体与实现仓库

---

## 参考链接

### Anthropic

- https://www.anthropic.com/news/the-anthropic-institute
- https://www.anthropic.com/news/mozilla-firefox-security
- https://www.anthropic.com/news/acquires-vercept
- https://www.anthropic.com/news/responsible-scaling-policy-v3
- https://www.anthropic.com/news/detecting-and-preventing-distillation-attacks
- https://www.anthropic.com/news/claude-sonnet-4-6
- https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- https://www.anthropic.com/engineering/AI-resistant-technical-evaluations
- https://www.anthropic.com/engineering/multi-agent-research-system
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

### OpenAI

- https://openai.com/index/harness-engineering/
- https://openai.com/index/designing-agents-to-resist-prompt-injection/
- https://openai.com/index/ai-agent-link-safety/
- https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/

### Google / Cognition / 行业作者

- https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/
- https://cognition.ai/blog/how-cognition-uses-devin-to-build-devin
- https://cognition.ai/blog/closing-the-agent-loop-devin-autofixes-review-comments
- https://cognition.ai/blog/agent-trace
- https://simonwillison.net/2025/Oct/22/living-dangerously-with-claude/
- https://simonwillison.net/2026/Mar/14/pragmatic-summit/
- https://martinfowler.com/articles/agentic-ai-security.html
