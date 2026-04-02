---
type: "note"
---
# 01 Chat 重建主线

日期：2026-03-23\
时间标签：0323_0001\
状态：进行中

## 最新进度（2026-03-23 13:45:00）

### 旧 wrapper 测试已迁到 chat 真源

1. 本轮已把最后一批直接绑在旧入口上的测试迁到 `chat` 真源：

   * `test_butler_bot_model_controls.py`
     -> `test_chat_engine_model_controls.py`
   * `test_butler_bot_streaming.py`
     -> `test_chat_engine_streaming.py`
   * `test_agent_message_flow.py`
     现改为直测：
     `butler_main.chat.feishu_bot.transport`
   * `test_agent_runtime_resilience.py`
     现改为直测：
     `butler_main.chat.feishu_bot.transport`
   * `test_chat_feishu_config_path.py`
     现改为直测：
     `butler_main.chat.feishu_bot.transport`

2. 同时，一批已经不属于纯 chat 主链的旧测试已直接废弃：

   * `test_butler_bot_upgrade_approval.py`
   * `test_explicit_heartbeat_task_protocol.py`
   * `test_decide_file_send.py`

3. 这意味着：

   * 旧 wrapper 测试已不再要求
     `agent.py`
     `butler_bot.py`
     执行 chat 真源
   * 两个根入口现在已经可以安全退化为过时 stub

### old 根入口已不再承接 chat 真源

1. 本轮已把以下文件改为过时提示 stub：

   * `butler_bot_code/butler_bot/agent.py`
   * `butler_bot_code/butler_bot/butler_bot.py`
   * `butler_bot_code/butler_bot/self_mind_bot.py`

2. 当前它们的语义已经变成：

   * 历史占位
   * 明确提示新真源位置
   * 不再把 `chat` 源码 exec 到旧命名空间里

3. 到这一步可以明确说：

   * `chat` 已经完全独立运行
   * `butler_bot_code/agent` 不再是 chat 的运行依赖
   * old code 中剩余文件即使存在，也不再拥有 chat runtime ownership

4. 本轮新增聚焦验证已通过，累计这一批共 64 个用例通过，包括：

   * `test_chat_engine_model_controls`
   * `test_chat_engine_streaming`
   * `test_agent_message_flow`
   * `test_agent_runtime_resilience`
   * `test_chat_feishu_config_path`
   * 以及上一轮纯 chat 主线验证集合

## 最新进度（2026-03-23 11:45:00）

### Chat Codex 调用修正

1. 本轮已定位到当前 `chat -> cli_runner -> codex exec` 与“手工终端直接跑 codex”之间的关键差异：

   * 当前机器上终端环境存在：
     `HTTP_PROXY / HTTPS_PROXY / ALL_PROXY`
   * `agents_os/execution/cli_runner.py`
     之前会在 `_build_codex_env()` 里无条件清掉这些继承代理
   * 因此会形成典型现象：
     手工终端 `codex` 可用
     但 Butler 子进程调用 `codex exec` 失败

2. 本轮已按工程化方式修正：

   * `cli_runtime.providers.codex`
     新增：
     `inherit_proxy_env`
     `config_overrides`
   * 当前实际运行配置
     `butler_main/butler_bot_code/configs/butler_bot.json`
     已打开：
     `inherit_proxy_env = true`
   * 这样 Codex 子进程默认不再丢失终端里的代理环境
   * 同时保留：
     `provider http_proxy/https_proxy/all_proxy/no_proxy`
     的显式覆盖能力

3. 同轮顺手补齐两个执行一致性点：

   * `provider.ephemeral=true`
     现在会真实透传成 `codex exec --ephemeral`
   * `provider.config_overrides`
     现在会和 runtime request 的 `config_overrides`
     一起进入 `codex -c ...`

4. 本轮验证结果：

   * 单测已通过：
     `test_butler_bot_model_controls`
   * 按当前真实配置解析后，Codex 子进程环境已确认会保留：
     `HTTP_PROXY / HTTPS_PROXY / ALL_PROXY / NO_PROXY`
   * 当前 Codex CLI 在本会话 sandbox 里做真实外呼时，仍可能额外受当前执行环境限制；但导致 Butler 调用与手工终端行为不一致的主因已经收口

## 最新进度（2026-03-23 11:42:00）

### Chat 与 compat 中间层已切开

1. 本轮已把 `chat -> compat -> legacy` 的过渡链收成 `chat -> legacy implementation` 单跳：

   * 新增：
     `chat/providers/legacy_runtime_bridge.py`
   * `chat/providers/butler_memory_runtime.py`
     不再引用：
     `butler_main/compat/chat_memory_legacy_runtime.py`
     `butler_main/compat/chat_control_legacy_runtime.py`
   * 上述两个 compat bridge 文件已删除

2. 这意味着当前 `chat` 包内部已经不再依赖 `butler_main/compat` 这个过渡层；
   legacy manager 虽然还在，但 bridge ownership 已经回到 `chat` 自己名下。

### old code 中大批 chat 兼容壳已移除

1. 本轮已删除 `butler_bot_code` 中一批纯 re-export 旧壳：

   * `butler_bot/adapters/*`
   * `butler_bot/chat/*`
   * `butler_bot/composition/chat_mainline_service.py`
   * `butler_bot/composition/talk_mainline_service.py`
   * `butler_bot/orchestrators/chat_router.py`
   * `butler_bot/orchestrators/talk_router.py`
   * `butler_bot/services/chat_runtime_service.py`
   * `butler_bot/services/talk_runtime_service.py`

2. 同时：

   * `services/bootstrap_loader_service.py`
     已不再 import `butler_main.chat.assets`
   * `services/message_delivery_service.py`
     已不再 import `butler_main.chat.feishu_bot`
   * `self_mind_bot.py`
     已冻结为废弃入口，不再继续承接 chat transport

3. 截至本轮，`butler_bot_code/butler_bot` 中剩余命中的 `butler_main.chat` 文本只在：

   * `agent.py`
   * `butler_bot.py`

   且这里只剩“旧入口说明文字/根入口兼容边界”。

4. 换句话说，现在仓内的状态已经变成：

   * `chat` 主线完全在 `butler_main/chat`
   * `chat` 内部不再通过 `compat` 包回接自己
   * `butler_bot_code` 里原先那批 chat 中间壳已基本清掉
   * 剩余真正的历史债集中到了两个根入口：
     `agent.py`
     `butler_bot.py`

5. 本轮新增验证已通过：

   * `test_message_delivery_service`
   * `test_runtime_module_layout`
   * 连同上一轮 chat 主线测试，共 26 个聚焦用例通过

## 最新进度（2026-03-23 11:15:00）

### Chat 纯化硬切已落地

1. 本轮已把 chat 从“多入口兼容前门”硬切成“纯 chat 单入口”：

   * `chat/routing.py`
     不再给 `self_mind/direct_branch/mission_ingress/orchestrator`
     分配 route
   * `chat/feishu_bot/input.py`
     `chat/weixi/input.py`
     不再把 `/mission` `/branch` `/self_mind`
     与旧 marker 识别成特殊入口
   * `chat/mainline.py`
     已去掉 `MissionOrchestrator` 直连执行分支

