# Butler-flow Desktop V1 PRD + 页面线框 + 技术栈与目录结构

- 日期：2026-04-02
- 文档类型：PRD / 信息架构 / 页面线框 / 技术方案
- 适用范围：**仅 Butler-flow**
- 不包含：campaign、heartbeat、chat 主入口、全局系统总控台、通用记忆浏览器
- 当前产品前提：
  - Butler-flow 的默认主体不是单 agent，而是 **flow**。
  - 现阶段由 **supervisor** 作为顶级流。
  - **manager** 作为 template 选择与 flow 创建入口。

---

## 0. 文档目标

本文件用于收束一版 **Butler-flow Desktop V1** 的产品与技术方案，目标是：

1. 明确 Butler-flow 桌面端的产品定位。
2. 明确页面结构与关键交互。
3. 明确 V1 范围与不做项。
4. 明确技术栈、前后端分层与目录结构。
5. 作为后续使用 Codex / 本地工程代理执行开发时的单一实施参考。

---

## 1. 产品定位

## 1.1 一句话定位

**Butler-flow Desktop V1 = ChatGPT / Codex 风格的 Flow Chat Workbench。**

它不是：
- 一个普通聊天软件
- 一个纯 DAG / BPMN 图编辑器
- 一个覆盖全 Butler 系统的总控台

它是：
- 左侧 **flow 列表**
- 右侧 **supervisor 主 flow 的对话式流式展示**
- 消息流中嵌入 **child session / child agent / artifact / approval / status** 卡片
- 允许从顶级 flow 中点击进入 flow 内部子 session / agent / run

## 1.2 对齐对象

### 对齐 Proma
吸收其：
- Electron 桌面应用壳层
- 本地优先思路
- 多面板高信息密度
- 右侧状态 / 活动区
- 工作区概念

### 对齐 Codex
吸收其：
- 会话式工作台交互
- 执行过程可见性
- 子执行单元并行与可点击深入
- 桌面 app / 本地 agent 工作台气质

### Butler-flow 的独特点
保留并突出：
- flow-first，而非 agent-first
- supervisor 顶级流
- manager 作为 template + create flow 入口
- 子 session / 子 agent / 子 run 的层级导航
- flow contracts（verification / approval / recovery）

---

## 2. 范围定义

## 2.1 V1 必做范围

1. Flow 列表
2. 新建 Flow（通过 manager + template）
3. Supervisor 主 session 对话式视图
4. Child session / child agent / run 卡片展示
5. Active children 托盘
6. 子 session / 子 agent 的点击进入
7. Detail Drawer（Route / Contracts / Inputs / Runtime / Events）
8. Flow 级流式更新（SSE / WebSocket）

## 2.2 V1 不做范围

1. 不做 chat-first 主入口
2. 不做 heartbeat / campaign / memory / governor 总控页
3. 不做全局知识或长期记忆编辑器
4. 不做飞书远程入口
5. 不做复杂的多人协作
6. 不做可视化 DAG 拖拽编排器
7. 不做数据库重构

---

## 3. 用户故事

## 3.1 新建一个 flow

作为用户，我希望：
- 点击“新建 Flow”
- 看到 manager 提供的模板列表
- 选择模板并填写必要初始化信息
- 创建成功后直接进入该 flow 的 supervisor 主 session

## 3.2 在 supervisor flow 中观察与推进任务

作为用户，我希望：
- 在右侧看到 supervisor 的流式响应
- 看到本轮计划拆解
- 看到新创建的 child session / child agent / run 卡片
- 在不离开主 flow 的情况下感知整体进展

## 3.3 深入某个子 session / 子 agent

作为用户，我希望：
- 在 supervisor 主 flow 中点击某个 child card
- 进入对应的子 session / 子 agent 页面
- 顶部 breadcrumb 清楚告诉我当前所在层级
- 可以再返回 supervisor 主 flow

