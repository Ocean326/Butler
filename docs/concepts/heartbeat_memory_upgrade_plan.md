# 心跳任务记忆改造实施计划

更新时间：2026-03-07

> **状态提示（2026-03-11 二轮代谢检查补充）**：本计划文档描述的是 2026-03-07 时点的心跳任务记忆改造设想。当前实现中，`heart_beat_memory.json` 已作为**兼容期短期心跳任务镜像**存在（真源以 `agents/state/task_ledger.json` + `agents/local_memory/heartbeat_tasks.md` 为主），`heartbeat_long_tasks.json` 也仍保留为兼容期长期任务镜像。实际运行状态以近期代码与 `heartbeat_新陈代谢机制_试运行_20260310.md`、`self_mind与回忆机制_总体设计_20260311.md`、`SELF_COGNITION_butler_bot.md` 等更新文档为准。本文件在后续实现与重构时应视为**待对齐的历史规划稿**，使用前建议先复核是否仍与当前实现一致。

## 目标

把当前“固定文案心跳”改造成“基于任务记忆的自治心跳”，满足以下要求：

1. 在 `recent_memory` 旁新增短期心跳任务记忆 `heart_beat_memory`，供每次心跳作为 prompt 输入。
2. 用户在对话中显式或隐式提出的后台任务、提醒、工作时段等信息，能够沉淀到心跳任务系统。
3. 新增长期/定时任务持久化真源文件，并提供 Markdown 镜像，保证提醒与周期任务跨重启保留。
4. 每次心跳时统一把三类来源交给模型决策优先级：
   - 短期任务
   - 长期/定时任务
   - 模型自行发现的可执行事项
5. 心跳执行后会回写状态，自动更新短期任务和长期任务。
6. 当前阶段将心跳频率调整为每 5 分钟一次，并且每次触发都向用户发消息。

## 设计原则

1. 调度保持简单：继续复用现有 heartbeat 单线程循环，不额外引入复杂调度器。
2. 状态结构化：JSON 作为真实数据源，Markdown 作为人工可读镜像。
3. 写入保守：优先从显式表述和高置信隐式表达提取任务，避免把普通闲聊错误沉淀为后台任务。
4. 心跳分两段：先做“决策/规划”，再做“执行/汇报”，避免一条 prompt 承担全部职责。
5. 兼容现有 recent/local memory，不破坏已有短期记忆与长期记忆维护逻辑。

## 数据结构

### 1. （历史设想）短期心跳任务存储

文件：`./butler_bot_agent/agents/recent_memory/heart_beat_memory.json`  
（当前实现已改为以 `agents/state/task_ledger.json` + `agents/local_memory/heartbeat_tasks.md` 为心跳任务主口径，本小节仅保留为 2026-03-07 设计稿记录）

建议结构：

```json
{
  "version": 1,
  "updated_at": "2026-03-07 12:00:00",
  "tasks": [
    {
      "task_id": "uuid",
      "source": "conversation",
      "source_memory_id": "uuid",
      "created_at": "2026-03-07 11:50:00",
      "updated_at": "2026-03-07 11:50:00",
      "status": "pending",
      "priority": "medium",
      "title": "12:00 提醒开始汇报整理",
      "detail": "用户要求以后每天 12:00 提醒开始汇报整理",
      "trigger_hint": "daily@12:00",
      "due_at": "2026-03-08 12:00:00",
      "tags": ["提醒", "定时"],
      "last_result": ""
    }
  ],
  "notes": []
}
```

### 2. 短期心跳任务 Markdown 镜像

文件：`./butler_bot_agent/agents/recent_memory/heart_beat_memory.md`

用途：

- 便于用户人工查看当前短期后台任务
- 便于模型在执行时读取人类友好格式

### 3. （历史设想）长期/定时任务存储

文件：`./butler_bot_agent/agents/local_memory/heartbeat_long_tasks.json`  
（当前实现中，该文件更多作为兼容期镜像，统一结构化真源仍以 `task_ledger.json` 为主）

建议结构：

```json
{
  "version": 1,
  "updated_at": "2026-03-07 12:00:00",
  "tasks": [
    {
      "task_id": "uuid",
      "kind": "reminder",
      "schedule_type": "daily",
      "schedule_value": "12:00",
      "time_window": "14:00-17:00",
      "timezone": "Asia/Shanghai",
      "enabled": true,
      "title": "每天 12:00 提醒我",
      "detail": "提醒用户检查今日任务",
      "created_at": "2026-03-07 12:00:00",
      "updated_at": "2026-03-07 12:00:00",
      "last_run_at": "",
      "next_due_at": "2026-03-08 12:00:00",
      "last_result": ""
    }
  ]
}
```

### 4. 长期/定时任务 Markdown 镜像

文件：`./butler_bot_agent/agents/local_memory/heartbeat_long_tasks.md`

用途：人工检查、模型辅助阅读、便于直接在工作区追踪。

## 流程改造

### A. 对话结束后的任务提取

