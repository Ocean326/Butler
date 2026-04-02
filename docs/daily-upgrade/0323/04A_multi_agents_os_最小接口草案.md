---
type: "note"
---
# 04A multi_agents_os 最小接口草案

日期：2026-03-23\
状态：草案

## 文档目的

本页只回答一个问题：

在当前阶段，`multi_agents_os` 对 `orchestrator`、`research bridge`、future `agents_os` 应冻结哪些最小接口，哪些先不要假装已经稳定。

本页不讨论：

1. workflow VM 的完整执行语义

2. framework compiler 的完整 Collaboration Contract

3. research 热状态是否整体迁移

## 1. 读取接口

### 1.1 稳定读取单位

稳定读取单位固定为：

`WorkflowSessionBundle`

包含：

| 字段                  | 作用                                                          | 当前是否稳定 |
| ------------------- | ----------------------------------------------------------- | ------ |
| `template`          | workflow 模板定义、steps、roles、entry/exit contract               | 是      |
| `session`           | session identity、driver_kind、active_step、role_bindings、refs | 是      |
| `shared_state`      | workflow-scoped shared facts                                | 是      |
| `artifact_registry` | artifact index + visibility                                 | 是      |
| `collaboration`     | mailbox / ownership / join / handoff                        | 是      |

### 1.2 读取原则

1. 上层不应直接拼底层文件。

2. 上层默认通过 `WorkflowFactory.load_session(session_id)` 读取。

3. 上层可以依赖 bundle 的对象边界，但不应依赖文件名作为长期 contract。

## 2. 写入接口

### 2.1 `WorkflowFactory` 最小写接口

| 接口                                        | 作用                            | 主要消费者                                               |
| ----------------------------------------- | ----------------------------- | --------------------------------------------------- |
| `create_session(...)`                     | 创建 workflow session           | orchestrator                                        |
| `patch_shared_state(session_id, payload)` | 更新共享状态                        | orchestrator / research bridge                      |
| `add_artifact(...)`                       | 追加 artifact 与 visibility      | research bridge / future workflow VM                |
| `post_mailbox_message(...)`               | 写 mailbox item                | future workflow VM / future adapters                |
| `assign_step_owner(...)`                  | 声明 step ownership             | future workflow VM / future adapters                |
| `declare_join_contract(...)`              | 声明 join barrier               | future workflow VM / future adapters                |
| `record_role_handoff(...)`                | 写 role handoff                | research bridge / future workflow VM                |
| `update_active_step(...)`                 | 更新 session active_step/status | orchestrator / research bridge / future workflow VM |
| `list_events(...)`                        | 读取 local collaboration trace  | orchestrator / observation                          |

### 2.2 当前写入原则

1. `orchestrator` 负责 session 创建与上层分发绑定。

2. `research bridge` 当前只应做 projection write-back，不应自己发明第二套 session protocol。

3. future `agents_os` 接入后，应优先消费这组接口，而不是绕过 factory 直接改文件。

4. 对 replay / retry / resume 敏感的写接口，当前统一要求具备幂等语义：

   * `assign_step_owner` 以 `step_id` 为 upsert key

   * `add_artifact` 以 `dedupe_key` 或 `step_id + ref` 为 upsert key

   * `post_mailbox_message` 以 `dedupe_key` 为 upsert key

   * `record_role_handoff` 以 `dedupe_key` 为 upsert key

   * `declare_join_contract` 以 `dedupe_key` 为 upsert key

   * `patch_shared_state` / `update_active_step` 对无变化重放应 no-op

## 3. research 的最小投影输入

当前 `research` 不需要直接“懂” `multi_agents_os` 的全部对象，只需要稳定输出下面这些字段供 bridge 投影：

