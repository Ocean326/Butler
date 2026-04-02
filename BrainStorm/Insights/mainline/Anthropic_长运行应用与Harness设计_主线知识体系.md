# Anthropic 长运行应用与 Harness 设计：从 Agent 到长任务生产系统的主线知识体系

> **主线定位**：这条主线不是泛泛讲 Anthropic 博客，而是围绕 `2026-03-24` 的 **Harness design for long-running application development** 收口，向前串起 Anthropic 最近几篇最关键的 engineering 文。目标不是摘抄观点，而是回答一个更直接的问题：**当任务从单轮问答变成长时间、可恢复、可验收的软件开发或复杂执行时，系统的主线应该怎么设计？**
>
> **整合来源**：Anthropic `Building effective agents`、`How we built our multi-agent research system`、`Effective context engineering for AI agents`、`Effective harnesses for long-running agents`、`Demystifying evals for AI agents`、`Building a C compiler with a team of parallel Claudes`、`Harness design for long-running application development`，以及 Butler 当前 `0326` 稳定态主线。

---

## 一句话结论

**Anthropic 最近这一串文章真正收敛出来的，不是“模型越来越像 agent”，而是“长任务系统必须围绕 harness、artifact、context reset、独立评估和有限分工来设计”。**

翻成更工程化的话就是：

**生产级 agent 系统的真源，正在从 prompt 和单轮对话，迁移到 `planner / executor / evaluator + external artifacts + eval harness + recoverable runtime`。**

---

## 一、为什么 2026-03-24 这篇是当前主轴

`Harness design for long-running application development` 是 Anthropic 最近几篇工程文里最接近“阶段性裁决”的一篇。

它有三个非常关键的变化：

1. **把长任务 coding harness 讲成了应用开发系统，而不只是 agent loop**
   - 重点从“模型会不会继续干活”变成“系统如何在长周期内不漂移、不早退、不断线”。
2. **把角色分工收束成 `planner / generator / evaluator` 三元结构**
   - `planner` 扩写需求与完成标准
   - `generator` 负责增量构建
   - `evaluator` 负责独立验收，而不是让生成者自己宣布成功
3. **明确提出：模型变强以后，要敢于删脚手架**
   - harness 不是越多越好
   - 每一层 scaffold 都要重新证明自己还在提供净收益

所以这篇文章的价值不只是一个新 pattern，而是把 Anthropic 过去一年关于 agent 的分散经验，压成了一条更像工程总线的判断：

**真正难的不是让模型跑起来，而是让系统在长任务里保持目标、状态、验证和恢复能力。**

---

## 二、Anthropic 最近几篇文章收敛出的演进链

如果按时间线看，这条主线不是突然出现的，而是逐步推进出来的。

### 2.1 `Building effective agents`

起点不是“多 agent 万能”，而是一个很克制的判断：

- 先问有没有必要上 agent
- 能用 workflow 解的，不要先上高自治
- agent 适合高不确定性、长链路、路径不能预先写死的问题

这一步确定了总原则：

**agent 是例外能力，不是默认架构。**

### 2.2 `How we built our multi-agent research system`

第二步开始证明，多 agent 的价值不在“多开窗口”，而在：

- 可并行探索
- 局部上下文隔离
- lead agent 做综合
- subagent 做分工和压缩

这一步真正补出的不是多 agent 炫技，而是：

**一旦问题存在广度搜索和上下文爆炸，多 agent 的主要价值是把认知负担分摊出去。**

### 2.3 `Effective context engineering for AI agents`

第三步把重心从 prompt engineering 推到 context engineering。

核心判断变成：

- 上下文是稀缺资源
- 不是把所有东西塞进去，而是让模型在正确时刻看到正确材料
- note、memory、artifact、subagent isolation 比“全量对话历史”更重要

这一步让 Anthropic 的主线从“怎么写 prompt”转到：

**怎么管理状态、怎么做交接、怎么让上下文不腐烂。**

### 2.4 `Effective harnesses for long-running agents`

第四步开始直面长任务。

这篇的关键贡献是：

- 用 `initializer + coding` 的拆分，对抗长任务的漂移和提前收工
- 用 feature list、progress file、handoff artifact，替代纯对话延续
- 让 session reset 成为正常动作，而不是失败补丁

也就是：

**长任务持续性，不能靠单轮上下文硬撑，必须靠外部工件续命。**

### 2.5 `Demystifying evals for AI agents`

第五步补上独立验证。

Anthropic 这里讲得非常明确：

- `transcript success != outcome success`
- eval 的对象不是模型文本，而是系统最终状态
- 没有 eval harness，模型升级和系统迭代都没有可靠尺子

这一步把主线进一步收紧成：

**agent 不该靠“我做完了”的自述收尾，而要靠独立 grader 和环境结果收尾。**

### 2.6 `Building a C compiler with a team of parallel Claudes`

第六步把并行团队推进到极限。

这篇最重要的教训不是“16 个 Claude 很强”，而是：

