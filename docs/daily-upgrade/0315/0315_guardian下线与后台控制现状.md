# 0315 guardian 下线与后台控制现状

更新时间：2026-03-15

## 这轮已经落地的变化

1. `guardian` 不再作为 Butler 运行时的必要守护链路。
2. `butler_bot` 主进程重新接管 `heartbeat` 与 `self_mind` 的启动和看护。
3. 对话窗口现在可以直接发运行控制指令，不需要再绕到 guardian。

## 当前后台真实结构

### 1. 主对话进程

- 入口：`butler_main/butler_bot_code/butler_bot/butler_bot.py`
- 职责：接收用户消息、调用 talk agent、回写 recent memory、处理显式后台控制命令

### 2. heartbeat

- 由 `MemoryManager.start_background_services()` 在主进程启动时直接拉起
- 独立子进程运行，主进程内置 watchdog 负责看护与自动重拉
- 当前运行目标：
  - planner：优先按配置走 `codex / gpt-5.2`
  - executor：默认走 `cursor / auto`

### 3. self_mind

- 由主进程内线程直接运行
- 当前已关闭脑-体循环，只保留 `talk / hold`
- 目标窗口使用 guardian 原来的那套飞书配置独立直发

## talk 现在可直接控制的后台动作

目前已支持这些直接口令：

- `重启后台`
- `重启心跳`
- `重启意识循环`
- `重启 self_mind`
- `停止心跳`

实现位置：

- `butler_main/butler_bot_code/butler_bot/butler_bot.py`
- `butler_main/butler_bot_code/butler_bot/memory_manager.py`

处理方式：

1. talk 收到消息后先走运行控制命令识别
2. 命中后不再进入普通任务推理
3. 直接由 `MemoryManager` 执行对应的 heartbeat / self_mind 生命周期操作
4. 返回简短回执给用户

## 当前运行现状

### heartbeat

- 新链路已生效
- 主进程日志已出现：
  - `已启动独立子进程 PID=...`
  - `心跳服务·看门狗 已启动`
  - `Butler 主进程已接管 heartbeat / self_mind`
- 最新 heartbeat 日志说明：
  - sidecar 已成功启动
  - 初始化消息已发出
  - 已进入实际 branch 执行与 heartbeat snapshot 产出

### self_mind

- 循环在正常跑，`mind_loop_state.json` 会持续刷新
- `mental_stream_20260315.jsonl` 中已确认出现过 `talk` 和 `self_mind_direct_talk_sent`
- 当前多数轮次仍然是 `hold`，原因不是链路坏，而是最近上下文里没有新用户输入、且上轮已说过，再开口会变成复读

## 现阶段的判断

### 已解决

- guardian 不再是后台运行前提
- 主进程已能本地拉起 heartbeat
- talk 已能直接重启 heartbeat / self_mind
- self_mind 已经具备真实主动发话能力，不再是纯 hold

### 仍需继续观察

- heartbeat planner 的 `codex / gpt-5.2` 链路虽然已经接上，但你刚刚单独修复过一次运行错误，这部分还需要继续看后续轮次是否稳定
- `manager.ps1 status` 的 PID 识别仍有旧状态残留问题，运行本身不影响，但状态展示偶尔会滞后

## 关键代码位置

- `butler_main/butler_bot_code/butler_bot/memory_manager.py`
- `butler_main/butler_bot_code/butler_bot/butler_bot.py`
- `butler_main/butler_bot_code/manager.ps1`

## 建议的下一步

1. 用一条真实消息测试 `重启心跳` 与 `重启意识循环` 回执是否符合预期
2. 连续观察 2 到 3 轮 heartbeat，确认 planner 侧稳定
3. 如果后续要继续收口架构，再把残留 guardian 相关“升级审批备案”文案和路径一起清掉
