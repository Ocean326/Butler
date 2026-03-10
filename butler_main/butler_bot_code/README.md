# 飞书机器人统一管理

多机器人的目录结构、配置规范与进程管理方案。

## Butler 新分层

当前 Butler 按四层自我系统理解与维护：

- `butler_bot_agent/` 是脑子：负责角色、工作流、记忆读取、任务分派。
- `butler_bot_code/` 是身体：负责飞书运行时、心跳、守护、日志、配置、测试。
- `butle_bot_space/` 是家：负责生活痕迹、备份、探索记录、心跳相关沉淀。
- `工作区/` 是公司：负责用户任务与正式产出。

后续做自我整理、自我升级时，先判断修改属于哪一层，再落到对应目录。统一约定见 `docs/脑体家工_自我系统与维护约定.md`。

## 目录结构

```
feishu-bots/
├── README.md           # 本说明
├── registry.json       # 机器人注册表（名称 → 配置、脚本、描述）
├── manager.ps1         # 统一管理：启动、停止、状态、列表
├── bots/               # 机器人实现脚本
│   └── butler_bot.py
├── configs/            # 各机器人配置（按名称，不提交敏感信息）
│   └── butler_bot.json.example
├── run/                # 运行时 PID
├── logs/               # 运行日志
└── workspace/          # 运行时工作区（预留：临时文件、缓存、输出）
```

## 配置规范

- 每个机器人在 `configs/` 下有一份配置，如 `{bot_name}.json`
- 提供 `{bot_name}.json.example` 作为模板，实际配置加入 `.gitignore`
- 配置字段由各机器人脚本自行定义，需至少包含 `app_id`、`app_secret`

## 新增机器人流程

1. 在 `bots/` 下编写 `{name}.py`，支持 `--config configs/{name}.json`
2. 在 `registry.json` 中注册
3. 复制 `configs/{name}.json.example` 为 `configs/{name}.json` 并填写
4. 使用 `.\manager.ps1 start {name}` 启动

## 自我认知（Self-Cognition）

- 本仓库为「管家 bot」实现；与 Cursor / 飞书工作站的衔接、入口、记忆与调用链说明见：**[docs/SELF_COGNITION_butler_bot.md](docs/SELF_COGNITION_butler_bot.md)**。供后续自我进化与改进计划参考。
- Butler 的整体四层定位与后续维护原则见：**[docs/脑体家工_自我系统与维护约定.md](docs/脑体家工_自我系统与维护约定.md)**。
- 如果需要先建立整体脑图、快速定位配置/进程/心跳/守护问题，优先看：**[docs/Butler项目全景说明与排障地图.md](docs/Butler项目全景说明与排障地图.md)**。

## 版本与改动说明

- 最新改动说明：**[docs/变更说明_20260311_心跳tell_user反思式开口.md](docs/变更说明_20260311_心跳tell_user反思式开口.md)**
- 上一版重要说明：**[docs/变更说明_20260308_心跳并行与可见性.md](docs/变更说明_20260308_心跳并行与可见性.md)**
- 维护规则：**[docs/改动说明维护规范.md](docs/改动说明维护规范.md)**
- 历史说明：见 `docs/` 目录下以 `变更说明_YYYYMMDD_主题.md` 命名的文档。

## Cursor Agent 扩展能力

- **飞书文档检索**：用户消息包含「检索」「搜索」「文档」等关键词时，自动调用飞书云文档搜索 API，将结果注入上下文。需在飞书开放平台申请「搜索云文档」等权限。
- **卡片式交互（已升级）**：机器人回复会优先发送 `interactive` 卡片，并在最终回复卡片附带快捷按钮（如「继续展开」「总结待办」「一句话版」）；用户点击后通过 `card.action.trigger` 回调触发下一轮处理，机器人会根据动作与上下文自行决定发送内容。
- **产出文件发送**：由模型在回复末尾输出【decide】块指定要发送的文件，格式 `[{"send":"./工作区/xxx.md"},...]`，系统解析后直接上传发送。
- **运行时切换模型**：可在飞书消息里直接写「用 gpt-5 回答：...」「[模型=sonnet-4] ...」，也可发送「模型列表」「当前模型」查询。
- **本机记忆接口**：`python bots/memory_cli.py recent-list`、`local-query`、`recent-add`、`local-add` 可直接读写 `recent_memory` / `local_memory`。
- **后台心跳**：心跳 sidecar 的启动、巡检与重启已迁移到 `guardian/`；Butler 仅保留心跳执行逻辑与配置，不再承担守护职责。
- **独立守护迁移**：Butler 不再内置 `restart_guardian_agent.py` 看门狗；守护、审阅、执行与值守日志统一迁移到仓库根目录下的 `guardian/`。
- **心跳任务记忆**：心跳任务已开始切换到 `./butler_bot_agent/agents/state/task_ledger.json` 统一账本；兼容期仍会同步 `./butler_bot_agent/agents/recent_memory/heart_beat_memory.json` 与 `./butler_bot_agent/agents/local_memory/heartbeat_long_tasks.json`。旧 Markdown 镜像已停写并归档，不再作为活跃真源。
- **心跳 prompt 分层**：planner role 在 `./butler_bot_agent/agents/heartbeat-planner-agent.md`，planner context 在 `./butler_bot_agent/agents/heartbeat-planner-context.md`，JSON 模板在 `./butler_bot_code/prompts/heart_beat.md`；后续调整时按 soul + role + context + template 分层修改，不要再把它们重新混写回配置或代码。
- **心跳并行执行（Agent Team）**：单轮心跳支持「多分支规划 + 受控并行执行 + 主控汇总」；默认单轮最多并行 3 路（可用 `heartbeat.max_parallel_branches` 配置，实际上限仍为 3），适用于互不依赖任务并行推进；复杂任务可拆成 2-3 个分支后合并摘要，超出预算的任务延后到下一轮。
- **心跳独立日志**：心跳已改为独立子进程，默认写入 `logs/butler_bot_heartbeat_YYYYMMDD_001.log`（按天 + 每文件最多 1000 行自动分片递增 `_002`、`_003`...），与主 bot 长连接日志分开，便于排障。
- **日志级别热更新**：支持在 `configs/butler_bot.json` 的 `logging.level` 设置 `debug|info|error`，进程运行中改配置可自动生效（按 `logging.check_interval_seconds` 轮询）。

## 飞书后台事件配置（卡片交互必需）

请在飞书开放平台机器人应用中确认已订阅以下事件并发布版本：

- `im.message.receive_v1`（接收用户消息）
- `card.action.trigger`（接收卡片按钮点击回调）

若缺少 `card.action.trigger`，机器人仍可发卡片，但按钮点击不会触发后续处理。

## 管理命令

```powershell
.\manager.ps1 list              # 列出已注册机器人
.\manager.ps1 status            # 查看运行中的机器人
.\manager.ps1 start <name>      # 启动指定机器人（后台）
.\manager.ps1 stop <name>       # 停止指定机器人
.\manager.ps1 stop --all        # 停止全部飞书机器人
.\manager.ps1 restart <name>    # 重启指定机器人
```

> `status` 仅显示 Butler 主进程；心跳与守护状态请使用仓库根目录下的 `guardian/manager.ps1` 查看与管理。
