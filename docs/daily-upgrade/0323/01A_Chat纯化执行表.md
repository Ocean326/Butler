---
type: "note"
---
# 01A Chat 纯化执行表

日期：2026-03-23  
时间标签：0323_1100  
状态：本轮已完成

## 目标

把 `butler_main/chat` 收敛成单一产品面：

1. 只保留纯聊天入口。
2. 只保留 chat 自己的 prompt 组装真源。
3. 只保留 chat 自己的 recent memory / reply persistence。
4. `feishu/weixin` 只作为 chat 展示与输入接口层。
5. 旧 `talk` 的控制面、编排面、分支面全部迁出 active runtime。

## 执行表

| 序号 | 执行项 | 目标文件/范围 | 处理方式 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | chat 前门单一路由化 | `butler_main/chat/routing.py` | `chat/talk` 统一落到 `chat`，不再产出 `self_mind/direct_branch/mission_ingress/orchestrator` | 已执行 |
| 2 | channel 输入适配纯化 | `chat/feishu_bot/input.py` `chat/weixi/input.py` | 停止把 `/mission` `/branch` `/self_mind` 和旧 marker 识别成特殊入口，统一归为 `chat` | 已执行 |
| 3 | mainline 去 orchestrator 分支 | `butler_main/chat/mainline.py` | 移除 `MissionOrchestrator` 直连路径，只保留 chat executor | 已执行 |
| 4 | engine 去旧控制分支 | `butler_main/chat/engine.py` | 停止在 active chat runtime 中处理 upgrade/runtime-control/direct-branch/orchestrator/self-mind chat | 已执行 |
| 5 | prompt/memory adapter 收口 | `chat/prompt_profile.py` `chat/prompt_context.py` `chat/memory_policy.py` | 只保留 `chat/talk -> chat` 归一化规则 | 已执行 |
| 6 | background services 最小化 | `chat/memory_runtime/background_services.py` | 只拉 recent recover / main process state / maintenance，不再拉 `self_mind/heartbeat` | 已执行 |
| 7 | 旧 chat 切片迁出备案 | `01B_Chat迁出记录.md` | 明确冻结件、迁出件、后续可删除条件 | 已执行 |
| 8 | 去 compat 中间层 | `chat/providers/butler_memory_runtime.py` `chat/providers/legacy_runtime_bridge.py` | compat bridge 收回 chat 自己管理，并删除 `butler_main/compat` 对应桥文件 | 已执行 |
| 9 | old code re-export 壳清理 | `butler_bot_code/butler_bot/adapters` `chat` `composition` `orchestrators` `services` | 删除无引用 chat 兼容壳，保留根入口历史边界 | 已执行 |
| 10 | 根入口改为过时 stub | `butler_bot_code/butler_bot/agent.py` `butler_bot.py` `self_mind_bot.py` | 停止执行 chat 真源，只保留过时提示 | 已执行 |
| 11 | 旧 wrapper 测试迁移/废弃 | `butler_main/butler_bot_code/tests` | 将有价值覆盖迁到 `chat` 真源，删除纯旧链路测试 | 已执行 |
| 12 | 聚焦验证 | chat 相关单测 | 验证纯 chat 主线可运行 | 已执行 |

## 本轮验证

已通过：

1. `test_chat_router_frontdoor`
2. `test_chat_feishu_input`
3. `test_chat_weixin_input`
4. `test_chat_background_services_runtime`
5. `test_talk_mainline_service`
6. `test_talk_runtime_service`
7. `test_chat_app_bootstrap`
8. `test_chat_module_exports`
9. `test_message_delivery_service`
10. `test_runtime_module_layout`
11. `test_chat_engine_model_controls`
12. `test_chat_engine_streaming`
13. `test_agent_message_flow`
14. `test_agent_runtime_resilience`
15. `test_chat_feishu_config_path`

## 冻结原则

1. `direct_branch`、`orchestrator_ingress`、`control_runtime` 暂不继续接入 chat active runtime。
2. 相关文件先保留为迁出记录与兼容壳参考，不再作为 `chat` 正向能力扩展点。
3. 若后续升级到 `agents_os` / `orchestrator`，必须以通用运行时接口重新接入，不能再回挂 `chat` 前门。
