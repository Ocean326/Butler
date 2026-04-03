# 0403 Butler Flow Desktop shared surface 一期抽层

日期：2026-04-03  
状态：已落代码 / 当前真源  
所属层级：L1 `Agent Execution Runtime`

## 1. 本轮目标

继续推进 `butler-flow desktop` 时，当前最明显的缺口不是 CLI 或 `/manage` 能力本身，而是：

- `workspace_payload()`
- `single_flow_payload()`
- `manage_center_payload()`

这些已经稳定、且最接近 future Desktop 的 payload 仍主要长在 `tui/controller.py` 里；  
`butler_main/butler_flow/surface/` 只沉淀了一层 `FlowSummaryDTO`，还不足以作为 TUI / Desktop 共用的 shared surface。

因此本轮裁决是：

> 先补齐 `butler_flow/surface` 的 typed DTO 与 builder/service，再让 TUI controller 复用这层；不改 sidecar 真源，也不引入第二状态源。

## 2. 当前状态判断

当前 `butler-flow desktop` 的基础面其实已经具备：

- foreground CLI 已稳定收口在 `butler-flow new/resume/exec/...`
- TUI 已有 `workspace / single flow / /manage / settings`
- `/manage` 已经是 transcript-first shell，并具备 manager session / draft / pending_action
- `single flow` 已有 `supervisor_view / workflow_view / inspector / role_strip / operator_rail`

真正缺的是中间这层：

- 缺可复用 DTO
- 缺稳定 surface builder
- 缺让 TUI 明确消费 surface 的实现路径

这会让后续 Desktop 很容易继续直接依赖 controller 私有组织方式，而不是复用 `butler-flow` 自己的 shared surface。

## 3. 本轮实现

### 3.1 `surface/` 补齐

新增/补齐了以下 DTO：

- `FlowSummaryDTO`
- `SupervisorViewDTO`
- `WorkflowViewDTO`
- `RoleRuntimeDTO`
- `OperatorRailDTO`
- `FlowConsoleDTO`
- `FlowDetailDTO`
- `WorkspaceSurfaceDTO`
- `ManageCenterDTO`

同时补了 builder / service：

- `surface/queries.py`
  - 负责 summary、role/runtime、operator rail、single-flow detail 的 DTO 化
- `surface/service.py`
  - 负责 workspace/manage-center/single-flow 的 surface 组装

### 3.2 TUI controller 接 surface

`butler_main/butler_flow/tui/controller.py` 当前改为复用 surface 层来产出：

- `manage_center_payload()`
- `workspace_payload()`
- `role_strip_payload()`
- `operator_rail_payload()`
- `flow_console_payload()`
- `single_flow_payload()`

外部 payload 合同保持不变，TUI 页面无须跟着改心智。

### 3.3 顺手修正的一处 TUI 回归

shared surface 抽层后，`history/settings/flows/back` 切换期间更容易撞上 `tui/app.py` 的轮询刷新。  
为避免浏览类页面发生“意外全量刷新”，本轮把 `_poll_runtime_surface()` 收口为：

- `flow` 主视图继续自动刷新
- `history / settings / manage` 不再由轮询触发全量 `_refresh_snapshot()`

这样既保住了 attached flow 主视图的实时性，也避免视图切换时的噪声刷新。

## 4. 验收

本轮最小必要回归：

- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_surface.py butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py -q`
- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_tui_app.py -q`

结果：

- `test_butler_flow_surface.py + test_butler_flow_tui_controller.py`：`28 passed`
- `test_butler_flow_tui_app.py`：`47 passed`

## 5. 当前缺口与下一步

shared surface 现在已经不再只有 `FlowSummaryDTO`，但下一阶段仍有三件事：

1. 继续把 `detail_payload()` / inspector 取数逻辑往 `surface/` 收口
2. 为 future Desktop 明确 `adapter / transport` 边界，而不是让 Desktop 直接贴 controller
3. 视情况补 `surface` 层的 action/query service，避免 future Desktop 重新绕回 `FlowApp` 或 TUI 私有方法

一句话：

> `butler-flow desktop` 当前已经从“有 TUI、没 shared surface”进入“surface-first 已起步、TUI 已开始复用”的阶段，后续可以更稳地往 Desktop 壳推进。
