# Talk + AgentOS 双路 GPT-5.4 施工任务包

日期：2026-03-21

适用前提：

- 按 `Talk + AgentOS 升级计划（v2）` 执行
- 两路都使用 GPT-5.4
- 每一路任务允许更大、更完整，但必须锁定写集，避免互相踩踏
- 若需要第三路总装，请配套参考：
  - `talk_agent_os_gpt54_third_lane_total_assembly_20260321.md`

---

## 总体施工原则

### 原则 1：先做中性层，再接产品层

两路里必须至少有一路优先承接 `agent_os` 中性能力，不得两路同时直接改旧 `talk` 主链。

### 原则 2：按写集彻底分离

两路的文件写集必须不重叠。

### 原则 3：先骨架，后接线

这轮不是全量功能迁移，而是：

- 先建立 contracts / receipts / projection / adapter / router 骨架
- 再由主线做接线

### 原则 4：heartbeat 保持 legacy-compatible

两路都不得继续给 heartbeat 增新功能。  
若涉及 heartbeat，只允许：

- 标 legacy
- 做兼容边界说明
- 做退出准备

---

## 路线总览

### 路 1：AgentOS 中性层 + MissionOrchestrator 基础层

负责人关注点：

- 中性 contracts
- projection / receipt helpers
- subworkflow capability interface
- mission runtime 的中性接口准备

### 路 2：Butler Talk 新骨架 + Feishu adapter/delivery session

负责人关注点：

- `TalkRouter`
- `FeishuInputAdapter`
- `FeishuDeliveryAdapter`
- `ButlerPromptProfileAdapter`
- `ButlerMemoryPolicyAdapter`
- legacy 边界清理

---

## 路 1：GPT-5.4 任务包

### 任务标题

`AgentOS 中性层升级：contracts + projection + capability + mission interface`

### 目标

把 `agent_os` 先升级成能支撑未来 `TalkRouter` / `MissionOrchestrator` 的中性 substrate，但不吞 Butler 产品层实现。

### 允许写入的目录

只允许写：

- `butler_main/agents_os/contracts/**`
- `butler_main/agents_os/runtime/**`
- `butler_main/agents_os/factory/**`

必要时可补：

- `butler_main/agents_os/__init__.py`
- `butler_main/agents_os/runtime/__init__.py`
- `butler_main/agents_os/factory/__init__.py`

### 明确禁止修改

- `butler_main/butler_bot_code/butler_bot/**`
- `butler_main/research/**`
- 任何 heartbeat 旧实现文件
- 任何 feishu adapter 文件

### 任务内容

#### 1. 收敛 contracts

基于已落地的 contracts 脚手架继续整理和补齐，至少保证下面对象稳定：

- `Invocation`
- `PromptProfile`
- `PromptContext`
- `ModelInput`
- `MemoryScope`
- `MemoryPolicy`
- `MemoryContext`
- `MemoryHit`
- `MemoryWritebackRequest`
- `ToolPolicy`
- `OutputPolicy`
- `ArtifactRef`
- `OutputBundle`
- `DeliverySession`
- `DeliveryRequest`
- `DeliveryResult`

#### 2. 新增 receipt / projection helpers

新增中性运行时对象：

- `WorkflowReceipt`
- `WorkflowProjection`
- `RouteProjection`
- `ExecutionReceipt`

要求：

- 不掺 Butler 私有字段命名
- 字段足够让 `MissionOrchestrator` 和 `TalkRouter` 后续共用

#### 3. 新增 subworkflow capability interface

目标：

- 统一表达某个 agent/runtime 能否承接某类 subworkflow

建议对象：

- `SubworkflowCapability`
- `CapabilityBinding`
- `CapabilityResolver`

要求：

- 不直接绑定到 research / heartbeat 业务字面值
- 可以表达：
  - supported entrypoints
  - supported workflow kinds
  - required policies
  - output expectations

#### 4. 新增 runtime/factory 骨架

最小骨架即可，不做重实现：

- `agent_factory.py`
- `agent_spec.py`
- `profiles.py`
- `projection.py`
- `receipts.py`
- `subworkflow_interface.py`
- `capability_registry.py`

要求：

- 重点是接口和骨架
- 可以有 stub，但命名必须稳定、自洽

#### 5. 为 MissionOrchestrator 留好接口

本路不用实现新的 `MissionOrchestrator`，但要把它未来会依赖的中性对象准备好：

- receipt
- projection
- capability
- invocation
- output contract

### Done 标准

1. `agent_os` 里形成一套自洽的中性 contracts
2. receipt / projection / capability 接口稳定
3. 代码能被 Butler talk 新骨架 import，而不必依赖 heartbeat 旧实现
4. 没有把 Butler persona / feishu / heartbeat 私有语义带进 `agent_os`

### 交付说明要求

最终汇报时必须给出：

- 修改文件列表
- 每个文件的职责
- 新增 contract 之间的关系
- 哪些地方是刻意留空、等待主线接线

---

## 路 2：GPT-5.4 任务包

### 任务标题

`Butler Talk 新骨架升级：TalkRouter + Feishu adapters + legacy boundary`

### 目标

