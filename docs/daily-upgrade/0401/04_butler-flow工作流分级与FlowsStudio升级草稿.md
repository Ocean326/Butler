# Claude Code Operator Pattern 参考下的 butler-flow workspace/manage 分工升级计划

日期：2026-04-01  
状态：执行拆解 + 第一轮实施回写  
所属层级：主落 L1 `Agent Execution Runtime`，辅用 L2 本地状态与 sidecars  
说明：文件名沿用历史草稿名，当前内容已改写为 `workspace / manage` 新边界

关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [01_前台ButlerFlow入口收口与New向导V1.md](./01_前台ButlerFlow入口收口与New向导V1.md)
- [02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md](./02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)（上位真源）
- [0331 前台WorkflowShell收口.md](../0331/02_前台WorkflowShell收口.md)
- [0331 04c-butler-flow完备升级与视觉设计计划.md](../0331/04c_butler-flow完备升级与视觉设计计划.md)
- [0331 前台butler-flow角色运行时与role-session绑定计划.md](../0331/06_前台butler-flow角色运行时与role-session绑定计划.md)

## 改前四件事

| 项 | 内容 |
| --- | --- |
| 目标功能 | 将 `0401/02` 的大计划拆成可连续执行的专题小计划，每个专题按 `plan -> imp -> review` 多轮推进直至完成。 |
| 所属层级 | 主落 L1 前台执行运行时与 TUI 壳层；状态继续落本地 flow sidecars，不进入后台 `campaign/orchestrator` 真源。 |
| 当前真源文档 | 以 [02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md](./02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md) 为准；本文只做执行拆解与实施回写。 |
| 计划查看的代码与测试 | `butler_main/butler_flow/{app,runtime,events,models,state,tui/controller.py,tui/app.py}`；主测 `test_butler_flow.py`、`test_butler_flow_tui_app.py`、`test_butler_flow_tui_controller.py`。 |

## 一句话裁决

`0401/02` 是上位真源；`0401/04` 只做执行拆解与节奏控制。  
本轮计划 4 的核心不是“统一把一切都塞进 `/manage`”，而是把两条产品线拆干净：

- `workspace + single flow`：只管 instance runtime
- `/manage`：只管 `builtin + template` shared assets

## 0401 实施回写（当前阶段）

- 已把 repo-local 资产树收口到 `butler_main/butler_bot_code/assets/flows/{builtin,templates,instances}`，并为旧 `run/butler_flow` 保留实例读取兼容。
- 已把 `project_loop` 等 builtin 读取接到 repo-local 资产根；旧代码目录只保留兼容 fallback。
- 已把 `build_manage_payload()` 收口为 shared asset 视图，当前 TUI `/manage` 只显示 `builtin + template`。
- 已把 `workspace` 默认 home 切到 instance runtime browser；旧 `/history` 只做兼容 alias/归档语义，不再承担产品级主导航。
- 已把 `/flows` 降为迁移提示并跳 `/manage`。
- 已把 `setup -> free` 改为“先经 `/manage template:new ...` 创建模板，再以 `template:<id>` 启动 instance”。
- 已补上 `catalog_flow_id=template:<id>` 的运行链路，并为其增加回归测试。
- 已把单 flow 页从“固定 summary + operator rail”重设为 `默认 supervisor 单栏流 + Shift+Tab 切到 workflow 流`，并把主信息并入 `supervisor` 流开头。
- 已补 `runtime_plan.json`、`strategy_trace.jsonl`、`prompt_packets.jsonl` 等 sidecars，用于支撑 `supervisor` 结构化流与后续更细粒度投影。
- 已把 `prompt_packets.jsonl` 升级为“结构化 packet + rendered prompt”双落地，packet 口径围绕 `flow_board / role_board / turn_task_packet` 收口。
- 已接入真实 `supervisor` runtime 路径与 `supervisor_thread_id`，并保留 heuristic fallback；当前通过 `butler_flow.supervisor_runtime.enable_llm_supervisor` 配置开启。
- 已让 executor / judge 走统一 packet compiler 路径，不再只靠旧 prompt 拼接器。
- 已接入 `mutations.jsonl` 的正式写入，并支持 `spawn_ephemeral_role` 等 flow-local 结构变异。
- 已让 TUI `supervisor` 视图显式外显 `supervisor_thread / session_mode / load_profile / latest_mutation`。

## 执行拆解总览

专题分为六类，全部来自 `0401/02` 的目标面：

1. `Controller / Event Spine`
2. `Workspace Shell`
3. `Flow Console Streams`
4. `Workspace / Manage / Setup State Model`
5. `Multi-Agent Surfacing`
6. `Acceptance / Doc Writeback`

推荐执行顺序：

1. `Controller / Event Spine`
2. `Workspace Shell`
3. `Flow Console Streams`
4. `Workspace / Manage / Setup State Model`
5. `Multi-Agent Surfacing`
6. `Acceptance / Doc Writeback`

## 专题一：Controller / Event Spine

### 目标

把 `0401/02` 的 `workspace / single flow single-column dual-stream console` 结构投影落到 controller 层；统一 timeline 汇聚与事件分类，为 TUI 和后续 surfaces 提供稳定数据。

