---
type: "note"
---
# 05 Orchestrator 完善设计与实施计划

日期：2026-03-25
时间标签：0325_0005
状态：`0325` 唯一活动计划 / Campaign MVP 主施工计划

## 一句话定位

1. 当前 orchestrator 的最准确定义不是“完整通用 workflow engine”，而是：**控制面已经成型、research 支线更深、普通执行面仍偏单 branch 驱动的 mission 编排内核。**
2. 今日 `Campaign MVP` 边界保持不变；本文件只负责把既定 MVP 路线压成唯一活动计划，不再额外扩题。
3. `orchestrator` 继续固定为第 `3` 层 control plane，不吸收新的第 `4` 层业务协议真语义。
4. [08_第四层接口冻结_V1_简化版.md](./08_第四层接口冻结_V1_简化版.md) 继续作为冻结件保持不变；本文件不得反向改写第四层端口、证据集和依赖边界。
5. [10_Codex原生能力边界与Butler吸收参考.md](./10_Codex原生能力边界与Butler吸收参考.md) 只作为原生能力实机验证与 harness 对接参考，不改变今日主施工顺序。
6. [11_Codex时代1_2_3层收口与并行推进计划.md](./11_Codex时代1_2_3层收口与并行推进计划.md) 作为补充收口件，回答 `Codex` 时代 `1 / 2 / 3` 层的删改增判断，并把 `Campaign MVP` 与 `research path` 统一降为架构验针；它不替代本文件的唯一活动计划地位。

## Codex 原生能力施工边界

1. 直接使用原生能力，不再在 Butler 内部重造平行外壳：
   - `subagents / multi_agent`
   - `review`
   - `resume / fork`
   - `MCP`
   - 项目级 `.codex/agents` role pack
2. Butler 只保留一层很薄的 harness 适配：
   - runtime policy 路由
   - 外部执行事实记录
   - role source 导出与校验
   - campaign 证据归一
3. Butler 必须继续自己保留为真源的部分：
   - 第 `2` 层 `runtime_os.process_runtime`
   - 第 `3` 层 `orchestrator control plane`
   - 第 `4` 层 `campaign domain protocol / supervisor layer`
4. 今日明确不做的事：
   - 不在 `agent_os` 或 `orchestrator` 里再造一套平行的 subagent runtime
   - 不把 Codex 的 session/thread 误判成 Butler 的 `workflow_session`
   - 不把 `review / resume / fork / MCP` 抬升成第 `2/3` 层真语义

## 当前已成立的东西

1. 入口层边界已经对：
   - `chat/mainline` 只做前门与路由。
   - `mission_orchestrator` 只保留 `create/status/control/feedback`。
   - runtime 细节没有再直接回流到 chat/product 层。
2. 控制面真源已经对：
   - `OrchestratorService` 持有 `Mission / MissionNode / Branch / LedgerEvent`。
   - `scheduler` 只做 ready 激活。
   - 预算、治理、状态写回留在 service。
3. 编译与执行边界已经出现：
   - branch dispatch 前会先编译成 `WorkflowIR`。
   - `WorkflowVM` 已经能按执行边界切到 `execution_bridge` 或 `research_bridge`。
4. session substrate 已经不是概念稿：
   - `multi_agents_os` 已有 `template / session / shared_state / artifact_registry / blackboard / collaboration / event_log`。
5. research path 已经更接近真实 workflow：
   - `dispatch / step / handoff / decision` 能被投影回 session substrate。

## 当前核心缺口

1. 普通 path 仍然主要是一次 branch 对一次 runtime 调用。
2. `agent_os` 还没有被正式拆成 `Agent Runtime` 与 `Process Runtime` 两层，导致很多通用 workflow/gate 语义仍然悬空。
3. approval / verification / recovery 目前虽然已临时统一回 orchestrator，但普通 path 里还没有完全变成显式的 runtime/session gate。
4. 普通 path 对 `shared_state / artifact / mailbox / join contract` 的消费远弱于 research path。
5. 本地 run data 还没有真实证明新版链路被普通任务使用：
   - 当前仅有 `mission_f0244ac4c4ca`
   - `workflow_session_count = 0`
   - runtime 观测窗口显示 runner `stale`
