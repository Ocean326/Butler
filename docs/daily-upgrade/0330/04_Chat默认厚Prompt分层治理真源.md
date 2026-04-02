# 0330 Chat 默认厚 Prompt 分层治理真源与 V1 治理计划

日期：2026-03-30  
最后更新：2026-03-30（V1 首轮已实施并回写）  
状态：**第 0 部分 §1–§7** 为现役代码真源，必须与当前实现同步；**第 I–X 部分** 为 V1 计划文档，作为后续治理、实施、测试、回写与验收的统一基线。

关联文档：

- [00_当日总纲.md](./00_当日总纲.md)
- [02_AgentHarness全景研究与Butler主线开发指南.md](./02_AgentHarness全景研究与Butler主线开发指南.md)
- [0329 Chat显式模式与Project循环收口.md](../0329/02_Chat显式模式与Project循环收口.md)
- [0327 SkillExposurePlane与Codex消费边界.md](../0327/02_SkillExposurePlane与Codex消费边界.md)
- [当前系统基线](../../project-map/00_current_baseline.md)
- [功能地图](../../project-map/02_feature_map.md)
- [系统级审计与并行升级协议](../../project-map/06_system_audit_and_upgrade_loop.md)

---

## 文档定位

这份文档同时承担两种职责，但必须严格分层阅读：

1. **现状真源**
   - 用于回答“今天 chat 默认厚 prompt 到底由哪些块组成、块顺序是什么、门控在哪、recent 在哪一层、Codex 分支和 `/pure*` 如何覆盖”。
   - 这部分只允许描述**当前代码已存在的行为**。
2. **V1 治理计划**
   - 用于回答“后续如何把巨型 prompt 从静态堆叠改造成分层、可压缩、可退出、可观测、可维护的上下文系统”。
   - 这部分只允许描述**计划、阶段、验收、风险、回写纪律**，不得伪装成现役行为。

与 [02_AgentHarness全景研究与Butler主线开发指南.md](./02_AgentHarness全景研究与Butler主线开发指南.md) 的分工如下：

- `02` 是**上层方法论与分层裁决**：告诉我们应该用 `Context / Memory / State / Artifact / Policy Plane / Product Surface` 这套语言理解系统。
- 本文是**chat 默认厚 prompt 的专项治理真源**：把 `02` 的抽象落到 `prompting.py`、`dialogue_prompting.py`、recent、skills、capabilities、soul/profile 等具体拼装链。

---

## 改前五件事

| 条目 | 说明 |
|------|------|
| 目标功能 | Butler chat 最终送入模型的系统侧拼装，不含用户原始消息本身，但包含 system 侧静态块与 user 侧 recent 接入边界。 |
| 主要代码入口 | `prompting.py`、`dialogue_prompting.py`、`prompt_purity.py`、`runtime.py`、`mainline.py`、`session_modes.py`。 |
| 用户契约真源 | [0329 Chat显式模式与Project循环收口.md](../0329/02_Chat显式模式与Project循环收口.md)。 |
| 注入边界真源 | [0327 SkillExposurePlane与Codex消费边界.md](../0327/02_SkillExposurePlane与Codex消费边界.md)。 |
| 本文改动纪律 | 改块顺序、门控、预算、`/pure*` 语义、recent 接入方式、Codex 分支时，必须同步回写本文对应表格。 |

---

# 第 0 部分：现状代码真源（§1–§7，与实现同步）

> 维护纪律：`build_chat_agent_prompt`、`assemble_dialogue_prompt`、`_build_codex_chat_prompt`、`PromptPurityPolicy`、recent 组装链、capabilities 门控一旦变化，必须先改代码，再同步更新本节。

## §1 已存在的切薄入口

这些入口都是在“默认厚路径”之上做减法或分支，不负责替代完整上下文治理。

| 入口 | 类型 | 作用 |
|------|------|------|
| `/pure`、`/pure2`、`/pure3` | 用户 slash | 解析为 `PromptPurityPolicy`，逐项关闭 bootstrap、soul、profile、skills、capabilities、recent 等。真源：`prompt_purity.py`、`mainline.py`。 |
| `/chat`、`/share`、`/brainstorm`、`/project`、`/bg` 等 | sticky 主模式 | 影响 `_resolve_prompt_mode`、scene 文案、`MODE_RECENT_PROFILES` 配额，以及 runtime 侧是否拉取 capabilities prompt。真源：`session_modes.py`、`frontdoor_modes.py`、`mainline.py`。 |
| `RouterCompilePlan` | 前台编译计划 | 当前 router 会先把用户输入编译成 `intent_id / main_mode / role_id / injection_tier / capability_policy / skill_collection_id / router_session_* / chat_session_id`，再把结果写回 invocation metadata 供 runtime 与 prompt 层消费。真源：`router_plan.py`、`routing.py`、`mainline.py`、`session_selection.py`。 |
| `runtime_cli == codex` | 运行时分支 | 走 `_build_codex_chat_prompt`，不接完整 `assemble_dialogue_prompt` 厚对话核。真源：`prompting.py`。 |
| `features.chat_frontdoor_tasks_enabled` | 配置开关 | 控制前门上下文是否参与拼装。真源：`feature_switches.py` 与配置。 |
| `prompt_mode` 隐式推断 | 关键词 / intake | 改变 soul、local_memory、前门块、协议块是否出现。真源：`prompting.py` 中 `_resolve_prompt_mode` 与各 `_should_include_*`。 |

