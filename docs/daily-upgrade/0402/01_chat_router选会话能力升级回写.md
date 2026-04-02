# 0402 Chat Router 选会话能力升级回写

日期：2026-04-02  
状态：已实施  
层级：`Product Surface / chat frontdoor`

## 背景裁决

- Butler chat 在一个 `session_scope_id` 内，可以连续存在多条内部 chat 主线；当前前台只续接“当前活跃的那条”。
- 若用户消息明显切到新题，frontdoor 可以在当前 scope 内重开新的 `chat_session_id`。
- 若用户消息只是短追问、补充、修正、引用上一轮，则默认续接当前 session，不额外开模型轮次做澄清。

## 本轮实现

1. 新增 `butler_main/chat/session_selection.py`
   - 增加 `ChatSessionState`、`ChatSessionSelection`
   - 增加 `select_chat_session()`、`build_chat_session_state_after_turn()`
   - 统一沉淀 followup/new-task/topic-overlap 判断
   - 增加 bootstrap 逻辑：当前 scope 第一次进入 chat 也会先拿到 `chat_session_id`
2. `mainline -> routing -> router_plan`
   - `mainline` 在 build runtime request 前先做 session 选择
   - `RouterCompilePlan` 增加：
     - `router_session_action`
     - `router_session_confidence`
     - `router_session_reason_flags`
     - `chat_session_id`
   - sticky mode 与 slash override 继续保留，但 slash 显式模式不会被 session reopen 干扰
3. `runtime / conversation_turn / prompt`
   - runtime 复用 `prefilled_intake_decision`，减少一次 intake classify
   - prompt 注入轻量 `session_selection` 指示块
   - Codex 分支同样消费该块，不额外起协商轮
4. `recent memory`
   - `recent_memory.json`
   - `recent_raw_turns.json`
   - `recent_summary_pool.json`
   都支持按 `chat_session_id` 过滤
   - 当前 turn 的 provisional entry、raw turn、summary pool 都会写入对应 `chat_session_id`
5. `project phase`
   - review 态推进更保守
   - 若用户仍在 review 语境，只因为出现“实现方案”这类词，不再误推到 `imp`

## 当前行为口径

- `session_scope_id`
  - Butler chat 对外连续性的主键
- `chat_session_id`
  - 当前 scope 内部当前会话主线 id
- `router_session_action=continue_current`
  - 默认续接当前内部 chat session
- `router_session_action=reopen_new_session`
  - 表示当前消息被判为新题，当前 scope 内切到新内部 session
- `router_session_reason_flags`
  - 只做轻量解释与 prompt 提示，不作为新协议面暴露给用户

## 回归测试

- `butler_main/butler_bot_code/tests/test_talk_mainline_service.py`
  - sticky project review 行为
  - 新题重开内部 chat session
- `butler_main/butler_bot_code/tests/test_chat_recent_memory_runtime.py`
  - recent context 只投喂当前 `chat_session_id`
- `butler_main/butler_bot_code/tests/test_talk_runtime_service.py`
  - runtime 复用 prefilled intake，避免重复 classify
- `butler_main/butler_bot_code/tests/test_chat_router_frontdoor.py`
  - 继续覆盖 `RouterCompilePlan` 编译行为

## 仍保留的边界

- 本轮不做跨 thread / 全局 chat 检索。
- 本轮不把 vendor-native thread 当 Butler chat 连续性的真源。
- 本轮不新增 second-pass disambiguation model round。
- 当前 recent 条目总量仍按 scope 粗裁，不按 `chat_session_id` 单独配额裁剪；这是后续可优化项，不影响当前正确性口径。
