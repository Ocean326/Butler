---
type: "note"
---
# 00 agents_os 内核长期维护主线

日期：2026-03-23\
时间标签：0323_0000_kernel\
状态：长期进行中

## 定位

这不是一条“阶段性补丁线”，而是一条 Butler 长期保留的常驻 worker 主线。

它的正式角色固定为：

`Kernel / Runtime Owner`

也就是说，这条线长期负责维护 `agents_os` 作为 `Execution Kernel Plane` 的内核职责，而不是承担产品总包、前台交付或最终用户验收。

## 为什么必须单独设这条线

如果没有一条长期 `agents_os` 维护主线，`agents_os` 很容易退化成：

1. 谁都往里塞一点协议的杂物层。

2. 只补接口、不补执行语义的占位层。

3. 被 `chat`、`orchestrator`、`research`、`multi_agents_os` 反向拉扯的混合层。

Butler 长期又明确需要一个稳定执行内核，所以这条线必须被单独命名并长期维护。

## 长期职责

这条 worker 长期主要负责：

1. execution contract

2. runtime binding

3. capability invocation

4. checkpoint / resume

5. step execution semantics

6. approval / verification / recovery 的执行侧接口

7. receipt / tracing / runtime observability 的内核接线

8. execution kernel 与上层控制面的稳定边界

## 明确不负责

这条 worker 明确不负责：

1. `chat` 前台交互产品形态

2. `orchestrator` 的 mission/control plane 组织

3. `research` 的场景解释与业务热状态

4. `multi_agents_os` 的协作状态设计

5. 最终用户可见交付

6. 产品级“总包闭环”

## 向上交付关系

这条线不是自己闭环产品，而是逐层向上交付：

1. 向 `orchestrator` 交付 execution kernel contract

2. 由 `orchestrator` 组织后台主验收

3. 最终由 `chat` 完成用户可见交付

所以它的成功标准不是“自己能单独跑完全部系统”，而是：

1. 是否稳定向上提供 execution contract

2. 是否被 `orchestrator` 稳定消费

3. 是否支撑 `chat` 通过上层链路完成交付

## 当前阶段判断（2026-03-23）

截至当前，`agents_os` 已经有不少协议、runtime 对象与治理片段，但还没有完全长成真正统一的 workflow execution kernel。

当前最准确的判断是：

`agents_os`**&#x20;已有运行时骨架，但还不是 Butler 长期目标中的完整 execution kernel。**

当前关键缺口集中在：

1. 多步 workflow execution semantics

2. 真正统一的 checkpoint / resume / replay 语义

3. verification / recovery 的强执行内核化

4. capability invocation request/result/receipt 的完整闭环

5. 与 `orchestrator.workflow_vm` 的长期边界收口

## 近期优先级

这条长期 worker 近期优先级应固定为：

### P0 执行内核语义

1. 补齐最小 workflow execution semantics

2. 固化 step / edge / gate / resume 基本对象

### P1 capability 执行链

1. 固化 `CapabilityPackage -> CapabilityBinding -> Invocation`

2. 不再把 skill/package 真源与 runtime invocation 混写

### P2 gate 与恢复

1. 把 approval / verification / recovery 明确分为：

   * 执行侧

   * 治理侧

2. 执行侧归 `agents_os`

### P3 向上 contract 稳定化

1. 向 `orchestrator` 提供稳定 execution contract

2. 不再让上层桥接层长期代替内核承担执行语义

## 与其他主线的关系

1. 对 `01 Chat`

   * 不直接接管前台产品逻辑

   * 只提供 runtime contract

2. 对 `03 Orchestrator`

   * 是最关键的上游依赖之一

   * 长期要把“最小 workflow VM 路由器”逐步升级为真正消费 `agents_os` 内核

3. 对 `04 multi_agents_os`

   * 不抢协作状态主权

   * 只消费其 collaboration substrate contract

4. 对 `research`

   * 不接管场景解释

   * 长期承接逐步回收出来的通用执行语义

## 一句话记忆版

`00 agents_os` 这条长期 worker 不是总包方，而是：

**Butler 的 execution kernel 常驻维护线。**

⠀