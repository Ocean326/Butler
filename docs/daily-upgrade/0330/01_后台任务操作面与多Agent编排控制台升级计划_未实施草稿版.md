# 0330 后台任务操作面与多Agent编排控制台升级计划

日期：2026-03-30（预排）  
时间标签：0330_0001  
状态：已实施并完成首轮 V2 升级回写（文件路径保留历史命名）

关联文档：

- [00_当日总纲.md](./00_当日总纲.md)
- [02_AgentHarness全景研究与Butler主线开发指南.md](./02_AgentHarness全景研究与Butler主线开发指南.md)
- [当前系统基线](../../project-map/00_current_baseline.md)
- [分层地图](../../project-map/01_layer_map.md)
- [功能地图](../../project-map/02_feature_map.md)
- [0329 后台任务双状态与前门弱化重构](../0329/03_后台任务双状态与前门弱化重构.md)
- [0327 Skill Exposure Plane 与 Codex 消费边界](../0327/02_SkillExposurePlane与Codex消费边界.md)
- [Visual Console API Contract v1](../../runtime/Visual_Console_API_Contract_v1.md)
- [系统级审计与并行升级协议](../../project-map/06_system_audit_and_upgrade_loop.md)

## 一句话裁决

`0330` 预排升级的目标，不是继续给当前 `console` 零散加按钮，而是把它从“观测面”升级成面向 operator 的 `Operator Harness`：

1. 对外形成稳定的人工介入、恢复、审计与有限编排操作面
2. 对内继续坚持 `campaign truth / workflow truth / session truth` 分别留在 control plane 与 runtime
3. 只吸收外部 Agent Harness 的稳定原语，不照抄外部框架术语、DSL 或 UI 命名
4. `V1` 保留“有限热修正”能力，但必须受统一 contract、策略约束和审计对象治理
5. `Audit Plane` 从附属日志提升为正式对象层
6. `Workflow Authoring` 方向明确改成更产品化的 operator shell，而不是只留一组底层 patch API

## 本轮实施回写（2026-03-30）

本轮已按本文方案完成第一波代码落地，当前现役状态如下：

1. `Product Surface`
   - `ContextPanel` 新增 `operator` 选项卡，落地 control plane、recovery、prompt/skill、workflow patch、audit list 五块区域
   - `DraftBoard` 升级为 `Draft Studio`，支持 draft workflow authoring、compile preview、launch 前预编译检查
   - URL state、query hook、API client、样式层已同步升级，前端已通过 `typecheck + build`
2. `Domain & Control Plane`
   - `campaign` 正式引入 `OperatorActionRecord`、`OperatorPatchReceipt`、`RecoveryDecisionReceipt`
   - `ConsoleControlService` 已支持 `recover / retry_step / skip_to_step / force_transition / prompt_patch / workflow_patch`
   - `ConsoleQueryService` 已支持 `control-plane / transition-options / recovery-candidates / audit-actions / prompt-surface / workflow-authoring / compile-preview`
3. `Audit Plane`
   - operator 动作现在会记录 `trace_id / receipt_id / recovery_decision_id`
   - prompt/workflow patch 会生成 before/after summary 与 policy source
4. `Acceptance`
   - 前端：`npm run typecheck`、`npm run build`
   - 后端：`test_console_services.py`、`test_console_server.py`、`test_orchestrator_campaign_service.py`
   - 服务：`tools/butler restart console`、`tools/butler restart orchestrator`、`tools/butler status`

## Review Follow-Up（2026-03-30）

在完成首轮落地后，又补了一轮 review 修复，当前额外收口如下：

1. 修正 `campaign workflow patch` 的保留语义
   - 仅改 `phase_plan / role_plan` 时，不再误清空现有 `transition_rules / recovery_entries`
2. 修正 operator UI 的恢复列表稳定性
   - recovery / transition 卡片改用稳定唯一 key
   - 应用候选时补传 `target_node_id / target_scope`，避免审计目标漂移
3. 恢复 `append_feedback` 在 operator surface 的正式入口
   - 不再只剩后端 action 能力、前端无入口
4. 补 prompt overlay 的输入校验
   - 非法 JSON 不再被静默转成空对象并提交
5. draft studio 增加失败反馈
   - 保存、编译、启动失败时会明确回显，而不是静默吞掉异常

