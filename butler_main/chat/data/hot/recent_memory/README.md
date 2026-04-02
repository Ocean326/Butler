# recent_memory

用途：保存 chat runtime 的短期记忆与窗口摘要。

- 机器读写文件：`recent_memory.json`
- 原始 turn 真源：`recent_raw_turns.json`（保留 `assistant_reply_visible` / `assistant_reply_raw`）
- 窗口摘要池：`recent_summary_pool.json`（每 10 条 completed turn 生成 1 条，最多保留最近 5 条）
- prompt 注入：最近 10 条 visible turn + 最近 5 条窗口摘要，总注入文本默认不超过 10000 字
- 长期治理队列：`long_memory_queue.json`
- 旧记忆沉淀：窗口摘要被挤出池后，先进入治理，再择优写入 `../local_memory/`
- 旧记忆压缩归档：`recent_archive.md`
- 启动维护状态：`startup_maintenance_status.json`（记录启动维护是否已完成）

说明：当前目录由 `butler_main/chat` runtime 自动维护。
