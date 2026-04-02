# 上下文工程与记忆架构 — 从六大厂实践到 Butler 落地路径

> **综合类型**：跨主题深度综合（Cross-cutting Synthesis）
> **母本 Insight**：
> - `20260317_xiaohongshu_context_management_six_vendors_Insight.md`（六大厂上下文管理对比）
> - `20260318_Butler_Prompt架构与上下文压缩交接范式_insight.md`（Butler prompt 结构 + handoff 范式）
> - `20260318_OpenAI_Codex_Harness工程范式_Agent_Runtime_insight.md`（Context compaction 段落）
> - `20260318_claude_code_agent_工程化拆解_insight.md`（上下文控制作为五大工程问题之一）
> - `20260318_Anthropic前沿研究_Butler自省对齐设计启发_insight.md`（Memory Tool + 自省通道）
> **母本 Working**：`20260317_codex_prompt_and_vendor_compression_instructions.md`
> **外部补充**：2026 年 context engineering 前沿综述（LangChain / Meta-Intelligence / LogRocket 等）
> **提炼时间**：2026-03-18
> **主题轴**：上下文工程、记忆架构、prompt caching、压缩策略、跨 agent 交接、KV-Cache 优化

---

## 一、主题概述

"上下文工程"（Context Engineering）正在取代"提示工程"成为 Agent 系统的核心设计活动。它不是"怎么写 prompt"，而是**"在每一步，如何让模型看到恰好正确的信息"**。

对于 Butler 这样的长期运行、多角色、多轮交互的 Agent 系统，上下文工程的质量直接决定了三件事：
1. **执行准确度**：模型在当前步能否做出正确判断，取决于它看到了什么
2. **成本与延迟**：无效 token 是纯开销，prompt caching 命中率直接影响成本与响应速度
3. **跨轮连续性**：长对话和 heartbeat 多轮执行中，关键信息如何在压缩后幸存

本文综合 6 家厂商实践、Butler 自身 prompt 架构分析、以及 2026 年前沿研究，提炼出一套可操作的上下文工程框架。

---

## 二、核心观点提炼

### 1. 上下文工程的四操作原语：Write–Pull–Compress–Isolate

**来源**：LangChain 分类法 × 六大厂实践对比 × Butler prompt 解剖

LangChain 提出的四操作原语已成为行业共识框架：

| 原语 | 含义 | 代表厂商实现 | Butler 当前覆盖 |
|------|------|-------------|----------------|
| **Write** | 信息写入长期存储 | OpenAI 结构化状态对象 (profile + notes)、Claude Memory Tool (create/insert) | ✅ STATE / MEMORY / task_ledger / 工作区文件 |
| **Pull** | 按需从存储拉回上下文 | Cursor 动态上下文发现、Anthropic 循环内检索 | ✅ local_memory 命中 / self_mind 摘录 / 文件引用 |
| **Compress** | 摘要/截断/降精度 | Manus 完整版+紧凑版双存储、OpenAI 截断/压缩/状态化三模式 | ⚠️ 有 max_chars 截断，缺语义级压缩 |
| **Isolate** | 在独立上下文中执行子任务 | Cursor Subagents、Manus 子上下文隔离 | ✅ heartbeat executor / sub-agent 独立 prompt |

**关键发现**：Butler 在四个原语中的三个（Write / Pull / Isolate）已有可用机制，**Compress 是最大短板**——当前的"压缩"本质上只是 `max_chars` 截断，不具备语义理解，无法区分"可丢弃的冗余"和"必须保留的核心信息"。

---

### 2. "Context Rot" 比 "Context Overflow" 更危险

**来源**：六大厂共识 × 2026 前沿综述

行业对上下文问题的认知已从"窗口不够大"迁移到"窗口里的信息在腐烂"：

- **Context Rot**（上下文腐化）：长对话中早期信息逐渐失去影响力，模型对中段信息的注意力显著下降（"Lost in the Middle"现象），过时的工具输出仍留在上下文中误导后续推理
- **Context Poisoning**（上下文投毒）：错误信息一旦进入上下文，会被模型当作事实反复强化
- **Context Distraction**（上下文干扰）：过量的正确但无关信息稀释了关键信息的注意力份额

**产业数据**：系统性的上下文管理可防止约 30% 的信息丢失，实施有效管理的系统报告成本降低 60-80%（Meta-Intelligence 2026 综述）。

**→ Butler 映射**：Butler 的 heartbeat 多轮执行是 Context Rot 的高发场景——executor 的回执、planner 的分析、历史 branch 的摘要逐轮累积，到第 5-6 轮时早期信息几乎被淹没。当前没有主动的"上下文卫生"机制来清理过时或冗余信息。

