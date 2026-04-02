## 一句话概览

把「外部 Web 内容（知乎专栏 / 小红书等）」从飞书对话里的单条链接，稳定走完一条**可复用、可验收**的流水线：  
飞书甩链接 → `web-note-capture-cn` 抓取并下载图片 → agent 按本地图片路径直接读图整理 → 落盘 `BrainStorm/Raw` → 汇入 `BrainStorm/MEMORY.md` / `STATE.md` → 生成结构化笔记与潜在任务。

> 本文是当前版本的 **MVP 流程**，只整理现有能力，不新增代码或改动配置；后续可以在心跳 / 对话中继续演进。

---

## 快速总览：任务视图 & 真源入口

- **适用场景**：  
  - 单篇知乎专栏 / 小红书 / 其它网页内容，需要「抓取 → 下载图片 → 直接读图整理 → 落盘 BrainStorm → 进入长期记忆/任务」。  
  - 多篇技术文章/技术博客一批导入时，在完成本流程后，可配合 `BrainStorm/[Template]_multi_article_tech_notes.md` 做二次汇总和行动线索提炼。
- **主要 skills / 脚本真源**：  
  - `web-note-capture-cn`：`butler_main/butler_bot_agent/skills/web-note-capture-cn/SKILL.md`（入口脚本 `scripts/social_capture.py`）。  
- **BrainStorm 真源文档**：  
  - 机制总览：`BrainStorm/README.md`。  
  - 目录规则：`BrainStorm/Guides/命名与目录约定.md`。  
  - 流程细节：本文件 `BrainStorm/Playbooks/Web_内容抓取到头脑风暴_MVP流程.md`。  
- **典型输出路径**：  
  - 抓取输出：`工作区/网页抓取验证/{platform}_{id}.json` / `.md`  
  - 图片本地路径：`工作区/网页抓取验证/images/...`（也会写回 `image_local_paths`）  
  - 主题整理：`BrainStorm/Raw/daily/YYYYMMDD/YYYYMMDD_主题.md` → `BrainStorm/Insights/日期_主题_Insight.md` → `BrainStorm/MEMORY.md` / `STATE.md`

---

## 一屏版：Web→抓取→读图→BrainStorm→行动线索（最小闭环）

- **触发条件**：用户在飞书/对话中甩出「值得沉淀」的单条网页链接或含 `xhslink` 的文案，并明确这是研究/长期内容；heartbeat / 对话 agent 为其挂上一条任务（或长期任务子任务）。  
- **抓取落盘（工作区）**：按 `web-note-capture-cn` 说明对该链接调用 `social_capture.py`，将结构化 JSON + Markdown 统一落在 `工作区/网页抓取验证/{platform}_{id}.{json,md}`，并默认把图片下载到 `images/` 子目录，在任务回执中记录路径。  
- **图片补全文本（工作区/BrainStorm）**：若抓取 JSON 中 `images` 非空或人工判断关键信息在图片里，则直接读取 `image_local_paths` 中的本地图片路径，由 agent 逐张读图、识字、整理图中信息。  
- **挂入 Raw 与主题**：将本条内容（抓取 + 图片整理）挂入合适的 Raw 文件：要么直接引用 `image_local_paths` 与读图结果，要么在当日/当批的 `BrainStorm/Raw/daily/YYYYMMDD/YYYYMMDD_主题.md` 中加一个小节，并在文内标出来源链接、图片路径与长期任务 id。  
- **提炼行动线索**：当同一主题累计若干条 Raw 后，在对应的 `BrainStorm/Insights/日期_主题_Insight.md` 中写出关键观点 + 2–3 条「下一步可行动/可验证」线索（如「补读图结构化模板」「为该主题起一份 IDE 助手 power file」）。  
- **写回长期记忆与任务**：将对长期方向有价值的结论摘入 `MEMORY.md` / `STATE.md` 或长期任务说明，记录关联的 Raw/Insights 路径；在 task_ledger 中更新该任务的证据字段与完成状态，标清闭环是否已达成或还缺哪一步。  
- **执行侧自检**：单条内容视角下，任务回执中至少要能列出「工作区抓取文件路径 + 本地图片路径 + BrainStorm/Raw 文件路径 +（如适用）Insights 小节位置」，并说明读图整理/结构化/记忆吸收各自是否已完成。

