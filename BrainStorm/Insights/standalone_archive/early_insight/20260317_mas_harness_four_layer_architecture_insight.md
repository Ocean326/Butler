# Insight: MAS Harness 四层架构——从模型能力到运行环境的主战场迁移

> 提炼自（合并 3 篇 Raw）：
> - `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_multi_agent_harness_engineering.md`（#05）
> - `BrainStorm/Raw/daily/20260316/20260316_zhihu_web_content_capture_skills.md`（#06，知乎长文骨架）
> - `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_agent_harness_quanshiwang_diaoyan.md`（#07）
>
> 早期 Insight 参考：`BrainStorm/Raw/Simon_agent_xhs_series/20260317_xiaohongshu_multi_agent_harness_engineering_insights.md`
>
> 原文作者：Simon / sunnyzhao（小红书 + 知乎）| 原文发布：2026-03-12 ~ 03-17  
> 提炼时间：2026-03-18 · heartbeat-executor-agent

---

## 核心观点

### 1. Agent 的主战场在模型外，不在模型里

生产级 MAS 的决定性差异不在于调用了哪家 frontier 模型，而在于是否有一套完整的 Harness 架构与治理闭环。几乎所有高分 agentic benchmark 成绩都伴随明确的 harness 条件说明；OpenClaw、Anthropic 16-agent 编译器实验等案例都表明，绝大部分工程精力花在测试体系、任务锁、反馈循环等 harness 侧。

**核心定义**：Harness Engineering = 把 Agent 外围的「运行环境」当成核心工程对象来设计——工具调度、上下文压缩、状态持久化、安全门控、观测与评测。区别于 scaffolding（首轮组装），harness 强调的是**长期运行环境**。

> 马具类比：马决定往哪跑、多快跑；马具负责把力量安全地传导到车上并防止脱轨。能力越强，马具越重要。

### 2. 四层解耦架构

| 层 | 职责 | 关键组件 | 失败时的后果 |
|----|------|---------|------------|
| **知识供给层** Knowledge | 让 Agent 看懂业务约束与领域语言 | 参数化知识（模型权重）、非参数化知识（RAG/知识库）、经验知识（Playbook/案例库） | 各 Agent 用不一致的业务语义做决策，输出互相矛盾 |
| **执行编排层** Orchestration | 任务怎么拆、谁来做、怎么协调 | Orchestrator、Stateful Workflow、Router/Handoffs/SubAgents | 任务分工混乱、子任务漏接、状态丢失 |
| **风险门控层** Guard/Policy | 安全与合规做成中间件 | 权限与预算控制、工具调用白/黑名单、Prompt Injection 防御、Safety/Compliance Checks | 安全逻辑散落在各 Agent，出一个漏洞全线失守 |
| **治理运营层** Governance | 从日志到知识，经验飞轮 | 任务级案例库、协调模式库、失败模式库、运行观测 Dashboard | 系统"越跑越乱"而非"越跑越强" |

**核心论点**：把这四层混在一个 orchestrator 或 workflow 里，只会在迭代中不断堆规则，最后滑向 "more rules, less autonomous"。

### 3. 经验资产是长期护城河

任务级案例库、协调模式库、失败模式库——这些资产只能从真实运行中积累，无法直接购买或从公开 benchmark 学到。投入时间越长、运行次数越多，优势越大。三个演化阶段：

| 阶段 | 特征 | 重点 |
|------|------|------|
| **阶段一：跑通闭环** | 全量记录和可追溯 | 不急于引入复杂自适应调度，先确保日志完整、轨迹可回放 |
| **阶段二：经验反哺** | Orchestrator 与门控开始引用历史成功路径和自动归纳规则 | 运营成本与成功率共振改善 |
| **阶段三：飞轮显现** | 新任务越来越能从历史经验中获益 | "越跑越强"而非"越跑越乱" |

### 4. MAS 失败模式的系统性归因

来自 MAST 框架（"Why Do Multi-Agent LLM Systems Fail?"）：

| 失败类别 | 含义 | 典型表现 |
|---------|------|---------|
| **FC1 系统设计** | 角色分工、拓扑结构不合理 | Agent 职责重叠，输出互相覆盖 |
| **FC2 协调失败** | 多 Agent 之间通信/同步机制有缺陷 | 子任务"传了但没人接"、状态在 handoff 中丢失 |
| **FC3 验证缺失** | 没有跨 Agent 的输出验证 | 某个 Agent 输出了错误结果但下游直接使用 |