2. `chat/engine.py` 现役路径也已同步收紧：

   * 不再在 active runtime 中处理：
     `upgrade_decision`
     `runtime_control_result`
     `direct_branch_result`
     `explicit_task_result`
     `self_mind_chat`
   * 当前仅保留：
     CLI / model 解析
     标准 chat runtime 执行
     reply 后 recent / memory 持久化

3. `chat` 自己的 prompt / memory true-source 也已同步收口：

   * `chat/prompt_profile.py`
   * `chat/prompt_context.py`
   * `chat/memory_policy.py`

   现在统一只承认：

   * `chat`
   * `talk -> chat`

4. `chat` 背景服务已最小化：

   * `chat/memory_runtime/background_services.py`

   只保留：

   * recent pending recover
   * main process state loop
   * memory maintenance loop

   不再由 chat 启动：

   * `self_mind loop`
   * `self_mind listener`
   * `heartbeat watchdog`

5. 为后续废弃 old code/agent，本轮新增两份倒序执行文档：

   * `01A_Chat纯化执行表.md`
   * `01B_Chat迁出记录.md`

   它们明确了：

   * 本轮硬切执行项
   * 已迁出 active runtime 的模块
   * 旧 `code/agent` 何时可以整体过时

6. 以当前状态判断：

   * `chat` 主路径已经是“纯 chat + 对应 memory”
   * `direct_branch/orchestrator_ingress/control_runtime`
     已经退出 active runtime
   * 剩余工作不再是“chat 继续兼容这些旧职责”，而是：
     后续择机把这些冻结件继续迁往 `agents_os/orchestrator`
     或直接过时

7. 本轮聚焦验证已通过：

   * `test_chat_router_frontdoor`
   * `test_chat_feishu_input`
   * `test_chat_weixin_input`
   * `test_chat_background_services_runtime`
   * `test_talk_mainline_service`
   * `test_talk_runtime_service`
   * `test_chat_app_bootstrap`
   * `test_chat_module_exports`

## 最新进度（2026-03-23 10:25:40）

### Chat 飞书支线收口

1. 本轮已把 `chat/feishu_bot` 与当前 chat 主线接线关系重新确认并补齐真实验证：

   * `chat/app.py`
     默认 `channel="feishu"`，`ChatApp.run()` 直接走 `run_chat_feishu_bot`
   * `chat/feishu_bot/runner.py`
     已承担 chat -> feishu transport / presentation / delivery adapter 装配
   * 当前 chat 默认运行入口已经是：
     `chat_engine.run_agent -> chat runner -> chat/feishu_bot`

2. 飞书配置链路已确认可用，当前解析顺序为：

   * 优先 `butler_main/chat/configs/<name>.json`
   * fallback `butler_main/butler_bot_code/configs/<name>.json`

真实环境 preflight 已通过，当前这台机器上的实际运行配置仍是旧路径 fallback：

   * `butler_main/butler_bot_code/configs/butler_bot.json`

3. 本轮补齐了飞书发送后回读校验能力，不再只看 `send code=0`：

   * `chat/feishu_bot/api.py`
     新增：
     `get_message(message_id)`
     `list_messages(container_id, container_id_type="chat")`
   * 手工验证脚本：
     `butler_main/butler_bot_code/tests/manual/feishu_send_verify.py`

当前推荐的飞书测试闭环固定为：

   * 先发送，拿到 `message_id / chat_id`
   * 再 `get_message(message_id)` 验证单条消息存在
   * 再 `list_messages(chat_id)` 验证最近聊天记录里能查到这条消息

4. 本轮已把飞书流式回复从“只收集快照，最后发一次 final”升级成：

   * 先 reply 一张占位 `interactive` 卡
   * 流式过程中按快照节奏 PATCH 更新同一条卡
   * 结束后再 PATCH 收口成最终版本

关键实现位置：

   * `chat/feishu_bot/api.py`
     `update_raw_message()`
   * `chat/feishu_bot/replying.py`
     `create_interactive_reply()`
     `update_interactive_message()`
   * `chat/feishu_bot/transport.py`
     `handle_message_async()` 已改成：
     `placeholder -> stream update -> final update`

5. 针对飞书流式卡片，本轮已完成真实环境验证，不只是本地 mock：

   * `stream_final`
     真机验证通过
     占位卡创建成功
     3 次中间 update 成功
     1 次 final 收口 update 成功
   * `stream_snapshot`
     真机验证通过
     占位卡创建成功
     3 次中间 update 成功
     1 次 final 收口 update 成功
   * 两条最终 reply 均已通过
     `get_message + list_messages`
     回读验证

6. 本轮同时修正了一处上线前卡片兼容问题：

   * 旧 quick actions 卡片里曾使用 schema v2 当前环境下不接受的元素
   * 已改成纯 markdown 提示型 quick actions，不再触发 `interactive -> post/text` 异常回退

7. 当前飞书支线剩余边界，需明确记住：

   * 当流式占位卡启用时，最终文本收口优先 update 已有卡片，因此 `deliver_output_bundle_fn` 的文本发送会跳过
   * 当前 chat 主线实际 `OutputBundle` 主要仍是：
     `1 个 TextBlock + decide files`
     多块 rich bundle 还没有真正作为“同一张可更新卡片”来表达
   * `ImageAsset / FileAsset / residual text blocks`
     目前仍更适合在主卡 finalize 之后分开发送；尚未做成 stream card 内统一更新
   * 若最终 update 失败，当前实现会 fallback 再发一条 final reply；这种异常路径下，飞书里可能出现：
     一张停在旧版本的流式卡
     加一条新的最终消息
   * 当前并发口径应理解为：
     `one inbound turn -> one primary reply card`
     而不是“整个会话永远只用一张卡”

8. 因此，飞书这条支线当前更稳妥的工程口径是：

   * 一个 turn 强制一张主流式卡
   * 主流式卡只承载主文本状态
   * finalize 后若有图片 / 文件 / 长附加文本，再顺序补发
   * 不建议把多任务并发都强行折叠到同一张全局卡里

9. 本轮与飞书相关的新验证已通过：

   * `test_chat_feishu_api`
   * `test_chat_feishu_replying`
   * `test_agent_message_flow`
   * `python -m butler_main.chat --preflight`
   * `python butler_main/butler_bot_code/tests/manual/feishu_send_verify.py --cases direct,stream`

10. 以当前状态判断，飞书前台链路已经满足：

   * config 可解析
   * preflight 可过
   * `text / post / interactive` 真发送可用
   * reply fallback 可用
   * stream card create/update/finalize 真发送可用
   * message readback 验证链可用

剩余未收口项已经不再是“飞书链路不通”，而是：

   * `OutputBundle residual assets` 如何在 stream finalize 后做统一 delivery
   * update 失败时如何避免“旧卡 + 新 final”双版本观感
   * 是否给 stream update 增加 debounce / retry / per-turn serialization

### Chat 飞书支线可能的优化方向

1. `stream finalize + residual bundle delivery`

   * 把主流式卡与 residual assets 明确拆成两段：
     `primary text card`
     `post-finalize follow-ups`
   * 当本轮已启用 stream card 时：
     主文本继续走 `create/update/finalize`
     `ImageAsset / FileAsset / residual text blocks / doc links`
     在 finalize 后顺序补发

