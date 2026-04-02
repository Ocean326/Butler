# Butler Prompt 架构解剖 × 上下文压缩·交接范式 · Insight

> 母本：`BrainStorm/Working/20260317_codex_prompt_and_vendor_compression_instructions.md`
> 关联 Insight：`20260317_xiaohongshu_context_management_six_vendors_Insight.md`（六大厂方案对比）
> 区别于关联 Insight：前者从外部视角横向对比六家方案；**本篇从 Butler 内部出发**，拆解自身 prompt 结构，与各家策略做逐点对照，并提炼一个可复用的「上下文检查点压缩 + 跨 agent 交接」范式。
> 提炼时间：2026-03-18
> 主题轴：Prompt 架构、上下文工程、压缩策略、跨实例 Handoff、KV-Cache 友好设计

---

## 核心观点

### 1. Butler 的 Prompt 已具备「静态前缀 + 动态后缀」的 Cache 友好结构

母本对 `build_feishu_agent_prompt()` 的 15 个 block 做了完整逆向。Butler 的 prompt 组装逻辑自上而下：

| 位置 | 块 | 稳定性 |
|------|-----|--------|
| 1-4 | 身份角色 → 场景 → Bootstrap → 基础行为 | 高（跨轮不变） |
| 5 | 对话上下文（主意识摘录、SOUL 摘录、用户画像、长期记忆命中、self_mind） | 中（按需加载、有长度控制） |
| 6-14 | 协议、技能目录、回复要求等（按 mode 可选注入） | 中-高（同 mode 下稳定） |
| 15 | 用户消息 | 低（每轮变） |

这个结构天然符合 OpenAI Prompt Caching 的最佳实践——静态内容在前、变动内容在后，使得相同 mode 下的连续对话可以复用前缀缓存。

**但当前的隐含风险**：
- 第 5 块（对话上下文）在每轮都会变化，且位于中段，可能切断后续 block 的 cache 命中
- Bootstrap 文件的细微改动（如多加一个换行）会导致整条缓存失效
- 缺乏显式的「cache 边界标记」，难以诊断命中率

**→ 可执行改进**：在 prompt 组装时增加一个逻辑分界——将"几乎不变的前缀块"和"可能变化的动态块"之间加入稳定的分隔标记，便于未来对接 prompt caching 诊断工具。

---

### 2. 「上下文检查点压缩」是跨 agent/跨轮交接的通用范式

母本中识别出一段来自用户截图的指令，核心是 **CONTEXT CHECKPOINT COMPACTION**——让当前 LLM 生成一份结构化交接摘要（handoff summary），供下一个 LLM 实例无缝接续。

交接摘要的四要素：
1. **当前进度与关键决策**（progress + decisions）
2. **重要约束与用户偏好**（constraints + preferences）
3. **待完成事项与下一步**（remaining + next steps）
4. **关键数据与参考资料**（critical data + references）

以及一个强制性 QA 步骤：生成摘要前必须逐字引用原始压缩指令，防止指令在传递中被篡改或遗漏。

**Butler 的对照**：

| 检查点压缩要素 | Butler 当前等价机制 | 差距 |
|---|---|---|
| 进度 + 决策 | heartbeat 回执中的"做了什么" | 缺少"关键决策"的显式记录 |
| 约束 + 偏好 | user_preferences + SOUL 摘录 | 已较好，但交接时不一定带上 |
| 待完成 + 下一步 | task_ledger 的 next_steps | 格式不统一 |
| 关键数据 + 引用 | 工作区文件路径 | 散落在回执各处，未结构化 |
| 强制 QA | 无 | 完全缺失——无法验证交接信息完整性 |

**→ 可执行改进**：设计一个标准化的 `handoff_summary` 结构（JSON 或 Markdown 模板），在 heartbeat branch 结束时由 executor 填写，planner 汇总时做完整性校验。这比当前的自由文本回执更可靠。

---

### 3. 各家压缩策略可归纳为四种操作原语，Butler 已覆盖三种

母本横向梳理了 OpenAI、Cursor、Anthropic、Manus 四家的压缩策略后，提炼出与 LangChain 分类法对齐的四种操作原语：

