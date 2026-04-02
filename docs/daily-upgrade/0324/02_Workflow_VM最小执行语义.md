---
type: "note"
---
# 02 Workflow VM 最小执行语义

日期：2026-03-24
时间标签：0324_0002
状态：已完成

## 目标

1. 在 `agents_os` 内部补出真正的最小 workflow execution engine。
2. 让 Butler 第一次具备“解释执行 workflow”的能力，而不是只会存 session 和 dispatch branch。
3. 给后续的 governance、package binding、durable execution 预留明确执行接口。

## 今日要完成的事

1. 定义最小 step kind：
   - `dispatch`
   - `verify`
   - `approve`
   - `join`
   - `finalize`
2. 定义最小 edge 语义：
   - `next`
   - `on_success`
   - `on_failure`
   - `resume_from`
3. 定义 cursor 推进规则。
4. 定义最小 checkpoint / resume 规则。
5. 在测试中跑通一条最小多步流。
6. 明确 side-effect boundary：
   - 哪些 step 允许外部执行
   - 哪些 step 只做状态推进
7. 明确 package / runtime binding 在执行期如何被解析。

## 重点限制

1. 先做最小可解释语义，不追求一次支持全部复杂图。
2. 先做 deterministic 核心，不先追求大量 host/runtime 兼容。
3. 先让调度、停机、恢复、授权语义有骨架，不先追求大而全 DAG 功能。

## 验收标准

1. `ExecutionRuntime` 不再只是 placeholder。
2. 至少存在一条真实多步执行测试。
3. 至少存在一条 resume 测试。
4. 至少有一版 step 执行与 runtime binding 解耦的接口。

## 完成回执

1. `agents_os.runtime.ExecutionRuntime` 已具备最小 workflow 解释执行能力。
2. 已落地最小 `step kind / edge / cursor / checkpoint / resume` 语义。
3. 已补真实多步执行测试与 approval gate 后 resume 测试。
4. 已验证 `agents_os -> orchestrator execution bridge -> workflow vm` 相关主链测试通过。
