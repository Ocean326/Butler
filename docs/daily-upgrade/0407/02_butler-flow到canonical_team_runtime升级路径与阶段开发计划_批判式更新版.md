# 0407 Butler Flow 到 Canonical Team Runtime 升级路径与阶段开发计划（批判式更新版）

日期：2026-04-07
状态：方案更新 / `P0-P5` 已落地 / `P6` gate 验收中
所属层级：当前实施主落 L1 `Agent Execution Runtime`，辅触 L2 durability substrate / Product surface / Control Plane
定位：用 `proposal-critique-refine` 对 “butler-flow -> canonical team runtime” 路线做删改式收敛，明确该保留什么、该降级什么、该延后什么、该先证明什么

关联：

- [0407 当日总纲](./00_当日总纲.md)
- [0407 Canonical Team Runtime 最终收口：任务产物真源、治理真源与升级门槛](./01_canonical_team_runtime最终收口_任务产物真源与升级门槛.md)
- [0401 前台 Butler Flow 入口收口与 New 向导 V1](../0401/01_前台ButlerFlow入口收口与New向导V1.md)
- [0401 Claude Code 对 Butler Flow 工作台化升级与 TUI 信息架构计划](../0401/02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)
- [0401 Butler Flow workspace/manage 分工升级计划](../0401/04_butler-flow工作流分级与FlowsStudio升级草稿.md)
- [0401 Claude / Codex CLI 单 Session 能力报告](../0401/20260401_claude_codex_cli_session_report.md)
- [0403 Butler Flow Codex 执行根隔离与 `repo_bound` 裁决](../0403/01_butler-flow_Codex执行根隔离与repo_bound裁决.md)
- [0403 Butler Flow supervisor 控制画像与 agents-flow 治理升级](../0403/02_butler-flow_supervisor控制画像与agents-flow治理升级.md)
- [真源矩阵](../../project-map/03_truth_matrix.md)
- [改前读包](../../project-map/04_change_packets.md)

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 更新此前的升级路径，不只做加法，还要明确删改当前 butler-flow 中与 `0407/01` 不一致的叙事、对象边界和阶段排序。 |
| 所属层级 | 当前文档是 docs-only；后续实施主落 `butler_main/products/butler_flow/` 与 `butler_main/agents_os/execution/cli_runner.py`，并会牵动 `platform/runtime` 与现役 control-plane 真源映射。 |
| 当前真源文档 | 以 [0407/01](./01_canonical_team_runtime最终收口_任务产物真源与升级门槛.md)、[0403/01](../0403/01_butler-flow_Codex执行根隔离与repo_bound裁决.md)、[0403/02](../0403/02_butler-flow_supervisor控制画像与agents-flow治理升级.md)、[0401/01](../0401/01_前台ButlerFlow入口收口与New向导V1.md)、[0401/04](../0401/04_butler-flow工作流分级与FlowsStudio升级草稿.md) 为准。 |
| 计划查看的代码与测试 | 代码重点看 `butler_main/products/butler_flow/`、`butler_main/agents_os/execution/cli_runner.py`、`butler_main/platform/runtime/`；主测保留 `test_butler_flow.py`、`test_butler_flow_tui_app.py`、`test_butler_flow_tui_controller.py`、`test_chat_cli_runner.py`、`test_agents_os_wave1.py`。 |

## 一句话裁决

这条路线必须改成 `subtraction-first`，不能继续靠 additive layering 自我安慰。  
Butler Flow 当前更准确的目标不是“继续把 workbench 做大”，而是先收口成：

> **`Mission Console over a Receipt-backed Repo-Bound Task Contract Runtime`**

它的主线应改为：

`Truth Freeze -> Task Contract Launch -> Artifact/Receipt Spine -> Operator Recovery Lane -> Authority/Policy Minimum -> Derived Responsibility Graph + Mission Console -> Canonical Closure Gate`

其中：

- `P6` 不再是一个“再加一层”的实现阶段，而是命名与真源闭环门槛
- `team graph` 不再是早期 headline phase，而是后置、只读、派生的责任图
- 当前产品命名继续保持在 `canonical team runtime`，直到 `P6` 闭环验收通过

