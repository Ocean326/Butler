# 0317 现状：recent -> local memory 机制说明

> 更新：2026-03-17 晚间已完成一轮 `memory_pipeline/` 模块化接线。本文前半部分描述的是 0317 白天的原始链路，末尾第 13 节补充“模块化后的真实现状”。

## 1. 目的

本文只描述 **当前 Butler 代码真实生效** 的 recent -> local memory 链路，用来回答四个问题：

1. recent 什么时候会尝试沉淀到 local memory
2. 是谁在整理
3. 怎么整理
4. 为什么有些“用户长期偏好/对话约定”虽然被记住了，但没有变成强约束

主要代码位置：

- `butler_main/butler_bot_code/butler_bot/memory_manager.py`
- `butler_main/butler_bot_code/butler_bot/agent.py`
- `butler_main/butler_bot_code/butler_bot/services/local_memory_index_service.py`

---

## 2. 总览一句话

当前机制不是“recent 满了以后一次性搬进 local”。

而是三段式：

1. 每轮对话先提炼成 recent
2. 每轮收尾时，直接尝试把本轮 long_term_candidate 写入 local
3. 每轮和维护时，再 sweep 一遍 recent 中尚未提升的 long_term_candidate，补写到 local

所以它本质上是：

- `per-turn direct promote`
- `per-turn sweep promote`
- `maintenance sweep promote`

并行存在，而不是单一路径。

---

## 3. recent 是怎么生成的

入口函数：

- `MemoryManager._finalize_recent_and_local_memory()`
- 代码：`memory_manager.py:1757`

在每轮回复发送后，Butler 会：

1. 先写一条 fallback recent，避免因为异步线程失败导致 recent 断档
2. 再调用 `_summarize_turn_to_recent()` 提炼本轮对话
3. 再经 `subconscious_service.consolidate_turn(...)` 把一轮对话整理成：
   - 主 recent 条目
   - companion 条目（如 relationship / mental / task_signal）

对应关键函数：

- `_summarize_turn_to_recent()`：`memory_manager.py:1918`
- `_heuristic_long_term_candidate()`：`memory_manager.py:2088`

### 3.1 本轮 recent 里和 local 提升最相关的字段

每条 recent 最关键的是：

1. `summary`
2. `next_actions`
3. `long_term_candidate`

其中 `long_term_candidate` 结构里最重要的是：

1. `should_write`
2. `title`
3. `summary`
4. `keywords`
5. `promoted_to_local_at`
6. `promoted_action`
7. `promoted_source`

只有 `should_write=true` 的条目，才有资格进入 local memory 提升链。

---

## 4. recent 什么时候整理到 local memory

当前有两个主时机。

### 4.1 每轮对话结束后立即整理

发生位置：

- `MemoryManager._finalize_recent_and_local_memory()`
- 代码：`memory_manager.py:1757`

流程如下：

1. 提炼本轮 recent entry
2. 写入 recent 池
3. 如果本轮主 entry 自带 `long_term_candidate.should_write=true`
   - 立刻调用 `_upsert_local_memory(...)`
   - 来源记为 `source_type="per-turn"`
   - `source_reason="long_term_candidate"`
4. 然后再调 `_promote_recent_long_term_candidates(...)`
   - 对 recent 池里尚未提升的候选做一次 sweep
   - 原因记为 `per-turn-sweep`
5. 最后 compact recent 并保存

这意味着：

1. 本轮内容有可能当轮就进 local
2. 本轮没直接写进去，也可能在同一轮 sweep 时补写进去

### 4.2 recent 维护时批量整理

发生位置：

- `MemoryManager._run_recent_memory_maintenance_once()`
- 代码：`memory_manager.py:1729`

维护链路会做：

1. 压缩 recent
2. 归档 stale recent
3. 再调用 `_promote_recent_long_term_candidates(...)`
   - 原因记为 `recent-maintenance:{reason}`

这意味着：

1. 有些在单轮里漏掉的 long_term_candidate
2. 会在后续维护时再次被扫描并提升到 local

---

## 5. 是谁在整理

