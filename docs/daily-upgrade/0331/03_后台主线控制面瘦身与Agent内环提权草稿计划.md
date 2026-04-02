# 0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写

日期：2026-03-31  
状态：已落代码 / 实施回写（文件名保留历史“草稿计划”字样）  
所属层级：`Domain & Control Plane` 主层，触达 `L4 Multi-Agent Session Runtime`、`L1 Agent Execution Runtime`  
关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [0329 后台任务双状态与前门弱化重构](../0329/03_后台任务双状态与前门弱化重构.md)
- [0330/02A_runtime层详情.md](../0330/02A_runtime层详情.md)
- [0330/02C_会话协作与事件模型开发计划.md](../0330/02C_会话协作与事件模型开发计划.md)
- [0330/02G_治理观测与验收闭环开发计划.md](../0330/02G_治理观测与验收闭环开发计划.md)
- [系统分层与事件契约](../../runtime/System_Layering_and_Event_Contracts.md)

## 一句话裁决

`0331` 这轮已把后台 campaign 主线从“厚控制链”收口成：

`campaign 宏账本 -> workflow_session 内环状态 -> agent turn receipt -> harness 持久化/恢复/设施`

本轮现役裁决固定为：

1. `campaign` 继续保留为后台主线的宏观身份与账本真源
2. `workflow_session` 承担细粒度运行态、上下文、artifact 与 turn 轨迹
3. `agent` 成为默认主控者，按 turn 直接提交大多数宏状态
4. `harness` 只保留结构校验、记录、恢复、artifact/session 基础设施
5. `mission/node/branch/runner` 退出 campaign 主链，只保留给非 campaign 的旧 orchestrator 路径
6. 对外稳定面收口到：`campaign_id`、`canonical_session_id`、宏 `status`、`task_summary`

## 本文边界

本文现在是 `0331` 这轮实现后的**专题真源**。  
当前 campaign 新主线已经在代码中生效；旧 `mission/runner` 路径仍保留，但只作为兼容与非 campaign 流程使用。

## 已落实现范围

### 1. 控制面收薄为宏账本

`CampaignDomainService` 新主线把 `campaign.status` 收敛为宏状态：

- `draft`
- `running`
- `waiting`
- `paused`
- `completed`
- `failed`
- `cancelled`

`campaign.metadata` 当前主保存：

1. 身份与入口：
   - `campaign_id`
   - `control_plane_refs.canonical_session_id`
2. 合同与治理：
   - `planning_contract`
   - `governance_contract`
3. 最近提交结果：
   - `latest_summary`
   - `latest_next_action`
   - `latest_delivery_refs`
   - `latest_verdict`
   - `latest_turn_receipt`
4. 设施引用：
   - `bundle_root`
   - `bundle_manifest`
   - `turn_cursor`
   - `legacy_refs`

旧 `current_phase / next_phase / execution_state / closure_state / progress_reason / operator_next_action` 仍可做兼容读取，但不再是新主线驱动真源。

### 2. Agent 接管主循环

`resume_campaign()` 对新 campaign 的语义已固定为“执行一个可重入 supervisor turn”。  
当前每次 turn 的持久化结果是 `CampaignTurnReceipt`，固定字段包括：

- `turn_id`
- `campaign_id`
- `session_id`
- `macro_state`
- `summary`
- `next_action`
- `delivery_refs`
- `verdict`
- `artifact_records`
- `session_patch`
- `advisory_updates`
- `continue_token`
- `yield_reason`

turn receipt 追加写入 `turns.jsonl`；`workflow_session` shared state、blackboard、artifact registry 同步由 harness/factory 负责。

### 3. Campaign 路径绕开 Runner

`OrchestratorCampaignService.create_campaign()` 对新 campaign 不再创建 `mission/node/branch`，而是：

1. 归一化 spec / contract / feedback metadata
2. 创建 `campaign + workflow_session`
3. 回填 `canonical_session_id`
4. 初始化 bundle 与首份 `task_summary`

