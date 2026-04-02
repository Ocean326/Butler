# Butler Flow 主脑自治与预制 Flow 平衡概念设计稿

日期：2026-04-01  
状态：概念真源 + 第一轮实现已落地（2026-04-01）  
所属层级：主落 L1 `Agent Execution Runtime` 的前台 `butler-flow` 产品语义，辅触及 `role/session` 编排心智  
定位：承接本轮关于 DeerFlow 与 Butler Flow 的 brainstorm，先固定设计方向，不在本文展开 schema、状态字段、接口与实现步骤

关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md](./02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)
- [04_butler-flow工作流分级与FlowsStudio升级草稿.md](./04_butler-flow工作流分级与FlowsStudio升级草稿.md)
- [0331 04b-butler-flowV1版本开发计划.md](../0331/04b-butler-flowV1版本开发计划.md)
- [0330 AgentHarness全景研究与Butler主线开发指南.md](../0330/02_AgentHarness全景研究与Butler主线开发指南.md)

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 给当前 brainstorm 先落一版概念性设计稿，明确 Butler Flow 后续如何吸收 DeerFlow 的“主脑才智”，以及 `supervisor` 与预制 `flow` 的关系。 |
| 所属层级 | 主落前台 `butler-flow` 产品与运行时心智，不改 `campaign/orchestrator` 控制面真源。 |
| 当前真源文档 | 以 [0401 当日总纲](./00_当日总纲.md)、[0401/02](./02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)、[0401/04](./04_butler-flow工作流分级与FlowsStudio升级草稿.md) 为主。 |
| 计划查看的代码与测试 | 本稿不进入代码与测试设计，只作为后续实现的概念上位稿。 |

## 一句话裁决

Butler Flow 应该吸收 DeerFlow 的“主脑才智”，但不应退化成单一 `lead_agent` 包打天下；推荐路线是把 `supervisor` 从“流程控制器”升级成“认知控制器”，同时保留 Butler 现有的外层治理边界与受控角色分工。

## 为什么要吸收 DeerFlow 的主脑能力

DeerFlow 最值得借鉴的，不是“单 agent loop”这个外形，而是主脑对全局任务保持持续建模的能力。它的优点主要体现在：

1. 主脑能一直持有整体目标、已知信息、关键不确定性和风险点，而不是每一步只按预定 phase 机械前进。
2. 主脑能先做轻量探测，再决定是否真正分派执行，从而减少过早承诺错误路径。
3. 主脑能比较多个候选推进路径，而不是只有“照模板往下走”这一种选择。
4. 主脑天然更适合承载“工作记忆”“动态假设”“风险登记”和“策略切换”。

Butler 如果只保留一个过于程序化的 `supervisor`，会很难发挥“主脑才智”；它更像调度壳，而不是会思考的 flow owner。

## 为什么不能直接照抄 DeerFlow

Butler 现有优势并不在“所有控制都塞进一个 agent”。

1. Butler 已经有较清晰的外层治理骨架：`supervisor / executor / judge / operator`。
2. Butler 的 operator 介入、pause/resume、receipt/trace、role-session 边界，本来就是产品化的重要资产。
3. 如果直接把所有判断、执行、恢复、验收都压回一个 `lead_agent`，短期会更灵活，长期会削弱审计性、可恢复性和产品边界。
4. DeerFlow 的单主脑模式适合“主脑很强、系统较轻”的 flow；Butler 更适合“主脑增强，但治理外壳仍然存在”的路线。

所以 Butler 要学的是“更聪明的主脑”，不是“把系统重新压扁成单 agent”。

## 两个极端方案及其问题

### 极端一：完全靠预制 Flow 驱动

问题不是稳定性不足，而是上限太低：

1. 预制 `flow` 会逐步变成硬脚本，`supervisor` 只剩跳格子能力。
2. 任务一旦偏离模板，系统就容易僵住，只能靠人工兜底。
3. 角色虽然存在，但更像静态工位，而不是围绕问题动态组织的能力组合。

### 极端二：完全交给自治 Supervisor 即兴发挥

问题不是灵活性不足，而是治理面会被冲垮：

