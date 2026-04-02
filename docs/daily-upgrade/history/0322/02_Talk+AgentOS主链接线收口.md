---
type: "note"
---
# 02 Talk + AgentOS 主链接线收口

日期：2026-03-22\
时间标签：0322_0046\
状态：已完成（普通 chat -> feishu 主链已闭环；整体 chat 迁移仍在继续）

## 最新进度（2026-03-23 01:55）

1. 本轮开始明确收缩旧 `talk` 设计债：在 `butler_main/chat` 主链内部，前台普通对话的**标准路由名**已从 `talk` 统一为 `chat`；`talk` 现在只作为兼容入口别名继续被接受，不再作为新主语义。

2. 已完成统一的位置包括：

   * `chat/routing.py`：`chat|talk -> chat`，普通前台路径产出的 route / agent_id / profile_id 均已落到 `butler.chat`
   * `chat/mainline.py`：本地默认 `entrypoint` 保持 `chat`
   * `chat/feishu_bot/transport.py`、`chat/weixi/input.py`、旧 `adapters/feishu_input_adapter.py`：默认入口提示已切到 `chat`
   * `chat/prompting.py`：bootstrap 装配已按 `chat` 会话加载，不再把 `talk` 当内部主名

3. 与此同时，兼容边界仍保留但已降级：

   * `talk` 入口仍可进入普通 chat 主链
   * `BootstrapLoaderService` 仍接受 `talk` / `chat` 两种 session 名，但内部统一视作 `chat`
   * `ButlerPromptProfileAdapter` / `ButlerPromptContextAdapter` / `ButlerMemoryPolicyAdapter` 现已改成 `talk -> chat` 归一化；对外 contract 继续稳定，但新真源不再落到 `talk`

4. 这一步的意义是：以后 `chat` 包内部不再继续复制一套 “新代码还是 chat、核心 route 却叫 talk” 的双命名；旧 `talk` 只在兼容层和历史 runtime/memory 数据里保留，避免继续把设计债带入 AgentOS 抽象。

5. 本轮新增验证已通过：

   * `test_chat_router_frontdoor`
   * `test_chat_weixin_input`
   * `test_talk_mainline_service`
   * `test_talk_runtime_service`
   * `test_talk_router_and_mission_orchestrator`
   * `test_chat_app_bootstrap`
   * `test_chat_feishu_runner`
   * `test_chat_module_exports`
   * `test_butler_bot_model_controls`
   * `test_butler_bot_streaming`
   * `test_butler_bot_upgrade_approval`
   * `test_explicit_heartbeat_task_protocol`
   * `test_agent_message_flow`
   * `test_agent_soul_prompt`
   * `python -m butler_main.chat --help`

6. 当前剩余原则不变：

   * 能通用的 runtime / provider / state contract，继续抽到 `agents_os`
   * `talk` 冗余命名、前台接线和 Butler 过渡逻辑，不再继续保留设计上的“等价双轨”，而是直接向 `chat` 真源收口
   * `memory_manager.py` 里的通用 lifecycle 仍是下一阶段重点

## 最新进度（2026-03-23 01:47）

1. `Phase 5` 已完成第一轮 memory/runtime 分层收口，边界如下：

   * `butler_main/agents_os/runtime/turn_state.py` 新增 `ThreadLocalStateStore` / `ContextStateSnapshot`，承接**通用**的 per-turn 线程态存储，不含任何 Butler/chat 语义
   * `butler_main/chat/providers/butler_memory_provider.py` 继续作为 chat 对记忆生命周期的接入层
   * `butler_main/chat/providers/butler_chat_control_provider.py` 新增 chat 专属控制适配，承接 upgrade approval / runtime control / self_mind prompt 这类暂时仍属 Butler/chat 语义的能力

2. `butler_main/chat/engine.py` 已切到新分层：

   * `TURN_CONTEXT` 兼容出口仍保留，但其底层已改为 `agents_os.runtime.ThreadLocalStateStore`
   * `MEMORY` 兼容出口仍保留，但 engine 内部对 memory 的调用已区分为 `memory lifecycle` 与 `chat control`
   * `run_agent` / `post-reply writeback` / `startup background service` 不再直接散落调用多处 `MemoryManager` 细节

3. 本轮同时补了一处包级兼容修复：`butler_main/chat/__init__.py` 改为**惰性导出**，避免 `import butler_main.chat.assets` 时被 `app/prompting` 提前拉起，消除 `BootstrapLoaderService <-> chat.prompting` 的循环依赖。

4. 这意味着当前已经明确了一条可持续边界：

   * 进入 `agents_os` 的，只能是可复用 runtime/state/provider contract
   * 留在 `chat` 的，是 chat 产品层自己的控制流、兼容壳、Feishu 展示/接线与 Butler 过渡适配
   * `memory_manager.py` 仍是底层 Butler 真实现，但 `chat engine` 到它之间已经不再是裸直连

5. 本轮新增验证已通过：

   * `test_chat_app_bootstrap`
   * `test_butler_bot_model_controls`
   * `test_butler_bot_streaming`
   * `test_butler_bot_upgrade_approval`
   * `test_explicit_heartbeat_task_protocol`
   * `test_agent_message_flow`
   * `test_chat_feishu_runner`
   * `test_chat_module_exports`
   * `test_agent_soul_prompt`
   * `test_talk_mainline_service`
   * `test_talk_runtime_service`
   * `python -m butler_main.chat --help`

6. 当前下一步缺口也更清楚了：

   * `memory_manager.py` 里与 recent/memory writeback 相关的**通用生命周期能力**，后续还应继续向 `agents_os.runtime.memory` 抽象
   * `self_mind / upgrade governance / runtime control` 目前仍是 Butler/chat 过渡能力，短期应继续留在 `chat` adapter 层，不应过早放进 `agents_os`
   * `butler_bot_code` / `butler_bot_agent` 里仍有部分 chat 兼容壳与旧真源待继续清点，目标仍是最终整体过时化

## 最新进度（2026-03-23 01:35）

1. `Phase 4` 已开始第一轮真迁移：`butler_main/chat/assets/` 已建立，并已承接 chat 专属静态模板真源：

   * `chat/assets/roles/chat-feishu-bot-agent.md`
   * `chat/assets/bootstrap/CHAT.md`
   * `chat/assets/bootstrap/TALK.md`
   * `chat/assets/bootstrap/SOUL.md`
   * `chat/assets/bootstrap/USER.md`
   * `chat/assets/bootstrap/TOOLS.md`
   * `chat/assets/bootstrap/MEMORY_POLICY.md`

2. `chat.prompting` 已改为直接引用 `./butler_main/chat/assets/roles/chat-feishu-bot-agent.md`；普通 talk prompt 的 role 展示路径已经不再回指 `butler_bot_agent/agents/chat-feishu-bot-agent.md`。

