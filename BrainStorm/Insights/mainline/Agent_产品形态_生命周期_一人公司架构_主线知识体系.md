# Agent 产品形态·生命周期·一人公司架构：从 Demo 到可信赖长期伙伴

> **主线定位**：这是 BrainStorm 中直接关系到"Butler 该成为什么"的核心主线，整合了 4 篇 standalone Insight + 2 篇 Raw 素材 + 1 篇 AutoResearch 实验记录 + 2 次网络搜索补充（Persistent vs Ephemeral Agents 2026 Benchmarks / One-Person Company Agent Architecture）。核心问题：**Agent 的生命周期该如何设计？一次性 worker 和长期伙伴如何在同一系统中共存？"一人公司 + AI 团队"的组织范式对 Butler 意味着什么？**
>
> **整合来源**：小红书 Dior Debby 一人公司五层构架实录、科研龙虾 72h 迭代战报（刘思源）、Karpathy autoresearch 开源项目实测笔记、Computer Agents Blog 2026 Benchmarks、Autoflowly Startup OS 架构、OpenClaw 一人公司 AI 委托实践

---

## 一、Agent 世界的两种生命周期范式

### 1.1 核心分野

2026 年 Agent 部署中，最根本的架构选择不是"用哪个模型"或"选哪个框架"，而是 **Agent 实例的生命周期策略**——是用完即弃（Ephemeral/Disposable），还是持续存活（Persistent）？

| 维度 | Ephemeral Agent | Persistent Agent |
|------|----------------|-----------------|
| **生命期** | 分钟到小时 | 天到月 |
| **状态** | 无状态，每轮重置 | 有状态，跨会话持久化 |
| **记忆** | 无，或仅限当轮上下文 | 长期记忆 + 偏好累积 |
| **失败模式** | 失败即弃，隔离性好 | 失败需恢复，容错要求高 |
| **核心价值** | 并行性、隔离性、低风险 | 累积性、信任度、连续性 |
| **典型场景** | 一次性搜索、批量数据处理、探索型实验 | 项目管理、客户关系、个人助手 |
| **成本模型** | 按请求计费 | 订阅/长驻模型 |

### 1.2 2026 年的量化证据

Computer Agents Blog 的 2026 基准测试给出了关键数据：

| 任务类型 | Ephemeral 成功率 | Persistent 成功率 | 差距 |
|---------|-----------------|------------------|------|
| 单次研究 | 92% | 94% | ≈持平 |
| 多文件代码重构 | 68% | 91% | +34% |
| 7 天连续日报 | 22% | 87% | +65%（≈4×） |
| 错误自恢复率 | 41% | 78% | +90% |

**关键发现**：对于需要跨轮次上下文保持的任务，Persistent 架构的优势是压倒性的。而对于简单的一次性任务，两种架构几乎等效。这直接指向一个设计原则：**不是所有任务都需要长期 Agent，也不是所有任务适合一次性 Agent——系统需要同时支持两种模式。**

### 1.3 Sandbox 解耦问题：生命周期的工程深水区

一个被广泛低估的架构缺陷是 **执行沙箱与 Agent 生命周期的紧耦合**。当 Agent 进程终止时，其沙箱立即销毁，所有运行状态随之丢失。即使是轻微的崩溃也会导致完整的上下文丢失，而非优雅降级。

解决方案的核心是 **状态外置**：将 Agent 的关键状态（记忆、任务进度、中间产出）从临时执行环境中解耦出来，通过外部化的状态管理和文件持久化实现生存能力。

---

## 二、"一人公司 + AI 团队"：正在发生的组织范式

### 2.1 从隐喻到现实

Dior Debby 在小红书上记录的场景——"我管 agent 管 agent 管 agent 管……"——不是科幻预想，而是 2026 年正在发生的工作模式。OpenClaw 项目更是将公司全部的会计、合规和运营委托给了 AI Agent 团队，Discord 频道充当部门，消息充当指令。

到 2026 年 Q1，一人公司的 AI 团队架构已收敛出三种主要拓扑：

| 模式 | 结构 | 适用场景 | 主要风险 |
|------|------|---------|---------|
| **层级式（Boss-Worker）** | 协调 Agent → 专家 Agent | 内容管线、代码审查 | 协调 Agent 成为瓶颈 |
| **对等式（Mesh）** | Agent 间直连消息总线 | 实时监控、多源整合 | 反馈环失控 |
| **事件驱动（Reactive）** | Agent 订阅事件流 | CI/CD、自动化工作流 | 需要排序保障 |