---

## 标准步骤（单条内容视角）

### 步骤 1：飞书里甩链接 & 建立任务入口

- **输入**：用户在飞书里发送单条网页链接或含 `xhslink` 的分享文案（知乎专栏 / 小红书等），并表达「这条值得沉淀 / 请抓下来」。
- **动作**：
  - 对话侧 agent（如 `feishu-workstation-agent`）识别这是「Web→BrainStorm」场景；
  - 在统一任务体系中登记一条任务（对应 long-term 任务之一），写清：
    - 目标：本条内容需要被抓取、下载图片、读图整理并落盘到 `BrainStorm/Raw`，形成最小结构化笔记；
    - 边界：本轮仅处理单条内容，不改 `butler_main/butler_bot_code`、不自动升级 skill；
    - 完成判据：见下文「完成判据」小节。
  - 将任务 id 与本条链接一起写入 task 记录（例如落在 `task_ledger.json` 一类状态真源中），并在心跳分支 / 回执中带上。
- **涉及的长期任务 id（示例对齐）**：
  - `0dfa6f8d-30aa-405e-8822-b1aee2e5f267`、`0c97817d-2ca7-43dc-8efc-1f94c396a9b7`、`130c5a91-4d7d-474b-8ffe-42e3217cb209`
  - `63a20d32-7fdc-485a-b6e5-bb7c8e0aad10`、`d6f30e24-652f-4886-b481-9a9dfbffcc5e`、`d33f9e92-db16-4ba1-97c8-9572374bee36`

> Task/heartbeat 对接建议：无论入口源自对话还是 heartbeat，自始至终以同一任务 id 追踪「抓取 + 读图整理 + 落盘 + 结构化」的完成情况，避免在对话与 heartbeat 中各自维护平行任务池。

---

### 步骤 2：使用 `web-note-capture-cn` 抓取网页内容

- **对应 skill**：`web-note-capture-cn`  
  - 入口文档：`butler_main/butler_bot_agent/skills/web-note-capture-cn/SKILL.md`
  - 入口脚本：`butler_main/butler_bot_agent/skills/web-note-capture-cn/scripts/social_capture.py`
- **输入**：步骤 1 中的单条链接或含 `xhslink` 的完整分享文案。
- **推荐调用（示意）**：
  - 小红书分享页 / 短链 → 参照 skill 文档中的 `social_capture.py` 示例；
  - 知乎专栏 → 先不带 cookie 试抓一次，如遇 403 再按 skill 文档说明补 cookie 环境变量。
- **输出目录（工作区侧）**：
  - 默认落在 `工作区/网页抓取验证` 下，生成：
    - 结构化 JSON（含 `platform` / `source_url` / `resolved_url` / `id` / `title` / `author` / `content_text` / `images` / `image_assets` / `image_local_paths` 等字段）；
    - 对应 Markdown 摘要文件。
- **与任务视图的衔接**：
  - 在任务回执中记录抓取输出的具体文件路径；
  - 若调用失败（如 403 / 平台限制），在任务备注中写明失败原因与下一步（补 cookie / 更换链接等），而不是只报「失败」。

---

### 步骤 3：若含图片，直接按本地图片路径读图整理

- **触发条件**：
  - 抓取 JSON 中 `images` 字段非空；
  - 或人工判断该条内容的关键信息主要在截图 / 插图中。
- **推荐动作（示意）**：
  - 读取步骤 2 生成的 JSON 中 `image_local_paths`；
  - 逐张打开本地图片，直接读出图中文字、结构、表格或流程信息；
  - 将整理结果写入 Raw 汇总稿或工作稿，不再默认生成单独的 OCR JSON / Markdown。
- **图片不完整时的处理**：
  - 若 `images` 非空但 `image_local_paths` 为空或数量明显不全，先检查下载失败原因并补跑抓取；
  - 在任务备注中标记「图片下载未完成」，但不要误报为“已经做过 OCR”。
