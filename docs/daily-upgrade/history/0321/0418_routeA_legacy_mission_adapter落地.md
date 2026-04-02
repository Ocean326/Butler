# 0321 Route A：legacy heartbeat mission adapter 首轮落地

## 1. 目的

这一步只做路线 A：

- 不重写旧 heartbeat 主循环
- 不碰新 orchestrator core
- 只把 `talk -> legacy heartbeat` 收敛到稳定 mission 接口后面

目标是先把旧系统包住，而不是继续把旧 heartbeat 的内部耦合往外扩。

---

## 2. 本轮实际落地

本轮新增了两层：

1. mission 协议层
2. legacy heartbeat adapter 层

对应文件：

- `butler_main/butler_bot_code/butler_bot/services/legacy_mission_protocol.py`
- `butler_main/butler_bot_code/butler_bot/services/legacy_heartbeat_mission_adapter.py`
- `butler_main/butler_bot_code/butler_bot/services/talk_heartbeat_ingress_service.py`
- `butler_main/butler_bot_code/tests/test_legacy_heartbeat_mission_adapter.py`

---

## 3. 当前冻结的 Route A 接口

当前 adapter 已实现这五个统一入口：

- `create_mission(request)`
- `get_mission_status(mission_id)`
- `append_user_feedback(mission_id, feedback)`
- `control_mission(mission_id, action)`
- `list_delivery_events(mission_id)`

说明：

- 目前 `mission_id == heartbeat_task_v2.task_id`
- 这是一层 compatibility contract
- 后续新 orchestrator 也应实现同一组接口

---

## 4. 现在的真源与落点

### 4.1 任务真源

当前 mission adapter 背后的真源仍是：

- `state/heartbeat/heartbeat_task_v2.json`

也就是：

- legacy heartbeat 继续跑旧 runtime
- 但 talk 不再直接依赖 `MemoryManager.handle_explicit_heartbeat_task_command(...)`
- talk 现在走 mission adapter

### 4.2 人类可读写区

任务工作区仍然沿用 task workspace：

- `state/task_workspaces/...`

adapter 会把反馈与控制记录继续投到这些工作区里，方便人工查看。

### 4.3 稳定事件区

为了避免 task workspace 因状态桶迁移而漂移，本轮额外加了稳定 mission 事件区：

- `run/heartbeat/legacy_missions/<mission_id>/events.jsonl`
- `run/heartbeat/legacy_missions/<mission_id>/feedback.md`

这个目录是 Route A 的 compatibility runtime 侧日志区，不是未来 orchestrator 的正式 ledger。

---

## 5. talk 当前如何接入

### 5.1 自然语言兼容

`talk_heartbeat_ingress_service` 现在直接把自然语言翻译成 mission 调用，兼容这些入口：

- `放进心跳：整理周报`
- `取消心跳任务 task_id=short-xxx`
- `完成心跳任务 task_id=short-xxx`
- `暂停心跳任务 task_id=short-xxx`
- `恢复心跳任务 task_id=short-xxx`
- `查询心跳任务 task_id=short-xxx`

### 5.2 结构化入口

本轮也补了结构化协议入口：

```text
【talk_heartbeat_mission_json】
{"op":"create_mission","title":"整理周报","detail":"补完本周汇总"}
【/talk_heartbeat_mission_json】
```

已支持：

- `create_mission`
- `get_mission_status`
- `append_user_feedback`
- `control_mission`
- `list_delivery_events`

这一步的意义是：

- talk 可以继续保留自然语言兼容
- 系统内部已经有一条明确的结构化 mission 协议

---

## 6. 现在这层解决了什么

### 6.1 解决的点

- talk 不再直接绑旧 heartbeat 显式任务写入函数
- legacy heartbeat 被 mission gateway 包起来了
- 已经能把任务创建、状态查询、用户反馈、控制、delivery 查询统一表达成 mission 操作
- future orchestrator 可以对齐同一个接口面

### 6.2 没解决的点

- 旧 heartbeat 主循环仍是 legacy
- `MemoryManager` 内部仍有大量历史 heartbeat 逻辑
- 当前 mission adapter 只是兼容层，不是新 orchestrator runtime
- `list_delivery_events` 目前还是轻量 delivery timeline，不是正式 mission ledger

---

## 7. 当前工程判断

这一步已经把路线 A 的核心边界切出来了：

- `talk` 负责入口翻译
- `legacy mission adapter` 负责 compatibility
- `heartbeat_task_v2` 负责 legacy mission truth

因此后续路线 B 可以独立推进：

- 新 orchestrator 只要实现同一组 mission 接口
- talk 就可以在 legacy adapter / new orchestrator 之间切换实现

---

## 8. 下一步建议

路线 A 后续只建议继续做三件事：

1. 把旧 talk / heartbeat 其它隐式入口继续往 mission 协议上收
2. 给 `append_user_feedback / list_delivery_events` 再补更清晰的 DTO 与展示规则
3. 做一个 `legacy adapter` 与 `new orchestrator` 的实现切换点

不建议在路线 A 上继续做：

- 旧 heartbeat 主循环增强
- 继续往 `MemoryManager` 里堆入口逻辑
- 把 compatibility layer 写成新 orchestrator 雏形

---

## 9. 一句话结论

本轮不是在升级旧 heartbeat，而是在旧 heartbeat 外面补了一层 mission compatibility shell，让 talk 先从 legacy 内部结构上脱钩。