6. 兼容壳仍然存在，抽核尚未完全收尾。

## 第一阶段真实收口

截至 `2026-03-25 11:09`，本文件不再只是设计稿，而需要承认下面这些已经成为当前主干事实：

1. `runtime_os` 根兼容命名空间已成立，`process_runtime` 表面已经独立成型。
2. `orchestrator` 中与治理相关的部分已经开始经 `runtime_bridge/governance_bridge.py` 收口，不再全部堆在 `service.py`。
3. 第四层消费面已经有独立冻结件：
   - `butler_main/orchestrator/fourth_layer_contracts.py`
   - `query_service` 的 `mission_view / branch_view / session_view / observation snapshot`
   - `08_第四层接口冻结_V1_简化版.md`
4. 当前相关验收不是口头判断，而是已有 `45` 个相关测试通过，说明一阶段已经可以从“并行探索”转入“第二阶段抽核施工”。
5. 因此，本文件后面的重点不再是证明方向对不对，而是明确第二阶段的主施工包、依赖关系和 done 定义。

## 目标态

1. `Mission` 继续是控制面对象。
2. `MissionNode` 从“发一次 branch 的任务节点”升级成“声明一个可执行 workflow 单元的调度节点”。
3. `Branch` 明确退回为：
   - 一次执行尝试
   - 一次恢复尝试
   - 一次 session 驱动的外部执行票据
4. `WorkflowSession` 成为普通 path 和 research path 共同依赖的运行时实例容器。
5. `WorkflowVM` 成为统一的流程执行入口：
   - 普通 path 走最小 workflow 语义
   - research path 走更深的 research 语义
   - 两者共享 event、artifact、resume、governance contract
6. `approval / verification / recovery` 成为显式 gate 语义，但真源回到 `agent_os process runtime`，而不是继续主要依赖 `orchestrator service`。
7. `orchestrator` 明确退回第三层控制面，只消费 runtime verdict，不再兼任通用治理执行层。

## 3 / 2 / 1 硬冻结版

### A. 主轴

1. 本轮先按 `3 -> 2 -> 1` 冻结：
   - `3 = orchestrator / control plane`
   - `2 = runtime_os / process runtime`
   - `1 = runtime_os / agent runtime`
2. `orchestrator` 之后只回答三类问题：
   - 哪个 `mission/node/branch` 该被派发
   - 何时派发或恢复
   - runtime 结果如何投影回控制面
3. 任何超出上述范围的通用流程语义，默认都不是第 3 层职责，而应回到第 2 层。

### B. 第 3 层的正式职责

1. `Mission / MissionNode / Branch / LedgerEvent` 真源。
2. `scheduler / policy / branch budget / node activation`。
3. `mission -> compile plan -> runtime bridge -> writeback`。
4. `query / observe / runner / ingress` 这些产品口与运维口。

### C. 第 3 层明确不该负责

1. 不定义 `approval / verification / recovery / resume` 的真执行语义。
2. 不直接维护 `WorkflowSession` 的私有文件结构与 session 内部状态机。
3. 不把 `WorkflowIR` 继续做成包含所有层语义的混装对象。
4. 不让 `research_bridge` 或其他 domain bridge 继续直接摸 `service` 私有内脏。

### D. `service.py` 的目标拆法

1. `service.py` 的长期目标不是继续做“大总管”，而是退回第 3 层 application facade。
2. 首批应拆出去的不是 mission graph，而是以下几类重语义：
   - approval gate
   - verification gate
   - recovery / resume
   - workflow session 内部更新
