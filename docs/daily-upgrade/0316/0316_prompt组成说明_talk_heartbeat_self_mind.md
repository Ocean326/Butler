# 当前 Prompt 注入限制说明（Talk / Heartbeat / Self-Mind）

## 1. 目的

这份文档描述 **当前代码真实生效** 的 prompt 注入规则，而不是历史设计稿。

关注点只有三类：

1. 哪些内容会被注入
2. 在什么条件下会被注入或跳过
3. 现在仍有哪些限制会影响效果

主要实现位置：

- `butler_main/butler_bot_code/butler_bot/butler_bot.py`
- `butler_main/butler_bot_code/butler_bot/agent.py`
- `butler_main/butler_bot_code/butler_bot/memory_manager.py`
- `butler_main/butler_bot_code/butler_bot/services/prompt_assembly_service.py`
- `butler_main/butler_bot_code/butler_bot/services/self_mind_prompt_service.py`
- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`
- `butler_main/butler_bot_code/butler_bot/services/bootstrap_loader_service.py`

---

## 2. 总体原则

当前 Butler 的 prompt 由 4 层组成：

1. bootstrap 层
   - 来自 `bootstrap/` 目录的稳定真源
2. 角色/协议层
   - 来自 role 文档和 protocol registry
3. 动态上下文层
   - recent、local memory、self_mind、任务上下文等
4. 能力层
   - skills、sub-agent、team、公用能力目录

当前限制的核心思路是：

1. bootstrap 默认加载，但有字数截断
2. 动态上下文按链路分别装载，不再所有链路共用一锅炖
3. 能力层按条件注入，不默认全开
4. Talk 仍然是限制最多、最容易被裁剪的一条链

---

## 3. Bootstrap 装载限制

由 `BootstrapLoaderService.load_for_session()` 决定。

### 3.1 Talk

Talk 会装载：

1. `SOUL.md`
2. `TALK.md`
3. `USER.md`
4. `TOOLS.md`
5. `MEMORY_POLICY.md`

### 3.2 Heartbeat Planner

Heartbeat planner 会装载：

1. `HEARTBEAT.md`
2. `TOOLS.md`
3. `MEMORY_POLICY.md`

### 3.3 Heartbeat Executor

Heartbeat executor 会装载：

1. `EXECUTOR.md`
2. `TOOLS.md`
3. `MEMORY_POLICY.md`

### 3.4 Self-Mind

`self_mind_cycle` 和 `self_mind_chat` 会装载：

1. `SOUL.md`
2. `SELF_MIND.md`
3. `USER.md`
4. `MEMORY_POLICY.md`

### 3.5 当前限制

1. bootstrap 不是全文注入，而是 excerpt；默认有 `max_chars` 截断
2. 不同 session type 只能读自己那组 bootstrap，不会跨会话自动补全
3. 如果 bootstrap 文件存在重复规则，当前代码不会去重，只是照读

---

## 4. Talk Prompt 注入限制

Talk 主入口：`butler_bot.py`

普通消息链路顺序：

1. `begin_pending_turn()`
2. `prepare_user_prompt_with_recent()`
3. `build_feishu_agent_prompt()`
4. 调模型
5. `on_reply_sent_async()` 回写 recent/local memory

### 4.1 recent 注入

由 `MemoryManager.prepare_user_prompt_with_recent()` 决定。

当前会尝试注入：

1. `recent_memory`
2. `recent_summary`
3. `recent_summary_archive`
4. `最近显式要求与未完约束`
5. `pending followup`
6. `continuation hint`

当前已经生效的变化：

1. 不再因为“全新任务/全新情景”直接跳过 recent 注入
2. 不再因为 `content_share` 直接跳过 recent 注入
3. 现在的默认规则是：`默认沿用 recent_memory 做上下文续接`

当前仍存在的限制：

1. 如果 `recent_text + summary_text + summary_history_text` 都为空，就不会造一个空的 recent block
2. recent 仍是“直接拼进用户消息前面”的文本拼接，不是独立结构化对象
3. recent 是否足够强，仍受 recent 提炼质量影响

### 4.2 prompt mode 分类限制

由 `agent.py::_classify_prompt_mode()` 决定，当前只有四类：

1. `maintenance`
2. `content_share`
3. `companion`
4. `execution`

判定顺序有硬优先级：

1. 先看 maintenance 关键词
2. 再看 content_share
3. 再看 companion
4. 否则 execution

这意味着：

1. 一条消息只会进一个 mode
2. 若同时包含“维护信号”和“分享链接”，优先命中 maintenance
3. `content_share` 不是用户显式声明，而是按启发式规则判定

### 4.3 Talk 上下文层注入限制

由 `build_feishu_agent_prompt()` + `PromptAssemblyService.assemble_dialogue_prompt()` 决定。

固定会进入的块：

1. `feishu-workstation-agent` 角色入口
2. `Bootstrap/TALK` 等 talk bootstrap
3. `基础行为`
4. `dialogue_prompt`
5. `回复要求`
6. `decide`
7. `用户消息`

#### 4.3.1 Soul 注入限制

由 `_should_inject_butler_soul()` 决定。

会注入 soul 的情况：

1. `prompt_mode` 是 `companion`
2. `prompt_mode` 是 `maintenance`
3. 用户消息长度 >= 160
4. 用户消息命中 `_SOUL_TRIGGER_KEYWORDS`

不会注入 soul 的情况：

1. 短执行消息
2. 短分享消息，且未命中 soul 关键词

这意味着：

1. 不是每轮对话都看得到 soul
2. 简短的执行/分享消息，经常拿不到 soul 层

#### 4.3.2 用户画像注入限制

当前会读取用户画像 excerpt，并放进 `【当前用户画像】`。

限制：

1. 只读 private 文件或 template 的 excerpt
2. 有字符截断
3. 不是命中式检索，而是固定 excerpt

#### 4.3.3 local memory 注入限制

由 `PromptAssemblyService.render_local_memory_hits()` 决定。

特点：

1. 不是整库注入，只注入 query 命中片段
2. `limit` 默认最多 4 条
3. `max_chars` 在 talk 中较小
4. `memory_types` 会按 mode 收窄

当前限制：

1. `content_share` 和 `companion` 只查 `personal`
2. `execution` 才会带上 `task`
3. 命中依赖 query_text，本轮表述偏、缩写多、没提关键词时，可能查不到

#### 4.3.4 self_mind 上下文注入限制

只有满足下列条件才会注入 self_mind：

1. `prompt_mode` 是 `companion`
2. `prompt_mode` 是 `maintenance`
3. 用户文本明确提到 `self_mind / self-mind / 小我 / 内心`

当前限制：

1. 普通 execution 不带 self_mind
2. 普通 content_share 也不带 self_mind
3. self_mind 注入的是 excerpt，不是完整状态

### 4.4 Request Intake 注入限制

由 `_should_include_request_intake_block()` 决定。

会注入的情况：

1. `maintenance`
2. 文本长度 >= 180

不会注入的情况：

1. 多数短消息
2. 多数短分享消息

这意味着：

1. 前台分诊说明现在不会在每轮都出现
2. 短消息更轻，但也更少显式约束

### 4.5 Skills 注入限制

有两层限制：

1. `butler_bot.py` 先决定是否把 `skills_prompt` 传进 `build_feishu_agent_prompt()`
2. `agent.py::_should_include_skills_catalog()` 再决定是否真正拼进去

当前第一层限制：

- `skills_prompt = "" if recent_mode == "content_share" else _render_available_skills_prompt(workspace)`

也就是说：

1. 只要 `RequestIntakeService.classify()` 把这轮认成 `content_share`
2. 当前轮 `skills_prompt` 会在入口被直接清空
3. 后面的 `_should_include_skills_catalog()` 即使想放，也没东西可放

当前第二层限制：

即使不是 `content_share`，也只有文本命中这些词才会真的注入 skills：

1. `skill`
2. `技能`
3. `mcp`
4. `调用`
5. `抓取`
6. `ocr`
7. `检索`

当前影响：

1. 这正是“小红书分享场景效果不稳”的关键限制之一
2. recent 里虽然可能写着“应该走 web-note-capture-cn + web-image-ocr-cn”
3. 但当轮如果被判成 `content_share`，技能目录本身仍可能拿不到

### 4.6 Agent Capabilities 注入限制

也有两层限制。

当前第一层限制：

- `capabilities_prompt = "" if recent_mode == "content_share" else _render_available_agent_capabilities_prompt(workspace)`

因此：

1. `content_share` 默认直接失去 sub-agent / team 能力目录

当前第二层限制：

即使不是 `content_share`，还要满足：

1. `prompt_mode` 必须属于 `execution` 或 `maintenance`
2. 文本命中以下关键词之一：
   - `sub-agent`
   - `subagent`
   - `agent team`
   - `team`
   - `并行`
   - `分工`
   - `协作`

当前影响：

1. companion 和 content_share 默认看不到 agent capability 目录
2. execution 里如果用户没写这些词，也不会注入

### 4.7 协议层注入限制

#### task_collaboration

只在以下 mode 注入：

1. `execution`
2. `maintenance`

#### self_mind_collaboration

只在以下情况注入：

1. `companion`
2. `maintenance`
3. 已注入 soul 且用户明确提到 `self_mind / self-mind / 小我 / 内心`

#### self_update

只在 `maintenance` 注入。

当前影响：

1. 普通分享消息通常拿不到 task 协议和 self_update 协议
2. 短执行消息如果没到 maintenance，也不会被强制拉进维护协议

---

## 5. Heartbeat Prompt 注入限制

### 5.1 Planner

由 `HeartbeatOrchestrator.build_planning_prompt()` 构造。

Planner 动态上下文会准备：

1. `tasks_context`
2. `recent_text`
3. `context_text`
4. `local_memory_text`
5. `soul_text`
6. `role_text`
7. `task_workspace_text`
8. `skills_text`
9. `subagents_text`
10. `teams_text`
11. `public_library_text`
12. `maintenance_entry_text`

当前限制：

1. planner 侧是“先供数，再看模板占位符是否引用”
2. `assemble_planner_prompt()` 只做字符串替换，不做智能裁剪
3. 如果模板没引用某块，就算上下文准备了，也不会进最终 prompt
4. 代码仍会兜底补两个块：
   - `tasks_context`
   - `context_text`
5. bootstrap 也仍然是 excerpt，不是完整文件

### 5.2 Executor / Branch

Heartbeat branch prompt 不是全量大 prompt，而是按 branch 契约拼。

当前固定链路：

1. workspace hint
2. 执行角色/流程角色
3. 协议块
4. 运行时路由
5. branch 自身 prompt

skill 注入限制：

1. 只有 branch JSON 里 `requires_skill_read=true` 才会带 `【本分支指定 skill】`
2. 默认很多 branch 都是 `false`
3. 即使 skill 已登记，也不会自动全目录注入

当前影响：

1. Heartbeat executor 的能力曝光更严格
2. planner 如果没把 `requires_skill_read` 规划出来，executor 不会自己补读 skill

---

## 6. Self-Mind Prompt 注入限制

### 6.1 self_mind_cycle

由 `SelfMindPromptService.build_cycle_prompt()` 生成。

固定只有 3 个输入块：

1. `当前上下文`
2. `用户画像与陪伴记忆`
3. `自己最近续思`

当前限制：

1. 不读主 talk recent
2. 不读 heartbeat recent
3. 不读 skills / sub-agent / team 目录
4. 输出被限制为 JSON schema，且 `decision` 只能是 `talk|agent|hold`

### 6.2 self_mind_chat

由 `SelfMindPromptService.build_chat_prompt()` 生成。

固定输入块：

1. `self_mind 当前上下文`
2. `用户偏好与陪伴记忆`
3. `self_mind 自己最近聊天`
4. `self_mind 自我认知`
5. `最近续思痕迹`
6. `用户对 self_mind 说的话`

当前限制：

1. 不读主 talk recent
2. 不读 heartbeat recent
3. 不读 talk 的 skills/capabilities
4. 定位是陪伴型独立聊天，不是第二个主执行器

---

## 7. 当前最关键的限制汇总

### 7.1 已经放开的限制

1. Talk 现在默认注入 recent，不再因为“新任务”跳过
2. Talk 现在默认注入 recent，不再因为 `content_share` 跳过

### 7.2 仍然最影响效果的限制

1. `content_share` 仍会在入口清空 `skills_prompt`
2. `content_share` 仍会在入口清空 `agent_capabilities_prompt`
3. skills/capabilities 还有第二层关键词门槛
4. local memory 是命中式检索，不保证每轮都召回到关键长期约束
5. recent 仍是文本拼接，不是结构化上下文对象
6. self_mind 与主 talk / heartbeat 是隔离的，不能指望它替主链补行为约束

### 7.3 对“小红书分享 + skill解析 + 计入头脑风暴”场景的直接影响

当前真实情况是：

1. 这类消息现在能拿到 recent
2. recent 里也可能已经写了“应走 web-note-capture-cn / web-image-ocr-cn / BrainStorm”
3. 但如果这轮被判成 `content_share`，skills 和 capability 目录仍可能直接缺席
4. 所以模型更容易回成“理解内容、总结内容、承诺后续”，而不是稳定进入执行链

---

## 8. 建议作为后续修正入口的点

如果后续还要继续收口，优先级建议如下：

1. 先处理 `content_share` 对 `skills_prompt` / `agent_capabilities_prompt` 的硬清空
2. 再决定是否要把“网页分享 + 抓取/OCR/BrainStorm”做成更强的 execution-like 模式
3. 最后再考虑把 recent 从文本拼接升级为结构化 context block

这样改动最小，但能直接改善当前最明显的行为落差。
