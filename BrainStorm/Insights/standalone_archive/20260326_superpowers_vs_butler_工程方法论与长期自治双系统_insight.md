# Insight: Superpowers vs Butler —— 工程方法论与长期自治的双系统分工

- **来源/对读范围**：
  - `MyWorkSpace/TargetProjects/superpower/superpower/obra-superpowers/README.md`
  - `MyWorkSpace/TargetProjects/superpower/superpower/obra-superpowers/skills/brainstorming/SKILL.md`
  - `MyWorkSpace/TargetProjects/superpower/superpower/obra-superpowers/skills/writing-plans/SKILL.md`
  - `MyWorkSpace/TargetProjects/superpower/superpower/obra-superpowers/skills/subagent-driven-development/SKILL.md`
  - `butler_main/orchestrator/framework_catalog.py`
  - `butler_main/orchestrator/framework_profiles.py`
  - `docs/daily-upgrade/0325/10_Codex原生能力边界与Butler吸收参考.md`
  - `docs/daily-upgrade/0323/01D_全局skil与注入.md`
- **整理方式**：基于本地仓库对读，不是外部二手评论
- **Insight 整理日期**：2026-03-26
- **主题域**：Harness Engineering / Coding Agent 工程化 / Butler 架构演进

---

## 核心摘要

这次对读后最关键的判断不是“`superpowers` 比 Butler 多了哪些功能”，而是：

**它们在解决两类不同但必须协同的工程问题。**

- `superpowers` 主要在解决：复杂任务如何被稳定地讨论、设计、计划、执行、复核
- Butler 当前主要在解决：任务如何被长期运行、监督、恢复、编排和积累经验

因此，`superpowers` 对 Butler 最有价值的地方，不是 plugin 形态、skill 外壳或 host 适配，而是它把**工程方法本身**做成了一套强制流程。  
Butler 当前真正缺的，也不是 subagent、reviewer 或 skill pool 这些零件，而是：

**还没有把“工程方法论”提升成一套独立、默认、带硬 gate 的系统。**

---

## 核心观点（7 条）

### 1. `superpowers` 真正强在 Delivery Method，而不是 Runtime Kernel

从它的 README 和核心 skills 看，`superpowers` 的主轴非常稳定：

```text
brainstorm -> design/spec -> implementation plan -> subagent execution -> review -> finish
```

它强的不是“有更多 agent”，而是：

- 先设计，后实现
- 先写 plan，后动代码
- 每一步都有明确的前置条件
- review 不是可选能力，而是默认门槛
- 子 agent 不是自由漫游，而是任务粒度很细的执行工人

因此，`superpowers` 本质上是一个 **Delivery Method System**：

- 它定义“工程任务应该怎么做”
- 它约束“什么时候能进入下一阶段”
- 它要求“必须留下哪些工件”

它不是一个更底层的 runtime，不是 Butler `2/3` 层的替代品。

### 2. Butler 当前更强的是 Autonomy Runtime，而不是 Delivery Method

对照本仓库，Butler 已经明显在另一条线投入更多：

- `3 = orchestrator / control plane`
- `2 = runtime_os / process runtime`
- `1 = runtime_os / agent runtime`

而且已经有：

- `campaign supervisor`
- `workflow_ir / workflow_vm`
- `runtime routing`
- `reviewer / acceptance` 相关概念
- `skills registry`
- `framework profile`
- `governance / recovery / observation`

这说明 Butler 不是“没有工程意识”，而是**更偏运行系统建设**。  
也就是说，Butler 已经在搭：

**Autonomy Runtime System**

它回答的是：

- 任务怎么长期跑
- 失败怎么恢复
- 多轮状态怎么维持
- 谁来监督、谁来裁决
- 经验如何累积进系统

这条线是 `superpowers` 没有真正展开的。

### 3. Agent 工程应至少拆成三层：能力层、方法层、运行层

这次对读最大的理论收获，是要把过去容易混在一起的东西彻底拆开：

| 层 | 核心问题 | 典型对象 |
|---|---|---|
| **Capability Layer** | 系统“能做什么” | model、tool、skill、reviewer、subagent |
| **Method Layer** | 系统“应该怎么做” | brainstorm、spec、plan、review、acceptance |
| **Runtime Layer** | 系统“怎么跑起来并持续运行” | session、workflow、campaign、supervisor、recovery |

很多团队的问题不在于没有能力，而在于：

- 把 capability 误当 methodology
- 把 runtime 误当 delivery discipline
- 把文档习惯误当系统化 gate

