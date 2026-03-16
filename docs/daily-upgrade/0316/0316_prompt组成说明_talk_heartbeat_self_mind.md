# 0316 Prompt 组成说明：Talk / Heartbeat / Self-Mind

## 1. 这轮调整后的总原则

这轮 prompt 治理参考了 `工作区/学习项目/research-claw` 的 bootstrap 思路，核心不是继续给主 prompt 叠规则，而是把 prompt 拆成几层：

1. 稳定层
   - 人格、角色、长期边界、固定协议。
   - 这类内容应尽量稳定，来自少数真源文件。
2. 动态层
   - 当前输入、少量相关 recent、命中的长期记忆、任务上下文。
   - 只在当前轮真的相关时加载。
3. 能力层
   - skills、sub-agent、team、公用能力目录。
   - 只在用户明确提到，或当前任务确实需要时加载。

这次的明确收敛点：

1. `talk` 不再默认把 `request_intake + skills 目录 + agent capabilities + self_mind 上下文` 一起塞进主 prompt。
2. `talk` 不再在 prompt 中重复注入 `当前输入` / `原始输入` / `用户消息` 三份同义内容。
3. `heartbeat planner` 改成模板真源优先，不再因为模板里没写某个块，就自动把一堆能力目录补进去。

---

## 2. Talk Prompt 组成

### 2.1 入口链路

主入口在：

- `butler_main/butler_bot_code/butler_bot/butler_bot.py`

执行顺序：

1. 先处理运行时控制指令。
2. 再处理显式 heartbeat 任务命令。
3. 若命中 `self-mind:` / `@self-mind:` 这类前缀，则改走 self_mind 独立聊天链，不走主 talk。
4. 普通消息进入主 talk。

### 2.2 recent 处理

recent 由这里注入：

- `butler_main/butler_bot_code/butler_bot/memory_manager.py`
- 方法：`prepare_user_prompt_with_recent()`

当前规则：

1. 普通执行类消息：
   - 仍会注入 `recent_memory`、recent summary、显式约束、续接提示。
2. 素材分享 / 链接转发类消息：
   - `RequestIntakeService.classify()` 识别为 `content_share`。
   - 这类消息改走轻量模式，不再默认注入整段 `recent_memory` 和那套“默认续接协议”。

对应入口：

- `butler_main/butler_bot_code/butler_bot/services/request_intake_service.py`
- `butler_main/butler_bot_code/butler_bot/butler_bot.py`

### 2.3 主 prompt 组装

主组装函数在：

- `butler_main/butler_bot_code/butler_bot/agent.py`
- 方法：`build_feishu_agent_prompt()`

当前由 5 层组成。

#### A. 角色入口层

固定写入：

1. `你正在以 feishu-workstation-agent 的身份回复飞书用户。`
2. `【角色设置】@./butler_main/butler_bot_agent/agents/feishu-workstation-agent.md`
3. `【当前场景】mode=...`
4. `【基础行为】...`

这里的 `mode` 由 `_classify_prompt_mode()` 决定，当前有：

1. `companion`
2. `content_share`
3. `execution`
4. `maintenance`

#### B. 对话上下文层

由 `PromptAssemblyService.assemble_dialogue_prompt()` 负责，文件：

- `butler_main/butler_bot_code/butler_bot/services/prompt_assembly_service.py`

当前会按需拼这些块：

1. `你是 Butler...` 基础角色块
2. `【灵魂摘录】`
3. `【当前用户画像】`
4. `【长期记忆命中】`
5. `【self_mind 当前上下文】`
6. `【self_mind 认知体系】`

这轮已移除：

1. `【当前输入】`
2. `【原始用户输入】`

原因是主 prompt 末尾本来就有 `【用户消息】`，重复注入会放大“解释流程、复述任务、套规则”的倾向。

#### C. 协议层

按模式条件性注入：

1. `maintenance`：
   - `update-agent` 维护入口
   - `self_update` 协议
