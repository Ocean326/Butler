# 0319 AutoResearchClaw 学习笔记：科研 Agent 的分层、门控、横切层与失败提炼

更新时间：2026-03-19 01:26
时间标签：0319_0126

## 一、这份笔记回答什么

本笔记不再重复 AutoResearchClaw 的 23 个 stage 明细，而是把这次调研收束成更可迁移的 Agent / Harness 工程笔记，重点回答：

- 除了 23-stage pipeline，它真正值得学的技术骨架是什么
- 科研 Agent 应该怎么分层，而不是只按步骤切 prompt
- 门控、验证、回滚、横切监控应该由什么类型的 Agent / 机制承担
- 失败如何从日志变成可复用 skill，而不是停留在“这次没做好”
- Butler 如果借鉴，应该学什么，不该照搬什么

一句话总览：

> AutoResearchClaw 最值得学的不是“把科研拆成 23 步”，而是把科研运行时做成一个带有 **专业 Agent、控制平面、验证平面、学习平面、适配平面** 的 research runtime。

---

## 二、项目的真正骨架：不是 pipeline，而是 research runtime

从工程视角看，AutoResearchClaw 不是“23 个 prompt 串联”，而是五类部件共同构成的运行时：

1. **生产 Agent（Production Agents）**
   - 直接生产代码、benchmark、图表、论文段落等产物
2. **控制平面（Control Plane）**
   - gate、PROCEED / REFINE / PIVOT、stage-level rollback、artifact versioning
3. **验证平面（Verification Plane）**
   - 引用验证、实验快速失败、论文-证据一致性检查、anti-fabrication
4. **学习平面（Learning Plane）**
   - 失败 / 警告 → lesson → skill → 下轮 overlay
5. **适配平面（Adapter Plane）**
   - ACP / OpenClaw Bridge / 可插拔 LLM 后端

因此，AutoResearchClaw 更接近：

- `workflow engine`
- `policy engine`
- `verification engine`
- `learning engine`
- `agent adapter layer`

而不是单纯的“论文写作 agent”。

---

## 三、怎么给科研 Agent 分层

### 3.1 第一原则：不要只按 stage 切 Agent

AutoResearchClaw 最关键的启发之一是：

> **Agent 的切分维度不应首先是流程阶段，而应首先是产出物质量域。**

也就是说，不是简单做成：

- Stage 10 一个 Agent
- Stage 11 一个 Agent
- Stage 12 一个 Agent

而是优先按“谁对哪类产物质量负责”来切：

- 代码质量域
- benchmark / 评测质量域
- 图表与可视化质量域
- 写作与证据一致性质量域

这样切的好处：

1. **责任更稳定**
   - 阶段会变化，但代码质量、图表质量、证据质量这些域长期稳定
2. **验证器更容易绑定**
   - 每类 Agent 都可以绑定自己的硬验证条件
3. **可迁移性更强**
   - 一个 `FigureAgent` 可以服务多个 stage，而不是只能服务某一步
4. **避免 stage 越拆越碎**
   - 否则最后会得到一大堆“弱小但相似”的 agent

### 3.2 第二原则：Agent 至少分五层

如果把 AutoResearchClaw 抽象成通用模式，科研 Agent 建议至少分成下面五层：

#### A. 业务生产层

负责把东西做出来。

- `CodeAgent`
- `BenchmarkAgent`
- `FigureAgent`
- `WritingAgent`

职责：生成、修复、迭代、交付产物。

#### B. 决策编排层

负责决定往前、返工还是换方向。

- `Planner / Orchestrator`
- `DecisionAgent`
- `Debate Arbiter`

职责：

- 决定下一步做什么
- 在关键节点做 `PROCEED / REFINE / PIVOT`
- 管理 stage-level 回滚

#### C. 门控验证层

负责“过门”与“不准过门”。

- `GateAgent`
- `Validator`
- `CitationVerifier`
- `ExperimentChecker`

职责：

- 在高风险阶段做强制检查
- 检查不通过时阻止推进
- 决定回到哪个上游阶段

