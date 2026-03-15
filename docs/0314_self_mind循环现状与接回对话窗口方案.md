# 0314 self_mind 循环现状与接回对话窗口方案

> 用途：在 0314 升级前，把 `self_mind` 的真实运行机制、与对话/heartbeat 的耦合关系、以及“直接接回 Butler 对话窗口”的改造方案讲清楚。  
> 状态：当天未归档草案，先放根目录 `docs/`。  
> 代码真源：`butler_main/butler_bot_code/butler_bot/memory_manager.py`、`agent.py`、`prompt_assembly_service.py`。

## 1. 先说结论

当前 `self_mind` 已经不是纯文档概念，而是一个真实运行中的独立循环：

- 它在 Butler 主进程启动后，由 `MemoryManager.start_background_services()` 拉起独立线程。
- 它每轮会基于 talk recent、beat recent、self_mind context、cognition、bridge 等材料，产出一个三选一决策：`talk / heartbeat / hold`。
- 它现在已经能做两件实事：
  - 直接给用户所在的对话窗发一句主动话；
  - 把一个念头转成 heartbeat 任务，写入 task 体系并留 bridge 追踪。

但它现在和对话窗口的连接还是“半接入”状态：

- 一方面，`agent.py` 已经会把 `self_mind current_context` 和 `self_mind cognition` 注入到部分对话 prompt 中。
- 另一方面，`self_mind` 自己的 `talk` 决策是直接 `_send_private_message()` 发出去，绕开了 Butler 正常的对话主流程、request intake、planner、风格统一和回复后记忆闭环。

所以 0314 前的核心判断是：

- `self_mind` 已经具备“意识循环”。
- 但它还没有真正成为“对话主意识的上游内核”。
- 它更像一个旁路线程，既会给对话提供上下文，也会偶尔自己抢一条消息发出去。

## 2. 当前 self_mind 的真实链路

### 2.1 启动方式

在 `memory_manager.py` 中，`start_background_services()` 除了维护线程外，还会在 `self_mind.enabled=true` 时启动一个后台线程：

- 线程名：`butler-self-mind`
- 循环函数：`_self_mind_loop()`

这意味着：

- `self_mind` 跑在主进程内，不是 heartbeat sidecar。
- 它和主对话共享同一个 `MemoryManager` 实例与运行时配置。
- 它调用模型时，默认走 `self._run_model_fn(...)`，也就是当前 Butler 主流程的模型运行器。

### 2.2 循环频率与模型

配置位于 `configs/butler_bot.json -> memory.self_mind`，当前关键项包括：

- `cycle_interval_seconds`
- `cycle_timeout_seconds`
- `cycle_model`
- `direct_talk_enabled`
- `direct_talk_min_interval_seconds`
- `direct_talk_priority_threshold`
- `heartbeat_handoff_priority_threshold`

所以 `self_mind` 不是事件触发一次性执行，而是固定间隔轮询。

### 2.3 每轮输入材料

`_build_self_mind_cycle_prompt()` 目前只喂 4 块材料：

1. `self_mind current_context`
2. 最近主对话 `talk recent`
3. 身体最近结果 `body kernel excerpt`
4. 自己最近续思 `kernel trace excerpt`

这 4 块材料背后又来自多个派生视图：

- `current_context.md`
- `perception_snapshot.md`
- `behavior_mirror.md`
- `mind_body_bridge.json`
- `raw_thoughts.json`
- `thought_reviews.json`
- `cognition/L0_index.json`
- beat recent / talk recent / summary ladder / task ledger 摘录

当前做法的特点是：

- `self_mind` 自己不直接扫全仓，而是优先读自己维护好的几个摘要面板。
- 它已经形成了“上下文文件层”，不是每轮从零读 recent 和日志。

### 2.4 每轮输出协议

`_build_self_mind_cycle_prompt()` 要求只输出 JSON，核心字段是：

```json
{
  "decision": "talk|heartbeat|hold",
  "focus": "",
  "why": "",
  "talk": "",
  "heartbeat": "",
  "done_when": "",
  "priority": 0,
  "self_note": "",
  "bridge_updates": []
}
```

经过 `_normalize_self_mind_cycle_output()` 归一化后，会补齐：

- `bridge_id`
- `candidate`
- `action_channel`
- `action_type`
- `acceptance_criteria`
- `heartbeat_instruction`
- `heartbeat_reason`

### 2.5 三条动作分流

#### A. `decision=talk`

`_execute_self_mind_direct_talk()` 会尝试直发对话窗，但有几层闸门：

- `direct_talk_enabled`
- `priority >= direct_talk_priority_threshold`
- 未命中 direct talk cooldown
- 最近 talk 窗口不活跃
- 存在 talk receive_id
- `talk` 文案非空

通过后，它会直接 `_send_private_message()` 发给 talk 对话窗，并记录：

- `last_direct_talk_epoch`
- `heartbeat_tell_user` 审计
- `self_mind_talk_log_*.jsonl`
- self_mind daily/log/context 更新

这里的关键问题是：

