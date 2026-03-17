# maintenance_memory_agent

职责：
- 独立周期性运行
- 不依赖主对话链路
- 执行 merge duplicates / prune stale / TTL / canonical rewrite / relation repair

权限边界：
- 可以治理 local memory
- 默认不直接修改 `user_profile`