`superpowers` 的价值在于把 **Method Layer** 做得很重。  
Butler 的价值在于已经把 **Runtime Layer** 看得很重。  
未来真正成熟的 Butler，必须把这三层同时拉开，而不是继续混写在 prompt、文档、skill 和 orchestrator 之间。

### 4. `spec / plan / review / acceptance` 不是文档，而是认知稳定器

如果只把这些对象理解成“写得更规范一点的文档”，理论层次还是不够。

更准确的说法是：

- `spec` 用来抑制 **目标漂移**
- `plan` 用来抑制 **执行漂移**
- `review` 用来抑制 **质量漂移**
- `acceptance` 用来抑制 **完成定义漂移**

所以它们不只是可读材料，而是 Agent 工程里的 **cognitive stabilizers**。

当系统复杂度上来之后，仅靠：

- 对话记忆
- 长上下文
- 一次性 prompt
- 人工“心里记着”

都不足以稳定工程行为。  
必须把这些中间工件显式化、对象化、持久化，才能让 agent 的交付行为不因为上下文波动而失真。

### 5. Butler 的问题不是“没有这些零件”，而是“没成为默认主路径”

如果只从代码和文档现状看，Butler 其实已经有很多相关前置件：

- `framework_catalog.py` 明确把 `superpowers` 识别为软件工厂方法论参照
- `framework_profiles.py` 已有 `superpowers_like` profile
- `docs/daily-upgrade/0325/10_...` 已经裁定哪些能力可吸收、哪些只能包裹
- `skills` 真源、collection registry、role pack 也在推进
- `campaign reviewer`、`review packet`、`acceptance` 已经开始出现

因此真实问题不是“缺 review / 缺 skill / 缺角色包”，而是：

1. **缺单一方法真源**
   - 方法散在 docs、profile、skill、prompt、demo fixture 里
2. **缺默认入口强制力**
   - 进入仓库后，不会自然稳定地走同一条方法主线
3. **缺硬 gate**
   - review 常是能力，尚未完全成为不可跳过的阶段门

所以 Butler 当前像是：

**已经收集了很多 Delivery Method 的零件，但还没把它们组装成一个正式系统。**

### 6. Butler 的正确目标不是复制 `superpowers`，而是建立“双系统耦合”

这次最重要的正向判断是：

Butler 不该把目标设成“做出一个中国版 superpowers”，也不该只沿着“更强的自治 runtime”单线前进。

更合理的目标形态是：

```text
System A: Delivery Method System
    负责 spec / plan / review / acceptance / task discipline

System B: Autonomy Runtime System
    负责 campaign / supervisor / workflow / recovery / long-running execution
```

两者的关系不是替代，而是耦合：

- A 没有 B：会变成高质量但短命的会话方法
- B 没有 A：会变成能长期运行但交付质量持续漂移的自治系统

换句话说：

**`superpowers` 是 Butler 在 System A 上的强参照样本。**  
**Butler 的长期 ambition 则是把 A 和 B 接起来。**

### 7. “工程方法”最终必须被编译，而不是只被阅读

Butler 当前已经有一个很好的前提：你并不是在一个纯 prompt 系统里做这件事，而是已经有：

- `framework profile`
- `workflow template`
- `governance policy`
- `runtime binding`
- `campaign supervisor`

这意味着方法论的终极落点，不该只是：

- 一份长文档
- 一组 prompt 建议
- 一套“请记得这么做”的人格要求

而应该是：

**Methodology 可以被 profile / policy / workflow template 编译成可执行流。**

这是 Butler 相比纯宿主型 workflow 系统更有潜力的地方。

---

## 一个更清晰的理论模型

### 1. 三层模型

```text
Capability Layer
  模型、工具、skills、subagents、reviewer
  回答：系统“能做什么”

Method Layer
  brainstorm、spec、plan、review、acceptance
  回答：系统“应该怎么做”

Runtime Layer
  session、workflow、campaign、supervisor、recovery
  回答：系统“怎么跑起来并持续运行”
```

### 2. 双系统模型

```text
Delivery Method System
  = Method Layer 的主系统化落地

Autonomy Runtime System
  = Runtime Layer 的主系统化落地
```

### 3. 两类系统的不同失效模式

| 系统缺失 | 典型后果 |
|---|---|
| Delivery Method System 弱 | 目标漂移、计划漂移、质量漂移、完成定义漂移 |
| Autonomy Runtime System 弱 | 长任务中断、恢复困难、监督失效、经验无法沉淀 |

这也解释了为什么很多 coding agent 项目“看起来很强但不稳”：

- 不是模型不够强
- 而是只补了能力层，没有把方法层和运行层都做成系统

