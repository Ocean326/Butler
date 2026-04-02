## Butler research：Agent Instance / Workflow / Application Flow 分层判断

**任务背景**
- 用户当前在推进 Butler 的 `agents_os` 升级，已经补了 `AgentRuntimeInstance`、`InstanceStore`、`RuntimeHost`。
- 当前最想推进的 research 场景有三类：
  - 头脑风暴
  - 自动搜索 + 整理论文/资料
  - 从 idea 到代码改进到结果提升
- 用户提出的新想法是：是否应该在 instance 之上再封一层 `agent_workflow`，配套 agent 间协议；每个应用场景内部只保留入口、实例化资料、workflow 格式、出口；无论是用户直接调用、talk 入口还是 heartbeat 调用，都实例化同一个场景 workflow。

**本稿定位**
- 不是泛泛综述，而是面向 Butler 当前代码基线的架构判断稿。
- 目标是回答三件事：
  - 现在要不要补 `agent_workflow`
  - `instance / workflow / protocol / application_flow` 该怎么分层
  - 这三类 research 场景长期该怎么借力当前 `agent instance`

---

### 1. 一句话结论

**方向是对的，但不要一步做成“通用工作流平台”。**

更合适的演进方式是：

1. 把 `AgentRuntimeInstance` 继续当作**运行态容器**
2. 在其上补一个**轻量、声明式、场景内聚**的 `agent_workflow`
3. 再往上抽象出面向业务复用的 `application_flow`
4. 协议层优先做**最小 step/handoff/decision 契约**，不要先做大而全 MAS 协议

也就是说，**现在应该补 workflow，但不应该直接做一个重型 universal orchestrator**。

---

### 2. 为什么现在该补 workflow，而不是只靠 instance

从 Butler 当前形态看，`AgentRuntimeInstance` 已经解决了几个关键问题：

- 有独立 instance 身份与目录根
- 有 session / checkpoint / resume / retire
- 有 artifacts / handoff / workspace / inbox / outbox 等运行态容器
- 有 `RuntimeHost` 负责 create/load/update/submit/resume/retire

但 instance 本身只回答了：

- 这个 agent 现在是谁
- 它的运行态资产放哪
- 它如何被恢复和续跑

它**没有回答**：

- 这个场景分几步
- 每一步的输入输出是什么
- 哪一步需要 handoff
- 哪一步是 decision gate
- heartbeat / talk / user direct call 进入时该从哪里接续

而 research 场景恰好最依赖这些东西：

- brainstorm 不是一次回复，而是一串发散/收敛动作
- 文献搜索不是一次搜索，而是 query -> collect -> screen -> organize -> digest
- idea 到代码改进更明显是多轮 loop

所以只靠 instance 会让“场景控制流”继续散落在 manager、prompt、人工约定和心跳逻辑里，最终实例虽然持久了，但业务仍然不可复用、不可解释、不可演进。

---

### 3. 推荐的四层切分

#### 3.1 Instance 层：运行态容器

这层继续放在 `agents_os`。

职责只保留：

- 身份与生命周期：create/load/update/submit/resume/retire
- session / checkpoint / trace / artifact / recovery
- profile、budget、risk、governance、tool policy
- 对上层暴露稳定 host API

**不要把业务 stage、research phase、文献策略塞回 instance。**

instance 是“容器”，不是“业务流”。

#### 3.2 Protocol 层：最小协作契约

这是现在最值得补、但也最容易做重的一层。建议只做四类最小协议：

- `step_input`
- `step_output`
- `handoff_receipt`
- `decision_receipt`

最少应包含：

- `workflow_id`
- `run_id`
- `step_id`
- `producer`
- `consumer`
- `goal`
- `artifacts`
- `status`
- `next_action`
- `uncertainties`

如果继续扩一点，再加：

- `budget_snapshot`
- `frozen_scope`
- `acceptance_gate`
- `resume_from`

