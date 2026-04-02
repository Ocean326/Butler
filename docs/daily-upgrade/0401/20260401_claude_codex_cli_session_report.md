# Claude / Codex CLI 单 Session 能力报告

日期：2026-04-01
范围：基于仓库内 `Claude` 学习源码、`Codex` 源码压缩包、以及 Butler 现有 runtime 适配层，分析如何在**一个 session 家族**内完成：

`压缩 -> skill 注入 -> subagent -> agent -> agent team`

---

## 1. 先给结论

### 1.1 结论一句话

如果按你现在仓库里已经能落地核验的材料来判断：

- `Claude` 已经在同一套 CLI 源码里，把 `query + compact + skills + task/subagent + coordinator/team` 做成一条连续主链。
- `Codex` 现在也已经补到**源码级证据**，不再只是 `.codex/` 配置和 Butler adapter；`codex-main.zip` 里可以直接确认 `thread/session`、`compact`、`skills`、`subagent`、`agent hierarchy / collaboration` 都是正式 runtime 组成部分。
- `Butler` 现在能把这条链条复刻成自己的前台实现，但它更像：
  - `thread/session_id`
  - `SkillExposureContract`
  - `role_pack + role_session + handoff`
  - `execution_mode + session_strategy`

  也就是“用单 flow/session 家族 + 多角色运行时”去逼近 `subagent / agent team`。

### 1.2 最关键裁决

想在一个 session 内完成这五层能力，必须满足下面的依赖顺序：

1. **先有 durable session / thread**
2. **再做 compact / summary / boundary**
3. **再做 skill discovery / injection**
4. **再做子 agent 派发**
5. **最后才升级为 team / teammate / parallel orchestration**

这里的“单 session”不是“永远只有一条消息历史、一个执行体”，而是：

- 有一个根 session / root thread
- 可以在同一个 session 家族里 compact
- 可以在同一个 session 家族里派生 child task / child thread
- 最后由 coordinator / parent 汇总回主链

如果这五件事顺序颠倒，系统就会出现典型问题：

- 没有 session，resume 不了
- 没有 compact，子 agent 会把上下文烧穿
- 没有 skill contract，subagent 只会拿到散 prompt
- 没有 task / thread registry / summary，team 只会变成“多个并发终端”

---

## 2. 证据范围

### 2.1 Claude 证据

主项目：

- `MyWorkSpace/TargetProjects/claude-code-main/`

关键文档与源码：

- `README.md`
- `docs/subsystems.md`
- `docs/tools.md`
- `src/query.ts`
- `src/coordinator/coordinatorMode.ts`
- `src/skills/loadSkillsDir.ts`
- `src/tasks/LocalAgentTask/LocalAgentTask.tsx`
- `src/tasks/LocalMainSessionTask.ts`

### 2.2 Codex 证据

主项目：

- `MyWorkSpace/TargetProjects/codex-main.zip`

关键文档与源码：

- `codex-main/README.md`
- `codex-main/codex-cli/README.md`
- `codex-main/codex-rs/core/src/compact.rs`
- `codex-main/codex-rs/core/src/skills.rs`
- `codex-main/codex-rs/core/src/thread_manager.rs`
- `codex-main/codex-rs/core/src/tools/handlers/multi_agents.rs`
- `codex-main/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs`
- `codex-main/codex-rs/core/src/agent/registry.rs`
- `codex-main/codex-rs/app-server/tests/suite/v2/thread_resume.rs`
- `codex-main/codex-rs/core/tests/suite/hierarchical_agents.rs`
- `codex-main/codex-rs/app-server-protocol/schema/json/v2/Thread*.json`
- `codex-main/codex-rs/app-server-protocol/schema/json/v2/Skills*.json`
- `codex-main/codex-rs/app-server-protocol/schema/typescript/v2/Collab*.ts`

备注：

- 这次已经补到独立 `Codex` CLI 源码树。
- 因此本报告对 `Codex` 的判断，已经从“配置/适配层可验证”升级成“**源码级机制可验证**”。

