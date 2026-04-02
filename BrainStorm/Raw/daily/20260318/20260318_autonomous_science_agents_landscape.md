# Autonomous Science / AI Research Agent 项目全景比较

> 调研日期: 2026-03-18
> 范围: GitHub 上 2024-2026 年主要的自主科研 Agent 项目（排除已研究的 AutoResearchClaw, Karpathy autoresearch, agency-agents）

---

## 一、项目速览表

| 项目 | 仓库 | Stars | 发布时间 | 架构模式 | 核心定位 |
|------|------|-------|----------|----------|----------|
| AI Scientist v1 | `SakanaAI/AI-Scientist` | ~12,400 | 2024-08 | 模板驱动线性流水线 | 端到端自动论文生成(ML领域) |
| AI Scientist v2 | `SakanaAI/AI-Scientist-v2` | ~2,300 | 2025-04 | Agentic 树搜索(BFTS) | 去模板化, 跨领域开放探索 |
| EvoScientist | `EvoScientist/EvoScientist` | ~850 | 2026-01 | 多Agent + 进化记忆 | 自进化的多Agent科研系统 |
| Agent Laboratory | `SamuelSchmidgall/AgentLaboratory` | ~5,400 | 2025-01 | 三阶段流水线 + Human-in-loop | 人机协作的研究助手 |
| DeepScientist | `ResearAI/DeepScientist` | ~540 | 2025-09 | 贝叶斯优化 + 累积记忆 | 长周期前沿突破性发现 |
| Curie | `Just-Curieous/Curie` | ~340 | 2025-02 | 实验严谨性引擎(Rigor Engine) | 自动化严谨科学实验 |
| OpenResearcher (TIGER) | `TIGER-AI-Lab/OpenResearcher` | ~430 | 2026-02 | 长程深度研究轨迹合成 | 开源深度研究模型训练 |
| Sparks | `lamm-mit/Sparks` | ~18 | 2025 | 多模态多Agent闭环 | 蛋白质科学等实验科学 |

---

## 二、逐项目详细分析

### 1. SakanaAI/AI-Scientist (v1)

**Stars:** ~12,400 | **许可:** Apache-2.0 | **语言:** Python

**做什么：** Sakana AI 开发的全自动科研系统。给定一个人工编写的代码模板（如 NanoGPT、2D Diffusion、Grokking），系统自动生成研究想法、修改代码执行实验、可视化结果、撰写完整 LaTeX 论文，并通过自动 peer review 评估质量。每篇论文成本约 $15。

**核心架构：模板驱动线性流水线 (Template-Driven Linear Pipeline)**

```
Template → Idea Generation → Novelty Check (Semantic Scholar)
  → Experiment (Aider 改代码 + 执行) → Paper Write-up (LaTeX)
  → Automated Review → [Optional] Improvement
```

**关键设计决策：**
- **模板系统**：每个研究领域需要人工创建 template 目录（`experiment.py` + `plot.py` + `prompt.json` + `seed_ideas.json`），这是最核心的约束 harness
- **Aider 作为代码修改工具**：不直接让 LLM 生成代码，而是通过 `aider-chat` 库在已有模板代码上做增量修改
- **批量并行**：`launch_scientist.py` 支持 `--parallel` 参数并行处理多个 idea，每个 idea 独立走完整流水线
- **自动 Reviewer**：内置评审 agent，据称接近人类评审准确度
- **成本控制**：每 idea 完整流程 ~$15，明确的 cost ceiling

**Harness 工程视角：**
- 模板是 **硬约束 harness**：领域边界完全由模板定义，AI 只能在模板框架内操作
- 线性流水线意味着每个阶段的输入/输出接口是固定的，调试和可观测性好
- 缺点：扩展到新领域需要人工建模板，灵活性受限

---

### 2. SakanaAI/AI-Scientist-v2

**Stars:** ~2,300 | **许可:** Apache-2.0 | **语言:** Python

