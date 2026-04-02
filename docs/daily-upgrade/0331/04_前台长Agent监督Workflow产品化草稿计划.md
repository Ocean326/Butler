# 0331 前台长 Agent 监督 Workflow 产品化草稿计划

日期：2026-03-31  
状态：未实施草稿 / 产品化计划稿  
所属层级：`Product Surface` 主层，触达 `Domain & Control Plane`、`L4 Multi-Agent Session Runtime`、`L2 Durability Substrate`、`L1 Agent Execution Runtime`  
关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [02_前台WorkflowShell收口.md](./02_前台WorkflowShell收口.md)
- [03_后台主线控制面瘦身与Agent内环提权草稿计划.md](./03_后台主线控制面瘦身与Agent内环提权草稿计划.md)
- [0330/02F_前门与Operator产品壳开发计划.md](../0330/02F_前门与Operator产品壳开发计划.md)
- [0330/02A_runtime层详情.md](../0330/02A_runtime层详情.md)
- [0330/02C_会话协作与事件模型开发计划.md](../0330/02C_会话协作与事件模型开发计划.md)
- [0330/02D_持久化恢复与产物环境开发计划.md](../0330/02D_持久化恢复与产物环境开发计划.md)
- [0330/02G_治理观测与验收闭环开发计划.md](../0330/02G_治理观测与验收闭环开发计划.md)
- [0330/02R_外部Harness映射与能力吸收开发计划.md](../0330/02R_外部Harness映射与能力吸收开发计划.md)
- [Visual_Console_API_Contract_v1.md](../../runtime/Visual_Console_API_Contract_v1.md)
- [系统分层与事件契约](../../runtime/System_Layering_and_Event_Contracts.md)

## 一句话裁决

如果 Butler 要让用户**从前台直接启动一个长时间、agent 监督 agent 的 workflow**，最稳妥的方向不是把现有后台 `campaign` 直接搬到前台，也不是继续停留在 CLI 工具态，而是产品化出一条新的轻主线：

`Frontdoor Draft -> Foreground Workflow Run -> Supervisor Agent Inner Loop -> Operator Intervention -> Optional Handoff to Campaign`

这里的关键是：

1. **agent 成为前台 workflow 的主驱动者**
2. **harness 负责稳定性兜底**
3. **前台 run 保持轻控制面，不直接继承后台厚状态机**

换句话说，这条线的目标不是“弱控制面、强放养”，而是：

`Agent-led inner loop + Harness-enforced boundary`

## 本文边界

本文是 `0331` 的一份前台产品化草稿，不替代当前现役真源。  
在代码落地前，当前现役判断仍然不变：

1. `workflow shell` 仍属于 L1 前台执行运行时
2. 它当前不进入 `campaign/orchestrator` 后台任务主链
3. console/frontdoor 仍只能发受控 action，不直接成为运行真源

## 为什么前台要单独做一条长 Workflow 主线

当前前台 `workflow shell` 已经具备：

1. `single_goal / project_loop`
2. Codex 主执行
3. Cursor 守看和判定
4. resume / phase history / local trace

但它现在仍然更像：

1. 一个强 CLI
2. 一个本地前台执行 loop
3. 一个 operator 不可见的长任务外环

它还不是：

1. 正式前台长任务对象
2. 可查询、可接手、可审计的产品面 run
3. 可升格为后台 durable 任务的前台入口

## 从 0330 外部项目研究得到的关键裁决

本草稿不是凭空设计，而是基于 `0330` 对外部 harness 的整理，收出下面 6 条最重要的吸收原则。

### 1. `OpenAI Agents SDK + Codex Harness`

最值得吸收的不是 vendor API，而是：

1. `thread / turn / item` 作为产品级事件边界
2. 双向 approval 协议
3. `Humans steer. Agents execute.`
4. subagent 继承式治理

对前台长 workflow 的含义是：

1. 前台 run 不能只有“当前状态”，还要有 `thread -> turn -> item` 事件面
2. operator 不是旁观者，而是正式 steering 方
3. supervisor agent 可以主导推进，但人必须保留 ask-human / approve / redirect 能力

