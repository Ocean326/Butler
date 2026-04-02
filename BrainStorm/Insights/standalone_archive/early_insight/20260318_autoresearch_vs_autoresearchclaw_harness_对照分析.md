# Insight: autoresearch vs AutoResearchClaw —— Harness Engineering 落地的两极形态

> 来源：GitHub 一手调研  
> - [karpathy/autoresearch](https://github.com/karpathy/autoresearch)（40.5k stars，2026-03）  
> - [aiming-lab/AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw)（4.4k stars，v0.3.0，2026-03）  
> - Medium 深度分析：[Dreamwalker 源码拆解](https://medium.com/@aristojeff/autoresearch-why-karpathy-turned-program-md-into-a-research-operating-system-58ae2532374d)  
> 提炼时间：2026-03-18 · BrainStorm 对照分析

---

## 一句话结论

**同样是"让 AI 自主做科研"，两个项目代表了 Harness Engineering 的两极——极简约束式（autoresearch）vs 全管线编排式（AutoResearchClaw）。它们的设计差异精确映射了 harness 领域的核心张力：控制粒度 vs 自主空间。**

---

## 1. 两个项目分别是什么

### autoresearch（Karpathy）

给 AI agent 一个单 GPU 的真实 LLM 训练环境，让它每 5 分钟跑一轮实验、自动保留好结果/丢弃差结果、无限循环。核心只有 3 个文件：

| 文件 | 角色 | 谁编辑 |
|------|------|--------|
| `prepare.py` | 不可变执行层：数据、分词器、评估函数、时间预算 | 人类（锁定不动） |
| `train.py` | 搜索空间：模型架构、优化器、超参、训练循环 | **Agent** |
| `program.md` | 组织协议：分支策略、实验循环、日志格式、保留/丢弃规则 | 人类 |

**设计哲学**：不是让 agent 模仿人类研究员，而是把研究本身重新设计成 agent 能高效优化的形态。

### AutoResearchClaw（aiming-lab）

输入一个研究想法，全自动产出一篇会议级论文（含真实文献、沙箱实验、LaTeX、多轮 peer review）。23 个 stage、8 个 phase 的完整管线：

```
A: 问题定义(1-2) → B: 文献发现(3-6) → C: 知识综合(7-8) →
D: 实验设计(9-11) → E: 实验执行(12-13) → F: 分析决策(14-15) →
G: 论文写作(16-19) → H: 终稿(20-23)
```

多 Agent 子系统：CodeAgent（代码生成+自修复）、BenchmarkAgent（基准测试）、FigureAgent（图表生成）。MetaClaw 跨 run 学习使管线越跑越强。

**设计哲学**：用完备的管线编排覆盖整个科研流程，每个阶段都有明确的输入/输出契约和质量门控。

---

## 2. Harness Engineering 四层架构对照

用之前整理的 Harness 四层框架逐层对比：

| Harness 层 | autoresearch | AutoResearchClaw |
|-----------|-------------|-----------------|
| **知识供给** | 极简：agent 只需读 `train.py` + `prepare.py` 的代码上下文。知识就是代码本身 | 重型：OpenAlex + Semantic Scholar + arXiv 三源文献检索，结构化知识卡片提取，跨 run 知识库（6 类） |
| **执行编排** | `program.md` 一份 Markdown 定义完整实验循环。无框架、无配置文件、无状态机代码 | 23-stage pipeline + 3 个多 Agent 子系统 + PIVOT/REFINE 决策循环 + 最多 10 轮迭代修复 |
| **风险门控** | 隐式但极强：`prepare.py` 不可修改（信任边界）、5 分钟时间预算（资源上限）、NaN/loss>100 快速失败、单文件约束（爆炸半径极小） | 显式且多层：3 个 human-in-the-loop 门控（stage 5/9/20）、4 层引用验证、AI-slop 检测（50+ 短语黑名单）、Sentinel 看门狗 |
| **治理运营** | `results.tsv` + git commit 历史。人类事后用 `analysis.ipynb` 做综合解读 | MetaClaw 自动从失败中提取 lesson → 转化为 skill → 注入后续 run。知识库跨 6 个维度自动归档 |

### 关键洞察

**autoresearch 的 harness 看起来几乎不存在，但它的约束力极强**——通过三个精确的设计决策（单文件、单指标、固定时间）把 agent 的自由度压缩到恰好能产生价值的范围。它是**减法式 harness**。

**AutoResearchClaw 的 harness 是工程化的正面实现**——每个 stage 有明确的输入/输出契约、错误修复策略、质量评估标准。它是**加法式 harness**。

---

## 3. 六个核心设计维度对比

### 3.1 控制粒度

| 维度 | autoresearch | AutoResearchClaw |
|------|-------------|-----------------|
| Agent 可编辑范围 | 1 个文件（`train.py`） | 管线内按 stage 生成代码、文本、图表 |
| 评估指标 | 1 个数字（`val_bpb`） | 7 维评审打分 + NeurIPS checklist + 引用完整性 |
| 时间预算 | 严格 5 分钟/轮 | 可配置 `time_budget_sec`，默认 300s/experiment |
| 回滚策略 | git reset 到上次好结果 | stage-level rollback + PIVOT/REFINE 循环 |

**Karpathy 的核心洞察**：agent 在窄约束下表现远好于在宽约束下。把研究重新格式化为 agent 友好的优化问题，比给 agent 更多自由度更有效。

### 3.2 Markdown 作为控制平面

两个项目都大量使用 Markdown，但角色完全不同：

- **autoresearch**：`program.md` 就是编排层本身。没有 Python orchestrator，没有状态机代码。自然语言直接定义实验协议。Karpathy 称之为"super lightweight skill"。
- **AutoResearchClaw**：`RESEARCHCLAW_AGENTS.md` 是让外部 coding agent（Claude Code / Codex）理解如何启动管线的接口文档，管线本身是 Python 代码。

**这揭示了一个 harness 设计的分水岭**：`program.md` 模式假设 agent 足够强，自然语言协议就够了；pipeline 模式假设 agent 需要被代码级别地引导和约束。

### 3.3 记忆与自我进化

| 维度 | autoresearch | AutoResearchClaw |
|------|-------------|-----------------|
| 短期记忆 | `run.log` + grep 提取关键指标 | 每个 stage 的 artifact 自动版本化 |
| 长期记忆 | git 提交历史 + `results.tsv` | MetaClaw 知识库（lessons → skills，30 天时间衰减） |
| 自我进化 | 无（人类事后分析 → 手动改 `program.md`） | 有（失败自动转 skill，下轮注入所有 stage 的 LLM prompt） |
| 进化效果 | — | -24.8% retry rate, -40% refine cycles, +18.3% robustness |

**MetaClaw 是目前看到的最接近"经验飞轮"落地的实现**——不是人工整理案例库，而是管线自动从失败中提炼可复用技能。这直接对应了 Harness 四层中"治理运营层"从阶段一（全量记录）到阶段二（经验反哺）的跃迁。

### 3.4 人类角色定位

| | autoresearch | AutoResearchClaw |
|--|-------------|-----------------|
| 人类做什么 | 设计 `program.md`（实验协议）、事后解读结果、决定哪些发现值得推回上游 | 输入研究话题、可选审批 3 个门控（或 `--auto-approve` 跳过） |
| 人类不做什么 | 不改代码、不跑实验、不选超参 | 不做文献综述、不写代码、不写论文 |
| 分工模型 | Human-above-the-loop（人类在循环上方设计规则） | Human-at-the-gate（人类在关键节点审批） |

### 3.5 可迁移性与平台绑定

| | autoresearch | AutoResearchClaw |
|--|-------------|-----------------|
| 领域 | 仅 LLM 训练（单 GPU, nanochat） | 通用科研（任意主题） |
| 模型绑定 | 无（任何 coding agent 都行） | OpenAI 为主，支持 ACP 协议接任意 agent |
| 计算绑定 | 强（NVIDIA GPU，结果与硬件相关） | 弱（GPU/MPS/CPU 自动检测） |
| 结果可比性 | 跨硬件不可比（刻意设计，为当前平台找最优解） | 跨 run 可比（统一评估框架） |

### 3.6 工程复杂度与可维护性

| | autoresearch | AutoResearchClaw |
|--|-------------|-----------------|
| 核心代码量 | ~630 行（3 文件） | 大型 Python 包（23 stage + 3 子系统 + MetaClaw bridge） |
| 依赖 | PyTorch + 几个小包 | OpenAI API + Semantic Scholar + OpenAlex + arXiv + Docker + LaTeX |
| 配置 | 零配置 | YAML 配置文件（~80 个可配置项） |
| 上手时间 | 分钟级 | 小时级（需配置 API key、环境、模板等） |
| 测试 | 无显式测试 | 1,284 个测试用例 |

---

## 4. 两者互相印证的 Harness Engineering 模式

尽管设计哲学对立，两个项目在以下 harness 模式上**高度一致**：

### 模式 A：不可变信任边界

- autoresearch：`prepare.py` + `evaluate_bpb` 不可修改 = agent 无法篡改评估标准
- AutoResearchClaw：sandbox 的 `immutable harness` + 引用验证的 4 层检查 = 管线无法自欺

**共识**：harness 必须有 agent 无法绕过的不可变锚点。评估函数/验证标准不能交给被评估的 agent 自己修改。

### 模式 B：时间预算作为硬约束

- autoresearch：固定 5 分钟训练时间，超 10 分钟自动 kill
- AutoResearchClaw：`time_budget_sec: 300`，可配置但有上限

**共识**：时间预算不只是资源管理，更是把"质量-效率"权衡内化到 agent 的搜索目标中。

### 模式 C：失败即数据

- autoresearch：crash 记入 `results.tsv`，status="crash"，不是浪费而是信息
- AutoResearchClaw：MetaClaw 自动从失败中提取 lesson → 转化为后续 run 的 skill

**共识**：生产级 harness 不怕 agent 失败，怕的是失败不留痕。

### 模式 D：单一入口点

- autoresearch："have a look at program.md" → agent 自行 bootstrap
- AutoResearchClaw：`researchclaw run --topic "..." --auto-approve` → 一句话启动全管线

**共识**：harness 对外接口越简单，越容易被复用和组合。

### 模式 E：Git/版本控制作为原生基础设施

- autoresearch：每次实验一个 commit，好结果保留分支、坏结果 reset
- AutoResearchClaw：PIVOT/REFINE 时自动版本化 artifacts

**共识**：版本控制不是辅助工具，而是 harness 的状态管理层。

---

## 5. 对 Harness Engineering 趋势的判断

### 判断 1：两种范式会在不同场景各自成立

| 场景 | 适合的范式 | 原因 |
|------|----------|------|
| 有明确单一指标、搜索空间可定义 | autoresearch 式极简约束 | 约束越紧，agent 越高效 |
| 端到端流程、涉及多种能力和外部 API | AutoResearchClaw 式全管线 | 需要 stage-level 的契约和错误修复 |
| 早期探索、快速验证 | 极简 | 低成本试错 |
| 生产环境、需要可审计性 | 全管线 | 每个 stage 有日志和质检 |

### 判断 2："program.md 即编排"是一个值得关注的趋势

Karpathy 用 Markdown 替代了 orchestrator 代码。这不是偶然——当 agent 足够强时，自然语言协议比代码更灵活、更容易迭代、更跨平台。随着 frontier 模型持续变强，更多编排逻辑会从代码迁移到 Markdown 协议。

但这**不意味着 pipeline 会消失**。AutoResearchClaw 的 23 stage 管线在当前 agent 能力下是必要的——agent 还不够强到能从一段 Markdown 协议自行推导出完整的科研流程。

**趋势方向**：pipeline 的 stage 数量会随 agent 能力增强逐渐减少，更多细粒度编排被压缩进 agent 自身能力。最终形态可能是 "program.md + 几个关键门控"。

### 判断 3：MetaClaw 指向了 Harness 的自我进化

autoresearch 的 harness 是静态的（`program.md` 由人类手动迭代）。AutoResearchClaw 的 MetaClaw 让 harness 本身能从运行中学习。这是 Harness Engineering 的下一个前沿：**harness 不只是约束 agent，harness 本身也在进化**。

对应之前整理的经验飞轮三阶段：
- autoresearch = 阶段一（全量记录，人工分析）
- AutoResearchClaw without MetaClaw = 阶段一到二之间（有日志，有知识库，但反哺靠人）
- AutoResearchClaw with MetaClaw = 阶段二（自动经验反哺，+18.3% robustness 可证）
- 阶段三（飞轮显现）= 尚未被任何开源项目完整实现

---

## 6. 对 Butler 的启发

### 启发 1：Butler 的 heartbeat 更接近 autoresearch 的设计精神

Butler 的 heartbeat 循环 + task_ledger + skills pipeline 本质上就是一个"program.md 式"的自然语言编排系统。当前的改进方向不应该是把它变成 AutoResearchClaw 那样的 23-stage 管线，而是：
- 确保不可变信任边界清晰（哪些行为 Butler 绝不能自行修改）
- 让时间预算和资源上限成为显式约束
- 让失败日志自动进入可检索的经验资产

### 启发 2：MetaClaw 模式可以小规模引入

不需要做完整的 lesson → skill 转化管线，但可以：
- 心跳每轮记录"本轮尝试了什么、结果如何"的结构化条目
- 积累到一定量后，自动归纳"这类任务应该怎么做/不应该怎么做"
- 注入后续心跳的上下文（类似 MetaClaw 的 `build_overlay()`）

### 启发 3：两种范式的选择标准

Butler 在选择"极简约束 vs 全管线"时，可以用一个简单判据：
- **如果任务有单一明确指标 + 可定义搜索空间** → 走 autoresearch 式（给 agent 一个 program.md + 一个评估函数 + 让它循环）
- **如果任务是端到端流程 + 涉及多种外部资源** → 走 pipeline 式（拆 stage、定义契约、加门控）

---

## 关键数据点

| 指标 | autoresearch | AutoResearchClaw |
|------|-------------|-----------------|
| Stars | 40,500+ | 4,400+ |
| 核心代码 | ~630 行 / 3 文件 | 大型 Python 包 / 23 stages |
| 实验频率 | ~12 次/小时 | 1 完整 run = 数小时 |
| 实际效果 | val_bpb 0.9979→0.9697（126 实验） | 完整论文产出（含真实引用+实验） |
| 自学习 | 无 | MetaClaw +18.3% robustness |
| 上手门槛 | 分钟级（单 GPU + uv sync） | 小时级（API keys + 环境配置） |
| 人类角色 | 设计 program.md + 事后解读 | 输入话题 + 可选门控审批 |
| 测试覆盖 | 无 | 1,284 tests |
| 发布时间 | 2026-03 | 2026-03（v0.1→v0.3 三周内） |
