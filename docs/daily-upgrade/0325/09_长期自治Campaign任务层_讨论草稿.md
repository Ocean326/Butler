# 长时自治型 Research-Driven R&D Campaign V1

日期：2026-03-25
状态：最终讨论稿 / 开发态输入
定位：第 4 层 `campaign supervisor` 业务协议层草案
适用范围：V1 默认以 `单 workspace / 单 repo campaign` 为单位

## 与 08 的关系

1. [08_第四层接口冻结_V1_简化版.md](./08_第四层接口冻结_V1_简化版.md) 负责冻结第四层消费面 contract，包括端口、证据集与依赖边界。
2. 本文承接的是第四层长期自治任务层讨论：`campaign supervisor`、外层阶段循环、`WorkingContract`、`EvaluationVerdict` 等业务协议。
3. 本文不修改 `08` 的冻结边界；后续若进入实现阶段，也默认建立在 `08` 已冻结的第四层消费面之上。

## Summary

下三层在现状上应被视为 `substrate`，不是成品业务系统：

- `orchestrator / control plane`
  - 负责 `mission`、`branch`、事件、调度与记账，已经够稳定做底座。
- `runtime_os / process runtime`
  - 已有 `session`、`artifact`、`blackboard`、`mailbox`、`join/handoff`、`resume/recovery`，适合承载阶段内自治。
- `runtime_os / agent runtime`
  - 已能稳定承接单次执行与代码写入。

V1 不应把 system task 直接摊平成 generic mission graph。正确落法是新增一个第 4 层 `campaign supervisor`，让它在一个长生命周期 session 内运行 `Discover -> Implement -> Evaluate -> Iterate` 外层循环，并把下三层当执行与持久化底座使用。

## Key Changes

### 1. 新增 Campaign 业务协议层

定义一套面向长期自治任务的显式 contract，而不是继续把语义塞回 `orchestrator`：

- `CampaignSpec`
  - 输入只要求 `top_level_goal` 和 `materials`
  - 可选 `hard_constraints`、`workspace_root`
- `CampaignInstance`
  - 记录 campaign 当前状态、当前 phase、当前 iteration、全局时间跨度、全局日志索引
- `WorkingContract`
  - `working_goal`
  - `working_acceptance`
  - `iteration_budget`
  - `risk_register`
  - `phase_scorecard`
- `EvaluationVerdict`
  - `decision = continue | converge | recover`
  - `score`
  - `rationale`
  - `next_iteration_goal`
- `IterationBudget`
  - 轮次预算
  - 时间预算
  - 改动预算

约束直接冻结为：

- 顶层 `user goal` 和 `hard constraints` 不可被自动改写。
- 后续轮次只允许局部改写 `working goal / phase acceptance / execution strategy`。

### 2. 用单一 Campaign Supervisor 承载外层阶段循环

V1 不走动态长出 mission node 的路线。

外层 `control plane` 只维护一个长期运行的 `campaign mission`，核心执行节点由 `campaign_supervisor` 持有。这个 supervisor 在内部 session 中执行固定外层循环：

- `Discover`
  - 从只有目标和资料的薄输入生成首轮 `WorkingContract`
  - 产出 `discover report`、风险、初始验收口径、初始预算
- `Implement`
  - 允许代码改动、测试编写、局部 agent 分工
  - 真实执行在 repo 内发生
- `Evaluate`
  - 由专门 `reviewer / evaluator agent` 作最终判定
  - 主执行 agent 只能提供自评与证据，不能决定停机
- `Iterate`
  - 如果未收敛，局部改写 `WorkingContract`
  - 进入下一轮 `Discover / Implement / Evaluate` 子循环，或直接回到 `Implement`

外层 `phase model` 固定为 `Discover -> Implement -> Evaluate -> Iterate`。

阶段循环发生在 `campaign_supervisor` 内，不发生在 generic mission graph 动态扩图上。

### 3. 阶段内自治放进 Session，不放进 Mission Graph

阶段内自治使用现有 `process-runtime substrate`：

- `blackboard`
  - 记录阶段事实、局部结论、共享上下文
- `mailbox / handoff / join_contract / ownership`
  - 记录角色协作
- `artifact_registry`
  - 记录代码、报告、测试结果、review 证据
- `workflow_session event log`
  - 记录完整会话过程

`generic path` 目前还不是真正的 `step/role VM`，因此 V1 的阶段内自治由 `campaign supervisor` 先落地。

通用 `step/role VM` 可以并行推进，但只作为后续替换 `campaign supervisor` 内部 `phase runtime` 的实现，不阻塞 V1。

### 4. 重试与收敛规则冻结

- 重试不是无限自旋
  - 必须受 `IterationBudget` 约束
  - 用尽后只能进入 `recover` 路径并缩小或重写 `WorkingContract`
- 不允许系统改写顶层用户目标来伪造收敛
- `reviewer / evaluator` 是最终判定者
  - 主 agent 可以自评
  - 自评只能作为 evidence 输入
  - 最终 verdict 必须来自独立 reviewer
- 完整会话日志是硬要求
  - V1 不做日志裁剪优先优化

## Public Interfaces

### 建议新增的对外接口

- `create_campaign(spec: CampaignSpec) -> CampaignInstanceSummary`
- `get_campaign_status(campaign_id) -> CampaignStatus`
- `list_campaign_artifacts(campaign_id) -> ArtifactIndex`
- `resume_campaign(campaign_id) -> CampaignStatus`
- `stop_campaign(campaign_id) -> CampaignStatus`

### 建议新增的内部运行接口

- `PhaseRuntime.run(context, working_contract) -> PhaseResult`
- `ReviewerRuntime.evaluate(context, working_contract, evidence) -> EvaluationVerdict`
- `WorkingContract.rewrite_from_evaluation(...) -> WorkingContract`

## Test Plan

- 创建 campaign：仅输入 `goal + materials`，首轮 `Discover` 能生成 `WorkingContract`
- `Evaluate` 阶段：必须由独立 reviewer 给最终 verdict，主 agent 不得直接宣布收敛
- `Iterate` 阶段：允许局部改写 `working goal / acceptance`，但顶层 `goal` 与 `hard constraints` 不变

- V1 以 `单 workspace / 单 repo campaign` 为默认单位
- V1 的业务目标是 `研究驱动研发循环`，不是通用多业务平台
- 下三层继续做 `substrate`，不把 campaign 语义反灌回 `orchestrator core`
- 外层阶段固定，阶段内自治可强；外层图结构在 V1 不做开放式动态扩图
- `reviewer / evaluator` 是最终判定者；主 agent 自评仅作为证据输入
- 完整会话日志是硬要求，V1 不做日志裁剪优先优化

## 结论

V1 的关键不是把现有 system task 再包装成更复杂的 mission graph，而是承认“长期自治研发循环”本身就是一个新的第 4 层业务协议问题。

因此，正确路线是：

1. 保持 `3 -> 2 -> 1` 继续作为稳定 substrate。
2. 在其上新增显式 `campaign supervisor`。
3. 用固定外层阶段循环承接长期自治。
4. 用独立 reviewer 保证收敛判定不被主执行 agent 自我宣告污染。
5. 用 session substrate 保证阶段内自治、证据沉淀与可恢复性。

当前这份文档先作为长期方向与接口草案输入，不构成 `0325` 当天立即实现承诺。