这层的目的不是做“agent 联邦协议”，而是让 Butler 内部不同 agent/entrypoint/heartbeat 之间有统一接力面。

#### 3.3 Workflow 层：场景内控制流

这是本次最应该新增的层。

定义：

- 一个 workflow 对应一个**可持续运行的场景控制流**
- 负责 stage 顺序、状态迁移、gate、handoff、resume 点
- 依赖 instance 提供持久化与恢复
- 依赖 protocol 保证每一步能被别的入口接续

这里要坚持三个原则：

- **轻量**
- **声明式**
- **场景本地化**

也就是优先做：

- `workflow.spec.json` / `workflow.yaml`
- `stages/*.md` 或 `stages/*.json`
- `prompts/`
- `handoff templates`
- `acceptance rules`

而不是先做一个 Butler 全局 DAG 平台。

#### 3.4 Application Flow 层：应用包与未来自生成对象

这层不应该等于 workflow engine。

更合适的理解是：

- application flow = 一个可实例化、可复制、可演进的**业务场景包**

它内部可以包含：

- 入口定义
- workflow 规格
- agent profile / prompt profile / memory profile
- 配套素材区
- 出口产物格式

你现在说的“应用场景内部只做入口 + agents 实例化资料 + agentsworkflow 格式 + 出口”，本质上就是这层。

所以：

- `instance` 解决“怎么活着”
- `workflow` 解决“怎么跑”
- `application_flow` 解决“这类业务怎么被复用和生成”

---

### 4. 对用户当前想法的直接判断

你的想法整体上是对的，而且和 Butler 当前基线是兼容的。

更精确地说，应该这样收口：

- **不是**“每个入口一个 agent 实例”
- **而是**“每个持续业务内核一个 instance”

也就是说：

- `talk`
- `heartbeat`
- 用户手工触发

这些都不应该各自拥有一套 research agent。

它们应该只是：

- 发现某个场景 workflow
- 加载/创建该 workflow 对应的 instance
- 以当前入口身份提交一次 step / run
- 在统一的 protocol 与 checkpoint 上继续推进

所以 entrypoint 是**唤醒方式**，scenario 才是**运行实体**。

---

### 5. 三个 research 场景该怎么用 instance

#### 5.1 brainstorm：长寿命、弱执行、强记忆

这个场景适合做成一个长期存在的 scenario instance。

它的核心不是强执行，而是：

- 持续积累问题树
- 收集启发来源
- 沉淀候选方向
- 做发散 -> 收敛 -> 留档

建议 workflow 极简化：

```text
capture -> cluster -> expand -> converge -> archive
```

这个场景里最重要的是：

- memory refs
- overlays
- idea cards
- 结构化 handoff

不需要一开始就搞强 stage 编排，但很需要：

- 可恢复上下文
- 跨入口接续
- “上次收敛到哪了”的 working summary

所以 brainstorm 是 **instance + 轻 workflow + 强 memory protocol**。

#### 5.2 自动搜索 + 文献整理：周期运行、检索筛选型 workflow

这个场景比 brainstorm 更适合显式 workflow。

推荐的最小流：

```text
topic_lock -> query_plan -> search -> collect -> screen -> organize -> digest -> archive
```

关键不是把所有文献平台逻辑都塞进 runtime，而是：

- 把 query、screen 规则、输出卡片、归档结构做成场景资产
- 用 instance 保存：
  - 当前 topic
  - 已用 query
  - 已看 source
  - 最近 digest
  - checkpoint

这个场景最适合 heartbeat 接手，因为它天然是周期型任务。

同时也最适合学习 `Research-Claw` 的一个设计点：

- **把场景驱动资产写成 bootstrap/协议文件，而不是把全部业务控制流烤进 runtime**

#### 5.3 idea -> code -> result：最适合 instance 的硬场景

这块是当前 Butler 最值得优先做强的 research workflow。

因为它天然需要：

- checkpoint
- artifact versioning
- replay / resume
- maker-checker
- decision loop
- frozen scope

