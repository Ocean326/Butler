---
name: iodraw-architecture
description: Maintain and update Butler architecture diagrams using iodraw (diagrams.net) based on the latest architecture docs. Use when the user mentions iodraw, 架构图, 机制图, or Butler_机制+系统思维导图.drawio.
---

# iodraw Architecture Diagram Skill

本 skill 负责 Butler 架构图的维护工作，围绕现有的 `Butler_机制+系统思维导图.drawio`，在架构认知更新时给出**具体的改图指导**，并配合用户在 iodraw / diagrams.net 中落地。

默认上下文：

- 主要文件：`Butler_机制+系统思维导图.drawio`（位于仓库根目录）
- 主要参考文档：
  - `butler_main/butler_bot_code/docs/总体架构蓝图_20260309.md`
  - `butler_main/butler_bot_agent/agents/docs/AGENTS_ARCHITECTURE.md`

## 使用场景

在以下场景下优先调用本 skill：

- 用户提到「更新架构图」「更新机制图」「调整系统思维导图」。
- 用户提到「iodraw」「diagrams.net」「drawio」相关需求。
- 架构蓝图、Agent 列表、分层文档明显有了新版本，需要同步到图里。

## 快速流程总览

1. **读文本真源**
   - 读取 `butler_main/butler_bot_code/docs/总体架构蓝图_*.md` 中最新一版。
   - 读取 `butler_main/butler_bot_agent/agents/docs/AGENTS_ARCHITECTURE.md`。
2. **理解当前架构认知**
   - 提炼出分层（Transport / Conversation Runtime / Memory Service / Task Ledger / Governor / Observer / Upgrade Engine 等）。
   - 提炼出主 Agent / Sub-Agent 列表及协作关系。
3. **对比现有图**
   - 如需要细看现有结构，可读取 `Butler_机制+系统思维导图.drawio`，只做**结构/标签级别**理解，不在 XML 层面频繁微调布局。
4. **生成「改图指令」而不是生硬 XML**
   - 面向用户生成一份「在 iodraw 里如何操作」的步骤：应该新增哪些框、改哪些文案、连哪些箭头。
   - 只在非常简单、低风险的情况下才直接改 `.drawio` 的 XML（例如批量改文字标签，不大幅调整布局）。
5. **如用户需要，可生成新的分层草图方案**
   - 把重构后的架构整理成分层草案（例如：顶部是对外入口，中间是 runtime 和 memory，底部是 governor / upgrade engine）。
   - 让用户在 iodraw 里照着搭积木。

## 打开与保存图的推荐流程（给用户看的说明）

当需要在 iodraw / diagrams.net 里实际操作图时，可以按以下步骤执行（这些步骤通常写进答复里给用户）：

1. 在本地文件系统中找到 `Butler_机制+系统思维导图.drawio`。
2. 打开浏览器访问 iodraw 或 diagrams.net（例如：`https://app.diagrams.net`）。
3. 选择「从本地打开」/「打开已有图」，上传 `Butler_机制+系统思维导图.drawio`。
4. 按本 skill 给出的「改图指令」在画布上增删框和连线。
5. 完成后选择「文件 → 另存为」或「保存」，将更新后的 `.drawio` 文件下载回本地，并覆盖仓库中的同名文件。

> 说明：本仓库内仅保存 `.drawio` 源文件，不强制输出 PNG / SVG；如用户有导出需求，再根据上下文补充导出步骤。

## 架构分层对照（蓝图 → 图元素）

下面是根据 `总体架构蓝图_20260309.md` 提炼出的**推荐图层结构**，用于生成改图建议：

- **Transport**
  - 标签建议：`Transport（飞书长连接 / 消息入口）`
  - 主要内容：飞书长连接、消息发送、附件下载、去重、回调入口。
- **Conversation Runtime**
  - 标签建议：`Conversation Runtime（对话编排）`
  - 职责：单轮编排、recent 注入、调用模型、产出候选记忆与候选任务。
- **Memory Service**
  - 标签建议：`Memory Service（记忆服务）`
  - 职责：`talk_recent_memory`、`beat_recent_memory`、`semantic_memory`，候选提取和正式落账。
- **Task Ledger**
  - 标签建议：`Task Ledger（统一任务总账）`
  - 职责：短期/长期任务记录、唯一 machine-readable 真源、只读镜像输出。
- **Governor**
  - 标签建议：`Governor（风险与权限治理）`
  - 职责：动作风险评估、是否允许自动执行、自升级边界控制。
- **Observer / Telemetry**
  - 标签建议：`Observer / Telemetry（运行观测）`
  - 职责：心跳快照、planner backoff、守护/主进程状态，仅做观测。