### 2.2 五层递归委托的真实挑战

Dior Debby 终端截图里的场景——Dalton 和 Helmholtz 两个 worker 未在收敛窗口内完成任务被关闭，立刻 spawn 了 Kepler 和 Pauli 替代——揭示了递归委托的核心痛点：

1. **层间通信成本指数增长**：每增一层，上下文传递、状态同步、错误回传的成本都在放大
2. **收敛超时是常态而非异常**：长任务型 Agent 无法在预期窗口内收敛是 MAS 的结构性问题
3. **"杀与留"的心智负担落在人身上**：决定哪个 Agent 继续跑、哪个该关、什么时候起新的——这个决策的认知开销比实际执行更消耗人类精力
4. **退役知识的流失**：被杀掉的 Agent 做了什么、失败在哪、产出了什么半成品——这些信息随 kill 一起消失

### 2.3 花名不是拟人化噱头，而是认知锚点

Dior Debby 给 Agent 起花名（Dalton、Helmholtz、Kepler、Pauli）指向一个被忽视的设计需求：**在多 Agent 并发场景下，人类需要快速区分、追踪和记忆不同 Agent 的角色与状态。** UUID 无法提供这种认知支撑。好的 Harness 应把 Agent 命名/标识纳入正式设计。

---

## 三、Disposable Core + Persistent Shell：双层生命周期架构

### 3.1 范式融合

两种生命周期不是非此即彼，而是应该在同一系统中共存。成熟的架构模式是 **"持久核心 + 一次性外围"**：

```
┌─────────────────────────────────────────────────┐
│           Persistent Core（持久核心）              │
│  ┌─────────────────────────────────────────────┐ │
│  │ · 长期记忆        · 用户偏好                  │ │
│  │ · 关系连续性      · 任务台账                  │ │
│  │ · 人格与价值观    · 经验资产库                │ │
│  └─────────────────────────────────────────────┘ │
│                       ↕ 状态交接协议               │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐            │
│  │Worker│ │Worker│ │Worker│ │Worker│  ← 按需      │
│  │  A   │ │  B   │ │  C   │ │  D   │    spawn/   │
│  └──────┘ └──────┘ └──────┘ └──────┘    kill     │
│           Disposable Workers（一次性执行层）        │
└─────────────────────────────────────────────────┘
```

### 3.2 状态交接协议的关键设计

两层之间的交接协议决定了系统的健壮性：

| 交接方向 | 传递内容 | 设计要点 |
|---------|---------|---------|
| **Core → Worker**（分派） | 任务目标、最小必要上下文、工具白名单、收敛窗口 | 不传递全量记忆，只传递当前任务所需的最小集 |
| **Worker → Core**（回收） | 执行结果、半成品、诊断信息、退役日志 | 即使失败也必须输出结构化回执，不能"静默死亡" |
| **Worker → Worker**（继承） | 可选：前任 Worker 的部分上下文 | 由 Core 决定新 Worker 是从零开始还是继承前任 |

### 3.3 收敛窗口与降级策略

成熟的 Harness 应在 Worker 分派时就内建超时和降级：

1. **收敛窗口（convergence window）**：每个 Worker 带有最大等待时长和中间检查点
2. **降级策略（fallback strategy）**：超时后不是简单 kill → respawn，而是先评估"部分产出是否可回收"
3. **退役日志（retirement log）**：被关闭的 Worker 自动输出结构化诊断（做了什么、卡在哪、半成品路径）

---

## 四、产品级 Agent 的质量工程

### 4.1 科研龙虾给出的质量范本

刘思源的科研龙虾在上线后 72 小时内的迭代轨迹，是 2026 年 Agent 产品质量工程的教科书级案例：

