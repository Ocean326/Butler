---
type: "note"
---
# 04 稳定 Harness 之后的下一阶段主线：Anthropic 长运行 Harness 吸收版

日期：2026-03-26  
时间标签：0326_0004  
状态：已收口 / 作为 `0326` 后续主线唯一正式计划真源

关联文档：
- [00_当日总纲.md](./00_当日总纲.md)
- [03_Harness全系统稳定态运行梳理.md](./03_Harness全系统稳定态运行梳理.md)
- [Anthropic_长运行应用与Harness设计_主线知识体系.md](../../../BrainStorm/Insights/mainline/Anthropic_长运行应用与Harness设计_主线知识体系.md)

本文是 `0326` 当天“稳定态之后下一阶段主线”的唯一正式文档真源。  
若与 BrainStorm、临时讨论或同目录其它 `04_*.md` 存在差异，以本文为准。

## 一句话裁决

当前 Butler 已经完成“系统能稳定持续运行”的阶段目标；下一阶段不应再继续围绕“能不能跑”扩零件，而应在现有前门、campaign、query、feedback 主链上，做一轮最小但可靠的升级：

`mode frontdoor -> planning contract -> campaign execution -> evaluator verdict -> feedback/status -> handoff/resume`

这轮不是再发明一套新系统，而是把已有主线收成：

1. 显式模式更清楚
2. 合同对象更明确
3. query / feedback 更像长期任务系统，而不是运行播报

## 现状分析

### 1. 已经成立的基础设施

当前仓库里，下一阶段最关键的几个支点已经存在：

1. 前门主链
   - `butler_main/chat/mainline.py`
   - 已经把 `RequestIntakeService`、`FrontDoorTaskQueryService`、`CampaignNegotiationService` 串起来
2. 后台长任务承载
   - `butler_main/orchestrator/interfaces/campaign_service.py`
   - 已经能创建、恢复、查询 `campaign`
3. 长任务查询与观测
   - `butler_main/orchestrator/interfaces/query_service.py`
   - 已经能投影 `campaign_view / session_view / verdict_summary / user_feedback`
4. 反馈面
   - `butler_main/orchestrator/feedback_notifier.py`
   - 已经形成 `feedback_contract -> doc/push -> query doc_link` 通路
5. 模板与方法基础
   - `butler_main/domains/campaign/template_registry.py`
   - `butler_main/orchestrator/framework_profiles.py`
   - 已有 `campaign.single_repo_delivery`、`campaign.research_then_implement`、`campaign.guarded_autonomy`
   - 已有 `superpowers_like / gstack_like / openfang_guarded_autonomy`

所以 Butler 下一阶段不是“从零设计 Anthropic 式 harness”，而是“基于已经稳定的 harness 做最省改动的主线升级”。

### 2. 当前真正缺的是什么

结合现有代码，当前缺的不是 runner、campaign 或 feedback，而是下面三层口径还没收成产品真源：

1. 前门缺显式 mode
   - 当前仍是自然语言分诊优先
   - `/mission` 已存在，但不是产品主路径
2. `campaign` 缺 planning contract 口径
   - 当前更像“后台任务实体”
   - 还不是“长期合同实体”
3. query / feedback 缺更强的长期任务摘要
   - 当前能回报 phase、artifact、verdict_count
   - 但还不能稳定回报 `spec / plan / progress / next action / risk` 这类产品摘要

### 3. 当前不应做的事

从仓库现状看，下面几件事会直接把改动量和风险拉高，不适合做成本轮主线：

1. 不一次性新建完整治理平台
2. 不先新建一套 DSL 或重协议森林
3. 不把所有 `mission/template` 一次性迁进 `campaign`
4. 不在 v1 就新增研究专用 campaign 模板
5. 不把多 worker 并行当作主收口项

## V1 正式裁决

### 1. 文档真源裁决

`0326` 目录下历史上已经出现 3 份 `04_*.md`。下一阶段正式口径固定为：

1. 本文是唯一正式 `04` 真源
2. 另外两份 `04_*.md` 只保留“已合并/已重定向”说明
3. [00_当日总纲.md](./00_当日总纲.md) 只指向本文

### 2. V1 前门模式集

V1 固定 5 个显式模式：

1. `/plan`
2. `/delivery`
3. `/research`
4. `/status`
5. `/govern`

这里故意不用 `/observe` 作为 v1 产品模式名，原因是：