## 0. 当前实施回写（截至 2026-04-07）

当前代码基线已经不再只是 `P0 + P1`，而是：

1. `task_contract.json` 已作为任务真源稳定存在。
2. `flow_definition.json` 已降级为 materialization，围绕 `task_contract_id + task_contract_summary` 外显。
3. `receipts.jsonl` 已落地为第一条 canonical receipt spine：
   - `turn_acceptance`
   - `artifact_acceptance`
   - `operator_action`
   - `exec_terminal`
   - `authority_transition`
   - `policy_update`
4. `recovery_cursor.json` 已落地为 transcript-independent recovery pointer。
5. `status / workspace / single-flow / TUI summary` 已能外显：
   - `latest_receipt_summary`
   - `latest_artifact_ref`
   - `accepted_receipt_count`
   - `recovery_cursor`
   - `recovery_state`
6. `resume` 当前已优先读取 `task_contract.json -> recovery_cursor.json -> receipts.jsonl`，并能最小区分：
   - `resume_existing_session`
   - `reseed_same_contract`
   - `rebind_role_session`
   - `rollback_to_receipt`
   - `pause_for_operator`

7. authority / policy 的写路径当前已收口为：
   - typed governance receipt
   - `task_contract.json` 当前快照同步
   - `recovery_cursor.json` 刷新
   `workflow_state.json` 只继续保留 runtime shadow/cache。
8. `apply_operator_action()` 已修正 stale external operator-state merge，避免 canonical control-profile / repo-binding / doctor 相关变更被旧 shadow 状态覆盖。
9. `surface_meta` 已成为 shared projection truth，稳定提供：
   - `canonical_surface`
   - `display_title`
   - `legacy_aliases`
10. 当前可见标题已统一为：
   - `Mission Index`
   - `Contract Studio`
   - `Run Console`
   旧 alias 仍接受输入，但不再作为任何主标题、空状态或帮助文案。
11. compat patch-path 也已补齐：
   - 测试补丁命中 `app/flow_shell`
   - `runtime`
   - `manage_agent`
   三条现役路径时，都会落回当前 canonical product implementation。

因此，当前真正未闭合的主缺口已经收缩为 `P6` 的正式 gate 证据、文档封板与 PR 整理，而不是 `P4/P5` 本身仍待实现。

## 1. Proposal Brief

- `problem_or_opportunity`
  - 当前 butler-flow 已经是一个很强的 CLI agent 工作台，但它仍然偏 `flow/session-first`，容易把 projection、runtime 容器和组织能力混在一起讲。
- `proposed_approach`
  - 用删改优先的路线，把 butler-flow 从 “session/flow-centered CLI workbench” 收口成 “contract/artifact/receipt-first 的 repo-bound engineering runtime”，再在其上证明最小治理与责任关系。
- `target_user_or_stakeholder`
  - 当前主要是 repo owner / operator / manager，而不是通用组织平台用户。
- `key_constraints`
  - 不制造双真源；不推翻现役 `P/C/L4/L3/L2/L1` 骨架；`v1` 只证明单 operator、单 repo-bound engineering task、单 primary substrate。
- `success_criteria`
  - 路线能清楚说出：什么要保留、什么要降级、什么必须删叙事、什么先做、什么后做，以及什么证据出现前不能升级命名。
- `main_unknowns`
  - `Authority` 的最小 typed object 到底落在哪；现役 butler-flow 的哪些 sidecar 应保留为 runtime truth，哪些只是过渡材料；何时才值得引入 responsibility graph。

## 2. Review Stance

本轮按 `proposal-critique-refine` 执行，采用：

- `neutral baseline`
  - 先平衡价值、可行性和风险，不默认偏保守或偏激进。
- `innovation-first`
  - 避免把路线修成一个“更稳的 workflow runtime”，保留真正能与现有产品拉开距离的赌注。
- `evidence-first`
  - 任何命名升级、对象升级、治理升级都要求更强的 falsifiable wedge 与 acceptance gate。

