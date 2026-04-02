# Agency Agents —— Persona-as-Markdown 框架与 Swarm 编排机制 Insight

> 来源 Raw：`Raw/daily/20260318/20260318_github_agency_agents_note.md`  
> 提炼时间：2026-03-18  
> 关联主线：① Harness Engineering · ② Agent 架构原则与模式 · ⑨ MAS 与协作模式

---

## 1. 核心洞察：Persona-as-Markdown 是一种轻量级 Harness

agency-agents 本质上是一个 **静态 Harness 层**——它不控制运行时，但通过 Markdown 系统提示词定义了每个 Agent 的：
- **行为边界**（Critical Rules: ✅/⚠️/🚫 三级约束）
- **决策流程**（Workflow Process）
- **质量闸门**（Success Metrics）
- **交付规范**（Deliverables + 代码示例）

这与 Harness Engineering 主线中识别的四层架构形成有趣映射：

| Harness 四层 | agency-agents 对应 | 实现程度 |
|-------------|-------------------|---------|
| **编排层** | Swarm Builder + Nexus Exercise | ⚠️ 实验中 |
| **工具层** | IDE 原生工具（Claude Code/Cursor 内置） | ✅ 直接复用 |
| **约束层** | Critical Rules + 行为边界 | ✅ Markdown 静态定义 |
| **观测层** | 无 | ❌ 完全缺失 |

**关键判断**：agency-agents 在约束层做到了极致的轻量化（一个 Markdown 文件 = 一个约束完备的 Agent），但完全没有运行时的观测和反馈闭环。

---

## 2. 与 autoresearch / AutoResearchClaw 的三角对照

| 维度 | agency-agents | autoresearch (Karpathy) | AutoResearchClaw |
|------|--------------|------------------------|------------------|
| **Harness 风格** | Persona 注入式（静态约束） | 极简约束式（3文件/1指标） | 全管线编排式（23 stage/8 phase） |
| **Agent 数量** | 112+ persona，按需激活 | 1 个主循环 agent | 3 个多Agent子系统 |
| **编排方式** | 用户手动选择 / Swarm（实验） | program.md 即编排 | Stage-Gated Pipeline + MetaClaw 元学习 |
| **自学习** | ❌ 无 | 有限（5分钟预算内迭代） | ✅ MetaClaw 跨任务元学习 |
| **适用场景** | 软件开发全生命周期 | 科研实验探索 | 科研论文全管线 |
| **复杂度** | 低（MD文件） | 极低 | 极高（23 stage） |

**三角启示**：三者分别代表了 Agent 定义的三种粒度——
1. **Persona 粒度**（agency-agents）：定义"谁来做"，不定义"怎么做"
2. **约束粒度**（autoresearch）：定义"在什么框里做"，不定义"谁做"
3. **流程粒度**（AutoResearchClaw）：定义完整的"谁做 × 怎么做 × 做到什么程度才过门"

Butler 当前在约束粒度和流程粒度之间，但 Persona 粒度的经验可以补充进 skill/sub-agent 定义规范。

---

## 3. Agent 定义的六要素模型

agency-agents 沉淀出的 Agent 定义六要素值得作为通用参考：

```
┌─────────────────────────────────────────┐
│  1. Identity Traits   — 谁？性格/思维方式  │
│  2. Core Mission      — 干什么？职责边界    │
│  3. Success Metrics   — 做到什么算好？      │
│  4. Critical Rules    — 绝对不能做什么？     │
│  5. Workflow Process  — 怎么做？决策链      │
│  6. Deliverables      — 交什么？示例/模板    │
└─────────────────────────────────────────┘
```

**对比 Butler sub-agent 现状**：

| 六要素 | Butler sub-agent 覆盖 | 差距 |
|--------|---------------------|------|
| Identity | ✅ 有角色描述 | — |
| Mission | ✅ 有职责说明 | — |
| **Success Metrics** | ⚠️ 多数缺失 | 建议补充 |
| Critical Rules | ✅ 有约束 | — |
| Workflow | ✅ 有流程 | — |
| **Deliverables** | ⚠️ 多数隐含 | 建议显式化 |

---

## 4. Swarm 编排的 Registry 架构

PR #117 暴露的 Swarm 编排管线：

```
Agent Markdown Files
       ↓
  slugify + parse YAML frontmatter
       ↓
  Agent Registry (内存索引)
       ↓
  Loader API: loadAgent(slug) / listAgents(filter)
       ↓
  Swarm Builder: buildSwarm(agentSlugs[], orchestrationRules)
       ↓
  输出: system_prompt + metadata → IDE / CI / npm consumer
```

**与 Butler heartbeat planner 的对照**：
- agency-agents 的 Registry ≈ Butler 的 skill shortlist + sub-agent 目录
- agency-agents 的 Loader ≈ Butler 的 "先看 skill 目录是否命中"
- agency-agents 的 Swarm Builder ≈ Butler 的 planner 选择 sub-agent/team 组合
- **关键差异**：agency-agents 是无状态的（每次重新加载），Butler 是有状态的（task_ledger + 记忆）

---

## 5. 52K Stars 的增长逻辑

- **极低贡献门槛**：新增 Agent = 提交一个 Markdown PR，不需要写任何代码
- **即时可用**：`./scripts/install-cursor.sh` 一行命令完成所有 Agent 注入
- **Reddit 传播**：专业化 Persona 的"人设卖点"在社交媒体上天然有传播力
- **平台中立**：支持 Claude Code / Cursor / Aider / Copilot / Windsurf / Gemini CLI / OpenCode，覆盖几乎所有主流 coding agent

---

## 6. Butler 可行动项

### 短期（可直接做）
1. **为 Butler sub-agent 补充 Success Metrics 和 Deliverables 字段** —— 从 `update-agent.md` 等现有文档中提炼
2. **为 skill/sub-agent 文档增加标准化 YAML frontmatter** —— 至少包含 `name` / `description` / `tags` / `services`，方便 planner 做能力匹配

### 中期（需评估）
3. **参考 Registry 模式，让 planner 能程序化检索 skill/sub-agent 能力** —— 当前是手写 shortlist，未来可自动化
4. **评估 agency-agents 中特定 Persona 对 Butler 的价值** —— 如 Reality Checker、Code Reviewer 等 QA 类 Persona 可能直接借鉴

### 长期（方向参考）
5. **"一个 Markdown 文件 = 一个新能力" 的极简扩展模式** 是 Butler skill 体系的理想态之一

---

## 7. 关键判断总结

> agency-agents 的真正价值不在 112 个 Persona 本身，而在于它证明了：**结构化 Markdown 系统提示词 + 极低贡献门槛 + 多平台注入脚本** 这套组合能在无运行时、无记忆、无编排的情况下，仅靠"约束层"就创造巨大实用价值。
>
> 但它也清晰暴露了纯静态 Persona 的天花板：没有记忆就没有成长，没有编排就没有协作，没有观测就没有质量闭环。Butler 已经在这三个维度领先，agency-agents 能补的是 **Persona 定义规范** 和 **极简扩展模式** 这两块。
