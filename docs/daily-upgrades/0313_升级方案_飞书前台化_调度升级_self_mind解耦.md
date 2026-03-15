# 0313 升级方案：飞书前台化、调度升级、self_mind 解耦

## 1. 目标

本轮升级的目标不是继续给 Butler 叠功能，而是把它从“单轮并行、单入口承压、人格/执行混杂”的状态，升级成一个可长期运行、可监督、可验收、可动态选工具的多代理系统。

本方案覆盖四条主线：

1. 飞书 bot 重新定位为前台入口：承接讨论、澄清、任务分发、流式同步回复。
2. 心跳从“单轮并行调度器”升级为“同步 + 异步混排”的 planner-supervisor 系统。
3. planner 支持按任务特征动态选择 `cursor-cli`、`codex-cli` 与不同模型。
4. `self_mind` 从主系统剥离为可选外挂项目，但继续共享 local memory。

---

## 2. 现状判断

基于当前代码与文档，现状大体如下：

- 飞书入口已经支持流式回复、sub-agent/team 触发、CLI 热切换，但主入口仍承担了过多执行与认知注入。
- 心跳已有 `HeartbeatOrchestrator`、`TaskLedgerService`、task workspace、planner backoff、并行支路与固定新陈代谢支路。
- 任务账本已经开始具备“任务状态 + 工作区 + 最终报告”能力，但 planner 仍更像一次性调度器，而不是持续监督者。
- `self_mind` 当前深度耦合在 `memory_manager.py`、飞书 prompt 构造和心跳写回链路里，尚不是独立可开关的附加系统。

核心问题不是“不能做”，而是三类职责还没彻底分开：

- 前台对话职责
- 后台执行/监督职责
- 主观陪伴/self_mind 职责

---

## 3. 总体设计原则

### 3.1 单一真源

- 任务真源：`task_ledger.json` + `任务工作区`
- 对话真源：飞书消息流与 recent memory
- 运行期调度真源：planner run state + execution queue + branch/run receipt
- 人格/陪伴真源：独立 `self_mind` 项目

不再允许一份任务意图同时依赖“飞书上下文 + planner 临时文本 + 多份镜像 markdown”来维持。

### 3.2 前后台分离

- 飞书 bot 负责接住用户、讨论、分诊、同步反馈。
- planner/supervisor 负责调度、监督、追踪、验收。
- executor/sub-agent 负责执行，不负责全局记账和最终验收。

### 3.3 事件驱动优先，定时轮询兜底

纯“每 10 分钟醒一次”不够细；纯同步也不稳。

推荐采用：

- 事件驱动立即调度：新消息、新任务、新失败、新 branch 完成时立刻触发轻量 planner。
- 定时心跳巡检：每 10 分钟做一次全局复盘、超时清扫、上下文修复、阻塞解除建议。

也就是“事件驱动主调度 + 定时心跳监督”的混排方式。

### 3.4 Planner 不只调度，还要监督与验收
''
【用户批注】：“这里感觉planner还是角色太多了，应当想把过程相关的职责角色拆出来：
像软件全过程/工程全过程一样管理，至少包含【planner、executor、test/evaluat、验收】，每个过程应当是专职的agent角色，切应当支持更多范式/动态调整，比如【计划+若干模块并行+再计划+test/evaluate+验收不通过，提出改进意见+在执行】。这四个
而planner应当是管理者，负责在任务/项目全生命周期的调度和管理，定位应当是经理+收发汇总各阶段report，形成过程管理文档+自己每一轮的决策回执一并到任务终稿”
''

新的 planner 不应该继续膨胀成“既是 PM、又是 executor、又是 tester、又是验收员”的超级角色。

更合理的是采用 **经理制 + 轻量代码调度**：

- `Manager / Planner`
  - 只负责分诊、阶段切换、调度决策、收发各阶段 report
- `Executor`
  - 负责按当前阶段目标执行，不越级定义全局策略
- `Test / Evaluator`
  - 负责验证、失败分析、给出返工建议
- `Acceptance`
  - 负责收口、验收结论、面向用户的最终结论