本轮实际使用的独立视角是：

- `value-strategy`
- `execution-feasibility`
- `downside-risk`
- `improver`

## 3. Round Summary

### 3.1 Round 1：主要批评

第一轮最集中的批评有四条：

1. 当前路线仍然太像“不断加能力”，不像“先冻住一条新的真源边界”。
2. `minimal team graph` 和 `governance kernel` 出场太早，容易在现有 butler-flow 之上再叠第二套可写对象。
3. `workspace / manage / single flow` 的产品面仍然被说得太中心，容易把 projection 继续误当成真源。
4. 路线没有把单一差异化赌注说尖，容易沦为“更强的 CLI workbench”而不是 “accountable handoff layer over vendor agents”。

### 3.2 Round 2：修复方向

第二轮修复后，路线被改成：

- 把 `P0` 改成 `truth-owner mapping + deletion/demotion plan`
- 把 `P1/P2/P3` 收成第一条必须先证明的闭环
  - `Task Contract -> Artifact/Receipt -> Recovery`
- 把 `P4` 从模糊的 `governance kernel` 改成 `authority/policy minimum`
- 把 `P5` 从 “team graph” 改成 “derived responsibility graph + Mission Console”
- 把 `P6` 从功能阶段改成 closure gate

### 3.3 Round 3：验证后留下的结论

第三轮验证后，当前最稳的结论是：

- 这条路线仍然有创新性，因为它押的是 `task/artifact/receipt` 与 `accountable handoff`
- 这条路线比原稿更稳，因为它先要求冻结真源、冻结写路径、冻结恢复依据
- 剩余未解问题已经不是“再讨论一下路线”，而是要靠映射表、acceptance case 和一个 working slice 来证明

## 4. Issue Register Snapshot

| id | lens | issue | evidence_type | severity | confidence | status | suggested_repair |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `I1` | `execution-feasibility` | 现有路线太 additive，容易把 butler-flow 变成双真源运行时。 | `source-backed` | `high` | `high` | `patched` | 前置 `truth mapping + delete/alias plan`，并把 `P6` 改成 gate。 |
| `I2` | `downside-risk` | `team graph / governance kernel` 若太早变成可写对象，会形成 shadow control plane。 | `source-backed + inference` | `high` | `high` | `patched` | 把治理收窄成 authority/policy minimum，把责任图改成只读派生图。 |
| `I3` | `value-strategy` | 路线没有早期证明一个不可替代的 truth boundary，差异化赌注不够尖。 | `user-provided + inference` | `high` | `medium-high` | `patched` | 把单一赌注写死为 `Receipt-backed Repo-Bound Task Contract Runtime`。 |
| `I4` | `failure-mode` | `workspace/manage/single flow` 仍容易被读成系统中心，session-first 心智会回潮。 | `inference` | `high` | `medium` | `patched` | 明确把 workbench 重命名为 `Mission Console`，把 `/manage` 重命名为 `contract studio` 的方向。 |
| `I5` | `governance` | `Authority` 目前还更像一个词，不是稳定 typed object。 | `source-backed + inference` | `medium-high` | `medium-high` | `patched-in-code / still-open-as-gate` | 已把 authority/policy 变化写成 typed governance receipt；下一步只继续收紧门槛，不扩成完整 organizational kernel。 |

## 5. Repairs Applied

这轮对原路线做了六个关键删改：

1. 不再把 `butler-flow -> canonical team runtime` 写成一路加层，而是先做减法和映射。
2. 不再把 `minimal team graph` 放在前半程主轴。
3. 不再把 `governance kernel` 当成一个一开始就要命名和设计完整的新层。
4. 不再把 `P6 canonical closure` 当成实现功能，而是当成命名升级门槛。
5. 不再让 `workspace/manage/single flow` 承担系统真源叙事，只保留 operator projection 叙事。
6. 不再把多 substrate、general knowledge work、完整 recursive team 写进近程 v1 目标。

## 6. 当前 Butler Flow 的保留 / 降级 / 停止强化

### 6.1 保留为基础设施