## 3.4 检查某次执行的高级细节

作为高级用户 / 开发者，我希望：
- 打开 detail drawer
- 查看 route、runtime、contracts、result_ref、events
- 知道这一轮为什么这样路由、用谁执行、卡在哪、输出了什么

---

## 4. 设计原则

1. **flow-first**：UI 命名和信息组织必须围绕 flow，而不是默认围绕 agent。
2. **对话主视图**：主视图是会话流，不是全时间显示 DAG 图。
3. **层级可钻取**：从 supervisor -> child session -> child agent -> run 必须可导航。
4. **状态显式化**：running / waiting / blocked / completed / failed 必须直接可见。
5. **真源不迁移**：桌面端不发明新的业务真源。
6. **本地优先**：优先复用现有本地 flow / session / event / artifact 数据。
7. **轻改后端，重做前台表达**：V1 重点是桌面表达层，不是重写 flow 引擎。

---

## 5. 信息架构

## 5.1 一级结构

- Flows
- Templates
- Current Flow Session
- Active Children Tray
- Detail Drawer

## 5.2 核心对象映射

### 产品层对象
- Flow
- Supervisor Session
- Child Session
- Child Agent
- Run
- Artifact
- Approval
- Event

### 与现有 Butler-flow 实现的映射
- Flow ≈ mission
- Child Session / Child Agent / Run ≈ node / branch / workflow_session 的产品化表达
- Detail Drawer 的高级信息来源于 workflow_ir、runtime_debug、events 等

---

## 6. 页面设计

## 6.1 页面一：Flow Home / 主工作台

### 目标
作为默认首页，承载：
- 左侧 flow 列表
- 中间当前 flow 主 session
- 底部 active children tray
- 右侧 details drawer（按需展开）

### 结构
- 左侧 Sidebar
- 主内容区 Session Stream
- 底部 Active Children
- 右侧 Drawer

---

## 6.2 页面二：Template Picker

### 目标
作为 manager 入口：
- 查看 template 列表
- 选择模板
- 配置初始化参数
- 创建 flow

### 展示内容
- template name
- template summary
- recommended scenario
- required fields
- create button

---

## 6.3 页面三：Child Session / Agent Detail View

### 目标
承载被点击进入的子 session / 子 agent。

### 结构
- 顶部 Breadcrumb
- 中间该 session 的流式会话内容
- 底部该 session 的 children tray
- 右侧 details drawer

---

## 6.4 页面四：Artifacts / Results Panel（V1 可为 Drawer Tab）

### 目标
展示：
- result_ref
- output docs
- patch / report / summary
- open / copy / reveal in folder

V1 可先不做独立页，先作为 drawer tab。

---

## 7. 页面线框（低保真）

## 7.1 主工作台线框

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Butler-flow Desktop                                                         │
├──────────────┬──────────────────────────────────────────────┬───────────────┤
│ Flows        │  Breadcrumb: Flow / Transfer_Recovery        │  Details      │
│              │──────────────────────────────────────────────│  (drawer)     │
│ + 新建 Flow  │ [User] 展示一下你的 subagent / flow 能力...  │               │
│              │                                              │  Tab: Route   │
│ 运行中       │ [Supervisor] 我会做一个小型 flow 演示...     │  Tab: Runtime │
│ - Transfer   │                                              │  Tab: Inputs  │
│ - Research   │ [Planning Card]                              │  Tab: Events  │
│              │ - create 3 child sessions                    │  Tab: Contract│
│ 最近         │ - inspect repo / run checks / summarize      │               │
│ - Flow A     │                                              │               │
│ - Flow B     │ [Child Card] analysis-session-03   running   │               │
│              │ [Open]                                        │               │
│ Templates    │                                              │               │
│ - Recovery   │ [Child Card] critic-agent          waiting   │               │
│ - Research   │ [Open]                                        │               │
│ - Delivery   │                                              │               │
│              │ [Status Card] 2/3 children completed         │               │
│              │                                              │               │
│              │ [Artifact Card] report.md                    │               │
│              │                                              │               │
│              │ Ask follow-up / continue this flow...        │               │
├──────────────┴──────────────────────────────────────────────┴───────────────┤
│ Active Children: session-03 | critic-agent | implement-run-12 [Open]       │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 7.2 Template Picker 线框

