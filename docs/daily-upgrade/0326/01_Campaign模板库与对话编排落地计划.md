---
type: "note"
---
# 01 Campaign 模板库与对话编排落地计划

日期：2026-03-26  
时间标签：0326_0001  
状态：已落地 / 对话协商 + Campaign 模板库 + 自动启动已实现并验收

关联验证文档：
- [02_长任务对话验证集与prompt迭代矩阵.md](./02_长任务对话验证集与prompt迭代矩阵.md)

## 现状

1. `campaign` 已可创建与运行，但仍以“单模板 + 直接 create”形态存在，缺模板库与编排能力。
2. `chat` 前门可路由到 `mission_ingress`，但没有“任务协商态”，用户输入仍偏命令式。
3. 后台 `mission/campaign` 承接可用，但“对话协商 -> 自动启动”的产品协议未形成。

## 目标

1. 建立 `campaign` 模板库：完整模板 + 模块模板。
2. 在对话侧建立 `campaign negotiation` 草案态，形成“协商 -> 自动启动/确认”的正式链路。
3. 固定自动启动边界：完整模板可自动启动，骨架/角色改写必须确认。
4. 形成可复读验收件，确保对话驱动的后台任务启动可验证。

## 已确认设计

1. 模板库形态：完整模板 + 模块组合。
2. 对话可改骨架与角色，但一旦改骨架/角色必须用户确认。
3. 用户未明确 `mission/campaign` 时，系统允许推荐并自动启动（高置信前提）。
4. 自动启动仅适用于完整模板原样或轻改。

## 并行任务拆分

### Lane A：模板库与组合规则

目标：
- 建立 `campaign` 官方模板库（3-5 个完整模板）。
- 建立模块模板（phase/role/governance 片段）。
- 定义组合兼容规则与推荐逻辑。

落点建议：
- `butler_main/domains/campaign/templates/`
- `butler_main/domains/campaign/template_registry.py`

### Lane B：对话协商与草案态

目标：
- 新增 `CampaignNegotiationDraft` 与持久化。
- 对话侧完成模板推荐、草案生成、自动启动判定。
- 骨架改写进入确认流程。

落点建议：
- `butler_main/chat/negotiation/`
- `butler_main/chat/mainline.py` 接入 negotiation handler

### Lane C：后台创建与写回

目标：
- `OrchestratorCampaignService` 接受模板/组合 spec。
- 创建时写入 `template_origin`、`composition_mode`、`skeleton_changed`。
- 确保 `mission_id` / `supervisor_session_id` / `workflow_session` 观测成立。

落点建议：
- `butler_main/orchestrator/interfaces/campaign_service.py`
- `butler_main/domains/campaign/models.py`（metadata 扩展）

### Lane D：测试与验收件

目标：
- 回归测试覆盖模板推荐、组合编排、自动启动与确认边界。
- 产出两条正式验收件：
  - 完整模板直启
  - 模板组合 + 确认后启动

落点建议：
- `butler_main/butler_bot_code/tests/test_chat_mainline_service.py`
- `butler_main/butler_bot_code/tests/test_campaign_domain_runtime.py`
- `docs/runtime/acceptance/`

## 验收口径

1. 对话能生成 `campaign draft`，并明确展示推荐模板与差异。
2. 完整模板可高置信自动启动；骨架/角色改写必须确认。
3. 启动后 `mission_id`、`campaign_id`、`workflow_session_id` 可观测。
4. 对话补材料/补约束/补验收能写回后台对象。
5. 回归测试覆盖模板推荐/组合/确认边界。
6. 两条 run-data 证据可复读并归档。

## 已完成实现

### Lane A：模板库与组合规则

1. 已新增 `butler_main/domains/campaign/template_registry.py`，固定三类完整模板：
   - `campaign.single_repo_delivery`
   - `campaign.research_then_implement`
   - `campaign.guarded_autonomy`
2. 已补 phase / role / governance 模块模板，形成产品真源，而不是只在对话里硬编码推荐词。
3. `chat negotiation` 已改为消费该模板库。

### Lane B：对话协商与草案态

1. `CampaignNegotiationService` 已支持：
   - 模板推荐
   - 显式模板 hint
   - `composition_mode` 区分
   - 自定义骨架确认流
   - 草案持久化到 `run/orchestrator/negotiations/campaign/`
2. `ChatMainlineService` 已保持：
   - `mission_ingress` 请求优先走 mission
   - campaign negotiation 在普通 chat 路径内接管协商态
3. 已新增回归，验证确认流可跨 service 实例续接。

### Lane C：后台创建与写回

1. `CampaignSpec` 已固定显式合同字段：
   - `template_origin`
   - `composition_mode`
   - `skeleton_changed`
   - `composition_plan`
   - `created_from`
   - `negotiation_session_id`
2. `OrchestratorCampaignService` 已把 top-level 输入与 legacy metadata 统一归一到 `metadata["template_contract"]`。
3. `CampaignDomainService` 已把归一后的 `template_contract` 和完整 `spec` 持久化到 campaign metadata。

### Lane D：测试与验收件

1. 已补 `test_chat_campaign_negotiation.py`、`test_talk_mainline_service.py`、`test_orchestrator_campaign_service.py`、`test_campaign_domain_runtime.py` 的新增断言。
2. 已产出两份正式 evidence：
   - `docs/runtime/acceptance/20260326_campaign_smoke_evidence.json`
   - `docs/runtime/acceptance/20260326_campaign_negotiation_evidence.json`
3. 已发现并修复一条真实缺陷：`materials` 标签切分正则误把字母 `n` 视作换行，现已修复并回归覆盖。

## 最终验收结果

1. 主线测试共 `37` 个用例通过。
2. `template auto-start` 与 `composition + confirmation` 两条 run-data 证据均已成立。
3. 以本文定义范围计，本轮功能完成度为 `100%`。
