# 0320 research scenario runner 升级方案：brainstorm / paper_discovery / idea_loop

更新时间：2026-03-20 23:52
时间标签：0320_2352

## 一、这轮要解决什么

上一轮已经完成：

- `agents_os` 的 `protocol + workflow` 最小骨架
- `research_manager` 的多入口同业务核
- `scenario_registry` 对 research 场景资产包的映射

但当前 research 仍然停在：

- manager 能把 `scenario` 和 `workflow_projection` 塞进 dispatch payload
- 还没有一个真正的场景级 runner 来解释“当前走到哪一步、下一步该做什么、出口该长什么样”

所以这轮目标不是做通用编排器，而是补一个：

> **轻量、场景级、可接续的 `scenario_runner`**

它只服务当前最重要的三个 research 场景：

- `brainstorm`
- `paper_discovery`
- `idea_loop`

---

## 二、一句话工程决策

这轮 research 不做重 orchestrator，只补：

> **`scenario_runner = scenario spec loader + cursor resolver + step plan projector + minimal receipt emitter`**

这意味着：

- 继续复用 `agents_os.workflow` 的 `WorkflowSpec / WorkflowCursor / WorkflowRunProjection`
- 继续复用 `agents_os.protocol` 的 `StepReceipt / HandoffReceipt / DecisionReceipt`
- `ResearchManager` 仍只做 research 业务核
- `scenario_runner` 只负责把场景 workflow 解释成“当前 step + 下一步 + 出口格式”

---

## 三、职责边界

`scenario_runner` 应负责：

- 读取 scenario 对应的 `workflow.spec.json`
- 根据 invocation / cursor 推导当前 step
- 给出当前 step 的 stage brief
- 给出下一步 handoff / decision
- 生成最小 `step / handoff / decision` receipts
- 给出该场景当前 step 的输出骨架和出口格式

`scenario_runner` 不负责：

- 真的执行搜索、阅读、总结、代码修改
- 管理 CLI provider / runtime profile
- 代替 `RuntimeHost`
- 变成通用 graph/DAG 引擎

---

## 四、最小接口

建议新增：

- `research_manager/services/scenario_runner.py`

对外只提供一个主入口：

- `build_scenario_dispatch(invocation, unit)`

它返回一个轻量 bundle，至少包含：

- `scenario`
- `workflow_projection`
- `workflow_cursor`
- `active_step`
- `step_receipt`
- `handoff_receipt`
- `decision_receipt`
- `output_template`
- `entry_contract`
- `exit_contract`

其中最重要的是：

- `active_step`
- `output_template`
- `decision_receipt`

因为 research manager 真正要给到 heartbeat / talk / codex 的，是：

- 这一轮该做什么
- 应该产出什么
- 下一步准备交给谁

---

## 五、状态推进策略

本轮只做轻推进，不做完整执行状态机。

### 5.1 cursor 来源

优先级：

1. `invocation.metadata.workflow_cursor`
2. `invocation.payload.workflow_cursor`
3. scenario 默认首 step

### 5.2 action 来源

优先级：

1. `invocation.metadata.scenario_action`
2. 默认 `prepare`

支持的最小动作：

- `prepare`
  - 初始化或读取当前 cursor
- `advance`
  - 正常推进到下一 step
- `resume`
  - 保持当前 step，不推进
- `recover`
  - 走 recover 分支或回退到 recover 语义

### 5.3 decision 来源

优先级：

1. `invocation.metadata.decision`
2. 默认 `proceed`

本轮只支持最小 decision 集：

- `proceed`
- `refine`
- `retry`
- `accept`

---

## 六、三个场景的最小推进语义

## 6.1 brainstorm

目标：

- 把问题收口
- 把想法聚类
- 展开可行方向
- 收敛成可执行输出

step 语义：

- `capture`
  - 锁定问题、约束、目标
- `cluster`
  - 把输入想法分组归纳
- `expand`
  - 扩展候选方向、列出可能路线
- `converge`
  - 收敛成 1-3 个主方向并说明取舍
- `archive`
  - 形成归档输出

默认输出模板：

- `problem_frame`
- `idea_clusters`
- `candidate_directions`
- `recommended_direction`
- `open_questions`

入口偏好：

- `talk`
- `codex`

---

## 6.2 paper_discovery

目标：

- 从 topic 到 query 到 shortlist 到 digest

step 语义：

- `topic_lock`
  - 锁定主题、时间窗、筛选边界
- `query_plan`
  - 形成查询式、来源、筛选规则
- `search`
  - 执行搜索与候选收集
- `screen`
  - 过滤与初筛
- `digest`
  - 产出 digest / shortlist

默认输出模板：

- `topic_frame`
- `query_set`
- `paper_candidates`
- `screening_notes`
- `shortlist`

入口偏好：

- `heartbeat`
- `talk`
- `codex`

---

## 6.3 idea_loop

目标：

- 从 hypothesis 到执行计划，到验证，再到下一轮决策

step 语义：

- `idea_lock`
  - 锁定 hypothesis / target metric
- `plan_lock`
  - 形成实验或实现计划
- `iterate`
  - 执行改进、写代码或整理方案
- `final_verify`
  - 比对结果、判断有效性
- `archive`
  - 形成结果归档
- `recover`
  - 当 `refine / retry` 时进入恢复语义

默认输出模板：

- `hypothesis`
- `change_plan`
- `implementation_notes`
- `verification_result`
- `next_iteration`

入口偏好：

- `heartbeat`
- `talk`
- `codex`

特殊推进规则：

- 在 `final_verify` 上若 decision 为 `retry / refine`，下一步优先进入 `recover`

---

## 七、manager 接线方式

这轮不改 `ResearchManager` 的定位，只改 dispatch payload 的来源：

旧：

- `unit_registry.py` 直接拼 `scenario + workflow_projection`

新：

- `unit_registry.py` 调 `scenario_runner.build_scenario_dispatch()`
- 把 runner 的结果并入 dispatch payload

这样好处是：

- manager 仍然干净
- unit handler 不需要自己解释 workflow step
- 后续要把场景 runner 单独挪出去，改造面很小

---

## 八、代码落地范围

本轮建议新增：

- `butler_main/research/manager/code/research_manager/services/scenario_runner.py`

本轮建议修改：

- `butler_main/research/manager/code/research_manager/services/unit_registry.py`
- `butler_main/research/manager/code/research_manager/services/__init__.py`
- `butler_main/research/README.md`
- 相关测试文件

本轮建议新增测试：

- `test_research_scenario_runner.py`

测试关注点：

1. 三个场景都能返回正确的初始 step
2. `advance` 能推进到下一 step
3. `idea_loop` 在 `final_verify + retry/refine` 时走 `recover`
4. manager dispatch payload 已包含 runner 产物

---

## 九、这轮不做什么

明确不做：

- runtime 驱动的自动执行器
- 真的联网搜论文
- 自动读论文和自动改代码
- 全局 application flow catalog
- 场景之间的动态 agent 编组

本轮仍然坚持：

> 先把“场景 workflow 的解释层”做好，再考虑“场景 workflow 的自动执行层”。

---

## 十、最终判断

对当前 Butler research 来说，最正确的推进不是先做一个大 research platform，而是：

- 先让 `brainstorm / paper_discovery / idea_loop` 都拥有统一的场景 runner
- 让 `heartbeat / talk / codex` 共享同一份场景解释层
- 让 workflow/protocol 真正从“资产描述”推进到“可接续的运行语义”

一句话总结：

> 这轮 research 的核心，不是把 agent 再堆多，而是把 scenario 从静态资产包推进成轻量可运行的 workflow 解释层。