#### D. 横切守护层

负责持续巡检，而不是只在单点审批。

- `Sentinel / Watchdog`
- `ConsistencyMonitor`
- `AntiFabricationGuard`

职责：

- 跨 stage 监控
- 检查局部看起来正常、全局却不一致的问题
- 发现运行时异常并快速失败

#### E. 学习沉淀层

负责把失败变成结构化经验。

- `LessonExtractor`
- `SkillPromoter`
- `KnowledgeDecayManager`

职责：

- 提炼失败模式
- 变成可注入的 skill / overlay
- 给过时经验降权

### 3.3 第三原则：把“角色层”和“平面层”区分开

AutoResearchClaw 真正成熟的地方在于，它隐含地区分了两种东西：

1. **角色层**：谁来产出
2. **平面层**：谁来约束、验证、监控、学习

很多系统的问题是：只有角色，没有平面。

比如只做了：

- research_agent
- code_agent
- reviewer_agent

但没有单独做：

- gate plane
- verification plane
- watchdog plane
- learning plane

结果就是：

- 角色会越来越多
- 约束会越来越散
- 错误会重复发生

---

## 四、怎么用 Agent 做门控

### 4.1 门控不是“人工确认弹窗”，而是可计算的决策点

AutoResearchClaw 的 gate 设计最值得借鉴的点不是 Human-in-the-loop，而是：

> **gate 是一个显式、可回滚、可审计的状态迁移点。**

一个成熟 gate 至少包含：

- 当前 stage
- 待验证 artifact
- 验证规则
- 结果：`pass / fail / refine / pivot`
- 失败后的回退目标
- 本次 gate 的日志与证据

这意味着 gate 不只是“问人要不要继续”，而是一个结构化控制点。

### 4.2 门控最好由三部分组成

#### 1）产物检查器

先检查 artifact 是否满足基本规范。

例如：

- 代码能否通过 AST / import / sandbox 检查
- 图表是否满足分辨率、配色、误差条要求
- 引用是否真实且相关

#### 2）决策器

根据检查结果给出动作：

- `PROCEED`
- `REFINE`
- `PIVOT`
- `REJECT`

#### 3）回滚控制器

失败不是直接退出，而是决定：

- 回到上一个 stage
- 回到某个更早的关键 stage
- 是否保留当前 artifact 版本

### 4.3 门控的本质：把“质量判断”从生成里抽出去

最常见的错误是：

- 让同一个 Agent 既生成，又判断自己是否合格

这会导致：

- 自评偏乐观
- 生成与验证耦合
- agent 可以“骗过自己”

AutoResearchClaw 的强点是：

- 生成归生产层
- 过门归 gate / validator
- 全局一致性归 sentinel

这是一种很明确的 **separation of concerns**。

### 4.4 门控可以由“Agent + 不可变锚点”共同承担

门控不能只依赖 LLM 判断，还要有不可变锚点。

典型锚点包括：

- AST 检查
- import 检查
- NaN / Inf fast-fail
- DOI / paper ID 校验
- CrossRef / Semantic Scholar 对照
- 固定格式 schema 校验

结论：

> **GateAgent 负责综合判断，但判断所依赖的底层验证锚点应尽量不可被生成 Agent 篡改。**

---

## 五、怎么做横切层（Sentinel / Watchdog / Consistency Plane）

### 5.1 横切层的价值：解决“局部正确、全局错误”

很多科研 Agent 在单个 stage 看起来都完成了，但全流程仍然失败，原因通常不是某一步完全坏掉，而是：

- 论文写了一个结论，但实验根本没支持
- 引用了存在的论文，但与论点不相关
- 代码跑完了，但结果异常未被识别
- 多轮修复后 artifact 彼此不一致

这些问题很难由单个 stage 负责。

因此需要横切层持续巡检。

### 5.2 横切层应该管什么

可以抽象成四类监控：

#### 1）运行时健康

