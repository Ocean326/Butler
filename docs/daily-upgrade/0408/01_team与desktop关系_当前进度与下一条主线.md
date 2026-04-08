# 0408 Team 与 Desktop 关系、当前进度与下一条主线

日期：2026-04-08
状态：现状澄清 / 分支对齐裁决 / 当前真源
所属层级：L1 `Agent Execution Runtime` / L2 durability substrate / Product surface
定位：把前台 `butler-flow` 的 `team runtime` 与 `desktop projection` 的关系、当前完成度，以及接下来的推进主线写成当前真源

关联：

- [0408 当日总纲](./00_当日总纲.md)
- [0405 Butler Flow Desktop 线程化工作台与 Manager-Supervisor 串联落地](../0405/01_butler-flow_desktop线程化工作台与manager-supervisor串联落地.md)
- [0403 Butler Flow Desktop 壳与 shared surface bridge 落地](../0403/03_butler-flow_desktop壳与shared_surface_bridge落地.md)
- [真源矩阵](../../project-map/03_truth_matrix.md)
- [改前读包](../../project-map/04_change_packets.md)
- 对接基线：`main@80d595b` 上的 canonical runtime 闭环提交与其 `0407` 文档组

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 解释当前 `team` 与 `desktop` 的现役关系、真实进度，以及下一条主线，避免继续把 Desktop 误当 runtime 主体或把 team 误扩成组织内核。 |
| 所属层级 | 主落前台 `butler-flow` 的 L1/L2 runtime 线，辅触 Product surface。 |
| 当前真源文档 | 当前分支内以 [0408/00](./00_当日总纲.md)、[0405/01](../0405/01_butler-flow_desktop线程化工作台与manager-supervisor串联落地.md)、[0403/03](../0403/03_butler-flow_desktop壳与shared_surface_bridge落地.md) 为准；runtime 对接基线参考 `main@80d595b` 上的 `0407` 文档组。 |
| 计划查看的代码与测试 | `butler_main/products/butler_flow/{app.py,runtime.py,state.py,surface/,desktop_bridge.py,desktop/}` 与 `test_butler_flow*.py`、desktop `typecheck/vitest`。 |

## 一句话裁决

当前仓库里：

- `team` 是运行时语义
- `desktop` 是投影壳
- 前台 `butler-flow` 才是两者共同依附的 runtime 主体

所以当前最准确的表达是：

> **Desktop 是 team runtime 的可视化控制台，不是 team runtime 本体。**

但要补一句当前分支现实：

> **`codex/flow-desktop` 还没有把 `main@80d595b` 的 canonical runtime 闭环完整带进来，所以接下来的主线首先是合流，而不是继续扩壳。**

## 1. Team 当前落点

当前所谓 “team” 的现役含义，已经被收紧为前台 `butler-flow` 上的 runtime 语义，而不是：

- 独立 `Team OS`
- 群聊/群组工作台
- 可写组织图
- 后台 `campaign/orchestrator`

从目标口径上看，它应该落在 canonical runtime 那条事实链上。该基线已经在 `main@80d595b` 收口，核心对象包括：

1. `task_contract.json`
   - 唯一任务真源
2. `receipts.jsonl`
   - accepted progress / governance ledger
3. `recovery_cursor.json`
   - transcript-independent recovery pointer
4. `authority/policy`
   - 通过 typed governance receipt 写回 contract snapshot
5. `derived_responsibility_graph`
   - 只读派生，不是第二套真源

因此所谓 `team runtime`，本质上是在证明：

- 一个 repo-bound engineering task
- 如何在多角色、多回合执行里
- 保持 contract-first
- 保持 receipt-backed
- 保持可恢复
- 保持可治理

但对当前工作树要诚实：

- 这套对象目前还不在 `codex/flow-desktop@ae31396` 里完整出现
- 当前分支代码仍主要体现 Desktop thread-first shell
- 所以这里的 `team` 更像“应对齐的 runtime 语义”，而不是“当前分支已经完全合入的代码事实”

## 2. Desktop 当前落点

Desktop 当前已经是真实工程壳，但它的职责边界很清楚：

1. 物理落点：
   - `butler_main/products/butler_flow/desktop/`
2. Python bridge：
   - `butler_main/products/butler_flow/desktop_bridge.py`
3. shared surface：
   - `butler_main/products/butler_flow/surface/`
4. renderer 读取方式：
   - 只通过 `preload + IPC + bridge`
   - 不直接读取 raw sidecars
5. truth 关系：
   - Desktop 只负责展示和操作
   - Desktop 不负责定义 truth owner
   - TUI 与 Desktop 共用同一条 truth chain

但当前还要额外看见一个现实情况：

- `0405` 的 Desktop 产品壳是 thread-first workbench
- canonical runtime 基线已经在 `main@80d595b` 收口
- 当前 `codex/flow-desktop` 分支并没有把这两者真正合到一条代码线上

这不是两套 runtime，而是：

- runtime 真源已经在主干线往 contract/receipt/recovery 收紧
- desktop 产品壳还停在当前施工分支的 thread-first 组织方式

