# Butler Prompt 治理与重构建议（交付 Codex 实现稿）

> 版本：2026-03-18 v2  
> 用途：交给本地 Codex / 本地工程实现者，作为 prompt / context architecture 改造的参考文档  
> 目标：把 Butler 从“长 prompt + 胖 schema + 少量原文回放”的形态，升级为“分层注入 + 状态投影 + skills 按需加载 + 受控原文引用”的 agent harness

---

## 0. 这份文档解决什么问题

这份文档回答 6 个工程问题：

1. Butler 当前 prompt 的真实问题是什么；
2. 应该向哪些成熟范式对齐；
3. 原文是否重要，是否应该固定注入最近几轮原文；
4. 模型回答要不要进入 memory / prompt；
5. “承诺 / 假设 / 计划 / 未完成动作”这类状态应该如何分类、由谁分类；
6. Butler 应该按什么顺序落地改造，避免再次回到 `memory_manager.py` 一锅炖。

---

## 1. 对当前现状的判断

结合你现有文档，当前系统的关键事实不是“prompt 已经被大量原文淹没”，而是：

- talk prompt 仍然以 `summary` 注入为主，少量原文回放主要来自 `raw_user_prompt`；
- heartbeat prompt 的主输入不是 `heart_beat_memory.json` 全量，而是 `heartbeat_tasks.md + 统一 recent + local_memory + runtime`；
- `recent_memory` 的 schema 偏胖，但长期稳定发挥作用的字段主要仍是 `topic + summary`；
- 当前最高优先级风险是：`raw_user_prompt` 会把敏感原文重新带回 prompt。

这意味着：

**当前最该做的不是把总 prompt 写得更长，而是重构“上下文注入架构”。**

也就是从：

```text
存储 schema -> 直接拼 prompt
```

改成：

```text
原始事件 / 存储层 -> 状态抽取 -> 归一化 -> prompt 投影视图 -> prompt
```

---

## 2. 该向哪些成熟范式对齐

### 2.1 Codex：分层指令 + skills 按需调用

可借鉴点：

- 使用 `AGENTS.md` 作为分层项目指令；
- 把可复用工作流拆成 skills，而不是不断往主 prompt 里塞长说明；
- 项目规则是“常驻骨架”，skill 说明是“按需加载”；
- 重点不是更多原文，而是更稳定的 instruction contract。

适配到 Butler：

- Butler 也应保留一个短而稳的 core contract；
- 把 memory compaction、heartbeat planning、sensitive redaction、code review 等拆成 skills；
- talk / heartbeat 每轮只注入当前需要的状态视图，而不是所有历史说明。

### 2.2 Cursor：持久规则层 + 规则优先级

可借鉴点：

- 长期稳定规范和当前任务状态应分层；
- 并非所有规则都应每轮全量注入；
- 需要区分 always-on 的项目规则与按相关性引入的局部规则。

适配到 Butler：

- “项目长期行为规范”与“用户当前会话状态”不要混写；
- 常驻层只放稳定行为，不放近期状态和历史片段；
- 局部策略应由 PromptProjection 决定是否进入本轮上下文。

### 2.3 OpenClaw：固定 system 骨架 + bootstrap 文件 + skills 元数据常驻

可借鉴点：

- system prompt 保持 section 化、紧凑；
- bootstrap 文件即使注入，也要注意 token 预算；
- skills 列表可以常驻，但正文不要默认全带；
- 真正需要 skill 时再读 `SKILL.md`。

适配到 Butler：

- prompt 应固定成若干 section，而不是自然生长的大段文字；
- skills 正文不要常驻；
- 只保留 compact skill index + 按需读取机制。

### 2.4 GPT-5.4 风格：明确 output contract / tool rules / completion criteria

可借鉴点：

- 长任务 prompt 在 block-structured 结构下更稳定；
- 明确 tool-use expectations、verification loop、completion criteria；
- modular prompt 比一段自然语言大散文更可靠。

适配到 Butler：

- talk prompt 和 heartbeat prompt 都应做成固定骨架；
- 动态变化的仅是 `{talk_context_view}` / `{heartbeat_state_view}`；
- 不再让“最近几轮上下文堆砌”承担全部控制职责。

---

## 3. 核心判断：原文重要吗？

### 3.1 结论

**原文重要，但不应该固定注入最近几轮完整原文。**

更专业的做法是：

- 默认注入“状态化摘要 / 约束投影”；
- 原文只在必要时按需引入；
- 原文进入 prompt 前必须先经过脱敏、裁剪、用途判断。

### 3.2 为什么不能默认塞最近几轮原文