不是一个组件包办，而是 3 层协作。

### 5.1 Turn 提炼层

负责把一轮对话抽成结构化 recent 候选：

- `TurnMemoryExtractionService`
- 入口由 `_summarize_turn_to_recent()` 调用

职责：

1. 生成主 summary
2. 生成 `next_actions`
3. 生成 `long_term_candidate`
4. 在模型失败时退回 heuristic

### 5.2 对话收尾层

负责每轮结束时把 recent 和 local 真正落盘：

- `MemoryManager._finalize_recent_and_local_memory()`

职责：

1. 写 completed recent
2. merge companion 条目
3. direct promote 当前轮 long_term_candidate
4. per-turn sweep 提升未写入的候选
5. merge heartbeat tasks
6. compact recent

### 5.3 维护补捞层

负责在维护阶段再次扫描 recent：

- `MemoryManager._run_recent_memory_maintenance_once()`

职责：

1. 处理 recent 压缩与归档
2. 扫描 recent 中仍未提升的 `should_write` 条目
3. 以维护原因为来源标记补写到 local

---

## 6. 怎么从 recent 提升到 local

核心函数：

- `_promote_recent_long_term_candidates()`：`memory_manager.py:6123`
- `_upsert_local_memory()`：`memory_manager.py:6201`
- `_mark_recent_entry_local_promoted()`：`memory_manager.py:6112`

### 6.1 promote 的筛选条件

`_promote_recent_long_term_candidates()` 会倒序扫描 recent 条目，满足以下条件才处理：

1. 条目是 dict
2. 有 `long_term_candidate`
3. `should_write=true`
4. 还没有 `promoted_to_local_at`
5. `long_term_candidate.summary` 非空

满足后，会调用 `_upsert_local_memory(...)`。

### 6.2 upsert 到 local 的规则

`_upsert_local_memory(...)` 不是简单“写个文件”，而是做一套 upsert：

1. 先确保 local memory 目录与索引存在
2. 先找相似记忆
3. 若找到相似文件：
   - 追加到已有文件
   - action 可能是 `append-similar` 或 `duplicate-skip`
4. 若没找到：
   - 以 `title` 为文件名写入 L1 summary 文件
   - action 可能是 `write-new` 或 `append-existing`
5. 若 summary 太长：
   - 拆到 `L2_details/..._detail.md`
   - L1 只保留 preview / current conclusion
6. 更新：
   - local memory index
   - relations
   - write journal

### 6.3 promote 成功后 recent 会被怎么标记

如果 upsert 的 action 属于以下之一：

- `write-new`
- `append-existing`
- `append-similar`
- `duplicate-skip`

就会调用 `_mark_recent_entry_local_promoted()`，回写到 recent 条目的 `long_term_candidate`：

1. `promoted_to_local_at`
2. `promoted_action`
3. `promoted_source`

所以 current recent 里能知道：

1. 这条是否已经进过 local
2. 是 direct promote 还是 sweep promote
3. 最终落盘动作是什么

---

## 7. local memory 最终落在哪些文件

常见落点分三层。

### 7.1 L1 摘要层

例如：

- `local_memory/L1_summaries/对话长期约束.md`
- `local_memory/L1_summaries/...`

作用：

1. 保存人类可读的长期摘要
2. 作为 local memory query 的主要检索对象

### 7.2 L2 详情层

例如：

- `local_memory/L2_details/..._detail.md`

作用：

1. 保存较长原文或详细沉淀
2. L1 只保留浓缩后的 current conclusion

### 7.3 写入日志与索引层

例如：

- `local_memory/local_memory_write_journal.jsonl`
- `local_memory/L0_index.json`
- `local_memory/.relations.json`

作用：

1. 记录写入动作来源
2. 支持检索与相似归并
3. 让 Talk / Heartbeat 后续能 query 命中

---

## 8. Talk 里 local memory 是怎么被读回来的

Talk 并不会把整个 local memory 全量注入，而是命中式查询。

入口：

- `agent.py:138` `render_local_memory_hits(...)`

后端：

