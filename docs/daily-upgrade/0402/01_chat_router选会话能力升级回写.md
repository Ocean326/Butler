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
6. `frontdoor + router + cli lane`
   - 新增 `butler_main/chat/frontdoor_cli_router.py`
   - `mainline` 先做 legacy session/intake 粗判，再由 unified frontdoor compile 一次性决定：
     - `route`
     - `frontdoor_action`
     - `main_mode / project_phase / role`
     - `session_action / chat_session_id`
     - `runtime_lane / runtime_cli / runtime_model`
   - 当前 lane 口径：
     - `cursor_fast` = `cursor --mode ask + composer-2-fast`
     - `cursor_exec` = `cursor + composer-2`
     - `codex_deep` = `codex + gpt-5.4`
   - chat/frontdoor 默认 lane 改为 `cursor_fast`，不改全局 `cli_runtime.active`
7. `engine / cli_runner`
   - `chat/engine.py` 不再把普通 chat turn 的默认 CLI 提前拍死
   - 用户显式 `cli/model/profile` 仍可作为 override 传入 unified router
   - 实际执行前由 mainline 编译结果写入 `TURN_STATE.turn_cli_request`
   - `cli_runner.resolve_runtime_request()` 新增 `_router_selected_runtime` 保护，chat router 选中的 Cursor lane 不再被 Codex-first 规则偷偷升级
8. `router 治理与复盘`
   - 新增 `butler_main/chat/data/hot/frontdoor_cli_router/governance_state.json`
   - 新增 `review_journal.jsonl`
   - 每 50 个 eligible chat/frontdoor turn，用轻量模型复盘最近若干轮的用户反馈与 hard failure
   - 复盘产物只写短 `prompt_appendix` 回到治理状态，不回写主配置文件

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
- `frontdoor_action`
  - `normal_chat / query_status / govern / background_entry / mission_ingress`
  - 当前仍保留 slash 强约束与 capability fallback，避免 `/status`、`/govern`、后台入口跟进等兼容语义被新 router 破坏
- `runtime_lane`
  - `cursor_fast` 为 chat/frontdoor 默认 lane
  - `cursor_exec` 用于一般执行、代码修改、常规排查
  - `codex_deep` 只给复杂、长程、后台或高风险任务
- `router prompt governance`
  - 短 policy overlay 写在专用治理文件，不进入主配置
  - 周期复盘默认只调小 prompt append，不做大段 prompt 膨胀

## 回归测试

- `butler_main/butler_bot_code/tests/test_talk_mainline_service.py`
  - sticky project review 行为
  - 新题重开内部 chat session
  - query / negotiation / slash status 仍按前门能力稳定进入
- `butler_main/butler_bot_code/tests/test_chat_recent_memory_runtime.py`
  - recent context 只投喂当前 `chat_session_id`
- `butler_main/butler_bot_code/tests/test_talk_runtime_service.py`
  - runtime 复用 prefilled intake，避免重复 classify
- `butler_main/butler_bot_code/tests/test_chat_router_frontdoor.py`
  - 覆盖 unified lane 编译与 background -> codex lane
- `butler_main/butler_bot_code/tests/test_chat_engine_model_controls.py`
  - 覆盖 router 选中的 Cursor lane 不再被执行层升到 Codex

## 仍保留的边界

- 本轮不做跨 thread / 全局 chat 检索。
- 本轮不把 vendor-native thread 当 Butler chat 连续性的真源。
- 本轮虽引入轻量 router model round，但 legacy route/session/intake 仍保留为 fallback 和兼容护栏。
- 当前 recent 条目总量仍按 scope 粗裁，不按 `chat_session_id` 单独配额裁剪；这是后续可优化项，不影响当前正确性口径。
- `/chat`、`/reset`、`/project phase` 这类显式 slash 切态仍由现有 mode switch 逻辑优先处理，不完全放权给模型。
