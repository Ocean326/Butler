# 周五组会分享材料：AI Agent 自主科研——从"养龙虾"到 Harness Engineering

> **汇报人**：[TODO: 填写汇报人姓名]
> **日期**：2026-03-20（周五）15:00
> **准备日期**：2026-03-18（v8 · 补充会前清单 + 飞书能力扩展证据）
> **时长建议**：~5 分钟口头汇报（配 slides 可视化关键表格与光谱图）+ 2 分钟弹性 Q&A
> **素材来源**：BrainStorm 41 Insight + 10 主线 + 8 自主科研 Agent 全景调研 + 3 仓库源码深潜 + S 级博客巡检 2 轮 + 飞书 skill 实战
>
> **三段式结构**：开场（范式变迁）→ 中段（龙虾为什么火 + 技术根基）→ 收尾（Butler 实践与展望）
> **演讲备忘**：每节开头粗体句即口头 hook，可直接朗读；表格留给 PPT，不逐行念。
>
> **⚠️ 会前清单（非汇报内容，仅供会前自检）**：
> - [ ] 移动端第三方测试——确认验收状态，准备口头同步（来源：上次会议纪要）
> - [ ] 上次会议纪要回顾（飞书链接已存档，需提前读一遍 `QvXLdALtMoJcZrxL34vcsI1ynvT`）
> - [ ] 汇报人姓名填写 + PPT 制作
> - [ ] 试讲一遍控制在 5 分钟内

---

## 〇、一句话预告

> **2026 年 Q1，"让 AI 自己做科研"从论文概念变成了可 `git clone` 运行的现实。本次分享拆解这波浪潮的核心架构模式，以及它对我们自己做 AI Agent 的启示。**

---

## 一、【开场】AI 范式正在发生什么变化？

**先讲一个数字：17 小时 vs 8 年。** Karpathy 今年 3 月发布的 autoresearch 项目里，AI 在 17 小时内重新发现了人类花 8 年才逐步摸索出来的模型训练技术——比如 RMSNorm——性能提升约 35%。这不是论文里的理论推演，是可以 `git clone` 下来自己跑的真实项目。

这件事让我意识到，AI 的角色正在发生根本性的变化：

```
2023  人写 Prompt → AI 回答          （工具范式）
2024  人拆步骤 → AI 逐步执行          （助手范式）
2025  人设边界 → AI 自主循环探索       （Agent 范式）
2026  人设竞技场 → AI 自主进化         （自主科研范式）
```

**关键转折**：人类的价值从"亲手做实验"迁移到"设计实验竞技场"——定义规则、约束、评估函数和搜索空间，然后放手让 AI 高频迭代。

---

## 二、【中段-上】"养龙虾"为什么火？

**这两周朋友圈被"养龙虾"刷屏了——深圳线下排队排到千人。一个 AI 项目能让 9 岁小孩和 70 岁老人同时上头，背后发生了什么？**

### 2.1 三个现象级事件

| 事件 | 规模 | 核心特征 |
|------|------|---------|
| **OpenClaw 养龙虾** | 深圳线下千人排队、4 万+公网实例 | 零编码部署、用户 9-70 岁全覆盖 |
| **科研龙虾（刘思源）** | 431 skills、1029 测试、72h 极限迭代 | Skill 型 Agent 产品工程标杆 |
| **傅盛 14 天养成日记** | 1157 条消息、22 万字、1→8 Agent 团队 | 用户-AI 共同演化实证 |

### 2.2 为什么火？三重门槛同时跌破临界点

**三件事同时发生**：部署门槛降（Docker 四步起）、使用门槛降（对话即训练）、认知门槛降（"养宠物"隐喻）。更深层的原因——养龙虾同时触发了三种此前 AI 工具很少满足的需求：

| 维度 | 旧的工具范式 | 养成/伙伴范式 | 为什么重要 |
|------|---------|-------------|-----------|
| **情感连接** | 用完即走 | "它记得我"、越养越有感情 | 用户留存和主动回访的核心动力 |
| **任务能力** | 单次问答 | 431 个 skill、可以真干活 | 不只是玩具，有实用价值 |
| **长期演化** | 无状态、每次从零开始 | 跨会话持久化、越用越强 | 价值曲线从扁平变成上升 |

