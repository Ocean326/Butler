# Butler-flow Desktop V2.1 PRD（main 分支对齐 / foreground flow CLI 入口 / TUI + Desktop 双轨）

- 日期：2026-04-02
- 版本：V2.1 更新版（前台 flow 对齐）
- 适用范围：**仅前台 `butler-flow` / flow CLI / Textual TUI / 未来 Desktop**
- 分支基准：`main`
- 文档目标：把此前混入 `orchestrator / mission / branch / workflow_session` 的规划线剥离掉，改为严格以前台 `butler-flow` 当前真源、CLI 入口、sidecar 状态和已落地 TUI 为基准来定义 Desktop V2.1

---

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 去掉后台 `orchestrator` 线后，重新定义 `butler-flow` 的前台桌面/TUI 双轨计划，并把 Desktop 规划贴住当前 foreground flow 真源。 |
| 所属层级 | 主落 L1 `Agent Execution Runtime`，辅用 L2 本地状态与 sidecars。 |
| 当前真源文档 | `0331/02` 定义前台 CLI 总入口；`0401/01` 定义 `new/resume/exec + setup picker`；`0401/02` 定义 `workspace / single flow / /manage` 信息架构；`0402/02` 与 `0402/11` 定义 manage center 与 supervisor 观测流。 |
| 计划查看的代码与测试 | `butler_main/butler_flow/`、`butler_main/butler_flow/tui/`、`tools/butler-flow`、`butler_main/__main__.py`；相关测试为 `test_butler_flow.py`、`test_butler_flow_tui_controller.py`、`test_butler_flow_tui_app.py`。 |

## 0. 本次修正的核心结论

相比此前版本，这次最重要的修正是：

> **Butler-flow Desktop V2.1 必须严格跟随前台 `butler-flow` 真源，不再借用后台 `orchestrator` 的 `mission / branch / workflow_session` 作为桌面产品对象模型。**

原因不是后台线无价值，而是它与当前前台 `butler-flow` 的现役边界冲突：

1. 当前前台 `butler-flow` 明确是 **foreground attached runtime**，不进入 `campaign/orchestrator` 主链。
2. 当前前台 `butler-flow` 的真源是本地 `workflow_state.json + flow_definition.json + turns/actions/events/artifacts/role_sessions/handoffs`。
3. 当前 Textual TUI 已经不是空壳，而是已有：
   - `workspace`
   - `single flow`
   - `supervisor / workflow` 双流
   - `/manage` transcript-first shell
4. 因此前台 Desktop 规划不该再从后台 mission board 反推，而应从**现有前台 flow payload 与 sidecar 投影**继续抽象。

一句话：

> **这次不是“给 orchestrator 做桌面”，而是“让现有 `butler-flow` 形成 desktop-ready foreground surface”。**

---

## 1. main 分支上已确认的前台 flow 入口

## 1.1 当前公共入口不是 `runner.py`，而是 `butler-flow`

在 `main` 分支上，前台 flow 的公共入口已经固定为：

- `butler-flow`
- `butler-flow new`
- `butler-flow resume`
- `butler-flow exec`
- `tools/butler-flow ...`
- `python -m butler_main ...`

当前公开能力围绕这几类命令展开：

- `new`
- `resume`
- `exec new / exec resume`
- `status`
- `list`
- `preflight`
- `action`
- `tui`

因此，Desktop V2.1 必须承认一个现实：

> **Butler-flow 已经有 flow-native CLI；缺的不是“flow CLI”，而是更清晰的 shared surface 与更完整的 desktop shell。**

## 1.2 当前前台链路应理解为三层

### Layer A：系统暴露与安装层（已存在）

入口：

- `tools/install-butler-flow`
- `tools/butler-flow`
- `python -m butler_main`

职责：

- 提供系统命令暴露
- 提供仓库内兼容入口
- 提供模块级 fallback 入口

### Layer B：flow-native runtime CLI（已存在）

入口：

- `butler-flow new/resume/exec/status/list/preflight/action`

职责：

- 创建和恢复前台 flow
- 驱动 foreground flow runtime
- 写本地 sidecars
- 在 plain / exec 模式下输出状态与 JSONL receipt

### Layer C：interactive shell / future Desktop（部分已存在，部分待补）

当前已存在：

- Textual launcher
- `workspace`
- `single flow`
- `/manage`
- `/settings`

未来待补：

- desktop adapter
- desktop shell
- richer artifact/preview/drill-down 体验

因此，V2.1 的正确修正不是“找出 runner 那一层”，而是：

> **承认 `butler-flow` 自己已经形成 foreground flow CLI + TUI，再在其上抽 desktop-ready surface。**

---