- **与脑内机制的对接**：
  - 读图整理结果直接进入 Raw 层正文或对应主题汇总，后续 `Insights` / 模型文档可引用其中的结构 / 公式 / 分层。

---

### 步骤 4：将抓取与读图整理结果落盘到 `BrainStorm/Raw`

- **Raw 层写入规范**（结合 `BrainStorm/README.md` 与现有样本）：
  - 抓取与读图整理结果可按以下方式落盘：
    - 保持 `工作区/网页抓取验证/{platform}_{id}.{json,md}` 作为抓取事实记录；
    - 在 `BrainStorm/Raw` 下：
      - 直接在主题稿中记录图片整理结果与对应 `image_local_paths`；
      - 或按日期/主题汇总多条内容成 `daily/YYYYMMDD/YYYYMMDD_主题名.md`，在文件内引用对应抓取 JSON / Markdown 与本地图片路径。
  - 命名示例：
    - `BrainStorm/Raw/daily/20260316/20260316_claude_code_agent_xhs.md`
    - `工作区/网页抓取验证/images/01_xxxxxxxx.jpg`
- **调用方自检约定**（与 README 保持一致）：
  - 若抓取结果含 `images`，且 `image_local_paths` 为空或明显不全，则视为「ingest 未完成」，需要优先补跑抓取并完成图片下载；
  - 若暂时只能落盘正文、未完成读图整理，也应在任务中明确标记后续需补读图。

---

### 步骤 5：从 Raw 进入 `MEMORY` / `STATE`，生成结构化笔记与潜在任务

- **从 Raw 到 `Insights` / `MEMORY` / `STATE`**：
  - 当围绕某一主题累计了若干条 Raw + 图片整理内容后：
    - 在 `Insights/日期_主题_Insight.md` 中做主题化压缩；
    - 由定期任务或心跳分支将高价值洞察补入 `MEMORY.md`，并在 `STATE.md` 中挂上索引；
    - 对应长期任务 id（见步骤 1 中列出的 6 条）可在 `STATE.md` 或任务文档中标明「已吸收到哪一层」（Raw / Insights / MEMORY）。
- **生成结构化笔记（可直接为 IDE/助理服务）**：
  - 对于足够成熟的主题，可以：
    - 复制 `BrainStorm/Templates/ide_assistant_power_file_template.md`，在工作区或项目 `docs/` 下实例化为某个 IDE/助理的「战力翻倍」文件；
    - 由当前长期任务（如 `130c5a91-4d7d-474b-8ffe-42e3217cb209` / `d33f9e92-db16-4ba1-97c8-9572374bee36` 等）负责持续迭代该文件内容。
- **潜在任务生成**：
  - 在整理 Raw/读图内容时，若发现明确的改进行动（如「补读图模板」「调整抓取参数」「补一张架构图」），应：
    - 在对应 long-term 任务下增加子任务；
    - 并写回 task 记录（如 `task_ledger.json`）中，标记来源 Raw 文件路径与关联的 Web 链接。

---

## 最小标准与自检清单（单条内容）

> 这部分是给执行侧/heartbeat 用的「最小合格线」，用于快速判断一条 Web→BrainStorm 流水线是否走完，以及哪里需要补坑。

