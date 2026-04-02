# Talk + AgentOS 升级计划（v2）

日期：2026-03-21

## 当前进度（截至今日）

当前按这份 v2 计划来看，前 3 步已经推进到下面状态：

1. `先补 AgentOS 中性层`
   - 已完成第一版落地
   - 当前已有 `contracts / runtime / factory` 基础骨架
   - `Invocation / PromptProfile / PromptContext / MemoryPolicy / OutputBundle / DeliverySession / WorkflowReceipt / WorkflowProjection / SubworkflowCapability` 等核心对象已经在仓库中

2. `并行推进 MissionOrchestrator 最小黄金路径`
   - 已完成第一版产品适配
   - 当前已有 `MissionOrchestrator` protocol、`RouteProjection / WorkflowProjection / ExecutionReceipt / WorkflowReceipt`
   - 当前也已有 Butler 产品层包装器 `butler_bot/orchestrators/mission_orchestrator.py`
   - 现有实现已经可以把 mission ingress 请求映射到现有 orchestrator service，并返回 `WorkflowReceipt`

3. `再接 TalkRouter`
   - 已完成第一版前台骨架
   - 当前已有 `TalkRouter / FeishuInputAdapter / FeishuDeliveryAdapter / ButlerPromptProfileAdapter / ButlerMemoryPolicyAdapter / legacy heartbeat boundary`
   - `TalkRouter` 现在已经直接产出 `AgentSpec`，不再停留在 spec-like dict
   - 当前也已经有主线桥接层 `composition/talk_mainline_service.py`
   - 当前也已经有 `services/talk_runtime_service.py`
   - 普通 `talk` 路径已接入 `Invocation -> TalkRouter -> TalkRuntime -> OutputBundle` 这条最小主链
   - 但飞书最终发送还没有正式切到 `FeishuDeliveryAdapter` transport

所以当前最准确的判断是：

- 前 3 步已经完成第一版代码落地
- 主线下一步不该继续扩规划，而应该开始最小接线
- `heartbeat` 继续保持 `legacy-compatible, no new feature`

## 核心判断

这轮不直接按“大迁移版 v1”执行，改为更稳的 v2：

1. 先升级 `agent_os` 的中性层，不先整体搬 `talk` 的 prompt/memory/output runtime。
2. 明确拆名：
   - 前台入口编排叫 `TalkRouter`
   - 后台 mission runtime 叫 `MissionOrchestrator`
   - 模型/工具/子代理执行层留在 `AgentRuntime`
3. 旧 `heartbeat` 不立即废弃，改成：
   - `legacy-compatible`
   - `no new feature`
   - 等新链路打通再退主链
4. `feishu bot` 最终收敛成 adapter + delivery session，不再承载 Butler 私有 runtime。

---

## 一、为什么要从 v1 收缩成 v2

上一版 v1 的问题不在方向，而在落地顺序偏激进：

- 把“AgentOS contract 升级”和“Talk runtime 迁移”绑得太紧
- 把“orchestrator”既当后台 mission runtime，又当 talk 前台路由
- 在新链路尚未建立前，就准备整体废弃 heartbeat

这样会导致两个风险：

1. `agent_os` 还没形成稳定 contracts，就被迫接 Butler 产品层语义
2. `talk` 和 heartbeat 同时重构，迁移窗口太大

所以 v2 的思路是：

- 先补中性层
- 先打最小黄金路径
- 再迁前台 runtime

---

## 二、当前系统的真实问题

### 1. Talk 仍是混合层

当前 `talk` 主链同时承担：

- 飞书消息入口
- runtime control
- 升级审批
- direct branch invoke
- heartbeat ingress
- prompt 装配
- memory pending turn / recent 注入 / reply 后写回
- agent runtime request
- 飞书回复、图片、文件发送

这意味着 `talk` 现在是 Butler 私有 runtime，而不是前台路由层。

### 2. Prompt ownership 仍在入口层

现在 `talk` 和 `heartbeat` 都还在本地拼 prompt：

- `talk`: `build_feishu_agent_prompt()`
- `heartbeat`: `HeartbeatOrchestrator` + `PromptAssemblyService`