## 2. 当前前台 flow 的真实对象面

## 2.1 当前核心真源对象

当前前台 `butler-flow` 真正稳定的对象不是后台的 `Mission/Branch`，而是：

- `FlowState`
- `flow_definition.json`
- `turns.jsonl`
- `actions.jsonl`
- `events.jsonl`
- `artifacts.json`
- `role_sessions.json`
- `handoffs.jsonl`
- `runtime_plan.json`
- `prompt_packets.jsonl`
- `strategy_trace.jsonl`
- `mutations.jsonl`

从产品视角，可映射为：

- `Flow` = 一条前台 instance flow
- `Flow Definition` = 当前实例的 materialized static/runtime definition
- `Supervisor View` = 主脑判断流
- `Workflow View` = runtime 输出流
- `Role Session` = medium/complex 语义下的角色会话绑定
- `Handoff` = 角色切换与 bounded truth 交接
- `Manage Asset` = `builtin + template` shared assets

## 2.2 当前现役产品投影已经存在

`butler_main/butler_flow/tui/controller.py` 里，当前已经有几组现役 payload：

- `workspace_payload()`
- `single_flow_payload()`
- `manage_center_payload()`
- `detail_payload()`
- `role_strip_payload()`
- `operator_rail_payload()`
- `flow_console_payload()`

其中真正贴近未来 shared surface 的，是：

- `workspace_payload`
- `single_flow_payload`
- `manage_center_payload`
- `detail_payload`

这意味着当前仓库已经有一层“准 surface”，只是还长在 TUI controller 里。

因此 V2.1 的重点不是重新从零定义桌面对象，而是：

> **把 controller 内已经稳定的 foreground payload 抽成 `butler_flow` 自己的 shared surface。**

---

## 3. shared flow surface 的修正定义

## 3.1 shared surface 不再挂到 `orchestrator`

此前版本默认想新增：

```text
butler_main/flow_surface/
```

并让它直接包 `orchestrator.service` 与 `runner.py`。

这个方向现在要修正为：

```text
butler_main/butler_flow/surface/
```

职责：

- 对前台 `butler-flow` 的 sidecar 真源做 DTO 化
- 承接当前 `FlowTuiController` 的现役 payload
- 为 Textual TUI 与 future Desktop 提供统一对象结构
- 不引入第二真源
- 不把后台 `mission / branch / workflow_session` 混进前台 flow 模型

## 3.2 推荐 DTO

### `FlowSummaryDTO`

用于 `workspace` 列表与 Desktop 左栏：

- `flow_id`
- `workflow_kind`
- `effective_status`
- `effective_phase`
- `goal`
- `approval_state`
- `execution_mode`
- `session_strategy`
- `active_role_id`
- `role_pack_id`
- `latest_judge_decision`
- `latest_operator_action`
- `latest_handoff_summary`
- `updated_at`

### `FlowDetailDTO`

用于 `single flow` / Desktop 主工作台：

- `flow`
- `summary`
- `step_history`
- `timeline`
- `artifacts`
- `turns`
- `actions`
- `handoffs`
- `runtime_snapshot`
- `flow_definition`

### `SupervisorViewDTO`

用于 supervisor 主视图：

- `header`
- `events`
- `approval_state`
- `pending_codex_prompt`
- `latest_supervisor_decision`
- `latest_judge_decision`
- `latest_operator_action`
- `latest_handoff_summary`
- `latest_token_usage`
- `context_governor`
- `latest_mutation`

### `WorkflowViewDTO`

用于 workflow 输出视图：

- `events`
- `runtime_summary`
- `artifact_refs`

### `ManageCenterDTO`

用于 `/manage` 与 future Desktop manage center：

- `assets`
- `selected_asset`
- `role_guidance`
- `review_checklist`
- `bundle_manifest`
- `manager_notes`

### `RoleRuntimeDTO`

用于 detail drill-down：

- `active_role_id`
- `role_sessions`
- `pending_handoffs`
- `recent_handoffs`
- `latest_handoff_summary`

## 3.3 shared surface 的边界

shared surface 现在只服务：

1. 当前 Textual TUI
2. 未来 Desktop
3. 未来可能的轻量只读 adapter / API

shared surface 当前**不服务**：

- `campaign/orchestrator` 后台 operator console
- chat frontdoor
- visual console 后台 campaign graph

---

## 4. 对 TUI 的计划修正

## 4.1 当前 TUI 不是待从零实现，而是待抽象与瘦身

此前版本把 interactive TUI 写成“待补齐”；这已经不准确。

更准确的说法是：

- 当前 Textual TUI 已落地一轮实现
- 现在的问题不是“有没有”
- 而是“controller payload 还没有正式沉淀成 desktop-ready surface”