---

### 3. 多层记忆架构是长期 Agent 的必要基础设施

**来源**：Anthropic Memory Tool × OpenAI 会话记忆 × 六大厂对比 × 前沿综述

成熟的 Agent 记忆系统至少需要三层：

| 层级 | 特征 | 典型内容 | 生命周期 |
|------|------|---------|---------|
| **工作记忆**（Working Memory） | 当前任务的即时上下文 | 当前对话、当前 branch 目标、工具调用结果 | 单轮/单 branch |
| **情景记忆**（Episodic Memory） | 过去交互的结构化回忆 | 历史任务的回执摘要、用户偏好变更记录 | 跨轮/跨天 |
| **语义记忆**（Semantic Memory） | 沉淀的知识和规则 | 用户画像、SOUL 设定、skill 能力描述 | 长期稳定 |

Anthropic 的 Claude Memory Tool 将这一思路产品化——提供 view/create/str_replace/insert/delete 等操作，让 Agent 主动管理自己的长期记忆，实测 token 消耗降低约 84%。

**→ Butler 映射**：

| 记忆层级 | Butler 当前实现 | 成熟度 | 差距 |
|---------|---------------|--------|------|
| 工作记忆 | 对话上下文 + branch prompt + 工具返回 | ★★★ | 缺显式的"工作记忆边界"声明 |
| 情景记忆 | recent（摘录）+ task_ledger + local_memory | ★★☆ | recent 摘录质量依赖截断而非语义；task_ledger 缺检索接口 |
| 语义记忆 | SOUL + 用户画像 + MEMORY.md + STATE.md | ★★★ | 基本够用，但缺少自动从情景记忆中提炼到语义记忆的升级通道 |

---

### 4. Prompt 前缀稳定性决定 Cache 命中率，是成本控制的第一杠杆

**来源**：Butler prompt 解剖 × OpenAI Prompt Caching × Manus KV-Cache 策略

跨厂商的四条共识：

1. **静态在前、动态在后**：系统指令/角色/规则放 prompt 开头，每轮变动的用户输入放末尾
2. **追加优于重排**：历史日志只追加不插入/重排，避免破坏已缓存前缀
3. **Mask 优于移除**：不用的工具/能力用 mask 标记为不可用，而非从列表中删除
4. **大观察落盘**：工具调用的大体量返回值写入文件系统，prompt 中只保留轻量引用

Butler 当前状态：
- ✅ 规则 1（Bootstrap 在前、用户消息在末尾）
- ✅ 规则 4（大文件写工作区）
- ⚠️ 规则 2（无显式的"只追加"约定）
- ❌ 规则 3（可选块按条件 include/exclude，非 mask 模式）

**量化参考**：OpenAI Prompt Caching 在前缀稳定时可降低约 90% 输入 token 成本和约 80% 延迟；Manus 把 KV-Cache 视为"神圣资源"，prompt 前缀格式连空白和 key 顺序都要保持确定性。

---

### 5. "检查点压缩 + 交接摘要"是跨 Agent 交接的标准范式

**来源**：用户截图中的 CONTEXT CHECKPOINT COMPACTION 指令 × Butler prompt 解剖

一个完整的跨 agent/跨轮交接摘要应包含四要素：

```
1. 当前进度与关键决策（Progress + Decisions）
2. 重要约束与用户偏好（Constraints + Preferences）
3. 待完成事项与下一步（Remaining + Next Steps）
4. 关键数据与参考资料（Critical Data + References）
```

以及一个强制性 QA 步骤：生成摘要前必须逐字引用压缩指令本身，防止指令在传递链中被篡改或遗漏。

**→ Butler 映射**：heartbeat 的 executor 回执已包含部分信息（做了什么、下一步），但缺少"关键决策"和"约束/偏好"的显式记录，也完全没有 QA 步骤来验证交接信息的完整性。当 heartbeat 从 branch A 的输出传递到 branch B 时，信息损耗是系统性的。

---

### 6. "注意力预算"概念将上下文管理从直觉驱动转向资源管理

**来源**：Anthropic "注意力预算" × Cursor A/B 测试数据 × 前沿综述

Anthropic 提出的"注意力预算"框架改变了设计范式——从"尽量多给信息"转向"精确分配有限的注意力资源"：

- **System Prompt 有"金发女孩区"**：过度工程化（塞太多规则）和过度模糊（只给一句话）都不好，存在一个最优信息密度区间
- **Cursor 的 A/B 测试验证**：减少预先塞入的细节、改为让 Agent 按需拉取，在多个指标上优于"全量预加载"
- **可量化标志**：Cursor 的 MCP 工具懒加载实现了约 46.9% 的 token 降幅

