---
type: "note"
---
# 01C Chat CLI 入口计划

日期：2026-03-23
时间标签：0323_chat_cli入口
状态：规划中

## 目标定位

这份计划专门回答一件事：

**在 `chat` 体系里新增一个正式的命令行入口，使其与飞书 / 微信同属前台 channel，能够共享 Butler 的对话上下文，并且在终端里直接看到底层 CLI 的流式输出。**

它不是：

1. 飞书 transport 里的隐藏本地测试分支
2. 只会单轮 `--prompt` 的临时脚本
3. 一个脱离 `chat` 主链、只在本机自嗨的小壳

它必须是：

1. `chat/<channel>/` 体系中的正式 channel
2. 可持续使用的命令行 frontdoor
3. 对用户可交互、可观察、可继续对话的入口

## 为什么现在要单独做这条线

当前 `chat` 的正式前门实际上只有：

1. `feishu`
2. `weixi`（仍未完成 transport 绑定）

而所谓“命令行模式”目前只是飞书 runner 里的一段隐藏分支，存在三个明显问题：

1. 语义不对
   它挂在飞书 transport 下，不是独立 channel。
2. 上下文不稳
   当前本地调用默认容易落成 `local + 随机 session`，不具备明确的跨入口连续性表达。
3. 流式呈现不完整
   代码虽然支持 runtime streaming，但本地入口没有把流式内容稳定地直接呈现在终端。

所以这一条不能再当成“顺手补个 REPL”，而要按正式入口来设计。

## 设计目标

### G0 入口地位

CLI 入口要和飞书 / 微信并列，而不是从属它们。

目标形态：

1. `python -m butler_main.chat.cli`
2. `chat.app` 能识别 `channel="cli"`
3. `chat/__init__.py` 能导出对应 bootstrap

### G1 上下文共享

CLI 入口必须共享 Butler chat 的真实上下文，不做孤岛。

这里的“共享上下文”至少包含三层：

1. 共享同一套 prompt / memory / runtime 主链
2. 共享 recent / local memory / 用户画像等长期事实
3. 对会话连续性有明确 session 策略，而不是每轮随机 session

### G2 交互性

CLI 入口不是一次性执行器，而是可以持续对话的交互入口。

至少要支持：

1. 单轮 prompt
2. REPL 多轮对话
3. 会话连续
4. 退出、重开、继续会话

### G3 流式呈现

每次对话时，终端中要直接可见底层 CLI 的流式输出。

不是：

1. 只在日志里有流式片段
2. 内部走 streaming，但终端最后一次性打印 final
3. 让用户看不到“正在生成”的过程

而是：

1. 用户发出消息后，终端立即进入生成态
2. 内容按流式片段持续刷新
3. 结束时自然收口为最终答复

### G4 呈现信息

CLI 不只是“把文本吐到 stdout”，还要把必要的状态信息呈现清楚。

至少应包括：

1. 当前会话 id / 会话名
2. 当前 runtime CLI
3. 当前模型
4. 本轮是否开启 streaming
5. 本轮是否命中了 runtime control

## 功能边界

### 本轮应做

1. 正式 CLI channel 入口
2. 单轮与 REPL 两种使用方式
3. 共享 chat 主链上下文
4. 终端流式输出
5. 基础会话与状态呈现
6. 明确的帮助信息与参数

### 本轮不强求

1. 多模态图片上传
2. 复杂 TUI
3. 富文本卡片级渲染
4. 与微信 transport 的双向联动
5. 终端里完整重建 FeishuDelivery 的所有表现

### 明确不应该做的事

1. 再把 CLI 入口埋回 `feishu_bot.transport`
2. 继续使用“本地模式只是测试模式”的口径
3. 为了赶进度，把 session 继续做成每轮随机
4. 为了图省事，只在最终结果返回后一次性打印

## 用户体验要求

### 基础交互

进入 CLI 后，用户应能看到清晰头部信息，例如：

1. 这是 Butler Chat CLI
2. 当前会话名 / 会话 id
3. 当前默认 runtime CLI / model
4. 常用退出命令

### 输入体验

建议支持：

1. `你> ` 作为输入前缀
2. `管家> ` 作为回复前缀
3. 空输入跳过
4. `exit / quit / /exit` 退出

### 流式回复体验

建议标准为：

