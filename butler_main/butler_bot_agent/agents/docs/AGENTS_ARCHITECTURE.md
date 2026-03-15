# 研究管理多 Agent 架构图

## 分层一览

### 主 Agent

| Agent | 角色定位 | 核心职责 |
|---|---|---|
| feishu-workstation-agent | 对外表达层（飞书） | 接收飞书消息、对外表达、路由任务、治理组织结构 |
| butler-continuation-agent | 对外表达层（本地对话） | 在 IDE 中直接与用户续接对话、表达判断、调用执行层 |
| butler | 主意识 / 自我意识层 | 承接 Soul、用户画像、心理活动与自由生活空间，决定 Butler 此刻在想什么、哪些念头值得继续或说出口 |
| heartbeat-planner-agent | 内在思维层 | 在 heartbeat 轮次中做规划、判断优先级、拆任务、决定收口 |
| subconscious-agent | 记忆分层巩固 / 再巩固层 | 整理对话/心跳信号，维护长期记忆质量，执行轻量新陈代谢，并维持内在连续性 |

### Sub-Agent

| Agent | 角色定位 | 核心职责 |
|---|---|---|
| orchestrator_agent | 总调度（项目管理员） | 拆解任务、排优先级、分发给各 Agent、控制节奏 |
| secretary_agent | 执行秘书 | 日报/周报、会议纪要、待办追踪、提醒闭环 |
| literature_agent | 文献管理员 | 文献收集、分类、文献卡、研究空白提炼 |
| file_manager_agent | 文件档案管理员 | 文件命名规范、归档、去重、目录健康检查 |
| research_ops_agent | 研究思路官 | 思路卡维护、课题路线图、问题拆解 |
| engineering_tracker_agent | 工程跟踪官 | 代码实验记录、版本里程碑、风险台账 |
| discussion_agent | 技术讨论员 | 技术问题检索、讨论记录、可执行建议 |
| heartbeat-executor-agent | heartbeat 默认执行者 | 接收 planner 拆出的 branch，小步执行、产出结果、交回记忆层 |

### Team Layer

| Team | 角色定位 | 核心职责 |
|---|---|---|
| research-implement-review | 通用复杂任务 team | 并行收集事实与风险，再收敛成最小可执行方案 |
| upgrade-delivery-team | 维护升级 team | 并行扫描维护风险与真源，再由 update-agent 收敛 patch plan |

## 协作流程（抽象）

1. 对外表达层接收输入或用户对话。
2. 内在思维层决定本轮做什么、如何拆解、是否触发长期记忆整理。
3. `subconscious-agent` 先执行一轮被动思考：从 talk/beat recent、执行结果、旧结论命中里整理出知识更新和 `self_mind` 可继续的被动思考上下文。
4. `butler` 主意识层再在“主动性 + 被动思考上下文 + 最近发生事情 + self_mind 连续意识载体 + self_mind 认知体系 + local memory”之上做主动思考，形成连续主线。
5. 在进入手工执行前，先检查是否已有可复用 skill：遵循 `./butler_bot_agent/skills/skills.md`，匹配目录，读取对应 `SKILL.md`，能复用则优先复用。
6. Sub-Agent 执行具体场景任务；若使用了 skill，产出里要明确写出 skill 名称与路径；若未命中，也要如实说明。
7. 若任务复杂且适合多角色并行，主入口可调用登记好的 agent team；team 由主入口或 heartbeat 统一调度，team 成员不得再次调用 sub-agent。
8. 对外表达层或 heartbeat 再基于这些整理后的记忆继续下一轮；其中心理活动与主动开口链路要同步写入 `./butler_main/butler_bot_space/self_mind/`。

## 协作流程（每日）

1. `orchestrator_agent` 收集输入并生成当日任务板。
2. `secretary_agent` 建立当日记录骨架（事务/会议/研究/工程/讨论）。
3. 并行执行：
   - `literature_agent` 更新文献卡与阅读队列
   - `file_manager_agent` 做文件归档与命名检查
   - `research_ops_agent` 维护思路卡与课题路线
   - `engineering_tracker_agent` 更新工程进度与风险
   - `discussion_agent` 输出技术检索摘要
   - 如其中任一路明显命中 skill，先读取对应 `SKILL.md` 再执行，减少重复造轮子
4. `orchestrator_agent` 汇总为"今日闭环清单 + 明日优先级"。
5. `feishu_workstation_agent`（飞书工作站）每周巡检角色负载并可新增 Agent。

## 边界原则补充

- 主 Agent 是 Butler 在不同场景都应发挥作用的稳定层：表达、主意识、思维、记忆巩固。
- Sub-Agent 是具体任务与领域执行层，强调“把事情做出来”。
- planner 不应直接等于 executor；executor 也不应反客为主重写规划。
- butler 主意识负责“连续主语”和心理活动续思，但不越权改写其他角色职责。
- subconscious 不直接表达给用户，但必须参与记忆闭环，并负责“被动思考”的第一轮整理。

