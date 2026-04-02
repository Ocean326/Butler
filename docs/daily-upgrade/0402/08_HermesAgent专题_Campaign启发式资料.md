# 0402 Hermes Agent 专题：Campaign 启发式资料

日期：2026-04-02
对象：`NousResearch/hermes-agent`

---

## 1. 一句话裁决

Hermes 对 Butler Campaign 的最好吸收方式是：

> 只吸收“执行支撑层”的工程启发，不动 Butler 当前 `campaign ledger / workflow_session / turn receipt` 真源口径。

---

## 2. 应吸收的启发

### 2.1 为 Campaign 补更清晰的调度桥接层

Hermes cron 说明：

- 定时触发
- 执行
- 保存
- 投递

是可以单独成层的。  
Butler 后续如果强化 schedule/auto-run，最好把它做成：

- 外层 trigger/scheduler
- 内层 campaign 领域合同

而不是把 scheduler 写进 ledger 真源。

### 2.2 强化 worker/child turn 的隔离合同

Hermes `delegate_tool` 很适合提供以下启发：

- child 上下文隔离
- child 工具集裁剪
- parent 只收摘要
- 并发有上限

这可直接帮助 Butler 继续收紧：

- `agent turn`
- `worker sidecar`
- `handoff receipt`

### 2.3 强化 delivery 目标抽象

Hermes 的 cron delivery 说明：

- 结果并不一定只回到当前入口

Butler 可以进一步明确：

- query 面
- feedback notifier
- console/operator
- 外投渠道

各自的职责与桥接边界。

### 2.4 把轨迹、账本、实验输出彻底分层

Hermes 明确区分：

- session store
- batch trajectories

Butler 也应继续坚持：

- ledger/receipt 是治理真源
- 训练轨迹、长日志、临时输出是旁路资产

---

## 3. 不应吸收的部分

### 3.1 不把 cron job 升格成 campaign 真源

Hermes 的 job/scheduler 很实用，但 Butler 的 campaign 不应退化成“一个定时任务记录”。

### 3.2 不把 session DB 当成 campaign 状态机

Campaign 需要：

- execution state
- closure state
- latest receipt
- acceptance 结果

这些不是普通会话库能替代的。

### 3.3 不把 batch runner 误当 operator console

Hermes 的 batch_runner 偏批跑执行与统计。  
Butler 的 console/operator 面仍应围绕：

- 宏摘要
- query/feedback
- recovery decision

来设计。

---

## 4. 推荐实验

### 实验 A：schedule -> campaign bridge

目标：

- 做一个只负责触发的 scheduler 桥接层

验收：

- 不改变 campaign ledger 真源
- 能把 trigger 来源写清楚

### 实验 B：child turn receipt 模板

目标：

- 为 worker/child 运行固定摘要模板

验收：

- parent 不读长日志也能判断结果

### 实验 C：delivery target 抽象

目标：

- 统一“回前门 / 发反馈 / 发外部渠道”的目标表达

验收：

- 不同渠道只改 adapter，不改 campaign 真源

---

## 5. 最终结论

Hermes 不能指导 Butler 重写 campaign 架构；  
它真正能提供的，是对以下判断的外部背书：

1. 调度应独立于账本真源
2. 子任务必须隔离并摘要回流
3. delivery 与 trajectory 应作为支撑层，而不是反客为主定义领域模型