- 任务是否可分解，比 agent 数量更重要
- 文件系统和共享 artifact 可以承担协调总线
- 没有强 verifier 和测试，更多 agent 只会更快放大错误

也就是说：

**多 agent 的瓶颈不是并行本身，而是分解质量和验证质量。**

### 2.7 `Harness design for long-running application development`

第七步完成当前收束。

Anthropic 最终给出的结构不复杂，但非常清晰：

- 用 `planner` 明确任务合同
- 用 `generator` 长时推进实现
- 用 `evaluator` 做独立验收
- 用 artifact 和 reset 抵抗 context rot
- 用更强模型换回更少 scaffold，而不是继续堆 orchestration

所以到这里，完整主线已经成立：

**长运行应用的设计重点，不再是“有没有 agent”，而是“有没有一套能长期维持目标、状态、验证和恢复的 harness”。**

---

## 三、Anthropic 主线的六个稳定判断

### 3.1 先判断要不要 agent，再谈 harness 复杂度

不是所有任务都需要自治系统。

判断顺序应该是：

1. 能否用确定性 workflow 解决
2. 是否存在高不确定性和长链路
3. 是否真的需要模型自己做路径选择
4. 只有答案是“需要”，才值得上 agent harness

这意味着：

**harness 设计的第一原则不是做大，而是做对。**

### 3.2 一旦进入长任务，artifact 比对话历史更重要

Anthropic 这条线反复在强调同一件事：

- spec
- task list
- progress log
- memory note
- test result
- known issues
- acceptance criteria

这些都应该成为外置工件，而不是只留在上下文窗口里。

也就是说：

**长任务真正的主存不是 chat transcript，而是 artifact graph。**

### 3.3 `context reset` 往往比“勉强压缩后继续跑”更健康

最新这篇里很关键的一点，是 Anthropic 对 reset 的态度更积极了。

它背后的逻辑是：

- 长上下文会引发目标漂移
- 模型会出现所谓 `context anxiety`
- compaction 有价值，但不是万能修复
- 结构化 handoff 之后重新开始，常常比拖着旧上下文继续跑更稳

所以主线不是“永远不断线”，而是：

**让系统能够安全地断点续跑。**

### 3.4 生成和评估必须解耦

从 `Demystifying evals` 到 `2026-03-24` 这篇，Anthropic 一直在把同一个原则说得更硬：

- generator 自评容易宽松
- evaluator 必须有独立视角
- 最终应该看真实环境和可验证结果
- UI、API、数据库状态、文件产物，比漂亮的解释更重要

这意味着：

**独立 evaluator 不是附加角色，而是长任务系统的信任锚。**

### 3.5 多 agent 是条件升级，不是默认答案

Anthropic 的文章合起来看，其实对多 agent 很克制：

- research 很适合并行探索
- coding 只在任务可拆、验收明确时适合加并行
- 不可分解的问题，增加 agent 只会增加协调税

所以一个成熟系统应默认：

- 单 agent + loop 是基础态
- planner / evaluator 是必要结构态
- 多 worker 并行是高价值场景的增量态

### 3.6 模型升级以后，旧 harness 要重新做减法

这是 3 月 24 日文章里最值得记住、也最容易被忽视的一条。

Anthropic 不是说“结构不重要了”，而是说：

- 某些旧 scaffold 曾经是必要的
- 模型能力上来后，它们可能变成额外摩擦
- harness 的目标是净收益，不是仪式感

所以真正成熟的工程姿态应该是：

**每次模型升级，都重新验证哪些结构还值得保留。**

---

## 四、这条主线真正定义的系统骨架

如果把 Anthropic 最近几篇压成一个最小可复用骨架，我会写成下面这套：

### 4.1 四个系统角色

1. `Frontdoor / Request Intake`
   - 判断任务类型、风险等级、是否需要协商、是否进入长任务模式
2. `Planner`
   - 把用户目标扩成 spec、约束、done criteria、验收口径
3. `Generator / Executor`
   - 在有限上下文中持续推进实现，写出 artifact 和 progress
4. `Evaluator`
   - 独立验收 outcome，必要时退回 planner 或 generator

### 4.2 五类关键 artifact

1. `Spec`
   - 任务目标、范围、约束、成功标准
2. `Progress Log`
   - 已完成、未完成、阻塞点、下一步
3. `Reference Set`
   - 关键文件、接口、路径、测试、外部依赖
4. `Evaluation Verdict`
   - 通过/失败、失败原因、证据、回退建议
5. `Risk Record`
   - 风险等级、权限边界、是否允许 side effect

### 4.3 三条运行时原则

1. **每轮上下文都应该是可丢弃的**
   - 因为真正的状态在外部 artifact 中
2. **每轮输出都必须可接力**
   - 因为长任务默认要支持 handoff 和 resume
3. **每轮完成都必须可验证**
   - 因为自述完成不算完成

---

## 五、把 Anthropic 主线翻译成 Butler 当前主线

结合 `docs/daily-upgrade/0326/00_当日总纲.md`，Butler 现在已经有一条很接近 Anthropic 方向的骨架：

