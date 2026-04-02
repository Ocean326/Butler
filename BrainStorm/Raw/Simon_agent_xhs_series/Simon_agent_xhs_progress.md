## Simon 小红书 Agent 系列 · 进度与计划（盘点用）

### 一、当前现状小结

1. **目录入口已建立**：`Simon_agent_xhs_series/README.md` 已明确本系列作为 Simon 在小红书上与 Agent / 多智能体 / AI 工作流相关笔记的 Raw 母本入口，并约定了命名规范与状态标注字段。
2. **已抓取的 Simon 相关原文**：在 `BrainStorm/Raw/` 下，已存在至少 10 篇 2026-03-16～17 的 Simon 小红书 Agent 向 Raw 文本（如 `20260317_xiaohongshu_agent_architecture_principles.md`、`..._multi_agent_harness_engineering.md`、`..._10_agent_projects.md` 等），以及 1 篇以读图方式补完内容的 Harness 调研汇总稿 `20260317_xiaohongshu_agent_harness_quanshiwang_diaoyan.md`。
3. **图片与 OCR 状态**：与 Simon 小红书相关的 noteId 级别 Raw（`xiaohongshu_<id>_ocr.md/.json` 系列）目前约有 10+ 个文件，说明已有一批笔记完成了首轮配图下载与 OCR 或人工读图，但多数 Raw 顶部尚未统一补写 README 中约定的「是否完成图片 OCR / 是否已派生结构化文档」等状态字段。
4. **评论区与结构化对齐缺口**：以 `20260317_xiaohongshu_agent_architecture_principles.md` 为代表，目前大部分 Raw 仅包含正文一手真源，对评论区有明确「尚未抓取」说明；与 Butler / Agent 架构的对齐提示、结构化拆解和 Working 层衔接，多数仍处于待补状态。
5. **目录归位程度**：Simon 相关 Raw 现阶段主要仍散落在 `BrainStorm/Raw/` 根层，`Simon_agent_xhs_series/` 目录本身只有 README 说明，尚未真正成为「已经归档就位的 Simon Agent 系列母本汇聚点」。

### 二、未来 1–2 轮心跳内的最小整理步骤（建议）

1. **最小归位动作（不改正文）**  
   - 目标：在不新建大量 Raw 文件的前提下，让现有 Simon 相关笔记至少「被目录看见」。  
   - 动作建议：在下一轮心跳中，为上述 10 篇 20260316–17 的 Simon Agent Raw 各自补充或校对顶部元信息中的作者/平台/时间字段，并在 `Simon_agent_xhs_series/README.md` 中增加一个「已归位/待归位清单」小节，用列表方式挂接这些现有文件路径（可视作轻量索引，而非物理迁移）。

2. **状态标注打底（聚焦 3–5 篇代表性 Raw）**  
   - 目标：先让一小批核心笔记达到 README 中定义的「状态字段完整」基线，作为后续批量化整理的模板。  
   - 动作建议：优先选取 3–5 篇与 Butler 多 Agent 架构高度相关的笔记（如 Harness 调研、multi-agent harness engineering、架构设计原则、10 个 Agent 项目共性），在各自文件顶部补充统一格式的状态区块：是否完成图片 OCR、是否已有 Working 结构化稿、评论区抓取情况，并用「占位注释」方式标出后续结构化入口（不实质拆解正文）。

3. **Working 结构化切入口设计（计划层，不在本轮落盘）**  
   - 目标：为后续心跳设计一个可复用的「单篇 Simon Agent 笔记 → Working 结构化稿」模板，避免每次从零临时想。  
   - 动作建议：在 BrainStorm/Working 层预留一个统一模板的规划（如「标题 + 背景 + 关键观点拆解 + 对 Butler 架构的映射 + 后续问题」五段式），并优先指定 3 篇代表性 Raw 作为首批结构化候选；本轮仅在本进度文件中记录这一计划，实际新建 Working 文件留给后续心跳执行。

