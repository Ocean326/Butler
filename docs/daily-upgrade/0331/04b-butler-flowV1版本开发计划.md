# 04b-butler-flowV1 版本开发计划

日期：2026-03-31  
状态：已按本稿完成 V1 第一轮实现并通过回归（2026-03-31）  
定位：`Product Surface` 与 `L1/L2/L4` 的前台轻量主线，不替代后台 `campaign/orchestrator` 真源

关联输入：

- `0331 前台 Butler Flow CLI 收口（workflow shell 历史别名）`
- `0331 Butler Flow CLI 交互式升级：对标调研与技术方案`
- `0331 前台长 Agent 监督 Workflow 产品化草稿计划`
- `0330 Agent Harness 全景研究与 Butler 主线开发指南（含 DeerFlow / Codex Harness / Deep Agents 等整理）`

---

## 一句话裁决

`04b-butler-flowV1` 不做“大而全的前台产品平台”，而是收口成一条 **agent-led、operator-steerable、foreground-attached** 的轻量主线：

`Draft/Launcher -> Supervisor Agent Inner Loop -> Executor/Judge/Recovery -> Operator Intervention -> Resume/Handoff`

它的核心不是“再造一个 workflow 编辑器”，而是：

1. **让 agent 成为前台 flow 的决策面核心**；
2. **让 harness 负责 pause / resume / receipt / trace / audit / handoff 边界**；
3. **保持功能简约，但交互体验显著强于当前 print + input 壳**；
4. **保持自由度，不把 phase/节点图写死成僵硬 DSL**；
5. **实现范围控制在一轮大请求里可以持续完成，不拆成需要频繁来回确认的碎任务。**

---

## 0. 本版目标与边界

## 0.1 本版目标

V1 只追 4 件事：

1. 把当前 `butler-flow` 从“Codex 主执行 + Cursor 守看”的外环，升级成 **显式 supervisor agent 主控的前台 flow**；
2. 把当前 `flow state + phase history` 升级为 **run / turn / action / trace / receipt** 结构；
3. 把当前 CLI 从“命令行工具态”升级成 **可扫视、可恢复、可介入** 的附着式 operator 壳；
4. 保持现有前后台边界：**仍然不直接进入 campaign/orchestrator 主链**。

## 0.2 本版不做

1. 不做完整浏览器 Workflow Studio；
2. 不做后台 campaign 主链改造；
3. 不做重型全屏 Textual TUI 作为首版必选；
4. 不把外部框架 DSL、术语、对象名直接灌回 Butler 真源；
5. 不引入“自由放养多 agent swarm”作为默认模式；
6. 不做嵌套 vendor 原生 TUI（避免 PTY / resize / 双层交互问题）。

## 0.3 本版产品定位

V1 的正确定位是：

- **foreground attached runtime**
- **agent-led but operator-steerable**
- **可恢复、可审计、可升级到后续产品面**

它不是：

- 后台 `campaign` 的前台皮肤；
- 单纯更花哨的 CLI；
- 一个靠 prompt 放养的“超自由 agent 模式”。

---

## 1. 现有真源与外部参考，如何共同收口

## 1.1 Butler 当前现役事实（必须继承，不可打破）

当前真源已经把 `butler-flow` 固定为 L1 前台附着执行运行时，具备 `run / resume / status / list / preflight`、本地文件状态、Codex 主执行、Cursor 守看和判定，但**不进入** `campaign/orchestrator` 主链。现有本地状态字段至少包括 `workflow_id`、`workflow_kind`、`goal`、`guard_condition`、`current_phase`、`phase_history`、`codex_session_id`、`last_cursor_decision`、`attempt_count`、`status`。fileciteturn7file2

CLI 升级草稿同时指出，当前主要差距是：交互壳弱导航、流式与 judge 输出混杂、缺少统一布局，以及存在嵌套 TTY 风险；因此更推荐 **Butler Own UI + 子进程机器可解析输出** 的路线，而不是在 Butler 里再嵌一个厂商原生 TUI。fileciteturn7file0

前台长 workflow 草稿则进一步要求：前台 run 要变成正式产品对象，显式引入 `ForegroundWorkflowRun`、`WorkflowTurnRecord`、`WorkflowActionReceipt`、`WorkflowHandoffPacket`，并把 supervisor agent 作为主控制循环，同时保留 run lifecycle、approval、receipt/trace、handoff 四条 harness 硬边界。fileciteturn7file1