1. 当前代码和用户语义都已经更接近 `status/query`
2. 现有 `FrontDoorTaskQueryService` 可以直接复用
3. 这样改动最小、回归风险最低

`/mission` 继续保留，但只作为兼容和运维控制入口，不作为下一阶段产品主路径。

### 3. 模式解析与兼容优先级

mode 解析固定落在：

1. `Invocation` 建好之后
2. `RequestIntakeService.classify()` 之前
3. `FrontDoorTaskQueryService` 与 `CampaignNegotiationService` 之前

兼容优先级固定为：

1. `/mission ...`
   - 继续走现有 `mission_ingress`
2. `/status`
   - 优先进入现有 `FrontDoorTaskQueryService`
3. `/govern`
   - 进入治理模式解析
4. `/plan /delivery /research`
   - 优先于自然语言 heuristics
5. 无 slash 时
   - 继续沿用现有 `task_query + request_intake + campaign_negotiation`

### 4. 五个 mode 的 v1 行为

| mode | 复用现有链路 | 是否创建 campaign | v1 目标 |
|---|---|---|---|
| `/plan` | negotiation store | 否 | 产出 `TaskDraft / WorkingSpec / ExecutionPlan` 摘要与 refs |
| `/delivery` | `CampaignNegotiationService -> OrchestratorCampaignService` | 是 | 明确交付型长任务主线 |
| `/research` | `CampaignNegotiationService -> OrchestratorCampaignService` | 是 | 明确研究型长任务主线 |
| `/status` | `FrontDoorTaskQueryService -> OrchestratorQueryService` | 否 | 显式状态/观测入口 |
| `/govern` | governance summary + campaign metadata | 否 | 轻写入治理入口 |

### 5. `/govern` 的 v1 边界

`/govern` 进入 v1，但只做轻写入治理面，不长成独立平台。

V1 只支持：

1. `view`
2. `set_risk_level`
3. `set_autonomy_profile`
4. `request_approval`
5. `resolve_approval`

固定边界：

1. target 默认为当前线程唯一活动 campaign
2. 若 target 不明确，则只返回说明，不执行写入
3. 所有治理写入只改治理摘要，不触发主任务执行

## 合同与对象调整

### 1. v1 只提级最小合同集合

为保证最高效、最可靠，v1 只把下面这些对象提到正式主线：

1. `TaskDraft`
2. `WorkingSpec`
3. `ExecutionPlan`
4. `ProgressLog`
5. `ReviewPacket`
6. `AcceptanceVerdict`
7. `RiskRecord`

`ReferenceSet` 可以保留，但 v1 允许它先作为 `ProgressLog` 或 artifact 附带结构，不强制做独立新 store。

### 2. 存储策略按现有 `CampaignSpec.metadata` 落地

当前 `CampaignSpec` 顶层字段已经承载：

1. `template_origin`
2. `composition_mode`
3. `skeleton_changed`
4. `composition_plan`
5. `created_from`
6. `negotiation_session_id`

为避免高风险 dataclass 扩张，v1 的新增合同统一落到 `CampaignSpec.metadata` 下：

1. `planning_contract`
   - `mode_id`
   - `method_profile_id`
   - `plan_only`
   - `draft_ref`
   - `spec_ref`
   - `plan_ref`
   - `progress_ref`
2. `evaluation_contract`
   - `review_ref`
   - `latest_review_decision`
   - `latest_acceptance_decision`
3. `governance_contract`
   - `autonomy_profile`
   - `risk_level`
   - `approval_state`

这条裁决的目的很简单：

1. 先把 query/feedback 口径立起来
2. 不在本轮引入大规模兼容迁移

### 3. 方法与模板的 v1 现实口径

当前方法与模板基础已经足够支撑 v1：

1. 交付型任务
   - 默认 `campaign.single_repo_delivery`
   - 默认 `method_profile_id=superpowers_like`
2. 研究型任务
   - v1 固定复用 `campaign.research_then_implement`
   - 不新增 `campaign.research_delivery`

这样定的原因是：

1. `campaign.research_then_implement` 已存在
2. negotiation 当前已经能稳定推荐并启动它
3. 新开模板会扩大实现与回归面

### 4. `/research` 的 v1 解释

为避免当前模板名误导实现，本文明确规定：

1. `/research` v1 虽然复用 `campaign.research_then_implement`
2. 但其 `implement` 阶段允许表示“产出研究交付物”
3. 不强制等价为“必须改代码”