3. `BootstrapLoaderService` 已改成：对 `talk` 会话优先读取 `chat/assets/bootstrap/*`，旧 `butler_bot_agent/bootstrap/*` 仅作为兼容 fallback。

4. 本轮明确了资产边界：当前迁入 `chat/assets` 的只应是 chat 专属**静态资产**；以下内容仍视为运行态或动态真源，暂不迁入 `chat/assets`：

   * `butler_bot_agent/agents/local_memory/*`
   * `Current_User_Profile.private.md`
   * `Butler_SOUL.md`
   * `self_mind/current_context.md`
   * `agents/state/*`
   * `task_workspaces/*`

5. 本轮新增验证已通过：

   * `test_agent_soul_prompt`
   * `test_chat_app_bootstrap`
   * `test_talk_mainline_service`
   * `test_talk_runtime_service`
   * `test_chat_feishu_runner`
   * `test_agent_message_flow`
   * `test_chat_module_exports`
   * `python -m butler_main.chat --help`

6. 当前剩余缺口进一步收敛：

   * `chat/assets` 还只覆盖了 talk/chat 侧静态模板，`update-agent` 等复用型资产暂未迁，后续应结合 `Phase 6` 的 catalog/平台归属一起判断
   * `Phase 5` 尚未启动：`memory_manager.py` 仍是记忆真源，`chat` 只是 engine/provider 接入，尚未完成 memory 分层

## 最新进度（2026-03-23 01:25）

1. `Phase 2` 已完成主切换：`butler_main/chat/engine.py` 已成为 `run_agent`、`MEMORY`、`TURN_CONTEXT`、runtime control、post-reply writeback 的代码真源。

2. `chat.app` 已不再依赖 `butler_bot_code/butler_bot/butler_bot.py`：

   * `create_default_chat_app()` 现在直接装配 `chat_engine.run_agent`
   * `ButlerChatMemoryProvider` 现在直接包裹 `chat_engine.MEMORY`
   * reply 持久化 callback 现在直接挂 `chat_engine._after_reply_persist_memory_async`

3. 旧 `butler_bot.py` 已退成兼容壳，方式与 `agent.py` 一致：执行 `chat.engine` 真源到旧模块命名空间，继续兼容旧测试、旧 monkeypatch 与旧导入路径。

4. 这意味着 `Phase 2` 的关键验收已成立：

   * `chat.app` 不再依赖 `body_chat.run_agent`
   * `chat.app` 不再依赖 `body_chat.MEMORY`
   * `butler_bot.py` 不再承载 chat engine 真实现

5. 本轮新增验证与回归已通过：

   * `test_chat_app_bootstrap`
   * `test_butler_bot_model_controls`
   * `test_butler_bot_streaming`
   * `test_butler_bot_upgrade_approval`
   * `test_explicit_heartbeat_task_protocol`
   * `test_chat_feishu_runner`
   * `test_agent_message_flow`
   * `test_talk_mainline_service`
   * `test_talk_runtime_service`
   * `test_talk_router_and_mission_orchestrator`
   * `python -m butler_main.chat --help`

6. 当前剩余主缺口已前移到后续阶段：

   * `Phase 3` 现已基本完成主实现回迁，但仍需继续清点旧目录兼容壳是否还能再收
   * `Phase 4` 仍未做：`butler_bot_agent` 中 chat 专属静态资产尚未系统迁入 `butler_main/chat/assets`
   * `Phase 5` 仍未做：`memory_manager.py` 仍是 Butler 记忆真源，`chat` 只是通过 provider/engine 接入，尚未完成 memory 分层

## 最新进度（2026-03-22 23:44）

1. `Phase 0` 已完成第一轮硬切：`chat/weixi/input.py` 与 `chat/routing.py` 已不再识别 `talk_heartbeat_mission_json` 或 `heartbeat` 前台 hint；前台 chat 入口只再接受 `mission/orchestrator` 语义。

2. `Phase 1` 已完成真迁移：`butler_main/chat/feishu_bot/transport.py` 已承接原 `agent.py` 的 Feishu transport/message loop/helper 真源；`chat.feishu_bot.runner` 与 `self_mind_bot.py` 已直接依赖新 transport。

3. 旧 `butler_bot_code/butler_bot/agent.py` 已退成兼容壳，但兼容方式不是简单 re-export，而是执行新 transport 源到旧模块命名空间，确保旧 monkeypatch/test 语义不被破坏。

4. 为了继续收旧引用，`chat/mainline.py`、`chat/runtime.py`、`chat/routing.py` 也已承接真实现；原 `composition/chat_mainline_service.py`、`services/chat_runtime_service.py`、`orchestrators/chat_router.py` 已退成兼容转发壳。这意味着 chat 主链的 front-door/runtime/router 真源已回到 `butler_main/chat`。

5. 本轮新增并通过的边界验证包括：

   * `test_chat_weixin_input`

   * `test_chat_router_frontdoor`

   * `test_agent_message_flow`

   * `test_agent_runtime_resilience`

   * `test_chat_feishu_runner`

   * `test_chat_app_bootstrap`

   * `test_chat_module_exports`

   * `test_feishu_delivery_adapter`

   * `test_chat_feishu_rendering`

   * `test_chat_feishu_presentation`

   * `test_talk_mainline_service`

   * `test_talk_runtime_service`

   * `test_talk_router_and_mission_orchestrator`

   * `test_chat_weixin_official`

   * `python -m butler_main.chat --help`

6. 该条目中的 `Phase 2 未完成` 状态已失效，仅保留作 2026-03-22 当晚历史记录。

## 文档维护规则

1. 从本条开始，`02` 文档改为**倒序维护**：最新进度、最新计划、最新结论放在最上面。

2. `追加记录` 以后只允许在顶部插入新条目，不再按时间正序续写。

3. 计划区优先维护“下一阶段要做什么”，而不是只保留历史上的“今日计划”。

## 审阅结论（2026-03-22 23:20）

1. 本页现已确认采用更激进的主线：`heartbeat` 对前台 `chat` 主链**完全屏蔽**，不再保留“legacy-compatible, no new feature”这一执行口径。

2. 后续 worker 不再以“守着旧入口继续缝补”为目标，而是以“把 `agent.py` / `butler_bot.py` / `butler_bot_agent` 中的 chat 相关真实现整体迁出”为目标。

3. 本页中早于 `2026-03-22 22:45` 的“先建壳、延后搬实现、heartbeat 仅保留 legacy-compatible”口径，统一视为**历史判断**，不再作为后续执行基线。

## 最新计划（2026-03-22 22:45）

### 总目标