## 1.2 外部参考，本版真正吸什么

本版不“换框架”，只吸 5 条外部共识：

1. **Codex Harness / App Server**：用 `thread / turn / item` 事件边界组织 agent loop，用 approval/ask-human 做正式中断点；OpenAI 公开把 Codex harness 的关键部分描述为 thread lifecycle、tool execution/extensions 和 App Server，且强调 “Humans steer. Agents execute.”。citeturn268040search0turn268040search4
2. **Deep Agents**：把 planning、filesystem、subagents、memory、context management 视为 agent harness 原语，而不是散落在 prompt 外的补丁。LangChain 明确写到 Deep Agents 建立在 LangGraph 之上，并增加 planning、file systems、spawn subagents 等能力。citeturn268040search1turn268040search13
3. **DeerFlow 2.0**：把 runtime、gateway、frontend、sandbox、memory、subagent、artifacts 做成一个全栈 super agent harness；其后端文档明确写到它是 full-stack architecture，运行在 per-thread isolated environments 中，并通过 middleware 链组织 thread data、sandbox、summarization、guardrail、clarification 等能力。citeturn268040search2turn268040search6
4. **Claude Agent SDK / Claude Code**：把 tools、agent loop、context management、subagents、hooks、skills 做成可编程的 agent 工作环境。Anthropic 当前官方文档明确说 Agent SDK 提供与 Claude Code 相同的 tools、agent loop 和 context management。citeturn268040search3turn268040search7turn268040search16
5. **LangGraph**：不拿它的 DSL 做内部真源，但吸收它的 durable execution / interrupts / resume 语义，作为 V1 的恢复与 lineage 心智底座。Deep Agents 官方也直接把自己定位成建立在 LangGraph 之上的 harness。citeturn268040search1

## 1.3 本版收口后的总原则

V1 只采取下面这个组合：

`stable harness spine + agent-driven inner loop + lightweight operator shell`

不采取：

`smart UI + free-form agent + hidden state`

---

## 2. 04b 的正式目标口径

## 2.1 V1 主张

`butler-flowV1` 的核心主张是：

1. **agent 是控制面核心**：由 supervisor agent 持有长线程和当前上下文，决定下一步是 plan / execute / review / recover / ask-human / delegate；
2. **harness 不是裁决内容，而是裁决边界**：负责状态对象、turn 记录、trace、receipt、暂停恢复、权限与 handoff；
3. **自由性来自 agent 调度，不来自取消结构**：允许 supervisor 动态选择下一步，但必须落在结构化 turn/action 合同里；
4. **交互体验来自可视 operator surface，不来自更复杂的 prompt**；
5. **工程上先做薄层闭环，再往 console 和 campaign 升格。**

## 2.2 V1 用户体验目标

对操作者来说，这版 should feel like：

1. 启动时像一个简洁的 agent flow launcher；
2. 运行时能看见：当前目标、当前 phase / turn、最近 judge、最近 artifact、最近 operator action；
3. 过程中能快速做 4 类动作：`pause`、`resume`、`append_instruction`、`retry/recover`；
4. 中断后下次能从最近 flow 直接回来；
5. 不需要理解后台 campaign，也不需要理解复杂节点图。

---

## 3. V1 核心设计：agent 做决策面，harness 守硬边界

## 3.1 决策面对象：Supervisor Agent

V1 显式引入一个 `Supervisor Agent`，作为前台 flow 的决策面核心。

它负责：

1. 收紧目标；
2. 判断当前处于 `plan / execute / fix / review / recover / waiting_operator` 哪类工作语义；
3. 决定是否调用 executor；
4. 决定是否让 judge/reviewer 复查；
5. 决定是否给出 bounded recovery；
6. 决定是否请求 operator；
7. 决定是否触发 selective delegation；
8. 决定是否建议 handoff。

### Supervisor 不是做什么

它**不是**：

1. 直接落盘 run status 的唯一真源；
2. 直接控制 pause / resume / approval 的最终裁决器；
3. 绕开 trace/receipt/audit 的黑箱循环；
4. 亲自下场做 repo 改动；普通 bug 修复由显式 `fix` turn 驱动 executor 执行。

## 3.2 执行面对象：Executor / Judge / Recovery

V1 保持 3 个受控执行角色：

