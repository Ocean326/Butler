# Chat CLI / 飞书 / 微信链路梳理

## 目标

梳理 `butler_main/chat/` 当前三条前台链路：

- CLI
- 飞书
- 微信（`weixi` / OpenClaw bridge）

重点回答：

1. 现在是否已经有统一的“渠道无关”机制来表达文本、图片、文件、流式、更新式回复？
2. 飞书特有的“发图片 / 发文件”等能力，是否已经被系统化建模，还是仍然只是单渠道特例？
3. CLI、飞书、微信三条链路各自真正落到了哪一层？

---

## 一句话结论

`chat` 层已经有一套统一契约：`Invocation -> ChatRouter -> ChatRuntimeService -> OutputBundle / DeliverySession / DeliveryPlan`，理论上足够表达文本、卡片、图片、文件和回复目标。

但渠道落地不一致：

- 飞书：已经把这套契约基本执行到底，包含流式展示、图片下载、图片/文件回传、交互卡片更新。
- CLI：只走到了“统一运行时”，没有真正接入 `OutputBundle` 的多模态发送层，本质上还是终端文本呈现。
- 微信：已经有输入适配和 `DeliveryPlan` 规划，但当前 runner/bridge 主要是“生成 OpenClaw 官方请求 JSON”，真实 transport 仍未接通。

所以现状不是“没有统一设计”，而是“统一语义层已有，统一能力门控和统一交付执行层还没收口”。

2026-03-24 这轮又往前收了一步：`butler_main/chat/channel_profiles.py` 已经作为统一渠道能力真源接入前门、prompt 和 runtime。

- `ChatRouter.build_runtime_request()` 会先把 `cli` / `feishu` / `weixin` 以及 `weixi` / `wechat` 这类别名收敛成统一 `ChannelProfile`
- prompt 会显式注入 `【当前回复渠道】`，让模型知道自己当前是在 CLI、飞书还是微信里回复
- runtime 会在 `OutputBundle` 出站前做一次 `normalize_output_bundle_for_channel()`，把当前渠道暂不直接交付的 `cards/images/files` 收口掉

这意味着“渠道感知”不再只是文档里的建议，而是已经进入系统真链路。

---

## 公共骨架

### 1. 入口选择

`butler_main/chat/app.py`

- `ChatApp.run()` 会根据 `channel` 选择 runner：
  - `cli` -> `run_chat_cli`
  - `weixi/weixin/wechat` -> `run_chat_weixin_bot`
  - 默认 -> `run_chat_feishu_bot`
- `ChatApp` 统一携带三类能力开关：
  - `supports_images`
  - `supports_stream_segment`
  - `send_output_files`

这说明系统已经在 app 装配层承认“渠道能力不同”。

### 1.5 当前统一能力真源

`butler_main/chat/channel_profiles.py`

这层现在补上了一个更靠近“系统真源”的能力描述：

- `resolve_channel_profile(channel)`：把原始渠道名和别名统一收敛
- `render_channel_prompt_block(profile)`：给模型一个简洁的当前渠道说明
- `render_channel_reply_requirements(profile)`：给模型一个正向的交付取向
- `normalize_output_bundle_for_channel(bundle, profile)`：把当前渠道不应直接下发的输出类型收口掉

它的价值在于把“模型该怎么说”和“运行时最后能发什么”挂到同一份渠道事实上，而不是各自散着判断。

### 2. 前门主链

`butler_main/chat/mainline.py`

`ChatMainlineService` 做的事是：

1. 把渠道输入转成统一 `Invocation`
2. 通过 `ChatRouter` 生成 `ChatRuntimeRequest`
3. 调用 chat executor
4. 把结果封装为 `OutputBundle`
5. 如果知道渠道，则进一步生成对应 `delivery_plan`

这里的关键不是飞书或微信本身，而是：

- `Invocation` 是统一入站语义
- `OutputBundle` 是统一出站语义
- `DeliverySession` 是统一投递目标语义

### 3. 统一输出契约

`butler_main/agents_os/contracts/output.py`
`butler_main/agents_os/contracts/delivery.py`

