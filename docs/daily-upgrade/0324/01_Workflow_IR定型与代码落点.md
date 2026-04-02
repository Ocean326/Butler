---
type: "note"
---
# 01 Workflow IR 定型与代码落点

日期：2026-03-24
时间标签：0324_0001
状态：已完成

## 本次落地结果

1. Butler 正式出现统一 `Workflow IR` 口径，真源落在：
   - 文档：`docs/runtime/WORKFLOW_IR.md`
   - 代码：`butler_main/orchestrator/workflow_ir.py`
   - 编译入口：`butler_main/orchestrator/compiler.py`
   - 测试：`butler_main/butler_bot_code/tests/test_orchestrator_workflow_ir.py`
2. `Workflow IR` 不再只是扁平 metadata 包装，已经具备：
   - `workflow / step / edge / role / artifact / handoff`
   - `compile_time / runtime / observability` 三层出口
   - `capability_package_ref / team_package_ref / governance_policy_ref`
   - `runtime_binding`
   - `input_contract / output_contract`
3. 保留了现有顶层兼容字段：
   - `runtime_key`
   - `agent_id`
   - `worker_profile`
   - `workflow_template`
   - `role_bindings`
   - `verification / approval / recovery`

## 关键决策

1. `Mission` 仍然是真正的控制面对象，`Workflow IR` 是 mission/node 编译后的流程对象。
2. `Workflow Session` 是运行态实例，不反向充当 compile-time schema。
3. `Artifact Registry` 继续保存实际 artifact 实例，`Workflow IR.artifacts` 只负责声明流程期望产物。
4. `Receipt` 继续是执行事实记录，`Workflow IR` 不吞并 receipt。
5. `WorkflowIR.from_dict()` 同时兼容旧扁平 payload 和新结构化 payload，避免今天把 orchestrator/VM 链路打断。

## 验收对应

1. 统一 workflow 语言：已完成。
2. 后续 `orchestrator`、`multi_agents_os`、framework compiler 可复用的 schema 入口：已建立。
3. package / contract / policy / runtime binding 的最小扩展位：已落代码。
4. 文档 + 代码 + 测试三落点：已建立。
