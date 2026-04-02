# recent_memory → local_memory 迁移与写入机制说明（详情）

> 用途：说明从 recent 迁移/压缩到 local_memory 的机制、触发条件、以及如何追踪「哪条对话写入了 local_memory」。  
> 创建：2026-03-10，feishu-workstation-agent 根据 memory_manager / memory_service / 长期记忆整理记录 梳理。  
> **用户反馈**：记不住「何时何条写入了 local memory」、无写入流水。2026-03-10 已补充写入流水与 should_write 补偿迁移，见 §2、§4。

---

## 1. 三条写入 local_memory 的路径

### 1.1 每轮回复落盘时（即时沉淀）

- **位置**：`memory_manager._finalize_recent_and_local_memory` → 在 `_summarize_turn_to_recent` 得到本条 `long_term_candidate` 后。
- **条件**（同时满足才会写）：
  - `long_term_candidate.should_write === true`
  - `long_term_candidate.summary` 非空
  - `_govern_memory_write` 放行（默认未开 governor 则一律放行）
- **`should_write` 从哪来**：
  - **模型提炼**：`TurnMemoryExtractionService.extract_turn_candidates` 会调模型产出 JSON，其中含 `long_term_candidate.should_write`。
  - **启发式**：若模型未标或提炼失败，用 `_heuristic_long_term_candidate`：只有对话内容里出现 `LONG_TERM_HINTS` 中的词才会标 `should_write`。
- **LONG_TERM_HINTS**（代码常量）：  
  `"记住","以后","默认","偏好","必须","统一","固定","长期","沿用","always","default","remember","preference","must"`
- **结论**：只有「用户或助手说了这类词」或「模型判断值得长期保留」的轮次，才会在**当轮落盘时**写入 local_memory。其它轮次不会在这一步写。

### 1.2 每轮/维护的 should_write 补偿迁移（防漏）

- **位置**：`memory_manager._promote_recent_long_term_candidates`，在两处触发：  
  - 每轮收尾：`_finalize_recent_and_local_memory`  
  - recent 维护：`_run_recent_memory_maintenance_once`
- **行为**：扫描 recent 中 `long_term_candidate.should_write === true` 且 `summary` 非空、但尚未标记 `promoted_to_local_at` 的条目，按最新优先最多提升 N 条（每轮 2 条，维护 3 条）写入 local。
- **写回标记**：成功写入（含重复判定）后，在该 recent 条目的 `long_term_candidate` 内写入：  
  - `promoted_to_local_at`  
  - `promoted_action`  
  - `promoted_source`
- **结论**：不再只依赖“当轮一次命中”；历史 should_write 条目可被补偿迁移，降低遗漏。

### 1.3 压缩时（反思沉淀）

- **位置**：`memory_manager._compact_recent_entries_if_needed`，在 recent 条数 > 15 或总字符 > 15k 时触发（与 `recent_memory_compact_policy.md` 一致）。
- **行为**：把「被挤出去的旧条」里、**时间早于 1 天**的条目，用关键词筛（反思、教训、下次、避免、必须、默认、偏好、规则、约束），最多选 **2 条** 调用 `_upsert_local_memory`。
- **结论**：只有「先被挤出 recent + 已超过 1 天 + 内容带上述关键词」的条目才会通过这条路径进 local_memory，**频率低、条件严**。

---

## 2. 写入流水（可追溯）

- **位置**：`local_memory/local_memory_write_journal.jsonl`（按行 JSON）
- **落点**：由 `_upsert_local_memory` 统一追加，无论来源是：  
  - 每轮即时沉淀（`source_type=per-turn`）  
  - should_write 补偿迁移（`source_type=recent-sweep`）  
  - 压缩反思沉淀（`source_type=recent-compact`）  
  - 手动追加（`source_type=manual`）
- **关键字段**：`timestamp`、`action`、`title`、`summary_path`、`detail_path`、`source_memory_id`、`source_reason`、`source_topic`。
- **用途**：可直接回答“哪次写入了 local、写到了哪、来源是哪条 recent”。

---

## 3. 其它相关但「不负责批量 recent→local」的部分

- **file-manager-agent 长期记忆整理**：  
  触发方式为「用户主动说触发长期记忆整理」或 startup/watchdog。  
  做的是：盘点 local_memory 文件、合并同主题、压缩 recent、在 `长期记忆整理记录.md` 里记一笔。  
  文档里虽写「将 long_term_candidate.should_write: true 的条目择优写入 local_memory」，但**实际执行取决于 file-manager 的 prompt 与当次上下文**，不是 memory_manager 里对「所有 should_write 条目」的自动批量写入。
- **recent_archive.md**：  
  只存「被压缩掉的旧条」的摘要快照，**不记录**「哪条被写入了 local_memory、写入到哪个文件」。

---

## 4. 为什么过去会出现“聊了很多但记不住”

可以拆成两点理解：

1. **以前没有集中可查的写入流水**  
   现在已补 `local_memory_write_journal.jsonl`。

2. **很多轮未命中 should_write**
   - 若用户**没有**说「记住、以后、默认、偏好…」等（heuristic 不标），且模型也没标 `should_write`，则**当轮不会写入** local_memory。
   - 过去若当轮没写，只能等压缩反思路径（条件苛刻）。  
   - 现在新增 should_write 补偿迁移，会回扫 recent 并补写。

---

## 5. 当前机制状态（2026-03-10）

- **每轮即时沉淀**：仍按 `should_write + summary + governor` 写 local。
- **should_write 补偿迁移**：已上线，避免“当轮漏写后永久丢失”。
- **压缩反思沉淀**：仍保留，作为旧条目兜底。
- **写入历史**：已上线 `local_memory_write_journal.jsonl`，可追溯来源与落点。

---

## 6. 后续可继续优化（可选）

- **写入流水可视化**：把 jsonl 汇总成可读 markdown 视图，便于人工巡检。
- **写入质量评分**：对 `duplicate-skip` 频次做统计，识别“过度重复沉淀”。
- **策略分层**：把“偏好/约定/愿景”拆不同阈值，进一步平衡召回与噪音。

---

- **关键词**：recent_memory、local_memory、迁移、压缩、should_write、写入历史、long_term_candidate、memory_manager、file-manager-agent