因此当前 Desktop 与 Team 的关系不是“Desktop 承载 Team”，而是：

1. Team runtime 先成立
2. TUI / Desktop / CLI 再各自作为入口或投影壳
3. Desktop 必须跟随 runtime truth，而不能反向驱动 truth model

## 3. 当前正确层级关系

当前更准确的层级是：

1. `team runtime`
   - 主落 L1/L2
   - 辅触 Product surface
2. `desktop`
   - Product surface
3. `desktop`
   - 只消费 shared surface / status payload / bridge payload
4. `surface`
   - 最终应从 runtime truth 派生，而不是由 Desktop 自定义 mission/team truth

所以当前最重要的边界是：

- runtime truth 在前
- projection shell 在后
- Desktop 不得反客为主

## 4. 当前进度

### 4.1 Runtime / Team 线

当前 runtime 线的最新完成态不在本分支，而在 `main@80d595b`：

1. `P0-P5` 已在主干线落地
2. `P6` 仍是 gate，不是新功能阶段
3. canonical runtime 的真源边界已经完成收紧
4. 这条线的剩余问题是验收闭环，而不是继续发明对象

但对当前分支必须加一个现实注记：

1. 当前工作树里没有 `0407/` 文档目录
2. 当前代码搜索不到 `task_contract.json / receipts.jsonl / recovery_cursor.json`
3. 因此这里不能把 Desktop 分支直接写成“已经完整进入 P6 gate 的运行时完成态”

### 4.2 Desktop 线

当前 Desktop 线以 `0405` 为最新专题真源，状态是：

1. 壳已落地
2. bridge 已可用
3. shared surface 已接上
4. thread-first renderer 契约已存在
5. 已有 `typecheck`、renderer `vitest`、bridge/e2e 基础回归

但它还没有到“产品完成态”，而且当前最大的缺口不是壳本身，而是它与 `0407` runtime 口径之间仍需收束：

1. 主干 runtime 已强调 contract-first / receipt-backed / projection purity
2. Desktop 当前仍保留 thread-first workbench 叙事
3. 当前分支还没有把 runtime 真源对象一并带入
4. 因此 Desktop 下一轮最重要的工作不是扩壳，而是先完成与 runtime 基线的合流

## 5. 接下来的主线

### 5.1 不该走的方向

接下来不该再把主线写成：

- 更大的 `Team OS`
- 新的可写 `team graph`
- 让 Desktop 先扩成功能平台
- 把 `campaign/orchestrator` 对象重新拉进前台 Butler Flow

### 5.2 主线 A：先做 Team/Desktop 合流

接下来的唯一主线首先是：

> **先把 `codex/flow-desktop` 对齐到 `main@80d595b`，让 runtime truth 和 Desktop projection 回到同一条代码线上。**

这一步完成前，不应继续把 Desktop 往“独立平台”方向扩。

合流完成后，再进入：

> **把 `canonical team runtime over vendor substrate` 从“已经很像完成态”推进成“证据上闭环”。**

固定检查点继续只认：

1. `G0`
   - one fact -> one truth owner
2. `G1`
   - contract-first launch
3. `G2`
   - receipt coverage
4. `G3`
   - transcript-independent recovery
5. `G4`
   - governance completeness
6. `G5`
   - projection consistency

这里 Desktop 的角色是帮助证明 `G5`，不是自己另开一条战略线。

### 5.3 主线 B：Desktop 只做 `P6` 的 projection-hardening 配套

Desktop 下一轮只应做与 `P6` 直接相关、且建立在合流之后的事：

1. 扩充真实 workspace 样本与 fixture
2. 校验 real payload 在 Desktop / TUI / CLI 上的一致性
3. 稳定展示 contract/receipt/recovery 等摘要
4. 补真实 artifact open / status toast / preflight / settings 等最小闭环
5. 如果要做刷新，优先做 bridge/surface 驱动的刷新，不引入第二套状态源
6. 若 Desktop 保留 thread-first 壳，则它也必须被重新解释成同一条 runtime truth 的 product shell，而不是另一套 team 模型

### 5.4 主线 C：`P6` 过门后，再决定是否进入 Desktop 产品化

只有 `P6` 真正通过后，才值得讨论：

- Desktop 自动刷新 / watcher
- 更多 operator action UX
- packaging / release
- richer real-workspace coverage
- 是否把 Desktop 作为默认主入口之一

也就是说：

> **现在不该是 “以 Desktop 带 Team”，而是 “以 Team gate 收口 Desktop”。**

## 6. 默认假设

1. `0405` 仍是当前分支内可直接阅读的 Desktop 线专题真源。
2. canonical runtime 闭环基线位于 `main@80d595b`，但 `0407` 文档目录当前不在本分支工作树中。
3. 当前工作区分支为 `codex/flow-desktop`，HEAD 为 `ae31396`。
4. 此处的 `team` 仅指 `canonical team runtime` 这条前台 `butler-flow` runtime 线，不指后台 `campaign/orchestrator`。
5. 当前主线以“先合流、再闭环、最后产品化”为优先顺序，不按更远期愿景扩张。
