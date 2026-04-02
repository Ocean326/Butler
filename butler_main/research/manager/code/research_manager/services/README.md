# research_manager services

这里放研究业务服务层。

当前最小分层：

- `scenario_registry.py`
  - 维护 `unit_id -> scenario asset` 的静态映射
  - 负责读取 `workflow.spec.json`
- `scenario_instance_store.py`
  - 维护 scenario thread / instance 的最小状态真源
  - 负责 bind/create/load/update/events
- `scenario_runner.py`
  - 把场景 asset 解释成当前 `active_step`
  - 输出 `workflow_cursor / receipts / output_template`
- `unit_registry.py`
  - 维护 `unit_id -> handler` 的统一映射
  - 保证 `orchestrator` / `talk` / `codex` 入口最终都走同一业务核
  - 负责把 unit handler、scenario runner、scenario instance 拼起来

后续建议继续承接：

- 论文发现与筛选流水线
- 项目下一步规划
- 进展摘要生成
- 研究看板同步

服务层负责业务编排，不直接承担 runtime core 职责。
