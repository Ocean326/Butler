# 0402 Butler Flow Manage Center 资产中心升级与会话式交互落地

日期：2026-04-02  
状态：已实施

## 1. 本轮裁决

1. `/manage` 继续只管理 shared assets，不接管 `instance` runtime。
2. shared assets 的真源仍是 `assets/flows/{builtin,templates}/*.json`，但升级为 **JSON 合同 + companion bundle**：
   - JSON 是 runtime / materialization 真源
   - bundle 承载 `manager.md`、`supervisor.md`、`sources.json`、`references/`、`assets/`、`derived/`
3. manager agent 现役生命周期升级为：
   - `proposal`
   - `build`
   - `review`
   - `commit`
4. `/manage` TUI 从栏式卡片改成 transcript-first shell：
   - 下方输入框是主入口
   - 支持 `$template:<id>` / `$builtin:<id>` mention
   - 选中后继续自然语言描述管理意图
   - `Enter` 在 picker 打开时先做 mention 选择，不直接发送
   - picker 固定出现在输入框下方，最多展示 7 个候选，可 `↑/↓/Enter`
5. builtin 资产每次修改都必须显式二选一：
   - `clone` 到 editable template
   - `edit` 原地修改 builtin
6. supervisor 认知采用 **手写 + 编译混合**：
   - bundle 内允许 `supervisor.md`
   - runtime/compiler 注入 `compiled supervisor knowledge`
   - 不把完整 supervisor prompt 文件当唯一真源

## 2. 静态资产升级

shared asset definition 新增以下静态字段：

- `asset_state`
  - 当前阶段与资产状态，例如 `draft / active`
- `lineage`
  - clone 来源、编辑来源、来源版本
- `instance_defaults`
  - materialize instance 时的默认 `execution_mode / session_strategy / role_pack_id / launch_mode`
- `review_checklist`
  - 管理/发布前的静态检查项
- `bundle_manifest`
  - 关联 bundle 的路径与派生产物入口

instance materialization 新增以下来源字段：

- `source_asset_key`
- `source_asset_kind`
- `source_asset_version`

## 3. 代码落点

- `butler_main/butler_flow/app.py`
  - manage asset definition 扩展静态字段
  - builtin `clone/edit` 明确分流
  - template/builtin materialization 写入 `source_asset_*`
  - instance `flow_definition.json` 持久化 `bundle_manifest / review_checklist / source_asset_*`
- `butler_main/butler_flow/manage_agent.py`
  - manager prompt/result 支持 `proposal/build/review/commit`
- `butler_main/butler_flow/state.py`
  - 新增 shared bundle root/manifest/helper
  - shared asset 自动补 bundle 目录与基础文件
- `butler_main/butler_flow/compiler.py`
  - compiled packet 挂接 `asset_context / supervisor_knowledge`
- `butler_main/butler_flow/runtime.py`
  - runtime 从 instance definition/bundle 读取 mixed supervisor knowledge 并注入 supervisor packet
- `butler_main/butler_flow/tui/app.py`
  - `/manage` 改为 transcript-first shell
  - 各页纯文本路由：`manage -> manager chat`、`flow -> supervisor queue`、`history -> reject`
  - manager chat queue + manager session reuse
  - `$asset` inline picker + 资产选择
- `butler_main/butler_flow/tui/manage_interaction.py`
  - 抽离 manage prompt 解析、mention picker 状态、bare target/`$target` 解析
- `butler_main/butler_flow/manage_agent.py`
  - 新增 manager chat prompt/result
  - manager chat 走 Codex 同 session resume
- `butler_main/butler_flow/tui/controller.py`
  - 新增 `manage_chat()` API，和 `manage_flow()` 分离

## 4. 当前交互口径

### 4.1 transcript-first `/manage`

- 主屏展示：
  - overview
  - assets
  - selected asset
  - manage notes
- 输入模式示例：
  - `$template:new create a reusable research flow`
  - `$template:my_flow refine the review checklist`
  - `$builtin:project_loop clone make a team-specific variant`
  - `$builtin:project_loop edit update the builtin in place`

### 4.2 当前输入协议

- `manage` 页
  - 纯文本默认进入 manager chat
  - 无显式 target 时，由 manager chat 先沟通、澄清，再决定是否执行 `new` / `template:new` / 现有资产更新
  - 若带 `$template:<id>` / `$builtin:<id>`，表示把目标资产绑定到当前 chat 轮次
  - 若用户直接写 `template:<id> ...` / `builtin:<id> ...`，显式 target 仍优先于当前焦点资产
  - manager chat 在信息充分时可直接回传结构化 action，并自动衔接 `manage_flow()`
- `flow` 页
  - 纯文本默认进入 supervisor
  - 当前 flow 为 `running/paused` 时，文本走 `append_instruction`，排到同一 flow session 的后续 turn
- `history` 页
  - 纯文本不发送，只接受 slash 命令

### 4.3 manager chat vs 显式命令

- manager chat
  - 当前是 `manage` 页纯文本默认入口
  - 负责先讨论、补齐约束、细化静态字段与资产边界
  - 在 ready 时自动下发 `manage_flow()`，用于新建 `pending` flow、创建 template 或更新现有 shared asset
- 显式命令
  - `/manage ...` 仍保留
  - 适合需要明确指定 `template:new / builtin:<id> / template:<id>` 的场景
  - builtin 修改仍必须显式 `clone` / `edit`

### 4.4 builtin 操作

- 没写 `clone` / `edit` 时，当前实现直接拒绝，要求显式选择
- `clone` 会转成新的 template asset，并写入 `lineage.cloned_from_asset_key`
- `edit` 会保留 builtin 身份，并在 `asset_state.mode` 标记原地编辑

### 4.5 flow session queue

- flow supervisor 输入若当前 flow 为运行中：
  - 文本通过 `append_instruction` 入队
  - 由现有 flow `codex_session_id` / role session 续接语义消费

## 5. 与 single flow/runtime 的边界

- `/manage`
  - 管 shared `builtin + template`
  - 管静态字段、bundle、manager handoff、review checklist
- `workspace + single flow`
  - 管 `instance`
  - 管 runtime timeline / supervisor/workflow stream / operator action
  - 只读显示 materialized source asset 摘要，不在这里回写 shared definition

## 6. 本轮验收

- `test_butler_flow.py`
  - 覆盖 template materialization 的 `source_asset_*`
  - 覆盖 template bundle 自动创建
  - 覆盖 builtin 必须显式 `clone/edit`
  - 覆盖 supervisor knowledge 注入 packet
- `test_butler_flow_tui_app.py`
  - 覆盖 `/manage` transcript-first
  - 覆盖 `$asset` mention suggester
  - 覆盖 `manage/flow/history` 纯文本默认路由
  - 覆盖 plain text -> manager chat、manager chat -> `manage_flow()` 自动执行
  - 覆盖 picker 7 项窗口、explicit target 覆盖当前 builtin focus
- `test_butler_flow_tui_controller.py`
  - 复验 controller 参数面未回退
  - 覆盖 `manage_chat()` API
- 实测回归：
  - `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow.py butler_main/butler_bot_code/tests/test_butler_flow_tui_app.py butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py -q`
  - 本次变更后重新执行并回写最新结果
