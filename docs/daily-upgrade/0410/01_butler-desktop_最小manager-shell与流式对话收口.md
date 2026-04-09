# 0410 Butler Desktop 最小 Manager Shell 与流式对话收口

日期：2026-04-10
状态：已落代码 / 已验证 / 当前真源
所属层级：Product Surface（主） / L1 `Agent Execution Runtime`（辅）
定位：暂时关掉当前 Desktop 壳中和这轮目标无关的模式，把前台收口成一个适合继续增量开发的最小 `Manager conversation shell`

关联：

- [0410 当日总纲](./00_当日总纲.md)
- [0409 Butler Desktop Codex 式 Manager Thread 前端升级计划与实施稿](../0409/01_butler-desktop_codex式manager-thread前端升级.md)
- [0403 Butler Flow Desktop 壳与 shared surface bridge 落地](../0403/03_butler-flow_desktop壳与shared_surface_bridge落地.md)
- [真源矩阵](../../project-map/03_truth_matrix.md)
- [改前读包](../../project-map/04_change_packets.md)

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 把 Desktop 当前前台壳临时收窄成最小 `Manager shell`，并补上 manager message 的流式对话体验。 |
| 所属层级 | Product Surface 主落，辅触 Desktop IPC / bridge。 |
| 当前真源文档 | `0410/00`、本稿、`0409/01`、`0403/03`。 |
| 计划查看的代码与测试 | `desktop/src/{renderer,main,preload,shared}`、desktop `typecheck / vitest / build`。 |

## 1. 本轮产品裁决

这轮不是继续把 Desktop 做成更完整的工作台，而是先反过来把壳层压缩。

前台正确的一级对象固定为：

- `Manager`

前台当前要临时退出主路径的对象包括：

- `Runtime`
- `Studio`
- `Agent detail`
- `code split pane`
- 其他强调工作台分区的卡片与条带

因此当前前台骨架固定为：

1. 左 rail
   - 品牌
   - `New thread`
   - history cards
2. 右侧主区
   - 薄 header
   - `Manager` 对话流
   - composer

## 2. 实施结果

### 2.1 Renderer 壳层

当前 renderer 已改成更小的双栏壳：

- 左 rail 只读 thread continuity
- 右侧只读 manager conversation

以下旧壳心智当前已从首屏与默认 render tree 退出：

- `Runtime / Studio` mode switcher
- snapshot cards
- runtime/studio inline strips
- agent detail sheet
- workbench 风格的多卡片主区

### 2.2 Conversation 组装

`manager-thread` 当前不再只被当作 block 列表展示，而是会在 renderer 内重新归一化成 chat-like message 序列：

- `payload.instruction` -> user bubble
- `payload.response / summary` -> manager bubble

这让同一份 shared surface 在不改 truth owner 的前提下，更适合作为真正的对话壳起点。

### 2.3 Manager 流式 IPC

Desktop 当前新增最小 manager stream 能力：

- 请求通道：`desktop:send-manager-message-stream`
- 事件通道：`desktop:manager-message-stream-event`
- preload API：
  - `sendManagerMessageStream(payload)`
  - `onManagerMessageEvent(listener)`

现阶段 stream 仍是“最小真实流式”：

1. main 侧先启动 request 并返回 `requestId`
2. adapter 复用现有 `sendManagerMessage`
3. 在拿到最终 response 后，按固定切片逐段发出：
   - `started`
   - `chunk`
   - `completed`
4. 若失败，则发：
   - `failed`

当前这层 stream 的目标是让右侧主对话成立，而不是定义新的 runtime 真语义。

## 3. 代码落点

本轮代码主要落在：

1. `desktop/src/renderer/App.tsx`
   - 收口为最小状态容器
   - 只保留 config attach、history 切换、new thread、manager streaming send
2. `desktop/src/renderer/components/mission-shell/MissionShell.tsx`
   - 改成左 rail + manager conversation 的最小 UI
3. `desktop/src/renderer/lib/mission-shell.ts`
   - 新增对话消息归一化 helper
4. `desktop/src/shared/ipc.ts`
   - 增加 manager stream 类型与 API
5. `desktop/src/preload/index.ts`
   - 暴露 stream invoke + event subscribe
6. `desktop/src/main/ipc/channels.ts`
   - 新增 `manager-message-stream` channels
7. `desktop/src/main/ipc/register-flow-workbench-ipc.ts`
   - 接起 requestId + event emit
8. `desktop/src/main/adapters/flow-workbench-adapter.ts`
   - 复用现有 send 能力生成最小 stream 事件
9. `desktop/src/renderer/App.test.tsx`
   - 改成最小 Manager shell 的 renderer 回归

## 4. 验收与验证

本轮通过标准固定为：

1. 用户进入 Desktop 后，首先看到的不是工作台，而是最小对话壳。
2. 左侧 thread rail 只服务 history continuity。
3. 右侧只保留 Manager 主对话。
4. 发送消息后，能看到真实 started/chunk/completed 驱动的流式更新。
5. 黑/日模式继续保留。
6. 这轮没有把 Desktop 改成新的 truth owner。

已执行验证：

1. `git diff --check`
2. `cd butler_main/products/butler_flow/desktop && npm run typecheck`
3. `cd butler_main/products/butler_flow/desktop && npm run test:renderer`
4. `cd butler_main/products/butler_flow/desktop && npm run build`