1. 把 `chat` 变成 Butler 前台对话产品的唯一真源：代码真源、装配真源、channel 真源都回到 `butler_main/chat`。

2. `butler_bot_code` 与 `butler_bot_agent` 不再承载 chat 主实现，只保留短期兼容壳，最终整体移入 `obsolete`。

3. 迁移原则不是把所有东西都塞进 `chat`：

   * 可复用合同 / provider / runtime 底座优先进入 `agents_os`

   * 用户画像 / local_memory / self_mind / task ledger / 运行日志 等动态事实继续留在 workspace/runtime

   * 迁的是 chat 的代码真源、静态资产真源、装配真源

### 强约束

1. `heartbeat` 从本轮开始对 `chat` 主链完全屏蔽：

   * 不再作为前台入口

   * 不再承担 chat 路由、chat 调度、chat 回传

   * 不再接受任何“先挂回 heartbeat 再说”的临时补丁

2. `agent.py`、`butler_bot.py`、`butler_bot_agent` 从现在开始禁止新增 chat 真实现：

   * 允许兼容壳

   * 允许迁移期 adapter

   * 不允许把新的 chat 逻辑继续写回旧目录

3. 后续 worker 一律以“切断旧引用”为验收方向，而不是以“保住旧入口也能跑”为验收方向。

4. `chat/weixi/` 当前仅保留 namespace 与入口壳；在 Feishu 主链彻底迁完前，不继续投入真实微信 transport。

### 主线优先级

1. `P0`：切断 `heartbeat -> chat` 前台链路，冻结旧入口。

2. `P1`：把 `agent.py` 中仍存活的 Feishu chat transport / helper 真迁出。

3. `P2`：把 `butler_bot.py` 中 chat engine、turn context、runtime control 真迁出。

4. `P3`：把 `butler_bot_agent` 中 chat 专属静态真源迁到 `butler_main/chat/assets`，并补归属矩阵。

### 迁移分期

1. `Phase 0: heartbeat 硬屏蔽`

   * 前台 `chat` 主链不再读取 heartbeat 入口语义，不再为 heartbeat 保留新兼容分支

   * 旧 heartbeat 相关 chat 入口统一冻结，只保留历史对照与必要的兼容壳

   * 验收标准：新增 chat 改动不再触碰 heartbeat 主循环、heartbeat ingress、heartbeat 前台语义

2. `Phase 1: feishu transport 真迁移`

   * 把 `agent.py` 中长连接 loop、消息解析、reply/push/upload/download、card action dispatch、`handle_message_async`、`run_feishu_bot*` 抽成中性 transport 层

   * `chat.feishu_bot.runner` 改为直接依赖新 transport，不再依赖 `agent.py`

   * `self_mind_bot.py` 同步切到新 transport

   * 验收标准：chat 主链不再 import `agent.py`

3. `Phase 2: chat engine 真迁移`

   * 把 `butler_bot.py` 中 `run_agent`、turn context、bundle/session 管理、chat runtime control、orchestrator ingress 接入迁入 `chat`

   * `chat.app` 直接装配 chat 自己的 engine，不再依赖 `body_chat.run_agent`

   * `butler_bot.py` 退成兼容入口壳

4. `Phase 3: chat runtime 真迁移`

   * 把 `mainline / runtime / routing` 的真实现从 `butler_bot_code` 物理迁入 `butler_main/chat`

   * `butler_bot_code/butler_bot/chat/*` 退成兼容转发壳

   * 验收标准：`butler_main/chat/*.py` 不再回指 `butler_bot_code/butler_bot/chat/*`

5. `Phase 4: chat 静态资产真源迁移`

   * 把 chat 专属 bootstrap / role / prompt blocks / channel assets 从 `butler_bot_agent` 迁入 `butler_main/chat/assets`

   * `butler_bot_agent` 不再保存 chat 专属静态真源

   * 运行数据与长期记忆内容不迁，继续留 workspace

6. `Phase 5: memory 真迁移`

   * `agents_os` 继续承接 memory contracts / provider interfaces / policy

   * `chat` 接管 Butler chat 专属 memory orchestration

   * `memory_manager.py` 逐步拆成通用 adapter/provider + chat 兼容壳 + heartbeat/self_mind 专属部分

   * 验收标准：`ChatApp` 不再依赖 `body_chat.MEMORY`

7. `Phase 6: registry / catalog 分层`

   * `skills / sub-agents / teams / public-library` 中凡是未来多 agent 复用的，迁入平台 catalog（优先 `agents_os` 或独立 `agents_library`）

   * `chat` 只保留 Butler chat 的选择规则与接入层，不再把 `butler_bot_agent` 当平台资产根目录

8. `Phase 7: 旧目录冻结并整体过时`

   * 冻结 `butler_bot_code/butler_bot/agent.py`、`butler_bot.py`、`chat/*`、`composition/chat_mainline_service.py`

   * 冻结 `butler_bot_agent` 中 chat 专属 assets

   * 在全部引用切断后整体迁入 `obsolete`

### 最终完成判据

1. `butler_main/chat` 不再 import `butler_bot_code/butler_bot` 的 chat 真实现。

2. `chat.app` 不再依赖 `body_chat.run_agent` 与 `body_chat.MEMORY`。

3. `chat.feishu_bot.runner` 不再依赖 `agent.py`。

4. `butler_bot.py` 与 `agent.py` 只剩兼容壳。

5. `butler_bot_agent` 不再保存 chat 专属静态真源。

6. `python -m butler_main.chat` 可独立跑通。

7. 旧 reply/file fallback 不再参与普通 chat 生产主链，只保留显式兼容开关。

8. 旧目录移走后，chat 主链测试仍全绿。

### 执行顺序

1. 先做 `Phase 0`

2. 再做 `Phase 1`

3. 再做 `Phase 2`

4. 再做 `Phase 3`

5. 然后做 `Phase 4-6`

6. 最后做 `Phase 7`

原因：必须先把 heartbeat 与旧入口屏蔽掉，再迁 transport 和 engine，最后做资产与 catalog；否则 worker 会不断把新逻辑补回旧体系。

### Worker 切包

1. `Worker A: Feishu transport`

   * 负责 `agent.py -> chat/feishu_bot` 的 transport/helper 迁移

   * 目标文件：`butler_main/chat/feishu_bot/*`

   * 禁止回写新的 chat 逻辑到 `agent.py`

2. `Worker B: Chat engine`

   * 负责 `butler_bot.py -> butler_main/chat` 的 engine/turn/runtime control 迁移

   * 目标文件：`butler_main/chat/app.py`、`mainline.py`、`runtime.py`、`routing.py`

   * 禁止在 `butler_bot.py` 继续扩实现

