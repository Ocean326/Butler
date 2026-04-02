# 0330 DeerFlow 专题：Harness Engineering 深度学习资料（系统化重排版）

日期：2026-03-30
时间标签：0330_0003
状态：已重构整理 / 系统化学习真源（替换前一版堆砌稿）

关联文档：

- [00_当日总纲.md](./00_当日总纲.md)
- [01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md](./01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md)
- [02_AgentHarness全景研究与Butler主线开发指南.md](./02_AgentHarness全景研究与Butler主线开发指南.md)
- [当前系统基线](../../project-map/00_current_baseline.md)
- [分层地图](../../project-map/01_layer_map.md)
- [功能地图](../../project-map/02_feature_map.md)
- [系统级审计与并行升级协议](../../project-map/06_system_audit_and_upgrade_loop.md)

外部证据源（DeerFlow 开源仓库）：

- `README.md`
- `Install.md`
- `Makefile`
- `backend/docs/ARCHITECTURE.md`
- `backend/docs/GUARDRAILS.md`
- `backend/docs/CONFIGURATION.md`
- `backend/docs/HARNESS_APP_SPLIT.md`
- `backend/docs/API.md`
- `backend/docs/middleware-execution-flow.md`
- `backend/docs/task_tool_improvements.md`
- `backend/docs/MEMORY_IMPROVEMENTS.md`
- `backend/docs/MCP_SERVER.md`
- `backend/pyproject.toml`
- `frontend/package.json`

---

## 一句话裁决

这份 DeerFlow 学习资料不再采用“功能点堆砌”写法，而是按 Harness Engineering 的统一主线重排为：

`问题域 -> 分层架构 -> 运行机制 -> 状态机 -> 配置扩展 -> 质量工程 -> 治理策略 -> 迁移路线`。

每条判断都要求具备“证据路径 + 工程意义 + Butler 映射”。

---

## 本轮收口的问题

1. 上一版是资料堆砌，不是系统梳理。
2. 缺少“证据 -> 判断 -> 动作”的闭环。
3. 缺少 Butler 语境的层级映射。
4. 缺少裁决语句（吸收什么 / 不吸收什么 / 何时吸收）。

---

## 研究方法

1. 只使用 DeerFlow 官方公开仓库材料作为事实源。
2. 固定统一解剖维度：对象、控制、持久化、委派、审批、扩展、观测、产品壳。
3. 所有章节都落到 SuperButler 的短中长期动作清单。

---

## 第一章：项目定位与问题域

DeerFlow 2.0 的核心变化是：从 Deep Research 工具升级为 Super Agent Harness。

这不是“功能增加”，而是“工程目标变更”：

- 从回答问题转向持续执行。
- 从一次对话转向分钟到小时级任务闭环。
- 从 Prompt 技巧转向 Runtime 能力建设。

证据：`README.md`（rewrite + harness 定位）。

### 本章裁决

- 吸收：运行时目标与问题定义方式。
- 不吸收：把 DeerFlow 具体术语直接替换 Butler 真源术语。
- 节奏：先统一问题定义，再讨论功能映射。

---

## 第二章：系统架构分层（控制面/执行面/状态面/观测面/安全面）

### 控制面

通过 `config.yaml`、`extensions_config.json`、Gateway API 定义行为。

证据：`backend/docs/CONFIGURATION.md`、`backend/docs/MCP_SERVER.md`、`backend/docs/API.md`。

### 执行面

lead agent + subagent + tools + sandbox + filesystem 形成执行闭环。

证据：`README.md`、`backend/docs/HARNESS_APP_SPLIT.md`。

### 状态面

thread/run/uploads/artifacts/memory 构成状态体系，并提供清理入口。

证据：`backend/docs/API.md`、`backend/docs/MEMORY_IMPROVEMENTS.md`。

### 观测面

SSE + run history + tracing + middleware 流程文档构成诊断链路。

证据：`README.md`、`backend/docs/API.md`、`backend/docs/middleware-execution-flow.md`。

