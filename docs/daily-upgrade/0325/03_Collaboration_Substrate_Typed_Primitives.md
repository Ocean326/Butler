---
type: "note"
---
# 03 Collaboration Substrate Typed Primitives

日期：2026-03-25
时间标签：0325_0003
状态：已迁入完成态 / process runtime 输入保留

## 目标

1. 让 `multi_agents_os` 再向真正的 collaboration substrate 迈一步。
2. 为未来 framework compiler 和 workflow VM 提供 typed 协作原语。
3. 为 future autonomous package / team package 运行提供统一协作底座。

## 今日要完成的事

1. 明确 mailbox primitive。
2. 明确 ownership primitive。
3. 明确 join contract primitive。
4. 明确 role output contract。
5. 明确 artifact visibility scope。
6. 明确 workflow-scoped memory / blackboard primitive。
7. 明确 package instance 与 collaboration session 的关系。

## 验收标准

1. `multi_agents_os` 不再只是 session 容器。
2. 它开始具备 team engine 所需的 typed collaboration 基础。
3. 它开始能承接自治能力包与协作工作流的共同底座，而不是只服务 prompt team。

## 范围边界

### 这一路必须回答

1. 哪些 collaboration primitive 是 Butler 的正式 typed substrate。
2. 这些 primitive 如何被 workflow / compiler / runtime 共同消费。
3. 它们如何与 artifact、ownership、join、共享状态对齐。

### 这一路不要做

1. 不在这里做远程分布式调度系统。
2. 不在这里做 message broker 基建幻觉。
3. 不在这里顺手改 orchestrator 的 mission 业务模型。

## 现有基础

当前 `butler_main/multi_agents_os/session/collaboration.py` 已经有：

1. `MailboxMessage`
2. `StepOwnership`
3. `JoinContract`
4. `RoleHandoff`
5. `CollaborationSubstrate`

所以这一路不是从零开始，而是要把这些对象从“有数据结构”推进到“有正式 primitive 边界和消费语义”。

## 建议代码落点

1. 优先补强：
   - `butler_main/multi_agents_os/session/collaboration.py`
   - `butler_main/multi_agents_os/session/workflow_session.py`
   - `butler_main/multi_agents_os/session/artifact_registry.py`
   - `butler_main/multi_agents_os/bindings/role_binding.py`
2. 必要时新增：
   - `butler_main/multi_agents_os/session/contracts.py`
   - `butler_main/multi_agents_os/session/blackboard.py`
3. 测试优先放在：
   - `butler_main/butler_bot_code/tests/test_multi_agents_os_factory.py`
   - 新增 `test_multi_agents_os_collaboration.py`
   - `test_orchestrator_research_projection.py`

## 这一路对其他 lane 的输出

1. 给 `Lane B`：
   - compiler 可合法输出的 primitive 名单
   - 每种 primitive 的最小字段
2. 给 `Lane D`：
   - demo 中允许被观测的 collaboration event
   - artifact visibility 与 join 的最小示例

## 最小 primitive 集

1. `mailbox`
2. `ownership`
3. `join_contract`
4. `handoff`
5. `artifact_visibility_scope`
6. `workflow_blackboard`

## 执行拆解

1. 第一阶段：冻结 primitive 边界
   - 哪些对象已经是正式对象
   - 哪些对象还只是内部 metadata
2. 第二阶段：把 artifact scope 和 blackboard 补成正式对象或正式字段。
3. 第三阶段：明确 compiler / VM / projection 如何读取这些 primitive。
4. 第四阶段：补测试，至少覆盖：
   - mailbox 去重
   - ownership 更新
   - join contract 收敛
   - blackboard 可见性

## 首日动作

1. 先把现有 `CollaborationSubstrate` 对象表列出来，确认哪些已经够正式。
2. 先只补最缺的两个对象：
   - `artifact_visibility_scope`
   - `workflow_blackboard`
3. 先写 consumption contract，再继续加字段，避免又变成 session 杂物箱。

## 风险与缓解

1. 风险：这一路越做越像“另一个 workflow engine”。
   - 缓解：严格限定只做 collaboration primitive，不碰 orchestrator control plane。
2. 风险：primitive 太抽象，`Lane B` 无法使用。
   - 缓解：每个 primitive 必须带一条 compiler 输出示例。
3. 风险：只加结构，不加消费点。
   - 缓解：至少补一条 orchestrator / projection / demo 读取路径。
