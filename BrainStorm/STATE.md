# 当前状态机

> 当前「我在哪、最近在想什么、要做什么、还在悬着的问题、手头资产」的快照。由「更新状态机」或定时任务刷新。

---

## 我在哪里

- BrainStorm 已进入 **结构治理 + 维护态**：默认入口切换为 `Insights/README.md` 自动知识目录；阅读、归档、主线回看不再靠手工找文件。
- 当前结构按 **Raw → Working → Insights(mainline/standalone_archive) → STATE** 运转；其中 `Insights/README.md` 与 `Insights/index.md` 由 `BrainStorm/tools/refresh_brainstorm.py` 自动刷新。
- 当前资产快照（2026-03-19）：`Raw/` 54 个文本/JSON 资产 + 98 个图片资产，`Working/` 27 篇工作稿，`Insights/` 10 篇主线文档 + 1 篇跨主线总图 + 36 篇归档洞察。
- **十条主线 Insight 综合 + 跨主线落地路线图全部完成**，已进入维护态——后续仅在新增 Raw/Working 素材时追加。
- **v1.1 更新**：主线⑩已迁入 `Insights/mainline/` 标准路径，补充 MetaClaw 结构化经验管线 + Ouroboros-joi 安全事件实证。全部 10 条主线现已统一存放于 `Insights/mainline/`。
- **v2.2 质量审计**（2026-03-18 heartbeat-executor）：全 10 条主线抽查确认内容深度达标。主线④ 经 v2.1（Opus 4.6 compaction）→ v2.2（MetaClaw 跨轮知识迁移）两轮增补。主线⑤⑥⑦ 实际均已升至 v1.1（含 #16 AutoResearchClaw + #17 agency-agents 洞察），索引已对齐。
- **v1.1 主线批量升级**（2026-03-18）：#16 AutoResearchClaw + #17 agency-agents 调研成果整合进主线①②⑨，三条主线同步升至 v1.1。

## 十条主线综合概览（2026-03-18 完成）

| # | 主线 | 关键结论 | 路径 |
|---|------|---------|------|
| ① | Harness Engineering | Harness 是 Agent 一等基础设施；v1.1 新增 MetaClaw 经验飞轮实证 + Harness 重量级光谱 | `Insights/mainline/Harness_Engineering_主线知识体系.md` |
| ② | Agent 架构原则与模式 | 四件套同构；v1.1 新增三种定义粒度 + 六要素模型 + Stage-Gated Pipeline | `Insights/mainline/Agent_架构原则与模式_主线知识体系.md` |
| ③ | Claude Code / Coding Agent 工程化 | 工程化 ≠ 架构复杂化，每步只加一个机制 | `Insights/mainline/Claude_Code_Coding_Agent_工程化_主线知识体系.md` |
| ④ | 记忆与上下文工程 | Compress 是最大短板；handoff 交接标准化是第一优先；v2.2 新增 MetaClaw 跨轮知识迁移 + Opus 4.6 compaction | `Insights/mainline/记忆与上下文工程_主线知识体系.md` |
| ⑤ | Agent 评估·安全·自治度 | 评估 ≠ Benchmark 刷分；CLASSic/TRACE 多维评估 + 自治度分级是落地关键 | `Insights/mainline/Agent_评估_安全_自治度_主线知识体系.md` |
| ⑥ | Agent 产品形态·生命周期·一人公司架构 | Ephemeral 与 Persistent 两种范式必须共存；一人公司需要 5-7 专家 Agent | `Insights/mainline/Agent_产品形态_生命周期_一人公司架构_主线知识体系.md` |
| ⑦ | Anthropic 前沿研究·自省·对齐·人格设计 | 自省有用但不可靠；人格稳定靠 assistant axis 而非角色扮演；对齐必须防伪装 | `Insights/mainline/Anthropic_前沿研究_自省_对齐_人格设计_主线知识体系.md` |
| ⑧ | 自律系统与行为约束 | 真正自律需 prompt 之外独立检查机制（Hook/SDD/运行时宪法） | `Insights/mainline/自律系统与行为约束_主线知识体系.md` |
| ⑨ | 多智能体系统（MAS）与协作模式 | 协调税真实存在；v1.1 新增按产出物分 Agent + Debate 机制 + Swarm Registry | `Insights/mainline/多智能体系统_MAS_与协作模式_主线知识体系.md` |
| ⑩ | 自我进化与实验竞技场 | 从被动执行到自主进化；Darwin Gödel Machine/Ouroboros 等前沿框架指明方向；v1.1 新增 MetaClaw 经验管线 + Ouroboros-joi 安全事件实证 | `Insights/mainline/自我进化与实验竞技场_主线知识体系.md` |
| — | 跨主线落地路线图 | 50+ 改进建议去重为 24 条，按 P0-P3 排列；新增 `agent_os` 双层运行时与 `orchestrator` 控制面分层 | `Insights/mainline/Butler_跨主线落地路线图_2026Q1.md` |

