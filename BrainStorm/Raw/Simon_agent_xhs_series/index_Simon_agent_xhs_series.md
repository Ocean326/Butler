## Simon 小红书 Agent 系列 · 轻量索引

- **用途**：为 `Simon_agent_xhs_series/` 以及 2026-03-16～17 已抓取的 Simon Agent 相关 Raw 提供一个最小索引视图，方便后续归位与结构化，不改动任何原文。
- **覆盖范围**：当前仅盘点已明显与「Agent 架构 / Multi-Agent / Harness / 自律系统」相关、且在仓库中已能直接看到的 8 篇代表性条目与 2 篇 BrainStorm 结构化稿；按文件名与内容实查，**当前真正在库的时间覆盖为 2026-03-16～17**。
- **时间空缺提示**：`README.md` 中约定本系列阶段性目标是「从 2025-07 起 follow Simon 与 Agent 相关帖子」，但在当前仓库中 **尚未发现 2025-07～2026-03-15 的对应 Raw 文件**，本区间暂记为「待补抓取区间」，仅在本索引中标记，不在本轮补抓。

---

## 一、目录现状（本轮盘点）

- **Raw 入口目录**：`BrainStorm/Raw/Simon_agent_xhs_series/`
  - 已存在：
    - `README.md`：给出命名规范、抓取与维护原则。
    - `Simon_agent_xhs_progress.md`：对 2026-03-16～17 期间的抓取与整理节奏做了盘点与后续建议。
    - `20260317_xiaohongshu_agent_architecture_principles_brainstorm.md`：围绕「Agent 架构设计原则」的结构化脑暴稿。
    - `20260317_xiaohongshu_multi_agent_harness_engineering_brainstorm.md`：围绕「Multi-Agent Harness Engineering（下）」的结构化脑暴稿。
- **相关 Raw 仍在上层目录**：`BrainStorm/Raw/` 根下已存在多篇时间戳型 Raw（本索引中暂以「相对路径」方式挂接，不做物理移动）。

> 本索引文件只做「可见化 + 轻量标签」，不承担迁移与改写；后续若有更系统的归档方案，可以基于本表继续扩展或拆分。

---

## 二、条目索引（首批 10 条）

### 1. 本目录下的结构化脑暴 / 进度稿

| 文件 | 类型 | 是否含 OCR | 初步主题标签 | 备注 |
| --- | --- | --- | --- | --- |
| `Simon_agent_xhs_progress.md` | 进度盘点 / 计划 | 不适用 | 进度追踪, 目录归位计划, OCR 对齐 | 概览 2026-03-16～17 Simon Agent 相关 Raw 的分布、状态与下一步建议。 |
| `20260317_xiaohongshu_agent_architecture_principles_brainstorm.md` | BrainStorm 结构化稿 | 文本层为主，未显式依赖图片 OCR | 架构设计原则, 单 Agent → 多轮迭代, 工具原子化 | 源自 `http://xhslink.com/o/29JtlVMX2jI`，当前版本正文来自网页文本层，适合作为「Agent 架构设计原则」的结构化入口。 |
| `20260317_xiaohongshu_multi_agent_harness_engineering_brainstorm.md` | BrainStorm 结构化稿 | 正文可读，配图仍依赖 App/后续 OCR | Multi-Agent, Harness Engineering, 四层架构 | 对应 `http://xhslink.com/o/6pReIIUZecl`，结合知乎长文，对 MAS Harness 四层架构与治理思路做了提炼。 |

### 2. `BrainStorm/Raw/` 根目录下的代表性 Raw 条目

> 以下文件目前物理位置在 `BrainStorm/Raw/` 根层，本索引仅以相对路径挂接，后续是否物理迁移动议可在 Heartbeat / 架构层另行决策。