3. `Worker C: Assets/bootstrap`

   * 负责 `butler_bot_agent` 中 chat 专属静态资产迁移与归属矩阵

   * 目标目录：`butler_main/chat/assets/`

   * 禁止把运行态数据搬进 `chat/assets`

4. `Worker D: Memory split`

   * 负责 `memory_manager.py` 的 chat 侧拆分方案与 adapter/provider 落点

   * 优先产出接口和切割点，不要求一轮重写完全部 memory

5. `Worker E: Cleanup/test`

   * 负责兼容壳收缩、引用切断、测试补齐

   * 以“移除旧引用”而不是“保住旧 fallback”作为验收口径

## 最新进度（2026-03-22 22:42）

1. `chat.prompting` 已正式落地：`build_feishu_agent_prompt()`、mode 判定、Soul / profile / self_mind / skills / agent capabilities 组装，已从 `butler_bot_code/butler_bot/agent.py` 迁出到 `butler_main/chat/prompting.py`。

2. `chat/providers/butler_prompt_provider.py` 与 `butler_bot.py` 已改为直接依赖 `chat.prompting`；`butler_bot.py` 通过 `set_config_provider(get_config)` 把 body 配置注入到 chat prompt 层，不再反向从 `agent.py` 取 prompt 构造。

3. `butler_bot_code/butler_bot/agent.py` 已完成一轮去 chat 化：

   * 已删除 chat prompt 组装逻辑

   * 已删除 chat delivery adapter / presentation 依赖

   * 已删除对 `butler_main.chat.feishu_bot` 的 import

   * 当前只保留通用 Feishu transport / message loop / reply helper 能力

4. `chat/feishu_bot/runner.py` 已从“单纯转发到 `agent.run_feishu_bot*`”升级为真正的 chat 侧装配层：

   * chat bundle delivery 已迁到 `deliver_chat_turn_output_bundle()`

   * `agent.py` 通过 `deliver_output_bundle_fn` 接受外置 delivery hook

   * 这意味着 chat 专属输出链已不再定义在 `agent.py` 里

5. 测试边界已同步重排：

   * `test_agent_soul_prompt` 改为直接测 `chat.prompting`

   * `test_agent_message_flow` 只保留通用消息层 / callback hook 行为

   * 新增 `test_chat_feishu_runner` 负责验证 chat bundle delivery

6. 当前状态需要明确区分：

   * `agent.py` 已不再涉及 chat 语义与 chat 组装

   * 但 `chat` 仍临时复用 `agent.py` 中的通用 Feishu transport/helper

   * 所以“chat 不再写在 agent.py 里”已成立；“chat 与 butler_bot_code 完全物理脱离”还差最后一层 transport 下沉或外提

7. 本轮验证已通过：`py_compile`、`test_agent_soul_prompt`、`test_agent_message_flow`、`test_chat_feishu_runner`、`test_chat_feishu_presentation`、`test_chat_feishu_rendering`、`test_chat_app_bootstrap`、`test_chat_module_exports`、`test_feishu_delivery_adapter`、`test_talk_mainline_service`、`test_talk_runtime_service`、`test_talk_router_and_mission_orchestrator`、`python -m butler_main.chat --help`。

## 最新进度（2026-03-22 22:xx）

1. `chat/weixi/` 已正式开一路，作为 `chat` 下与 `feishu_bot` 并列的微信接口层。

2. 本轮已补：

   * `chat/weixi/input.py`

   * `chat/weixi/delivery.py`

   * `chat/weixi/official.py`

   * `chat/weixi/runner.py`

   * `chat/weixi/__init__.py`

   * `chat/weixi/__main__.py`

   * `chat/weixi/README.md`

3. `weixi runner` 已按腾讯官方安装包链路收口，支持直接执行：

   * `npx -y @tencent-weixin/openclaw-weixin-cli@latest install`

   * `openclaw plugins install "@tencent-weixin/openclaw-weixin"`

   * `openclaw config set plugins.entries.openclaw-weixin.enabled true`

   * `openclaw channels login --channel openclaw-weixin`

   * `openclaw gateway restart`

   * `openclaw config set agents.mode per-channel-per-peer`

4. `chat.app` 已补到可程序化生成 `weixi` 这一路 bootstrap；同时也新增了 `python -m butler_main.chat.weixi` 入口，专门承接这条官方安装/登录命令链。

5. 当前完成的是“官方安装/登录命令链 + 微信 namespace + adapter 壳 + runner 真入口”；当前未完成的仍是：真实微信消息 transport、Butler runtime 实桥接、以及 OpenClaw 微信 channel 事件到 Butler 的会话映射。

## 最新进度（2026-03-22 18:53）

1. `chat.app` 独立 bootstrap 仍保持成立：`butler_main/chat/__main__.py` 走 `chat.app.main()`，旧 `butler_bot.py` 的 `main()` 继续只做桥接壳。

2. prompt / memory 分层保持在 provider 化阶段：`agents_os/runtime/provider_interfaces.py` + `chat/providers/` 已在位，但真实 prompt/memory 事实层仍主要在 body。

3. `chat/feishu_bot` 已继续从 presentation facade 推进到 rendering 真抽层：新增 `chat/feishu_bot/rendering.py`，`interactive card / post / quick actions` 渲染已不再只定义在 body `agent.py`。

4. `agent.py` 里的 delivery adapter 仍经由 `ChatFeishuPresentationService` 构造，且 card/post 渲染已经改成调用 `chat/feishu_bot` 的 rendering 模块；这意味着飞书展示层已经开始同时抽 transport facade 和 rendering 逻辑。

5. 当前还没抽完的 Feishu 事实层主要剩：event dispatch、reply helper、message loop、部分文件/图片发送 helper，仍在 body `agent.py`。

6. 本轮新增验证已通过：`test_chat_feishu_rendering`，以及回归 `test_chat_feishu_presentation`、`test_chat_module_exports`、`test_chat_app_bootstrap`、`test_feishu_delivery_adapter`、`test_agent_message_flow`、`python -m butler_main.chat --help`。

## 主线

1. 今天只接受一种改动：能直接帮助跑通 `FeishuInputAdapter -> TalkRouter -> AgentRuntime -> OutputBundle -> FeishuDeliveryAdapter` 的普通 `talk` 黄金路径。

2. `Phase 1 ready` 和 `Phase 4 adapter-ready` 不代表结束；今天要把“骨架 ready”真正收成“主链可跑”。

3. 在普通 `talk` 新主链未闭环前，不扩 `self_mind / direct_branch / mission_ingress` 的主链接线。

4. heartbeat 从现在开始对前台 `chat` 主链完全屏蔽，不允许再把 heartbeat 当成 chat 入口、chat 调度器或 chat 兼容兜底。

