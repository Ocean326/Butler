# 0331 前台 butler-flow 角色运行时与 role-session 绑定实施回写

日期：2026-03-31  
最后修改：2026-04-01  
状态：已落代码 / 当前真源  
所属层级：L1 `Agent Execution Runtime`（前台附着），辅用 L2 本地状态/轨迹存储  
关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [02_前台WorkflowShell收口.md](./02_前台WorkflowShell收口.md)
- [04c_butler-flow完备升级与视觉设计计划.md](./04c_butler-flow完备升级与视觉设计计划.md)
- [System_Layering_and_Event_Contracts.md](../../runtime/System_Layering_and_Event_Contracts.md)
- [02B_协议编排与能力包开发计划.md](../0330/02B_协议编排与能力包开发计划.md)
- [02C_会话协作与事件模型开发计划.md](../0330/02C_会话协作与事件模型开发计划.md)
- [02D_持久化恢复与产物环境开发计划.md](../0330/02D_持久化恢复与产物环境开发计划.md)
- [02R_外部Harness映射与能力吸收开发计划.md](../0330/02R_外部Harness映射与能力吸收开发计划.md)

## 改前四件事（本轮收口）

| 项 | 内容 |
| --- | --- |
| 目标功能 | 在前台 `butler-flow` 引入三档执行模式：`simple / medium / complex`；本轮主落 `medium=角色 + session 绑定`，并让 `simple` 保持兼容。 |
| 所属层级 | 主落 L1 前台执行运行时；向下借 L4 的 typed handoff / artifact visibility 语义；持久化仍落 L2 文件侧边车。 |
| 当前真源文档 | [02_前台WorkflowShell收口.md](./02_前台WorkflowShell收口.md) 负责前台 CLI 总入口；本文负责 role runtime 细节与 medium 当前边界。 |
| 主代码与测试 | `butler_main/butler_flow/`；辅看 `butler_main/multi_agents_os/session/` 与 `workflow_factory.py`；回归 `test_butler_flow.py`、`test_butler_cli.py`、`test_butler_flow_tui_controller.py`、`test_butler_flow_tui_app.py`、`test_chat_cli_runner.py`。 |

## 一句话裁决

前台 `butler-flow` 现在已具备显式 `execution_mode`，并把 **角色分工** 与 **共享状态/消息流** 拆开：  
`simple` 仍是单 session；`medium` 已落 role-bound session；`complex` 只保留 per-activation 的合同、状态字段与路由位，不在本轮把整套调度硬做完。

## 已落实现

本轮代码主落：

- `butler_main/butler_flow/constants.py`
- `butler_main/butler_flow/role_runtime.py`
- `butler_main/butler_flow/models.py`
- `butler_main/butler_flow/state.py`
- `butler_main/butler_flow/prompts.py`
- `butler_main/butler_flow/runtime.py`
- `butler_main/butler_flow/app.py`
- `butler_main/butler_flow/cli.py`
- `butler_main/butler_flow/role_packs/`

实现结果：

- 新增执行模式：
  - `simple`
  - `medium`
  - `complex`
- 新增 session 策略：
  - `shared`
  - `role_bound`
  - `per_activation`
- CLI / launcher / manage 入口已能携带：
  - `--execution-mode <simple|medium|complex>`
  - `--role-pack <coding_flow|research_flow>`
- 新 flow 创建时优先采用前台配置默认值；旧 flow `resume/manage` 时保留原 mode / pack，除非显式覆盖。

## 执行模式

- `simple`
  - 单 `codex_session_id` 贯穿全流程
  - 角色只体现在 prompt 描述，不做 session 级隔离
  - 旧 flow 无 role 字段时统一按这一档解释
- `medium`
  - 每个 role 独立 session
  - 角色再次激活时优先 resume 自己 session
  - 角色切换只通过 `handoff + artifact refs + bounded flow truth`
  - 不共享上一个 role 的 thread 历史
- `complex`
  - 每次进入角色都要求新建 session
  - 所有必需上下文都必须来自 handoff / artifact / flow truth
  - 当前仅落状态合同与 `per_activation` 策略映射，尚未把缺失 handoff 时的硬失败门控做成完整产品面

默认映射：

- `simple -> session_strategy=shared`
- `medium -> session_strategy=role_bound`
- `complex -> session_strategy=per_activation`

## 角色与相位分离

相位仍保留 `plan -> imp -> review` 主环，但 `medium` 已把角色和相位拆开：

- `plan -> planner`
- `imp -> implementer`
- `review -> reviewer`
- `review` 判为 bug/fix 时 -> `fixer`
- `done -> reporter`
- `research_flow` role pack 额外允许 `researcher`

当前路由口径：

- 相位决定默认角色
- 角色完成后可通过 judge / follow-up 决定下一角色
- `fixer` 视为实现修复的专职角色，不再和 `implementer` 共享同一 role session

## 状态模型

### `workflow_state.json`

新增或扩展字段：

- `execution_mode`
- `session_strategy`
- `active_role_id`
- `role_pack_id`
- `role_sessions`
- `latest_role_handoffs`

兼容规则：

- 旧 flow 未出现 role 字段时，按 `simple/shared` 解释
- 旧 `codex_session_id` 保留，继续作为 simple 模式主 session 与兼容字段
- 读取旧 flow 时若缺少 `session_strategy`，按 `execution_mode` 自动推导

### `role_sessions.json`

每条 flow 新增 sidecar：

- `flow_id`
- `items`
- `by_role_id`
- `updated_at`

其中 `items[*]` 当前至少包含：

- `role_id`
- `session_id`
- `status`
- `updated_at`
- `last_handoff_id`

