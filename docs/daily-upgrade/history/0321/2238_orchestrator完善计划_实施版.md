# Orchestrator 完善计划（实施版）

日期：2026-03-21
时间标签：0321_2238

本文是对 [Talk + AgentOS 升级计划（v2）](C:/Users/Lenovo/Desktop/Butler/docs/daily-upgrade/0321/talk_agent_os_upgrade_plan_20260321.md) 中 `MissionOrchestrator` 部分的实施化收口。

目标不是再讲一遍抽象边界，而是把“接下来怎么把 orchestrator 推成产品级后台 runtime”写成可施工版本。

---

## 1. 先校正口径

按当前 v2 计划，`MissionOrchestrator` 对应的是 `Phase B`，不是 `Phase D`。

- `Phase B`：继续独立推进 `MissionOrchestrator`
- `Phase C`：落地 `TalkRouter`
- `Phase D`：重做 `Feishu delivery session`

因此，当前若要“从 orchestrator 开始推进”，准确说法应是：

> 把 `Phase B` 从“协议层完成”推进到“产品层完成”，并允许它与 `Phase D` 并行，而不是把两者混为一步。

---

## 2. 当前现状判断

结合当前仓库代码，orchestrator 相关部分已经不是空白，而是处于“骨架已成，产品闭环未成”的阶段。

### 2.1 已有部分

已有核心目录：

- `butler_main/butler_bot_code/butler_bot/orchestrator/`
- `butler_main/butler_bot_code/butler_bot/orchestrators/mission_orchestrator.py`
- `butler_main/butler_bot_code/butler_bot/orchestrator/runner.py`
- `butler_main/butler_bot_code/tests/test_orchestrator_runner.py`

已有核心对象和能力：

- `Mission / MissionNode / Branch / LedgerEvent`
- `FileMissionStore / FileBranchStore / FileLedgerEventStore`
- `OrchestratorService`
- `OrchestratorScheduler`
- `ButlerMissionOrchestrator`
- `runner` 独立 tick / dispatch

### 2.2 当前缺口

虽然对象已经有了，但还存在四个关键缺口：

1. 还没有明确“产品级 orchestrator 的最小闭环验收”
2. `orchestrator/` 和 `orchestrators/mission_orchestrator.py` 的职责还容易混
3. `MissionOrchestrator -> AgentRuntime` 的真实执行桥还未打通
4. talk 侧还没有通过统一 gateway 稳定消费 orchestrator，而仍主要停留在骨架和 legacy ingress 并存状态

因此当前最准确的判断是：

> 现在不缺“再规划一个 orchestrator”，而是缺“把已有 orchestrator 收成一个清晰可接线的产品级后台 runtime”。

---

## 3. 本实施版的目标

本轮只做一件事：

> **把 orchestrator 推到“可作为新后台 mission runtime 被主链接线”的程度。**

本轮完成后，期望达到的状态是：

1. `orchestrator/` 成为后台 mission 真源与 runtime core
2. `orchestrators/mission_orchestrator.py` 成为产品层包装与 talk-facing gateway
3. `MissionOrchestrator` 能稳定执行 `create / status / control / feedback / delivery_events`
4. `runner` 能独立推进 mission，不依赖旧 heartbeat 主循环
5. talk 后续只需做接线，而不需要再替 orchestrator 补领域模型

---

## 4. 明确边界

### 4.1 `butler_bot/orchestrator/` 的职责

这一层是后台 runtime core。

只负责：

- `Mission / Node / Branch / Ledger` 真源
- mission 状态机
- ready node 激活
- dispatch / collect / judge / retry / timeout / park / cancel
- runtime tick
- runtime state 与 ledger 落盘

不负责：

- Feishu event 解析
- Butler persona / prompt 组装
- reply/update/push 交互细节
- talk recent/local memory 读取规则

### 4.2 `butler_bot/orchestrators/mission_orchestrator.py` 的职责

这一层是产品层 mission gateway。

只负责：

- 接 `RuntimeRequest`
- 调用 `orchestrator service`
- 产出 `RouteProjection / WorkflowProjection / WorkflowReceipt / OutputBundle`
- 对 talk 暴露稳定 mission ingress/query/control 接口面

不负责：

- 自己保存 mission 真源
- 自己实现 scheduler / branch store / event store
- 直接承担 delivery transport

