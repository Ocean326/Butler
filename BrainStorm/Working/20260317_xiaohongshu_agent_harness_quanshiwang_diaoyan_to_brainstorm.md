## 20260317 · 小红书 · Agent Harness 全网调研介绍【汇总版】· 结构化头脑风暴

- **来源**: 小红书「Agent Harness 全网调研介绍【汇总版】 今年 AI 领域...」（xhslink）
- **原文 Raw**: `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_agent_harness_quanshiwang_diaoyan.md`
- **抓取与读图**: 2026-03-17，web-note-capture-cn + 直接读图补充（PaddleOCR 未装）
- **同系材料**: 多 Agent Harness Engineering（下）、六大厂上下文管理、10 个 Agent 项目、架构设计原则

---

## 1. 一句话印象

> **2026 重心从「做 Agent」转向「做 Agent Harness」：观察优于堆量、行动空间最难、Harness 解决 context durability 与 model drift；但若靠人工写死结构扩展，会与苦涩教训冲突。Butler 的 heartbeat/规划/记忆真源即一种 harness，需在「控制与可预测」与「少写死结构」之间找平衡。**

---

## 2. 原文关键信号拆解

### 2.1 构建有效 Harness 的经验（图 1）

- **Rohit**：Harness 不是 volume，是 **observation**——see like an agent：Watch logs, Catch loops, Tweak tools.
- **Anthropic**：最难的是 **constructing action space**（行动空间构建）。
- 对 Butler：heartbeat 日志、loop 可见性、skills 可调，即「观察」基础设施；action space ≈ 可调用的 skills + 任务类型边界。

### 2.2 2026 趋势：Prompt the harness（图 2）

- 不要用 SDK/库/框架自己组装 agent，而是 **prompt the harness** 拿最佳结果。
- **Philipp Schmid**：2025 是 agents 开端，**2026 围绕 Agent Harnesses**。
- **原因**：验证真实世界进展（在用例与约束下测最新模型）、增强用户体验（无 harness 则体验落后于模型潜力）。
- 对 Butler：飞书入口即「prompt the harness」；Butler 本体 = 稳定 harness，用户/任务 = prompt 与约束。

### 2.3 反馈循环与训练/推理融合（图 3）

- **真实世界反馈**：共享稳定环境（Harness）形成反馈循环，基于实际采用迭代。
- **Schmid**：训练与推理环境融合；新瓶颈是 **context durability**；**Harness 成为解决 model drift 的主要工具**。
- **「苦涩教训」辩论**：Harness 是否符合「通用计算胜手工知识」有争议。
- 对 Butler：recent/分场景装载/记忆真源 = context durability 的一层；model drift 对应「长期偏好 vs 当前事实」的更新策略。

### 2.4 核心张力与应用案例（图 4）

- **核心张力**：若 harness 主要通过**添加更多人工编写结构**扩展，可能在与苦涩教训作斗争。
- **应用案例**：客户支持（对话、外部数据、程序化操作、按解决率定价）、编程智能体。
- 对 Butler：技能/规则优先改 skills 与配置、少改核心代码，即减少「人工写死结构」；Harness 层做控制和引导，而非堆 if-else。

### 2.5 SWE-bench 与 Harness Engineering（图 5）

- **Anthropic SWE-bench**：真实 GitHub 问题、多文件编辑、测试结果作反馈、自动化测试+人工审查。
- **Martin Fowler Harness Engineering**：**控制与引导 AI 系统**、**安全性与可预测性**。
- 对 Butler：与 `docs/concepts/` 中 Harness、MAS 设计一致；Butler 的「身体/脑子/家/公司」分层即控制与可预测性的一层实现。

---

## 3. 与同系材料的对照

| 维度           | 本篇（Harness 全网调研）     | 多 Agent Harness（下） | 六大厂上下文     | 10 个 Agent / 架构原则 |
|----------------|-----------------------------|------------------------|------------------|------------------------|
| 焦点           | Harness 经验与 2026 趋势    | 四层 Harness + 经验飞轮 | 何时看到什么+如何组织 | LLM+Tools+Loop+Memory |
| 关键矛盾       | 观察 vs 堆量；人工结构 vs 苦涩教训 | 单 Agent vs MA、门控层 | 压缩/缓存/窗口   | 工具生态、任务规划     |
| 对 Butler 启示 | 稳定 harness + 少写死结构   | MAS 门控、经验飞轮     | recent/分场景    | 技能真源、规划与协作   |

---

## 4. 对 Butler 的启发

- **Harness 定位**：Butler 即用户侧的 Agent Harness——飞书/对话为 prompt 入口，heartbeat+task_ledger+skills 为稳定行动空间与反馈环。
- **观察优先**：日志、loop、工具可调（Rohit 三点）对应 heartbeat 日志、任务状态、skills 可插拔；保持可观测比堆功能重要。
- **Context durability 与 model drift**：记忆真源、recent 窗口、分场景装载已在做；需显式考虑「长期偏好 vs 当前事实」的更新与 handoff，避免漂移。
- **少写死结构**：新能力优先进 skills/配置/文档，核心代码与 SOUL 收敛、不堆临时分支，与「核心张力」一致。
- **安全与可预测**：Martin Fowler 的 Harness Engineering 与 Butler 的分层、任务协议、高风险变更过检一致；可把本篇与 `Butler_机制+系统思维导图`、MAS 文档放在一起做「Harness 语汇」统一审阅。
