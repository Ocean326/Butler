# compact_memory_agent

职责：
- 在 recent 超阈值、即将驱逐前处理 old_entries
- 生成 SummaryBlock
- 从 SummaryBlock 提取 summary_candidates

权限边界：
- 只允许受限写入 `project_state` / `reference` / `archive`
- 默认不允许直接修改 `user_profile`