关键结论：多数 MAS 失败不是 prompt 写得不够好，而是协调拓扑、角色设计、验证路径在**系统层面**有缺陷。4+ Agent 后收益递减甚至下降的实证结果说明，盲目堆 Agent 只会制造"协调税"。

### 5. Harness 是 2026 年的核心趋势

多方信号汇聚：
- Philipp Schmid：If 2025 was the beginning of agents, **2026 will be around Agent Harnesses**.
- Anthropic：构建 agent harness 最难的部分之一是 **constructing its action space**。
- Martin Fowler：Harness Engineering 专注于**控制与引导 AI 系统**，强调安全性与可预测性。
- 共识：不要用 SDK/framework 自己组装 agent，而是 **prompt the harness** 拿最佳结果。

---

## 对 Butler 的映射

### 映射 1：四层架构在 Butler 中的落点

| Harness 层 | Butler 当前对应 | 成熟度 | 关键缺口 |
|-----------|---------------|-------|---------|
| **知识供给** | `docs/` + `BrainStorm/` + `local_memory` + SOUL prompt | ★★☆ | 跨场景知识一致性尚未显式管理；经验知识（Playbook/案例库）还在 task_ledger 中以状态形式存在，未提炼为可检索资产 |
| **执行编排** | heartbeat_orchestration + skills pipeline + 对话模式切换 | ★★☆ | planner/executor 分层已有，但"谁来做哪种任务"的路由策略还比较粗放 |
| **风险门控** | 自我升级审批（heartbeat_upgrade_request.json）、工具调用白名单（隐式） | ★☆☆ | 未作为独立中间件存在；权限/预算/安全检查散落在各处 |
| **治理运营** | task_ledger + self_mind + heartbeat 汇总 | ★☆☆ | 日志到知识的转化链路不通；缺少协调模式库和失败模式库 |

### 映射 2：Butler 当前处于阶段一

对照经验飞轮三阶段，Butler 正在"跑通闭环"阶段。优先事项：
1. **全量记录**：确保 heartbeat 每轮的输入/输出/决策依据有结构化日志
2. **可追溯**：任务从创建到完成的全链路可回放（task_ledger 已有雏形）
3. **不急于自适应**：先积累足够的运行实例，再引入自动归纳规则

### 映射 3：门控层是最大短板

当前 Butler 的安全/权限/预算控制以约定形式散落在文档和 prompt 中（如"自我升级审批"、"不直接改核心代码"）。按四层架构思路，应该将这些收拢为独立的 Guard 机制：
- 显式的工具调用白名单/黑名单
- 单次任务的 token/时间预算
- 关键操作（文件删除、代码修改、外部调用）的 Maker-Checker

### 映射 4：避免"协调税"

Butler 当前的 Agent 数量还在安全区（主 Agent + planner + executor），暂未触及 4+ Agent 收益递减的阈值。在规划 AgentTeam / 专家 Agent 时，应：
- 先论证新 Agent 的增量价值是否大于协调成本
- 优先用 skill 扩展能力，而非增加 Agent 数量
- 每新增一个 Agent 角色，同步定义其在四层架构中的位置和 handoff 协议

---

## 可执行的启发点

| # | 启发 | 优先级 | 落点 |
|---|------|-------|------|
| 1 | 将门控逻辑从散落的 prompt 约定收拢为显式配置 | 高 | 新建 `butler_bot_agent/config/guard_policy.json` 或类似机制 |
| 2 | 在 task_ledger 中增加"失败原因分类"字段，为未来失败模式库积累数据 | 中 | task_ledger schema 扩展 |
| 3 | 定义 heartbeat 结构化日志格式，确保每轮 input/output/decision 可回放 | 中 | heartbeat 日志规范文档 |
| 4 | 绘制"Butler 四层 Harness 映射图"，作为架构决策的参考坐标系 | 低 | `docs/` 或 iodraw 架构图 |

---

## 开放问题（留给后续迭代）

1. Butler 的门控层应该在代码中实现（middleware 模式），还是通过 prompt + 配置文件的"软约束"即可？
2. 经验资产（案例库/模式库）的存储格式：JSON 还是 Markdown？需要支持语义检索吗？
3. 如何量化"协调税"——是否需要一个指标来衡量新增 Agent 的边际收益？
4. 知乎长文 #06 的正文尚未完整抓取，其中可能包含更详细的四层实现细节，后续补全后应回来修订本 Insight。
