# AI 技术博客地图 + 每日巡检任务书

> 最后更新：2026-03-18
> 用途：指导「每日访问 AI 技术博客、整理发展趋势、沉淀头脑风暴素材」的工作。
> 目标不是机械转述文章，而是持续提炼对 **个人科研 agent / Butler / harness engineering / context engineering / multi-agent 编排** 最有价值的新信号。

---

## 一、怎么用这份地图

每日巡检时，重点抓三类东西：

### 1. 新能力

- 新的 agent API / SDK 变更
- eval / tracing / observability 工具
- MCP / tool use 协议更新
- runtime / memory / security boundary 变化

### 2. 新范式

- context engineering / harness engineering
- multi-agent / subagent / agent team
- planner / executor / verifier 模式演进
- 自我进化 / 竞技场范式

### 3. 新信号

- 哪类组织开始把 agent 从 demo 推到 production
- 哪些厂商反复强调同一种架构模式
- 哪些看似「产品更新」的内容，其实代表新的系统范式

---

## 二、站点分层逻辑

5 层分类，因为不同来源的信号性质不同：

| 层级 | 适合看什么 |
|------|-----------|
| **前沿实验室** | 方向和范式 |
| **应用 / Agent 平台** | 落地方法 |
| **开源生态** | 扩散趋势 |
| **工程基础设施** | runtime / security / deployment |
| **学术 / 个人观察者** | 抽象与反思 |

---

## 三、S 级：每日必看

### 1. OpenAI

- [OpenAI Newsroom](https://openai.com/newsroom/)
- [OpenAI Research](https://openai.com/research/)
- [OpenAI Engineering](https://openai.com/news/engineering/)

**重点**：deep research / AgentKit / harness engineering / evals / safety / runtime

### 2. Anthropic

- [Anthropic Engineering](https://www.anthropic.com/engineering)
- [Anthropic Research](https://www.anthropic.com/research/)

**重点**：effective harnesses / multi-agent research system / context engineering / agent evals / long-running agents

### 3. LangChain / LangGraph / LangSmith

- [LangChain Blog](https://blog.langchain.com/)
- [LangChain](https://www.langchain.com/)

**重点**：agent engineering / deep agents / context management / multi-agent / observability / deployment

### 4. Google DeepMind

- [DeepMind Blog](https://deepmind.google/blog/)
- [DeepMind Research](https://deepmind.google/research/)

**重点**：AI for science / robotics / reasoning / autonomous systems / research agents

### 5. Hugging Face

- [Hugging Face Blog](https://huggingface.co/blog)

**重点**：open-source agent ecosystem / benchmark / tool/library 演化 / robotics / science / community trends

---

## 四、A 级：隔天看 / 重点周更

### 1. Vercel

- [Vercel Blog](https://vercel.com/blog/)
- [Vercel Agents](https://vercel.com/agents/)

**重点**：AI SDK / agent security boundaries / tool 数量与上下文效率 / AGENTS.md / no-nonsense agent development

### 2. GitHub Blog

- [GitHub Blog AI & ML](https://github.blog/ai-and-ml/)

**重点**：context engineering / Copilot 工作流 / custom instructions / reusable prompts / custom agents

### 3. Microsoft Research

- [MS Research Blog](https://www.microsoft.com/en-us/research/blog)

**重点**：agents for real work / verifier / multimodal reasoning / enterprise agent patterns

### 4. Mistral

- [Mistral News](https://mistral.ai/news)

**重点**：reasoning / coding agent / studio/platform 化 / open-weight 生态信号

### 5. NVIDIA

- [NVIDIA Blog](https://blogs.nvidia.com/blog/)

**重点**：agentic AI infrastructure / long-context support / inference runtime / deployment / optimization

---

## 五、B 级：每周扫一到两次

### 1. BAIR Blog

- [BAIR Blog](https://bair.berkeley.edu/blog/)

**重点**：embodied agents / RL deployment / persona / social agents / 学术框架

### 2. 个人工程/研究博客

- [Hamel's Blog](https://hamel.dev/blog/)

**重点**：evals / agent debugging / MCP / harness engineering / how to teach coding agents

---

## 六、程序化巡检清单

```yaml
daily_sources:
  frontier_labs:
    - name: OpenAI Newsroom
      url: https://openai.com/newsroom/
    - name: OpenAI Research
      url: https://openai.com/research/
    - name: OpenAI Engineering
      url: https://openai.com/news/engineering/
    - name: Anthropic Engineering
      url: https://www.anthropic.com/engineering
    - name: Anthropic Research
      url: https://www.anthropic.com/research/
    - name: Google DeepMind Blog
      url: https://deepmind.google/blog/
    - name: Google DeepMind Research
      url: https://deepmind.google/research/

  agent_platforms:
    - name: LangChain Blog
      url: https://blog.langchain.com/
    - name: LangChain
      url: https://www.langchain.com/
    - name: Vercel Blog
      url: https://vercel.com/blog/
    - name: Vercel Agents
      url: https://vercel.com/agents/
    - name: GitHub Blog AI & ML
      url: https://github.blog/ai-and-ml/

  open_ecosystem:
    - name: Hugging Face Blog
      url: https://huggingface.co/blog
    - name: Mistral News
      url: https://mistral.ai/news

  infra_and_research:
    - name: Microsoft Research Blog
      url: https://www.microsoft.com/en-us/research/blog
    - name: NVIDIA Blog
      url: https://blogs.nvidia.com/blog/
    - name: BAIR Blog
      url: https://bair.berkeley.edu/blog/

weekly_personal_watchlist:
  - name: Hamel's Blog
    url: https://hamel.dev/blog/
```

---

## 七、巡检产出规范

每次巡检的产出应直接进入 BrainStorm 体系：

| 发现类型 | 落盘位置 | 格式 |
|---------|---------|------|
| 值得深读的文章 | `BrainStorm/Raw/日期_来源_主题.md` | 标题 + 链接 + 核心摘要 + 与主线的关联 |
| 可更新已有主线的新证据 | 直接追加到 `Insights/mainline/对应主线.md` | 以新章节形式追加，标注来源和日期 |
| 全新主题方向 | 先记 Raw，累积 3+ 篇后考虑开新主线 | — |

**关键原则**：

1. **不抄文章**——只提炼对 Butler / 个人科研 最有价值的信号
2. **直接关联主线**——每条发现标注它属于哪条主线（①-⑩）
3. **累积再归并**——不为单篇文章开新 Insight；累积同主题素材后直接更新主线文档
