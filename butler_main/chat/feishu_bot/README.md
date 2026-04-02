# Feishu Bot Layer

`chat/feishu_bot/` 是 chat 前台在飞书上的唯一现役接口层。

当前分层：

- `interaction.py`
  负责飞书事件归一化、消息文本/附件提取、card action payload 与 invocation metadata 编译。
- `dispatcher.py`
  负责长连接事件分发，把 message / card action 接到统一 `handle_message_async()`。
- `api.py`
  负责飞书 OpenAPI 调用：token、reply、push、图片/文件上传下载。
- `replying.py`
  负责 reply 降级策略：`interactive -> post -> text`，以及 markdown 图片引用处理。
- `delivery.py`
  负责 `OutputBundle -> DeliveryResult` 的 delivery adapter 合同。
- `presentation.py`
  负责 presentation callback facade。
- `runner.py`
  负责 chat 主线的 Feishu runner 装配。
- `transport.py`
  只保留兼容入口、message flow、长连接 loop、本地 CLI/repl 入口。

上线前建议至少做一次：

```bash
.venv\Scripts\python.exe -m butler_main.chat --config <your-config>.json --preflight
```

配置真源：

- 默认优先读取 `butler_main/chat/configs/<name>.json`
- 若新路径不存在，则兼容回退到 `butler_main/butler_bot_code/configs/<name>.json`
- 当前默认配置名仍是 `butler_bot`

检查点：

- `app_id / app_secret` 已配置。
- `workspace_root` 指向正确工作区。
- preflight 能拿到 tenant access token。
- 飞书机器人事件订阅已包含：
  `im.message.receive_v1`
  `card.action.trigger`
- 机器人权限已覆盖当前发送路径需要的消息、图片、文件能力。
- 目标环境已验证一条：
  文本 reply
  图片 reply
  文件 reply
  card action 回流

回归建议：

```bash
.venv\Scripts\python.exe -m unittest \
  butler_main.butler_bot_code.tests.test_chat_feishu_api \
  butler_main.butler_bot_code.tests.test_chat_feishu_replying \
  butler_main.butler_bot_code.tests.test_chat_feishu_input \
  butler_main.butler_bot_code.tests.test_chat_feishu_interaction \
  butler_main.butler_bot_code.tests.test_chat_feishu_runner
```

发送验收建议不要只看 `send/reply code=0`，要补一层飞书消息回读验证：

1. 发送后记录返回的 `message_id` 与 `chat_id`
2. 用 `GET /im/v1/messages/{message_id}` 确认单条消息可回读
3. 用 `GET /im/v1/messages?container_id_type=chat&container_id=<chat_id>` 确认最近聊天记录中能查到这条消息
4. 若验证 `handle_message_async()`，应记录真实 reply 产生的 `message_id`，而不是只验证 anchor message

仓库已内置一个手工验证脚本：

```bash
$env:PYTHONPATH="C:\Users\Lenovo\Desktop\Butler"
.venv\Scripts\python.exe butler_main/butler_bot_code/tests/manual/feishu_send_verify.py --cases direct,stream
```

脚本会做两类校验：

- `direct`
  发送 `text / post / interactive`，并对每条消息执行 `get_message + list_messages`
- `stream`
  通过 `handle_message_async()` 触发真实 reply，记录 reply `message_id`，再执行 `get_message + list_messages`

当前推荐的飞书上线前最小验收标准：

- `text / post / interactive` 发送成功
- 回读接口能通过 `message_id` 查到消息
- 最近聊天记录里能查到刚发送的消息
- `stream_final` 和 `stream_snapshot` 都能完成真实 reply 回读验证
