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

## 当前剩余风险

当前唯一未完成的环境项是：

- `electron` npm postinstall 二进制下载在本机网络下出现 `socket hang up`

影响：

- 源码已完成编译与打包
- 但本轮无法在当前环境中完成 `npx electron --version` / `npm run start` 的最终运行验证

因此当前结论是：

- **源码层面：已落地**
- **bridge 层面：已可用**
- **工程编译：已通过**
- **Electron runtime 二进制：受当前网络下载中断影响，待环境恢复后二次验证**

## 后续接力建议

下一轮如果继续做 Butler Desktop，不要再回到纯规划，直接沿以下顺序：

1. 先解决 Electron binary 下载，完成 `npm run start`
2. 再补 real payload 的细节 polish：
   - artifact open 的 file-path 映射
   - action receipt 与 status toast 的细化
   - preflight / settings 面板
3. 再补 Desktop 侧自动刷新或 watcher 推送
4. 再视需要补 packaging / release

## 现役结论

从 `2026-04-03` 起，Butler Flow Desktop 的现役实现边界更新为：

- `butler_main/butler_flow/desktop/` 是 Desktop 壳真落点
- `butler_main/butler_flow/desktop_bridge.py` 是 Python bridge 入口
- `butler_main/butler_flow/surface/` 是 TUI/Desktop 共用 shared surface
- Desktop 不得绕过 bridge 直接读 sidecars
- Desktop 不得引入 `campaign/orchestrator mission/branch` 作为主对象
