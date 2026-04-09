# 0409 Butler Desktop Codex 式 Manager Thread 前端升级计划与实施稿

日期：2026-04-09
状态：已落代码 / 已验收 / 当前真源
所属层级：Product Surface（主） / L1 `Agent Execution Runtime`（辅）
定位：把当前 Butler Desktop 从 `0405` 的 thread-first workbench，收口成更接近 Codex 的 `Manager` 单主语 conversation shell，并在同日第二波补到更成熟的桌面壳与 projection continuity

关联：

- [0409 当日总纲](./00_当日总纲.md)
- [0408 Team 与 Desktop 关系、当前进度与下一条主线](../0408/01_team与desktop关系_当前进度与下一条主线.md)
- [0405 Butler Flow Desktop 线程化工作台与 Manager-Supervisor 串联落地](../0405/01_butler-flow_desktop线程化工作台与manager-supervisor串联落地.md)
- [真源矩阵](../../project-map/03_truth_matrix.md)
- [改前读包](../../project-map/04_change_packets.md)

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 把 Desktop 前端升级成更接近 Codex 的 `Manager` conversation shell，同时保留 Butler runtime truth 与桥接边界。 |
| 所属层级 | Product Surface 主落，辅触前台 `butler-flow` 的 runtime 投影读取。 |
| 当前真源文档 | `0409/00`、本稿、`0408/01_team与desktop关系...`、`0405/01_butler-flow_desktop线程化工作台...`。 |
| 计划查看的代码与测试 | `desktop/src/renderer/{App.tsx,components/mission-shell/*,lib/mission-shell.ts,state/queries/use-thread-workbench.ts,styles/*.css}`、`surface/service.py`、`butler_bot_code/tests/test_butler_flow_surface.py`、desktop `typecheck / vitest / build`、Python `surface/desktop_bridge` 回归。 |

## 1. 产品定义

当前 Desktop 的正确产品定义是：

> **一个以 `Manager` 为唯一一级前台代理对象的连续 thread 产品。**

用户不是在前台分别操作：

- supervisor
- recovery
- studio
- team graph
- template team 页面

用户是在：

- 选择某条连续的 Manager thread
- 通过 Manager 对话来托管 mission
- 让内部 runtime / supervisor / team agents 推进工作
- 在需要时查看可折叠的来源消息、结构化证据块和 agent drill-in

因此 Desktop 不是 dashboard，也不是多页面工作台，而是：

> **Manager Conversation for This Mission**

## 2. 固定产品裁决

### 2.1 前台一级对象

前台唯一一级对象固定为：

- `Manager`

以下对象不再作为一级前台对象：

- `Supervisor`
- `Recovery`
- `Studio`
- `Agent focus`
- `Template team`

它们只允许以三种形态出现：

1. Manager 的代述或总结
2. 对话中的结构化内联 block
3. 点击后展开的细流 / detail sheet / drill-in

### 2.2 左侧结构

左侧固定为 thread continuity rail，而不是功能导航栏。

必须包含：

1. 全局壳
   - 品牌
   - 当前 workspace/config
   - 极少量全局动作
2. 新线程入口
3. thread 列表
   - 活跃线程
   - 连续历史

不再把这些内容放成一级导航：

- `Supervisor`
- `Templates`
- `Agent focus`
- `Recovery`
- `Studio`

### 2.3 顶部结构

顶部必须收口成 1 到 2 行的薄状态条。

只展示：

- 当前 thread / mission 标题
- 状态、phase、最新 signal
- 少量关键动作，例如：
  - refresh
  - pause / resume
  - studio only when relevant
  - recovery only when relevant

不再保留厚工具栏、分区工具面板或大块 hero。

### 2.4 主区结构

右侧主体固定为统一的 `Manager` 主对话。

它必须满足：

1. 同一条 thread 连续贯穿：
   - 准备
   - 执行
   - 恢复
   - 收尾
   - 追加
2. 不因进入 recovery/studio 就切到完全不同的大页
3. 结构化信息以内联 block 进入对话
4. 非 Manager 输出默认折叠、默认多藏

### 2.5 输入区结构

始终只有一个 composer，但它是 context-aware composer。

它会随当前语境改变：

- placeholder
- 提交语义
- slash 提示
- 建议动作

首批保留的显式控制命令包括：

- `/start`
- `/pause`
- `/resume`

后续允许在同一 composer 中扩充，但不新增第二个主要输入区。

## 3. 当前代码基线与要推翻的旧心智

### 3.1 当前代码基线

当前分支以 `0405` 的 renderer 为基线，现有心智是：

- 左 rail：
  - `Manager 管理台`
  - `Threads 历史`
  - `New Flow 新建`
  - `Templates 模板`
- 主区：
  - `Manager thread`
  - `Supervisor thread`
  - `Agent focus`
  - `Template team`