研究型 acceptance 的 v1 最小口径固定为：

1. 研究报告
2. 文献矩阵
3. 引用集
4. 摘要/综述
5. 结论性建议

都可以作为最终 artifact。  
evaluator 需要明确说明“为什么这些研究产物已经满足 done criteria”。

短生命周期 research、brainstorm、一次性模板任务继续保留在 `mission/template` 体系，不在本轮强迁。

## Query / Feedback 的最小升级

### 1. `OrchestratorQueryService` 的 v1 目标

当前 query 已经能回报：

1. `campaign_view`
2. `session_view`
3. `phase_runtime`
4. `verdict_summary`
5. `user_feedback`

v1 只在这个基础上增量增加：

1. `mode_id`
2. `method_profile_id`
3. `spec_ready`
4. `plan_ready`
5. `latest_review_decision`
6. `latest_acceptance_decision`
7. `latest_risk_level`
8. `latest_progress_summary`
9. `latest_handoff_summary`

### 2. `FrontDoorTaskQueryService` 的 v1 目标

`/status` 默认复用现有查询主链，但输出要逐步从：

1. `status/current_phase/next_phase`

升级成同时带上：

1. `spec_ready`
2. `plan_ready`
3. `latest_review_decision`
4. `latest_acceptance_decision`
5. `latest_progress_summary`
6. `task_doc`

### 3. feedback harness 的 v1 目标

当前 feedback harness 已成立，所以 v1 不新建第二套反馈系统，只升级展示口径：

1. 仍坚持“线程一份总览，campaign 一个子文档”
2. 仍坚持 `query/doc/push` 同源
3. 展示模型从“运行播报”升级成“合同摘要 + verdict + next action”

## 实施顺序

### Phase 1：文档真源与模式口径收口

目标：

1. 只保留本文为正式 `04`
2. `00_当日总纲.md` 只指向本文
3. 固定 `/plan /delivery /research /status /govern`

### Phase 2：前门模式最小改造

目标：

1. 在 `chat/mainline.py` 前门引入显式 mode 解析
2. `/status` 复用现有 `FrontDoorTaskQueryService`
3. `/delivery` 和 `/research` 复用现有 negotiation -> campaign create 链
4. `/plan` 先走 plan-only 草案路径

### Phase 3：planning contract 摘要化

目标：

1. 把 `TaskDraft / WorkingSpec / ExecutionPlan / ProgressLog` 摘要挂到 `CampaignSpec.metadata`
2. query/feedback 默认回报这些摘要
3. 不引入额外重 store

### Phase 4：feedback/query 升级

目标：

1. query 能默认返回 `spec/plan/progress/review/acceptance/risk` 摘要
2. feedback 文档展示 `verdict + next action`
3. `/govern` 的轻写入治理面成立

## 下一阶段不做的事

为避免再次夸夸其谈和长出平行蓝图，本轮明确不做：

1. 不把所有动作都做成 slash 命令
2. 不把 `/govern` 扩成完整治理平台
3. 不新建一套 DSL 或重协议森林
4. 不新建 `campaign.research_delivery`
5. 不把所有 mission/template 一次性迁进 campaign
6. 不把多 worker 并行当作主收口项
7. 不让 Feishu 文档变成第二套状态真源

## 验收口径

这轮文档完善完成的标志应是：

1. `0326` 目录只剩一个正式 `04` 真源
2. 本文不再同时承诺冲突的 mode、template 或治理路线
3. 本文所有 v1 改动都能明确映射到当前现有实现：
   - `ChatMainlineService`
   - `RequestIntakeService`
   - `FrontDoorTaskQueryService`
   - `CampaignNegotiationService`
   - `OrchestratorCampaignService`
   - `OrchestratorQueryService`
   - `feedback_notifier`
4. 这份文档已经能直接指导下一轮代码改动，而不是再要求实现者自己补系统定义

## 最终裁决

Anthropic 这条主线对 Butler 的真正推动，不是让我们“更像一个大 agent 框架”，而是逼我们把下一阶段收得更硬、更现实：

1. 显式模式少而清楚
2. planning contract 基于现有 campaign 真源增量生长
3. `/research` 先复用现有模板，不额外长新模板
4. query / feedback 先升级为更像长期任务系统的摘要面
5. 治理入口先做轻写入，不做大平台

所以 `0326` 之后的主线，不是“继续扩零件”，而是基于当前稳定 harness 做一轮最小、可靠、可直接实现的产品升级。
