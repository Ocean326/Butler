# SubAgent vs AgentTeam 双引擎架构 · Insight

- **来源 Raw**：`BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_subagent_vs_agentteam.md`
- **原始平台**：小红书（老朱说AI · 复盘系列第五篇）
- **原始日期**：2026-03-17
- **Insight 整理日期**：2026-03-18

---

## 核心论点（4 条）

### 1. 两种多 Agent 模式各有适用场景，不可互替

| 维度 | SubAgent（子代理） | AgentTeam（智能体团队） |
|---|---|---|
| **运行方式** | 进程内，毫秒级启动 | 独立进程，通过 mailbox 通信 |
| **协作能力** | 子代理间无直接通信，像"工具小工" | 成员间可自主通信、分工、汇总 |
| **适用场景** | 简单后台任务、一次性子任务 | 复杂研究/分析、跨阶段协作 |
| **生命周期** | 用 Map 管理，轻量回收 | SDK 管理，需处理 stream 生命周期 |
| **隐喻** | 一群随叫随到的工具人 | 一个有组织的项目组 |

**关键洞察**：不是选 A 或 B，而是在同一系统中同时保留两套引擎，按任务复杂度动态切换。

### 2. 双引擎设计的架构要点

原文作者在本地 AI 桌面应用中实现了双引擎共存，核心经验：

- **统一入口切换**：通过 `/team` 命令在两套执行引擎间切换，上层用户不需要关心底层差异。
- **共享 Provider + 记忆**：两套系统共用同一套模型 Provider 配置和记忆系统，通过适配层打通，避免各自为政。
- **解决的工程难题**：
  - SDK stream 生命周期管理（resume 循环 + 空闲检测）
  - ESM / CJS 混合加载带来的模块边界问题

### 3. 行业走向：从百花齐放到自组织

- 2025：MCP 协议成为标准，多智能体框架百花齐放（CrewAI、AutoGen、LangGraph 等）
- 2026 预测：**自组织 Agent 团队** + **跨平台协作** — AI 自主决定团队结构、分配任务
- 面向未来的桌面 Agent 应预留「多引擎、多团队」的扩展位

### 4. 记忆系统是双引擎的粘合剂

两种 Agent 模式如果各自维护独立状态，系统将退化为两套互不相干的工具集。**统一记忆**是让双引擎产出可叠加而非互相覆盖的关键架构决策。

---

## 与 Butler 当前架构的映射

| 双引擎概念 | Butler 现有对应 | 差距 / 演进方向 |
|---|---|---|
| SubAgent（轻量工兵） | heartbeat executor + 单次 skill 调用 | Butler 的 sub-agent 已有雏形（executor 分支执行），但生命周期管理偏手动 |
| AgentTeam（项目组） | planner → executor 分支树 | 目前是 planner 单点分派，尚无真正的"成员间 mailbox 通信" |
| 双引擎切换 | 无统一切换机制 | 可在 heartbeat planner 层做路由：简单任务走 SubAgent 模式，复杂任务走 Team 模式 |
| 共享 Provider + 记忆 | memory_manager + task_ledger | 已有统一记忆的基础，但 sub-agent 间共享上下文的接口尚未显式化 |
| 自组织团队 | 尚未具备 | 远期目标：让 planner 能根据任务自动决定召集哪些 Agent、分配什么角色 |

---

## 可执行建议（3 条）

1. **在 heartbeat planner 中引入"任务复杂度评估 → 引擎路由"逻辑**
   - 简单任务（单文件操作、单次抓取、单步查询）→ 直接走当前 executor 分支（SubAgent 模式）
   - 复杂任务（跨多文件的研究整理、需要多角色协作的系统设计）→ 走多分支并行 + 汇总模式（AgentTeam 雏形）
   - 初步可以用任务标签 / 预估步骤数做粗粒度路由，不需要重新造框架。

2. **显式化 sub-agent 间的上下文传递协议**
   - 当前 executor 分支之间通过 task_ledger 和文件系统隐式共享状态。建议定义一个最小的"分支间消息格式"：`{from_branch, to_branch, artifact_type, artifact_path, summary}`。
   - 这是从 SubAgent 模式自然演进到 AgentTeam 模式的桥梁，不需要引入 mailbox 基础设施，先用文件 + JSON 即可。

3. **把"双引擎"概念写入 Butler 架构演进路线图**
   - 在 `AGENTS_ARCHITECTURE.md` 或新增文档中，明确记录：Butler 的执行层将支持两种模式（轻量 SubAgent + 协作 AgentTeam），以及两者的切换条件和共享层设计。
   - 为后续架构决策提供锚点，避免在单一模式上过度投入。

---

## 主题标签

`#SubAgent` `#AgentTeam` `#双引擎架构` `#多智能体协作` `#记忆系统统一` `#任务路由` `#Butler架构演进` `#2026趋势`