2. `execution / maintenance`：
   - `task_collaboration` 协议
3. `companion / maintenance / 明确提到 self_mind`：
   - `self_mind_collaboration` 协议

真源来自：

- `butler_main/butler_bot_code/butler_bot/standards/protocol_registry.py`

#### D. 能力层

这轮改成按需加载，不再默认全开。

1. Skills 目录
   - 仅在用户文本明确出现 `skill / 技能 / mcp / 调用 / 抓取 / ocr / 检索` 这类信号时注入。
2. Sub-agent / Team 目录
   - 仅在用户文本明确出现 `sub-agent / team / 并行 / 分工 / 协作` 这类信号时注入。
3. `content_share` 默认不再带这两层。

#### E. 输出约束层

主 talk 结尾固定保留：

1. `【回复要求】`
2. `【decide】`
3. `【用户消息】`

当前约束已经简化为四个核心点：

1. 用 Markdown，长内容先结论后展开。
2. 不要汇报自己“读了什么、准备调用什么”。
3. 只有真的执行过某个工具 / skill / sub-agent / team，才允许提它。
4. 除非用户明确要命令或步骤，否则不要把本机操作甩给用户。

### 2.4 当前默认不会再注入的内容

对于普通主 talk：

1. 不再因为“有灵魂”就顺手注入 `self_mind` 上下文。
2. 不再因为“可能要执行”就顺手注入 skills 全目录。
3. 不再因为“可能要协作”就顺手注入 sub-agent / team 全目录。
4. 短消息和素材分享，默认不再带 `前台分诊` 大段说明。

---

## 3. Heartbeat Prompt 组成

Heartbeat 分两层：

1. planner prompt
2. executor / branch prompt

### 3.1 Heartbeat Planner Prompt

入口文件：

- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`
- 方法：`build_planning_context()`
- 方法：`build_planning_prompt()`

模板真源：

- `butler_main/butler_bot_agent/agents/heartbeat-planner-prompt.md`

#### A. Planner 动态上下文

`build_planning_context()` 当前会准备这些数据：

1. `tasks_md_text`
   - 来自 `heartbeat_tasks.md`
2. `recent_text`
   - unified heartbeat recent
3. `context_text`
   - 运行时额外上下文
4. `local_memory_text`
   - heartbeat 查询命中的长期记忆 + baseline
5. `soul_text`
   - Butler soul 摘录
6. `role_text`
   - heartbeat planner role 摘录
7. `task_workspace_text`
   - 当前任务工作区视图
8. `skills_text`
9. `subagents_text`
10. `teams_text`
11. `public_library_text`

#### B. Planner 模板填充原则

这轮之前的问题：

1. 如果模板里没写某个占位符，代码会自动补 `skills / teams / public library / maintenance` 等整块。
2. 这使得 planner prompt 很容易越补越厚，模板不再是真源。

这轮之后的原则：

1. 模板文件优先。
2. 代码只补三个硬必需项：
   - `json_schema`
   - `tasks_context`
   - `context_text`
3. 其他内容如果模板没引用，就尊重模板不注入。

这点更接近 OpenClaw 的 bootstrap 方式：模板决定行为边界，代码只负责供数。

### 3.2 Heartbeat Executor / Branch Prompt

branch 执行入口：

- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`
- 方法：`run_branch()`

当前顺序如下：

1. `heartbeat-executor-workspace-hint.md`
2. `【执行角色】`
   - 对应具体 `agent_role` 的 role 摘录
3. `【流程角色】`
   - executor / test / acceptance / manager 的阶段约束
4. `【本分支指定 skill】`
   - 仅在 `requires_skill_read=true` 时注入
5. `【任务协作协议】`
6. 若 `role_name == update-agent`
   - 再加 `统一维护入口协议`
   - 再加 `自我更新协作协议`
7. `【heartbeat 执行协议】`
8. `【运行时路由】`
   - 当前 branch 的 runtime profile
