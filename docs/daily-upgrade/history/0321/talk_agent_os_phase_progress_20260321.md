# Talk + AgentOS Phase 0-5 推进结果

日期：2026-03-21

---

## Phase 0

状态：`通过`

完成依据：

- 三层命名已形成：`TalkRouter / MissionOrchestrator / AgentRuntime`
- 输入输出主合同已形成：`Invocation / OutputBundle / DeliverySession / WorkflowReceipt`
- heartbeat 已被标记为 `legacy-compatible, no new feature`

残留约束：

- 主线后续不得重新把前后台统称为 `orchestrator`

---

## Phase 1

状态：`ready，待主线接线`

已经具备：

- `FeishuInputAdapter`
- `TalkRouter`
- `FeishuDeliveryAdapter`
- `OutputBundle`

未完成项：

- 旧 talk 主入口接线
- delivery transport 接线

---

## Phase 2

状态：`route-ready`

已经具备的路由口：

- `talk`
- `self_mind`
- `direct_branch`
- `mission_ingress`

未完成项：

- 这四类入口的真实运行时承接

---

## Phase 3

状态：`未完成`

原因：

- `MissionOrchestrator` 仍只有协议层，没有 Butler 产品级后台 runtime

---

## Phase 4

状态：`adapter-ready`

已经具备：

- `FeishuReplySession`
- `create / update / finalize`
- `OutputBundle` 到飞书消息类型的映射

未完成项：

- 飞书真实 transport
- 与旧 reply 流程的替换

---

## Phase 5

状态：`frozen，未到退场条件`

已经具备：

- heartbeat legacy 边界说明
- 替换方向：`TalkRouter -> mission ingress`

未完成项：

- 新 ingress 稳定
- 新后台 mission 承接点
- 新 delivery 回传链

---

## 第三路建议结论

现在不该宣布“phase0-5 全完成”。  
正确结论是：

- `Phase 0` 完成
- `Phase 1/2/4` 已进入可接线状态
- `Phase 3/5` 还只能继续推进，不能宣告完成