2. `final update retry / graceful fallback`

   * 当前最终 update 失败时，会 fallback 新发一条 final reply，可能形成：
     旧流式卡 + 新最终消息
   * 可选优化方向：
     先做有限次 retry
     retry 失败后把旧卡更新成“以下方最终消息为准”
     或把 fallback 策略改成更明确的 degrade 文案

3. `per-turn stream update debounce`

   * 当前每次新快照都会直接 PATCH 更新飞书消息
   * 后续可加入：
     最小时间间隔
     文本最小增量阈值
     末尾稳定窗口
   * 目标是减少高频 PATCH、降低乱序感、减轻飞书接口压力

4. `per-turn serialization / concurrency contract`

   * 当前更合理的长期约束应固定为：
     `one inbound turn -> one primary reply card`
   * 不建议回到“整个会话只用一张全局卡”
   * 但同一 turn 内仍可增加：
     per-turn update lock
     per-turn ordered flush
     finalize 后 residual follow-up 队列

5. `delivery adapter update-aware`

   * 当前 `FeishuDeliveryAdapter` 虽已具备 `update/finalize` plan 结构，但实际 transport callback 仍主要按 reply/push 思路执行
   * 若未来要让 `OutputBundle.cards / images / files / links`
     也参与同一轮 update-aware delivery
     需要继续把 adapter 做成：
     stream session aware
     message update aware
     residual asset policy aware

6. `manual verify -> preflight/selftest 标准化`

   * 当前已具备：
     `feishu_send_verify.py`
   * 后续可把它进一步并入统一：
     `preflight + send verify + readback verify`
     自检入口
   * 上线前最小验收可固定成：
     `text / post / interactive / stream_final / stream_snapshot`
     全部发送成功且可回读

## 最新进度（2026-03-23 10:15:22）

1. 本轮继续往下真拆，已经把 `reply persistence`、`background services`、以及 `runtime request override` 的 chat 侧遗留 wrapper 基本清空。

2. `reply persistence` 现在不再经由 `MemoryManager.on_reply_sent_async` 整块入口，而是改成：

   * `chat/memory_runtime/reply_persistence.py`
   * `agents_os/runtime/writeback.py`

其中：

   * `ChatReplyPersistenceRuntime`
     负责 chat 侧的 fallback 写回 + 异步调度组装
   * `AsyncWritebackRunner`
     负责通用 daemon thread writeback 启动

因此，compat 现在只把 legacy manager 当作底层 finalize hooks 提供者：

   * `_write_recent_completion_fallback`
   * `_finalize_recent_and_local_memory`

而不再让 `chat` 直接依赖 `on_reply_sent_async` 这个 monolithic 入口。

3. `background services` 也已经从 `manager.start_background_services()` 整块入口切成了 chat-owned runtime：

   * `chat/memory_runtime/background_services.py`

`ChatBackgroundServicesRuntime` 现在按分步 hook 启动：

   * pending recover
   * main process state
   * maintenance loop
   * self_mind loop/listener
   * heartbeat sidecar/watchdog

这意味着 `chat` 当前不再直接依赖 `MemoryManager.start_background_services()`。

4. `runtime request override` 这一条也继续收口：

   * 新增 `chat/memory_runtime/runtime_request_override.py`
   * `compat/chat_memory_legacy_runtime.py`
     已改为直接使用 `manager._runtime_request_state`

因此，`chat` 当前也不再通过 legacy wrapper 去调 `MemoryManager.get_runtime_request_override()`。

5. 随着这几条切片落地，原先 `chat/memory_runtime/legacy_components.py` 里那批旧的纯转发组件已经失去存在必要，现已整份删除。

6. 到这一轮为止，`chat` 这条 memory/runtime 迁移线上已经完成的结构变化可以概括为：

   * recent turn lifecycle -> chat owned
   * recent prompt assembly -> chat owned
   * control surface -> chat owned slices
   * reply persistence scheduling -> chat owned
   * background bootstrap assembly -> chat owned
   * runtime request override read path -> chat owned adapter + agents_os state

7. 当前 compat `chat_memory_legacy_runtime.py` 里剩余的 legacy 依赖已主要缩成：

   * `MemoryManager` 实例本身
   * `_write_recent_completion_fallback`
   * `_finalize_recent_and_local_memory`
   * 若干 background hook 的底层实现方法

也就是说，剩余的真正难点已经不再是“chat 还在直接 import 旧体系”，而是：

   * legacy manager 里底层 memory finalize 逻辑本身还没有继续往更细的 runtime contract 里切开
   * background 各 hook 虽已由 chat 组装，但底层执行动作还在 legacy manager 内

8. 本轮新增验证已通过：

   * `test_chat_reply_persistence_runtime`
   * `test_chat_background_services_runtime`
   * `test_chat_runtime_request_override_runtime`
   * `test_chat_control_runtime`
   * `test_agents_os_runtime_request_state`
   * `test_chat_app_bootstrap`
   * `test_talk_runtime_service`
   * `test_chat_orchestrator_ingress`

## 最新进度（2026-03-23 10:05:43）

1. 本轮开始按刚刚补写的分层判断继续真拆代码，已经先完成两条切片：

   * `runtime control / upgrade control surface`
   * `runtime request override`

2. `control surface` 这一块不再继续挂在 `chat/memory_runtime/` 下面，而是新建了独立的：

   * `chat/control_runtime/protocols.py`
   * `chat/control_runtime/runtime_commands.py`
   * `chat/control_runtime/upgrade.py`
   * `chat/control_runtime/self_mind_prompt.py`

3. 具体上，这轮把原来混在 `LegacyButlerChatControlSurface` 里的几件事拆成了三个独立部件：

   * `ButlerChatRuntimeControlCommands`
   * `ButlerChatUpgradeApprovalSurface`
   * `ButlerChatSelfMindPromptBuilder`

4. `ButlerChatControlProvider` 现在也不再要求单个“大控制面对象”，而是改成可按切片组合：

   * `upgrade_surface`
   * `runtime_control_handler`
   * `self_mind_prompt_builder`

这一步的结构意义是：

   * chat 前台控制口已经开始从 “memory 附属物” 变成独立 frontdoor 组件
   * `self_mind prompt`、升级审批、后台控制命令不再被迫捆在一个 legacy surface 里

5. compat bridge 也随之从单桥改成了双桥：

   * `compat/chat_memory_legacy_runtime.py`
     现在只承接 memory provider
   * 新增 `compat/chat_control_legacy_runtime.py`
     单独承接 control provider

因此，当前 `ButlerChatMemoryRuntime` 虽然名字还没改，但内部已经不再是“memory 里顺带塞 control”，而是：

   * memory bridge
   * control bridge

6. 同时，`runtime request override` 已开始按长期口径上收 `agents_os`：

   * 新增 `agents_os/runtime/runtime_request_state.py`
   * `memory_manager.get_runtime_request_override`
   * `memory_manager.runtime_request_scope`

现在都改为委托这个通用状态组件，而不是继续由 `MemoryManager` 自己维护 thread-local 细节。

7. 本轮新增验证已通过：

   * `test_chat_control_runtime`
   * `test_agents_os_runtime_request_state`
   * `test_chat_app_bootstrap`
   * `test_talk_runtime_service`
   * `test_chat_orchestrator_ingress`

