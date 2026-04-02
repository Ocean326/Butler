## 20260317 · 小红书 · AI Agent 上下文管理：六大厂方案对比 · 结构化头脑风暴 + 技术博客整理

- **来源**: 小红书《AI Agent 上下文管理：六大厂方案对比》（作者：AI技术立文）
- **原文 Raw**: `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_context_management_six_vendors.md`
- **抓取状态**: 正文开篇已落盘；主体内容在 24 张图中，**已通过直接读图（2026-03-17）补充至 Raw「图中内容补充」**，含六大厂名单、各厂要点、方案对比矩阵与总结。下文 §3 技术博客整理基于正文+图中点名与公开检索补全。
- **主题标签**: #agent #AI人工智能 #上下文工程 #开发

---

## 1. 一句话印象

> **做 AI Agent 的几家都在解同一道题：LLM 何时看到何种信息、信息如何组织。文中点名 Manus、Cursor、Anthropic、OpenAI 均通过博客/SDK/论文公开方案；下面按「原文论点 + 检索到的技术博客」整理成一份可对照、可落地的上下文管理清单，并接到 Butler 的 memory/recent/分场景装载设计。**

---

## 2. 原文核心论点（开篇 + 图中待 OCR 补全）

### 2.1 统一问题

- **本质问题**：LLM 应该**什么时候**看到**什么信息**，信息应该**如何组织**。
- **公开程度**：各家公司通过博客、SDK 文档、研究论文公开方案；有共识也有分歧。

### 2.2 六大厂/框架（正文+图中补全）

- **Manus** · **Cursor** · **Anthropic** · **OpenAI** · **Google** · **LangChain**  
（正文开篇点名前四家；图中目录与对比矩阵补全为六家/六框架，含 Google 与 LangChain。）

- **图中各厂要点**（Manus 六条原则与 KV-cache/ mask、Cursor 五种技术与 46.9% token 降、Anthropic 金发女孩区与 95% 摘要、OpenAI 截断/压缩/状态记忆、Google 2M/10M 与 ReadAgent Gist、LangChain 写/拉/压缩/隔离四操作）见 Raw「图中内容补充」小节。

---

## 3. 技术博客与官方文档整理（检索补全）

以下为按「上下文管理 / 记忆 / 缓存 / Agent 会话」主题检索到的**官方或一手来源**摘要，用于补全小红书图中未抓到的内容，并便于与 Butler 设计对照。

### 3.1 Manus

- **核心思路**：Context Engineering——在上下文窗口内**策略性管理**信息，以优化性能、成本与稳定性。
- **三条策略**：  
  1. **Isolate Context**：信息分块、隔离、有序。  
  2. **Offload Context**：大块数据（日志、长输出）存外部（如文件系统），上下文里只保留短摘要或引用。  
  3. **Reduce Context**：压缩（摘要、只保留 ID 不保留全文）。
