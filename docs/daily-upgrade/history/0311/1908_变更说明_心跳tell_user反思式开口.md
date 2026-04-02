# 变更说明：心跳 tell_user 反思式开口

- 日期：2026-03-11
- 范围：`butler_bot_code/butler_bot/memory_manager.py`、`butler_bot_code/butler_bot/heartbeat_orchestration.py`、`butler_bot_code/butler_bot/subconscious_service.py`、`butler_bot_code/prompts/heart_beat.md`、`butler_bot_agent/agents/heartbeat-planner-agent.md`、`butler_bot_code/tests/test_heartbeat_proactive_talk.py`、`butler_bot_code/tests/test_memory_manager_maintenance.py`、`butler_bot_code/README.md`
- 目标：把心跳的 `tell_user` 从“planner 当轮直接写给用户的话”改成“上一轮心理活动沉淀 -> 下一轮继续心理活动并决定是否开口 -> 由 Feishu 对话人格组织最终表达”。

## 背景

此前 `tell_user` 主要来自 planner 直接输出，或来自同轮内的启发式补文案。这会导致两个问题：

1. 心跳更像在交付一个字段，而不是像人一样在多轮里积累“我现在想和用户说点什么”。
2. 最终用户可见的话术由 planner 层直接决定，和 Feishu 对话人格存在职责混叠。

这次调整把“想说什么”与“怎么说”拆开：planner 只留下候选意图，下一轮再由 Feishu 角色继续那段心理活动，决定要不要开口、如何开口。

## 功能变更

1. `tell_user` 从单轮字段改为跨轮意图。
- 本轮 heartbeat 会把候选说话意图沉淀进 `heartbeat_execution_snapshot.tell_user_intention`。
- 下一轮 heartbeat 优先尝试承接上一轮的 pending tell-user intention，再判断是否发往对话窗。

2. planner 不再直接拥有最终用户话术。
- planner schema 新增：`tell_user_candidate`、`tell_user_reason`、`tell_user_type`、`tell_user_priority`。
- 兼容旧字段 `tell_user`，但仅作为候选意图 fallback，不再视作最终发言文本。

3. Feishu 对话人格接管最终组织语言。
- `memory_manager.py` 新增通过 Feishu role 继续心理活动并生成最终文案的链路。
- 组织语言本身也被视为继续心理活动，而不是简单模板拼接。

4. 主对话活跃时让路，不抢话。
- 新增 recent talk 窗口活跃检测；若用户刚在主对话里活跃，pending tell-user intention 会延期到后续轮次。

5. 心跳快照与 companion entries 会携带更完整的 tell-user 意图信号。
- `subconscious_service.py` 现在会把 `result_share`、`risk_share`、`thought_share`、`light_chat` 等类型写入心跳快照。
- 关系信号和心理活动 companion entries 会保留“为什么想说”的痕迹，便于后续继续。

## 关键实现点

- `heartbeat_orchestration.py`
  - `build_status_only_plan`
  - `build_planning_prompt`
  - `plan_action`
  - planner schema 扩展为 tell-user candidate/reason/type/priority

- `subconscious_service.py`
  - `_build_heartbeat_tell_user_intention`
  - `_build_heartbeat_primary_entry`
  - `_build_heartbeat_companion_entries`

- `memory_manager.py`
  - `_heartbeat_tell_user_intent_path`
  - `_load_heartbeat_tell_user_intent`
  - `_save_heartbeat_tell_user_intent`
  - `_clear_heartbeat_tell_user_intent`
  - `_talk_window_is_active`
  - `_build_reflective_tell_user_intent_for_next_round`
  - `_compose_reflective_tell_user_text_via_feishu`
  - `_continue_reflective_tell_user`
  - `_run_heartbeat_once`

## 验证结果

已执行：

```powershell
.venv\Scripts\python.exe -m unittest -v butler_main.butler_bot_code.tests.test_heartbeat_proactive_talk butler_main.butler_bot_code.tests.test_memory_manager_maintenance butler_main.butler_bot_code.tests.test_heartbeat_orchestration
```