## §2 默认厚路径：块顺序与主门控（非 Codex）

下列顺序对应 `build_chat_agent_prompt` 中 `blocks` 的逻辑顺序。前门相关为 `insert`，因此用“约第 N 段”理解最终阅读顺序。

| # | 段标题 / 含义 | 默认厚（`PromptPurityPolicy()`） | 主要门控或数据源 |
|---|----------------|----------------------------------|------------------|
| 1 | 渠道开场白 | 总是 | `channel_profiles` |
| 2 | 渠道块 | 总是 | `render_channel_prompt_block` |
| 3 | 纯净模式说明 | 仅 `purity.enabled` | `render_prompt_purity_block` |
| 4-5 | 前门合同 + 前门协议 | 见 `_should_include_frontdoor_blocks` | `frontdoor_context`、`chat_frontdoor_tasks_enabled` |
| 6 | 角色文件引用 + router 角色卡 | `include_role_asset` | `CHAT_AGENT_ROLE_FILE_REL` + `router_plan.render_role_prompt()` |
| 7 | session selection 指示块 | 总是 | `_render_session_selection_block`；消费 `router_session_action / router_session_confidence / router_session_reason_flags`，告诉模型这是续接还是新题重开 |
| 8 | 渠道对话资产摘要 + 指针 | `include_dialogue_asset` | `feishu/cli/weixin` dialogue md，当前按“真源路径 + 摘要”渲染，默认预算约 `500` 字 |
| 9 | 当前场景 + phase | 总是 | `_render_scene_block`，由 bootstrap `CHAT.md` 按 mode 抽段 |
| 10 | Bootstrap 多段 | `include_bootstrap` | `load_chat_bootstrap`，`max_chars=1200` |
| 11 | 基础行为 | 总是 | bootstrap `## baseline` 或默认一句 |
| 12 | `assemble_dialogue_prompt` | 总是，内容受下级门控 | 见 §3 |
| 13 | intake 前台块 | `_should_include_request_intake_block` | `request_intake_prompt` |
| 14 | 维护 / 任务 / self_mind 扩展协议 | `include_extended_protocols` + 各 `_should_include_*` | `ButlerChatPromptSupportProvider` |
| 15 | 灵魂真源路径 | `inject_soul` 且 `include_soul_source_ref` | `_should_inject_butler_soul` |
| 16 | 飞书检索结果 | 有则加 | 参数 |
| 17 | Skills | `should_include_skills_for_purity` | `render_skill_prompt_block` |
| 18 | Agent capabilities | `include_agent_capabilities` 且 `_should_include_agent_capabilities` | 与 `runtime._should_include_capabilities_for_mode` 双层门控，见 §4 |
| 19 | 图片路径说明 | 有则加 | 参数 |
| 20 | 回复要求 | 总是 | bootstrap `## reply_requirements` + 渠道回复要求 |
| 21 | decide / 交付方式 | 总是 | 渠道 `allow_decide_send` |
| 22 | 用户消息 | 总是 | `user_prompt`，可能已含 recent，见 §5 |

**Codex 分支**：`_build_codex_chat_prompt` 复用“角色 / session selection / 场景 / baseline / 前门 / intake / skills / capabilities / 图片 / 用户消息”的基本思路，但不拼接 `assemble_dialogue_prompt` 对话核，也不走灵魂 / 画像 / local memory 摘录链，并固定追加 Codex Chat 约束。Codex 分支当前会保留 router 角色语义与 session 续接指示，但不再强行暴露角色文件路径指针。

## §3 `assemble_dialogue_prompt` 子层（对话语义核）

实现入口：`dialogue_prompting.py`。在默认厚路径中，该整段挂在 §2 第 11 项。

| 子块 | 厚路径默认 | 关闭条件或主门控 |
|------|------------|------------------|
| 基底三行 | 总是 | 无 |
| 主意识摘录 | 几乎不填 | 当前 `butler_main_agent_text` 多为空 |
| 灵魂摘录 | 常有 | `include_soul_excerpt` + `_should_inject_butler_soul`；`companion`/`maintenance` 强开；`share`/`project`/`bg` 关 |
| 对话硬约束 | 常有 | `include_conversation_rules`；从用户画像 md 的 `## 当前对话硬约束` 抽取 |
| 用户画像 | 常有 | `include_user_profile`；当前按“真源路径 + 摘要”渲染 |
| 长期记忆命中 | 常有 | `include_local_memory`；`companion`/`share` 仅 personal |
| self_mind 正文 / 认知 | 条件 | `include_self_mind` 且依赖 mode 或关键词；当前按“真源路径 + 摘要”渲染 |

