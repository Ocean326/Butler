# 0320 runtime instance 完善方案：最小字段 / 目录设计与 ConnectOnion 补充启发

更新时间：2026-03-20 16:08
时间标签：0320_1608

## 一、为什么要补这份方案

基于今天前面的判断，`agents_os` 当前的核心问题不是“没有 runtime 抽象”，而是：

- 已经有 `Run / Worker / Workflow / Trace / Context / Approval / Recovery / Verification` 这些零件
- 但还没有一个**可托管、可隔离、可恢复、可交接的 `Agent Runtime Instance`**

也就是说，Butler 现在还不太能自然做到：

- 给每个 agent 分配一套独立运行环境
- 为该 agent 绑定稳定的：
  - prompt / role 资产
  - memory backend
  - session 生命周期
  - approval / boundary
  - handoff 与产物区
  - trace / event 输出
  - recovery / resume 能力

所以，这份文档要解决的是：

1. **一个 `Agent Runtime Instance` 最少应该包含哪些字段**
2. **一个 `Agent Runtime Instance` 最少应该包含哪些目录**
3. **这些东西里哪些该进入 `agents_os` core，哪些该留在 manager adapter**
4. **除了 runtime instance 之外，ConnectOnion 还有哪些做法值得 Butler 学**

---

## 二、一句话定义

> **`Agent Runtime Instance` = 一个被 runtime host 托管的 agent 运行单元。它不是 prompt，也不是 worker，而是“一个 agent 在某个 session / profile / workspace / boundary 下的运行容器”。**

这个容器最少要回答七个问题：

1. 你是谁
2. 你绑定什么 prompt / profile
3. 你在哪个 workspace / storage 里运行
4. 你当前属于哪个 session / run
5. 你有哪些边界与审批规则
6. 你的中间产物与交接件放哪
7. 你挂了以后怎么恢复

---

## 三、最小字段设计

建议把 `Agent Runtime Instance` 至少拆成下面 8 组字段。

## 3.1 Identity：实例身份

最少字段：

- `instance_id`
- `agent_id`
- `agent_kind`
- `manager_id`
- `owner_domain`
- `created_at`
- `updated_at`
- `status`

说明：

- `instance_id`：实例主键，不等于 `agent_id`
- `agent_id`：逻辑角色名，例如 `heartbeat.executor.main`
- `agent_kind`：例如 `planner / executor / verifier / approval / talk`
- `manager_id`：实例归属哪个 manager
- `owner_domain`：例如 `heartbeat / research / talk`
- `status`：建议至少有 `idle / running / blocked / waiting_input / failed / retired`

为什么需要独立 `instance_id`：

- 同一个逻辑 agent 可以有多个实例
- 同一个 agent 可以在不同 session / workspace 下并存
- 后续做多 worker、重连、恢复时，不能只靠角色名识别

## 3.2 Profile：实例配置画像

最少字段：

- `prompt_profile_id`
- `runtime_profile`
- `memory_profile_id`
- `governance_profile_id`
- `handoff_profile_id`
- `tool_policy_profile_id`
- `model_preferences`

说明：

- `prompt_profile_id`：绑定哪套 prompt / role 资产
- `runtime_profile`：例如 `cli=codex`、`model=gpt-5.4`、`timeout=900`
- `memory_profile_id`：该 agent 使用怎样的 memory 策略
- `governance_profile_id`：审批、边界、风险级别、升级门槛
- `handoff_profile_id`：交接件结构与下游接收规则
- `tool_policy_profile_id`：允许哪些工具 / 哪些目录 / 哪些危险动作

关键点：

- profile 要成为一等对象，不能散在 prompt、cfg、manager dict、临时变量里
- 后续“同角色换不同模型 / 不同审批策略 / 不同记忆策略”时，才不需要继续堆 if/else

## 3.3 Session：实例会话视角

最少字段：

- `session_id`
- `parent_session_id`
- `active_run_id`
- `conversation_cursor`
- `last_checkpoint_id`
- `resume_token`
- `current_goal`
- `current_handoff_id`

说明：

- `session_id`：当前实例归属的会话主键
- `parent_session_id`：用于子 agent / 分叉 run / replay
- `active_run_id`：当前在跑哪一个 run
- `conversation_cursor`：当前对话 / 事件流进度
- `last_checkpoint_id`：最近可恢复点
- `resume_token`：后续如果做 host/client resume，会很有用
- `current_handoff_id`：当前要交给谁、交到哪一步

关键点：

- session 不是可有可无
- 没有 session 视角，memory、trace、handoff、recovery 都会散

## 3.4 Context：实例上下文视角

