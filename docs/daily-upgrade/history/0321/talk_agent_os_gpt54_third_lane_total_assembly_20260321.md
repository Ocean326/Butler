# Talk + AgentOS 第三路 GPT-5.4 总装任务包

日期：2026-03-21

适用前提：

- 已采用 `Talk + AgentOS 升级计划（v2）`
- 已存在双路任务包：
  - `talk_agent_os_gpt54_dual_lane_task_package_20260321.md`
- 第三路使用 GPT-5.4，角色定位不是“再开一条实现路”，而是“总装负责人”

---

## 一、第三路的定位

第三路不是去抢做路 1 或路 2 的实现，而是承担总装与收口：

- 审核路 1 的 `agent_os` 中性 contracts 是否自洽
- 审核路 2 的 `TalkRouter / Feishu adapter` 骨架是否正确消费这些 contracts
- 统一命名、边界、目录约束、验收口径
- 形成最小接线方案，但不直接重写旧主链
- 给主线准备“下一步该怎么接”的明确顺序

一句话定义：

第三路是 `Integration Lead / Assembly Lead`，不是第三个并行实现工人。

---

## 二、第三路必须承接的事情

### 1. 对齐边界

必须明确并反复校验以下边界：

- `TalkRouter` 只做前台产品路由
- `MissionOrchestrator` 只做后台 mission runtime
- `AgentRuntime` 只做执行基座
- `agent_os` 先承接中性 contract，不承接 Butler persona/product 语义
- `heartbeat` 处于 `legacy-compatible, no new feature`

### 2. 对齐命名

第三路要负责把所有产物的命名压到同一套词表上：

- `Invocation`
- `PromptProfile`
- `PromptContext`
- `MemoryPolicy`
- `OutputBundle`
- `DeliverySession`
- `WorkflowReceipt`
- `WorkflowProjection`
- `SubworkflowCapability`
- `TalkRouter`
- `MissionOrchestrator`
- `AgentRuntime`

如果发现路 1 和路 2 各自用了不同词，要由第三路拉回统一。

### 3. 对齐接口

第三路要检查至少三组接口是否能接上：

1. `FeishuInputAdapter -> Invocation`
2. `TalkRouter -> agent_os contracts/runtime request`
3. `OutputBundle -> FeishuDeliveryAdapter`

### 4. 管住重构范围

第三路必须防止范围失控：

- 不允许把 Butler 旧 talk runtime 整体迁移进 `agent_os`
- 不允许提前废掉 heartbeat 主链
- 不允许直接在旧 `agent.py` / `butler_bot.py` 上开大口子
- 不允许把“产品层风格问题”伪装成“中性层 contract 设计”

---

## 三、第三路的输入

第三路至少要消费下面几类输入：

### 1. 计划文档输入

- `talk_agent_os_upgrade_plan_20260321.md`
- `talk_agent_os_gpt54_dual_lane_task_package_20260321.md`

### 2. 路 1 输出输入

重点核查：

- `butler_main/agents_os/contracts/**`
- 若后续补了 `runtime/**`、`factory/**`，也纳入审阅

### 3. 路 2 输出输入

重点核查：

- `butler_main/butler_bot_code/butler_bot/adapters/**`
- `butler_main/butler_bot_code/butler_bot/orchestrators/**`
- `butler_main/butler_bot_code/butler_bot/legacy/**`

### 4. 旧系统参考输入

需要对照但不直接重写：

