# 0318 Butler Prompt 完善计划

> 更新时间：2026-03-18
>
> 目标：结合 `0149_butler_prompt_refactor_guidance_v2.md` 与 `0219_两轨制prompt.md`，基于 Butler 当前真实架构，形成一版更适合当前仓库落地的 prompt 完善计划。

## 0. 先给结论

`v2` 文档的大方向是对的：

1. 不能再靠“胖 schema 直接拼 prompt”继续长出来
2. `raw_user_prompt` 默认回放需要收
3. talk / heartbeat 应该分开治理
4. prompt 应该吃“受控视图”，而不是吃存储层全貌

但它有几个明显不贴合 Butler 现状的地方：

1. 它默认 Butler 还缺一整套 prompt 组装骨架，实际仓库里已经有 `PromptAssemblyService`
2. 它默认状态抽取层还不存在，实际已有 `TurnMemoryExtractionService`、`SubconsciousConsolidationService`、`MemoryPipelineOrchestrator`
3. 它倾向于再起一批全新模块名，容易和现有 `memory_manager.py + services/* + memory_pipeline/*` 并行生长，制造第二套架构
4. 它把 skills 化讲得比较重，但 Butler 现在更紧急的是收敛 prompt-visible 边界，而不是先把一切拆成 skill

但结合新增的“两轨制 prompt”讨论，当前更适合 Butler 的路线不是“尽快做厚重 projection”，而是：

**沿现有骨架渐进重构，采用“两轨制 + 薄门控层”。**

也就是：

1. `Raw turn log` 作为可检索真源，保留最近若干轮 user / assistant 原文
2. `Light prompt view` 作为默认注入层，仍以 summary / requirement / local hits / task board 为主
3. `Thin projection gate` 只负责：
   - 默认 prompt 保持干净
   - 需要时去查 raw
   - 查回来后裁剪、脱敏、按用途注入

---

## 1. 当前 Butler 已经有什么，不该重复造轮子

### 1.1 prompt 组装骨架已经存在

当前仓库已经有：

- `butler_main/butler_bot_code/butler_bot/services/prompt_assembly_service.py`

这里已经明确分成：

1. `assemble_dialogue_prompt()`
2. `assemble_planner_prompt()`
3. `DialoguePromptContext`
4. `PlannerPromptContext`

这说明 Butler 不是“完全没有 prompt skeleton”，而是：

- skeleton 已经有
- 但动态上下文输入还不够精简和治理化

因此不建议直接再起一个平行的 `core_contracts.py + prompt_projection.py + prompt_budget.py` 三件套，把旧逻辑整体废掉。  
更合理的做法是：

1. 保留 `PromptAssemblyService` 作为装配层
2. 在它之前增加一层“上下文投影 / 字段收敛”服务
3. 让 talk / heartbeat 的动态输入先投影，再交给 assembly

### 1.2 记忆抽取与归一化已经部分存在

当前仓库已经有：

- `butler_main/butler_bot_code/butler_bot/services/memory_service.py`
- `butler_main/butler_bot_code/butler_bot/services/subconscious_service.py`
- `butler_main/butler_bot_code/butler_bot/memory_pipeline/orchestrator.py`

它们已经承担了：

1. 从 user / assistant 回合抽取候选记忆
2. recent entry 归一化
3. companion entry / implicit long-term signal 推断
4. compact / maintenance / post-turn pipeline 协调

所以 Butler 不是“还没有 Extractor / Normalizer”，而是：

- 已经有初步 extractor / normalizer
- 但没有把“存储层字段”和“prompt 可见字段”彻底切开

因此本轮不该先推翻旧抽取层，而应优先：

1. 利用已有抽取结果
2. 增加 prompt projection 规则
3. 只在确有必要时再新增更细的 state store

### 1.3 heartbeat 的任务真源已经明确

当前 heartbeat 任务真源已经是：

- `task_ledger.json`

而不是：

- `heart_beat_memory.json`