最少字段：

- `recent_context_refs`
- `memory_refs`
- `overlay_refs`
- `frozen_scope`
- `working_summary`
- `context_budget`

说明：

- `recent_context_refs`：近期上下文片段引用
- `memory_refs`：长期记忆引用
- `overlay_refs`：本轮附加约束、近期 lesson、风险提示
- `frozen_scope`：当前禁止越界的范围
- `working_summary`：为压缩恢复准备的中间摘要
- `context_budget`：该实例允许消耗的上下文预算

关键点：

- context 不能只靠 prompt 拼接
- runtime instance 必须知道自己“正带着哪些上下文资源”

## 3.5 Governance：实例边界与审批

最少字段：

- `approval_mode`
- `risk_level`
- `permission_set`
- `trust_level`
- `upgrade_policy`
- `verification_required`
- `maker_checker_required`

说明：

- `approval_mode`：例如 `auto / human_gate / session_gate / disabled`
- `risk_level`：例如 `low / medium / high / critical`
- `permission_set`：可执行能力边界
- `trust_level`：后续如果有 agent-to-agent / remote host，就会用到
- `upgrade_policy`：能否改 prompt、代码、配置、依赖
- `verification_required`：结果是否必须验收
- `maker_checker_required`：是否必须提议者与批准者分离

关键点：

- 这些字段不该埋在自然语言里
- 它们应该成为 runtime 读得懂、执行得动的结构化配置

## 3.6 Artifacts / Handoff：产物与交接

最少字段：

- `artifact_root`
- `handoff_root`
- `draft_root`
- `publish_root`
- `last_artifact_ids`
- `last_handoff_receipt_id`

说明：

- `artifact_root`：运行中所有中间产物
- `handoff_root`：交接件区
- `draft_root`：未确认产物
- `publish_root`：已批准、可提升的结果
- `last_handoff_receipt_id`：最近一次交接回执

关键点：

- “交接产区”必须显式存在
- 否则 branch 输出、verify 结果、approval 结果、promote 结果会继续混在 dict 和日志里

## 3.7 Observability：实例可观测性

最少字段：

- `trace_path`
- `event_stream_path`
- `metrics_path`
- `last_heartbeat_at`
- `last_error`
- `health_state`

说明：

- `trace_path`：结构化 trace
- `event_stream_path`：后续可供前端 / CLI / replay 消费
- `metrics_path`：延迟、fallback、retry、degrade 等指标
- `health_state`：`healthy / degraded / stale / dead`

关键点：

- 没有 observability，就没有真正的 runtime instance，只是运行中的对象

## 3.8 Recovery：实例恢复信息

最少字段：

- `recovery_policy_id`
- `retry_budget`
- `backoff_policy`
- `stale_after_seconds`
- `degrade_strategy`
- `replayable`

说明：

- `recovery_policy_id`：绑定哪套恢复策略
- `retry_budget`：剩余重试额度
- `backoff_policy`：退避策略
- `stale_after_seconds`：多久视为卡死
- `degrade_strategy`：失败时是否允许 status-only / pause / escalate
- `replayable`：是否允许 replay / smoke 重放

---

## 四、建议的数据结构草案

下面是一版面向 Butler / `agents_os` 的最小对象草案。

```python
@dataclass(slots=True)
class AgentRuntimeInstance:
    instance_id: str
    agent_id: str
    agent_kind: str
    manager_id: str = ""
    owner_domain: str = ""
    status: str = "idle"
    created_at: str = ""
    updated_at: str = ""

    prompt_profile_id: str = ""
    memory_profile_id: str = ""
    governance_profile_id: str = ""
    handoff_profile_id: str = ""
    tool_policy_profile_id: str = ""
    runtime_profile: dict[str, Any] = field(default_factory=dict)
    model_preferences: dict[str, Any] = field(default_factory=dict)

    session_id: str = ""
    parent_session_id: str = ""
    active_run_id: str = ""
    conversation_cursor: str = ""
    last_checkpoint_id: str = ""
    resume_token: str = ""
    current_goal: str = ""
    current_handoff_id: str = ""

    recent_context_refs: list[str] = field(default_factory=list)
    memory_refs: list[str] = field(default_factory=list)
    overlay_refs: list[str] = field(default_factory=list)
    frozen_scope: list[str] = field(default_factory=list)
    working_summary: str = ""
    context_budget: dict[str, Any] = field(default_factory=dict)

    approval_mode: str = "human_gate"
    risk_level: str = "medium"
    permission_set: dict[str, Any] = field(default_factory=dict)
    trust_level: str = "local"
    upgrade_policy: dict[str, Any] = field(default_factory=dict)
    verification_required: bool = True
    maker_checker_required: bool = False

    roots: dict[str, str] = field(default_factory=dict)
    last_artifact_ids: list[str] = field(default_factory=list)
    last_handoff_receipt_id: str = ""

    trace_path: str = ""
    event_stream_path: str = ""
    metrics_path: str = ""
    last_heartbeat_at: str = ""
    last_error: str = ""
    health_state: str = "healthy"

    recovery_policy_id: str = ""
    retry_budget: int = 0
    backoff_policy: dict[str, Any] = field(default_factory=dict)
    stale_after_seconds: int = 0
    degrade_strategy: str = ""
    replayable: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)
```

