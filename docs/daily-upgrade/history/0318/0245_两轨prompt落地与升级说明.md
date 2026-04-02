# 0318 两轨 Prompt 落地与升级说明

> 更新时间：2026-03-18
>
> 本文记录本轮“两轨制 prompt”落地结果、测试情况、上线动作与当前验证结论。

## 1. 本轮目标

按 `0200_butler_prompt完善计划.md` 的最小落地路线，优先实现：

1. `Raw turn log` 与 `Light prompt view` 的两轨制
2. 默认 prompt 不直接回放 `raw_user_prompt`
3. 在需要时按需检索近期 raw turn
4. heartbeat 继续保持 `task_ledger` / `heartbeat_tasks.md` 为主视图，不退化成 raw history 驱动

本轮明确**未做**：

1. 敏感信息脱敏治理
2. 大规模 state machine / assistant_state_store
3. planner 架构重写

也就是：先把“两轨制”落下，再谈更细的治理。

## 2. 实际代码改动

### 2.1 新增 raw turn artifact service

新增文件：

- `butler_main/butler_bot_code/butler_bot/services/raw_turn_artifact_index.py`

职责：

1. 为最近 raw turns 建结构化 artifact 抽取
2. 当前抽取对象包括：
   - URLs
   - file paths
   - commands
   - error blocks
   - code snippets
   - assistant commitments
   - explicit user constraints
3. 构建轻量索引，供按需 prompt 检索

### 2.2 新增薄门控层

新增文件：

- `butler_main/butler_bot_code/butler_bot/services/prompt_projection_service.py`

职责：

1. 不负责大规模语义状态机
2. 只负责按需 raw 检索门控
3. 当前会在用户输入命中以下类型时尝试引入 raw 线索：
   - 链接
   - 路径 / 文件
   - 命令
   - 报错
   - 代码片段
   - 助手承诺
   - 用户原话

### 2.3 在 MemoryManager 中接入两轨制

修改文件：

- `butler_main/butler_bot_code/butler_bot/memory_manager.py`

主要变更：

1. 新增 `recent_raw_turns.json`
2. 新增 `raw_turn_artifact_index.json`
3. 在 fallback 写入与 finalize 写入时，按 `memory_id` upsert raw turn
4. `prepare_user_prompt_with_recent()` 接入按需 raw quote block
5. `_render_recent_requirement_context()` 不再默认回放 `raw_user_prompt`，改为优先使用 `summary/topic/next_actions`

结果是：

1. 默认 prompt 仍以 recent summary 为主
2. raw turn 不再默认回放
3. 但在“那个链接 / 上次报错 / 刚才那段代码 / 你答应的事 / 按我原话”这类问题上，系统已具备按需引用近期原文线索的能力

## 3. 当前两轨制的实际形态

### 3.1 轨 1：Raw turn log

当前路径：

- `butler_main/butler_bot_agent/agents/recent_memory/recent_raw_turns.json`
- `butler_main/butler_bot_agent/agents/recent_memory/raw_turn_artifact_index.json`

当前策略：

1. 保留最近 40 轮 raw turn
2. user / assistant 都保留
3. 以 `memory_id` upsert，避免 fallback 与 finalize 重复写两份
4. 不默认注入 prompt

### 3.2 轨 2：Light prompt view

默认仍由：

1. `recent_memory` summary 窗口
2. requirement / next actions
3. local memory hits
4. heartbeat task board / unified recent

承担 prompt 主上下文。

raw 只作为：

1. 精确回指的检索真源
2. 默认关闭的按需引用材料

## 4. 测试结果

本轮已跑通过：

1. `python -m pytest butler_main\butler_bot_code\tests\test_memory_manager_recent.py -q`
   - 结果：`44 passed`
2. `python -m pytest butler_main\butler_bot_code\tests\test_agent_soul_prompt.py -q`
   - 结果：`11 passed`
3. `python -m pytest butler_main\butler_bot_code\tests\test_heartbeat_orchestration.py -q`
   - 结果：`29 passed`

本轮新增 / 更新覆盖点包括：

1. 短 followup 仍能续接，但 requirement block 不再直接回放 raw prompt
2. “那个链接再打开一下”会触发按需 raw 引用
3. raw turn log 以 `memory_id` upsert，不会被 fallback + finalize 写重复

## 5. 上线动作与当前状态

本轮已执行：

1. `manager.ps1 restart butler_bot`

命令返回：

- `已启动 butler_bot（状态文件稍后刷新）`

随后执行状态检查：

1. `manager.ps1 status butler_bot`

当前返回为：

- `无运行中的飞书机器人`
- `对话主进程：stale`
- `心跳 sidecar：stale`

这说明：

1. 代码改动与测试回归已经通过
2. “重启命令已执行”这一动作完成了
3. 但当前 manager 维度的运行态**没有验证到健康上线**

所以这轮更准确的上线结论是：

**代码已合入并通过相关测试，已尝试重启服务，但当前 manager 状态仍为 stale，运行实例健康性需要后续继续确认。**

## 6. 当前已达成的效果

本轮实际达成：

1. Butler 不再只剩“summary 或 raw 回放”二选一
2. 已具备“两轨制”基础形态
3. 默认 prompt 更干净
4. 精确回指问题已有最小闭环
5. heartbeat 没有被这轮改动拉回“聊天历史驱动”

## 7. 下一步建议

如果继续按 0318 路线推进，下一步建议顺序为：

1. 验证并修复 manager stale 问题，确认真实运行实例恢复正常
2. 把 on-demand raw retrieval 再补到：
   - 报错复盘
   - 代码片段引用
   - 助手承诺追踪
3. 再进入下一轮治理：
   - raw 摘录裁剪更稳
   - artifact index 检索精度提升
   - 视情况再补轻量 prompt-visible 规则表

一句话总结：

**本轮已经把 Butler 从“summary 单轨 + raw 直接回放风险”推进到“summary 主轨 + raw 检索辅轨”的可运行形态，但服务运行态的最终健康上线仍需补确认。**
