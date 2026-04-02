---
type: "note"
---
# 03 Verification / Approval / Recovery 执行化

日期：2026-03-24
时间标签：0324_0003
状态：已完成

## 目标

1. 把 `verification / approval / recovery` 从结构字段推进为真实执行语义。
2. 让 Butler 的多 Agent 流从“能跑”开始迈向“可控、可恢复、可治理”。
3. 让治理层开始像内核能力，而不是业务后处理。

## 今日要完成的事

1. 明确 verification 的触发点、失败路径、回写点。
2. 明确 approval 的暂停点、等待态、恢复点。
3. 明确 recovery 的最小策略：
   - retry step
   - repair branch
   - workflow resume
4. 让这些对象开始影响 workflow cursor，而不只是被记录。
5. 明确 approval / verification 与 capability package 的关系：
   - 哪类能力默认需要 gate
   - 哪类恢复允许自动进行

## 验收标准

1. verification 不再只是 summary/receipt。
2. approval 不再只是 metadata。
3. recovery 不再只是文档口径。
4. 至少出现一条“被 gate 卡住后再恢复执行”的测试或伪闭环设计。

## 实际落点

1. `verification`
   - `OrchestratorService` 在 branch 成功后不再直接把 workflow session 提前终结。
   - verification required 时，session 会先进入 `verifying`，judge verdict 再决定 `completed / repairing / failed / awaiting_decision`。
   - verification skipped 时，会直接回写 `verification_skipped` 事件并把 session 收敛到 `completed`。
2. `approval`
   - approval gate 会把 node 推到 `blocked`、mission 推到 `awaiting_decision`，同时把 workflow session 状态写成 `awaiting_approval`。
   - `resolve_node_approval()` 不再只是清 metadata，而是会继续驱动 success path / recovery path，把 session 从 gate 态推进到最终态或恢复态。
3. `recovery`
   - recovery policy 现在区分 `retry`、`retry_step`、`repair`、`resume`，不再把它们全部压成同一个动作。
   - `retry_step / resume` 会复用已有 workflow session，并把 cursor 恢复到 `resume_from`。
   - `repair` 会新建 workflow session，形成真正的 repair branch 语义。
   - `disabled` 与 `unsupported` 已区分，默认编译器注入的 `kind: recovery` 不再被误判成 unsupported。
4. `workflow cursor`
   - workflow session 的 `status / active_step` 现在会被 approval / verification / recovery 驱动，不再只是 branch receipt 结束后写死。
   - session template 读取对额外字段改成容忍模式，避免 richer workflow IR 反向喂给 workflow session 时直接炸掉。

## 验收结果

1. 已补一条 approval gate 闭环测试：
   - `blocked -> awaiting_approval -> approve -> done/completed`
2. 已补两条 recovery 语义测试：
   - `retry_step` 复用同一 workflow session，并恢复到指定 step
   - `repair` 重新 dispatch 时创建新 workflow session
3. 已补 workflow IR 动作区分测试：
   - `retry_step` 与 `resume` 在 gate policy 中保持独立动作，不再被压扁成 `retry`

## 本次验证

1. `python -m py_compile butler_main/orchestrator/service.py butler_main/orchestrator/workflow_ir.py butler_main/multi_agents_os/templates/workflow_template.py butler_main/butler_bot_code/tests/test_orchestrator_core.py butler_main/butler_bot_code/tests/test_orchestrator_workflow_ir.py`
2. 通过带最小 `ExecutionRuntime` stub 的 `unittest` 定点跑通：
   - `butler_main.butler_bot_code.tests.test_orchestrator_core`
   - `butler_main.butler_bot_code.tests.test_orchestrator_workflow_ir`

## 剩余边界

1. 这次仍然是 orchestrator 侧的最小执行化，`agents_os` 内部通用 `ExecutionRuntime` 真正落地仍属于另一条主线。
2. workflow step 级 cursor 目前仍以 orchestrator 可控最小语义为主，还没有推进到完整 durable checkpoint / replay / generalized step VM。