### 2.3 Butler 证据

- `butler_main/agents_os/execution/cli_runner.py`
- `butler_main/agents_os/skills/exposure.py`
- `butler_main/butler_flow/runtime.py`
- `butler_main/butler_flow/role_runtime.py`
- `butler_main/butler_flow/cli.py`
- `butler_main/domains/campaign/codex_runtime.py`

---

## 3. Claude 是怎么在一个 session 内串起五层能力的

### 3.1 压缩：不是“总结一下”，而是 query 主循环里的正式阶段

`Claude` 的压缩不是外挂命令，而是 `query` 主循环里的正式能力：

- `src/query.ts` 里先走 `contextCollapse`
- 再走 `autocompact`
- 压缩成功后生成 `postCompactMessages`
- 继续在**同一次 query/session 调用链**里往后跑
- 同时还会为下一轮递归调用异步生成 `tool use summary`

这意味着：

- compact 不会把 session 切断
- compact 后的 boundary/message 仍属于同一条会话
- task budget / token accounting / continuation 都是连续的

所以 `Claude` 的 compact 不是“另起一个 summary 命令”，而是：

- 主循环内建
- 有边界对象
- 有压缩后继续执行

### 3.2 skill 注入：先 discovery，再按 session/context materialize

`Claude` 的 skill 不只是静态目录：

- `src/skills/loadSkillsDir.ts` 明确把技能来源拆成 `skills / plugin / managed / bundled / mcp`
- 代码里有 `getSkillsPath(...)`，分别对接 `userSettings`、`projectSettings`、`policySettings`、`plugin`
- `registerMCPSkillBuilders` 说明 MCP 也能生成 skill
- `src/query.ts` 还存在 `skillPrefetch` 路径

这说明 `Claude` 的 skill 模式是：

1. session 仍然是主载体
2. skill 作为可发现资产挂到 query/session 上
3. skill 可以来自本地目录，也可以来自 plugin、managed、bundled、MCP builder
4. 注入不是一次性全量塞 prompt，而是带 loader / registry / prefetch 的按需 materialize

### 3.3 subagent：是 task runtime 的一种 task，不是“另开一个 shell”

`Claude` 的 subagent 不是“后台多开个进程”这么粗糙：

- `docs/tools.md` 明确有 `AgentTool`、`SendMessageTool`
- `src/tasks/LocalAgentTask/LocalAgentTask.tsx` 里可以看到统一的 task state
- 子 agent 会输出 `task-notification` XML
- 每个 task 都有 `status / summary / result / usage / output_path`
- 还维护 `toolUseCount / tokenCount / recentActivities / progress summary`
- 支持 `pendingMessages`、继续、停止、背景运行、磁盘 transcript 挂接

这意味着 `Claude` 的 subagent 是正式 task 对象，具备：

- task id
- 可观测进度
- usage 统计
- transcript/output
- 被 parent 继续驱动的接口

### 3.4 agent：主 session 自己也被 task 化

`src/tasks/LocalMainSessionTask.ts` 很关键，它说明：

- 主 session 可以被 background
- background 之后仍继续跑 `query(...)`
- 主 session 也会被注册成 task
- 它复用了和 subagent 同一套 `LocalAgentTaskState`
- 完成后同样通过 notification / SDK 事件回流

也就是说，在 `Claude` 里：

- main agent
- local subagent
- remote agent
- background main session

并不是四套割裂系统，而是被收进同一层 task 语义。

### 3.5 agent team：不是多个 subagent 的松散集合，而是 coordinator mode

`src/coordinator/coordinatorMode.ts` 提供了比旧结论更强的证据：

- coordinator 明确区分自己和 worker
- 工具面明确暴露 `AgentTool`、`SendMessageTool`、`TaskStopTool`
- 还有 `TeamCreateTool`、`TeamDeleteTool`
- worker 的可用工具、MCP server、scratchpad 都会被显式注入 user context
- prompt 中直接规定 coordinator 负责 `research -> synthesis -> implementation -> verification`
- 并且明确要求 fan-out 并发、汇总、纠偏、停止、继续已有 worker

