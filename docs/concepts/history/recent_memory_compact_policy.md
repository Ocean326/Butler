# Recent Memory 压缩策略说明

> 状态说明（2026-03-25）：本文描述的是 `talk_recent / beat_recent` 双池时代的历史压缩策略。当前现行口径以按 `session_scope_id` 隔离的 recent memory 为准；文中的 `beat_recent` 应理解为历史后台自动化池命名。

> **对应清单**：自我改进计划 2.2 — recent 压缩策略文档化（compact 触发条件、摘要策略）  
> **实现位置**：`butler_bot_code/butler_bot/memory_manager.py`  
> **文档创建**：2026-03-08（心跳·文献阅读长期任务备选：02 无未读资料时推进 butler 自我改进清单）

## 0. 当前池划分

- `talk_recent`：`butler_bot_agent/agents/recent_memory/recent_memory.json`，供对话续接使用。
- `beat_recent`：`butler_bot_agent/agents/recent_memory/beat_recent/recent_memory.json`，供历史后台连续思考使用。
- 两个池独立压缩、独立归档，可以互相只读，但不直接混写活跃内容。

---

## 1. 触发条件

压缩在以下**任一**条件满足时触发：

| 条件 | 常量 | 含义 |
|------|------|------|
| 条数超限 | `TALK_RECENT_MAX_ITEMS = 15` | `len(entries) > 15`（talk 池） |
| 字符超限 | `TALK_RECENT_MAX_CHARS = 15000` | `_recent_entries_chars(entries) > 15000`（talk 池） |

**调用点**：

- 每轮对话落盘后：`_finalize_recent_and_local_memory` → `_compact_recent_entries_if_needed(..., reason="per-turn")`
- 每轮 fallback 落盘：`_write_recent_completion_fallback` → `reason="per-turn-fallback"`
- 每轮 pending 追加：`begin_pending_turn` → `reason="per-turn-pending"`
- 定时/启动维护：`_run_recent_memory_maintenance_once` → `reason="startup-subprocess"` / `"startup-watchdog"` / `"scheduled"`
- 手动追加：`append_recent_entry` → `reason="manual-append"`

---

## 2. 压缩行为（摘要策略）

1. **保留**：只保留**最近 `TALK_RECENT_MAX_ITEMS` 条**（即最后 15 条），`keep_entries = entries[-15:]`。  
2. **旧条归档**：被挤出的旧条 `old_entries = entries[:-15]`：
   - 取其中**最多最近 20 条**，按 `[timestamp] topic: summary[:120]` 拼成文本，总长上限 2000 字符；
   - 该文本以 `## {stamp} 旧记忆压缩({reason})\n\n{archive_text}` 形式**追加**到 `./butler_bot_agent/agents/recent_memory/recent_archive.md`。
3. **反思沉淀**：在 `old_entries` 中，将 **时间早于 1 天** 的条目做关键词筛选（含「反思、教训、下次、避免、必须、默认、偏好、规则、约束」等），最多选 **2 条**，写入 **local_memory**（`_upsert_local_memory`），便于长期记忆保留。
4. **落盘**：压缩后的列表（仅 `keep_entries`）写回 `recent_memory.json`。

---

## 3. 与长期记忆的关系

- **recent_archive.md**：仅作历史快照，不参与 prompt 注入；供人工或后续工具查看「曾经发生过什么」。
- **local_memory**：通过「反思沉淀」选出的少量条目会 upsert 到 `./butler_bot_agent/agents/local_memory/`，与长期记忆的「文件数限制、超长截断」策略一致（见 long memory 维护逻辑）。
- **prompt 注入**：`prepare_user_prompt_with_recent` 读取 `recent_memory.json` 中**最近 `TALK_RECENT_MAX_ITEMS`（15）条**对话短期记忆，总字符上限 `TALK_RECENT_MAX_CHARS`，渲染为「最近 N 轮摘要」注入用户 prompt；**最近 15 条不压缩**，即全部进入上下文。

---

## 4. 小结

| 项目 | 说明 |
|------|------|
| 触发 | 条数 > 15（talk）或 JSON 总字符 > 15000 |
| 保留 | 最后 15 条 |
| 注入 | 最近 15 条对话短期记忆不压缩，全部进入 prompt |
| 归档 | 旧条摘要追加到 `recent_archive.md`（最多 20 条、2000 字） |
| 反思 | 1 天前的旧条中按关键词选最多 2 条写入 local_memory |

后续若调整阈值（如 `RECENT_MAX_ITEMS`、`RECENT_MAX_CHARS`）或摘要格式，可在本文档中同步更新。

---

## 5. 抽查记录（2026-03-11）

- `butler_bot/memory_manager.py` 中 `TALK_RECENT_MAX_ITEMS` 与 `BEAT_RECENT_MAX_ITEMS` 当前均为 15，且 `_recent_max_items` / `_recent_max_chars` 统一作为 recent 压缩与维护入口。
- `_render_recent_context` 渲染对话侧近期流时使用 `talk_lines[-TALK_RECENT_MAX_ITEMS:]`，与本文件“最近 15 条全部进入 prompt、不额外再截断”的约定一致。
- 未发现回退到 10 条或额外的双重截断逻辑；心跳与对话侧近期流在条数与阈值上保持一致。
- 本轮仅为策略与实现现状抽查，后续若调整条数或字符上限，需要同时更新本文档与相关 tests。
