# 日常运行流程（管理员 + 秘书）

## 0. 记录原则（先执行）

1. 所有执行记录优先写入 `chat`。
2. 每个任务最少两条记录：开始、结束。
3. `LOCAL_CONTEXT` 仅在复杂任务时可选补充，不作为日常强制项。

## A. 每日启动（10 分钟）

1. `orchestrator_agent` 汇总输入（昨日日志、新任务、会议安排）。
2. `secretary_agent` 创建当日日志并生成待办看板。
3. 依据任务类型分发给专项 Agent。

## B. 日间执行（并行）

- 文献任务 -> `literature_agent`
- 文件归档 -> `file_manager_agent`
- 研究思路 -> `research_ops_agent`
- 工程事项 -> `engineering_tracker_agent`
- 技术讨论/检索 -> `discussion_agent`

## C. 每日收口（15 分钟）

1. `secretary_agent` 汇总"完成/未完成/阻塞"。
2. `orchestrator_agent` 生成明日优先级。
3. `file_manager_agent` 执行当日归档动作。

## D. 每周例行（30 分钟）

1. 飞书工作站进行职责冲突巡检。
2. 对高负载岗位做扩编建议。
3. 更新 `AGENTS_ARCHITECTURE.md` 与角色文档。