其实 `idea_loop` 文档已经在往这个方向走了：

```text
idea_lock -> plan_lock -> iterate[k] -> final_verify -> archive
```

这类场景最应该吃到：

- `instance` 的 session/checkpoint/recovery
- `workflow` 的 stage 与 decision
- `protocol` 的 verify / decision / handoff receipt

长期看，它会成为 Butler research 域里最像 `autoresearch` 和 `AutoResearchClaw` 中间态的模块：

- 不做 23-stage 重管线
- 但也不只是一个松散 prompt loop

---

### 6. 从成熟项目里抽到的四个关键启发

#### 6.1 `autoresearch`：强约束比大自由度更先带来价值

`autoresearch` 的核心不是多 agent，而是三件事：

- 单文件改动边界
- 固定时间预算
- 单一主指标

它说明一个重要判断：

**在 research 改进类任务里，先把“搜索空间”收紧，比先把 agent 数量做多更有效。**

对 Butler 的直接启发是：

- `idea_loop` 不要先追求复杂 team
- 先把 frozen scope、done criteria、budget、acceptance 固定好

#### 6.2 `AutoResearchClaw`：复杂研究流需要显式阶段契约

`AutoResearchClaw` 证明了另一件事：

- 一旦任务进入“多阶段、多能力、多外部资源”的研究管线，隐式 prompt 约定就不够了
- 必须补 stage-level 的输入输出契约、gate、版本化、经验回灌

但 Butler 当前不该直接模仿它的重度形态。

真正值得学的是：

- `PIVOT / REFINE / PROCEED` 这种 decision contract
- artifacts 自动版本化
- 失败 lesson 反哺后续 run

#### 6.3 `Research-Claw`：应用场景更适合做成“场景资产包”

`Research-Claw` 很值得借的不是它的全部前后端工程，而是它对 `workspace` bootstrap 的处理：

- `AGENTS.md`
- `HEARTBEAT.md`
- `TOOLS.md`
- `MEMORY.md`

这些文件共同定义了一个可运行场景，而不是把业务都写死在 runtime 里。

这和你现在提出的“应用场景内部只放入口、资料、workflow 格式、出口”非常一致。

所以 Butler 更适合做：

- 场景本地资产包
- 通用 instance host
- 统一 protocol

而不是“一个超级 manager 管所有业务分支”。

#### 6.4 LangGraph：workflow 和 agent 应该分开看

LangGraph 文档有个判断非常对路：

- workflow = 预定代码路径
- agent = 动态决定过程和工具使用

同时它把 `thread_id`、checkpoint、state history 作为 persistence 主轴。

这对 Butler 的启发很直接：

- `workflow` 负责预定义 stage/gate/resume 点
- `agent instance` 负责 thread/session/checkpoint
- 两者不要混成一个概念

---

### 7. 对 Butler 的推荐落地方向

#### 7.1 先补“场景级 workflow”，不要先做“全局 workflow engine”

推荐先在 `research` 域内落：

- `brainstorm_workflow`
- `paper_discovery_workflow`
- `idea_loop_workflow`

先做 3 个 scenario-local workflow，积累共性后再回收抽象。

#### 7.2 先补最小协议，不要先做复杂 agent team protocol

建议第一批协议只做：

- `step_receipt.json`
- `handoff_receipt.json`
- `decision_receipt.json`
- `acceptance_receipt.json`

够 heartbeat、talk、user direct invoke 三路接续就行。

#### 7.3 入口统一成“唤醒现有 instance 或创建新 scenario instance”

也就是：

- 用户输入时：resolve scenario -> load/create instance -> submit step
- talk 调用时：同上
- heartbeat 调用时：同上

不要让不同入口各自维护自己的研究状态。

#### 7.4 经验回灌先做弱版

现在不需要直接做 MetaClaw。

先做：

- 每次 run 产出 `lesson.md` / `lesson.json`
- 每个 scenario instance 维护最近 lessons
- workflow 启动时加载最近 lessons 形成 overlay