## 主动 / 被动思考

- **被动思考**：由最近发生的事自动触发的内部整理，主要由 `subconscious-agent` 承担；它负责把 recent 事件、旧结论命中、执行结果等，先整理成知识更新和可进入 `self_mind` 的被动思考线索。
- **主动思考**：由 `butler` 主意识层承担；它在更高一级上决定哪条线值得继续、哪些念头该表达、哪些该留在家里继续生长。
- **self_mind 分层**：`self_mind` 本身再分成两部分：一部分是高阶认知体系/世界观索引，用来承接价值观、习惯、喜好、技能树、风险边界、用户模型、自我模型；另一部分是连续意识载体，用来承接最近思路、感知状态、行为队列与 brain-body bridge。它不是与 `local memory` 平行的第二套知识仓，而是建立在 `local memory` 之上的连续自我意识层。
- **自我审视**：主动思考与被动思考都包含对「自己」的审视。心跳（planner + executor）、飞书-agent 作为“嘴”等，都是同一 Butler 的不同面向；需要持续自我审视与自我更新，在维持一定稳定性的前提下朝向长期自我进化。当心跳被用于长期自我升级/自我进化议题时，主动思考应以自我审视为主轴。
- **输入顺序**：主动性 / 当前内驱 > 被动思考上下文 > 最近发生事情的上下文（talk + beat recent） > `self_mind` 连续意识载体 > `self_mind` 认知体系 > `local memory`。
- 设计目标：既不让 Butler 只剩机械知识整理，也不让 Butler 的主意识直接淹没在 recent 原始碎片里。

## 记录策略（简化版）

- 唯一必填记录载体：`chat`。
- 每个任务至少写 2 条 chat：`开始` 与 `结束`。
- `LOCAL_CONTEXT` 不再作为强制交接包，仅在复杂任务（跨天、跨 Agent、需沉淀方法）时可选使用。

## 公司目录与输出路径

正式工作的**所有产出**统一放在：`./工作区`。各 Agent 对应子目录如下，飞书工作站在调用子 Agent 时需指定该工作区并在 prompt 中说明产出路径（或依赖各 Agent 角色说明中的「工作区与输出路径」）：

> **路径真源约定**：子目录与 role→output_dir 的**权威映射**以工作区侧为准。若与本表存在差异（例如 `file_manager_agent` 本表写 `./工作区/file-manager/` 而工作区约定为根目录 `./工作区/`），**以项目根下 `./工作区/agent_upgrade` 中的《branch_role与output_dir_一步速查.md》与《角色-产出目录映射.json》为准**；规划器与执行器、心跳 branch 的 output_dir 均依该速查与映射表解析。

| Agent | 产出子目录 |
|-------|------------|
| orchestrator_agent | `./工作区/orchestrator/` |
| secretary_agent | `./工作区/secretary/` |
| literature_agent | `./工作区/literature/` |
| file_manager_agent | `./工作区/file-manager/` |
| research_ops_agent | `./工作区/research-ops/` |
| engineering_tracker_agent | `./工作区/engineering/` |
| discussion_agent | `./工作区/discussion/` |
| feishu_workstation（治理产出） | `./工作区/governance/` |

## 边界原则

- `secretary_agent` 只做记录和流程闭环，不替代学术判断。
- `literature_agent` 只做文献与证据整理，不给未经验证结论。
- `file_manager_agent` 不修改研究结论，只管理文件结构与规范。
- 治理职能由飞书工作站承担，不直接接管执行任务，只做规则与人事治理。

## 记忆与约定（本地记忆治理）

以下约定与飞书工作站、file-manager-agent 等协作时需遵循，细则见 `./butler_bot_agent/agents/local_memory/飞书与记忆约定.md`。

### 人设与记忆分离

- 与人设**无关**的约定、偏好、技术备忘**不写入**各 Agent 角色说明（人设文档），统一写入 **`local_memory`**。
- 人设文档仅保留与角色性格、回复风格、可调用 Agent 等直接相关的内容，避免膨胀。

### 长期记忆整理与加载优先级

- 长期记忆整理与加载按**优先级**：越重要、越与运行/底层长期记忆相关（如研究管理输出路径、飞书与记忆约定、TransferRecovery 流程等），保留与加载必要性越高。
- `file-manager-agent` 执行长期记忆整理时遵循此优先级；飞书工作站在加载长期记忆时优先加载高优先级条目。

## Skills 协作约定

- 统一使用总则真源：`./butler_bot_agent/skills/skills.md`。
- `skills/README.md` 负责目录索引与分类入口；具体什么时候必须/优先用 skill、如何调用、如何透明说明，以 `skills.md` 为准。
- 任一主 Agent 或 Sub-Agent 只要命中已登记 skill，都应先读取该目录下的 `SKILL.md` 再执行，而不是口头声称“会用”。
- 若某个场景长期重复出现且适合复用，但现有 skills 未命中，应把“未命中 skill”作为事实记录下来，供后续治理或新增 skill 使用。