8. 需要单独记录的环境问题：

   * `test_chat_recent_memory_runtime`
   * `test_chat_prompt_support_provider`
   * `test_memory_manager_maintenance`

在当前这台机器上会被 `tempfile.TemporaryDirectory()` 创建后的 Windows 目录权限异常卡住，报错集中在 `PermissionError: [WinError 5]`，表现为临时目录下创建 `butler_main/...` 路径失败。现象看起来是本机测试环境问题，不是这轮 control/runtime-request 切片引入的逻辑回归；本轮通过的非临时目录相关用例可以正常覆盖新的改动路径。

## 最新进度（2026-03-23 04:18:49）

1. 本轮先把 `chat` 剩余的 compat bridge 切片重新对齐到长期架构文档，确认“`chat` 彻底前台一号”后的准确含义，不再把这些遗留实现统称成“chat memory”。

2. 结合 [docs/concepts/外部多Agent框架调研与Butler长期架构规划_20260323.md](/C:/Users/Lenovo/Desktop/Butler/docs/concepts/%E5%A4%96%E9%83%A8%E5%A4%9AAgent%E6%A1%86%E6%9E%B6%E8%B0%83%E7%A0%94%E4%B8%8EButler%E9%95%BF%E6%9C%9F%E6%9E%B6%E6%9E%84%E8%A7%84%E5%88%92_20260323.md) 的 `6.7 memory 统一约束`、`6.8 skill/capability 长期口径`、`7.1 agents_os`、`7.2 orchestrator`、`7.3 multi_agents_os`、以及现状映射表，当前剩余四个遗留切片应理解为：

   * `runtime request override`\
     作用：给单轮执行临时覆写 `cli/model/runtime_request` 一类运行参数。\
     长期归位：`agents_os / Execution Kernel Plane`。\
     `chat` 角色：只消费最终覆写结果，不拥有这套运行时上下文机制。

   * `reply persistence`\
     作用：回复发出后的 recent turn 收尾、记忆写回、后处理与异步持久化。\
     长期归位：执行侧写回 contract 上收 `agents_os`，治理/审计相关结果回写归 `Governance / Observability Plane`；`chat` 只保留对话前台特有的投影视图与展示策略。

   * `background services`\
     作用：启动后维护线程、sidecar/watchdog、heartbeat/self_mind 等保持运行态的后台链路。\
     长期归位：控制与调度归 `orchestrator / Mission-Control Plane`，执行与恢复归 `agents_os / Execution Kernel Plane`。\
     `chat` 角色：最多只做入口启动和状态透传，不再拥有后台服务真源。

   * `runtime control / self_mind / upgrade control surface`\
     作用：前台口令识别、升级批准、后台重启、self_mind 聊天入口。\
     长期归位：批准/恢复/执行控制协议应分流到 `orchestrator + agents_os`；`chat` 只保留“把控制意图翻译成前台可交互动作”的入口面。\
     额外判断：`self_mind` 若保留为陪伴型前台人格，其 prompt 资产可继续由 `chat` 展示和组装；但其 loop/runtime/恢复机制不应继续藏在 `chat` 下。

3. 因而，“`chat` 彻底前台一号”现在可以固定为下面这个口径：

   * `chat` 是 `Product Entry / Interface Surface`

   * `chat` 是前台用户验收口

   * `chat` 负责飞书/微信/本地交互入口、前台 prompt/rendering、交付与展示

   * `chat` 可以展示 skill/capability、memory 投影、审批状态

   * `chat` 不再拥有 runtime core、后台服务、恢复执行、skill 真源

4. 这也意味着，后续迁移不是“把旧 talk 整体搬进 chat”，而是：

   * 真正前台特有的留下 `chat`

   * 真正通用执行侧的上收 `agents_os`

   * 真正任务控制/后台运行态的上收 `orchestrator`

   * 已过时、只服务旧 `butler_bot_code/agent` 的粘合层继续清空

5. 依据这个重新归位后的判断，compat bridge 后续拆迁顺序调整为：

   * 先拆 `runtime control / upgrade control surface` 中可独立的前台翻译层

   * 再拆 `reply persistence` 的写回 contract

   * 再拆 `background services` 的启动与运行态 ownership

   * 最后消掉 `compat/chat_memory_legacy_runtime.py` 这类过渡桥

## 最新进度（2026-03-23 04:12:18）

1. 本轮继续按“拆干净，但不打乱 chat 现有分层”推进，已经完成两件关键收口：

   * `orchestrator_ingress` 不再依赖旧 `services.legacy_*`

   * `chat` 包内不再直接 import `memory_manager`

2. 为此新增了 chat 自己的 mission runtime 模块：

   * `chat/mission_runtime/protocol.py`

   * `chat/mission_runtime/fs_utils.py`

   * `chat/mission_runtime/adapter.py`

   * `chat/orchestrator_ingress.py` 已切到这些 chat-owned 模块

3. 同时把 legacy memory implementation bridge 挪出了 `chat` 包本身：

   * 新增 `butler_main/compat/chat_memory_legacy_runtime.py`

   * `chat/providers/butler_memory_runtime.py` 现在只依赖 compat bridge，不再直接 import `memory_manager`

4. 这一轮最重要的阶段性结果是：

`chat`**&#x20;包内对旧体系的直接 import 已清零。**

也就是说，当前对 `butler_main/chat/` 做扫描，已经没有：

* `from memory_manager`

* `from services.*`

* `from registry.*`

* `from standards.*`

* `from execution.agent_team_executor`

* `from agent`

1. 但要诚实说明，整体 runtime 还没有完全摆脱旧实现，只是已经被压缩成包外 compat bridge：

   * `butler_main/compat/chat_memory_legacy_runtime.py` 里仍在承接 legacy `MemoryManager`

因此，下一阶段真正剩下的老实现收口点已经只剩：

* `reply persistence`

* `background services`

* `runtime control / self_mind / upgrade control surface`

1. 本轮新增验证已通过：

   * `test_chat_orchestrator_ingress`

   * `test_chat_recent_memory_runtime`

   * `test_chat_prompt_support_provider`

   * `test_talk_runtime_service`

   * `test_chat_app_bootstrap`

   * `test_chat_module_exports`

   * `test_agent_soul_prompt`

## 最新进度（2026-03-23 04:02:03）

1. 本轮继续推进 `MemoryManager` 分层重建，但明确遵守“不能打乱当前 chat 分层”的要求，因此没有改 `engine -> runtime -> provider` 外层结构，只在 `chat/memory_runtime/` 下落了新的内层实现。

2. 这轮已完成的第一批真正替换切片是：

   * `turn lifecycle`

   * `recent prompt assembly`

3. 新增：

   * `chat/memory_runtime/recent_turn_store.py`

   * `chat/memory_runtime/recent_prompt_assembler.py`

4. `ButlerChatMemoryRuntime` 已改为：

   * `begin_turn` 不再走 legacy `MemoryManager.begin_pending_turn`

   * `prepare_turn_input` 不再走 legacy `MemoryManager.prepare_user_prompt_with_recent`

   * 仍保持 `ButlerChatMemoryProvider` / `ButlerChatControlProvider` 对外 contract 不变