legacy store 目前更多是 bootstrap / 同步视图。

所以 Butler 不需要再讨论“要不要把 task 统一迁到 ledger”，这件事在架构上已经定了。  
真正要补的是：

1. planner prompt 不要再受到 legacy 膨胀视图的反向污染
2. `heart_beat_memory.json` 需要控体积，避免兼容层继续长胖

---

## 2. 对 v2 文档的批判性审视

### 2.1 可以直接吸收的部分

以下判断基本成立，可以直接吸收：

1. 默认上下文应以 summary / state projection 为主，不应回放整段原文
2. 原文只应在 wording-sensitive / evidence-sensitive / quote-required 等特殊条件下引入
3. assistant 长篇原文不应默认进入 prompt
4. talk / heartbeat 应使用不同的上下文视图
5. prompt-visible field 必须白名单化

### 2.2 需要改写后再用的部分

以下内容方向对，但表达方式需要更贴当前实现：

1. `PromptProjection`
   - 可以做，但不宜做成厚重的语义重构中心
   - 更适合落成“薄门控层”，挂在现有 assembly 前面
   - 它主要负责检索门控、字段白名单、摘录裁剪，而不是先定义大量新状态类型
2. `state 抽取层`
   - 已有雏形，不应重新造一套平行 extractor
   - 应先在现有 `memory_service.py` / `subconscious_service.py` 基础上补“prompt 可见性”
3. `assistant_state_store`
   - 长期是合理方向
   - 但不应作为第一阶段前置条件
   - 当前优先级低于 raw 保留、按需检索、字段白名单、planner 视图收缩

### 2.3 当前不宜重投的部分

以下内容如果现在就做，容易偏离 Butler 的现实：

1. 大规模新目录重构
   - 例如一次性引入 `prompting/ state/ memory/ tasks/ skills/` 全新布局
   - 风险是让旧逻辑和新逻辑双轨并存
2. 把 skills 作为当前主抓手
   - Butler 已经有 skill registry / catalog
   - 现在的问题主要不是“没有 skills”，而是 prompt 注入边界不清
3. 先上复杂 token 槽位系统
   - 方向正确
   - 但 Butler 眼下更适合先做简单预算白名单和 block 上限
   - 否则实现成本高，收益不成比例

---

## 3. Butler 当前最真实的问题，不要抽象错

本轮判断，Butler 当前 prompt 侧的关键问题不是“完全缺少现代范式”，而是以下四个更具体的问题：

### 3.1 prompt 可见字段和存储字段还没真正分层

现在 `recent_memory` 的 entry schema 很胖，但 prompt 实际主要消费：

1. `topic`
2. `summary`
3. `status`
4. 少量 `raw_user_prompt`
5. 少量 `next_actions`

这导致两个后果：

1. 存储层看起来复杂，维护者会误以为这些字段都在 prompt 中发挥同等作用
2. 任何未来修改都容易让新字段“顺手”漏进 prompt

### 3.2 `raw_user_prompt` 默认回放是真实高优先级风险

这不是理论问题，而是已经在真实数据里出现了敏感原文回流。  
因此本轮第一优先级不是“抽更细的语义状态”，而是：

**先把原文回放闸门收住。**

### 3.3 heartbeat legacy 兼容层过胖

`heart_beat_memory.json` 当前更多是兼容视图堆积池，不是 planner 主真源。  
它的风险不是“当前已经直接灌满 prompt”，而是：

1. 持续膨胀
2. 未来误接回 planner
3. 兼容层反向污染正式状态层

### 3.4 当前最大缺口其实是“没有稳定的 raw 检索轨”

recent 现在同时被拿来做：

1. 续接上下文
2. 近期要求回放
3. 任务候选输送
4. heartbeat 近期背景

这并不全错，但会让 recent 成为“什么都往里放”的中间层。  
与此同时，Butler 当前又缺一个稳定的 raw turn 检索轨，导致系统在两种坏选择之间摇摆：