## 当前状态

基于 `0321` 文档，当前已经具备：

1. `TalkMainlineService`、`TalkRuntimeService`、`TalkRouter`、`OutputBundle`、`FeishuDeliveryAdapter` 骨架都已出现。

2. 普通 `talk` 已开始进入新桥接层，`Invocation -> TalkRouter -> AgentSpec` 这段语义已成立。

3. `OutputBundle` 已经是统一输出包装对象，而不再只是一段裸文本。

当前仍待继续的部分：

1. 普通 `chat` 的飞书最终发送已接到 `FeishuDeliveryAdapter.deliver()`，旧 reply/file 链已降为 transport callback 与 fallback；这部分已闭环。

2. 运行时内部 route key 仍保留 `talk` 兼容值，属于兼容层，不再代表前台主命名。

3. `chat` 真实现仍主要位于 `body/runtime`，`butler_main/chat/` 仍是根入口 + 导出层，第二阶段物理迁移未完成。

## 下一阶段计划（最新）

### 设计目标

1. 这轮计划不只服务 `chat`，而是把 `chat` 作为第一条产品线，顺手把 `agent_os` 的 prompt / memory / runtime 基础设施打成可复用底座。

2. 原则是：`agent_os` 负责公共合同、公共 runtime、公共策略接口；`chat` 负责 Butler 前台产品语义；`body/runtime` 负责当前物理执行与落盘事实；`chat/feishu_bot` 负责飞书接口与展示层。

3. 任何这轮新增的 prompt / memory 能力，都要先判断是否可能被未来的其他 agent 复用；能复用的优先抽成 `agent_os` 合同或 runtime 扩展点，不再直接写死在 `chat` 私有大函数里。

### Wave 1：chat 独立运行

1. 把 `butler_main/chat/__main__.py` 从“转发到 `butler_bot.main()`”推进到“chat 自己的 bootstrap / app 入口”。

2. 新建 chat app 装配层，明确装配：config provider、mainline、runtime、channel runner、memory provider、prompt provider。

3. `butler_bot.py` 退成兼容壳，只负责旧入口桥接，不再承担 chat 主进程事实层。

4. 验收标准：`python -m butler_main.chat ...` 能不依赖 `butler_bot.main()` 直接完成本地/飞书启动。

### Wave 2：prompt 组装分层

1. 在 `agent_os` 侧继续补齐 prompt 公共件：

   * `PromptProfile`

   * `PromptContext`

   * `PromptBlock`

   * `ModelInput`

   * prompt assembler / renderer 扩展点

2. 在 `chat` 侧沉淀 Butler 私有 prompt 资产：

   * mode 语义

   * Soul / 用户画像 / 表达策略

   * chat route 对应的 prompt block 选择规则

3. 在 `body/runtime` 侧保留当前读取事实：bootstrap 文件读取、workspace 事实、当前 CLI/runtime 注入。

4. 拆分目标：把当前 `build_feishu_agent_prompt()`、`PromptAssemblyService` 逐步改成“`agent_os` 组装骨架 + chat block provider + body data provider + channel adapter”。

5. 长远要求：未来别的 agent 若要接入 prompt 体系，不需要复制 Butler 的大 prompt 函数，只要实现自己的 block provider / profile adapter 即可。

### Wave 3：memory 分层

1. 在 `agent_os` 侧补齐 memory 公共协议：

   * `MemoryReadPolicy`

   * `MemoryPromotionPolicy`

   * `MemoryCompactionPolicy`

   * `MemoryWritebackRequest`

   * memory runtime/provider 接口

2. 在 `chat` 侧只保留产品判断：

   * 哪些 route 读 recent

   * 哪些 route 可见 local/profile/self_mind

   * 哪些回复应该触发 writeback / promotion

3. 在 `body/runtime` 侧暂时保留真实事实：recent/local 读写、pending turn、压缩、持久化、目录布局。

4. `memory_manager.py` 这一轮不要求立刻搬走，但要开始收口成 provider，而不是继续兼做产品逻辑和运行时逻辑。

5. 长远要求：未来其他 agent 可以复用 `agent_os` 的 memory contract 和 runtime/provider 接口，而不依赖 Butler 的目录事实或飞书对话事实。

### Wave 4：feishu 展示接口层独立化

1. 把 `agent.py` 中与飞书展示强绑定的逻辑继续抽到 `chat/feishu_bot`：

   * 事件分发

   * 文本 / interactive card / post 渲染

   * 图片 / 文件展示发送

   * reply / update / push 语义

2. 目标分工：

   * `FeishuInputAdapter` / `FeishuDeliveryAdapter` 负责接口合同与 session/delivery 语义

   * `chat/feishu_bot` 展示层负责“在飞书里如何呈现”

   * `chat mainline` 只产出标准 `Invocation / RuntimeRequest / OutputBundle`

3. 长远要求：未来若接企业微信、网页 chat、App chat，也能并列新增新的 channel presentation layer，而不是继续复制 `agent.py`。

4. 本轮已先按该原则在 `chat/weixi/` 开一路 shell，作为微信接口层真源入口。

### Wave 5：chat 兼容层收缩与 agent_os 对齐

1. 收缩 `talk_*` 兼容壳和 `route=talk` 兼容键，逐步把运行时内部主语义也切到 `chat`。

2. 把 `self_mind / direct_branch / mission_ingress(orchestrator)` 与 chat 主线边界重新收口，避免继续混在同一入口事实层里。

3. 为未来多 agent 统一出一套装配矩阵：

   * 哪些进 `agent_os`

   * 哪些留产品层

   * 哪些留 body/runtime

   * 哪些归 channel interface layer

4. 继续补测试、启动链验证、模块边界文档和迁移矩阵，保证后续物理迁移不是盲拆。

### 总体验收口径

1. `chat` 可以独立运行，不再依赖 `butler_bot.main()`。

2. prompt / memory 的公共合同和 runtime 扩展点位于 `agent_os`，不是 Butler 私有实现。

3. Butler chat 只承载自己的产品语义，不再顺手吞掉公共基础设施。

4. `chat/feishu_bot` 成为清晰的接口与展示层，而不是混在消息大函数里的遗留实现。

5. 未来新增别的 agent 或别的 channel 时，能复用 `agent_os` 的 prompt + memory 底座，而不是再复制一套 chat 私有链路。

## 明确暂缓

1. 暂缓 `self_mind` 主链接线。

2. 暂缓 `direct_branch` 的自然语言扩展和更多场景种类。

3. 暂缓 `mission_ingress` 的完整产品链幻想式推进。

4. 暂缓把 Butler 私有 prompt/memory runtime 大规模搬进 `agent_os`。

5. 暂缓继续扩 `chat/weixi/` 的真实 transport 与会话桥接。