5. 这一步的结构意义是：

   * `chat` 已经真正拿回了前台对话 recent-turn 的最核心两件事

   * 但 `reply persistence / background services / runtime control / upgrade execution` 仍暂时由 legacy `MemoryManager` 承接

   * 因而迁移是沿着现有 provider 边界推进，而不是把 chat 主链重新搅乱

6. 到这一轮为止，`chat` 对旧体系剩余的直接代码依赖仍只有两条，但其中 `MemoryManager` 已进一步缩为“部分切片的 transitional implementation”，而不是继续掌握整段 turn lifecycle：

   * `chat/providers/butler_memory_runtime.py`\
     里的 `MemoryManager`

   * `chat/orchestrator_ingress.py`\
     里的 `legacy_heartbeat_mission_adapter / legacy_mission_protocol`

7. 本轮新增验证已通过：

   * `test_chat_recent_memory_runtime`

   * `test_talk_runtime_service`

   * `test_chat_app_bootstrap`

   * `test_chat_module_exports`

   * `test_agent_soul_prompt`

## 最新进度（2026-03-23 03:55:28）

1. 本轮按刚刚新增的“`prompt-support` 完全重建 + `MemoryManager` 分层重建”计划，已经完成第一阶段代码落地。

2. `prompt-support` 这条链本轮已经实质性去旧源化：

   * 新增 `butler_main/chat/prompt_support/skills.py`

   * 新增 `butler_main/chat/prompt_support/agent_capabilities.py`

   * 新增 `butler_main/chat/prompt_support/protocols.py`

   * 新增 `butler_main/agents_os/runtime/local_memory_index.py`

   * `chat/providers/butler_prompt_support_provider.py` 已改为直接依赖这些新模块

3. 因而 `chat/providers/butler_prompt_support_provider.py` 已不再直接依赖：

   * `registry.skill_registry`

   * `registry.agent_capability_registry`

   * `standards.protocol_registry`

   * `services.local_memory_index_service`

4. `MemoryManager` 这条线本轮没有做假性“整体搬运”，而是先建立了新的分层 runtime contract：

   * 新增 `agents_os/runtime/memory_components.py`

   * 新增 `chat/memory_runtime/legacy_components.py`

   * `ButlerChatMemoryProvider` 已改为按职责切片组合：

     * background services

     * runtime request override

     * turn lifecycle

     * prompt assembler

     * reply persistence

   * `ButlerChatControlProvider` 已改为只接 chat-specific control surface

5. 这一步的关键意义不是“MemoryManager 已经迁完”，而是：

   * 从现在开始，后续 memory 迁移将按切片替换

   * 不再允许继续往 `MemoryManager` 或其替代品里堆更多职责

   * `MemoryManager` 现在开始退化为 legacy implementation provider，而不是 chat 新真源

6. 到这一轮为止，`chat` 对旧体系剩余的直接代码依赖已经压缩到两条：

   * `chat/providers/butler_memory_runtime.py`\
     里的 `MemoryManager`

   * `chat/orchestrator_ingress.py`\
     里的 `legacy_heartbeat_mission_adapter / legacy_mission_protocol`

7. 本轮新增验证已通过：

   * `test_chat_prompt_support_provider`

   * `test_talk_runtime_service`

   * `test_chat_app_bootstrap`

   * `test_chat_module_exports`

   * `test_agent_soul_prompt`

## 最新计划（2026-03-23 03:43:55）

针对当前剩余的两块大耦合：

* `MemoryManager`

* `prompt-support`

这条主线后续不再做“继续在旧类外围多包几层”的假迁移，而按下面的重建口径执行：

1. `prompt-support` 直接完全重建：

   * `skill catalog` 从旧 `registry.skill_registry` 脱出，转为 `chat` 自己的定义读取模块

   * `agent capability catalog` 从旧 `registry.agent_capability_registry` 脱出，转为 `chat` 自己的定义读取模块

   * `protocol registry` 从旧 `standards.protocol_registry` 脱出，转为独立静态协议加载器

   * `local memory index` 不再挂在旧 `services.local_memory_index_service`，改为更通用的小型 memory index service

2. `MemoryManager` 不直接“整体搬家”，而拆成最小 runtime 职责切片：

   * background services

   * runtime request override

   * turn lifecycle

   * prompt memory assembly

   * reply persistence

   * chat-only control surface

3. 这些切片里：

   * 通用 memory runtime contract 进入 `agents_os`

   * chat-only control / self_mind / upgrade prompt 等 chat 特有控制面留在 `chat`

   * 旧 `MemoryManager` 先退化为 transitional implementation provider，而不是继续做真源

4. 这条重建路线的硬目标是：

**后续即使继续迁移，也不能再生成另一个“6000 行 MemoryManager 替代品”，而必须让每一块职责都能独立替换、独立测试、独立进&#x20;**`agents_os`**&#x20;或留在&#x20;**`chat`**。**

## 最新进度（2026-03-23 03:38:42）

1. 本轮继续往前推进，没有停在 `agent.py` compat 这一层，而是顺手把 `chat/providers/butler_runtime_executor.py -> execution/agent_team_executor.py` 这条旧 body 依赖也切掉了。

2. 这一步的做法不是把多 agent 体系正式保留在 `chat`，而是：

   * 把现有 `subagent/team` 运行逻辑内收为 `chat` 自己的 frozen compat executor

   * 同时去掉对旧 `execution.agent_team_executor` 的直连

   * 并把这条 compat 逻辑改为直接使用 `chat/pathing.py` 下的路径常量，而不是继续挂在旧 `butler_paths` / registry 组合上

3. 到这一轮为止，`chat` 主链相关剩余的旧体系耦合已经进一步缩成三类：

   * `chat/providers/butler_memory_runtime.py`\
     内部仍包着 `MemoryManager`

   * `chat/providers/butler_prompt_support_provider.py`\
     内部仍包着 `skill_registry / agent_capability_registry / protocol_registry / local_memory_index_service`

   * `chat/orchestrator_ingress.py`\
     仍冻结依赖 `legacy_heartbeat_mission_adapter / legacy_mission_protocol`

4. 这轮结果也再次支持当前主线判断：

   * `agent.py` compat 链和 `AgentTeamExecutor` compat 链，都不应该再算作 `chat` 前台主链的真实结构组成

   * 即使暂时保留 compatibility runtime，也应该先被压进 `chat` 自己的 provider / adapter 内，再等待未来统一被 `agents_os / multi-agent os` 替代

   * 也就是说，现在剩下真正需要继续判断的，已经主要是 `MemoryManager` 和 prompt-support 这两大块，而不是旧的 `agent/team` 壳

5. 本轮新增验证已通过：

   * `test_chat_runtime_executor`

   * `test_talk_runtime_service`

   * `test_chat_app_bootstrap`

   * `test_chat_module_exports`

   * `test_agent_soul_prompt`

## 最新进度（2026-03-23 03:32:42）

1. 本轮继续按“先把 `chat` 主链从旧 body 直连里拔出来，再讨论哪些真的值得上升到 `agents_os`”执行，已经把 `chat/engine.py -> agent.py` 这条历史直连切掉。

2. 为此新增了一个 chat 自己的 compat provider：

   * 新增 `butler_main/chat/providers/butler_agent_compat_provider.py`

   * 它只承接 `chat` 当前真正还需要的四个旧符号能力：

     * `CONFIG`

     * `get_config`

     * `load_config`

     * `parse_decide_reply`

