# 多代理 × Harness × 未来趋势：各大家方案对照与头脑风暴（0404）

> **用途**：在 `docs/每日头脑风暴/0403/02_一手资料与学习地图_Agentic与Harness_头脑风暴集.md` 的「链接地图」之上，补一层 **各家在「怎么跑多代理 / 谁掌舵」上的公开解法对照**，并把「下篇」类讨论里常见的 **分水岭判断** 写成可继续实验的议题簇。  
> **边界**：厂商页面会改版；外链以整理时可检索的公开标题为准。下文中对**某篇小红书下篇**的归纳，依据的是**当前对话里已给出的摘要取向**（架构表层 vs 运行环境 / Harness），不是逐字转写原文。

---

## 0. 先给可用结论（本轮沉淀的「一句话」）

1. **分水岭**：多代理竞争正在从「画几张 agent 框图」转向 **谁提供可复用的运行环境（harness）**——线程与工具生命周期、上下文策略、观测与恢复、人类介入点、与仓库真源（`AGENTS.md` / `docs/`）的机械对齐。  
2. **各家并不是同一道题**：有的卖 **方法论 + 产品内嵌循环**（OpenAI），有的卖 **研究与工程上的多路并行 + 强模型分工**（Anthropic），有的卖 **可部署的多代理框架与云运行时**（Google ADK），有的卖 **编排模式库与企业集成面**（Microsoft Agent Framework / Semantic Kernel）。**没有单一赢家模板**，只有与你任务价值、token 预算、合规边界是否匹配。  
3. **中文工程圈**：腾讯开发者社区等更多是 **术语对齐与案例转述**；要与具体署名长文 **逐段对齐**，仍需要首发链接或授权稿（0403 学习地图里已写明纪律）。

---

## 1. 与「Agent 架构下篇」同构的展开（论证骨架）

下列小节是把「多代理、Harness、趋势」拆成 **可核对** 的论点链，便于你后续把原帖截图或段落贴进来做逐句标注。

### 1.1 多代理：三种常见「假问题」

- **假问题 A**：「要不要很多个 bot？」——真正决定成败的往往是 **并行边界、汇总机制、以及子上下文是否隔离**。  
- **假问题 B**：「用哪张 orchestration 图？」——图是文档；**运行时是否支持中断恢复、工具幂等、日志给下一轮 agent 读**才是硬条件。  
- **假问题 C**：「强模型越多越好？」——多代理的公开经验里，**成本与方差**经常同时上升；只适合 **高价值、可并行分解** 的任务族。

### 1.2 Harness：从「套 prompt」到「套工程系统」

把 Harness 想成四层叠起来，讨论会清晰很多：

| 层 | 问句 |
|----|------|
| **意图层** | 人类给的是目标还是步骤？验收标准是否可机械检查？ |
| **上下文层** | 入口短、深文懒加载、规则分层——与 progressive disclosure 同族。 |
| **执行层** | tool/MCP/skill 的边界、超时、重试、并行 DAG 还是串行状态机？ |
| **治理层** | CI、门禁、审计轨迹、哪些失败必须阻断合并 |

### 1.3 趋势：从「单会话智能」到「可运营的智能体栈」

- **产品侧**：同一条能力会出现在 CLI、IDE、Web、移动端；**App Server / JSON-RPC** 这类接口把「智能」从界面里抽出来。  
- **组织侧**：岗位叙事从「写代码」迁移到「设计环境、工具形状、反馈闭环」——与 OpenAI **Harness engineering** 的公开叙述同向。  
- **风险侧**：多代理放大 **工具误用、上下文漂移、不可复现**；需要 **观测面给 agent 读** 与 **人类可介入点** 成对设计。

---

## 2. 各大家「公开解法」对照（一手入口 + 各自解决什么）

> 详细链接表仍以 `0403/02_...md` 为 **主索引**；这里强调 **差异化**，避免重复堆 URL。

### 2.1 OpenAI：Harness engineering + Codex 产品化运行环

**在解决什么**：把软件生产改成 **agent-first**：人类主要负责目标分解、边界与反馈；强调 **仓库真源、渐进式披露、机械规则防漂移、可观测性**。  
**多客户端怎么统一**：公开讨论 **Codex App Server**（双向 JSON-RPC）把 harness 接到 CLI / IDE / Web 等表面。  
**一手入口（与 0403 一致）**：

- Harness engineering：https://openai.com/index/harness-engineering/  
- Unlocking the Codex harness（App Server）：https://openai.com/index/unlocking-the-codex-harness/  
- Unrolling the agent loop：https://openai.com/index/unrolling-the-codex-agent-loop/  
- Execution plans（Cookbook）：https://cookbook.openai.com/articles/codex_exec_plans  

**可记一句**：OpenAI 的「方案」偏 **完整闭环叙事 + 商业产品承载**，适合你对照 Butler 的 **真源文档协议、cli_runner、观测与恢复**。

### 2.2 Anthropic：Effective agents + 多代理研究系统（工程实证）

**在解决什么**：  
- **何时不要上多代理**：workflow 能搞定就不要硬上 autonomous swarm。  
- **何时值得上**：breadth-first、需多路独立检索再汇总的研究型任务；公开材料描述 **lead / subagent 分工、并行、汇总合成**，并强调 **token 与评测方差** 代价。  

**一手入口**：