| 对象 | 新口径 |
| --- | --- |
| `new / resume / exec` | 当前最好的 intake / recovery surface，继续保留。 |
| `execution_context` | 执行位置真源，继续保持与 authority/policy 分离。 |
| `control_profile` | 继续保留，但只作为 `policy envelope precursor`。 |
| 显式 repo binding | 继续保留，作为 authority/policy 的重要前置条件。 |
| `medium = role_bound` | 继续保留，但只作为 execution packaging，不再作为“团队成立”的证据。 |
| sidecars / run receipts | 继续保留，作为 materialized runtime 与 receipt spine 的输入材料。 |
| TUI / Desktop | 继续保留，但明确降级为 projection shell。 |

### 6.2 降级为 compile input / runtime truth / projection

| 当前对象 | 降级后的口径 |
| --- | --- |
| `workspace / manage / single flow` | 产品表面层，不再承担系统真源叙事。 |
| `template / role_pack / bundle_manifest / manager assets` | 编译输入与资产层，不是团队合同真源。 |
| `role_sessions / handoffs / transcript / history / thread` | runtime/recovery truth，不是交付真源，也不是组织真源。 |
| `flow_definition.json / workflow_state.json` | runtime materialization，不再宣称自己就是 `Task`。 |

### 6.3 停止强化的叙事

以下叙事在近程路线里不再继续强化：

- `team workspace`
- `multi-agent platform`
- `group chat / @ / 1:1` 作为核心组织模型
- `portable semantics`
- `general knowledge work`
- `完整 recursive team`
- `多 substrate parity`

## 7. 现役对象 -> canonical-now 映射

| 现役对象 | 当前改写口径 | 目标对象 | 写入方 | 进入阶段 |
| --- | --- | --- | --- | --- |
| `new / resume / exec` | operator intake / recovery surface | `TaskContract` / `RecoveryAction` | CLI / runtime | `P1` / `P3` |
| `flow_definition.json + workflow_state.json` | contract 物化后的 runtime instance | `TaskContract` 的 materialization | runtime compiler | `P1` |
| `control_profile + execution_context + repo_binding_policy/paths` | policy/authority 前身 | `PolicyRef + AuthorityRef` | manager / supervisor / operator | `P1` 到 `P4` |
| `flow_exec_receipt + bundle outputs` | 当前 receipt 前身 | `RunReceipt + ArtifactReceipt` | runtime | `P2` |
| `role_sessions.json + handoffs.jsonl` | 角色绑定与运行痕迹 | `Derived Responsibility Graph` | runtime only | `P5` |
| `workspace / manage / desktop` | operator cockpit | `Mission Console / Contract Studio / Run Console` | Product Surface | `P5` |
| `campaign ledger -> workflow_session -> turn receipt` | 当前外部稳定链路 | `canonical bridge` | Control Plane | `P6` |

## 8. Revised Phase Plan

### `P0` Truth Freeze & Subtraction Map

- `目标`
  - 先把现役对象分成 `truth / runtime-recovery / projection / compat` 四类。
- `删改`
  - 停止用更大的组织平台叙事讲 butler-flow。
  - 停止把 `session / history / transcript` 讲成业务连续性本体。
- `新增`
  - 三张表：
    - `canonical-now vs provisional`
    - `现役对象 -> 新对象映射表`
    - `delete / downgrade / alias plan`
- `出关门槛`
  - 每一类事实都必须有唯一 truth owner、唯一写路径、唯一恢复依据。

### `P1` Task Contract Launch

- `目标`
  - 让 `new` 的产物从 “启动一个 flow” 改成 “编译一个 `TaskContract`”。
- `删改`
  - `flow_definition/workflow_state` 不再声称自己就是任务真源。
- `新增`
  - `TaskContract` 最小字段：
    - `goal`
    - `repo_scope`
    - `acceptance`
    - `owner`
    - `authority`
    - `policy`
    - `execution_context`
- `出关门槛`
  - 单 repo-bound coding task 能从 contract 启动，并能通过 `resume/exec` 续接，不需要再靠 free-form flow 叙事兜底。

