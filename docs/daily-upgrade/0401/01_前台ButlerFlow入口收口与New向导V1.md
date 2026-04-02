# 0401 前台 Butler Flow 入口收口与 New 向导 V1

日期：2026-04-01  
状态：实施中 / 当前真源（覆盖 0331 入口口径）  
所属层级：L1 `Agent Execution Runtime`，辅用 L2 本地状态/轨迹存储  
关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md](./02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)
- [04_butler-flow工作流分级与FlowsStudio升级草稿.md](./04_butler-flow工作流分级与FlowsStudio升级草稿.md)
- [0331 前台 Workflow Shell 收口](../0331/02_前台WorkflowShell收口.md)

## 一句话裁决

前台 `butler-flow` 的公开入口收口为 `new/resume/exec`。  
TTY 下 `new` 必经 setup picker。`/flows` 不再是产品入口，只保留迁移提示；`free` 设计链路改为“先在 `/manage` 创建 template，再从 setup 继续启动”。

## 入口与兼容

### 公开入口

- `butler-flow`
- `butler-flow new`
- `butler-flow resume`
- `butler-flow exec`

### 兼容别名

- `butler-flow run` -> `butler-flow new`
- `butler-flow exec run` -> `butler-flow exec new`
- `butler-flow flows` -> 迁移提示，指向 `/manage`

兼容别名保留一版，但不在首屏帮助、launcher 主动作或 setup 提示中展示。

## New 向导（setup picker）

### 触发规则

- TTY 下 `new` 固定进入 setup picker。
- `--plain` 表示“走 plain 向导 / plain attached UI”，不再表示“跳过向导直接执行”。
- 非 TTY 下 `new` / `exec new` 仍允许纯参数直跑。

### 向导步骤

1. `goal`
2. `mode=single|flow`
3. 若 `flow`：
   - `level=simple|medium|high(禁用)`
   - `flow=<builtin catalog | free | template:<id>>`
4. `guard condition / attempts`
5. `confirm`

### 映射规则

- `single` -> `workflow_kind=single_goal`、`phase=free`、`execution_mode=simple`
- `flow + simple` -> builtin 或 template flow，`execution_mode=simple`
- `flow + medium` -> builtin 或 template flow，`execution_mode=medium`
- `flow + high` -> 仅可见但禁用，显示 `coming soon`，不允许提交

## Builtin Catalog 与 Template 消费

### Builtin Catalog 合同字段

- `flow_id`
- `label`
- `description`
- `workflow_kind`
- `phase_plan`
- `default_role_pack`
- `allowed_execution_modes`

### V1 交付

- 当前真实 builtin 项至少保留 `project_loop`
- `template:<id>` 由 `/manage` 创建后回流到 setup picker 使用
- `free` 永远是 setup 动作入口，不再是静态 catalog 文件项，也不再直接产出 instance

## `free` 的现役链路

### 当前产品语义

`new -> flow -> free` 的含义不再是“立刻进入 `/flows` 设计 instance”。  
它的现役含义是：

1. 从 setup 跳到 `/manage`
2. 预填 `template:new ...` 指令
3. 由 manager 侧创建一个 shared template
4. 创建成功后回到 setup confirm
5. 以 `catalog_flow_id=template:<id>` 启动新的 instance flow

### 产物边界

- shared definition 落在 `templates/<id>.json`
- runtime instance 仍落在 flow sidecars
- instance 与 template 的偏差来自 materialization 时刻，而不是后续在 `/manage` 任意改 instance

## 持久化扩展

### `workflow_state.json` / `flow_definition.json`

- 新增字段：`launch_mode`、`catalog_flow_id`
- 当实例来自模板时，`catalog_flow_id` 记录为 `template:<id>`

### 设计态 sidecar

兼容期仍允许保留：

- `design_session.json`
- `design_turns.jsonl`
- `design_draft.json`

但它们不再对应产品级 `/flows` 页面；当前产品面只保留 setup -> `/manage template:new ...` 这一条设计入口。

## 运行边界

- `workspace` / `single flow` 负责 instance runtime
- `/manage` 只负责 `builtin + template` shared assets
- `instance` 不进入 `/manage`
- `exec` 的 JSONL 与 `flow_exec_receipt` 契约保持不变
- 本轮只改前台 L1/L2，不进入 `campaign/orchestrator`