- `LocalMemoryIndexService.render_prompt_hits()`

当前行为：

1. 以当前 `source_prompt` 为 query_text
2. 最多取 `limit=4`
3. 字数有 `max_chars` 限制
4. 会按 `memory_types` 收窄

结果是：

1. local memory 已经存在，不代表本轮一定会被看见
2. 只有 query 命中，才进入 `【长期记忆命中】`
3. Talk 真正稳定显式注入的，不是整个 local memory，而是：
   - `Current_User_Profile.private.md` 的 excerpt
   - query 命中的少量 local memory hits

---

## 9. 为什么“用户长期偏好”没有稳定变成强约束

这正是当前机制的关键缺口。

### 9.1 现状

现在 recent -> local 的自动沉淀，会把 long_term_candidate 统一交给 `_upsert_local_memory(...)`。

它会判断：

1. 写哪份 L1/L2 文件更合适
2. 是否和已有记忆相似
3. 是否需要追加、跳过、建新文件

但它 **不会自动判断**：

1. 这条应该进入 `Current_User_Profile.private.md`
2. 这条只是 `对话长期约束.md`
3. 这条是工作流经验、技术备忘，还是当前用户专属偏好

所以结果是：

1. “分享小红书/知乎/科研技术贴就默认抓取+读图+进 BrainStorm”
2. 很可能被沉淀进普通 local memory
3. 但不会自动升级成 `Current_User_Profile.private.md` 的稳定用户偏好

### 9.2 后果

这会导致三层约束力差异：

1. **强约束层**：`Current_User_Profile.private.md`
   - Talk 几乎每轮都能显式看到 excerpt
2. **中约束层**：`recent_memory`
   - 近几轮能看到，但会滚动、会压缩
3. **弱约束层**：普通 local memory
   - 只有 query 命中时才进入 `【长期记忆命中】`

所以很多本该是“当前用户长期偏好”的东西，现在只是“普通长期记忆”。

---

## 10. 当前机制对“小红书/知乎分享工作流”为什么不够稳

这不是 single point failure，而是两层叠加。

### 10.1 第一层：偏好没被自动路由到用户画像

如上所述，recent -> local 机制并不会自动把这类条目写进 `Current_User_Profile.private.md`。

所以它缺少最稳定的显式注入入口。

### 10.2 第二层：content_share 仍会削弱执行层能力曝光

Talk 入口当前还有两个硬限制：

- `butler_bot.py:616`
- `butler_bot.py:617`

即：

1. `recent_mode == "content_share"` 时，`skills_prompt` 被清空
2. `recent_mode == "content_share"` 时，`agent_capabilities_prompt` 被清空

于是当前真实效果是：

1. recent 里可能已经写着“应该走 web-note-capture-cn / web-image-ocr-cn / BrainStorm”
2. 但一旦命中 `content_share`
3. 当轮 prompt 可能看不到技能目录本身
4. 模型就更容易回成“理解/总结/承诺”，而不是立刻执行抓取链路

---

## 11. 当前结论

### 11.1 recent -> local 现状判断

当前 Butler 已经具备：

1. 每轮 recent 提炼
2. 每轮 direct promote
3. 每轮 recent sweep promote
4. 维护期再 sweep promote
5. local memory index / relations / journal / L1 / L2 的完整落盘链路

所以从“有没有 recent -> local 机制”来看，答案是：**有，而且并不弱。**

### 11.2 真正的短板

当前短板不是“没有沉淀”，而是：

1. 没有把 long_term_candidate 自动分类为“用户画像偏好 / 对话长期约束 / 技术记忆 / 工作流规则”
2. 没有一条 recent -> `Current_User_Profile.private.md` 的专门写入口
3. Talk 对普通 local memory 是命中式读取，不保证每轮都看到
4. `content_share` 仍会削弱技能与能力目录的显式注入

### 11.3 对 0317 现状的最终描述

可以把当前机制概括为：

- `recent -> local` 的“沉淀”已经形成闭环
- 但 `local -> 强用户偏好约束` 这一步还没有专门机制
- 所以很多本该成为“当前用户稳定偏好”的规则，仍停留在“普通长期记忆”层，而不是“强约束用户画像”层