- `butler_main/butler_bot_code/butler_bot/butler_bot.py`
- `butler_main/butler_bot_code/butler_bot/agent.py`
- `butler_main/butler_bot_code/butler_bot/services/talk_heartbeat_ingress_service.py`
- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`

---

## 四、第三路的输出

第三路至少要交付下面四类产物：

### 1. 总装审计结果

输出一份明确审计结论，回答这几个问题：

- 路 1 contract 是否足够支撑路 2
- 路 2 adapter/router 是否正确站位
- 目前哪些地方还只是骨架
- 哪些命名、字段、边界还不稳定

### 2. 接线蓝图

输出主线接线顺序，至少明确：

1. `FeishuInputAdapter`
2. `TalkRouter`
3. `AgentRuntime request`
4. `OutputBundle`
5. `FeishuDeliveryAdapter`

### 3. 差异清单

必须显式列出：

- 路 1 与路 2 的术语差异
- 旧 talk 与新骨架的语义差异
- heartbeat 兼容壳还未替换的点

### 4. 下一阶段推进单

必须把“总装完成后怎么推进”拆成阶段，并带 gate：

- 哪个阶段可以开始接线
- 哪个阶段只允许最小黄金路径
- 哪个阶段才能动旧 heartbeat 退场

---

## 五、第三路允许写入的目录

为了避免与前两路冲突，第三路默认只允许写：

- `docs/daily-upgrade/0321/**`
- `docs/architecture/**` 如果不存在则不强行创建
- `butler_main/butler_bot_code/butler_bot/composition/**` 如果需要最小接线蓝图骨架

如果要写代码，必须满足两个条件：

- 写集不和路 1 的 `agents_os/**` 冲突
- 写集不和路 2 的 `adapters/**`、`orchestrators/**`、`legacy/**` 冲突

---

## 六、第三路禁止修改

第三路禁止直接改：

- `butler_main/agents_os/contracts/**`
- `butler_main/butler_bot_code/butler_bot/adapters/**`
- `butler_main/butler_bot_code/butler_bot/orchestrators/**`
- `butler_main/butler_bot_code/butler_bot/legacy/**`
- `butler_main/butler_bot_code/butler_bot/agent.py`
- `butler_main/butler_bot_code/butler_bot/butler_bot.py`
- `butler_main/butler_bot_code/butler_bot/memory_manager.py`
- 任何 heartbeat 旧主体实现

第三路的默认工作方式是：

- 审核
- 收口
- 统一
- 规划接线

不是抢改主链。

---

## 七、第三路施工步骤

### Step 1：建立总装基线

先把 v2 的硬边界写死：

- `TalkRouter != MissionOrchestrator`
- `agent_os != Butler 产品层`
- `heartbeat = legacy-compatible, no new feature`

### Step 2：审核路 1

检查路 1 是否满足：

- contract 词表稳定
- 字段没有混入 Butler 私货
- projection / receipt / capability 有清晰职责
- 后续 `TalkRouter` 可以直接 import 使用

### Step 3：审核路 2

检查路 2 是否满足：

- `FeishuInputAdapter` 真正产出 `Invocation`
- `TalkRouter` 真的是前台路由层
- `FeishuDeliveryAdapter` 真正对准 `OutputBundle`
- `ButlerPromptProfileAdapter` 与 `ButlerMemoryPolicyAdapter` 只做映射，不直接重做 runtime

### Step 4：拉齐差异

把路 1 / 路 2 的差异收口成一张表，至少覆盖：

- 名称差异
- 字段差异
- 责任边界差异
- 未来接线假设差异

### Step 5：形成最小主线接线方案

注意这里是“方案”，不是“全量迁移”。  
最小黄金路径建议固定为：

1. 飞书消息进入 `FeishuInputAdapter`
2. 产出 `Invocation`
3. 交给 `TalkRouter`
4. 由 `TalkRouter` 选择 talk 路由
5. 生成 runtime request 并对接 `agent_os`
6. 返回 `OutputBundle`
7. 由 `FeishuDeliveryAdapter` 完成 reply

### Step 6：明确 heartbeat 退场条件

第三路必须把 heartbeat 退场条件写清楚，而不是只写“将来解耦”：

至少满足以下条件后，旧 heartbeat 才能退主链：

1. 新 talk ingress 已经稳定
2. 最小黄金路径已跑通
3. `OutputBundle -> FeishuDeliveryAdapter` 已跑通
4. 旧 heartbeat 只剩兼容壳，不再承担新增产品能力

---

## 八、第三路 Done 标准

第三路完成，不是“写了点意见”就算结束，而是至少满足：

1. 有一份正式的总装审计结果
2. 有一份清晰的接线蓝图
3. 有一份差异清单
4. 有一份总装后推进顺序
5. 明确写出 heartbeat 的退场 gate
6. 没有和前两路发生写集冲突

---

## 九、第三路建议产出文件

建议第三路最终至少交付：

- `docs/daily-upgrade/0321/talk_agent_os_integration_review_20260321.md`
- `docs/daily-upgrade/0321/talk_agent_os_contract_alignment_matrix_20260321.md`
- `docs/daily-upgrade/0321/talk_agent_os_post_assembly_next_steps_20260321.md`

如果需要最小骨架，也可以补：

- `butler_main/butler_bot_code/butler_bot/composition/README.md`

但不要把第三路变成大规模代码施工。

---

## 十、可直接投喂第三路 GPT-5.4 的 Prompt

```text
你现在是 Butler 本轮 Talk + AgentOS 升级的第三路总装负责人，角色是 Integration Lead / Assembly Lead，不是第三个并行实现工人。

你的任务不是重复实现路 1 或路 2，而是对它们做系统总装、边界收口、命名统一、接线规划和推进排序。

本轮统一采用 v2 方案，硬边界如下：

1. TalkRouter = 前台产品路由
2. MissionOrchestrator = 后台 mission runtime
3. AgentRuntime = 执行基座
4. agent_os 本轮只承接中性 contract / projection / receipt / capability，不承接 Butler persona/product 语义
5. heartbeat 现在是 legacy-compatible, no new feature，不允许继续扩

你必须先阅读并对齐以下输入：

- docs/daily-upgrade/0321/talk_agent_os_upgrade_plan_20260321.md
- docs/daily-upgrade/0321/talk_agent_os_gpt54_dual_lane_task_package_20260321.md
- butler_main/agents_os/contracts/**
- butler_main/butler_bot_code/butler_bot/adapters/** 如果已经存在
- butler_main/butler_bot_code/butler_bot/orchestrators/** 如果已经存在
- butler_main/butler_bot_code/butler_bot/legacy/** 如果已经存在

你的工作目标：

1. 审核路 1 的 contracts 是否足够支撑路 2 的 adapter/router
2. 审核路 2 的骨架是否正确消费 agent_os 的中性层
3. 拉齐命名、字段、职责边界
4. 产出最小黄金路径的接线蓝图
5. 明确 heartbeat 退场 gate
6. 给出总装后的阶段推进顺序

你默认只允许写：

- docs/daily-upgrade/0321/**
- docs/architecture/** 如果需要
- butler_main/butler_bot_code/butler_bot/composition/** 如果确实需要最小接线骨架

你禁止修改：

- butler_main/agents_os/contracts/**
- butler_main/butler_bot_code/butler_bot/adapters/**
- butler_main/butler_bot_code/butler_bot/orchestrators/**
- butler_main/butler_bot_code/butler_bot/legacy/**
- butler_main/butler_bot_code/butler_bot/agent.py
- butler_main/butler_bot_code/butler_bot/butler_bot.py
- butler_main/butler_bot_code/butler_bot/memory_manager.py
- 任何 heartbeat 旧实现主体

你的交付必须至少包含 3 份文档：

1. integration review
2. contract alignment matrix
3. post-assembly next steps

要求：

- 先审计，再收口，再规划，不要直接开大改
- 严格防止把 Butler 产品语义塞进 agent_os
- 严格防止 TalkRouter 和 MissionOrchestrator 混名
- 严格防止 heartbeat 在本轮继续扩张
- 如果发现路 1 / 路 2 有冲突，优先输出统一建议和差异矩阵

最终输出时必须给出：

- 修改文件列表
- 每个文件的职责
- 当前总装结论
- 最小黄金路径怎么接
- heartbeat 什么时候才能退主链
```
