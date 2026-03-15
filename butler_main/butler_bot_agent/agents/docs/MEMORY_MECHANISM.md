# 短期 + 长期记忆机制规范（可复用）

> 本文件描述**统一的短期 + 长期记忆机制**：路径约定、数据结构、读写与压缩规则。  
> 飞书管家、新建管家 Agent、或其它角色 Agent（如某项目的 coder）均可复用此机制，只需指定各自的**记忆根路径**即可。

---

## 1. 概述

- **短期记忆**：最近 N 轮对话的摘要与待办，用于续接上下文。
- **长期记忆**：按主题/文件存放的持久化信息（约定、偏好、技术备忘、人事等）。
- **关系**：短期记忆超量时压缩，其中值得保留的条目可沉淀到长期记忆。
- **治理原则**：记忆服务任务连续性，不服务于机械自我加码；避免把每轮都变成“先读完、再写满、再补反思”。

---

## 2. 路径约定（可配置）

默认以 **`./butler_bot_agent/agents`** 为记忆根（飞书管家即用此根）。其它 Agent 可指定自己的根路径（如 `./butler_bot_agent/agents/coder_memory` 或工作区内某目录）。

| 用途       | 默认路径（飞书管家）                    | 说明 |
|------------|-----------------------------------------|------|
| 短期记忆   | `{记忆根}/recent_memory/recent_memory.json` | JSON 数组，机器读写 |
| 短期归档   | `{记忆根}/recent_memory/recent_archive.md`  | 压缩后的旧条目标题/摘要 |
| 长期记忆   | `{记忆根}/local_memory/`                   | 目录下多个 `.md` 文件，按主题分子文件 |

**示例**：若某「项目 Coder」Agent 使用独立记忆，可设记忆根为 `./butler_bot_agent/agents/coder_memory`，则短期为 `recent_memory/recent_memory.json`，长期为 `local_memory/`。

---

## 3. 短期记忆（recent_memory）

### 3.1 文件与格式

- **主文件**：`recent_memory.json`，顶层为 **JSON 数组**。
- **单条结构**建议字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `timestamp` | string | 时间戳，如 `"2026-03-07 05:16:44"` |
| `topic` | string | 本轮主题/标题 |
| `summary` | string | 摘要，供续接上下文用 |
| `next_actions` | array of string | 下一步动作或待办 |
| `long_term_candidate` | object | 是否建议写入长期记忆 |
| `long_term_candidate.should_write` | boolean | 是否建议沉淀 |
| `long_term_candidate.title` | string | 建议的长期记忆标题 |
| `long_term_candidate.summary` | string | 建议的长期记忆摘要 |
| `long_term_candidate.keywords` | array of string | 关键词，便于归类 |
| `memory_id` | string | 可选，唯一 id |
| `status` | string | 可选，如 `"completed"` |

### 3.2 使用规则

- **沿用**：用户**未**明确说「全新任务 / 全新情景」时，默认**沿用** recent_memory 续接上下文。
- **忽略**：用户**明确开启新任务**时，**不**加载 recent_memory，本轮视为全新起点。
- **读取策略**：是否先读 recent_memory，遵循 `MEMORY_READ_PROMPTS.md`，默认按需轻载，不做机械全读。
- **写入**：仅当本轮信息对后续续接、恢复现场、跨轮待办或长期沉淀有明显价值时，再由调用方（如管家bot）或 Agent 本人提炼一条短期记忆并追加到 `recent_memory.json`（含上述字段）；一次性、低复用、纯闲聊内容可不写。

### 3.3 长度与压缩

- **长度控制**：与 `butler_bot_code/docs/recent_memory_compact_policy.md` 一致，当前为「最近 15 条」、总字符约 15k（TALK_RECENT_MAX_ITEMS=15、TALK_RECENT_MAX_CHARS=15000）。
- **压缩触发**：超过轮数或长度时，将「较早的条目」压缩：
  - 摘要可合并写入 `recent_archive.md`；
  - 其中 `long_term_candidate.should_write === true` 的条目，择优沉淀到 `local_memory/`（见下），同类记忆优先更新已有文件。

---

## 4. 长期记忆（local_memory）

### 4.1 存放方式

- **目录**：`{记忆根}/local_memory/`。
- **文件**：Markdown 文件，按主题/ bot 名/项目分子文件（如 `研究管理_输出路径与约定.md`、`非研究生活.md`、`项目A_技术备忘.md`）。
- **内容**：自由格式，建议含标题、日期、摘要、关键词，便于后续按主题加载。

### 4.2 加载优先级（可选）

若希望整理与加载都按重要性排序，可约定：

- **高优先级**：与运行/底层长期记忆相关（如输出路径、记忆约定、关键流程）。
- **一般**：项目备忘、人事、生活等。
- 执行记忆整理的 Agent（如 file-manager-agent）与读取方都应遵循同一优先级约定，便于「先读重要、再按需读其余」。

### 4.3 沉淀来源

- 短期记忆压缩时，将 `long_term_candidate.should_write === true` 的条目择优写入 local_memory。
- 也可由用户或 Agent 主动将反思、经验、约定写入 local_memory；**与人设无关的约定、偏好、技术备忘不写入角色说明，应写入 local_memory**。
- 沉淀前先判断：是否真的会跨轮复用、是否属于重复失误或高风险问题、是否值得长期保留；不要因为一次小失误就立即扩写长期约定。

---

## 5. 与新角色 Agent 的对接

若你**新建一个角色 Agent**（例如某项目的 coder），希望它也具备「短期 + 长期记忆」：

1. **指定记忆根**：为该 Agent 选定记忆根路径（可与管家共用 `./butler_bot_agent/agents`，或用独立目录如 `./butler_bot_agent/agents/coder_memory`）。
2. **在角色说明中引用本机制**：写明短期/长期路径、以及「遵循 `./butler_bot_agent/agents/docs/MEMORY_MECHANISM.md` 中的使用规则与压缩规则」。
3. **若需「先读再回」**：同时引用 `./butler_bot_agent/agents/docs/MEMORY_READ_PROMPTS.md`，或把其中的读取提示词抄入该 Agent 说明并替换路径。
4. **写入与压缩**：若由管家bot 统一维护，需在配置中为该 Agent 绑定同一套 recent_memory/local_memory 路径；若由 Agent 自行维护，则需在回复结束时按本规范追加短期记忆，并在实现中按本规范做压缩与沉淀。

---

## 6. 与现有组件的对应关系

- **飞书管家**：记忆根为 `./butler_bot_agent/agents`，短期 `recent_memory/recent_memory.json`，长期 `local_memory/`；读取提示词见 `MEMORY_READ_PROMPTS.md`。
- **管家bot**：负责飞书场景下 recent_memory 的自动追加与压缩、以及启动时长期记忆整理（可调 file-manager-agent）。
- **file-manager-agent**：执行长期记忆整理时，遵循本机制中的路径与优先级约定，并知晓「沿用 / 全新任务」规则，在整理/压缩 recent 时保留相应语义。

---

*记忆读取的**提示词**（如何读、何时读）见 `./butler_bot_agent/agents/docs/MEMORY_READ_PROMPTS.md`；避免系统越维护越僵硬，所有使用方同时遵循 `./butler_bot_agent/agents/docs/ANTI_OVERCONSTRAINT.md`。*