这是 Butler 当前阶段更稳的“半自动经验飞轮”。

---

### 8. 一个更适合当前 Butler 的目录理解

如果按你现在的想法继续推进，更合适的组织不是“全局 agent workflow 平台”，而是：

```text
research/
  scenarios/
    brainstorm/
      workflow/
      protocols/
      prompts/
      assets/
      outputs/
    paper_discovery/
      workflow/
      protocols/
      prompts/
      assets/
      outputs/
    idea_loop/
      workflow/
      protocols/
      prompts/
      specs/
      outputs/
```

同时运行态实例继续放在：

```text
agents_os/runtime/instances/<instance_id>/
```

于是代码层和运行态层会更清楚：

- `research/scenarios/*` = 场景定义与素材
- `agents_os/runtime/*` = 通用运行时容器

---

### 9. 对“未来 agent 自己生成应用流”的判断

你现在提“应用流探索，为未来 agent 可以自己生成应用流做铺垫”，这个方向是成立的，但前提是先把 application flow 压成几个稳定构件。

未来 agent 能生成的，不该是任意代码级 orchestrator，而更应该是：

- 选一个 flow 模板
- 补齐目标、阶段、预算、gate、出口格式
- 组装对应的 prompts / protocols / assets
- 实例化成一个新的 scenario package

也就是说，未来 agent 生成的应该是：

- **application flow spec**

而不是先直接生成复杂 runtime 核心。

只有先把下面这些收敛成显式对象，未来自生成才有基础：

- stage
- decision
- handoff
- acceptance
- archive

---

### 10. 最终判断

综合 Butler 当前基线、`idea_loop` 方向、`Research-Claw` 的场景资产包思路、`autoresearch` 的极简约束思路、`AutoResearchClaw` 的 stage 契约与经验回灌、以及 LangGraph 对 workflow/persistence 的划分，当前最合适的路线是：

- **补 `agent_workflow`，但只做轻量场景级**
- **补 agent 间协议，但只做最小 receipt/handoff/decision 契约**
- **把 application flow 理解为“场景资产包 + workflow 规格 + 出口格式”**
- **让 talk / heartbeat / direct invoke 共享同一个 scenario instance，而不是各自一套 agent**

如果压成一句工程决策：

**Butler research 下一步不该是做一个大而全的 multi-agent 平台，而是把 `instance` 上面补成“可复用、可恢复、可接续”的 scenario workflow 层。**

---

### 11. 本稿可直接转化的实现优先级

#### P0

- 在 `research` 域补 3 个 scenario workflow 规格
- 补最小 `step/handoff/decision/acceptance` 契约
- 统一三种入口到“load/create scenario instance -> submit step”

#### P1

- 给每个 scenario instance 增加 `lesson` 归档与 overlay 注入
- 给 brainstorm / paper discovery / idea loop 各补一份最小 workflow asset 包

#### P2

- 再抽一层 `application_flow` 模板化
- 探索 agent 根据模板生成新 flow spec

---

### 12. 参考材料

**Butler 本地**
- `butler_main/agents_os/runtime/instance.py`
- `butler_main/agents_os/runtime/host.py`
- `butler_main/research/manager/code/research_manager/manager.py`
- `butler_main/research/units/research_idea/docs/20260320_idea_loop_设计方案.md`
- `BrainStorm/Insights/standalone_archive/early_insight/20260318_autoresearch_vs_autoresearchclaw_harness_对照分析.md`

**外部一手材料**
- Karpathy, `autoresearch` README: <https://github.com/karpathy/autoresearch>
- AutoResearchClaw README: <https://github.com/aiming-lab/AutoResearchClaw>
- Research-Claw README: <https://github.com/wentorai/Research-Claw>
- LangGraph official docs, Workflows and agents: <https://docs.langchain.com/oss/python/langgraph/workflows-agents>
- LangGraph official docs, Persistence: <https://docs.langchain.com/oss/python/langgraph/persistence>