3. 这一步的关键不是“又造一个中间层”，而是正式完成路线纠偏：

   * `chat` 不再直接 import `butler_bot_code.butler_bot.agent`

   * 旧 `agent.py` 现在只剩 compatibility shell 身份

   * `chat` 主链真正依赖的是 chat 自己的 `feishu transport + compat provider`

4. 到这一轮为止，`chat` 对旧 body / 旧体系的剩余耦合已经进一步压缩为 provider / compat adapter 内部耦合，而不是前台主链直连：

   * `chat/providers/butler_memory_runtime.py`\
     里仍包着 `MemoryManager`

   * `chat/providers/butler_runtime_executor.py`\
     里仍包着 `AgentTeamExecutor`

   * `chat/providers/butler_prompt_support_provider.py`\
     里仍包着 `skill_registry / agent_capability_registry / protocol_registry / local_memory_index_service`

   * `chat/orchestrator_ingress.py`\
     里仍冻结着 `legacy_heartbeat_mission_adapter / legacy_mission_protocol`

5. 这也进一步说明现在的主线判断是对的：

   * 真正该先做的是把 `chat` 前台主链收薄

   * 不是继续把旧模块原样搬进 `agents_os`

   * 只有当剩余依赖都收成 provider / adapter 后，才有资格判断哪些是 `agents_os` 的 runtime-core，哪些只是 `chat` 的产品兼容负担

6. 本轮新增验证已通过：

   * `test_chat_app_bootstrap`

   * `test_talk_runtime_service`

   * `test_agent_soul_prompt`

   * `test_chat_module_exports`

## 最新判断（2026-03-23 03:14:54）

1. `01 Chat` 仍然是当前四条主线里推进最快的一条，已经明显进入“有代码迁移、有测试回归、有结构收口”的真实施工阶段。

2. 当前最准确的阶段判断不是“chat 还在旧体系里动不了”，而是：

**chat 前台已经开始变薄，但还没有完成从历史 body 到 provider contract 的彻底脱耦。**

3. 这条线接下来最重要的路线纠偏是：

* 不再继续以“看到一个旧模块就往 `agents_os` 搬”作为主动作

* 转为优先拆：

  * provider contract

  * chat-specific prompt truth

  * memory/runtime/prompt 的边界

4. 当前主要未收口点也应明确固定为：

* `chat/prompting.py`

* `agent.py`

* `MemoryManager`

* registry / path / prompt truth 一类静态依赖

5. 因此，这条 worker 下一步的正确目标不是“继续搬家”，而是：

**先把 chat runtime 骨架彻底理顺，再决定哪些进入&#x20;**`agents_os`**、哪些留在&#x20;**`chat`**、哪些沉淀到定义层。**

## 施工问题答复（2026-03-23 03:22）

针对 [01_Chat_problem.md](./01_Chat_problem.md) 里提出的 `skill` 归位问题，这条主线的执行口径先固定如下：

1. `skill` 真源长期不直接放进 `agents_os`。

2. `skill` 长期归 `Package / Framework Definition Plane`，也就是定义层 / 冷数据层 / package 层。

3. `agents_os` 只承接 skill/package 的运行时侧：

   * capability binding

   * invocation contract

   * policy / approval / guardrail integration

   * tracing / receipt / observability

4. `chat` 只保留产品层问题：

   * 是否向用户展示某些能力

   * 如何把 capability shortlist 渲染进 prompt

   * 如何结合 chat-specific truth 使用这些定义对象

这条答复对 `01` 主线的直接含义是：

1. 当前不再把 `skill_registry` 原样上提到 `agents_os`。

2. 当前应把 `skill_registry` 视为“定义层暂存区 + chat prompt 展示适配器”的混合旧对象。

3. `01` 主线后续应优先拆开两件事：

   * skill/package 定义真源

   * chat prompt 展示逻辑

4. `agents_os` 若需要承接能力体系，也应承接的是：

   * `CapabilityPackage`

   * `CapabilityBinding`

   * `CapabilityInvocationRequest/Result/Receipt` 而不是直接继续扫描 `SKILL.md` 并输出 skills shortlist 文本。

因此，`01` 这条线关于 skill 的路线纠偏正式固定为：

**不再问“skill_registry 要不要直接搬进 agents_os”，而改问“定义层如何产出 package，runtime 层如何消费 capability，chat 层如何做展示适配”。**

结合长期规划文档，本条再补一条正式指示：

1. `skill` 进入 Butler 长期架构后，按“定义层静态资产 / package asset”维护。

2. `chat` 当前若仍需消费 skill，也应把它视为展示与适配对象，而不是 runtime 真源。

3. `01` 后续所有与 `skill_registry` 相关的施工，都应优先服务于：

   * skill 真源与 prompt 展示解耦

   * skill/package 与 capability/binding 解耦

   * 为后续 `CapabilityPackage -> CapabilityBinding -> Invocation` 主线让路

## 最新进度（2026-03-23 03:13）

1. 本轮继续拆 `chat/prompting.py`，但不是把它整体抬进 `agents_os`，而是先把其中的 chat-specific 装配部件抽回 `chat` 自己：

   * 新增 `butler_main/chat/pathing.py`

   * 新增 `butler_main/chat/bootstrap.py`

   * 新增 `butler_main/chat/dialogue_prompting.py`

2. `chat/prompting.py` 已因此切掉三条旧 body 依赖：

   * 不再直接依赖 `butler_paths`

   * 不再直接依赖 `bootstrap_loader_service`

   * 不再直接依赖 `prompt_assembly_service`

3. 同时又顺手把飞书 transport 的一条路径依赖收回了 chat：

   * `chat/feishu_bot/transport.py` 已改为使用 `chat/pathing.py`

   * 因而 `chat` 主链里的 `butler_paths` 直连，已经进一步缩到 prompt/provider 相关的剩余小块

4. 到这一轮为止，`chat` 对旧 body 的剩余依赖已经清晰压缩为四类：

   * `chat/engine.py`：`agent.py` 兼容链

   * `chat/providers/butler_memory_runtime.py`：`MemoryManager` 兼容包装

   * `chat/providers/butler_runtime_executor.py`：`AgentTeamExecutor` 兼容包装

   * `chat/prompting.py` / `chat/providers/butler_prompt_provider.py` / `chat/dialogue_prompting.py`：\
     `agent_capability_registry`、`skill_registry`、`protocol_registry`、`local_memory_index_service`

   * `chat/orchestrator_ingress.py`：\
     `legacy_heartbeat_mission_adapter`、`legacy_mission_protocol`

5. 这轮结果再次证明当前路线是对的：

   * `bootstrap`、`pathing`、`dialogue prompt assembly` 这类东西首先应该回到 `chat` 产品层自身，而不是仓促塞进 `agents_os`

   * 真正还值得继续判断是否上升的，只剩更通用的 runtime-facing contract，而不是这些 chat-specific prompt/source 装配件

6. 本轮新增验证已通过：

   * `test_agent_soul_prompt`

   * `test_talk_runtime_service`

   * `test_chat_feishu_runner`

   * `test_chat_app_bootstrap`

   * `test_chat_module_exports`

