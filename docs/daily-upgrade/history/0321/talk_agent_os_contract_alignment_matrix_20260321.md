# Talk + AgentOS 合同对齐矩阵

日期：2026-03-21

---

## 一、核心概念对齐

| 概念 | AgentOS 落点 | Butler 新骨架落点 | 旧系统参考 | 当前判断 |
| --- | --- | --- | --- | --- |
| 前台调用入口 | `Invocation` | `FeishuInputAdapter.build_invocation()` | 飞书 event + `agent.py` 入口 | 已对齐 |
| Prompt 配置 | `PromptProfile` | `ButlerPromptProfileAdapter.build_profile()` | `bootstrap_loader_service.py` / `prompt_assembly_service.py` | 已对齐，但仍是映射层 |
| Prompt 动态上下文 | `PromptContext` | `ButlerPromptProfileAdapter.build_context()` | talk/heartbeat 各自本地拼接 prompt | 已对齐，但未接主链 |
| 记忆策略 | `MemoryPolicy` | `ButlerMemoryPolicyAdapter.resolve_policy()` | `memory_manager.py` 里的 visibility / recent / writeback 逻辑 | 已对齐，但仍是映射层 |
| 交付会话 | `DeliverySession` | `TalkRouter.build_delivery_session()` | 飞书 reply 语义 | 已对齐 |
| 输出载体 | `OutputBundle` | `FeishuDeliveryAdapter` 消费 | `message_delivery_service.py` 等 | 已对齐，transport 未接 |
| 路由投影 | `RouteProjection` | 暂无直接 Butler 实现 | talk 内部路由判断 | 中性层已有，产品层未消费 |
| 工作流投影 | `WorkflowProjection` | 暂无直接 Butler 实现 | heartbeat/mission 状态 | 中性层已有，产品层未消费 |
| 执行回执 | `ExecutionReceipt` | 暂未直接接入 `TalkRouter` | talk/heartbeat 各自回执风格 | 中性层已有 |
| 工作流回执 | `WorkflowReceipt` | 未来供 `MissionOrchestrator` 使用 | heartbeat mission 状态链 | 中性层已有 |
| 子工作流能力 | `SubworkflowCapability` | 暂无 Butler adapter 消费 | research / heartbeat subworkflow | 中性层已有 |
| 前台路由器 | 无需放入 `agent_os` 产品名 | `TalkRouter` | 旧 talk 大入口 | 已对齐 |
| 后台 mission runtime | `MissionOrchestrator` protocol | 尚无 Butler 产品实现 | heartbeat / mission runtime | 未完成 |
| 执行层 | `AgentRuntime` protocol | `TalkRouter` 只声明 ownership，不实现 runtime | Butler agent runtime | 已分层，但未接主链 |

---

## 二、Phase 0 词表冻结建议

以下词表建议立即冻结，不再改名：

| 冻结词 | 原因 |
| --- | --- |
| `TalkRouter` | 明确前台产品路由层 |
| `MissionOrchestrator` | 明确后台 mission runtime |
| `AgentRuntime` | 明确执行层 |
| `Invocation` | 前台统一输入合同 |
| `PromptProfile` | persona/bootstrap/policy 的配置投影 |
| `PromptContext` | 动态 prompt 上下文 |
| `MemoryPolicy` | 可见性与读写策略 |
| `OutputBundle` | 统一输出资产合同 |
| `DeliverySession` | 统一交付会话合同 |
| `ExecutionReceipt` | 单次执行回执 |
| `WorkflowReceipt` | 工作流/mission 回执 |

---

## 三、当前缺口矩阵

| 缺口 | 当前状态 | 应归属哪层 |
| --- | --- | --- |
| 普通 talk 最小主链接线 | 未完成 | 主线接线 |
| `self_mind` 真正运行入口 | 未完成 | `TalkRouter` 后续接线 |
| `direct_branch` 真正运行入口 | 未完成 | `TalkRouter` 后续接线 |
| `mission_ingress` 新后台承接 | 未完成 | `MissionOrchestrator` 产品层 |
| 飞书真实 delivery transport | 未完成 | `FeishuDeliveryAdapter` 与主线接线 |
| heartbeat 主链退场 | 未完成 | Phase 5 以后 |

---

## 四、不应混淆的边界

| 容易混淆项 | 正确关系 |
| --- | --- |
| `memory` 和 `prompt` | `memory` 不是 `prompt` 的子集。`memory` 是被 `prompt context resolve` 消费的一类输入来源 |
| `OutputBundle` 和 `DeliverySession` | `OutputBundle` 是输出内容，`DeliverySession` 是投递会话，两者不能混成一个对象 |
| `TalkRouter` 和 `MissionOrchestrator` | 前者只路由前台产品请求，后者只管理后台 mission runtime |
| `agent_os` 和 Butler 产品层 | 前者本轮只承接中性 substrate，后者继续承接 persona/product 语义 |
| heartbeat compatibility 和 heartbeat ownership | 兼容壳还在，不代表 heartbeat 仍应拥有新架构入口 |

---

## 五、第三路对齐判断

当前总装后可以明确：

- 路 1 的词表足以支撑路 2
- 路 2 的骨架总体正确消费了路 1 的中性 contract
- 最大缺口不在命名，而在主链接线与后台 mission runtime
- heartbeat 已经从“继续扩功能”转入“保留兼容壳”