1. 不带 raw，于是“那个链接 / 上次报错 / 刚才那段代码 / 你答应的事”很难精确回忆
2. 直接回放 raw，于是又把敏感文本和噪音带回 prompt

因此 Butler 现在更适合的是：

- 不立刻推翻 recent
- recent 回到“近期摘要层”
- 新增一条独立 raw 检索轨，专门解决精确回指问题

---

## 4. 适合 Butler 的目标架构

本轮不建议引入“全新架构名词体系”，建议采用更贴 Butler 当前代码的目标分层：

### 4.1 第一层：稳定骨架层

继续由现有 prompt 模板和 `PromptAssemblyService` 承担。

职责：

1. 保持 talk / planner 的固定 section 结构
2. 只做文本装配
3. 不负责决定“哪些状态应该出现”

### 4.2 第二层：Raw turn log 轨

新增或明确一条独立的原文轨道，用来保存最近若干轮 user / assistant 原文，但不默认注入 prompt。

职责：

1. 保存最近 20~50 轮 raw turns
2. 作为“找链接 / 找路径 / 找报错 / 找代码片段 / 找原话 / 找承诺”的检索真源
3. 与 recent summary 分轨，不再让 `raw_user_prompt` 直接承担 prompt 回放职责

### 4.3 第三层：Light prompt view 轨

默认 prompt 仍保持轻量，主要包含：

1. recent summaries
2. recent requirements
3. local memory hits
4. task board view
5. 少量 quoted excerpts

也就是说，默认常驻上下文仍然以轻量摘要为主，不以 raw transcript 为主。

### 4.4 第四层：薄门控层

新增一个轻量服务，例如：

- `butler_main/butler_bot_code/butler_bot/services/prompt_projection_service.py`

但这一层的职责应重新定义为“薄门控层”，而不是“大语义重构层”。

职责：

1. 决定当前轮是否需要查 raw
2. 如果需要，决定查哪类 raw 对象
3. 对查回内容做脱敏、裁剪、用途标注
4. 把结果投给 `PromptAssemblyService`

典型触发条件：

1. “那个链接”
2. “上次报错”
3. “刚才那段代码”
4. “你上轮答应的事”
5. “按我刚才原话”

### 4.5 第五层：状态抽取与记忆流水线
继续复用：

1. `TurnMemoryExtractionService`
2. `SubconsciousConsolidationService`
3. `MemoryPipelineOrchestrator`

职责不变：

1. 生成 recent entry
2. 做归一化和 companion signal
3. 做 compact / maintenance / post-turn 维护

### 4.6 第六层：任务真源层

继续明确：

1. `task_ledger.json` 是 heartbeat 任务真源
2. `heartbeat_tasks.md` 是 planner 可读视图
3. `heart_beat_memory.json` 只是兼容层

---

## 5. 本轮建议的最小落地方案

### 5.1 阶段一：先控风险，不谈大重构

目标：在不大动架构的前提下，先把最危险的 prompt 注入点收住。

应做事项：

1. 关闭 `raw_user_prompt` 的默认直接回放
2. 如果必须展示近期显式要求，优先使用：
   - `topic`
   - `summary`
   - `next_actions`
   而不是直接拼 `raw_user_prompt`
3. 新增最近若干轮 raw turn 的稳定保存，不默认注入
4. 为 raw turn 建立轻量 artifact index，优先抽：
   - URLs
   - file paths
   - commands
   - error blocks
   - code snippets
   - explicit user constraints
5. 为 talk prompt 建显式字段白名单
6. 为 heartbeat recent 建显式字段白名单
7. 给所有“原文摘录”增加统一入口：
   - 脱敏
   - 裁剪
   - 用途标记
8. 给 `heart_beat_memory.json` 加控量策略：
   - 活跃任务优先保留
   - done 任务只保留少量最近样本

这一阶段不需要引入新 store，也不需要大目录重构。

