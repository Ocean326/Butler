---
type: "note"
---
# 02 Framework Compiler 最小落地

日期：2026-03-25
时间标签：0325_0002
状态：已迁入完成态 / compiler 背景输入保留

## 目标

1. 把外部框架从“知识对象”推进成“可编译对象”。
2. 建立 `framework profile -> Butler Workflow IR` 的最小编译器。
3. 让编译器开始输出 package / contract / policy 绑定，而不是只输出 step 序列。

## 今日要完成的事

1. 编译 `Superpowers-like` 流程：
   - brainstorm
   - plan
   - implement
   - review
2. 编译 `gstack-like` 流程：
   - think
   - plan
   - build
   - qa
   - ship
3. 把编译结果统一输出为 Butler IR，而不是直接输出 prompt。
4. 增加一条 `OpenFang-inspired` 编译测试：
   - autonomous research / monitor 类能力
   - 产出 capability package 引用
   - 自动挂上 approval / governance policy

## 验收标准

1. 外部框架开始进入 Butler runtime，而不是只停在调研文档。
2. 编译结果至少有一条体现出 Butler 自己的 package / governance 语义，而不是外部术语原样透传。

## 范围边界

### 这一路必须回答

1. Butler 如何把 `framework profile` 编译成正式 `Workflow IR`。
2. 编译结果里哪些是 workflow 结构，哪些是 package / contract / governance 绑定。
3. 编译器和 orchestrator / workflow VM 的边界在哪里。

### 这一路不要做

1. 不把 compiler 退化成 prompt 模板渲染器。
2. 不在 compiler 里偷塞 demo 特例逻辑。
3. 不在这里重做 `Lane A` 的 catalog 和记账功能。

## 建议代码落点

1. 优先延伸：
   - `butler_main/orchestrator/compiler.py`
   - `butler_main/orchestrator/workflow_ir.py`
2. 必要时新增：
   - `butler_main/orchestrator/framework_profiles.py`
   - `butler_main/orchestrator/framework_compiler.py`
3. 测试优先放在：
   - `butler_main/butler_bot_code/tests/test_orchestrator_workflow_ir.py`
   - `butler_main/butler_bot_code/tests/test_orchestrator_workflow_vm.py`
   - 新增 `test_orchestrator_framework_compiler.py`

## 对其他 lane 的依赖与输出

1. 依赖 `Lane A`：
   - `framework_id`
   - `mapping spec`
   - `package / governance defaults`
2. 依赖 `Lane C`：
   - typed collaboration primitive 的最小正式集合
3. 输出给 `Lane D`：
   - 两条真实编译结果
   - 一条带 governance / approval 的编译结果

## 编译器输出 contract

这一路最先要冻结的是编译结果最小 contract：

1. `workflow_template`
2. `role_bindings`
3. `workflow_inputs`
4. `capability_package_refs`
5. `team_package_refs`
6. `governance_policy_refs`
7. `runtime_binding`
8. `metadata.framework_origin`

## 执行拆解

1. 第一阶段：冻结 `compile(profile, mission_context)` 的最小入口。
2. 第二阶段：做两条 profile 编译：
   - `Superpowers-like`
   - `gstack-like`
3. 第三阶段：做一条 `OpenFang-inspired` 编译结果：
   - 明确 capability package
   - 明确 approval / governance policy
4. 第四阶段：把编译结果接回 `WorkflowIR.from_dict()` / `to_dict()` 以及 orchestrator 消费点。

## 首日动作

1. 不先扩 framework 数量，先让两个 profile 真能落到 `Workflow IR`。
2. 先补 `framework_origin / package refs / governance refs` 这几个输出位。
3. 先把 compiler 结果喂给现有 `orchestrator.workflow_vm` 的入口，而不是另起一套执行壳。

## 风险与缓解

1. 风险：`Lane A` schema 在中途变化。
   - 缓解：加一层 profile normalization，不让内部 compiler 直接吃原始 catalog 结构。
2. 风险：编译结果又退回“只有 step 列表”。
   - 缓解：package / governance ref 作为必填验收项。
3. 风险：编译器开始直接绑死 `multi_agents_os` 当前实现细节。
   - 缓解：只输出 primitive 名称和 binding hints，不直接输出 session 内部存储细节。