固定塞最近几轮原文，会带来 4 个问题：

1. token 占用不可控；
2. 用户原文里可能含敏感内容、无关噪音、重复表达；
3. 原文在模型眼里权重往往过高，容易覆盖结构化状态；
4. long context 下，模型更需要“任务态投影”，而不是“聊天记录堆”。

### 3.3 什么情况下需要按需引入原文

只有满足以下之一时，才应引入原文摘录：

- **wording-sensitive**：用户措辞本身很关键，例如写作、润色、法律/合规措辞；
- **evidence-sensitive**：需要引用用户明确说过的话作为证据；
- **disambiguation-sensitive**：摘要不足以区分两个近似意图；
- **quote-required**：用户明确要求“按我原话”“保留原句”；
- **debugging-sensitive**：需要复盘模型为什么误解了用户原文。

### 3.4 原文引入规则

建议统一成以下门槛：

```text
默认：不引入完整原文
例外：只引入短摘录，不引入整轮 transcript
前置：先脱敏，再裁剪，再标注用途
限制：最多 1~2 段，每段不超过固定 token 上限
```

建议字段：

```json
{
  "quoted_excerpt": {
    "source": "user",
    "reason": "wording_sensitive",
    "excerpt": "...",
    "is_redacted": true
  }
}
```

---

## 4. 模型回答要不要包含？

### 4.1 结论

**不建议把模型回答原文作为默认注入内容。**

更好的做法是：

- 不保留 assistant 长篇原文作为常驻上下文；
- 只抽取 assistant 输出中的“状态性成果”；
- 让未来轮次看到的是“我已经承诺了什么 / 假设了什么 / 计划到哪一步 / 还欠什么动作”，而不是一大段上次回复全文。

### 4.2 assistant 原文默认不进 prompt 的原因

模型回答往往包含：

- 礼貌话术；
- 冗长解释；
- 风格性表述；
- 局部推理过程；
- 临时组织语言。

这些内容大多不适合做长期状态。

### 4.3 assistant 应该被抽取成什么

保留以下类型：

- **commitment 承诺**：我会做什么；
- **assumption 假设**：我暂时按什么前提推进；
- **plan 计划**：我准备如何推进；
- **decision 决策**：已经选定的处理策略；
- **pending_action 未完成动作**：我还欠用户的下一步；
- **open_question 未决问题**：还有什么没有澄清；
- **handoff_state 交接状态**：哪些信息需要交给 heartbeat / task system。

不建议默认保留：

- 整段回答原文；
- 大段解释；
- 临时推理链；
- 风格性输出。

---

## 5. 不要只按字段分类，要按“五层语义”分类

“承诺 / 假设 / 计划 / 未完成动作”不能只看字段名，应该按以下五层分类：

1. **来源 source**：user / assistant / tool / runtime / planner；
2. **语义类型 semantic_type**：constraint / commitment / assumption / plan / task / decision / note；
3. **生命周期 lifecycle**：ephemeral / session / active_until_done / long_term；
4. **真源 owner**：谁负责维护这个状态；
5. **prompt 可见性 visibility**：默认可见、条件可见、默认不可见。

### 5.1 推荐统一 schema

```json
{
  "id": "state_xxx",
  "source": "assistant",
  "semantic_type": "commitment",
  "status": "active",
  "scope": "session",
  "owner": "assistant_state",
  "visibility": "conditional",
  "confidence": 0.88,
  "relevance": 0.91,
  "created_at": "2026-03-18T10:32:00Z",
  "expires_at": null,
  "summary": "Assistant committed to produce a refactor design doc for prompt governance.",
  "details": {
    "next_action": "Generate implementation-oriented design doc",
    "blocked_by": null
  },
  "provenance": {
    "turn_id": "...",
    "message_role": "assistant"
  }
}
```

---

## 6. 这几类状态怎么定义

### 6.1 commitment（承诺）

定义：主体已经明确表示“会去做”的动作。

常见来源：assistant、偶尔 user。  
典型触发词：

- 我会……
- 接下来我去……
- 我将……
- 我会先……再……

特点：

- 应进入短期状态；
- 如果承诺影响后续执行，应进入 heartbeat / task ledger；
- 完成后应关闭，不长期常驻。

### 6.2 assumption（假设）

定义：为了推进任务临时采用、但尚未验证的前提。

特点：

- 默认短生命周期；
- 一旦被验证，应升级为 decision / fact；
- 一旦被推翻，应立即清除或标记失效；
- 不应长期驻留在 memory 主窗口。

### 6.3 plan（计划）

定义：多步推进路线，不等于每一步都已经承诺。