| 文件（相对路径） | 是否含 OCR（当前可见状态） | 初步主题标签 | 备注 |
| --- | --- | --- | --- |
| `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_agent_architecture_principles.md` | 正文文本已抓取，配图 OCR 状态待统一 | Agent 架构原则, 多轮迭代, 工具设计 | 与本目录下的 `..._architecture_principles_brainstorm.md` 一一对应，是真源级 Raw。 |
| `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_multi_agent_harness_engineering.md` | 正文已抓取，部分配图需后续 OCR / 读图补完 | Multi-Agent, Harness, 系统演化 | 与 `..._multi_agent_harness_engineering_brainstorm.md` 对应，讨论 MAS Harness 的整体框架。 |
| `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_10_agent_projects.md` | 文本为主，配图 OCR 状态不明 | Agent 实践案例, 项目共性, 设计模式 | 汇总 10 个 Agent 项目，适合作为「实际落地案例」素材池。 |
| `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_agent_harness_quanshiwang_diaoyan.md` | 已有读图 / 调研稿，细粒度 OCR 待对齐 | Harness 调研, 多平台对比, 系统视角 | 面向「全视网」式 Harness 调研，适合作为后续架构对标的基准文档之一。 |
| `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_context_management_six_vendors.md` | 正文已抓取，图片 OCR 状态待查 | 上下文管理, 厂商对比, 记忆机制 | 聚焦不同厂商的上下文管理方案，直接服务 Butler 记忆 / context 设计。 |
| `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_subagent_vs_agentteam.md` | 文本为主，配图 OCR 状态不明 | 多智能体架构, 组织形态, 角色划分 | 讨论 SubAgent 与 AgentTeam 的边界与协作方式。 |
| `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_agent_best_architecture_is_loop.md` | 正文可读，配图 OCR 待补 | 自律系统, 循环架构, 反馈回路 | 围绕「最好的 Agent 架构是一条循环」展开，直接指向 Heartbeat / 自律系统设计。 |
| `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_claude_code_self_discipline.md` | 文本已抓取，图片 OCR 状态不明 | 自律系统, 工程实践, 代码约束 | 结合 Claude Code 体验，讨论「自律」与工具/流程的关系，可为 Butler 工程实践提供参考。 |

> 近期新增但尚未完全对齐 OCR / 结构化状态的 Raw：
>
> - `BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_sdd_vibe_coding_refactor.md`：以「基于 SDD 的 Vibe Coding 代码重构实践」为主题，当前仅抓到标题与简介，推断正文主要在配图中；图片 OCR 未完成、尚未挂接独立 BrainStorm 稿，后续心跳可按 README 中的状态字段规范补齐「是否完成图片 OCR / 是否已派生 Working 结构化稿」标注。

---

## 三、对 Butler MAS / Harness 设计最关键条目的结构化要点

> 本节选取 2 篇与 Butler 多 Agent / Harness 工程最强相关的条目，给出「核心观点 → 对 Butler 架构的启发 → 一句话可执行建议」，方便后续在 Heartbeat 或架构设计中快速引用。

- **`BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_multi_agent_harness_engineering.md`（及其 BrainStorm 稿）**
  - 核心观点：从单 Agent 走向 MAS 时，需要一套「知识层 → 编排层 → 风险门控层 → 治理层」的四层 Harness 架构，把知识、任务编排、安全门控与治理经验拆层管理，而不是只堆更多 Agent。  
  - 对 Butler 的启发：可以把现有 `docs` / `BrainStorm` / long-term memory 视作知识层，把 heartbeat 与 skills pipeline 视作编排层，将 `task_ledger`、工具白名单、预算与限流上收为统一的 Guard 层，并在日志与失败复盘上形成治理层经验飞轮。  
  - 一句话可执行建议：**在下一轮 Butler 架构图与文档中，显式按「四层 Harness」重新标注现有组件，并为至少一条关键工具链补一小节「风险门控条件」。**

