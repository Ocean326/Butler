## 小红书：谈谈 Coding Agent / Nano-Coder / Compaction / JCT / IDE→ADE（按 13 张图直接整理）

## 来源

- 平台：小红书
- note id：`69c099e6000000001a026d68`
- 原始链接：`https://www.xiaohongshu.com/discovery/item/69c099e6000000001a026d68`
- 发布时间：`2026-03-23T09:39:50+08:00`
- 本次整理依据：`BrainStorm/Raw/daily/20260324/images/` 下 13 张本地图
- 图片记录：`BrainStorm/Raw/daily/20260324/xiaohongshu_69c099e6000000001a026d68_ocr.md`
- 首轮抓取 JSON：`BrainStorm/Raw/daily/20260323/xiaohongshu_69c099e6000000001a026d68.json`
- 当前边界：正文不是从 HTML 正文区完整抓下，而是**按 13 张截图人工直接整理**；用于 BrainStorm 研究判断是足够可信的，但不按“逐字校对全文”表述

## 一句话判断

**这条内容真正有价值的，不是“又做了一个 Coding Agent”，而是它把 Coding Agent 拆成了几层非常工程化的东西：ReAct Loop、Context Engineering、MCP / Skills / Subagent / Plan Mode、Compaction、以及最终可能走向的 ADE。**

它本质上是在回答三个问题：

1. Coding Agent 到底由哪些脚手架组成；
2. Agent workload 会把推理系统和指标拉向哪里；
3. 面向 Agent 的开发环境会不会从 `IDE` 演进到 `ADE`。

## 图文整理

### 1. Nano-Coder 被作者当成一个“把 Agent 软件层做全”的练手项目

作者说自己 2026 年初开始做一个叫 `Vibe-AI-Infra` 的周末项目，已经推进到构建 `Coding Agent` 这一步，并提到自己先 vibe 了 `nano-coder`（功能上类似 `Claude Code / Codex`）。

文中列出的 `nano-coder` 当前支持项包括：

- `ReAct Loop`
- `Tools`
- `Skills`
- `MCP`
- `Subagent`
- `Plan mode`
- `Context Compaction`
- `Poor-man's Context Engineering`
- `CLI UX`
- `Logging / Monitoring / Observability`

作者的一个关键感受是：**有了这些工具后，真正的开发时间被显著压缩，中间大量“先停下来理解 AI 写了什么代码”的时间被省掉了。**

### 2. 作者对 Coding Agent 本质的定义：三要素

文中直接给了一个很重要的判断：`Claude Code / Codex / OpenCode` 这一类 Coding Agent，本质上有三个核心要素：

- **大道至简的 `ReAct Loop`**
- **已成艺术的 `Context Engineering`**
- **大力奇迹的 `Large Language Model`**

作者进一步强调：

- `Context Engineering` 决定任务表现的**下限**；
- `LLM` 决定任务表现的**上限**；
- 所谓 `Agent Scaffold / Agent Harness`，本质是把模型从一个聊天机器人，变成一个**功能和目标导向的 Agent**。

这个判断很值得记：**模型不是整个 Agent，真正把模型变成 Agent 的，是外面那层脚手架。**

### 3. 作者自己的工作流：Claude Code + Codex + GLM 混用

图里列出的个人工作流大致是：

1. 同时使用 `Claude Code + GLM + Codex` 开发；
2. 用 `Claude Code` 给项目初始化计划和初始代码；
3. 一句话特性的设计和实现更多交给 `Codex`；
4. 用 `Claude Code /simplify` 优化代码；
5. 用 `Claude Code` 创建一个 `Tech-Doc-Writer Agent` 写文档；
6. `Nano-Coder` 本身使用 `GLM-5`。

这段信息的价值不在于具体 vendor，而在于：**作者已经把多模型、多角色分工当成默认工作方式，而不是单模型包打天下。**

### 4. 作者眼里的 Nano-Coder 构建顺序，本质是在逐层补齐 Agent Harness

文中把自己的构建过程拆成了几步：

1. 初始化 `Repo`，搭 `CI/CD`，补基础 `Logging/Monitoring`；
2. 初始化 `ReAct Agent Loop`，先跑通“LLM + tool 调用”的最小循环；
3. 加更多 built-in tools，例如读文件、写文件、执行 `Bash`；
4. 加 `MCP` 支持，让 coder 启动时和外部 `MCP Server` 握手，把外部 tools 纳入能力面；
5. 加 `Skills` 支持，把 `prompt + 示例` 封装成可读取、可渐进暴露的能力资产；
6. 做更好的 `CLI UX` 和 slash menu，例如 live markdown rendering、live status、help、`/context`；
7. 加 `Context Compaction` 支持；
8. 加 `Subagent` 支持；
9. 加 `/plan mode` 支持。