### 4.3 `agents_os` 的职责

这一层是中性 substrate。

只负责：

- contracts
- projections
- receipts
- capability interface
- runtime request / execution context 的中性表达

不负责：

- Butler 产品层 mission 领域模型
- legacy heartbeat 兼容逻辑
- Feishu 输出样式

---

## 5. 本轮不做什么

以下内容明确不纳入本实施版：

1. 不重写旧 `heartbeat_orchestration.py`
2. 不把 `MemoryManager` 搬进 orchestrator
3. 不让 orchestrator 承担 talk prompt 装配
4. 不把 `Feishu delivery session` 当成 orchestrator 的 blocker
5. 不在本轮引入顶层 `Decision Layer`
6. 不追求一次支持所有 research workflow

一句话：

> 这轮做的是“后台 runtime 产品化”，不是“整套 Butler 大迁移”。

---

## 6. 施工主线

本轮按 `B0 -> B5` 推进。

### B0：冻结领域边界与目录职责

目标：

- 明确 `orchestrator/` 是 runtime core
- 明确 `orchestrators/mission_orchestrator.py` 是产品层 gateway
- 明确 `MissionOrchestrator` 与 `TalkRouter` 不混名

交付：

- 本文档
- 必要 README / 模块注释补充

Done 标准：

- 后续新增代码不再把 runtime core 写回 `talk` 或 `MemoryManager`

### B1：收紧 mission 真源模型

目标：

- 把 `Mission / MissionNode / Branch / LedgerEvent` 视为唯一真源对象
- 补齐最小状态机与字段口径

重点：

- mission 状态：`draft / ready / running / blocked / awaiting_decision / completed / failed / parked / cancelled`
- node 状态：`pending / ready / dispatching / running / partial_ready / awaiting_judge / repairing / blocked / done / failed / skipped`
- branch 状态：`queued / leased / running / succeeded / failed / timed_out / cancelled`

优先写集：

- `butler_main/butler_bot_code/butler_bot/orchestrator/models.py`
- `butler_main/butler_bot_code/butler_bot/orchestrator/mission_store.py`
- `butler_main/butler_bot_code/butler_bot/orchestrator/branch_store.py`
- `butler_main/butler_bot_code/butler_bot/orchestrator/event_store.py`

Done 标准：

1. core status 枚举稳定
2. mission summary 输出稳定
3. store 层可以独立支撑 mission 全生命周期

### B2：打通 runtime loop

目标：

- 让 `runner` 与 `service.tick()` 真正成为后台推进主循环

重点：

- ready node 激活
- dispatch budget
- running branch 收割
- judge 后继续 / repair / finish / park
- watchdog / run_state / pid / lock 归位

优先写集：

- `butler_main/butler_bot_code/butler_bot/orchestrator/service.py`
- `butler_main/butler_bot_code/butler_bot/orchestrator/scheduler.py`
- `butler_main/butler_bot_code/butler_bot/orchestrator/policy.py`
- `butler_main/butler_bot_code/butler_bot/orchestrator/runner.py`
- `butler_main/butler_bot_code/tests/test_orchestrator_runner.py`

Done 标准：

1. `runner --once` 可以完成一次稳定 tick
2. mission 至少能从 `ready` 推到 `running`
3. dispatch / judge / ledger 有连续事件链

### B3：补 execution bridge

目标：

- 把 `MissionOrchestrator -> AgentRuntime` 的桥接定义清楚
- 让 node 不只是“被标记 running”，而是真能挂接执行层

本阶段最小要求：

- 先允许 stub execution
- 但接口必须按未来真执行设计

建议接口输入：

- `Invocation`
- `AgentSpec`
- `RouteProjection`
- `WorkflowProjection`
- mission/node/branch metadata

建议接口输出：

- `ExecutionReceipt`
- `OutputBundle`
- artifact refs
- branch result payload

优先写集：

- `butler_main/agents_os/runtime/orchestrator.py`
- `butler_main/butler_bot_code/butler_bot/orchestrators/mission_orchestrator.py`
- `butler_main/butler_bot_code/butler_bot/orchestrator/judge_adapter.py`
- 必要的 execution bridge 文件

Done 标准：

1. node dispatch 不再只是本地状态翻转
2. branch result 能被 receipt 化并回写 mission
3. orchestrator 不直接知道 Feishu transport 细节