### 5.2 阶段二：引入 Prompt Projection，但只补一层

目标：补一个很薄的“检索门控 + 轻量投影”层，而不是厚重状态机。

建议新增：

- `services/prompt_projection_service.py`

建议提供两个最小接口：

```python
class PromptProjectionService:
    def build_talk_projection(self, workspace: str, user_prompt: str, recent_entries: list[dict]) -> dict:
        ...

    def build_heartbeat_projection(self, workspace: str, heartbeat_cfg: dict) -> dict:
        ...
```

输出目标不是复杂 schema，而是紧凑的 prompt view，并能决定是否检索 raw。

talk projection 最小建议字段：

1. `recent_summaries`
2. `recent_requirements`
3. `local_memory_hits`
4. `user_profile_excerpt`
5. `self_mind_excerpt`
6. `quoted_excerpts`
7. `raw_turn_artifact_hits`

heartbeat projection 最小建议字段：

1. `task_board_view`
2. `recent_execution_signals`
3. `relevant_local_memory_hits`
4. `runtime_context`
5. `skill_catalog_excerpt`

### 5.3 阶段三：清 recent 的职责，不急着新建一堆 store

目标：让“两轨制”稳定下来，recent 负责摘要，raw 负责检索真源。

应做事项：

1. 明确 recent 的 prompt-visible 字段只用于续接，不再默认承担精确原文回放
2. 明确 task 状态继续由 `task_ledger` 负责
3. 明确长期偏好 / 规则继续由 `local_memory` 和用户画像负责
4. assistant 承诺 / pending action 先尝试通过现有 `next_actions` 与任务流衔接
5. raw turn 只在命中回指 / 精确措辞 / 证据需求时进入 prompt

这一阶段可以暂缓新建 `assistant_state_store`。  
原因很简单：Butler 现在先收可见边界，比再造一个状态库更重要。

### 5.4 阶段四：再考虑更细的状态化增强

只有当阶段一到三稳定后，再考虑：

1. 是否新增 `assistant_state_store`
2. 是否把 commitment / assumption / plan / decision 做成更明确的结构化状态
3. 是否引入更细的预算管理
4. 是否拆出更多 skill 化能力

---

## 6. 建议的 prompt 完善路径

### 6.1 talk prompt

Butler 对话侧本轮不需要推翻现有 prompt，而是做三件事：

1. 收缩 recent 注入块
2. 去掉高风险原文回放
3. 增加“按需 raw 引用”能力
4. 把“续接提示 / 最近要求 / 长期命中”改成更稳定的 section

建议结构：

1. 稳定角色骨架
2. 当前对话硬约束 / 最近确认规则
3. 当前用户画像
4. 近期摘要视图
5. 长期记忆命中
6. self_mind 摘录
7. 可选原文摘录 / raw artifact 命中

其中第 4 块应由薄门控层生成，不再由存储字段直接拼；第 7 块默认为空，只在命中精确回指时出现。

### 6.2 heartbeat prompt

heartbeat 侧本轮不建议大改 planner 总模板，而是做两件事：

1. 进一步明确 `task_ledger / heartbeat_tasks.md` 是任务主视图
2. recent 只保留“最近执行信号”，不再承担任务真源角色
3. heartbeat 不退化成聊天历史驱动

建议结构：

1. planner 骨架
2. 当前任务板视图
3. 最近执行信号
4. 本地长期记忆命中
5. runtime / maintenance 上下文
6. skills / subagents / teams 目录摘录

这和当前实现是兼容的，不需要完全推翻。

---

## 7. 具体落点建议

### 7.1 应优先修改的代码位置

第一优先级：

1. `butler_main/butler_bot_code/butler_bot/memory_manager.py`
   - `prepare_user_prompt_with_recent()`
   - `_render_recent_requirement_context()`
   - `_render_recent_context()`
   - `_render_unified_heartbeat_recent_context()`
   - recent raw turn 落盘与读取入口