当前常见摘录预算：渠道对话资产 `500`、灵魂 `1100`（`companion` 放宽到 `1500`）、规则 `500`、画像 `700`、普通 local memory `600`、维护态 local memory `1000`、self_mind `700`、self_mind cognition `500`。这些预算由 `prompting.py` 的 `_PROMPT_BLOCK_BUDGETS` 与对应调用参数共同约束。

## §4 Capabilities 的双层门控

1. **Runtime 侧**：`runtime.py::_should_include_capabilities_for_mode`
   - 先做 mode / phase / purity 级预筛；只有预筛通过后，才继续看 prompt 侧关键词门控。
   - `share`、`brainstorm`、`bg` 默认不拉取；`project` 仅 `imp` 相拉取。
2. **Prompt 侧协作意图门控**：`prompting.py::should_include_agent_capabilities_prompt`
   - 默认 chat 仍要求用户消息里出现多 agent 协作类关键词才视为真正需要。
   - 本轮实现后，runtime 会先复用这层判断，避免“不需要但先生成 capabilities 文本”的空耗；prompt 拼装时仍再次按同一条件决定是否注入。
3. **观测侧**：`prompt_debug_metadata['block_stats']` + runtime `[chat-prompt-block-stats]`
   - 每个块都会记录 `block_id / char_count / budget_chars / include_reason / suppressed_by / source_ref`，用于解释“为什么厚、厚在哪一块”。

因此任何 capabilities 改动都必须两层一起看，避免“算了不用”或“该注没注”的双重漂移。

## §5 Recent 不在 `prompting.py` 里组装

Recent 真源在 turn 引擎与 memory 链：`prepare_user_prompt_with_recent` 负责生成带 recent 前缀的 `prepared_user_prompt`。自 `0402` 起，recent 默认只读取当前 `session_scope_id` 下活跃 `chat_session_id` 的 entries/raw turns/summary pool。

- 默认：`prompt_user_text = prepared_user_prompt`，模型看到的 user block 已经含 recent。
- `/pure3`：当 `include_recent_in_prompt=False` 时，改用 `turn_input.user_prompt`，只削 user 侧 recent；system 侧厚块仍按 `build_chat_agent_prompt` 决定。

因此 `/pure2` 与 `/pure` 观感差异不大时，常见原因是 recent 仍占大量窗口。这是当前设计结论，不是块顺序错误。

## §6 文档同步纪律

1. 改 `build_chat_agent_prompt`、`_build_codex_chat_prompt` 的块顺序、门控或预算：同步更新本文 §2–§3。
2. 改 `PromptPurityPolicy` 字段或 `/pure*` 语义：同步更新本文 §1，并补 `prompt_purity.py` 头注释。
3. 改 router 编译结果字段、`role_id / injection_tier / capability_policy / skill_collection_id` 注入方式时：同步更新本文 §1–§2，并对照 `routing.py`、`runtime.py`、`prompting.py` 三处实现。
4. 新增切薄入口：先在 [0329 Chat显式模式与Project循环收口.md](../0329/02_Chat显式模式与Project循环收口.md) 补用户契约，再落代码，再在本文 §1 加行。
5. 与 Skill / Codex 消费边界冲突时，以 [0327 SkillExposurePlane与Codex消费边界.md](../0327/02_SkillExposurePlane与Codex消费边界.md) 与 `injection_policy.py` 为准。

## §7 当前最小测试面

- `butler_main/butler_bot_code/tests/test_agent_soul_prompt.py`
- `butler_main/butler_bot_code/tests/test_talk_runtime_service.py`
- `butler_main/butler_bot_code/tests/test_chat_recent_memory_runtime.py`
- `butler_main/butler_bot_code/tests/test_chat_router_frontdoor.py`
- `butler_main/butler_bot_code/tests/test_talk_mainline_service.py`

当前这三组里已经覆盖的首轮新增断言：

1. 渠道对话资产、用户画像等块已切到“摘要 + 真源指针”表达。
2. 普通 chat 在未命中协作关键词时，不会白算 `agent_capabilities_prompt`。
3. runtime 会把 `prompt_block_stats / prompt_block_budgets` 回传到执行元数据。
4. router session 选择结果会进入 prompt，并驱动 recent 只续接当前内部 chat session。

---

# 第 I 部分：V1 计划总目标与边界

## I.1 要解决的根问题

当前 chat 巨型 prompt 的问题不是“字太多”这么简单，而是四类系统性问题叠加：

1. **静态堆叠问题**
   - 很多内容只要默认进入 chat 就会反复携带，即使当前回合并不需要。
2. **职责混叠问题**
   - `Context`、`Memory`、`Artifact`、`Policy`、`Mode`、`Skill Exposure` 被混装在若干字符串块里，导致真源边界不稳。
3. **退出机制粗糙问题**
   - 现有 `/pure*` 是有效减法，但仍偏“套餐式关闭”，缺少更细粒度、可解释、可观测的退出语义。
