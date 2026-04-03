# 0403 Butler Flow Desktop 壳与 shared surface bridge 落地

日期：2026-04-03  
状态：已落代码 / 当前真源  
所属层级：L1 `Agent Execution Runtime`

## 目标

把 `0402` 的 Butler Flow Desktop 规划从“仅方案”推进到“可编译、可接 Python shared surface、可继续迭代的真实工程壳”，并明确：

- Desktop 继续只消费前台 `butler-flow` 的 sidecars / shared surface
- 不进入 `campaign/orchestrator`
- 不让 renderer 直接读取 raw sidecars
- TUI 与 Desktop 共享同一份 surface payload 心智

## 一句话裁决

当前 Desktop 真正落地为：

> **`Electron + React + TypeScript + Jotai + Tailwind` 壳 + `python -m butler_main.butler_flow.desktop_bridge` 薄桥接层 + `butler_main.butler_flow.surface` 作为唯一 shared surface。**

其中：

- `desktop_bridge.py` 负责把 `workspace / manage / single_flow / detail / preflight / action` 暴露成稳定 JSON
- `surface/service.py` 负责统一 DTO、timeline 合成和 single-flow 投影
- TUI controller 继续消费 `surface`
- Desktop main/preload/renderer 只通过 bridge 读写

## 本轮代码落点

### 1. shared surface 收口

本轮继续把 `butler_flow/surface/` 收口成当前现役 shared surface：

- `surface/service.py`
  - 统一 `workspace / manage / status / inspect / timeline / single_flow / detail / role_strip / operator_rail / flow_console`
  - 合并真实事件与 synthetic timeline
  - `single_flow_payload` 同时产出：
    - `summary`
    - `navigator_summary`
    - `supervisor_view`
    - `workflow_view`
    - `inspector`
    - `role_strip`
    - `operator_rail`
    - `flow_console`
    - 兼容 `surface.*` 包装
- `surface/dto.py`
  - 固化 `FlowSummaryDTO / FlowDetailDTO / SupervisorViewDTO / WorkflowViewDTO / ManageCenterDTO / RoleRuntimeDTO`
- `surface/queries.py`
  - 固化 summary / handoff / role chips 计算
- `tui/controller.py`
  - 继续按 shared surface 代理 payload

### 2. Python Desktop bridge

新增：

- `butler_main/butler_flow/desktop_bridge.py`

当前桥接命令：

- `python -m butler_main.butler_flow.desktop_bridge home`
- `python -m butler_main.butler_flow.desktop_bridge flow --flow-id <id>`
- `python -m butler_main.butler_flow.desktop_bridge detail --flow-id <id>`
- `python -m butler_main.butler_flow.desktop_bridge manage`
- `python -m butler_main.butler_flow.desktop_bridge preflight`
- `python -m butler_main.butler_flow.desktop_bridge action --flow-id <id> --type <action>`

当前裁决：

- stdout 只输出 JSON payload
- Desktop main process 通过 Python 子进程调用 bridge
- bridge 直接复用 `surface/service.py` 与 `FlowApp.apply_action_payload()`

### 3. Desktop 工程壳

新增目录：

- `butler_main/butler_flow/desktop/`

当前工程组成：

- Electron main:
  - `src/main/index.ts`
  - `src/main/window.ts`
  - `src/main/ipc/channels.ts`
  - `src/main/ipc/register-flow-workbench-ipc.ts`
  - `src/main/adapters/flow-workbench-adapter.ts`
  - `src/main/adapters/mock-flow-workbench-adapter.ts`
- preload:
  - `src/preload/index.ts`
- shared TS DTO / IPC:
  - `src/shared/dto.ts`
  - `src/shared/ipc.ts`
- renderer:
  - `src/renderer/App.tsx`
  - `src/renderer/components/navigation/FlowRail.tsx`
  - `src/renderer/components/app-shell/WorkbenchShell.tsx`
  - `src/renderer/components/workbench/SupervisorStream.tsx`
  - `src/renderer/components/workbench/WorkflowStrip.tsx`
  - `src/renderer/components/workbench/DetailDrawer.tsx`
  - `src/renderer/components/manage/ManageCenterShell.tsx`
  - `src/renderer/state/atoms/*`
  - `src/renderer/state/queries/*`
  - `src/renderer/styles/globals.css`
  - `src/renderer/styles/workbench.css`

## 当前 Desktop 产品面

当前 renderer 已具备：