1. `Executor Agent`
   - 负责 repo 内实际探索、修改、命令执行、文件操作；
   - 默认仍以 Codex 为主执行能力来源。
2. `Judge / Reviewer Agent`
   - 负责结构化 verdict：`advance / retry / complete / abort / ask_operator / recover`；
   - 当前还负责给出 `issue_kind / followup_kind`，把 `agent_cli_fault`、普通 bug、plan gap、service fault 拆开；
   - 当前可继续沿用 Cursor judge 的结构化输出心智。
3. `Recovery Agent`
   - 只在失败或低置信度时触发；
   - 产出 bounded recovery proposal，而不是无限 retry。

补充裁决：

- `fix` 是显式 turn 语义，不是新的持久 phase。
- `fix` 默认复用同一 Codex session。
- `fix` 只处理本地 agent CLI 调用链故障，不处理业务级 repo bug。
- 连续 `agent_cli_fault` auto-fix 超过 `2` 轮后，默认转 `ask_operator`，而不是无限重试。

## 3.3 Harness 四条硬边界

V1 固定保留下面 4 条硬边界：

1. `run lifecycle boundary`
   - 谁可以创建/暂停/恢复/完成/失败 run；
2. `approval boundary`
   - 哪些动作必须等 operator；
3. `trace / receipt boundary`
   - 每轮决策和动作怎样被记录；
4. `handoff boundary`
   - 何时能升格到更高层对象，何时不能。

这 4 条边界来自你现有前台产品化草稿的主张，也和 Codex Harness、DeerFlow、LangGraph 的收口方式一致。fileciteturn8file1 fileciteturn8file8 citeturn268040search0turn268040search2

---

## 4. V1 形式化对象（最小集合）

V1 只新增最小必要对象，不一次引入过多层级。

## 4.1 `FlowDraftV1`

用途：启动前草案对象。

建议字段：

- `draft_id`
- `workflow_kind`
- `goal`
- `guard_condition`
- `materials`
- `skill_exposure`
- `risk_level`
- `autonomy_profile`
- `approval_mode`
- `launch_intent`
- `workspace_root`

裁决：

- 这是启动合同，不是后台 campaign spec；
- 可以来源于 CLI 参数 + launcher 交互；
- 必须可序列化，供未来 console 复用。

## 4.2 `FlowRunV1`

用途：V1 主对象。

建议字段：

- `flow_id`
- `draft_id`
- `workflow_kind`
- `goal`
- `guard_condition`
- `status`
- `current_phase`
- `current_turn_id`
- `supervisor_thread_id`
- `primary_executor_session_id`
- `latest_judge_decision`
- `latest_supervisor_decision`
- `risk_level`
- `autonomy_profile`
- `approval_state`
- `workspace_root`
- `artifact_index_ref`
- `trace_refs`
- `receipt_refs`
- `created_at`
- `updated_at`

裁决：

- 它是前台轻主状态真源；
- 不直接替代现有 `workflow_state.json`，但要兼容写回；
- V1 允许先用 file-store 落地。

## 4.3 `FlowTurnRecordV1`

用途：把当前“phase history”升级成可审计 turn 历史。

建议字段：

- `turn_id`
- `flow_id`
- `phase`
- `turn_kind` (`plan|execute|review|recover|operator_wait|handoff`)
- `attempt_no`
- `supervisor_decision`
- `executor_agent_id`
- `judge_agent_id`
- `decision`
- `reason`
- `confidence`
- `artifact_refs`
- `trace_id`
- `receipt_id`
- `started_at`
- `completed_at`

## 4.4 `FlowActionReceiptV1`

用途：operator 动作的正式 receipt。

建议字段：

- `action_id`
- `flow_id`
- `action_type`
- `operator_id`
- `policy_source`
- `before_state`
- `after_state`
- `trace_id`
- `receipt_id`
- `result_summary`
- `created_at`

## 4.5 `FlowWorkspaceViewV1`

用途：把 DeerFlow 启发下的 thread/workspace/artifact 环境壳引进来，但不照搬 DeerFlow 命名。

建议字段：

- `flow_id`
- `workspace_root`
- `uploads_dir`
- `outputs_dir`
- `artifacts_manifest_path`
- `codex_home`
- `trace_root`

裁决：

