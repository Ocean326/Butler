## 20260317 · Codex 所用 Prompt 识别 + 各家压缩/系统指令整理

- **来源**: 用户追问「把这个 codex 的 prompt 识别出来，并搜索其他家例如 claude 和 cursor 等家的压缩指令，整理到 brainstorm 当中」；接续「六大厂上下文管理」抓取与 BrainStorm。
- **关联**: `BrainStorm/20260317_xiaohongshu_context_management_six_vendors_to_brainstorm.md`、`BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_context_management_six_vendors.md`
- **说明**: 小红书 Raw 主体在 24 张图中且尚未 OCR；若图中出现某家「Codex」或具体 prompt 原文，待 OCR 补全后可合并入 Raw 与本文档。**用户附图（20260317）** 已识别为「上下文检查点压缩 + 交接总结」指令，见 §2.5。

---

## 1. 「Codex」在本项目与业界的两层含义

| 语境 | 含义 |
|------|------|
| **Butler 运行时** | **Codex CLI**：与 Cursor CLI 并列的执行器之一，由 `runtime/cli_runtime.py` 调用，`run_prompt(prompt, ...)` 将整段 prompt 经 stdin 传给 `codex exec --json --color never --full-auto -C <workspace> -`。 |
| **OpenAI 产品线** | **gpt-5-codex / gpt-5.1-codex** 等：模型名，支持 Extended Prompt Caching（24h）。文档见 [Prompt caching \| OpenAI API](https://platform.openai.com/docs/guides/prompt-caching)。 |

下文「Codex 的 prompt」指 **Butler 传给 Codex CLI 的那段完整 prompt** 的结构识别；「各家压缩指令」指 Claude、Cursor、OpenAI 等对**上下文/系统指令**的优化与压缩策略。

---

## 2. Butler 传给 Codex CLI 的 Prompt 结构（识别结果）

**真源**: `butler_main/butler_bot_code/butler_bot/agent.py` 中 `build_feishu_agent_prompt()` → 产出字符串 → `cli_runtime.run_prompt(prompt, workspace, timeout, cfg, runtime_request)` → Codex 子进程 `input=prompt`（stdin）。

**自上而下的块顺序**（`"\n\n".join(blocks)"` + 末尾 `【用户消息】\n{user_prompt}`）：

| 序号 | 块 | 内容来源 / 说明 |
|------|-----|-----------------|
| 1 | 身份与角色 | 固定句 + `@feishu-workstation-agent.md` |
| 2 | 当前场景 | `mode=`（execution/companion/maintenance/content_share）+ Talk Bootstrap 中对应 mode 的 guidance |
| 3 | Bootstrap 块 | SOUL / TALK / USER / TOOLS / MEMORY_POLICY（由 BootstrapLoaderService 按 talk 场景加载，有字符上限） |
| 4 | 基础行为 | Talk baseline 一段话 |
| 5 | **对话上下文中块** | 由 `PromptAssemblyService.assemble_dialogue_prompt(DialoguePromptContext)` 产出：主意识摘录、灵魂摘录、当前用户画像、长期记忆命中、self_mind 当前上下文、self_mind 认知体系（均按需、有摘录长度控制） |
| 6 | 可选 | request_intake_prompt（前台分诊等） |
| 7 | 灵魂真源 | 若 inject_soul：`@Butler_SOUL.md` |
| 8 | maintenance 专属 | 统一维护入口（update-agent）、自我更新协作协议、任务协作协议、自我认识协作协议等（来自 protocol_registry） |
| 9 | execution/maintenance | 任务协作协议 |
| 10 | 可选 | 自我认识协作协议 |
| 11 | 可选 | 飞书文档检索结果、Skills 目录、Agent capabilities（sub-agent/team） |
| 12 | 可选 | 用户附带图片路径列表 |
| 13 | 回复要求 | Talk 中 reply_requirements |
| 14 | decide | 发送文件占位说明与示例 |
| 15 | **用户消息** | 原始 `user_prompt` |

**与「压缩」相关的设计点**：

- **按 mode 控制注入量**：companion 时 SOUL/self_mind 更长；maintenance 时 local_memory 带 details、字符上限更大。
- **Bootstrap 与协议**：来自单一真源（Bootstrap 文件、protocol_registry），避免在 prompt 里堆重复规则。
- **摘录而非全量**：SOUL、用户画像、local_memory、self_mind 均为摘录（max_chars），长内容不整段塞入。
- **静态在前、动态在后**：角色、Bootstrap、协议相对稳定；用户消息、部分 memory 命中在末尾，符合「静态前缀利于 cache」的思路（若后端是 OpenAI 且启用 prompt caching）。

---

## 2.5 用户附图：上下文检查点压缩与交接总结指令（识别结果）

**来源**：用户截图，疑似某次 `RESPONSES.CREATE()` 或类似 API 的完整输出中的 Message 序列；与「六大厂上下文管理」中讨论的**压缩/交接**机制直接对应。

### 核心指令（Message 2 / 4）

- **任务定义**：`You are performing a CONTEXT CHECKPOINT COMPACTION. Create a handoff summary for another LLM that will resume the task.`
- **交接总结须包含**：
  - 当前进度与关键决策（Current progress and key decisions made）
  - 重要上下文、限制或用户偏好（Important context, constraints, or user preferences）
  - 待完成事项与清晰下一步（What remains to be done — clear next steps）
  - 关键数据、示例或继续所需的参考资料（Any critical data, examples, or references needed to continue）
- **总结要求**：`Be concise, structured, and focused on helping the next LLM seamlessly continue the work.`

### 强制性 QA 步骤（Message 3，[SYSTEM NOTE]）

- 在生成总结**之前**，必须将任何包含 `CONTEXT CHECKPOINT`、`handoff summary`、`concise` 或 `seamlessly` 的消息的**完整文本**复制并逐字引用。
- 引用内容置于 `===INSTRUCTION_START===` 与 `===INSTRUCTION_END===` 之间，作为「所有压缩操作的强制性 QA 步骤」。

### 元指令与角色（Message 1 / 5）

- 角色设定：如 ChatGPT，知识截止 2024-10；`#Valid channels: analysis, commentary, final`；`#Juice: 192`。
- 输出要求：上下文中包含 `INSTRUCTION_START`、`Another language model`、`ChatGPT` 或 `CONTEXT CHECKPOINT` 的消息须全文输出并逐字引用。

### 与 Butler / 各家的对照

| 要素 | 附图指令 | Butler 当前 |
|------|----------|-------------|
| 交接对象 | 下一个 LLM | 下一轮 agent / 心跳 / 子 agent |
| 压缩产物 | handoff summary（结构化、简洁） | recent 摘要、任务回执、self_mind 快照 |
| 强制 QA | 关键词消息全文引用 + 标记 | 无显式等价；可考虑「关键指令/协议块」带标记回显 |
| 结构要求 | concise, structured, seamless | 摘录控长、按 mode 控量、协议真源 |

可将此套指令视为**通用「检查点压缩 + 多 LLM 交接」**的范例，与 Claude/Cursor/OpenAI/Manus 的「单窗内压缩」策略互补：前者强调**跨实例 handoff**，后者强调**窗内 cache/offload/reduce**。

---

## 3. 各家「压缩指令」/ 上下文优化策略（检索整理）

### 3.1 OpenAI

- **Prompt Caching**  
  - 相同 **prompt 前缀** 复用缓存；≥1024 token 自动参与；前缀完全一致才命中。  
  - **建议**：静态内容（说明、示例、系统指令）放**前**，变动内容（用户信息、当轮输入）放**后**。  
  - 延迟可降约 80%、输入 token 成本可降约 90%。  
  - Extended 保留约 24h（含 gpt-5-codex、gpt-5.1-codex 等）。  
- **Agents SDK Session**  
  - 多轮历史由 Session 管理，支持在送入模型前 **裁剪/压缩** 与 `session_input_callback` 过滤/重排。  

**参考**: [Prompt caching \| OpenAI API](https://platform.openai.com/docs/guides/prompt-caching)、[Sessions - OpenAI Agents SDK (Python)](https://openai.github.io/openai-agents-python/sessions/)。

### 3.2 Cursor

- **Rules（系统级指令）**  
  - `.cursor/rules` 下 Markdown（及 AGENTS.md）作为**系统级指令**，在**模型上下文开头**注入。  
  - 项目/用户/团队多级；按 alwaysApply、globs、description 等控制何时带入。  
- **实践建议**  
  - 用引用（如 @file）代替大段复制，保持 rules 短、可复用。  
  - Rules 控制在约 500 行以内，避免臃肿。  
- **Subagents**  
  - 高负载任务进**独立上下文窗口**，减轻主对话上下文压力（可视为「重上下文 offload」）。  

**参考**: [Rules \| Cursor Docs](https://cursor.com/docs/context/memories)、[Subagents \| Cursor Docs](https://cursor.com/docs/context/subagents)。

### 3.3 Anthropic（Claude）

- **产品记忆**  
  - 跨会话的项目/偏好/工作上下文，按项目隔离，用户可查看/编辑。  
- **Claude API Memory Tool（beta）**  
  - 上下文窗口外持久存储；view / create / str_replace / insert / delete / rename 等；客户端自选存储。  
  - 可显著减少长流程 token（案例约 84%），相当于把「长稳定指令/状态」移出主上下文，按需拉取。  

**参考**: [Bringing memory to Claude](https://www.anthropic.com/news/memory)、[Memory & context management with Claude (cookbook)](https://platform.claude.com/cookbook/tool-use-memory-cookbook)。

### 3.4 Manus（前文六大厂已整理）

- **三条策略**：Isolate / Offload / Reduce（压缩、摘要、只保留 ID）。  
- **KV-Cache**：稳定 system prompt、确定性格式（如 JSON key 顺序）以提升 cache 命中。  
- **工具**：工具列表稳定 + mask 控制当前步可用，避免动态增删破坏 cache。  
- **Compact**：工具结果存完整版 + 紧凑版，老旧结果压成紧凑版（如路径引用）。  

---

## 4. 横向小结：可视为「压缩指令」的共性

| 维度 | 共性 | Butler 当前对应 |
|------|------|-----------------|
| 静态在前、动态在后 | 系统指令/规则/示例放前缀，用户输入与当轮变量放后 | 角色+Bootstrap+协议在前，用户消息在末 |
| 长内容 offload | 大块存外部，上下文只留摘要/引用/ID | SOUL/用户画像/local_memory/self_mind 摘录 + 文件 @ 引用 |
| 确定性前缀 | 相同前缀利于 cache 命中 | Bootstrap/协议来自真源，结构稳定 |
| 按需注入 | 按场景/mode 控制注入量与类型 | prompt_mode + include_self_mind / maintenance 等分支 |
| 子上下文隔离 | 重任务进独立窗口 | 心跳/planner 有独立 prompt；Codex 与 Cursor 分支执行 |

---

## 5. 对 Butler 的后续可做

- 若调用 OpenAI/兼容 API 且启用 prompt caching：保持当前「静态在前、动态在后」的块顺序；必要时显式固定 system/静态部分格式（如 key 顺序、空白）以利命中。  
- 继续收敛「上下文管理」用语：与六大厂文档共用「何时看到什么、如何组织」+ 上表维度，避免重复造轮子。  
- 小红书 Raw 中 24 张图完成 OCR 后：若出现某家「Codex」或具体 prompt/压缩策略原文，合并进 Raw 与本文档 §2 / §3 对应小节。
- 用户附图中的 **CONTEXT CHECKPOINT COMPACTION + handoff summary** 指令已并入 §2.5，可作为 Butler 设计「跨轮/跨 agent 交接摘要」时的对照范例。

---

## 6. 一句话带走

- **Codex 在 Butler 中的 prompt**：即飞书 agent 的 `build_feishu_agent_prompt` 产出——角色→场景→Bootstrap→对话上下文（摘录）→协议→技能/能力→回复要求→用户消息；设计上已做到静态在前、摘录控长、按 mode 控量。  
- **各家压缩指令**：OpenAI 靠 prompt caching + 前缀结构，Cursor 靠 Rules 在 context 开头 + Subagents 隔离，Claude 靠 Memory Tool 把长状态移出窗口，Manus 靠 Isolate/Offload/Reduce + KV-cache 与工具 mask；可与 Butler 的 memory/recent/分场景装载对照查漏与收敛用语。