1. `supervisor` 若能自由改写 phase、角色、验收边界，运行态会越来越难理解。
2. 每个 flow 都从零发明角色和流程，长期很难沉淀复用资产。
3. operator 很难分辨“这是合理自治”还是“系统在漂移”。

这两个极端都不是 Butler 适合走的路线。

## 推荐中间路线

推荐采用“预制 `flow` 作为强先验骨架，`supervisor` 在骨架内受约束自治”的中间方案。

核心含义是：

1. 预制 `flow` 提供默认阶段结构、默认角色集合、默认验收框架和常见推进路径。
2. `supervisor` 不再只是照单执行，而是持续维护自己的运行时理解，并在边界内决定下一步。
3. `supervisor` 可以临时探测、回跳、插入局部子阶段、切换已知角色，必要时生成当前 flow 私有的临时角色。
4. 这些变更只对当前 flow 生效，不应自动写穿成全局真源定义。

也就是说：预制 `flow` 是骨架，不是剧本；`supervisor` 可以改走法，但不能随意改任务本体。

## `flow`、`role`、`supervisor` 的概念关系

### `flow_definition`

它是预制骨架，也是系统给 `supervisor` 的强先验。  
它回答的是：这个任务通常有哪些阶段、哪些角色、哪些基本边界。

### `flow_runtime_plan`

它是 `supervisor` 对当前任务态势的运行时理解。  
它回答的是：当前问题被怎样理解、下一步候选路径有哪些、此刻该推进哪条。

### `flow_mutations`

它是运行过程中发生的局部结构调整。  
它回答的是：本次执行中，骨架被做了哪些局部变形，以及为什么。

### `role`

`role` 定义的是能力分工，不等于固定 phase。  
一个角色可以跨多个阶段复用；一个阶段也可以临时需要不同角色参与。

### `supervisor`

`supervisor` 是当前 flow 的认知控制中心。  
它负责维持对任务的整体理解、比较推进路径、选择调用哪些角色，并决定何时升级为 operator 介入。

## 自治权的推荐分层

### 第一层：阶段内自治

建议默认允许：

1. 在当前阶段内重试、切换已知角色、补一个 probe、重新排序局部步骤。
2. 为当前问题临时挂一个 flow-local 的辅助角色。
3. 在不改验收语义的前提下，更换推进策略。

这是最应该放开的自治层，因为它最接近“主脑才智”的真实发挥空间。

### 第二层：局部 Flow 结构变更

建议受约束允许：

1. 插入一个临时子阶段。
2. 从后续阶段回跳到上游阶段补洞。
3. 合并相邻小步骤，或把一个阶段拆成两个局部段落。

但这些变更必须满足两个条件：

1. 只对当前 flow instance 生效。
2. 必须留下结构化痕迹，能被 operator 看见，也能被后续复盘吸收。

### 第三层：全局 Flow 改写

建议默认不允许自治直写：

1. 不允许当前 `supervisor` 直接把一次运行中的局部变更，写回成全局 `flow_definition` 真源。
2. 如果运行态出现稳定的新模式，应以“候选新模板”或“待采纳升级建议”的方式沉淀。
3. 这一层应该由 operator 或更高层治理流程决定是否晋升为正式预制 `flow`。

这是为了防止单次运行把系统主线越改越散。

## 对角色体系的概念裁决

1. 默认优先复用已有 `role catalog`，不要把“现场发明角色”作为常规路径。
2. 临时新角色可以存在，但应只作为当前 flow 的附着体，而不是系统级永久角色。
3. `supervisor` 的价值不在于发明很多新角色，而在于判断何时该用现有角色、何时需要一个临时补位角色。
4. 一个好的多角色系统，不是角色越多越强，而是分工边界足够清晰，切换成本足够低。

## 对任务适配性的概念判断

这种中间路线比两个极端都更适合 Butler 的任务面。

1. 对标准化任务，它仍然能依赖预制 `flow` 快速起步，不必每次重做流程设计。
2. 对探索性任务，`supervisor` 可以靠运行时探测与路径比较，避免模板僵化。
3. 对复杂长任务，外层治理和 operator 介入仍然成立，不会因为主脑变强就失去可恢复性。
4. 对未来扩展，预制骨架、角色目录和运行时变异记录都能分别演进，而不是绑死在同一层。

## 统一 Prompt 理论的目标与反目标

