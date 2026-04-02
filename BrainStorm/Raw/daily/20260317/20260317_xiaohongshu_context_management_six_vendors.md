# 小红书原文 · AI Agent 上下文管理：六大厂方案对比

- **platform**: xiaohongshu
- **author**: AI技术立文
- **title**: AI Agent 上下文管理：六大厂方案对比（页内标题可能被解析为「搜索小红书」）
- **source_url**: `http://xhslink.com/o/4b8vlY8fs4w`
- **resolved_url**: `https://www.xiaohongshu.com/discovery/item/69ad7f76000000002602d32f...`
- **note_id**: 69ad7f76000000002602d32f
- **published_at**: 2026-03-08
- **updated_at**: 2026-03-11
- **capture_time**: 2026-03-17（web-note-capture-cn）
- **engagement**: 赞 386 / 评论 9 / 收藏 800 / 分享 166

---

## 一手正文（网页首屏文本）

> 当前做 AI Agent 的公司，无论 Manus、Cursor、Anthropic 还是 OpenAI，本质上都在解决同一个问题：**LLM 应该什么时候看到什么信息，信息应该如何组织**。
>
> 有意思的是，这些公司都把自己的方案公开了——通过博客、SDK 文档、研究论文。每家公司从不同的约束出发，走出了不同的方案。有些方案趋于一致，有些甚至互相矛盾。
>
> 这篇文章把各家的方案拆开来看，做了横向对比，总结出哪些技术正在成为行业标准，哪些还在实验阶段。
>
> #agent #AI人工智能 #上下文工程 #开发

---

## 图片与 OCR 状态

- **图片数量**: 24 张（正文主体在图中）
- **图片本地路径**: `BrainStorm/Raw/images/` 下已下载，文件名前缀 `img_` + URL 的 base64 编码
- **OCR 状态**: 本机未安装 PaddleOCR，未生成图中文字；**已通过直接读图（2026-03-17）将 24 张图内容补充至下方「图中内容补充」小节**，可替代 OCR 用于正文+结构+对比矩阵
- **抓取 JSON**: `工作区/网页抓取验证/xiaohongshu_69ad7f76000000002602d32f.json`
- **OCR 输出占位**: `BrainStorm/Raw/xiaohongshu_69ad7f76000000002602d32f_ocr.md`（当前为无文字版，仅记录 error）

---

## 附图 URL 列表（供后续 OCR 或人工校对）

见抓取 JSON 的 `images` 字段，或 `工作区/网页抓取验证/xiaohongshu_69ad7f76000000002602d32f.json` 中的 images 字段。

---

## 图中内容补充（直接读图，2026-03-17）

以下由对 `BrainStorm/Raw/images/` 下 24 张已下载图片的直接读取整理，补全正文未抓到的图中文字与结构。

### 文档结构（图中目录）

- **1. 问题背景**
- **2. Manus: 六条生产原则**（2.1 背景，2.2 六条原则）
- **3. Cursor: 动态上下文发现**（3.1 背景，3.2 五种技术）
- **4. Anthropic: 注意力预算框架**（4.1 背景，4.2 核心策略）
- **5. OpenAI: 会话记忆即基础设施**（5.1 背景，5.2 三种模式）
- **6. Google: 长上下文赌注**（6.1 背景，6.2 方案）
- **7. LangChain: 框架分类法**（7.1 背景，7.2 四个操作）
- **8. 方案对比矩阵**（8.1 上下文窗口管理，8.2 信息检索，8.3 规划与一致性，8.4 多 Agent 与隔离，8.5 记忆与健壮性）
- **9. 总结**（9.1 共识，9.2 争议，9.3 未解决，9.4 值得关注）
- **10. 开放问题** + **参考资料**

**六大厂/框架**：Manus、Cursor、Anthropic、OpenAI、**Google**、**LangChain**（后两者在图中补全）。

### 问题背景（图）

- 共同约束：**上下文窗口有限**，Agent 生成 token **指数级增长**；典型任务约 50 次工具调用，易产生 **Context Rot**。
- Anthropic 称「注意力预算」；LangChain 类比「上下文窗口 = RAM」。共识：**更聪明的上下文管理比更大的窗口更重要**。

### Manus（图）

