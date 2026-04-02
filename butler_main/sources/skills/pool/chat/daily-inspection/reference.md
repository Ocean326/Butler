# 每日巡检 - 详细参考

## 与 WORKFLOW.md 的对应

| WORKFLOW 环节 | 本 skill 对应 | 调用 Agent |
|---------------|----------------|------------|
| A. 每日启动（10 分钟） | 每日启动 | orchestrator → secretary → 按需分发 |
| B. 日间执行 | 不属本 skill，由用户/飞书按需触发 | literature / file-manager / research-ops / engineering-tracker / discussion |
| C. 每日收口（15 分钟） | 每日收口 | secretary → orchestrator → file-manager |
| D. 每周例行（30 分钟） | **每周巡检**，非本 skill | feishu-workstation-agent（治理产出到 `工作区/Butler/governance/`） |

## 每日启动检查清单

- [ ] orchestrator 已汇总：昨日日志、新任务、会议安排
- [ ] 当日任务板已生成并写入 `./工作区/Butler/manager/orchestrator/`
- [ ] secretary 已创建当日日志并生成待办看板
- [ ] 待办看板已写入 `./工作区/Butler/manager/secretary/`
- [ ] 已按任务类型分发给对应 Agent（如需）

## 每日收口检查清单

- [ ] secretary 已汇总：完成 / 未完成 / 阻塞
- [ ] 汇总结果已写入 `./工作区/Butler/manager/secretary/`
- [ ] orchestrator 已生成明日优先级
- [ ] 明日优先级已写入 `./工作区/Butler/manager/orchestrator/`
- [ ] file-manager 已执行当日归档
- [ ] 归档记录已写入 `./工作区/Butler/governance/workspace_hygiene/file_manager/`

## 每周巡检（非每日巡检）

每周例行由 **feishu-workstation-agent** 直接承担，不通过本 skill 的「每日」流程：

1. 职责冲突巡检
2. 高负载岗位扩编建议
3. 更新 `AGENTS_ARCHITECTURE.md` 与角色文档
4. 产出写入 `./工作区/Butler/governance/`

当用户说「每周巡检」「治理巡检」时，应走治理流程而非本 daily-inspection skill。

## 公司目录路径速查

| Agent | 产出子目录 |
|-------|------------|
| orchestrator_agent | `./工作区/Butler/manager/orchestrator/` |
| secretary_agent | `./工作区/Butler/manager/secretary/` |
| file_manager_agent | `./工作区/Butler/governance/workspace_hygiene/file_manager/` |
| literature_agent | `./MyWorkSpace/Research/<topic>/...` |
| research_ops_agent | `./MyWorkSpace/Research/<topic>/...` |
| engineering_tracker_agent | `./MyWorkSpace/TargetProjects/<project>/runtime/` |
| discussion_agent | `./工作区/Butler/manager/discussion/` 或显式项目目录 |
| 治理（飞书工作站） | `./工作区/Butler/governance/` |

以当前 chat / orchestrator 运行事实为准，避免继续依赖旧 `agents/docs` 文档。