当前统一契约已经能表达：

- 文本：`text_blocks`
- 卡片：`cards`
- 图片：`images`
- 文件：`files`
- 文档链接：`doc_links`
- 回复目标：`platform / mode / target / target_type / thread_id`

这意味着“飞书能发文件、CLI 不行”这种差异，原则上不该散落在业务层，而应体现在渠道 delivery adapter 的能力上。

### 4. 统一运行时如何产出 OutputBundle

`butler_main/chat/runtime.py`
`butler_main/chat/engine.py`

`ChatRuntimeService.execute()` 会：

- 调用模型
- 解析 `【decide】`
- 把 `decide.send` 路径转成 `OutputBundle.files`
- 把可见文本转成 `OutputBundle.text_blocks`

`engine.run_agent()` 会把本轮结果存进线程态：

- `turn_output_bundle`
- `turn_delivery_session`
- `turn_delivery_plan`

并通过：

- `run_agent.get_turn_output_bundle`
- `run_agent.get_turn_delivery_session`
- `run_agent.get_turn_delivery_plan`

暴露给渠道 runner。

这一步非常关键：它说明“统一输出层”不是概念，而是已经接在真实 `run_agent()` 返回链路上了。

---

## 三条链路能力对照

| 能力 | CLI | 飞书 | 微信 |
| --- | --- | --- | --- |
| 统一走 `engine.run_agent()` | 是 | 是 | 是 |
| 有渠道输入适配器 | 弱，主要靠本地参数注入 | 是 | 是 |
| 文本入站 | 是 | 是 | 是 |
| 图片入站 | 否 | 是，下载为本地图片路径 | 仅识别附件类型，未下载媒体 |
| 流式展示 | 是，终端增量文本 | 是，流式占位卡片 + update | 否 |
| 最终文本发送 | 是，终端输出 | 是 | 当前 bridge 仅返回 JSON，不直接发出 |
| 图片回传 | 否 | 是 | 只会生成官方 request plan |
| 文件回传 | 否 | 是 | 只会生成官方 request plan |
| `OutputBundle` 真正被消费 | 否 | 是 | 部分，主要用于生成 plan |
| `DeliverySession` 真正被消费 | 否 | 是 | 部分，主要用于生成 plan |
| update/finalize 语义 | 终端层自管，不走 delivery adapter | 已建模并部分落地 | 已建模但未接 transport |
| `supports_images` 等能力开关是否真实生效 | 否 | 是 | 否 |

---

## CLI 现状

### 入口

`butler_main/chat/cli/runner.py`

CLI 现在是一个完整的终端前端，支持：

- 单轮 prompt
- stdin 输入
- REPL 多轮
- 流式终端打印
- runtime event / status window

### 真正落地的能力

- `invocation_metadata["channel"] = "cli"`
- session 复用
- 增量文本展示
- runtime event 展示
- 回复后触发 `on_reply_sent`

### 没有落地的能力

CLI runner 一开始就把这些参数直接丢掉了：

- `supports_images`
- `supports_stream_segment`
- `send_output_files`

也就是说：

- CLI 当前没有“渠道能力门控”
- CLI 也没有消费 `OutputBundle.images/files`
- 即使 runtime 产出了文件或图片，CLI 不会走统一 delivery adapter

### 结论

CLI 当前是“统一运行时 + 终端文本渲染器”，不是“完整渠道 delivery 实现”。

如果以后想让 CLI 和飞书一样消费统一 `OutputBundle`，需要至少补一种 CLI 表达方式，例如：

- 文件：打印可点击路径
- 图片：打印本地路径或在终端内嵌预览提示
- doc link：专门格式化

---

## 飞书现状

### 入口与 transport

`butler_main/chat/feishu_bot/transport.py`
`butler_main/chat/feishu_bot/runner.py`
`butler_main/chat/feishu_bot/dispatcher.py`

飞书链路是当前最完整的一条。

它真正消费了三类 app 级开关：

- `supports_images`
- `supports_stream_segment`
- `send_output_files`

### 入站能力

