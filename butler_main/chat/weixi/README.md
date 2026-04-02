# Weixi

`chat/weixi/` 是 Butler 的微信接口层，当前覆盖三件事：

- 把微信 bridge / 微信样式 JSON 事件适配进 `chat` 主链
- 把 `OutputBundle` 组装成微信 bridge `ilink/bot/sendmessage` 请求体
- 在 client 侧按官方协议把本地图片/文件转换成真实可发送的媒体消息
- 提供本地 webhook bridge、扫码登录与二维码入口落盘工具

当前已闭环的是文本链路、图片/文件出站链路、bridge 协议对齐，以及 Butler 自己通过 bridge 扫码登录并长轮询收发消息。

## 本地 bridge

```bash
.venv\Scripts\python.exe -m butler_main.chat.weixi --serve-bridge
```

默认地址：

- `http://127.0.0.1:8789/weixin/webhook`

请求体接受 `message.content.text` 或 `item_list` 文本项，返回 Butler 结构化结果，并在 `weixin_protocol.sendmessage_requests` 中附带协议请求体。若回复 bundle 包含图片或文件，client 会先按官方协议上传媒体，再发送正式消息。

## 直连微信

```bash
.venv\Scripts\python.exe -m butler_main.chat.weixi --run-bridge-client --weixin-state-dir 工作区/weixin_state
```

这条命令会：

- 读取状态目录中的 `baseUrl` / `cdnBaseUrl`
- 调 bridge 获取二维码并等待扫码确认
- 登录成功后持续长轮询 `getupdates`
- 把 Butler 回复真正发回 `sendmessage`
- 若回复包含图片/文件，自动执行 `getuploadurl -> AES-128-ECB -> CDN upload -> sendmessage`

## 二维码入口

打印入口：

```bash
.venv\Scripts\python.exe -m butler_main.chat.weixi --official-print-qr-link
```

落盘入口：

```bash
.venv\Scripts\python.exe -m butler_main.chat.weixi --official-write-qr-link 工作区/weixin_state/weixin_qr_login.md
```

默认控制台地址：

- `http://127.0.0.1:18789/`

默认登录命令：

- `.venv\Scripts\python.exe -m butler_main.chat.weixi --run-bridge-client`

状态目录约定：

- 优先读取 `工作区/weixin_state/weixin.json`
- 兼容回退读取旧的 `openclaw_state/openclaw.json`