### 涉及代码与测试

- 代码：`butler_main/butler_flow/tui/controller.py`、`butler_main/butler_flow/events.py`、`butler_main/butler_flow/state.py`
- 测试：`butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py`

### 验收关注

- payload 不再混淆 runtime 与 shared asset 管理
- timeline 能把 approval / operator / handoff / judge 提升成稳定投影
- legacy 别名命令可以解析，但不再主动展示为产品级入口

## 专题二：Workspace Shell

### 目标

把默认主壳改成 `workspace + focused flow console`，并明确 `workspace` 只浏览 instance runtime。

### 涉及代码与测试

- 代码：`butler_main/butler_flow/tui/app.py`
- 测试：`butler_main/butler_bot_code/tests/test_butler_flow_tui_app.py`

### 验收关注

- 默认 home 是 workspace
- workspace 左侧只列 instance flows
- workspace 右侧只做 runtime preview / timeline
- 任何 shared asset mutation 都通过 `/manage` 跳转，不在 workspace 内直接处理

## 专题三：Flow Console Streams

### 目标

落实 `supervisor/workflow` 单栏双流切换；把 approval/judge/operator/handoff/phase 稳定外显到结构化流，并把主信息并入 `supervisor` 流开头。

### 涉及代码与测试

- 代码：`butler_main/butler_flow/tui/app.py`、`butler_main/butler_flow/tui/controller.py`
- 测试：`test_butler_flow_tui_app.py`、`test_butler_flow_tui_controller.py`

### 验收关注

- approval / judge / operator 不再依赖 transcript 才能看见
- `handoff / role / phase` 不再依赖固定 rail，而是能稳定进入结构化流
- flow 页不再常驻右侧 inspector，相关运行时辅助信息先并入 `supervisor` 流前导块

## 专题四：Workspace / Manage / Setup State Model

### 目标

把产品状态迁移彻底写实：

- workspace：instance runtime browser
- single flow：instance runtime console
- `/manage`：shared builtin/template asset center
- `setup -> free`：先建 template，再启动 instance

### 涉及代码与测试

- 代码：`butler_main/butler_flow/tui/app.py`、`butler_main/butler_flow/app.py`
- 测试：`test_butler_flow_tui_app.py`、`test_butler_flow.py`

### 当前回写

- `/manage` 不再显示 instances
- `/flows` 只保留迁移提示
- `/history` 退位为 alias / archive 语义
- `prepare_new_flow()` 已支持 `template:<id>` 启动

### 验收关注

- `free` 不再直出 instance definition
- `/manage` 不再承载 runtime instance 管理
- `instance` definition 仍存在，但归单 flow/runtime 边界

## 专题五：Multi-Agent Surfacing

### 目标

在 `supervisor` 流开头提供紧凑多 agent 主信息；完整 role/session/handoff 先通过结构化事件与前导块承载，不再把 `/history` 当作多 agent 主展示面。

### 涉及代码与测试

- 代码：`butler_main/butler_flow/tui/controller.py`、`butler_main/butler_flow/tui/app.py`
- 测试：`test_butler_flow_tui_controller.py`、`test_butler_flow_tui_app.py`、`test_butler_flow.py`

### 验收关注

- `supervisor` 流开头只展示 `active role + execution/session mode + latest handoff`
- 角色与 handoff 辅助信息通过前导块和结构化事件可见
- archive/recovery 场景若保留独立 `/history` 语义，也只展示历史实例，不承担当前 runtime 主面

### 0401 实施回写

- 已把 `latest_handoff` 从“时间上最新”改成 `pending-first`：若存在 pending handoff，主屏优先展示 pending；否则再回退最近 consumed。
- 已把兼容层 `role_strip` 从 `role_id:session_id` 串接升级为推断型状态 chip，现役主界面则把这些状态用于 header / structured events：
  - `active` -> `role*`
  - `receiving_handoff` -> `role[in]`
  - `handoff_source` -> `role[out]`
  - `idle` -> `role`
- 当前完整多 agent detail 先落在 controller `multi_agent` 读模型里，包含：
  - `role_chips`
  - `pending_handoffs`
  - `recent_handoffs`
  - `role_sessions`
- workspace 右侧 preview 继续保持轻量，只额外补 `active_role + pending-first handoff`，不展开完整 role 列表。

## 专题六：Acceptance / Doc Writeback

### 目标

补齐验收、回归测试与文档回写，完成 `0401/02` 的落地闭环。

### 涉及代码与测试

- 测试：`test_butler_flow.py`、`test_butler_flow_tui_app.py`、`test_butler_flow_tui_controller.py`
- 文档：`docs/daily-upgrade/0401/00_当日总纲.md`、`docs/daily-upgrade/0401/{01,02,04}_*.md`、`docs/project-map/02_feature_map.md`、`docs/project-map/03_truth_matrix.md`、`docs/project-map/04_change_packets.md`、`docs/README.md`

### 验收关注

- 文档、真源矩阵与改前读包同步
- 关键 TUI 测试全部通过
- 产品面不再把 `/history`、`/flows` 当正式命令推荐
- shared asset manage 与 instance runtime 叙述完全分开
