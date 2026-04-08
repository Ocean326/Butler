# 0408 Butler Desktop 产品形态收口：Manager 对话壳、连续线程与多藏 agent 输出

日期：2026-04-08
状态：当前真源 / docs-only
所属层级：Product Surface，辅触 L1 `Agent Execution Runtime`
定位：把最近一轮关于 Butler Desktop UI、交互逻辑、与 `canonical team runtime` 关系的讨论收口成当前正式产品定义

关联：

- [0408 当日总纲](./00_当日总纲.md)
- [0407 Canonical Team Runtime 最终收口：任务产物真源、治理真源与升级门槛](../0407/01_canonical_team_runtime最终收口_任务产物真源与升级门槛.md)
- [0407 Butler Flow 到 Canonical Team Runtime 升级路径与阶段开发计划（批判式更新版）](../0407/02_butler-flow到canonical_team_runtime升级路径与阶段开发计划_批判式更新版.md)
- [0403 Butler Flow Desktop 壳与 shared surface bridge 落地](../0403/03_butler-flow_desktop壳与shared_surface_bridge落地.md)
- [真源矩阵](../../project-map/03_truth_matrix.md)
- [改前读包](../../project-map/04_change_packets.md)
- `butler_main/products/butler_flow/surface/dto.py`
- `butler_main/products/butler_flow/desktop/src/shared/dto.ts`
- `butler_main/products/butler_flow/desktop/src/renderer/App.tsx`
- `butler_main/products/butler_flow/desktop/src/renderer/components/navigation/FlowRail.tsx`

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 收口 Butler Desktop 的下一版正式产品形态，明确它如何从 `canonical team runtime` 长出来，以及前端真正应该展示什么。 |
| 所属层级 | 主落 `Product Surface`；下层依赖仍是 `butler-flow` 当前的 contract / receipt / recovery runtime。 |
| 当前真源文档 | 以 `0407/01`、`0407/02`、`0403/03` 为主，再结合当前 shared surface/desktop renderer 代码现状。 |
| 计划查看的代码与测试 | 代码重点看 `products/butler_flow/surface/`、`desktop_bridge.py`、`products/butler_flow/desktop/`；后续若实现 UI，再以 `test_butler_flow_surface.py`、`test_butler_flow_tui_controller.py`、`test_butler_flow_desktop_bridge.py`、renderer `vitest` 与 Electron `Playwright` 为主。 |

## 一句话裁决

Butler Desktop 当前应正式定义为：

> **`Manager-facing conversation shell over the canonical team runtime`**

也就是说：

- `team runtime` 是语义与真源链
- `desktop` 是它的会话式投影壳
- 用户前台只面对一个一级对象：`Manager`

Desktop 不再继续按：

- dashboard
- multi-page workbench
- team workspace
- 多个 agent 并列直面用户

来定义自己。

## 1. Team 与 Desktop 的现役关系

### 1.1 Team 当前落点

当前仓库里，“team”的现役含义已经收紧为：

- 运行在 `Codex / Claude Code` 这类 vendor CLI substrate 之上
- 以 `TaskContract + Receipt Spine + Recovery Cursor + Authority/Policy` 为硬骨架
- 仍处在 `canonical team runtime over vendor substrate` 的命名口径

它证明的是：

- 一个 repo-bound engineering task
- 如何在多角色、多回合执行中保持 contract-first
- 如何让 accepted progress、recovery、governance 不依赖 transcript prose

### 1.2 Desktop 当前落点

Desktop 不是新的真源层，也不是新的 team kernel。  
它当前只是一层前台投影壳：

- 物理落点：`products/butler_flow/desktop/`
- Python bridge：`products/butler_flow/desktop_bridge.py`
- shared surface：`products/butler_flow/surface/`
- 读取路径：`preload + IPC + bridge`

因此两者的准确关系是：

> **team runtime 先成立，Desktop 再把它投影成可对话、可控制、可钻取的前台界面。**

## 2. 为什么不能继续沿多页 workbench 走

这轮收口的关键，不是“Desktop 要不要更强”，而是“它要不要继续沿错的壳形态往前长”。

