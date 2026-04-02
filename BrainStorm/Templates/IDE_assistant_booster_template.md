## 一句话目的

把「外部优质内容（如小红书生产力笔记）」通过 `web-note-capture-cn` / `web-image-ocr-cn` 抓进仓库，落在 `BrainStorm/Raw` 与 `BrainStorm/MEMORY.md`，再抽成「一个文件让 IDE / 助理战力翻倍」协作手册模板，形成可复用流水线。

---

## 标准 4 步流程（web-note-capture-cn → web-image-ocr-cn → BrainStorm → 协作手册）

### 步骤 1：用 `web-note-capture-cn` 抓取文本 + 图片信息

- **输入**：外部链接（本轮优先小红书生产力类笔记，如 Claude Code / 一人公司 / Agent 工程化等）。
- **动作**：
  - 调用 `web-note-capture-cn`，将笔记正文、元信息（作者、时间、互动量等）和图片链接抓取到本地；
  - 产出形态优先为 `BrainStorm/Raw/YYYYMMDD_xxx.md`，在开头明确：
    - 来源平台 / 作者 / 时间；
    - 原始链接；
    - 抓取方式（例：`web-note-capture-cn skill，2026-03-16`）。
- **输出**：一份结构化 Markdown Raw 文件 + 若干图片 URL 说明，可选指向 `工作区/temp/` 下的更多图片信息。

### 步骤 2：如有关键信息在图片中，用 `web-image-ocr-cn` 做补充

- **触发条件**：
  - Raw 文件中标记「首图/结构图/关键示意图」但正文未完全覆盖其信息；
  - 需要复用图片中的结构或流程（例如 Agent 调度日志截图、架构图等）。
- **动作**：
  - 将图片 URL 或本地路径交给 `web-image-ocr-cn`；
  - 产出对应的 `*_ocr.md` / `*_ocr.json`（例如本仓已有：
    - `BrainStorm/Raw/xiaohongshu_69b4eaf4000000002102f8ec_ocr.md`
    - `BrainStorm/Raw/web_image_ocr.md` / `web_image_ocr.json`）。
- **输出**：
  - 在 Raw 文件或单独 OCR 文件中，补上一小节「首图内容（OCR 补跑）」一类说明，保证未来只看文字就能大致还原图中的结构。

> TODO（技能层改进建议）：`web-image-ocr-cn` 在调用前应检测当前环境是否具备 OCR 能力（如 PaddleOCR / 调用的远程 API），若不满足则：
> - 在日志和文档中显式写明「当前环境未配置 OCR，只保留图片链接」；
> - 将失败原因与图片路径记录到统一的错误日志（例如 `BrainStorm/STATE.md` 或单独的 `ocr_error_log.jsonl`），便于后续补跑。

### 步骤 3：写入 `BrainStorm/Raw` + 在 `BrainStorm/MEMORY.md` 中挂一条索引

- **Raw 层**：
  - 按日期与主题命名 Raw 文件，例如：
    - `BrainStorm/Raw/daily/20260316/20260316_claude_code_agent_xhs.md`
    - `BrainStorm/Raw/daily/20260316/20260316_agent_subordinates_killing_xhs.md`
  - 在文末可加「Butler 视角下的要点 / 启发」一节，为后续总结留入口。
- **MEMORY 层**：
  - 在 `BrainStorm/MEMORY.md` 里，按照日期/主题追加条目：
    - 给出关键共鸣点与核心句；
    - 标注 Raw 源文件路径；
    - 明确这条记忆会指向哪些 Butler 机制（如 `self_mind` / `task_ledger` / 协作手册等）。
  - 示例：本仓已存在的条目：
    - 「把 Claude Code 拆开看，Agent 就不神秘了」共鸣点，指向 `Raw/daily/20260316/20260316_claude_code_agent_xhs.md`，并抽出「真正分水岭不在 prompt，而在状态/上下文/任务/回滚/协作」这五问。

### 步骤 4：从 Raw + MEMORY 中选高价值条目，汇入「战力翻倍」协作手册文件

- **目标文件**：
  - 使用 `BrainStorm/Templates/ide_assistant_power_file_template.md` 作为「一个文件让 IDE / 助理战力翻倍」的结构母版；
  - 针对具体 IDE / 助理（如 Butler / Claude Code / Cursor）在工作区或项目 docs 下实例化一份具体文件：
    - 例如：`./工作区/IDE-Assistant/butler_power_file.md`（示例命名）；
    - 或项目内的 `docs/ide_assistant_guide.md`。
- **筛选原则**：
  - 优先选择能直接改变工作方式 / 协作约定的内容，而不是泛泛鸡汤；
  - 要能转写成「环境设定 / 高频工作流 / 常见坑 / 示例对话」四类信息之一。
- **落地动作**：
  - 将 MEMORY 中的共鸣点翻译成具体可执行的「协作约定」；
  - 填入 `ide_assistant_power_file_template.md` 中对应的小节，形成可读、可执行的一页纸协作说明。

---

## 最小示例：从 Claude Code 小红书笔记到 3–5 条可复用协作约定