## 最新进度（2026-03-23 03:09）

1. 本轮继续按“先改 chat 运行模式，再决定模块归属”执行，已经完成一轮 runtime 收口：

   * 新增 `butler_main/chat/providers/butler_runtime_executor.py`

   * 新增 `butler_main/chat/providers/butler_memory_runtime.py`

   * `ChatRuntimeService` 已支持直接接入 `memory_provider / prompt_provider / runtime_executor`

2. 这一步的结构意义是：

   * `engine.py` 不再直接持有 `AgentTeamExecutor`

   * `engine.py` 不再直接持有 `MemoryManager`

   * `engine.py` 不再直接依赖 `skill_registry`

   * `engine.py` 当前剩余的旧 body 直连，只剩 `agent.py` 这一条历史 CLI / reply parser 兼容链

3. 当前 `chat` 对旧 body 的耦合已经从“前台主链直接耦合”缩成“少量 provider/compat adapter 内部耦合”：

   * `chat/providers/butler_memory_runtime.py` 内部仍包着 `MemoryManager`

   * `chat/providers/butler_runtime_executor.py` 内部仍包着 `AgentTeamExecutor`

   * `chat/providers/butler_prompt_provider.py` 仍包着 `skill_registry / agent_capability_registry`

   * `chat/prompting.py` 仍直接依赖 `bootstrap_loader_service / prompt_assembly_service / protocol_registry / butler_paths`

4. 这说明上一轮的判断是对的：

   * 真正该先做的不是“继续把旧模块往 `agents_os` 生搬”，而是先把 `chat` 的运行时入口变薄、把历史身体收成 provider/adapter

   * 只有收口完后，才看得清哪些是通用执行内核能力，哪些只是 chat 产品壳内的兼容包袱

5. 迁移优先级也因此更新为：

   * 第一优先：继续拆 `chat/prompting.py`，把“prompt 装配骨架”与“chat prompt truth / 本地目录扫描 / protocol 静态定义”分开

   * 第二优先：把 `agent.py` 这条剩余 reply parser / CLI 兼容链继续缩到 chat provider 内，而不是留在 `engine.py`

   * 第三优先：`legacy heartbeat mission adapter/protocol` 继续冻结，只做兼容壳，不再进入任何新主链

6. 本轮新增验证已通过：

   * `test_talk_runtime_service`

   * `test_chat_app_bootstrap`

   * `test_butler_bot_upgrade_approval`

   * `test_chat_module_exports`

## 最新进度（2026-03-23 03:03）

1. 本轮先按长期规划文档，给剩余 `chat -> old body` 依赖做了正式裁决，不再采用“看到旧模块就直接往 `agents_os` 搬”的推进方式。

2. 裁决标准明确固定为三类：

   * 只有满足“任意单 agent 入口可复用 / 不绑定 chat 或飞书产品形态 / 即使未来 chat 变薄 frontdoor 也仍成立”的能力，才允许进入 `agents_os`

   * 明显属于对话产品入口、飞书展示层、chat persona/prompt truth 的能力，留在 `chat`

   * 属于历史兼容或层次混杂、需要先改运行模式才能判断归属的，先不搬，先做 runtime 收缩

3. 按该标准，当前清单裁决如下：

   * `应进 agents_os`：\
     `RequestIntakeService`、`markdown_safety`、后续“真正通用的 prompt assembly skeleton / provider contract / runtime-facing capability visibility contract”

   * `应留 chat`：\
     `MessageDeliveryService`、`feishu transport/presentation/rendering`、chat-specific prompt truth、chat-specific memory visibility policy

   * `不应直接进 agents_os，应归更上层静态定义/目录平面`：\
     `protocol_registry`、`butler_paths`、当前基于本地目录扫描的 `skill_registry` / `agent_capability_registry`

   * `需先改 chat 运行模式再判断`：\
     `engine.py` 当前对 `agent.py` / `MemoryManager` / `AgentTeamExecutor` 的耦合，以及 `bootstrap_loader_service` / `prompt_assembly_service` 当前把“通用 prompt 装配骨架”和“chat 专属 prompt 真源”混在一起的问题

4. 按这份清单，今天已经直接执行了两项：

   * `markdown_safety` 真源已迁入 `butler_main/agents_os/runtime/markdown_safety.py`

   * `MessageDeliveryService` 真源已迁入 `butler_main/chat/feishu_bot/message_delivery.py`

5. 对应旧目录已退成兼容壳：

   * `butler_bot_code/butler_bot/utils/markdown_safety.py`

   * `butler_bot_code/butler_bot/services/message_delivery_service.py`

6. `chat` 主链上的剩余旧依赖因此再次收口：

   * `chat/engine.py`：`agent`、`AgentTeamExecutor`、`MemoryManager`、`registry.skill_registry`

   * `chat/prompting.py` 与 `chat/providers/butler_prompt_provider.py`：`agent_capability_registry`、`skill_registry`、`bootstrap_loader_service`、`prompt_assembly_service`、`protocol_registry`、`butler_paths`

   * `chat/feishu_bot/transport.py`：`butler_paths`

   * `chat/orchestrator_ingress.py`：`legacy_heartbeat_mission_adapter`、`legacy_mission_protocol`

7. 这意味着下一轮的正确动作已经不是“继续抽零件”，而是：

   * 先把 `chat` runtime 进一步变薄

   * 把 prompt/memory/runtime 的“骨架 contract”与“chat 专属 truth”分开

   * 再决定哪些继续升到 `agents_os`，哪些留在 `chat`，哪些改放到定义平面

8. 本轮新增验证已通过：

   * `test_markdown_sanitize_and_truncate`

   * `test_talk_runtime_service`

   * `test_chat_feishu_rendering`

   * `test_message_delivery_service`

   * `test_chat_feishu_runner`

   * `test_chat_app_bootstrap`

## 最新进度（2026-03-23 02:39）

1. 本轮继续沿着“能进 `agents_os` 的先通用化”再切掉一项旧 body 依赖：

   * `RequestIntakeService` 真源已迁入 `butler_main/agents_os/runtime/request_intake.py`

   * `butler_main/agents_os/runtime/__init__.py` 已直接导出 `RequestIntakeService` / `IntakeDecision`

   * `butler_bot_code/butler_bot/services/request_intake_service.py` 已退成兼容壳

   * `butler_main/chat/engine.py` 已改为直接从 `butler_main.agents_os.runtime` 导入 `RequestIntakeService`

2. 这一步的边界含义是明确的：

   * “前台分诊 / 请求规模与跟进概率判断”不再被视为 chat 私有逻辑

   * 该能力已经开始变成 `agents_os` 的单 agent 运行时配套设施，可供未来其他入口 agent 复用

3. 迁完后，`chat -> 旧 body` 剩余直接依赖再次收口：

   * `chat/engine.py`：`agent`、`AgentTeamExecutor`、`MemoryManager`、`registry.skill_registry`、`markdown_safety`

   * `chat/prompting.py` 与 `chat/providers/butler_prompt_provider.py`：`agent_capability_registry`、`skill_registry`、`bootstrap_loader_service`、`prompt_assembly_service`、`protocol_registry`、`butler_paths`

   * `chat/runtime.py` 与 `chat/feishu_bot/transport.py`：`message_delivery_service`、`markdown_safety`、`butler_paths`

   * `chat/orchestrator_ingress.py`：`legacy_heartbeat_mission_adapter`、`legacy_mission_protocol`