关键判断：

- 这不是 `Run`
- 这不是 `Session`
- 这不是 `Worker`
- 这是比三者更稳定的“实例容器”

---

## 五、最小目录设计

建议在 `agents_os/run/instances/` 下管理实例目录。

推荐目录：

```text
butler_main/agents_os/run/
  instances/
    <instance_id>/
      instance.json
      profile.json
      status.json
      session/
        session.json
        checkpoints/
        overlays/
      context/
        working_summary.md
        recent_refs.json
        memory_refs.json
      traces/
        events.jsonl
        latest_trace.json
        metrics.json
      artifacts/
        drafts/
        handoff/
        published/
      approvals/
        tickets/
        decisions/
      recovery/
        directives/
        replay/
      workspace/
      inbox/
      outbox/
```

## 5.1 各目录职责

- `instance.json`
  - 该实例的全量元信息快照
- `profile.json`
  - prompt / memory / governance / runtime profile
- `status.json`
  - 当前状态、active_run、health、last_error
- `session/`
  - 当前会话、checkpoint、overlay
- `context/`
  - 当前工作摘要、上下文引用
- `traces/`
  - 结构化 trace、事件流、指标
- `artifacts/drafts/`
  - 未经验证或未批准产物
- `artifacts/handoff/`
  - 交接件
- `artifacts/published/`
  - 已提升结果
- `approvals/`
  - 审批票据与决议
- `recovery/`
  - 恢复指令、replay 材料
- `workspace/`
  - 实例运行期临时工作区
- `inbox/`
  - 上游给该实例的输入件
- `outbox/`
  - 该实例发给下游的输出件

## 5.2 为什么需要 `inbox / outbox`

这是 Butler 后续走多 agent / 多 manager 时很关键的点：

- 没有 `inbox / outbox`，handoff 还会继续变成临时 dict
- 有了 `inbox / outbox`，你才更容易把：
  - talk -> planner
  - planner -> executor
  - executor -> verifier
  - verifier -> approval
  - approval -> promote
  做成稳定边界

---

## 六、哪些该进 `agents_os`，哪些该留在 adapter

## 6.1 应进入 `agents_os` core 的

- `AgentRuntimeInstance` contract
- instance store / lifecycle manager
- session container contract
- artifact / handoff root contract
- approval / recovery / verification 的标准目录与数据结构
- event stream / trace stream contract
- runtime host API

## 6.2 仍应留在 Butler adapter 的

- heartbeat 的具体 prompt 资产
- `task_ledger` 细节与字段
- 飞书 / tell_user 接口细节
- Butler 的 workspace 命名方式
- Butler 当前分支任务组织方式
- research / talk / heartbeat 各自的业务真源

一句话：

> `agents_os` 负责实例容器和运行壳；manager adapter 负责把 Butler 业务语义挂进去。

---

## 七、建议新增的 runtime host 接口

仅有 `RuntimeKernel.execute()` 还不够，建议下一步最少补下面这些 host 级接口：

```python
create_instance(profile) -> AgentRuntimeInstance
load_instance(instance_id) -> AgentRuntimeInstance
update_instance(instance_id, patch) -> AgentRuntimeInstance
submit_run(instance_id, run_input) -> RunResult | RunHandle
stream_events(instance_id, run_id=None) -> EventStream
load_session(instance_id) -> dict
resume_instance(instance_id, checkpoint_id=None) -> RunResult | RunHandle
retire_instance(instance_id) -> None
```

这几个接口的意义是：

- `kernel` 负责跑一次
- `host` 负责托管一个 agent instance 的生命周期

---

## 八、与当前 `agents_os` 现状的差距

对照目前代码，差距主要有 5 点：

1. **有 `Run`，但没有 `AgentRuntimeInstance`**
   - 当前核心对象更偏单次执行，不偏实例容器

2. **有 `WorkflowSpec`，但没有 workflow 驱动的实例状态机**
   - 现在 workflow 更多是描述，不是 host 级运行机制