## 0331 Agent-Turn 对齐回写

`0331` 在 campaign 主线切到 `campaign ledger -> workflow_session -> agent turn receipt -> harness` 之后，console 再补一轮复核，当前现役口径以本节覆盖上文里仍带旧相位语义的表述：

1. `console` 主视图不再以 `discover / implement / evaluate / iterate` 作为 operator 一线心智模型
2. campaign graph / board 当前固定展示：
   - `ledger`
   - `turn`
   - `delivery`
   - `harness`
3. `control-plane` 当前主展示固定优先读取：
   - `canonical_session_id`
   - `macro_state`
   - `task_summary`
   - `latest_turn_receipt`
   - `latest_delivery_refs`
   - `harness_summary`
4. operator 主动作已收口为：
   - `pause`
   - `resume`
   - `abort`
   - `annotate_governance`
   - `force_recover_from_snapshot`
   - `append_feedback`
5. 旧 `force_transition / retry_step / skip_to_step` 当前只保留为 legacy/best-effort 兼容写口，不再作为主 UX 承诺
6. `append_feedback` 现在支持 campaign-alone 新主线，会直接写入 canonical session shared state / blackboard，不再要求先有 `mission_id`
7. 前端 `Operator Harness` 壳已收口为自然语言摘要优先：
   - `task_summary`
   - latest turn receipt
   - delivery refs
   - harness health
   - audit feed
   - prompt/workflow patch 面降到次要信息，不再占主视图中心
8. 前端展示层补一轮产品化修复：
   - inspector sheet、preview modal、agent detail dialog 改为互斥打开，不再允许多层窗口叠在同一屏上
   - day/night theme 改为真正可切换并持久化：
     - 首屏在 React hydrate 前就按本地偏好或系统偏好写入 `data-theme`
     - overlay / sheet / command rail / code preview 等深色覆盖补齐，不再只切一部分 token
9. 前端主题层再补一轮系统性修复：
   - `workspace-stage / graph-stage / flow node / timeline card / activity dock` 不再保留“固定深底浅字”硬编码，统一切到 theme token
   - light theme 改为暖灰工作面 + 深色文字，dark theme 保持深场景，但 flow node 也同步切 dark token，避免浅字压浅底
   - 左侧 rail 修正为：
     - 展开态可滚动
     - 折叠态增宽并允许滚动
     - 折叠按钮文案缩短，避免挤字和溢出
   - 对应实现位于 `butler_main/console/webapp/spa/src/App.tsx`、`styles.css`、`index.html`
   - 本轮额外影响 `butler_main/console/webapp/spa/src/components/command-rail.tsx`
   - 验证：
     - `cd butler_main/console/webapp && npm test`
     - `cd butler_main/console/webapp && npm run typecheck`
     - `cd butler_main/console/webapp && npm run build`
     - `./tools/butler restart console`
     - `./tools/butler status`

## 当前已落地范围

本专题在当前代码中的落地点固定为：

1. `butler_main/console/service.py`
2. `butler_main/console/server.py`
3. `butler_main/console/types.py`
4. `butler_main/domains/campaign/models.py`
5. `butler_main/domains/campaign/service.py`
6. `butler_main/orchestrator/interfaces/campaign_service.py`
7. `butler_main/console/webapp/spa/src/`

对应现役 API / UI 面包括：

1. `GET /console/api/campaigns/{campaign_id}/control-plane`
2. `GET /console/api/campaigns/{campaign_id}/transition-options`
3. `GET /console/api/campaigns/{campaign_id}/recovery-candidates`
4. `GET /console/api/campaigns/{campaign_id}/audit-actions`
5. `GET|PATCH /console/api/campaigns/{campaign_id}/prompt-surface`
6. `GET|PATCH /console/api/campaigns/{campaign_id}/agents/{node_id}/prompt-surface`
7. `GET|PATCH /console/api/campaigns/{campaign_id}/workflow-authoring`
8. `GET|PATCH /console/api/drafts/{draft_id}/workflow-authoring`
9. `GET|POST /console/api/drafts/{draft_id}/compile-preview`
10. `POST /console/api/campaigns/{campaign_id}/actions` 扩展字段：`target_scope / target_node_id / transition_to / resume_from / check_ids / feedback / prompt_patch / workflow_patch / operator_reason / policy_source`

## 本轮追加裁决（2026-03-30 第二轮）