### 安全面

sandbox 隔离 + guardrails 前置授权 + 部署边界提醒。

证据：`backend/docs/GUARDRAILS.md`、`README.md`（security notice）。

### 本章裁决

Butler 应继续坚持“控制面定义策略、运行时执行策略、产品面仅投影状态”的依赖方向。

---

## 第三章：技术栈与框架

后端：Python 3.12、LangGraph/LangChain、FastAPI、Uvicorn、通道 SDK。
前端：Next.js + React + TypeScript + 查询与渲染能力栈。
运维：Makefile 统一入口，Docker/Local 双路径，config-upgrade 支持演进。

证据：`backend/pyproject.toml`、`frontend/package.json`、`Makefile`、`Install.md`。

### 本章裁决

技术栈价值不在“新”，在“边界清晰 + 入口统一 + 升级可控”。

---

## 第四章：Harness Engineering 七大机制

1. Sandbox：执行边界，开发便利与生产可信分离。
2. Memory：先受预算约束，再优化召回算法。
3. Tools：分组治理优先于能力堆叠。
4. Skills：从提示片段升级为可运营能力单元。
5. Subagents：并发复杂度内收至 runtime。
6. Message Gateway：产品接口与编排核心解耦。
7. Guardrails：前置授权与 fail-closed 默认策略。

证据：`backend/docs/CONFIGURATION.md`、`backend/docs/API.md`、`backend/docs/GUARDRAILS.md`、`backend/docs/task_tool_improvements.md`。

### 本章裁决

Butler 的吸收顺序应为：Guardrails -> Task Runtime -> 状态生命周期 -> Skills 运营化。

---

## 第五章：编排模式与状态机

- Thread/Run 双对象建模。
- middleware 生命周期顺序明确。
- Clarification 与 Guardrails 形成人工/自动协同治理。
- 线程本地状态可清理，避免“只增长不收敛”。

证据：`backend/docs/API.md`、`backend/docs/middleware-execution-flow.md`、`backend/docs/GUARDRAILS.md`。

### 本章裁决

Butler 必须把“推进态”和“闭环亚态”与 runtime 状态机绑定，而不是靠自由文本解释状态。

---

## 第六章：配置与扩展

- config_version + config-upgrade 形成配置演进机制。
- provider 反射加载提升模型接入弹性。
- MCP 扩展独立治理。
- Skills 支持启停与安装，具备运营属性。

证据：`backend/docs/CONFIGURATION.md`、`backend/docs/MCP_SERVER.md`、`backend/docs/API.md`。

### 本章裁决

配置系统必须作为“控制面真源”治理，而不是实现细节。

---

## 第七章：质量工程

- 契约回归：API/配置 schema。
- 行为回归：middleware 顺序、guardrails allow/deny、timeout。
- 场景回归：长任务、上传、MCP 变更、cleanup。

证据：`backend/docs/API.md`、`backend/docs/GUARDRAILS.md`、`backend/docs/MEMORY_IMPROVEMENTS.md`。

### 本章裁决

回归必须覆盖“状态机行为”，不能只覆盖“函数执行成功”。

---

## 第八章：对 SuperButler 的短中长期吸收

### 短期

- 前置授权最小闭环。
- 后台任务轮询内收。
- 线程数据生命周期接口化。
- middleware 顺序文档化与回归化。

### 中期

- Harness/App 依赖边界强化。
- Skills 版本与启停治理。
- 配置版本迁移流程化。
- trace + projection 联合观测。

### 长期

- 多策略 provider。
- 多租户策略模板。
- runtime SLO 体系。
- 操作面/控制面产品化。

### 本章裁决

吸收节奏服从 Butler `3 -> 2 -> 1` 依赖方向，不做反向耦合。

---

## 第九章：风险与反模式

1. 只堆功能，不建治理。
2. 把 local 模式当生产安全边界。
3. 状态不可清理，系统持续膨胀。
4. 让 LLM 承担后台轮询与控制逻辑。
5. 中间件顺序无契约。
6. 无证据结论反复传播。