- **生产重点**：**KV-Cache 命中率**；稳定 system prompt、确定性格式（如 JSON key 顺序、空白）以保持 cache 命中，可带来约 10x 成本差异。
- **工具与 cache**：工具列表保持稳定在上下文中，用 **mask** 控制「当前步可用哪些」，而不是动态增删工具（避免破坏 cache 连续性）。
- **Compact 策略**：工具结果存「完整版 + 紧凑版」；老旧结果压成紧凑版（如文件路径引用），需要时再取全文。
- **参考**：  
  - [Context Engineering with Manus AI Agent](https://manus.so/post/context-engineering-with-manus-ai-agent)  
  - [Context Engineering for AI Agents: Lessons from Building Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)  
  - Vercel AI SDK 中有 KV-cache 友好与 tool masking 的实践示例。

### 3.2 Cursor

- **子 Agent 隔离**：用 **Subagents** 把高上下文负载任务放进**独立上下文窗口**，保护主对话上下文；支持并行多线（Explore / Bash / Browser 等）。
- **持久上下文**：**Rules**（`.cursor/rules` 下的 Markdown）作为系统级指令，在模型上下文开头注入；支持项目/用户/团队范围。
- **按需加载**：**Agent Skills** 以包的形式存在（如 `.cursor/skills/`），按需加载，避免一次性塞满上下文。
- **使用场景**：复杂调研用 Subagents 做上下文隔离与并行；Rules 统一风格与架构决策；Skills 做单次可复用的动作。
- **参考**：  
  - [Subagents | Cursor Docs](https://cursor.com/docs/context/subagents)  
  - [Rules | Cursor Docs](https://cursor.com/docs/context/memories)  
  - [Agent Skills | Cursor Docs](https://cursor.com/docs/context/skills)  
  - [Context | Cursor Learn](https://cursor.com/learn/context)

### 3.3 Anthropic（Claude）

- **产品级 Memory**：Claude 官方「记忆」功能，跨会话记住用户/团队的项目、偏好与工作上下文；按项目隔离存储，用户可查看/编辑/管理。
- **开发者/Agent 侧**：**Claude API Memory Tool**（beta）：在上下文窗口外做持久存储，提供 view / create / str_replace / insert / delete / rename 等操作；可显著减少长流程中的 token 使用（有案例约 84%）。
- **存储控制**：Memory 在客户端实现，开发者可自选存储（本地、数据库、加密等）。
- **参考**：  
  - [Bringing memory to Claude](https://www.anthropic.com/news/memory)  
  - [Memory & context management with Claude (cookbook)](https://platform.claude.com/cookbook/tool-use-memory-cookbook)

### 3.4 OpenAI

- **Prompt Caching**：相同 prompt 前缀复用缓存，延迟可降约 80%、输入 token 成本可降约 90%；≥1024 token 的 prompt 自动参与，前缀完全一致才命中。建议把静态内容（说明、示例）放前，变动内容（用户信息）放后。
- **缓存保留**：内存约 5–10 分钟（最长约 1 小时）；Extended 可将缓存保留约 24 小时（部分模型）。
- **Agents SDK 会话记忆**：内置 **Session** 管理多轮对话历史，自动维护并在每轮前拼入上下文；支持 Python（如 SQLiteSession）与 TypeScript；可自定义 Session 实现（存储后端可换）。支持裁剪/压缩策略与 `session_input_callback` 在送入模型前过滤/重排历史。
- **参考**：  
  - [Prompt caching | OpenAI API](https://platform.openai.com/docs/guides/prompt-caching)  
  - [Sessions - OpenAI Agents SDK (Python)](https://openai.github.io/openai-agents-python/sessions/)  
  - [Context Engineering - Session Memory (OpenAI Cookbook)](https://developers.openai.com/cookbook/examples/agents_sdk/session_memory/)

---

## 4. 横向对照（可成为行业标准 vs 仍在实验）

### 4.1 维度归纳（与原整理一致）

| 维度           | 趋同/常见做法                               | 仍在分化/实验的点                         |
|----------------|---------------------------------------------|-------------------------------------------|
| 问题定义       | 「何时看到什么 + 如何组织」                 | 各家的边界与术语不完全一致                |
| 长上下文       | Offload / Reduce / 摘要与引用               | 具体压缩策略、compact 粒度               |
| 持久记忆       | 会话外存储（Memory Tool / Session）        | 产品级 vs 开发者级、存储位置与权限        |
| 缓存与成本     | 静态前缀 + 确定性格式以提升 cache 命中      | KV-cache 与 prompt cache 的优先级与实现  |
| 工具与上下文   | 工具列表稳定 + mask 可用性                  | 是否全部采用、与 subagent 的配合         |
| 子 Agent/隔离  | 重任务进独立上下文（Cursor Subagents 等）   | 子 agent 与主上下文的协议、状态共享       |

### 4.2 图中方案对比矩阵（原文图例：\[C\] 核心/考虑中 \[Y\] 已用 \[--\] 未讨论 \[alt\] 替代）

**8.1 上下文窗口管理**  
- KV-cache / prompt caching：Anthropic [Y]、Google [Y]、Manus [C]  
- Compaction / 自动摘要：Manus / Cursor / OpenAI / LangChain [Y]，Anthropic [C]，Google [alt]  
- Context trimming：OpenAI [C]，Google [alt]，LangChain [Y]  
- Massive context 1M+：Google [C]  

**8.2 信息检索**  
- 即时/动态检索：Manus / LangChain [Y]，Cursor / Anthropic [C]  
- 文件系统扩展记忆：Anthropic / LangChain [Y]，Manus / Cursor [C]  
- 懒加载工具：Anthropic [Y]，Cursor [C]，Manus [alt]  
- 语义搜索/RAG：Cursor / Anthropic / LangChain [Y]，Google [alt]  

**8.3 规划与一致性**  
- 持久计划文件：Anthropic / LangChain [Y]，Manus [C]  
- 注意力操纵/复述：Manus [C]  
- No-op 规划工具：Anthropic / LangChain [Y]  
- 错误保留：Anthropic / LangChain [Y]，Manus [C]  

**8.4 多 Agent 与隔离**  
- 子代理上下文隔离：Anthropic / OpenAI / LangChain [Y]，Manus [C]  
- Agent-as-tool：OpenAI / LangChain [Y]，Manus [C]  

**8.5 记忆与健壮性**  
- 基于状态长期记忆：OpenAI [C]，LangChain [Y]  
- Gist/episodic 记忆：Google [C]  
- 聊天记录可恢复文件：Cursor [C]  
- 结构化变体抗固化：Manus [C]  
- 总结漂移缓解：Cursor / OpenAI [Y]  

### 4.3 图中总结共识与未解决（原文 9.1 / 9.3）

- **共识**：文件系统作为扩展记忆；动态优于静态检索；长任务用持久化计划文件；错误追踪保留不清理。  
- **未解决**：工具过载（Manus logit 屏蔽 vs Cursor 懒加载）；长上下文 vs 精简（Google vs 其他）；会话记忆无两家相同；无标准 benchmark（Cursor 46.9% token 减少为少数公开数据）；何时隔离子 Agent 上下文仍偏经验。  
- **值得关注**：最好 Agent 团队一直在简化；Manus 重写五遍、每遍在删；若 harness 越来越复杂而模型越来越好则有问题。

---

## 5. 对 Butler 的启发

### 5.1 已对齐的点

- **记忆真源**：长期记忆、recent 窗口、分场景装载（talk / heartbeat / self_mind）本质上就是在做「何时看到什么 + 如何组织」。
- **价值**：与上述厂商方案对照，可用来**收敛用语**、**查漏**（如 cache、compact、mask）和**避免重复造轮子**。

### 5.2 可补强的方向

- **KV-Cache / Prompt Caching**：若调用 OpenAI/兼容 API，是否把 system/静态部分固定并前置，以利于缓存命中（成本与延迟）。
- **工具在上下文中的呈现**：是否考虑「工具列表稳定 + 按步 mask」，而不是每步重写整个工具列表。
- **大块结果 Offload**：长日志、大段抓取结果是否只留摘要/引用在上下文，全文落盘或走 memory 按需拉取。
- **子任务/重负载隔离**：类似 Subagents，心跳或执行里是否有「重上下文」子流程可放进独立上下文或子 agent，避免撑爆主会话。

### 5.3 后续可做

- 图中对比表与结论已通过直接读图合并至 §4.2 / §4.3，Raw 中见「图中内容补充」小节。
- 在 `docs/concepts` 或 BrainStorm 中保留一份「上下文管理·厂商对照」活文档，随 Butler 的 memory/recent 设计一起迭代。

---

## 6. 技术博客与文档链接汇总（便于后续深挖）

- **Manus**:  
  - https://manus.so/post/context-engineering-with-manus-ai-agent  
  - https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus  
- **Cursor**:  
  - https://cursor.com/docs/context/subagents  
  - https://cursor.com/docs/context/memories  
  - https://cursor.com/docs/context/skills  
  - https://cursor.com/learn/context  
- **Anthropic**:  
  - https://www.anthropic.com/news/memory  
  - https://platform.claude.com/cookbook/tool-use-memory-cookbook  
- **OpenAI**:  
  - https://platform.openai.com/docs/guides/prompt-caching  
  - https://openai.github.io/openai-agents-python/sessions/  
  - https://developers.openai.com/cookbook/examples/agents_sdk/session_memory/

---

## 7. 一句话带走 + 下次怎么用

- **一句话**：各家 Agent 都在解「何时看到什么、如何组织」；Manus 重 KV-cache 与 offload/compact，Cursor 用 Subagents+Rules+Skills，Anthropic 推 Memory Tool，OpenAI 用 prompt caching + Agents SDK Session；Butler 的 memory/recent/分场景装载已在对齐同一命题，可据此查漏与收敛设计。
- **下次优先看**：§3 技术博客整理、§4 横向对照（含图中对比矩阵）、§5 对 Butler 的启发；Raw「图中内容补充」已含六大厂细节与对比矩阵。
