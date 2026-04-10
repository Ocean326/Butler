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

### 2.4 Codex 式静态布局再收口

在最小 shell 成立后，本轮继续把静态骨架往 Codex 方向收紧：

- 左 rail history cards 改成两行轻卡，只保留题目、时间、状态
- 右侧 header 只保留题目、工作目录、状态
- 对话列与 composer 同宽居中，composer 常驻底侧
- Manager 输出占满对话列宽，用户消息右对齐并压到约 3/4 宽

这轮目标不是新增功能，而是先把“第一眼像一个会长期使用的对话产品”这件事做稳。

### 2.5 parse-failed 聊天正文净化

这轮同时修了一个真实产品 bug：

- 过去 manager parse-failed 时，`normalize_manage_chat_result()` 会把 raw non-JSON reply 直接写进 `response`
- `surface/service.py` 又会把 `response / error_text` 直接投影成 Desktop manager block
- 结果是 Desktop 会把 `failed to open state db`、plugin sync/network error 等原始 Codex 日志显示成聊天正文

当前现役收口改为：

1. 新生成的 parse-failed turn：
   - `response / summary` 统一改成紧凑失败说明
   - `raw_reply / parse_status / session_recovery.initial_raw_reply` 继续保留
2. 已落盘的旧脏 turn：
   - surface 投影时也会二次净化，不再把旧 raw log 直接显示到 Desktop 对话

因此这轮不是纯前端遮挡，而是 manager surface 的真实语义修复。

补充根因裁决：

- 当前发现 manager chat 与 flow runtime 之前并不对称
- flow runtime 已经会给 Codex 准备 workspace-local `codex_home`
- manager chat 则直接落回全局 `~/.codex`
- 当全局 `~/.codex/state_5.sqlite` 与本机 Codex 版本出现 migration 差异时，就会在 manager chat 首轮直接吐出 `failed to open state db` 等原始日志，最终触发 parse failure

因此本轮还补上了 manager chat 的独立 `codex_home` 与 flow 同步的 MCP disable overrides，避免它继续吃全局状态与远程 MCP 噪声。

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
10. `butler_main/products/butler_flow/manage_agent.py`
   - parse-failed 时不再把 raw non-JSON reply 塞回用户可见 `response`
11. `butler_main/products/butler_flow/surface/service.py`
   - manager turn 投影时统一净化 parse-failed 正文，并保留 `raw_reply`
12. `butler_main/butler_bot_code/tests/test_butler_flow.py`
   - 回归 parse-failed 持久化与 pending_action 保留
13. `butler_main/butler_bot_code/tests/test_butler_flow_surface.py`
   - 回归旧脏 turn 在 Desktop surface 中不会再显示原始 Codex 日志

## 4. 验收与验证

本轮通过标准固定为：

1. 用户进入 Desktop 后，首先看到的不是工作台，而是最小对话壳。
2. 左侧 thread rail 只服务 history continuity。
3. 右侧只保留 Manager 主对话。
4. 发送消息后，能看到真实 started/chunk/completed 驱动的流式更新。
5. 黑/日模式继续保留。
6. 这轮没有把 Desktop 改成新的 truth owner。
7. 旧 manager thread 中若含 parse-failed turn，Desktop 聊天正文也不能再直接显示 raw Codex 日志。

已执行验证：

1. `git diff --check`
2. `cd butler_main/products/butler_flow/desktop && npm run typecheck`
3. `cd butler_main/products/butler_flow/desktop && npm run test:renderer`
4. `cd butler_main/products/butler_flow/desktop && npm run build`
5. `./.venv/bin/pytest butler_main/butler_bot_code/tests/test_butler_flow.py -k parse_failure_preserves_pending_action`
6. `./.venv/bin/pytest butler_main/butler_bot_code/tests/test_butler_flow_surface.py`
7. 重启 `butler_main/products/butler_flow/desktop` Electron Desktop 复验运行态