> **从"用完即走的工具"到"越用越懂你的伙伴"——这句话终于不再只是产品文案。**

**量化证据**（Computer Agents Blog 2026）：持久 Agent 在 7 天连续任务上完成率 87%，无状态 Agent 仅 22%——**差距近 4 倍**。持久化记忆不是锦上添花，是决定 Agent 能不能真正有用的分水岭。

---

## 三、【中段-下】技术根基：8 个自主科研 Agent 全景扫描

**文化现象背后一定有技术根基。** 我们扫描了 GitHub 2024-2026 年全部主要自主科研 Agent 项目，并对三个代表性仓库做了源码级深潜。

### 3.1 全景速览（PPT 放完整表，口头只讲前三行）

| 项目 | Stars | 架构模式 | 核心特征 |
|------|-------|---------|---------|
| autoresearch (Karpathy) | 40.5K | 极简约束 | 3 文件 630 行，5 分钟/轮自动实验 |
| AI Scientist v1 (Sakana) | 12.4K | 模板驱动流水线 | $15/篇自动论文，Aider 代码修改 |
| AI Scientist v2 | 2.3K | Agentic 树搜索 | 去模板化，首篇 AI 论文通过 ICLR 同行评审 |
| Agent Laboratory | 5.4K | 人机协作三阶段 | co-pilot 模式，成本仅 $2.33/run |
| AutoResearchClaw | 4.4K | 全管线编排 | 23 stage、MetaClaw 自学习 |
| EvoScientist | 850 | 多Agent+进化记忆 | 双持久记忆、Elo 排名、6 篇论文全被接收 |
| DeepScientist | 540 | 贝叶斯优化循环 | 连续运行数周、两周追平人类三年进展 |
| agency-agents | 52K | Persona-as-Markdown | 112 个 Agent 人设、零代码贡献门槛 |

### 3.2 核心发现一：三种 Harness 哲学

> **⭐ 汇报要点 #1 —— 口头 hook：「做完架构拆解，我们发现这些项目分成了三大阵营，核心分歧是一个问题：你给 AI 多少自由度？」**

对这些项目做架构拆解后，我们发现它们对应三种不同的"约束 AI 行为"的设计哲学：

```
                    ┌────────────────────────────────────────────┐
                    │       Harness Engineering 光谱             │
                    │                                            │
  极简约束 ◀━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━▶ 全管线编排   │
                    │                                            │
  autoresearch      │   EvoScientist    AI-Sci v2    Agent Lab   │  AutoResearchClaw
  (3文件/1指标)     │   (进化记忆)      (树搜索)     (co-pilot)  │  (23 stage)
                    │                                            │
  减法式 Harness    │        自适应约束（2026 新兴趋势）          │  加法式 Harness
                    └────────────────────────────────────────────┘
```

**三种哲学的本质差异**：

| 范式 | 代表 | 核心假设 | 适用场景 |
|------|------|---------|---------|
| **极简约束** | autoresearch | Agent 足够强，窄约束下表现更好 | 有单一指标的搜索优化 |
| **全管线编排** | AutoResearchClaw | Agent 需要被 stage 级引导和约束 | 端到端复杂流程 |
| **进化/自适应** | EvoScientist、DeepScientist | 约束应随经验动态调整 | 长周期、需要积累的任务 |

**Karpathy 的核心洞察**："把研究重新格式化为 Agent 友好的优化问题，比给 Agent 更多自由度更有效。"

### 3.3 核心发现二：记忆是 Agent 演化的关键分水岭

> **⭐ 汇报要点 #2 —— 口头 hook：「如果说 Harness 决定了 Agent 的上限，那记忆决定了它能不能越用越强。」**

