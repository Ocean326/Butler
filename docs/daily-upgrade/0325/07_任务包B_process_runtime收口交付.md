# 07 任务包 B process runtime 收口交付

日期：2026-03-25
时间标签：0325_0007
状态：已迁入完成态 / process runtime 输入冻结

## 这包真正要解决什么

这包不是“再做一个 workflow engine”，而是把当前灰区里的第二层真语义正式收回：

1. 把“包裹在单 agent run 之外、但又不是 mission 控制面”的通用流程语义统一归第 2 层。
2. 把 `workflow / session / governance / collaboration substrate` 从散落状态收口成正式的 `runtime_os.process_runtime`。
3. 让 `orchestrator` 从“兼管流程细节”回到第三层 control plane。

## 主线思想

1. 整个系统先按 `3 -> 2 -> 1` 冻结：
   - `3 = orchestrator / control plane`
   - `2 = runtime_os / process runtime`
   - `1 = runtime_os / agent runtime`
2. 任务包 B 只负责第 2 层。
3. 第 2 层只回答：
   - 一个通用多步过程如何 dispatch
   - 如何 gate
   - 如何 pause / resume
   - 如何 finalize
4. 第 2 层不回答：
   - 为什么要跑这个 mission
   - 哪个 node 现在应该激活
   - 用户/产品域流程到底是什么

## 当前最关键的混叠点

1. `agents_os/runtime/execution_runtime.py`
   - 这里已经在承载第二层语义，但名字和归属都不对。
2. `agents_os/workflow/*`
   - 这些是第二层 workflow schema，不该继续被看成第一层 runtime 的附属物。
3. `multi_agents_os/session/*`
   - 这些其实已经是第二层 runtime substrate，而不是另一个独立“多人系统”。
4. `orchestrator/service.py`
   - approval / verification / recovery 真执行语义还在这里泄漏。

## 正式边界

### 第 2 层应正式持有

1. workflow schema：
   - `WorkflowSpec`
   - `WorkflowCursor`
   - `WorkflowCheckpoint`
2. process engine：
   - `dispatch`
   - `verify`
   - `approve`
   - `join`
   - `finalize`
   - `resume`
3. governance runtime：
   - `DecisionReceipt`
   - `ApprovalTicket`
   - `RecoveryDirective`
4. session substrate：
   - `WorkflowSession`
   - `SharedState`
   - `ArtifactRegistry`
   - `WorkflowBlackboard`
   - `Mailbox`
   - `JoinContract`
5. capability binding：
   - step 到 capability 的运行期绑定

### 第 2 层明确不应持有

1. `Mission / MissionNode / Branch / LedgerEvent`
2. research / background / chat 领域语义
3. CLI/单次执行 host 的第一层对象

## 未来目录建议

```text
butler_main/runtime_os/process_runtime/
  workflow/
  engine/
  governance/
  session/
  bindings/
  contracts.py
```

## 首批文件归属建议

| 当前文件 / 文件组 | 未来归属 | 动作类型 |
| --- | --- | --- |
| `butler_main/agents_os/runtime/execution_runtime.py` | `runtime_os/process_runtime/engine/` | 必须改语义 |
| `butler_main/agents_os/workflow/*` | `runtime_os/process_runtime/workflow/` | 只挪位置 |
| `butler_main/multi_agents_os/session/*` | `runtime_os/process_runtime/session/` | 先兼容转发，后回收真源 |
| `butler_main/multi_agents_os/templates/*` | `runtime_os/process_runtime/session_or_templates/` | 先兼容转发 |
| `butler_main/multi_agents_os/factory/*` | `runtime_os/process_runtime/bindings_or_factory/` | 先兼容转发 |
| `butler_main/orchestrator/service.py` 中 gate 语义 | `runtime_os/process_runtime/governance/` | 必须改语义 |

## 首批最值得动的 5 个点

1. 把 `ExecutionRuntime` 的真实归属从 `agents_os.runtime` 明确切到第 2 层。
2. 让 `agents_os.runtime.__all__` 不再继续暴露 `WorkflowSpec / WorkflowCursor / WorkflowCheckpoint / ExecutionRuntime`。
3. 给 `runtime_os.process_runtime` 建立更清楚的目标目录和稳定导出面。
4. 把 `multi_agents_os/session/*` 明确改写成“兼容壳指向第 2 层”，而不是继续作为第二总名。
5. 给 approval / verification / recovery 建立第 2 层的正式 contract 名，而不是继续借 `orchestrator` 私有 helper 表达。

## 非目标

1. 不做重 BPM 引擎。
2. 不在这里重写 orchestrator 控制面。
3. 不在这里扩写 research 业务流。
4. 不要求一天内把所有 gate 逻辑全部物理搬完。

## 验收口径

1. 第 2 层的正式边界被写清。
2. 第 2 层目标目录与导出面被写清。
3. 至少指出 3-6 个最先该动的文件，并区分：
   - 只挪位置
   - 需要改语义
4. 明确指出哪些符号必须从第 1 层导出面撤出。
5. 明确给出从 `orchestrator/service.py` 回收 gate 真语义的路径。