4. **缺乏块级观测问题**
   - 今天可以感知“厚”，但还不能稳定回答“哪一块变厚、为什么变厚、是否真的对成功率有贡献”。

## I.2 V1 总目标

V1 不是一次性把 chat prompt 做成完美系统，而是建立一套可持续演进的治理框架。核心目标如下：

| 编号 | 目标 | 判定标准 |
|------|------|----------|
| G1 | 最小充分上下文 | 默认 chat 回合只装载完成当前决策所需的最小信息集合。 |
| G2 | 单一真源 + 指针化 | 长规则尽量驻留文档或资产文件，prompt 只保留摘要与稳定指针。 |
| G3 | 二级上下文按需读取 | 把长文、画像、soul、协议、artifact 等迁到外置层或会话层，避免一股脑堆在 system。 |
| G4 | 明确压缩与退出机制 | `/pure*`、mode、关键词门控、未来细粒度 policy，形成统一退出模型。 |
| G5 | 可观测、可回归 | 能按块统计长度、命中率、注入原因，并配套最小回归测试。 |
| G6 | 文档与代码不再漂移 | 现状真源、用户契约、计划文档、project-map 回写形成闭环。 |

## I.3 非目标

1. 不在本轮把 Butler 替换成外部 Harness。
2. 不在本轮设计一套新的通用 workflow DSL。
3. 不以“缩短 token”为唯一目标；如果缩短会伤害关键约束遵守，优先保行为正确。
4. 不直接把 Dify、DeerFlow、LangGraph、OpenAI Agents SDK 的术语回流成 Butler 现役命名。

## I.4 方法论基线

V1 明确采用 [02_AgentHarness全景研究与Butler主线开发指南.md](./02_AgentHarness全景研究与Butler主线开发指南.md) 的分层语言：

- `Product Surface` 负责给用户与 operator 暴露可解释行为。
- `Policy Plane` 负责决定“哪些块该出现”。
- `Context` 只表示当前轮模型可见内容。
- `Memory` 表示跨轮保留信息，不应默认全量回灌为 system。
- `Artifact / Resource` 表示可外置、可读取、可回引用的材料。

换句话说，治理 chat 厚 prompt，本质上是在做一次 **Context 预算回收**：把不该长期占据窗口的东西迁回 `Memory / Artifact / Resource / Policy` 所在层。

---

# 第 II 部分：问题诊断矩阵

## II.1 现状问题分解

| 问题 | 现象 | 根因 | V1 对策 |
|------|------|------|----------|
| 语义重复 | baseline、对话硬约束、回复要求、协议块中存在重复要求 | 多处各自增长，缺少去重真源 | 建重复矩阵，按“唯一保留侧”治理 |
| 长文常驻 | 角色摘录、对话资产、画像、soul、维护协议容易变厚 | 静态默认注入 + 预算控制不足 | 摘录瘦身、指针化、按 mode 更严门控 |
| recent 与 system 双厚 | system 厚块与 recent 都在抢窗口 | 会话连续性与静态合同未分层 | 把 recent 明确归 L1，会话摘要化纳入后续阶段 |
| capabilities 漂移 | runtime 可能生成，prompt 侧未必注入 | 双层门控分散 | 统一日志与触发依据，后续延迟生成 |
| `/pure*` 粗颗粒 | 只能整体开关一组块 | 当前 policy 粒度有限 | 后续引入细粒度 metadata policy |
| 文档漂移 | 文档描述和代码细节不同步 | 缺少固定回写纪律 | 现状真源与计划文档在一份文档中分区维护 |

## II.2 需要被严格区分的四类内容

1. **永远成立的基础合同**
   - 渠道、最低行为边界、回复要求、必要安全约束。
2. **随 mode 变化的操作语义**
   - `chat`、`share`、`brainstorm`、`project`、`bg`、`maintenance` 等差异。
3. **只在特定任务/当前轮需要的增强上下文**
   - capabilities、检索结果、任务协议、维护协议、图片说明、部分 soul / self_mind。
4. **应迁出 system 的会话连续性材料**
   - recent、artifact、用户工作区、长画像、长规则全文、长文档真源。

只要一段文本无法回答“它属于哪一类”，就不应该继续直接塞进默认 system prompt。

---

# 第 III 部分：V1 的三级上下文模型

## III.1 三层定义

| 层级 | 名称 | 载体 | 典型内容 | 设计要求 |
|------|------|------|----------|----------|
| L0 | 主拼装层 | `build_chat_agent_prompt`、`assemble_dialogue_prompt` 输出 | 渠道合同、场景、最小 baseline、必要硬约束 | 短、稳定、可版本化 |
| L1 | 会话工作集 | recent、prepared user prompt、project artifact、会话摘要 | 当前任务连续性、最近轮次、阶段状态 | 专用化，不与 L0 重复 |
| L2 | 外置二级上下文 | `docs/`、`CHAT.md`、画像文件、soul 文件、skill 资产、工作区 artifact | 长规则、长说明、可复用知识、引用材料 | 指针化、按需读取、可审计 |

