# 0327 Butler 系统分层与事件契约收口

日期：2026-03-27  
时间标签：0327_0003  
状态：已收口 / 作为本轮系统抽象重排与事件分层专题真源

关联文档：

- [00_当日总纲.md](./00_当日总纲.md)
- [Butler System Layering And Event Contracts](../../runtime/System_Layering_and_Event_Contracts.md)
- [Workflow IR 正式口径](../../runtime/WORKFLOW_IR.md)

## 一句话裁决

从 `2026-03-27` 起，Butler 的系统抽象默认改为：

`Product Surface（产品表面层） -> Domain & Control Plane（领域与控制平面） -> L4 Multi-Agent Session Runtime（多 Agent 会话运行时） -> L3 Multi-Agent Protocol（多 Agent 协议层） -> L2 Durability Substrate（持久化基座） -> L1 Agent Execution Runtime（Agent 执行运行时）`

`multi-agent` 后续默认只指 `L3 + L4`。

## 本轮收口的问题

这轮不是功能 bug 修补，而是概念性混淆收口。当前已确认的主要混淆有四类：

1. `Butler System（全系统）` 和 `multi-agent` 长期混说。
2. `Process Runtime（过程运行时）` 同时背了 protocol、session runtime、durability 三层语义。
3. `Observe（观察）` 被混成 role、phase、projection、debug trace 的统称。
4. 事件流没有显式分层，容易出现跨层偷写真源对象。

## 本轮实现

### 1. runtime_os 公开面收口

代码层第一版已经新增：

1. `runtime_os.multi_agent_protocols`
2. `runtime_os.multi_agent_runtime`
3. `runtime_os.durability_substrate`

并保留：

4. `runtime_os.process_runtime`

当前意义是：

1. 新代码可以直接按 L3/L4/L2 命名导入。
2. 老代码和兼容测试仍可以继续走 `process_runtime`。
3. 先做语义收口，再做物理搬迁。

### 2. 事件封套种子落地

`WorkflowSessionEvent` 已经补入最小事件封套字段：

- `event_id`
- `event_type`
- `layer`
- `subject_ref`
- `causation_ref`
- `created_at`
- `payload`

这意味着 `L4 Multi-Agent Session Runtime（多 Agent 会话运行时）` 已经有统一的事件种子，不再只是一条无层级标签的流水记录。

### 3. Workflow IR 边界补标

`workflow_ir.execution_boundary` 已补出：

1. `protocol_owner=runtime_os.multi_agent_protocols`
2. `session_runtime_owner=runtime_os.multi_agent_runtime`
3. `durability_owner=runtime_os.durability_substrate`

同时保留旧的 `process_runtime_owner / collaboration_owner` 兼容字段，避免现有调用面立即断裂。

### 4. 术语冻结

本轮正式冻结三组区别：

1. `RoleSpec（角色规格）` vs `RoleBinding（角色绑定）`
2. `Observability（可观测性）` vs `Projection（投影读模型）`
3. `Domain Truth（领域真源）` vs `Projection（投影读模型）`

## 事件分层计划

后续默认按下面口径推进：

1. `L1 Execution Events（执行事件）`
2. `L2 Durability Events（持久化事件）`
3. `L4 Session Events（会话事件）`
4. `C Plane Domain Events（控制平面领域事件）`
5. `P Layer Refresh Events（产品层刷新事件）`

当前只把 `L4` 的事件封套做成代码事实；`L2 / C / P` 仍以文档和边界标签先冻结，不在本轮强起第二套事件实现。

## 文档回写

本轮已同步回写：

1. `docs/runtime/System_Layering_and_Event_Contracts.md`
2. `docs/runtime/WORKFLOW_IR.md`
3. `docs/project-map/00_current_baseline.md`
4. `docs/project-map/01_layer_map.md`
5. `docs/project-map/02_feature_map.md`
6. `docs/project-map/03_truth_matrix.md`
7. `docs/project-map/04_change_packets.md`
8. `docs/README.md`
9. `docs/daily-upgrade/0327/00_当日总纲.md`

## 验收

本轮定向回归结果：

- `14 passed`

命令：

```bash
.venv/bin/python -m pytest \
  butler_main/butler_bot_code/tests/test_runtime_os_namespace.py \
  butler_main/butler_bot_code/tests/test_runtime_os_root_package.py \
  butler_main/butler_bot_code/tests/test_agents_os_process_runtime_surface.py \
  butler_main/butler_bot_code/tests/test_orchestrator_workflow_ir.py -q
```

## 最终结论

当前这版不追求一次性把全部目录搬完；它要先把三件事钉死：

1. 以后再说 `multi-agent`，默认只指协议层和会话运行时。
2. 以后再说 `observe`，默认拆成 `Observability（可观测性） + Projection（投影读模型）`。
3. 以后再说 `event`，默认先问它属于哪一层、能不能跨层写真源。