- NaN / Inf
- 异常退出
- 资源超限
- 长时间卡住

#### 2）证据一致性

- 论文 claim 是否有实验或文献支持
- 图表是否真的来源于当前 run
- 引用与正文是否一致

#### 3）反编造

- 没跑过的实验被写进论文
- 不存在或不相关的引用被硬塞
- 空洞 AI 套话冒充结论

#### 4）跨版本一致性

- refine / pivot 后，旧结论是否仍被沿用
- 新 artifact 是否和当前路线一致
- 版本切换后是否留有脏状态

### 5.3 横切层不应嵌入某个单一 Agent

如果把 watchdog 逻辑塞进 `CodeAgent` 或 `WritingAgent`，会出现两个问题：

1. 视角太局部
2. 容易被业务逻辑淹没

更合理的做法是：

- 把横切层做成独立 watcher / sentinel
- 订阅关键事件
- 周期性做巡检
- 发现问题后触发 gate / rollback / alert

也就是从架构上明确：

> **Sentinel 不生产内容，只生产“是否可信、是否一致、是否需要中断”的判断。**

---

## 六、怎么提炼失败：从 log 到 lesson，再到 skill

### 6.1 “失败即数据”是第一原则

AutoResearchClaw 与普通 Agent 项目的差距，很大一部分不在生成能力，而在于：

> 它把失败当成结构化资产，而不是一次性事故。

这意味着失败不能只停留在：

- 控制台日志
- 自然语言复盘
- 某天的日报里

而应被结构化记录。

### 6.2 一条可复用的失败提炼链

最值得学的不是具体实现细节，而是这条链：

`run event -> failure record -> lesson extraction -> skill promotion -> future overlay`

可以拆成五步：

#### 第一步：失败记录结构化

至少记录：

- 任务 / run / stage
- 失败类型
- 表现症状
- 触发条件
- 当前 artifact
- 修复动作
- 最终结果

#### 第二步：失败归类

不是所有失败都值得沉淀成 skill。

可以先按类型归类：

- 工具错误
- 约束缺失
- 常见幻觉
- 质量门控缺失
- 流程次序错误
- 上下文缺失

#### 第三步：提炼 lesson

lesson 不应写成长篇感想，而应写成：

- 在什么条件下
- 哪种做法会失败
- 推荐替代动作是什么

也就是尽量写成“可执行规则”。

#### 第四步：晋升为 skill / rule / overlay

只有高频或高价值 lesson 才进入长期层。

晋升条件可以是：

- 同类失败反复出现
- 单次失败代价很高
- 修复策略高度稳定

#### 第五步：时间衰减与淘汰

不是所有经验都应永久保留。

过时经验如果一直注入，会让系统变钝。

因此需要：

- 时间衰减
- 命中率统计
- 长期未触发自动降权
- 与新规则冲突时合并或淘汰

### 6.3 提炼失败时，最容易犯的三个错误

#### 错误 1：把失败写成情绪，而不是规则

例如：

- “这次效果不太好”
- “好像引用有点乱”

这种写法无法复用。

#### 错误 2：把一次偶发事件直接上升为总原则

例如：

- 某次 API 超时，就固化成“不要用这个 API”

这会把短期噪音错误沉淀成长期偏见。

#### 错误 3：只记失败，不记触发条件

没有上下文条件的失败经验很难正确套用。

所以 lesson 必须包含“适用范围”。

---

## 七、从 AutoResearchClaw 可提炼出的通用 Harness 原则

### 原则 1：生产、门控、监控、学习要分层

不要让一个 agent 同时承担：

- 生成
- 自评
- 全局监控
- 经验沉淀

这四件事最好分开。

### 原则 2：按质量域切 Agent，而不是只按流程切

质量域比 stage 更稳定，也更容易绑定验证器。

### 原则 3：高风险决策不要只靠单轮生成

可用：

- debate
- validator
- gate
- rollback

组成真正的控制链。

### 原则 4：横切问题必须有横切层

证据一致性、反编造、运行时健康，这些不应“顺便检查”，而应由独立层负责。