| 记忆类型 | 代表项目 | 效果 |
|---------|---------|------|
| **无记忆** | autoresearch, AI Scientist v1/v2 | 每次从零开始，擅长单次深度探索 |
| **进化记忆** | EvoScientist（双持久记忆） | 跨周期积累，Elo 排名筛选最佳 idea |
| **贝叶斯累积** | DeepScientist（Findings Memory） | 智能平衡探索/利用，运行数周 |
| **自动技能提取** | AutoResearchClaw（MetaClaw） | 失败自动转 skill → 重试率 -24.8%、鲁棒性 +18.3% |

**关键结论**：**MetaClaw 的"失败 → 教训 → 技能 → 注入下轮"是目前最接近"经验飞轮"落地的实现**。大多数 Agent 系统停在"记日志"阶段，缺少自动从失败中提炼可复用策略的能力。

### 3.4 核心发现三：五个跨项目共识 + Markdown 趋势

> **⭐ 汇报要点 #3 ——「这些团队互不认识、哲学对立，但在五件事上不约而同做了同样选择。」**

| 共识模式 | 一句话 | 例证 |
|---------|-------|------|
| **不可变信任边界** | Agent 不能篡改评估标准 | autoresearch 锁死 prepare.py |
| **时间预算硬约束** | 质量-效率权衡内化到搜索 | 5 分钟/轮、300s/experiment |
| **失败即数据** | 失败不留痕才是最大风险 | MetaClaw 自动从失败提取 lesson |
| **单一入口点** | 接口越简单越好 | `program.md`、`researchclaw run` |
| **Git 原生基础设施** | 版本控制即状态管理 | 好结果留分支、坏结果 reset |

> **附带趋势（加分项）**：Markdown 正在成为 Agent 的"操作系统"——autoresearch 的 `program.md` 就是编排层本身，agency-agents 52K⭐ 一个 Markdown 文件定义一个完整 Agent。Agent 定义正分化为三种粒度：Persona 粒度（"谁来做"）、约束粒度（"在什么框里做"）、流程粒度（"怎么做到什么程度"）。当模型足够强，pipeline stage 将递减，最终形态可能是"一个 program.md + 几个关键门控"。

---

以上三个核心发现——Harness 光谱、记忆分水岭、五大共识——构成了自主科研 Agent 的"技术地形图"。**接下来：这跟我们在做的事有什么关系？**

---

## 四、【收尾-上】实践感悟：做 Butler 的体会

**我做 Butler 几个月，回看这些调研最大感受：我们在同一方向上，只是还没把几块关键拼图拼起来。**

### 4.1 Butler 和这些项目的映射

Butler 是持久化 AI 伙伴系统（跨会话记忆 + heartbeat 循环 + skill 体系）。四个最关键的映射：

| 外部机制 | Butler 对应 | 启发 |
|---------|-------------|------|
| autoresearch 5 分钟实验循环 | heartbeat 周期循环 | 已有基础设施，可嵌入 micro-experiment |
| MetaClaw 经验飞轮 | **Butler 最大空白** | 停在"记日志"阶段，缺自动反哺 |
| agency-agents 六要素 Persona | skill / sub-agent 定义 | 需补 Success Metrics 与 Deliverables |
| 工具生态自扩展 | **Butler 已验证**：自主调研 API → 当天建成 feishu-doc-read skill | Agent 按需给自己"长新技能" |

### 4.2 一个核心感悟

> **⭐ 本次分享最重要的一句话：Harness（约束）比 Model（模型）更重要。**

**口头版**：如果你今天只记住一件事，就记住这个——不急着换更贵的模型，先把约束机制做好。

两组定量证据：

1. **LangChain 实证**：同一模型换 Harness，准确率 +13.7pp。模型没变，只改了约束方式。
2. **DeepMind AutoHarness（3/14 刚发）**：78% Agent 失败来自非法动作；小模型+自动约束在 145 个游戏中击败大模型——**约束质量比模型参数量更决定上限**。

**实操优先级**：先做经验飞轮、先把失败变成数据、先优化 handoff——ROI 远高于升级模型。