特点：

- 适合 session 级或 active-until-done 生命周期；
- 计划中的步骤可以拆解成多个 pending actions；
- 计划本身可见，但过细的执行说明不必常驻。

### 6.4 pending_action / task（未完成动作）

定义：已经提出、安排或承诺，但还没有关闭的动作。

特点：

- 最适合作为 heartbeat / task ledger 的真源；
- talk prompt 只应看到少量与当前轮最相关的未完成动作；
- 不建议让 recent summary 承担 task 真源职责。

### 6.5 decision（决策）

定义：已经确认并应稳定延续的结论或默认策略。

例子：

- 默认不回放 `raw_user_prompt` 原文；
- talk 侧优先注入 summary projection；
- heartbeat 以 task ledger 为真源。

特点：

- 可进入 project rules / persistent state；
- 生命周期比 assumption / plan 更长；
- 需要明确 owner 和版本。

---

## 7. 由谁分类？不要让一个模块全包

建议拆成四层职责：

### 7.1 Extractor：抽候选项

职责：

- 从 user / assistant / tool / runtime 事件中抽取候选状态；
- 规则优先，模型辅助；
- 高置信信号先用规则抓，不要全靠 LLM 再理解一遍。

建议优先抽的触发模式：

- 用户显式要求 / 禁止 / 偏好；
- assistant 明确承诺；
- assistant 明确假设；
- assistant 给出多步计划；
- heartbeat 产生 blocked / waiting_input / deferred；
- tool 返回了影响后续动作的关键结果。

### 7.2 Normalizer：归一化

职责：

- 把候选项统一映射到标准 schema；
- 做去重、归并、置信度设置；
- 做脱敏、长度裁剪、字段白名单处理；
- 明确生命周期、scope、visibility。

### 7.3 Owner / Source of Truth：维护真源

不要所有状态都进一个大 JSON。

建议 owner 分层：

- **user_state**：用户长期偏好、硬约束、当前目标；
- **assistant_state**：助手承诺、假设、计划、未完成交付；
- **task_ledger**：活跃任务、待办、阻塞、等待输入；
- **decision_store**：已经确认并长期有效的系统/项目决策；
- **archive**：历史原文和低频检索材料。

### 7.4 PromptProjection：决定这轮要不要带入 prompt

这一层最关键。

正确分类 ≠ 本轮一定注入。

PromptProjection 负责：

- 当前是 talk 还是 heartbeat；
- 当前用户问题是什么；
- 哪些状态与当前问题强相关；
- 当前 token 预算剩余多少；
- 是否需要原文摘录；
- 是否应该只带摘要而不带细节。

---

## 8. 一个推荐的模块拆分

建议不要继续把所有逻辑堆回 `memory_manager.py`。  
推荐最小模块化拆分：

```text
butler_bot/
  prompting/
    core_contracts.py
    prompt_projection.py
    prompt_budget.py
  state/
    extraction.py
    normalization.py
    schemas.py
    conflict_resolution.py
  memory/
    user_state_store.py
    assistant_state_store.py
    decision_store.py
    archive_store.py
  tasks/
    task_ledger.py
    task_projection.py
  skills/
    sensitive_redaction/
      SKILL.md
    heartbeat_planning/
      SKILL.md
    memory_compaction/
      SKILL.md
    code_review/
      SKILL.md
```

### 8.1 关键接口草案

```python
class StateExtractor:
    def extract_from_message(self, role: str, text: str, metadata: dict) -> list[dict]:
        ...

class StateNormalizer:
    def normalize(self, candidates: list[dict]) -> list[dict]:
        ...

class StateRouter:
    def route(self, states: list[dict]) -> None:
        """按 semantic_type / owner 写入不同真源"""
        ...

class PromptProjection:
    def build_talk_view(self, query: str, budget: int) -> dict:
        ...

    def build_heartbeat_view(self, runtime_state: dict, budget: int) -> dict:
        ...

    def should_include_raw_excerpt(self, query: str, state: dict) -> bool:
        ...
```

---

## 9. Prompt 不要直接吃存储 schema，要吃“投影视图”

### 9.1 talk prompt 视图

建议固定只暴露这些：

```json
{
  "active_user_goal": "...",
  "hard_constraints": ["..."],
  "soft_preferences": ["..."],
  "relevant_recent_summaries": [
    {
      "time": "...",
      "topic": "...",
      "summary": "...",
      "status": "..."
    }
  ],
  "assistant_open_commitments": ["..."],
  "top_pending_actions": ["..."],
  "quoted_excerpt": []
}
```