这组顺序很说明问题：**作者不是把 Coding Agent 看成一个“大模型 UI”，而是看成一套逐层长出来的运行时。**

### 5. `Skills` 和 `CLI UX` 在作者这里不是边角料，而是核心工程件

图中有两段非常值得单独记：

#### 5.1 `Skills` 是 prompt 与样例的封装，也是运行时暴露策略的一部分

作者写到，`Skills` 本质是一些 `Prompt` 和样例的封装；从开发角度看，关键不只是“能读 skill 文件夹”，而是要支持以 `Progressive Disclosure` 的方式使用 skill。

作者还明确提到一些设计取舍问题：

- 默认的 skill catalog 要不要全放进 system prompt；
- 动态加载的 `skill.md` 和文件在后续对话时要不要保留；
- 这些做法是否只是一些 ablation。

也就是说，**skill 不是静态文档堆，而是上下文编排策略的一部分。**

#### 5.2 `CLI UX` 是容易被忽略、但非常值得投入的层

作者认为一句话式需求、live rendering、状态呈现、help、上下文查看等 CLI 体验，是程序员容易忽略但很值得投资的东西。

这背后其实是一个产品判断：**Coding Agent 不只比模型，也比运行时交互质量。**

### 6. `Context Compaction` 被作者视为整个 Coder 里技术含量最高的部分之一

作者说 `Compaction` 是支持 long-running agent 的核心组件：通过压缩长上下文，让 agent 可以继续和 LLM 对话。

文中给出的实现思路接近：

1. 先 `prune` 一些较长的 tool output；
2. 再用 `LLM`（这里是 `GLM-5`）做总结压缩；
3. 最后把压缩结果按顺序重新组装进上下文。

作者明确判断：

- `Compaction` 需要一定算法设计；
- 压缩策略会直接影响任务质量和效率；
- 这部分很像 `OpenCode` 的一些思路；
- 当前这个实现几乎是“直接可落地”的方案，核心仍依赖 LLM 的总结能力。

### 7. `Subagent` 和 `Plan Mode` 被视为高频且重要的控制结构

文中提到：

- `Subagent` 让 parent agent 可以在一个 turn 内生成并等待多个 subagents；
- 每个 subagent 有自己的上下文窗口，但共享一套 `skills / tools / mcp`；
- 模型如果被明确提示“使用几个 subagent 干 XX”，通常能较好调用；如果不明确说，往往不会主动用。

对于 `Plan Mode`，作者的理解是：

- 先让模型给计划；
- 操作者 review；
- 同意后再执行。

并且他把 `Plan Mode` 的难点落在两个点上：

- 一个新的 prompt；
- 只读权限。

更进一步，他认为这里还有研究问题：**模型在执行过程中到底能多深地 stick to the plan，以及面对“计划赶不上变化”时如何调整。**

### 8. 第二部分的核心：Agent 的执行时间正在拉长，Compaction 变成基础设施

作者把 Agent Task Duration 分成三个阶段：

- `Seconds Era (2019~2022)`
- `Minutes Era (2023~2024)`
- `Hours Era (2025~)`

他的判断是：Agent 的执行时间在最近几个月增长很快，而背后至少有两个关键技术：

- 大模型本身能力提升；
- Coding Agent 中的 `Context Compaction` / 上下文压缩。

图中一个非常具体的说法是：`Compaction` 可以把上下文从比如 `150K` 压缩到 `25K`，从而允许单个 Agent 持续运行。

### 9. 压缩不是免费午餐，最终要看 E2E 结果

作者对 `Compaction` 的深入判断主要有两点：

- 任何人为策略的引入，都可能导致一定信息损失，未来更理想的是模型自己主导压缩策略；
- 如果把 `KV` 压缩看成 `Intra-Session Sparsity`，那么 `Compaction` 可以看作 `Inter-Session Sparsity`，两种 sparsity 都会引入 loss。

所以结论不是“压得越狠越好”，而是：**不管采用什么压缩策略，最后都应该回到端到端结果去评估。**

### 10. 从推理系统角度，`TTFT / TPOT` 不再够，`JCT` 更重要

作者提到自己从 2023 年开始做大模型推理，经历了 `PD 分离` 和 `Prefix Caching`，也感受到推理负载发生了结构性变化。