### 2. `LangGraph`

最值得吸收的不是 graph DSL，而是：

1. stateful runtime
2. durable execution
3. interrupt / resume
4. checkpoint discipline

对前台长 workflow 的含义是：

1. 前台 run 不能只是临时流式输出
2. 需要正式的 run checkpoint / resume 语义
3. 中断、恢复、切 phase 必须是正式动作合同

### 3. `CrewAI`

最值得吸收的是：

1. `flow` 与 `autonomy` 分离

对前台长 workflow 的含义是：

1. phase/step/turn 是 harness 的事
2. subagent/crew/supervisor 的自主推进是 agent 的事
3. 不能把“agent 很聪明”直接变成“系统没有流程边界”

### 4. `Dify`

最值得吸收的是：

1. 产品壳完整度
2. `run history + node history`
3. fault tolerance
4. workflow/chatflow 的产品面区分

对前台长 workflow 的含义是：

1. 需要 `run history`
2. 需要 `turn history`
3. 需要可读的 operator surface
4. 需要启动前的 launch/preview，而不是只给命令行参数

### 5. `DeerFlow`

最值得吸收的是：

1. `Harness / App Split`
2. thread-isolated workspace
3. middleware chain
4. artifact / filesystem / thread 一体环境
5. 统一 policy shell 约束下的 delegation runtime

对前台长 workflow 的含义是：

1. 前台产品壳和运行时真源必须切开
2. 每个长 workflow run 应有自己的 thread/workspace 视图
3. subagent delegation 必须受统一 policy shell 约束

### 6. `02G` 的治理结论

`0330/02G` 的核心不是“让 agent 更自由”，而是：

1. `risk_level / autonomy_profile / approval / trace / receipt / action ledger`
   必须成为第一类事实

这意味着前台长 workflow 即使更 agent-led，也不能放弃：

1. trace
2. receipt
3. approval
4. operator action audit

## 前台长 Workflow 的目标定位

这条新线应被定位为：

1. **foreground attached long-running workflow**
2. **agent-led but operator-steerable**
3. **可恢复、可审计、可转后台**

它不是：

1. 旧后台 `campaign` 的前台皮肤
2. 只在本地终端可见的 CLI 小工具
3. 一个随意放养的“超强 agent 模式”

## 建议新增的正式对象

### 1. `ForegroundWorkflowDraft`

前台启动前的草案对象，负责：

1. `workflow_kind`
2. `goal`
3. `guard_condition`
4. `materials`
5. `skill_exposure`
6. `risk_level`
7. `autonomy_profile`
8. `launch_intent`

它的作用接近前台 workflow 的 launch contract，而不是后台 campaign spec。

### 2. `ForegroundWorkflowRun`

这是前台长 workflow 的主对象。  
建议最小字段：

1. `workflow_run_id`
2. `workflow_kind`
3. `goal`
4. `guard_condition`
5. `status`
6. `current_phase`
7. `current_turn_id`
8. `supervisor_thread_id`
9. `primary_executor_session_id`
10. `latest_judge_decision`
11. `risk_level`
12. `autonomy_profile`
13. `approval_state`
14. `trace_refs`
15. `receipt_refs`
16. `handoff_target_campaign_id`

### 3. `WorkflowTurnRecord`

前台 run 不应只记录 phase history，还应记录 turn 级事件：

1. `turn_id`
2. `phase`
3. `attempt_no`
4. `executor_agent_id`
5. `judge_agent_id`
6. `decision`
7. `reason`
8. `artifact_refs`
9. `trace_id`
10. `receipt_id`
11. `started_at`
12. `completed_at`

### 4. `WorkflowActionReceipt`

operator 对 run 的操作必须有 receipt，至少包括：

1. `action_id`
2. `action_type`
3. `operator_id`
4. `policy_source`
5. `trace_id`
6. `receipt_id`
7. `before_state`
8. `after_state`
9. `result_summary`

### 5. `WorkflowHandoffPacket`

