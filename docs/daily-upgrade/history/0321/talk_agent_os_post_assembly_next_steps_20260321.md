# Talk + AgentOS 总装后推进顺序

日期：2026-03-21

---

## 一、推进原则

总装完成后，不要立刻进入“大迁移”。  
正确顺序是：

- 先冻结词表与边界
- 再跑最小黄金路径
- 再替换 talk 前台 ingress
- 再升级 Feishu delivery session
- 最后才讨论 heartbeat 退主链

---

## 二、阶段推进

### Phase 0：冻结边界与命名

目标：

- 冻结 `TalkRouter / MissionOrchestrator / AgentRuntime` 三层命名
- 冻结 `Invocation / OutputBundle / DeliverySession / WorkflowReceipt` 等关键 contract 词表

通过条件：

1. 路 1 和路 2 没有关键术语冲突
2. 第三路已给出差异矩阵
3. 不再继续把 Butler 产品语义塞进 `agent_os`

### Phase 1：跑通最小 talk 黄金路径

目标：

跑通这一条链：

1. `FeishuInputAdapter`
2. `Invocation`
3. `TalkRouter`
4. runtime request
5. `OutputBundle`
6. `FeishuDeliveryAdapter`

通过条件：

1. 至少一条普通 talk 消息能完整走通
2. 不依赖把 heartbeat 逻辑嵌回新骨架
3. reply 路径可验证

### Phase 2：补齐前台路由口

目标：

在最小 talk 路径稳定后，再逐步补：

- `self_mind`
- `direct branch`
- `mission ingress`

通过条件：

1. `TalkRouter` 仍保持前台路由定位
2. 新入口没有把 mission runtime 逻辑倒灌回来

### Phase 3：推进 MissionOrchestrator 独立成形

目标：

继续让后台 mission runtime 独立推进：

- mission
- node
- branch
- ledger
- receipt / projection

通过条件：

1. 后台 runtime 可独立演进
2. 前台 talk 路由不再与后台 orchestrator 混名

### Phase 4：升级 Feishu delivery session

目标：

把当前 reply-centric 发送升级成 session-centric：

- create
- update
- finalize
- 图片/文件/卡片统一纳入 `OutputBundle`

通过条件：

1. `OutputBundle` 字段稳定
2. delivery adapter 支持多种输出资产
3. 不再把输出协议散落在旧 talk 大函数里

### Phase 5：heartbeat 退主链准备

目标：

把 heartbeat 收缩成兼容壳，而不是继续扩功能。

只有满足下面条件，才进入退主链讨论：

1. 新 talk ingress 已稳定
2. talk 黄金路径已稳定
3. mission ingress 已有新承接点
4. 旧 heartbeat 不再承接新增产品能力
5. 兼容壳边界已文档化

---

## 三、当前最需要避免的错误顺序

不要这样推进：

1. 还没冻结 contract 就改主链
2. 还没跑通最小 talk 路径就废 heartbeat
3. 还没拆清 TalkRouter / MissionOrchestrator 就继续写“orchestrator”
4. 还没整理 OutputBundle 就继续堆飞书发送分支

---

## 四、主线接下来最合理的动作

如果第三路总装完成，主线下一步最合理的是：

1. 先根据总装文档确认 contract 词表
2. 选一条普通 talk 请求做最小接线
3. 只接 `Invocation -> TalkRouter -> OutputBundle -> FeishuDeliveryAdapter`
4. 验证通过后，再接 `self_mind / direct branch / mission ingress`
5. heartbeat 继续冻结，不扩

---

## 五、结论

这轮升级不是“直接把 talk 全搬进 agent_os”，而是：

- 先把 `agent_os` 做成稳定中性层
- 再把 `TalkRouter` 从旧 talk 中抽成真正的前台路由
- 再把 Feishu 交互升级成 session 化 delivery
- 最后才让 heartbeat 退出主链

这个顺序更慢一点，但更稳，也更自洽。