在 `MemoryManager._summarize_turn_to_recent` 现有 JSON 输出基础上扩展 schema，增加：

- `heartbeat_tasks`: 本轮应加入短期心跳任务的项目列表
- `heartbeat_long_term_tasks`: 本轮应沉淀为长期/定时任务的项目列表

同时加入规则兜底：

1. 显式提取：用户出现“后台帮我”“心跳里做”“每天提醒我”“以后每天”“工作时间是”等表达时，优先抽取任务。
2. 隐式提取：当句子同时包含动作 + 时间/周期线索时，允许提取到长期任务候选。
3. 模型失败时，用启发式规则至少抽取：
   - 每天/每周/定时提醒
   - 工作时段
   - “后台继续完成”的未闭环任务

落地方式：

1. 精炼 recent memory
2. 将 `heartbeat_tasks` 追加/合并进 `heart_beat_memory.json`
3. 将长期/定时项追加/合并进 `heartbeat_long_tasks.json`
4. 同步刷新两个 Markdown 镜像

### B. 心跳前的统一决策

改造 `_run_heartbeat_once`，不再只依赖 `heartbeat.agent_prompt`。

新流程：

1. 读取 `heart_beat_memory.json`
2. 读取 `heartbeat_long_tasks.json`
3. 读取最近几条 `recent_memory`
4. 构造“心跳规划 prompt”，明确告诉模型有三类候选：
   - 短期任务
   - 长期/定时任务
   - 自主发现事项
5. 第一次模型调用只输出结构化 JSON 决策，例如：

```json
{
  "chosen_mode": "short_task|long_task|explore|status",
  "reason": "...",
  "user_message": "...",
  "execute_prompt": "...",
  "selected_task_ids": ["..."],
  "updates": {
    "complete_task_ids": [],
    "defer_task_ids": [],
    "touch_long_task_ids": []
  }
}
```

6. 若 `execute_prompt` 非空，则第二次调用模型实际执行。
7. 将执行结果与状态回写到短期/长期任务中。
8. 无论是否执行任务，本阶段都向用户发送一条心跳消息。

### C. 心跳后的自更新

每次心跳结束后：

1. 将已完成的短期任务标记为 `done`
2. 将仍未完成的任务更新时间与最近结果
3. 对长期任务更新 `last_run_at`、`next_due_at`、`last_result`
4. 若模型发现某短期任务已自然完成，则从活动列表中移除或归档
5. 刷新 Markdown 镜像

## OpenClaw 借鉴点与本地化调整

借鉴点：

1. 采用统一 wake-up/heartbeat 驱动，而不是给每类任务单独起线程。
2. 配置驱动周期，而不是把提醒逻辑写死在代码里。
3. 用“规划 + 执行”两段式 prompt，降低一次性大 prompt 的混乱度。

本仓库中的本地化调整：

1. 继续保留现有 `MemoryManager` 为中心，不拆新服务。
2. 用本地 JSON + Markdown 文件承载任务状态，避免外部依赖。
3. 复用现有 `_run_model_fn` 和飞书私聊发送逻辑。

## 配置改动

`configs/butler_bot.json` 与 `.example` 同步调整：

1. `heartbeat.every_minutes` 改为 `5`
2. 新增建议字段：
   - `planner_model`
   - `executor_model`
   - `always_notify`
   - `max_short_tasks`
   - `max_long_tasks_in_prompt`
3. 默认启用 `always_notify=true`

## 测试计划

### 单元测试

1. `test_memory_manager_recent.py`
   - recent 精炼结果能写入短期心跳任务
   - 显式提醒表达能进入长期任务
   - 模型失败时启发式规则仍能提取部分任务

2. `test_memory_manager_maintenance.py`
   - 心跳第一次等待 `startup_delay_seconds`，之后按 5 分钟周期
   - 心跳规划在无 `agent_prompt` 时也会调用新的规划流程

3. 新增或扩展心跳测试
   - 规划结果选择短期任务
   - 规划结果选择长期任务
   - 规划结果选择自主探索
   - 心跳后任务状态成功回写

### 集成验证

1. 本地运行相关测试文件
2. 检查生成的 JSON/Markdown 文件结构
3. 重启 `butler_bot`
4. 观察日志确认心跳线程按 5 分钟调度

## 执行顺序

1. 新增计划文档
2. 扩展记忆目录与任务文件读写工具
3. 扩展 recent 精炼 schema 与启发式提取
4. 改造 heartbeat 为“规划 + 执行 + 回写”流程
5. 更新配置模板和实际配置
6. 编写与修正测试
7. 更新 README/说明文档
8. 运行测试并重启服务

## 风险与控制

1. 模型提取过度：通过显式关键词 + 时间线索双重条件降低误报。
2. 任务并发写冲突：继续复用 `self._memory_lock` 保护 recent/heartbeat 文件。
3. 心跳 token 消耗过高：规划调用与执行调用设置较短超时，并限制 prompt 内任务数量。
4. 用户刷屏：本阶段按要求每次都发消息，后续可再引入“仅有事才发”的配置开关。