## 验收标准

1. 至少一条普通 `talk` 请求能完整走新链并完成最终 reply 发送。

2. 主链不再在旧大函数里直接拼回复。

3. 结论文案里只允许写“普通 talk 主链已闭环到什么程度”，不允许再写泛化的“Talk + AgentOS 已完成”。

## 追加记录

> 本节从现在起按倒序维护：最新记录永远插在最上面。

### 2026-03-22 18:53 rendering 已从 body 外提

* `chat/feishu_bot/rendering.py` 已落地，`interactive card / post / quick actions` 已从 body `agent.py` 外提到 chat 的飞书展示层目录下。

* 当前 `agent.py` 里的同名函数已经改成调 `chat/feishu_bot` rendering 模块，这一步让飞书展示层不再只有 transport facade，也开始承接真正的展示结构定义。

* 这轮还没有动 event dispatch / message loop，但 presentation 的“渲染定义”已经不再只躺在 body 大文件里，后续继续往 `chat/feishu_bot` 收口的方向是明确的。

### 2026-03-22 18:39 presentation service 已接入主链

* `chat/feishu_bot/presentation.py` 已落地，并且 `agent.py` 的 delivery adapter 现在经由 `ChatFeishuPresentationService` 构造，不再完全在 body 里内联装配。

* 这一步的意义不是“飞书层已经拆完”，而是先把 presentation transport facade 单独立住，为后续继续把 rendering / dispatch / reply helper 从 `agent.py` 外提做准备。

* 相关验证已补上：`test_chat_feishu_presentation` 已通过，说明新的 presentation 层不只是导出存在，而是能真实驱动 delivery callback。

### 2026-03-22 18:03 1-5 已开始落地

* `chat` 独立运行已迈出第一步：`chat.app`、`ChatAppBootstrap`、`chat.__main__`、旧 `butler_bot.main()` 兼容桥接都已经接通。

* prompt / memory 分层已进入代码层：新增 `agents_os` provider interface，并在 `chat/providers` 下落了 Butler 过渡 provider，开始把这块从纯 body 事实层往 app/provider 结构迁移。

* `chat/feishu_bot` 已新增 runner 装配层；当前还只是把启动入口抽了一层，后续还要继续把 presentation/rendering 事实从 `agent.py` 拆出来。

* 当前不是“1-5 完成”，而是“1-5 的骨架工程已经开始，后续会继续从 body 中抽真实事实层”。

### 2026-03-22 12:41 面向 agent_os 的下一阶段计划

* 已将下一阶段计划重写为“`chat` 是第一条产品线，但 `agent_os` 要承接未来多 agent 的 prompt + memory 公共底座”的口径。

* 计划已明确拆成五个 wave：`chat` 独立运行、prompt 分层、memory 分层、`feishu` 展示接口层独立化、chat 兼容层收缩与 `agent_os` 对齐。

* 新要求已写明：能跨 agent 复用的 prompt / memory 能力优先进入 `agent_os` 合同或 runtime/provider 扩展点，不再直接写死在 Butler chat 私有大函数里。

### 2026-03-22 12:33 最新推进口径

* 已把后续主线明确改写为：`chat` 独立运行、prompt 组装分层、memory 分层、`chat/feishu_bot` 展示接口层，以及其它 chat 相关兼容层收缩事项。

* 当前判断保持不变：普通 `chat + feishu` 主链已经闭环，但 `chat` 仍未脱离 body/runtime 独立运行。

* 之后本页不再按时间正序堆积，新增进度一律写在顶部，方便直接读取当前状态。

### 2026-03-22 00:46

* 依据 `talk_agent_os_phase_progress_20260321.md`、`talk_agent_os_mainline_execution_plan_20260321.md`、`talk_agent_os_integration_review_20260321.md` 收口今天主线。

* 决定今天不再扩 `Phase 2/3/5` 规划，而是先把 `Phase 1 + Phase 4` 的最小闭环做实。

### 2026-03-22 命名收口决定

* `talk` 从 `butler_bot_code` / `butler_bot_agent` 的散落命名中抽出，前台主命名统一改为 `chat`。

* `feishu_bot` 明确降为 `chat` 下的接口层，而不是继续承担前台主概念。

* 旧 `talk_*` 模块短期保留兼容壳，但不再作为新增能力的命名基线。

* 原先对外说法里的 `heartbeat` 入口语义废弃，统一对外改称 `orchestrator`；旧 heartbeat 仅保留历史兼容和底层遗留实现语境。

### 2026-03-22 结构收口追加计划

* 结论先定：前台产品名应直接统一为 `chat`，不再把 `talk` 作为未来主命名。

* 但目录迁移分两步做，不在同一轮里把运行实现整体从 `butler_bot_code/` 硬搬到 `butler_main/` 根层。

#### 判断

1. **命名层**：应该直接改名为 `chat`。\
   原因不是“看起来更顺”，而是它已经承接了统一前台入口、`feishu_bot` 接口层、后续多渠道入口的中性语义；继续保留 `talk` 作为主名，只会让代码、文档、入口词三套口径继续分裂。

2. **目录层**：不建议这一轮直接把主实现搬出 `butler_bot_code/`。\
   当前 `butler_bot_code` 仍是运行时身体层，里面挂着配置、manager、logs、run、tests、memory_manager、飞书启动链；这时直接把入口物理上移到 `butler_main/`，改动面会从“主链收口”扩大成“项目分层重构”，会把今天的主线冲散。

3. **正确方向**：应该让 `butler_main/` 先拥有一个明确的 `chat` 根入口，但该入口初期只做薄转发，不复制实现。

#### 下一步计划

1. 在 `butler_main/` 下建立显式 `chat/` 根入口目录，作为产品层入口名义真源。

2. `butler_main/chat/` 第一阶段只保留：

   * 根入口脚本/包导出

   * 对 `butler_bot_code/butler_bot/chat` 的薄封装

   * 与 `feishu_bot` 相关的接口层装配

3. `butler_bot_code/` 继续保留运行时身体职责：

   * manager / configs / logs / run

   * 现有 runtime / memory / transport / watchdog

   * 兼容期测试与旧导入壳

4. 待下面条件成立后，再做第二阶段物理迁移：

   * `FeishuDeliveryAdapter` 真实 transport 已接通

   * 普通 `chat` 主链已明确脱离旧 heartbeat 前台依赖

   * `butler_bot.py` 启动链已切成“根入口薄壳 + body runtime”

   * 旧 `talk_*` 导入已基本只剩兼容引用

5. 第二阶段再考虑把 `chat` 的主实现逐步从 `butler_bot_code/butler_bot/` 挪到 `butler_main/chat/`，并把 `butler_bot_code` 收窄成纯 body/runtime 仓。