代码层不要一开始就做重型分布式编排，而是先让 branch 支持 `process_role`，再用轻量服务做：

- 前台分诊
- runtime 路由
- 经理回执
- 验收回执

这样后续增删 agent 角色时，主要是增删角色文档与少量路由规则，而不是反复重写主流程。

---

## 4. 飞书 Bot 重新定位

## 4.1 目标角色

飞书 bot 改成“前台工作台 agent”，主要做四件事：

1. 讨论与澄清
2. 判断这是自己就可以完成的简单小任务还是自己+subagent就可以完成的实时任务，还是长周期、严要求的异步大任务，后者需要交给心跳机制运行
3. 实时任务触发合适的 sub-agent/team/async run
4. 持续向用户流式同步当前阶段状态

不再让飞书 bot 默认自己把所有大任务做完。

## 4.2 新的入口决策

飞书入口收到请求后，先做 `Request Intake`：

- `discussion_only`
  - 讨论、方案、发散，不入异步执行
- `sync_quick_task`
  - 预估 2-5 分钟内可完成，直接同步执行
- `sync_then_async`
  - 单线长任务先同步给出框架/第一步，流式发送给用户，再转异步继续推进，推进后同步给用户
- `async_program`
  - 大任务要先辅助用户做好规划，确认好任务细节和验收标准后，直接入队，由 planner-supervisor 维护+同步进度给用户

建议新增请求分类字段：

```json
{
  "request_id": "",
  "conversation_id": "",
  "mode": "discussion_only|sync_quick_task|sync_then_async|async_program",
  "user_goal": "",
  "urgency": "low|medium|high",
  "estimated_scale": "small|medium|large",
  "freshness_need": "low|medium|high",
  "acceptance_hint": [],
  "preferred_output": "chat|doc|patch|report"
}
```

## 4.3 飞书前台的同步体验

同步回复分两层：

- 第一层：即时流式思考/进展反馈
- 第二层：标准化状态卡片

标准状态建议固定为：

- `已接收，正在澄清`
- `已转为异步任务`
- `正在执行第 N 阶段`
- `当前阻塞/需要你决策`
- `已完成，可验收`

这样用户能持续看到 Butler 在做什么，而不是只看到一轮很长的回复。

---

## 5. 心跳升级：从一次性并行到同步 + 异步混排

## 5.1 为什么不建议只做“每 10 分钟醒一次”

只靠固定心跳的问题：

- 新任务响应慢
- 短任务被不必要延迟
- branch 完成后不能立即进入下一阶段
- 用户刚补充关键信息时，系统无法快速重规划

所以更优方案不是纯异步心跳，而是混排：

- 同步路径负责即时性
- 异步路径负责大任务续航
- 心跳负责监督和兜底

## 5.2 推荐调度架构

### 层 A：前台同步调度

触发时机：

- 飞书新消息
- 卡片动作
- 用户追加澄清

职责：

- 判断是否直接同步执行
- 生成 async task/program
- 对用户做阶段性反馈

### 层 B：事件驱动 planner

触发时机：

- 新任务入队
- branch 完成
- branch 失败
- 用户补充信息导致上下文变化

职责：

- 只规划受影响任务，不扫全局
- 重新选择模型/工具
- 决定是否拆出下一批 branch

### 层 C：周期性 supervisor heartbeat

建议周期：

- `2-3 分钟` 轻巡检：只看活跃任务和超时 branch
- `10 分钟` 中巡检：看全局任务、健康度、上下文新鲜度
- `60 分钟` 深巡检：做沉淀、压缩、治理、验收补文档

职责：

- 维护任务健康状态
- 检测 branch 卡死/重复失败
- 做跨轮总结与验收补齐
- 推动长期任务收口，不让它们无穷续命

---

## 6. Planner 强化：从调度器升级为 Supervisor

【用户批注】：这点和我上面写的哪个基本一致，不过具体的实验我建议以：仔细编排的多角色agent+轻量化代码调度的形式进行，便于后续增删改服务角色

## 6.1 新职责拆分

建议把现有 `HeartbeatOrchestrator` 的职责拆成四个服务，并让 orchestrator 退化为兼容 facade：

