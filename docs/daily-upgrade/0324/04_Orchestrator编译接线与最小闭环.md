---
type: "note"
---
# 04 Orchestrator 编译接线与最小闭环

日期：2026-03-24
时间标签：0324_0004
状态：计划中

## 目标

1. 让 `orchestrator` 开始消费 workflow，而不是继续停留在 branch 级对象搬运。
2. 建立 `mission/node -> compile -> workflow -> execute -> writeback` 的最小闭环。
3. 明确 `orchestrator` 是 mission/control plane，而不是超级 agent。
4. 把 `chat` 到 `orchestrator` 的最小接线正式纳入闭环，而不是继续停留在“前台能说、后台能跑、但中间协议口径分散”的状态。

## 今日要完成的事

1. 明确 node 编译到 workflow 的入口。
2. 明确 branch 与 workflow 的关系。
3. 明确 workflow 执行完成后如何回写：
   - node status
   - branch status
   - artifacts
   - receipts
4. 让 `orchestrator` 不再只是“调 execution bridge 一次然后等结果”。
5. 明确 `orchestrator` 与 package / runtime binding 的边界：
   - 它负责挑选什么
   - 它不负责亲自执行什么
6. 明确 `chat -> mission ingress -> orchestrator -> workflow -> execute -> writeback -> chat` 的最小闭环。
7. 明确 `chat` 与 `orchestrator` 的最小交互接口：
   - `create`
   - `status`
   - `control`
   - `feedback`
8. 明确前台与后台的职责边界：
   - `chat` 负责对话入口、用户意图承接、状态展示、结果汇报
   - `orchestrator` 负责任务受理、workflow 编译、执行推进、回写与治理
9. 明确 `04` 与 `08` 的边界：
   - `04` 只关心 `chat` 如何接到 `orchestrator` 主闭环
   - `08` 继续负责 CLI / 飞书 / 微信三条前台渠道的交付细节与能力差异

## 验收标准

1. 存在一条最小 workflow-backed orchestrator 闭环。
2. `orchestrator` 开始变成真正的 control plane，而不是 branch 调用器。
3. `orchestrator` 没有滑回 “聊天 agent 拿工具全管” 的实现方向。
4. 存在一条从 `chat` 发起、由 `orchestrator` 承接、再回到 `chat` 汇报的最小闭环。
5. `chat` 与 `orchestrator` 的接口不再靠隐式 metadata 和历史兼容壳维持，而开始形成稳定口径。