## III.2 各层职责边界

1. L0 只保留完成当前轮决策必需的最小 system 合同。
2. L1 负责“这轮之前刚发生了什么”，不得被误塞回静态 system。
3. L2 负责“如果需要，去哪里拿更完整的说明”，不得默认全文复制进 L0。

## III.3 与 02 文档的映射

| 02 的母概念 | chat 治理中的落点 |
|-------------|-------------------|
| Context | L0 + 当前轮最终 user block |
| Memory | local_memory、recent 摘要化后的跨轮连续性 |
| Artifact | project_artifact、工作区文件、检索结果引用 |
| Policy Plane | mode、purity、feature switch、future metadata policy |
| Product Surface | slash、sticky mode、operator 可见统计与文档契约 |

---

# 第 IV 部分：二级上下文与按需读取策略

## IV.1 二级上下文对象清单

| 对象 | 当前状态 | V1 目标 |
|------|----------|---------|
| `CHAT.md` / bootstrap | 已存在，但仍有部分规则散落在 `prompting.py` | 收敛 mode 语义与基础文案，把字符串常量迁回文件真源 |
| 渠道对话资产 | 已摘录进入 prompt | 缩短摘录，保留路径引用，避免重复传达相同约束 |
| soul / 画像 / self_mind | 当前混合“摘录 + 条件注入” | 缩减默认摘录长度，按 mode 严格门控，保留真源路径 |
| `docs/project-map` / `docs/runtime` | 人读真源较强 | 作为长规则与稳定合同的二级真源，被 prompt 以短指针引用 |
| skills / capabilities | 已有门控，但链路分散 | 统一为“先判断需不需要，再生成，再注入”的策略 |
| artifact / 工作区文件 | 已存在但未系统纳入 prompt 治理 | 强化“结论进 artifact，prompt 留指针”原则 |

## IV.2 外置原则

一段内容满足任一条件时，应优先迁入 L2，而不是继续长驻 L0：

1. 该内容超过当前轮常见决策所需长度。
2. 该内容可被稳定路径或 artifact id 指向。
3. 该内容只在少数 mode / 少数任务中使用。
4. 该内容本质是说明文档，而不是 system 强制合同。

## IV.3 指针化规则

未来二级上下文在 prompt 中的表达应遵循统一格式：

1. **一句摘要**：告诉模型这份外置材料解决什么问题。
2. **稳定指针**：文件相对路径、artifact 名称或受控引用名。
3. **明确触发**：只有在模型具备读取该材料的通道时，才鼓励“按需阅读”。

禁止出现“不给路径、不给摘要，只写一句去看文档”的伪指针。

---

# 第 V 部分：压缩机制与退出机制

## V.1 当前已存在的退出机制

| 机制 | 当前能力 | 局限 |
|------|----------|------|
| `/pure`、`/pure2`、`/pure3` | 可以成组关闭厚块 | 粒度仍偏粗 |
| sticky mode | 可以改变 mode 级装载策略 | 与隐式关键词存在耦合 |
| mode / 关键词门控 | 可以让部分扩展块按需出现 | 触发依据分散，不易审计 |
| Codex 分支 | 绕过部分厚对话核 | 仍需与普通 chat 共享部分治理语义 |
| 摘录 `max_chars` | 提供硬顶 | 只能截短，不能解决职责错位 |

## V.2 V1 要补齐的压缩机制

1. **块级预算制度**
   - 每类块有明确预算，不再只凭局部 `max_chars` 各自演化。
2. **重复矩阵驱动压缩**
   - 先找重复，再决定删哪一侧，而不是纯靠压字数。
3. **二级上下文替代全文注入**
   - 优先“短摘要 + 指针”，再考虑大段摘录。
4. **capabilities 延迟生成**
   - 只有 prompt 侧最终判定会注入时，才去生成 capabilities 文本。
5. **会话摘要出口**
   - 作为后续阶段能力，用于减少 recent raw 堆叠，但必须与 0329 契约对齐。

## V.3 V1 要补齐的退出机制

1. **细粒度 policy 字段**
   - 目标是支持 `include_recent`、`include_role_excerpt`、`include_profile` 这类显式字段，而不是继续新增 slash 变体。
2. **块级命中原因可见**
   - 每一块为什么出现，必须能在日志里解释。
3. **回合级“厚度可解释”**
   - 至少能回答：本轮大头是 L0 还是 L1，哪类块超预算，是否由 mode 触发。

---

# 第 VI 部分：目标架构与工程拆包

## VI.1 目标架构

V1 希望把 chat prompt 治理稳定成下列形态：

1. **现状真源层**
   - 本文 §1–§7 固定描述当前块顺序、门控与测试面。
2. **策略决策层**
   - 由 mode、purity、feature switch、future metadata policy 统一决定“本轮该装什么”。
3. **主拼装层**
   - 只组装 L0 最小 system 合同与必要引用。
4. **会话连续性层**
   - 由 recent、会话摘要、artifact 状态承担 L1，不回灌到 L0。
