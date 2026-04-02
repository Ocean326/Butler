# MAS Harness Engineering 四层架构 · Insight

- **来源 Raw**：`BrainStorm/Raw/daily/20260316/20260316_zhihu_web_content_capture_skills.md`
- **原始平台**：知乎专栏（作者 sunnyzhao）
- **原始日期**：2026-03-12
- **Insight 整理日期**：2026-03-18
- **区别于**：`20260318_agent_harness_全网调研汇总_insight.md`（多源横向观点汇总）；本篇是**单篇知乎长文的深度结构化提炼**，聚焦四层架构细节与经验飞轮演化路径。

---

## 核心论点（3 条）

### 1. Agent 项目的主战场在模型外侧的 Harness 层

生产级 MAS 的决定性差异不在于调用哪家 frontier 模型，而在于是否有完整的 Harness 架构与治理闭环。作者用「马具」类比：马决定往哪跑、多快跑，马具负责把力量安全传导到车上并防止脱轨。Harness 涵盖工具调度、context 压缩、安全门控、状态持久化、全链路观测——与推理逻辑严格解耦。

### 2. 知识—编排—门控—治理四层解耦是 MAS 的基础结构

- **知识供给层（Knowledge）**：参数化知识、非参数化知识（RAG）、经验知识三类资产，外加跨 agent 知识一致性治理。
- **执行编排层（Orchestration）**：Orchestrator + Stateful Workflow + Policy Runtime 三分，解决任务拆解、分配、协调。
- **风险门控层（Guardrail）**：独立于推理链的安全中间件——权限、预算、动作拦截、prompt injection 防御。
- **治理运营层（Governance）**：从运行轨迹中提炼可检索的协调模式库、任务案例库、失败模式库。

四层混在一个 orchestrator 里只会导致 "more rules, less autonomous"。

### 3. 经验资产是 MAS 的长期护城河

任务级案例库、协调模式库、失败模式库不会因模型升级而归零。这些资产只能从真实运行中积累，投入时间越长优势越大。作者给出三阶段演化路径：
1. **跑通闭环**：全量记录和可追溯，不急于自适应调度。
2. **经验反哺**：Orchestrator 与门控开始引用历史成功路径和自动归纳规则。
3. **飞轮显现**：新任务越来越能从历史经验中获益，"越跑越强"而非"越跑越乱"。

---

## 可借鉴的关键机制

| 机制 | 原文要点 | Butler 可落地方向 |
|---|---|---|
| **Ralph Loop** | 每轮全新 context + 文件持久化进度 + 自动验收；用门控和 checkpoint 替代无限累积对话历史 | Butler heartbeat 已有类似雏形（branch prompt + task_ledger），可强化 checkpoint 与自动验收 |
| **Context Rot 治理** | 上下文越长性能不稳、关键信息被埋在中段（Lost-in-the-middle）；需 context engineering + 分段重启 | Butler prompt_assembly 目前按优先级拼接，可加入"中段关键信息前置"策略 |
| **MAST 失败框架** | 系统设计问题(FC1)、协调失败(FC2)、验证缺失(FC3)；多数失败不是 prompt 问题而是拓扑缺陷 | 可用 MAST 三分类做 heartbeat 执行失败的根因标签，积累失败模式库 |
| **协调税** | 4+ agent 后收益递减甚至下降 | Butler 当前 sub-agent 数量可控，但需在扩展时设硬上限或自动合并机制 |

---

## 与 Butler 当前架构的映射

| 四层架构 | Butler 现有对应 | 差距 / 演进方向 |
|---|---|---|
| 知识供给层 | skills/ + BrainStorm/ + MEMORY.md | 缺少跨 agent 知识一致性机制；经验知识尚未结构化为可检索库 |
| 执行编排层 | heartbeat planner → executor 分层 | 已有雏形，但 Stateful Workflow 和 Policy Runtime 尚未分离 |
| 风险门控层 | 工具白名单 + heartbeat_upgrade_request | 需升级为独立中间件：预算控制、动作拦截、injection 防御 |
| 治理运营层 | task_ledger + BrainStorm Insights | 需建"执行 → 案例卡片 → 可检索经验库"的半自动流程 |

---

## 行动建议（3 条）

1. **引入 MAST 三分类做失败根因标签**：在 task_ledger 的失败回执中增加 `failure_class: FC1/FC2/FC3` 字段，逐步积累失败模式库，为经验飞轮提供原料。

2. **将门控逻辑从 executor 中抽离**：当前安全检查散落在各处，应收敛为统一的 guardrail 中间件层，与编排层解耦，降低迭代时的耦合风险。

3. **为 heartbeat 增加 Ralph Loop 式 checkpoint**：每个 branch 执行完成时自动持久化进度摘要到文件，下一轮 branch 从文件读取而非依赖对话历史累积，对抗 context rot。

---

## 主题标签

`#MAS` `#HarnessEngineering` `#四层架构` `#经验飞轮` `#RalphLoop` `#ContextRot` `#MAST失败框架` `#Butler架构演进`