- `request_intake_service.py`
  - 飞书入口分诊、同步/异步判定、生成任务规范
- `planner_service.py`
  - 任务拆解、branch 规划、工具/模型选择
- `supervisor_service.py`
  - 追踪 branch 状态、超时、失败重试、依赖解锁
- `acceptance_service.py`
  - 生成验收结论、最终总结、回写任务 workspace/final_report

本轮最小落地优先做三件事：

1. `request_intake_service.py`
   - 前台先把请求分成 `discussion_only / sync_quick_task / sync_then_async / async_program`
2. `runtime_router.py`
   - branch 级别自动选择 `cursor/codex/model`
   - 加入 `codex` 5h 周期内的配额守卫
3. `acceptance_service.py`
   - 把经理决策、运行时信息、验收结论落入 `task_ledger` 与 `final_report`

## 6.2 任务生命周期
【用户批注】：同上，生命周期的判定和管理应当交由【经理】判断和推进，而不是写死到状态机里

建议给任务加更明确的状态机：

- `queued`
- `triaged`
- `planned`
- `running`
- `waiting_input`
- `blocked`
- `reviewing`
- `accepted`
- `closed`
- `archived`

branch 状态单独维护：

- `ready`
- `running`
- `succeeded`
- `failed_retryable`
- `failed_terminal`
- `superseded`

这样 planner 就能知道：

- 任务是否还在推进
- 哪个 branch 卡住了
- 是否该收口而不是继续拆

## 6.3 健康度与验收

【用户批注】：同上，生命周期的判定和后续动作应当交由【验收员】判断，而不是写死到状态机里

每个 async task/program 应维护：

- `progress_score`
- `context_health`
- `retry_count`
- `staleness_seconds`
- `last_supervised_at`
- `acceptance_status`

验收不再只是“执行结束就 done”，而要检查：

1. 是否满足 acceptance criteria
2. 是否有明确产出物
3. 是否已写 final summary / final report
4. 是否需要对用户发送收尾同步

---

## 7. 动态选择 Cursor / Codex / 模型

【用户批注】：需要注意，codex有5h周期限额，调度和使用考虑需要加上周期内合理使用限额

## 7.1 为什么必须做动态路由

当前已经有 `cli_runtime` 热切换，但还是偏“本轮指定”。
升级后应让 planner 自动做 runtime routing，而不是所有任务都走同一个 CLI/模型。

## 7.2 选择维度

对每个 branch 打分：

- `task_difficulty`
- `urgency`
- `context_freshness_need`
- `tooling_need`
- `patch_risk`
- `verification_need`
- `cost_budget`
- `latency_budget`

## 7.3 推荐路由策略

### 适合 `cursor-cli`（只有 auto）

- 适合工程
- 适合简单任务

### 适合 `codex-cli`

- 涵盖gpt 5.1 5.2codx gpt 5.4（这个可能需要动态获取让选择模型自己判断）

### 模型选择建议

- `fast/cheap`：轻量分类、摘要、清扫、低风险维护
- `balanced`：多数实现/文档/中等复杂调试
- `strong`：重构设计、复杂调度、失败分析、最终验收

## 7.4 最小落地方案

在现有 `cli_runtime.py` 之上新增：

- `runtime_router.py`
  - 根据 branch metadata 产出 `runtime_request`
- `model_policy.py`
  - 维护不同任务类型对应的默认模型档位

branch 规划结果新增字段：

```json
{
  "runtime_profile": {
    "cli": "cursor|codex",
    "model": "auto|gpt-5|...",
    "reasoning_effort": "low|medium|high",
    "why": ""
  }
}
```

另外需要补一个过程角色字段：

```json
{
  "process_role": "executor|test|acceptance|manager"
}
```

这样 planner 才是在“编排阶段”，而不是在一个 branch prompt 里偷偷把全过程揉成一团。

---

## 8. self_mind 解耦方案

## 8.1 新定位

`self_mind` 不再是 Butler 主系统的默认内核流程，而是一个可选启动的附加项目：

- 独立聊天窗口
- 独立 prompt 文档
- 独立 recent memory
- 独立入口代码
- 共享 local memory / long-term memory