这套统一 prompt 理论的目标，不是把系统写成一个越来越厚的总 prompt，而是提供一套可编译、可裁剪、可分级装载的设施。

### 目标

1. 让 `supervisor` 和各个角色都能复用同一套上位结构，而不是每种角色各写一套散乱 prompt。
2. 让 `same-session` 和 `new-session` 共用同一套对象模型，只是装载深度不同。
3. 让 context 成为受控资源，而不是“反正模型还装得下就继续塞”。
4. 让未来的 `supervisor` 或 `supervisor secretary` 能动态决定本轮该装多少、舍弃多少、优先读什么。

### 反目标

1. 不是让每次调用都把所有层信息全量重灌。
2. 不是把 repo 里的所有知识都预先写进角色 prompt。
3. 不是让“统一框架”反过来逼所有角色都变重。
4. 不是把 session 记忆当作可以替代结构化状态的黑箱能力。

一句话说，统一 prompt 理论首先是装载理论，其次才是 prompt 理论。

## 统一 Prompt 框架：逻辑层与装载层分离

建议把统一 prompt 体系拆成两层：

### 第一层：逻辑框架层

这层定义系统有哪些信息块，但不代表每次都必须全部发送给模型。

推荐固定五块：

1. `role_charter`
   - 角色身份、职责、禁区、默认风格
2. `governance_policy`
   - 权限边界、可调用对象、何时 ask operator、输出契约
3. `flow_board`
   - 当前 flow 的全局目标、阶段、关键事实、风险、约束、角色拓扑、最新决定
4. `role_board`
   - 当前角色自己的局部任务、局部记忆、依赖、待处理 handoff
5. `turn_task_packet`
   - 本轮具体要完成的任务、输入、成功判据和输出要求

这五块是统一语义骨架，不是固定的最终 prompt 文本。

### 第二层：装载编译层

这层决定本轮真正发给模型的内容。

它回答的不是“系统有哪些信息”，而是：

1. 这次是不是 `same-session`？
2. 这个角色是否已经拥有稳定局部记忆？
3. 当前任务是不是高风险、高分支、高依赖？
4. 本轮 token 预算和 context 压力如何？
5. 需要最小延迟，还是更强对齐？

所以 Butler 不该维护“一份最终 prompt”，而应该维护“可按需编译的 prompt packet”。

## 两个维度：Session 等级与装载等级

用户刚才提出的“两步”是对的，但它适合定义成两个正交维度，而不是两套独立体系。

### 维度一：Session 等级

#### A. `same-session / warm`

角色复用已有 session，依靠既有 thread、compact 后摘要和局部连续性继续工作。

适用：

1. `supervisor`
2. 持续多轮推进的重型 `executor`
3. 需要跨轮保有局部判断的研究/实现角色

#### B. `new-session / cold`

角色新建 session，通过显式状态重新 hydrate。

适用：

1. `judge`
2. `recovery`
3. 一次性执行角色
4. 需要去叙事污染、重新审视的场景

### 维度二：装载等级

无论是 warm 还是 cold，都不该只有“最简”与“全量”两档。  
推荐至少保留三档装载比例：

#### 1. `delta`

只发送本轮新增变化：

1. 最新状态变化
2. 新增风险
3. 本轮任务要求

适合：

1. 同 session 的连续执行
2. 当前局势稳定
3. 角色刚刚完成上一轮，记忆仍然新鲜

#### 2. `compact board`

发送一份压缩过的局势板：

1. 当前目标
2. 当前阶段
3. 已知事实
4. 未解问题
5. 最新决策
6. 关键约束
7. 本轮任务

适合：

1. warm session 但已经过了较多轮
2. 刚发生 phase 切换
3. 需要重新对齐，但不值得 full hydrate

#### 3. `full hydrate`

重新装载角色所需的完整最小世界模型：

1. `role_charter`
2. `governance_policy`
3. `flow_board`
4. `role_board`
5. `turn_task_packet`

适合：

1. 新 session
2. 恢复执行
3. 重大结构变异后
4. 需要明确去除旧叙事污染时

所以真正合理的运行态不是二选一，而是像这样组合：

1. `warm + delta`
2. `warm + compact board`
3. `cold + compact board`
4. `cold + full hydrate`

