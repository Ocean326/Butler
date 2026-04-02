---
type: "note"
---
# 04 端到端 Demo 与验收口径

日期：2026-03-25
时间标签：0325_0004
状态：已迁入完成态 / 闭环验收口径保留

## 目标

1. 为 `0323-0325` 的工作准备一个最小端到端 demo 目标。
2. 把“做了很多骨架”收口成“能展示一条完整路径”。
3. 把命名迁移、`process runtime` 收口、`orchestrator control plane` 收缩三路的复核尾项吸收到同一个 closure 包里，确保 D 完成即可收总任务。

## 新定位

1. `Lane D` 不再只是 demo 跟随。
2. 它现在是 `0325` 的最终集成与验收收口包。
3. 它负责消费前三路边界结论，并补齐 `observe/query/smoke/tests/compat` 这一侧的集成尾项。

## 最小 demo 路径

1. 输入一个 mission。
2. 指定一个 framework profile。
3. 编译成 Butler Workflow IR。
4. 解析 package / contract / runtime binding。
5. 进入 workflow VM 执行。
6. 产出 artifacts / receipts。
7. 如中断则 resume。
8. 回写 orchestrator mission / branch / node 状态。

## 验收标准

1. 有一条完整的端到端链路。
2. 有明确的可演示对象，而不只是文档和模型。
3. 演示链路中至少有一个 approval / verification / recovery 或 package binding 的真实节点。
4. A/B/C 的未完成项已经被吸收到单一 `closure checklist`，并且完成或被明确判定为“不阻塞总验收”的后置项。
5. D 完成后，不再需要额外新开“总收口包”。

## 范围边界

### 这一路必须回答

1. 到 `2026-03-25` 结束时，什么算“这四路真的接起来了”。
2. demo 用什么输入、什么 framework profile、什么事件序列来证明不是纸面工程。
3. smoke 和验收要挂到哪些现有入口，而不是只写在文档里。
4. 命名迁移、runtime 收口、control plane 收缩三路各自还剩哪些跨包尾项，要由 D 统一补掉。
5. 哪些事项可以后置，但不会阻塞当天总验收。

### 这一路不要做

1. 不做前端展示壳。
2. 不做花哨演示素材。
3. 不在这里重构 compiler 或 collaboration substrate。
4. 不把未完成项继续散回其他包。

## 建议代码与验证落点

1. 优先落到：
   - `butler_main/orchestrator/smoke.py`
   - `butler_main/orchestrator/runner.py`
   - `butler_main/orchestrator/service.py`
   - `butler_main/orchestrator/query_service.py`
   - `butler_main/orchestrator/observe.py`
   - `butler_main/orchestrator/execution_bridge.py`
   - `butler_main/orchestrator/runtime_adapter.py`
2. 测试优先放在：
   - `butler_main/butler_bot_code/tests/test_orchestrator_runner.py`
   - `butler_main/butler_bot_code/tests/test_orchestrator_workflow_vm.py`
   - `butler_main/butler_bot_code/tests/test_orchestrator_package_bootstrap.py`
3. 如需最小 fixture，可新增：
   - `butler_main/orchestrator/demo_fixtures.py`

## 需要吸收的尾项

1. 命名迁移尾项：
   - 最终靶名冻结
   - `import / re-export / codemod` 后的 consumer 侧补位
   - `framework/demo/tests` 对新目录命名的跟随
2. `process runtime` 尾项：
   - 普通 path session 证据链
   - `governance receipt / resume / session` 观测口
   - `workflow_session_count > 0` 或等价 session 观测对象
3. `orchestrator` 收缩尾项：
   - `runtime verdict / writeback` 接口稳定
   - `execution_bridge / runtime_adapter / query / observe` 跟随
   - research/domain 文件降层后的兼容路径

## 对其他 lane 的依赖

1. 依赖 `Lane A`：
   - 选定 demo framework profile
2. 依赖 `Lane B`：
   - 至少两条真实编译结果
3. 依赖 `Lane C`：
   - 至少一个 collaboration primitive 能进入 event / projection / artifact 结果

## demo 固定题

这一路建议尽早冻结两条 demo：

1. `Demo 1`
   - `Superpowers-like` 的 `brainstorm -> plan -> implement -> review`
   - 用来证明 framework profile 能编译成 Butler workflow
2. `Demo 2`
   - `OpenFang-inspired` 的自治能力包流
   - 用来证明 capability package / governance policy / approval gate 真能进入链路

## 必须观测到的事件

1. `workflow_ir_compiled`
2. `workflow_vm_executed`
3. 至少一个：
   - `verification_skipped` 或真实 verification 事件
   - `approval_requested`
   - `recovery_scheduled`
4. artifacts / receipts / node writeback
5. `workflow_session_count > 0` 或等价 session 级观测对象

## 执行拆解

1. 第一阶段：冻结 demo fixture、验收清单和 A/B/C 尾项 `closure checklist`。
2. 第二阶段：补 `smoke/query/observe` 路径，哪怕先走最小 fake or local bridge。
3. 第三阶段：把 `Demo 1` 跑通。
4. 第四阶段：把 `Demo 2` 跑到至少出现 governance / approval / recovery 节点。
5. 第五阶段：复核所有尾项是否已经关闭；如果仍有残留，只允许保留不阻塞总验收的 defer 列表。

## 首日动作

1. 先写“演示什么，不演示什么”，防止后三路做完却没有统一展示对象。
2. 先冻结两条 demo 的 mission 输入和 framework profile。
3. 先把 A/B/C 的尾项列成单一 checklist，再反推 `smoke/query/observe/tests` 的补位。
4. 先把需要观察的事件名列出来，再反推 smoke 测试。

## 风险与缓解

1. 风险：demo 变成临时拼接脚本。
   - 缓解：优先挂到现有 `orchestrator/smoke.py` 和测试入口。
2. 风险：demo 过晚定义，前三路越做越散。
   - 缓解：把 fixture 作为最早冻结件之一。
3. 风险：只证明“能跑一次”，无法说明边界。
   - 缓解：验收里强制要求事件、artifacts、writeback 三类都可见。
4. 风险：D 只做展示，不真正吸收 A/B/C 的尾项。
   - 缓解：把 `closure checklist` 作为 D 的正式交付件，而不是口头备注。
