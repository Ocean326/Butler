# Butler Chat

`butler_main/chat/` 是 Butler 前台对话链路的根入口目录。

当前职责：

- `app.py`：chat 独立 bootstrap / app 装配入口
- `ChatMainlineService`：前门主链编排
- `ChatRouter`：chat 路由判定
- `ChatRuntimeService`：chat 运行时
- `providers/`：chat 侧 prompt / memory provider 适配层
- `feishu_bot/`：chat 下的飞书接口层与 runner
- `weixi/`：chat 下的微信接口层，已接入 OpenClaw 官方安装/登录命令链，并已打通文本/图片/文件的真实发送链路
- `__main__.py`：根层 chat 启动入口

当前迁移策略：

- `butler_bot_code/` 继续承载 runtime/body 实现
- `butler_main/chat/` 作为产品层、app 层与入口层真源
- `chat` 先独立 bootstrap，再逐步把运行事实从 body 中抽出
- `chat` 前门只保留 `chat` / `mission_ingress` 两类入口，不再保留旧后台入口语义
- 新 channel 先按 `chat/<channel>/` 并列开接口层，再决定是否接入真实 transport
- `chat` 前台入口统一收敛到 `.venv\Scripts\python.exe -m butler_main.chat` / `butler_main/chat/engine.py`

当前渠道能力真源：

- `channel_profiles.py` 是 chat 的统一渠道能力真源，负责把 `cli` / `feishu` / `weixin` 以及 `weixi` / `wechat` 这类别名收敛成统一 profile。
- `ChatRouter.build_runtime_request()` 在前门把 `Invocation.channel` 解析为 `channel_profile`，后续 prompt、runtime、delivery 都消费同一份渠道事实。
- prompt 层通过 `【当前回复渠道】` 和渠道化 `【回复要求】` 告诉模型当前是在什么界面回复。
- runtime 层通过 `normalize_output_bundle_for_channel()` 把当前渠道不适合直接交付的 `cards/images/files` 收口掉，避免只靠 prompt 约束。
- 当前默认策略：
  - `cli`：文本优先
  - `feishu`：文本、图片、文件、更新式回复都可直接利用
  - `weixin`：文本优先，同时支持图片、文件；纯文本会收敛成更适合微信阅读的轻量排版