所以 `Claude` 真正的 team 语义不是“多个 agent 同时跑”这么简单，而是：

- 有 coordinator / worker contract
- 有 team lifecycle
- 有任务通知总线
- 有共享上下文注入
- 有并发调度规范

---

## 4. Codex 在你仓库里现在能确认到什么

### 4.1 已经补到独立 Codex CLI 源码树，不再只是配置面

`codex-main.zip` 已经能确认这是正式 `Codex` CLI 源码：

- `codex-main/README.md` 说明这是 OpenAI 的本地 coding agent / CLI 仓库
- `codex-main/codex-cli/README.md` 说明旧的 TypeScript CLI 已进入 legacy，现主实现是 Rust

因此现在必须修正旧结论：

- 不能再写成“仓库里没有独立 Codex CLI 源码树”
- 更准确的说法是：`Codex` 在仓库内同时具备**源码、配置、Butler adapter**三层证据

### 4.2 session / thread：Codex 是 thread-first 的单 session 家族模型

`Codex` 的“单 session”不是单个 shell 进程，而是 thread-first：

- `core/src/thread_manager.rs` 负责创建和维护内存中的 thread
- 里面同时挂着 `skills_manager`、`plugins_manager`、`mcp_manager`、`skills_watcher`
- protocol schema 直接定义了：
  - `ThreadStart`
  - `ThreadResume`
  - `ThreadFork`
  - `ThreadCompactStart`
  - `ThreadStatusChanged`
  - `ThreadTokenUsageUpdated`
- `app-server/tests/suite/v2/thread_resume.rs` 证明 resume 不是概念文案，而是实际测试过的 thread 恢复能力

所以 `Codex` 的一条主链是：

- root thread 建立
- thread 可 resume / fork / compact
- 子 agent 作为 child thread 派生
- 这些 child thread 仍属于同一 session 家族

### 4.3 压缩：Codex 的 compact 也是正式 session 机制，不是文档功能

`core/src/compact.rs` 给出的证据非常直接：

- compaction 本身就是一个正式 task
- 会创建 `ContextCompactionItem`
- 使用独立 `SUMMARIZATION_PROMPT` 和 `SUMMARY_PREFIX`
- 在 compaction 完成后构造 `replacement_history`
- 必要时重新注入 initial context
- 然后用新的 compacted history 替换旧历史继续运行

所以 `Codex` 的 compact 也具备这几个核心性质：

- 不是人工“总结一下”
- 不是切断 thread 后另开新会话
- 而是 thread 内的 replacement history / continuation 机制

这和 `Claude query.ts` 的思路不同，但层级是同一档的。

### 4.4 skill 注入：Codex 不是“读 SKILL.md 就完了”，而是正式 SkillsManager

`core/src/skills.rs` 说明 `Codex` 的 skill 机制并不只是目录扫描：

- 有 `SkillsManager`
- 有 `SkillsLoadInput`
- 有 `build_skill_injections`
- 有 dependency 解析
- 有 `detect_implicit_skill_invocation_for_command`
- 缺失依赖时还能走 `request_user_input`
- skill telemetry 也会计数

`core/src/thread_manager.rs` 里还可以看到：

- `skills_watcher` 会监听技能变化
- 技能变化后清 cache

protocol schema 里又有：

- `SkillsList`
- `SkillsChanged`
- `SkillsConfigWrite`

所以 `Codex` 的 skill 机制是：

- 有 loader
- 有 watcher
- 有 injection
- 有依赖补全
- 有 session/thread 级缓存与变更通知

### 4.5 subagent / agent / team：Codex 已有正式 collaboration runtime

这部分是本次补证里最重要的变化。

从 `core/src/tools/handlers/multi_agents.rs` 与 `multi_agents_v2/spawn.rs` 可以确认：