4. **OCR 资产与 noteId 的轻量对齐**  
   - 目标：让现有 `xiaohongshu_<id>_ocr.*` 与时间戳型 Raw 之间建立最小「能互相找到」的对应关系，便于后续查漏补缺。  
   - 动作建议：在后续一轮心跳中，以清单形式列出当前 10+ 个 `xiaohongshu_<id>_ocr.*` 文件，并在对应的时间戳型 Raw（若已确认属于同一笔记）顶部补一行「关联 OCR 资产：<id>」的引用行即可，无需当场搬运或合并内容。

---

### 三、本轮心跳实际进展（对齐任务 `b6c3a9c1-1f8b-4a3a-9b0c-2f7e9d4e5a21`）

- **2026-03-20（第十轮 · heartbeat-executor · 索引格）**：本机只读复核 `index.md`/§九；**新增 §9.0** 钉死 **`202507` 锚点日 `2025-07-16`**（`687726…`）与 **`2025-07-17`～`2026-03-14` 空白区间**；并修正 `index_Simon_agent_xhs_series.md` §四 与主索引矛盾的「2025-07～2026-03-15 全无母本」口径。**未**新跑 `social_capture`、**未**新增 capture 文件；阻塞类仍为缺 `xhslink`/explore 无 `note_id` + Harness(下) OCR **9/18**。
- **2026-03-20（第九轮 · heartbeat-executor）**：已读 `web-note-capture-cn/SKILL.md`。Simon 系列下一篇「可推进抓取」顺位取 §3.1 **#3**「Harness Engineering(中-1)」（#1/#12 等已前置阻塞）；执行 `social_capture.py` **1 次** explore 全标题关键词 URL，回报 **无 `note_id`**；落盘 `20260320_xhs_simon_harness_engineering_mid1_explore_blocked.md`，`index.md` 同步 §头注/§3.1 #3/变更记录/§四/§九/§十（**`SIMON-Q6`**）/§10.1。**未**生成新 `xiaohongshu_*.json`。**未**调用 `web-image-ocr-cn`。未改 `butler_bot_code`。
- **2026-03-20（第八轮 · heartbeat-executor）**：已读 `web-note-capture-cn/SKILL.md`。沿 2025-07 时间轴在 §九 两条 `blocked_external` 之后顺延至 §3.1 #12「skill通过渐进式披露…」；执行 `social_capture.py` 两路 explore 关键词复试，均报 **无 `note_id`**；落盘 `20260320_xhs_simon_skill_progressive_disclosure_blocked.md`，更新 `index.md` §头注/§3.1/§3.1 变更记录/§九/§十（**`SIMON-Q4`**）。**未**调用 `web-image-ocr-cn`（无 capture JSON）。未改 `butler_bot_code`。
- **2026-03-20 续跑（第七轮）**：已读 `web-note-capture-cn/SKILL.md`；§3.1 时间序 #1「Magentic-One…」仍 **无 xhslink**，**未**执行 `social_capture.py`。补 **Harness(下)** 配图 OCR **7/18 → 8/18**（Image 8：经验沉淀飞轮；`heartbeat_executor_vision` → `xiaohongshu_69b62fb000000000210383a0_ocr.{json,md}`）。`index.md` 更新 §头注/§二/§四/§七/§九/§十，并新增 **§10.1** 下一篇单帖 URL 占位队列（1 条）。未调用 `web-image-ocr-cn`（避免无后端整文件覆盖）。
- **2026-03-20 续跑（第六轮）**：索引侧下一篇可抓 Agent 帖仍 **缺 `xhslink.com/o/...`**（两条 `blocked_external` 不变），**未**重跑 `social_capture.py`。改补 **Harness(下)** 配图 OCR **6/18 → 7/18**（Image 7：文首三条「问题—对策」+ 观测体系与全链路 Trace；`heartbeat_executor_vision` 写入 `xiaohongshu_69b62fb000000000210383a0_ocr.{json,md}`）。`index.md` §二/§四/§七/§九/§十 与 `SIMON-Q1` 已同步。未调用 `web-image-ocr-cn`（避免无后端整文件覆盖）。
- **2026-03-20 续跑（第五轮）**：主线改为「2025-07 起下一篇待抓 Agent 帖」。在 `agent测评基准整理`（已 `blocked_external`）之后，登记 **`agent 2026年的几个技术发展趋势`**；按 `web-note-capture-cn` 运行 `social_capture.py` 复试 **主页短链**与**关键词 explore**，均报 `没有定位到 note_id`；落盘 `20260320_xhs_simon_agent_2026_trends_blocked.md`，并更新 `index.md` §3.1/§四/§九/§十（新增 `SIMON-Q3`）。本机曾因缺 `requests` 临时 `pip install`（用户级 Python，未改 `butler_bot_code`）。**未**调用 `web-image-ocr-cn`（无新 capture JSON）。
- **2026-03-20 续跑（第四轮）**：同帖 OCR **5/18 → 6/18**（Image 6：自动评估续句 + 模型辅助/人工评估 + MAS 失败根因路由表）。误跑 `web-image-ocr-cn`/`image_ocr.py` 在无 OpenAI/Paddle 时整文件覆盖 `*_ocr.*`，已用脚本合并恢复 Image 1–5 历史转写后再落盘 Image 6。索引见 `index.md` §二/§四/§七/§九/§十。
- **2026-03-20 续跑（第三轮）**：同帖 OCR **4/18 → 5/18**（Image 5：日志 vs 提纯协作案例、治理层持续「日志→资产」、「三层评估」与自动评估维度开篇；末行英文在配图处截断）。已写入 `xiaohongshu_69b62fb000000000210383a0_ocr.{json,md}` 并同步 `index.md` §二/§四/§七/§九/§十。未重跑 `social_capture.py` / `image_ocr.py`（无新链接抓取需求；本机仍无 OCR 自动化后端，延续 executor 读图转写）。
- **2026-03-20 续跑（第二轮）**：`xiaohongshu_69b62fb000000000210383a0`（Harness Engineering 下）配图 OCR **3/18 → 4/18**（Image 4 为 executor 读图转写：协调异常检测、动态规则、治理运营层开篇；已写入 `*_ocr.json` / `*_ocr.md`）。`index.md` 与 `SIMON-Q1` 已同步。本机仍无 `OPENAI_API_KEY` / PaddleOCR；新一篇 XHS 直抓仍依赖分享短链。
- **2026-03-20 续跑（第一轮）**：同帖 OCR **1/18 → 3/18**（Image 2、3 读图转写）。时间轴上下一篇「未抓取」Agent 帖仍缺 `xhslink.com/o/...`（见 `index.md` §3.1）。
- 已在 `Simon_agent_xhs_series/` 目录内，对以下两篇 Simon Agent 相关笔记补齐结构化 BrainStorm 小节（「核心观点 / 对 Butler 架构与心跳 / 潜在实验想法」三块），作为 Raw → BrainStorm 的首批落地样本：  
  - `20260317_xiaohongshu_agent_architecture_principles_brainstorm.md`  
  - `20260317_xiaohongshu_multi_agent_harness_engineering_brainstorm.md`  
- 本轮未新增或迁移动任何 Raw，只在现有结构化稿上补充了对 Butler 的映射与实验想法，便于后续继续沿「从 2025-07 起抓取 Simon 的 Agent 相关笔记并沉淀到 BrainStorm/Raw」这一任务主线扩展到更多篇目。

> 本文件只承担「盘点 + 计划 + 轻量进展记录」角色，不对原始抓取内容做任何编辑；实际结构化提炼与大规模归档动作，仍建议按上述最小步骤在后续心跳中逐步推进。

---
### 四、本轮原则化观察：不断更新自我认知（便于迁移到 Butler）

1. **把“自我认知”当作可更新的状态而不是固定配置**：每轮迭代都应从可验证的执行证据（日志/结果/失败原因）更新自我模型，否则多轮会退化成“更长的猜测链”。
2. **区分证据、推断与策略，并为每层保留可回溯版本**：证据层（观测）不轻易被改写；推断层（理解）可以修订；策略层（下一步）需随置信度变化而调整，从而让“更新认知”变成可控的演进。
3. **将自我更新闭环接入治理节奏（heartbeat / 任务账本）**：更新不应只发生在一次对话内部，而应沉到可复用的任务状态（如 `task_ledger`）与后续决策门控中，避免认知漂移。