3. 拆完之后 `service.py` 应主要保留：
   - `create_mission`
   - `dispatch_ready_nodes`
   - `record_branch_outcome`
   - `resolve_node_approval`
   - `tick`
   - query / summary / observation 入口
4. 这些入口内部只消费 runtime verdict，不再自己解释完整 gate 过程。

### E. `WorkflowIR` 的裁决

1. 当前阶段允许保留 `WorkflowIR`，但只把它看成 `3 -> 2` 的过渡 envelope。
2. `WorkflowIR` 从现在起必须按三块理解：
   - compile/projection 字段
   - process runtime 字段
   - observability 字段
3. `orchestrator` 负责前后两块：
   - compile/projection
   - observability
4. 第 2 层只消费 process runtime 字段。
5. 长期目标是把它拆成两个对象：
   - `MissionExecutionPlan`
   - `ProcessStartRequest`

## 非目标

1. 不是立刻做分布式 durable workflow 平台。
2. 不是把 `multi_agents_os` 重新做成总调度器。
3. 不是今天就把所有普通 branch 一次性重写成复杂 DAG engine。
4. 不是为了追求“通用”而打散已经正确收口的 chat/product 边界。

## 设计原则

1. 保持 `mission_ingress -> mission_orchestrator -> orchestrator service` 边界不动。
2. 控制面仍以 `OrchestratorService` 为唯一控制面真源，但不再承担通用 runtime/gate 语义真源。
3. 编译面负责声明，不负责直接执行业务特例。
4. 执行面优先补“普通 path 最小 workflow 化”，不追求一次做成全图引擎。
5. research path 不是特例垃圾桶，而是普通 path 演进时可复用的先进样板。
6. 观测与落盘必须和能力演进同步推进，不能继续出现“代码已有，run data 无证据”的状态。
7. 第 3 层只能依赖第 2 层公开 API，不能回头依赖第 2 层私有实现。
8. 第 3 层不再新增对 `agents_os`、`multi_agents_os` 旧目录的直接依赖。

## 完善设计

### A. 执行模型统一

1. 新的统一语义应是：
   - `mission` 驱动 `node`
   - `node` 编译出 `workflow_ir`
   - `workflow_ir` 驱动 `workflow_session`
   - `branch` 记录一次执行尝试与结果回写
2. 普通 path 先分两级演进：
   - `P1`：session-aware branch execution
   - `P2`：真正多步 workflow execution
3. `P1` 的关键不是追求复杂多步，而是让普通 path 先具备：
   - 稳定 `workflow_session_id`
   - 可 resume 的执行票据
   - session 级 artifact/shared_state 写回
4. `P2` 再补：
   - `step`
   - `handoff`
   - `join`
   - `wait/gate`
   - 非终态 branch receipt

### B. 普通 Path 的 Workflow 化

1. `dispatch_ready_nodes()` 继续作为 node 激活后的入口，但它 dispatch 的不再只是 branch，而是：
   - 先确保 session 建立或恢复
   - 再创建 branch attempt
   - 再写入编译后的 `workflow_ir`
2. `execution_bridge` 需要补一版统一回执模型，至少区分：
   - `completed`
   - `awaiting_approval`
   - `awaiting_verification`
   - `repair_scheduled`
   - `resumable`
3. `WorkflowVM.execute_and_record()` 需要把“终态/非终态”从 research path 扩展到普通 path，而不是默认普通 path 一次打穿。
4. `record_branch_result()` 的长期目标不是只接 `ok/fail`，而是接统一 execution outcome。

### C. 治理语义显式化

1. approval / verification / recovery 的控制面消费点仍在 orchestrator service。
2. 但它们的执行语义真源应逐步迁回 `runtime_os process runtime`，而不是继续把 orchestrator 当治理内核。
3. gate 状态应逐步从 node metadata 拼接，迁到更正式的 session/receipt contract：
   - `gate_type`
   - `gate_status`
   - `resume_from`
   - `decision_ref`
   - `repair_attempt`