- **Upgrade Engine**
  - 标签建议：`Upgrade Engine（升级引擎）`
  - 职责：接收升级提议、生成补丁与执行计划、调用 governor 审批、测试上线与回滚。

生成改图建议时，可以把这些分层按**自上而下**或**左到右**的顺序排布成一列或两列，尽量：

- 上面是「对外接口 / 对话入口」；
- 中间是「runtime + memory + task ledger」；
- 下面是「observer + governor + upgrade engine」支持层。

## 多 Agent 架构对照（AGENTS_ARCHITECTURE.md → 图元素）

根据 `AGENTS_ARCHITECTURE.md`，在图中建议保留以下板块：

- **主 Agent**（可画成一组并列框）：
  - `feishu-workstation-agent`：飞书对外表达与治理。
  - `butler-continuation-agent`：IDE 本地对话。
  - `heartbeat-planner-agent`：heartbeat 内在规划。
  - `subconscious-agent`：记忆巩固与新陈代谢。
- **Sub-Agent**：
  - `orchestrator_agent`、`secretary_agent`、`literature_agent`、`file_manager_agent`、
    `research_ops_agent`、`engineering_tracker_agent`、`discussion_agent`、`heartbeat-executor-agent`。
- **协作主线**：
  - 对外表达层 → 内在思维层 → Sub-Agent 执行 → subconscious 整理记忆 → 再回到表达层。

在生成改图建议时：

- 清楚标出**主 Agent 区**与 **Sub-Agent 区**。
- 用粗箭头强调：输入从飞书 / IDE 进来，经过 planner / executor，最后回到用户。
- 避免在图中过度堆叠文案，把复杂细节放到文字说明和 docs。

## 输出格式建议（给用户的「改图指令」）

当用户说「更新一下架构图」时，本 skill 建议生成**结构化的改图 checklist**，类似：

```markdown
## Butler 架构图本轮更新建议

1. 在画布左上角新增一个分层标题「Transport」，画一个矩形写：飞书长连接 / 消息发送 / 附件下载 / 去重 / 回调入口。
2. 在 Transport 右侧画「Conversation Runtime」，箭头从 Transport 指向它，标签「飞书消息 → Runtime 编排」。
3. 在 Runtime 下方画「Memory Service」，与 Runtime 双向箭头，标签「上下文注入 / 记忆落账」。
4. 在 Memory Service 右侧画「Task Ledger」，从 Runtime 和 Memory 都有箭头指向它，说明「统一任务总账」。
5. 在图底部中间画「Governor」，从 Runtime、Task Ledger、Upgrade Engine 画箭头到 Governor，说明「风险评估 / 权限控制」。
6. 在 Governor 右侧画「Observer / Telemetry」，从所有上层模块画虚线箭头到它，说明「只读观测」。
7. 在 Governor 下方画「Upgrade Engine」，从 Task Ledger 和 Governor 有箭头进入，说明「升级提议 → 执行 → 回滚」。
8. 在图右侧保留一块「多 Agent 架构」，把 `feishu-workstation-agent`、`butler-continuation-agent`、`heartbeat-planner-agent`、`subconscious-agent` 放在一列，Sub-Agent 放在另一列，箭头连接如文档所述。
```

实际生成时，可以根据本轮架构变更，只输出**需要变动的部分**，避免每次都重画全图。

## 何时直接改 `.drawio`

默认优先给用户「在 iodraw 里怎么改」的指令，不强行在 XML 层直接操作布局。

只有在满足以下条件时，才考虑对 `Butler_机制+系统思维导图.drawio` 做轻量自动编辑：

- 变更仅涉及**节点标签的小幅修正**（例如把「Recent Mem」改为「talk_recent_memory」/「beat_recent_memory」说明）。
- 不需要新增/删除大量节点和连线。
- 现有 XML 结构清楚，能通过少量 `<mxCell>` 文本替换完成。

即便修改 XML，也要：

- 保持 `<mxfile>` / `<diagram>` / `<mxGraphModel>` 结构完整。
- 不改动 `id` 布局关系，只改 `value` 文案。
- 修改前后保证文件可被 diagrams.net / iodraw 正常打开。

## 与其他 skill 的协作

- 当用户的需求更偏「每日巡检 / 启动 / 收口」，而非专门的架构对齐时，优先使用 `daily-inspection` skill。
- 当需要把架构图更新写入治理备忘或长期记忆时，可以配合 `file-manager-agent` 相关工作流，把本次图修改记录进 `./工作区/governance/` 或 `local_memory` 中。

