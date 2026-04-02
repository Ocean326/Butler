# 0318 prompt 现状

> 更新时间：2026-03-18
>
> 这份文档只回答四个问题：
> 1. 现在 talk prompt 和 heartbeat prompt 分别从哪里注入；
> 2. `recent_memory` / `heart_beat_memory` 当前真实数据量有多大；
> 3. 当前到底有多少是原文注入，多少是 summary 注入；
> 4. 现阶段最值得警惕的 prompt 风险是什么。

## 1. 当前 prompt 注入入口

### 1.1 talk prompt

对话侧 prompt 当前由 `MemoryManager.prepare_user_prompt_with_recent()` 组装。

代码位置：

- `butler_main/butler_bot_code/butler_bot/memory_manager.py:512-568`

当前注入块有四类：

1. `recent_memory` 窗口摘要
2. `recent_summary` 窗口外摘要池
3. `recent_summary_archive` 阶梯摘要
4. `最近显式要求与未完约束`

其中真正的近期主块来自 `_render_recent_context()`，它只消费每条 recent entry 的 `timestamp/topic/summary/status/memory_stream`，不会把整条 JSON 原样灌进 prompt。

代码位置：

- `butler_main/butler_bot_code/butler_bot/memory_manager.py:6389-6419`

“最近显式要求与未完约束”则主要取自 `raw_user_prompt` 和 `next_actions`。

代码位置：

- `butler_main/butler_bot_code/butler_bot/memory_manager.py:2182-2205`

### 1.2 heartbeat prompt

heartbeat planner 当前不是直接读取 `heart_beat_memory.json` 作为主要 prompt 输入。

实际规划上下文来自：

1. `heartbeat_tasks.md`
2. `统一 recent` 文本
3. `local_memory` 命中片段
4. 运行时上下文

代码位置：

- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py:223-257`
- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py:1043-1071`

统一 recent 文本由 `_render_unified_heartbeat_recent_context()` 生成，本质上是：

1. talk recent 摘要窗口
2. beat recent 摘要窗口

代码位置：

- `butler_main/butler_bot_code/butler_bot/memory_manager.py:5786-5796`

## 2. 当前真实存储现状

截至本次检查，`recent_memory` 目录主要文件规模如下：

- `recent_memory.json`：100 条，约 234 KB
- `beat_recent/recent_memory.json`：40 条，约 132 KB
- `heart_beat_memory.json`：511 个 task，约 493 KB
- `recent_archive.md`：约 817 KB
- `beat_recent/recent_archive.md`：约 537 KB

其中 `heart_beat_memory.json` 当前结构为：

- 顶层键：`version / updated_at / tasks / notes / last_heartbeat_sent_at`
- `tasks` 数量：511
- `notes` 数量：0

task 状态统计：

- `done`：262
- `pending`：227
- `in_progress`：9
- `deferred`：8
- `waiting_input`：5

这说明 `heart_beat_memory.json` 目前已经明显偏向“兼容视图堆积池”，而不是轻量的 prompt 工作窗口。

## 3. recent entry 字段现状

### 3.1 talk recent

`recent_memory.json` 当前每条 entry 几乎都带完整 schema，最近文件中常见字段包括：

- `memory_id`
- `timestamp`
- `topic`
- `summary`
- `scene_mode`
- `memory_scope`
- `memory_stream`
- `event_type`
- `raw_user_prompt`
- `status`
- `next_actions`
- `detail_points`
- `unresolved_points`
- `self_mind_cues`
- `heartbeat_tasks`
- `heartbeat_long_term_tasks`
- `long_term_candidate`
- `salience`
- `confidence`
- `derived_from`
- `context_tags`
- `mental_notes`
- `relationship_signals`
- `relation_signal`
- `active_window`
- `subconscious`

但非空分布并不均匀：

- `summary`：100/100 非空
- `raw_user_prompt`：16/100 非空
- `next_actions`：16/100 非空
- `detail_points`：16/100 非空
- `unresolved_points`：16/100 非空
- `mental_notes`：16/100 非空
- `relationship_signals`：16/100 非空
- `self_mind_cues`：16/100 非空
- `heartbeat_tasks`：13/100 非空
- `heartbeat_long_term_tasks`：14/100 非空