因此新 campaign 的 `mission_id` 默认允许为空；`supervisor_session_id` 继续兼容存在，但语义已降级为 `canonical_session_id` 的旧字段。

### 4. Query / Feedback / Console 收口

对外稳定消费面当前优先读取：

1. `campaign_id`
2. `canonical_session_id`
3. 宏 `status`
4. `task_summary`

当前 `task_summary` 稳定结构为：

- `spec`
- `progress`
- `next_action`
- `risk`
- `output`
- `closure`

`feedback_notifier` 现已优先从 `task_summary`、`latest_*` 与 `latest_turn_receipt` 取材；只有旧 campaign 才回退到兼容语义计算。

### 5. 新增/显式接口

当前代码里已补齐：

- `CampaignDomainService.run_campaign_turn(campaign_id, reason="...")`
- `CampaignDomainService.summarize_campaign_task(campaign_id)`
- `OrchestratorCampaignService.run_campaign_turn(workspace, campaign_id, reason="...")`
- `OrchestratorCampaignService.summarize_campaign_task(workspace, campaign_id)`

### 6. Console 已对齐新主线

本轮又补一轮 console 复核与修复，当前 `visual console` 对新 campaign 的现役口径固定为：

1. graph / board 不再把 `discover -> implement -> evaluate -> iterate` 当主视图
2. campaign graph 当前改为：
   - `ledger`
   - `turn`
   - `delivery`
   - `harness`
3. `control-plane` 主展示改成：
   - `canonical_session_id`
   - `macro_state`
   - `narrative_summary`
   - `operator_next_action`
   - `latest_turn_receipt`
   - `latest_delivery_refs`
   - `harness_summary`
4. operator 主动作收口为：
   - `pause`
   - `resume`
   - `abort`
   - `annotate_governance`
   - `force_recover_from_snapshot`
   - `append_feedback`
5. 旧 `force_transition / skip_to_step` 仅保留兼容入口，不再作为主 UX 合同
6. campaign-alone `append_feedback` 现在直接路由到 canonical workflow session，不再要求 `mission_id`

## 本轮代码落点

- `butler_main/domains/campaign/models.py`
- `butler_main/domains/campaign/store.py`
- `butler_main/domains/campaign/service.py`
- `butler_main/domains/campaign/status_semantics.py`
- `butler_main/orchestrator/interfaces/campaign_service.py`
- `butler_main/orchestrator/interfaces/query_service.py`
- `butler_main/orchestrator/fourth_layer_contracts.py`
- `butler_main/orchestrator/feedback_notifier.py`
- `butler_main/console/service.py`
- `butler_main/console/webapp/spa/src/`

## 本轮回归

- `test_campaign_domain_runtime.py`
- `test_orchestrator_campaign_service.py`
- `test_orchestrator_campaign_observe.py`
- `test_orchestrator_feedback_notifier.py`
- `test_console_services.py`
- `test_console_server.py`

## 兼容口径

1. 显式 `legacy_supervisor` runtime 仍走旧 supervisor/reviewer 链
2. 旧 campaign 上的 `mission_id / supervisor_session_id / branch refs` 统一降级为 `legacy_refs`
3. `build_campaign_semantics()` 对新 campaign 仍保留兼容投影，但不再是 feedback/query 的首选真源

## 历史背景

下面保留本轮改造前的设计分析，作为为什么要做这次收薄的背景说明。

## 当前问题判断

### 1. 控制面当前为什么显得“厚”

当前代码里，`campaign` 不只是业务主载体，还额外承担了几类职责：

1. 业务合同与阶段推进
2. 验收 blocker、进度原因、闭环原因的状态语义回写
3. `spec.metadata` 的镜像同步
4. `mission / workflow_session` 的绑定与回填辅助
5. operator patch 和 operator receipt 记录

这会让控制面从“真源提交层”膨胀成“业务 + 运行 + 派生摘要”的混合层。

### 2. 当前最主要的复杂性来源

#### A. 派生状态回写进真源

