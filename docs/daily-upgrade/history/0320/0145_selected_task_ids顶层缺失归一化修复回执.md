# selected_task_ids 顶层缺失归一化修复回执

时间：2026-03-20 01:45  
时间标签：0320_0145  
归档分支 ID：`20260319-selected-task-ids-normalize`

## 本次结论

- 已确认 `ButlerHeartbeatSchedulerAdapter.normalize_planner_plan()` 在 `chosen_mode != 'status'` 且顶层 `selected_task_ids` 为空时，会从 `task_groups -> branches -> selected_task_ids` 聚合并回填顶层。
- 已补一条更贴近故障面的测试：当顶层 `selected_task_ids` 类型不是 `list` 时，仍可从 branch 回填，避免误降级为 `status-only`。

## 目标问题

此前心跳规划器输出若缺少顶层 `selected_task_ids`，或该字段类型异常，消费方只读顶层字段时会把本可执行计划误判为“未明确选中任务”，继而降级为 `status-only`。

## 当前实现

- 代码位置：`butler_main/butler_bot_code/butler_bot/agents_os_adapters/heartbeat_scheduler.py`
- **行号锚点（以 import 为准，续跑时若漂移请以文件内符号为准）**
  - 类入口 `ButlerHeartbeatSchedulerAdapter`：约 L8
  - `_sanitize_id_list`（顶层列表清洗；非 `list` 类型直接视为空列表）：约 L12–L23
  - `_selected_ids_from_task_groups`（按 `task_groups → branches[*].selected_task_ids` 聚合、去重、保序）：约 L25–L44
  - `normalize_planner_plan`（`explore` 门控 → 顶层清洗 → 条件回填 → 仍空则 `status_only_plan`）：约 L78–L95
- 关键策略：
  - 顶层 `selected_task_ids` 若为**非 list**（如字符串），`_sanitize_id_list` 返回 `[]`，随后当 `chosen_mode != 'status'` 时触发 branch 回填；这与「类型异常仍可从 branch 恢复」的故障面一致。
  - 当 `chosen_mode != 'status'` 且清洗结果为空时，从 `task_groups/branches` 聚合 `selected_task_ids`；
  - 聚合结果回填到顶层 `selected_task_ids`；
  - 仅在回填后仍为空时，才保留原有 `status-only` 降级（理由串见代码内 `status_only_plan(..., '规划器输出缺少明确 selected_task_ids，降级为 status-only')`）。
- **与 `task_ledger.json` 真源的关系（三角验收语义）**
  - 本归一化只解析/修正**规划器输出的 plan 字典**中的 `selected_task_ids` 承载方式，**不读写 ledger**。
  - 任务执行态与状态机仍以 `agents/state/task_ledger.json` 为 machine-readable 真源；planner 文本读口与 active 域边界见 `butler_main/butler_bot_agent/agents/local_memory/人格与自我认知.md` 锚点 `HEARTBEAT_LEDGER_TRUTH_BOUNDARY`、`SELECTED_TASK_IDS_NORMALIZE_GUARD`（与索引 `docs/daily-upgrade/INDEX.md` → 本文）。

## 验证

- 测试文件：`butler_main/butler_bot_code/tests/test_runtime_smoke_scenarios.py`
- 通过用例：
  - 顶层为空，branch 提供 `selected_task_ids=['t1','t2']`，归一化后保留 `short_task` 且返回 `['t1','t2']`；
  - 顶层类型异常（字符串），branch 提供 `selected_task_ids=['t1']`，归一化后保留 `short_task` 且返回 `['t1']`。
- 本地执行：
  - `python -m pytest .\butler_main\butler_bot_code\tests\test_runtime_smoke_scenarios.py -q`
  - 结果：`6 passed`

## 影响与边界

- 未引入新字段。
- 未改变 `chosen_mode='explore'` 的原有降级规则。
- 未放宽“最终仍无明确任务选择则降级为 `status-only`”这一兜底策略。

## 下一步建议

- 若后续要彻底闭环，可再补一次历史 trace 回放，确认同类 planner 输出不再出现 `规划器输出缺少明确 selected_task_ids，降级为 status-only`。