4. `WorkflowIR` 继续承载 policy 引用：
   - `approval_policy_ref`
   - `verification_policy_ref`
   - `recovery_policy_ref`
5. service 只消费 policy 与 runtime verdict，不回头把执行器做成治理真源。

### D. Session Substrate 共享化

1. research path 已经会投影到：
   - `shared_state`
   - `artifact_registry`
   - `mailbox`
   - `join contract`
2. 普通 path 下一步也必须共享这套 contract，哪怕初始只消费最小子集：
   - `shared_state`
   - `artifact_registry`
   - `workflow_blackboard`
3. `mailbox / handoff / join` 可以先从编译输出和 projection 契约冻结开始，不要求首日全部跑通。

### E. 观测与运维

1. `observe/query` 需要明确区分三类对象：
   - control plane：mission/node/branch
   - session plane：workflow_session/template/shared_state/artifact/collaboration
   - runtime plane：runner/watchdog/execute summary
2. `mission overview` 的 `workflow_session_count` 必须变成有实际意义的指标，而不是长期为 `0`。
3. `smoke` 和 `demo_fixtures` 需要至少产出一条普通 path session 样例。
4. runner 当前 `stale` 的问题至少要有清晰口径：
   - 是运维问题
   - 还是链路根本没被使用
   - 还是 demo 未建立

### F. 兼容迁移

1. 保留 `butler_bot_code/.../orchestrators` 的兼容壳，但不再让它承载新语义。
2. 旧调用路径统一经 re-export 指向 `butler_main/orchestrator`。
3. 新增能力优先落在新核，不在兼容壳重复实现。
4. 旧 branch-only 流程允许继续存在，但需要被明确标成过渡态。

## 第二阶段施工包

第二阶段不再建议拆成很多碎任务，而是以四个中等偏大的施工包推进。每个包都应足够大到改变真实边界，但不承担“一次性重写全系统”的不现实目标。

### 包 2A：`runtime_os` 真抽核

目标：

1. 把第 2 层的真语义进一步从兼容表面压实到 `runtime_os.process_runtime`。
2. 把 `workflow / session / governance / bindings` 的正式公开 API 固定下来。
3. 让 `agents_os / multi_agents_os` 只保留兼容壳，不再新增真语义。

主要文件：

- `butler_main/runtime_os/process_runtime/*`
- `butler_main/agents_os/process_runtime/*`
- `butler_main/multi_agents_os/session/*`
- `butler_main/multi_agents_os/templates/*`

参考文档：

- `00_当日总纲.md`
- `03_Collaboration_Substrate_Typed_Primitives.md`
- `07_任务包B_process_runtime收口交付.md`

完成判定：

1. `approval / verification / recovery` 至少有一条正式 runtime receipt contract，不再主要依赖 `orchestrator.service` 私有拼装。
2. `workflow_session / shared_state / artifact_registry / template` 的正式入口清楚落在 `runtime_os.process_runtime`。
3. 旧目录新增代码只允许兼容转发。

### 包 2B：`orchestrator` 物理分层

目标：

1. 把今天已经在概念上冻结的第 3 层，落成真实目录与 import 层级。
2. 让 `service.py` 从“大总管”退回 control plane façade。
3. 建立 `domain / application / compile / runtime_bridge / interfaces / infra / fixtures` 的目录骨架。

主要文件：

- `butler_main/orchestrator/service.py`
- `butler_main/orchestrator/models.py`
- `butler_main/orchestrator/compiler.py`
- `butler_main/orchestrator/workflow_ir.py`
- `butler_main/orchestrator/workflow_vm.py`
- `butler_main/orchestrator/runtime_bridge/*`

参考文档：

- `00_当日总纲.md`
- `05_Orchestrator完善设计与实施计划.md`
- `07_任务包C_orchestrator_control_plane收缩交付.md`