9. `【heartbeat 回执约定】`
10. branch 自身的 `prompt`

所以 heartbeat executor 现在本质上是：

1. 工作区约定
2. 分支角色约束
3. 协议
4. 当前 branch 任务

而不是一个全局大杂烩 prompt。

### 3.3 Heartbeat Team / Sub-Agent

若 branch 落到 team / sub-agent：

- `butler_main/butler_bot_code/butler_bot/execution/agent_team_executor.py`

`sub-agent` prompt 由这些块组成：

1. workspace hint
2. `【子Agent角色】`
3. `【运行约束】`
4. `【调用原因】`
5. `【前序团队上下文】`
6. `【输出契约】`
7. `【本轮任务】`

这条链已经比较接近 OpenClaw 的做法：任务 prompt 明显比主对话 prompt 更窄、更契约化。

---

## 4. Self-Mind Prompt 组成

Self-mind 现在分两条独立 prompt：

1. cycle prompt
2. chat prompt

真源文件：

- `butler_main/butler_bot_code/butler_bot/services/self_mind_prompt_service.py`

### 4.1 Self-Mind Cycle Prompt

入口：

- `MemoryManager._build_self_mind_cycle_prompt()`
- `SelfMindPromptService.build_cycle_prompt()`

当前组成固定为 3 个输入块：

1. `【1. 当前上下文】`
   - `self_mind current_context`
2. `【2. 用户画像与陪伴记忆】`
   - companion memory
3. `【3. 自己最近续思】`
   - raw thoughts / trace

输出要求：

1. 只输出 JSON
2. 只能在 `talk / agent / hold` 三选一

重要的是它明确不读：

1. 主 talk recent
2. heartbeat recent

也不允许：

1. 指挥 talk-heartbeat
2. 通过旧 bridge 写回 heartbeat

### 4.2 Self-Mind Chat Prompt

入口：

- `MemoryManager._build_self_mind_chat_prompt()`
- `SelfMindPromptService.build_chat_prompt()`

当前输入块：

1. `【self_mind 当前上下文】`
2. `【用户偏好与陪伴记忆】`
3. `【self_mind 自己最近聊天】`
4. `【self_mind 自我认知】`
5. `【最近续思痕迹】`
6. `【用户对 self_mind 说的话】`

当前不读：

1. 主 talk recent
2. heartbeat recent

定位是：

1. 独立聊天
2. 陪伴
3. 解释自己观察到的机制问题
4. 但不把自己说成主执行体或第二个调度器

---

## 5. 当前三条链的差异总结

### 5.1 Talk

目标：

1. 接住用户
2. 直接回答
3. 必要时再触发执行能力

特点：

1. 最容易被历史 recent、人格、人设、技能目录污染
2. 所以现在重点是减法和按需加载

### 5.2 Heartbeat

目标：

1. 自主规划
2. 分支执行
3. 状态同步

特点：

1. planner 适合模板真源
2. executor 适合契约化任务 prompt

### 5.3 Self-Mind

目标：

1. 陪伴
2. 观察
3. 续思
4. 解释自身机制

特点：

1. 应尽量隔离主执行流
2. 读自己的上下文、陪伴记忆和聊天历史
3. 不再读取 talk / heartbeat recent

---

## 6. 后续建议

如果继续沿 OpenClaw 的方向做，下一步最值得落的不是继续加 mode，而是这三件事：

1. 给 `talk` 也建立真正的 bootstrap 真源
   - 例如把稳定层收口成固定的 `SOUL / ROLE / USER / RULES` 四个文件。
2. 把 `recent_memory` 从“直接拼进用户消息”改成“结构化 context block”
   - 不再在 `user_prompt` 字符串里混入解释性说明。
3. 给 `skills / capabilities` 做显式引用制
   - 没命中就不进 prompt，而不是先塞进去再靠模型自觉忽略。