- **最小步骤骨架（单条内容）**  
  1. **链接 → `web-note-capture-cn` 抓取**：  
     - 输入：单条网页链接或包含 `xhslink` 的分享文案；  
     - 期望输出：`工作区/网页抓取验证/{platform}_{id}.json` 和 `.md`（至少包含标题、正文、图片列表与 `image_local_paths`）。  
  2. **如有图片 → 直接读本地图片**：  
     - 条件：抓取 JSON 中 `images` 非空，或人工判断关键信息在图片里；  
     - 期望输出：可访问的 `image_local_paths`，以及一份合并进 Raw/Working 的读图整理结果。  
  3. **落盘 Raw（含未完成说明也要落盘）**：  
     - 抓取与读图整理结果在 `BrainStorm/Raw` 下有明确落点（按日期/主题或单条命名）；  
     - 若图片下载或读图未完成，也要写明失败原因或待补动作。  
  4. **结构化总结**：  
     - 视主题情况，在 `BrainStorm/Raw/daily/YYYYMMDD/YYYYMMDD_主题.md` 或 `Insights/日期_主题_Insight.md` 中做最小结构化笔记（关键观点 + 引用片段）；  
     - 至少能回答「这条内容讲了什么、对长期任务有什么帮助」。  
  5. **写入 BrainStorm/Insights / MEMORY / STATE**：  
     - 若已进入当前长期研究主题，至少：  
       - 在对应 `Insights` 文件中挂上本条的核心结论；  
       - 或在 `MEMORY.md` / `STATE.md` 或任务回执中写明来源 Raw 路径和长期任务 id。

- **执行前自检（开始前 3 项）**  
  1. **链接与场景确认**：  
     - 确认这是「值得沉淀」的长文/图文内容，而不是一次性通知；  
     - 在 task 记录中写清目标、边界（本轮只用既有 skills，不改核心代码）、完成判据。  
  2. **skill 可用性检查**：  
     - 本机可以正常访问 `butler_main/butler_bot_agent/skills/web-note-capture-cn` 的 `SKILL.md` 与脚本；  
     - 若这些路径缺失或版本异常，应在任务中标记「skill 环境待补」，避免误以为已执行。  
  3. **图片下载可用性检查**：  
     - 当前流程依赖 `web-note-capture-cn` 在 `--output-dir` 下成功下载图片；  
     - 在调用前，应确认输出目录可写；  
     - 若图片下载被平台限制或目录不可写，必须在任务或回执中显式标记，而不是静默跳过。  

- **执行后自检（收尾 4–5 项）**  
  1. **抓取是否成功**：  
     - `工作区/网页抓取验证/` 下是否存在本条对应的 `{platform}_{id}.json` 与 `.md`；  
     - JSON 中是否至少包含 `platform` / `source_url` / `title` / `content_text` 等核心字段。  
  2. **图片与本地路径是否齐全**：  
     - 若抓取 JSON 的 `images` 非空：  
       - 检查 JSON 中是否存在对应的 `image_local_paths`；  
       - 若不存在或数量明显不对，需在任务中标记「ingest 未完成：待补图片下载/读图」，并视情况补跑或记录失败原因。  
  3. **输出路径是否按日期 + 来源/主题命名**：  
     - `BrainStorm/Raw` 与 `Insights` 中的文件命名是否符合 `{YYYYMMDD}_{主题}` 等约定，方便后续检索与聚合；  
     - 若本次只生成了临时文件（如工作区草稿），需在回执中写明「尚未汇入 BrainStorm/Raw」。  
  4. **结构化总结是否落地**：  
     - 是否至少有一份汇总笔记（Raw 汇总或 `Insights` 草稿），而不仅仅是抓取原文；  
     - 总结中是否标记了与哪些长期任务 id 相关。  
  5. **失败兜底策略是否明确**：  
     - 如因平台限制 / 403 / 图片下载失败导致部分步骤失败：  
       - 是否在任务回执中写清失败原因、当前已落盘的证据路径；  
       - 是否给出下一步建议（补 cookie / 重跑下载 / 改用人工摘要等）。  

---

## 多篇文章导入模板（知乎专栏 / 技术博客）

> 适用于「一次性导入多篇知乎专栏 / 技术博客」的场景，目标是有一个可直接复用的壳，方便在 heartbeat 分支或对话中快速挂任务。

### 1. 标准输入清单（多篇长文）

- **链接列表**：  
  - `articles`: 数组形式的链接清单，每一项至少包含：  
    - `url`: 原始网址（知乎专栏 / 技术博客）  
    - `title_hint`（可选）：人工补充的标题/主题提示，用于后续合并命名  
    - `tags`（可选）：如 `["LLM Agent", "检索", "架构设计"]`。
