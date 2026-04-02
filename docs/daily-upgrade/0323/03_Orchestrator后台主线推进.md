---
type: "note"
---
# 03 Orchestrator 后台主线推进

日期：2026-03-23\
时间标签：0323_0003\
状态：进行中

## 最新判断（2026-03-23 03:14:54）

1. `03 Orchestrator` 已经从“后台账本层 / 规划层”进入真实施工，不再只是概念推进。

2. 当前最准确的阶段判断是：

**orchestrator 已具备最小 compile + control plane 雏形，但还没有成为长期目标里的完整 execution kernel。**

3. 当前已经落地的关键点应固定承认：

* `workflow_ir`

* `compiler`

* 最小 `workflow_vm`

* approval gate

* workflow-backed session / writeback 链路

4. 当前最需要防止的误判是：

* 误以为 orchestrator 已经完成内核化

* 误以为只要继续扩 store / bridge 就能自然长成 workflow VM

5. 因此路线纠偏应明确为：

**下一步先打实&#x20;**`IR -> VM -> gate -> writeback`**，不再优先扩更多桥接壳层，也不让 orchestrator 重新滑回 branch 调用器。**

## 主线

1. `orchestrator` 今天的目标不再是“继续做后台唯一现役 runtime”的抽象口径，而是要成为 Butler 长期目标下的 **Mission / Control Plane**。

2. 今日不再以“继续补 store / model / bridge 骨架”为主要目标，而是要围绕 `Workflow IR -> Workflow VM -> Framework Compiler` 总轴线重新理解 orchestrator。

3. `orchestrator` 必须开始从“mission / node / branch 账本层”向“编译与控制层”推进，而不是继续停留在 branch 调用器。

4. `multi_agents_os` 只作为被消费的协作底座存在；workflow 编译、派发边界、回写与观测仍由 `orchestrator` 主线负责。

## 参照长期架构文档后的重新判断

结合 外部多Agent框架调研与Butler长期架构规划_20260323.md，当前 Butler 最大缺口不再是“是否有 mission / session 模型”，而是：

1. 缺统一 `Workflow IR`。

2. 缺真正的多步执行引擎 / workflow VM。

3. 缺 typed collaboration substrate 上的完整执行语义。

4. 缺 verification / approval / recovery 作为第一类执行语义。

5. 缺 framework-native compiler，把外部方法论编译成 Butler 内部统一语法。

因此，今天的 orchestrator 推进不能只停留在“再接几条桥”，而是要开始承担这些长期能力的第一轮产品化落地。

## 当前状态

1. `butler_main/orchestrator/` 已具备：

   * models

   * stores

   * scheduler

   * service

   * runner

   * observe

   * research_bridge

   * execution_bridge

2. 当前未完成的已经不只是产品级后台最小闭环，而是：

   * `mission/node` 还没有统一编译到 Butler 内部 workflow 语言

   * `orchestrator` 还没有消费一个真正的 workflow VM

   * verification / approval / recovery 仍主要停在对象和回执层

3. 真正缺口集中在六类：

   * `MissionNode -> Workflow IR` 编译链路

   * `MissionNode -> workflow session` 稳定引用

   * `MissionNode -> workflow execution` 真实跑通

   * `collect / judge / writeback` 最小闭环

   * verification / approval / recovery 执行化

   * framework-native ingress 还未出现

## 今日总目标

1. 让 `orchestrator` 从“后台现役控制面口径”迈向“真正的 compile + control plane”。

2. 让 `orchestrator -> Workflow IR -> workflow execution -> writeback` 至少形成一条明确的最小路径。

3. 把 `research` 的场景执行继续往 `orchestrator` 背后收，而不是让 research 继续像旁路系统。

4. 明确下一阶段的真正施工对象不再是更多 store，而是：

   * Workflow IR

   * workflow VM / multi-step execution semantics

   * verification / approval / recovery 执行化

   * framework compiler 的 orchestrator 接口

## 今日计划

### P0 后台职责边界冻结

1. 明确 `orchestrator` 是后台唯一现役控制面。

2. 明确 `heartbeat` 不再是后台主 runtime。

3. 明确 `multi_agents_os` 不是第二个后台主线。

### P1 Workflow IR 入口预埋

1. 明确 `MissionNode` 编译到 `Workflow IR` 的目标字段。

2. 明确 `runtime_plan` 到 `Workflow IR` 的过渡语义。

3. 明确 branch 与 workflow 的关系不再只是松散 metadata 关联。

### P2 最小闭环推进

1. 推进 `MissionNode -> workflow session` 的稳定引用与写回。

2. 推进 `MissionNode -> execution bridge` 的真实执行链路。

3. 推进 `branch collect / judge / writeback` 的最小闭环。

### P2 Research 主链收编

1. 继续推进 `orchestrator -> research_bridge`，避免 research 长期悬在旁路。

