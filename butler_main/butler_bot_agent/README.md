# 研究生文件管理与日常研究管理（多 Agent 初始化）

本配置面向“管理员 + 秘书”工作模式，覆盖：
- 日常维护性事务记录与思路整理（研究、会议、工程）
- 文献整理
- 文件管理
- 技术讨论与资料搜集
- 动态新增 Agent 与职责

## 系统定位

`butler_bot_agent/` 是 Butler 的脑子，负责：

- 定义角色、人设、规则与工作流
- 决定先读什么记忆、该调用哪个 Agent、产出写到哪里
- 把经验和方法沉淀成可复用的认知，而不是把一切塞进代码

对应关系固定为：`butler_bot_agent = 脑子`，`butler_bot_code = 身体`，`butle_bot_space = 家`，`工作区 = 公司`。脑子只负责思考、决策、分派和总结，不代替身体承担运行时细节。

## 快速开始

1. 先阅读 `agents/docs/AGENTS_ARCHITECTURE.md`
2. 再阅读 `agents/docs/AGENT_SPECS_AND_PROMPTS.md`
3. 按 `agents/docs/WORKFLOW.md` 执行当日流程
4. 使用 `工作区/` 下模板落盘

## 目录

- `agents/`：主 Agent。当前包含：
	- 入口与运行层：`feishu-workstation-agent`、`heartbeat-planner-agent`
- `agents/sub-agents/`：场景执行层与专业执行者（orchestrator、secretary、literature、heartbeat-executor 等）
- `bootstrap/`：当前 prompt 真源（SOUL/TALK/HEARTBEAT/EXECUTOR/SELF_MIND/USER/TOOLS/MEMORY_POLICY）
- `agents/docs/`：架构、规范、流程、交接模板
- `工作区/`：实际工作文件夹与模板

## 当前运行真源速记

- talk/self_mind/heartbeat bootstrap 真源：`bootstrap/*.md`
- planner 角色真源：`agents/heartbeat-planner-agent.md`
- planner context 真源：`agents/heartbeat-planner-context.md`
- heartbeat prompt 模板真源：`agents/heartbeat-planner-prompt.md`
- 任务执行账本真源：`agents/state/task_ledger.json`
- planner 任务读口真源：`agents/local_memory/heartbeat_tasks.md` + `agents/local_memory/heartbeat_tasks/*.md`
- 心跳任务变更日志：`agents/local_memory/heartbeat_tasks/task_change_log.jsonl`
- 长期记忆实现层：`agents/local_memory/`
- 工作区 `local_memory`：治理镜像、说明与草稿层，不等于单一运行真源

## 角色迁移

以下历史 role 已迁移到 `过时/roles_legacy_20260316/`，不再作为运行时 prompt 真源：

1. `butler-agent.md`
2. `butler-continuation-agent.md`
3. `subconscious-agent.md`

---
维护者：`feishu_workstation_agent`（飞书工作站）