## 8.2 边界重定义

主系统保留：

- 对话 recent
- 任务 recent
- local memory
- task ledger
- planner/supervisor 所需运行状态

外挂 `self_mind` 保留：

- 情感陪伴
- 主观续思
- relationship/inner reflection
- 非任务导向的心理活动流

共享但不互相覆盖：

- `local_memory`
- 用户画像
- 部分长期认知索引

## 8.3 代码拆法

当前 `memory_manager.py` 里与 `self_mind` 相关的循环、bridge、direct talk、reflection 等逻辑应迁出为：

- `self_mind_app/`
  - `self_mind_runner.py`
  - `self_mind_service.py`
  - `self_mind_prompt_builder.py`
  - `self_mind_memory_bridge.py`

主系统只保留一个薄接口：

- `self_mind_bridge_client.py`
  - 判断是否启用外挂
  - 提供共享记忆读写桥

## 8.4 启动模式

建议支持：

- `butler core`
  - 不启动 self_mind
- `butler core + self_mind`
  - 启动附加窗口/附加服务

配置层示意：

```json
{
  "optional_apps": {
    "self_mind": {
      "enabled": false,
      "entry": "./self_mind/self_mind_runner.py",
      "share_local_memory": true
    }
  }
}
```

---

## 9. 建议的目标模块图

## 9.1 前台入口

- `feishu_frontdesk_service.py`
- `request_intake_service.py`
- `conversation_status_service.py`

## 9.2 任务与调度

- `task_program_service.py`
- `planner_service.py`
- `supervisor_service.py`
- `acceptance_service.py`
- `runtime_router.py`
- `model_policy.py`
- `execution_queue.py`

## 9.3 执行层

- `agent_team_executor.py`
- `branch_executor_service.py`
- `review_executor_service.py`

## 9.4 记忆与共享层

- `memory_backend.py`
- `task_ledger_service.py`
- `recent_memory_service.py`
- `local_memory_index_service.py`
- `self_mind_bridge_client.py`

## 9.5 可选外挂

- `self_mind_app/*`

---

## 10. 与当前代码的精确重构映射

## 10.1 `agent.py`

当前问题：

- 飞书 prompt 注入了过多主意识与 self_mind 逻辑
- 前台入口与主观陪伴耦合

改造：

- 保留消息收发、流式回复、卡片交互
- 把请求分诊迁到 `request_intake_service.py`
- 把 self_mind 注入改成可选 profile，不再默认硬耦合

## 10.2 `heartbeat_orchestration.py`

当前问题：

- 同时承担 planner、branch 运行、结果汇总、snapshot 持久化

改造：

- `HeartbeatOrchestrator` 退化为兼容 facade
- 规划逻辑迁到 `planner_service.py`
- 监督逻辑迁到 `supervisor_service.py`
- 总结/收尾迁到 `acceptance_service.py`

## 10.3 `task_ledger_service.py`

当前优势：

- 已经有任务状态、工作区、最终报告雏形

继续升级：

- 增加 `program_id`、`branch_id`、`acceptance_status`、`runtime_profile`
- 增加 branch/run receipt 存储
- 支持 supervisor 写健康度与验收记录

## 10.4 `memory_manager.py`

当前问题：

- self_mind、recent、heartbeat、bridge、写回逻辑过重

改造：

- 逐步把 `self_mind loop`、`direct talk`、`bridge review` 迁出
- 保留 recent/local memory 与兼容写口
- 最终让它退化为 memory facade

## 10.5 `cli_runtime.py`

改造：

- 保持 provider 适配层
- 不再自己决定“何时用什么”
- 决策上移到 `runtime_router.py`

---

## 11. 推荐实施顺序

这里采用的是 **superpower 稳定工程范式** 的思路：

- 单一真源
- 边界清晰
- 可回溯
- 小步自我维护

所以实施顺序不追求一次性革命，而是先搭骨架，再逐步替换旧职责。

## 11.0 本轮已落地的最小骨架

本轮先把“经理制多阶段 agent”的最小工程骨架落到代码：