---

## 与 Butler 当前架构的映射

| `superpowers` 的方法对象 | Butler 当前对应 | 当前状态 | 关键差距 |
|---|---|---|---|
| brainstorming | docs + role pack + 人工流程 | 有意识，但未系统化 | 缺统一入口和阶段门 |
| written spec | 文档 / daily-upgrade / 讨论计划 | 存在但分散 | 不是正式 artifact contract |
| writing-plans | planner / 文档计划 / campaign 规划 | 有雏形 | 未形成统一 plan schema |
| task execution | agent runtime / codex harness / worker role | 已具备 | 缺和 spec/plan 的强绑定 |
| spec review / code review | reviewer / campaign reviewer / review packet | 已有角色与概念 | 尚未彻底变成硬 gate |
| finish / acceptance | acceptance、verdict、campaign 收口 | 已开始出现 | 完成定义仍不够统一 |

映射后的判断很清楚：

Butler 当前不是“做不到”，而是：

**Method Layer 的对象已经局部出现，但还没有被收口为正式系统。**

---

## 对 Butler 的设计启发

### 1. Butler 需要一个独立的 Methodology Plane

这个 plane 不属于 `1/2/3` 层 runtime 真源，但也不能继续只是文档约定。  
它应该定义：

- 允许的阶段
- 每阶段的输入输出 contract
- 每阶段允许的角色与运行时
- 哪些 gate 是强制的

也就是把“复杂任务如何被工程化地完成”独立出来。

### 2. `superpowers_like` 不应长期停留在 demo profile

它最有价值的地方不是 demo，而是说明 Butler 已经识别出“这种方法型框架”的存在。  
下一步不是继续给它做 showcase，而是：

- 把它升级成正式 methodology family
- 让 artifact contract 明确化
- 让 review / acceptance 真正下沉为治理策略

### 3. Skill 系统不能代替 Method System

Butler 当前 skill 真源、collection registry 的方向是对的，但必须区分：

- **Action Skill**
  - 回答“具体做哪件事”
- **Process Skill / Method Rule**
  - 回答“做事时必须遵守什么阶段纪律”

如果这两类东西继续混在一起，最后会出现：

- skill 很多
- 角色很多
- 注入很多
- 但工程主线仍然不稳定

### 4. Campaign / Supervisor 不能吞掉 Delivery Discipline

这是未来最容易犯的错。

Butler 很容易因为自己有 `campaign / mission / workflow / supervisor`，就自然认为：

“既然已经有编排器，那工程方法以后都能被编排器吸收。”

但编排器解决的是运行逻辑，不自动等于交付纪律。  
如果没有显式的 spec / plan / review / acceptance contract，系统只会变成：

**更强的编排器，去稳定地放大不稳定的工程行为。**

---

## 五个常见误区

### 误区 1：更多 subagent 就更接近 `superpowers`

错。`superpowers` 的关键不是 agent 数量，而是方法纪律和阶段门。

### 误区 2：把 `AGENTS.md` 写长一点就够了

错。说明文件只能提供方向，不能代替 artifact 和 gate。

### 误区 3：有 orchestrator 就自然拥有工程方法

错。运行时编排不自动生成 delivery discipline。

### 误区 4：先把长期自治做强，再补方法论也来得及

风险很大。这样会先形成“稳定地产生漂移产物”的系统惯性。

### 误区 5：`superpowers` 的宿主/plugin 结构值得照搬

不值得。真正值得吸收的是它的方法系统，不是它的分发外壳。

---

## 可执行的下一步建议

1. **先在 BrainStorm 层正式承认“双系统理论”**
   - 以后讨论 Butler，不再只讲 runtime/harness，也显式讨论 Delivery Method System。

2. **把“工程方法对象”加入 Butler 的长期术语表**
   - `spec artifact`
   - `implementation plan artifact`
   - `review packet`
   - `acceptance receipt`

3. **后续主线文档应补一节：Harness 不只在运行时，也在交付方法**
   - 这会修正当前主线中过于偏 runtime 的视角。

4. **后续 Butler 代码演进应把 Methodology Plane 独立建模**
   - 不是继续把方法论散落在 docs、skills、prompt 和 fixture 里。

5. **用 `superpowers` 作为 System A 的参照样本，而不是整体蓝本**
   - 学它的阶段纪律和工件意识，不学它的宿主壳和产品边界。

---

## 主题标签

`#Superpowers` `#Butler` `#HarnessEngineering` `#工程方法论` `#DeliveryMethodSystem` `#AutonomyRuntimeSystem` `#CodingAgent工程化` `#双系统理论`