### 4.3 外部对标：三个仓库的源码级启示（0318 深潜）

> **口头 hook：「我们源码级地拆了三个仓库，每个都给 Butler 指出了一个最该补的方向。」**

| 仓库 | 一句话启示 |
|------|----------|
| **Karpathy/autoresearch** (40.5K⭐) | 630 行 = 完整 Agent Runtime。启示：**核心循环保持极简**，复杂度推到 skill 层。 |
| **AutoResearchClaw** (4.4K⭐) | MetaClaw「失败→lesson→skill→注入下轮」= 当前最成熟的经验飞轮。启示：**Butler 最缺的就是结构化失败提炼**。 |
| **agency-agents** (52K⭐) | 112 个 Persona 全靠 Markdown，零代码门槛。启示：**skill 定义补齐 Success Metrics 与 Deliverables**。 |

> **一句话总结**：极简循环（autoresearch）给骨架，经验飞轮（MetaClaw）给肌肉，Persona 规范（agency-agents）给皮肤——Butler 三者都需要。

---

## 五、【收尾-下】下一步与展望

**从调研到落地，每一步都有成功先例支撑。**

| 时间线 | 行动 | 对标的成功先例 | 状态 |
|--------|------|--------------|------|
| 本周 ✅ | **Prompt 两轨制重构**——talk/heartbeat 分轨，执行链路标准化 | autoresearch 的单一入口点 | 已落地 |
| 本周 ✅ | **飞书 skill 自扩展**——Butler 自主调研 API 并建成 feishu-doc-read skill | Agent 按需长能力 | 已建成待权限 |
| 本周 | **结构化 Handoff 协议**——executor 回执引入 4 字段交接摘要 | autoresearch 的单一入口点 | 进行中 |
| 本周 | **失败分类标签**——task_ledger 失败回执加 failure_class | 五大共识之"失败即数据" | 规划中 |
| 月级 | **经验飞轮 MVP**——heartbeat 加"失败提取 → 沉淀 → 注入"最小链路 | MetaClaw 模式 | 规划中 |
| 季度 | **micro-experiment**——重复任务自动尝试策略变体 | autoresearch 5 分钟实验循环 | 远景 |

> **展望**：随着 frontier 模型能力持续增强，管线的 stage 数量会减少，更多编排逻辑会被压缩成自然语言协议。最终形态可能是"一个 program.md + 几个关键门控"。**我们现在投入约束机制和经验飞轮，就是在为那个终态做基础设施准备。**
>
> **能力扩展方向（已启动）**：Butler 已验证"Agent 自主扩展工具生态"的可行性——自主调研飞书开放平台 API，当天建成 feishu-doc-read skill（聊天记录 ✓ → 云文档读取 ✓ → 写文档 → 多维表格），下一步接入日历/提醒能力，逐步覆盖工作助手高频场景。

---

## 六、一页纸总结（PPT 最后一页 / 可截图分享）

```
┌──────────────────────────────────────────────────────────────┐
│  AI Agent 自主科研：2026 Q1 全景                               │
│                                                               │
│  ① 范式变迁：人从"亲手做"→"设竞技场"                           │
│     AI 17h 重现人类 8 年成果 (Karpathy autoresearch)           │
│                                                               │
│  ② 三种 Harness 哲学 × 三种 Agent 定义粒度                     │
│     极简约束 ←→ 自适应进化 ←→ 全管线编排                        │
│     Persona粒度 · 约束粒度 · 流程粒度                          │
│                                                               │
│  ③ 五大跨项目共识：                                            │
│     不可变信任边界 · 时间预算硬约束 · 失败即数据                  │
│     单一入口点 · Git 原生基础设施                               │
│                                                               │
│  ④ 核心判断：Harness > Model                                   │
│     LangChain +13.7pp · DeepMind 小模型+约束胜大模型            │
│                                                               │
│  ⑤ 养成式 AI = 2026 范式转移                                   │
│     记忆 + 进化 + 共同成长 · 持久Agent完成率 4× 无状态Agent     │
│     附: Markdown→Agent OS · 六要素 Persona (agency-agents)     │
│                                                               │
│  ⑥ Butler 实证：Agent 能给自己"长新技能"                        │
│     自主调研 API → 当天建成 feishu-doc-read skill               │
│     Prompt 两轨制重构已落地 · 路线图本周 2/4 项已完成           │
└──────────────────────────────────────────────────────────────┘
```

