# 0326 Harness 全系统稳定态运行梳理

日期：2026-03-26  
时间标签：0326_0003  
状态：已形成系统总图 / 已补正式证据 / 可作为当前稳定态真源

## 一句话结论

当前 Butler 已经不再只是“chat 能回、orchestrator 能跑、campaign 能做 demo”的松散拼装，而是形成了一条可复读的完整 harness 主线：

`chat/frontdoor -> negotiation/query -> mission/campaign facade -> orchestrator runner/control plane -> process runtime/session substrate -> agent runtime/provider -> writeback -> observation/query -> chat/feishu feedback`

以“当前系统能否稳定持续运行、各部分是否都在发挥作用”为口径，本轮已经达到稳定态；剩余问题主要是架构真源继续收薄，而不是主线不能运转。

## 当前完整运行图

## 第 4 层：FrontDoor / Domain / Product Plane

这一层现在已经形成 4 个稳定职责：

1. `chat/mainline.py`
   - 负责统一前门
   - 分发 `chat / task_query / campaign_negotiation / mission_ingress`
2. `chat/negotiation.py`
   - 负责长任务协商、模板推荐、组合确认、后台启动边界
3. `chat/task_query.py`
   - 负责前门状态查询与已启动后台任务的跟进
4. `orchestrator/interfaces/*`
   - 负责第四层稳定消费面：`submit / query / control / feedback / campaign facade / observation`

当前这层的关键裁决已经成立：

- 长任务不会再默认掉回 chat 前台执行
- 已启动后台任务后的补充消息会优先走 feedback append
- campaign 不再只是“单模板 create”，而是“模板库 + 组合 + 协商启动”

## 第 3 层：Orchestrator / Control Plane

这一层当前已经比较清楚地退回控制面：

1. `Mission / MissionNode / Branch / LedgerEvent` 仍是控制面真源
2. `dispatch_ready_nodes()` 已经变成 session-aware dispatch
3. `runner` 负责常驻、tick、dispatch、auto_execute、恢复回收、运行状态写入
4. `query / observe` 负责统一把 mission/branch/session/campaign 投影成第四层证据面

当前这一层已经具备稳定持续运行所需的几件事：

- `auto_dispatch=true`、`auto_execute=true` 默认成立
- runner 启动前会检查 `pid_file / run_state / watchdog` 三处 owner
- runner 重启后会回收 `queued / leased / running` branch
- 观测面能看到 `workflow_ir_compiled / workflow_vm_executed / workflow_session_count`

## 第 2 层：Process Runtime

第二层现在已经不是文档概念，而是实际被 orchestrator 消费的运行时 substrate：

1. `ProcessExecutionOutcome / ProcessWritebackProjection / RuntimeVerdict`
   - 已成为统一 writeback 合同
2. `workflow_session`
   - 已在普通 path 和 campaign path 中真实落地
3. `workflow_session_bridge`
   - 负责 branch/session 绑定、恢复、结果更新、session summary
4. `governance_bridge`
   - 负责 approval / verification / recovery 的控制面消费与二层语义对接

当前这一层已经满足稳定态运行所需的最低要求：

- session 可创建、复用、恢复、更新、终结
- 普通 path 不再只是“一次 branch 调一次 runtime”
- writeback 不再靠 façade 内部散拼

## 第 1 层：Agent Runtime

第一层现在的正确理解是“CLI-native execution adapter layer”，而不是自造 agent 内核：

1. provider-native 能力由 `runtime_os.agent_runtime` 暴露
2. orchestrator 执行主干通过 execution bridge 消费这一层
3. campaign supervisor 可按 metadata 切 deterministic / Codex runtime
4. reviewer 继续保持独立 deterministic verdict

这层当前已满足稳定态要求，但仍有一笔明确技术债：

- `runtime_os.agent_runtime` 仍以 curated export wrapper 为主
- 这属于“继续真源化”的工作，不构成当前主线稳定运行阻塞

## 系统不是各转各的，而是如何连起来的

当前一条真实长任务路径已经是：

