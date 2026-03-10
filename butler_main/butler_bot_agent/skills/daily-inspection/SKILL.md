---
name: daily-inspection
description: 每日启动与收口的例行巡检流程。当用户要求做「每日巡检」「今日启动」「今日收口」或确认当日待办/明日优先级时使用，按 WORKFLOW 调用 orchestrator、secretary、file-manager 等并产出到公司目录。
metadata:
	category: operations
---

# 每日巡检

按 `./butler_bot_agent/agents/docs/WORKFLOW.md` 执行每日启动与每日收口，确保待办、日志、归档与明日优先级就绪。

## 教程与方案来源

- **流程依据**：`WORKFLOW.md` 中的「A. 每日启动」「C. 每日收口」。
- **协作依据**：`AGENTS_ARCHITECTURE.md` 中 orchestrator → secretary → 各专项 Agent → 收口汇总。
- **产出路径**：所有产出写入 `./工作区` 下对应 Agent 子目录（见 AGENTS_ARCHITECTURE）。

## 快速开始

### 每日启动（约 10 分钟）

1. 调用 **orchestrator-agent**：汇总输入（昨日日志、新任务、会议安排），生成当日任务板。
2. 调用 **secretary-agent**：创建当日日志并生成待办看板。
3. 按任务类型分发给专项 Agent（literature / file-manager / research-ops / engineering-tracker / discussion）。

```bash
# 飞书工作站通过 Cursor CLI 依次调用，工作区指定为 ./工作区
agent -p --force --trust --approve-mcps --output-format json --workspace "./工作区" "<给 orchestrator：汇总昨日与新任务，生成当日任务板，产出写入 ./工作区/orchestrator/>"
agent -p --force --trust --approve-mcps --output-format json --workspace "./工作区" "<给 secretary：创建今日日志与待办看板，产出写入 ./工作区/secretary/>"
```

### 每日收口（约 15 分钟）

1. 调用 **secretary-agent**：汇总「完成 / 未完成 / 阻塞」。
2. 调用 **orchestrator-agent**：生成明日优先级。
3. 调用 **file-manager-agent**：执行当日归档动作。

```bash
# 收口阶段同样指定工作区 ./工作区，并明确产出路径
agent -p ... "<给 secretary：汇总今日完成/未完成/阻塞，产出写入 ./工作区/secretary/>"
agent -p ... "<给 orchestrator：生成明日优先级，产出写入 ./工作区/orchestrator/>"
agent -p ... "<给 file-manager：执行当日归档，产出写入 ./工作区/file-manager/>"
```

## 输出格式

- **orchestrator**：当日任务板、明日优先级（Markdown 或结构化列表）。
- **secretary**：当日日志、待办看板、完成/未完成/阻塞汇总。
- **file-manager**：当日归档记录、目录健康检查结果（若有）。

产出均位于 `./工作区/<agent 名>/`，便于追溯与周报引用。

## 方案选择

| 场景       | 建议 |
|------------|------|
| 仅「今日启动」 | 只执行「每日启动」三步。 |
| 仅「今日收口」 | 只执行「每日收口」三步。 |
| 完整每日巡检   | 先启动后收口；若同一天已做过启动，收口可单独执行。 |
| 每周例行     | 见 [reference.md](reference.md)，由飞书工作站做职责冲突巡检与治理产出。 |

## 注意事项

- 调用子 Agent 时**必须指定工作区**为 `./工作区`（或具体子路径），并在 prompt 中写明「产出写入 `./工作区/<对应位置>`」。
- 每个任务至少两条 chat 记录：开始、结束。
- 每日巡检与**每周巡检**不同：每周巡检为治理层面（角色负载、扩编建议、AGENTS_ARCHITECTURE 更新），由 feishu-workstation-agent 直接处理，产出在 `./工作区/governance/`。

## 更多说明

- 与 WORKFLOW / 每周巡检的对应关系及检查清单见 [reference.md](reference.md)。