| 时间线 | 动作 | 工程意义 |
|--------|------|---------|
| Day 1 | 连夜修 bug（标签数量不对、暗色主题白弹窗、删论文后标签未同步） | 发布后第一时间修复数据一致性问题——Agent 管理高价值数据时容错空间极小 |
| Day 2 | 16 个新功能上线 | 全部来自用户评论和私信——用户反馈是 Skill 迭代的最高效信号源 |
| Day 3 | 测试用例 318 → 1029 | 每个操作、状态变更、文件写入都有自动化测试守着——这是从"能 demo"到"可日用"的分水岭 |
| 持续 | Git 自动提交 | 所有工作区文件变更可回滚——将 Agent 操作从"不可逆"降级为"可回滚" |
| 持续 | 清理 57 个低质 Skill | 431 个 Skill 全经人工遴选——Skill 价值不在数量，在于可信度 |

### 4.2 关键工程数字

> 431 个学术技能 · 28 个本地工具 · 13 个 API 工具 · 150 个 MCP 配置 · 6 个 Dashboard · 21 种消息卡片 · 1029 个单元测试

这种精确的数字披露不是炫技，而是一种 **信任建立策略**：让技术用户能快速评估产品的工程深度。

### 4.3 Skill 质量管理的三条原则

1. **遴选优于堆量**：431 个 Skill 中每一个都经过人工遴选，上线三天又清理了 57 个不达标的。在 AI 生成 Skill 的时代，人工遴选不是低效，而是信任的唯一可信路径
2. **测试粒度对齐到 Skill 级别**：每个 Skill 的每个操作路径都应有自动化验证，而不是只测端到端场景
3. **退化是持续风险**：上线后暴露的问题本质上都是 Skill 内部逻辑或 Skill 间状态一致性的缺陷，需要持续监控

### 4.4 Agent 定义的六要素模型（agency-agents 启发）

> *来源：`Insights/20260318_agency_agents_Persona框架与Swarm编排_insight.md`*

agency-agents（⭐ 52K+）在 112+ 个 Persona 的实践中沉淀出一套 **Agent 定义六要素**，值得作为 Butler sub-agent / skill 定义的通用参考：

```
┌─────────────────────────────────────────┐
│  1. Identity Traits   — 谁？性格/思维方式  │
│  2. Core Mission      — 干什么？职责边界    │
│  3. Success Metrics   — 做到什么算好？      │
│  4. Critical Rules    — 绝对不能做什么？     │
│  5. Workflow Process  — 怎么做？决策链      │
│  6. Deliverables      — 交什么？示例/模板    │
└─────────────────────────────────────────┘
```

**与 Butler sub-agent 的覆盖度对比**：

| 六要素 | Butler 当前覆盖 | 差距 |
|--------|---------------|------|
| Identity | ✅ 有角色描述 | — |
| Mission | ✅ 有职责说明 | — |
| **Success Metrics** | ⚠️ 多数缺失 | 建议补充可量化的成功判据 |
| Critical Rules | ✅ 有约束 | — |
| Workflow | ✅ 有流程 | — |
| **Deliverables** | ⚠️ 多数隐含 | 建议显式化产出物模板 |

**可行动项**：
1. 为 Butler sub-agent/skill 补充 **Success Metrics** 和 **Deliverables** 字段
2. 增加标准化 **YAML frontmatter**（至少包含 name / description / tags / services），便于 planner 做能力匹配
3. "一个 Markdown = 一个新能力" 的极简扩展模式是 Butler skill 体系的理想态之一

### 4.5 从 Persona 库到 Swarm 编排（Registry 架构）

agency-agents 的 PR #117 暴露了一条从静态 Persona 走向程序化编排的演进路径：

```
Agent Markdown → slugify + parse YAML → Agent Registry → Loader API → Swarm Builder → system_prompt + metadata
```

**与 Butler 的对照**：
- Registry ≈ Butler 的 skill shortlist + sub-agent 目录
- Loader ≈ "先看 skill 目录是否命中"
- Swarm Builder ≈ planner 选择 sub-agent/team 组合
- **关键差异**：agency-agents 无状态（每次重新加载），Butler 有状态（task_ledger + 记忆）

agency-agents 证明了：**结构化 Markdown 系统提示词 + 极低贡献门槛 + 多平台注入脚本** 这套组合，仅靠约束层就能创造巨大实用价值。但它也暴露了纯静态 Persona 的天花板：没有记忆就没有成长，没有编排就没有协作，没有观测就没有质量闭环。Butler 在这三个维度已经领先。

---

## 五、AutoResearch 与 AutoResearchClaw：Agent 作为自主进化引擎

### 5.1 核心范式转换

