---
type: "note"
---
# 01B Chat 迁出记录

日期：2026-03-23  
时间标签：0323_1105  
状态：生效中

## 保留在 Chat 的职责

1. 单 agent 聊天入口与主执行链。
2. chat 自身 prompt 组装真源与 profile。
3. chat recent memory 注入。
4. chat reply persistence / writeback。
5. `feishu`、`weixin` 输入与展示接口层。

## 已迁出 active runtime 的内容

| 模块/能力 | 当前位置 | 结论 | 说明 |
| --- | --- | --- | --- |
| `direct_branch` | `butler_main/chat/direct_branch.py` | 冻结 | 不再由 chat router / input / engine 主动进入 |
| `orchestrator_ingress` | `butler_main/chat/orchestrator_ingress.py` | 冻结 | 编排入口不再走 chat 前门 |
| `control_runtime` | `butler_main/chat/control_runtime/` | 冻结 | upgrade/runtime control/self_mind prompt 不再是 chat active path |
| `MissionOrchestrator` 直连 | `butler_main/chat/mainline.py` 旧逻辑 | 已迁出 | chat mainline 不再直连 orchestrator |
| `self_mind chat` 特殊通道 | `butler_main/chat/engine.py` 旧逻辑 | 已迁出 | 纯 chat 不再承载 self-mind 独立入口 |
| `heartbeat/self_mind` 后台拉起 | `chat/memory_runtime/background_services.py` 旧逻辑 | 已迁出 | chat 启动只保留 memory 所需最小后台项 |

## 对旧体系的影响

1. `butler_bot_code/agent` 不应再继续把上述能力视为 chat 真源。
2. 旧 `talk` 语义只保留兼容别名，语义等同于 `chat`。
3. 旧 `heartbeat/orchestrator/direct_branch/self_mind` 相关入口即使文件仍在，也已不是 chat 正常运行路径。

## 已移除的兼容壳

1. `butler_main/compat/chat_memory_legacy_runtime.py`
2. `butler_main/compat/chat_control_legacy_runtime.py`
3. `butler_bot_code/butler_bot/adapters/*` 下 chat re-export 壳
4. `butler_bot_code/butler_bot/chat/*` 下 chat re-export 壳
5. `butler_bot_code/butler_bot/composition/chat_mainline_service.py`
6. `butler_bot_code/butler_bot/composition/talk_mainline_service.py`
7. `butler_bot_code/butler_bot/orchestrators/chat_router.py`
8. `butler_bot_code/butler_bot/orchestrators/talk_router.py`
9. `butler_bot_code/butler_bot/services/chat_runtime_service.py`
10. `butler_bot_code/butler_bot/services/talk_runtime_service.py`

这些文件删除后，`chat` 主线不再通过 compat 包或 old code 中间壳回接自己。

## 当前剩余历史债

1. `butler_bot_code/butler_bot/agent.py`
2. `butler_bot_code/butler_bot/butler_bot.py`

这两个根入口本轮已不再执行 chat 真源，只保留过时提示 stub。

3. `self_mind_bot.py`

已冻结成废弃入口，不再继续承接 chat/feishu transport。

## 已迁走或废弃的旧测试

1. `test_butler_bot_model_controls.py`
   已迁为 `test_chat_engine_model_controls.py`
2. `test_butler_bot_streaming.py`
   已迁为 `test_chat_engine_streaming.py`
3. `test_agent_message_flow.py`
   已改为直测 `chat.feishu_bot.transport`
4. `test_agent_runtime_resilience.py`
   已改为直测 `chat.feishu_bot.transport`
5. `test_chat_feishu_config_path.py`
   已改为直测 `chat.feishu_bot.transport`
6. `test_butler_bot_upgrade_approval.py`
   已删除，因 upgrade approval 已不属纯 chat 主链
7. `test_explicit_heartbeat_task_protocol.py`
   已删除，因 heartbeat/orchestrator ingress 已不属纯 chat 主链
8. `test_decide_file_send.py`
   已删除，因其为旧自测型脚本且依赖旧 agent 入口

## 后续可直接过时的判据

满足以下条件后，可把旧 `code/agent` 中对应 chat 旧源整体标记过时：

1. `chat` 入口、运行、memory、展示都只从 `butler_main/chat` 取源。
2. `butler_bot_code/agent` 中不再有 chat 主线逻辑，只剩兼容导出或历史冻结件。
3. 旧控制面能力已在 `agents_os` / `orchestrator` 找到新宿主，或明确废弃。

## 备注

这份记录的作用不是保留旧设计，而是明确：

1. 什么已经不属于 chat。
2. 什么只是暂留文件，不再接主链。
3. 之后废弃 old code/agent 时，可直接按这里核对。