前台 run 升格到后台 campaign 时，必须通过 handoff packet，而不是直接共享全部状态。

建议字段：

1. `goal`
2. `materials`
3. `phase_summary`
4. `artifact_refs`
5. `judge_blockers`
6. `latest_receipt_refs`
7. `recommended_runtime_mode`
8. `recommended_governance_defaults`

## 状态模型建议

前台长 workflow 的状态一定要比后台轻。  
建议正式状态固定为：

1. `draft`
2. `ready`
3. `running`
4. `waiting_operator`
5. `paused`
6. `completed`
7. `failed`
8. `handed_off`

### 关键裁决

1. `phase`
   - 是 workflow 内部运行上下文
   - 不是主状态机
2. `approval_state`
   - 是治理子状态
   - 不替代 run status
3. `guard_condition_satisfied`
   - 是 judge result
   - 不替代 completed status

## 运行模型建议

### 1. Supervisor Agent 作为前台主控制循环

当前前台 shell 已有 Codex 主执行 + Cursor judge。  
产品化后，建议显式化为：

1. `supervisor agent`
   - 持有长 thread
   - 负责规划下一轮
   - 决定是否调用 executor/subagent
   - 决定是否请求 operator
2. `executor agent`
   - 执行具体 repo/task work
3. `reviewer/judge agent`
   - 输出结构化 verdict
4. `recovery agent`
   - 在失败时输出 bounded recovery proposal

### 2. Harness 保持四条硬边界

为了兼顾稳定性，agent 不能裸控一切。  
前台长 workflow 的 harness 至少保留：

1. run lifecycle boundary
2. approval boundary
3. receipt / trace boundary
4. handoff boundary

也就是：

1. agent 可以决定“下一步做什么”
2. harness 负责决定“这一步如何被记录、暂停、恢复、审计、移交”

### 3. `flow` 与 `autonomy` 分离

参考 CrewAI，建议明确二分：

1. `flow`
   - `launch -> turn -> intervene -> handoff`
   - 由 harness 驱动
2. `autonomy`
   - plan / execute / review / recover / delegate
   - 由 agent 驱动

## 稳定性与智能性的分层分工

前台长 workflow 如果要让 agent 成为主驱动，关键不是“哪一层更强”，而是每一层只守自己该守的边界。

| 目标 | 主收口层 | 具体承担 |
|---|---|---|
| launch / draft / operator surface | `Product Surface` | launch contract、timeline、operator action、compile preview |
| run 身份与轻主状态 | `Domain & Control Plane` | `ForegroundWorkflowRun`、`status`、`handoff boundary`、action audit |
| thread / turn / item / delegation visibility | `L4 Multi-Agent Session Runtime` | turn lineage、mailbox/handoff、subagent lifecycle、artifact visibility |
| pause / resume / checkpoint / lineage continuity | `L2 Durability Substrate` | checkpoint、resume pointer、writeback、handoff packet durability |
| execute / review / recover / delegate | `L1 Agent Execution Runtime` | supervisor / executor / reviewer / recovery execution receipt |

可执行裁决是：

1. 智能性主要来自 `supervisor/planner/reviewer/recovery` 的 agent 内环
2. 稳定性主要来自 `run status + session event + checkpoint + receipt + approval`
3. 产品层只能暴露这些边界，不能把它们混成一个“大一统智能对象”

因此前台长 workflow 的推荐组合不是：

`smart UI + free-form agent`

而是：

`stable harness spine + agent-driven inner loop`

## 产品面建议

### 1. 新增 `Workflow Studio`

当前 Draft Studio 更偏 draft-to-campaign。  
前台长 workflow 建议新增一块正式产品面：

1. `Launch Panel`
   - `single_goal`
   - `project_loop`
   - `research_loop`
   - `repo_fix_loop`
2. `Goal Contract`
   - 目标
   - 完成条件
   - guard condition
3. `Skill & Governance`
   - skill collection
   - risk level
   - autonomy profile
   - approval mode