- `spawn_agent` 是正式 tool handler
- child agent 会继承 turn config / runtime state
- 支持 role 应用
- 支持 `fork_turns = none | all | last N`
- 会校验 spawn depth limit
- 会发出 `CollabAgentSpawnBeginEvent` / `CollabAgentSpawnEndEvent`

从 `core/src/agent/registry.rs` 可以确认：

- 有统一 `AgentRegistry`
- 会限制 session 内总 sub-agent 数量
- 会记录 live agents、path、nickname、role、last_task_message
- 会管理 depth / thread 限额

从 protocol schema 可以确认：

- 有 `CollaborationMode`
- 有 `CollabAgentState`
- 有 `CollabAgentStatus`
- 有 `CollabAgentTool`

从 `core/tests/suite/hierarchical_agents.rs` 可以确认：

- child agent 会附带 `AGENTS.md` 指令
- 这不是推测，而是有测试明确校验

所以 `Codex` 现在已经可以被准确描述为：

- thread-first
- compact-aware
- skills-aware
- multi-agent capable
- hierarchical-agent capable

它和 `Claude` 的区别主要不在“有没有这些机制”，而在：

- `Claude` 更偏 `query/task/coordinator` 产品壳
- `Codex` 更偏 `thread/collab handler/agent registry` 运行时壳

### 4.6 Butler 对 Codex 的接入是在外层把 session 家族收口成产品工作流

即使 `Codex` 内部已有这些能力，Butler 现在的实际接入仍然很重要：

- `butler_main/agents_os/execution/cli_runner.py` 已经支持 `codex exec`
- 也支持 `codex exec resume`
- 会记录 `thread_id`
- 会把 `external_session.thread_id`、`resume_capable` 写进 metadata

所以 Butler 的价值不是“凭空发明 Codex 的 session/collab”，而是：

- 把 `Codex` 的 thread/runtime 能力纳入 Butler 自己的 flow、receipt、handoff、role runtime

---

## 5. Butler 现在怎样把这条链做成“单 session 闭环”

### 5.1 压缩：Butler 目前更偏结构化摘要，而不是 Claude/Codex 那种内建 compact runtime

Butler 当前更接近：

- `task_summary`
- `latest_summary`
- `phase_history`
- `handoff.summary`
- `compact_json(...)`

也就是：

- 用结构化摘要控制上下文
- 用 handoff / artifact / summary 代替全量历史

它已经能工作，但和 `Claude src/query.ts`、`Codex core/src/compact.rs` 这种“session 内正式 compact + boundary + continuation”相比，还不是同等级的一体化压缩内核。

### 5.2 skill 注入：Butler 已经是正式合同，不是 prompt 碎片

`butler_main/agents_os/skills/exposure.py` 已经定义：

- `SkillExposureContract`
- `collection_id`
- `family_hints`
- `direct_skill_names`
- `provider_overrides`

`cli_runner.py` 会把这个合同 materialize 给具体 provider。

这部分其实已经很规整，因为它明确区分了：

- skill 真源
- exposure contract
- provider override

### 5.3 subagent：Butler 前台目前走“role-bound session”而不是 provider 原生 task swarm

`butler_flow/runtime.py + role_runtime.py` 现在的做法是：

- 一个 flow 保持一个主 `codex_session_id`
- `execution_mode`
  - `simple`
  - `medium`
  - `complex`
- `session_strategy`
  - `shared`
  - `role_bound`
  - `per_activation`

在 `medium` 模式下，Butler 用：

- `role_sessions.json`
- `handoffs.jsonl`
- `active_role_id`
- `latest_role_handoffs`

把多角色执行压进**同一 flow/session 家族**里。

这本质上是在做：

- session 内 subagent 化
- 但不是直接暴露 provider 自己的多 agent task runtime

### 5.4 agent：Butler 已经有主 agent + judge + fixer + reviewer 的可运行形态

从 `role_runtime.py` 和 `runtime.py` 可以确认：

- planner
- implementer
- reviewer
- fixer
- reporter
- researcher

