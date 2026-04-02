# 0317 Talk Prompt 与记忆注入现状分析：技能与硬约束治理

> 更新时间：2026-03-17 23:58
>
> 本文记录 0317 这轮对 talk 链路的两项关键治理：
> 1. skill 注入不再只靠关键词触发；
> 2. “当前对话硬约束 / 用户刚确认的规则”不再只靠 recent raw prompt 倒序拼接。

## 1. 改造前的真实问题

### 1.1 skill 经常忘

对话链路此前存在两个结构性问题：

1. `skills` 注入只在用户当前消息命中 `skill / 技能 / mcp / 调用 / 抓取 / ocr / 检索` 等关键词时才进入 prompt
2. `content_share` 模式会直接把 `skills_prompt` 清空

这会导致一种非常典型的失败场景：

1. 用户上一轮已经说过“以后技术类链接默认走 web 抓取 skill”
2. 下一轮只说“按这个继续处理”或直接丢一个链接
3. 当前消息没再显式写 skill 关键词
4. prompt 里就可能完全没有 skills shortlist
5. 最终表现成“明明已经约定过了，但这轮又没用 skill”

### 1.2 A / B 约束容易互相覆盖

此前对话 prompt 里虽然会注入：

1. `recent_memory`
2. `recent_summary`
3. `recent_summary_archive`
4. `最近显式要求与未完约束`
5. `Current_User_Profile.private.md` 摘录

但“用户这几轮刚确认过、当前必须继续沿用的规则”并没有独立真源，也没有独立 prompt block。

结果是：

1. A 规则可能落在 recent 原文里
2. B 规则可能落在 recent summary 里
3. C 偏好可能已经进了 profile
4. 模型在长 prompt 里只抓到其中一部分

这就是“说了 A 忘了 B，说了 B 忘了 A”的根因之一。

---

## 2. 当前对话 prompt 的真实注入结构

截至 2026-03-17，talk 主链路如下：

### 2.1 `run_agent()` 先拼 recent

入口在：

- `butler_main/butler_bot_code/butler_bot/butler_bot.py`

当前会先调用 `MemoryManager.prepare_user_prompt_with_recent()`，拼出：

1. `recent_memory`
2. `recent_summary`
3. `recent_summary_archive`
4. `最近显式要求与未完约束`
5. `追问上下文`
6. `续接提示`

### 2.2 `build_feishu_agent_prompt()` 再拼结构化上下文

接着进入：

- `butler_main/butler_bot_code/butler_bot/agent.py`

当前会继续注入：

1. 基础角色块
2. bootstrap / talk guidance
3. `当前对话硬约束 / 最近确认规则`
4. `当前用户画像`
5. `长期记忆命中`
6. self_mind 上下文（按需）
7. skills shortlist
8. sub-agent / team catalog（按需）

这意味着 talk prompt 当前已经从“只有 recent + profile”升级成：

**recent 续接 + profile 真源 + active rules block + default skill shortlist**

---

## 3. 本轮已落地改动

### 3.1 skills 由“关键词触发”改为“默认注入精简 shortlist”

当前已改成：

1. `run_agent()` 默认都会注入一份精简 skills shortlist
2. `content_share` 模式不再把 skills 注入清空
3. skills shortlist 改为精简模式，避免把 talk prompt 撑爆
4. 若当前消息明显命中 `skill / 技能 / 调用 / 抓取 / 检索 / OCR / MCP` 语义，会额外加一层“本轮强提醒”

强提醒的硬规则是：

1. 不能只口头说会用
2. 必须先匹配 skill
3. 必须读取对应 `SKILL.md`
4. 回复里必须明确说出使用了哪个 skill 和路径
5. 若没命中，也必须明确说没找到

### 3.2 增加“当前对话硬约束”独立注入块

当前已新增：

1. `Current_User_Profile.private.md` 中的 `## 当前对话硬约束` section
2. talk prompt 单独注入 `【当前对话硬约束 / 最近确认规则】`
3. 这块不再和整个用户画像正文混在一起

这意味着以后像：

1. “以后技术类链接默认走 web 抓取 skill”
2. “默认输出更简洁版本”
3. “后续都先给计划再执行”

这类规则会有一个更稳定的独立落点，而不是只在 recent 里漂。

### 3.3 post-turn memory agent 开始负责提取这类规则

当前已把规则提取接到 post-turn memory agent：

1. 规则仍写入 `Current_User_Profile.private.md`
2. 不新造第二套 profile 真源
3. 触发条件优先看用户消息中是否出现高信号规则词，例如：
   - 以后
   - 默认
   - 约定
   - 规则
   - 记住
   - 都走 / 都用
   - 统一 / 一律
   - 后续
4. 提取结果落到 `## 当前对话硬约束`

当前先采用的是保守 heuristic，而不是高风险的“自动重写整份 profile”。

---

## 4. 这轮设计选择

### 4.1 为什么把“当前对话硬约束”放进用户画像

原因有三个：

1. 现有系统里用户画像本来就是 talk 默认注入真源
2. 现有 memory pipeline 已经支持 profile writer，不需要另造绕过治理的散写入口
3. 这类规则本质上是“当前这位用户最近确认过、需要连续沿用的协作规则”，比纯 recent 更稳定，但又还没到写 Soul 的层级

所以这次没有新增独立文件，而是选择：

**仍以 `Current_User_Profile.private.md` 为真源，但把该类规则拆成单独 section。**

### 4.2 为什么先做 heuristic，而不是直接让模型自由写 profile

因为这一步的目标是先止住“忘规则、忘 skill”，不是先把 profile 写作做复杂。

当前更优先的是：

1. 先让高信号规则有稳定落点
2. 先让这块默认进入 talk prompt
3. 先避免“本轮刚说过，下轮就忘”

后面如果要继续升级，可以再把 profile section 的重写、去重、时效治理做成更强的 governed rewrite。

---

## 5. 当前仍存在的边界

这轮不是终局，当前还留着几处边界：

1. “当前对话硬约束”现在还是 heuristic 提取，不是模型审校后的结构化重写
2. 规则 dedupe 目前主要靠文本包含判断，语义近似去重还不够强
3. skills 目前是默认精简 shortlist，不是“按用户请求自动命中最相关 skill 并强制读取”
4. profile 里“长期稳定偏好”和“当前阶段性规则”虽然已经分 section，但还没做自动老化和降级

---

## 6. 本轮验证

本轮已通过的直接相关测试：

1. `test_agent_soul_prompt.py`
2. `test_memory_pipeline.py`

共 15 个测试通过。

重点覆盖了：

1. content_share 场景也会注入 skills
2. 非 skill 明示场景也会注入默认 shortlist
3. 命中 skill 语义时会出现强提醒
4. `当前对话硬约束` section 会进入 talk prompt
5. post-turn memory agent 会把显式规则写入 profile

---

## 7. 当前结论

0317 这一步完成后，talk 链路在“记住规则”和“别忘 skill”两个问题上已经比之前更稳：

1. skill shortlist 默认在场，不再只靠当前消息关键词触发
2. content_share 不再天然失去 skills
3. 用户刚确认的规则开始有 profile 真源和独立 prompt block
4. 对话 prompt 已具备 recent + active rules + profile + skill shortlist 的更清晰结构

下一步若继续修 talk 质量，最值得继续做的是：

1. 把 `当前对话硬约束` 做成带时效/优先级/失效条件的 governed section
2. 把“skills shortlist 默认注入”升级成“按当前请求自动命中最相关 skill 并要求读 `SKILL.md`”
3. 把 recent requirement / profile rules / local memory hits 做一次统一去重与优先级排序
