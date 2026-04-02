# Talk + AgentOS 第三路总装评审

日期：2026-03-21

关联输入：

- `talk_agent_os_upgrade_plan_20260321.md`
- `talk_agent_os_gpt54_dual_lane_task_package_20260321.md`
- `talk_agent_os_gpt54_third_lane_total_assembly_20260321.md`

---

## 一、总装结论

第三路总装结论如下：

1. `Phase 0` 已基本成型，可以视为“边界冻结候选”
2. `Phase 1` 已具备最小接线骨架，但还没有接入旧主链
3. `Phase 2` 的前台路由口已经命名齐全，但仍只是前台骨架
4. `Phase 3` 仍停留在中性 runtime protocol / contract 层，没有独立的产品级 `MissionOrchestrator`
5. `Phase 4` 已有 `FeishuReplySession` 抽象，但 transport 仍故意未接
6. `Phase 5` 的 heartbeat 已完成“冻结与标界”，但距离退主链还差新 ingress 落地

换句话说：

本轮第三路可以认定“总装框架已成”，但不能认定“主链迁移已完成”。

---

## 二、当前已成立的骨架

### 1. AgentOS 中性 contract 已成立

当前已经存在的核心对象：

- `Invocation`
- `PromptProfile`
- `PromptContext`
- `MemoryPolicy`
- `OutputBundle`
- `DeliverySession`
- `RouteProjection`
- `WorkflowProjection`
- `ExecutionReceipt`
- `WorkflowReceipt`
- `SubworkflowCapability`

这说明 `agent_os` 至少已经形成一套可被前台骨架消费的中性词表。

### 2. Butler 前台新骨架已出现

当前已经存在：

- `FeishuInputAdapter`
- `ButlerPromptProfileAdapter`
- `ButlerMemoryPolicyAdapter`
- `FeishuDeliveryAdapter`
- `TalkRouter`
- `legacy/heartbeat_boundary.py`

这说明前台骨架已经从“口头规划”进入“代码占位”。

### 3. heartbeat 的新定位已经明确

当前已明确：

- `heartbeat = legacy-compatible, no new feature`
- `TalkHeartbeatIngressService` 被定义为旧兼容边界
- 新前台入口目标是 `TalkRouter -> mission ingress`

这一点非常关键，因为它阻止了旧 heartbeat 继续向新架构渗透。

---

## 三、第三路发现的关键问题

### 1. `MissionOrchestrator` 仍只有协议层，没有产品级落点

现状：

- `agents_os/runtime/orchestrator.py` 中已经有 `MissionOrchestrator` protocol
- 但 Butler 产品侧还没有独立的后台 mission runtime 实现

影响：

- `Phase 3` 还不能说真正启动
- 当前 `mission_ingress` 只能算路由概念已对齐，不能算后台运行时已接好

结论：

必须把 `MissionOrchestrator` 继续视为下一阶段主线工作，而不是本轮已完成项。

### 2. `FeishuDeliveryAdapter` 还没有真实 transport 接线

现状：

- `FeishuReplySession` 已经支持 `create / update / finalize`
- 但 `deliver()` 明确返回 `transport_not_connected`

影响：

- `Phase 4` 只能认定为 session abstraction 已就位
- 不能认定为飞书交互层升级已完成

结论：

主线下一步应只做最小接线，不应误判为 delivery 已落成。

### 3. `TalkRouter` 已到位，但还没有主链入口替换

现状：

- `TalkRouter` 已具备：
  - route decision
  - runtime request build
  - prompt profile / memory policy adapter consumption
  - delivery session build

但当前仍未接入：

- `agent.py`
- `butler_bot.py`

影响：

- `Phase 1` 还只是“ready for mainline wiring”
- 用户侧真实 talk 入口尚未迁移

### 4. 仍需警惕“orchestrator”名字回流混用

现状：

- `TalkRouter` 命名已经清晰
- 但 `agents_os/runtime/orchestrator.py` 里还存在一个通用 `Orchestrator`

影响：

- 主线若后续继续在 Butler 产品文档和代码里泛用 `orchestrator`，仍会把前台与后台重新混掉

结论：

后续主线必须坚持：

- 产品前台只叫 `TalkRouter`
- 产品后台只叫 `MissionOrchestrator`
- `agent_os` 里的中性 `Orchestrator` 只作为底层泛型容器，不回流为产品层主名

### 5. `mission_ingress` 现在仍偏“路由概念”，不是“完整产品链”

现状：

- `FeishuInputAdapter` 能识别 heartbeat marker / mission hint
- `TalkRouter` 能把其归到 `mission_ingress`
- legacy heartbeat boundary 也已标界

但当前尚未补齐：

- 新 mission ingress 的后台承接器
- 主链接线
- 结果回传链路

结论：

heartbeat 还不能退场，最多只能继续冻结。

---

## 四、Phase 0-5 推进判断

### Phase 0：冻结边界与命名

状态：`基本完成，可进入主线采纳`

已经具备：

- `TalkRouter / MissionOrchestrator / AgentRuntime` 三层命名
- `Invocation / OutputBundle / DeliverySession / WorkflowReceipt` 等关键词表
- heartbeat 已被标成 legacy

仍需注意：

- 主线不要重新使用含混的 `orchestrator`

### Phase 1：最小 talk 黄金路径

状态：`骨架完成，待主线最小接线`

已经具备：

- `FeishuInputAdapter`
- `TalkRouter`
- `OutputBundle`
- `FeishuDeliveryAdapter`

未完成：

- 老主链接线
- 真正可用的 delivery transport

### Phase 2：前台路由口补齐

状态：`命名完成，运行未完成`

已覆盖路由口：

- `talk`
- `self_mind`
- `direct_branch`
- `mission_ingress`

未完成：

- 对应运行时的主线承接

### Phase 3：MissionOrchestrator 独立成形

状态：`未完成`

原因：

- 当前只有中性 protocol / contract
- 没有独立 Butler mission runtime

### Phase 4：Feishu delivery session 升级

状态：`抽象完成，transport 未完成`

已完成：

- `create / update / finalize`
- 基于 `OutputBundle` 选择消息类型

未完成：

- 真实发卡片、发图片、发文件的 transport 绑定
- reply/update/push 与旧飞书发送链路的替换

### Phase 5：heartbeat 退主链准备

状态：`冻结完成，退场未就绪`

已完成：

- legacy 边界说明
- 退场方向说明

未完成：

- 新 talk ingress 稳定
- 新 mission ingress 后台承接
- 新结果回传链路

---

## 五、第三路给主线的动作建议

下一步主线最应该做的，不是继续开大规划，而是：

1. 只挑一条普通 talk 请求，走最小黄金路径接线
2. 先不碰 heartbeat 退场
3. 先不碰大规模 prompt/memory runtime 迁移
4. 先验证 `Invocation -> TalkRouter -> OutputBundle -> FeishuDeliveryAdapter`
5. 验证通过后，再补 `self_mind / direct_branch / mission_ingress`

---

## 六、第三路最终判断

如果按第三路标准来判断：

- `Phase 0` 可以判为通过
- `Phase 1` 可以判为 ready
- `Phase 2` 可以判为 route-ready
- `Phase 3` 仍未开始真正产品化
- `Phase 4` 可以判为 adapter-ready
- `Phase 5` 只能判为 frozen，不可判为 removable

因此本轮最合理的推进方式是：

先把主线最小接线打通，而不是过早宣布 heartbeat 已经被替换。