`execution_state / closure_state / progress_reason / latest_acceptance_decision` 这类字段当前由 `build_campaign_semantics()` 计算后再写回 `instance.metadata`。  
这一步见：

- `butler_main/domains/campaign/service.py::_refresh_status_semantics`

随后又会同步回 `spec.metadata`，见：

- `butler_main/domains/campaign/service.py::_sync_spec_metadata`

结果是：

1. 真源里保留了大量本可读时计算的派生状态
2. projection、业务真源、spec 镜像三处更容易打架

#### B. 同一任务同时存在多层状态

当前同一条后台任务至少同时存在：

1. `campaign.status / current_phase / next_phase`
2. `mission.status`
3. `node.status`
4. `branch.status`
5. `workflow_session.status / active_step`
6. `execution_state / closure_state`
7. `approval_state`

这些状态各自都合理，但叠在一起时，控制面的同步成本很高。

#### C. 控制面承担了运行同步桥职责

`OrchestratorCampaignService.create_campaign()` 当前会一次性建立：

1. `mission`
2. `supervisor_session`
3. `campaign`

然后还会：

1. 把 session 绑定回 mission node
2. 用 campaign payload 回填 session shared state、blackboard、artifact
3. 再 arm mission

这意味着控制面除了拥有真源，还同时在做 runtime bridge。

#### D. operator 写口过强

`apply_operator_patch()` 当前可直接改：

1. `status`
2. `current_phase`
3. `next_phase`
4. `metadata`

这对救火有价值，但也意味着平时系统复杂度无法完全靠结构约束收住。

## 当前后台主线的正确结构

在现役架构里，后台主线应继续理解为：

1. `chat/frontdoor`
   - 协商、查询、跟进
2. `OrchestratorCampaignService`
   - 建 `mission + session + campaign`
3. `runner`
   - `tick -> dispatch -> execute -> feedback`
4. `CampaignDomainService`
   - `discover -> implement -> evaluate -> iterate`
5. `query / feedback / console`
   - 只读投影与受控动作

当前结构的问题不是“完全错层”，而是第 2 步到第 4 步之间的职责边界太厚。

## 目标架构草图

### 目标一：薄控制面

控制面后续只保留下面几类正式事实：

1. 任务身份
   - `campaign_id`
   - `mission_id`
   - `canonical_session_id`
2. 少量宏观状态
   - `draft`
   - `running`
   - `waiting`
   - `blocked`
   - `completed`
3. 治理参数
   - `risk_level`
   - `autonomy_profile`
   - `approval_state`
4. 最终提交边界
   - `acceptance verdict committed`
   - `delivery refs committed`
   - `recovery decision committed`

控制面不再长期保有大量细 phase 派生态。

### 目标二：强 Supervisor Agent 内环

当前 `discover -> implement -> evaluate -> iterate` 这套循环，后续逐步收进 supervisor agent 的内部运行循环：

1. supervisor agent 负责：
   - 细化计划
   - 调 executor / subagent
   - 汇总阶段证据
   - 发起 review
   - 给出 recovery proposal
2. 控制面只看：
   - 当前 turn/round 的 receipt
   - 是否请求审批
   - 是否遇到 blocker
   - 是否满足提交边界

### 目标三：Hybrid Reviewer

reviewer 从“纯代码决定一切”逐步改成：

1. `agent reviewer`
   - 负责语义层评审
   - 输出结构化 `decision / blockers / evidence_refs / next_goal`
2. `code validator`
   - 负责硬校验：
   - `deliverable_refs`
   - `pending_correctness_checks`
   - `receipt / trace`
   - `approval_state`
3. `control plane`
   - 只在二者都满足条件时提交最终 acceptance

这样做的效果是：

1. agent 判断力更强
2. 真源仍然稳定

### 目标四：Session 提权

`workflow_session` 后续不再只是陪同镜像，而要真正承载：

1. supervisor agent 当前上下文
2. subagent lifecycle
3. handoff / mailbox / join
4. artifact visibility
5. round/turn receipt

也就是让“细协作状态”留在 `L4`，不要继续挤进 control plane metadata。

