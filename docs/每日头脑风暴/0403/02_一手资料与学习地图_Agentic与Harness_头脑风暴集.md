# Agentic 工程 × Harness：一手资料地图 + 头脑风暴集（0403）

> **用途**：在小红书导读（见 `01_...md`）之外，补齐 **可被引用的官方/半官方链接**，并把 **Harness Engineer** 与 **Butler** 两条心智线各自拆成可讨论的议题簇。  
> **边界**：外链以 2026-04-03 可访问的公开页面为准；厂商文档会改版，若 404 请以站内搜索标题找回。

---

## 1. 学习地图（建议阅读顺序）

1. **先建共同语言**：OpenAI「Harness engineering」长文（人类掌舵、Agent 执行、仓库即真源、渐进式披露）。  
2. **再补厂商工具论**：Anthropic「Effective agents」+「为 Agent 写工具」+ Agent SDK / Subagents / Skills。  
3. **对齐你当前痛点**：Codex harness / App Server（线程生命周期、JSON-RPC 接入面）。  
4. **看社区如何把技能打包**：everything-claude-code（命令 / skill / agent 分隔的社区样板）。  
5. **回到组织落地**：对照 `01` 图 15 的「四阶段」—但把「方向盘」具体化成你们仓库里的单一入口（chat/frontdoor、flow、skills 家族）。

---

## 2. 一手资料索引（按机构）

### 2.1 OpenAI（含「论坛」入口）

| 主题 | 链接 | 我读的时候重点看什么 |
|------|------|----------------------|
| Harness engineering（方法论主干） | https://openai.com/index/harness-engineering/ | 「AGENTS.md 当目录而非百科全书」、`docs/` 为真源、渐进式披露、机械校验防漂移、Ralph loop、可观测性给 Agent 读 |
| Codex App Server | https://openai.com/index/unlocking-the-codex-harness/ | harness 与多客户端接入、JSON-RPC、bidirectional |
| Agent loop 拆解 | https://openai.com/index/unrolling-the-codex-agent-loop/ | turn / tool / 中断与恢复语义，对照你们 cli_runner 卡点 |
| Codex Execution Plans（Cookbook） | https://cookbook.openai.com/articles/codex_exec_plans | 「计划」作为一等资产、可版本化，对照 campaign / flow artifact |
| 开发者社区（论坛） | https://community.openai.com/ | 搜 `Codex`、`harness`、`AGENTS.md`；适合找「非正式但高信噪」的讨论串 |

### 2.2 Anthropic（Skills / Subagent / Agent 设计）

| 主题 | 链接 | 备注 |
|------|------|------|
| Building effective agents | https://www.anthropic.com/research/building-effective-agents | workflow vs agent、何时不要上复杂编排 |
| Multi-agent research system | https://www.anthropic.com/engineering/built-multi-agent-research-system | 对照图 14「多路研究 / breadth-first」；token 与评测方差 |
| Writing tools for agents | https://www.anthropic.com/engineering/writing-tools-for-agents | 工具形状、错误信息即「给模型的Remediation」 |
| Claude Agent SDK | https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk | agent loop、与 Claude Code 对齐的能力面 |
| Subagents（文档） | https://code.claude.com/docs/en/sub-agents | **上下文隔离**与并行，和 `01` 图 10 Subagent 层级互证 |
| Skills（文档） | https://code.claude.com/docs/en/skills | 渐进加载、可审阅知识包 |

### 2.3 Cursor / 渐进式上下文（图 14 中的「动态上下文发现」）

- 公开产品文档入口（功能总览、Rules、索引策略会随版本变）：https://cursor.com/docs  

> 深挖建议：把 Cursor 的策略理解成「**别一次性灌满**」+「**索引与规则分层**」，与 OpenAI 文内的 progressive disclosure 同一族。

### 2.4 社区样板：everything-claude-code

- 仓库：https://github.com/affaan-m/everything-claude-code  
- 用法：把它当「**命令 / skill / agent 分隔**」的标本库，而不是要整体 fork 进 Butler；对照你们 `AGENTS.md`、`docs/project-map/`、`SKILL.md` 家族落位是否会产生图 8 的「路由噪声」。

### 2.5 腾讯侧（笔记引用的「技术工程」长文）

- **现状**：笔记指向「腾讯技术工程 + **rickyshou** + Agentic Engineering 实战」；本轮公网检索**未**锁定该署名的微信原文稳定 URL。  
- **可替代的「同主题、可引用」扩展阅读**（开发者社区，**不等价**于笔记作者点名的那一篇）：  
  - Agent / 工作流选型与模式全景（腾讯云开发者社区稿件，可作工程语言补包）：https://cloud.tencent.com/developer/article/2617070  
  - 从 Vibe coding 到 Agentic Engineering 的讨论型文章（GLM 视角，可读作「中文圈复述」）：https://cloud.tencent.com/developer/article/2631564  
  - AI 与 Harness 重构软件工程（中文技术圈对 harness 的转述）：https://cloud.tencent.com/developer/article/2647499  