### `P2` Artifact + Receipt Spine（当前已落地第一版）

- `目标`
  - 把 butler-flow 的 accepted progress 全部压进统一 receipt spine。
- `删改`
  - 不再允许“进度只存在于 transcript/timeline，没有正式 receipt”。
- `新增`
  - 最小对象：
    - `ArtifactRecord`
    - `RunReceipt`
    - `ArtifactReceipt`
    - `OperatorActionReceipt`（可先预埋）
- `出关门槛`
  - 任何被接受的代码、文档、测试、验收动作都必须具备 receipt coverage。
- `当前实现`
  - `receipts.jsonl` 已落到实例目录
  - `runtime` 已把 accepted turn / accepted artifact / operator action / terminal exec / governance change 写回同一条 ledger
  - `artifacts.json` 已补齐 `task_contract_id / produced_by_receipt_id / accepted_in_receipt_id / status`
- `剩余缺口`
  - 还没把更完整的 receipt taxonomy 和更强 receipt typing 收到最终 `P6` 验收门槛

### `P3` Operator Recovery Lane（当前已落地第一版）

- `目标`
  - 把恢复路径改成 “从 `RecoveryCursor + latest accepted receipt` 恢复”，而不是从聊天历史猜状态。
- `删改`
  - 不再把 transcript-first recovery 当默认口径。
  - 不再允许 operator 通过无 receipt 的 ad-hoc patch 改写系统状态。
- `新增`
  - `resume`
  - `reseed`
  - `rebind`
  - `rollback`
  - `doctor`
- `出关门槛`
  - 强杀 vendor session 后，系统仍能在不依赖 prompt prose 的前提下恢复推进。
- `当前实现`
  - `recovery_cursor.json` 已成为恢复指针文件
  - `resume` 当前已按 contract/cursor/receipt/role-session 做最小恢复判断
  - `pause_for_operator` 已从“隐含状态”收口成真实恢复结论
  - `status / surface / TUI` 已能在缺 transcript 时解释“任务是什么、做到哪、从哪恢复”
- `剩余缺口`
  - `doctor`、`rollback` 与 authority/policy 变更之间的 typed receipt 关系还需继续收紧

### `P4` Authority / Policy Minimum（已落地并完成 hardening）

- `目标`
  - 在不扩成完整组织内核的前提下，让 `authority` 真的变成可写、可审计、可恢复的 typed 最小对象。
- `删改`
  - 不再把治理语义散落在 prompt 语气、`manager_notes` 或隐含角色 lore 中。
- `新增`
  - 最小帽子：
    - `requester`
    - `manager`
    - `operator`
  - 最小 typed 对象：
    - `AuthorityTransitionReceipt`
    - 收窄版 `policy envelope`
- `具体内容`
  - authority truth 继续只挂在 `task_contract.json` 当前快照上，并经由 `task_contract_summary.owner_summary + authority_summary + responsibility_summary` 对外外显。
  - governance ledger 当前已开始把 `authority_transition / policy_update` 写成 typed receipt，字段最少包含：
    - `before / after`
    - `changed_fields`
    - `action_scope`
  - 当前 policy envelope 只收最稳定对象：
    - `execution_context`
    - `repo_scope`
    - `control_profile.repo_binding_policy`
    - `control_profile.repo_contract_paths`
  - 任何 authority-changing action 都必须通过 `receipts.jsonl` 留下 typed receipt，才能进入 audit / recovery / rollback 语义。
- `当前代码回写`
  - governance mutation 当前会先补写 typed receipt，再同步 `task_contract.json` 当前快照，并刷新 `recovery_cursor.json`。
  - `apply_operator_action()` 已去掉 canonical mutation 落盘时对 stale external operator state 的重新合并，避免 operator action 把权威治理字段重新退回 shadow cache。
  - `status / workspace / single-flow` 当前已稳定外显 `governance_summary + latest_governance_receipt_summary`。
- `出关门槛`
  - 当前实现已满足功能门槛；剩余只是在 `P6 G0/G4` 中把“无 bypass ledger 写路径”做正式验收与证据归档。

