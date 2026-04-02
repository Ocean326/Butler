# Agent 架构设计四原则 · Insight

- **来源 Raw**：`BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_agent_architecture_principles.md`
- **原始平台**：小红书（Simon · Agent 架构系列）
- **原始日期**：2026-03-17
- **Insight 整理日期**：2026-03-18

---

## 核心论点（5 条）

### 1. 单轮→多轮迭代是 Agent 架构的分水岭

一次性「感知-规划-执行-反馈」只够做 Demo。现实任务需要 Agent 自主决定"要不要继续迭代"，而不是靠硬编码规则来驱动下一轮。多轮迭代能力是衡量 Agent 架构成熟度的第一指标。

### 2. 架构弥补模型能力缺口

当前大模型尚不具备完全自律的多轮决策能力。Agent 的自主性不能仅仅依赖 prompt 和模型推理，必须用架构级的机制（循环控制、检查点、回退策略）把"继续 / 终止 / 换路"的决策结构化。

### 3. 工具原子性 + 业务适配器分层

工具保持原子、通用；业务逻辑不塞进工具内部，而是通过适配器层 / 外围配置注入。这样工具可跨场景复用，业务变更只影响适配层，不破坏执行引擎。

### 4. 给自由、再加护栏

设计原则上应「先给 Agent 足够的自主空间，再通过 Human-in-the-loop 做必要约束」。反过来先限制再放权，会把 Agent 退化成流水线脚本。

### 5. Multi-Agent 需自底向上三层设计

从基础层（消息、状态、工具管理）→ 协调层（任务调度、交互策略）→ 应用层（场景适配、业务流程），逐层搭建。跳过基础层直接在应用层拼多 Agent，会导致状态不一致和通信混乱。

---

## 与 Butler 当前架构的映射

| 原则 | Butler 现有对应 | 差距 / 演进方向 |
|---|---|---|
| 多轮迭代 | heartbeat 循环 + planner→executor 分支 | 循环内的"继续/终止/换路"判据主要靠 planner prompt，尚缺显式的迭代控制状态机 |
| 架构弥补模型 | heartbeat_orchestration + memory_pipeline | 已有框架雏形，但回退/重试策略分散在各 executor 内部，未统一抽象 |
| 工具原子性 | skills 体系（每个 skill 单一职责） | 基本符合；部分 skill 内部仍耦合了场景假设（如 OCR skill 绑定小红书图片格式），可进一步解耦 |
| 自由→护栏 | executor 有自主执行权 + 升级审批机制 | 方向正确；heartbeat_upgrade_request.json 机制已是 Human-in-the-loop 落地 |
| 三层 MAS 设计 | planner 充当协调层，executor 是基础执行层 | 基础层的消息/状态管理尚未显式分层；task_ledger 在尝试统一状态，但跨分支通信协议缺失 |

---

## 可执行建议（2 条）

1. **在 heartbeat 循环中引入显式迭代控制点**
   - 为每轮 executor 返回结果定义标准化的迭代决策字段：`{continue | terminate | escalate | retry}`，让 planner 基于结构化信号而非纯自然语言做下一步决策。
   - 这直接回应"架构弥补模型"的原则，把迭代控制从 prompt 层拉到协议层。

2. **梳理 skills 内的场景耦合，抽出适配器层**
   - 对现有 skills 做一轮审查，把 skill 内嵌的平台/格式假设（小红书 HTML 结构、知乎 API 字段等）抽为独立的 adapter 配置文件。
   - skill 只保留原子逻辑（OCR、抓取、发送），adapter 负责"输入从哪里来、输出格式怎么对齐"。

---

## 主题标签

`#Agent架构原则` `#多轮迭代` `#工具原子性` `#适配器分层` `#Human-in-the-loop` `#Multi-Agent三层设计` `#Butler架构演进`