- **背景**：服务数百万用户，典型任务约 50 次工具调用，输入输出 token 约 **100:1**；曾四次重写 Agent 框架，每次因更好的**上下文塑形**。
- **六条原则（图中要点）**：  
  - **KV-Cache 神圣**：缓存 token 成本约 0.3/MTok，未缓存约 3/MTok，差约 10 倍。保持 prompt 前缀稳定、日志只追加；即使重排 JSON 键名也会使缓存失效。  
  - **Design Around the KV-Cache**：正确做法是历史 Action/Observation 原序保留、只末尾追加新步；错误做法是中间插入或重排导致大量 Cache Miss。  
  - **Mask, Don't Remove**：用 Logit 屏蔽而非移除工具；所有工具永久加载；每步可用性通过解码时约束输出 token 概率控制；上下文稳定，只有行为约束在变。  
  - **文件系统作为扩展记忆**：大观察写入文件，上下文只留轻量引用；只要可逆，压缩就 OK。  
  - **通过背诵操作注意力**：活的待办列表每步更新并重读，把当前目标放在高注意力区域（上下文末尾）。

### Cursor（图）

- **背景**：2026-01 博客提出五种技术；结论：模型能力增强后，**减少预给细节、让 Agent 自己拉取上下文**效果更好（有 A/B 数据支持）。
- **五种技术（图中部分）**：  
  - 文件作为工具输出接口：大 JSON 写入文件，Agent 用 `tail`/`grep` 增量读，避免不必要摘要。  
  - 聊天历史文件实现无损压缩：完整历史在摘要前无损落盘，可恢复任意细节。  
  - 技能作为可发现文件：领域能力存为文件，通过搜索发现，不预加载到 system prompt。  
  - 懒加载 MCP 工具：只预加载工具名，按需取完整定义；A/B 测试 **MCP 动态上下文发现使总 token 减少 46.9%**。  
  - 终端会话作为文件：Shell 历史可搜索。  
- **通用原则**：保留错误不清理（便于隐式信念更新）；结构化变化防固化（不同迭代用不同序列化/措辞）。

### Anthropic（图）

- **背景**：2025-09 注意力预算框架；2026-01 长周期 Agent Harness；2025-11 基于 MCP 的代码执行；基于 Claude Code 构建。
- **System Prompt 金发女孩区**：失败模式一为过度工程化（2K+ 词 if-else）；失败模式二为过于模糊（如 "be helpful"）。做法：用 XML/标题结构化 prompt，给典型示例，让模型自行处理边缘情况。
- **即时检索**：从推理前 RAG 转向**循环内检索**。无重叠的精简工具；95% 窗口时自动摘要；长周期 Agent 用初始化 Agent 写跨窗口持久化需求文件（200+ 特性）。代码执行优于直接工具调用（多服务器 MCP 下 Agent 写代码调工具）。

### OpenAI（图）

- **背景**：方案在 Agents SDK 与两份 cookbook：短期会话记忆（2025-09）、长期上下文个性化（2025-12）；贡献是**面向框架、开发者可直接采用的模式**。
- **失败模式**：Agent 一杆进洞复杂项目时中途耗尽上下文；跨窗口压缩导致信息传递不完整。**解决方案**：文件系统里的结构化规划文件；定义留在文件系统。
- **三种模式**：  
  - **截断**：删更早轮次、保留最后 N 个；简单、确定、零延迟，但早期约束易「失忆」。  
  - **压缩**：单独模型调用摘要更早历史；摘要可作「清洁室」修正错误；风险为摘要漂移。  
  - **基于状态的长期记忆**：结构化状态对象（profile + notes）跨会话持久化；每次运行：提炼记忆 → 合并 notes → 注入状态（优先级：最新输入 > 会话 > 全局默认）。OpenAI 区分「基于检索的记忆」与「基于状态的记忆」，后者支持信念更新、更可靠确定。
- **SummarizingSession**：多轮对话可总结为 Context Summary 再续对话。

### Google（图）

- **背景**：与其余各家不同，押注**富足**——Gemini 提供高达 **2M token** 上下文，研究测试甚至 **10M**。
- **6.2 方案（ReadAgent 等）**：「全放进去」默认填满窗口；RAG/摘要是有限上下文模型的 workaround；上下文缓存 API 可减约 75% 成本；渐进截断；ReadAgent Gist Memory（交互压成情景 gist，需时查原文，有效上下文增约 20 倍）；多样本上下文学习。张力：长上下文未消除上下文工程，但改变了形态；研究显示上下文变长时性能仍可能降 15–47%。