```text
┌──────────────────────────────────────────────────────────────┐
│ Create Flow                                                  │
├──────────────────────────────────────────────────────────────┤
│ Templates                                                    │
│                                                              │
│ [Recovery]      恢复 / 转移 / 排障类流程模板        [Select] │
│ [Research]      调研 / 汇总 / 评估类流程模板        [Select] │
│ [Delivery]      工程实现 / patch / 验收类模板      [Select] │
│                                                              │
│ Selected Template: Recovery                                  │
│ - title: [____________________]                              │
│ - goal:  [____________________]                              │
│ - constraints: [____________________]                        │
│                                                              │
│ [Cancel]                                       [Create Flow] │
└──────────────────────────────────────────────────────────────┘
```

## 7.3 Child Session 线框

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Recovery / Transfer_Recovery / analysis-session-03              │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Session Summary Card]                                                      │
│ [Agent Card] critic-agent                                                    │
│ [Status Card] waiting for input                                              │
│ [Run Card] implement-run-12 completed                                        │
│                                                                              │
│ Ask follow-up / continue this child session...                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Active Children: critic-agent | implement-run-12                             │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 关键交互设计

## 8.1 新建 Flow

1. 点击左侧 `+ 新建 Flow`
2. 打开 Template Picker
3. 选择 template
4. 填写初始化参数
5. 调用 create flow API
6. 自动进入新建 flow 的 supervisor session

## 8.2 在主 flow 中发送请求

1. 用户输入文本
2. supervisor 开始流式回复
3. 中途可能生成 planning card
4. 中途可能生成 child cards
5. 底部 tray 同步显示活跃 children
6. supervisor 汇总结果并产出 artifact / approval 卡片

## 8.3 从主 flow 进入 child session / agent

1. 点击 child card 的 Open
2. 页面切换到 child session view
3. breadcrumb 增加一层
4. 仍采用 chat-like stream 展示
5. 可以返回上一层

## 8.4 打开高级详情

1. 点击某条 child / artifact / approval / run 卡片
2. 右侧打开 drawer
3. 可切换：Route / Runtime / Inputs / Events / Contracts

---

## 9. V1 功能清单

## 9.1 必做功能

### A. Flow 列表
- flow list
- status badge
- search
- pin recent
- create flow

### B. Session Stream
- markdown 渲染
- 流式更新
- planning cards
- child link cards
- status cards
- approval cards
- artifact cards

### C. Child Navigation
- click to open child session
- breadcrumb navigation
- child session 内继续展示 its children

### D. Active Children Tray
- 当前 flow 活跃 children 列表
- open 快捷入口
- 状态 badge

### E. Detail Drawer
- Route
- Runtime
- Inputs
- Events
- Contracts

### F. Template Picker
- template list
- create flow

## 9.2 可延后功能（V1.5）
- split view
- dedicated graph/map view
- side-by-side compare
- local notification
- richer runtime logs
- drag pin cards to sidebar

---

## 10. 内容块设计

## 10.1 Planning Card
字段：
- title
- intent summary
- created children
- next actions

## 10.2 Child Link Card
字段：
- display_name
- type: session / agent / run
- status
- profile / runtime badge
- open button

## 10.3 Status Card
字段：
- overall state
- progress summary
- completed count / total count

## 10.4 Approval Card
字段：
- contract type: verification / approval / recovery
- summary
- actions: accept / reject / retry

## 10.5 Artifact Card
字段：
- artifact name
- artifact type
- result ref
- open / copy path / reveal