完成判定：

1. `service.py` 明显变薄，重语义下沉到更清楚的 `application / runtime_bridge / compile`。
2. 第 3 层对第 2 层的依赖只走公开 API，不再继续摸 session substrate 私有实现。
3. 目录一眼能看出控制面层级，而不是继续扁平堆放。

### 包 2C：普通 Path Workflow 化

目标：

1. 把“普通 path 已 session-aware”推进到“普通 path 真正开始可 resume / wait / gate / 非终态回执”。
2. 让普通 path 不再只是一次 branch 对一次 runtime call。
3. 让观察面能清楚看到普通 path 的 session 和非终态证据。

主要文件：

- `butler_main/orchestrator/workflow_vm.py`
- `butler_main/orchestrator/execution_bridge.py`
- `butler_main/orchestrator/runtime_bridge/*`
- `butler_main/orchestrator/query_service.py`
- `butler_main/orchestrator/smoke.py`

参考文档：

- 本文 `P1 / P2 / P3`
- `07_任务包D_总收口与集成验收交付.md`
- `08_第四层接口冻结_V1_简化版.md`

完成判定：

1. 至少一条非 research path 出现稳定 `workflow_session_id` 与非终态回执。
2. `query / observe / smoke` 至少两处能看见普通 path 的 `resume/gate` 证据。
3. `record_branch_result()` 开始消费统一 runtime verdict，而不是只接 `ok/fail`。

### 包 2D：命名 Codemod 与边界守卫

目标：

1. 用脚本化方式推进 `agents_os -> runtime_os`，避免长期停留在人工搬运。
2. 为第 4 层和第 3 层建立禁止 import 守卫。
3. 把第二阶段里 A/B/C 的兼容尾项、边界回归和文档回填统一吸收。

主要文件：

- codemod / rename 脚本
- `butler_main/orchestrator/__init__.py`
- 第四层 contract 与相关测试
- import 边界测试与兼容测试

参考文档：

- `00_当日总纲.md`
- `07_任务包A_runtime_os命名迁移与兼容期方案.md`
- `08_第四层接口冻结_V1_简化版.md`

完成判定：

1. 新增 consumer 默认走 `runtime_os` 命名空间。
2. 第四层不再继续扩大对 `service.py / workflow_vm / multi_agents_os` 私有实现的直接依赖。
3. 第二阶段结束时，ABC 不会再次留下需要临时总收口的散项。

## 长期自治 Campaign 开发态裁决

经过概念修正后，长期自治层的归属已经明确：

1. 它不是 `3.5` 层，也不是 `orchestrator` 的延伸语义。
2. 它正式归入第 4 层，并建议命名为：
   - `campaign domain protocol / supervisor layer`
3. 因此，当前后续工作的终点不再只是“边界更清楚”，而是：
   - 交付一个可用的最小 `Campaign MVP`

### Campaign MVP 的完成定义

1. 只支持 `单 workspace / 单 repo / 单 campaign`
2. 对外可用接口至少包括：
   - `create_campaign`
   - `get_campaign_status`
   - `list_campaign_artifacts`
   - `resume_campaign`
   - `stop_campaign`
3. `create_campaign()` 后必须能：
   - 创建长期 `campaign mission`
   - 创建 `campaign_supervisor` session
   - 自动完成首轮 `Discover`
   - 产出第一版 `WorkingContract`
4. `resume_campaign()` 后必须能：
   - 推进一轮有边界的 `Implement -> Evaluate -> Iterate`
   - 由独立 reviewer/evaluator 给最终 verdict
   - 在未收敛时局部改写 `WorkingContract`
5. 顶层 `goal` 与 `hard_constraints` 不可被自动改写。
6. run data、artifact、session、verdict 与 contract rewrite 必须可追溯。

### 转开发态后的主施工顺序

