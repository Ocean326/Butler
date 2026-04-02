# 0402 Hermes Agent 专题：Campaign 详细参考学习资料

日期：2026-04-02
对象：`NousResearch/hermes-agent`
主题：Hermes 对 Butler `campaign` 的可参考部分与不可参考部分

---

## 1. 先给结论

Hermes **没有** Butler 当前这种显式的：

- `campaign ledger`
- `workflow_session`
- `latest_turn_receipt`
- `canonical_session_id`

所以 Hermes 不能当作 Butler Campaign 的一一对应实现参考。  
但它在“长任务执行壳”上提供了三类很有价值的工程证据：

1. `cron` 调度
2. `delegate_tool` 子任务隔离
3. `batch_runner` / `trajectory` / `delivery` 这类长期运行支撑件

---

## 2. Hermes 中与 Campaign 最接近的三层

### 2.1 cron：自然语言计划任务 + 外投递

`cron/scheduler.py` 显示：

- 定时 tick
- file lock 防重入
- 找到 due jobs
- 保存输出
- 可投递回 origin 或指定平台

这说明 Hermes 的“长任务”更接近：

- 定时自动运行 agent
- 结果投递给某个聊天入口

而不是 Butler 这种显式 campaign 宏账本。

### 2.2 delegate：父子任务隔离

`tools/delegate_tool.py` 显示：

- parent/child 隔离
- child 工具裁剪
- child 独立 session
- batch parallel
- 深度限制

这非常适合作为 Butler Campaign 中 `agent turn` 或 `worker turn` 的“隔离执行”对照证据。

### 2.3 batch_runner：批量长任务与训练数据壳

`batch_runner.py` 展示了：

- dataset batching
- multiprocessing
- checkpoint/resume
- trajectory 保存
- tool stats 聚合

这说明 Hermes 在“离线/批量任务壳”上已经工程化，但它的主抽象仍不是 campaign ledger。

---

## 3. Hermes 与 Butler Campaign 的关键差异

| 维度 | Hermes | Butler Campaign | 结论 |
| --- | --- | --- | --- |
| 长任务主抽象 | cron job / batch run / delegated task | campaign ledger / workflow_session / agent turn receipt | Butler 更强、更清晰 |
| 状态真源 | session DB + job/output 文件 + batch checkpoints | campaign domain + receipt + summary + canonical session | Butler 真源更集中 |
| 查询面 | 偏 session/job 读取 | query/feedback/console | Butler 更产品化 |
| 恢复面 | job rerun / batch resume / session resume | resume_campaign / turn receipt / macro summary | Butler 恢复语义更明确 |
| 外投递 | gateway delivery 很成熟 | feedback/query/console 分工更清楚 | Hermes 强在跨平台投递，Butler 强在领域合同 |

---

## 4. Hermes 对 Butler Campaign 有价值的具体点

### 4.1 “调度”应该和“执行”解耦

Hermes cron 并没有把 scheduler 直接写成会话本身，而是：

- 找 due jobs
- 运行
- 保存输出
- 投递结果

这对 Butler Campaign 的启发是：

- campaign 领域合同要继续独立
- schedule/trigger 可以是外层桥接，而不是把调度揉进 ledger 真源

### 4.2 子任务必须隔离

Hermes 子代理有：

- 独立上下文
- 工具裁剪
- 深度限制
- 返回摘要而非全过程

这和 Butler 当前 `agent turn receipt` 思路一致：

- 主线看到的是受控回执
- 不是把所有执行细节无边界暴露

### 4.3 delivery 不应只靠当前前门

Hermes cron 可以：

- deliver 到 origin
- deliver 到指定平台

这提醒 Butler：

- `campaign` 结束后的反馈与投递
- 不应只绑定某一种当前入口

### 4.4 轨迹与在线会话最好分层保存

`hermes_state.py` 明确写到：

- batch runner 和 RL trajectories 不进同一个 session store

这对 Butler 很重要。  
Campaign 的 ledger / summary / receipt 不应和训练轨迹、实验输出混成一层。

---

## 5. Hermes 不能直接给 Butler Campaign 提供什么

### 5.1 不能替代宏账本

Hermes 没有 Butler 那种显式的：

- `campaign -> workflow_session -> turn receipt -> harness`

主线结构。

### 5.2 不能替代 query/feedback 口径

Hermes 有结果投递，但没有 Butler 这种稳定的：

- query
- feedback
- operator/console

领域面。

### 5.3 不能替代 phase/receipt/acceptance 合同

Hermes 的 cron 与 batch 更偏执行器。  
Butler Campaign 还承担：

- 计划推进
- review/acceptance
- 残余风险总结

这是更高层的控制面职责。

---

## 6. 对 Butler Campaign 的参考结论

Hermes 对 Butler Campaign 的主要价值不是“告诉我们 campaign 该怎么设计”，而是：

1. 证明调度、子任务、投递、轨迹都值得拆成支撑层
2. 证明长任务执行时“隔离子任务 + 摘要回流”是可行的
3. 证明 campaign 真源不该和训练/批跑/会话 DB 混层

也就是说，Hermes 是 Butler Campaign 的**执行支撑层参考**，不是**领域真源参考**。

---

## 7. 证据清单

- `MyWorkSpace/TargetProjects/hermes-agent/upstream/hermes-agent-main/tools/delegate_tool.py`
- `MyWorkSpace/TargetProjects/hermes-agent/upstream/hermes-agent-main/cron/scheduler.py`
- `MyWorkSpace/TargetProjects/hermes-agent/upstream/hermes-agent-main/batch_runner.py`
- `MyWorkSpace/TargetProjects/hermes-agent/upstream/hermes-agent-main/gateway/session.py`
- `MyWorkSpace/TargetProjects/hermes-agent/upstream/hermes-agent-main/hermes_state.py`
- `docs/project-map/02_feature_map.md`
- `docs/project-map/03_truth_matrix.md`
- `docs/daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md`
- `docs/daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md`
