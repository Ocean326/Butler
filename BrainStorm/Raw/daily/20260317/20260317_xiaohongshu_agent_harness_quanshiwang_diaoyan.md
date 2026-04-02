# Agent Harness 全网调研介绍【汇总版】

- **platform**: xiaohongshu
- **id**: 69a69181000000002801e418
- **source_url**: http://xhslink.com/o/90K8ToVqkIG
- **capture_time**: 2026-03-17（web-note-capture-cn）
- **read_figures**: 2026-03-17（直接读图补充；PaddleOCR 未装）

---

## 简短结构化摘要（Simon · Agent Harness 全网调研）

- **主题**：汇总 2026 年围绕 Agent Harness 的代表性观点与实践案例，强调通过统一 Harness 环境把「日志观测、工具空间设计、真实世界反馈」收敛成可迭代的工程系统。
- **关键观点**：
  - 构建 Harness 的关键在于「观察日志、捕捉死循环、调参工具空间」，而不是拼接更多 Agent 或框架。
  - Agent Harness 将成为 2026 年验证真实世界进展、对齐训练与推理环境、对抗模型漂移与上下文衰减的核心抓手。
  - 高质量 Harness 需要把安全、预算、权限与评估做成一等公民，而不是散落在单点脚本或单个 Agent 中。
- **对 Butler / MAS 的启发**：
  - 将当前 `task_ledger`、工具白名单、限流与日志观测显式纳入「Harness 工程」视角，围绕少量关键场景打通从日志到策略调优的闭环。
  - 在多 Agent / AgentTeam 设计中，优先规划「统一 Harness 环境 + 多 Agent 协作协议」，而不是先堆角色再补观测与门控。

---

## Simon Agent 小红书系列 · 状态标注

- **图片 / OCR 状态**：配图已下载到 `BrainStorm/Raw/images/`，当前版本依赖人工读图提炼文字，细粒度 OCR 与版式级还原待后续补齐。
- **结构化要点状态**：本 Raw 已在顶部补充最小结构化摘要与对 Butler/MAS 的架构启发，可视为「已具备 Working 入口，后续若需要可再派生独立 BrainStorm 稿」。
- **评论区状态**：小红书原贴评论区暂未抓取，当前版本仅覆盖正文与配图要点。

## Content（首屏摘要）

正文首屏为空，主内容在 5 张配图中，主题为 **Agent Harness** 全网调研汇总：构建有效 Harness 的经验、2026 趋势、真实世界反馈与训练/推理融合、核心张力与应用案例。

## Images

- 图1～5 已下载至 `BrainStorm/Raw/images/`，对应 capture JSON 中的 5 条 URL；OCR 未跑（本机无 PaddleOCR），图中文字为直接读图提炼。

## 图中内容补充

### 图 1（构建有效 Harness 的经验 — @seejayhess）

- **Rohit (@rohit4verse)**：Building an agent harness 不在于 volume，而在于 **observation**。要 "see like an agent"：Watch the logs, Catch the loops, Tweak the tools.
- **Anthropic**：构建 agent harness 最难的部分之一是 **constructing its action space**（构建其行动空间）。
- **Or Hiltch (@_orcaman)**：提供了务实的建议（图中截断）。

### 图 2（2026 年趋势预测）

- **观点**：不要用 Agent SDK/library/framework 自己组装 agent，而是 **prompt the harness** 拿最佳结果。
- **Philipp Schmid 预测**：If 2025 was beginning of agents, **2026 will be around Agent Harnesses**.
- **三个关键原因**（图中列了两条）：
  1. **验证真实世界进展**：允许用户轻松测试和比较最新模型在自身用例与约束下的表现。
  2. **增强用户体验**：没有 harness，用户体验可能落后于模型潜力。

### 图 3（真实世界反馈 + 训练与推理融合）

- **通过真实世界反馈进行爬坡**：共享、稳定的环境（Harness）形成反馈循环，研究人员可基于实际用户采用情况迭代改进。
- **训练与推理的融合**：Schmid — 我们正走向 training 与 inference 环境的融合；新瓶颈是 **context durability**（上下文持久性）；**Harness 将成为解决 model drift（模型漂移）的主要工具**。
- **「苦涩教训」辩论**：Agent Harness 是否符合「苦涩教训」（通用计算/方法最终胜过手工知识）存在重大讨论；Noah Brier 有评论（图中未展开）。

### 图 4（核心张力 + 应用案例）

- **英文引言**：需要新词来描述「面向未来构建有价值工具」的现实。
- **核心张力**：若「agent harness」主要通过**添加更多人工编写的结构**来扩展，可能在与苦涩教训作斗争。
- **九、应用案例**：
  1. **客户支持智能体**：自然对话流程、访问外部数据（客户历史、知识库）、程序化操作（退款、工单更新）、基于成功解决率的定价。
  2. **编程智能体**（仅标题）。

### 图 5（SWE-bench 与 Harness Engineering）

- **Anthropic 的 SWE-bench 实现**：解决真实 GitHub 问题；按任务描述编辑多文件；用测试结果作迭代反馈；结合自动化测试与人工审查。
- **Martin Fowler 的 Harness Engineering**：专注**控制与引导 AI 系统**；强调**安全性与可预测性**。

## Notes

- 当前结果来自分享页 HTML 首屏；正文为空，标题由用户消息补全为「Agent Harness 全网调研介绍【汇总版】」。
- 与同系列：`20260317_xiaohongshu_multi_agent_harness_engineering.md`、六大厂上下文管理、10 个 Agent 项目共性、架构设计原则等可对照阅读。