> 原始素材：`BrainStorm/Raw/daily/20260316/20260316_claude_code_agent_xhs.md`  
> 对应记忆：`BrainStorm/MEMORY.md` 中「2026-03-16 小红书『把 Claude Code 拆开看，Agent 就不神秘了』共鸣点」

### 原文关键信息（压缩版）

- 从 `s01 → s12` 递进，每一节只加一个机制；
- 核心公式：**one tool + one loop = an agent**；
- 真正的分水岭不在 prompt，而在：
  - 状态怎么存
  - 上下文怎么控
  - 任务怎么追
  - 失败怎么回滚
  - 协作怎么对齐
- 启发：亲手撸过一套骨架，再看任何 Agent 框架都会变得「透明」。

### 抽成 Butler / IDE 协作约定示例（可直接写进战力文件）

1. **协作约定：先讲五问，再讲需求**
   - 每次开一条较大的心跳任务或工程分支时，优先与 Butler 对齐这五问：
     - 我们的「状态」在哪里落盘（`self_mind` / `task_ledger` / BrainStorm / 项目内 STATE 文件）？
     - 这条任务的上下文注入策略是什么（先读哪些文件 / 哪些目录是只读的）？
     - 任务进度怎么追踪（心跳任务 id / task_ledger 条目 / docs 里哪一页）？
     - 如果执行失败，怎么回滚或降级（只读模式 / 不改 `butler_main/butler_bot_code` / 写入 `heartbeat_upgrade_request.json` 等）？
     - 当前分支和其他角色/agent 的协作边界是什么？

2. **协作约定：大工程先搭「一条骨架」，再加机制**
   - 对应 learn-claude-code 的 `s01 → s12`：
     - 对于 Butler / IDE 的工程演进，默认采用「每一轮只多加一个机制」的节奏，例如：
       - 本轮只加「任务落盘到 `task_ledger.json`」；
       - 下一轮再考虑「多 Agent 并发」；
       - 再下一轮才加入「自动回滚/降级」。
   - 在协作手册里，可以为当前项目标注「我们已经做到 s 几」，方便未来对齐预期。

3. **协作约定：所有新流水线，都要在 BrainStorm 中有 Raw + MEMORY 入口**
   - 类似本次「web-note-capture-cn → web-image-ocr-cn → BrainStorm → 协作手册」的链路：
     - 每一次新的外部灵感/文章，都必须至少留下：
       - 一个 `BrainStorm/Raw/*.md`（原文/摘要）；
       - 一条 `BrainStorm/MEMORY.md` 的稳定共鸣点。
   - 这样 Butler 可以在执行分支前快速复读这些长期认知，而不是只依赖当前对话上下文。

4. **协作约定：Agent 不靠花名神秘，靠工程骨架透明**
   - 协作手册中尽量避免只用「酷炫命名」描述 agent，而是：
     - 写清每个角色的输入/输出、状态存储位置与失败处理方式；
     - 让任何新助手在 10 分钟内「看懂骨架」，而不是靠记住花名来理解职责。

上述 3–4 条约定，可以直接迁入具体项目的 `ide_assistant_power_file`，成为「一个文件让 Butler / IDE 战力翻倍」的一部分。

---

## 对 Butler 自己的使用建议（2–3 条）

- **1. 何时优先走这条流水线**  
  - 当遇到「明显高价值的生产力类内容」，且有意将其长期内化为协作规范时：
    - 例如：Agent 工程化实践、IDE 使用套路、一人公司/多 Agent 组织设计等；
    - 不适合「一次性资讯」或纯情绪吐槽。

- **2. 不要在低价值链接上滥用抓取与 OCR**  
  - 若内容只是一时感兴趣、难以抽出可执行结构（如纯段子/梗图），应：
    - 只在 self_mind 或 local_memory 中留一句提及；
    - 避免完整走「抓取 → OCR → Raw → MEMORY → 协作手册」全流程，以免噪音淹没信号。

- **3. 默认从已有模板出发，而不是重写一遍结构**  
  - 在项目内要创建新的「战力文件」时，优先复制：
    - `BrainStorm/Templates/ide_assistant_power_file_template.md`
  - 只根据当前项目补齐具体环境/工作流/坑，而不是重复发明新的结构，保持不同项目之间的协作手册形态尽量一致。

---

## TODO（后续在代码 / skill 层需要补的点）

- **OCR 能力检测与错误日志统一化**  
  - 为 `web-image-ocr-cn` 增加「环境自检 + 统一错误日志」机制，避免调用失败时只在对话中口头说明；
  - 建议落盘到类似 `BrainStorm/STATE.md` 或独立的 `ocr_error_log.jsonl`，记录：
    - 图片标识（来源链接 / 本地路径）；
    - 调用时间与环境信息；
    - 失败原因与下一步建议（例如「需配置 PaddleOCR」或「需打开远程 OCR 服务」）。
- **抓取 → MEMORY → 协作手册的自动化链路**  
  - 在未来的心跳任务或 skill 升级中，可考虑增加一个轻量脚本/skill：
    - 检测 `BrainStorm/Raw` 新增文件；
    - 引导/半自动生成对应的 MEMORY 条目草稿；
    - 根据特定标签（如「Agent 工程化」「IDE 协作」）建议是否推入某个 `ide_assistant_power_file` 具体实例。

