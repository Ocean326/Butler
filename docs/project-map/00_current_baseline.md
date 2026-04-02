# 当前系统基线

更新时间：2026-03-27  
状态：现役  
用途：定义 agent 改动前默认采用的当前术语、分层和主线入口

## 一句话基线

当前 Butler 的现役主线固定为：

`Product Surface（产品表面层） -> Domain & Control Plane（领域与控制平面） -> L4 Multi-Agent Session Runtime（多 Agent 会话运行时） -> L3 Multi-Agent Protocol（多 Agent 协议层） -> L2 Durability Substrate（持久化基座） -> L1 Agent Execution Runtime（Agent 执行运行时）`

不要再把当前系统默认理解成：

1. `heartbeat / guardian / sidecar`
2. `multi-agent system = 整个 Butler`
3. `observe = role / phase / debug log / query summary`

## 当前默认术语

- `Product Surface（产品表面层）`
  - `chat/frontdoor`、`visual console / Draft Board`、`query`、`feedback`
- `Domain & Control Plane（领域与控制平面）`
  - `campaign`、`mission`、`orchestrator`、template selection、verdict commit、projection assembly
- `L4 Multi-Agent Session Runtime（多 Agent 会话运行时）`
  - `session`、`artifact registry`、`mailbox`、`handoff`、`join`、`session event log`
- `L3 Multi-Agent Protocol（多 Agent 协议层）`
  - `workflow template`、`role spec`、`handoff spec`、`acceptance contract`
- `L2 Durability Substrate（持久化基座）`
  - `checkpoint`、`writeback`、`recovery`、bundle/output linkage
- `L1 Agent Execution Runtime（Agent 执行运行时）`
  - provider / CLI adapter、one-shot run、execution receipt

## 当前稳定态入口

1. [0327 当日总纲](../daily-upgrade/0327/00_当日总纲.md)
2. [0327 Butler 系统分层与事件契约收口](../daily-upgrade/0327/03_Butler系统分层与事件契约收口.md)
3. [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
4. [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
5. [0327 后台任务固定输出区与严格验收收口](../daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)
6. [0327 Skill Exposure Plane 与 Codex 消费边界](../daily-upgrade/0327/02_SkillExposurePlane与Codex消费边界.md)
7. [Visual Console API Contract v1](../runtime/Visual_Console_API_Contract_v1.md)

## 当前裁决

1. `multi-agent` 后续默认只指 `L3 + L4`，不再指代整个 Butler。
2. `Domain & Control Plane（领域与控制平面）` 拥有 `campaign / mission / verdict ledger / canonical session pointer` 真源。
3. `Projection（投影读模型）` 永远不是真源对象，只由控制面组装给产品面消费。
4. `Observability（可观测性）` 与 `Projection（投影读模型）` 必须分开；前者面向诊断审计，后者面向产品态展示。
5. `runtime_os.process_runtime` 保留兼容别名，但不再作为长期命名目标。
6. 每次升级收尾必须至少做一轮服务重启和状态复验，避免“代码已改、live 进程仍旧版本”。

## 历史术语映射

- `heartbeat`
  - 先判断是 `Product Surface（产品表面层）`、`Domain & Control Plane（领域与控制平面）` 还是 `Durability Substrate（持久化基座）`
- `guardian`
  - 当前已退役，不再视为现役组件
- `sidecar`
  - 当前通常对应旧后台自动化或旧运维链路，不直接作为现役定位词
- `multi-agent system`
  - 当前默认映射为 `Multi-Agent Protocol（多 Agent 协议层） + Multi-Agent Session Runtime（多 Agent 会话运行时）`
- `observe`
  - 当前默认映射为 `Observability（可观测性） + Projection（投影读模型）`

## 改动前默认动作

1. 先在 `01_layer_map.md` 确认主层级
2. 再在 `02_feature_map.md` 确认功能条目
3. 最后按 `04_change_packets.md` 选择最小必读包
4. 涉及系统抽象、事件契约或跨层命名时，补读 `docs/runtime/System_Layering_and_Event_Contracts.md`
5. 改动完成后默认执行：相关测试 -> `./tools/butler restart ...` -> `./tools/butler status`