- Building effective agents：https://www.anthropic.com/research/building-effective-agents  
- How we built our multi-agent research system：https://www.anthropic.com/engineering/built-multi-agent-research-system  
- Writing tools for agents：https://www.anthropic.com/engineering/writing-tools-for-agents  
- Claude Agent SDK：https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk  
- Subagents / Skills（产品文档）：https://code.claude.com/docs/en/sub-agents 、https://code.claude.com/docs/en/skills  

**可记一句**：Anthropic 的「方案」在公开论述里 **更强调约束与工具形状**，多代理部分有 **可引用的工程 postmortem 风格**。

### 2.3 Google：ADK（Agent Development Kit）与云上运行时

**在解决什么**：把 **多代理组合、层级、并行/串行/循环等工作流原语** 做成框架与文档，并对接 **Vertex AI Agent Engine** 等部署与运维故事。公开材料强调 **MCP 工具、多模型后端、本地调试 UI** 等「工程打包」。  

**一手入口（示例）**：

- ADK 概览（Cloud 文档）：https://cloud.google.com/agent-builder/agent-development-kit/overview  
- Google Developers Blog（ADK 介绍）：https://developers.googleblog.com/en/agent-development-kit-easy-to-build-multi-agent-applications  
- 多代理专题文档（ADK docs）：https://google.github.io/adk-docs/agents/multi-agents/  

**可记一句**：Google 的「方案」偏 **框架 + 云路径**，适合你对照「Butler 要不要吞一整段云托管运行时」还是 **自研 orchestrator**。

### 2.4 Microsoft：Semantic Kernel / Agent Framework 编排模式族

**在解决什么**：把多代理协作抽象成 **可切换的 orchestration 模式**（顺序、并发、群聊、handoff、Magentic 类等），与企业集成叙事绑定。  

**一手入口（示例）**：

- Agent Framework 总览：https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/  
- Multi-agent orchestration 博文：https://devblogs.microsoft.com/agent-framework/semantic-kernel-multi-agent-orchestration/  
- 编排文档：https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-orchestration/  

**可记一句**：微软的「方案」偏 **模式库 + 企业开发体验**，适合你对照 flow/campaign 里 **是否要有显式「编排模式」枚举**。

### 2.5 腾讯与中文技术社区（补位，不是替代一手论文）

**在解决什么**：**中文术语对齐、国内业务场景复述、Vibe coding → Agentic Engineering 的二次叙述**。  
**纪律**：若要对齐某篇 **署名首发**（例如笔记里点名的作者稿），仍走 **微信原文 / PDF / 授权转载**；开发者社区文章宜标为 **二手脉络**，见 `0403/02_...md` 2.5 节已有链接与警告。

### 2.6 厂外编排框架（LangGraph 等）——放在哪一层？

- 典型用途：**状态机、检查点、human-in-the-loop** 等与「 harness 执行层」相邻。  
- Butler 仓库内已有 harness 全景吸收：`docs/daily-upgrade/0330/02_AgentHarness全景研究与Butler主线开发指南.md` —— **避免本文件重复粘贴**，需要时只回指。

---

## 3. 对照总表（快速选型脑图）

| 维度 | OpenAI | Anthropic | Google ADK | Microsoft SK |
|------|--------|-----------|------------|----------------|
| 叙事中心 | 人类掌舵 + 仓库真源 + 产品内 harness | 有效代理约束 + 研究型多代理实证 | 可组合代理 + 云部署路径 | 编排模式 + 企业集成 |
| 多代理强调点 | agent loop 与客户端统一 | 并行子代理 + 汇总 + 成本提醒 | 层级 / 并行 / 循环等工作流原语 | 群聊、handoff、并发等模式 |
| 与你最相关的 Butler 映射 | `AGENTS.md`、`docs/project-map`、cli 接入 | Subagent/Skill 形状、工具错误即修复信号 | 若考虑云托管 agent runtime | flow/campaign 编排抽象 |

---

## 4. 头脑风暴议题簇（接续 0403，偏「下篇」）

**D1. 环境优先**：如果明天只能升级一层，你选 **工具+MCP 治理**、**上下文渐进**、还是 **观测+恢复**？为什么？  
**D2. 多代理准入**：用一条 **任务价值 / token 预算 / 可并行度** 公式写「准入门槛」，避免「为酷而 swarm」。  
**D3. 汇总权**：并行子代理之后，**谁有写权限**（单一 committer？还是双模型 review？）——对照 OpenAI 文内 agent-to-agent review 的治理隐喻。  
**D4. 中文素材真源**：下一篇小红书/飞书转述，**第一张图**就应标出：哪些是 **一手链接**、哪些是 **观点复述**。  
**D5. 与长文衔接**：`0403/03_从二阶控制论到AgentTeam_...md` 里的「观察—控制—建模外扩」，在本篇对应为：**Harness = 把控制回路嵌进软件工程**。

---

## 5. 本轮执行说明（诚实边界）

- **已做**：新建本文件；对照与链接以 **0403/02** 主索引为底，并补充 **Google ADK、Microsoft Agent Framework** 的公开入口（便于和 OpenAI / Anthropic 并排放）。  
- **未做**：未在本机重新抓取你提供的 `xhslink.com/o/9bQ3SlW3Oi6` 全文；文中对「下篇」的展开是 **与对话摘要同构的论证骨架**，方便你后续贴原文逐段「钉真源」。  
- **建议下一步**：若你补 **原帖长截图或导出 Markdown**，可在本节下追加「原文锚点 + 页码/段落号」表，把 D4 一次做实。

---

*整理日期：2026-04-04*