### `P5` Derived Responsibility Graph + Mission Console（已落地并完成 visible closure）

- `目标`
  - 只在前四步成立后，引入一个派生的责任图和更诚实的产品投影。
- `删改`
  - 不做可编辑 `team graph`
  - 不做 group-chat-first 的产品叙事
- `新增`
  - `Derived Responsibility Graph`
  - `Mission Console`
  - `workspace = mission index`
  - `/manage = contract studio`
  - `single flow = run console`
- `具体内容`
  - `workspace / single-flow / /manage` 只允许作为 projection surface，不再承担任务或治理真源职责。
  - 这些 surface 的读取真源固定为：
    - `task_contract.json`
    - `receipts.jsonl`
    - `recovery_cursor.json`
  - `Derived Responsibility Graph` 继续只允许从 `task_contract + receipts + role_sessions + handoffs` 只读派生，不得落成第二个可写图文件。
  - `Mission Console` 当前对外最小解释块应稳定为：
    - `contract summary`
    - `latest accepted receipt`
    - `latest artifact ref`
    - `recovery state`
    - `responsibility summary`
- `当前代码回写`
  - `surface_meta` 已成为三块 surface 的共享投影定义，字段固定为 `canonical_surface / display_title / legacy_aliases`。
  - 三块 surface 当前已收口成：
    - `mission_index / Mission Index`
    - `contract_studio / Contract Studio`
    - `run_console / Run Console`
  - `mission_console` 投影当前已进入 `status / workspace / single-flow` payload，并稳定包含：
    - `task_contract_summary`
    - `latest_receipt_summary`
    - `latest_artifact_ref`
    - `recovery_state`
    - `governance_summary`
    - `derived_responsibility_graph`
  - `responsibility_summary` 当前保留一轮 compat，但数据源已与 `derived_responsibility_graph` 完全同源。
  - TUI / controller / desktop bridge / desktop renderer 当前都读取同一套投影定义；旧 `workspace / history / flows / manage_center / single_flow` 只保 compat alias 输入，`manage` 与 `list` 继续是现役入口，不视为 legacy。
- `出关门槛`
  - 当前实现已满足产品收口门槛；剩余只是在 `P6 G5` 中把可见标题、payload 与 controller/TUI/Desktop 行为的一致性做正式验收。

### `P6` Canonical Closure Gate（当前进入正式验收）

- `目标`
  - 决定这条线有没有资格进入 `canonical team runtime` 命名。
- `删改`
  - 不再把 `P6` 当成“继续加 feature”的阶段。
- `新增`
  - closure checklist
  - 对 `campaign ledger -> workflow_session -> turn receipt` 的桥接裁决
- `出关门槛`
  - 若 `G0-G5` 全部成立，可内部使用 `canonical team runtime` 口径。
  - 若任一关键门槛未过，则继续使用：
    - `Mission Console over a Receipt-backed Repo-Bound Task Contract Runtime`
- `当前证据`
  - `G0`
    - `task_contract.json / receipts.jsonl / recovery_cursor.json` 已锁成三件套真源；`flow_definition.json` 继续只是 materialization，`workflow_state.json` 继续只是 runtime/recovery shadow。
  - `G1 + G3`
    - `new / resume / status / exec / workspace / single-flow` 当前都围绕 `task_contract_id + latest_receipt_summary + recovery_state` 解释任务；缺 transcript 时，surface 与 controller 仍能解释“任务是什么、做到哪、怎么恢复”。
  - `G4`
    - authority/policy 变更当前都走 typed governance receipt；operator action 的 stale merge 旁路已被关闭。
  - `G5`
    - 可见标题已在 TUI / Desktop / bridge / renderer 统一切到 `Mission Index / Contract Studio / Run Console`；旧 alias 只保路由兼容。
  - `验证`
    - `test_butler_flow.py`
    - `test_butler_flow_tui_app.py`
    - `test_butler_flow_surface.py`
    - `test_butler_flow_tui_controller.py`
    - `test_butler_cli.py`
    - `test_chat_cli_runner.py`
    - desktop `typecheck`
    - renderer `vitest`
    - `butler-flow --help`
    - `python -m butler_main --help`