| 原语 | 含义 | Butler 覆盖情况 |
|------|------|----------------|
| **Write** | 信息写入长期存储 | ✅ STATE / MEMORY / task_ledger / 工作区文件 |
| **Pull** | 按需从存储拉回上下文 | ✅ local_memory 命中 / self_mind 摘录 / 文件引用 |
| **Compress** | 摘要/截断/降精度 | ⚠️ 有摘录控长，但缺少显式的「压缩策略」声明 |
| **Isolate** | 在独立上下文中执行子任务 | ✅ heartbeat executor / sub-agent 独立 prompt |

**关键差距在 Compress**：
- Manus 有明确的「完整版 + 紧凑版」双存储——工具输出先存完整版，老旧结果自动压成紧凑版（如只保留路径引用）
- Butler 当前的"摘录"是隐式的（由 `max_chars` 截断），没有语义级的压缩
- 缺少「压缩策略」的配置化——什么时候压缩、压到什么程度、保留什么，全靠硬编码

**→ 可执行改进**：为 Butler 的 context 管线引入显式的压缩层——至少对 heartbeat 回执和 self_mind 快照增加"完整版存盘 + 紧凑版入 prompt"的双模式。

---

### 4. Cache 友好设计的四条共识可直接作为 Butler Prompt 工程规范

从母本整理中提炼的四条跨厂商共识：

1. **前缀稳定**：系统指令/规则/示例/角色描述放在 prompt 最前面，且格式（包括空白和 key 顺序）尽量不变
2. **追加优于重排**：历史日志只追加，不重新排序或插入，避免破坏已缓存的前缀
3. **Mask 优于移除**：不用的工具用 mask 标记为不可用，而不是从列表中删除，保持工具列表结构稳定
4. **大观察落盘**：工具调用的大体量返回值写入文件系统，prompt 中只保留轻量引用

Butler 在第 1 和第 4 条上做得较好（Bootstrap 在前、大文件写工作区），但在第 2 和第 3 条上还有空间——当前 prompt 中的可选块（skill 目录、协议等）是按条件 include/exclude 的，而非 mask。

---

## 与 Butler 架构的映射总览

| 维度 | 当前状态 | 改进方向 | 优先级 |
|------|---------|---------|--------|
| Prompt 前缀稳定性 | Bootstrap 在前，基本符合 | 增加 cache 边界标记 + 诊断 | 中 |
| 交接摘要（handoff） | 自由文本回执 | 标准化 handoff_summary 结构 | 高 |
| 压缩策略 | 隐式 max_chars 截断 | 引入语义压缩 + 双模存储 | 中-高 |
| 工具列表稳定性 | 按需 include/exclude | 改为 mask 模式 | 低 |
| 日志/历史追加策略 | 部分符合 | 明确"只追加"约定 | 低 |

---

## 可执行的下一步

1. **handoff_summary 模板 v0**：定义一个 4 字段的 JSON/Markdown 模板（progress, constraints, remaining, references），在 heartbeat branch executor 的回执格式中引入，先试跑 2-3 轮验证信息完整性
2. **压缩策略配置化**：在 prompt 组装管线中，为 self_mind / recent / heartbeat_context 增加一个 `compression_mode` 配置项（full / compact / reference_only），允许按场景切换
3. **Prompt cache 诊断**：如果 Butler 后端使用 OpenAI API，在日志中记录每次请求的 `cached_tokens` 字段，积累数据后分析命中率与前缀稳定性的关系

---

## 母本中的补充材料（备用）

- `BrainStorm/Working/openai_anthropic_recent_tech_posts_2026q1/openai/2026-02-13_beyond-rate-limits.md`：OpenAI 的 rate limit + credits metering 系统，属于 Agent 平台基础设施层，与上下文工程间接相关（计费正确性依赖 token 计量），可在设计 Butler 的 token 预算时参考
- `BrainStorm/Working/openai_anthropic_recent_tech_posts_2026q1/openai/2026-01-22_scaling-postgresql.md`：PostgreSQL 扩容策略，纯后端基础设施，与 Butler 当前架构关联度较低，仅作技术储备