#### 现阶段落地口径

* 对外和对内文档都优先说 `chat`，不再把 `talk` 说成未来主名。

* 代码上允许暂时存在 `talk` 兼容模块，但新增入口、导入、文档、测试优先使用 `chat`。

* 入口位置上采用“**先根层建壳，再延后搬实现**”的策略，而不是今天直接做大挪移。

### 2026-03-22 开始执行根层迁移

* 已开始把 `chat` 真入口上提到 `butler_main/chat/`。

* `butler_main/chat/__main__.py` 作为新的根层启动入口，允许后续直接从 `butler_main` 侧承接 chat。

* `butler_bot_code/butler_bot/chat/` 退为兼容桥，不再作为主入口真源。

* 后续拆分原则：先迁入口与导入，再迁实现，再收缩 `butler_bot_code` 为 body/runtime。

### 2026-03-22 butler_bot_agent 联动整理计划

`butler_bot_agent` 里仍有一批 `talk` 时代残留，这一轮不只改名字，还要顺手把 **memory / prompt 装配** 的归属讲清楚。

#### 当前识别到的 talk 相关真源

1. `bootstrap/TALK.md`

2. `bootstrap/MEMORY_POLICY.md`

3. `agents/docs/MEMORY_MECHANISM.md`

4. `agents/docs/MEMORY_READ_PROMPTS.md`

5. `feishu-workstation-agent` 这组旧入口角色表述

6. 若干文档中把 talk recent / 飞书表达 / prompt 组装混写在同一层

#### 最终分层判断

后续不再只按 `chat / body / agentOS` 三层粗分，而是明确成 **四分法**：

1. `agent_os`

   * 放抽象接口、协议、通用合同、可跨产品复用的装配规范

   * 例如：`PromptProfile / PromptContext / MemoryPolicy`、memory promotion/compaction 协议、`OutputBundle`、runtime/workflow 合同

2. `chat`

   * 放 Butler 前台产品语义

   * 例如：chat route、companion/content_share/execution 模式、Butler_SOUL 映射、用户画像、前台表达策略

3. `body/runtime`

   * 放真实运行机制和物理执行层

   * 例如：recent/local 持久化、压缩触发、manager/config/run/logs、CLI/runtime 执行、watchdog、workspace 落盘

4. `chat/feishu_bot`

   * 放飞书专属接口层

   * 例如：`FeishuInputAdapter`、`FeishuDeliveryAdapter`、飞书 session/reply/update/push 语义、chat 到飞书的接口装配

一句话判断标准：

* 能跨产品复用的，进 `agent_os`

* 属于 Butler 前台产品语义的，留 `chat`

* 属于运行机制和物理执行的，留 `body/runtime`

* 飞书专属接口，统一收进 `chat/feishu_bot`

#### 对 memory / prompt 装配的具体判断

1. `bootstrap/TALK.md` 不应整体搬进 agentOS。\
   其中只有“模式切换接口”值得抽象；具体文案、人设、语气是 Butler chat 私货，应留在产品层。

2. `bootstrap/MEMORY_POLICY.md` 可以拆成三层。

   * `chat` 私有部分：`chat/self_mind/orchestrator` 各自读什么、禁止什么。

   * `body/runtime` 部分：真实读取时机、注入点、压缩/写回触发。

   * `agentOS` 公共部分：`MemoryPolicy` 抽象、visibility scopes、轻载/重载策略、route visibility。

3. `MEMORY_MECHANISM.md` 不应原样搬进 agentOS。\
   路径 `./butler_bot_agent/agents/...`、recent/local 文件布局、Current_User_Profile 等都是 Butler 目录事实；真正可迁的是“短期/长期/promotion/compaction”的协议和字段约束。

4. `MEMORY_READ_PROMPTS.md` 也要拆。

   * “先判断是否需要读 recent/local”这套原则可进入 agentOS。

   * 具体文件路径、飞书管家口径、Current_User_Profile 私有说明仍留 Butler。

5. prompt 装配要从“文档约定”继续变成“agentOS 接口 + Butler adapter + chat 产品文本”。\
   也就是：Butler 继续维护自己的 bootstrap 文本，飞书接口放 `chat/feishu_bot`，最终由 adapter 转成 `PromptProfile / PromptContext / MemoryPolicy`，而不是在主链里手搓拼接。

#### 迁移计划

##### Wave 0：口径冻结

1. 文档中统一采用四分法：`agent_os / chat / body-runtime / chat-feishu_bot`。

2. 停止新增 `talk` 主命名；新增内容统一使用 `chat`。

3. 停止把飞书接口散落在 body 或 agent 文档里，统一归到 `chat/feishu_bot` 口径。

##### Wave 1：飞书接口彻底收进 chat

1. `FeishuInputAdapter`、`FeishuDeliveryAdapter`、飞书 delivery session 相关装配都以 `chat/feishu_bot` 为唯一入口口径。

2. `feishu-workstation-agent` 的历史表述改写为“`chat` 的飞书接口角色”，不再代表整个前台系统。

3. Butler 文档中凡是“飞书入口 = 主入口”的旧表述，逐步改成“飞书只是 chat 的一个接口层”。

##### Wave 2：chat 与 body/runtime 拆清

1. `bootstrap/TALK.md` 逐步转成 `CHAT` 口径。

2. `bootstrap/MEMORY_POLICY.md` 中把产品语义和运行时机制分开。

3. recent/local 的真实读写、压缩、持久化触发，从 agent 文档口径里抽回 `body/runtime` 事实层。

4. `chat` 只保留“该读什么、该怎么说、怎么看用户”的产品逻辑，不承载底层写盘细节。

##### Wave 3：从 Butler 抽 agentOS 公共件

1. 把 `PromptProfile / PromptContext / MemoryPolicy` 继续做成稳定 adapter 接口。

2. 把“是否读取 recent/local”“promotion/compaction 如何定义”“route visibility 如何表达”抽成 agentOS 协议。

3. Butler 私有 prompt 文本、用户画像、Soul、飞书口径不搬走，只通过 adapter 接入 agentOS。

##### Wave 4：butler_bot_agent 归属矩阵落盘

1. 新增一份“`butler_bot_agent -> agent_os / chat / body-runtime / chat-feishu_bot` 归属矩阵”。

2. 逐条登记：

   * bootstrap

   * memory docs

   * role docs

   * skills

   * adapters

3. 之后所有迁移按矩阵推进，不再靠临时判断。

#### 立即执行项

1. 在 `butler_bot_agent` 中把 `TALK` 口径逐步改名为 `CHAT` 口径，旧名保留兼容期说明。