## Prompt 理论的核心裁决：统一的是结构，不是字数

最容易走偏的地方，是把“统一框架”误解成“统一长 prompt”。  
正确裁决应该是：

1. 统一的是对象结构和编译口径。
2. 不统一每次调用的文本长度。
3. 允许不同角色、不同风险等级、不同 session 状态使用不同装载比例。
4. 只要所有 packet 都能追溯回同一套对象模型，系统就仍然是一致的。

也就是说，Butler 需要的是：

`one prompt theory, multiple loading profiles`

而不是：

`one huge prompt for every role`

## 谁决定装载比例：Supervisor 与 Supervisor Secretary

后续建议把“装载决策”从业务推进中拆出来，形成一个轻量的上下文装载职责。

### 方案一：由 `supervisor` 自己决定

优点：

1. 简单直接
2. 认知与装载判断合一

问题：

1. `supervisor` 既管任务推进，又管 prompt 裁剪，职责会越来越重
2. 容易把“如何思考”和“如何喂上下文”混成一件事

### 方案二：引入 `supervisor secretary`

更推荐的长期方向是把它设计成 `supervisor` 的前置秘书层。

它不负责做最终任务判断，只负责：

1. 读取 `flow state`
2. 判断当前是 warm 还是 cold
3. 评估当前 context 压力和风险等级
4. 为目标角色编译出合适的 packet
5. 决定本轮使用 `delta / compact board / full hydrate` 哪一档

这层本质上更接近 `briefing compiler`，而不是新的业务 agent。

## 各角色的推荐默认档位

### `supervisor`

推荐默认：

1. `same-session`
2. 优先 `delta`
3. 跨 phase、重大失败、长时间中断后切到 `compact board`
4. session 丢失、模型切换或严重漂移时切到 `cold + full hydrate`

### `executor`

推荐按任务重量分流：

1. 复杂实现 / 长研究：可用 `same-session`
2. 单次修改 / 单次探索：优先 `new-session`
3. 默认不要把所有 `executor` 都做成长期线程

### `judge`

推荐默认：

1. `new-session`
2. 优先 `compact board`
3. 只读必要产物、必要验收条件和必要上下文

这样能减少被旧叙事绑架的概率。

### `recovery`

推荐默认：

1. `new-session`
2. 吃失败摘要、约束、最近决策与可用资源
3. 不需要长期 thread

## 从相近项目得到的共识

这轮补看了几类相近项目和官方文档，能提炼出几条很明确的共同规律。

### Anthropic Claude Code / Agent SDK

吸收到的核心点：

1. subagent 默认是 fresh context，只有在显式 resume 时才延续原上下文。
2. subagent 的价值主要是隔离高噪声工作，把摘要而不是完整 transcript 带回主线程。
3. 对于应留在主线程的复用 prompt/工作流，Anthropic 明确建议优先使用 `Skills`，而不是一律拆成 isolated subagent。
4. subagent 也支持 auto-compaction，说明“持久 session”依然需要主动管理 context 压力。

对 Butler 的启发是：

1. `same-session` 应该是可选增强，不是角色默认前提。
2. “resume worker” 应该只留给少数值得保有局部连续性的角色。
3. 主线程和子角色之间应以摘要回传为主，而不是回灌完整 transcript。

### OpenAI Agents SDK

吸收到的核心点：

1. 官方明确区分 `sessions`、`conversation state` 和本地 `context object`，说明“持久会话”与“结构化状态”不是一回事。
2. 官方把 `manager agent keeps control` 与 `handoffs` 明确分开，说明“主控 agent”与“直接把控制权转交给 specialist”是两种不同 orchestration。
3. 官方强调多 agent 最重要的做法之一仍然是“good prompts + monitor + specialized agents”，而不是盲目增加抽象层。

对 Butler 的启发是：

1. `supervisor` 适合 manager-style 持有主控权。
2. Butler 的 `flow state` 不应被 `session memory` 取代。
3. 本地运行态对象、模型可见上下文、会话历史，必须分开建模。

### LangChain / LangGraph

吸收到的核心点：