- **期望输出目录约定**：  
  - 抓取验证：统一落在 `工作区/网页抓取验证/multi/` 下，命名示例：  
    - `multi_tech_{batch_id}_{index}.json` / `.md`  
  - Raw 层汇总：统一在 `BrainStorm/Raw` 下，以日期+主题命名：  
    - `BrainStorm/Raw/daily/{YYYYMMDD}/{YYYYMMDD}_{batch_topic}_multi_articles.md`
- **命名约定（建议）**：  
  - `batch_id`: 当天或本次批次的短 id，如 `20260316_zhihu_agents`；  
  - 单篇抓取文件：`{platform}_{short_id}_{batch_id}.json` / `.md`；  
  - 图片目录：`工作区/网页抓取验证/multi/images/`。  
- **是否需要读图的标记**：  
  - 在批次参数中增加：`need_image_reading: true | false | "auto"`：  
    - `true`: 默认对每一篇都读取本地图片；  
    - `false`: 仅抓取正文，不补图；  
    - `"auto"`：按抓取 JSON 中是否存在 `images` 字段自动决定。  
- **任务视角的补充字段**（对齐 heartbeat 模型）：  
  - `task_id`: 对应本次「多篇导入」的任务 id；  
  - `goal`: 如「导入 N 篇知乎/技术博客到 BrainStorm/Raw，并形成一份主题化总结草稿」；  
  - `done_criteria`: 用于后续自动/人工验收的判据（见下文示例）。

### 2. 最小链路：从抓取到 BrainStorm/MEMORY

- **Step A：批次级任务建档**  
  - 在 `task_ledger.json` 中增加一条「多篇导入」任务记录：  
    - 写明 `task_id` / `goal` / `boundary`（本轮只导入与初步整理，不改核心代码） / `done_criteria`；  
    - 在任务描述中列出本批次的 `articles` 链接清单与 `batch_topic`。
- **Step B：逐条调用 `web-note-capture-cn`**  
  - 对 `articles` 中的每个链接：  
    - 由 heartbeat 分支或对话 agent 依次调用 `web-note-capture-cn`（参照前文「步骤 2」的调用方式）；  
    - 输出统一写入 `工作区/网页抓取验证/multi/`，并在任务回执中记录每一条的文件路径。  
- **Step C：按需读取本地图片**  
  - 若 `need_image_reading = true` 或 `"auto"` 且某条抓取结果含 `images`：  
    - 读取该条 JSON 中的 `image_local_paths`；  
    - 将读图结论直接写入批次汇总稿；  
    - 若图片下载不完整，则在任务状态中标记「待补图片下载/读图」。
- **Step D：在 `BrainStorm/Raw` 中做批次级汇总**  
  - 创建/更新一个批次汇总文件，如：  
    - `BrainStorm/Raw/daily/{YYYYMMDD}/{YYYYMMDD}_{batch_topic}_multi_articles.md`；  
  - 在该文件中按「单篇摘要 + 关键片段引用」的形式，汇总本批次所有抓取/读图结果，保留指向各自抓取 JSON 与本地图片路径的引用。
- **Step E：进入 `Insights` / `MEMORY` 的最小桥接**  
  - 在合适的 heartbeat 分支中：  
    - 以批次汇总文件为输入，为该主题创建/更新一份 `Insights/{YYYYMMDD}_{batch_topic}_Insight.md` 草稿；  
    - 从中挑选对长期任务有帮助的要点，补入 `MEMORY.md`，并在 `STATE.md` 中挂上指向本批次 Raw/Insights 的索引。  
  - 首轮只要求「有一份可读的 Insight 草稿 + 至少 1-2 条被吸收到 `MEMORY`」，后续可在长期任务中继续细化。

### 3. 任务视图示例（对齐 heartbeat 模型）

> 下面是一个面向 `task_ledger.json` 的示意结构，展示多篇导入任务及其子任务的典型写法。