## 分层收口裁决

| 能力 | 推荐收口层 | 正式对象形态 |
|---|---|---|
| 宏观任务状态 | `Domain & Control Plane` | `campaign summary state` |
| 治理参数 | `Domain & Control Plane` | `governance_contract` |
| 单次 agent 执行 | `L1 Agent Execution Runtime` | `execution receipt` |
| subagent 执行 | `L1` | `task-scoped execution unit` |
| 多 agent 协作 | `L4 Multi-Agent Session Runtime` | `role binding / mailbox / handoff / join` |
| agent 角色定义 | `L3 Multi-Agent Protocol` | `role spec / capability package` |
| 语义评审 | `L1 + Control Plane` | `agent reviewer verdict + code validator` |

## 草稿实施节奏

### P0：先减厚，不先大改智能体

先做最小减负，目标是先把状态机层数降下来。

1. 停止把下列字段当作长期真源元数据：
   - `execution_state`
   - `closure_state`
   - `progress_reason`
   - `operator_next_action`
2. 这些字段改成 query/feedback/console 读时计算
3. `campaign.metadata` 只保留 atomic facts：
   - pending/resolved/waived checks
   - latest accepted deliverable refs
   - governance contract
   - latest committed verdict
4. 收缩 operator patch 写口：
   - 默认只允许 `pause/resume/governance/recovery decision`
   - 直接改 phase/status 降级为 admin-only

### P1：把 phase loop 收进 supervisor agent

1. 新增 `supervisor runtime mode = agent_supervisor`
2. 让 `discover/implement/evaluate/iterate` 逐步变成 session 内部 round
3. 控制面只接收每一轮 round receipt
4. `campaign` 不再逐相位自己驱动所有跳转

### P2：引入 Hybrid Reviewer

1. 保留当前 deterministic reviewer 作为 fallback
2. 新增 `agent reviewer` 输出结构化 verdict
3. 增加 code validator，检查：
   - 证据是否落 bundle
   - correctness checks 是否闭合
   - approval 是否满足
4. 最终由控制面 commit

### P3：正式开放 subagent

1. subagent 进入 `L1 + L4`
2. 默认继承：
   - sandbox
   - approval policy
   - risk ceiling
   - trace context
3. 不允许 subagent 直接扩权或直写 control plane 真源

## 预期收益

若按上面路径推进，预期收益主要有四类：

1. 状态机层数下降
2. 控制面 bug 面缩小
3. agent 对复杂长任务的智能推进能力增强
4. query / feedback 的状态解释口径更一致

## 明确不做

1. 不把最终真源直接交给 agent 自由文本结论
2. 不把前台 `workflow shell` judge 外环直接搬进后台主链
3. 不让 query/console 直接把 agent 文本当业务状态
4. 不再继续给控制面增加更多散装 patch/action 类型

## 建议的首批代码切入点

若后续把本草稿转成实施方案，首批优先检查和改造：

1. `butler_main/domains/campaign/service.py`
   - `_refresh_status_semantics`
   - `_sync_spec_metadata`
   - `apply_operator_patch`
2. `butler_main/domains/campaign/reviewer_runtime.py`
   - reviewer 改成 hybrid 入口
3. `butler_main/orchestrator/interfaces/query_service.py`
   - projection 改为读时计算
4. `butler_main/orchestrator/runtime_bridge/workflow_session_bridge.py`
   - session 提权，承接更多内环协作状态
5. `butler_main/domains/campaign/codex_runtime.py`
   - supervisor/executor/subagent 运行模式扩展

## 文档回写前提

如果这份草稿后续进入实施，不应只改代码，还需要同步回写：

1. 当天 `00_当日总纲.md`
2. `0330/02A`
3. `0330/02C`
4. `0330/02G`
5. `docs/project-map/03_truth_matrix.md`
6. `docs/project-map/04_change_packets.md`
7. `docs/README.md`

当前阶段，这份文档只作为 `0331` 的计划草稿入口，不替代现役真源。