在不碰旧 `talk` 主链的前提下，先把未来的新前台骨架搭出来，让它能在接口上对接升级后的 `agent_os`。

### 允许写入的目录

只允许写：

- `butler_main/butler_bot_code/butler_bot/adapters/**`
- `butler_main/butler_bot_code/butler_bot/orchestrators/**`
- `butler_main/butler_bot_code/butler_bot/legacy/**`

必要时可补：

- 对应目录的 `__init__.py`
- 说明性 README

### 明确禁止修改

- `butler_main/agents_os/**`
- `butler_main/butler_bot_code/butler_bot/agent.py`
- `butler_main/butler_bot_code/butler_bot/butler_bot.py`
- `butler_main/butler_bot_code/butler_bot/memory_manager.py`
- 旧 heartbeat 代码主体

### 任务内容

#### 1. 明确前台新骨架命名

必须统一使用：

- `TalkRouter`

不得继续使用模糊名字：

- `orchestrator` 既指前台又指后台

#### 2. 新增 adapter 骨架

建议至少创建：

- `feishu_input_adapter.py`
- `feishu_delivery_adapter.py`
- `butler_prompt_profile_adapter.py`
- `butler_memory_policy_adapter.py`

职责要求：

- `FeishuInputAdapter`
  - 飞书 event -> 中性 `Invocation`
  - 先定义接口与字段映射，不必把旧逻辑全搬过来

- `FeishuDeliveryAdapter`
  - `OutputBundle` -> 飞书投递请求
  - 明确支持的 delivery mode：
    - `reply`
    - `update`
    - `push`

- `ButlerPromptProfileAdapter`
  - 负责把 Butler persona/bootstrap 内容映射成中性 `PromptProfile` / `PromptContext`
  - 不直接拼最终 prompt

- `ButlerMemoryPolicyAdapter`
  - 负责把 Butler talk/self_mind/research 的可见性规则映射成中性 `MemoryPolicy`

#### 3. 新增 `TalkRouter`

要求：

- 只做前台路由，不做 mission runtime
- 能表达未来的分流口：
  - `talk`
  - `self_mind`
  - `direct branch`
  - `mission ingress`

但本轮不要求把旧逻辑全接进来。

建议至少定义：

- `route(invocation) -> RouteDecision`
- `build_runtime_request(...)`
- `resolve_agent_spec(...)`

#### 4. 搭出 `FeishuReplySession` 的抽象落点

即使本轮不实现完整 create/update/finalize，也要在 delivery adapter 侧预留结构：

- `create`
- `update`
- `finalize`

并说明当前哪些能力暂未接老链。

#### 5. 明确 legacy heartbeat 边界

在 `legacy/` 下新增说明：

- heartbeat 处于 `legacy-compatible, no new feature`
- `TalkHeartbeatIngressService` 属于旧边界
- 新 `TalkRouter` 不再以内嵌 heartbeat 领域逻辑为长期方案

### Done 标准

1. 新前台骨架命名统一为 `TalkRouter`
2. `FeishuInputAdapter` / `FeishuDeliveryAdapter` / policy/profile adapter 都有明确职责边界
3. legacy heartbeat 边界有清晰 README 或注释说明
4. 没有直接改旧 `agent.py` / `butler_bot.py`
5. 新骨架能明显看出未来接 `agent_os` 的位置

### 交付说明要求

最终汇报时必须给出：

- 修改文件列表
- 每个 adapter/router 的职责
- 哪些地方故意没有接旧链
- 未来主线需要把哪些旧模块接过来

---

## 两路并行协作规则

### 1. 不共享写集

路 1 不得修改 Butler feishu 侧文件。  
路 2 不得修改 `agents_os` 目录。

### 2. 共享概念，但不共享实现

共享概念：

- `Invocation`
- `PromptProfile`
- `MemoryPolicy`
- `OutputBundle`
- `DeliverySession`
- `WorkflowReceipt`

实现上：

- 路 1 负责定义 contract
- 路 2 负责按 contract 设计 Butler adapter

### 3. 主线负责最后接线

两路都不要在本轮擅自改：

- `agent.py`
- `butler_bot.py`
- `memory_manager.py`

接线由主线统一做。

---

## 推荐的完成顺序

### 路 1 先出

先完成 `agent_os` 中性 contract / receipt / projection / capability。  
这样路 2 可以更容易对齐命名。

### 路 2 随后对齐

在路 1 contract 基本稳定后，路 2 对照 contract 补 Butler adapter/router。

---

## 主线集成前检查项

主线开始接线前，至少确认：

1. `Invocation` 字段稳定
2. `OutputBundle` 字段稳定
3. `DeliverySession` 字段稳定
4. `TalkRouter` 不再与 `MissionOrchestrator` 混名
5. heartbeat 已明确标成 legacy-compatible

---

## 最终目标

这两路施工完成后，主线应能开始做的事情是：

- 用 `FeishuInputAdapter` 生成 `Invocation`
- 用 `TalkRouter` 做前台分流
- 用新 `agent_os` 中性 contracts 承接 runtime request
- 用 `FeishuDeliveryAdapter` 吃 `OutputBundle`

而不是继续在旧 `talk` 大函数里扩逻辑。
