---
type: "note"
---
# 04B research 三场景运行语义与上线前链路设计

日期：2026-03-23\
状态：设计稿

## 文档目的

本页只解决两个问题：

1. 如果上线口径要求支持重复执行、重试、resume、多轮推进，那么 `research -> multi_agents_os -> orchestrator` 链路必须满足什么条件。

2. 对 `research` 当前三个核心场景：

   * `brainstorm`

   * `paper_discovery`

   * `idea_loop`

3. 应如何从专业科研 workflow 角度定义其运行语义、热状态、协作投影与恢复边界。

本页遵守 `docs/concepts/外部多Agent框架调研与Butler长期架构规划_20260323.md` 的分层：

* `research` 负责 scenario-specific interpreter 与场景热状态

* `multi_agents_os` 负责 collaboration substrate

* `orchestrator` 负责 mission/control plane

* `agents_os` 未来负责 workflow VM / execution kernel

## 1. 上线前链路要求

如果上线目标不是“只跑通单轮 happy path”，而是要支持：

1. 重复执行

2. 重试

3. resume

4. 多轮推进

那么链路必须至少满足下面五条。

### 1.1 投影必须幂等

同一个 `scenario_instance`、同一个 `step_receipt/handoff_receipt/decision_receipt` 被重复投影时，不应在 `multi_agents_os` 中无限追加重复对象。

至少要有：

* artifact dedupe key

* mailbox dedupe key

* handoff dedupe key

* join contract dedupe key

建议最小幂等键：

* artifact: `session_id + ref`

* handoff: `session_id + handoff_id`

* mailbox: `session_id + handoff_id`

* join contract: `session_id + decision_id`

### 1.2 research 热状态必须可恢复

`scenario_instance_store` 至少要保证：

* 同一 `scenario_instance_id` 可以 load

* 能根据 `workflow_cursor/current_step_id/latest_decision` 恢复下一步

* 不同入口复用同一 `session_id` 时不会错误开新线程

### 1.3 collaboration projection 必须是可重放的

`research` 不应直接把解释器内部对象丢进 `multi_agents_os`。

应先产出结构化 receipts / checkpoint，再由 projection layer 做纯函数式映射。

也就是说，理想状态下：

同一个 `ResearchResult.dispatch` 重放多次，得到的 projection 应一致。

### 1.4 orchestrator 只观察与派发，不吞 scenario 真源

`orchestrator` 可以：

* 创建 workflow session

* 调用 research

* 回写 branch/node/mission 结果

* 观察 workflow session summary

但不应成为：

* scenario 热状态真源

* research 私有状态的解释器

### 1.5 future workflow VM 接入时要能接管执行语义

今天的链路允许 `research` 暂时保存场景热状态；

但设计上必须留出以后迁移到 `agents_os` 的空间，尤其是：

* retry

* replay

* resume

* approval / verification gate

* branch/join execution semantics

## 2. research 三场景的专业科研定位

### 2.1 `brainstorm`

定位：

用于问题澄清、方向发散、方案收敛、形成下一步研究/工程候选方向。

它不是“随便发想法”，而是：

**围绕明确问题边界进行受约束发散与可解释收敛。**

专业上应强调：

* 先锁问题框架，再发散

* 发散阶段和收敛阶段必须分开

* 最终必须形成明确 decision，而不是永远开放

### 2.2 `paper_discovery`

定位：

用于研究窗口锁定、检索策略生成、候选文献发现、筛选、短名单整理、digest 输出。

它不是“帮我搜搜论文”，而是：

**一个可复跑、可筛选、可累计 backlog 的检索与整理回合。**

专业上应强调：

* topic window 要稳定

* query plan 要有版本

* search/screen 要有筛选理由

* shortlist 与 digest 要可被下游阅读/比较/追踪

### 2.3 `idea_loop`

定位：

用于假设提出、改动计划、实验/实现、验证、失败恢复、下一轮迭代。

它不是单次 coding task，而是：

**围绕一个假设持续迭代的研究-工程闭环。**

专业上应强调：

* hypothesis 要明确

* verify 不能被省略

* failure mode 要结构化记录

* 每轮必须能形成 continue / retry / accept / stop 的决策

## 3. 每个场景的运行语义设计

### 3.1 `brainstorm` 运行语义

#### 核心阶段

1. `capture`

   * 锁问题、目标、约束

2. `cluster`

   * 把原始线索聚类

3. `expand`

   * 对候选方向做受控扩展

4. `converge`

   * 收敛并比较候选方案

5. `archive`

   * 归档可复用结论与开放问题

#### 必须保留在 research 的热状态

* problem frame 的私有解释上下文

* cluster 暂存结构

* 发散过程中的候选方向草稿

* 收敛中的评价理由草稿

这些适合留在 `scenario_instance.state`，不必全部投影。

#### 应投影到 collaboration substrate 的状态

* 当前活跃阶段

* `step_receipt`

* 收敛产生的 `decision_receipt`

* 需要交给下游时的 `handoff_receipt`

* 最终 decision artifact / note artifact

#### 多轮推进语义

`brainstorm` 不应无限轮循环。

建议：

* 一轮 `brainstorm` 的终点必须是 `archive`

* 如果用户或上层要求继续 brainstorm，应新开一轮或显式 `resume` 同一线程

* `refine` 只允许把当前轮推回 `cluster/expand/converge`，不应静默无限自旋

#### 重试/恢复语义

* 如果输入约束不清，允许回到 `capture`

* 如果方案发散质量差，允许回到 `cluster`

* 如果收敛证据不足，允许回到 `expand`

