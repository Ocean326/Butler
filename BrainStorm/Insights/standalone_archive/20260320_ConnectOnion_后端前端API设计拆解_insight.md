## ConnectOnion 后端 / 前端 / API 设计拆解 · Insight（2026-03-20）

- **来源/Raw 路径**：`BrainStorm/Raw/daily/20260320/20260320_xiaohongshu_agent_framework_shift_and_hidden_practices.md`
- **配套闪念**：`BrainStorm/Ideas/inbox/20260320_agent框架切换与最佳实践不在模型里.md`
- **代码依据**：本地仓库 `工作区/TargetProjects/connectonion`
- **整理日期**：2026-03-20

---

### 一、核心判断

- ConnectOnion 真正内置的，不是“完整 React 前后端产品”，而是一个 **Agent Host Runtime**：
  - 本地后端壳
  - 一套 HTTP / WebSocket 协议
  - 基于地址与签名的身份层
  - Relay 注册与发现层
  - 一个很薄的浏览器测试页
- 它宣传里的“内置前端”更准确地说，是：
  - 本地自带 `/docs` 静态交互页，方便调试
  - 线上有一个托管的 `chat.openonion.ai` 作为现成聊天前端
- 所以它省掉的主要不是“你完全不用做前端后端”，而是：
  - 你不用先自己设计 Agent host protocol
  - 不用自己从零搭实时事件流
  - 不用自己先做身份签名、session、relay、approval 这些运行时骨架

---

### 二、后端是怎么设计的

1. **后端不是 FastAPI，而是自写 raw ASGI**
   - `network/host/server.py` 里的 `host()` 负责把 agent factory、trust、session storage、relay 生命周期拼起来。
   - `network/asgi/__init__.py` 直接按 ASGI `http / websocket / lifespan` 三种 scope 分发。
   - `network/asgi/http.py` 和 `network/asgi/websocket.py` 手写路由与协议处理，没有依赖 Starlette / FastAPI。
   - 这说明它追求的是“Agent 协议控制权”和更薄的运行时，而不是传统 Web 框架生态。

2. **核心执行模型是 agent factory，而不是长驻单实例**
   - `host()` 接收的是 `create_agent`，每次请求新建一个 agent。
   - `routes.input_handler()` 每次调用 `create_agent()`，把 `agent.io` 和 `agent.storage` 注入进去，再执行 `agent.input(...)`。
   - 这个设计的好处是隔离强：带状态的工具不会轻易串台。
   - 代价是 agent 本体不是长驻 session actor，跨请求状态主要靠 session 数据结构和存储层恢复。

3. **长任务与实时交互走 WebSocket + 线程桥接**
   - `network/asgi/websocket.py` 在收到 `INPUT` 后，给 agent 配一个 `WebSocketIO`，再起线程跑 agent。
   - `network/io/websocket.py` 用两个 queue 把“同步 agent”与“异步 websocket”桥接起来。
   - 这意味着 ConnectOnion 没把 agent 重写成全异步 actor，而是保留同步编程模型，再在边界做适配。
   - 对 coding agent 这类大量同步工具调用的场景，这个折中很实用。

4. **Session 是后端里的第一等公民**
   - HTTP 和 WS 都支持 `session` 续聊。
   - `routes.input_handler()` 会把客户端 session 与服务端存储做 merge，然后把完整 `current_session` 存回去。
   - 输出时不只给最终文本，还回 `session` 和 `chat_items`。
   - 说明它不是把 API 当成“一问一答 RPC”，而是把它当成“可恢复对话 runtime”。

5. **信任与认证不在 Agent 内，而在 Host 边界**
   - `network/host/auth.py` 明确把签名验证和 trust decision 放在 host 层。
   - trust 支持 `open / careful / strict`，也支持自定义 policy / TrustAgent。
   - 这使 agent 逻辑和接入治理解耦，这一点非常对。

6. **Relay 是后端的重要组成，不是附属功能**
   - `server.py` 启动时会创建 relay lifespan。
   - `network/relay.py` 把 agent 注册到 `wss://oo.openonion.ai/ws/announce`，并通过 heartbeat 维持在线。
   - 所以它的“可聊天、可发现、可公网接入”能力，有一部分依赖官方 relay 基础设施。

---

### 三、前端是怎么设计的

1. **仓库里没有完整独立前端工程**
   - 本地仓库没有明显的 React / Next / Vite 应用。
   - 真正随代码提供的浏览器 UI 是 `network/static/docs.html`。
   - 这个页面更像 Swagger 风格调试台，而不是产品级聊天界面。

2. **本地前端非常薄，主要承担“协议观察器”角色**
   - `/docs` 页能测：
     - `POST /input`
     - `GET /sessions`
     - `GET /sessions/{id}`
     - `GET /info`
     - `GET /health`
     - `GET /admin/*`
     - `WS /ws`
   - 它还能拼 payload、展示 curl、读附件、打印 websocket 消息。
   - 本质是在帮开发者调 agent host，而不是在做真正的最终用户产品。

3. **正式聊天前端是外接的 `chat.openonion.ai`**
   - `README.md` 直接把 frontend 指向 `chat.openonion.ai`。
   - `network/host/server.py` 启动 banner 里会生成 `https://chat.openonion.ai/{address}`。
   - `cli/co_ai/main.py` 启动 `co ai` 时还会自动打开这个网页。
   - 也就是说，前端产品层和 SDK/runtime 层并不在一个 repo 里。