1. `D0 概念修正完成`
   - 第 4 层补出 `campaign domain protocol / supervisor layer`
   - `09` 成为开发态输入，而不是继续漂浮的讨论稿
2. `D1 架构完善`
   - 补齐 `Campaign MVP` 必需的 `L3/L2` 消费 contract
   - 明确 `campaign` 代码落位，避免继续塞进 `orchestrator core`
3. `D2 Campaign Domain MVP`
   - 落 `CampaignSpec / CampaignInstance / WorkingContract / EvaluationVerdict / IterationBudget`
   - 落 `campaign supervisor` 与外层 phase runtime
4. `D3 闭环验收`
   - query / observe / run data / artifacts 一起完成
   - 证明这不是讨论稿，而是可用功能

### 推荐代码落位

1. 第 4 层 campaign 真源建议落在：
   - `butler_main/domains/campaign/*`
2. 对外薄接口建议落在：
   - `butler_main/orchestrator/interfaces/campaign_service.py`
3. 原则保持不变：
   - campaign 业务协议不进入 `orchestrator core`
   - orchestrator 只托管长期 mission 与控制面状态
   - runtime_os 只承接执行、session 与恢复 substrate

## 分阶段计划

### P0. 口径冻结

1. 目标：
   - 冻结 orchestrator 当前定位、目标态、非目标、阶段边界。
   - 冻结 `3 / 2 / 1` 主轴、公开 API 与禁止依赖。
   - 冻结 `WorkflowIR` 的过渡定位与后续拆分方向。
2. 代码与文档落点：
   - `docs/daily-upgrade/0325/00_当日总纲.md`
   - `docs/daily-upgrade/0325/05_Orchestrator完善设计与实施计划.md`
3. 验收：
   - 后续 Lane A-D 都以这版定位为约束，不再把 orchestrator 误写成已经完成的通用 workflow engine。
   - 第 3 层不再新增 runtime/gate 真语义。

### P1. 普通 Path Session 化

1. 目标：
   - 让普通 branch 路径稳定产出 `workflow_session_id`，并且 session 真有运行态写回。
2. 代码优先落点：
   - `butler_main/orchestrator/service.py`
   - `butler_main/orchestrator/workflow_vm.py`
   - `butler_main/orchestrator/execution_bridge.py`
   - `butler_main/multi_agents_os/factory/workflow_factory.py`
3. 需要补的能力：
   - 普通 path 的 session 准备与恢复 contract
   - branch -> session 的统一写回
   - session 级 artifact/shared_state 最小投影
4. 测试建议：
   - `test_orchestrator_workflow_vm.py`
   - `test_orchestrator_core.py`
   - `test_orchestrator_runner.py`
5. 验收：
   - 一条非 research mission 的 `workflow_session_count > 0`
   - `observe session` 能看到真实 session 状态

### P2. 普通 Path 最小多步 Workflow 化

1. 目标：
   - 让普通 path 不再只能一次 branch 打穿。
2. 代码优先落点：
   - `butler_main/orchestrator/workflow_vm.py`
   - `butler_main/orchestrator/workflow_ir.py`
   - `butler_main/orchestrator/compiler.py`
   - `butler_main/orchestrator/execution_bridge.py`
3. 需要补的能力：
   - step receipt
   - wait/gate
   - resume contract
   - join/handoff 的最小消费位
4. 测试建议：
   - `test_orchestrator_workflow_vm.py`
   - `test_orchestrator_smoke.py`
5. 验收：
   - 至少一条普通 path 多步流
   - 至少一条普通 path 非终态 -> resume 流

### P3. 治理 Session 化

1. 目标：
   - 把 approval / verification / recovery 从“service 临时托管”推进到“agent_os runtime 显式 gate + orchestrator 消费 verdict”。
2. 代码优先落点：
   - `butler_main/agents_os/runtime/execution_runtime.py`
   - `butler_main/agents_os/workflow/*`
   - `butler_main/orchestrator/service.py`