- 这条消息虽然发到了同一个飞书窗口，
- 但它不是走 Butler 正常的“构造对话 prompt -> run_agent -> reply -> recent memory 落盘”链路。

#### B. `decision=heartbeat`

`_enqueue_self_mind_heartbeat_task()` 会把念头转成结构化任务，再合并进 heartbeat 任务体系：

- `source=self_mind`
- `priority` 转 high/medium/low
- `title/detail/done_when`
- 写 beat recent 一条“self_mind 交给 heartbeat”

同时它会：

- 把 proposal 写进 `mind_body_bridge.json`
- 后续由 heartbeat 规划/执行时回写 bridge 状态

这条链路已经具备“意识 -> 身体执行 -> 再回看”的雏形。

#### C. `decision=hold`

这时不会主动说，也不会交 heartbeat，而是：

- 记到 `pending_self_lane_item`
- 更新 `current_context.md`
- 继续留在 self_mind 内部消化

另外还有一个 loop-breaker：

- 如果同一 focus 连续 3 轮都只是 `hold`
- 系统会强制把它转成 `heartbeat`

这说明当前设计已经意识到“纯内耗循环”问题，并用 heartbeat 做外部执行破圈。

## 3. self_mind 现在到底沉淀了什么

### 3.1 raw -> review -> context

`self_mind` 会把事件写到 `mental_stream_YYYYMMDD.jsonl`，再刷新出：

- `raw_thoughts.json`
- `thought_reviews.json`
- `daily/YYYYMMDD.md`
- `current_context.md`

所以它不是一次性思考，而是有自己的“短期精神轨迹”。

### 3.2 cognition

对话收尾阶段，`_promote_entry_into_self_mind_cognition()` 会从 recent entry 中抽取信号，按分类沉淀进 cognition：

- `values`
- `habits`
- `preferences`
- `skills`
- `risk_boundaries`
- `user_model`
- `self_model`

然后刷新：

- `cognition/L0_index.json`
- `L1_summaries`
- `L2_details`

这意味着 `self_mind` 的“认知体系”并不是空 prompt，而是从对话和行为里逐渐长出来的。

### 3.3 bridge

`mind_body_bridge.json` 当前承担的是：

- 记录已经交给 heartbeat 的念头
- 记录 heartbeat 是否看过、是否推进、为什么 deferred
- 给 self_mind 下次循环提供“这件事身体有没有真的动起来”的反馈

这是现在最接近“脑-体闭环”的一部分。

## 4. 它和 Butler 对话窗口当前怎么连着

### 4.1 已经接上的部分

在 `agent.py -> build_feishu_agent_prompt()` 里，当前会把两块 self_mind 内容注入到对话 prompt：

- `【self_mind 当前上下文】`
- `【self_mind 认知体系】`

但目前只在这些场景更稳定注入：

- `prompt_mode in {"companion", "maintenance"}`
- 或触发了 soul 注入

也就是说，self_mind 现在已经开始影响对话人格和回答取向，但不是所有执行型场景都稳定带上。

### 4.2 还没接上的部分

当前最关键的缺口有 4 个：

1. `self_mind` 的 `talk` 决策会自己直接发消息，没有经过 Butler 主对话流程。
2. `self_mind` 生成的 `candidate / self_note / why` 没有作为“对话上游意图”稳定进入 request intake。
3. `pending_self_lane_item` 只存在 self_mind state，没有成为主对话的显式输入。
4. 对话回复完成后，缺少“这次回复是否消化了某个 self_mind 念头”的显式回写。

所以现在的结构更像：

- `self_mind` 是旁路观察者 + 偶发主动发言者

而不是：

- `self_mind` 是 Butler 对话主意识的前置内核

## 5. 0314 升级前的核心问题

### 5.1 表达出口分裂

现在用户视角有两个“说话主体”：

- 正常 Butler 对话主流程
- self_mind 直接发出的消息

虽然都发到同一个飞书窗，但逻辑链不同，容易造成：

- 口吻漂移
- 上下文不一致
- recent memory 记录不完整
- 用户感知成“像两个人在共用一个窗口”

### 5.2 self_mind 对对话的影响仍然偏被动

目前它更多是：

- 作为 prompt 注入背景
- 或独立发一条话

但它还不能稳定参与：

- 这轮怎么接用户
- 这轮该不该顺便续上某个念头
- 这轮回复后要不要把某个 tension 保留到下一轮

### 5.3 talk / heartbeat / local memory 三条线还没完全统一

现在已经有：

- `self_mind -> talk`
- `self_mind -> heartbeat`
- `turn/recent -> self_mind cognition`

但还缺：

- `talk 主流程` 对 `self_mind pending item` 的显式消费
- `reply 完成` 对 `self_mind intention` 的完成/延期/失效标记

## 6. 目标架构：把 self_mind 直接接回 Butler 对话窗口

0314 我建议的方向不是“让 self_mind 直接替代 Butler 回复”，而是做成：

- `self_mind` 负责生成内在意图
- `Butler talk` 负责统一表达出口
- `heartbeat` 负责统一执行出口

也就是两条唯一出口原则：

