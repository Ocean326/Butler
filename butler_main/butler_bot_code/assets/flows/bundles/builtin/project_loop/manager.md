# Manager Notes · Project Loop

## Asset Identity
- asset_kind: builtin
- asset_id: project_loop
- goal: 提供稳定的 plan → implement → review 编码工作主骨架。

## Reuse Guidance
- 这是 repo-owned builtin，更适合作为“母骨架”，而不是每次都直接拿来建实例。
- 如果用户想把它用于某类长期重复任务，优先 clone 到 template，再在 template 层调整。
- 如果用户只是想讨论某次具体任务怎么落到这套骨架，先把 template/flow 的分层讲清楚，不要立刻创建实例。

## Manager Checklist
- 当需求是新工作时，先判断：应该复用现有 template，还是从 `project_loop` clone 出一个 task-specific template。
- 如果 phase 职责、goal 结构、review 标准会长期变化，优先走 clone，而不是直接围绕 builtin 创建 flow。
- 只有当 template 层和 supervisor 方向都已经说清楚并被确认后，才进入具体 flow 创建。
