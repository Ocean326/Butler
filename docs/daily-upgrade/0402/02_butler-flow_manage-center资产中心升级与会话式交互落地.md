# 0402 Butler Flow Manage Center 资产中心升级与会话式交互落地

日期：2026-04-02  
状态：已实施（同日补充 lightweight `role_guidance` 与临时角色参考）

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
- `role_guidance`
  - 轻量角色参考字段，只服务两件事：
    1. 给 manager 在创建 template/flow 时提供参考
    2. 给 supervisor 在 runtime 中选择临时节点角色时提供参考
  - 当前口径是**建议型静态资产**，不是固定 team contract
  - 推荐结构：
    - `suggested_roles`
    - `suggested_specialists`
    - `activation_hints`
    - `promotion_candidates`
    - `manager_notes`

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
  - `flow_board / asset_context` 透传 `role_guidance`，并显式标注其为 advisory only
- `butler_main/butler_flow/runtime.py`
  - runtime 从 instance definition/bundle 读取 mixed supervisor knowledge 并注入 supervisor packet
  - runtime 透传 `role_guidance` 给 supervisor 作为轻量角色参考
- `butler_main/butler_flow/role_runtime.py`
  - 补 `creator / product-manager / user-simulator` 的 fallback role prompt
  - ephemeral role 优先继承 role pack 中的 base role prompt，不再只靠单一 fallback
- `butler_main/butler_flow/tui/app.py`
  - `/manage` 改为 transcript-first shell
  - 各页纯文本路由：`manage -> manager chat`、`flow -> supervisor queue`、`history -> reject`
  - manager chat queue + manager session reuse
  - `$asset` inline picker + 资产选择
  - manage detail 显示 `role_guidance`
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
  - 无显式 target 时，由 manager chat 先沟通、澄清，并默认先走 `template-first`：先选/建/改 template，再决定 flow 实例化
  - 若带 `$template:<id>` / `$builtin:<id>`，表示把目标资产绑定到当前 chat 轮次
  - 若用户直接写 `template:<id> ...` / `builtin:<id> ...`，显式 target 仍优先于当前焦点资产
  - manager chat 需要显式经历 `template_confirm` 与 `flow_confirm` 两个确认点；只有确认到当前管理动作时，才回传结构化 action 并衔接 `manage_flow()`
- `flow` 页
  - 纯文本默认进入 supervisor
  - 当前 flow 为 `running/paused` 时，文本走 `append_instruction`，排到同一 flow session 的后续 turn
- `history` 页
  - 纯文本不发送，只接受 slash 命令

### 4.3 manager chat vs 显式命令

- manager chat
  - 当前是 `manage` 页纯文本默认入口
  - 采用 `manager role + manager skills + asset bundle/manager.md` 的注入结构，不再依赖本地文本硬门控
  - 负责先讨论、补齐约束、细化静态字段与资产边界；新需求默认 `template-first`
  - 创建顺序固定优先为：讨论 → 选/建/改 template → 补齐 `goal / guard_condition / supervisor.md` 方向 → 确认 template → 确认 flow → 创建/更新 flow
  - 当前显式输出 `manager_stage / active_skill / confirmation_scope / confirmation_prompt`
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

### 4.6 lightweight role guidance

- manager 在创建 template / pending flow 时，应主动思考但不强绑：
  - 当前默认适合哪些常驻角色参考（如 `planner / implementer / reviewer`）
  - 哪些只在堵点或创新点出现时再临时调用（如 `creator / product-manager / user-simulator`）
  - 哪些临时节点值得在 runtime 中升级成更持久的 role session
- supervisor 在执行时：
  - 仍保持唯一外部主脑
  - `role_guidance` 只作为启发，不替代 supervisor 自主判断
  - 若任务中出现环境缺口、产品体验验证、用户试用、格式/图表/知识盲区等问题，可按需 `spawn_ephemeral_role`

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
  - 覆盖 `role_guidance` 从 asset -> flow_state -> compiled prompt 的透传
  - 覆盖 `creator / product-manager / user-simulator` fallback prompt
- `test_butler_flow_tui_app.py`
  - 覆盖 `/manage` transcript-first
  - 覆盖 `$asset` mention suggester
  - 覆盖 `manage/flow/history` 纯文本默认路由
  - 覆盖 plain text -> manager chat、manager chat -> `manage_flow()` 自动执行
  - 覆盖 picker 7 项窗口、explicit target 覆盖当前 builtin focus
  - 覆盖 manage detail 的 `role_guidance` 展示
- `test_butler_flow_tui_controller.py`
  - 复验 controller 参数面未回退
  - 覆盖 `manage_chat()` API
- 实测回归：
  - `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow.py butler_main/butler_bot_code/tests/test_butler_flow_tui_app.py butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py -q`
  - 本次变更后重新执行并回写最新结果

## 6.1 0403 续落地补充

0403 对本专题继续补了三件关键事：

1. manager chat 从“模型直接回 `action_ready=true` 就执行”改为“持久化 `manage_session + draft + pending_action`”。
2. 首次给出 template / flow draft 时，默认只展示 draft 与待确认动作，不再自动创建。
3. 真正提交改为 `draft_payload -> manage_flow()`：
   - 提交结果以规范化后的实际写盘结果为准
   - `manage_handoff.summary` 与 `manage_audit` 改为从 canonical saved definition 生成
4. manager chat 的当前稳态修补口径补齐为：
   - 首轮纯文本会默认绑定当前 manage focus asset；同一 manager session 的后续轮次改为依赖 session sticky target，除非用户显式重新指定 target
   - TUI 提交前会清理悬空 `$`/无效 mention 前缀，避免把残留 picker token 直接送进 manager
   - 若 manager 返回的不是合法 JSON，系统会把原始 reply 透传给 operator，并把 `parse_status / raw_reply / error_text` 记入 manage turn，而不是回退成 `Manager chat completed.`
   - parse failed 时不清空既有 `pending_action`，避免讨论阶段把待确认草稿意外冲掉

同时补充 shared asset / instance static asset 字段：

- `supervisor_profile`
  - 精选 supervisor 风格，不做独立资产
- `run_brief`
  - 本次 run 或该 template 的 supervisor 运行摘要
- `source_bindings`
  - manager 讨论阶段选定的关键来源，提交后写入 bundle `sources.json`

runtime/compiler 当前注入口径：

- `asset_context` 透传 `supervisor_profile / run_brief / source_bindings`
- bundle `derived/supervisor_knowledge.json` 由静态字段编译生成，不再只保留空壳文件

0403 同步补了 manager -> supervisor 的治理交接口径：

- manager 在 template / flow 设计时应同步给出 `control_profile`
- `control_profile` 是实例级治理合同，不再只是 manager 讨论阶段的备注
- `repo_bound` 只表示执行位置；repo contract 是否生效，单独看 `control_profile.repo_binding_policy + repo_contract_paths`
- supervisor 后续对 `packet_size / evidence_level / gate_cadence / repo_binding_policy` 的调整会回写实例态，而不是只显示在 decision 里

## 7. 补充：长流治理与 supervisor 可观测性

- supervisor stream 的 Input / Output / Decision 外显，以及 heuristic supervisor 的合成输入/输出记录，已另行收口到：
  - [11_butler-flow_长流治理与supervisor可观测性升级.md](./11_butler-flow_长流治理与supervisor可观测性升级.md)