Karpathy 的 autoresearch 项目（37,300+ Stars）提出了一个比"工具调用"更深层的 Agent 使用范式：

**传统 Agent**：人类下指令 → Agent 执行 → 返回结果
**AutoResearch**：人类设计竞技场（目标 + 规则 + 搜索空间 + 自动评估） → Agent 自主在规则内做实验 → 持续进化

在 17 小时的自动实验中，AI 重新"发现"了人类 8 年间逐步发展出的若干技术（如 RMSNorm），从基线 1.506 优化到 0.975（约 35% 提升），且未触及架构性能上限。

### 5.2 竞技场思维的四要素抽象

```
目标（What to optimize）
  + 规则（Constraints & safety bounds）
    + 搜索空间（What can be varied）
      + 自动评估（How to score results）
        = 自主进化循环
```

这套抽象可跨领域迁移——产品迭代、营销策略、增长实验，都可以通过"搭建自动试验场 → 让 AI 在规则内做搜索"来完成。

### 5.3 AutoResearchClaw：从实验竞技场到端到端论文管线

> *来源：`Insights/20260318_AutoResearchClaw_全自主科研管线架构拆解_insight.md`*

如果 autoresearch 是"在一个窄实验空间内自动搜索最优解"，AutoResearchClaw（MIT, ⭐ 4,390+, v0.3.0）则是"把整条科研管线全自动化"：

| 维度 | autoresearch (Karpathy) | AutoResearchClaw |
|------|------------------------|------------------|
| 核心范式 | 实验竞技场：搜索空间 × 自动评估 | 端到端管线：idea → 会议级论文 |
| 产出物 | 实验结果 | 论文 + LaTeX + BibTeX + 代码 + 图表 + Peer Review |
| Agent 数量 | 单 Agent | 多 Agent（CodeAgent / BenchmarkAgent / FigureAgent + 辩论） |
| 自学习 | 无 | MetaClaw 跨轮知识迁移（重试率 -24.8%，鲁棒性 +18.3%） |
| 代码量 | ~630 行 | 23 stages / 8 phases 完整框架 |

**三个产品设计启发**：

1. **Stage-Gated Pipeline + PROCEED/REFINE/PIVOT 决策模型**：不是线性推进，而是在关键节点做三路分支（继续/微调/换方向），带自动回滚和产物版本化。可迁移到 Butler 的心跳任务治理
2. **按产出物类型划分 Agent + 硬验证门控**：CodeAgent / BenchmarkAgent / FigureAgent 各自对产出质量负全责，每个 Agent 自带 AST 验证等硬门控。与 §4.3 Skill 质量管理三原则互补
3. **MetaClaw 自学习**：失败 → 结构化 lessons → 可复用 skills（文件级 SKILL.md）→ 注入后续运行。30 天时间衰减防止过时知识累积。这是 "经验飞轮" 的工程化实现

**"Chat an Idea, Get a Paper"** 是 Skill 型 Agent 产品的极致形态——从一句自然语言输入到完整的学术交付物，中间的 23 个 Stage 全自动编排。与科研龙虾的 431 Skill × 1029 测试的精细化路线形成对照：前者追求端到端管线的深度，后者追求单点 Skill 的广度和质量。

### 5.4 三种 Agent 产品范式的谱系对照

综合 autoresearch、AutoResearchClaw 和 agency-agents，可以归纳出 Agent 定义的三种粒度：

| 粒度 | 代表 | 定义"什么" | 不定义"什么" | Butler 的位置 |
|------|------|----------|------------|------------|
| **Persona 粒度** | agency-agents | "谁来做"（身份 + 约束） | "怎么做" | sub-agent / skill 的角色层 |
| **约束粒度** | autoresearch | "在什么框里做"（目标 + 规则 + 评估） | "谁做" | heartbeat 的任务治理层 |
| **流程粒度** | AutoResearchClaw | "谁做 × 怎么做 × 做到什么程度才过门" | — | 目前未覆盖的端到端管线层 |

Butler 当前在约束粒度和流程粒度之间，Persona 粒度的经验可以补充进 skill/sub-agent 定义规范。

### 5.5 对 Agent 产品设计的总结启示

