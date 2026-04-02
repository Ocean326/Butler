# Orchestrator 网页观察台设计稿 v1

日期: 2026-03-24
阶段: V1 设计稿 + 静态原型
范围: 只做观察与展示，不做控制台写操作，不接真实后端

## 1. 设计目标

目标不是再做一个泛用后台，而是给 Butler 当前 orchestrator 做一个专用观察台，帮助人快速回答下面几类问题:

- 现在有哪些 mission 在跑，谁在推进，谁在卡住
- 某个 branch 卡在什么节点，最近发生了什么事件
- workflow session 当前执行到哪一步，产物和协作状态是否正常
- runtime 是否新鲜，是否已经进入 stale 状态

V1 只解决观察问题，不解决编排编辑问题。

## 2. 为什么先做网页端

先做本地网页端，而不是桌面端，原因很直接:

- 当前需求是观察，不是重交互 IDE 壳层
- 网页端最快落地，可直接用 mock 数据先把信息架构和视觉层稳定下来
- 后续对接 `OrchestratorQueryService` 时，前后端边界清晰
- Web 在大屏、笔记本、窄屏窗口之间更容易自适应

结论: 先做一个本地只读 Web Dashboard，比先做桌面壳更符合当前推进节奏。

## 3. V1 非目标

以下内容不在这轮设计稿范围内:

- 不做任务编辑器
- 不做 workflow 拖拽编排
- 不做实时控制按钮
- 不接 Grafana / OTEL / Prometheus
- 不直接写 branch / mission / event store

## 4. 核心用户任务

观察台围绕 4 个用户动作展开:

1. 快速扫 mission board，识别 active / waiting / blocked 的任务
2. 进入某个 mission，查看 workflow graph 和 branch timeline
3. 下钻 session inspector，判断 active step、共享状态、产物注册与协作信号
4. 查看 runtime freshness，避免对旧状态做判断

## 5. 页面信息架构

V1 页面采用三栏结构:

1. `Mission Rail`
2. `Main Workbench`
3. `Inspector`

### 5.1 Mission Rail

作用:

- 展示 mission 列表
- 提供状态筛选
- 快速暴露最近事件类型和告警

信息密度要求:

- 一屏能看多个 mission
- 每个 mission 不展开全量字段，只保留标题、状态、摘要、活跃 branch 数、最近事件标签

### 5.2 Main Workbench

作用:

- 展示当前选中 mission 的主视图
- 同时承载 workflow、timeline、session 三种视角

主区域分 4 层:

1. Hero 概览
2. Metric Cards
3. 选项卡区
4. 具体视图内容

三个主视图:

- `Workflow Graph`: 看执行结构与当前卡点
- `Branch Timeline`: 看事件推进顺序
- `Session Snapshot`: 看 template、shared state、artifact、collaboration

### 5.3 Inspector

作用:

- 放当前 branch / node / runtime 的高密度详情
- 不打断主工作流浏览

内容建议:

- Branch Detail
- Runtime Debug
- Collaboration Signals

## 6. 页面模块设计

### 6.1 顶部状态条

展示全局运行态:

- runtime online / stale
- workspace
- latest tick
- stale window
- mission 总数
- active branch 总数
- approval 队列数量

这个区块必须长期可见，建议 sticky。

### 6.2 Hero 概览

展示当前 mission 的判断性信息:

- mission title
- status
- summary
- 当前 alert
- recent event chips

目标不是列字段，而是让人 3 秒内判断这条 mission 正在发生什么。

### 6.3 Metric Cards

展示与当前 mission 强相关的四类数字:

- active branches
- workflow sessions
- current iteration
- recent event count / blocker count

### 6.4 Workflow Graph

这是观察台的核心模块，应该直接对应 orchestrator 执行意图。

展示内容:

- step 顺序
- 当前 active step
- step role / owner
- 每一步的状态
- 每一步的简短说明

V1 用静态 lane + step cards 即可，不需要先做可编辑 DAG。

### 6.5 Branch Timeline

按时间顺序展示:

- event time
- event type
- summary
- node / branch 归属

时间线比表格更适合做“卡住原因定位”。

### 6.6 Session Snapshot

面向 workflow session 展示:

- session id
- template id
- driver kind
- active step
- role bindings
- shared state
- artifact registry
- collaboration 状态

这里是后续接 `summarize_workflow_session()` 的主要落点。

### 6.7 Inspector

Inspector 右栏专门收纳高密度细节:

- branch id / node id / worker profile / status
- runtime debug: cli / model / reasoning effort / agent id / why
- collaboration signals: handoff、artifact refs、review state、risk flags

## 7. 与现有 Butler 真源映射

V1 页面结构不是凭空设计，后续直接对齐现有查询层。

