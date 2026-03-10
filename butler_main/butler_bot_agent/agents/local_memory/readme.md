# local_memory

长期记忆采用兼容式三层结构：

- `L0_index.json`：条目索引与类别元数据，作为 machine-readable 入口。
- `L1_summaries/`：摘要层，优先存放长期约定、经验、偏好、项目级摘要。
- `L2_details/`：详情层，存放较长原文或展开说明，L1 只保留摘要与引用。

兼容约定：

- 根目录现有 `*.md` 文件暂视为 legacy L1，不立即迁移，继续参与检索与摘要注入。
- `未分类_临时存放.md` 仍作为溢出与临时收纳入口。
- `heartbeat_tasks.md`、`heartbeat_long_tasks.json` 等仍属于任务兼容文件，不作为正式 semantic memory 分层条目。

维护原则：

- 新增长期记忆优先写入 `L1_summaries/`。
- 内容过长时，将全文写入 `L2_details/`，并在 L1 保留摘要与详情引用。
- 归档或整理时，优先更新 `L0_index.json`，保证索引与文件路径一致。

`json` 与 `md` 的边界：

- `json` 用于 machine-readable 状态：索引、关系、元数据、任务状态、路径映射、配置与会话状态。
- `md` 用于 human-readable 内容：长期事实、偏好、约束、项目摘要、经验总结、详细原文。
- `L0_index.json` 负责“这条记忆是什么、在哪、属于哪类”；不负责承载完整语义正文。
- `.relations.json` 负责“L1 摘要和 L2 详情怎么连”；不负责替代正文。
- `L1_summaries/*.md` 负责默认检索和默认上下文注入；这是 Butler 平时最常读的一层。
- `L2_details/*.md` 只在明确需要深挖时读取；不要让它默认参与 heartbeat 或聊天上下文拼装。