- **`BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_agent_harness_quanshiwang_diaoyan.md`**
  - 核心观点：从全网 Agent Harness 实践中抽取共性——高质量 Harness 依赖于统一的运行环境、对日志与死循环的长期观察、对工具空间的精心设计，以及把安全 / 预算 / 权限与评估做成一等公民。  
  - 对 Butler 的启发：当前 `task_ledger`、工具白名单、限流与日志观测可以被视作「Butler Harness」的雏形，需要在少量关键场景上打通从日志 → 策略调优的闭环，而不是散落在各个脚本中。  
  - 一句话可执行建议：**选 1–2 个核心任务场景，把相关任务日志、失败模式与策略调整记录进统一的「Harness 视角」小节，用于后续治理与架构演进。**

---

## 四、2025-07 起「follow」任务当前进度（心跳视角）

- **阶段性目标回顾**：`README.md` 中约定，本系列的阶段性目标是「从 2025-07 起，按时间顺序 follow Simon 在小红书上与 Agent 相关的帖子」，并将其 Raw 母本集中落盘到本目录或相邻位置，配合 BrainStorm / Butler 架构演进使用。
- **当前实际覆盖区间**：按本轮仓库实查（见上表与 `Simon_agent_xhs_progress.md`），**Simon_agent_xhs_series/ 目录内 noteId 级母本**与 `index.md` §二一致：最早为 **`2025-07-16`**（`687726400000000010012960`），另有 **`2026-03-15`** Harness(下)（`69b62fb000000000210383a0`）；`BrainStorm/Raw/` 根层仍集中有一批 **`20260317_xiaohongshu_*.md`** 等时间戳稿，与上两者并存。
- **2025-07～2026-03-15 覆盖情况**：**非全空**：`2025-07-16` 已 capture（见主索引 §二 #1）；**`2025-07-17`～`2026-03-14`** 仍无第二篇已落盘 Simon Agent 母本，与 §3.1 *估计日期* 及 `blocked_external` 队列一致，仅在此处标为「待补区间」，不在本轮补抓。
- **心跳任务对齐**：结合 `Simon_agent_xhs_progress.md` 与 `self_mind/current_context.md` 中对 Simon 线的描述，**本轮心跳已完成的主要是「2026-03-16～17 首批样本的盘点 + 结构化落地」**，尚未启动对 2025-07 起完整时间轴的系统补抓；后续心跳可以本索引为「真源入口」，继续向前（2025-07 起）与向后滚动覆盖。

> 简短结论：  
> - 「从 2025-07 起 follow」这一长期目标目前处于「已设定目标 → 已完成 2026-03-16～17 首批样本 → 2025-07～2026-03-15 仍为待补区间」阶段，本索引可作为后续心跳检查覆盖进度的单一真源视图。

---

## 五、作为脚本 / skill 的可扩展入口（命名与字段约定）

本索引文件同时承担「给人看的说明」和「将来本地脚本 / skill 可继续填充的入口」双重角色。为避免后续出现多套影子索引，建议统一遵循以下约定：

### 1. 约定的索引文件与命名

- **面向人类快速浏览的索引**：  
  - `BrainStorm/Raw/Simon_agent_xhs_series/index.md`（轻量表格视图，当前已存在）  
  - `BrainStorm/Raw/Simon_agent_xhs_series/index_Simon_agent_xhs_series.md`（本文件，含说明与策略）
- **面向脚本 / skill 的主索引入口**（建议约定，不要求本轮立即创建或填充）：  
  - 推荐统一使用：`BrainStorm/Raw/Simon_agent_xhs_series/Simon_agent_xhs_series_index.jsonl`  
  - 每行一条 JSON 记录，代表一篇 Simon Agent 相关笔记（无论 Raw 位于本目录还是 `BrainStorm/Raw/` 根层）。

> 若未来希望继续使用 Markdown 而非 JSONL，也可以保持当前表格结构，并通过脚本解析本文件的「条目索引」表格；但**单一机器可读真源仍建议落在 `..._index.jsonl` 上**。