1. 用户发出一轮后，立即显示 `管家> `
2. 后续流式片段直接接在这行后面
3. 流式结束后补换行
4. 若发生重写型 snapshot，不允许终端出现大段重复堆叠

### 状态提示

至少应提供：

1. 会话已加载哪个 config
2. 本轮实际使用的 CLI / model
3. 切模型 / 切 CLI 是否生效
4. 错误时给出明确失败原因

## 上下文共享设计

### 原则

CLI 与飞书 / 微信共享的是 **chat runtime context**，不是“把所有 channel 混成一个 session”。

因此要拆成两层：

1. 全局共享层
   recent memory / local memory / 用户画像 / workspace 上下文
2. 会话层
   每个 channel / thread 自己有稳定 session identity

### 需要解决的当前问题

当前 `ChatMainlineService.build_invocation()` 在本地路径下如果不给定 `session_id`，会生成随机值。

这会导致：

1. CLI REPL 多轮之间 session 不稳定
2. 无法可靠表达“这是同一段命令行会话”
3. 后续若要做恢复 / 续聊会很别扭

### 建议口径

CLI 入口应至少支持两种 session 模式：

1. 临时会话
   启动时生成一次 `cli_session_<id>`，整个 REPL 生命周期固定使用
2. 指名会话
   用户可显式指定 `--session <name>`，用于恢复或继续某段命令行会话

### 与飞书 / 微信共享的含义

“共享上下文”在实现上应理解为：

1. 仍然走同一个 `ChatMainlineService`
2. 仍然走同一个 `ChatRuntimeService`
3. 仍然使用同一个 memory provider
4. invocation 的 `channel` 改为 `cli`
5. invocation 的 `session_id` 由 CLI runner 稳定提供

这样做的结果是：

1. CLI 会继续使用 Butler 的长期记忆与 recent 事实
2. 但 CLI session 与飞书 thread 不会错误地硬绑成同一个 thread id
3. 后续若要做跨 channel 观察与诊断，也能明确看出来源 channel

## 流式输出设计

### 当前问题

`engine.run_agent()` 虽然已经支持 `stream_callback`，但目前本地入口没有把它做成真正的终端流式体验。

核心缺口是：

1. 没有正式的 stream printer
2. 没有 snapshot 去重 / 增量输出策略
3. 没有 final 收口策略

### 设计要求

CLI runner 需要一个专门的 terminal stream adapter。

它至少应做到：

1. 接收 runtime 流式片段
2. 识别增量 vs snapshot
3. 尽量只向终端输出新增部分
4. 在 final 时避免重复打印整段答案

### 呈现策略

建议采用：

1. 默认直接文本流
2. 不做复杂全屏刷新
3. 仅做最小增量输出
4. 最终答案以已经流出的内容为主，必要时补尾差量

原因很明确：

1. 这比全屏 TUI 稳
2. 这比不断重画一整段文本简单
3. 这能最快给用户“看得到正在生成”的反馈

## 信息呈现设计

CLI 入口应把“运行事实”显式展示出来，而不是只吐答案正文。

建议分三层呈现：

### 层 1：启动信息

展示：

1. 当前 config 路径
2. workspace_root
3. session id
4. 当前默认 CLI / model

### 层 2：每轮前提示

在用户回车后，立即输出本轮摘要：

1. route
2. cli
3. model
4. stream on/off

### 层 3：异常与回执

遇到异常时，终端需要明确区分：

1. 配置错误
2. runtime CLI 不可用
3. 模型调用失败
4. 中断退出

## 参数设计建议

CLI 入口建议至少提供以下参数：

1. `--config/-c`
   指定配置文件
2. `--prompt/-p`
   单轮执行
3. `--stdin`
   从标准输入读入单轮 prompt
4. `--session`
   指定会话 id / 会话名
5. `--stream`
   显式启用流式输出
6. `--no-stream`
   显式关闭流式输出
7. `--preflight`
   只检查配置与 runtime 目标

建议默认行为：

1. 无 `--prompt` 时进入 REPL
2. REPL 默认开启 streaming
3. 单轮模式默认也开启 streaming

原因：

1. 用户已经明确要求“每次对话可看到 cli 的流式输出”
2. 把 streaming 做成默认更符合 CLI 入口定位

## 模块落点建议

建议新增：