| 页面模块 | 主要字段 | 现有真源 |
| --- | --- | --- |
| Mission Rail | `mission_id` `title` `status` `active_branch_count` `recent_event_types` | `butler_main/orchestrator/service.py` 中 `_mission_overview()` |
| Hero / Metric Cards | mission 基本信息、branch/session 汇总 | `butler_main/orchestrator/service.py` |
| Workflow Graph | `workflow_session` `workflow_ir` `active_step` `step_ids` | `butler_main/orchestrator/service.py` 中 `_branch_summary()` / `_node_summary()` / `summarize_workflow_session()` |
| Branch Timeline | `events` | `summarize_branch()` + `list_recent_events()` |
| Inspector / Runtime Debug | `runtime_debug` `mission` `node` | `summarize_branch()` |
| Session Snapshot | `template` `shared_state` `artifact_registry` `collaboration` `event_log` | `summarize_workflow_session()` |

本轮已经确认的关键字段来源:

- `summarize_branch()` 会返回 branch 基本信息、`runtime_debug`、`mission`、`node`、recent `events`
- `summarize_workflow_session()` 会返回 `session_id`、`template_id`、`driver_kind`、`status`、`active_step`、`template`、`shared_state`、`artifact_registry`、`collaboration`、`event_log`
- `_branch_summary()` / `_node_summary()` 还会挂出 `workflow_session` 与 `workflow_ir`

这意味着前端不需要先发明新的数据模型，应该围绕 mission / branch / workflow_session 三层展开。

## 8. 响应式策略

### 8.1 大屏

布局:

- 左栏固定 mission rail
- 中栏主工作台
- 右栏 inspector

适用场景:

- 外接显示器
- 宽屏开发窗口

### 8.2 中屏

布局调整:

- 保留左栏
- inspector 下沉到主内容之后
- workflow graph 改为 2 列或横向滚动

适用场景:

- 普通笔记本
- 分屏开发

### 8.3 小屏

布局调整:

- mission rail 变成顶部横向卡片列表
- workflow graph 改为纵向 step stack
- inspector 各 section 叠放

适用场景:

- 窄窗口
- 平板 / 手机预览

## 9. 视觉方向

V1 不走黑底终端风，也不走常规白板后台风。

建议视觉语言:

- 暖纸面底色 + 工程蓝图线框感
- 背景使用柔和径向渐变与细网格纹理
- 标题用 serif，正文用更紧凑的 sans-serif
- 卡片不是纯白，而是半透明暖色 panel

建议字体:

- 标题: `Georgia`, `Palatino Linotype`, serif
- 正文: `Trebuchet MS`, `Verdana`, sans-serif

建议主色:

- Rust / Orange: 当前焦点与高亮
- Teal: active
- Moss Green: done
- Amber: waiting
- Brick Red: blocked / failed

## 10. 状态语义

| 状态 | 语义 | 颜色 |
| --- | --- | --- |
| done | 已完成且稳定 | moss green |
| active | 正在推进 | teal |
| waiting | 等待审批 / 外部输入 / 排队 | amber |
| blocked | 被策略或错误阻塞 | brick red |
| queued | 已创建未执行 | muted sand |

## 11. V1 Mock 数据设计

原型中使用 3 条 mission，分别覆盖三类典型态:

1. `Framework Compiler Demo Route`
   - 当前卡在 `approve`
   - 典型事件链: `workflow_ir_compiled -> workflow_session_created -> workflow_vm_executed -> approval_requested`

2. `OpenFang Inspired Autonomy Package`
   - 当前处于 `analyze`
   - 展示 observer / analyze / handoff / capability package 的推进链路

3. `Workspace Hygiene Sweep`
   - 当前 `blocked`
   - 展示 `policy_blocked / recovery_scheduled` 的恢复场景

这样可以覆盖:

- 正常推进
- 等待审批
- 被策略阻塞

## 12. V1 原型说明

本轮同步提供静态网页原型，作用是先把下面几件事固定住:

- 页面层级
- 信息密度
- 视觉方向
- 响应式行为
- mock 数据契约

V1 原型不依赖真实 API，不读取 event store。

## 13. 后续对接顺序建议

后续如果继续推进，建议按下面顺序接真数据:

1. 先接 mission list 与 mission overview
2. 再接 branch detail + recent events
3. 再接 workflow session summary
4. 最后补 runtime freshness 与自动刷新策略

原因:

- mission rail 一旦接通，观察台就有“活数据入口”
- branch timeline 与 inspector 会立刻提高排障效率
- session snapshot 最后接入也不会破坏前端结构

## 14. 交付物

本轮产物包含:

- 设计文档: `docs/runtime/Orchestrator_网页观察台设计稿_v1.md`
- 静态原型入口: `工作区/Butler/runtime/orchestrator_observation_dashboard_v1/index.html`
- 配套样式与 mock 数据脚本

这版可以直接作为下一轮前后端对接的页面蓝本。