当前不再推荐沿多页 workbench 继续推进，原因有四个：

1. 信息密度太高，用户会被同时暴露的 panel、box、chart、drawer 打散注意力。
2. 多个一级页面会把 `manager / supervisor / recovery / studio` 错误地摆成多个正面对接对象。
3. `history` 一旦被做成独立页面，就会把 mission 的连续线程拆断。
4. 这类布局会自然把 Desktop 推回“workspace-first dashboard”，而不是“conversation-first runtime shell”。

因此本轮正式裁决是：

- 不再让前端以“大面积平铺方框”作为主表达
- 不再把 `history` 与 `mission` 分成两个产品面
- 不再把 `recovery / studio / supervisor` 做成一级壳

## 3. Desktop 的正式产品形态

### 3.1 前台一级对象

前台只保留一个一级对象：

- `Manager`

它的定位不是“普通聊天对象”，而是：

- 用户的托管者
- 用户与整条 team runtime 之间的代理
- 对外唯一连续 narrator

### 3.2 线程模型

正式线程模型固定为：

> **一个 `Manager thread` 就是一个 mission 的连续前台表示。**

它覆盖整个生命周期：

1. 预备阶段
   - Manager 调用不同 agent 完成 idea、需求、team 设计、mission 设计、验收设计
2. `/start` 之后
   - supervisor 或主驱动 agent 连续工作
   - Manager 继续作为主 narrator 对外汇报
3. 完成之后
   - 同一条 thread 继续承载追加、恢复、状态修改、复验

因此：

- `history` 不是独立 surface
- `history` 只是 thread continuity
- 每个 mission 都应表现为一条连续 thread，而不是“当前任务 + 历史记录”的分裂对象

### 3.3 页面骨架

当前正式骨架应收成三段：

1. 左侧
   - `Manager thread` 列表
   - 当前 mission 与历史 mission 在同一列表连续呈现
   - 支持搜索、筛选、固定项，但不再拆成“mission 页”和“history 页”
2. 右侧上端
   - 仅 1-2 行必要任务信息与控制动作
   - 包含 `task_contract_summary / latest_receipt_summary / latest_artifact_ref / recovery_state` 的紧凑摘要
   - 动作以 `/start / pause / resume / inspect / open artifact` 这类操作为主
3. 右侧主体
   - 单条 `Manager` 主对话
   - 用户主要通过与 Manager 对话来驱动和协调 team runtime

## 4. 其他 agent 在前端怎么出现

### 4.1 不再作为一级对象

以下对象不再作为一级页面、一级标签或一级对话对象：

- `Supervisor`
- `Recovery`
- `Studio`
- 其他 worker/role agent

它们仍然存在，但只存在于：

- Manager 的内部调度
- 对话中的模式切换
- 对话中的发言来源标记
- 点击后可钻取的完整输出流

### 4.2 “多藏”是默认姿态

这轮正式引入一个明确的前端原则：

> **默认多藏，不默认多露。**

也就是：

- 主消息单元是 `Manager narration`
- 其他 agent 的输出默认摘要化、折叠化
- 当用户需要证据、细节或排查时，再点击展开

推荐的具体展示规则是：

1. 主对话区里默认显示 Manager 的归纳叙述。
2. 若某轮背后发生了 supervisor/recovery/studio/worker 的动作，则插入轻量 block：
   - 来源 badge
   - 一句话摘要
   - 状态与结果
   - “查看完整输出流”入口
3. 点击后进入完整 agent 子流：
   - 可用 drawer、overlay、split view 或 dedicated inspector
   - 但不改变主对话的一号 speaker 身份

## 5. 模式、发言来源与控制逻辑

### 5.1 Manager 是 narrator

`Manager` 是外显 narrator。  
其他来源只在消息元数据里出现：

- `Supervisor`
- `Recovery`
- `Studio`
- `Worker`
- `System`

它们的定位更像：

- mode
- source
- lens

而不是并列的聊天对象。

### 5.2 Recovery / Studio 的正确位置

`Recovery / Studio` 应被视为：