- 左侧 `FlowRail`
  - config attach / switch
  - `Workspace / Workbench / Manage` 三段导航
  - flow 搜索与 runtime list
- 空态 config attach
  - 原生 `Select Butler Config`
  - 手填 `Config Path Fallback`
  - 允许在远程桌面 / xvfb / 原生文件对话框不可见时继续验证 workbench
- `Home`
  - 当前 focus 摘要
  - workbench 规则说明
- `FlowWorkbench`
  - center: supervisor stream
  - lower strip: workflow ribbon / handoff summary
  - right drawer: `summary / artifacts / runtime / roles`
  - topbar action:
    - refresh
    - pause
    - resume
    - retry
    - append instruction
- `Manage`
  - asset list
  - selected asset detail
  - role guidance / review checklist / manager notes

视觉方向固定为：

- `graphite + oxide copper + cold blue`
- `Space Grotesk + IBM Plex Sans + IBM Plex Mono`
- 不走 dashboard card grid
- 以 rail / stream / ribbon / drawer 作为主视觉结构

## 当前验证结果

### Python 回归

- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_surface.py butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py butler_main/butler_bot_code/tests/test_butler_flow_desktop_bridge.py -q`
- 结果：`28 passed`

### Desktop 工程验证

- `npm run typecheck`
- `npm run build`
- 结果：通过，已生成 `dist/main/`、`dist/preload/`、`dist/renderer/`

### Desktop 测试链补齐

- `npm run test:renderer`
- 结果：`4 passed`
- 覆盖：
  - 空态点击原生 config picker
  - 手填 config path attach 并加载 workspace flow
  - workbench `Pause` action 点击回归
  - manage center 资产详情渲染

- `npm run test:e2e`
- 结果：`2 passed`
- 覆盖：
  - Electron 真窗口启动 -> 手填 config path -> 打开 workbench
  - Electron 真窗口启动 -> 手填 config path -> 切到 manage center

- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_surface.py butler_main/butler_bot_code/tests/test_butler_flow_desktop_bridge.py -q`
- 结果：`4 passed`

当前 e2e 裁决补充为：

- Electron `BrowserWindow` 需显式 `sandbox: false`，确保 preload 能注入 `window.butlerDesktop`
- `npm run test:e2e` 会先 `build`，再优先使用当前 `DISPLAY`
- 若当前环境无图形显示，则自动回退到系统 `xvfb-run`；若系统未安装，但存在本地 `/tmp/butler-xvfb/root/usr/bin/xvfb-run`，也会自动接管
- Playwright 产物写入 `test-results/`，该目录不进入版本控制

## 当前剩余风险

当前剩余风险更新为：

- 原生文件选择器仍受宿主桌面环境影响；在远程桌面、无窗口管理器或虚拟显示环境下，`Select Config` 可能无法提供可见反馈
- 因此自动化测试与远程人工验证当前都应优先使用手填 `Config Path Fallback`
- 当前 e2e 验证使用 mock adapter，说明 Electron 壳、preload、IPC、renderer 点击链路已通；但对真实 Python sidecars 的全量资产覆盖，后续仍需要补更多 workspace 样本

因此当前结论更新为：

- **源码层面：已落地**
- **bridge 层面：已可用**
- **工程编译：已通过**
- **Electron runtime：已在 xvfb 环境下实际启动并完成点击回归**
- **真实 workspace 样本回归：仍需扩充**

## 后续接力建议

下一轮如果继续做 Butler Desktop，不要再回到纯规划，直接沿以下顺序：

1. 先扩充 real workspace fixture / 样本库，覆盖 running / paused / failed / no-asset / approval-required 等状态
2. 再补 real payload 的细节 polish：
   - artifact open 的 file-path 映射
   - action receipt 与 status toast 的细化
   - preflight / settings 面板
3. 再补 Desktop 侧自动刷新或 watcher 推送
4. 最后再视需要补 packaging / release

## 现役结论

从 `2026-04-03` 起，Butler Flow Desktop 的现役实现边界更新为：

- `butler_main/butler_flow/desktop/` 是 Desktop 壳真落点
- `butler_main/butler_flow/desktop_bridge.py` 是 Python bridge 入口
- `butler_main/butler_flow/surface/` 是 TUI/Desktop 共用 shared surface
- Desktop 不得绕过 bridge 直接读 sidecars
- Desktop 不得引入 `campaign/orchestrator mission/branch` 作为主对象