1. 官方把 multi-agent 的中心定义为 `context engineering`，这和 Butler 当前要解决的问题高度一致。
2. 官方明确提出 `Skills` 模式，即由单主脑按需加载专门 prompt/知识，而不是总是切换 agent。
3. 官方比较了多种模式在 `repeat request` 和 `multi-domain` 下的 token/call tradeoff，结论是不同模式应该按场景混用，而不是追求单一架构。

对 Butler 的启发是：

1. Butler 统一 prompt 理论不应只服务多 agent，也应支持“主脑按需加载技能包”。
2. `preset flow` 可以理解成强先验骨架，`skills/prompt packs` 则是可按需加载的上下文片段。
3. 以后 `supervisor secretary` 的本质，就是 Butler 自己的 `context engineering` 编译层。

### CrewAI

吸收到的核心点：

1. 官方把 crew、manager、planning、memory、prompt file 分开建模，说明 prompt 资产、流程结构、规划过程和记忆层本身就应拆开。
2. hierarchical process 需要明确的 manager 角色，planning 也可以作为每轮前置动作附着进去。

对 Butler 的启发是：

1. prompt 维护不应藏在角色代码里，而应作为可单独维护的资产层。
2. `supervisor` 运行前的 planning/briefing 可以是前置编译动作，而不是每轮都靠 agent 自己从零组织。

## 当前最优解：Butler 应采用的统一 Prompt 装载方案

综合这轮 brainstorm 和外部调研，当前最优解不是“全体角色持久 session”，也不是“全体角色 stateless”，而是下面这套混合式方案：

1. `supervisor` 是 flow-scoped persistent session，默认 warm continuation。
2. `flow state` 始终是显式真源，任何角色都不得把会话记忆当成唯一依据。
3. 所有角色共用同一套五段式逻辑框架：`role_charter / governance_policy / flow_board / role_board / turn_task_packet`。
4. 真正发给模型的不是固定 prompt，而是由编译器生成的 packet。
5. packet 至少支持 `delta / compact board / full hydrate` 三档装载比例。
6. `judge / recovery` 默认走 cold path，尽量减少历史叙事污染。
7. `executor` 按任务重量决定是否绑定 session，不预设为一刀切。
8. Butler 长期应补一个 `supervisor secretary / briefing compiler` 层，负责按 token 预算、风险等级、phase 变更和 session 热度决定装载比例。
9. `preset flow` 提供骨架；`prompt packs / skills` 提供按需上下文；`session continuity` 只提供连续性增强，不替代显式状态。

这套方案的关键优点是：

1. 它对有限 context 更友好，不会逼所有角色吃全量大 prompt。
2. 它兼容同 session 与新 session 两种运行形态。
3. 它给未来的自适应装载策略留了空间。
4. 它既能吸收 DeerFlow 的主脑才智，也不会牺牲 Butler 的治理外壳。

## 0401 第一轮实现回写

本轮已把概念稿中的一部分能力真正落到 `butler_flow` 前台运行时，但落法比概念稿更保守，当前采用“新能力已接入、默认仍保兼容”的策略。

### 已落实现

1. 已新增统一 packet/compiler 雏形，当前围绕：
   - `flow_board`
   - `role_board`
   - `turn_task_packet`
2. 已把 `prompt_packets.jsonl` 从“只记 prompt 文本”升级为“结构化 packet + rendered prompt”双落地。
3. 已把 `runtime_plan.json` 扩成更丰富的运行态读模型，开始携带 `flow_board / active_turn_task / latest_mutation`。
4. 已把 `mutations.jsonl` 正式接上线，支持记录：
   - `switch_role`
   - `bounce_back_phase`
   - `insert_subphase`
   - `spawn_ephemeral_role`
5. 已接入真实 `supervisor` LLM runtime 路径，具备独立 `supervisor_thread_id`、结构化决策和 fallback 到代码 heuristic 的能力。
6. 已把 executor / judge prompt 统一改到 packet 编译路径，不再只靠旧的散装 prompt builder。
7. 已支持带 guardrails 的 `ephemeral role`：
   - 只在当前 flow 生效
   - 必须挂靠 `base_role_id`
   - 允许通过 `role_charter_addendum` 做 flow-local 扩展
8. TUI 已能外显新增的 `supervisor_thread`、`session_mode`、`load_profile` 与 `latest_mutation`。

### 当前实现边界