- `chat/frontdoor`
- `orchestrator/control plane`
- `runtime_os/process runtime`
- `runtime_os/agent runtime`
- `feedback harness`

如果按 Anthropic 这条线继续压实，Butler 的下一版主线可以明确写成：

### 5.1 `4 -> 3 -> 2 -> 1` 仍然成立，但要补一个独立验证面

当前分层：

- `4`：frontdoor / product plane
- `3`：orchestrator / control plane
- `2`：process runtime
- `1`：agent runtime

下一步要补的，不是再加更多执行角色，而是把下面两个东西提成显式对象：

- `planning artifact`
- `evaluation harness`

也就是让系统从“能持续跑”进一步走向“能独立验收”。

### 5.2 `campaign` 不该只是一条执行线，而要是一组工件合同

按 Anthropic 的方式看，长任务系统的真源不应只是：

- 任务启动了
- 分支在推进
- 日志在写回

还应该显式持有：

- 当前 spec 是什么
- done criteria 是什么
- 本轮 handoff 摘要是什么
- evaluator 的 verdict 是什么

这会让 `campaign` 从“后台任务实体”升级成“长任务合同实体”。

### 5.3 `feedback harness` 不能只做通知，还应承接 verifier 回写

Anthropic 的 evaluator 结构提醒我们：

- 反馈面不仅是推送状态
- 更应该承载“为什么通过 / 为什么不通过 / 哪些点待补”

所以 Butler 的反馈主线可以从：

- `started`
- `running`
- `completed`

升级到：

- `accepted`
- `rejected`
- `needs_clarification`
- `needs_fix`

这会让反馈面更像系统 verdict，而不只是运行播报。

### 5.4 当前最值得补的，不是更复杂多 agent，而是更清晰的 planner/evaluator 分离

如果直接照 Anthropic 最新主线翻译，Butler 的优先级应该是：

1. 强化 `planner/spec/done criteria`
2. 把 `generator/executor` 和 `evaluator/reviewer` 分开
3. 用 artifact 化 handoff 取代“对话拖长”
4. 只在真正可并行的任务上再扩 worker

这比一开始就把 orchestrator 再做复杂，更符合最近几篇文章的共识。

---

## 六、当前可执行的主线版本

如果要把这条主线压成一句可指导后续几轮设计的版本，我建议直接写成：

**Butler 下一阶段不再把长任务理解为“chat 把任务送进后台”，而是把它定义为一套围绕 `spec -> execute -> evaluate -> feedback -> resume` 运转的长运行 harness 系统。**

再展开成五条硬约束：

1. **默认先定义合同，再开始执行**
   - 先有 spec 和 done criteria，再有长任务启动
2. **默认把状态写成 artifact，而不是堆在上下文里**
   - session 可以断，但任务不能失忆
3. **默认生成和评估分离**
   - 生成者不拥有最终裁决权
4. **默认 outcome 验收优先于 transcript 漂亮**
   - 看真实结果，不看自述
5. **默认多 agent 只是增量能力，不是基础假设**
   - 没有独立收益，就不拆更多角色

---

## 七、这条主线最重要的反模式

Anthropic 最近几篇文章合起来，也同时在排除几种常见误区：

### 7.1 误把“长上下文”当“长任务能力”

长上下文只能延后问题，不会消灭问题。  
没有 artifact、handoff、reset，长任务仍会漂移。

### 7.2 误把“多 agent”当“系统成熟”

角色数量增加不代表结构更先进。  
没有可分解任务和独立 verifier，多 agent 只是放大复杂度。

### 7.3 误把“模型更强”当“可以不要系统设计”

模型升级只会改变最优 scaffold 的形状，不会让 harness 消失。  
它淘汰的是低价值脚手架，不是系统工程本身。

### 7.4 误把“完成自述”当“真实完成”

没有 evaluator、没有环境验证、没有 outcome verdict，完成就是不可信的。

---

## 八、主线后的开放问题

这条主线已经比较稳，但还有几个值得持续追的前沿问题：

1. `planner` 产出的 spec，什么粒度最合适
2. `evaluator` 应该多独立，是否需要和执行模型不同
3. `context reset` 和 `context compaction` 的最优切换点在哪里
4. 长任务中的 artifact graph，是否应该进一步成为显式数据模型
5. 当模型继续升级时，哪部分 orchestrator 会先被压缩掉

这些问题决定的不是 Anthropic 文章对不对，而是下一阶段大家会在哪些系统边界上继续竞争。

---

## 参考来源

- Anthropic: `Harness design for long-running application development` `2026-03-24`
- Anthropic: `Building a C compiler with a team of parallel Claudes` `2026-02-05`
- Anthropic: `Demystifying evals for AI agents` `2026-01-09`
- Anthropic: `Effective harnesses for long-running agents` `2025-11-26`
- Anthropic: `Effective context engineering for AI agents` `2025-09-29`
- Anthropic: `How we built our multi-agent research system` `2025-06-13`
- Anthropic: `Building effective agents` `2024-12-19`
- Butler: `docs/daily-upgrade/0326/00_当日总纲.md`