1. 用户从 chat/Feishu 进入前门
2. `RequestIntakeService` 给出 `should_discuss_mode_first / route / frontdoor_action`
3. `CampaignNegotiationService` 或 `FrontDoorTaskQueryService` 先处理协商/查询/跟进
4. 若需后台创建，chat 会先确保 orchestrator 在线，再进入 `mission_ingress`
5. orchestrator 创建 mission/campaign，并在 runner 周期中持续推进
6. branch dispatch 前先建或复用 `workflow_session`
7. `WorkflowVM` 决定走 `execution_bridge` 或 `research_bridge`
8. 执行结果统一落到 `ProcessExecutionOutcome`
9. service 统一回写 mission/node/branch/session
10. `query / observe / feedback_notifier` 把后台状态投影回前台与飞书

所以当前系统的稳定性，不再只取决于某一个模块，而取决于以下五个 harness 面同时成立：

1. `FrontDoor Harness`
2. `Control Harness`
3. `Execution Harness`
4. `Process Harness`
5. `Feedback Harness`

## 本轮补上的系统级增强

这轮新补的不是大协议，而是把稳定态观测补完整：

1. `stable_evidence` 现在在系统空闲但已完成时，也会回填最近一次 `branch / workflow / workflow_session`
2. 这解决了之前 observation window 在 idle 状态下“session_count 有，但 branch/workflow id 为空”的可复读性缺口
3. 因此当前稳定态证据不再只适用于“系统正在跑”，也适用于“系统已完成并进入稳定空闲”

## 当前稳定态证据

正式证据见：

- [20260326_campaign_smoke_evidence.json](../../runtime/acceptance/20260326_campaign_smoke_evidence.json)
- [20260326_campaign_negotiation_evidence.json](../../runtime/acceptance/20260326_campaign_negotiation_evidence.json)
- [20260326_harness_system_stability_evidence.json](../../runtime/acceptance/20260326_harness_system_stability_evidence.json)

本轮新增 `harness_system_stability_evidence` 证明了几件事：

1. `butler_bot` 与 `orchestrator` 两个独立服务当前都在线
2. runner 当前处于 `running / progressing / idle` 的稳定待机状态，而不是 stale 或空转异常
3. observation window 在 idle 状态下仍能保留最近一次 `mission / branch / workflow / session` 证据
4. 当前已有真实 `workflow_session_count > 0`
5. 当前已有真实 completed missions 与 linked campaign
6. 前门 / runner / feedback / campaign / control plane / runtime 这一组定向回归共 `86` 个用例通过

## 当前达到 100% 的含义

本轮说“100%”，口径只指：

1. 当前系统主线已经能稳定持续运行
2. chat、orchestrator、campaign、runner、query、observe、feedback 这些关键部件都在发挥作用
3. 当前正式证据已经能够证明“系统是一个整体”，而不是离散模块各自可跑

不包含的内容是：

1. 第 1 层彻底去兼容壳
2. 第 2 层 session/factory/workflow 全部物理真源化
3. 第 4 层继续扩更多 domain pack 或渠道

这些是后续继续收薄/真源化的工作，不影响当前稳定态判断。

## 剩余非阻塞技术债

1. `runtime_os.agent_runtime` 仍然主要是 legacy surface 的 curated export
2. 第二层 session/workflow/factory 仍有 compat-origin 历史包袱
3. 当前 live 任务没有挂 active Feishu feedback contract，因此 `feedback_notifier` 的 live push/doc 指标为 `0`
4. 这不代表反馈链路不可用，只代表当前在线任务没有把飞书反馈面作为实际交付面打开

## 后续推进原则

下一轮如果继续推进，不应再围绕“能不能跑”重复建设，而应只做两类工作：

1. 真源化
   - 继续把 `1 / 2 / 3 / 4` 的边界抽干净
2. 扩展稳定消费面
   - 在不破坏现主线的前提下，再补更多 domain pack、渠道反馈或自治循环

下一阶段正式计划已转入：

- [04_稳定Harness之后的下一阶段主线_Anthropic长运行Harness吸收版.md](./04_稳定Harness之后的下一阶段主线_Anthropic长运行Harness吸收版.md)

裁决保持不变：

- 不新增重规则系统
- 不让 orchestrator 回头吸收 process/runtime/domain 语义
- 不让第四层直接读二三层私有实现
