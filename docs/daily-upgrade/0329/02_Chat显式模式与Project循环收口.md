# 0329 Chat 显式模式与 Project 循环收口

日期：2026-03-29  
状态：现役 / 已落代码

## 目标

把 chat 从“隐式混合前门”收口成“少量显式主场景 + 独立 prompt 厚度 + mode-specific recent + 稳定 project 循环”。

## 当前裁决

### 1. 用户可见主模式

1. 默认无 slash：
   - 当前已升级为 **router 自动判别主模式**
   - 默认仍从 `chat` 入口进入，但会在前台编译阶段自动判到 `share / brainstorm / project(plan|imp|review) / bg`
2. 显式主模式：
   - `/share`
   - `/brainstorm`
   - `/project`
   - `/bg`
3. `project` phase 命令：
   - `/plan`
   - `/imp`
   - `/review`
4. 控制命令：
   - `/status`
   - `/govern`
   - `/reset`
5. prompt 厚度控制：
   - `/pure`
   - `/pure2`
   - `/pure3`

### 2. sticky 规则

1. `/share`、`/brainstorm`、`/project`、`/bg` 继续作为**显式 override**，优先级高于 router 自动判别。
2. `/plan`、`/imp`、`/review` 若当前不在 `project`，会自动进入 `project` 并设置当前 phase。
3. `/chat` 和 `/reset` 都会清空 sticky mode，回到默认 `chat`。
4. 没有 slash 时，router 会先结合当前 sticky state、当前消息内容和短续接特征，自动决定本轮 `main_mode / role / injection_tier`。
5. 只有带正文的 slash 会继续执行当前轮；裸命令只返回模式切换确认，不会继续调用 chat executor。

### 3. prompt 厚度职责

1. `/pure` 系列只做减法，不再负责功能分流。
2. `pure`：
   - 去掉长期记忆大块、冗余 bootstrap、self_mind 等厚内容
3. `pure2`：
   - 再减到“基础骨架 + 当前模式最小 block + 必要 recent”
4. `pure3`：
   - 极简态，只保留安全骨架、当前消息和当前模式最小合同
5. 当前厚度主档由 router 先编译成：
   - `minimal`
   - `standard`
   - `extended`
   然后再由 `/pure*` 在该档位之上继续做减法。

### 4. main mode 对 prompt 的影响

`chat`

- 默认高密度工作聊天
- 允许 capabilities
- recent 最大

`share`

- 面向分享、转发、整理、提炼
- 不注入 agent capabilities
- 优先内容理解和结构化整理

`brainstorm`

- 面向发散、迁移、方向生成
- 不注入 agent capabilities
- 优先方向簇和最值得继续推进的 1-3 条

`project`

- 面向稳定项目循环
- 只有 `phase=imp` 时允许 agent capabilities
- 连续性优先依赖 `project_artifact`

当前 router 同步给出角色：

- `plan -> project_planner`
- `imp -> project_implementer`
- `review -> project_reviewer`

`bg`

- 唯一后台入口态
- 不注入 agent capabilities
- 只负责后台目标、边界、启动条件、状态查询协作

### 5. recent 配额

1. `chat`
   - visible `10`
   - summary `5`
2. `share`
   - visible `6`
   - summary `3`
3. `brainstorm`
   - visible `5`
   - summary `3`
4. `project`
   - visible `6`
   - summary `4`
5. `bg`
   - visible `4`
   - summary `3`

当前装配顺序固定为：

1. mode artifact
2. 最近直接相关轮次
3. mode-specific visible recent
4. mode-specific summary recent

### 6. project 循环

1. `project` 默认 phase：
   - `plan`
2. 自动建议循环：
   - `plan -> imp`
   - `imp -> review`
   - `review -> pass ? plan : imp`
3. `project_artifact` 当前最小字段：
   - `goal`
   - `latest_conclusion`
   - `open_question`
   - `next_action`
   - `next_phase`
4. project 连续性不再主要靠堆 recent，而是靠 `project_artifact + 少量 recent`。

### 7. 后台入口边界

1. 显式 `/bg` 是唯一常规后台入口。
2. `/status`、`/govern` 继续作为控制命令存在，不受 `chat_frontdoor_tasks_enabled=false` 的普通任务熔断影响。
3. 普通消息不再因为“后台”“任务”等关键词自动偷跑到后台 negotiation。
4. 兼容命令 `/delivery`、`/research` 仍按 `bg` 兼容入口处理，但不再建议作为主用户态。

## 代码真源

1. mode 状态与 recent 配额：
   - `butler_main/chat/session_modes.py`
2. slash 模式解析：
   - `butler_main/chat/frontdoor_modes.py`
   - `butler_main/chat/mainline.py`
   - `butler_main/chat/router_plan.py`
3. prompt 装配与场景 guidance：
   - `butler_main/chat/prompting.py`
   - `butler_main/chat/assets/bootstrap/CHAT.md`
   - `butler_main/chat/providers/butler_prompt_provider.py`
4. runtime 能力注入边界：
   - `butler_main/chat/runtime.py`
   - `butler_main/agents_os/skills/injection_policy.py`
5. recent 装配：
   - `butler_main/chat/memory_runtime/recent_turn_store.py`
   - `butler_main/chat/memory_runtime/recent_prompt_assembler.py`
   - `butler_main/runtime_os/process_runtime/engine/conversation_turn.py`
6. 前门兼容与任务熔断边界：
   - `butler_main/chat/feature_switches.py`
   - `butler_main/agents_os/runtime/request_intake.py`

## 验证

1. 已通过定向回归：
   - `test_conversation_turn_engine.py`
   - `test_talk_runtime_service.py`
   - `test_agent_soul_prompt.py`
   - `test_chat_recent_memory_runtime.py`
   - `test_talk_mainline_service.py`
   - `test_chat_router_frontdoor.py`
   - `test_request_intake_service.py`
2. 结果：
   - `76 passed`
3. 本轮未重跑：
   - `test_chat_campaign_negotiation.py`
   - `test_chat_long_task_frontdoor_regression.py`
4. 原因：
   - 这两组在 `0329` 当日总纲里已被确认存在历史性的退出挂住问题，本轮没有顺带清理其进程/资源收尾机制。