- V1 先做 view / manifest，不做复杂对象图；
- 关键是让 operator 看见“这轮 flow 产出了什么”，而不是只看文本总结。这个方向与你现有 DeerFlow 专题整理一致。fileciteturn8file15 fileciteturn8file16

---

## 5. V1 状态机与事件模型

## 5.1 Run 主状态

V1 主状态固定为：

- `draft`
- `ready`
- `running`
- `waiting_operator`
- `paused`
- `completed`
- `failed`
- `handed_off`

裁决：

1. `phase` 不等于主状态；
2. `approval_state` 不替代主状态；
3. `guard_condition_satisfied` 是 judge result，不替代 `completed`。

这条裁决直接继承你现有前台长 workflow 草稿。fileciteturn8file0

## 5.2 Turn 事件模型

V1 引入轻量 `turn / item` 心智，但不做完整 App Server：

### Turn

- 一轮 supervisor 主导下的完整推进；
- 可能包含 plan、执行、judge、recover、operator wait 中的一种主语义；
- 一次 turn 必须产出至少一个 receipt。

### Item / Event

建议事件类型：

- `turn_started`
- `supervisor_decided`
- `executor_started`
- `executor_chunk`
- `executor_completed`
- `judge_completed`
- `recovery_proposed`
- `operator_required`
- `operator_action_applied`
- `phase_transitioned`
- `artifact_registered`
- `turn_completed`
- `run_status_changed`

CLI 升级草稿已经在建议把 `codex_chunk`、`judge_result`、`phase_transition` 这类类型化事件推进到 display 层；V1 正好把这件事正式化。fileciteturn8file19

## 5.3 最小 phase 语义

V1 不再把 `single_goal` 和 `project_loop` 硬拆成两套完全不同的心智，而是统一到一个轻量 phase 语义层：

- `plan`
- `execute`
- `review`
- `recover`
- `wait_operator`
- `done`

映射规则：

- `single_goal` 默认从 `execute` 起步，可直接进入 `review` / `done`；
- `project_loop` 默认从 `plan` 起步，在 `plan -> execute -> review` 之间循环；
- 是否回退到 `plan`，由 supervisor + judge 共同决定；
- phase 仍是运行上下文，不升格为大状态机。

---

## 6. V1 交互壳：简约但强交互

## 6.1 交互路线裁决

V1 默认采用：

`Butler own lightweight UI + machine-readable child process output`

不采用：

`嵌套 Codex / Cursor 原生全屏 TUI`

原因：你的 CLI 升级草稿已经明确指出嵌套 TTY / 伪终端风险，并把方案 A（Rich 半屏）作为低风险 MVP。fileciteturn8file12

## 6.2 V1 UI 方案

直接选 **方案 A：编排壳 + 半屏 Rich**，不把 Textual 作为首版刚需。

### 必须有的面板

1. `Header`
   - workspace
   - flow_id
   - workflow_kind
   - current_status
   - current_phase
   - current_turn
2. `Main Stream`
   - Codex / Executor chunk
   - judge 摘要
   - supervisor 决策摘要
3. `Right / Bottom Summary`
   - latest decision
   - latest artifact
   - latest receipt
   - latest operator action
4. `Command Line`
   - `run`
   - `resume`
   - `pause`
   - `append`
   - `retry`
   - `quit`

### 必须支持的交互动作

- `pause`
- `resume`
- `append_instruction`
- `retry_current_phase`
- `accept_recovery`
- `abort`

### 必须保留的兼容性

- 非 TTY 行为不变；
- `--json` 行为稳定；
- `run / resume / status / list / preflight` 保持兼容；
- 失败时可回退到朴素 print。

这些兼容目标与 0331 CLI 升级稿一致。fileciteturn7file0

---

## 7. V1 实现范围：以一次大请求可持续完成为约束

这部分是本计划最关键的地方：**为了适配按调用次数计费的 Copilot / Codex 5.3 实施方式，V1 的任务切分必须足够大、顺序清晰、跨文件边界一次交代清楚。**

## 7.1 实施原则

1. 一次请求内允许持续做完整批次，不在中途频繁停下来问；
2. 只在以下情况停：
   - 遇到真实 blocker；
   - 测试体系无法定位；
   - 现役真源与新计划发生冲突，且无法局部兼容；
3. 若没有 blocker，必须连续完成：
   - 契约更新
   - 代码实现
   - 测试补全
   - 文档回写