---

## 12. 后续最自然的升级方向

如果后面要补机制，优先级建议是：

1. 为 long_term_candidate 增加分类：
   - `user_profile`
   - `dialogue_rule`
   - `task_rule`
   - `reference`
2. 为 `user_profile` 类新增专门写入口：
   - 自动 upsert 到 `Current_User_Profile.private.md`
3. 再处理 `content_share` 对 skills/capabilities 的硬清空

这样可以最小改动地把“普通记忆”提升成“真正有约束力的当前用户偏好”。

---

## 13. 2026-03-17 晚间更新：memory pipeline 模块化后的现状

这轮不是推倒重写 `memory_manager.py`，而是在保留旧写入原语的前提下，把 memory agent 体系显式抽成独立模块：

- `butler_main/butler_bot_code/butler_bot/memory_pipeline/`
- `agents/`
- `adapters/`
- `prompts/`
- `orchestrator.py`

### 13.1 当前真实架构

当前 `recent -> local/profile` 已不再只有一条“写死在 memory_manager 里的隐式逻辑”，而是变成四层：

1. 主 agent
   - 继续负责正常对话与任务执行
   - 可产出 `candidate_memory`
   - 可通过窄权限入口直写 `user_profile`
2. `post_turn_memory_agent`
   - 负责 recent -> local memory 主治理
   - 读取 candidate / recent / local / profile
   - 决定 add / update / merge / ignore / dedupe
3. `compact_memory_agent`
   - 负责 recent 超阈值前的 compact
   - 只输出 `SummaryBlock` 与受限 `summary_candidates`
   - 默认不能直接改 `user_profile`
4. `maintenance_memory_agent`
   - 负责周期性治理
   - 独立于主对话链路运行

### 13.2 `memory_manager.py` 现在扮演什么角色

`memory_manager.py` 现在仍然是运行中的总入口，但它在这条链上的角色已经收窄为：

1. 构造 recent entry
2. 选择是否启用 pipeline flag
3. 调用 `MemoryPipelineOrchestrator`
4. 在 flag off 时回退旧逻辑
5. 继续复用旧原语：
   - `_upsert_local_memory()`
   - local index
   - relations
   - write journal

也就是说：

- **agent 决策被显式保留了**
- **旧写入底座没有被破坏**
- **orchestrator 没有重新吞掉 agent 职责**

### 13.3 为什么这次模块化重要

0317 白天文档里的核心问题是：

1. recent -> local 有沉淀闭环
2. 但谁在治理、谁能写 profile、谁能做 compact，边界不够显式

晚间这轮改造之后，这几个边界已经被代码结构明确表达：

1. `post_turn_memory_agent` 才是 recent -> long-term 主治理 agent
2. `compact_memory_agent` 只能受限写 `project_state/reference/archive`
3. `user_profile` 通过独立 `profile_writer.py` 处理
4. `maintenance_memory_agent` 独立运行，不依赖主对话链路

### 13.4 0317 结束时仍然存在的短板

虽然 memory pipeline 已经模块化，但 0317 结束时仍有几个现实问题没有完全解决：

1. `memory_manager.py` 本身仍然过重
2. `HeartbeatOrchestrator` 仍然较大，heartbeat manager/planner/executor 边界还不够薄
3. profile 写入目前已经独立，但规则仍然偏保守，主要由 `relation_signal.preference_shift` 驱动
4. pipeline 现在是“已接线、可开关、可回滚”，还不是完全接管所有旧治理逻辑

### 13.5 对 0317 最终现状的修正描述

因此，0317 的最终状态不应再描述为“recent -> local 是一组散落在 memory_manager 里的提升逻辑”，而应描述为：

- old memory primitives 仍在 `memory_manager.py`
- new memory governance 已显式抽成 `memory_pipeline/`
- 当前处于“旧底座 + 新 agent 编排接管”的过渡阶段
- `flag off` 时旧行为尽量保持一致