1. 真实 `supervisor` 当前通过配置开启：
   - `butler_flow.supervisor_runtime.enable_llm_supervisor=true`
2. 默认仍保留 heuristic supervisor 主路径，目的不是回退方向，而是先保证现役前台回归全绿，再逐步扩大默认接管面。
3. `ephemeral role` 当前已能执行，但仍属于 flow-local 附着体，不进入 role catalog 真源。
4. 局部 mutation 已能落盘和驱动当前 flow，但仍不允许自动写回 builtin/template 定义。

### 当前裁决

因此，`0401/03` 在 2026-04-01 的真实状态不是“纯 brainstorm”，而是：

1. 概念方向已固定。
2. packet/compiler、mutation、ephemeral role、real supervisor runtime 已有第一轮实现。
3. 默认产品行为仍以兼容安全为先，真实 `supervisor` 先走配置开启，而不是未经验证地直接成为默认唯一主脑。

## 当前概念结论

1. Butler Flow 的升级方向不是“更重的流程控制器”，而是“更强的认知控制器”。
2. `supervisor` 应该成为真正理解任务、比较路径、管理风险和调度角色的主脑。
3. 预制 `flow` 必须继续存在，但它的角色应从“硬剧本”降级为“强先验骨架”。
4. 运行态自治应主要放在阶段内与局部结构层，不应默认拥有全局定义写回权。
5. 角色体系应以稳定 catalog 为主，临时角色为辅，且临时角色只在 flow-local 范围内生效。
6. 任何结构性变异都必须留下结构化痕迹，为 operator 理解、复盘与后续模板升级提供依据。
7. 统一 prompt 理论的重点是“按需装载”，而不是“统一长 prompt”。
8. `same-session` 与 `new-session` 应共享同一套对象模型，只在装载深度上分化。
9. `supervisor` 可以是持久 session，但 `flow state` 必须始终独立存在，并支持 cold replay。
10. 后续应把装载决策逐步从业务推进逻辑中拆出来，形成 `briefing compiler` 或 `supervisor secretary` 能力。
11. 当前第一轮实现已落 packet/compiler 与 real supervisor runtime，但为了兼容现役回归，真实 `supervisor` 仍先采用配置开启而非默认强切。
11. 对应产品面上，`single flow` 页应把 `supervisor` 的结构化决定流与 `workflow` 的实时执行流拆开显示；flow 主要信息头放在 `supervisor` 视图顶部，`handoff / role / operator` 主要通过结构化流式事件外显。

## 下一步方向

本文之后的下一步，不是立刻写实现细节，而是继续补三类上位设计：

1. `flow_board / role_board / turn_task_packet` 的最小字段口径，需要补一版轻量对象草案。
2. `warm/cold` 与 `delta/compact/full` 的切换条件，需要补一版运行时策略草案。
3. `supervisor secretary / briefing compiler` 是否独立成角色，还是先以内嵌设施存在，需要补一版职责裁决稿。
4. `preset flow`、`role catalog`、`prompt packs / skills`、`operator approval` 之间的边界，需要补一版结构化治理稿。
5. `supervisor` 结构化流与 `workflow` 实时流各自应该消费哪些事件族，需要补一版稳定事件分类口径。

## 外部参考

1. [Anthropic Claude Code Subagents](https://code.claude.com/docs/en/sub-agents)
2. [Anthropic Agent SDK: How the agent loop works](https://platform.claude.com/docs/en/agent-sdk/agent-loop)
3. [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
4. [OpenAI Agents SDK: Sessions](https://openai.github.io/openai-agents-python/sessions/)
5. [OpenAI Agents SDK: Context management](https://openai.github.io/openai-agents-python/context/)
6. [OpenAI Agents SDK: Agent orchestration](https://openai.github.io/openai-agents-python/multi_agent/)
7. [LangChain Multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent)
8. [LangGraph Multi-Agent Supervisor](https://langchain-ai.github.io/langgraphjs/reference/modules/langgraph-supervisor.html)
9. [AutoGen Multi-agent Conversation Framework](https://autogenhub.github.io/autogen/docs/Use-Cases/agent_chat/)
10. [CrewAI Documentation](https://docs.crewai.com/)

在这三件事完成前，暂不在本文中下沉到字段、接口、文件格式或具体实现流程。