基于本轮讨论，`01` 在 `02` 的研究裁决基础上继续追加三条明确结论：

1. `V1 Operator Harness` 继续保留 `live campaign patch`
   - 但只允许有限热修正，不开放任意 runtime 改写
2. `Audit Plane` 升格为正式对象
   - 不再只是“动作后顺便打一条日志”
3. `Workflow Authoring` 明确走更产品化的壳
   - operator 需要一套稳定的编排、检查、发布、对比和回滚体验
   - 不再只理解成“暴露几个 PATCH 接口，再让人自己拼”

## 本文与 `02` 的分工

`02_AgentHarness全景研究与Butler主线开发指南.md` 负责回答：

1. 外部 Agent Harness 能力应按 Butler 哪一层吸收
2. 哪些原语该优先吸收，哪些只能做参考
3. 为什么 Butler 不应让外部框架反向成为内部真源

本文负责回答：

1. 这些上位裁决如何落实到 `console + control plane + runtime bridge`
2. `V1 Operator Harness` 与 `V2 Workflow Authoring` 的产品面、接口面、实现面边界
3. 升级节奏、验收口径和文档回写要求

## 当前定位

本专题对应的主层级固定为：

1. `Product Surface（产品表面层）`
2. `Domain & Control Plane（领域与控制平面）`

次层级会触达：

1. `L4 Multi-Agent Session Runtime`
2. `L2 Durability Substrate`
3. `L1 Agent Execution Runtime`

当前固定边界：

1. `console` 只消费投影与受控动作，不直接写 runtime 真源文件
2. `campaign` 仍是控制面真源
3. `WorkflowSession` 与事件历史仍在 `L4`
4. prompt 的长期真源是结构化合同，而不是最终拼出来的 prompt 文本

## 对照 `02` 后的升级目标

### 1. Butler 应优先吸收的 Harness 原语

本专题与 `02` 对齐后，优先吸收下面几类能力，而不是继续按“页面缺什么就补什么”理解：

1. 中断 / 恢复 / checkpoint / replay 的统一动作合同
2. handoff / approval / guardrail / tracing / session 的对象化表达
3. subagent 继承式治理与自治等级约束
4. `flow` 与 `autonomy` 的分离
5. operator 可见的 run history / node history / audit receipt
6. `skill exposure / prompt surface / governance package` 的结构化治理面

### 2. 当前明确不吸收

1. 不把外部 graph DSL 直接变成 Butler 协议层真源
2. 不把外部产品术语直接写进 Butler 现役命名
3. 不让 UI 节点图反向改写 runtime store
4. 不把 vendor-specific API surface 写死为 Butler 主合同

## 实施前缺口基线（本轮已基本关闭）

### 1. Product Surface 缺口

下列内容保留为实施前基线；对应缺口已在本轮首轮实施中基本关闭：

当前 `butler_main/console/webapp/spa/` 已经具备：

- campaign list / board / graph / timeline
- draft board
- artifact preview
- agent detail dialog
- 少量 campaign action

但现状仍主要停留在观察面，缺口包括：

1. `campaign` 页面当前只暴露少量动作：
   - `pause`
   - `resume`
   - `request_approval`
2. `recovery` 没有独立 operator 面：
   - 看不到 `recovery candidates`
   - 不能选择 `resume_from`
   - 不能做受控 `retry_step / skip_to_step / force_transition`
3. Draft Board 虽然底层已支持 `skill_selection` patch，但没有正式的前端治理面
4. Agent Detail 当前只展示：
   - `overview`
   - `planned_input`
   - `artifacts`
   - `raw_records`
   还不能查看结构化 prompt 注入、策略来源与最终 prompt 物化结果
5. 多 agent 图面当前是只读投影，尚未形成“只读观测 + 受控 patch + 审计回放”的正式 operator 语义

### 2. Domain & Control Plane 缺口

当前后端已经存在的基础能力包括：

1. `POST /console/api/campaigns/{campaign_id}/actions`
2. `PATCH /console/api/drafts/{draft_id}`
3. `GET /console/api/skills/*`
4. `skill_exposure_observation`
5. `campaign / workflow_session / phase_runtime / governance_summary` 投影

但仍缺下面几类正式能力：