这比更早版本已经好很多，但仍然偏工作台/多页面，而不是统一对话壳。

### 3.2 本轮要推翻的旧心智

1. `Supervisor` 不再作为独立大页抢主位。
2. `Agent focus` 不再作为独立主导航目的地。
3. `Templates` 不再作为 thread 同级主页面。
4. `History` 不再表现成与 mission 分裂的另一类对象；它只是 thread continuity 的一部分。
5. 主区不再是“页面切换 + 大块说明 + 大量卡片”，而是 conversation-first。

## 4. 视觉与交互方向

### 4.1 总体方向

本轮视觉方向固定为：

- 更接近 Codex
- 更克制
- 更像线程产品
- 更低信息密度
- 更少粗卡片和厚边框

视觉 thesis：

> **像一个冷静、可信、持续运行中的桌面代理线程，而不是功能很多的前台工位。**

### 4.2 页面结构

固定页面骨架：

1. 左侧 rail
   - 全局壳
   - 新线程
   - thread list
2. 右侧
   - 极薄 header
   - Manager 主对话
   - context-aware composer

### 4.3 元素层级

元素展示必须遵循：

1. `Manager narration` 最醒目
2. `mission status / phase / latest signal` 次之
3. 结构化 block 作为证据附着在消息流里
4. 非 Manager 来源以轻 badge、折叠块或 drill-in 方式露出

### 4.4 内联 block 策略

首批对象统一按“消息内联 block”展示：

- latest receipt
- accepted artifact
- runtime / supervisor trace
- recovery suggestion
- studio / contract edit context
- responsibility summary

默认不做：

- 满屏 dashboard
- 常驻 inspector 大分栏
- 多块并列大图表

## 5. 实施波次

### Wave A：今天先做前端壳收口

1. 左 rail 改成连续 thread rail
2. 折叠 `History / New Flow / Templates` 的多页导航心智
3. 右侧统一收成 Manager 主对话
4. 顶栏收成极薄状态条
5. 保留新线程入口，但它只是新建一条空白 manager thread
6. 保留 thread 打开能力，但打开后统一进入同一对话壳

### Wave B：把内部来源压回同一条 thread

1. `Supervisor` 变成 Manager 对话里的 runtime 细流 / summary block / mode badge
2. `Agent focus` 变成对话里的可展开 drill-in
3. `Template team / Studio` 收成同一主对话里的 studio 语境与 block
4. slash 控制和状态动作挂到同一 composer 与顶栏中

### Wave C：测试与收口

1. 更新 renderer 测试到新的文案和交互
2. 跑 `typecheck`
3. 跑 `test:renderer`
4. 跑 `build`
5. 再按 `vibe-close` 收尾并回写 project-map/doc 入口

## 6. 接口约束

### 6.1 不改 truth owner

这轮只是 Desktop 升级，不允许：

- 新增 Desktop 私有 truth
- 绕过 `desktop_bridge.py`
- 直接读取 raw sidecars
- 让 renderer 反向定义 mission/team truth

### 6.2 DTO 策略

优先复用现有 DTO：

- `ThreadHomeDTO`
- `ManagerThreadDTO`
- `SupervisorThreadDTO`
- `AgentFocusDTO`
- `TemplateTeamDTO`

本轮可允许：

- 在 renderer 内重新组织它们的消费方式
- 增加更适合 conversation shell 的归一化 helper

若出现字段缺口，优先小幅补 DTO，而不是发明第二套数据面。

## 7. 测试计划

### 7.1 renderer 交互回归

必须覆盖：

1. 默认进来是 Manager conversation shell
2. 左 rail 显示 thread continuity，而不是多页 workbench
3. 新线程入口仍能从空白 manager thread 发起
4. 从历史 thread 打开后仍进入同一主对话壳
5. supervisor / agent / template 细节不再以一级页面出场，而以内联/展开方式出现
6. 顶部状态条与 composer 仍可执行必要动作

### 7.2 工程验证

固定顺序：

1. `git diff --check`
2. `npm run typecheck`
3. `npm run test:renderer`
4. `npm run build`
5. 若无图形环境，e2e 明确记为阻塞，不虚报

## 8. 通过标准

本轮通过标准固定为：

1. 用户进入 Desktop 后，前台唯一主语清晰是 `Manager`
2. 左 rail 主要是 thread continuity，而不是功能页切换
3. 右侧主要是主对话，不再是并列工作台页
4. 非 Manager 内容默认多藏，可折叠，可钻取
5. 顶部明显更薄、更克制，整体信息密度下降
6. 设计语言、页面骨架、元素节奏明显更接近 Codex
7. 现有 bridge 与 runtime truth chain 未被破坏

## 9. 当前默认假设

