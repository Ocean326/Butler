# Guardian 负责重启 Butler 的约定

来源：feishu 管家bot 自动沉淀

> **时效说明（2026-03-25 更新）**：这条约定已经退役，不再代表当前 Butler chat 的运行机制。当前不再依赖 guardian 守护进程触发 chat 重启；涉及当前守护与任务真源时，以 `人格与自我认知.md`、chat runtime 与 `task_ledger.json` / `background_maintenance` 现行链路为准。


## 2026-03-10 04:57
- 摘要：Guardian 为守护进程，重启 Butler 的权限在 Guardian；用户只需在 guardian 端触发重启，由 guardian 对 Butler 主进程执行软重启或更彻底重启，人格与规则按 feishu-workstation-agent.md 与 Butler_SOUL 重载。
- 关键词：Guardian、守护进程、重启 Butler、feishu-workstation-a、Butler_SOUL