---

## 11. 技术方案

## 11.1 总体原则

- 产品壳参考 Proma：**Electron + React + TypeScript + Tailwind + Jotai** 路线
- 交互参考 Codex：**会话式工作台 + 子执行单元可点击深入 + 运行时透明**
- 业务内核保持现有 Butler-flow 实现，不做 Rust 重写
- V1 不引入新的业务真源

## 11.2 推荐技术栈

### 桌面层
- Electron
- React
- TypeScript
- Vite

### 状态与请求
- TanStack Query
- Jotai（优先）或 Zustand

### UI
- Tailwind CSS
- Radix UI / shadcn-ui

### 内容渲染
- react-markdown
- remark-gfm
- rehype-highlight 或 Shiki

### 高级组件
- xterm.js（用于后续 runtime / logs 面板）
- React Flow（用于 V1.5 及高级 flow map）

### 本地 API
- Python FastAPI
- SSE（优先）
- WebSocket（可后续增强）

---

## 12. 前后端分层

## 12.1 后端原则

新增一个轻量桌面 API 层，放在现有 Butler-flow 引擎之前：
- 负责读取 flow list / session / child data / event stream
- 负责模板读取与 create flow
- 负责流式更新推送
- 不负责重写核心 flow 逻辑

## 12.2 前端原则

- Electron 负责窗口、托盘、系统集成、文件打开
- React Renderer 负责 UI
- 不把业务真源搬到前端 store
- 前端 store 只存：UI 状态、当前选中 flow/session/drawer tab

---

## 13. 目录结构建议

## 13.1 仓库目录（建议新增）

```text
butler_main/
  flow_desktop_api/
    app.py
    dto.py
    routes/
      flows.py
      sessions.py
      templates.py
      stream.py
      actions.py
    adapters/
      flow_adapter.py
      session_adapter.py
      template_adapter.py
      stream_adapter.py
    services/
      flow_query_service.py
      flow_action_service.py
```

## 13.2 桌面前端目录（建议新增）

```text
apps/
  butler-flow-desktop/
    electron/
      main/
        index.ts
        window.ts
        tray.ts
        ipc.ts
      preload/
        index.ts
    renderer/
      src/
        app/
          router.tsx
          layout.tsx
        pages/
          FlowHome/
          FlowSession/
          TemplatePicker/
        modules/
          sidebar/
          session-stream/
          flow-input/
          child-tray/
          detail-drawer/
          artifact-card/
          status-card/
          approval-card/
          child-link-card/
        api/
          client.ts
          flows.ts
          sessions.ts
          templates.ts
          stream.ts
        store/
          ui.ts
          navigation.ts
        types/
          flow.ts
          session.ts
          child.ts
          event.ts
          template.ts
        components/
          markdown/
          badges/
          cards/
          breadcrumbs/
```

---

## 14. 后端 API 草案

## 14.1 查询接口

- `GET /api/flows`
  - 返回 flow 列表
- `GET /api/flows/:flowId`
  - 返回 flow 概览
- `GET /api/flows/:flowId/session`
  - 返回 supervisor 主 session
- `GET /api/sessions/:sessionId`
  - 返回某个 child session
- `GET /api/sessions/:sessionId/children`
  - 返回子 session / 子 agent / runs
- `GET /api/templates`
  - 返回 manager 可用模板列表
- `GET /api/details/:entityType/:entityId`
  - 返回 drawer detail 数据

## 14.2 动作接口

- `POST /api/flows`
  - manager 创建 flow
- `POST /api/flows/:flowId/messages`
  - 向当前 flow 发送输入
- `POST /api/sessions/:sessionId/messages`
  - 向某个 child session 发送输入
- `POST /api/actions/:entityType/:entityId`
  - accept / reject / retry / continue

## 14.3 流式接口

- `GET /api/stream/flows/:flowId`
  - supervisor flow stream
