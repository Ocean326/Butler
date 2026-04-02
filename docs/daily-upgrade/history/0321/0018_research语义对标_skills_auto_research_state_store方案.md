# 0321 research 语义对标：skills / auto-research / state store 方案

更新时间：2026-03-21 00:18
时间标签：0321_0018

## 一、这轮对标要回答什么

在继续补 `scenario instance/state store` 之前，需要先确认三件事：

1. `skills` 在 research 场景里应该扮演什么角色
2. `research workflow` 的 agent 角色应该怎么收口
3. `state store` 到底应该长成“平台态”还是“thread/checkpoint 态”

这轮对标的目的不是搬运别人实现，而是校准 Butler 现在的语义设置，避免后面越做越偏。

---

## 二、外部参考结论

## 2.1 OpenClaw：skills 应该是能力包，不是 workflow 真源

从 OpenClaw 官方 skills 文档看，skills 的核心定义是：

- 每个 skill 是一个目录
- 以 `SKILL.md` 为入口
- 可以有 workspace 级、共享级、bundled 级三层来源
- 多 agent 时支持 per-agent skill 与 shared skill 分层

更重要的是两个约束：

- 第三方 skills 应视为不可信代码
- skill 更适合作为“教 agent 如何用工具的能力包”，而不是 workflow 真源

因此对 Butler 的约束是：

- `skills` 适合作为 research 场景中的“检索能力包 / 文献整理能力包 / 实验执行能力包”
- `skills` 不应该取代 `scenario workflow`
- `scenario instance` 不应该直接等同于“某个 skill 的运行状态”

一句话：

> skill 是可装配能力，不是场景状态真源。

---

## 2.2 LangGraph：可恢复 workflow 的核心是 thread + checkpoint，不是大平台

LangGraph 官方 durable execution 文档给出的核心约束非常直接：

- 要有 persistence / checkpointer
- 要有 thread identifier
- workflow 必须尽量 deterministic / idempotent
- side effect 和非确定操作要被隔离

这对 Butler 的启发非常强：

- `scenario instance` 最应该对齐的是 `thread identifier`
- `state store` 最应该保存的是“这个场景线程当前走到哪、之前决策是什么、最后一次产出是什么”
- 不需要先做大而全 orchestration platform

因此对 Butler 的约束是：

- `scenario_instance_id` 应作为 research 场景线程 id
- `workflow_cursor` 应作为当前线程的最小状态指针
- `entrypoints` 共享同一个 instance，而不是每个入口单独一套 agent

一句话：

> 先把 research 场景做成“有 thread、有 checkpoint 的可接续工作流”，再谈更大的 agent system。

---

## 2.3 AutoRA：research workflow 的核心是 state 累积，不是 agent 数量

AutoRA 官方文档里最有价值的一点是：

- 把研究循环理解为状态 `S`
- 每个组件只返回对状态的增量 `ΔS`
- 整个 research cycle 本质上是状态累积

这正好能修正 Butler 里一个容易走偏的点：

- 不要先堆很多 agent，再找它们怎么协作
- 应先定义 research state，agent 只是对 state 的变换器

因此对 Butler 的约束是：

- `brainstorm / paper_discovery / idea_loop` 都要先有明确的 scenario state
- 每次 invocation 的产出，本质上应该是：
  - 更新 `workflow_cursor`
  - 更新场景 state
  - 追加 step/decision 历史

一句话：

> research agent 的正确抽象首先是 state transformer，其次才是 agent persona。

---

## 2.4 GPT Researcher：research agent 结构应收口成 planner / execution / publisher，而不是泛化多 agent 平台

GPT Researcher 官方 README 给出的架构非常实用：

- planner 生成 research questions
- execution agents 收集信息
- publisher 聚合结果成报告

同时它对 deep research 的描述也很关键：

- tree-like exploration
- configurable depth and breadth
- smart context management across branches

这对 Butler 的启发是：

- `paper_discovery` 不该抽象成一堆随意 agent，而应围绕：
  - topic lock / query planning / search / screening / digest
- `brainstorm` 不该抽象成通用 multi-agent，而应围绕：
  - capture / cluster / expand / converge / archive
- `idea_loop` 不该抽象成 agent 海洋，而应围绕：
  - hypothesis / plan / iterate / verify / recover

一句话：

> 真正影响效果的不是 agent 数量，而是 planner-execution-publisher 这种清晰的阶段语义。

---

## 三、对 Butler 当前语义的校准

综合上面四类参考，Butler 当前这套 research 语义需要明确成下面这样。

## 3.1 skills 的语义

`skills` 只承担：

- 搜索源接入
- 文献抓取与清洗
- 文档整理
- 代码实验或验证
- 输出格式化

`skills` 不承担：

- 场景生命周期
- workflow 状态真源
- 跨入口 continuity

## 3.2 scenario 的语义

`scenario` 才是 research 的工作流真源。

它负责：

- step 序列
- step 语义
- output contract
- handoff / decision 边界

## 3.3 scenario instance 的语义

`scenario instance` 是：

- 某个 scenario 在某条线程上的运行态

它至少需要保存：

- `scenario_instance_id`
- `unit_id / scenario_id / workflow_id`
- `session_id / task_id / workspace`
- `workflow_cursor`
- `current step`
- `latest decision`
- `entrypoints_seen`
- `state`
- `recent receipts`

## 3.4 agent 的语义

对 research 这条线来说，当前 agent 设计不应该继续泛化成平台，而应收口成：

- planner-like step
- execution-like step
- verification/publisher-like step

也就是说：

- agent role 是 step 语义的投影
- 不是先定义一堆 agent，再让 workflow 去适配它们

---

## 四、对 scenario instance/state store 的直接设计要求

基于以上对标，这轮 state store 应满足：

1. 有稳定 `scenario_instance_id`
2. 支持按显式 id / session_id / task_id 找回同一个 instance
3. 保存 `workflow_cursor`
4. 保存场景级 `state`
5. 保存 `active_step / output_template / last receipts`
6. 追加事件日志，便于回放和恢复

但明确不做：

1. 不做通用数据库层
2. 不做全局 workflow engine
3. 不做复杂 branch merge
4. 不做真正执行 side effects 的恢复重放

一句话：

> Butler 现在需要的是 research 场景线程存储，不是全局 agent database。

---

## 五、最终判断

综合 OpenClaw、LangGraph、AutoRA、GPT Researcher 的启发，当前最合适的语义收口是：

- `skills` = 可插拔能力包
- `scenario` = 工作流语义真源
- `scenario_instance` = 场景线程运行态
- `state_store` = thread/checkpoint/store
- `agent role` = step 语义投影

如果压缩成一句工程判断：

> Butler research 下一步最该补的不是更多 agent，而是让 `brainstorm / paper_discovery / idea_loop` 拥有共享的 scenario instance 和最小 state store。

---

## 六、参考资料

- OpenClaw Skills
  - https://docs.openclaw.ai/tools/skills
- LangGraph Durable Execution
  - https://docs.langchain.com/oss/python/langgraph/durable-execution
- AutoRA States and Workflows
  - https://autoresearch.github.io/autora/core/docs/cycle/Basic%20Introduction%20to%20Functions%20and%20States/
- GPT Researcher README
  - https://github.com/assafelovic/gpt-researcher
