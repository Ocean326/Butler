# Talk + AgentOS 主线推进计划

日期：2026-03-21

这份文档用于替代当前分散的多路/phase/评审型产物，作为接下来实际施工的主线计划。

---

## 一、这轮只做什么

这轮只做两件事：

1. 把 `talk` 从旧 heartbeat 入口依赖里拆出来，形成新的前台主入口
2. 把飞书交互层收敛成统一输入/输出骨架，为后续卡片、图片、文件、流式更新做准备

对应到主线，当前唯一需要先跑通的链路是：

`FeishuInputAdapter -> TalkRouter -> AgentRuntime -> OutputBundle -> FeishuDeliveryAdapter`

当前状态更新：

- 普通 `talk` 已经接入新的主线桥接层
- 当前已经存在：
  - `composition/talk_mainline_service.py`
  - `services/talk_runtime_service.py`
  - `Invocation -> TalkRouter -> AgentSpec`
  - 普通 `talk` runtime -> `OutputBundle`
  - 飞书事件基础元信息 -> `Invocation`
- 但飞书最终发送目前仍由旧 reply 发送链执行，`FeishuDeliveryAdapter` 目前处于“生成 delivery plan、尚未接 transport”阶段

---

## 二、命名与边界先冻结

后面不再改名，不再反复讨论：

- `TalkRouter`：前台产品路由
- `MissionOrchestrator`：后台 mission runtime
- `AgentRuntime`：执行层
- `Invocation`：统一输入合同
- `PromptProfile / PromptContext`：prompt 配置和动态上下文
- `MemoryPolicy`：记忆可见性和写回策略
- `OutputBundle`：统一输出载体
- `DeliverySession`：统一投递会话

同时冻结一条原则：

- `heartbeat = legacy-compatible, no new feature`

意思是：

- 旧 heartbeat 先保留兼容壳
- 不再往 heartbeat 路径上继续加新能力
- 新入口都往 `TalkRouter` 收

---

## 三、当前已经有的东西

当前可直接利用的骨架：

- `agents_os/contracts/**`
- `agents_os/runtime/**` 中的 receipt / projection / runtime protocol
- `butler_bot/adapters/feishu_input_adapter.py`
- `butler_bot/adapters/feishu_delivery_adapter.py`
- `butler_bot/adapters/butler_prompt_profile_adapter.py`
- `butler_bot/adapters/butler_memory_policy_adapter.py`
- `butler_bot/orchestrators/talk_router.py`
- `butler_bot/legacy/heartbeat_boundary.py`

当前缺的不是概念，而是主链接线。

---

## 四、主线执行顺序

### Step 1：只接普通 talk 主入口

状态：`已完成第一版最小接线`

先不要一口气迁移所有入口。  
只做普通 `talk`：

1. 飞书事件进入 `FeishuInputAdapter`
2. 生成 `Invocation`
3. 交给 `TalkRouter`
4. 产出 runtime request
5. 交给现有 `AgentRuntime` 承接
6. 返回 `OutputBundle`
7. 交给 `FeishuDeliveryAdapter`

验收标准：

- 至少一条普通 talk 请求能完整跑通
- 不依赖 heartbeat 逻辑参与
- 主线不再在旧大函数里直接拼回复

当前进展：

- 已新增 `TalkMainlineService`
- 已新增 `TalkRuntimeService`
- `run_agent()` 的普通 `talk` 路径已改为先进入主线桥接层
- 飞书消息入口已开始把基础事件元信息传入 `run_agent(invocation_metadata=...)`
- 普通 `talk` 已可形成：
  - `Invocation`
  - `TalkRuntimeRequest`
  - `AgentSpec`
  - `TalkRuntimeExecution`
  - `OutputBundle`
- `OutputBundle` 现在不只包文本，也开始承接 `decide` 产出的文件/artifact

当前仍未完成：

- 旧飞书最终发送仍未替换成 `FeishuDeliveryAdapter.deliver()`

### Step 2：把 delivery 先接成最小可用

状态：`进行中`

先不追求飞书交互层一次到位。  
先让下面三件事成立：

- 文本 reply 能发
- `OutputBundle` 成为唯一输出入口
- 图片/文件/卡片先通过 adapter plan 统一表示

验收标准：

- 旧发送逻辑开始从“多处分支发送”收敛到 `FeishuDeliveryAdapter`
- 即使 update/push 还没完全接通，reply 主链必须先可用

当前进展：

- `FeishuDeliveryAdapter` 已经参与主线桥接，能够生成 delivery plan
- `OutputBundle` 已经成为普通 `talk` 回复的统一包装对象
- 普通 `talk` 内部逻辑已经不再只返回裸文本，而是先产出结构化 bundle

当前仍未完成：

- 最终 transport 仍由旧 `reply_message / reply_file / reply_image` 路径执行
- `FeishuDeliveryAdapter` 还没有接到真实发送链

### Step 3：再补其他入口

状态：`未开始主链接线`

普通 `talk` 稳定后，再补：

- `self_mind`
- `direct_branch`
- `mission_ingress`

顺序不要反。

验收标准：

- `TalkRouter` 继续只做前台路由
- 新入口没有把后台 mission 逻辑重新塞回前台

### Step 4：单独推进 MissionOrchestrator

状态：`已完成第一版产品包装器，未接主链`

`mission_ingress` 只是入口名，不代表后台已经完成。  
真正的后台 mission runtime 单独推进：

- mission
- node
- branch
- ledger
- receipt / projection

验收标准：

- `MissionOrchestrator` 作为独立后台存在
- 不再和 `TalkRouter` 混名

### Step 5：最后再谈 heartbeat 退场

状态：`冻结中`

只有下面条件都满足，heartbeat 才能退主链：

1. 新 talk ingress 稳定
2. 普通 talk 主链稳定
3. `mission_ingress` 有新后台承接器
4. `OutputBundle -> FeishuDeliveryAdapter` 已经跑稳

在这之前，heartbeat 只保留兼容，不做扩展。

---

## 五、现在不要做什么

这几件事先别做：

- 不要继续拆更多路
- 不要继续扩 phase 文档
- 不要把 Butler 私有 prompt/memory runtime 全搬进 `agent_os`
- 不要先做 heartbeat 退场
- 不要先追求飞书 create/update/finalize 全功能
- 不要同时改 `agent.py`、`butler_bot.py`、`memory_manager.py` 大块逻辑

---

## 六、最小交付目标

如果只看接下来一轮施工，最小交付目标只有三个：

1. 普通 `talk` 新主链接通
2. 输出统一收敛到 `OutputBundle`
3. heartbeat 明确冻结，不再扩张

只要这三件事成立，这轮就是有效推进。

---

## 七、这份计划怎么用

后面施工时，只需要按这个顺序判断：

1. 这次改动是不是在帮助跑通普通 `talk` 主链
2. 这次改动是不是在帮助统一输入/输出骨架
3. 这次改动是不是会把 heartbeat 又拉回主链中心

如果答案分别是：

- 是
- 是
- 否

那这次改动大概率就是对的。

---

## 八、背景文档

下面这些文档保留作背景，不再作为主施工入口：

- `talk_agent_os_upgrade_plan_20260321.md`
- `talk_agent_os_gpt54_dual_lane_task_package_20260321.md`
- `talk_agent_os_gpt54_third_lane_total_assembly_20260321.md`
- `talk_agent_os_integration_review_20260321.md`
- `talk_agent_os_contract_alignment_matrix_20260321.md`
- `talk_agent_os_phase_progress_20260321.md`