4. **前端与 agent 的耦合点是“事件协议”，不是组件库**
   - `WebSocketIO` 会自动给事件补 `id` / `ts`，明显是在照顾前端渲染。
   - `session_to_chat_items()` 把 session 转成前端友好的 `user / agent / tool_call` 列表。
   - `tool_approval`、`ui_stream`、`image_result_formatter`、`ulw` 都通过 `agent.io` 往前端发结构化事件。
   - 这说明它真正稳定下来的，是“前端消费什么事件”，而不是“前端长什么样”。

---

### 四、API 层是怎么设计的

1. **API 不是传统 REST 优先，而是“HTTP + WS 双轨”**
   - HTTP 负责：
     - `POST /input`
     - `GET /sessions`
     - `GET /sessions/{id}`
     - `GET /health`
     - `GET /info`
     - `GET /docs`
     - `GET /admin/logs`
     - `GET /admin/sessions`
   - WebSocket 负责：
     - 实时 trace
     - tool approval 往返
     - ask_user
     - onboarding
     - session 重连与恢复
   - 这比“纯 REST 聊天接口”更像一个 agent runtime protocol。

2. **协议核心是事件流，不是单一 response**
   - WS 消息里有 `INPUT / OUTPUT / ERROR / PING / PONG / ONBOARD_REQUIRED / ONBOARD_SUCCESS / ADMIN_*`。
   - 同时还夹带 `thinking / tool_call / tool_result / approval_needed / ask_user` 等 trace 事件。
   - 这说明 ConnectOnion API 的真正主语是“执行过程”，不是“最终答案”。

3. **身份模型用地址 + Ed25519 签名**
   - `auth.py` 里 `extract_and_authenticate()` 先验签，再走 trust decision。
   - `from` 是调用方地址，`payload.timestamp` 控 5 分钟有效期，`payload.to` 可校验目标 agent。
   - 这比 cookie / bearer token 更适合 agent-to-agent 和公网 relay 场景。

4. **但文档页与真实协议存在偏差**
   - `/docs` 页还写着：
     - `open` 可接受 unsigned
     - `careful` 如果有签名才校验
   - 但实现和测试都已经改成：
     - **所有请求都必须签名**
   - 这暴露了一个现实问题：它的“测试前端”不是协议真相，源码和测试才是。

5. **客户端侧也按“可直连优先、relay 兜底”设计**
   - `network/connect.py` 会先去 relay 查 agent endpoint。
   - 如果能解析到 agent 的直连地址，就直接连 `/ws`。
   - 否则退回 `wss://oo.openonion.ai/ws/input` 走 relay。
   - 这是一个很实用的网络层设计：先直连，失败再中继。

---

### 五、最值得 Butler 参考的 5 点

1. **把 Agent Host 当成独立 runtime 层**
   - Agent 本体、接入协议、认证/信任、实时 UI、session 恢复，不应该混在一坨应用代码里。

2. **用事件协议统一前端、终端、agent-to-agent**
   - 一套 `tool_call / tool_result / ask_user / approval_needed / complete` 事件，比多个零散接口更容易扩展。

3. **把 trust / approval 放在 Host 边界**
   - 这比让每个 agent 自己判断“能不能执行”更稳，也更可审计。

4. **把“直连优先，relay 兜底”做成默认网络策略**
   - 对跨机器、多环境、内网/公网切换都很友好。

5. **把 session 当作可恢复资产，而不是临时上下文**
   - 这对长任务、断线重连、UI 回放都很关键。

---

### 六、不建议直接照搬的 4 点

1. **前端不在同仓，容易让“内置前端”被高估**
   - 如果 Butler 想强调可控性，最好把最小生产前端也纳入自己的主仓或子仓编排。

2. **raw ASGI 虽薄，但维护门槛更高**
   - 协议完全自控是优点，但 debugging、生态复用、团队协作成本都会上来。

3. **每请求新建 agent 的模型不一定适合所有长期代理**
   - 对“长期人格 / 持久任务 / 常驻 browser session”型 agent，可能还需要 actor 化或 worker 常驻化。

4. **官方 relay 依赖意味着关键体验不完全自治**
   - 如果 Butler 后续也走这条路，最好尽早设计自托管 relay 或可替换 relay 抽象。

---

### 七、对 Butler 的直接启发

- Butler 可以抄的不是“ConnectOnion 的 UI 长相”，而是它把 Agent 工程问题压缩成一个 host runtime 的方式。
- 更具体地说，Butler 可以单独抽出一层：
  - `butler host`
  - `butler event protocol`
  - `butler trust / approval gateway`
  - `butler session recovery`
  - `butler relay / directory`
- 这样 Butler 的主循环、skills、subagent、memory 才会有一个更稳定的外部运行壳，而不是都挤在单一执行器框架里。

---

### 八、一句话结论

- ConnectOnion 的强项，不是“帮你做完前后端产品”，而是 **把 Agent 的接入层、实时协议层、信任层、发现层做成了现成 runtime**。这比单纯一个 prompt 框架更有参考价值。