5. **二级上下文层**
   - 由 `docs/`、资产文件、画像、soul、artifact、skills 构成 L2，按需暴露。
6. **观测层**
   - 记录每块长度、触发原因、是否被 purity 关闭、是否由 mode 拉起。

## VI.2 工程工作包矩阵

| 工作包 | 内容 | 涉及文件 / 真源 | 产出 |
|--------|------|------------------|------|
| P1 | 重复矩阵审计 | `prompting.py`、`dialogue_prompting.py`、本文 | 重复矩阵文档 + 删除建议 |
| P2 | 块级预算表 | `prompting.py`、本文 | 预算清单 |
| P3 | 文案真源回收 | `CHAT.md`、`prompting.py` | 从代码字符串迁回文件真源 |
| P4 | 指针化治理 | `docs/`、聊天资产、画像 / soul 载体 | 长文缩短、路径稳定 |
| P5 | capabilities 触发链收口 | `runtime.py`、`prompting.py` | 双层门控对齐、延迟生成设计 |
| P6 | purity 粒度升级 | `prompt_purity.py`、`mainline.py`、0329 文档 | 细粒度退出机制 |
| P7 | recent / 会话摘要联动 | turn / memory 链、0329 文档 | L1 压缩策略 |
| P8 | 块级统计与日志 | runtime / chat 日志链 | 可观测 schema + grep 入口 |
| P9 | 回归测试补齐 | 三个核心测试 + 新增断言 | 测试基线 |
| P10 | 文档回写 | 本文、0329、docs/README、project-map | 真源闭环 |

## VI.3 依赖顺序

推荐主序如下：

1. `P1 -> P2 -> P3`
2. `P4` 与 `P5` 可在 `P3` 后并行
3. `P6` 必须先更新 0329 用户契约，再改代码
4. `P7` 必须建立在 `P6` 或现有 purity 语义不冲突的前提下
5. `P8` 最好在 `P4/P5` 前后尽早开始，以便后续变化有可比数据
6. `P9/P10` 跟随每个工作包收口，不放到最后一次性补

---

# 第 VII 部分：分期实施计划

## 阶段 A：审计与真源收口

目标：先把“今天到底厚在哪里、重复在哪里、真源在哪里”固定下来。

| 编号 | 工作 | 结果 | 风险 |
|------|------|------|------|
| A1 | 建立 system 块重复矩阵 | 明确哪些规则重复出现、保留哪一侧 | 低 |
| A2 | 核对 mode / 关键词误触发 | 找出不该出现却出现的块 | 低 |
| A3 | 建立块级预算表 | 给后续压缩提供统一标尺 | 低 |
| A4 | 回写本文 §2–§3 与测试引用 | 现状真源稳定化 | 低 |

阶段出口：

1. 能列出默认厚 prompt 的主要块占比。
2. 能指出重复段落的唯一保留侧。
3. 三个核心测试仍通过或已知缺口被记录。

## 阶段 B：L0 瘦身与 L2 指针化

目标：把真正不该长驻 L0 的材料迁出去。

| 编号 | 工作 | 结果 | 风险 |
|------|------|------|------|
| B1 | 把长文案从 `prompting.py` 回收到 `CHAT.md` 或文档真源 | 代码字符串减少 | 中 |
| B2 | 角色、渠道对话、soul、画像等摘录缩短 | 默认 system 长度下降 | 中 |
| B3 | 增加“摘要 + 指针”表达 | prompt 中外置真源表达更稳定 | 中 |
| B4 | 对齐 0327 skill exposure 边界 | 避免 skill 侧重复注入 | 中 |

阶段出口：

1. 默认厚 prompt 在保行为前提下明显缩短或至少不再继续增长。
2. 关键合同仍然可解释，且外置材料具备稳定路径。
3. 文档说明与代码实现一致。

## 阶段 C：退出机制细化

目标：让“我要多厚/多薄”变成正式 policy，而不是隐式魔法。

| 编号 | 工作 | 结果 | 风险 |
|------|------|------|------|
| C1 | 设计细粒度 purity / metadata policy | 可以独立控制 recent、profile、role excerpt 等 | 中高 |
| C2 | 同步 0329 用户契约 | 用户可见行为有文档真源 | 中 |
| C3 | 保持 slash 兼容或给迁移策略 | 避免历史入口失效 | 中 |

阶段出口：

1. 默认路径与用户显式减法都具备可解释语义。
2. 测试能覆盖新老入口映射。
3. 日志能标识本轮具体应用了哪些 policy。

## 阶段 D：L1 压缩与观测闭环

目标：让 recent 不再成为不可治理的大头，并建立稳定观测面。

| 编号 | 工作 | 结果 | 风险 |
|------|------|------|------|
| D1 | 设计会话摘要或 recent 压缩策略 | 降低 recent raw 占比 | 中高 |
| D2 | 引入块级统计日志 | 可以按块追踪长度与命中原因 | 低 |
| D3 | 形成人工评审样例集 | 用真实样本验证缩短后行为未退化 | 中 |