### 跨主线交叉综合

| 主题 | 综合文档 | 覆盖 |
|------|---------|------|
| Agent 自治治理 | `自律信任行为边界_Agent自治的治理工程` | 自律系统 × 信任校准 × 行为边界 × 运行时宪法 |

## 行动项（跨主线路线图 P0-P2 摘要）

1. **P0** 结构化 Handoff 协议 v0（来自④⑨③共识——4 字段交接摘要）
2. **P0** MAST 失败分类标签 FC1/FC2/FC3（来自⑨⑤）
3. **P0** 退役日志协议（来自⑨⑥⑧共识——6 字段退役摘要）
4. **P0** 高危动作分级白名单（来自⑧自治治理综合）
5. **P1** 语义压缩层：完整版存盘 + 紧凑版入 prompt（来自④）
6. **P1** 独立 trajectory 裁决层（来自⑧自治治理综合）
7. **P1** 自省 checkpoint：每 5 步结构化自省快照（来自⑦）
8. **P1** 任务复杂度 → 引擎路由（来自⑨）
9. **P2** `agent_os` 双层运行时定型：`Agent Runtime` / `Process Runtime` 分层，`approval / verification / recovery` 真源收回运行时（来自①②④）
10. **P2** `orchestrator` 控制面分层：`Mission / Node / Branch / Ledger` 作为真源，目录按 `domain / application / compile / runtime bridge / infra / interfaces / frameworks / fixtures` 收口（来自①②⑨）

> 完整 24 条行动项见 `Insights/mainline/Butler_跨主线落地路线图_2026Q1.md`

## 维护审计记录（2026-03-18 晚）

- **触发**：planner 指令要求"推进 ④⑤⑥⑦ 主线整合"
- **诊断**：planner 任务描述基于过时状态快照——实际上全部 10 条主线已于今日早期轮次全部完成 v1.0-v2.2
- **执行**：全量扫描 37 个 Raw + 27 个 Working + 38 个 Insights + 9 个 Insight 文件，确认无遗漏内容
- **发现**：Simon 系列 `xiaohongshu_687726400000000010012960` 是 #03 的重复抓取（同一 noteId），已在索引中标注；OCR 资产（~10 文件）全部失败（缺基础设施），不影响文本 Insight 质量
- **收尾**：主线④索引 v2.1→v2.2、主线⑤⑥⑦索引 v1.0→v1.1 对齐；补录遗漏的 S10 对照分析 Insight
- **结论**：维护态确认，④⑤⑥⑦ 全部收口。后续新增素材（Simon 系列 P0 帖子等）到位后再追加

## 每日博客巡检进度（2026-03-18）

| 轮次 | 覆盖站点 | 新信号数 | 产出 |
|------|---------|---------|------|
| 首轮 | OpenAI / Anthropic / LangChain | 4 条 | `Raw/daily/20260318/20260318_S级博客巡检_首轮.md` |
| 第二轮 | DeepMind / HuggingFace / GitHub Trending | 4 条 | `Raw/daily/20260318/20260318_S级博客巡检_第二轮.md` |

第二轮关键发现：
- **DeepMind AutoHarness**（P0）：模型自生成运行时约束代码，小模型胜大模型，直接证明 harness > model
- **DeepMind Aletheia**（P1）：Generator-Verifier-Reviser 三段式全自主科研 agent + AI 自主性分级体系
- **NVIDIA NeMo Agentic Retrieval**（P2）：ReACT 迭代检索 pipeline，MCP → in-process 工程取舍
- **Holotron-12B**（P2）：SSM+Attention 混合架构 computer-use agent，2x+ 吞吐提升

S 级站点本日两轮全覆盖。下一轮可切 A 级站点。

## 待思考问题

- 22 条改进项从哪几条开始试点？先走 prompt 协议层（P0 文档/配置改动）还是先动代码？
- 和 Butler 的对话以后要不要定期往 BrainStorm 里沉？沉哪一层（Raw / Insights）？
- ⑩ 自我进化的实验竞技场如何在 Butler 中最小化落地？

## 资产索引

- `MEMORY.md`：长期记忆
- `Raw/`：54 个文本/JSON 资产 + 98 个图片/OCR 资产
- `Working/`：27 个加工中间稿
- `Insights/README.md`：自动生成的知识目录 / 知识树入口
- `Insights/`：10 篇主线文档 + 1 篇跨主线总图 + 36 篇归档 Insight
- `Archive/`：月度总结归档（待启用）
