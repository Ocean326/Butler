# OpenAI Codex Harness 工程范式 × Butler Agent Runtime 设计启发

> 母本：`BrainStorm/Working/openai_anthropic_recent_tech_posts_2026q1/openai/` 下 5 篇
> - 2026-02-11 Harness engineering
> - 2026-01-23 Unrolling the Codex agent loop
> - 2026-02-04 Unlocking the Codex harness (App Server)
> - 2026-03-11 From model to agent: Responses API with computer environment
> - 2026-01-29 Inside OpenAI's in-house data agent
> 提炼时间：2026-03-18
> 主题轴：Harness Engineering、Agent Loop、多端协议、Agent Runtime 基础设施、内部数据 Agent
> 区别于：`20260318_MAS_Harness四层架构_知乎深度拆解_insight.md`（知乎单篇的学术化四层架构）；本篇聚焦 **OpenAI 一手工程实践**，从 Codex 产品线提炼可操作的 harness 设计模式。

---

## 核心观点

### 1. 人类的角色正在从"写代码"转向"设计环境 + 表达意图 + 建立反馈回路"

**来源**：Harness engineering（2026-02-11）

OpenAI 用一个几乎没有人工手写代码、主要由 Codex 生成的内部产品来阐述这个范式转移。核心工程活动不再是逐行编码，而是：
- **Repository knowledge**：让 agent 理解代码库的结构、约定和上下文
- **Agent legibility**：让 agent 的行为对人类可读、可审计
- **架构约束**：通过约束而非指令引导 agent 的产出方向
- **合并哲学**：agent 产出的代码如何进入主干、质量门控怎么设
- **垃圾回收 / 熵增治理**：agent 持续产出会导致代码库熵增，需要系统性清理机制

**关键洞察**：Harness 不是"辅助工具"，而是 agent-first 世界里人类的主要工作界面。人类从直接执行者变成了环境设计者。

**→ Butler 映射**：Butler 的工作区（`./工作区`）、BrainStorm 体系、task_ledger 本质上就是在充当 "repository knowledge + 反馈回路" 的角色。当前的改进方向应该是：让 Butler 自己也意识到"工作区就是我的 harness"，而不仅仅是一个文件存放处。

---

### 2. Agent Loop = 推理 → 工具调用 → 结果回注 → 再规划，四步闭环

**来源**：Unrolling the Codex agent loop（2026-01-23）

Codex CLI 的 agent loop 被拆解为四个原子步骤：
1. **模型推理**：基于当前 context 决定下一步
2. **工具定义与调用**：明确工具接口和调用参数
3. **执行结果回注**：把工具输出注入下一轮 context
4. **再规划**：根据结果修正计划或决定终止

这不是新发明，但 OpenAI 强调的关键点是：**agent 不是一句 prompt，而是一套循环执行系统**。prompt 只是这套系统中的一个组件。

**→ Butler 映射**：Butler heartbeat 的 planner → executor → 回执 流程与此高度同构。差异在于 Butler 当前的"结果回注"环节较弱——executor 的产出经常以文本回执形式返回，没有结构化地反馈到下一轮的 context 拼装中。可参考 Codex 的做法，让每轮 executor 产出一份机器可读的结构化回执（而不只是人类可读的 markdown 报告）。

---

### 3. 跨多入口复用同一 Agent 的关键在于协议层抽象

**来源**：Unlocking the Codex harness / App Server（2026-02-04）

Codex App Server 的设计目标是让同一套 agent harness 能服务 web、CLI、IDE 扩展和桌面端。核心设计：
- **双向 JSON-RPC 协议**：统一的请求/响应/事件格式
- **会话原语**：thread（会话）、turn（轮次）、item（原子动作）三层抽象
- **客户端无关**：不同前端通过同一协议驱动同一 agent loop

**→ Butler 映射**：Butler 当前主要通过飞书消息入口驱动，但已有通过 Cursor IDE 驱动 heartbeat 的路径。如果未来要支持更多入口（命令行、Web 面板、移动端），需要在 Butler 和外部入口之间引入类似的协议抽象层。当前的 `feishu_handler` 实际上就是一个专用协议适配器，但没有被抽象为通用协议。

---

### 4. Agent Runtime = 计算机环境，而不只是 API 调用

**来源**：Responses API with computer environment（2026-03-11）