共享了 prompt 组件，但没有共享 prompt contract。

### 3. MemoryManager 职责太厚

`MemoryManager` 现在混合承载：

- recent/session memory
- retrieval/writeback
- runtime control
- upgrade governance
- heartbeat 通知/投递边界

这说明当前 memory 并不是一个中性 runtime service，而是一个产品层大管家。

### 4. Feishu 交互层是 reply-centric，不是 session-centric

飞书侧已经有：

- interactive/post/text 回退
- 卡片动作
- 图片/文件发送

但还没有：

- create/update/finalize
- message session
- output bundle
- delivery session

### 5. Heartbeat 仍然侵入 talk 主链

`TalkHeartbeatIngressService` 说明前台 talk 里还直接承接 heartbeat 领域命令。  
这意味着 heartbeat 还不是 legacy compatibility，而是活跃耦合。

---

## 三、v2 的目标边界

### 目标 1：先把 AgentOS 做成中性 substrate

`agent_os` 在本轮只承接中性能力：

- orchestration contracts
- workflow receipt / projection helpers
- subworkflow capability interface
- prompt/memory/output 的中性 contract

但不先把 Butler 私有 runtime 直接搬进去。

### 目标 2：TalkRouter 和 MissionOrchestrator 拆开

v2 之后应形成三层清晰边界：

1. `TalkRouter`
   - 前台入口路由
   - 识别当前是普通 talk、direct branch、self_mind、控制命令等

2. `MissionOrchestrator`
   - 后台任务编排
   - 负责 mission / node / branch / ledger / workflow progression

3. `AgentRuntime`
   - 统一执行层
   - 负责 prompt context resolve、execution、tool、subagent、output bundle

### 目标 3：Heartbeat 先冻结，不先拆除

这轮 heartbeat 的策略是：

- 继续兼容
- 不增新功能
- 不继续往新架构里扩散
- 等新 `TalkRouter -> MissionOrchestrator` 最小链打通后，再考虑退主链

---

## 四、AgentOS 本轮应该承接什么

### A. 这轮应进入 AgentOS 的内容

#### 1. Orchestration contracts

建议统一为中性 contracts：

- `Invocation`
- `WorkflowReceipt`
- `WorkflowProjection`
- `SubworkflowCapability`
- `CapabilityBinding`
- `AgentResult`

#### 2. Prompt contracts

这轮只补 contract，不搬 Butler prompt 实现：

- `PromptProfile`
- `PromptContext`
- `PromptBlock`
- `ModelInput`

#### 3. Memory contracts

这轮只补 contract 和 policy，不搬 Butler 的 memory runtime 细节：

- `MemoryScope`
- `MemoryPolicy`
- `MemoryContext`
- `MemoryHit`
- `MemoryWritebackRequest`

#### 4. Output contracts

- `OutputBundle`
- `ArtifactRef`
- `TextBlock`
- `CardBlock`
- `FileAsset`
- `ImageAsset`

#### 5. Delivery contracts

- `DeliverySession`
- `DeliveryRequest`
- `DeliveryResult`

### B. 这轮不要直接搬进 AgentOS 的内容

#### 1. Butler persona 内容真源

- `SOUL`
- `TALK`
- `USER`
- `SELF_MIND`

#### 2. Butler 产品语义

- 飞书卡片长相
- reply action 设计
- 用户侧输出风格

#### 3. Butler 私有 memory taxonomy

- 哪些 stream 对 talk 可见
- 哪些 stream 对 self_mind 可见
- 哪些 stream 是 legacy heartbeat 观察流

#### 4. 旧 heartbeat task 体系

- mission schema 兼容壳可以保留在产品层或 legacy 层
- 不要现在就强塞进 `agent_os`

---

## 五、v2 新命名

为了避免后续文档和代码持续混淆，统一采用下列名字：

### 1. `TalkRouter`

职责：

- 接收前台 `Invocation`
- 做产品语义分流
- 路由到 talk/self_mind/direct branch/mission ingress

### 2. `MissionOrchestrator`

职责：

- 管理后台 mission runtime
- 管理 workflow / node / branch / ledger
- 产出 receipt / projection / route