4. 当前判断保持不变：

   * `RequestIntakeService` 这类通用运行时前置判断，继续优先放进 `agents_os`

   * `BootstrapLoaderService` / 当前 `DialoguePromptContext` 仍混有 Butler/chat 特定 prompt 真源，不适合机械搬进 `agents_os`

   * 下一轮应优先把“真正通用的 prompt/runtime utility”与“chat 专属 prompt truth”拆开，而不是把整块 prompting 原封不动搬家

5. 本轮新增验证已通过：

   * `test_request_intake_service`

   * `test_talk_runtime_service`

   * `test_chat_app_bootstrap`

## 最新进度（2026-03-23 02:35）

1. 本轮先把 mission/orchestrator 这条真源从旧 `butler_bot_code` 主体里提到了根 `butler_main/orchestrator`：

   * 新增 `butler_main/orchestrator/mission_orchestrator.py`

   * 新增 `butler_main/orchestrator/ingress_service.py`

   * 新增 `butler_main/orchestrator/query_service.py`

   * `butler_main/orchestrator/__init__.py` 已直接导出 `ButlerMissionOrchestrator`、`OrchestratorIngressService`、`OrchestratorQueryService`

2. `chat` 前台到 mission 平面的接线已改成直连根 `orchestrator`，不再经旧 body 里的 orchestrator 真实现：

   * `butler_main/chat/mainline.py` 已改为 `from butler_main.orchestrator import ButlerMissionOrchestrator`

   * `butler_main/orchestrator/observe.py` 已改为直接使用根 `query_service`

3. 旧目录对应文件已退成兼容壳，不再承载 mission/orchestrator 真逻辑：

   * `butler_bot_code/butler_bot/orchestrators/mission_orchestrator.py`

   * `butler_bot_code/butler_bot/services/orchestrator_ingress_service.py`

   * `butler_bot_code/butler_bot/services/orchestrator_query_service.py`

4. 这一轮完成后，`chat -> 旧 body` 的一条关键主依赖已被切断：

   * `chat/mainline.py` 已不再依赖旧 `orchestrators/*`

   * mission 编排真源已明确归位到长期架构中的 `orchestrator` 平面，而不是继续挂在历史 `code` 包里

5. 当前剩余仍需继续处理的 `chat -> 旧 body` 依赖，已经收敛成四组明确清单：

   * `chat/engine.py`：`agent`、`AgentTeamExecutor`、`MemoryManager`、`RequestIntakeService`、`registry.skill_registry`、`utils.markdown_safety`

   * `chat/prompting.py` 与 `chat/providers/butler_prompt_provider.py`：`agent_capability_registry`、`skill_registry`、`bootstrap_loader_service`、`prompt_assembly_service`、`protocol_registry`、`butler_paths`

   * `chat/runtime.py` 与 `chat/feishu_bot/transport.py`：`message_delivery_service`、`markdown_safety`、`butler_paths`

   * `chat/orchestrator_ingress.py`：`legacy_heartbeat_mission_adapter`、`legacy_mission_protocol`

6. 按当前三层边界看，这四组里下一步应这样拆：

   * `request_intake / prompt_assembly / capability_registry / skill_registry / memory lifecycle / markdown presentation utility` 优先判断哪些该升到 `agents_os`

   * `message_delivery_service / butler_paths` 要判断哪些只是 chat 展示层依赖，哪些值得抽成通用 channel 基础设施

   * `legacy heartbeat mission adapter/protocol` 继续只保留兼容冻结，不再让其反向定义新的 chat/orchestrator 主链

7. 本轮新增验证已通过：

   * `test_talk_router_and_mission_orchestrator`

   * `test_talk_mainline_service`

   * `test_chat_router_frontdoor`

   * `test_orchestrator_ingress_and_template`

   * `test_chat_app_bootstrap`

   * `test_legacy_heartbeat_mission_adapter`

   * `test_chat_module_exports`

   * `python -m butler_main.chat --help`

## 最新进度（2026-03-23 02:11）

1. 本轮继续执行“把旧 `agent/code` 里的 chat 真源完全迁走”，并已完成一组关键收口：

   * `FeishuInputAdapter` 真源已迁入 `butler_main/chat/feishu_bot/input.py`

   * `FeishuDeliveryAdapter` 真源已迁入 `butler_main/chat/feishu_bot/delivery.py`

   * `TalkDirectBranchInvokeService` 真源已迁入 `butler_main/chat/direct_branch.py`

   * `ChatOrchestratorIngressService` / `TalkHeartbeatIngressService` 真源已迁入 `butler_main/chat/orchestrator_ingress.py`

2. 对应旧目录已退成兼容壳，不再承载 chat 真逻辑：

   * `butler_bot_code/butler_bot/adapters/feishu_input_adapter.py`

   * `butler_bot_code/butler_bot/adapters/feishu_delivery_adapter.py`

   * `butler_bot_code/butler_bot/services/talk_direct_branch_invoke_service.py`

   * `butler_bot_code/butler_bot/services/talk_heartbeat_ingress_service.py`

   * `butler_bot_code/butler_bot/services/chat_orchestrator_ingress_service.py`

3. `chat` 主链自身也已改成直接依赖新真源：

   * `chat/engine.py` 不再从旧 `services/*` 导入 direct branch / orchestrator ingress

   * `chat/weixi/delivery.py` 不再反向依赖旧 `feishu_delivery_adapter`

   * `chat/assets/bootstrap/TALK.md` 已修正为指向 `chat/assets/bootstrap/CHAT.md` 这个当前静态真源，而不是旧 `butler_bot_agent/bootstrap/CHAT.md`

4. 这一轮后的边界判断更清楚了：

   * 凡是前台 chat 专属输入/展示/前台入口控制，已经不应再留在旧 `agent/code`

   * 目前 `chat` 里仍直接依赖的旧目录能力，主要剩 `memory_manager`、`request_intake/prompt_assembly/bootstrap_loader`、`message_delivery_service`、`legacy mission adapter/protocol`、`markdown_safety`

   * 这些剩余项里，前两类更接近 body/runtime 或过渡基础设施，不再算“前台 chat 真源仍在旧目录”；后续是否继续抽，要按是否通用、是否属于 AgentOS 或 body 层来定

5. 对 `butler_bot_agent` 的判断也同步收紧：

   * chat 专属静态 role/bootstrap 真源已迁入 `chat/assets`

   * `butler_bot_agent` 里剩余被 chat 引用的，多数是 `skills`、`local_memory`、`agents/docs` 这类“脑子/知识/工作流事实”，不是前台 chat 产品壳本身

   * 后续若要继续从 `agent` 侧迁，只迁 chat 专属静态部分，不把长期 brain truth 生硬搬进 `chat`

6. 本轮新增验证已通过：

   * `test_chat_module_exports`

   * `test_feishu_delivery_adapter`

   * `test_chat_feishu_runner`

   * `test_talk_mainline_service`

   * `test_talk_runtime_service`

   * `test_explicit_heartbeat_task_protocol`

   * `

⠀