- `GET /api/stream/sessions/:sessionId`
  - child session stream

---

## 15. 状态模型建议

## 15.1 Flow 状态
- idle
- running
- waiting_input
- blocked
- completed
- failed

## 15.2 Child 状态
- queued
- running
- waiting
- blocked
- completed
- failed

## 15.3 UI 状态
- selectedFlowId
- selectedSessionId
- activeDrawerTab
- activeChildIds
- currentBreadcrumb

---

## 16. 视觉与交互风格建议

1. 整体深色优先，参考 ChatGPT / Codex / Proma 桌面风格
2. 左侧列表保持密度高但层级清晰
3. 主会话区保持气泡式 / 卡片式混排
4. child cards 与 artifact cards 要明显区别于普通 markdown 文本
5. tray 保持低高度、强状态感、支持一键打开
6. breadcrumb 要始终可见
7. detail drawer 是高级信息入口，不抢主视图焦点

---

## 17. 开发阶段计划

## Phase 0：冻结边界
- 产出本 PRD
- 明确仅做 Butler-flow

## Phase 1：后端桌面 API
- flows / sessions / templates / stream / actions 基础接口
- 基础 DTO

## Phase 2：桌面壳搭建
- Electron + React + Tailwind + Jotai
- 基础 layout

## Phase 3：主工作台
- 左侧 flow list
- 中间 supervisor session stream
- 底部 child tray
- 右侧 drawer

## Phase 4：template create flow
- manager template picker
- create flow
- auto navigate to supervisor session

## Phase 5：child navigation
- click child card -> child session page
- breadcrumb back / forward

## Phase 6：细节与优化
- artifact open
- actions
- better stream rendering
- polish loading / empty states

---

## 18. V1 验收标准

1. 可以从左侧看到 flow 列表
2. 可以通过 manager 入口创建 flow
3. 创建后自动进入 supervisor 主 flow
4. 右侧主区是流式会话，不是静态图
5. 会话里能显示 child session / child agent / artifact / approval 卡片
6. 可以点击卡片进入子 session / 子 agent
7. 页面有 active children tray
8. 页面有 detail drawer
9. 全程不引入 chat-first 或 heartbeat-first 页面
10. 目录和技术栈可直接作为后续实现底稿

---

## 19. 风险与注意事项

1. **不要把 flow UI 做回 agent UI**
   - 命名必须坚持 Flow / Session / Child / Run
2. **不要把主视图做成图编辑器**
   - 图形视图应作为辅助，而不是主交互
3. **不要让前端发明第二套状态机**
   - 业务真源仍在 Butler-flow 后端
4. **不要把 manager 做成常驻主会话**
   - manager 是入口，不是默认主体
5. **不要在 V1 塞进 campaign / heartbeat / chat 总控**
   - 严守边界

---

## 20. 参考

### Butler 仓库现有实现参考
- `butler_main/orchestrator/service.py`
- `butler_main/orchestrator/compiler.py`
- `butler_main/orchestrator/workflow_ir.py`
- `butler_main/orchestrator/workflow_vm.py`

### 外部产品参考
- Proma README: https://github.com/ErlichLiu/Proma/blob/main/README.md
- Codex README: https://github.com/openai/codex/blob/main/README.md
- Codex install/build: https://github.com/openai/codex/blob/main/docs/install.md

---

## 21. 最终结论

**Butler-flow Desktop V1 应被定义为：以 supervisor 为主 flow、以 manager 为创建入口、采用 ChatGPT/Codex 风格流式会话工作台的桌面端产品。**

其核心形态不是“agent chat”，而是：
- 左侧 flows
- 右侧 supervisor session
- 消息流中的 child cards
- 底部 active children tray
- 可钻取到子 session / agent / run

该方案在产品壳层参考 Proma，在交互工作台感上参考 Codex，在业务主体上严格坚持 Butler-flow 的 flow-first 结构。
