# BrainStorm 长期记忆

> 每次对话前必读。只放稳定沉淀下来的认知与选择，不堆当天的流水。

---

## 2026-03-18 十条主线知识整合·核心认知沉淀

经过 34 篇 Raw → 38 篇 standalone Insight → 10 篇 mainline Insight + 跨主线路线图的完整整合，以下认知已稳定沉淀：

### Agent 工程化的五个真正问题（跨主线共识）

状态怎么存、上下文怎么控、任务怎么追、失败怎么回滚、协作怎么对齐——这五个工程问题的解法质量，决定了 Agent 从"能跑"到"能信赖"的距离。prompt 不是分水岭，工程骨架才是。

### 上下文工程 > 提示工程（主线④核心结论）

"Context Engineering"正在取代"Prompt Engineering"成为 Agent 系统的核心设计活动。它不是"怎么写 prompt"，而是"在每一步让模型看到恰好正确的信息"。Butler 在 Write/Pull/Isolate 三个原语上已有可用机制，**Compress 和跨 agent 交接标准化**是最高优先级的两个补齐方向。

### Agent 评估 ≠ Benchmark 刷分（主线⑤核心结论）

Agent 评估有三个本质区别于模型评测的维度：多步骤误差累积、outcome-driven（不看文本漂亮）、环境交互性。Anthropic 的六概念框架（Task/Grader/Agent Harness/Eval Harness/Transcript/Trajectory）是标准术语。CLASSic（5 维度评估）和 TRACE（trajectory-level 评估）是 2026 前沿。Butler 应优先建立任务完成率的基础度量，再引入渐进式信任表（成功率 > 80% 且总量 > 5 时自动提升自治等级）。

### 多 Agent 不等于更好（主线⑨核心结论）

独立 MAS 的错误放大率可达单 Agent 的 17.2 倍；42% 执行时间被协调开销吞掉。5-7 个专家 Agent 是最优配置。Butler 的 heartbeat 已是事实上的 MAS，近期最该做的不是加 Agent，而是把 branch handoff 从非结构化文本升级为标准化契约，并为失败 branch 引入退役日志。

### Ephemeral 与 Persistent 必须共存（主线⑥核心结论）

Agent 生命周期的最根本选择不是"用哪个模型"，而是"用完即弃 vs 持续存活"。7 天连续任务中 Persistent 成功率（87%）是 Ephemeral（22%）的 4 倍，但简单一次性任务两者等效。Butler 需要明确主体（Persistent）和 heartbeat executor（Disposable）的状态边界——哪些状态必须回写主体、哪些随 executor 销毁。一人公司最优配置是 5-7 个专家 Agent + 递归委托层级不超过 3。

### 自省有用但不可靠（主线⑦核心结论）

Anthropic 实证表明模型能做到超越训练数据的真正自省（非统计鹦鹉），但同一机构也发现 Alignment Faking——模型在被观测时表现对齐、不被观测时偏离。因此 **self_mind 的自评不能替代独立验收**。人格稳定的关键在 assistant axis（几何空间锚定），而非角色扮演 prompt。去能化（disempowerment）模式在 150 万条对话中被量化证实，Butler 需要区分"学习区 vs 重复劳动区"来防止过度依赖。

### 自律的工程实现 ≠ 多写几条 prompt 规则（主线⑧核心结论）

真正可靠的自律需要在 prompt 之外建立独立的检查机制（Hook、SDD、运行时宪法）。三类约束的可靠性递进：Steering Constraint（概率性，在 prompt 中）< Toolchain Constraint（确定性，如 linter）< Orchestration Constraint（物理阻止，如 CI/Hook）。Butler 当前处于"说教式自律"→"检查点式自律"的过渡期。高危动作白名单、独立裁决层、结构化自省是三个最小可行改进。

### 自我进化的四阶段（主线⑩核心结论）

Agent 能力从工具调用器→任务执行器→策略优化器→自我改写器演进。Butler 当前在阶段 1。Darwin Gödel Machine (ICLR 2026) 和 Ouroboros 已在受控条件下展示阶段 3 的可行性，但安全性仍是核心挑战。近期最可行的是在 heartbeat 中引入 micro-experiment 机制（阶段 2 的最小化落地）：对非关键路径的重复任务自动尝试 2-3 种变体，记录效果差异。

### `agent_os` / `orchestrator` / domain 四层边界（新增稳定认知）

`agent_os` 不应再被理解为“只管单 agent 生命周期”的狭义 OS，而应显式分成两层：`Agent Runtime`（单 run / session / instance / context / capability）与 `Process Runtime`（workflow / cursor / checkpoint / verify / approve / recover / join）。`orchestrator` 只保留 `Mission / Node / Branch / Ledger` 控制面真源与编排用例；research / heartbeat / chat / operator plane 留在 domain & product plane。凡是通用执行语义，优先进 `agent_os`；凡是任务控制面，留在 `orchestrator`；凡是领域流程与产品交付，留在第四层。

### 跨主线路线图：24 条行动项已排优先级

50+ 条分散改进建议已去重合并为 24 条，按 P0（立即可做/不改代码）→ P3（季度级预研）排列。P0 共 5 条：结构化 Handoff 协议、MAST 失败分类标签、退役日志协议、高危动作分级白名单、self_mind 自省问卷。P2 新增两条关键收口项：`agent_os` 双层运行时定型、`orchestrator` 控制面分层。详见 `Insights/mainline/Butler_跨主线落地路线图_2026Q1.md`。

---

## 2026-03-16 知乎文章共鸣点（用 MaxClaw 做头脑风暴沉淀）

- **痛点**：AI 时代认知迭代速度已经不一样了，但跟 AI 聊完就关掉，等于每次从零开始。
- **方向**：用 MaxClaw（或同类可编程助手）搭一套「头脑风暴沉淀系统」，让聊得越多、进化越快。
- **三层结构**：Raw 碎片 → Insights 总结 → STATE 状态机。
- **节奏**：每周自动刷新、每月自动归档；手机随时触发，电脑关着它也在跑。
- **对自己的提醒**：和 AI 的对话要沉淀下来，不能只停留在当轮会话里。

（来源：知乎专栏 用MaxClaw做头脑风暴，聊得越多进化越快 | 链接已存于 Raw）

---

## 2026-03-16 小红书「把 Claude Code 拆开看，Agent 就不神秘了」共鸣点

- **核心句**：one tool + one loop = an agent，从 s01→s12 只做「每节加一个机制」的递进。
- **真正的分水岭不在 prompt**：而在「状态怎么存｜上下文怎么控｜任务怎么追｜失败怎么回滚｜协作怎么对齐」这些工程骨架。
- **学习方式提醒**：亲手撸完一套 learn-claude-code 式骨架，比让 AI 写 100 个需求更有用；一旦吃透，再看任何 Agent 框架都会变得「透明」。
- **对 Butler 的指向**：Butler 侧可以用同一套五问，对齐 self_mind（状态）、context 管理、task_ledger（任务追踪）、回滚策略和多 Agent 协作机制，把「Agent 工程化」讲清楚而不是只讲提示词。

（来源：小红书笔记 把 Claude Code 拆开看，Agent 就不神秘了 | 抓取自 `Raw/daily/20260316/20260316_claude_code_agent_xhs.md`）