3. **有 `ApprovalTicket / RecoveryDirective / VerificationReceipt`，但没接入实例生命周期**
   - 它们还是横向数据结构，不是实例主链一部分

4. **有 `trace / run_state` 文件能力，但没有实例根目录**
   - 状态落点还是分散的

5. **有 CLI runner，但没有 per-instance runtime profile 装配层**
   - 还不能标准化创建“带 profile 的 agent 容器”

---

## 九、ConnectOnion 除了这点以外，还值得学什么

除了“把 Agent Host 当成独立 runtime”之外，ConnectOnion 还有 8 个值得 Butler 学的点。

## 9.1 事件优先，而不是结果优先

ConnectOnion 最值得学的不是 `/input -> result`，而是：

- `thinking`
- `tool_call`
- `tool_result`
- `approval_needed`
- `ask_user`
- `complete`
- `OUTPUT`

也就是说，它把**执行过程**做成了一等协议。

Butler 值得学的是：

- 不要只存 `summary`
- 要把“过程事件”稳定下来，成为 CLI / UI / replay / debug 共用语言

## 9.2 前端消费事件，不直接绑定业务实现

ConnectOnion 的正式前端不在当前仓库，但它有个很重要的设计思路：

> 前端不是 agent 的耦合层，前端只是事件消费者。

这对 Butler 很重要，因为你后面无论接：

- terminal
- local web
- 飞书
- dashboard

都不该重新发明一套状态语言。

## 9.3 Trust / Approval 要在 host 边界做

ConnectOnion 把 trust、signature、approval 放在 host 层，而不是塞进 agent 内部。

Butler 值得学的是：

- 高风险动作不要主要靠 prompt 提醒
- 要靠结构化 boundary 和 runtime gate

## 9.4 Session merge / reconnect 思路很强

ConnectOnion 的一个先进点是：

- session 不是一次性上下文
- client session 和 server session 可以 merge
- 断线后还能继续恢复结果

Butler 值得学的是：

- session 不只是 memory key
- session 应成为恢复、handoff、replay 的主轴

## 9.5 同步 agent + 异步 transport 的桥接做法很实用

ConnectOnion 没强行把所有 agent 重写成 async actor，而是：

- agent 仍然按同步思维执行
- transport 层负责 websocket/queue 桥接

Butler 值得学的是：

- 不必为了“架构漂亮”立刻全 async
- 先把 runtime host 和 event bridge 立住，更符合现阶段收益

## 9.6 直连优先，relay 兜底

ConnectOnion 的网络层思路是：

- 能直连就直连
- 不行再走 relay

Butler 未来如果要支持：

- 多机器
- 多入口
- 本地与远程切换

这个思路非常值得学。

## 9.7 文档页不是协议真相，测试与源码才是

ConnectOnion 的 `/docs` 页面和真实签名要求存在偏差，这反而提醒了一件很重要的事：

> runtime 协议的真源必须是 contract + tests，不是 demo 页。

Butler 后续如果做 dashboard / docs，一定要避免“页面说一套，runtime 实际跑另一套”。

## 9.8 它真正 productize 的是“经验壳”，不是模型本身

这正好对上你今天反复提到的感觉：

- best practice 不主要在模型里
- 更在运行壳、审批、上下文治理、重连、session、工具交互、事件协议里

ConnectOnion 的启发是：

> 未来 Butler 的竞争力也不会只来自 prompt，而会来自 runtime / harness / governance 这层经验壳。

---

## 十、Butler 下一步最建议补的 3 个动作

## 10.1 Wave A：补 `AgentRuntimeInstance` contract + instance store

目标：

- 让实例成为一等对象
- 不再只围绕 `Run` 设计

产出建议：

- `agents_os/runtime/instance.py`
- `agents_os/runtime/instance_store.py`

## 10.2 Wave B：补 runtime host 生命周期接口

目标：

- 从 `execute()` 升级到 `host / submit / resume / retire`

产出建议：

- `agents_os/runtime/host.py`

## 10.3 Wave C：让 approval / verification / recovery 真正接到实例主链

目标：

- 不再只是 dataclass
- 真正成为实例运行的必经环节

产出建议：

- `agents_os/runtime/workflow_runner.py`
- 或在现有 `kernel` 外再加一个轻量 harness runner

---

## 十一、一句话结论

> `Agent Runtime Instance` 的本质，是把 agent 从“可调用能力”升级成“可托管运行单元”；而 ConnectOnion 最值得 Butler 学的，不只是 host runtime 本身，更是它把事件、信任、session、审批、恢复这些经验做成了运行时基础设施。