1. `butler_main/chat/cli/__init__.py`
2. `butler_main/chat/cli/runner.py`
3. `butler_main/chat/cli/__main__.py`

并同步调整：

1. `butler_main/chat/app.py`
2. `butler_main/chat/__init__.py`
3. `test_chat_app_bootstrap.py`
4. 新增 `test_chat_cli_runner.py`

## 运行链路建议

目标链路应是：

`chat.cli.__main__`
-> `create_default_cli_chat_app()`
-> `ChatApp(channel="cli")`
-> `chat/cli/runner.py`
-> `chat_engine.run_agent(..., invocation_metadata={"channel": "cli", "session_id": ...}, stream_callback=...)`
-> `ChatMainlineService`
-> `ChatRuntimeService`
-> `memory / prompt / runtime executor`

这条链路的重要意义是：

1. CLI frontdoor 与飞书 frontdoor 共享 body
2. CLI 不再借飞书 transport 才能活
3. streaming 在 CLI runner 自己名下完成

## 分阶段实施

### Phase 1 正式入口化

目标：

1. 新建 `chat/cli` 包
2. 提供 `python -m butler_main.chat.cli`
3. `app` 层认识 `cli` channel

验收：

1. 可启动 CLI 入口
2. 可单轮执行
3. 可进入 REPL

### Phase 2 会话与上下文稳定化

目标：

1. CLI session 稳定
2. 支持 `--session`
3. 同一 REPL 生命周期复用同一 session

验收：

1. 同一 REPL 多轮 invocation 使用同一 session id
2. recent / memory 持续可见
3. 不再出现每轮随机 session

### Phase 3 流式呈现补齐

目标：

1. 终端直接显示 stream
2. 支持 snapshot 去重
3. final 自然收口

验收：

1. 对话过程中终端持续可见输出增长
2. 不出现整段重复刷屏
3. 最终结果与流式内容一致

### Phase 4 呈现与可观察性补齐

目标：

1. 启动信息清晰
2. 每轮 runtime 信息可见
3. 错误信息可读

验收：

1. 用户能看出本轮到底用的哪个 CLI / 模型
2. 错误时知道该修哪里
3. `--help` 可自解释

## 测试与验收建议

### 单测

至少应补：

1. `app` 能路由到 `cli` runner
2. `create_default_cli_chat_app()` 正常装配
3. CLI runner 单轮模式会传入稳定 `channel/session`
4. CLI runner REPL 模式会复用同一 session
5. stream printer 对 snapshot 增量处理正确

### 手工验收

至少跑三类：

1. `python -m butler_main.chat.cli --prompt "你是谁"`
2. `python -m butler_main.chat.cli`
3. `python -m butler_main.chat.cli --session test_shared_context`

手工验收重点不看“有没有跑起来”而看：

1. 有没有 streaming
2. session 是否稳定
3. recent / memory 是否延续
4. runtime 信息是否看得见

## 风险点

### R1 流式片段并非纯增量

底层 CLI 很可能给的是 snapshot，而不是严格 delta。

因此必须提前设计：

1. 增量提取
2. 重复抑制
3. final 补尾

### R2 共享上下文不等于混 session

如果把 CLI 和飞书强行绑定到同一个 session id，会造成 thread 语义混乱。

因此必须明确：

1. 共享 memory truth
2. 保留 channel/session 分层

### R3 继续沿用飞书 transport 本地分支会拖脏边界

如果偷懒继续复用 `feishu_bot.transport` 的本地测试模式，最终会导致：

1. CLI 入口语义继续不清
2. 参数设计继续受飞书牵制
3. streaming 逻辑和飞书 transport 再次缠死

## 最终口径

这条 CLI 计划的正确产品定义应固定为：

**Butler Chat 的第三个正式前台入口。**

它与飞书 / 微信并列，复用同一套 chat 主链与记忆体系，但拥有自己明确的：

1. channel 身份
2. session 策略
3. 终端交互语义
4. 流式呈现方式

## 本计划的完成判据

当以下条件同时满足，才算这条计划完成：

1. 仓内已有正式 `chat/cli` 入口，而不是飞书隐藏 REPL
2. CLI 多轮对话共享 Butler chat 上下文
3. 每轮终端可直接看到底层 CLI 的流式输出
4. 用户能看清本轮运行的 CLI / model / session 信息
5. 对应测试与最小手工验收路径已经存在