1. 面向 `recovery` 的统一 action contract 与 option 计算
2. 面向 prompt / skill / governance 的结构化读写接口
3. 面向 workflow skeleton / transition rules 的 authoring 合同
4. 面向 operator 的 action ledger、before/after patch receipt、policy source 与 trace id

### 3. Runtime / Durability Bridge 缺口

当前 `runtime_bridge` 与 workflow session bridge 已进入主链，但仍缺：

1. session 级人工中断 / 恢复的统一外显口径
2. operator 介入后的 durable receipt 与 replay 证据
3. node-level patch 对“仅影响未来执行”与“显式 recover/replay 后生效”的清晰边界
4. prompt 结构化合同与最终 prompt 物化预览之间的稳定桥接

## 分层目标

### 1. Operator Surface

负责给人稳定地看、点、改、审计，包括：

1. Campaign Control
2. Recovery Inspector
3. Prompt & Skill Inspector
4. Workflow Inspection / 有限热修正面
5. Run History / Action Audit Timeline

### 2. Policy Plane

负责承载可治理的结构化对象，而不是散落 prompt 文案，包括：

1. `skill_exposure`
2. `prompt profile`
3. `phase overlays`
4. `governance blocks`
5. `risk_level`
6. `autonomy_profile`
7. `transition policy`

### 3. Execution Plane

继续承载真实运行，包括：

1. `campaign / mission`
2. `workflow session`
3. `recovery / replay / writeback`
4. `provider execution runtime`

### 4. Audit Plane

负责沉淀每次人工介入和系统恢复的正式事实，包括：

1. action ledger
2. durable receipt
3. before / after patch summary
4. operator reason
5. policy source
6. trace id / audit event id

### 5. 正式对象化裁决

本专题当前不再把 operator 介入视为“若干散落 API + timeline 字段”，而是升格为一组正式对象：

1. `OperatorActionRecord`
   - 表示一次正式人工动作
   - 最小字段应包含：
     - `action_id`
     - `campaign_id`
     - `target_scope`
     - `target_node_id`
     - `action_type`
     - `operator_id`
     - `operator_reason`
     - `policy_source`
     - `trace_id`
     - `created_at`
2. `OperatorPatchReceipt`
   - 表示一次 patch 的前后差异与生效范围
   - 最小字段应包含：
     - `receipt_id`
     - `action_id`
     - `patch_kind`
     - `before_summary`
     - `after_summary`
     - `effective_scope`
     - `effective_timing`
3. `RecoveryDecisionReceipt`
   - 表示一次恢复判定、恢复入口与结果
   - 最小字段应包含：
     - `action_id`
     - `resume_from`
     - `recovery_candidate_id`
     - `decision_summary`
     - `result_state`
4. `AuditTimelineProjection`
   - 表示给产品面消费的只读投影
   - 由上述正式对象组装而成，不反向成为真源

## 分期策略

### V1 Operator Harness

先落三件事：

1. 人工介入状态机
2. prompt / skill / governance 注入治理
3. 运行中 campaign 的有限热修正与可审计回放

`V1` 的目标不是“完整图上编排编辑器”，而是先把 operator 可以安全介入、恢复、审计这条链立住。

`V1` 当前明确允许的有限热修正包括：

1. `resume_from`
2. `retry_step`
3. `skip_to_step`
4. `force_transition`
5. `node-level prompt overlay update`
6. `campaign-level skill / governance patch`

`V1` 当前明确不允许：

1. 改写已发生历史
2. 绕开控制面直接写 runtime store
3. 不经审计地做批量 silent patch
4. 把图编辑结果直接当 session 真源

### V2 Workflow Authoring

再补三件事：

1. Draft / Template 的正式编排编辑器
2. 图上编辑 phase / role / edge / condition
3. launch 前预编译 / 校验 / diff 预览

`V2` 仍然坚持：

1. template / IR / VM / session 才是编排主链
2. authoring UI 只是协议与控制面的消费壳
3. 不让图编辑器反向成为 runtime 真源

但产品目标不再只是“图面可编辑”，而是形成完整的 authoring shell：

1. `Draft Workspace`
   - 负责目标、约束、skill 选择、governance defaults
2. `Workflow Canvas`
   - 负责 phase / role / edge / condition 的可视化编辑
3. `Inspector Panel`
   - 负责节点级 prompt overlays、transition rule、recovery entry、policy 来源