**做什么：** v1 的重大升级。去掉了人工模板依赖，改用 agentic 树搜索架构，由一个 Experiment Manager Agent 引导广度优先树搜索（BFTS），在假设空间中探索。已产出首篇通过 ICLR 2025 Workshop 同行评审的全 AI 生成论文。

**核心架构：Agentic 广度优先树搜索 (Agentic BFTS)**

```
Input Idea (JSON) → bfts_config.yaml 配置
  → Experiment Manager Agent 引导树搜索
    → 节点 = 假设/实验配置/结果/分析
    → 广度优先展开, 动态剪枝
  → Plot Aggregation → Paper Write-up → VLM Review
```

**关键设计决策：**
- **去模板化**：不再需要人工 template 目录，用 JSON idea 文件 + YAML 配置替代 → 极大降低人工门槛
- **移除 Aider**：不再依赖 `aider-chat`，代码生成/修改完全集成在 Agent Manager 内部的 LLM 调用中
- **细粒度模型选择**：`--model_agg_plots`, `--model_writeup`, `--model_citation`, `--model_review` 分别指定不同子任务的 LLM，允许成本优化
- **VLM Review**：引入视觉语言模型审查图表/引用质量，增加了输出验证维度
- **图结构管理**：引入 `python-igraph` 管理搜索树，`omegaconf` 管理复杂配置
- **单 idea 深度探索**：每次运行只处理一个 idea 的深度探索（vs v1 的多 idea 并行浅扫描）

**Harness 工程视角：**
- 从 **硬约束 harness** 转向 **软约束 harness**：idea JSON + YAML config 定义搜索边界，但内部探索高度自由
- 树搜索是真正的"探索性"架构，trade-off 是可靠性下降、计算成本上升、输出方差增大
- 对初始 idea 的质量高度敏感——idea 质量 ≈ 模板的替代品
- 配置复杂度高，需要 YAML 管理搜索参数

---

### 3. EvoScientist/EvoScientist

**Stars:** ~850 | **许可:** MIT | **语言:** Python | **论文:** arXiv:2603.08127 (2026-03)

**做什么：** 自进化多 Agent 科研框架。包含 3 个核心 Agent（Researcher、Engineer、Evolution Manager），通过持久化记忆在多次研究周期中不断改进研究策略。在 DeepResearch Bench II 排名第一，6 篇论文全部被 ICAIS 2025 接收（含最佳论文）。

**核心架构：多 Agent + 双树搜索 + 进化记忆 (Multi-Agent Evolving)**

```
Researcher Agent (RA) ─── Idea Tree Search ──→ 排名（Elo Tournament）
                                                    ↓
Engineer Agent (EA) ─── Experiment Tree Search ──→ 代码实现+执行
                                                    ↓
Evolution Manager (EMA) ─── 蒸馏洞察 ──→ Ideation Memory + Experimentation Memory
                                                    ↓
                                              反馈到下一轮 RA/EA
```

**关键设计决策：**
- **双持久记忆**：Ideation Memory（记录可行/不可行方向）+ Experimentation Memory（记录有效策略和代码模式），实现跨周期学习
- **Elo Tournament 排名**：idea 不是线性评估，而是通过竞争排名筛选最佳
- **三 Agent 分工**：RA 负责想法、EA 负责实验、EMA 负责元认知/记忆进化 → 清晰的关注点分离
- **三种记忆进化机制**：IDE（想法方向蒸馏）、IVE（想法验证蒸馏）、ESE（实验策略蒸馏）
- **Skill Pack 生态**：`EvoSkills` 仓库提供可安装的 skill packs，覆盖 research-ideation、idea-tournament、paper-writing 等