### 9.2 heartbeat prompt 视图

建议固定只暴露这些：

```json
{
  "active_goals": ["..."],
  "ready_tasks": ["..."],
  "blocked_tasks": ["..."],
  "waiting_user_input": ["..."],
  "due_soon": ["..."],
  "recent_execution_signals": ["..."],
  "risk_flags": ["..."],
  "candidate_skills": ["..."]
}
```

### 9.3 Prompt 可见字段白名单

必须显式白名单，不允许存储字段自动漏进 prompt。

```python
TALK_PROMPT_VISIBLE_FIELDS = {
    "recent_summary": ["timestamp", "topic", "summary", "status"],
    "constraint_projection": ["goal", "hard_constraints", "next_action"],
    "assistant_state": ["summary", "status", "next_action"],
}

HEARTBEAT_PROMPT_VISIBLE_FIELDS = {
    "task": ["id", "title", "state", "priority", "blocked_by", "due_at"],
    "signal": ["summary", "source", "confidence"],
}
```

---

## 10. 推荐的 prompt skeleton

### 10.1 talk prompt skeleton

```xml
<role>
你是 Butler 的对话代理。目标是帮助用户推进当前任务，而不是展示你记住了多少历史。
</role>

<behavior_contract>
- 优先回答当前问题。
- 只在有助于完成当前任务时引用历史。
- 不回放敏感原文。
- 不把存储层字段当作都同等重要。
</behavior_contract>

<context_loading_policy>
- recent_summary 是默认上下文。
- active_constraints 优先于普通 recent。
- 原文 excerpt 默认禁用，除非 need_quote=true。
- 信息不足时优先检索或再确认，不靠猜测补全。
</context_loading_policy>

<tool_and_memory_policy>
- 需要历史细节时先查 memory/retrieval。
- 不直接信任旧快照，必要时二次验证。
</tool_and_memory_policy>

<output_contract>
- 先给结论或动作。
- 再给必要解释。
- 不重复 recent 内容。
</output_contract>

<completion_criteria>
- 是否回答了当前主问题
- 是否保留了仍未完成的关键约束
- 是否避免泄露敏感原文
</completion_criteria>

<dynamic_context>
{talk_context_view}
</dynamic_context>
```

### 10.2 heartbeat prompt skeleton

```xml
<role>
你是 Butler 的 heartbeat planner。职责是维护任务推进，不是复述聊天历史。
</role>

<planning_policy>
- 优先处理 ready_tasks
- blocked_tasks 先识别阻塞因子
- waiting_user_input 不要反复催同一件事
- 已完成任务只保留少量最近样本用于状态连续性
</planning_policy>

<context_policy>
- recent 仅作为计划背景，不作为任务真源
- task_state 是真源
- legacy store 仅做 bootstrap / reconciliation
</context_policy>

<action_policy>
- 每轮最多选 1 个主推进动作 + 0~2 个次动作
- 高风险动作先验证
- 外部动作前先检查是否需要用户确认
</action_policy>

<completion_criteria>
- 是否明确了 next best action
- 是否避免从 done pile 中捞无关历史
- 是否对 waiting_input / blocked / deferred 做了正确分流
</completion_criteria>

<dynamic_context>
{heartbeat_state_view}
</dynamic_context>
```

---

## 11. token 预算不要按“条数”拍脑袋，要按“槽位”管理

建议：

### 11.1 talk

```text
static_contract: 800~1200 tokens
context_view: 600~1000 tokens
active_constraints: 200~400 tokens
quoted_excerpt: 默认 0，最多 120 tokens
reserve_for_generation: >= 35%
```

### 11.2 heartbeat

```text
planner_contract: 700~1000 tokens
task_state_view: 700~1200 tokens
recent_execution_signals: 200~400 tokens
reserve_for_reasoning_and_tools: >= 40%
```

核心原则：

- 预算管理的单位是“槽位”，不是“最近 15 条 / 30 条”；
- 每个槽位都有上限；
- 任何原文摘录都占用单独预算，不得偷偷混入 recent。

---

## 12. skills 化建议

这些内容不应常驻主 prompt，建议拆成 skills：

- `sensitive_redaction`：对 raw prompt / transcript 做脱敏与裁剪；
- `memory_compaction`：整理 recent 与 archive；
- `heartbeat_planning`：从 task ledger 选下一步；
- `code_review_butler`：代码审查规范；
- `report_generation`：汇报与材料整理；
- `conversation_disambiguation`：意图拆分与上下文判别。

主 prompt 中仅放 compact index：

