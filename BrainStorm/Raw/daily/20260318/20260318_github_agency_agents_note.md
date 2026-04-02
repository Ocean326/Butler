# Agency Agents —— 112+ 专业化 AI Agent Persona 框架

> 来源：GitHub `msitarzewski/agency-agents`  
> 调研时间：2026-03-18  
> 项目地址：https://github.com/msitarzewski/agency-agents  
> 许可证：未明确标注 | ⭐ 52,000+ | 创建：2025-03-13 | 最后活跃：2026-03-15

---

## 一句话定位

"A complete AI agency at your fingertips." —— 通过 **Markdown 系统提示词** 将通用 IDE 编码助手（Claude Code / Cursor / Aider / Copilot / Windsurf / Gemini CLI / OpenCode）变成 112+ 个领域专家 Persona，每个 Persona 有独立身份、任务流程、成功指标和交付物定义。

---

## 核心设计哲学

| 维度 | 要点 |
|------|------|
| **角色专精** | 不做通才 LLM，每个 Agent 深耕单一专业域 |
| **Markdown-as-Code** | Agent 定义全部是纯 Markdown 文件，可读、可版本控制、可 PR 贡献 |
| **Platform Agnostic** | 一套 Persona 定义 → 脚本自动转换为 Cursor `.mdc` / Claude Code `.md` / Aider `CONVENTIONS.md` |
| **结构化提示词** | 每个 Agent 包含：身份特质 → 核心使命 → 成功指标 → 关键规则 → 工作流程 → 交付物示例 |
| **减少幻觉** | 通过缩窄上下文到特定领域，显著降低通用 LLM 的编造率 |

---

## 组织架构（模拟真实公司分工）

### 工程部 (Engineering)
Frontend Developer / Backend Architect / Mobile App Builder / AI Engineer / DevOps Automator / Rapid Prototyper / Senior Developer / Security Engineer / Autonomous Optimization Architect / Embedded Firmware Engineer / Incident Response Commander / Solidity Smart Contract Engineer / Technical Writer / Threat Detection Engineer / Code Reviewer / Database Optimizer / Git Workflow Master / Software Architect / Site Reliability Engineer / AI Data Remediation Engineer / Data Engineer

### 设计部 (Design)
UI Designer / UX Researcher / UX Architect / Brand Guardian / Visual Storyteller / Whimsy Injector / Image Prompt Engineer / Inclusive Visuals Specialist

### 产品部 (Product)
Sprint Prioritizer / Trend Researcher / Feedback Synthesizer / Behavioral Nudge Engine / Product Manager

### 市场部 (Marketing)
Growth Hacker / Content Creator / Twitter Engager / TikTok Strategist / Instagram Curator / Reddit Community Builder / App Store Optimizer / Social Media Strategist / LinkedIn Content Creator / SEO Specialist / Podcast Strategist / Book Co-Author / AI Citation Strategist / Cross-Border E-Commerce Specialist

### 销售部 (Sales)
Outbound Strategist / Discovery Coach / Deal Strategist / Sales Engineer / Proposal Strategist / Pipeline Analyst / Account Strategist / Sales Coach

### 质量部 (Quality Assurance)
Evidence Collector / Reality Checker / Test Results Analyzer / Performance Benchmarker / API Tester / Tool Evaluator / Workflow Optimizer / Accessibility Auditor

### 项目管理部 (Project Management)
Studio Producer / Project Shepherd / Studio Operations Manager / Experiment Tracker / Senior Project Manager / Jira Workflow Steward

### 特殊领域
空间计算 / 游戏开发 / 学术世界构建 等新兴方向

---

## 单个 Agent 定义格式

每个 Agent 是一个 Markdown 文件，含 YAML Frontmatter + 结构化正文：

```markdown
---
name: "Backend Architect"
description: "..."
emoji: "🏗️"
vibe: "..."
services: [...]
---

# Backend Architect

## Identity Traits
- 性格、思维模式、沟通风格

## Core Mission
- 职责范围、专精域

## Success Metrics
- 可衡量的输出质量指标

## Critical Rules
- 不可逾越的最佳实践（✅ Always / ⚠️ Ask first / 🚫 Never）

## Workflow Process
- 任务分解、决策链、review 环节

## Deliverables
- 具体交付物示例与代码模板
```

---

## 多 Agent 协作编排

### 并行协作模式
项目提供 "Nexus Spatial Discovery Exercise" 等预设编排，8 个 Agent 并行工作：
- 一个做 API 设计
- 一个做安全审查
- 一个做数据库优化
- 自动协调产出