4. 优先做“最少文件数、最大闭环”的改动，不搞多处分叉试验；
5. 保持向后兼容，先新增再替换，不做大爆破式重命名。

## 7.2 推荐实施批次

### 批次 A：对象与状态合同收口（必须先做）

目标：把 V1 的 run/turn/action 变成正式结构。

实现项：

1. 在 `butler_flow` 现有状态层上新增：
   - `FlowDraftV1`
   - `FlowRunV1`
   - `FlowTurnRecordV1`
   - `FlowActionReceiptV1`
   - `FlowWorkspaceViewV1`
2. 保持对旧 `workflow_state.json` 的兼容读写；
3. 新增 `turns.jsonl` / `actions.jsonl` / `artifacts.json`（或等价文件）；
4. 增加 state loader / saver；
5. 补最小 schema 校验与序列化测试。

完成判据：

- 现有 flow 仍可 `status / resume`；
- 新 flow 会写出 turn/action 文件；
- 旧测试不坏，新对象有最小单测。

### 批次 B：Supervisor Inner Loop 显式化（V1 核心）

目标：从“Codex 外环 + Cursor judge”升级为“supervisor 驱动 executor/judge/recovery”。

实现项：

1. 在 runtime 层新增 supervisor 决策步骤；
2. 保留 Codex 为 executor 主执行；
3. 保留 Cursor judge 心智，但包装为结构化 reviewer；
4. 新增 recovery step：仅在失败或低置信度时启用；
5. 把每轮外环升级成：
   - `supervisor decide`
   - `executor run`
   - `judge verdict`
   - `maybe recovery`
   - `turn finalize`
6. 每一步都写 event/receipt。

完成判据：

- `single_goal` 和 `project_loop` 都走 supervisor 主控；
- 状态里能看到 `latest_supervisor_decision`；
- turn 历史可见；
- `resume` 不丢决策 lineage。

### 批次 C：Operator Actions 收口

目标：给操作者正式 steering 通道，而不是只能 Ctrl+C。

实现项：

1. 支持动作：
   - `pause`
   - `resume`
   - `append_instruction`
   - `retry_current_phase`
   - `abort`
2. 每个动作写 `FlowActionReceiptV1`；
3. 动作生效路径统一走 runtime action contract；
4. `pause/resume` 不等于重启，必须保持 checkpoint pointer / current turn context。

完成判据：

- CLI 内能触发 operator action；
- action 可审计；
- 恢复后能接着跑而不是重新开一个流。

### 批次 D：Rich 交互壳 MVP

目标：把当前 CLI 提升为可扫视 operator 壳。

实现项：

1. 抽象 display interface；
2. 保留 plain display；
3. 新增 `RichFlowDisplay`；
4. 主界面支持：
   - header
   - main stream
   - latest summary
   - command input
5. launcher 支持最近 flow 选择、高亮默认项、快捷 resume。

完成判据：

- TTY 下交互显著优于当前；
- 非 TTY 不退化；
- `resume --last` 与壳内选择最近 flow 一致。

### 批次 E：Artifact / Workspace / Trace 可见化

目标：把 DeerFlow 启发下的 thread/workspace/artifact 环境壳落进 V1。

实现项：

1. 注册 artifact manifest；
2. 输出最近 artifact summary；
3. CLI 中可查看最近 trace / receipt 摘要；
4. 将 `workspace_root / codex_home / outputs_dir` 统一收口到 `FlowWorkspaceViewV1`。

完成判据：

- operator 能看到本轮产出，不只看总结；
- artifact 与 turn 有基本关联；
- 不影响当前本地文件结构。

### 批次 F：文档与测试闭环

目标：一次性把真源、测试、文档更新完，避免再来回补。

实现项：

1. 扩展：
   - `test_butler_flow.py`
   - `test_chat_cli_runner.py`
   - 新增 run/turn/action 测试
   - 新增 pause/resume/action receipt 测试
2. 必要时补：
   - workflow state migration 测试
   - Rich display 降级测试
3. 回写文档：
   - `04b-butler-flowV1版本开发计划.md`（本稿）
   - 0331 CLI 收口文档
   - 0331 前台长 workflow 草稿（标注哪些进入 V1）
   - 相关 project-map / truth matrix / change packet

完成判据：