```xml
<available_skills>
- sensitive_redaction: 当需要从原文生成安全摘要时使用
- memory_compaction: 当 recent/archive 膨胀时使用
- heartbeat_planning: 当需要从任务态选择 next best action 时使用
- code_review_butler: 当用户要求做代码审查时使用
</available_skills>
```

---

## 13. 决策规则：这轮到底该不该带入某状态？

建议做成显式判定函数，而不是隐含在一堆 if 里。

```python
def should_project_state(query, state, mode):
    if state["status"] in {"closed", "invalidated", "expired"}:
        return False

    if mode == "talk":
        return (
            state["relevance"] >= 0.7
            and state["visibility"] != "hidden"
            and state["owner"] in {"user_state", "assistant_state", "task_ledger"}
        )

    if mode == "heartbeat":
        return state["owner"] in {"task_ledger", "assistant_state", "decision_store"}

    return False
```

### 13.1 原文摘录的显式门槛

```python
def should_include_raw_excerpt(query, state):
    return (
        state.get("requires_exact_wording", False)
        or state.get("evidence_sensitive", False)
        or state.get("quote_required", False)
    )
```

---

## 14. 推荐落地顺序

### 第一阶段：先控风险

1. 关闭 `raw_user_prompt` 默认直接回放；
2. 所有原文进入 prompt 前必须走 redaction + truncation；
3. 建 prompt-visible field 白名单；
4. 禁止存储 schema 直接漏进 prompt。

### 第二阶段：引入状态抽取层

1. 做 `StateExtractor`；
2. 做 `StateNormalizer`；
3. 把 assistant 的承诺 / 假设 / 计划 / 未完成动作抽出来；
4. 让这些状态进入独立 store，而不是埋在 recent JSON 里。

### 第三阶段：引入 PromptProjection

1. talk / heartbeat 分别构建投影视图；
2. 让 prompt 只吃视图；
3. recent 只保留摘要材料，不再承担全部语义角色。

### 第四阶段：skills 化与 eval

1. 拆出 sensitive_redaction / memory_compaction / heartbeat_planning；
2. 建立 eval：
   - 是否错误回放敏感原文；
   - 是否漏掉有效承诺；
   - 是否把过期假设继续带入；
   - heartbeat 是否能从 task ledger 正确选出 next best action。

---

## 15. 最终建议（一句话版）

Butler 现在最该做的不是“再写一版更强的总 prompt”，而是把 prompt 系统升级为：

**Core Contract + Project Rules + State Projection + Skills / Retrieval**

其中：

- **Core Contract**：短、稳、常驻；
- **Project Rules**：项目长期规范；
- **State Projection**：每轮动态生成的任务态视图；
- **Skills / Retrieval**：只在相关时读取。

而“最近几轮原文”和“模型上次大段回答”都不应成为默认主上下文。  
真正应该进入 prompt 的，是经过分类和治理的状态。

---

## 16. 给实现者的最小行动清单

先做这 8 件事：

1. 关掉 `raw_user_prompt` 默认回放；
2. 新建 `prompt_projection.py`；
3. 新建 `state/extraction.py`；
4. 新建 `state/normalization.py`；
5. 引入 `assistant_state_store`；
6. heartbeat 以 `task_ledger` 为真源；
7. 给 talk / heartbeat 各写一版固定 skeleton prompt；
8. 写 10~20 条 regression eval，重点测敏感原文、承诺延续、过期假设、任务推进。

---

## 17. 外部参考（供 Codex / 实现者延伸阅读）

- OpenAI Codex `AGENTS.md` 指南：`https://developers.openai.com/codex/guides/agents-md/`
- OpenAI Codex skills 更新：`https://developers.openai.com/codex/changelog?date=2026-01-06`
- OpenAI GPT-5.4 prompt guidance：`https://developers.openai.com/api/docs/guides/prompt-guidance/`
- OpenAI eval skills 文章：`https://developers.openai.com/blog/eval-skills/`
- Cursor Rules 文档：`https://cursor.com/docs/rules`
- OpenClaw System Prompt：`https://docs.openclaw.ai/concepts/system-prompt`
- OpenClaw Context / Skills：`https://docs.openclaw.ai/concepts/context`
- OpenClaw Agent Loop：`https://docs.openclaw.ai/concepts/agent-loop`

---

## 18. 附：一句话回答你的两个追问

### Q1. 原文重要吗？
重要，但默认不固定注入；只在 wording-sensitive / evidence-sensitive / quote-required 时按需引入短摘录。

### Q2. 包不包含模型回答？
不默认包含模型回答原文；只抽取其中的 commitment / assumption / plan / pending_action / decision 等状态化内容。