### LangChain（图）

- **背景**：贡献在**分类学**，把各家做法组织成连贯框架；基于 LangGraph 与 Deep Agents 分析。
- **四个操作**：**写**（窗口外保存：草稿本、持久状态、文件系统）；**拉**（RAG、语义搜索、文件系统 grep/glob；难点是在正确时间检索「正确上下文」）；**压缩**（摘要保留相关 token、修剪移除无关 token）；**隔离**（状态内划分、环境/沙盒持有、跨多 Agent 划分）。No-op 规划工具：Claude Code 待办工具实为上下文策略，强制 Agent 明确表述计划。

### 方案对比矩阵图例与要点

- 图例：`[C]` 核心差异化/考虑中，`[Y]` 已使用/倡导，`[--]` 未公开讨论，`[alt]` 替代方案。
- **8.1 上下文窗口管理**：KV-cache/prompt caching — Anthropic [Y]、Google [Y]、Manus [C]。Compaction/自动摘要 — Manus/Cursor/OpenAI/LangChain [Y]，Anthropic [C]，Google [alt]。Context trimming — OpenAI [C]，Google/LangChain [alt]/[Y]。Massive context 1M+ — Google [C]。
- **8.2 信息检索**：即时/动态检索 — Manus/LangChain [Y]，Cursor/Anthropic [C]。文件系统扩展记忆 — Anthropic/LangChain [Y]，Manus/Cursor [C]。懒加载工具 — Anthropic [Y]，Cursor [C]，Manus [alt]。语义搜索/RAG — Cursor/Anthropic/LangChain [Y]，Google [alt]。
- **8.3 规划与一致性**：持久计划文件 — Anthropic/LangChain [Y]，Manus [C]。注意力操纵/复述 — Manus [C]。No-op 规划工具 — Anthropic/LangChain [Y]。错误保留 — Anthropic/LangChain [Y]，Manus [C]。
- **8.4 多 Agent 与隔离**：子代理上下文隔离 — Anthropic/OpenAI/LangChain [Y]，Manus [C]。Agent-as-tool — OpenAI/LangChain [Y]，Manus [C]。
- **8.5 记忆与健壮性**：基于状态长期记忆 — OpenAI [C]，LangChain [Y]。Gist/episodic 记忆 — Google [C]。聊天记录可恢复文件 — Cursor [C]。结构化变体抗固化 — Manus [C]。总结漂移缓解 — Cursor/OpenAI [Y]。

### 总结（图）

- **9.1 共识**：文件系统作为扩展记忆；动态优于静态检索；长任务用持久化计划文件；错误追踪保留不清理。
- **9.2 争议**：（图中未展开）
- **9.3 未解决**：工具过载——Manus logit 屏蔽 vs Cursor 懒加载；长上下文 vs 精简——Google vs 其他；框架 vs 原始原语；会话记忆无两家相同；上下文工程无标准 benchmark（Cursor 46.9% token 减少是少数公开数据）；何时隔离子 Agent 上下文仍偏经验。
- **9.4 值得关注**：做出最好 Agent 的团队一直在简化；Manus 重写五遍、每遍在删东西；若 harness 越来越复杂而模型越来越好，就有问题。

### 开放问题与参考资料（图）

- **开放问题**：长上下文 vs 智能压缩——规模化后谁赢？子 Agent 应共享上下文还是只传结果？如何评估上下文工程质量？
- **参考资料**（图中链接，择要）：Manus 博客 Context Engineering；Cursor Dynamic Context Discovery；Anthropic Effective Context Engineering、Effective Harnesses for Long-Running Agents、Code Execution with MCP；OpenAI Cookbook Session Memory、Context Personalization；DeepMind ReadAgent Gist Memory；Google Long Context Documentation；LangChain Context Engineering for Agents、The Rise of Context Engineering、Filesystems for Context Engineering、Deep Agents；philschmid.de context-engineering-part-2；rlancemartin.github.io Manus。

---

## 评论区

默认未抓取；需评论可后续用带登录态抓取或用户粘贴补充。
