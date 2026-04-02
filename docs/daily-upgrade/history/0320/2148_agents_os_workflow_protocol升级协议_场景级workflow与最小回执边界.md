# 0320 agents_os workflow + protocol 升级协议：场景级 workflow 与最小回执边界

更新时间：2026-03-20 21:48
时间标签：0320_2148

## 一、这份协议要解决什么

在今天前面的升级里，`agents_os` 已经补上了：

- `AgentRuntimeInstance`
- `FileInstanceStore`
- `RuntimeHost`
- session checkpoint / resume

research 线也已经补了：

- 多入口统一到 `ResearchManager`
- `heartbeat / talk / codex` 共用同一 research 业务核

现在真正需要明确的是下一层：

> **`instance` 之上，`workflow` 和 `protocol` 该怎么补，补到什么程度，长期又该怎么独立出来。**

这份文档只做三件事：

1. 仔细核查 `agents_os` 当前现状
2. 明确 `workflow` / `protocol` 的近期升级边界
3. 为将来的独立演进留出稳定 seam

`application_flow` 本轮只做概念维护，不进入代码级落地目标。

---

## 二、一句话工程决策

当前最合适的路线是：

1. **继续把 `agents_os` 的 runtime core 保持干净**
2. **补 `workflow`，但只做轻量场景级**
3. **补 `protocol`，但只做最小 receipt / handoff / decision 契约**
4. **让 `workflow` / `protocol` 以后能从 `runtime` 里自然独立出来**

一句话压缩：

> **Butler 下一步不是做重型 multi-agent 平台，而是把 `instance` 上面补成“可复用、可恢复、可接续”的场景工作流层，并把相关协议从一开始就按独立层来收口。**

---

## 三、agents_os 现状核查

## 3.1 当前已经稳定的部分：runtime core

从目录和代码看，`agents_os` 当前已经具备一个比较清晰的 runtime core 雏形：

- `runtime/contracts.py`
  - 定义 `RunInput / Run / RunResult / AcceptanceReceipt / WorkerResult`
- `runtime/kernel.py`
  - 定义 `WorkerRegistry / WorkflowRegistry / RuntimeKernel / SingleWorkerWorkflow`
- `runtime/instance.py`
  - 定义 `AgentRuntimeInstance`
- `runtime/instance_store.py`
  - 定义 file-based instance store
- `runtime/host.py`
  - 定义 `RuntimeHost`
- `runtime/session_support.py`
  - 定义 checkpoint / current checkpoint / session merge

这意味着 `agents_os` 已经不是只有“一次 execute”的内核，而是已经进入：

- run
- worker
- host lifecycle
- instance
- checkpoint / resume

这部分是当前最应该保护住的干净内核。

## 3.2 当前已经存在但还很薄的部分：workflow 雏形

`workflow` 现在并不是完全没有，而是已经有两层雏形：

### A. runtime 内的最小 workflow 抽象

位置：

- `butler_main/agents_os/runtime/workflows.py`

当前已存在：

- `WorkflowSpec`
- `WorkflowStepSpec`
- `StepResult`

当前能力只够表达：

- workflow id
- step 列表
- step kind
- process role
- step 执行结果

也就是说，它现在更像：

> **workflow projection 数据结构**

而不是：

> **独立的 workflow 层**

### B. Butler heartbeat 侧的 adapter projection

位置：

- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_workflow.py`

当前已存在：

- `ButlerHeartbeatWorkflowAdapter.build_workflow_spec()`
- `build_step_result()`
- `attach_plan_projection()`

这说明 heartbeat 已经开始把自身运行流投影成：

- generic workflow spec
- generic step result

这是对的，但它现在仍然只是：

- adapter 层投影
- 不是通用 workflow runner
- 不是场景独立 workflow 包

## 3.3 当前已经存在但分散的部分：protocol 雏形

当前 `protocol` 实际上也已经存在，只是散在多个子目录：

### runtime run 协议

- `runtime/contracts.py`
  - `AcceptanceReceipt`
  - run / worker / result / failure class / process role / step kind

### verification 协议

- `verification/contracts.py`
  - `VerificationReceipt`

### governance / approval 协议

- `governance/approval.py`
  - `ApprovalTicket`

### recovery 协议

- `recovery/contracts.py`
  - `RecoveryDirective`

也就是说，现在缺的不是“协议对象”，而是：

1. 缺统一命名面
2. 缺统一入口
3. 缺 step / handoff / decision 这几个最关键连接件
4. 缺一个明确判断：哪些协议属于 runtime，哪些属于 workflow，哪些属于 manager adapter

## 3.4 当前 research 接入状态

research 当前已经做到了：

- 多入口统一：`heartbeat / talk / codex`
- 单业务核：`ResearchManager`
- unit handler skeleton：`daily_paper_discovery / project_next_step_planning / progress_summary / idea_loop`

但 research 目前还没有真正接上：

- scenario-level workflow runner
- scenario checkpoint cursor
- scenario handoff / decision receipt 主链

所以 research 现在是：

> **入口和业务核统一了，但 workflow 层和 protocol 主链还没真正接上。**

---

## 四、当前缺口判断

## 4.1 workflow 最大缺口：只有“描述”，没有“场景执行语义”

当前 `WorkflowSpec / WorkflowStepSpec / StepResult` 解决的是：

- 让 heartbeat 等分支结果投影成通用结构

但它还没有解决：

- 下一步是什么
- 从哪一步 resume
- 哪一步需要 handoff
- 哪一步需要 decision gate
- 哪一步写 checkpoint cursor
- talk / heartbeat / direct invoke 如何接续到同一个 workflow state

也就是说，当前 workflow 还不是“业务控制层”，只是“运行结果投影层”。

## 4.2 protocol 最大缺口：协议对象分散，缺统一接力边界

当前已有的协议对象各自成立，但还缺一个统一接力面。

最明显的表现是：

- `AcceptanceReceipt`
- `VerificationReceipt`
- `ApprovalTicket`
- `RecoveryDirective`
- `StepResult.handoff_payload`

这些对象能表达局部语义，但还没有形成一套可串起来的主链。

现在真正需要补的是：

- `step_receipt`
- `handoff_receipt`
- `decision_receipt`

这三个对象补齐之后，现有 acceptance / verification / approval / recovery 才能被挂到统一主链上。

## 4.3 runtime host 最大缺口：能 resume run，不能 resume scenario workflow

`RuntimeHost.resume_instance()` 当前做的是：

- 找 checkpoint
- merge session snapshot
- 用 checkpoint 里的 `run_input` 再 submit 一次

这对 run 级恢复已经够了。

但对以后场景级 workflow 来说，还少：

- workflow cursor
- current step id
- decision state
- pending handoff
- stage-local artifacts

所以 `RuntimeHost` 当前适合继续做：

- instance lifecycle host

不适合现在就强行升级成：

- 通用 workflow orchestrator

---

## 五、这轮协议：workflow 和 protocol 分别怎么补

## 5.1 workflow 升级协议

本轮对 `workflow` 的要求，不是做大而全引擎，而是做成：

> **轻量、声明式、场景级、可恢复的控制流层**

### workflow 的职责边界

应负责：

- 场景阶段定义
- step 顺序与 gate
- step 输入输出结构
- handoff 点
- decision 点
- resume 点

不应负责：

- CLI provider 选择
- tool permission 细则
- manager 业务路由
- 具体 prompt 资产装载
- application catalog

### workflow 的近期最小形态

建议先抽象成以下对象：

- `ScenarioWorkflowSpec`
- `ScenarioWorkflowStep`
- `WorkflowCursor`
- `WorkflowCheckpoint`
- `WorkflowRunProjection`

其中最关键的是：

- `WorkflowCursor`

它至少要回答：

- 当前在哪个 step
- 上一轮 decision 是什么
- 下一步是什么
- 是否等待 handoff / approval / input

### workflow 的近期放置原则

从长期独立演进考虑，**不建议继续把 workflow 都塞在 `runtime/workflows.py` 一处增长**。

更合理的长期方向是：

```text
agents_os/
  workflow/
    spec.py
    cursor.py
    checkpoint.py
    projection.py
    runner.py
```

但为了不打断当前代码，可以分两步：

1. 先在 `runtime/workflows.py` 维持兼容导出
2. 后续把真实实现迁到 `agents_os/workflow/`
3. `runtime/__init__.py` 只做 re-export

这样可以保证：

- 当前测试和 adapter 不立即破
- 长期边界从现在开始就清楚

## 5.2 protocol 升级协议

本轮对 `protocol` 的要求，是：

> **先统一最小接力边界，不追求全覆盖协议体系。**

### protocol 第一批必须补的对象

建议只补四类最小协议：

1. `StepReceipt`
2. `HandoffReceipt`
3. `DecisionReceipt`
4. `AcceptanceReceipt`

其中：

- `AcceptanceReceipt` 已存在，可继续复用
- 新增重点是 `HandoffReceipt` 与 `DecisionReceipt`

### 这些协议的最低公共字段

建议至少包含：

- `workflow_id`
- `instance_id`
- `run_id`
- `step_id`
- `producer`
- `consumer`
- `status`
- `summary`
- `artifacts`
- `next_action`
- `failure_class`
- `metadata`

其中按对象再扩：

#### `StepReceipt`

- `process_role`
- `step_kind`
- `evidence`

#### `HandoffReceipt`

- `handoff_kind`
- `target_step_id`
- `payload_ref`
- `handoff_ready`

#### `DecisionReceipt`

- `decision`
- `decision_reason`
- `retryable`
- `resume_from`

### protocol 的近期放置原则

同样从长期独立考虑，建议逐步形成：

```text
agents_os/
  protocol/
    run.py
    step.py
    handoff.py
    decision.py
    acceptance.py
    verification.py
    approval.py
    recovery.py