2. 明确 research scene 执行时：

   * 谁创建 workflow session

   * 谁维护 branch 状态

   * 谁回写 scenario instance

3. 保证 research 继续做 application / scenario plane，而不是反向长成后台控制面。

### P4 长期能力落点预埋

1. 开始明确 Butler 内部的 `Workflow IR` 目标字段与落点。

2. 开始明确 workflow VM / graph execution semantics 下一轮落在哪一层。

3. 开始明确 verification / approval / recovery 如何从 receipt 变成执行语义。

4. 开始明确 framework compiler 未来如何从 orchestrator 进入 runtime。

5. 今日不要求全部实现，但必须把这些能力从“口头愿景”推进成“下一轮明确落点”。

## 今日施工顺序

1. 先固定后台职责边界。

2. 再推进最小执行闭环。

3. 再推进 `orchestrator -> research` 接线收口。

4. 最后补长期执行语义的落点说明与观察/回归。

## 明确暂缓

1. 暂缓让 orchestrator 反向吞并前台 chat 路由。

2. 暂缓做大规模物理目录搬迁。

3. 暂缓在主闭环未跑通前再引入新的后台大抽象层。

4. 暂缓把 multi_agents_os 当成后台替代品。

## 验收标准

1. 必须能一句话说清：后台今天的唯一现役推进线是什么。

2. 必须能列出 `orchestrator` 今日新增的真实接管点，而不是只有抽象名词。

3. 必须能说明：哪些后台职责已经从 heartbeat 剥离，转到 orchestrator。

4. 必须能说明 Butler 的 `Workflow IR / workflow VM / verification semantics` 下一轮准备落在哪。

5. 相关观测和回归至少还能支撑最小可信验证。

## 追加记录

### 2026-03-23 当前追加

* `MissionNode -> Workflow IR` 已正式落到代码：`orchestrator/compiler.py` + `orchestrator/workflow_ir.py` 已形成最小编译层，dispatch 不再只直接消费散落的 `runtime_plan`。

* `orchestrator/workflow_vm.py` 已建立一版最小 workflow VM，但当前职责仍主要是“按 IR 选择执行引擎”，即在 `execution_bridge` 与 `research_bridge` 之间路由，还不是长期文档所要求的完整多步执行内核。

* `approval gate` 已进入执行链：branch 成功后若 IR 要求 approval，会真实进入 `awaiting_decision` 停机态，等待显式批准/拒绝，而不是直接继续后续判断。

* 当前施工点已收紧为：把 `verification gate` 也从“默认总会跑 judge”收口成“由 Workflow IR 显式控制是否经过验证闸门”，继续保持代码面简洁，不扩 recovery/scheduler。

### 2026-03-23 三项收紧定版

1. `verification gate` 现正式定为：

   * 归 `orchestrator` 控制面所有，不归 `workflow_vm`、`execution_bridge` 或 `multi_agents_os`

   * 语义只承认两档：`required` / `skip`

   * `required` 时进入 `judge_adapter`；`skip` 时直接 `writeback + done`

   * 默认口径是 `required`，只有 `Workflow IR.verification` 显式关闭时才跳过

2. 最小 `recovery action` 现正式定为：

   * 当前轮只承认 `retry` / `repair` / `disabled`

   * 不扩 `replay` / `compensation` / `pause-resume`

   * `max_attempts` 优先由 `Workflow IR` 给出，未声明时才回落全局 policy

   * recovery 仍由 `orchestrator.service` 触发和记账，不把恢复执行语义提前伪装成完整 kernel

3. `workflow VM` 与 `agents_os` 的长期边界现正式定为：

   * 当前 `workflow_vm` 只是 `dispatch_router`，负责按 `Workflow IR` 选执行引擎并记录边界事件

   * 普通 node 当前仍走 `workflow_vm -> execution_bridge -> agents_os runtime`

   * `research_scenario` 当前仍走 `workflow_vm -> research_bridge -> research manager`

   * `orchestrator` 保留 control plane / governance gate / writeback 主权

   * `agents_os` 长期负责 execution kernel，`multi_agents_os` 只负责 collaboration substrate

4. 这一版定版已经落实到代码口径：

   * `orchestrator/workflow_ir.py` 已新增 gate policy 与 execution boundary 摘要

   * `orchestrator/service.py` 已改为直接消费显式 verification / approval / recovery policy

   * `orchestrator/workflow_vm.py` 已把 `dispatch_router` 边界写入 `workflow_vm_executed` 事件

5. 因此，当前文档不再允许使用下面这些模糊说法：

   * “workflow_vm 已经接近完整 execution kernel”

   * “recovery 现在什么动作都可以挂进去”

   * “judge 默认总会跑，是否验证只是实现细节”

### 2026-03-23 03:14:54 进度复核