---

## 第十章：7天学习路径

Day1 总图、Day2 配置、Day3 API状态、Day4 治理、Day5 边界、Day6 长任务、Day7 迁移评审。

每一天都要求：阅读清单 + 实验记录 + 风险 + 下一步动作。

---

## 第十一章：10个实践作业

1. 最小 config 跑通。
2. guardrail deny 演练。
3. fail-closed 演练。
4. 线程全生命周期演练。
5. middleware 顺序变更实验。
6. 轮询内收成本对比。
7. memory budget 实验。
8. skill 启停与安装实验。
9. MCP 配置变更生效实验。
10. Butler 吸收提案交付。

每个作业必须包含：证据路径、结果、风险、改造建议。

---

## 第十二章：方法论收束

DeerFlow 对 Harness Engineering 的核心启发是“先骨架后能力、先约束后扩展”：

1. 先定义边界。
2. 再定义状态生命周期。
3. 再定义执行链与治理链。
4. 再定义扩展契约与回归策略。

这套顺序决定系统是否可长期演进。

---

## 证据索引

- `README.md`
- `Install.md`
- `Makefile`
- `backend/docs/ARCHITECTURE.md`
- `backend/docs/GUARDRAILS.md`
- `backend/docs/CONFIGURATION.md`
- `backend/docs/HARNESS_APP_SPLIT.md`
- `backend/docs/API.md`
- `backend/docs/middleware-execution-flow.md`
- `backend/docs/task_tool_improvements.md`
- `backend/docs/MEMORY_IMPROVEMENTS.md`
- `backend/docs/MCP_SERVER.md`
- `backend/pyproject.toml`
- `frontend/package.json`

### 深度卡片 001
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 002
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 003
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 004
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 005
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 006
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 007
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 008
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 009
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 010
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 011
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 012
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 013
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 014
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 015
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 016
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 017
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 018
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 019
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 020
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 021
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 022
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 023
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 024
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 025
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 026
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 027
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 028
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 029
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 030
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 031
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 032
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 033
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 034
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 035
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 036
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 037
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 038
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 039
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 040
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 041
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 042
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 043
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 044
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 045
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 046
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 047
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 048
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 049
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 050
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 051
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 052
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 053
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 054
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 055
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 056
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 057
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 058
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 059
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 060
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 061
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 062
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 063
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 064
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 065
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 066
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 067
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 068
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 069
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 070
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 071
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 072
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 073
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 074
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 075
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 076
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 077
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 078
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 079
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 080
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 081
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 082
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 083
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 084
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 085
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 086
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 087
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 088
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 089
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 090
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 091
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 092
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 093
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 094
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 095
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 096
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 097
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 098
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 099
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 100
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 101
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 102
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 103
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 104
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 105
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 106
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 107
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 108
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 109
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 110
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 111
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 112
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 113
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 114
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 115
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 116
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 117
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 118
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 119
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 120
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 121
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 122
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 123
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 124
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 125
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 126
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 127
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 128
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 129
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 130
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 131
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 132
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 133
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 134
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 135
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 136
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 137
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 138
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 139
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 140
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 141
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 142
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 143
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 144
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 145
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 146
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 147
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 148
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 149
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 150
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 151
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 152
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 153
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 154
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 155
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 156
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 157
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 158
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 159
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 160
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 161
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 162
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 163
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 164
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 165
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 166
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 167
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 168
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 169
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 170
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 171
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 172
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 173
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 174
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 175
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 176
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 177
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 178
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。

### 深度卡片 179
- 问题：如何把能力引入但不破坏系统边界？
- 证据：`backend/docs/GUARDRAILS.md` + `backend/docs/middleware-execution-flow.md`。
- 判断：治理策略必须在工具调用前执行，且默认 fail-closed。
- 动作：在 Butler 控制面新增 policy 对象，并在运行时强制执行。
- 验收：拒绝路径可观察、可追踪、可恢复。