```

当前已有对象可以逐步迁入或 re-export：

- `AcceptanceReceipt`
- `VerificationReceipt`
- `ApprovalTicket`
- `RecoveryDirective`

这一步的意义不是改名字，而是把“协议是第一层对象”这件事定下来。

---

## 六、长期独立规划：workflow / protocol 与 runtime 的关系

## 6.1 runtime 以后仍然只做运行时内核

长期边界应明确成：

- `runtime`
  - run
  - worker dispatch
  - instance
  - host lifecycle
  - session checkpoint
  - artifact / trace / context 最小运行设施

不把以下内容继续塞回 runtime：

- 业务场景 workflow
- manager-specific route policy
- scenario handoff schema
- research-specific decision taxonomy

## 6.2 workflow 以后作为独立控制层

长期边界应明确成：

- `workflow`
  - 场景控制流描述
  - workflow cursor / checkpoint
  - stage transition
  - resume semantics
  - projection to receipts

它应依赖 runtime，但不反过来要求 runtime 知道每个业务场景。

## 6.3 protocol 以后作为横切契约层

长期边界应明确成：

- `protocol`
  - step / handoff / decision / acceptance / verification / approval / recovery 的统一 contract

它的价值是：

- heartbeat 可写
- talk 可读
- manager 可决策
- host 可恢复
- task ledger 可投影

也就是说，protocol 是 workflow、runtime、manager、adapter 之间的横切接力面。

---

## 七、这轮不做什么

为了避免再走重平台路线，这轮明确不做以下事情：

1. 不做通用 DAG / graph orchestration engine
2. 不做 Butler 全局 multi-agent 平台
3. 不做 application marketplace / flow catalog
4. 不做 agent 自动生成 workflow 的执行器
5. 不把 heartbeat 当前 adapter 全量迁成新 workflow runner

这些都太早。

---

## 八、application_flow 这轮只做概念维护

`application_flow` 这轮不进入具体代码目标，只保留概念位。

当前统一定义为：

> **application_flow = 场景资产包 + workflow 规格 + 出口格式**

它现在只承担三个作用：

1. 帮我们区分“workflow 层”和“未来应用包层”不是一回事
2. 约束当前别把场景资产烤进 runtime
3. 为未来 agent 自生成 flow spec 预留术语

但这轮不做：

- `application_flow/` 包
- flow registry
- flow generator
- flow compiler

---

## 九、近期实施顺序

## P0：先把协议边界收口

优先级最高的是：

1. 补 `StepReceipt / HandoffReceipt / DecisionReceipt`
2. 统一与现有 `AcceptanceReceipt / VerificationReceipt / ApprovalTicket / RecoveryDirective` 的关系
3. 给 heartbeat projection 一个统一 receipt 主链

为什么先做这个：

- 没有 receipt 主链，workflow 以后还是会继续散在 adapter dict 里

## P1：再补 workflow 的独立 cursor / checkpoint

第二步再做：

1. 给场景 workflow 定义 cursor
2. 让 scenario checkpoint 不再只靠 `run_input`
3. 让 `RuntimeHost` 可被 workflow runner 调用，但不吞掉 workflow 语义

## P2：最后才接 research 场景

当协议与 workflow cursor 稳定后，再把 research 的 3 个场景逐步接入：

1. `brainstorm`
2. `paper_discovery`
3. `idea_loop`

这样不会让 research 反向绑架 core 抽象。

---

## 十、对当前代码的直接约束

从这份协议开始，新增代码默认遵守以下约束：

1. 新的场景控制流，不直接继续长在 `runtime/workflows.py`
2. 新的 receipt / handoff / decision 对象，不再散落到 manager / adapter 私有 dict
3. `RuntimeHost` 不承担业务场景编排，只承担 instance lifecycle
4. `agents_os_adapters/` 只做 Butler-specific 投影与接线，不承接协议真源
5. research 单元里的 prompt / specs / assets 不写进 runtime core

---

## 十一、当前结论

综合今天已经落下来的 `instance + host` 基线、heartbeat 的 workflow projection、research 的多入口同业务核结构，以及对未来独立演进的需求，当前最稳的升级路径是：

- **runtime core 继续保持轻**
- **workflow 开始独立成层，但先只做场景级**
- **protocol 开始独立成层，但先只做最小回执边界**
- **application_flow 只保留概念，不提前工程化**

一句话总结：

> **0320 之后，Butler 的 `agents_os` 应继续以 `runtime` 为硬内核，以 `protocol` 为横切契约，以 `workflow` 为场景控制层；三者分层推进，不再混长。**

---

## 十二、关联文件

- `butler_main/agents_os/README.md`
- `butler_main/agents_os/runtime/contracts.py`
- `butler_main/agents_os/runtime/workflows.py`
- `butler_main/agents_os/runtime/kernel.py`
- `butler_main/agents_os/runtime/host.py`
- `butler_main/agents_os/verification/contracts.py`
- `butler_main/agents_os/governance/approval.py`
- `butler_main/agents_os/recovery/contracts.py`
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_workflow.py`
- `butler_main/research/manager/code/research_manager/manager.py`
- `docs/daily-upgrade/0320/1506_research多入口同一业务核MVP落地.md`
- `docs/daily-upgrade/0320/1608_runtime_instance完善方案_最小字段目录与ConnectOnion补充启发.md`
- `docs/daily-upgrade/0320/1832_agents_os实例容器与RuntimeHost升级落地.md`