- 由 Manager 发起的模式切换
- 由 Manager 调用的 specialized lane
- 主线程里的情境状态

而不是：

- 左侧单独 tab
- 独立主页面
- 与 Manager 并列的一级产品对象

### 5.3 用户如何控制 team

用户的主要控制方式也应围绕 Manager：

- 自然语言协调
- slash 命令
- 顶部紧凑操作

当前推荐的高频控制动作是：

- `/start`
- `/pause`
- `/resume`
- `/inspect`
- `/open`
- `/handoff`

## 6. Composer 与消息交互

底部输入区应固定为：

> **一个 single, context-aware composer**

它不是多个页面多个输入框，而是一条连续输入通道。

它的行为随上下文变化：

1. 预备阶段
   - 以对话澄清为主
   - 不强推 setup wizard
2. 已启动 mission
   - 以给 Manager 下达协调、追问、追加、暂停/恢复意图为主
3. 恢复或 studio 上下文
   - 仍是同一输入框
   - 只是当前 mode 与 suggestions 改变

## 7. Desktop 读取什么，不读取什么

Desktop 当前应坚持只读以下 projection truth：

- `surface_meta`
- `mission_console`
- `task_contract`
- `task_contract_summary`
- `latest_receipt_summary`
- `latest_artifact_ref`
- `accepted_receipt_count`
- `recovery_cursor`
- `recovery_state`
- `governance_summary`
- `derived_responsibility_graph`

Desktop 当前不应直接拥有或新增：

- 第二套 mission truth
- 第二套 team truth
- 可写 `team_graph`
- raw sidecar 直读逻辑
- transcript-first 的状态解释链

## 8. 当前代码基线与下一轮实现差距

### 8.1 已经成立的部分

当前代码已经具备下一轮前端收口所需的大部分底层条件：

1. Python bridge 已成立。
2. shared surface 已成立。
3. DTO 已具备 contract/receipt/recovery/governance 关键字段。
4. Desktop/TUI/CLI 已共享一条 truth chain。

### 8.2 仍未收口的部分

但当前 renderer 叙事还停在更早的壳形态：

- `App.tsx` 仍然是 `home / flow / manage`
- `FlowRail.tsx` 仍然在左侧暴露多页导航
- `WorkbenchShell.tsx` 仍偏 run-console 工作台
- `DetailDrawer.tsx` 仍偏信息面板抽屉

### 8.3 下一轮实现主线

下一轮 Desktop 实现应该只沿下面几步推进：

1. 用 `Manager thread list` 替换左侧多页导航。
2. 把 `Mission Index / Contract Studio / Run Console` 这些 surface 语义吸收到同一条 Manager thread 视图里。
3. 把 `manager / supervisor / recovery / studio` 统一到一个 message protocol：
   - 主 speaker = Manager
   - 其他来源 = source badge + 可折叠详情
4. 把 `mission_console` 变成右上紧凑 header，不再变成大面积卡片网格。
5. 增加“查看完整 agent 输出流”的 drill-down 入口，但不让 agent 子流接管主页面。

## 9. 非目标

本轮产品定义明确不做这些事：

- 不把 Desktop 讲成 `Team OS frontend`
- 不新增可写 `team_graph`
- 不把 `history` 做成独立产品面
- 不让 `recovery / studio` 升格成一级页面
- 不把多个 agent 并列成多个主说话对象
- 不把 Desktop 做回 dashboard card wall

## 10. 下一轮 UI 实施验收标准

当下一轮 Desktop UI 实施时，应至少满足下面标准：

1. 用户从新建 mission 到 mission 结束，都可以停留在同一条 `Manager thread` 中。
2. 左侧只负责 thread continuity，不再拆 `mission` 与 `history`。
3. 右侧主区域始终是单条 Manager 对话，不被其他 agent 抢成多个主视图。
4. 其他 agent 输出默认折叠，但可点击进入完整详细输出流。
5. 顶部信息条只显示必要 contract/receipt/recovery 摘要与操作。
6. Desktop 继续只消费 runtime truth chain，不反向创造新的 truth owner。

