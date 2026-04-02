# recent 到 local_memory 迁移与写入机制

> 摘要入口；完整机制说明见 **L2_details/recent到local_memory迁移与写入机制_detail.md**。

## 摘要

- **两条写入路径**：① 每轮落盘时（`should_write` + summary 非空 + governor 放行），依赖模型或 LONG_TERM_HINTS 启发式；② 压缩时（recent 超量后挤出、>1 天且带反思类关键词，最多 2 条）。
- **现状**：机制在运行但触发面窄；**无写入流水或集中历史**，用户反馈记不住「何时何条写入了 local memory」。
- **可选改进**：增加写入流水、file-manager 整理时批量扫描 should_write 择优写入、放宽启发式。

**关键词**：recent_memory、local_memory、迁移、压缩、写入历史、LONG_TERM_HINTS、should_write、写入流水

## 2026-03-10 12:08
- 摘要：从 recent 到 local 有每轮落盘（should_write+summary）与压缩时（旧条>1天+关键词最多2条）两条路径，机制在运行但触发面窄；无写入流水或集中历史，用户反馈记不住「何时何条写入了 local memory」；已写 L1 说明文档，可选改进为增加写入流水与放宽启发式。
- 关键词：recent_memory、local_memory、迁移、压缩、写入历史、LONG_TERM_HINTS、should_write、写入流水