autoresearch 的 630 行核心代码和 AutoResearchClaw 的 23 Stage 管线共同提醒我们：**Agent 的价值不仅在于执行既定任务，更在于在受控空间内自主探索更优策略。** 产品级 Agent 如果只能被动响应指令，就只是一个花哨的 API 调用器。真正的差异化在于：Agent 能不能在用户划定的边界内，自主寻找更好的做事方式？

---

## 六、"一人公司"的情绪考古学

### 6.1 不只是技术问题，更是人机关系问题

Dior Debby 的叙事里藏着一个被技术讨论忽视的维度——**情绪**。

"既好笑又有点窒息"——一小时内看见二十几个 Agent "毕业"（被关掉重开），认可 Agent 的生产力，但觉得"流水线换下属"有点残酷。这种"共情 + 无奈"的情绪张力在 AI-native 工作者中非常普遍。

科研龙虾作者三天睡不到 10 小时的高强度迭代——独立开发者 + Agent 产品的典型生存状态。Agent 让一个人有了十人团队的产出，但也把一个人推向了十人的工作强度。

### 6.2 对 Butler 的人格设计启示

这些情绪线索直接指向 Butler 应该避免和追求的东西：

| 应避免 | 应追求 |
|--------|--------|
| 让用户感觉自己在"流水线换下属" | 让用户感觉有一个持续理解自己的伙伴 |
| 每次对话都从零开始的"失忆感" | "我记得上次我们做了什么"的连续性体验 |
| 用信息量轰炸制造认知焦虑 | 主动为用户减轻"杀与留"的决策负担 |
| 把心跳播报变成状态罗列 | 把心跳播报变成"建议做什么"的决策辅助 |

---

## 七、Harness 视角下的组织管理学重映射

### 7.1 "一人公司"的隐喻精度

Dior Debby 的"一人公司"比喻精准地指出：MAS 治理面临的问题——招聘（spawn）、考核（convergence check）、裁员（kill）、交接（context transfer）、组织记忆（retirement log）——本质上就是 **组织管理学的老问题，只不过周期从月/年压缩到了分钟/秒**。

| 组织管理概念 | MAS 对应 | 时间尺度压缩 |
|-------------|---------|-------------|
| 招聘 | Agent spawn | 月 → 秒 |
| 试用期考核 | 收敛窗口检查 | 季度 → 分钟 |
| 末位淘汰 | 超时 kill + 替换 | 年 → 分钟 |
| 离职交接 | Context transfer | 周 → 毫秒 |
| 组织记忆 | Retirement log / Task ledger | 持续 → 自动 |
| 企业文化 | System prompt / SOUL | 年 → 即时生效 |

### 7.2 成功的一人公司 AI 团队的关键成功因素

综合 OpenClaw、Autoflowly 和多个案例的实践经验：

1. **隔离**：每个 Agent 在独立容器中运行，独立的记忆、工具访问和资源限制，防止一个失控 Agent 耗尽全局资源
2. **人类审批卡口**：金融交易、公开通信等高风险操作必须经人类确认
3. **分阶段激活**：从"一个 Agent 身兼多职"开始，随工作量增长逐步拆分专职 Agent
4. **结构化决策框架**：为 Agent 的自主决策设定明确的审批准则和升级路径
5. **断路器**：防止 Agent 间的反馈循环失控

---

## 八、与 Butler 架构的系统映射

### 8.1 现状对标

| 本文概念 | Butler 对应 | 当前状态 | 成熟度 |
|---------|------------|---------|--------|
| Persistent Core | Butler 主体（记忆 + 人格 + task_ledger） | 已实现 | ★★★☆☆ |
| Disposable Worker | heartbeat executor / sub-agent | 已有雏形 | ★★☆☆☆ |
| 收敛窗口 | heartbeat 超时回退 | 基础超时 | ★★☆☆☆ |
| 退役日志 | task_ledger 回执 | 有但偏简略 | ★☆☆☆☆ |
| Skill 质量管理 | skills/ 目录 | 有增无减 | ★☆☆☆☆ |
| 测试覆盖 | tests/ 目录 | 部分覆盖 | ★★☆☆☆ |
| 变更可回滚 | 工作区文件操作 | 无系统性保障 | ★☆☆☆☆ |
| 竞技场/自主实验 | heartbeat 周期循环 | 纯执行，无自主探索 | ☆☆☆☆☆ |
| 认知负担管理 | heartbeat 报告 | 信息偏多偏散 | ★☆☆☆☆ |
| 花名/可读标识 | branch id + 角色标签 | UUID 式 | ★☆☆☆☆ |
| **Agent 六要素定义** | sub-agent markdown | 缺 Success Metrics + Deliverables | ★★☆☆☆ |
| **能力 Registry** | skill shortlist（手写） | 未程序化检索 | ★☆☆☆☆ |
| **跨轮自学习** | self_mind + 长期记忆 | 缺结构化 lesson→skill 管线 | ★☆☆☆☆ |