4. `Compile Preview`
   - 预估 phase path
   - judge contract
   - prompt summary
   - artifact expectation
5. `Run Timeline`
   - phase
   - turn
   - decision
   - artifacts
   - receipts
6. `Operator Actions`
   - pause
   - resume
   - append instruction
   - retry phase
   - handoff to campaign

### 2. 新增 `Run History / Turn History`

参考 Dify，前台长 workflow 至少要有：

1. run history
2. turn history
3. per-turn artifact list
4. per-turn trace/receipt link

### 3. 新增 `Agent Delegation View`

为了让“agent 作为控制面主力”不变成黑盒，建议补一个可读面：

1. active supervisor
2. current executor
3. spawned subagents
4. delegation reason
5. handoff / mailbox summary

## API 草稿建议

建议新增一组与 `campaign` 平行、但更轻的前台 workflow API：

1. `POST /console/api/workflow-runs`
2. `GET /console/api/workflow-runs`
3. `GET /console/api/workflow-runs/{workflow_run_id}`
4. `GET /console/api/workflow-runs/{workflow_run_id}/events`
5. `GET /console/api/workflow-runs/{workflow_run_id}/timeline`
6. `POST /console/api/workflow-runs/{workflow_run_id}/actions`
7. `POST /console/api/workflow-runs/{workflow_run_id}/handoff`
8. `GET /console/api/workflow-drafts/{draft_id}/compile-preview`

动作建议先只开放：

1. `pause`
2. `resume`
3. `append_instruction`
4. `retry_phase`
5. `abort`
6. `handoff_to_campaign`

## 稳定性设计要点

如果前台 workflow 要让 agent 成为主控制力量，稳定性必须靠 harness 明确兜住。  
建议固定以下 8 条。

### 1. `Harness / App Split`

参考 DeerFlow：

1. 前台 UI 不是 runtime 真源
2. `ForegroundWorkflowRun` 是 product-facing control object
3. L1/L4 runtime 继续持有 execution/session 事实

### 2. `thread / turn / item` 事件模型

参考 Codex Harness / App Server：

1. 一个 run 对应多个 turn
2. 一个 turn 对应多个 item/event update
3. approval 请求可以在 turn 中断点触发

### 3. 结构化 guardrail / approval

参考 OpenAI Agents SDK 和 `02G`：

1. guardrail 不只是 prompt 文本
2. approval 不只是 UI 提示
3. 必须有正式字段和 receipt

### 4. resume 必须是正式语义

参考 LangGraph：

1. pause/resume 不是“重新启动”
2. 必须有 checkpoint / thread pointer
3. 恢复后能看见之前的 run lineage

### 5. subagent 继承式治理

参考 Codex Harness、Deep Agents、`02A`：

1. 子 agent 默认继承：
   - sandbox
   - approval policy
   - risk ceiling
   - trace context
2. 禁止子 agent 独立扩权

### 6. artifact/workspace 一体视图

参考 DeerFlow：

1. thread 与 workspace/artifact 要可关联
2. operator 能看见这轮 run 到底产出了什么
3. 不把所有结果都塞回文本总结

### 7. run/turn 历史必须可见

参考 Dify：

1. operator 不只看“现在”
2. 还应能看“刚才为什么跳转”

### 8. handoff 是正式边界

前台 run 长大后不应野生延长，应有：

1. `handoff recommended`
2. `handoff accepted`
3. `handoff packet committed`

## 智能性设计要点

稳定性靠 harness，智能性则主要来自 agent 的内环能力。  
建议前台长 workflow 在这 5 个地方加重 agent 权重。

### 1. 计划收缩

前台启动后，先由 supervisor/planner agent 把 goal 收紧，而不是直接裸跑 executor。

### 2. 动态 phase 调度

允许 supervisor agent 在 `plan / execute / review / recover` 之间动态切换，但切换结果必须通过结构化 turn receipt 体现。

### 3. 自检与复盘

每一轮结束后由 judge/reviewer agent 给：

1. blocker
2. confidence
3. next best action
4. 是否建议 handoff