`butler_main/chat/feishu_bot/interaction.py`
`butler_main/chat/feishu_bot/input.py`

飞书输入侧已经支持：

- 文本
- quote / rich text 抽取
- 图片 key 抽取
- 卡片动作回调

`transport.handle_message_async()` 在 `supports_images=True` 时，会下载消息图片并把本地 `image_paths` 传给 `run_agent_fn`。

### 出站能力

飞书有两条出站链：

#### 1. 新链：`OutputBundle -> FeishuDeliveryAdapter`

`butler_main/chat/feishu_bot/delivery.py`
`butler_main/chat/feishu_bot/presentation.py`
`butler_main/chat/feishu_bot/runner.py`

新链已经支持：

- 文本 reply / push
- 图片 upload + reply / push
- 文件 upload + reply / push
- `reply / update / push / finalize` 语义

也就是说，飞书已经把统一 `OutputBundle` 的：

- `text_blocks`
- `images`
- `files`

真正投递到真实平台接口上。

#### 2. 旧链：`【decide】 -> _send_output_files`

`butler_main/chat/feishu_bot/transport.py`

如果新链没有接管，旧链仍然会：

- 解析 `【decide】`
- 上传文件
- 回复到原消息，或按 `open_id` 私聊发送

这条链是历史兼容壳，目前仍在工作。

### 流式能力

飞书是当前唯一真正做了“平台侧流式表现”的渠道。

`transport.py` + `replying.py` 当前支持：

- 创建流式占位 interactive reply
- 持续 patch update 同一张卡片
- 最终收口为最终文本
- interactive 失败时回退到 post / text

### 结论

飞书已经不只是“能聊天”，而是当前 `chat` 体系里唯一真正贯通：

- 输入适配
- 统一 runtime
- `OutputBundle`
- 实际 transport delivery
- 流式更新

的完整渠道。

---

## 微信现状

### 入口

`butler_main/chat/weixi/runner.py`

当前微信 runner 只做三件事：

- `--serve-bridge`
- `--official-print-qr-link`
- `--official-write-qr-link`

并且显式丢弃了：

- `supports_images`
- `supports_stream_segment`
- `send_output_files`
- `on_reply_sent`
- `immediate_receipt_text`

这说明微信 runner 目前不是一个“完整聊天渠道 runner”，而是一个：

- OpenClaw 对接辅助入口
- 本地 webhook bridge 入口

### 入站能力

`butler_main/chat/weixi/input.py`

微信输入适配器已经能做：

- 文本抽取
- 附件类型识别：`image / file / video`
- 生成统一 `Invocation`
- 补齐 `weixin.message_id / receive_id / context_token / raw_session_ref`

但它目前只识别附件类型，不负责下载真实媒体文件，也没有把图片路径喂给模型。

### 出站规划能力

`butler_main/chat/weixi/delivery.py`
`butler_main/chat/weixi/official.py`

微信 delivery 层已经能把 `OutputBundle` 转成 OpenClaw 官方 `sendmessage` 请求：

- 文本 -> text item
- 图片 -> image item
- 文件 -> file item
- 视频 -> video item

从“规划语义”上看，它已经具备和飞书同级的 delivery plan 能力。

### 真正缺口

`WeixinDeliveryAdapter.deliver()` 只有在传入 `send_request_fn` 时才会实际发送。

而当前：

- `runner.py` 没有注入 `send_request_fn`
- `bridge.py` 也没有调用真实微信 transport

`bridge.process_weixin_webhook_event()` 现在做的是：

1. 调 `run_agent_fn`
2. 读取 `turn_output_bundle / turn_delivery_session / turn_delivery_plan`
3. 如无现成 plan，则现场生成 `WeixinDeliveryPlan`
4. 把 plan 和官方请求 JSON 原样返回给 HTTP 调用方

也就是说，微信当前更准确的定位是：

- 已有“输入适配 + 输出规划”
- 还没有“最终发送执行”

### 结论

微信链路目前处在“半接通”状态：

- 不是空白
- 也不是完整渠道

