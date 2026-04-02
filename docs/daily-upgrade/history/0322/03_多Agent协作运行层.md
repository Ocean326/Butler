---
type: "note"
---
# 03 多 Agent 协作运行层

日期：2026-03-22\
时间标签：0322_0100\
最后修改时间：2026-03-22 09:43:44\
状态：进行中

## 主线

1. 这层的定位固定为：位于 `AgentRuntime` 之上、`orchestrator` 之下的局部协作运行层。

2. 这页从现在开始只负责推进 `butler_main/multi_agents_os/`，不再承担 orchestrator 主线接线叙事。

3. 它解决的是“多角色协作会话如何被装配和维护”，不解决系统级任务调度，也不接管前台产品路由。

4. 它的第一批消费者仍优先面向 `research scenario` 和 `orchestrator node`，但“怎么接进去”归 `04_Orchestrator主线接管.md` 负责。

## 当前状态

基于 `0321/2348_多Agent协作运行层_V0设计稿.md`，当前已经明确：

1. 最小对象集：`WorkflowTemplate`、`RoleBinding`、`WorkflowSession`、`SharedState`、`ArtifactRegistry`、`WorkflowFactory`。

2. 代码落点固定为 `butler_main/multi_agents_os/`，作为 `agent_os` 之上的共享中间层。

3. 与 `orchestrator` 的分层：`orchestrator` 负责系统级长期控制，这层只负责局部协作环境装配。

4. 与 `research` 的分层：`ScenarioRunner` 仍是 driver，需要多角色协作时再由这层把模板和 instance state 装成协作 session。

## 成熟项目参考

本轮对照了几类已有一手文档的成熟 multi-agent / workflow 项目，用来校正 `multi_agents_os` 的推进边界：

1. `OpenAI Agents SDK`

* 它刻意把原语压到很少：`Agents`、`Agents as tools / Handoffs`、`Guardrails`，并明确把多 agent 常见模式压成两类：`manager` 持有控制权，或 `handoff` 让专家 agent 接管当前回合。

* 对 `03` 的直接启发是：`multi_agents_os` 应继续保持少原语，优先把 `session`、`role binding`、`delegation boundary` 收稳，而不是先长出大而全调度平台。

2. `CrewAI Flows`

* 它把 workflow 明确做成结构化、事件驱动的 flow，并强调 `state management`、`persistence`、统一 memory 接口是 flow 层的基础能力。

* 对 `03` 的直接启发是：`WorkflowSession` 不能只会创建，下一步应补 `load/store`、最小 `event log`、状态 schema 与持久化边界；但 memory 仍应保持可注入，不应把 Butler 私有记忆直接硬塞进 `multi_agents_os`。

3. `LangGraph Supervisor`

* 它把 multi-agent supervisor 定义为“中心 supervisor 负责通信流和任务委派”，并把 `message history management`、`checkpointer/store`、多级 supervisor hierarchy 都做成可配置项。

* 对 `03` 的直接启发是：`multi_agents_os` 后续应提供可配置的 `history/output mode` 与持久化注入点，而不是把消息历史策略和存储策略写死在 session 对象里。

4. `AutoGen Magentic-One`

* 它把 lead orchestrator、`Task Ledger`、`Progress Ledger`、team composition 分得很清：orchestrator 负责高层规划、分派、追踪与纠偏，team 负责执行具体子任务。

* 对 `03` 的直接启发是：ledger、outer loop、progress governance 应继续留在 `orchestrator`，不应回灌进 `multi_agents_os`；`multi_agents_os` 只保留“局部团队会话容器”的职责。

5. `SuperAgentX`

* 它强调 goal-oriented multi-agents、`Parallel / Sequential / hybrid` 通信模式、contextual memory，以及独立于 agent 本体的统一控制面、观测与治理。