**Harness 工程视角：**
- **进化记忆是核心 harness 创新**：不是一次性流水线，而是随时间积累的"研究经验库"
- Agent 间的交互协议是关键约束——RA 输出 idea、EA 输出实验结果、EMA 输出记忆更新
- 与 Butler 的 memory_pipeline 概念高度类似：都是通过持久化记忆实现跨会话学习
- Elo Tournament 是一种 interesting 的质量把关机制（vs 简单的 LLM 评分）

---

### 4. SamuelSchmidgall/AgentLaboratory

**Stars:** ~5,400 | **许可:** MIT | **语言:** Python | **论文:** EMNLP 2025 Findings

**做什么：** 端到端研究工作流助手。接受人类提供的研究想法，输出研究报告和代码仓库。三阶段流程：文献综述 → 实验 → 报告撰写。强调人机协作（co-pilot 模式），声称比之前的自动研究方法降低 84% 成本。

**核心架构：三阶段流水线 + 人机协作 (3-Phase Pipeline + Human-in-Loop)**

```
Human Research Idea
  → Phase 1: Literature Review (arXiv agents)
  → Phase 2: Experimentation (mle-solver: REPLACE/EDIT 指令循环)
  → Phase 3: Report Writing (paper-solver: LaTeX 生成)
  → [Optional] Human Feedback at each phase
```

**关键设计决策：**
- **mle-solver**：独立的 ML 代码求解器，通过 REPLACE（全量重写）和 EDIT（行级修改）两种命令迭代改进代码，维护 top programs 排行，失败最多重试 3 次
- **co-pilot 模式**：不是纯自动，人类可以在每个阶段介入反馈 → 评估显示人机协作显著提升质量（overall score 3.8→4.38/10）
- **AgentRxiv**：Agent 间可以共享和基于彼此的研究成果，类似 arXiv 的 agent 知识共享平台
- **灵活后端**：支持 gpt-4o / o1-mini / o1-preview 等多种模型后端
- **成本高效**：gpt-4o 后端全流程 $2.33 / 1165 秒

**Harness 工程视角：**
- **最低 harness 约束之一**：只需一个自然语言 research idea，不需要模板/代码/配置
- mle-solver 的 REPLACE/EDIT 命令是 interesting 的代码修改抽象——比 Aider 更简单，比直接 LLM 生成更受控
- top programs 排行 + 3 次重试 = 简洁的质量保障机制
- AgentRxiv 是独特的 agent-to-agent 知识传播机制

---

### 5. ResearAI/DeepScientist

**Stars:** ~540 | **许可:** 分阶段开源 | **语言:** Python | **论文:** arXiv:2509.26603

**做什么：** 长周期自主研究系统，目标是持续推进科学前沿。将科学发现建模为贝叶斯优化问题，通过"假设→验证→分析"的层级评估循环运行数周，消耗 20,000+ GPU 小时。在 AI 文本检测任务上两周内达成了人类三年的研究进展。

**核心架构：贝叶斯优化 + 累积发现记忆 (Bayesian Opt + Cumulative Findings Memory)**

```
Goal-Oriented Loop (运行数周):
  → Hypothesize (基于 Findings Memory + 探索/利用平衡)
  → Verify (实验执行 + 验证)
  → Analyze (结果分析 + 更新 Findings Memory)
  → 累积 Findings Memory 引导下一轮
```

**关键设计决策：**
- **贝叶斯优化框架**：将科研建模为 explore/exploit 优化问题，不是简单的流水线
- **Findings Memory**：累积式发现记忆，智能平衡探索新假设与深挖有前景的方向
- **长时间尺度**：设计用于连续运行数周（vs 大多数系统的小时级别），消耗大量 GPU
- **前沿推进导向**：目标不是"写论文"而是"超越 SOTA"——设计上的根本差异
- **分阶段开源**：从受邀访问到逐步开放，目前 Phase 2 完成