### 2. 建议的字段结构（供将来脚本/skill 参考）

后续本地脚本 / skill 如需自动补全或更新索引，建议使用如下最小字段集合（示例为 JSON Schema 风格描述）：

```json
{
  "date": "2025-07-15",
  "xhs_note_id": "69b62fb000000000210383a0",
  "title": "multi-agent harness engineering（下）",
  "series": "simon_agent_xhs",
  "theme_tags": ["multi-agent", "harness", "自律系统"],
  "raw_path": "BrainStorm/Raw/daily/20260317/20260317_xiaohongshu_multi_agent_harness_engineering.md",
  "brainstorm_path": "BrainStorm/Raw/Simon_agent_xhs_series/20260317_xiaohongshu_multi_agent_harness_engineering_brainstorm.md",
  "ocr_assets": [
    "BrainStorm/Raw/xiaohongshu_69b62fb000000000210383a0_ocr.md",
    "BrainStorm/Raw/xiaohongshu_69b62fb000000000210383a0_ocr.json"
  ],
  "has_ocr": true,
  "has_brainstorm": true,
  "follow_status": "done",
  "source_platform": "xiaohongshu",
  "capture_method": "web-note-capture-cn+web-image-ocr-cn",
  "last_update": "2026-03-18T10:00:00+08:00"
}
```

推荐的最小必填字段（脚本若缺失可用 `null` / 空数组占位）：

- `date`：笔记发布日期（YYYY-MM-DD 或 YYYYMMDD）。
- `xhs_note_id`：小红书 noteId；若未知，可暂置 `null`。
- `title`：便于人类识别的标题或简短说明。
- `raw_path`：仓库内 Raw 母本相对路径（真源入口）。
- `has_ocr` / `has_brainstorm` / `follow_status`：与 `README.md` 中的状态字段保持一致，用于表达是否完成 OCR、是否已有 Working / BrainStorm 结构化稿，以及当前 follow 进度。

### 3. 建议的后续脚本行为（非本轮任务，仅作约定）

- **抓取 /同步脚本**：  
  - 在新增一篇 Simon Agent 笔记 Raw 时，脚本可按约定自动向 `Simon_agent_xhs_series_index.jsonl` 追加一条记录，填入已知字段（如 `date`、`raw_path`、`source_platform` 等），其余字段以 `null` 或默认值占位。
- **状态更新脚本**：  
  - OCR 完成或新增 BrainStorm / Working 结构化稿时，脚本只需根据 `raw_path` 或 `xhs_note_id` 定位对应记录，更新 `has_ocr`、`has_brainstorm` 与 `follow_status` 字段，无需重写整行内容。
- **心跳检查脚本**：  
  - 心跳任务可周期性读取该 JSONL 文件，根据 `date` 与 `follow_status` 推算「从 2025-07 起目前已覆盖到哪一月 / 哪几篇」，并回写简要统计到本文件或 `Simon_agent_xhs_progress.md` 中，保持「人类可读进度视图」与「脚本可读真源」的统一。

---

## 六、后续迭代建议（占位，非本轮任务）

- **状态字段补全**：后续心跳可参考 `Simon_agent_xhs_progress.md` 中的建议，为上表中 3–5 篇代表性 Raw 补充统一的「是否完成图片 OCR / 是否已有 Working 结构化稿」状态区块，并在将来落地的 `Simon_agent_xhs_series_index.jsonl` 中同步反映。
- **Working 结构化模板挂接**：在 BrainStorm/Working 中设计统一模板，并从上表中选取 2–3 篇优先落盘为结构化稿，与本索引和未来的 JSONL 索引做双向链接。
- **时间轴补完策略**：后续若继续 follow 2025-07 之后的 Simon 小红书 Agent 系列，可按「优先补 2025-07～2026-03-15 待补抓取区间」的顺序推进，并在新增 Raw 落盘与 JSONL 更新时，同时更新本索引的时间覆盖说明与心跳任务看板。

---