### 原则 5：失败提炼必须结构化

日志不是经验，lesson 才是经验；lesson 进一步稳定后才算 skill。

### 原则 6：经验要可注入，也要可过期

能注入但不能淘汰，会让系统越来越重。

---

## 八、对 Butler 的具体借鉴方式

### 8.1 应该学什么

#### 学 1：按质量域拆专业 Agent / Skill

Butler 未来做科研 domain 时，可以优先拆：

- `research_code_agent`
- `research_benchmark_agent`
- `research_evidence_agent`
- `research_figure_agent`
- `research_writing_agent`

而不是直接照着 23 个阶段一一对应。

#### 学 2：把 gate 做成显式服务

建议抽成独立原子能力：

- `gate_check`
- `validator_run`
- `rollback_plan`
- `artifact_version`

而不是散落在 prompt 里。

#### 学 3：做一层 research sentinel

专门检查：

- claim-evidence consistency
- citation authenticity / relevance
- run health
- artifact drift

#### 学 4：做 lesson → skill 管线

比起“把失败写进日报”，更值得优先做：

- 失败记录 schema
- lesson 提取模板
- skill 晋升阈值
- 时间衰减规则

### 8.2 不该照搬什么

#### 不要照搬 23-stage 重编排

Butler 当前更适合：

- 少数强 loop
- 少量关键 gate
- 可插拔 domain workflow

而不是把所有科研任务都钉死成超长固定流水线。

#### 不要让 prompt 承担全部验证职责

验证和门控应尽量服务化、结构化。

#### 不要把自学习等同于“记得更多”

真正有价值的是：

- 从失败提炼规则
- 让规则进入后续运行
- 并能淘汰旧规则

---

## 九、一个可直接复用的最小骨架

如果以后在 Butler 里做科研 domain，一个更轻量、但能吸收 AutoResearchClaw 精华的最小骨架可以是：

### 9.1 角色层

- `research_orchestrator`
- `code_agent`
- `benchmark_agent`
- `evidence_agent`
- `writing_agent`

### 9.2 控制层

- `gate_service`
- `decision_service`
- `rollback_service`
- `artifact_version_service`

### 9.3 横切层

- `research_sentinel`
- `citation_verifier`
- `consistency_checker`

### 9.4 学习层

- `failure_ledger`
- `lesson_extractor`
- `skill_promoter`
- `skill_decay`

### 9.5 一条运行链

`task -> produce artifact -> validator/gate -> proceed/refine/pivot -> sentinel cross-check -> finalize -> lesson extraction -> skill overlay`

这条链已经能保留 AutoResearchClaw 的主要工程价值，但不会把 Butler 直接推到超重管线那一端。

---

## 十、这次调研的压缩结论

### 10.1 核心结论

AutoResearchClaw 最值得学的，不是 23 个 stage，而是以下四件事：

1. **按质量域切 Agent**
2. **把门控做成显式控制平面**
3. **把 watchdog 做成横切层**
4. **把失败做成 lesson → skill 的学习链**

### 10.2 一句判断

> 如果 `autoresearch` 代表“极简实验闭环”，那 `AutoResearchClaw` 代表的不是“更长的流程”，而是“更完整的科研运行时”。

### 10.3 对 Butler 的一句建议

Butler 不应复制 AutoResearchClaw 的重管线外形，但非常值得吸收它的四个内核：**专业 Agent、显式 gate、横切 sentinel、结构化失败提炼**。

---

## 附：本笔记对应的主要参考

- 官方仓库：`https://github.com/aiming-lab/AutoResearchClaw`
- 官方 Release：`https://github.com/aiming-lab/AutoResearchClaw/releases/tag/v0.3.0`
- 现有拆解：`BrainStorm/Insights/standalone_archive/20260318_AutoResearchClaw_全自主科研管线架构拆解_insight.md`
- 现有原始记录：`BrainStorm/Raw/daily/20260318/20260318_github_autoresearchclaw_note.md`