4. `Compile & Diff Review`
   - 负责 launch 前 compile 结果、风险提示、diff 预览、发布确认

## 前端功能面

## 产品壳形态

本专题现在明确以更产品化的 operator shell 为目标，而不是“多个孤立页面”：

1. `Campaign Cockpit`
   - 面向运行中任务
   - 把 graph、timeline、action composer、recovery、prompt/skill、audit 串成同一操作台
2. `Draft Studio`
   - 面向 launch 前编排
   - 把草案、模板、编排、skill、policy、compile review 串成同一编辑台
3. `Audit Console`
   - 面向复盘与审计
   - 把 operator action、patch receipt、recovery decision、execution trace 串成同一查看面

当前推荐的 `Campaign Cockpit` 信息结构：

1. 左侧：campaign graph / active path / node status
2. 中央：selected node inspector / prompt & skill / records / artifacts
3. 右侧：action composer / recovery candidates / operator checklist / audit summary

当前推荐的 `Draft Studio` 信息结构：

1. 左侧：draft outline / phase list / template skeleton
2. 中央：workflow canvas / edge editor / node editor
3. 右侧：skill selection / governance defaults / compile result / launch review

### 1. Campaign Control

在当前 campaign 页面新增正式控制区，支持：

- `pause`
- `resume`
- `recover`
- `retry_step`
- `skip_to_step`
- `force_transition`
- `append_feedback`
- `request_approval`
- `resolve_approval`
- `resolve_checks`
- `waive_checks`

每次动作都必须要求：

- `operator_reason`
- `target_scope`
- 可选 `target_node_id`
- 成功后返回 `updated state + audit event id + trace id`

### 2. Recovery Inspector

新增专门的 `Recovery Inspector`，至少展示：

- `execution_state`
- `closure_state`
- `progress_reason`
- `closure_reason`
- `operator_next_action`
- `recovery candidates`
- `resume_from`
- `pending / resolved / waived checks`
- `latest acceptance decision`

在这个面上允许做受控恢复，不再要求 operator 只能去代码或 run-data 里猜。

### 3. Prompt & Skill Inspector

新增 `Prompt & Skill` 面板，支持双视角：

1. 结构化合同视角
   - `skill_exposure`
   - `prompt profile`
   - `phase overlays`
   - `governance blocks`
   - `provider overrides`
   - `risk_level / autonomy_profile`
2. 最终 prompt 预览视角
   - 本轮物化后的 prompt
   - patch 前后 diff
   - 生效范围说明

当前裁决固定为：

1. 默认改未来执行
2. 当前运行节点只有显式 `replay / recover` 后才吃到新设置
3. prompt 文本只用于预览、diff 与排障，不升格为长期真源

### 4. Workflow Inspection & Patch

`V1` 与 `V2` 分开处理：

1. `V1 Live Campaign Patch`
   - 只支持运行中有限热修正
2. `V2 Draft / Template Editor`
   - 才承接正式编排编辑

允许编辑的对象包括：

- phase path
- role plan
- node transition
- condition label
- recovery entry
- node-level prompt overlays

当前不允许：

- 直接篡改已发生的 session event 历史
- 让前端直接写 runtime store 真源文件
- 绕开 `template -> ir -> vm -> session` 主链路

### 5. Workflow Authoring 产品化要求

`V2` 的 authoring 不再只看“能不能编辑”，而要满足下面几类产品体验：

1. 可理解
   - operator 能看见 phase path、role plan、transition rule、recovery entry 之间的关系
2. 可检查
   - operator 能在 launch 前看到 compile 结果、缺失字段、风险提示、diff
3. 可发布
   - operator 能明确知道“这次发布会生成什么 campaign 合同”
4. 可回溯
   - operator 能回看草案版本、patch 记录、发布说明
5. 可比较
   - operator 能看 draft 与 live campaign、patch 前后、模板与实例之间的差异

### 6. Run History / Audit Timeline

在现有 graph / timeline 基础上补正式 operator 审计面，至少展示：

1. 谁在什么时候触发了什么动作
2. 该动作命中了哪个 `campaign / node / scope`
3. 触发前后的状态摘要
4. 关联的 `audit_event_id / trace_id / durable receipt`
5. 该动作对应的策略来源与恢复结果

## 后端接口面

### 1. 扩展统一 action contract

扩展现有：