**→ Butler 映射**：Butler 的 prompt 组装当前按 mode 控制注入量（companion 时 SOUL 更长、maintenance 时 local_memory 更详细），但缺少显式的"预算"概念——planner 在规划长任务时不会考虑"每步可用的上下文预算是多少"，也不会主动在任务回执中记录 token 开销。

---

## 三、与 Butler 的映射关系总览

| 上下文工程维度 | 行业最佳实践 | Butler 当前状态 | 差距评级 | 改进方向 |
|---|---|---|---|---|
| 四操作原语覆盖 | Write/Pull/Compress/Isolate 全覆盖 | Compress 缺失 | 🔴 高 | 引入语义压缩 + 双模存储 |
| Context Rot 治理 | 主动清理过时信息 | 无上下文卫生机制 | 🔴 高 | 在 heartbeat 多轮执行中增加上下文刷新策略 |
| 多层记忆架构 | Working / Episodic / Semantic 三层 | 有但层间缺升级通道 | 🟡 中 | 建立"情景→语义"自动提炼机制 |
| Prompt Cache 友好性 | 四条共识全满足 | 满足 2/4 | 🟡 中 | 工具列表 mask 化 + 追加约定 |
| 交接摘要标准化 | 四要素 + QA 步骤 | 自由文本回执 | 🔴 高 | 设计 handoff_summary 模板 |
| 注意力预算 | 显式分配 + A/B 验证 | 按 mode 粗粒度控制 | 🟡 中 | 增加 token 预算意识和开销记录 |

---

## 四、可执行启示（按优先级排序）

### P0：handoff_summary 模板 v0

**做什么**：为 heartbeat executor 的回执定义一个标准化结构——

```json
{
  "progress": "本轮完成了什么 + 关键决策",
  "constraints": "需要传递给下游的约束/偏好",
  "remaining": "待完成事项 + 明确的下一步",
  "references": ["关键文件路径", "工具调用结果摘要"],
  "qa_check": "是否完整回答了以上四个字段"
}
```

**为什么优先**：当前 heartbeat branch 之间信息传递的损耗是影响多步任务成功率的第一瓶颈。

**落地路径**：先在 heartbeat governance 的 branch 协议中以 Markdown 模板形式引入，executor 按模板填写回执；不需要改代码，只需改 prompt 协议。

### P1：语义压缩层——完整版存盘 + 紧凑版入 prompt

**做什么**：参考 Manus 的双存储模式，对 heartbeat 回执和 self_mind 快照实施"完整版写入工作区文件 + 紧凑版（关键结论 + 文件引用）注入 prompt"。

**为什么重要**：这是补齐 Compress 原语的最直接路径，预期可显著降低 heartbeat 多轮执行时的 token 消耗。

**落地路径**：
1. 在 executor 回执协议中增加 `compact_summary`（≤200 字）和 `full_report_path`（文件路径）两个字段
2. planner 汇总时只读 `compact_summary`，需要细节时再 Pull 完整文件

### P2：上下文卫生——heartbeat 多轮的信息刷新

**做什么**：在 heartbeat 执行超过 3 轮时，自动触发一次"上下文卫生检查"——标记哪些早期 branch 的结果已被后续 branch 覆盖/废弃，将其从 planner 的活跃上下文中移除。

**为什么重要**：防止 Context Rot 导致的长任务质量下降。

**落地路径**：在 planner 的汇总逻辑中增加一个轻量判断——"哪些历史 branch 的产出仍然活跃？哪些已被替代？"——只保留活跃产出的紧凑摘要。

### P3：token 预算记录

**做什么**：在 heartbeat 任务回执中增加 `estimated_tokens` 字段，记录本轮大致的上下文消耗。积累数据后可用于优化 prompt 组装策略。

**落地路径**：executor 在回执末尾追加一行估算，不需要精确计量，粗略分级即可（<4K / 4-8K / 8-16K / >16K）。

---

## 五、一句话带走

> 上下文工程的核心不是"给模型更多信息"，而是"在每一步给模型恰好正确的信息"。Butler 已有 Write/Pull/Isolate 三个原语的可用机制，**Compress 和跨 agent 交接标准化**是当前最高优先级的两个补齐方向。

---

## 主题标签

`#上下文工程` `#记忆架构` `#ContextEngineering` `#PromptCaching` `#压缩策略` `#HandoffSummary` `#KV-Cache` `#多层记忆` `#Butler架构演进` `#跨主题综合`