### Swarm 编排（PR #117，进行中）
- **npm 包** `agency-agents`：TypeScript/Node.js API，支持 loadAgent / listAgents / buildSwarm
- **GitHub Action** `action.yml`：CI/CD 中自动加载 Agent/Swarm，输出 system prompt 和元数据
- **Registry 机制**：slugification → frontmatter parsing → agent loading → swarm orchestration
- **测试覆盖**：vitest 测试 loader / registry / swarm 三层

### 安装集成

```bash
# Claude Code / Copilot
./scripts/install-claude.sh

# Cursor — 生成 .mdc 规则文件
./scripts/install-cursor.sh

# Aider — 编译 CONVENTIONS.md
./scripts/install-aider.sh

# npm（编程接口）
npm install agency-agents
```

---

## 项目演进时间线

| 时间 | 事件 |
|------|------|
| 2025-03 | 项目创建，首批 Agent persona 发布 |
| 2025-10~ | Reddit 社区爆发式增长 |
| 2026-03-10 | PR #117：npm 包 + GitHub Action + Swarm 编排 |
| 2026-03-15 | 最后活跃，52K+ stars，50 contributors |

---

## 与同类项目对照

| 维度 | agency-agents | agency-swarm (VRSEN) | tobias-walle/agency | Butler |
|------|--------------|---------------------|--------------------|----|
| **核心抽象** | Persona Markdown（系统提示词库） | Python 多 Agent 编排框架 | Rust CLI 多 Agent 编排器 | 长期陪伴式 Agent + 心跳 + 记忆 |
| **编排层** | 脚本注入 + Swarm（实验中） | OpenAI Agents SDK + send_message | Git Worktree 隔离 + Tmux | heartbeat + task_ledger + planner |
| **Agent 定义** | Markdown + YAML frontmatter | Python class + Pydantic tools | TOML 配置 + CLI flags | Role markdown + SOUL + skills |
| **协作方式** | IDE 内手动/自动切换 Persona | 框架内 Agent 间消息传递 | 终端 UI 并行任务 | sub-agent + team 层级协作 |
| **平台绑定** | 多平台（Claude/Cursor/Aider/Copilot） | OpenAI 生态 | 多 CLI Agent | 飞书 + Cursor |
| **记忆体系** | 无 | 可选 state persistence | 无 | 三层记忆 + self_mind |
| **star** | 52K+ | 4K+ | ~500 | — |

---

## Butler 视角的启发

### 1. Persona-as-Markdown 与 Butler Role 体系的对照
- agency-agents 的每个 Agent 定义结构（Identity → Mission → Metrics → Rules → Workflow → Deliverables）与 Butler 的 role/sub-agent markdown 天然同构
- **可借鉴**：Success Metrics 和 Deliverables 这两个维度 Butler 当前 role 文档中较薄弱，可考虑补充

### 2. 结构化 Frontmatter 的元数据规范
- YAML frontmatter 中 `emoji` / `vibe` / `services` 等字段提供了 Agent 的快速识别和分类检索能力
- **可借鉴**：Butler 的 sub-agent/skill 文档可统一增加标准化 frontmatter，便于 planner 做能力匹配

### 3. 多平台转换脚本
- 一套 Persona 定义 → 多平台格式的自动转换思路，与 Butler 未来若需支持多 IDE/多前端场景高度相关

### 4. Swarm 编排的演进方向
- PR #117 展示的 Registry → Loader → Swarm Builder 管线，本质上是把"选谁上场"和"怎么协作"编程化
- **对照**：Butler 的 heartbeat planner + task_ledger 已经在做类似的事，但 agency-agents 的 Registry 更接近"能力目录的程序化检索"

### 5. 贡献门槛极低
- 新增 Agent = 提交一个 Markdown 文件的 PR，无需懂代码
- **启发**：Butler 的 skill 体系也可以往这个方向走——让 skill 定义足够轻量，降低扩展门槛

---

## 局限性

1. **无记忆体系**：每次对话都是无状态的，Persona 只提供角色约束，不提供历史上下文
2. **无运行时调度**：没有 heartbeat/planner 等自主调度机制，依赖用户手动选择 Agent
3. **无自省与成长**：Persona 是静态的 Markdown 文件，不会根据交互反馈自我调整
4. **协作编排尚在实验阶段**：Swarm 相关的 npm/GitHub Action 仍在 PR 阶段，未合入主分支
5. **缺乏质量闭环**：虽然有 Reality Checker 等 QA Agent，但没有结构化的评估-反馈-迭代管线