### 3. `AgentRuntime`

职责：

- 统一执行层
- 承接 prompt context、memory context、policy、execution、output bundle

### 4. `FeishuInputAdapter`

职责：

- 飞书 event -> `Invocation`

### 5. `FeishuDeliveryAdapter`

职责：

- `OutputBundle` -> 飞书 reply/update/push

---

## 六、v2 的新链路

目标链路不再是“talk 一个大函数吃到底”，而是：

```text
Raw Feishu Event
  -> FeishuInputAdapter
    -> Invocation
      -> TalkRouter
        -> direct talk runtime
        -> self_mind path
        -> direct branch path
        -> mission ingress path
      -> AgentRuntime / MissionOrchestrator
        -> WorkflowReceipt / Projection / OutputBundle
      -> FeishuDeliveryAdapter
```

注意：

- `TalkRouter` 不等于 `MissionOrchestrator`
- `MissionOrchestrator` 不等于 `AgentRuntime`
- `FeishuDeliveryAdapter` 不等于 `OutputBundle`

---

## 七、v2 迁移顺序

### Phase A：先补 AgentOS 中性层

状态：`已完成第一版`

本阶段只做“以后所有入口都能复用”的东西。

目标：

- 补全中性 contracts
- 补全 workflow projection / receipt helpers
- 补全 subworkflow capability interface

交付：

- `contracts/*`
- `projection helpers`
- `capability interfaces`
- `runtime/*` 最小骨架
- `factory/*` 最小骨架

说明：

- 当前已先落了一版 `agents_os/contracts/**` dataclass 脚手架
- 当前也已经有：
  - `agents_os/runtime/projection.py`
  - `agents_os/runtime/receipts.py`
  - `agents_os/runtime/subworkflow_interface.py`
  - `agents_os/runtime/orchestrator.py`
  - `agents_os/factory/*`
- 这说明 AgentOS 中性层第一版已经具备，后续重点不再是继续拆 contracts，而是服务主链接线

### Phase B：继续独立推进 MissionOrchestrator

状态：`已完成第一版产品适配`

目标：

- 不等待 talk runtime 全量迁移
- 继续把后台 mission 黄金路径跑通

原则：

- `MissionOrchestrator` 继续保持自己的 Mission / Node / Branch / Ledger
- 先跑一个最小黄金路径
- 先把 receipt / projection 稳下来

当前落点：

- 已有 `MissionOrchestrator` protocol
- 已有 `RouteProjection / WorkflowProjection / ExecutionReceipt / WorkflowReceipt`
- 已具备“后台 runtime contract 先独立”的方向
- 已有 Butler 产品层包装器：
  - `butler_bot/orchestrators/mission_orchestrator.py`
- 当前包装器已经可以：
  - 接收 `RuntimeRequest`
  - 调用现有 mission orchestrator service
  - 返回 `WorkflowReceipt / OutputBundle / DeliveryRequest`

当前缺口：

- 还没有接入旧 talk 主链
- `mission_ingress` 目前已经有后台包装器，但还没有完成整条产品主链联通

### Phase C：落地 TalkRouter

状态：`已完成第一版骨架`

目标：

- 把前台 talk 入口从“产品大 runtime”收成“产品路由器”

这阶段做：

- `TalkRouter`
- `FeishuInputAdapter`
- `ButlerPromptProfileAdapter`
- `ButlerMemoryPolicyAdapter`
- `FeishuDeliveryAdapter`
- `legacy heartbeat boundary`

不做：

- 全量迁移 memory runtime
- 全量迁移 prompt render 机制

当前落点：

- `butler_bot/orchestrators/talk_router.py`
- `TalkRouter` 已直接产出 `AgentSpec`
- `butler_bot/adapters/feishu_input_adapter.py`
- `butler_bot/adapters/feishu_delivery_adapter.py`
- `butler_bot/adapters/butler_prompt_profile_adapter.py`
- `butler_bot/adapters/butler_memory_policy_adapter.py`
- `butler_bot/legacy/heartbeat_boundary.py`

当前缺口：