结论很直接：

1. schema 现在偏胖
2. 真正长期稳定发挥作用的字段，主要还是 `topic + summary`
3. 其余大量字段更多是在“存着备用”，不是持续进入 prompt 主窗口

### 3.2 beat recent

`beat_recent/recent_memory.json` 当前为 40 条。

非空分布同样显示主力字段仍是摘要：

- `summary`：40/40 非空
- `raw_user_prompt`：10/40 非空
- `heartbeat_execution_snapshot`：10/40 非空
- 其余 `detail_points / next_actions / self_mind_cues / heartbeat_tasks / heartbeat_long_term_tasks` 大多接近空

这说明 beat recent 也在沿着“统一 schema + 少数字段真正在用”的方向演化。

## 4. 当前原文注入 vs summary 注入

### 4.1 talk prompt

按当前真实文件和当前逻辑计算，对话侧最近一次典型注入可近似理解为：

- `summary 注入 = 15`
- `原文注入 = 4`

拆开看：

1. `recent_memory` 窗口摘要：15 条，全部来自 `summary`
2. `recent_summary_pool`：当前 0 条
3. `recent_summary_ladder`：当前 0 条
4. `最近显式要求与未完约束`：当前 4 条，主要来自 `raw_user_prompt`

也就是说，对话侧并不是“大量原文灌入”，而是：

- 主体是 recent summary
- 辅助夹带少量原文式要求回放

### 4.2 heartbeat prompt

按当前逻辑，heartbeat 统一 recent 上下文可近似理解为：

- talk recent summary：15 条
- beat recent summary：15 条
- 原文直注：0

所以 heartbeat recent 注入可近似记为：

- `summary 注入 = 30`
- `原文注入 = 0`

需要注意：heartbeat planner 虽然不是直接全量读 `heart_beat_memory.json`，但 `apply_plan()` 仍会加载 legacy store 做 truth bootstrap 和同步视图，因此它仍然是一个重要的历史兼容层，而不是完全无关的死文件。

代码位置：

- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py:1190-1198`

## 5. 当前最值得警惕的风险

### 5.1 schema 过胖，语义不够清爽

`recent_memory` 的 entry 现在字段很多，但 prompt 主窗口真正消费的字段很少。  
结果就是：

1. 存储层看起来信息很多
2. 注入层其实只吃其中一小部分
3. 维护者阅读 JSON 时会产生“到底哪些字段真有用”的认知负担

### 5.2 `raw_user_prompt` 会把敏感原文重新带回 prompt

当前 `最近显式要求与未完约束` 直接回放 `raw_user_prompt`。  
本次检查时，最近 4 条里已经出现带 cookie 的原文请求片段。

这类内容的问题不是“字段不好看”，而是会带来真实风险：

1. prompt 污染
2. 敏感信息回流
3. 不必要的长原文重复注入

### 5.3 `heart_beat_memory.json` done 任务堆积过多

虽然它不再是 planner 主注入源，但它仍有 262 条 done task 和 249 条未完成类 task。  
如果未来有任何逻辑误把它重新当成主要 prompt 源，或继续让它无限增长，会很容易把兼容层再次反向污染真源层。

## 6. 当前判断

截至 2026-03-18，关于“是不是注入了太多而且结构不清晰”，更准确的判断是：

1. `heart_beat_memory.json` 的存储膨胀问题是真实存在的
2. 但当前 prompt 过载主因不是它，而是 `recent_memory` 的摘要窗口和少量 `raw_user_prompt` 回放
3. 当前系统更像是“存储结构偏胖，但 prompt 主注入仍以 summary 为主”
4. 当前最先该收的不是 summary，而是 `raw_user_prompt` 的原文回放策略，以及 recent schema 的可见字段边界

## 7. 建议的下一步

若进入下一轮 prompt 治理，优先级建议如下：

1. 收缩 prompt 可见字段，只保留 `topic / summary / next_actions`
2. `raw_user_prompt` 默认不直接注入，至少先做脱敏和长度裁剪
3. `heart_beat_memory.json` 只保留活跃任务和少量最近完成项，不再长期堆积全部 done
4. 把“存储字段”和“prompt 可见字段”正式分层写清楚，避免 schema 继续自然膨胀