- 关键 pytest 集合通过；
- 文档口径与实现一致；
- 不遗留“代码已改、文档未跟”的状态。

---

## 8. 建议的代码切入点（按最少来回设计）

优先检查并修改：

1. `butler_main/butler_flow/runtime.py`
   - 新增 supervisor 驱动循环；
   - 新增 run/turn/action 状态推进；
   - 新增 operator actions contract。
2. `butler_main/butler_flow/display.py`
   - 抽象 display interface；
   - 新增 RichFlowDisplay。
3. `butler_main/butler_flow/app.py`
   - launcher / attached operator shell；
   - 最近 flow 选择；
   - 操作动作绑定。
4. `butler_main/butler_flow/cli.py`
   - 保持兼容入口；
   - 增加必要命令参数或 UI 开关。
5. `butler_main/agents_os/execution/cli_runner.py`
   - 保持 receipt-first；
   - 确保 child output 能稳定流式进入 event schema。
6. `butler_main/agents_os/execution/workflow_prompts.py` 或等价 prompt 位置
   - 显式 supervisor / reviewer / recovery prompt。
7. `butler_main/butler_bot_code/tests/test_butler_flow.py`
   - 作为第一主回归阵地。

如果涉及 console 只做极轻量预埋，不把 console 作为 V1 必交付：

8. `butler_main/console/service.py`
   - 只预留 workflow run query schema；
9. `butler_main/console/server.py`
   - 如有必要，仅做只读查询面，不做完整 Studio。

---

## 9. 推荐的 V1 事件与接口合同

## 9.1 内部事件 schema（建议）

```json
{
  "event_type": "supervisor_decided",
  "flow_id": "flow_xxx",
  "turn_id": "turn_xxx",
  "phase": "plan",
  "timestamp": "2026-03-31T12:00:00Z",
  "payload": {
    "decision": "execute",
    "reason": "need_repo_change",
    "confidence": 0.82,
    "next_action": "run_executor"
  }
}
```

建议首批事件类型：

- `turn_started`
- `supervisor_decided`
- `executor_chunk`
- `executor_completed`
- `judge_completed`
- `recovery_proposed`
- `operator_required`
- `operator_action_applied`
- `artifact_registered`
- `turn_completed`
- `run_status_changed`

## 9.2 Operator actions contract（建议）

```json
{
  "action_type": "append_instruction",
  "operator_id": "local_user",
  "payload": {
    "instruction": "先检查现有测试与状态文件兼容，不要直接重构整个状态结构"
  }
}
```

首批动作固定为：

- `pause`
- `resume`
- `append_instruction`
- `retry_current_phase`
- `abort`

---

## 10. 验收口径（必须写死）

## 10.1 行为验收

1. `butler-flow run --kind single_goal` 可正常创建 V1 flow，并写出 run + turn 记录；
2. `butler-flow run --kind project_loop` 至少能稳定跑多轮，并持续记录 turn/event；
3. `pause / resume` 不会重新起一个 flow；
4. `append_instruction` 会进入下一轮 supervisor 上下文；
5. `resume --last` 与交互壳选择最近 flow 指向同一对象；
6. 非 TTY 下原有命令行为不破；
7. 运行中能区分 executor 输出、judge 结果、supervisor 决策、operator 动作。

## 10.2 数据验收

至少能在 flow root 下稳定找到：

- `workflow_state.json`（兼容）
- `turns.jsonl`
- `actions.jsonl`
- `artifacts.json`
- `trace refs`
- `receipt refs`

## 10.3 测试验收

最低新增 / 扩展：

1. `test_butler_flow.py`
   - run / pause / resume / turn history / action receipt
2. `test_chat_cli_runner.py`
   - receipt-first 与 event streaming 不坏
3. 新增 migration 测试
   - 旧 flow 状态仍可恢复
4. 新增 display 降级测试
   - TTY 与非 TTY 不冲突

这与现有前台产品化草稿和 CLI 升级稿中的验收方向一致。fileciteturn8file5 fileciteturn8file14

---

## 11. 风险与控制

## 11.1 最大风险

1. **把 V1 做成小型平台项目**
   - 结果：范围爆炸，Codex 单次请求做不完；
2. **把 agent 自由度误解为取消结构**
   - 结果：run state 再次漂移；
3. **把 CLI 交互壳与 runtime 真源绑死**
   - 结果：后续 console 难以复用；