它已经能说明系统知道“微信可以发文本 / 图片 / 文件”，但这些能力还停留在 `DeliveryPlan` 层，没有落到 transport execution。

---

## 关于“飞书能发文件 / 图片，CLI 不行”这件事，系统里是否已有统一机制

### 已有的统一机制

有，而且已经不算薄：

1. `OutputBundle` 已统一表达文本、图片、文件。
2. `DeliverySession` 已统一表达回复目标与 delivery mode。
3. `ChatMainlineService` 已统一生成不同渠道的 delivery plan。
4. `engine.run_agent()` 已统一暴露本轮 bundle / session / plan。

### 还没有统一收口的地方

真正缺的是“渠道能力真源”。

当前能力差异散落在三种地方：

- `ChatApp` 上的三个布尔参数
- 各 runner 自己决定要不要消费这些参数
- 各 transport / adapter 自己决定能不能发图片文件

所以现状是：

- 有统一输出契约
- 没有统一能力注册表
- 没有统一的“渠道协商 / fallback”机制

例如：

- CLI 直接忽略 `send_output_files`
- 微信也直接忽略这三个能力开关
- 只有飞书真正消费了这套参数

---

## 现阶段最准确的架构判断

### 已经成立的部分

- `chat` 不再只是飞书脚本目录，已经有独立 app / router / runtime / mainline
- 渠道无关的前门语义已经建立
- 渠道相关的 input / delivery adapter 分层也已经建立

### 还没完全成立的部分

- 统一 `ChannelCapabilities` 真源还没有
- CLI 还没有基于 `OutputBundle` 的标准呈现器
- 微信还没有真实 transport executor
- 飞书还有“新 delivery 链 + 旧 decide 文件发送链”并存的历史包袱

---

## 建议的收口方向

### 1. 增加显式 `ChannelCapabilities`

建议不要继续靠三个松散布尔值传能力，改成类似：

- `can_receive_images`
- `can_stream_updates`
- `can_send_text`
- `can_send_images`
- `can_send_files`
- `can_update_message`
- `can_push_out_of_thread`

然后由：

- CLI runner
- 飞书 runner
- 微信 runner

统一声明。

### 2. 让 CLI 也消费 `OutputBundle`

哪怕不做真正多模态，也应至少做：

- `text_blocks` -> 终端文本
- `files` -> 打印路径
- `images` -> 打印路径或预览提示
- `doc_links` -> 专门格式化

这样 CLI 才算真正进入统一 delivery 体系。

### 3. 微信需要把 plan 和 execute 分开收口

微信现在已经有：

- `InputAdapter`
- `DeliveryPlan`

下一步缺的是二选一：

- 要么在 Butler 内部真正执行 `send_request_fn`
- 要么明确把 Butler 定位成“只输出官方请求，由外部 OpenClaw transport 执行”

否则当前 bridge 会一直停留在“看起来能发，实际上只是在回 JSON”。

### 4. 飞书需要清理旧文件发送壳

现在飞书同时有：

- 新 `OutputBundle` delivery
- 旧 `【decide】 -> _send_output_files`

建议最后保留一套，避免双轨长期并存。

---

## 当前真源结论

如果只看当前仓库代码真源，可以把三条链路概括成：

- CLI：统一 chat runtime 的终端壳，文本强，delivery 弱。
- 飞书：当前唯一完整贯通的生产级前台渠道。
- 微信：已完成统一输入和统一输出规划，但真实 transport 仍未落地。

---

## 验证

已跑针对本次梳理直接相关的测试：

```powershell
python -m pytest butler_main/butler_bot_code/tests/test_chat_cli_runner.py `
  butler_main/butler_bot_code/tests/test_chat_feishu_runner.py `
  butler_main/butler_bot_code/tests/test_feishu_delivery_adapter.py `
  butler_main/butler_bot_code/tests/test_chat_weixin_bridge.py `
  butler_main/butler_bot_code/tests/test_chat_weixin_input.py `
  butler_main/butler_bot_code/tests/test_talk_mainline_service.py -q
```

结果：

- `15 passed`