| 输入字段                    | 来源                                  | 去向                                 |
| ----------------------- | ----------------------------------- | ---------------------------------- |
| `workflow_session_id`   | invocation / bridge                 | session lookup                     |
| `research_unit_id`      | invocation / scenario dispatch      | shared_state                       |
| `scenario_action`       | invocation metadata                 | shared_state                       |
| `scenario_instance_id`  | scenario instance                   | shared_state / artifact ref        |
| `scenario_id`           | scenario instance / dispatch        | shared_state / artifact payload    |
| `workflow_id`           | scenario instance / workflow_cursor | shared_state / artifact payload    |
| `current_step_id`       | workflow_cursor / active_step       | shared_state / session.active_step |
| `workflow_cursor`       | scenario runner output              | shared_state                       |
| `latest_decision`       | decision receipt                    | shared_state                       |
| `last_step_receipt`     | scenario runner output              | ownership projection               |
| `last_handoff_receipt`  | scenario runner output              | handoff / mailbox projection       |
| `last_decision_receipt` | scenario runner output              | join contract projection           |
| `acceptance.artifacts`  | research result                     | artifact registry                  |
| `summary`               | research result                     | shared_state / event trace         |
| `next_action`           | acceptance receipt                  | shared_state                       |

## 4. research -> multi_agents_os 的最小投影动作

### 4.1 当前轮必须成立

| 动作                      | 最小内容                                                                                                                                                                           |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `patch_shared_state`    | `research_unit_id`、`scenario_action`、`scenario_instance_id`、`scenario_id`、`workflow_id`、`workflow_cursor`、`current_step_id`、`latest_decision`、`research_summary`、`next_action` |
| `update_active_step`    | 用 `current_step_id` 同步 `session.active_step`                                                                                                                                   |
| `add_artifact`          | 追加 `scenario_instance:{id}` 与 acceptance artifact refs                                                                                                                         |
| `assign_step_owner`     | 从 `last_step_receipt` 投影 role-bound output ownership                                                                                                                           |
| `record_role_handoff`   | 从 `last_handoff_receipt` 投影 role handoff                                                                                                                                       |
| `post_mailbox_message`  | 从 `last_handoff_receipt` 投影 mailbox item                                                                                                                                       |
| `declare_join_contract` | 从 `last_decision_receipt` 投影 join/decision gate                                                                                                                                |
| `event_log`             | 记录 state patch / artifact added / active_step changed 等最小轨迹                                                                                                                    |

补充约束：

同一份 `research result / receipts` 被 bridge 重放到同一个 `workflow_session` 时，不应重复追加 mailbox / handoff / join / artifact，也不应在 shared state / active step 无变化时继续追加事件。

### 4.2 下一轮候选扩展

| 候选动作                                        | 触发来源                                          |
| ------------------------------------------- | --------------------------------------------- |
| step receipt 到更细的 collaboration event 分类    | `last_step_receipt`                           |
| decision receipt 到多种 join/barrier 策略        | `last_decision_receipt` / future join receipt |
| mailbox 的 ack / consume / close 生命周期        | handoff-ready / task-ready receipt            |
| ownership 的 claim / release / transfer 生命周期 | role-bound output / assignee 变化               |

## 5. 当前明确不冻结的内容

下面这些内容今天不应伪装成已经稳定：

| 对象/规则                                          | 原因                                      |
| ---------------------------------------------- | --------------------------------------- |
| `last_step_receipt -> mailbox` 的固定映射           | 还没有统一 receipt 词表                        |
| `last_decision_receipt -> join_contract` 的固定映射 | decision 与 join 仍未完全对齐                  |
| `blackboard` schema                            | 对象层还没定义                                 |
| workflow-scoped memory schema                  | 还未从 shared state 中拆清                    |
| approval / verification / recovery gate 接口     | 未来属于 execution kernel + governance 共同定义 |
| framework compiler 级 Collaboration Contract    | 词表尚未冻结                                  |

## 6. 当前最小 contract 的一句话版本

当前阶段：

`multi_agents_os` 负责暴露稳定的 session/state/artifact/collaboration 写读接口；`research` 负责输出 scenario-specific checkpoint 与 receipts；bridge 负责把其中通用部分投影到 collaboration substrate。

⠀