文中几个关键点：

- 从用户和 MaaS 厂商视角，`Prefill` 是重点；
- 从 Serving 视角，`P` 侧的 `KV Cache` 复用越来越重要；
- 对 Coding Agent 来说，`TTFT` 和 `TPOT` 变成了“内科指标”；
- 用户并不关心中间结果，更关心最终结果，以及 `Job Completion Time (JCT)`。

这是一个很重要的视角切换：**Agent workload 会把系统优化目标，从 token 级在线指标，推向任务级完成指标。**

### 11. 作者因此提出 `Model-System-Codesign`

文中有一句非常关键的话：

**在这样的成本结构下，模型结构要不要改？更重要的是要结合 workload 变化去改底层组件。**

这就落到他提的 `Model-System-Codesign`：

- 模型能力；
- 推理系统；
- Agent 工作负载；

这三者不该割裂优化，而应该联动看。

### 12. Coding Agent 还能反向定义“模型到底该会什么”

作者把 `Coding Agent` 放在“模型消费端”的位置来理解，并说：通过 vibe 一个 `nano coding agent`，自己反而更清楚模型应该具备哪些能力。

文中列出的 Coding Agent 必备能力有：

- `reasoning`
- `tool use`
- `multi-step`
- `agent swarm`
- `...`

作者还把这条线和一些开源模型报告、以及 `Codex Research Engineer` 的岗位描述联系起来看。含义很直接：**Agent 不是模型能力的下游包装，而是在反向暴露模型缺什么。**

### 13. 最后一个很强的判断：开发环境会从 `IDE` 走向 `ADE`

作者提出：

- `IDE` 是帮助碳基程序员编写、执行、测试代码；
- `ADE`（Agent Development Environment）是帮助硅基 Agent 编写、执行、测试代码。

他认为当前 `IDE / CLI-based coding agent` 其实还是沿袭了人类开发者的工作习惯，而真正 agent-first 的开发范式可能还需要一套 built-for-agent 的环境。

文中点到的差异包括：

- agent 的权限管理；
- 多 agent 之间可见的状态；
- agent 之间的交互方式；
- 更 agent-first / prompt-first 的 UX。

他还拿 `Codex Mac App` 举例，认为那种界面就是一种尝试：**不是 project-files-first，而是 prompt-first。**

## 对 Butler / BrainStorm 的直接启发

### 1. 不要把 Coding Agent 理解成“一个强模型 + 一个聊天框”

这条内容再次证明，真正决定可用性的，往往是外面那层：

- loop 怎么组织；
- tool 怎么接；
- skill 怎么暴露；
- context 怎么压；
- subagent / plan 怎么控制；
- UX 怎么承接。

### 2. `Compaction` 更像系统能力，不只是 prompt 技巧

这条内容最值得保留的，不是“可以总结上下文”，而是：

- 长时间运行 agent 一定会逼出 compaction；
- compaction 会牵动质量、成本、持续执行能力；
- 它最后必须回到任务级结果来评估。

### 3. 评估指标应该从 token 级走向任务级

如果面向的是 Agent workload，那么：

- `TTFT / TPOT` 仍然重要；
- 但更关键的会是 `JCT`、端到端成功率、以及任务成本结构。

### 4. `IDE → ADE` 是值得长期跟的一条产品主线

这条判断和 Butler 非常相关，因为它触发的问题不是“再做一个 IDE”，而是：

- 如何让 agent 有自己的工作台；
- 如何展示 agent 状态；
- 如何做 agent 权限与协作；
- 如何让交互从 file-first 转向 task / prompt / state-first。

## 可继续展开的 BrainStorm 问题

- `Compaction` 的策略评估，应该用什么 E2E 指标做基准？
- `Subagent` 的触发是显式指令更好，还是让模型学会自主调用更好？
- `Plan Mode` 的价值上限，到底取决于计划质量、执行约束，还是 review 机制？
- 面向 Agent 的 `ADE`，最小必备界面元素到底是什么：权限、状态、任务、日志、协作，还是别的？
- 如果把 Coding Agent 放到“模型消费端”，它能否反向成为模型能力设计的测试台？

## 当前状态

- **这次已不再停留在分享页标题和标签。**
- 我已经按 `BrainStorm/Raw/daily/20260324/images/` 下的 13 张图，直接把正文主干整理出来。
- 因此这版比旧版“只基于分享页 + 猜测”的可信度高很多。
- 但它仍然是**研究整理稿**，不是逐字逐句全文转写稿。