因此 TUI 第一阶段不该推倒重来，而应：

1. 保持当前 `workspace / single flow / /manage` 产品壳
2. 将 payload 从 controller 抽到 `butler_flow/surface`
3. 让 TUI 变成 shared surface 的第一消费方

## 4.2 TUI 第一阶段应做什么

### 必做

- `workspace` 改为消费 `FlowSummaryDTO`
- `single flow` 改为消费 `FlowDetailDTO + SupervisorViewDTO + WorkflowViewDTO`
- `/manage` 改为消费 `ManageCenterDTO`
- inspector/detail 改为消费 `RoleRuntimeDTO + runtime/detail DTO`

### 不做

- 不回退到卡片式 `/flows`
- 不把 `/manage` 再做成 assets-only 卡片页
- 不引入后台 `mission / branch` 列表
- 不把 TUI 变成第二条 runtime daemon

---

## 5. 对 Desktop 的计划修正

## 5.1 Desktop 继续后移，但目标更清楚

Desktop 的目标不再是“补一个更漂亮的 orchestrator 工作台”，而是：

> **复用 foreground `butler-flow` 的 shared surface，提供更强的浏览、预览、artifact 打开和多面板信息密度。**

## 5.2 Desktop 最小结构

### Desktop Home

- 左栏：flow list
- 中栏：selected flow summary + supervisor/workflow switch
- 右栏：detail drawer
- 底部：action / status rail

### Desktop Flow Workbench

- `supervisor` / `workflow` 双主视图
- artifact preview
- phase / role / approval / operator explain
- prompt packet / mutation / handoff drill-down

### Desktop Manage Center

- 与 `/manage` 同一对象模型
- transcript-first
- asset detail
- review checklist
- bundle / lineage / role guidance

## 5.3 Desktop 当前不应该先做什么

- 不先接 Electron-specific API
- 不先做复杂动画和 graph editor
- 不把主视图重新做成 chat-first transcript app
- 不把后台 `campaign` console 心智搬到前台 desktop

---

## 6. V2.1 更新后的实施顺序

### Phase 0：冻结 foreground 真源

冻结以下事实：

- 公共入口以 `butler-flow` 为准
- 真源是前台 flow sidecars，不是后台 mission/branch
- TUI 当前已有 `workspace / single flow / /manage`

### Phase 1：抽 `butler_flow/surface`

目标：

- 新增 `butler_main/butler_flow/surface/`
- 承接 `FlowTuiController` 里的现役 payload
- 形成稳定 DTO

### Phase 2：让现有 TUI 薄改接 surface

目标：

- controller 只负责交互与命令编排
- 取数逻辑转入 surface
- 当前 UI 外观尽量不大改

### Phase 3：补 Desktop adapter

目标：

- 定义 Desktop 需要的 adapter / API 边界
- 不直接吃 raw sidecars
- 只消费 `butler_flow/surface`

### Phase 4：Desktop workbench

目标：

- flow list
- flow workbench
- manage center
- artifact preview
- detail drawer

---

## 7. 给 Codex / butler-flow 的更新版执行要求

## 7.1 禁止事项

1. 禁止把后台 `orchestrator` 重新引入为 Butler-flow Desktop 主真源
2. 禁止把 `Mission / Branch / WorkflowSession` 写成前台 `butler-flow` 当前对象模型
3. 禁止推翻当前 `workspace / single flow / /manage` 信息架构
4. 禁止把 `/manage` 再做回栏式 asset cards
5. 禁止让 Desktop 直接读取 raw sidecars 或 controller 内部兼容 payload

## 7.2 实现优先级

### P0

- `butler_flow/surface` DTO
- surface query/detail/builders
- TUI 薄改接 surface

### P1

- Desktop adapter / API
- Desktop home/workbench/manage 骨架

### P2

- artifact UX
- richer drill-down
- layout polish

---

## 8. V2.1 更新版结论

**现在需要去掉的不是一层 CLI，而是一整条“后台 orchestrator 线”的错误借用。**

修正后，Butler-flow Desktop V2.1 的正确路线是：

1. 以前台 `butler-flow` CLI 和 sidecars 为真源
2. 承认当前 Textual TUI 已经存在
3. 把 controller 里的现役 payload 抽成 `butler_flow/surface`
4. 先让 TUI 成为第一消费方
5. 再让 Desktop 复用这套 foreground surface

因此，V2.1 更新后的正确一句话定义是：

> **Butler-flow Desktop V2.1 = 以 foreground `butler-flow` 状态与现役 TUI payload 为真源的 desktop-ready flow workbench；TUI 与 Desktop 共用同一套前台 flow surface。**