* 对 `03` 的直接启发是：`driver_kind`、`policy_refs`、`capability_id` 这类字段应继续保持可扩展，好承接未来并行/串行/混合驱动；但观测、治理、统一策略面仍不应收进 `multi_agents_os` 本体。

## 当前阶段结论

1. `multi_agents_os` 现在走“薄中间层”方向是对的，和成熟项目的共识一致：先稳住少数原语，再让上层消费。

2. `03` 下一步该补的是：`session load/store`、最小 `event log`、history/output mode、可注入持久化边界。

3. `03` 明确不该补的是：mission ledger、全局调度、后台治理、统一控制面，这些继续归 `orchestrator` 或更上层控制面。

4. 因此，本页后续应继续把 `multi_agents_os` 做成“可装配、可恢复、可被消费”的局部协作运行层，而不是第二个 orchestrator。

## 薄中间层实施计划

本页后续按“只提供必要基础设施 + 装配，不长出调度系统”的顺序推进。

### P0 边界冻结

1. 固定 `multi_agents_os` 只提供六类核心对象与最小装配入口：`WorkflowTemplate`、`RoleBinding`、`WorkflowSession`、`SharedState`、`ArtifactRegistry`、`WorkflowFactory`。
2. 固定它不负责：mission scheduler、branch budget、task ledger、global mailbox、后台治理、统一控制面。
3. 固定消费关系：`research` 与 `orchestrator` 都只能消费它的 session/bundle/store 接口，不能把各自私有状态机反灌进来。

对应文件：
- `butler_main/multi_agents_os/__init__.py`
- `butler_main/multi_agents_os/templates/`
- `butler_main/multi_agents_os/bindings/`
- `butler_main/multi_agents_os/session/`
- `butler_main/multi_agents_os/factory/`

### P1 Session Store

1. 增加独立的 `FileWorkflowSessionStore`，把当前 factory 里的直接 JSON 落盘抽成正式 store。
2. store 只负责 `save / load / exists / list`，不承担 orchestrator 语义。
3. 继续沿用当前 session 目录布局，不为了 store 抽象重写目录结构。

建议文件：
- `butler_main/multi_agents_os/session/session_store.py`
- `butler_main/multi_agents_os/session/__init__.py`
- `butler_main/multi_agents_os/factory/workflow_factory.py`

验收点：
- 已创建 session 能被稳定重载。
- 调用方不需要手写路径拼接来读取 `session.json`。

### P2 Event Log

1. 增加最小 `FileWorkflowEventLog`，只记录 session 级局部事件，不记录系统级 ledger。
2. 事件种类先限制在：`session_created`、`state_patched`、`artifact_added`、`active_step_changed`。
3. event log 只解决“局部协作会话发生了什么”，不解决任务治理与全局追踪。

建议文件：
- `butler_main/multi_agents_os/session/event_log.py`
- `butler_main/multi_agents_os/session/__init__.py`
- `butler_main/multi_agents_os/factory/workflow_factory.py`

验收点：
- 新建 session 时能写入 `session_created`。
- 对 shared state / artifact registry 的最小变更能留下局部事件轨迹。

### P3 Recovery-Oriented Factory

1. 给 `WorkflowFactory` 补 `load_session()` 或等价读取入口，返回完整的 session bundle，而不只返回单个 `WorkflowSession`。
2. bundle 至少包含：`template`、`session`、`shared_state`、`artifact_registry`。
3. factory 继续只负责 assemble / load，不负责 advance / route / dispatch。

建议文件：
- `butler_main/multi_agents_os/factory/workflow_factory.py`
- 必要时新增 `butler_main/multi_agents_os/factory/session_bundle.py`

验收点：
- 一次 `create_session()` 生成的会话，后续可通过 factory 直接恢复为可消费 bundle。
- `orchestrator` / `research` 消费者不需要知道底层 JSON 文件布局。

### P4 最小消费契约