阶段出口：

1. 能区分 system 厚与 recent 厚。
2. 能通过日志与样例解释一次 prompt 的主要成本来源。
3. 可以决定是否继续进入 V2 更深改造。

---

# 第 VIII 部分：验收、测试与观测

## VIII.1 验收维度

V1 验收不能只看 token 变短，必须同时满足四类口径：

1. **行为正确性**
   - 不引入明显角色漂移、协议遗漏、回复要求失效。
2. **长度与预算**
   - 默认厚路径不再无上限膨胀，关键块预算可解释。
3. **门控正确性**
   - 不该出现的块不出现，该出现的块可说明理由。
4. **真源一致性**
   - 文档、代码、测试、用户契约一致。

## VIII.2 最小测试矩阵

| 测试方向 | 当前基础 | V1 需要补的断言 |
|----------|----------|----------------|
| soul / profile / mode | `test_agent_soul_prompt.py` | mode 误触发、摘录瘦身后仍保关键约束 |
| runtime provider / support provider | `test_talk_runtime_service.py` | capabilities 触发链与扩展协议门控 |
| recent / purity | `test_chat_recent_memory_runtime.py` | `/pure3`、future metadata policy、recent 压缩契约 |

## VIII.3 观测 schema 建议

建议引入统一日志前缀，例如：`[chat-prompt-block-stats]`。最小字段如下：

| 字段 | 含义 |
|------|------|
| `block_id` | 块标识，例如 `bootstrap`、`dialogue_asset`、`skills` |
| `char_count` | 该块字符数 |
| `mode` | 当前 chat mode |
| `channel` | 当前渠道 |
| `purity_level` | 当前 purity 或 policy 档位 |
| `include_reason` | 出现原因，例如 `default`、`mode=maintenance`、`keyword=multi_agent` |
| `suppressed_by` | 若被关闭，记录关闭原因 |
| `source_ref` | 块的主要真源路径或生成入口 |

## VIII.4 人工样例验收

每个关键阶段至少抽样：

1. `chat` 默认普通问答
2. `share` 模式
3. `brainstorm` 模式
4. `project` 模式
5. `maintenance` 或多 agent 协作意图
6. `/pure3` 极薄路径
7. Codex 分支

人工检查点：

1. 是否还能稳定维持正确人设与回复要求。
2. 是否存在关键约束消失。
3. 是否还有明显重复段落。
4. 是否能解释为什么某些块被拉起。

---

# 第 IX 部分：风险、回滚与实施纪律

## IX.1 主要风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 过度瘦身导致角色漂移 | 回复风格和行为约束失效 | 保留关键摘要，不做一刀切删除 |
| 指针化后模型不去读材料 | 行为不稳定 | 只有在具备读取通道时才强调指针，并保留最小摘要 |
| capabilities 延迟生成改序引入回归 | 协作类行为失真 | 先做日志，再做延迟生成；必要时加特性开关 |
| recent 压缩破坏会话连续性 | 多轮上下文丢失 | 摘要与 raw recent 并行对照阶段过渡 |
| 文档再次漂移 | 实现与计划错位 | 每次改 prompt 必须同时改本文和相关契约文档 |

## IX.2 回滚原则

1. 所有 prompt 治理改动都应可按工作包回滚，不做跨多主题的大混改。
2. 用户契约变化与实现变化必须成对提交，避免文档先行漂移。
3. 块级统计日志优先于激进瘦身，没有观测就不做大刀修改。

## IX.3 实施纪律

1. 改现状块顺序或门控时，先改代码，再改本文 §1–§7。
2. 改用户可见行为时，必须同步改 0329 文档。
3. 稳定后若某部分被反复引用，应提升到 `project-map` 或 `runtime`，不要长期埋在 daily-upgrade。
4. 不允许新增又长又散的无真源字符串继续堆进 `prompting.py`。

---

# 第 X 部分：执行清单与回写清单

## X.1 执行清单

```text
[ ] A1 建 system 块重复矩阵
[ ] A2 走查 mode / 关键词误触发
[ ] A3 建块级预算表
[ ] A4 回写本文 §2–§3 与测试引用
[ ] B1 文案真源从 `prompting.py` 回收到 `CHAT.md` / 文档
[ ] B2 对话资产 / soul / 画像摘录瘦身
[ ] B3 建立摘要 + 指针表达
[ ] B4 skills 注入边界对齐 0327
[ ] C1 设计细粒度 purity / metadata policy
[ ] C2 同步 0329 用户契约
[ ] C3 兼容 slash 迁移策略
[ ] D1 设计 recent 压缩 / 会话摘要策略
[ ] D2 引入块级统计日志
[ ] D3 建立人工样例集与验收记录
```

## X.2 文档回写清单