## 9. 实际实施波次回写

### 第一波并行：`P0 + P1`（已完成）

- `truth-lane`
  - 三张表与 deprecation plan
- `runtime-lane`
  - `TaskContract` 编译与 launch path
- `surface-lane`
  - `new / manage / workspace` 口径与命名收口

### Replan Checkpoint

检查三件事：

1. 有没有出现第二套可写 truth
2. `flow_definition/workflow_state` 是否已经被降级成 materialization
3. `new/resume/exec` 是否已经能围绕 contract 说清楚

### 第二波并行：`P2 + P3`（已完成）

- `receipt-lane`
  - artifact / run / operator receipt spine
- `recovery-lane`
  - recovery cursor 与 replay/rollback
- `acceptance-lane`
  - transcript-independence 验收

### 第三波并行：`P4 + P5`（已完成）

- `authority-lane`
  - authority/policy minimum
- `projection-lane`
  - Mission Console / Contract Studio / Run Console
- `docs-lane`
  - 口径、命名、truth matrix 回写

### 最终收口：`P6`（当前执行中）

- 真源矩阵
- 改前读包
- 产品命名
- 升级门槛与 accepted-risk 记录

## 10. Acceptance Gates 与建议指标

| gate | 含义 | 当前要求 |
| --- | --- | --- |
| `G0` | one fact -> one truth owner | 每类事实都有唯一 truth owner / write path / recovery source |
| `G1` | contract-first launch | `new/resume/exec` 以 `TaskContract` 为主对象 |
| `G2` | receipt coverage | 100% accepted outputs 有 receipt |
| `G3` | transcript-independent recovery | 不看聊天记录也能恢复到可执行状态 |
| `G4` | authority receipt completeness | 所有 authority-changing action 都有 typed receipt |
| `G5` | projection consistency | manager/operator/end-user 三个视图不分叉真相 |

建议跟踪的运行指标：

- `session-loss recovery rate`
- `receipt coverage`
- `out-of-scope reject rate`
- `recovery latency`
- `projection consistency`
- `transcript-independence`

## 11. Residual Risks

- `Authority` 仍然是本轮最大的 open item，不能假装已经对象化完成。
- 现役 `campaign ledger -> workflow_session -> turn receipt` 与新对象的桥接关系，当前仍需 code-level mapping 才能算真正落地。
- `Mission Console / Contract Studio / Run Console` 的新口径虽然更诚实，但也意味着要主动拆掉一部分既有 workbench 惯性。
- 如果后续需求继续强拉 “聊天连续性 / team chat ergonomics”，路线仍可能重新滑回 session-first。

## 12. Preserved Disagreements

- 是否应该在 `P6` 通过前，对外宣传 `canonical team runtime`
  - 当前建议：不宣传，最多只在内部文档口径使用。
- `P4` 与 `P5` 是否应并成一波实现
  - 当前建议：可以同一波并行，但不能共享一套写对象。
- 是否要立刻重命名产品面
  - 当前结果：可见壳层已正式改成 `Mission Index / Contract Studio / Run Console`，旧名只保 compat alias，不再显示为主标题。

## 13. Final Recommendation

- `Final Recommendation`
  - `proceed-to-gate`
- `Next-Step Artifact`
  - `gate evidence + ready PR`
- `Why This Pass Stops Here`
  - 剩余关键不确定性已经不在实现面，而在 gate 证据是否完整、文档是否同步、PR 是否能清楚说明 truth owner / governance / projection closure。继续扩功能不会比完成正式闭环更有价值。

## 14. 0407 Implementation Update（P0 + P1）

### 14.1 本轮已落地对象

本轮已把第一波实现推进到代码侧，当前已成立的最小对象是：

- `task_contract.json`
  - 当前 instance 级任务真源
- `task_contract_id`
  - 当前贯穿 `new / resume / status / exec receipt / workspace / single flow` 的主键
- `task_contract_summary`
  - 当前 projection 统一消费的 contract 摘要

