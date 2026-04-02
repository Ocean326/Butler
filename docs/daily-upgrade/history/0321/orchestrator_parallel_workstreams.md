# Orchestrator 并行工作流拆分

## 1. 背景

当前关于 `heartbeat` / `orchestrator` 的工程决策已经基本明确：

- 不继续在旧 `heartbeat` 上做主升级
- 旧 `heartbeat` 冻结为 legacy，只做兼容和必要 bugfix
- 新起一个真正独立的 `orchestrator core`
- 替换方式采用旁路重写 / 绞杀式替换，而不是大爆炸重写

在这个前提下，当前最适合拆成两个并行方向推进，减少相互阻塞。

---

## 2. 并行拆分原则

建议并行拆成两路：

1. `Legacy 解耦路`
2. `Greenfield Orchestrator Core 路`

拆分目标：

- 一路负责把旧系统边界切出来
- 一路负责旁路建立新 runtime core

这样可以同时推进“旧系统降耦”和“新系统成型”，避免在旧 heartbeat 上继续堆升级逻辑。

---

## 3. 路线 A：Legacy 解耦路

### 3.1 目标

把 `talk` 和旧 `heartbeat` 的边界切干净，让旧 heartbeat 降为 legacy runtime。

### 3.2 核心职责

- 冻结旧 `heartbeat`
- 只允许必要 bugfix
- 把 `talk -> heartbeat` 收敛成清晰接口
- 移除 talk 对 heartbeat 内部状态和 memory 拼装链的直接依赖
- 增加 compatibility adapter，让旧 heartbeat 可以挂在统一接口后

### 3.3 重点工作

- 梳理旧 `talk` 的 heartbeat 入口
- 梳理旧 `heartbeat` 的 ingress / query / delivery 出口
- 抽出统一协议层
- 让 talk 只通过协议调用 legacy heartbeat
- 减少 `MemoryManager` 驱动 heartbeat 的直接耦合面

### 3.4 建议接口

- `create_mission(request) -> mission_id`
- `get_mission_status(mission_id) -> summary`
- `append_user_feedback(mission_id, feedback) -> ok`
- `control_mission(mission_id, action) -> ok`
- `list_delivery_events(mission_id) -> events`

### 3.5 写集范围

优先改这些区域：

- 旧 `talk` 入口
- 旧 `heartbeat` 对接层
- 协议对象 / DTO
- compatibility adapter
- 相关文档

尽量不改：

- 旧 heartbeat 主循环内部逻辑
- planner prompt 细节
- memory manager 内部复杂机制

### 3.6 产出物

路线 A 结束时，应该得到：

- `talk` 不再直接控制 heartbeat 内部逻辑
- 旧 heartbeat 被包在统一接口之后
- 旧系统仍可继续运行
- 未来新 orchestrator 可以接管相同接口

---

## 4. 路线 B：Greenfield Orchestrator Core 路

### 4.1 目标

旁路起一个真正独立的后台任务运行时，不继承旧 heartbeat 的内部结构。

### 4.2 核心职责

- 新建 `orchestrator/` 目录
- 定义最小 runtime core
- 先只支持一个最小 mission 模板
- 不依赖旧 heartbeat 的 memory 拼装链
- 不依赖 talk recent/local memory 逻辑

### 4.3 最小对象

- `Mission`
- `Node`
- `Branch`
- `Artifact`
- `Ledger`
- `OrchestratorService`

### 4.4 最小能力

- Mission 状态机
- Node / Branch 生命周期
- `tick`
- `dispatch`
- `collect`
- `judge`
- `retry / timeout / quorum`
- `ledger event`

### 4.5 第一阶段建议范围

第一阶段只做：

- 最小 schema
- 最小 store
- 最小 runtime loop
- 一个最小 mission template
- 核心测试

先不做：

- 顶层 `Decision Layer`
- 全量 memory 系统
- 复杂 research template
- 大量 agent profile
- 高级自扩展逻辑

### 4.6 写集范围

优先写这些区域：

- 新 `orchestrator/` 目录
- models / store / service / scheduler / judge adapter
- template registry
- 最小测试

尽量不碰：

- 旧 `heartbeat_orchestration.py`
- 旧 `memory_manager.py`
- 旧 talk 内部逻辑

### 4.7 产出物

路线 B 结束时，应该得到：

- 一个独立可运行的 `orchestrator core`
- 能跑 1 个最小 mission
- 能通过统一协议被接入
- 不依赖旧 heartbeat 内部结构

---

## 5. 两路之间唯一需要先冻结的公共契约

为了让两路真正并行，必须先约定公共接口，不要一边写旧边界、一边写新 core，最后协议不一致。

建议先冻结这些接口：

- `create_mission(request) -> mission_id`
- `get_mission_status(mission_id) -> summary`
- `append_user_feedback(mission_id, feedback) -> ok`
- `control_mission(mission_id, action) -> ok`
- `list_delivery_events(mission_id) -> events`

说明：

- 路线 A 用这些接口包住 legacy heartbeat
- 路线 B 让新 orchestrator 也实现这些接口
- talk 只依赖接口，不依赖具体实现

---

## 6. 为什么这样拆最合适

### 6.1 可以避免重复建设

不建议拆成：

- 一路继续改旧 heartbeat 主循环
- 一路同时写新 orchestrator

这样会在 runtime 主逻辑层面重复建设，冲突最大。

### 6.2 可以避免旧逻辑继续扩散

路线 A 的目标不是继续增强旧 heartbeat，而是限制它、包住它、隔离它。

### 6.3 可以让新系统保持干净

路线 B 可以在不受旧 `MemoryManager` 结构拖累的情况下定义最小 orchestrator core。

### 6.4 可以支持渐进迁移

当新 orchestrator 成熟后，只需要把接口实现从 legacy adapter 切到新 core，而不是一次性推翻整个系统。

---

## 7. 不同路线的明确边界

### 7.1 路线 A 不负责什么

- 不负责设计新 orchestrator 内核
- 不负责重写 MissionGraph runtime
- 不负责复杂 template

### 7.2 路线 B 不负责什么

- 不负责清理旧 talk 的全部技术债
- 不负责修旧 heartbeat 的主循环
- 不负责兼容所有旧接口细节

---

## 8. 推荐执行顺序

虽然两路可以并行，但建议先做一个极小的同步动作，再各自展开。

### Step 0

先冻结统一协议草案：

- mission ingress
- mission query
- mission control
- delivery query

### Step 1A

路线 A 开始包 legacy heartbeat。

### Step 1B

路线 B 开始起 `orchestrator core`。

### Step 2

用一个最小 mission 场景打通新 core。

### Step 3

让 talk 可以在 legacy 和 new orchestrator 之间切换实现。

---

## 9. 最终目标

最终期望形成的系统结构：

- `butlerbot_talk`
  - 前台解释
  - direct branch invoke
  - mission 创建 / 查询
- `legacy_heartbeat_adapter`
  - 兼容旧 heartbeat
- `orchestrator`
  - mission store
  - node / branch runtime
  - scheduler
  - judge interface
  - ledger / event store
- `research`
  - 继续作为 subworkflow capability
  - 不直接承担 orchestrator 职责

---

## 10. 一句话结论

最合理的并行拆分是：

- 一路做 `talk <-> legacy heartbeat` 解耦与接口化
- 一路做全新的 `orchestrator core`

旧 heartbeat 不再继续承担主升级路径，新 orchestrator 通过旁路逐步接管。
