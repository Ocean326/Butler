# Agent Harness 全网调研汇总 · Insight

- **来源 Raw**：`BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_agent_harness_quanshiwang_diaoyan.md`
- **原始平台**：小红书（Simon 系列）
- **原始日期**：2026-03-17
- **Insight 整理日期**：2026-03-18
- **区别于**：同目录下已有的 `20260317_simon_agent_harness_insights.md`（侧重单篇 MAS Harness Engineering 长文）；本篇是**多源观点横向汇总**。

---

## 核心论点（5 条）

### 1. Harness 的核心是 Observation，不是堆 Agent

> Rohit: "Building an agent harness 不在于 volume，而在于 observation。要 see like an agent: Watch the logs, Catch the loops, Tweak the tools."

- 有效的 Harness 始于**高质量日志观测**，而不是在外围堆框架或堆 Agent 数量。
- 三个动作闭环：**看日志 → 捕死循环 → 调工具空间**，形成可迭代改进回路。

### 2. Action Space 构建是最难的部分

> Anthropic: "构建 agent harness 最难的部分之一是 constructing its action space."

- 工具空间不是越多越好；需要精心裁剪每个 Agent 在特定任务下可用的工具集，既保证能力覆盖，又避免爆炸式搜索。
- 与 Butler 现有的「工具白名单 + skill 注册」思路一致，但需要从"静态白名单"向"场景感知的动态 action space"演进。

### 3. 2026 年的行业押注：从 Agent 到 Agent Harness

> Philipp Schmid: "If 2025 was beginning of agents, 2026 will be around Agent Harnesses."

三个驱动力：
1. **验证真实世界进展**：Harness 提供统一基准，让用户在自己的用例和约束下测试和比较最新模型。
2. **增强用户体验**：没有 Harness 的 Agent 系统，用户体验很可能落后于模型本身的潜力。
3. **反馈飞轮**：共享、稳定的 Harness 环境形成反馈循环，研究人员和工程师可以基于实际用户采纳情况迭代改进。

### 4. Context Durability 是新瓶颈

> Schmid: "新瓶颈是 context durability；Harness 将成为解决 model drift 的主要工具。"

- Training 与 Inference 环境正在融合，但上下文的持久性（跨轮、跨 session）成为关键约束。
- Harness 不仅管工具和安全，还应承担**上下文保鲜与衰减对抗**的责任 — 这对 Butler 的 memory_manager 和 prompt_assembly 有直接指导意义。

### 5. 苦涩教训辩论：手工结构 vs 通用计算

- Agent Harness 通过**添加更多人工编写的结构**来扩展能力，但这可能与 Rich Sutton 的「苦涩教训」（Bitter Lesson）相矛盾 — 通用计算/方法最终总是胜过手工知识。
- 平衡点：Harness 中的结构应是**可被模型学习和替代的中间态**，而非永久固化的硬约束。Butler 在设计约束时需要留出"让模型自己发现更好方式"的空间。

---

## 与 Butler 当前架构的映射

| 全网调研观点 | Butler 现有对应 | 差距 / 演进方向 |
|---|---|---|
| Watch logs / Catch loops | heartbeat 日志 + task_ledger | 缺少自动化的"死循环检测 + 自动降级"机制 |
| Construct action space | skills 白名单 + 工具注册 | 目前静态注册，需向场景感知的动态 action space 演进 |
| Context durability | memory_manager + prompt_assembly | 需加强跨 session 的上下文持久与衰减管理 |
| 验证基准 (Harness as benchmark) | 尚无系统化基准 | 可在 BrainStorm/cases 或 tests/ 下建"场景回放基准" |
| 安全/预算做一等公民 | 工具白名单 + 简单限流 | 门控层需升级为中间件式统一策略层 |
| 经验飞轮 | task_ledger + BrainStorm Insights | 需要半自动的"执行→案例卡片→可检索经验库"流程 |

---

## 可执行建议（3 条）

1. **在 heartbeat executor 中加入"死循环检测"钩子**
   - 当同一 branch 连续 N 轮未产出增量结果时，自动触发降级/换路逻辑，而不是纯靠超时杀进程。
   - 这是 "Watch the logs, Catch the loops" 的最小可行落地。

2. **设计"动态 action space"机制**
   - 在 skill/Agent 调度前，根据任务类型和当前上下文，自动裁剪可用工具集。
   - 初步可以在 prompt_assembly 阶段根据 task_type 做 skill 过滤，不需要复杂框架。

3. **启动 Context Durability 专题治理**
   - 梳理 Butler 当前跨轮/跨 session 上下文丢失的高频场景。
   - 在 memory_manager 中建立"上下文保鲜度评分"，对即将衰减的关键上下文主动触发持久化。

---

## 主题标签

`#AgentHarness` `#Observation` `#ActionSpace` `#ContextDurability` `#BitterLesson` `#经验飞轮` `#Butler架构演进` `#2026趋势`