**Harness 工程视角：**
- **最长时间尺度的 harness 设计**：需要处理数周运行中的状态管理、故障恢复、资源管理
- 贝叶斯优化的 explore/exploit 平衡是一种 mathematically grounded 的搜索策略（vs 启发式树搜索）
- Findings Memory 的累积特性意味着系统有"研究历程"的概念
- 高 GPU 消耗意味着 harness 需要强资源治理能力

---

### 6. Just-Curieous/Curie

**Stars:** ~340 | **许可:** 未指定 | **语言:** Python | **论文:** 2025-02

**做什么：** 专注于科学实验严谨性的 AI Agent 框架。通过"实验严谨性引擎"确保实验可复现、计划与目标对齐、任务切换正确。支持 ML 工程、系统分析和通用科学发现场景。

**核心架构：实验严谨性引擎 (Experimental Rigor Engine)**

```
Hypothesis → Experiment Plan
  → Intra-Agent Rigor Module (单 Agent 内可靠性策略)
  → Inter-Agent Rigor Module (Agent 间协调控制)
  → Experiment Knowledge Module (结构化文档)
  → Execution → Analysis → Reporting
```

**关键设计决策：**
- **三层严谨性保障**：Intra-Agent（个体可靠性）→ Inter-Agent（协调正确性）→ Knowledge Module（可解释性）
- **可扩展严谨性策略**：rigor policies 可配置，不是硬编码的验证规则
- **复现导向**：强调实验可复现性（vs 大多数系统关注"能跑通"即可）
- **通用性**：不限于 ML，支持生物信息学、股票预测等多领域

**Harness 工程视角：**
- **唯一将"严谨性"作为一等公民的项目**：大多数系统关注"能做什么"，Curie 关注"做得对不对"
- Rigor Module 本质上是对 Agent 行为的 constraint layer——与 Butler 的 heartbeat governance 理念类似
- 三层严谨性架构可视为一种 **验证 harness**（vs 执行 harness）

---

### 7. TIGER-AI-Lab/OpenResearcher

**Stars:** ~430 | **许可:** Apache-2.0 | **语言:** Python

**做什么：** 开源深度研究轨迹合成管线。训练了一个 30B-A3B 的 agentic 语言模型，在 BrowseComp-Plus 上超越 GPT-4.1、Claude-Opus-4 等。发布了 96K 高质量深度研究轨迹数据集（100+ turn 交互），内建 ~11B token 检索语料库。

**核心架构：长程轨迹合成 + 蒸馏训练**

```
大量深度研究交互轨迹 → 96K 轨迹数据集
  → 训练 30B-A3B 模型
  → 11B token 语料库内检索（无需外部 Search API）
  → 长程多轮深度研究
```

**Harness 工程视角：**
- 与其他项目不同，这不是"运行时 harness"而是"训练数据 harness"——通过高质量轨迹蒸馏能力
- 消除外部 Search API 依赖是重要的工程决策（降低延迟/成本/依赖）
- 更偏"深度信息研究"而非"科学实验"

---

### 8. lamm-mit/Sparks

**Stars:** ~18 | **许可:** 未指定 | **语言:** Python

**做什么：** MIT 出品的多模态多 Agent 科研系统。能独立制定假设、执行实验、适应策略。应用于蛋白质科学，发现了关于多肽力学的未知现象。

**核心架构：多模态多 Agent 闭环**

**Harness 工程视角：**
- Stars 少但学术价值高——唯一真正涉及实验科学（非纯 ML/代码）的项目
- 多模态特性（处理实验数据/图像/结构）是独特的工程挑战

---

## 三、架构模式对比矩阵