这些角色都能：

- 绑定 session
- 消费 handoff
- 看到受控 artifact
- 写回下一跳 handoff

所以 Butler 的 agent 不是抽象名词，而是已落在：

- `role_pack`
- `current_role_prompt`
- `visible_artifacts`
- `create_handoff_packet`

### 5.5 agent team：Butler 当前是“轻 team runtime”，不是 Claude/Codex 那种一等协作运行时

Butler 已有 team 雏形：

- `orchestrator/framework_profiles.py` 里有 `team_package_ref`
- `multi_agents_os` 有 blackboard / artifact visibility / handoff primitive
- `butler_flow` 有 role pack + handoff + role session

但当前前台主链更像：

- 单 flow
- 多角色
- 紧凑 handoff
- supervisor / judge 控制

而不是完整的一等对象：

- `Claude` 式的 `TaskCreate/Agent/TeamCreate/SendMessage`
- 或 `Codex` 式的 `thread manager + collab handlers + agent registry`

换句话说：

- Butler 现在已经有“team 语义”
- 但还没有完全变成“team runtime”

---

## 6. 单 session 完成五层能力的正确实现顺序

### 6.1 Claude 路线

最完整的链路是：

1. 主 session 建立
2. `query` 主循环持续运行
3. 自动 compact / context collapse / tool-use summary 控制上下文
4. session 内 skill discovery / plugin / managed / MCP skill builder 注入
5. `AgentTool` 派发 subagent task
6. `SendMessageTool` 续跑子 agent
7. `TeamCreateTool` / coordinator mode 升级为 team
8. coordinator 汇总结果并回流主 session

### 6.2 Codex 路线

现在基于源码，`Codex` 的完整链路已经可以写得更准确：

1. `ThreadStart` 建立 root thread
2. `ThreadResume` / `ThreadFork` 维持同一 session 家族
3. `compact.rs` 在 thread 内做 replacement history
4. `SkillsManager + skills_watcher + skill injection` 完成技能装配
5. `spawn_agent` handler 派生 child thread
6. `AgentRegistry` 约束 live agents / depth / nickname / role
7. `CollaborationMode` 与 collab events 组成 team 协作面
8. parent thread 汇总 child thread 结果回到主链

如果通过 Butler 来消费 Codex，则是：

1. Butler `cli_runner` 先拿到 `thread_id`
2. 通过 `exec resume` 保持外部 session
3. 再用 Butler 自己的 `role_session + handoff + flow runtime` 叠加产品工作流

### 6.3 对 Butler 的工程建议

如果你的目标是“真正一条龙单 session”而不是“看起来像多 agent”，下一步应按这个顺序推进：

1. **把 compact 升级成正式 session 边界对象**
   - 现在 Butler 有 summary/handoff，但缺少 `Claude/Codex` 那种 compact boundary + post-compact continuation。
2. **把 role runtime 升级成 task runtime**
   - 让每个 role activation 都有 task id / summary / usage / result，而不只是写 `role_sessions.json`。
3. **把继续既有 worker 的接口做成一等对象**
   - 当前 Butler 更像 phase/handoff 跳转，缺少 `SendMessage` 或 `resume child context` 的正式语义。
4. **把 team 从 role pack 升到 coordinator/team contract**
   - `framework_profiles.py` 和 `multi_agents_os` 已有基础，但前台还没把 team 作为一等运行时对象。
5. **让 skill exposure、task、team 在同一观察面可见**
   - 现在 skill contract 很完整，但在 flow/team 维度上的可观测性仍弱于 `Claude/Codex`。

---

## 7. 最终判断

### 7.1 Claude

`Claude` 在你仓库里的学习源码已经证明：

- 单 session 可以同时承载 compact、skills、subagent、agent、team
- 关键不是 UI，而是 `query + task + coordinator + skills + compact` 在同一执行面里闭合

### 7.2 Codex

`Codex` 现在也已经有源码级证据证明：