1. 为上层调用者固定最小消费面：创建 session、加载 session、patch shared state、追加 artifact、读取 event log。
2. `driver_kind`、`policy_refs`、`capability_id` 继续保持可扩展，但不提前长出重型策略引擎。
3. 如需补 `history_mode / output_mode`，只做轻量字段或 metadata 约定，不做复杂消息系统。

建议文件：
- `butler_main/multi_agents_os/factory/workflow_factory.py`
- `butler_main/multi_agents_os/session/shared_state.py`
- `butler_main/multi_agents_os/session/artifact_registry.py`
- `butler_main/multi_agents_os/session/session_store.py`
- `butler_main/multi_agents_os/session/event_log.py`

验收点：
- 上层调用方可以只依赖 `multi_agents_os` 的公开接口完成“装配 + 恢复 + 最小回写”。
- 不需要直接操作底层文件，也不需要把 orchestrator 私有逻辑带进来。

## 立即施工顺序

1. 先做 `P1 Session Store`，把当前直接落盘收口成正式 store。
2. 再做 `P3 Recovery-Oriented Factory`，让 factory 真正具备 create/load 成对能力。
3. 再做 `P2 Event Log`，补局部会话级最小轨迹。
4. 最后做 `P4 最小消费契约` 的导出与测试收口。

## 本页明确不做

1. 不做 node dispatch、branch execute、judge、retry，这些继续归 `orchestrator`。
2. 不做 team manager、supervisor loop、全局消息总线。
3. 不做 Butler 私有 memory/runtime 的整包迁入。
4. 不做为了抽象而抽象的新平台层。
## 当前缺口

1. `template / session / factory` 的字段口径还需要继续收口。

2. store / session 持久化协议还没有稳定到长期版本。

3. 还没有把 `SharedState`、`ArtifactRegistry` 的最小协议沉淀成稳定消费面。

4. 当前仍是 V0 运行层，不允许被误判成后台主 runtime。

## 今日计划

1. 继续只围绕 `butler_main/multi_agents_os/` 推进，不把任务扩散回 orchestrator 主线。

2. 优先收口 `template / role_binding / workflow_session / workflow_factory` 四类对象。

3. 补足 session 落盘、对象导出、最小恢复读取这类中间层能力。

4. 保持“可被 orchestrator 消费”，但不在本页继续书写 orchestrator 接线施工细节。

## 明确暂缓

1. 暂缓把这层直接塞进 `agent_os`。

2. 暂缓把它扩成完整局部调度引擎、mailbox 系统或重型 MAS 平台。

3. 暂缓让它反向定义前台路由和系统级 mission 模型。

4. 暂缓在这页继续承担 orchestrator 的 branch dispatch / runner / ledger 接线描述。

## 验收标准

1. 今天对这层的记录必须能一句话说清：它是 `butler_main/multi_agents_os/` 的局部协作运行层，不是顶层 runtime。

2. 必须能一句话说清：它服务 `research` 与 `orchestrator node`，但不负责系统级接线。

3. 后续任何实现都不得和 `04_Orchestrator主线接管.md` 的后台主线职责重叠。

## 关联协议

- 三方连通约束统一参考  5_Orchestrator+MultiAgentOS+Research连通协议.md。

## 追加记录

### 2026-03-22 01:00

* 依据 `0321/2348_多Agent协作运行层_V0设计稿.md` 将这条线正式纳入 `0322` 的 `1+N`。

* 定位固定为 `AgentRuntime` 与 `orchestrator` 之间的中间层架构副线。

### 2026-03-22 当前追加

* 本页口径正式收紧为：只推进 `butler_main/multi_agents_os/`，不再承担 orchestrator 主线接线叙事。

* `orchestrator -> workflow session` 的消费接线、验收与 runner 归属，统一转交 `04_Orchestrator主线接管.md`。

* 本页后续只记录对象模型、session 装配、factory 落点、shared state 与 artifact registry 等中间层收口动作。

⠀