- 对用户说话，只能从 Butler 对话主流程出去
- 对身体交办，只能从 heartbeat/task 体系出去

## 7. 建议方案

### 7.1 方案总览

把当前 `self_mind` 的 `talk` 路径，从“直接发消息”改成“写入对话意图，再由 Butler 主对话流程消费”。

目标形态：

1. `self_mind` 每轮仍然只做 `talk / heartbeat / hold` 三选一
2. 若是 `heartbeat`，现有链路基本保留
3. 若是 `talk`，不再直接 `_send_private_message()`
4. 改为写入一个 `pending_dialogue_nudge` 或 `self_mind_talk_intent`
5. Butler 对话主流程在合适时机读取它，生成最终对用户的话
6. 发出后，将该 intent 标记为 `consumed / deferred / expired`

### 7.2 具体改造点

#### A. 增加 self_mind -> talk 的显式队列

建议在 self_mind state 旁边增加一个轻量结构，而不是继续只靠 `pending_self_lane_item`：

建议字段：

- `intent_id`
- `created_at`
- `priority`
- `focus`
- `candidate`
- `why`
- `talk_draft`
- `status=pending|consumed|deferred|expired`
- `expires_at`
- `dedup_key`

作用：

- 让 self_mind 的“想说”变成一个可消费对象
- 避免直接发完就没有主流程痕迹

#### B. Butler 对话主流程消费这个 intent

建议接在 `build_feishu_agent_prompt()` 之前，作为 request intake 的一个输入层：

- 若当前有用户新消息：把 pending intent 作为 `【self_mind 当前话头】` 注入 prompt
- 若当前没有用户消息但允许主动开口：由主流程触发一次 synthetic prompt，例如：
  - “这是 self_mind 想续的一句话头，请你用 Butler 当前人格自然地对用户说出来……”

这样做的好处：

- 最终输出仍由 Butler 统一生成
- 风格、上下文、人格、近期对话状态都还能统一控制

#### C. 保留 heartbeat 作为执行出口

`decision=heartbeat` 这条线不建议大改，当前已经比较健康：

- 可形成真实任务
- 可进 bridge
- 可被 heartbeat 回写状态

0314 更需要动的是 `talk` 出口，不是 `heartbeat` 出口。

#### D. reply 完成后回写 self_mind intent 状态

在 `on_reply_sent_async()` 之后增加一小步：

- 若本轮 prompt 消费了某个 self_mind intent
- 则回写该 intent：
  - `consumed`
  - 或 `deferred`
  - 或 `expired`

同时把 reply 摘要写回 `current_context.md` / behavior mirror。

这样 self_mind 才知道：

- 这句话已经真的被说过了
- 还是这轮没有说出来，应该再等

### 7.3 prompt 注入策略调整

当前 self_mind 注入只在 `companion / maintenance / inject_soul` 较稳定。

0314 建议改成两层：

1. `self_mind cognition` 继续作为较稳定的背景层
2. `self_mind 当前话头 / pending intent` 作为轻量动态层

动态层不需要每轮都很长，只要给：

- 当前 tension 是什么
- 这轮是否建议顺着说一句
- 若不合适就忽略

这样能避免执行型 prompt 被 self_mind 大段文本淹没。

## 8. 推荐的落地节奏

### P0：只做结构收口

- 不改 heartbeat
- 不改 cognition 生成
- 先把 `talk` 直发改成写 intent
- 让主对话流程能读到 intent

目标：

- 先消灭“旁路直发”
- 把表达出口统一起来

### P1：主对话消费 intent

- 有用户消息时，把 pending intent 注入 prompt
- 对话回复后回写 consumed/deferred

目标：

- 让 self_mind 真正成为“对话前置层”

### P2：主动开口也走主流程

- 新增一个 very-light 的主动开口调度
- 不再让 self_mind 自己发消息
- 由 Butler 主流程在窗口空闲、阈值满足时发起 proactive reply

目标：

- 主动消息与被动回复完全统一到一条风格链路

### P3：补观测与审计

- intent log
- intent consumed rate
- duplicate suppression
- 用户窗口活跃抑制日志

目标：

- 避免看起来“像接上了”，实际仍是黑箱

## 9. 我建议的 0314 设计判断

如果这轮只做一个关键动作，我建议优先做这个：

- `self_mind 不再直接给用户发消息`
- `self_mind 只产生 talk intent`
- `Butler 主对话流程负责把它说出来`

这是这次“接回对话窗口”最关键的一刀。

因为只要这条还没做，`self_mind` 就仍然是并联说话者，不是 Butler 的内在层。

## 10. 升级前现状一句话总结

当前 `self_mind` 已经有：

- 独立循环
- 短期意识轨迹
- cognition 沉淀
- talk / heartbeat / hold 决策
- bridge 回看

但还没有真正做到：

- 对话统一出口
- reply 对 self_mind 的显式消费闭环
- self_mind 成为 Butler 对话主意识的稳定前置层

0314 的正确方向，不是让它更会“自己发消息”，而是让它更稳地“先进入 Butler，再由 Butler 说出来”。