- `thread/session` 是一等对象
- `compact` 是正式历史替换机制
- `skills` 有 `SkillsManager + watcher + injection`
- `subagent / hierarchy / collab` 有正式 handler、registry、schema、测试

因此不能再把它描述成“只有配置层、没有完整 runtime 证据”。

更准确的表述是：

> `Codex` 与 `Claude` 都已经具备在一个 session 家族里完成
> `压缩 -> skill 注入 -> subagent -> agent -> agent team`
> 的核心运行时原语；
> 区别主要在产品壳和主执行抽象：
> `Claude` 更偏 `query/task/coordinator`，
> `Codex` 更偏 `thread/collaboration/agent-registry`。

### 7.3 Butler

`Butler` 已经具备把这五层能力收口到一个 session 的方向和大部分原语：

- session / resume：有
- skill contract：有
- role/subagent 语义：有
- team 轻量形态：有
- 真正一体化 compact/task/team runtime：还差最后一层收口

因此最准确的表述是：

> 你现在的仓库已经能用 Butler 在单 session 内逼近 `Claude` 和 `Codex` 的闭环；
> 真正还没完全补齐的，不是 skills，也不是 resume，
> 而是“compact 边界对象 + task runtime + coordinator/team contract”的最后三处收口。

---

## 8. 0401 实施回写

本轮代码已把前述裁决落实成 Butler 当前现役边界：

- `cli_runner` 现在会把 `external_session` 明确拆成：
  - `thread_id`
  - `resume_capable`
  - `resume_durable`
  - `durable_resume_id`
  - `recovery_state`
  - `vendor_capabilities`
- `chat` 现在不再把 vendor thread 当真恢复主键，而是：
  - 用 `session_scope_id` 作为 Butler 连续性真主键
  - 用 recent scope 持久化每个 provider 的 session binding
  - 下一轮执行前先按 binding 预判能否继续 vendor resume
  - 若发现 CLI 切换、重装、`codex_home` 变化或 binding 不再 durable，则直接走 `transparent reseed`
- `butler-flow` / `campaign` 已同步改成：
  - `thread_id` 继续记录，但只作为辅助 handle
  - 若上一轮 resume 明确失败，下一轮自动退回 `codex_mode=exec`

因此 0401 之后 Butler 对 `codex/claude cli` 的现役口径是：

1. vendor-native:
   - `session`
   - `resume`
   - `compact`
2. Butler-owned:
   - `recent/local memory`
   - `skill exposure`
   - `frontdoor continuity`
   - `collab/subagent/team` 的产品级连续性与恢复
3. hybrid:
   - 执行时可借 vendor thread 保留局部上下文
   - 但恢复时永远先保 Butler 状态，再决定是否复用旧 thread

---

## 9. Chat 当前现状（0401 重启后复验）

### 9.1 运行状态

截至 `2026-04-01` 本轮复验时，chat 后台运行正常：

- `butler_bot` 已完成重启并保持存活
- `manager status` 返回：
  - `running=True`
  - `stale_pid=False`
  - `pid=3284445`
  - `health_ok=True`
  - `health_status=200`
- 当前 pid 文件也与运行态一致：`butler_main/butler_bot_code/run/butler_bot.pid = 3284445`
- 同机配套进程也处于存活状态：
  - `orchestrator` 运行中
  - `console` 运行中且健康检查 `200`

这说明今天这轮改造后的 chat 主进程，至少在进程存活、健康检查、bot 长连恢复这三个层面已经闭环。

### 9.2 最新观察到的 chat 执行链

从 `butler_main/butler_bot_code/logs/butler_bot.log` 可直接确认，`2026-04-01 19:27:35` 与 `2026-04-01 19:33:33` 两次最近 chat 请求都跑通了完整主链：

- `route=chat`
- `chat-runtime-prompt-stats` 正常输出，说明 recent/skills/prompt build 已完成
- `agent_capabilities` block 仍被 gate 住，说明当前日常 chat 主链还不是“默认外显 agent runtime 能力”的前台形态
- `frontdoor_contract` 与 `frontdoor_protocols` 均显示 `suppressed_by=frontdoor_not_active`
- `chat-runtime-total` 正常输出，本轮模型执行分别为：
  - `model_exec=26.628s total=26.674s`
  - `model_exec=176.347s total=176.395s`