- `POST /console/api/campaigns/{campaign_id}/actions`

统一承载更多 action，并标准化 payload：

- `action`
- `target_scope`
- `target_node_id`
- `transition_to`
- `resume_from`
- `check_ids`
- `feedback`
- `prompt_patch`
- `workflow_patch`
- `operator_reason`
- `policy_source`

当前裁决固定为：

1. `resume / retry / skip / force_transition` 必须走同一 action contract
2. 所有受控动作都必须产生正式 receipt
3. query 面只读组装，不在 query 路径里偷偷改状态
4. `OperatorActionRecord` 与 `OperatorPatchReceipt` 必须能被 API 正式读取，而不是只存在内部日志

### 2. 新增查询接口

新增：

- `GET /console/api/campaigns/{campaign_id}/control-plane`
- `GET /console/api/campaigns/{campaign_id}/transition-options`
- `GET /console/api/campaigns/{campaign_id}/recovery-candidates`
- `GET /console/api/campaigns/{campaign_id}/audit-actions`
- `GET /console/api/campaigns/{campaign_id}/audit-actions/{action_id}`
- `GET /console/api/campaigns/{campaign_id}/prompt-surface`
- `GET /console/api/campaigns/{campaign_id}/agents/{node_id}/prompt-surface`
- `GET /console/api/drafts/{draft_id}/workflow-authoring`
- `GET /console/api/campaigns/{campaign_id}/workflow-authoring`
- `GET /console/api/drafts/{draft_id}/compile-preview`

### 3. 新增写接口

新增：

- `PATCH /console/api/campaigns/{campaign_id}/prompt-surface`
- `PATCH /console/api/campaigns/{campaign_id}/agents/{node_id}/prompt-surface`
- `PATCH /console/api/drafts/{draft_id}/workflow-authoring`
- `PATCH /console/api/campaigns/{campaign_id}/workflow-authoring`
- `POST /console/api/drafts/{draft_id}/compile-preview`

`V1` 与 `V2` 的默认边界：

1. `V1` 先做 `prompt-surface` 与 `live campaign patch`
2. `V2` 再做 `draft workflow authoring` 与预编译校验

## 后端实现面

### 1. Console Service

`butler_main/console/service.py` 需要从当前“薄 query + 少量 control”提升为：

1. control constraints assembler
2. recovery action resolver
3. prompt surface reader / patch writer
4. workflow authoring reader / patch writer
5. audit receipt projector
6. compile preview orchestrator

### 2. Orchestrator / Campaign Control Plane

`butler_main/orchestrator/interfaces/` 与 `butler_main/domains/campaign/` 需要补：

1. recovery option 计算
2. transition option 计算
3. operator patch apply
4. prompt / skill / governance contract patch apply
5. workflow patch contract apply
6. action ledger / receipt 标准事件模型
7. draft compile preview / publish review 组装

当前裁决固定为：

1. `campaign truth` 仍在控制面
2. `WorkflowSession` 仍在 `L4`
3. `prompt` 的长期真源是结构化合同，不是最终拼出来的 prompt 文本

### 3. Runtime / Recovery Bridge

`runtime_bridge` 与 workflow session bridge 需要补有限热修正规则：

允许：

- `resume_from`
- `retry_step`
- `skip_to_step`
- `node-level overlay update`

不允许：

- 伪造历史事件
- 改写已完成步骤的事实
- 把 projection 倒写成真源

并要求每个可恢复动作至少沉淀：

1. 触发原因
2. 前后状态
3. operator 身份
4. policy source
5. durable receipt

### 4. Skill / Prompt Plane

当前已经存在的 `skill_exposure_observation` 需要继续推进成：

1. 可查询
2. 可修改
3. 可审计
4. 可按 campaign / node 双层生效

最终 prompt 只保留为：

1. 物化预览
2. diff 预览
3. 问题排查依据

不把最终 prompt 文本本身升格为长期真源。

## 实施节奏

## 实施拆解（可实施版）

为了避免继续停留在“大方案可读、但没法下手”，本专题补一版按实现切片拆开的 `V1` 落地顺序。

### Phase 1：Action Contract + Audit Object

目标：

1. 统一动作合同
2. 让 `Audit Plane` 形成正式对象
3. 给 `Campaign Cockpit` 提供最小 operator 动作闭环

代码落点：