4. **过早上 Textual 全屏**
   - 结果：把精力消耗在 UI 而不是 flow 合同；
5. **旧状态兼容性处理不够**
   - 结果：现有 flow/resume 被破坏。

## 11.2 控制措施

1. 先对象与合同，后 UI；
2. 先 Rich 半屏，后 Textual；
3. 先 file-based durable state，后 API 化；
4. 先 turn/action/receipt，后 studio；
5. 兼容旧 `workflow_state.json`，通过 migration 或兼容 loader 过渡。

---

## 12. 交给 Copilot / Codex 5.3 的单次大请求执行协议

下面这一段，建议你原样或稍改后直接发给实现 agent。

### 执行任务单

你现在要在 Butler 仓库内实施 `04b-butler-flowV1`，目标是把当前 `butler-flow` 从“Codex 主执行 + Cursor 守看”的前台 loop，升级为一个 **agent-led、operator-steerable、foreground-attached** 的 flow V1。

必须遵守：

1. **保持现有前后台边界**：`butler-flow` 仍属于前台附着运行时，不进入 `campaign/orchestrator` 主链；
2. **保持兼容**：`run / resume / status / list / preflight` 现有命令、非 TTY 行为、旧状态文件恢复能力不能被打破；
3. **一次请求内持续做完**：不要分批等待确认；如果没有真实 blocker，就连续完成对象合同、runtime、display、测试、文档；
4. **优先最小闭环**：先实现 run/turn/action/receipt + supervisor inner loop + Rich operator 壳，不要先做完整 console 或重型 TUI；
5. **不要把外部框架名词直接写进 Butler 真源**：可以吸收 Codex Harness / Deep Agents / DeerFlow / Claude Agent SDK 的设计经验，但不要照搬对象命名。

### 你需要完成的工作顺序

1. 阅读并对齐当前真源与相关文档：
   - `0331 前台 Butler Flow CLI 收口（workflow shell 历史别名）`
   - `0331 Butler Flow CLI 交互式升级：对标调研与技术方案`
   - `0331 前台长 Agent 监督 Workflow 产品化草稿计划`
2. 在 `butler_flow` 现有状态层上新增最小 V1 对象：
   - `FlowDraftV1`
   - `FlowRunV1`
   - `FlowTurnRecordV1`
   - `FlowActionReceiptV1`
   - `FlowWorkspaceViewV1`
3. 兼容旧 `workflow_state.json`，新增 turn/action/artifact 相关持久化；
4. 在 runtime 中显式引入 `Supervisor Agent` 决策步骤，把当前 loop 升级为：
   - supervisor decide
   - executor run
   - judge verdict
   - optional recovery
   - turn finalize
5. 保留 Codex 为主执行、Cursor judge 结构化裁决的总体路线，但把它们包装进 supervisor 主控；
6. 增加 operator actions：
   - pause
   - resume
   - append_instruction
   - retry_current_phase
   - abort
7. 抽象 display interface，保留 plain display，并新增 Rich 半屏 operator 壳；
8. 保持非 TTY 路径兼容，避免嵌套外部原生 TUI；
9. 扩展关键测试：
   - flow run / pause / resume
   - turn history / action receipt
   - old state migration
   - non-TTY compatibility
10. 回写相关文档，至少补充：
   - 04b 开发计划结果
   - 0331 CLI 收口文档中的现役事实
   - 若有必要，补 change packet / truth matrix

### 执行中的约束

1. 不要把 UI 直接当 runtime 真源；
2. 不要让 operator action 绕过 receipt / trace；
3. 不要让 pause/resume 退化成“新开一条 flow”；
4. 不要把自由文本直接写成 run state；
5. 如果某一步实现超出 V1 范围，优先留 TODO / 文档注记，而不是扩项目边界。

### 交付要求

最终需要给出：

1. 修改过的代码；
2. 新增 / 扩展的测试；
3. 跑过的关键 pytest 命令与结果；
4. 文档回写摘要；
5. 剩余未完成项与原因。

### 只有在以下情况才停下来

1. 遇到真实 blocker（如真源冲突、测试体系断裂、关键依赖不存在）；
2. 无法在兼容现有状态的前提下继续推进；
3. 需要在两个互斥方案中二选一且文档没有裁决。

否则不要停，不要频繁请求确认，继续把完整闭环做完。

---

## 13. 本版最终裁决