若 provider 尚未返回新的 thread/session id，允许写入：

- `status=pending_session_id`

### `handoffs.jsonl`

每次角色切换追加一条 handoff 记录，当前至少覆盖：

- `handoff_id`
- `flow_id`
- `from_role_id`
- `to_role_id`
- `source_phase`
- `target_phase`
- `summary`
- `goal`
- `guard_condition`
- `completion_summary`
- `open_questions`
- `next_action`
- `artifact_refs`
- `verification_refs`
- `risk_flags`
- `created_at`
- `consumed_at`
- `status`

当前 `status` 已落：

- `pending`
- `consumed`

补充说明：

- `superseded` 仍属于下一步 handoff versioning 计划，不在本轮已落代码范围内

### `artifacts.json` 与 `turns.jsonl`

前台 artifact / turn 轨迹同步扩展：

- `artifacts.json`
  - `producer_role_id`
  - `consumer_role_ids`
  - `phase`
  - `turn_id`
- `turns.jsonl`
  - `role_id`
  - `role_session_id`
  - `source_handoff_id`
  - `target_handoff_id`

## Prompt 与治理层

当前 `medium` 的 prompt 装配顺序固定为：

1. flow truth
2. role prompt
3. latest inbound handoff
4. relevant artifacts / verification refs
5. 可选 governance overlay

前台 role pack 已落两套：

- `coding_flow`
  - `planner`
  - `implementer`
  - `reviewer`
  - `fixer`
  - `reporter`
- `research_flow`
  - `planner`
  - `researcher`
  - `implementer`
  - `reviewer`
  - `fixer`
  - `reporter`

提示词来源策略：

- 第一版优先采用外部开源范式的轻改写 seed
- Butler 侧只补：
  - 本仓库语境
  - handoff 契约
  - artifact 引用约定
  - verification 期望

前台治理开关继续只作用于 `butler_flow`：

- `butler_flow.role_runtime.enable_role_handoffs`
- `butler_flow.role_runtime.role_pack`
- `butler_flow.role_runtime.execution_mode_default`
- `butler_flow.prompt_policy.include_repo_governance_blocks`
- `butler_flow.prompt_policy.include_background_task_constraints`
- `butler_flow.prompt_policy.include_heavy_acceptance_blocks`

## 当前硬边界

1. 不进入 `campaign/orchestrator` 后台主链。
2. 不把 `mailbox/join` 做成本轮主循环强依赖。
3. 不把外部框架 UI/DSL/节点名直接回灌 Butler 真源。
4. 不用“同一个 session 里切角色 prompt”伪装多角色隔离。
5. `complex` 当前只保留合同和状态位，不宣称已完成完整隔离执行面。

## 验收结果

本轮已完成：

- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow.py butler_main/butler_bot_code/tests/test_butler_cli.py butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py butler_main/butler_bot_code/tests/test_butler_flow_tui_app.py butler_main/butler_bot_code/tests/test_chat_cli_runner.py -q`
  - 结果：`75 passed`
- `./.venv/bin/python -m py_compile butler_main/butler_flow/constants.py butler_main/butler_flow/role_runtime.py butler_main/butler_flow/models.py butler_main/butler_flow/state.py butler_main/butler_flow/prompts.py butler_main/butler_flow/runtime.py butler_main/butler_flow/app.py butler_main/butler_flow/cli.py`
- `./.venv/bin/python -m butler_main.butler_flow --help`

当前验收结论：

- simple 模式未回归
- medium 模式已稳定写出 `role_sessions.json`、`handoffs.jsonl`
- 角色切换时不再直接共享上一个角色的 session
- handoff / artifact 边界已可被下一角色消费
- 旧 flow 可兼容读取

## Medium 下一步赶紧计划

### 第一波：把当前已落字段真正做成稳定产品面

参考 [02D_持久化恢复与产物环境开发计划.md](../0330/02D_持久化恢复与产物环境开发计划.md) 与 [02C_会话协作与事件模型开发计划.md](../0330/02C_会话协作与事件模型开发计划.md)：

- 把 `role_sessions.json`、`handoffs.jsonl`、artifact visibility 做成明确的 status / history / inspect 投影
- 在 `/status`、`/flows`、TUI single-flow 里展示当前 `active_role_id`、每个 role 的 session 状态、最新 inbound handoff 摘要
- 给 handoff 增加更稳定的 `ack/consumed` 读写路径，而不是只有 JSONL 追加语义

### 第二波：把 role runtime 从“字段已落”推进到“协议更稳”

参考 [02B_协议编排与能力包开发计划.md](../0330/02B_协议编排与能力包开发计划.md) 与 [02C_会话协作与事件模型开发计划.md](../0330/02C_会话协作与事件模型开发计划.md)：

- 把 role prompt seed 进一步收口成 role spec / handoff contract，而不是只是一组 `.md` 提示词
- 给 `fixer`、`reviewer`、`researcher` 补更清晰的 required outputs / artifact expectations
- 让 `complex` 模式真正校验 handoff 完整性，缺字段时硬失败，不偷偷回退到共享历史

### 第三波：把外部学习样本正式纳入可维护映射

参考 [02R_外部Harness映射与能力吸收开发计划.md](../0330/02R_外部Harness映射与能力吸收开发计划.md)：

- 为 DeerFlow、LangGraph 风格工作流建立更正式的 role-pack/source mapping，而不是只做一次性拷贝
- 给 `role_packs/*/sources.json` 增加版本、来源、裁剪理由与 Butler 适配说明
- 形成“可升级外部角色种子 -> Butler role pack -> 运行态 handoff 契约”的固定链路