### 4. bounded recovery

失败时不只是 RETRY，而是允许 recovery agent 输出有边界的修复计划。

### 5. selective delegation

前台 run 不需要天然多 agent，但当：

1. 任务超出单线程上下文
2. 需要并行探查
3. 需要独立 review

才触发 subagent delegation。

## 不建议的做法

为了避免前台 workflow 走向“更智能但更乱”，这里明确列出反模式。

1. 不把当前 `workflow shell` 本地文件直接提升为唯一产品真源
2. 不让 UI 直接修改 runtime/session/durability 对象
3. 不把 agent 自由文本输出当最终 run state
4. 不把前台长 workflow 直接复制成后台 `campaign` 的缩略版
5. 不直接把 vendor graph DSL / studio 命名灌回 Butler 真源

## 分期实施建议

### P0：先把前台 Workflow 变成产品对象

1. 新增 `ForegroundWorkflowRun` / `WorkflowTurnRecord`
2. 补 `run history / timeline / actions`
3. 让 console/query 能正式读前台 run
4. CLI 继续保留，但不再是唯一入口

### P1：把 Supervisor Agent 显式化

1. 把当前 judge loop 升级成显式 supervisor inner loop
2. 增加 planner/reviewer/recovery 三类可选 agent
3. 把 `thread / turn / item` 接进前台产品事件模型

### P2：把 handoff 做成正式升格路径

1. run -> campaign handoff packet
2. handoff receipt
3. handoff 后 query/console 能显示 lineage

### P3：把 Workflow Studio 接进现有 operator harness

1. 与 Draft Studio 共存
2. 前者偏 foreground agent run
3. 后者偏 draft-to-campaign authoring

## 如果转实施，建议固定的最小验收口径

这份文档当前只是草稿，但如果后续转实施，建议从第一波开始就把验收口径写死，避免“产品更智能了，但 run 事实更散了”。

1. `test_workflow_shell.py`
   - 前台 run / pause / resume / turn history 基本合同
2. `test_chat_cli_runner.py`
   - CLI 与前台 workflow run 入口语义一致
3. `test_console_server.py`
   - `workflow-runs` 查询、timeline、actions、handoff API 合同
4. 新增前台 run 查询/控制测试
   - 验证 `ForegroundWorkflowRun`、`WorkflowTurnRecord`、`WorkflowActionReceipt`
5. 新增 handoff 回归测试
   - 验证 `workflow run -> handoff packet -> campaign lineage`
6. 必要时补 `test_orchestrator_campaign_service.py`
   - 确认前台 handoff 没有反向污染后台 `campaign` 真源

## 建议的首批代码切入点

如果后续把这份草稿转成实施，建议优先检查：

1. `butler_main/agents_os/execution/workflow_shell.py`
   - run object / timeline / action contract 扩展
2. `butler_main/agents_os/execution/workflow_prompts.py`
   - supervisor/judge/recovery prompt 结构化
3. `butler_main/console/service.py`
   - 新增 workflow run 查询、控制、handoff 视图
4. `butler_main/console/server.py`
   - 新增前台 workflow run API
5. `butler_main/console/webapp/spa/src/`
   - 新增 Workflow Studio / Run Timeline / Handoff 面板
6. `tools/butler`
   - 保持 CLI 入口，但与 console API 语义统一

## 文档回写前提

如果这份草稿后续进入实施，应同步回写：

1. 当天 `00_当日总纲.md`
2. `0331/02_前台WorkflowShell收口.md`
3. `0330/02F_前门与Operator产品壳开发计划.md`
4. `0330/02A_runtime层详情.md`
5. `0330/02C_会话协作与事件模型开发计划.md`
6. `0330/02G_治理观测与验收闭环开发计划.md`
7. `Visual_Console_API_Contract_v1.md`
8. `docs/project-map/03_truth_matrix.md`
9. `docs/project-map/04_change_packets.md`
10. `docs/README.md`

当前阶段，这份文档只作为 `0331` 的产品化草稿入口，不替代现役真源。