`04b-butler-flowV1` 的正确方向不是“把前台 flow 产品化成一个完整平台”，而是：

1. 以 **Supervisor Agent** 作为决策面核心；
2. 以 **run / turn / action / receipt / trace** 作为 harness 稳定脊柱；
3. 以 **Rich 附着式 operator 壳** 提供足够强的交互体验；
4. 以 **兼容现有 butler-flow 真源** 为第一约束；
5. 以 **一次大请求可持续完成** 为实施计划的组织原则。

对你当前阶段，这是一条最稳、最省调用、又能真正把“agent 作为控制面主力”落到代码里的路线。

---

## 14. 2026-03-31 落地结果回写（V1 第一轮）

本轮已按 `04b` 计划完成一轮可用闭环，且保持前后台边界不变（仍不进入 `campaign/orchestrator`）。

### 14.1 已落代码（核心）

1. `butler_main/butler_flow/state.py`
   - 新增并落盘 V1 侧文件：
     - `turns.jsonl`
     - `actions.jsonl`
     - `artifacts.json`
   - 新增旧状态兼容迁移入口 `ensure_flow_state_v1(...)`
   - 启动时自动补齐 V1 最小字段（如 `latest_supervisor_decision` / `latest_judge_decision` / `trace_refs` / `receipt_refs`）。

2. `butler_main/butler_flow/runtime.py`
   - 新增显式 supervisor 决策步骤（`_supervisor_decide`），并写入 `latest_supervisor_decision`。
   - 主循环显式化为：
     - supervisor decide
     - executor run
     - judge verdict
     - optional recovery instruction
     - turn finalize
   - 每轮写 turn 记录到 `turns.jsonl`，并注册 artifact 到 `artifacts.json`。
   - 新增 operator action 合同实现：
     - `pause`
     - `resume`
     - `append_instruction`
     - `retry_current_phase`
     - `abort`
   - operator action 统一写 `actions.jsonl` receipt，不绕过 trace/receipt 边界。

3. `butler_main/butler_flow/display.py`
   - 保留 `FlowDisplay`（plain）。
   - 新增 `RichFlowDisplay`（轻量状态块），用于 TTY 下更好扫视。

4. `butler_main/butler_flow/app.py` / `cli.py`
   - app 层引入 TTY 自动选择 `RichFlowDisplay`，非 TTY 继续 plain（兼容）。
   - 新增 CLI 子命令：
     - `butler-flow action --type <pause|resume|append_instruction|retry_current_phase|abort> [--instruction ...]`
   - 通过统一 runtime action contract 执行动作并返回 receipt JSON。

5. `butler_main/butler_flow/models.py`
   - 补齐 V1 typed 对象声明：
     - `FlowDraftV1`
     - `FlowRunV1`
     - `FlowTurnRecordV1`
     - `FlowActionReceiptV1`
     - `FlowWorkspaceViewV1`

### 14.2 测试与验收

本轮新增/扩展：

- `test_butler_flow.py`
  - turn/action/artifact 文件落盘校验
  - operator action receipt 校验
  - legacy `flow_state.json` 迁移恢复校验
  - display 非 TTY 降级校验

已执行回归：

```bash
./.venv/bin/python -m pytest \
  butler_main/butler_bot_code/tests/test_butler_flow.py \
  butler_main/butler_bot_code/tests/test_chat_cli_runner.py \
  butler_main/butler_bot_code/tests/test_butler_cli.py -q
```

结果：`29 passed`

### 14.3 与计划对照

- 批次 A（对象与状态合同）：已落最小集合并兼容旧状态。
- 批次 B（Supervisor Inner Loop）：已显式 supervisor 决策并写 turn lineage。
- 批次 C（Operator Actions）：已落 pause/resume/append/retry/abort + action receipt。
- 批次 D（Rich 壳 MVP）：已落轻量 Rich display，非 TTY 保持兼容。
- 批次 E（Artifact/Trace 可见）：已落 artifact manifest 与 turn 关联基础。
- 批次 F（测试与文档）：本稿 + 0331/02 已回写，关键 pytest 已通过。

### 14.4 本轮未扩范围项（按 V1 边界保留）

1. 未引入重型全屏 Textual；
2. 未把 butler-flow 升格接入后台 campaign 主链；
3. 未做浏览器侧 studio，仅保留 file-based durable state。
