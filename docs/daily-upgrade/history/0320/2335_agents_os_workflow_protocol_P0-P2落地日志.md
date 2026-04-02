# 0320 agents_os workflow + protocol P0-P2 落地日志

更新时间：2026-03-20 23:35
时间标签：0320_2335

## 一、本轮落地结论

围绕 `docs/daily-upgrade/0320/2148_agents_os_workflow_protocol升级协议_场景级workflow与最小回执边界.md`，本轮已经把 `P0-P2` 的最小工程骨架落下来了：

- `P0`：补了最小协议层，形成 `step / handoff / decision` 回执边界
- `P1`：补了轻量 workflow 层，形成 `spec / cursor / checkpoint / projection`
- `P2`：给 research 补了 3 个场景资产包骨架，并把 manager 侧投影接上

当前状态可以概括成一句话：

> `agents_os` 已经从“只有 runtime core”推进到“runtime core + 最小 protocol + 场景级 workflow”的可接续形态，但仍然没有进入重型 orchestration 平台路线。

---

## 二、P0：protocol 层落地内容

本轮新增：

- `butler_main/agents_os/protocol/receipts.py`
- `butler_main/agents_os/protocol/__init__.py`

最小协议对象已落地：

- `StepReceipt`
- `HandoffReceipt`
- `DecisionReceipt`

这批对象当前承担的职责是：

- 作为 workflow 过程中的最小统一回执
- 作为 adapter、task ledger、runtime checkpoint 之间的通用接力面
- 为后续 `verification / approval / recovery` 进一步挂入主链预留稳定边界

兼容策略：

- 保留旧的 `step_result`
- 新增 `step_receipt / handoff_receipt / decision_receipt`
- Butler 侧继续能读旧字段，但新链路开始以 receipt 为准

---

## 三、P1：workflow 层落地内容

本轮新增：

- `butler_main/agents_os/workflow/models.py`
- `butler_main/agents_os/workflow/__init__.py`

本轮补齐的核心对象：

- `WorkflowStepSpec`
- `WorkflowSpec`
- `WorkflowCursor`
- `WorkflowCheckpoint`
- `WorkflowRunProjection`
- `FileWorkflowCheckpointStore`

同时做了两件边界收口：

1. `runtime/workflows.py` 收成兼容导出层
2. `runtime/host.py` 只负责 instance lifecycle + workflow checkpoint 持久化，不承接业务场景编排

本轮 workflow 解决的问题：

- 能表达一个场景 workflow 的 step 规格
- 能表达当前 cursor 位置
- 能把 step/handoff/decision 写成 checkpoint
- 能把运行过程投影成 `workflow_projection`

本轮明确还没做的事情：

- 通用 DAG/graph runner
- 场景级自动跳步/自动路由引擎
- 大一统 multi-agent orchestration

---

## 四、runtime 层配套升级

本轮配套改动：

- `butler_main/agents_os/runtime/instance.py`
- `butler_main/agents_os/runtime/instance_store.py`
- `butler_main/agents_os/runtime/host.py`

主要变化：

- `AgentRuntimeInstance` 新增 workflow 相关字段
  - `active_workflow_id`
  - `current_step_id`
  - `last_workflow_checkpoint_id`
  - `latest_decision`
- instance root 目录补上：
  - `workflow/`
  - `workflow/checkpoints/`
  - `workflow/workflow.json`
- `RuntimeHost.submit_run()/resume_instance()` 开始写 workflow checkpoint

这意味着当前 instance 已经不仅能记 session，也能记：

- 当前在哪个 workflow
- 当前 step 是什么
- 最近一次 workflow checkpoint 是什么
- 最近一次 decision 是什么

---

## 五、Butler heartbeat / ledger 适配

本轮已接线：

- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_workflow.py`
- `butler_main/butler_bot_code/butler_bot/services/task_ledger_service.py`

Heartbeat adapter 现在会输出：

- `workflow_spec`
- `workflow_cursor`
- `workflow_projection`
- `step_receipt`
- `handoff_receipt`
- `decision_receipt`

Task ledger 现在会记录：

- `workflow_cursor`
- `workflow_projection`
- `step_receipt`
- `handoff_receipt`
- `decision_receipt`

同时保持兼容：

- `step_result` 仍然保留

这样做的意义是：

- 旧的 heartbeat 和 ledger 逻辑不需要一次性推翻
- 新的 protocol/workflow 数据已经开始进入真存储面

---

## 六、P2：research 场景骨架落地

本轮新增场景资产目录：

- `butler_main/research/scenarios/brainstorm/`
- `butler_main/research/scenarios/paper_discovery/`
- `butler_main/research/scenarios/idea_loop/`

每个场景当前都补了最小骨架：

- `workflow/workflow.spec.json`
- `protocols/README.md`
- `assets/README.md`
- `outputs/README.md`

Manager 侧新增：

- `butler_main/research/manager/code/research_manager/services/scenario_registry.py`

当前 research manager 已经能：

- 根据 `unit_id` 反查 `scenario`
- 加载对应 `workflow.spec.json`
- 生成初始 `workflow_projection`
- 让 `heartbeat / talk / codex` 共用同一 scenario 资产定义

这一步的价值不在于“已经有完整 runner”，而在于：

- research 的多入口开始共享同一份场景资产包
- 未来 scenario runner 接进来时，不需要再反向拆 manager

---

## 七、导入边界修复

本轮过程中出现过一次真实的包级循环导入：

- `protocol.receipts -> runtime.contracts`
- `runtime.__init__ -> workflow`
- `workflow.models -> protocol.receipts`

最终处理方式不是“再加更多 re-export”，而是：

- 把 `butler_main/agents_os/__init__.py` 收成轻入口 + 惰性加载
- 把 `butler_main/agents_os/runtime/__init__.py` 收成 contracts 直出 + 其余对象惰性导出

结果是：

- `protocol / workflow / runtime` 三层的边界现在更干净
- 后面把 `workflow` 和 `protocol` 独立出去时，改造成本更低

---

## 八、验证情况

已通过的验证：

- `butler_main.butler_bot_code.tests.test_agents_os_protocols`
- `butler_main.butler_bot_code.tests.test_agents_os_runtime_host`
- `butler_main.butler_bot_code.tests.test_agents_os_wave2_adapters`
- `butler_main.butler_bot_code.tests.test_task_ledger_service`
- `butler_main.butler_bot_code.tests.test_research_manager_multi_entry`
- 手工 probe：
  - `RuntimeHost` create/load/submit/resume + workflow checkpoint
  - `TaskLedgerService` workflow projection 记录
  - `scenario_registry` workflow projection 加载

为了稳定回归，本轮顺手补了一个仓库内测试目录 helper：

- `butler_main/butler_bot_code/tests/_tmpdir.py`

并把本轮相关新测例从 `tempfile.TemporaryDirectory()` 切到仓库内可控工作目录，因此当前这批与 `P0-P2` 直接相关的测试已经可以在本机环境完整跑通。

---

## 九、当前边界判断

截至现在，`agents_os` 的层次已经初步收口成：

- `runtime`
  - run / worker / instance / host / session checkpoint
- `protocol`
  - step / handoff / decision 的最小回执边界
- `workflow`
  - spec / cursor / checkpoint / projection
- `research scenario`
  - 场景资产包 + workflow spec + 输出约束

这和 0320 的工程判断一致：

> 先做“可复用、可恢复、可接续”的 scenario workflow 层，而不是做一个重型 multi-agent 平台。

---

## 十、下一步建议

在这轮 `P0-P2` 之后，下一步最值得做的不是扩大全局框架，而是继续收口两件事：

1. 在 research 侧补一个极轻的 `scenario runner`
   - 只负责按 `workflow_cursor` 推进场景 step
   - 不抢 `RuntimeHost` 的 lifecycle 职责
2. 把 `verification / approval / recovery` 渐进挂进统一 protocol 面
   - 先以 re-export 或 adapter 挂接
   - 不急着大改现有目录

一句话总结：

> 本轮已经把 workflow/protocol 从“概念”推进成“真实文件、真实回执、真实投影、真实持久化”，下一轮应做的是让 scenario 真正跑起来，而不是把平台做大。