### 3.2 `paper_discovery` 运行语义

#### 核心阶段

1. `topic_lock`

   * 锁定主题窗口、时间边界、筛选边界

2. `query_plan`

   * 生成 query set、source list、screening rules

3. `search`

   * 搜索候选文献，可 fan-out

4. `screen`

   * 去噪、筛选、说明保留/剔除理由

5. `digest`

   * 形成 shortlist、digest、下一步阅读建议

#### 必须保留在 research 的热状态

* query plan 的中间草稿与修订

* source adapter 相关上下文

* candidate 原始池与中间筛选过程

* screen 期间的解释器私有缓存

这些不应直接塞进通用 shared state。

#### 应投影到 collaboration substrate 的状态

* `topic_frame` / `current_step_id`

* query plan 的摘要信息

* `step_receipt` 里的搜索/筛选摘要

* shortlist handoff

* digest artifact / shortlist artifact

* proceed/refine/defer 的 `decision_receipt`

#### 多轮推进语义

`paper_discovery` 本质上是 round-based 的。

建议：

* 一轮 discovery 对应一个 topic window + query version

* 多轮推进应显式记录 round number

* round 之间可以复用同一 `scenario_instance`，但要保留：

  * 本轮 topic window

  * 本轮 query version

  * 本轮 shortlist

* 不应把多轮候选池静默混成一锅

#### 重试/恢复语义

* `search` 失败可 retry，但要保留 source failure class

* `screen` 发现 query 偏差时可退回 `query_plan`

* `digest` 如果 short list 质量差，可退回 `screen`

### 3.3 `idea_loop` 运行语义

#### 核心阶段

1. `idea_lock`

   * 锁 hypothesis 与 success signal

2. `plan_lock`

   * 锁 change plan / constraints / expected signal

3. `iterate`

   * 进行实现、实验或结构改造

4. `final_verify`

   * 验证结果，判断是否有效

5. `archive`

   * 归档结论与下一轮方向

6. `recover`

   * 当 verify 失败或结果弱时，显式进入恢复路径

#### 必须保留在 research 的热状态

* hypothesis 的上下文解释

* 计划草稿与修订原因

* 本轮实验/实现中间上下文

* failure mode 分析过程

这些属于 loop-specific reasoning，不应该全部投影。

#### 应投影到 collaboration substrate 的状态

* 当前 iteration 的阶段

* `step_receipt`

* verify 后的 `decision_receipt`

* recover 时的 handoff / next iteration contract

* metrics / acceptance / lesson artifact

#### 多轮推进语义

`idea_loop` 必须天然支持多轮。

建议：

* 一个 `scenario_instance` 对应一个 hypothesis family

* 每一轮有独立 `iteration_id`

* 每轮必须输出：

  * hypothesis snapshot

  * plan snapshot

  * verify result

  * decision

  * lesson

* `retry/refine` 不是简单重跑，而是新 iteration

#### 重试/恢复语义

* `iterate` 失败但原因明确，可 retry 当前 iteration

* `final_verify` 失败后，优先进入 `recover`

* `recover` 的出口必须是：

  * 新 iteration

  * accept failure and stop

  * escalate/block

## 4. research 应保留的热状态

综合三个场景，当前 `research` 应保留的热状态统一口径如下：

1. `thread_key`

2. `entrypoints_seen`

3. scenario-private `state`

4. scenario-specific interpreter 中间上下文

5. round / iteration 内部推理草稿

6. 各阶段的私有缓存、筛选草稿、假设修订上下文

7. 对场景包自身有意义、但对通用 collaboration substrate 无意义的字段

## 5. 应投影到 multi_agents_os 的通用状态

统一建议为：

1. `workflow_session_id`

2. `current_step_id`

3. `workflow_cursor` 的通用部分

4. `scenario_instance_id` 作为 metadata / artifact ref

5. `step_receipt`

6. `handoff_receipt`

7. `decision_receipt`

8. acceptance artifacts

9. 高层 summary / next_action

10. 由 receipts 派生出的：

* ownership

* mailbox

* handoff

* join contract

## 6. 上线前应新增的设计约束

### 6.1 必加的幂等约束

在正式上线前，至少应设计并实现：

1. 同一 `scenario_instance:{id}` artifact 不重复追加

2. 同一 `handoff_id` 不重复生成 mailbox/handoff

3. 同一 `decision_id` 不重复生成 join contract

4. 同一 `step_id + role` 的 ownership 采用 upsert 而不是 append

### 6.2 必加的多轮测试

至少补三类测试：

1. 同 session 同 branch 重复投影不重复追加 collaboration 对象

2. `advance -> resume` 后 `workflow_cursor/current_step_id` 一致

3. `idea_loop` 在 `final_verify -> recover -> next iteration` 中保持 iteration 边界清晰

### 6.3 必加的场景级 trace

每个场景至少要能回答：

1. 现在在哪一轮

2. 当前在哪一步

3. 为什么进入下一步

4. 为什么 retry / refine / recover

5. 当前最重要的 artifact 是什么

## 7. 当前结论

如果上线标准只是：

* 单轮触发

* 单次投影

* happy path 观察

那么当前链路已基本可用。

如果上线标准包括：

* 重复执行

* 重试

* resume

* 多轮推进

那么当前还缺：

1. collaboration projection 的幂等设计

2. 三个场景的 round/iteration 级显式语义

3. 更完整的重复投影与恢复测试

所以当前更准确的状态应定义为：

**链路主干已通，单轮可用；但离“上线前最终闭环”还差幂等与多轮推进设计的最后一层。**

⠀