1. 本轮复核确认，这条主线已经具备“代码 + 测试 + 运行链”的三件套：

   * 代码面已有 `workflow_ir.py`、`compiler.py`、`workflow_vm.py`

   * `service.py` 已把 `workflow_ir` 编译、approval gate、writeback 接回主链

   * 测试面已有 `test_orchestrator_workflow_ir.py`、`test_orchestrator_workflow_vm.py`、`test_orchestrator_runner.py`

2. 当前最准确的阶段判断是：

   * `orchestrator` 已从纯账本层推进到“最小 compile + control plane”

   * 但它还没有长成长期目标中的完整 workflow execution kernel

3. 因此这条 worker 目前既不是“还在规划”，也不是“已完成内核化”，而是：

**已经进入真实施工，但还处于最小 VM / gate / writeback 的打底阶段。**

1. 这也意味着下一步不该继续分散扩 store/bridge，而应优先收紧：

   * verification gate

   * 最小 recovery action

   * workflow VM 与 `agents_os` 长期边界

### 2026-03-23 运行入口追加

1. `orchestrator/runner.py` 的默认运行入口已补齐装配：

   * 当 `auto_execute=true` 且调用方未显式注入 bridge / VM 时，runner 会自动组装

   * `service + CLI runtime adapter + execution_bridge + research_bridge + workflow_vm`

2. 这意味着当前最小运行流已经从“代码能力存在但要手工注入”推进到“standalone runner 默认可跑”：

   * 普通 node 默认走 `workflow_vm -> execution_bridge -> CLI runtime`

   * `research_scenario` node 默认仍走 `workflow_vm -> research_bridge`

3. 现阶段的准确表述应是：

   * **最小入口与最小运行流已就位**

   * 但安全配套、恢复语义、真正的长期 `agents_os` execution kernel 仍未完成

4. 因此，接下来可以先做运行检测，\
   不必再等待新的大层级抽象补齐后才验证最小链路。

### 2026-03-23 Recovery 语义追加

1. `recovery` 已从“IR 里有字段、主链里有 repairing 状态”推进到最小执行语义：

   * branch 失败会按 `Workflow IR.recovery` 判断是否允许 retry

   * judge 返回 `repair` 也会消耗 recovery budget，而不是无限修复循环

   * `max_attempts` 开始优先由 IR 决定，未声明时再回落到全局 policy

2. 这意味着当前 `IR -> VM -> gate -> writeback` 链路里，`recovery` 不再只是占位字段，而是已经进入：

   * `recovery_scheduled`

   * `recovery_skipped`

   * `repair_exhausted`

3. 这三类可观测事件

4. 这一轮仍然只做最小 retry / repair，\
   不扩 replay / compensation / pause-resume 编排。

### 2026-03-23 定版后落实结果

1. `verification gate` 已落实为显式 policy：

   * `service.py` 不再靠分散的默认值判断 gate，而是统一读取 `Workflow IR` 归一化 policy

   * `verification_skipped` / `judge_verdict` 事件现在会带出 `verification_policy`

2. 最小 `recovery action` 已落实为显式 policy：

   * `service.py` 统一只承认 `retry` / `repair` / `disabled`

   * `recovery_skipped` / `recovery_scheduled` / `repair_exhausted` 事件现在会带出 `recovery_policy`

   * 若显式声明了当前轮不支持的 recovery 动作，将按 `workflow_ir_recovery_unsupported` 观测并直接失败，而不是继续模糊兜底

3. `workflow VM` 与 `agents_os` 的边界已落实为显式事件：

   * `workflow_vm_executed` 事件现在携带 `boundary`

   * 其中固定写明：

     * `vm_role=dispatch_router`

     * `control_plane=orchestrator`

     * 普通执行链 `execution_owner=agents_os`

     * research 场景链 `execution_owner=research`

4. 本轮对应验证已补到测试：

   * `test_orchestrator_workflow_ir.py`

   * `test_orchestrator_workflow_vm.py`

   * `test_orchestrator_core.py`

### 下一阶段计划（收紧版）

1. 先落最小 `approval gate`：\
   branch 成功后若 IR 要求 approval，则 mission 进入 `awaiting_decision`，node 进入阻塞态，等待显式批准/拒绝，而不是立即继续 judge。

2. 再落最小 `verification gate`：\
   judge 与 verify 不再只是“成功后统一默认跑一下”，而要由 workflow IR 决定是否必须经过验证闸门；若明确跳过，则直接完成 node。

3. 再落最小 `recovery action`：\
   先只支持 retry / repair 级恢复，不在这一轮扩成完整 replay/compensation 系统。

4. 本轮仍暂不扩 framework compiler；\
   要先把 `Workflow IR -> workflow VM -> governance gate` 这条内核路径打实，否则 compiler 只会继续生成无法严格执行的中间对象。

### 2026-03-23 00:03

* 本页作为 `0323` 的后台主线入口建立。

* 今日的后台工作不再以“继续规划”为目标，而是以“完成真实接管”为目标。

⠀