OpenAI 把"从模型到 agent"的关键一步定义为：**给模型一个完整的计算机环境**，而不是只给 prompt + API。这套环境包含：
- **Shell tool**：agent 可以执行任意命令
- **容器工作区**：隔离的文件系统和运行环境
- **网络访问控制**：agent 能上网但受限
- **Skills**：预定义的能力模块
- **Context compaction**：对话过长时的自动压缩机制

**→ Butler 映射**：Butler 当前的执行环境实际上就是 Cursor IDE + 本地文件系统 + Shell。这已经是一个"计算机环境"了，但缺少两个关键要素：
1. **隔离性**：heartbeat executor 直接操作用户文件系统，没有沙箱隔离
2. **Context compaction**：长对话时 context 会膨胀，目前没有自动压缩策略

---

### 5. 内部数据 Agent 的核心不是能力，而是权限边界和数据语义

**来源**：Inside OpenAI's in-house data agent（2026-01-29）

OpenAI 内部自用的数据 agent 展示了一个关键设计原则：**agent 要像同事一样协助分析，但不能越权查询或给出未经验证的结论**。设计要素包括：
- **Context 意识**：理解组织内的数据含义，而不是泛化处理
- **Memory**：记住历史交互和用户偏好
- **权限体系**：不是"能不能调 API"，而是"该不该看这个数据"
- **可信执行**：结论可追溯、可验证

**→ Butler 映射**：Butler 作为用户的个人助手，"权限"概念与企业 agent 不同，但"数据语义理解"高度相关——Butler 需要理解用户工作区里不同目录、不同文件的含义和重要程度，而不是把所有文件一视同仁。当前的 `MEMORY.md` 和 `STATE.md` 已经在做这件事，但颗粒度还不够。

---

## 与 Butler 架构的映射总览

| OpenAI Codex 设计模式 | Butler 对应机制 | 当前成熟度 | 可执行改进方向 |
|---|---|---|---|
| Repository knowledge | 工作区 + BrainStorm + skills | 中等 | 让 Butler 显式把工作区视为自己的 harness |
| Agent loop 四步闭环 | heartbeat planner → executor → 回执 | 已有 | 增加结构化回执格式（机器可读） |
| 跨端协议抽象 | feishu_handler（专用适配） | 低 | 抽象通用协议层，为多入口做准备 |
| 计算机环境 runtime | Cursor + 本地文件系统 + Shell | 高（能力够） | 缺隔离性和 context compaction |
| 权限与数据语义 | MEMORY.md + STATE.md | 基础 | 建立文件/目录语义索引 |
| Agent legibility | heartbeat 报告 | 中等 | 强化可审计性，增加决策链路记录 |
| 熵增治理 / GC | 无系统性机制 | 低 | 需要定期清理工作区的自动化流程 |

---

## 可执行的下一步

1. **结构化回执格式设计**：为 heartbeat executor 的产出定义一个 JSON schema——包含 `goal_achieved: bool`、`evidence: string[]`、`artifacts: string[]`、`uncertainties: string[]`、`next_step: string`，替代当前纯文本报告，让 planner 能机器化地吸收执行结果。

2. **工作区语义索引**：在工作区根目录维护一份 `workspace_semantic_map.md`，记录每个一级子目录的用途、重要度、更新频率，让 heartbeat 在操作文件前能快速判断"该不该动这个位置"。

3. **Context compaction 策略**：参考 OpenAI Responses API 的做法，在 prompt_assembly 中增加"长度超阈值时自动压缩旧轮 context"的逻辑——优先保留最近 2 轮和长期记忆，压缩中间轮次。

---

## 附：外围材料速览

以下 2 篇与 Butler 的直接关联较弱，但作为 OpenAI 工程实践的背景信息仍有参考价值：

- **Scaling PostgreSQL**（2026-01-22）：高增长产品下延后复杂分片的思路——先榨干读副本 + 连接池 + 缓存，再做分片。对 Butler 当前阶段不直接适用，但"先用简单架构推到极限"的理念与 Butler 的演进策略一致。
- **Beyond rate limits**（2026-02-13）：credits 余额 + rate limit + 实时计量的 waterfall 式访问控制。对 Butler 的 token 预算管理有设计参考价值。

---

## 主题标签

`#HarnessEngineering` `#AgentLoop` `#AgentRuntime` `#OpenAI` `#Codex` `#协议抽象` `#ContextCompaction` `#Butler架构演进`