1. 本轮优先改 renderer，不先扩 Python surface truth。
2. `Supervisor / Recovery / Studio` 先统一视为 Manager 对话中的语境与来源，不单开新导航。
3. thread continuity 优先级高于“显式区分 mission vs history”。
4. 前端默认策略是“多藏”，不是“多露”。
5. 本轮先完成 conversation shell 收口，再评估后续更深的 desktop 产品化能力。

## 10. 实际代码落点

本轮实际代码已落在：

1. `butler_main/products/butler_flow/desktop/src/renderer/App.tsx`
   - 不再承载整页 UI 细节，而是只负责 state container、bridge 接线、query invalidation 和 action orchestration
   - 把 “能跑但很重的单文件壳” 收口成可维护的桌面入口
2. `butler_main/products/butler_flow/desktop/src/renderer/components/mission-shell/MissionShell.tsx`
   - 提取 rail / mission header / thread body / inline block / composer / agent detail sheet
   - 让 Manager conversation shell 真正成为稳定组件树，而不是临时拼接页
3. `butler_main/products/butler_flow/desktop/src/renderer/lib/mission-shell.ts`
   - 统一 thread continuity 组装、composer 文案、mode 语义、block meta、时间与路径压缩策略
   - 让 UI 判断逻辑从 React 组件中抽离
4. `butler_main/products/butler_flow/desktop/src/renderer/state/queries/use-thread-workbench.ts`
   - 统一 React Query 默认值：`refetchOnWindowFocus=false`、`retry=1`、轻量 `staleTime/gcTime`
   - 把 `home` 和 thread 细流轮询拆成不同 cadence，减少成熟桌面壳里的抖动感和无意义刷新
5. `butler_main/products/butler_flow/desktop/src/renderer/styles/workbench.css`
   - 视觉壳从多卡片工作台改成更克制的 Codex 式 conversation layout
   - 顶栏变薄
   - thread list 更紧凑
   - message / inline strip / detail sheet 更轻
6. `butler_main/products/butler_flow/desktop/src/renderer/styles/globals.css`
   - 同步收口 day/night token、基础布局与桌面级留白
7. `butler_main/products/butler_flow/surface/service.py`
   - `thread_home_payload()` 对 linked `manager + supervisor` history 做 bundle 排序
   - 现役合同固定为：同一 linked flow 中 `manager` 必须先于 `supervisor`，同时整个 bundle 仍按最近活动时间排序
8. `butler_main/butler_bot_code/tests/test_butler_flow_surface.py`
   - 新增 linked history 顺序回归：`["manager", "supervisor"]`
9. 已删除旧的多页 workbench 壳组件：
   - `WorkbenchShell.tsx`
   - `ManageCenterShell.tsx`
   - `FlowRail.tsx`
   - `DetailDrawer.tsx`
   - `SupervisorStream.tsx`
   - `WorkflowStrip.tsx`
10. `butler_main/products/butler_flow/desktop/src/{main,preload,shared}/`
    - 新增 “默认 config 路径” IPC
    - 启动时由主进程把仓库固定默认值暴露给 renderer
    - renderer 首屏初始化优先自动挂载该路径，不再要求用户每次手动 attach

## 11. 同日第二波：成熟桌面壳与 projection hardening

1. renderer 成熟化
   - 第一波已经完成“产品心智收口”，第二波继续完成“实现壳层收口”
   - 目标不是 demo 页，而是更接近成熟桌面 app 的稳定 shell
2. projection continuity 补强
   - Manager-first shell 的前提，不只是视觉上突出 `Manager`
   - 还要求 history 投影在 linked flow 上保持连续、稳定、可预期
   - 因此本轮把 shared surface 的 `thread_home` history 排序补成 bundle 合同，而不是在 renderer 里做猜测性修补
3. 边界保持不变
   - 本轮仍然没有引入 Desktop 私有 truth
   - Desktop 继续只消费 `preload + IPC + python bridge` 提供的 shared surface
   - `manage_chat / manage_flow / supervisor runtime` 的真语义不在 renderer 内重写
4. 启动体验继续收口
   - Desktop 现在默认直接进入可用态，而不是先停在“请选择 config”
   - 固定默认值只落在 desktop projection 壳，不改变 Butler config/truth 的归属

## 12. 已执行验证

1. `git diff --check`
2. `cd butler_main/products/butler_flow/desktop && npm run typecheck`
3. `cd butler_main/products/butler_flow/desktop && npm run test:renderer`
4. `cd butler_main/products/butler_flow/desktop && npm run build`
5. `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_surface.py butler_main/butler_bot_code/tests/test_butler_flow_desktop_bridge.py -q`
6. `cd butler_main/products/butler_flow/desktop && npm run build`

补记：

- desktop `build` 过程仍会打印 Node/Vite 的 CJS/ES module warning，但退出码为 `0`，当前不构成阻塞

当前未执行：

- Electron `Playwright` e2e
  - 原因：本轮默认 gating 先以 renderer/typecheck/build 为主；若后续需要窗口层证据，再补主机图形环境验证