- 前台分诊：新增 `request_intake_service.py`
- 运行时路由：新增 `runtime_router.py`
- 验收回执：新增 `acceptance_service.py`
- 心跳 branch：支持 `process_role` 与 `runtime_profile`
- task ledger / workspace：开始记录 `program_id`、`manager_state`、`acceptance_status`、`runtime_profile`

这不是终局，但它已经把“前台 / 调度 / 执行 / 验收”从纯文本想法推进成了可扩的代码骨架。

## Phase 1：飞书前台化

目标：

- 飞书入口只做讨论、分诊、同步反馈、异步任务创建

代码动作：

- 新增 `request_intake_service.py`
- 在 `agent.py` 接入 `mode=discussion/sync/async`
- 给用户新增异步状态提示模板
- 前台默认按“经理”口径回复，不再假设所有任务都要当前轮直接做完

## Phase 2：task program + supervisor

目标：

- 大任务不再只是一轮 plan，而是有可持续监督的 task program

代码动作：

- 扩展 `task_ledger_service.py`
- 新增 `supervisor_service.py`
- 增加 branch receipt / acceptance receipt
- 生命周期的推进以经理/验收员判断为主，状态字段只做事实记录，不做唯一裁决者

## Phase 3：动态 runtime routing

目标：

- 根据任务类型动态选择 `cursor-cli` / `codex-cli` / model

代码动作：

- 新增 `runtime_router.py`
- branch schema 加 `runtime_profile`
- planner 输出 runtime 选择理由
- 对 `codex` 增加 5h 周期配额守卫，避免高强度任务把额度打空

## Phase 4：self_mind 外挂化

目标：

- 主系统可无 `self_mind` 运行
- `self_mind` 可独立启动

代码动作：

- 从 `memory_manager.py` 抽离循环与 direct talk
- 新建 `self_mind_app/`
- 用配置控制启停

## Phase 5：验收与治理闭环

目标：

- planner 真正具备监督、总结、验收能力

代码动作：

- 新增 `acceptance_service.py`
- 任务完成必须写 `final_report.md`
- 完成后自动产出用户可读总结

---

## 12. 关键指标

需要用指标判断“效率”和“质量”是否真的提升。

建议至少跟踪：

- `time_to_first_response`
- `time_to_first_plan`
- `task_completion_time`
- `replan_count`
- `retry_count`
- `acceptance_pass_rate`
- `user_interruption_rate`
- `stalled_task_count`
- `context_rebuild_count`
- `wrong_runtime_selection_count`

判定原则：

- 效率提升：首响应更快、短任务更少被异步拖慢、长任务平均卡死率下降
- 质量提升：最终 summary 更完整、验收通过率更高、重复返工更少

---

## 13. 关于 “superpower” 范式的吸收

`/superpower/群agent_稳定工程范式.md` 的核心值得直接吸收进本次升级：

- 单一真源
- 边界清晰
- 可回溯
- 小步自我维护

本轮代码落地就是按这四条来的：

- 不额外造一套影子账本，而是在 `task_ledger` 上加经理/验收回执
- 不把 runtime 决策散落到每个调用点，而是集中在 `runtime_router`
- 不让前台继续扮演全能执行器，而是先做 `request intake`
- 不把验收结论藏在长回复里，而是显式写到 `final_report`

本方案本质上就是把这些原则落到 Butler 的实际运行栈：

- 飞书 bot 是前台，不再混当全部执行器
- planner 不只是计划器，而是监督者
- task ledger 成为明确任务真源
- self_mind 退出主执行链，避免主系统人格/执行纠缠

---

## 14. 结论

最优方案不是“全同步”也不是“纯 10 分钟异步 planner”，而是：

- 前台同步讨论与快速执行
- 事件驱动的即时重规划
- 周期性心跳监督与治理
- 强化的 planner-supervisor-acceptance 闭环
- 动态的 CLI/模型路由
- `self_mind` 外挂化、主系统去耦

这套方案比当前架构更稳定的关键，不在于并行更多，而在于：

- 任务有生命周期
- planner 有监督责任
- 验收有独立收口
- 工具/模型选择有明确策略
- 陪伴人格与主任务系统分开演化