---

## 附录：素材索引

| 素材 | 路径 |
|------|------|
| 8 个自主科研 Agent 全景对比 | `BrainStorm/Raw/daily/20260318/20260318_autonomous_science_agents_landscape.md` |
| autoresearch vs AutoResearchClaw 对照分析 | `BrainStorm/Insights/standalone_archive/early_insight/20260318_autoresearch_vs_autoresearchclaw_harness_对照分析.md` |
| AutoResearchClaw 全自主科研管线架构拆解 | `BrainStorm/Insights/standalone_archive/20260318_AutoResearchClaw_全自主科研管线架构拆解_insight.md` |
| agency-agents Persona 框架与 Swarm 编排 | `BrainStorm/Insights/standalone_archive/20260318_agency_agents_Persona框架与Swarm编排_insight.md` |
| 科研龙虾 72h 迭代工程启示 | `BrainStorm/Insights/standalone_archive/20260318_科研龙虾72h迭代_Skill型Agent产品工程启示_insight.md` |
| 科研龙虾与低门槛养 AI 范式（大整合） | `BrainStorm/Insights/standalone_archive/early_insight/05_科研龙虾与低门槛养AI范式_20260318.md` |
| 跨主线落地路线图（22 条行动项） | `BrainStorm/Insights/mainline/Butler_跨主线落地路线图_2026Q1.md` |
| S 级博客巡检（DeepMind AutoHarness / Aletheia） | `BrainStorm/Raw/daily/20260318/20260318_S级博客巡检_第二轮.md` |
| BrainStorm 十条主线综合 | `BrainStorm/STATE.md` |
| feishu-doc-read skill（能力自扩展实证） | `butler_main/butler_bot_agent/skills/feishu-doc-read/SKILL.md` |
| Prompt 两轨制重构交付稿 | `docs/daily-upgrade/0318/0149_butler_prompt_refactor_guidance_v2.md` |

---

## 交付前 TODO（供用户决策）

- [ ] **汇报人姓名**：文档头部 `[TODO: 填写汇报人姓名]` 待填
- [ ] **PPT/Slides 制作**：本文为口头稿+备注级内容，尚未转为 PPT。建议 7-9 页 slides：范式变迁时间线、养龙虾三重门槛、Harness 光谱图、记忆对比表、Harness > Model 证据页、三仓库一句话对照、路线图（含状态标记）、能力自扩展实证
- [ ] **时间控制排练**：5 分钟 target（+2 分钟弹性 Q&A），建议对着稿子试讲一遍；第三节口头只讲光谱图 + 记忆分水岭 + 五大共识即可
- [ ] **数据核实**：Computer Agents Blog 2026 的"持久 Agent 完成率 87% vs 无状态 22%"数据，建议确认原始出处链接
- [ ] **移动端第三方测试**：会前确认验收状态（来源：上次会议纪要），准备口头同步进度
- [ ] **上次会议纪要**：提前阅读飞书文档 `QvXLdALtMoJcZrxL34vcsI1ynvT`，梳理遗留事项

---

*v9 · 0318 晚间状态检查：BrainStorm Insight 计数 38→41（散碎归档完成）；feishu-doc-read / 8 Agent 调研 / 移动端测试提醒已确认在文中 · 2026-03-18*
*v8 · 补充会前清单+飞书能力扩展实证+路线图状态标记+移动端测试提醒 · 2026-03-18*
*v7 · 精炼压缩版（5 分钟密度 · 三段式 · 每节≤3 要点）· 2026-03-18*
*v6 · 交付准备级 · 语言润色+口语化 · 2026-03-18*
*v5 · 结构终审 · 2026-03-18*