- 新骨架还未正式接入旧主链
- 当前还不能把 `Phase C` 视为“主链迁移完成”

### Phase D：重做 Feishu delivery session

目标：

- 不再以 reply-only 为核心

交付：

- `FeishuDeliveryAdapter`
- `FeishuReplySession`
- `create/update/finalize`

### Phase E：Heartbeat 退主链

前提：

- 新 `TalkRouter -> MissionOrchestrator` 至少打通一条链

到这一步才做：

- heartbeat 从主链退出
- legacy 只保留兼容壳

---

## 八、Heartbeat 的 v2 处理原则

不再使用“Phase 0 整体废弃”的说法，统一改成：

### `legacy-compatible, no new feature`

具体含义：

1. 继续能跑
2. 继续能兼容旧任务/旧状态
3. 禁止再扩新架构功能
4. Talk 新链路不再继续耦合 heartbeat ingress

需要标成 legacy 的对象：

- `TalkHeartbeatIngressService`
- `heartbeat_orchestration.py`
- 旧 heartbeat planner / executor prompt 链

---

## 九、v2 的代码拆分方向

### AgentOS

建议继续整理：

```text
butler_main/agents_os/
  contracts/
    invocation.py
    prompt.py
    memory.py
    policy.py
    output.py
    delivery.py
  runtime/
    projection.py
    receipts.py
    capability_registry.py
    subworkflow_interface.py
  factory/
    agent_factory.py
    agent_spec.py
    profiles.py
```

说明：

- 本轮重点不在 `runtime` 全实现
- 而在先把 contracts / receipts / projection / capability 抽稳

### Butler Talk

建议新增：

```text
butler_main/butler_bot_code/butler_bot/
  adapters/
    feishu_input_adapter.py
    feishu_delivery_adapter.py
    butler_prompt_profile_adapter.py
    butler_memory_policy_adapter.py
  orchestrators/
    talk_router.py
  legacy/
    README.md
```

说明：

- 这轮先搭骨架，不直接改 `agent.py` / `butler_bot.py`
- Talk 新骨架先与旧链并存

---

## 十、v2 施工边界

### 这轮允许做

- AgentOS 中性 contracts
- workflow receipt / projection helpers
- capability 接口
- TalkRouter/adapters 骨架
- Feishu delivery session 骨架

### 这轮不建议做

- 把整个 Butler prompt runtime 全搬进 AgentOS
- 把整个 MemoryManager 全搬进 AgentOS
- 在新旧链路都不稳定时直接摘 heartbeat 主链

---

## 十一、验收标准

### AgentOS v2 中性层完成标准

1. prompt/memory/output/delivery 都有明确 contract
2. workflow receipt / projection helpers 可供 orchestrator 直接使用
3. subworkflow capability 有统一接口
4. 产品层还未迁移时，contracts 也能单独稳定存在

### Talk v2 骨架完成标准

1. 前台编排统一改叫 `TalkRouter`
2. Talk 不再与后台 `MissionOrchestrator` 混名
3. 新 talk 骨架能在不依赖 heartbeat 新功能的前提下存在
4. 飞书 delivery 层开始支持 session 化接口

### Heartbeat legacy 标准

1. 可兼容旧链
2. 禁止新增 feature
3. 不继续扩散耦合

---

## 十二、最终判断

v2 的真正顺序是：

1. **先补 AgentOS 中性层** `已完成第一版`
2. **并行推进 MissionOrchestrator 最小黄金路径** `已完成第一版产品适配`
3. **再接 TalkRouter** `已完成第一版骨架，待接主链`
4. **再做 Feishu delivery session**
5. **最后让 heartbeat 退主链**

当前主线应该做的事，不再是继续扩前 3 步的规划，而是：

1. 继续把 `OutputBundle -> FeishuDeliveryAdapter -> transport` 接完整
2. 继续把普通 `talk` 剩余逻辑从旧发送链路里剥出来
3. 在普通 `talk` 主链稳定之前，不提前推进 heartbeat 退场
4. `MissionOrchestrator` 单独继续产品化，不再和前台入口混在一起

这个顺序比 v1 更稳，也更适合直接进入施工。