### 8.2 Butler 的自我定位断言

基于本主线的全部分析，Butler 应明确自己的产品定位：

> **Butler 不是 Disposable Agent，而是 Persistent Partner。它的核心差异化在于跨会话记忆、关系连续性和累积学习——这不是附加功能，是存在基础。**

但 Butler 同时需要管理好自己的 Disposable 下属（heartbeat executor、sub-agent），在"持久核心 + 一次性外围"的双层架构中做好状态边界和交接协议设计。

---

## 九、可执行的行动路线

### 近期（1-2 周）

1. **双层生命周期文档**：明确 Butler 主体（Persistent）和 heartbeat executor（Disposable）的状态边界——哪些状态必须回写主体、哪些随 executor 销毁
2. **退役日志协议**：被关闭的 sub-agent 自动输出结构化回执（做了什么、卡在哪、半成品路径），存入 task_ledger
3. **heartbeat 报告精简**：从"发生了什么"转向"建议做什么"，减少用户的认知负担

### 中期（1 个月）

4. **Skill 健康度索引**：为现有 skills 建立评分/使用频率/最后维护日期索引，作为遴选和淘汰依据
5. **关键操作 Git 快照**：在 heartbeat 修改工作区文件前，自动 commit 当前状态作为回滚点
6. **Sub-agent 可读命名**：用 `explorer` / `worker` / `reviewer` 等可读标签替代裸 UUID

### 远期（季度）

7. **Micro-experiment 机制**：在 heartbeat 中对非关键路径的重复性任务，允许自动尝试 2-3 种变体，记录效果差异，逐步积累最优策略
8. **Cron 预设服务模板**：参考科研龙虾的 arXiv 日扫 / 引用追踪 / 周报等预设任务，设计 Butler 版的"开箱即用周期性服务"

---

## 十、学习路径建议

### 阅读顺序

1. **概念入门**：先理解"Persistent vs Ephemeral"的核心分野（本文第一节）
2. **产业实践**：一人公司架构的三种拓扑 + 五层递归委托的真实挑战（本文第二节）
3. **架构设计**：双层生命周期 + 状态交接协议（本文第三节）
4. **质量工程**：科研龙虾的质量范本 + Skill 管理三原则（本文第四节）
5. **范式前瞻**：AutoResearch 竞技场思维（本文第五节）

### 推荐精读

| 优先级 | 文章/素材 | 核心价值 |
|--------|---------|---------|
| ★★★ | Computer Agents Blog: Persistent vs Ephemeral 2026 | 唯一有量化数据的生命周期对比 |
| ★★★ | 科研龙虾 72h 迭代战报 | Agent 产品质量工程的教科书级案例 |
| ★★☆ | Dior Debby 一人公司五层构架 | MAS 治理的情绪与认知维度 |
| ★★☆ | Karpathy autoresearch 项目 | 自主进化范式的概念验证 |
| ★★☆ | James Carr: Seven Hosting Patterns for AI Agents | 生产部署的 7 种托管模式 |
| ★☆☆ | OpenClaw / Autoflowly 案例 | 一人公司 AI 委托的实战参考 |

---

> **文档版本**：v1.1 (2026-03-18)
> **整合素材**：4 篇 standalone Insight + 2 篇 Raw + 1 篇 AutoResearch 实验记录 + 2 次网络搜索 + 2 篇新增 Insight（AutoResearchClaw + agency-agents）
> **v1.1 增量**：新增 §4.4 Agent 定义六要素模型（agency-agents）、§4.5 Registry 架构、§5.3 AutoResearchClaw 端到端管线范式、§5.4 三种 Agent 产品范式谱系对照、架构映射表增加三行新维度
> **状态**：v1.1 — 归入 AutoResearchClaw + agency-agents 洞察，后续可按需深化"双层交接协议"或"竞技场/管线机制设计"