- **主任务（batch 级）**：  
  - `task_id`: `b2c2e6e9-3b2d-4a6b-9f0b-zhihu-batch-20260316`  
  - `description`: 「导入 5 篇关于 LLM Agent 架构的知乎专栏/技术博客，完成抓取 + 读图整理 + Raw 汇总，并生成一份初步 Insight 草稿」  
  - `status`: `in_progress` / `completed` / `blocked`  
  - `goal`: 与上文 description 等价或略更结构化的表述  
  - `boundary`: 「本轮不改 `butler_main/butler_bot_code`，仅使用既有 skills 与工作区文档」  
  - `done_criteria`:  
    - 所有目标链接都有抓取 JSON + Markdown；  
    - 含图片的文章都至少完成一次图片下载，并对关键图片做过直接读图或留下待补说明；  
    - `BrainStorm/Raw/daily/{YYYYMMDD}/{YYYYMMDD}_{batch_topic}_multi_articles.md` 已创建且包含每篇文章的摘要；  
    - 该批次在 `Insights` 中有一份对应草稿，并至少 1 条信息被写入 `MEMORY` / `STATE`。
- **子任务（逐篇文章）示例**：  
  - `task_id`: `sub-b2c2e6e9-1`  
  - `description`: 「抓取并处理知乎专栏《LLM Agent 架构演进实践》（第 1 篇）」  
  - `status`: `completed`  
  - `evidence`:  
    - `workspace_capture_path`: `工作区/网页抓取验证/multi/multi_tech_20260316_zhihu_agents_01.md`  
    - `raw_path`: `BrainStorm/Raw/daily/20260316/20260316_zhihu_agents_multi_articles.md#article-01`  
    - `image_paths`（如有）：`工作区/网页抓取验证/multi/images/...`  
  - `status_note`: 简短说明当前进展或阻塞原因（如「图片下载不全，待补读图」）。

---

## 与 heartbeat / task_ledger 的对接建议

- **入口时刻**：
  - 当用户第一次在飞书甩出「值得沉淀」的链接，并明确这是研究/长期内容时：
    - heartbeat 或对话代理应新建一条任务记录（或复用既有 long-term 任务的子任务），写入链接与目标；
    - 任务说明中明确「本任务的完成标准 = 完成本文件所述 5 步」。
- **执行过程**：
  - 每一步（抓取 / 读图 / 落盘 / 结构化）完成后，在任务回执中追加「已完成步骤 X」，并附上对应文件路径作为证据；
  - 若某一步因环境/权限受阻，先写清诊断结论与替代路径，再决定是否将任务挂起。
- **完成判据（单条内容层面）**：
  - 已有网页抓取 JSON + Markdown（至少含标题与正文）；
  - 若抓取结果含图片：
    - 已成功下载图片并产出 `image_local_paths`；
    - 对可访问图片，至少有一部分读图整理结果或明确的失败说明写入 Raw / Working；
  - 该条内容在 `BrainStorm/Raw` 中有落点，并能通过 `MEMORY` / `STATE` 或任务回执追溯来源链接与长期任务 id。
- **任务收尾**：
  - 在 task 回执中补充一小段「这条内容对哪些长期任务有帮助」的说明，优先对齐上文提到的 6 个 long-term 任务 id；
  - 若本条内容已被抽进某个「IDE/助理战力文件」，则在回执中附上对应文件路径，方便后续对话直接使用。

---

## 后续可改进方向（MVP 之后）

1. **自动检测与补跑**  
   - 在 heartbeat 中增加轻量巡检逻辑：定期扫描 `工作区/网页抓取验证` 与 `BrainStorm/Raw`，发现「有抓取 JSON 但无 `image_local_paths` 或无读图整理」的条目时，自动或半自动触发补抓/补读图，并写回任务回执。
2. **从 Raw 到协作手册的半自动桥接**  
   - 基于现有 `BrainStorm/Templates/IDE_assistant_booster_template.md`，为特定长期任务（如 `130c5a91-4d7d-474b-8ffe-42e3217cb209` / `d33f9e92-db16-4ba1-97c8-9572374bee36` 等）增加一个「Raw→模板」建议脚本或心跳分支模版，自动提取共鸣点草稿，减少人工搬运成本。
   
_updated_at: 2026-03-16 (heartbeat-executor-agent)_