3. 需要补的能力：
   - gate receipt
   - session gate state
   - resume_from / decision writeback
4. 测试建议：
   - `test_orchestrator_core.py`
   - `test_orchestrator_workflow_vm.py`
   - `test_orchestrator_runner.py`
5. 验收：
   - approval / verification / recovery 至少一类不再主要靠 node metadata 承载运行语义
   - orchestrator service 开始消费 runtime verdict，而不是自己解释完整 gate 语义

### P4. Typed Collaboration Primitive 共享化

1. 目标：
   - 普通 path 开始消费与 research path 对齐的 collaboration primitive。
2. 代码优先落点：
   - `butler_main/multi_agents_os/session/collaboration.py`
   - `butler_main/multi_agents_os/session/contracts.py`
   - `butler_main/orchestrator/research_projection.py`
   - `butler_main/orchestrator/execution_bridge.py`
3. 最小范围：
   - `artifact_visibility_scope`
   - `workflow_blackboard`
   - `mailbox / join_contract` 的正式读取位
4. 测试建议：
   - `test_multi_agents_os_collaboration.py`
   - `test_orchestrator_research_projection.py`
5. 验收：
   - 至少一条普通 path 与 research path 共享同类 substrate 观测对象

### P5. Demo、观测与兼容收口

1. 目标：
   - 让 run data、smoke、observe 真正展示新版链路。
2. 代码优先落点：
   - `butler_main/orchestrator/smoke.py`
   - `butler_main/orchestrator/demo_fixtures.py`
   - `butler_main/orchestrator/query_service.py`
   - `butler_main/orchestrator/observe.py`
3. 需要补的能力：
   - 普通 path session demo
   - framework profile demo
   - stale runner 口径和运维说明
4. 验收：
   - 至少一条普通 path demo
   - 至少一条 framework-native demo
   - 观测窗口能同时看见 mission、branch、session、runtime

## 今日首批落点建议

1. 先不扩大概念，优先把 `P0 + P1` 说清并开始落地。
2. 第一批最值得动的文件是：
   - `butler_main/agents_os/runtime/execution_runtime.py`
   - `butler_main/multi_agents_os/session/workflow_session.py`
   - `butler_main/multi_agents_os/session/shared_state.py`
   - `butler_main/orchestrator/service.py`
   - `butler_main/orchestrator/workflow_vm.py`
   - `butler_main/orchestrator/workflow_ir.py`
3. 第一批最值得补的测试是：
   - 一条 runtime gate / resume 语义测试
   - 一条普通 path session 创建/恢复测试
   - 一条普通 path `observe session` 测试
   - 一条 orchestrator 消费 runtime verdict 的测试

## 风险与控制

1. 风险：把 orchestrator 目标态写得过满，反而让团队误判“已经是通用 workflow engine”。
   - 控制：明确 `P1 -> P2` 两级演进，不跨级承诺。
2. 风险：普通 path workflow 化时回头侵入 chat/product 边界。
   - 控制：所有新语义仍从 `mission_orchestrator -> service` 进入。
3. 风险：继续只有 research path 真正在用 session substrate。
   - 控制：把“非 research session 样例”设为硬验收项。
4. 风险：观测与 demo 跟不上，导致代码进展无法被 run data 证明。
   - 控制：`P5` 不作为收尾附属，而是从今天开始提前冻结验收对象。

## 结论

1. 当前 orchestrator 不需要推倒重来，主边界是对的。
2. 下一阶段真正要做的，不是再解释一遍“它像 workflow”，而是让普通 path 真正共享 workflow/session/governance substrate。
3. 所以最合理的推进顺序是：
   - 先冻结定位
   - 再把普通 path session 化
   - 再补普通 path 多步 workflow/gate/resume
   - 最后用 demo、observe、run data 证明这条链路真的活了