### B4：收成 talk-facing mission gateway

目标：

- 把产品层入口统一收在 `ButlerMissionOrchestrator`
- 对 talk 暴露稳定的 mission 操作面

稳定操作集：

- `create`
- `status`
- `control`
- `feedback`
- `delivery_events`

优先写集：

- `butler_main/butler_bot_code/butler_bot/orchestrators/mission_orchestrator.py`
- `butler_main/butler_bot_code/butler_bot/services/orchestrator_ingress_service.py`
- `butler_main/butler_bot_code/butler_bot/services/orchestrator_query_service.py`

Done 标准：

1. talk 后续只需要接 `RuntimeRequest`
2. talk 不再需要知道 `mission_store / event_store / branch_store` 的内部结构
3. `MissionOrchestrator` 可以替代 legacy adapter 成为新主链候选实现

### B5：补齐产品级验收与切换条件

目标：

- 明确什么时候 orchestrator 才算“可以接主链”

至少满足：

1. 独立创建 mission
2. 独立查询 mission
3. 独立暂停 / 恢复 / 取消 mission
4. 独立记录 feedback
5. 独立列出 delivery events
6. 独立 runner tick
7. 不依赖旧 heartbeat 主循环

切主链前置条件：

- 普通 `talk` 主链已接到 `TalkRouter`
- orchestrator 至少完成一条非 legacy mission ingress 链
- `heartbeat` 仍保留 compatibility shell

---

## 7. 推荐文件分工

为避免继续混乱，后续推荐按下面分工推进。

### 核心域模型与状态

- `butler_bot/orchestrator/models.py`
- `butler_bot/orchestrator/mission_store.py`
- `butler_bot/orchestrator/branch_store.py`
- `butler_bot/orchestrator/event_store.py`

### 调度与运行时

- `butler_bot/orchestrator/service.py`
- `butler_bot/orchestrator/scheduler.py`
- `butler_bot/orchestrator/policy.py`
- `butler_bot/orchestrator/runner.py`
- `butler_bot/orchestrator/workspace.py`

### 产品层包装

- `butler_bot/orchestrators/mission_orchestrator.py`
- `butler_bot/services/orchestrator_ingress_service.py`
- `butler_bot/services/orchestrator_query_service.py`

### 中性 substrate

- `agents_os/runtime/orchestrator.py`
- `agents_os/runtime/projection.py`
- `agents_os/runtime/receipts.py`
- `agents_os/factory/*`

---

## 8. 测试与验收清单

本轮至少应补这四类测试。

### 8.1 store / model 测试

- mission 保存与重载
- node / branch / event 序列化
- 非法状态归一化

### 8.2 service / scheduler 测试

- ready node 激活
- dispatch budget 限制
- judge verdict 后状态流转
- repair exhausted / park / cancel

### 8.3 runner 测试

- `--once` 写 runtime state
- auto dispatch 生效
- mission / node 状态能被 runner 推进

### 8.4 gateway 测试

- `create/status/control/feedback/delivery_events`
- `WorkflowReceipt / OutputBundle / DeliveryRequest` 产出稳定

---

## 9. 与其它主线的关系

### 9.1 与 TalkRouter 的关系

`TalkRouter` 不是本轮 blocker。

但本轮交付必须满足：

- 后续 `TalkRouter` 只需要决定“是否路由到 mission ingress”
- 不需要替 orchestrator 再补领域模型

### 9.2 与 Feishu delivery session 的关系

`Feishu delivery session` 不是本轮 blocker。

本轮只需保证：

- orchestrator 能产出 `OutputBundle`
- 产品层能产出 `DeliveryRequest`

至于 `reply/update/push` 的 transport 接线，属于并行主线，不阻塞 orchestrator 产品化。

### 9.3 与 heartbeat 的关系

heartbeat 保持：

- `legacy-compatible`
- `no new feature`

本轮不以“替掉 heartbeat”为目标，而以“形成可替代 heartbeat 的新后台 runtime”为目标。

---

## 10. 一句话实施结论

从现在开始，orchestrator 主线不再叫“继续想设计”，而应叫：

> **把已有 `orchestrator/` 收成独立后台 mission runtime，把已有 `mission_orchestrator.py` 收成 talk-facing gateway，然后用 runner、gateway、tests 把它推到可接主链的程度。**

这就是本轮的实施边界。