> **写作纪律**：若需要「腾讯团队七版架构推翻」那篇的**逐段引用**，仍应优先向用户拿到**微信首发**或**团队授权 PDF**；避免用二手镜像当真源。

### 2.6 厂外「论坛 / 聚合」线索（Optional）

- Hacker News：搜 `Harness engineering OpenAI`、`progressive disclosure AGENTS.md`，常能翻到工程圈内行讨论。  
- LangChain / LangGraph 文档中 **Deep Agents / harness** 词条：适合做「能力清单」对照（你们 `docs/daily-upgrade/0330/02_AgentHarness全景研究与Butler主线开发指南.md` 已有一层吸收，可不再重复造轮子）。

---

## 3. 头脑风暴 A：Harness Engineer 视角

**角色假设**：你负责的是「Agent 能不能**稳定跑完**」——线程、工具、沙箱、观测、恢复、评审闭环，而不是写业务 `if/else`。

| 编号 | 议题 | 可图 14 的哪一句对齐 |
|------|------|----------------------|
| H1 | **渐进式披露**在实现层长什么样？（入口 MD 短、深文懒加载、工具内再展开） | 「上下文稀缺 → progressive disclosure」 |
| H2 | **推 vs 拉**（图 9）：router 注入规范 vs tool/skill 懒加载——你们 frontdoor 当前是哪一种？混用时会不会图 8 复现？ | 「机械化强制执行」之前先避免机制性噪声 |
| H3 | **Subagent 禁止嵌套**（图 10）与 **多 checker 并行**（图 12）是否冲突？工程上如何用「DAG + 汇总节点」收束？ | OpenAI 文内 agent-to-agent review 可对照 |
| H4 | **三环幻觉治理**（图 11）里，哪一环最适合先变成 **CI/门禁**？（引用锚点、评分表、critical 定义） | 「让每次执行尽量一次做对」 |
| H5 | **观测面给 Agent 读**（OpenAI 文：日志/指标/链路）—Butler 侧最小子集是什么？（避免一上来堆全量可观测性） | harness 作为控制面 |
| H6 | **Ralph loop** 与 **人类注意力**：什么条件下允许「合并不阻断、事后修复」？什么必须硬门禁？ | OpenAI「吞吐改变合并哲学」一节 |

---

## 4. 头脑风暴 B：Butler 产品线视角

**角色假设**：你要的是「用户一次对话就能把事推进一步」，且长期能与 `docs/project-map` 真源对齐。

| 编号 | 议题 | 对照仓库现状（方向性，非审计结论） |
|------|------|--------------------------------------|
| B1 | 「**文档即记忆**」 vs 「recent 热记忆」：哪些必须进冷存储/true source？ | `project-map` / `change_packets` / `AGENTS.md` |
| B2 | **单命令方向盘**（图 15）在 Butler 是哪一个：**chat 模式**、**flow CLI**、还是二者并存时的优先级？ | 见近期 chat/router 与 flow 双轨讨论 |
| B3 | **错误 2 分钟记录**（图 7、17）能否落成单一 artifact 习惯（jsonl / 测试用例 / change packet 小条目）？ | 与 Codex stall、重连超时类问题同一复利逻辑 |
| B4 | **团队扩散**卡点如果真的是「不会描述需求」，产品面要不要提供**任务契约短模板**而不是继续堆系统 prompt？ | 比加几十条 role 规则更便宜 |
| B5 | **多 Agent 审查**（图 12）映射到 Butler：是 flow 内 role、还是 chat-side skill 家族触发？成本与延迟预算？ | 需配合模型分层策略 |

---

## 5. 头脑风暴 C：把两套视角拧成一组「下周可做的实验」（可选）

任选 **1** 个低耦合实验，避免同时开太多坑：

1. **实验 A（拉取优先）**：把一类高频规范从「router 注入」改成「skill 工具拉取」，观测：误判率 / 平均上下文长度 / 用户吐槽是否下降。  
2. **实验 B（真源优先）**：强制一个新约束——所有长结论必须带 `docs/` 或可执行测试的引用锚点，跑一周看交付可信度。  
3. **实验 C（并行审查）**：选一条低成本 PR 类任务试跑「多 checker」：固定检查项用弱模型，合并裁决用强模型，记录 token 与耗时。

---

## 6. 与仓库内既有长文档的衔接（避免重复发明）

以下正文已在 `docs/daily-upgrade/0330/` 做过更系统的 harness 全景吸收，**本轮不重复粘贴**：

- `02_AgentHarness全景研究与Butler主线开发指南.md`  
- `02R_外部Harness映射与能力吸收开发计划.md`  

建议把它当作 **Butler 官方语境下的「 harness 词典」**；本文件则补 **Agentic 工程公众讨论** ↔ **你们私有架构** 的桥。

---

*整理日期：2026-04-03*