当前代码口径已经不是 “flow definition 自己就是任务”，而是：

- `task_contract.json`
  - truth owner
- `flow_definition.json`
  - materialized contract snapshot + launch/runtime defaults
- `workflow_state.json`
  - runtime state + recovery cache

### 14.2 本轮实际改动

本轮已完成：

1. 新增 `butler_main/products/butler_flow/task_contract.py`
   - 负责最小 contract 组装与 summary 规范化
2. 在 `state.py` 补齐：
   - `task_contract_path()`
   - `read_task_contract()`
   - `write_task_contract()`
   - `migrate_legacy_flow_to_task_contract()`
3. 在 `app.py` 接线：
   - `_save_flow_state()` 写入 contract
   - `_save_flow_definition()` 写入 `task_contract_id + task_contract_summary`
   - `new / resume / status` 显式外显 `task_contract_id`
   - `flow_exec_receipt` 预埋 contract refs
4. 在 `surface` 接线：
   - `workspace` / `single flow` / detail payload 带 `task_contract` 与 `task_contract_summary`
   - `FlowSummaryDTO` 当前可直接从 contract 摘要讲清任务，而不是只依赖 runtime prose

### 14.3 当前仍保留的 compat

这轮没有激进到直接删掉 runtime 里的旧字段，当前明确保留：

- `workflow_state.goal`
- `workflow_state.guard_condition`
- `flow_definition.goal`
- `flow_definition.guard_condition`

但这些字段现在都应视为 compat cache / snapshot，而不是主真源。

### 14.4 本轮验证通过的 slice

当前已通过的直接验证是：

- 新建 flow 会物化 `task_contract.json`
- legacy 状态读取会补落 contract
- `workspace` / `single flow` / TUI summary 能外显 `task_contract_id + task_contract_summary`
- `chat_cli_runner` 未被这轮 contract 接线回归打坏

### 14.5 下一轮 replan 裁决

进入下一轮前，当前建议固定为：

1. `P2` 先从 `flow_exec_receipt + task_contract_summary` 起步，而不是一上来重写全 artifact ledger。
2. `P3` 先做 `latest accepted receipt` 指针，再谈完整 `rollback/replay`。
3. `P4` 只引入最小 `AuthorityTransitionReceipt`，不要把 authority 摘要直接膨胀成完整组织内核。

## 15. 0407 Closure Update（`P4` Hardening + `P5` Projection Closure）

### 15.1 `P4` 写路径硬化

本轮已把 authority/policy 的落盘路径从“局部功能成立”收紧成“统一闭环成立”：

1. authority/policy 变化当前先写 typed governance receipt，再同步 `task_contract.json`，最后刷新 `recovery_cursor.json`。
2. `workflow_state.json` 继续只承接 runtime shadow/cache，不再承担 authority/policy 的权威写入。
3. `apply_operator_action()` 已修正 control-profile 变更被 stale external state 覆盖的问题，`bind_repo_contract`、`force_doctor` 等 operator action 不再从 canonical mutation 路径滑出 ledger。

### 15.2 `P5` 可见投影收口

本轮已把产品壳从旧 workbench 叙事收紧成统一 projection：

1. `workspace -> Mission Index`
2. `manage_center -> Contract Studio`
3. `single_flow -> Run Console`
4. `surface_meta` 当前是共享投影元数据真源，统一提供 `canonical_surface / display_title / legacy_aliases`。
5. `mission_console` 当前是 surface 主摘要，至少稳定包含 `task_contract_summary / latest_receipt_summary / latest_artifact_ref / recovery_state / governance_summary / derived_responsibility_graph`。

### 15.3 compat 与验证

1. 旧 `workspace / history / flows / manage_center / single_flow` 仍接受为 compat alias，但不再显示为产品主标题。
2. `manage` 与 `list` 继续是现役入口，不应被误记为 legacy。
3. provider / manage-agent 的 compat patch path 已补齐，避免测试只 patch 旧入口时失效。
4. 当前验证已覆盖 Python 回归、desktop typecheck、renderer vitest 与 CLI help。