结果：`Ran 38 tests in 7.441s`，`OK`。

补充运行验证：

```powershell
Set-Location .\butler_main\butler_bot_code
.\manager.ps1 restart butler_bot
```

重启后确认：

- `run/butler_bot_main_state.json` 为 `state=running`，主进程 pid 已刷新。
- `run/heartbeat_watchdog_state.json` 与 `run/heartbeat_run_state.json` 为 `running`。
- `run/guardian_pid_snapshot.json` 刷新为 `overall.healthy=true`。

## 已知边界

- 当前 tell-user 仍以单条 pending intent 状态为主，不支持多条候选意图排队竞争。
- `parallel_branch_count` 在 heartbeat snapshot 中表示规划为并行的总分支数，不是运行时并发上限；运行时上限仍由执行器控制。
- 若 Feishu 文案生成失败，会退回本地 fallback 文案，语气会比 role 续写路径更机械。

## 回滚点

1. 回退 `memory_manager.py` 中 pending tell-user intention 的读写与 continuation 逻辑，恢复为同轮直接发送。
2. 回退 `subconscious_service.py` 中 `tell_user_intention` 快照写入，仅保留原有 heartbeat snapshot。
3. 回退 planner schema 的 tell-user candidate 扩展，恢复旧 `tell_user` 单字段语义。

## 心跳同步信息可读性改进备忘

> 目标：解决“心跳同步信息一堆可同步、看不出哪个分支在干啥”的反馈，让用户在心跳窗中一眼看出：**是谁在干什么，对我有什么影响**。

### 1. 给每个分支一个「标题 + 一句话」模板

- **分支建议标题**：`[主题标签] 关键动作/对象`，例如：
  - `[任务账本] 清理 heartbeat 长期任务视图`
  - `[记忆体系] recent/local 抽样自检`
  - `[外部集成] Feishu chat history 回溯对齐`
- **一句话说明模板**（用于 `【heartbeat_tell_user_markdown】` 内文）：
  - 结构：`我做了什么 → 现在状态如何 → 对你意味着什么/是否需要你确认`
  - 例：`本轮把 heartbeat 任务账本与文本视图对齐到同一枚举，你看到的长期任务列表已经去重，后续若有新增长期任务会优先写入账本而不是角色文档。`

### 2. 按主题分组，而不是平铺所有分支

- **心跳总览侧展示建议**（由整合层实现，不强行要求 planner）：
  - 先按主题分组，例如：`记忆与任务系统 / 外部集成与同步 / 自我升级与治理 / 轻量维护与整理`
  - 组内只展示每个分支的「标题 + 一句话」，必要时再展开细节链接到工作区/日志。
- **分支自报主题**：在 planner/执行器层可通过 `tell_user_type` 或补充元数据标记所属主题，整合层按主题聚合；缺省时可根据 `agent_role` 推断（如 `agent_upgrade` → 自我升级与治理）。

### 3. 标记哪些信息进 user_message，哪些留在详细日志

- **优先进入心跳窗 user_message 的信息**：
  - 风险、异常、可能影响用户决策的结构变更（如任务丢失风险、记忆机制切换、自我升级申请关键结论）。
  - 用户需要知道「现在可以/不可以做什么」的状态变化（如“心跳目前暂停执行外部写入，只做自检”）。
- **仅保留在详细日志/工作区文档的信息**：
  - 纯实现细节、调参记录、一次性排障过程、对内部机制的长篇思考。
- **实现建议**：
  - 在 planner schema 中继续利用 `tell_user_type` / `tell_user_priority`，约定高优先级 + 风险/结构类主题才进入 user_message，其它落在心跳日志与工作区文档。
  - Feishu 对话人格在组织最终文案时，只挑选当轮「高优先级 + 未读」意图拼成一条简明心跳同步，而不是逐分支逐条照搬。