- 回复发送完成后，都出现了：
  - `recent-fallback`
  - `记忆] 收到 on_reply_sent`
  - `recent-finalized`

这说明当前 chat 现役路径仍然是：

1. 走普通 `chat` 路由，不走 frontdoor task 分流。
2. 先装 recent memory 与 skills，再组装 prompt。
3. 模型执行完成后发回飞书。
4. 回包后再异步完成 recent memory 持久化与 finalized。

因此 0401 当前 chat 的真实状态不是“session 改造中断导致不可用”，而是：

- 基本 chat 主链可运行
- recent memory 可续接
- session 绑定与恢复逻辑已落到 runtime
- 但前台默认入口仍主要表现为普通 `chat route`，不是全时暴露 vendor/team/runtime 控制面

### 9.3 当前连续性边界

结合 0401 已实施代码，chat 当前现役连续性边界已经固定为：

1. `session_scope_id` 是 Butler chat 的真正连续性主键。
2. vendor `thread_id` 只是外部 `external_session` handle，不再承担 Butler 自身恢复主键职责。
3. recent scope 会按 `session_scope_id + provider` 持久化 runtime session binding。
4. execution receipt / metadata 里会带回：
   - `external_session`
   - `recovery_state`
   - `vendor_capabilities`
5. 如果检测到下面任一情况，Butler 不再强依赖旧 vendor thread，而是直接透明 `reseed`：
   - CLI provider 切换
   - CLI 重装或 binary 变化
   - session store / `codex_home` 变化
   - binding 不再 durable
   - 显式 resume 失败

这意味着现在 chat 已经从“把 CLI thread 当唯一恢复依据”的旧模式，切到“以 Butler 自身 session scope 为主、vendor resume 为辅”的新模式。

### 9.4 当前 Butler 与 vendor runtime 的能力分工

就 chat 当前实现来说，0401 之后的能力分工已经比较清晰：

- vendor-native：
  - `session`
  - `resume`
  - `compact`
- Butler-owned：
  - `recent memory`
  - `local memory`
  - `skill exposure`
  - chat/frontdoor 连续性
  - 产品级 `collab / subagent / team continuity`

也就是说，chat 现在虽然可以借 `Codex/Claude CLI` 的 session 能力保留局部上下文，但产品级恢复已经不再押注 vendor 本地 thread 一定长期可用。

### 9.5 代码真源

本节结论当前以这些代码位置为准：

- `butler_main/chat/runtime.py`
  - 负责解析 `session_scope_id`，并把 execution metadata 回写到 chat receipt
- `butler_main/chat/engine.py`
  - 负责 chat 主链执行与 execution metadata 在 chat 侧的承接
- `butler_main/chat/light_memory.py`
  - 负责 recent scope、runtime session binding、recent finalize 与 backfill
- `butler_main/agents_os/execution/cli_runner.py`
  - 负责 vendor capabilities、resume durability 判定、degraded recovery、transparent reseed
- `butler_main/butler_flow/runtime.py`
  - 负责 flow 侧消费 `external_session`，并在 resume 失败后退回 fresh exec
- `butler_main/domains/campaign/codex_runtime.py`
  - 负责 campaign/runtime receipt 面透出 `external_session / recovery_state / vendor_capabilities`
- `butler_main/agents_os/runtime/runtime_request_state.py`
  - 负责 runtime request state 对外部 session / recovery 元数据的承接

### 9.6 0401 对 chat 的一句话状态判断

截至 0401 当天复验，chat 的最新状态可以概括为：

> 前台 chat 已恢复健康运行，recent memory 与 session binding 已接到现役主链；
> Butler 已拿回连续性主权，vendor resume 退为可选增强，而不是唯一恢复基础。