| 变更主题 | 必须回写的文档 |
|----------|----------------|
| 块顺序 / 门控 / 预算 | 本文 §1–§7 |
| `/pure*` 或 mode 用户契约 | [0329 Chat显式模式与Project循环收口.md](../0329/02_Chat显式模式与Project循环收口.md) |
| skill / Codex 注入边界 | [0327 SkillExposurePlane与Codex消费边界.md](../0327/02_SkillExposurePlane与Codex消费边界.md) |
| 已稳定的治理规则 | `project-map` 或 `runtime` 对应真源 |
| 当天推进状态 | [00_当日总纲.md](./00_当日总纲.md) |

---

# 附录 A：文档与代码映射表

| 主题 | 文档真源 | 代码入口 |
|------|----------|----------|
| chat 厚路径块序与门控 | 本文 §2–§3 | `prompting.py`、`dialogue_prompting.py` |
| pure 语义 | 本文 §1、0329 文档、`prompt_purity.py` 头注释 | `prompt_purity.py` |
| recent 契约 | 0329 文档、本文 §5 | turn / memory 链、`mainline.py` |
| capabilities 双层门控 | 本文 §4 | `runtime.py`、`prompting.py` |
| skill 注入边界 | 0327 文档 | `injection_policy.py` 等 |
| Harness 方法论 | 02 文档 | 作为分层参考，不绑定单一代码文件 |

# 附录 B：本次 V1 重写相对旧版 04 的增量

1. 把“现状真源”和“治理计划”职责彻底拆开，避免计划段落伪装成现役行为。
2. 明确引入 `L0 / L1 / L2` 三级上下文模型，突出“二级上下文按需读取”。
3. 增加问题诊断矩阵、工作包矩阵、依赖顺序、分期出口、验收矩阵与回写清单。
4. 把 `02` 的 Harness 抽象真正下沉到 chat prompt 治理，而不是只停留在术语引用。
5. 增加块级统计日志 schema、人工样例验收和回滚纪律，使计划可执行、可验证、可追责。

# 附录 C：修订记录

| 日期 | 变更 |
|------|------|
| 2026-03-30 | 初版：chat 默认厚 prompt 块序、门控与简要治理计划 |
| 2026-03-30 | V1 重写：按“现状真源 + 计划文档”双层职责重组，补充三级上下文模型、二级上下文策略、压缩与退出机制、工作包矩阵、阶段计划、验收与回写纪律 |

---

# 完成报告（2026-03-30 首轮实施）

## 本轮完成项

1. `prompting.py`
   - 新增 `_PROMPT_BLOCK_BUDGETS`，把渠道对话资产、bootstrap、soul/profile/self_mind/local_memory、skills、capabilities 的预算显式化。
   - 默认厚路径与 Codex 分支都改成块级结构化拼装，并通过 `prompt_debug_metadata` 回写 `block_stats / block_budgets`。
   - 渠道对话资产、灵魂、画像、self_mind 相关块改成“摘要 + 真源指针”表达，而不是只塞长摘录。
2. `dialogue_prompting.py`
   - 对话语义核补了子块级 `dialogue_block_stats`，能区分 `dialogue_soul_excerpt / dialogue_user_profile / dialogue_local_memory / dialogue_self_mind*` 的长度与抑制原因。
3. `runtime.py`
   - `agent_capabilities_prompt` 改成“mode / phase / purity 预筛 + prompt 侧协作关键词门控都通过后才生成”。
   - runtime 新增 `[chat-prompt-block-stats]` 日志，并把 `prompt_block_stats / prompt_block_budgets` 回传到 `ChatRuntimeExecution.metadata`。
4. 测试
   - 补了“摘要 + 指针表达”“普通 chat 不白算 capabilities”“prompt block stats 可回传”的断言。

## 对应工作包状态

- `[x]` A3 建块级预算表
- `[x]` A4 回写本文 §2–§4 与测试引用
- `[x]` B2 对话资产 / soul / 画像摘录瘦身
- `[x]` B3 建立摘要 + 指针表达
- `[x]` P5 capabilities 触发链收口（首轮：延迟生成已落地）
- `[x]` P8 块级统计与日志（首轮：runtime 日志 + metadata 已落地）
- `[x]` P9 回归测试补齐（最小测试面）
- `[x]` P10 文档回写（本文）
- `[ ]` A1 建 system 块重复矩阵
- `[ ]` A2 走查 mode / 关键词误触发
- `[ ]` B1 文案真源从 `prompting.py` 回收到 `CHAT.md` / 文档
- `[ ]` B4 skills 注入边界进一步对齐 0327
- `[ ]` C1/C2/C3 细粒度 purity / 用户契约升级
- `[ ]` D1 recent 压缩 / 会话摘要策略
- `[ ]` D3 人工样例集

## 验证记录

已通过：

- `.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_agent_soul_prompt.py -q`
- `.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_talk_runtime_service.py -q`
- `.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_chat_recent_memory_runtime.py -q`

结果：

- `22 passed`
- `18 passed`
- `7 passed`

## 本轮未做

1. 未改 `/pure*` 用户契约，因此没有回写 `0329/02`。
2. 未进入 recent 摘要化/压缩策略，因此 §5 契约保持不变。
3. 未做服务重启与 live smoke；本轮收口停在代码、单测与文档真源一致性。