2. 清理 `feishu-workstation-agent` 的历史表述，明确它只是 `chat/feishu_bot` 的一个飞书接口角色，不再代表整个前台系统。

3. 新增一份“`butler_bot_agent -> agent_os / chat / body-runtime / chat-feishu_bot` 归属矩阵”文档，逐条登记 bootstrap、memory、prompt、role、skills 的去向。

4. 在代码侧继续把现有 Butler adapter 做实：

   * `PromptProfile` adapter

   * `MemoryPolicy` adapter

   * `PromptContext` adapter

   * 后续补 `MemoryReadPolicy` / `MemoryPromotionPolicy` adapter

5. 代码迁移从 `chat/feishu_bot` 和 `CHAT` bootstrap 开始，不再先碰 heartbeat 残留。

6. 待上面矩阵稳定后，再把 agentOS 只接走“抽象接口与协议”，而不是把 Butler 的私有 prompt 文案整体搬过去。

### 2026-03-22 迁移完成记录

* `butler_main/chat/` 已不再直接指向 `talk_*` 实现文件，而是统一经过 `chat` 导出层。

* `butler_bot_code/butler_bot` 内新增 `chat_router.py`、`chat_runtime_service.py`、`chat_mainline_service.py` 作为本轮主实现名。

* 旧 `talk_router.py`、`talk_runtime_service.py`、`talk_mainline_service.py` 已降为兼容壳，只保留别名导出。

* `chat/feishu_bot` 已补成显式模块入口：`input.py` / `delivery.py`。

* 当前仍保留 `route=talk` 作为兼容期运行路由键；这属于运行时兼容，不再代表前台主命名。

### 2026-03-22 chat transport 闭环记录

* `run_agent` 现已向消息层回传本轮 `OutputBundle / DeliverySession / DeliveryPlan`。

* `agent.py` 在飞书消息流里会优先走 `FeishuDeliveryAdapter.deliver()`，只在新链拿不到 bundle/session 或 transport 未接通时才回退旧 `_send_deduped_reply()` / `_send_output_files()`。

* `chat/feishu_bot` 已从“只会出 plan”升级到“真实绑定 reply / push / upload transport callback”。

* `decide` 产出文件在新链下会先按 `workspace_root` 解析成本地绝对路径，再执行上传与回复/推送。

* 本轮验证已覆盖：`test_feishu_delivery_adapter`、`test_agent_message_flow`、`test_talk_mainline_service`、`test_talk_runtime_service`、`test_talk_router_and_mission_orchestrator`、`python -m butler_main.chat --help`。

### 2026-03-22 状态问答快照

#### chat 现在算不算完全

* **普通 chat 主链已经完成，但整个 chat 迁移还不算完全完成。**

* 已完成的是：

  1. 前台主命名统一到 `chat`、根入口上提到 `butler_main/chat/`、`chat/feishu_bot` 成为显式接口层。

  2. 普通 chat 已能完整走 `Invocation -> Router -> RuntimeRequest -> OutputBundle -> DeliverySession -> FeishuDeliveryAdapter.deliver()`。

  3. `butler_bot.py` 已把 `OutputBundle / DeliverySession / DeliveryPlan` 回传给消息层，`agent.py` 在飞书场景下优先走新 delivery，旧 reply/file 链只作 fallback。

  4. 相对产出文件路径已能按 `workspace_root` 解析后上传，`decide` 文件发送不再只依赖旧 `_send_output_files()`。

* 还没完成的是：

  1. 运行时内部主 route key 仍保留 `talk` 兼容值；

  2. `chat` 主实现还没有第二阶段物理上移到 `butler_main/chat/`，当前仍是“根层真入口 + body 真实现”的双层结构；

  3. `self_mind / direct_branch / mission_ingress` 的二阶段主链清理和统一收口还没一起完成。

* 结论：**“普通 chat + Feishu 主链”可以判为闭环；“chat 全部迁移完成”还不能下结论。**

#### agents_os 里的 prompt / memory 基础设施现在到哪

* **基础合同层已经搭好，但还没有到“完整运行时已接管”的程度。**

* 已有：

  1. `agents_os/contracts/prompt.py`：`PromptBlock` / `PromptProfile` / `PromptContext` / `ModelInput`；

  2. `agents_os/contracts/memory.py`：`MemoryScope` / `MemoryPolicy` / `MemoryHit` / `MemoryWritebackRequest` / `MemoryContext`；

  3. `butler_bot_code/butler_bot/adapters/`：Butler 侧 `PromptProfile` / `PromptContext` / `MemoryPolicy` adapter 已落地；

  4. `agents_os/runtime/prompt_assembler.py`、`memory_runtime.py`：已有最小 runtime 骨架。

* 还没有：

  1. 基于 `PromptProfile / PromptContext / MemoryPolicy` 的完整 prompt 装配主链接管；

  2. recent/local memory 的真实读取、过滤、promotion、compaction、writeback 被 `agents_os` runtime 完整承接；

  3. `MemoryReadPolicy` / `MemoryPromotionPolicy` 这类更细的公共协议与 Butler adapter；

  4. 用 `agents_os` 自己的 prompt/memory runtime 替换 Butler 当前 `memory_manager.py` 主事实层。

* 结论：**prompt/memory 的“接口和协议层”基本有了，“运行时承接层”还只是骨架，不算完成。**

#### 飞书升级推进到哪里

* 已完成：

  1. `FeishuInputAdapter` 现在会携带 `source_event_id / feishu.message_id` 进入主链；

  2. `ChatRouter` 会把 `DeliverySession` 所需的 `message_id / raw_session_ref / thread_id` 装好；

  3. `run_agent` 会把本轮 `OutputBundle / DeliverySession / DeliveryPlan` 回传给消息层线程；

  4. `agent.py` 已优先使用 `FeishuDeliveryAdapter.deliver()` 执行文本 / 图片 / 文件发送，旧 `_send_deduped_reply()` 与 `_send_output_files()` 只在新链不可用时回退；

  5. `chat/feishu_bot` 现已不只是 planning adapter，而是绑定了真实 `reply / push / upload` transport callback；

  6. 已通过 `test_feishu_delivery_adapter`、`test_agent_message_flow`、`test_talk_*` 回归和 `python -m butler_main.chat --help` 验证。

* 当前剩余：

  1. `update / finalize` 语义虽然已在 adapter 里保留，但生产流目前主要走 `create / reply`；

  2. transport 仍复用旧飞书 `reply_message / upload_file / send_private_message` 实现，后续还可继续下沉成更干净的接口服务；

  3. 非飞书渠道和更广义的多接口层抽象还没展开。

* 结论：**飞书升级已经从&#x20;**`delivery planning ready`**&#x20;进入&#x20;**`ordinary chat delivery transport closed`**。**

⠀