2. `butler_main/butler_bot_code/butler_bot/services/prompt_assembly_service.py`
   - 保持装配职责
   - 接收投影视图

第二优先级：

1. `butler_main/butler_bot_code/butler_bot/services/subconscious_service.py`
   - recent 归一化后可保留胖 schema，但 prompt-visible 规则应独立出去
2. `butler_main/butler_bot_code/butler_bot/services/memory_service.py`
   - 继续作为候选提炼入口，不要顺手承担 prompt 投影职责

### 7.2 建议新增但应保持克制的文件

建议只新增一个主要服务：

- `butler_main/butler_bot_code/butler_bot/services/prompt_projection_service.py`

如有必要，再补一个常量文件：

- `butler_main/butler_bot_code/butler_bot/services/prompt_visibility_rules.py`
- `butler_main/butler_bot_code/butler_bot/services/raw_turn_artifact_index.py`

不建议本轮一口气新增：

1. `assistant_state_store.py`
2. `decision_store.py`
3. `core_contracts.py`
4. `prompt_budget.py`
5. 一整套全新 `state/` 包

这些不是永远不做，而是不是现在做。

---

## 8. 这一版适合 Butler 的验收标准

### 8.1 talk 侧

达标条件：

1. 默认情况下不再直接回放 `raw_user_prompt`
2. recent 主注入仍可续接上下文，但不暴露胖 schema
3. 用户明确要求保留原话，或出现“那个链接 / 上次报错 / 刚才那段代码 / 你答应的事”时，才能走受控 raw 检索


### 8.2 heartbeat 侧

达标条件：

1. planner 继续以 `task_ledger / heartbeat_tasks.md` 为任务主视图
2. recent 只作为背景和最近执行信号
3. heartbeat 不依赖聊天 raw history 推进任务
4. legacy `heart_beat_memory.json` 不再继续无上限膨胀
5. prompt 中看不到 done pile 的无关历史堆积

### 8.3 工程侧

达标条件：

1. 没有再造第二套 prompt 框架
2. 没有把更多逻辑继续堆回 `memory_manager.py`
3. 新逻辑可测试、边界清晰
4. talk / heartbeat 的职责更清楚，而不是更混

---

## 9. 推荐实施顺序

### 第一步

先做风险收敛：

1. 去掉 `raw_user_prompt` 默认回放
2. 保存最近 20~50 轮 raw turns，但不默认注入
3. 建 raw artifact 轻索引
4. 加 prompt-visible 白名单
5. 压缩 `heart_beat_memory.json` 的 done 堆积

### 第二步

补薄门控层：

1. talk projection
2. heartbeat projection
3. on-demand raw retrieval
4. 原文摘录判定与脱敏入口

### 第三步

接入现有 `PromptAssemblyService`：

1. talk prompt 改吃 projection
2. planner prompt 改吃 projection

### 第四步

补回归测试：

1. 敏感原文不回放
2. “那个链接 / 上次报错 / 刚才那段代码 / 你答应的事” 能正确回指
3. 近期摘要仍能续接
4. heartbeat 仍能正确选 task
5. planner 不从 legacy pile 中捞错任务

---

## 10. 最终判断

适合 Butler 的 prompt 完善路线，不是按 `v2` 概念稿去平地重建一个全新 agent harness，而是：

1. 保留现有 `PromptAssemblyService` 作为装配骨架
2. 保留现有 memory extraction / subconscious / pipeline 体系
3. 增加一条独立 `Raw turn log` 检索轨
4. 默认 prompt 继续使用轻量 `Light prompt view`
5. 在中间补一层薄门控层，负责“何时查 raw、查什么、怎么裁剪”
6. 先解决 `raw_user_prompt` 回放和 prompt-visible 边界
7. 再逐步把 recent 从“万能中间层”收缩为“近期摘要层”

一句话概括：

**Butler 当前更适合走“两轨制”：默认 summary，保留 raw，按需检索，planner 继续信任 ledger。**