| 维度 | Karpathy autoresearch | AutoResearchClaw | AI Scientist v1 | AI Scientist v2 | EvoScientist | Agent Lab | DeepScientist | Curie |
|------|----------------------|------------------|-----------------|-----------------|-------------|-----------|--------------|-------|
| **约束程度** | 极低(最小约束) | 高(全流水线) | 高(模板约束) | 中(YAML+idea) | 中(记忆约束) | 低(自然语言idea) | 中(目标约束) | 高(严谨性约束) |
| **架构模式** | 单循环/极简 | 全流水线 | 线性流水线 | 树搜索 | 多Agent+进化 | 三阶段流水线 | 贝叶斯优化循环 | 严谨性引擎 |
| **Agent 数量** | 1 | 多(流水线) | 1(+工具) | 1 Manager + 工具 | 3(RA+EA+EMA) | 多(专用Agent) | 1(+记忆) | 多(+Rigor层) |
| **记忆/学习** | 无 | 无/有限 | 无 | 无 | 双持久记忆 | AgentRxiv | 累积Findings | Knowledge Module |
| **代码修改方式** | LLM直接 | 工具辅助 | Aider | LLM内置 | 树搜索 | REPLACE/EDIT | 自主生成 | Agent控制 |
| **人机交互** | 无 | 有限 | 无 | 无 | CLI+多渠道 | co-pilot模式 | 无 | 无 |
| **时间尺度** | 小时 | 小时 | 小时 | 小时 | 小时-天 | 小时 | 天-周 | 小时 |
| **输出物** | 代码+结果 | 报告 | 完整论文 | 完整论文 | 完整论文 | 报告+代码 | SOTA突破 | 实验报告 |

---

## 四、从 Harness 工程视角的关键洞察

### 1. 三种 Harness 哲学

- **最小约束 (Karpathy autoresearch 流派)**：给 LLM 最大自由度，只定义 goal 和 output format。简单、灵活，但输出方差大。Agent Laboratory 也偏这个方向。

- **全流水线约束 (AutoResearchClaw / AI Scientist v1 流派)**：每个阶段的输入/输出严格定义，人工模板约束边界。可靠性高，但灵活性低，扩展需要人工劳动。

- **进化/自适应约束 (EvoScientist / DeepScientist 流派)**：通过记忆和反馈循环动态调整约束。初期灵活，随时间积累变得更精准。这是 2026 年的新兴趋势。

### 2. 代码修改策略的演进

```
Aider (v1, 2024) → LLM 内置 (v2, 2025) → REPLACE/EDIT 命令 (Agent Lab, 2025) → 树搜索 (EvoScientist, 2026)
```

趋势：从外部工具辅助 → 内置到 Agent 循环中 → 结构化命令抽象 → 搜索空间中的路径选择。

### 3. 记忆是关键分水岭

- 无记忆系统（v1, v2, autoresearch）：每次运行从零开始
- 有记忆系统（EvoScientist, DeepScientist）：跨运行积累经验
- 这直接影响 **效率随时间的改进曲线**

### 4. 质量保障机制对比

| 机制 | 代表项目 |
|------|----------|
| 自动 Peer Review | AI Scientist v1/v2 |
| Elo Tournament 排名 | EvoScientist |
| VLM 图表审查 | AI Scientist v2 |
| 三层严谨性引擎 | Curie |
| top programs 排行 | Agent Laboratory |
| 贝叶斯 explore/exploit | DeepScientist |

### 5. 与 Butler 架构的共鸣点

- **EvoScientist 的进化记忆** ↔ Butler 的 `memory_pipeline` + `cognition` 层级记忆
- **Curie 的 Rigor Module** ↔ Butler 的 `heartbeat_governance`（约束 Agent 行为的治理层）
- **Agent Laboratory 的 co-pilot 模式** ↔ Butler 的人机交互设计理念
- **DeepScientist 的长时间尺度** ↔ Butler 的持久化 context 管理挑战

---

## 五、数据来源

- GitHub 仓库页面（2026-03-18 访问）
- arXiv 论文: 2408.06292 (AI Scientist v1), 2603.08127 (EvoScientist), 2509.26603 (DeepScientist), 2501.04227 (Agent Laboratory)
- Sakana AI 官方博客: sakana.ai/ai-scientist/
- alphanome.ai 对比分析文章
- HuggingFace 论文页
