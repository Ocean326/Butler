# 0330/02A_runtime层详情：L1 Agent Execution Runtime 开发计划

日期：2026-03-30  
最后更新：2026-03-31  
状态：现役 / 0330 Agent Harness 子计划真源（L1 主轴）

关联文档：

- [00_当日总纲.md](./00_当日总纲.md)
- [02_AgentHarness全景研究与Butler主线开发指南.md](./02_AgentHarness全景研究与Butler主线开发指南.md)
- [02B_协议编排与能力包开发计划.md](./02B_协议编排与能力包开发计划.md)
- [02C_会话协作与事件模型开发计划.md](./02C_会话协作与事件模型开发计划.md)
- [02D_持久化恢复与产物环境开发计划.md](./02D_持久化恢复与产物环境开发计划.md)
- [02G_治理观测与验收闭环开发计划.md](./02G_治理观测与验收闭环开发计划.md)
- [System_Layering_and_Event_Contracts.md](../../runtime/System_Layering_and_Event_Contracts.md)
- [WORKFLOW_IR.md](../../runtime/WORKFLOW_IR.md)

## 一句话裁决

`02A` 只负责 `L1 Agent Execution Runtime`。  
这里的核心不是“再造一套产品壳”，而是把 `RuntimeHost / RuntimeKernel / provider adapter / guardrail / tracing / subagent governance` 收口成稳定执行宿主。

## 本文边界

- 主层级：`L1 Agent Execution Runtime`
- 次层级：`L2 Durability Substrate`、`Domain & Control Plane`
- 主代码目录：
  - `butler_main/runtime_os/agent_runtime/`
  - `butler_main/agents_os/runtime/`
  - `butler_main/agents_os/execution/`
- 默认测试：
  - `test_agents_os_runtime.py`
  - `test_agents_os_runtime_host.py`
  - `test_codex_provider_failover.py`
  - `test_runtime_os_root_package.py`
- 不在本文处理：
  - `WorkflowTemplate / Workflow IR` 的协议冻结，见 `02B`
  - `session / mailbox / handoff / join` 的会话语义，见 `02C`
  - `checkpoint / replay / writeback` 的持久化边界，见 `02D`
  - `risk_level / autonomy_profile / acceptance` 的治理归口，见 `02G`

## 当前已对齐能力

1. `RuntimeHost` 已能承担最小的 instance/run/resume 持久化宿主。
2. `RuntimeKernel` 已具备 guardrail inspect、trace observer、context merge、artifact bucket 等最小执行能力。
3. `provider_failover` 已形成 Codex 主备切换与 profile 回写的独立执行适配层。
4. execution runtime 已具备多步 workflow、approval gate、checkpoint resume 的最小可跑通闭环。

## 当前缺口

1. `handler -> receipt` 的 `output_bundle` 透传仍存在一致性风险，导致执行结果和外部 handler 产物可能分叉。
2. guardrail、trace、provider adapter、worker dispatch 之间的跨 provider 合同仍偏隐式，事件语义不够冻结。
3. `subagent` 目前更多停留在方法论与个别实现习惯，尚未形成“继承哪些治理策略、隔离哪些运行环境”的正式执行合同。
4. task-scoped workspace/filesystem/sandbox 还没有明确挂到 L1 宿主合同上，容易把环境治理误丢给上层 prompt 或外部壳。

## P0 开发计划

1. 修复 `output_bundle` 透传与回执归并规则，冻结 `handler output -> receipt output -> projection output` 的优先级。
2. 冻结 L1 最小执行事件合同，至少覆盖：
   - `run_started`
   - `context_prepared`
   - `guardrail_checked`
   - `worker_dispatched`
   - `worker_completed`
   - `receipt_emitted`
3. 把 `subagent` 明确定义成受同一治理壳约束的 task-scoped execution unit，而不是自由漂移的隐式 helper。
4. 明确 provider adapter 只负责执行接线与故障切换，不承载 workflow、policy、projection 真源。

## P1 开发计划

1. 把 task-scoped workspace/filesystem/sandbox profile 提升为执行宿主合同的一部分。
2. 统一不同 provider 的 execution receipt、artifact receipt、error receipt 字段，减少 provider-specific 分叉。
3. 把 `trace spans` 与 `execution receipts` 建立稳定关联键，保证 query、console、audit 能读到同一条执行证据链。
4. 为 `subagent` 补齐最小的 request/response 结构，至少包含：
   - 任务目标
   - 继承的治理参数
   - 可见 artifact/context
   - 最终回传报告

## P2 开发计划

1. 增加 runtime timeline 与资源预算可视化。
2. 增加 task profile 级别的 sandbox / network / filesystem 策略组合。
3. 为跨 provider 的 execution adapter 增加更细的 retry/fallback reason taxonomy。

## 关键合同

1. `RuntimeHost`
  - 负责 run lifecycle、resume entry、instance layout。
2. `RuntimeKernel`
  - 负责 guardrail、worker dispatch、trace、artifact merge。
3. `execution receipt`
  - 是 L1 对上游层暴露的最小完成/阻塞/失败事实，不允许由产品壳随意重写。
4. `provider adapter`
  - 只输出执行事实，不输出 workflow 真源。
5. `subagent governance inheritance`
  - 默认继承 sandbox、approval policy、risk ceiling、trace context，禁止子代理脱离父治理壳独立扩权。

## 验收口径

1. `test_agents_os_runtime.py` 覆盖：
   - 多步 workflow 执行
   - approval gate resume
   - `output_bundle` 透传一致性
2. `test_agents_os_runtime_host.py` 覆盖 run/resume round-trip。
3. `test_codex_provider_failover.py` 覆盖 provider 切换、冷却与回切规则。
4. 若后续改到 query/console 对外口径，补验 `test_console_server.py` 或 `test_orchestrator_campaign_service.py`，确认 L1 事实没有被产品层扭曲。

## 文档回写要求

1. 改 L1 执行合同后，同步回写：
   - `02_AgentHarness全景研究与Butler主线开发指南.md`
   - `02G_治理观测与验收闭环开发计划.md`
   - `docs/project-map/03_truth_matrix.md`
   - `docs/project-map/04_change_packets.md`
2. 若变更影响 `Workflow IR` 或 `checkpoint` 语义，必须同步检查 `02B` 与 `02D` 是否失真。

## 明确不做

1. 不把任何 vendor CLI 的命令形态直接当作 Butler 的执行合同。
2. 不让产品面 UI 事件直接替代 L1 receipt。
3. 不把 `subagent` 做成脱离治理、可自由扩权的“第二套 agent 系统”。