1. `butler_main/orchestrator/interfaces/`
2. `butler_main/domains/campaign/`
3. `butler_main/console/service.py`

最小交付：

1. `resume / retry / skip / force_transition` 统一 contract
2. `OperatorActionRecord / OperatorPatchReceipt` 最小模型
3. `GET /audit-actions` 与 action detail 查询

### Phase 2：Recovery + Prompt/Skill Operator Surface

目标：

1. recovery inspector 可用
2. prompt / skill 结构化读写可用
3. agent detail 能展示策略来源与 patch diff

代码落点：

1. `butler_main/console/`
2. `butler_main/orchestrator/interfaces/`
3. `butler_main/domains/campaign/`

最小交付：

1. `recovery-candidates`
2. `prompt-surface`
3. `campaign-level / node-level patch`
4. audit timeline 联动

### Phase 3：Draft Studio Preview

目标：

1. 在不直接实现完整图编排器的前提下，先让 `Draft Studio` 具备可检查、可发布的雏形
2. 把 “更产品化” 先落到编排检查与发布体验，而不是一上来堆复杂图编辑器

代码落点：

1. `butler_main/console/`
2. `butler_main/orchestrator/interfaces/`
3. `butler_main/orchestrator/workflow_ir.py`

最小交付：

1. `workflow-authoring`
2. `compile-preview`
3. launch 前 diff / risk / validation summary

### 第一波并行

第一波先对齐 `02` 的 Harness 吸收顺序，固定拆成 4 条 lane：

1. `lane-a/runtime-action-contract`
   - 统一 `resume / retry / skip / force_transition / replay` 的动作合同、receipt 与 durable boundary
2. `lane-b/control-plane-policy`
   - 做 `recovery options / transition options / prompt surface / governance patch` 的控制面闭环
3. `lane-c/operator-surface`
   - 做 recovery / prompt / workflow 三面只读 + 受控写入口
4. `lane-d/docs`
   - 同步维护 `0330` 当日真源、接口边界与验收口径

第一波目标：先把合同、策略与审计立住，避免“先做 UI，再补真源”。

### 中途 replan

第一波后强制重新拆分为：

1. 真 bug
2. 设计缺口
3. 产品语义错位
4. 文档过宣称
5. 观测性缺失

只保留真正阻塞主线的 `P0 / P1`。

### 第二波并行

1. `draft-authoring-lane`
2. `live-patch-lane`
3. `frontend-integration-lane`
4. `acceptance-lane`

第二波目标：把 `V1 Operator Harness` 收口，再决定 `V2 Workflow Authoring` 是否继续展开。

## 验收口径

至少覆盖五类场景：

1. `campaign` 进入 `recovery` 后，operator 可从 console 选恢复动作并继续推进
2. operator 可以查看某个 agent 的：
   - 结构化注入合同
   - 最终 prompt 预览
   - patch diff
   - policy source
3. Draft Board 可以编辑：
   - `skill_selection`
   - phase / role / transition skeleton
   并成功 launch 成 campaign
4. 对运行中 campaign 的有限热修正会：
   - 正确进入审计
   - 不篡改既有历史
   - 只影响未来执行或显式 replay / recover 后的节点
5. query / feedback / console 对同一 `campaign` 的状态解释保持一致：
   - `execution_state`
   - `closure_state`
   - `operator_next_action`
   - `acceptance_requirements_remaining`

并至少补下面这组回归方向：

1. `test_console_server.py`
2. `test_console_services.py`
3. `test_orchestrator_campaign_service.py`
4. `test_orchestrator_campaign_observe.py`
5. `test_orchestrator_runner.py`

系统级收口还必须补：

1. 相关回归测试
2. `./tools/butler restart butler_bot`
3. `./tools/butler restart orchestrator`
4. `./tools/butler restart console`
5. `./tools/butler status`
6. 文档回写：
   - 当天 `00_当日总纲.md`
   - 本专题正文
   - `docs/project-map/03_truth_matrix.md`
   - `docs/project-map/04_change_packets.md`
   - `docs/README.md`

## 当前说明

1. 本文是 `0330` 预排专题草稿。
2. 截至 `2026-03-30` 当前时点，相关内容尚未实施。
3. 后续若进入真实实现，应继续在本文件中追加：
   - 已落代码
   - 测试结果
   - 服务重启与 smoke
   - 文档回写清单
