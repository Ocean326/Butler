# 改前读包

更新时间：2026-04-09
状态：现役
用途：把常见改动压成固定最小读包，避免 agent 自由扩散式读库

## 通用基础包

所有改动默认先读：

1. 仓库根 `README.md`
2. [docs/README.md](../README.md)
3. 当天 `docs/daily-upgrade/<MMDD>/00_当日总纲.md`（当前为 `0409/00_当日总纲.md`）

## `frontdoor`

- 额外必读：
  - [当前系统基线](./00_current_baseline.md)
  - [分层地图](./01_layer_map.md)
  - [功能地图](./02_feature_map.md)
  - [0327 后台任务固定输出区与严格验收收口](../daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)
  - [0329 后台任务双状态与前门弱化重构](../daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
  - [0329 Chat 显式模式与 Project 循环收口](../daily-upgrade/0329/02_Chat显式模式与Project循环收口.md)
  - [0327 Skill Exposure Plane 与 Codex 消费边界](../daily-upgrade/0327/02_SkillExposurePlane与Codex消费边界.md)
  - [0401 Claude / Codex CLI 单 Session 能力报告](../daily-upgrade/0401/20260401_claude_codex_cli_session_report.md)
  - [0402 Chat Router 选会话能力升级回写](../daily-upgrade/0402/01_chat_router选会话能力升级回写.md)
  - [0326 Harness 全系统稳定态运行梳理](../daily-upgrade/0326/03_Harness全系统稳定态运行梳理.md)
- 默认代码目录：
  - `butler_main/products/chat/`
  - `butler_main/chat/`（compat shell）
  - `butler_main/products/campaign_orchestrator/orchestrator/interfaces/`
  - `butler_main/agents_os/execution/cli_runner.py`
  - `butler_main/products/chat/frontdoor_cli_router.py`
- 默认测试：
  - `test_chat_campaign_negotiation.py`
  - `test_chat_long_task_frontdoor_regression.py`
  - `test_request_intake_service.py`
  - `test_talk_mainline_service.py`
  - `test_chat_router_frontdoor.py`
  - `test_chat_engine_model_controls.py`
  - `test_talk_runtime_service.py`
  - `test_chat_recent_memory_runtime.py`
  - `test_conversation_turn_engine.py`
  - `test_chat_runtime_request_override_runtime.py`
- 临时熔断附加检查：
  - 先看 `butler_main/products/chat/feature_switches.py`
  - 再看 `butler_main/butler_bot_code/configs/butler_bot.json -> features.chat_frontdoor_tasks_enabled`
  - 回归优先补 `test_chat_router_frontdoor.py`、`test_talk_mainline_service.py`、`test_agent_soul_prompt.py`
  - 模式收口附加检查：
  - 先看 `butler_main/products/chat/frontdoor_modes.py` 的 slash 契约
  - 再看 `butler_main/products/chat/frontdoor_cli_router.py`、`butler_main/products/chat/router_plan.py` 与 `butler_main/products/chat/routing.py` 的 unified compile，确认当前 `route / frontdoor_action / main_mode / role_id / injection_tier / capability_policy / runtime_lane` 是否仍由单次前门编译产出
  - 若涉及“续接当前主线还是重开新题”，先看 `butler_main/products/chat/session_selection.py`、`butler_main/products/chat/mainline.py` 与 `butler_main/products/chat/memory_runtime/recent_turn_store.py`，确认 `chat_session_id` 是否已在当前 `session_scope_id` 内正确 bootstrap、写回、过滤 recent
  - 再看 `butler_main/products/chat/session_modes.py` 的 sticky state、recent 配额与 `project_artifact`
  - 再看 `butler_main/products/chat/mainline.py` 和 `butler_main/products/chat/prompting.py` 是否仍把 `/pure` 当成功能路由，而不是厚度 overlay
  - 改默认厚 prompt 块顺序、门控或 session selection 指示块时，对照 [0330 Chat 默认厚 Prompt 分层治理真源](../daily-upgrade/0330/04_Chat默认厚Prompt分层治理真源.md) 与 [0402 Chat Router 选会话能力升级回写](../daily-upgrade/0402/01_chat_router选会话能力升级回写.md) 同步更新文档
  - 若涉及 chat/frontdoor 默认 CLI，先看 `frontdoor_cli_router.py` 的 lane map 与 `butler_main/products/chat/data/hot/frontdoor_cli_router/governance_state.json`，不要直接改全局 `cli_runtime.active`
  - 若涉及 `codex/claude cli` session 连续性，先核对 `session_scope_id` 是否仍是 Butler 主键，再看 `cli_runner` 的 `external_session/recovery_state/vendor_capabilities`，最后检查 `chat/light_memory.py` 是否把 vendor thread 仅作为可丢的外部 binding 持久化

## `campaign-control-plane`

- 额外必读：
  - [当前系统基线](./00_current_baseline.md)
  - [分层地图](./01_layer_map.md)
  - [功能地图](./02_feature_map.md)
  - [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写（历史文件名保留草稿）](../daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)
  - [0327 后台任务固定输出区与严格验收收口](../daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)
  - [0329 后台任务双状态与前门弱化重构](../daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
  - [0327 Skill Exposure Plane 与 Codex 消费边界](../daily-upgrade/0327/02_SkillExposurePlane与Codex消费边界.md)
  - [0326 稳定 Harness 之后的下一阶段主线](../daily-upgrade/0326/04_稳定Harness之后的下一阶段主线_Anthropic长运行Harness吸收版.md)
- 默认代码目录：
  - `butler_main/products/campaign_orchestrator/orchestrator/`
  - `butler_main/products/campaign_orchestrator/campaign/`
  - `butler_main/orchestrator/`（compat shell）
  - `butler_main/domains/campaign/`（compat shell）
- 默认测试：
  - `test_orchestrator_campaign_service.py`
  - `test_orchestrator_runner.py`
  - `test_orchestrator_campaign_observe.py`
- 默认动作：
  - 先判断目标 campaign 是否为 `agent_turn` 新主线；若是，优先看 `canonical_session_id`、`task_summary`、`latest_turn_receipt`
  - 不再默认假设创建 campaign 会同时建 `mission/node/branch`
  - `resume_campaign` 对新 campaign 表示“只执行一个 supervisor turn”
  - `feedback/query` 优先读宏摘要和最新 turn receipt，不再把 `build_campaign_semantics()` 当首真源

## `runtime-contract`

- 额外必读：
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [分层地图](./01_layer_map.md)
  - [真源矩阵](./03_truth_matrix.md)
  - [Butler Runtime 复用接入指南](../runtime/README.md)
  - [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
  - [0327 Skill Exposure Plane 与 Codex 消费边界](../daily-upgrade/0327/02_SkillExposurePlane与Codex消费边界.md)
  - [0329 Codex 主备默认自动切换](../daily-upgrade/0329/01_Codex主备默认自动切换.md)
  - [0331 前台 Workflow Shell 收口](../daily-upgrade/0331/02_前台WorkflowShell收口.md)
- 默认代码目录：
  - `butler_main/platform/runtime/`（canonical alias）
  - `butler_main/compat/agents_os/`（canonical alias）
  - `butler_main/compat/multi_agents_os/`（canonical alias）
  - `butler_main/runtime_os/process_runtime/`
  - `butler_main/runtime_os/durability_substrate/`
  - `butler_main/runtime_os/multi_agent_protocols/`
  - `butler_main/runtime_os/multi_agent_runtime/`
  - `butler_main/orchestrator/runtime_bridge/`
  - `butler_main/orchestrator/workflow_ir.py`
- 默认测试：
  - `test_orchestrator_core.py`
  - `test_orchestrator_workflow_ir.py`
  - `test_orchestrator_workflow_vm.py`
  - `test_runtime_module_layout.py`

## `butler-flow`

- 额外必读：
  - [当前系统基线](./00_current_baseline.md)
  - [分层地图](./01_layer_map.md)
  - [功能地图](./02_feature_map.md)
  - [真源矩阵](./03_truth_matrix.md)
  - [0409 Butler Desktop Codex 式 Manager Thread 前端升级计划与实施稿](../daily-upgrade/0409/01_butler-desktop_codex式manager-thread前端升级.md)
  - [0405 当日总纲](../daily-upgrade/0405/00_当日总纲.md)
  - [0405 Butler Flow Desktop 线程化工作台与 Manager-Supervisor 串联落地](../daily-upgrade/0405/01_butler-flow_desktop线程化工作台与manager-supervisor串联落地.md)
  - [0408 Team 与 Desktop 关系、当前进度与下一条主线](../daily-upgrade/0408/01_team与desktop关系_当前进度与下一条主线.md)
  - [0403 当日总纲](../daily-upgrade/0403/00_当日总纲.md)
  - [0403 Butler Flow Codex 执行根隔离与 `repo_bound` 裁决](../daily-upgrade/0403/01_butler-flow_Codex执行根隔离与repo_bound裁决.md)
  - [0403 Butler Flow supervisor 控制画像与 agents-flow 治理升级](../daily-upgrade/0403/02_butler-flow_supervisor控制画像与agents-flow治理升级.md)
  - [0403 Butler Flow Desktop 壳与 shared surface bridge 落地](../daily-upgrade/0403/03_butler-flow_desktop壳与shared_surface_bridge落地.md)
  - [0401 当日总纲](../daily-upgrade/0401/00_当日总纲.md)
  - [0402 当日总纲](../daily-upgrade/0402/00_当日总纲.md)
  - [0402 Butler-flow Desktop V2.1 PRD（main 分支对齐 / foreground flow CLI 入口 / TUI + Desktop 双轨）](../daily-upgrade/0402/20260402_Butler-flow%20Desktop%20V2.1%20PRD_main%E5%88%86%E6%94%AF%E5%AF%B9%E9%BD%90_flow%20CLI%E5%85%A5%E5%8F%A3%E4%B8%8E%E5%8F%8C%E8%BD%A8%E5%AE%9E%E6%96%BD_%E6%9B%B4%E6%96%B0%E7%89%88.md)
  - [0402 Butler-flow-Desktop 开发计划（butler-flow 执行版，含 Desktop 技术选型与 Proma 复用边界）](../daily-upgrade/0402/20260402_Butler-flow-Desktop%E5%BC%80%E5%8F%91%E8%AE%A1%E5%88%92_butlerflow%E6%89%A7%E8%A1%8C%E7%89%88.md)
  - [0402 Butler Flow Manage Center 资产中心升级与会话式交互落地](../daily-upgrade/0402/02_butler-flow_manage-center资产中心升级与会话式交互落地.md)
  - [0402 Butler Flow 长流治理与 supervisor 可观测性升级](../daily-upgrade/0402/11_butler-flow_长流治理与supervisor可观测性升级.md)
  - [0402 Butler Flow Doctor 恢复角色与实例级静态资产修复](../daily-upgrade/0402/12_butler-flow_doctor恢复角色与实例级静态资产修复.md)
  - [0401 前台 Butler Flow 入口收口与 New 向导 V1](../daily-upgrade/0401/01_前台ButlerFlow入口收口与New向导V1.md)
  - [0401 Claude Code 对 Butler Flow 工作台化升级与 TUI 信息架构计划](../daily-upgrade/0401/02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [0331 前台 Workflow Shell 收口](../daily-upgrade/0331/02_前台WorkflowShell收口.md)
  - [0331 04c-butler-flow完备升级与视觉设计计划](../daily-upgrade/0331/04c_butler-flow完备升级与视觉设计计划.md)
  - [0331 前台 butler-flow 角色运行时与 role-session 绑定实施回写](../daily-upgrade/0331/06_前台butler-flow角色运行时与role-session绑定计划.md)
  - [0331 Agent 监管 Codex 实践（exec 与 resume）](../daily-upgrade/0331/01_Agent监管Codex实践_exec与resume.md)
  - [0401 Claude / Codex CLI 单 Session 能力报告](../daily-upgrade/0401/20260401_claude_codex_cli_session_report.md)
  - [0329 Codex 主备默认自动切换](../daily-upgrade/0329/01_Codex主备默认自动切换.md)
  - [0329 Chat 显式模式与 Project 循环收口](../daily-upgrade/0329/02_Chat显式模式与Project循环收口.md)
- 默认代码目录：
  - `butler_main/products/butler_flow/`
  - `butler_main/products/butler_flow/surface/`
  - `butler_main/products/butler_flow/desktop_bridge.py`
  - `butler_main/products/butler_flow/desktop/`
  - `butler_main/products/butler_flow/role_packs/`
  - `butler_main/butler_flow/`（compat shell）
  - `butler_main/__main__.py`
  - `butler_main/platform/runtime/`（canonical alias）
  - `butler_main/runtime_os/agent_runtime/`
  - `tools/butler-flow`
  - `tools/install-butler-flow`
  - `butler_main/butler_cli.py`
- 默认测试：
  - `test_butler_flow.py`
  - `test_butler_cli.py`
  - `test_chat_cli_runner.py`
  - `test_agents_os_wave1.py`
  - `test_butler_flow_tui_controller.py`
  - `test_butler_flow_tui_app.py`
  - `test_butler_flow_surface.py`
  - `test_butler_flow_desktop_bridge.py`
  - `butler_flow_desktop_thread_workbench_test_cases.md`
- TUI 信息架构附加检查：
  - 先确认当前实现是否已是 `workspace + single flow single-column dual-stream console + /manage + /settings`，并注意 `/history` `/flows` 都已经退成兼容语义，不要再把它们写成产品级主入口
- 再看 `butler_main/products/butler_flow/tui/controller.py` 的 payload 是否已抽象成 `workspace / single_flow.navigator_summary / single_flow.supervisor_view / single_flow.workflow_view / single_flow.inspector` 这些现役投影；`operator_rail_payload / role_strip_payload` 只应作为兼容层
  - 若做本轮升级，主屏常驻信息以 `0401/02` 为准：`workspace navigator + default supervisor stream + Shift+Tab -> workflow stream`
  - 当前 `workspace` 左栏应是 instance runtime list，右栏应是 runtime preview / timeline；如保留 `/history` 语义，也只承接 archive/recovery，不回到主导航职责
  - 当前 `/manage` 已收口为 shared asset center，只显示 `builtin + template`；`/flows` 只保留兼容别名，free 设计链路只应在 setup 内部通过 `/manage template:new ...` 进入
  - 当前 `/manage` 主视图必须是 transcript-first shell，而不是栏式资产卡片；底部输入框是主入口，支持 `$template:<id>` / `$builtin:<id>` mention 与自然语言管理意图
  - 当前纯文本路由固定为：`manage -> manager chat`、`flow -> supervisor queue`、`history -> reject`
- 若改 `/manage` 输入协议，先看 `butler_main/products/butler_flow/tui/manage_interaction.py` 与 `tui/app.py` 的 bare target/`$target` 解析、mention picker 7 项窗口、manager queue/session 续接；当前口径是：首轮纯文本默认绑定当前 asset focus，同一 manager session 后续轮次默认依赖 sticky target；提交前会清理悬空 `$` / 无效 mention 前缀；会话同时把 `manage_session / draft / pending_action` 落盘，支撑 `template_confirm -> flow_confirm` 的连续讨论
- 若改 manager chat prompt/runtime，优先看 `butler_main/products/butler_flow/manage_agent.py` 与 `butler_main/products/butler_flow/manager_prompt_assets/`；现役口径是 `manager role + skills + bundle/manager.md + references/`，但职责和提交门控的真源在代码侧：`manager skill registry` 决定当前 skill 的 scope / draft ownership / action capability，prompt payload 只注入轻量 `asset/session/pending_action` 摘要；首次 draft 不自动提交，只有纯确认才能消费已有 `pending_action`
  - 若排查 manager “不说话 / 只显示 Manager chat completed.”，先看 `manage_agent.py` 的 parse-failure 透传链路；当前非 JSON reply 会原样返回 UI，并把 `parse_status / raw_reply / error_text` 写入 manage turn，且 parse failed 时不主动清空既有 `pending_action`
  - 若排查 manager `resume` 卡在 `Reconnecting... / timeout waiting for child process to exit / no rollout found`，先看 `manage_agent.py` 的 manager-specific Codex self-heal；当前口径是同 provider 内自动从 `resume` 改跑一次 fresh Codex exec，成功后切到新 `manager_session_id`，但不切 Cursor，也不对首轮 fresh exec 做二次重试
  - 若涉及 builtin 修改，必须核对当前是否仍要求显式 `clone` 或 `edit`，不要回退到隐式原地修改
  - 若涉及静态资产，补看 shared JSON 是否带有 `asset_state / lineage / instance_defaults / review_checklist / role_guidance / supervisor_profile / run_brief / source_bindings / bundle_manifest`
  - 若涉及 runtime 注入，补看 instance `flow_definition.json` 是否已写入 `source_asset_key / source_asset_kind / source_asset_version`，以及 bundle 中 `sources.json + supervisor.md + derived/supervisor_knowledge.json` 是否仍由 compiler/runtime 混合注入
  - 若涉及 manager 真正提交路径，先看 `manage_chat()` 是否仍把确认后的结构化 `draft_payload` 传给 `manage_flow()`；不要回退到直接信任模型自由文本 `action_instruction`
  - 若涉及 `approval_state / judge / operator receipt / runtime events`，先核对它们是进入 transcript、rail 还是 detail，不要继续散落在 `/status`、`actions.jsonl` 和 raw timeline 之间
  - 若涉及 flow 管理，补看 repo-local `butler_main/butler_bot_code/assets/flows/{builtin,templates,instances}` 是否仍是唯一存储树；其中 `/manage` 只管 `builtin + template`，`instances` 只是 runtime/兼容布局
  - `test_codex_provider_failover.py`
  - `test_codex_cursor_switchover.py`
  - `test_runtime_os_namespace.py`
- 默认动作：
  - 先确认目标是前台 `butler-flow` CLI，而不是后台 `campaign/orchestrator`
  - 若问题是在讲 “team 与 desktop 的关系、当前进度、下一条主线”，先读 `0408/01`；若当前分支没有 `0407` 文档目录或对应真源对象，再对照 `main@80d595b`，不要假设 Desktop 分支已经自动带入 canonical runtime 闭环
  - 入口以 `new/resume/exec` 为主；`run/exec run` 仅是兼容别名
  - TTY 下 `new` 固定进入 setup picker；`--plain` 表示走 plain 向导，不是跳过向导
  - `workspace` / single flow 负责 instance runtime；`/manage` 只负责 `builtin + template` shared assets；`/list` 与 `/manage` 同义；`/flows` 仅是迁移提示
  - 当前 `team` 的默认理解固定为前台 `butler-flow` 上的 runtime 语义，而不是 `Team OS` 或后台控制面对象
  - 当前 `desktop` 的默认理解固定为 projection shell；任何下一轮 Desktop 工作都应优先服务 `P6 Closure Gate`，不要先扩成独立产品平台
  - 若改 `/manage`，优先检查 `build_manage_payload()`、`manage_flow()`、`tui/app.py` 的 transcript-first shell 与 `$asset` suggester，而不是回退到 `flows-list + flows-detail` 的卡片心智
  - 若本轮还涉及根工作区遗留脏改动吸收，优先把旧 compat 路径上的改动移植到 `butler_main/products/butler_flow/`，不要把旧物理路径重新写回 canonical tree
  - `free` 设计链路固定是“setup -> /manage template:new -> template:<id> -> launch instance”，不要再把它写回 `/flows` 设计页
  - 若涉及角色运行时，先确认 `execution_mode` 与 `session_strategy`；当前口径是 `simple=shared`、`medium=role_bound`、`complex=per_activation(预留合同)`；再确认 `role_guidance` 是否仍只是 manager/supervisor 的轻量参考，而不是硬 team contract
  - 若涉及 supervisor 治理、长流失控、repo contract、operator control action 或 manager->supervisor handoff，先看 `control_profile`；当前口径是 `packet_size / evidence_level / gate_cadence / repo_binding_policy` 属于实例级治理合同，supervisor 调整后必须回写实例态，而不是只挂在 `latest_supervisor_decision`
  - 再确认 `execution_context` 与 `repo_binding_policy` 没有混用；当前 `repo_bound` 只表示执行位置，不再自动等于显式 repo contract
  - 若涉及 asset/runtime 注入分叉，先核对 packet 是否以实例态 `flow_state.control_profile` 压过资产 definition 中的旧控制画像
  - 若涉及 Codex 执行根、仓库根 `AGENTS.md` 被误读、或 flow 是否该在 repo 内执行，先看 `execution_context`；当前口径是 `coding_flow=repo_bound`，非 `coding_flow` 默认 `isolated`
  - 再核对 receipt / `flow_exec_receipt` / `flow_definition.json` 是否已带 `execution_context + execution_workspace_root`
  - 若涉及长流恢复或 `/resume` 异常，补看 `doctor_policy`、实例 `bundle/doctor.md`、`bundle/skills/doctor/SKILL.md`，以及 `runtime.py` 是否会在重复 `resume/no-rollout`、session 绑定异常、重复 service fault 时自动拉起 `doctor`
  - 若涉及 flow 静态资产修复，先确认当前实例是否已经物化 `flow_definition.json + bundle/*`；不要把这类实例级修复重新退回模板或全局角色目录
  - 再看 `role_packs/<pack>/<role>.md` 与 `sources.json`；当前 role pack 只是前台 L1 prompt 资产，不是 L3 协议真源
  - 若排查 role handoff，优先看 `role_sessions.json`、`handoffs.jsonl`、`artifacts.json` 的 role visibility 字段，不要直接假设共享 thread 历史
  - 若改 supervisor/retry 语义，先核对当前是否已经有显式 `fix` turn、`issue_kind / followup_kind` 和 auto-fix 上限；当前只有 `issue_kind=agent_cli_fault + followup_kind=fix` 才能进入 `fix`，不要再把 supervisor 改成直接执行 repo 修复
  - 若目标是测试/排障执行面，优先看 `exec new` / `exec resume`，它们固定不进入 TUI 且 stdout 全 JSONL
  - 无子命令入口先检查 launcher / 向导，而不是只看 help 文案
  - 再检查 `cli_runner` 的 receipt / `thread_id` / fallback 边界
  - 若涉及 `exec resume` 恢复，先确认 `external_session.resume_durable` 与 `durable_resume_id` 是否成立；若 CLI 切换、重装或 `codex_home` 改变导致恢复不可信，当前口径是 Butler 透明 reseed，而不是强依赖旧 thread
  - 再检查 butler-flow 是否给当前 flow 准备了独立 `codex_home/`，避免直接吃全局 `~/.codex` 的 MCP state
  - 再检查 butler-flow 的 `disable_mcp_servers`；当前默认会 guard `stripe / supabase / vercel` 这类 OAuth 型远程 MCP，若显式配成 `[]` 才会关闭这层 override
  - 若用户手工 `Ctrl+C`，先检查 flow 是否被写成 `interrupted`，而不是残留 `running`
  - `project_loop` 卡在单 phase 时，先核对 `phase_attempt_count` 是否只统计 Codex 成功完成的尝试
  - 当前 CLI 升级已按 `04c` 落地：`system CLI entry + serializable event spine + operator TUI shell`
  - 当前还新增 `exec`：最后一行固定 `flow_exec_receipt`，退出码按 flow 终态收口
  - TTY 下优先核对是否正确进入 Textual launcher / attached run screen；若未进入，再检查 `requirements-cli.txt`、终端宽度与 `--plain`
- 若排查 TUI，优先看 `butler_main/products/butler_flow/tui/`、`butler_main/products/butler_flow/events.py` 与 `FlowRuntime` 的 `FlowUiEvent` 接线
  - 若讨论 Butler-flow Desktop/TUI 双轨、shared surface 抽取、Desktop 壳技术选型、Proma 复用边界或执行主计划，先按 `0402` 两份新文档确认：当前规划只以前台 `butler-flow` CLI、sidecars 与现役 TUI payload 为真源，不再引入 `campaign/orchestrator` 的 `mission / branch` 线；Desktop 壳优先吸收 Proma 的 `Electron + React + TypeScript + Jotai` 外壳与通用 UI 包装，但不直接搬 `Proma main/lib` 的 Agent 编排层
- 若目标已经进入 Butler Desktop 实作，先确认当前现役代码落点已经是 `butler_main/products/butler_flow/desktop/ + butler_main/products/butler_flow/desktop_bridge.py + butler_main/products/butler_flow/surface/`；renderer 只能经由 preload + IPC + bridge 访问 payload，不能直接读 raw sidecars；远程/无头环境下优先走手填 `Config Path Fallback`，不要把原生 file dialog 当唯一验证入口
  - 若这轮目标是 Desktop 前端升级或视觉收口，先读 `0409/01`；当前前台一级对象只保留 `Manager`，左侧应理解为 `New thread + Active / History` 的连续 thread rail，右侧应理解为统一的 mission conversation shell，`Runtime / Studio` 只作为同一主对话里的轻模式
  - `0409` 当前 renderer 的现役代码落点已进一步收口为 `desktop/src/renderer/App.tsx + components/mission-shell/MissionShell.tsx + lib/mission-shell.ts + state/queries/use-thread-workbench.ts`；旧 `WorkbenchShell / ManageCenterShell / FlowRail / DetailDrawer / SupervisorStream / WorkflowStrip` 已退役，不要继续在这些旧壳上叠改
  - 若这轮目标是“启动即用”，先看 `desktop/src/main/index.ts`、`desktop/src/main/ipc/register-flow-workbench-ipc.ts`、`desktop/src/preload/index.ts`、`desktop/src/shared/ipc.ts` 与 `desktop/src/renderer/App.tsx`；当前现役口径是启动时固定优先自动挂载仓库内 `butler_main/butler_bot_code/configs/butler_bot.json`，默认路径不可用时才退回手动 attach
  - 若这轮目标是 Desktop 下一条主线，优先做真实 workspace fixture、payload 一致性、runtime contract/receipt/recovery 摘要展示、artifact open / toast / preflight / settings 的最小闭环；不要先扩 watch/publish/packaging
  - 若这轮还涉及 manager-first continuity、linked history 错序或 supervisor 回跳异常，先看 `butler_main/products/butler_flow/surface/service.py -> thread_home_payload()`；现役合同要求同一 linked flow 的 history 固定成相邻的 `manager -> supervisor`，并由 `test_butler_flow_surface.py` 锁定回归
  - 若排查 Desktop 是否“已完成”，把验证拆成四层记录：Python bridge/surface 回归（至少 `test_butler_flow_surface.py`、`test_butler_flow_desktop_bridge.py`）、desktop `typecheck/build`、renderer `vitest`、Electron `Playwright` 点击回归；不要把源码编译通过误记成运行时已验证
- 若目标是当前 Desktop 的历史代码基线、`thread-home / manager-thread / supervisor-thread / agent-focus / template-team` 这套旧 renderer contract，先补读 [0405 Butler Flow Desktop 线程化工作台与 Manager-Supervisor 串联落地](../daily-upgrade/0405/01_butler-flow_desktop线程化工作台与manager-supervisor串联落地.md)；但当前产品壳真源已经升级为 `0409` 的 manager conversation shell，不要再把 `Supervisor / Templates / Agent focus` 当一级页面心智
  - 若这轮还涉及视觉壳层、bridge fallback、history 双 thread 合同或 manager/supervisor 上下文回跳，额外核对 0405 正文中的第二波补充：`thread-home` history 现役是 `manager + supervisor` 双 summary，renderer 不得再用 `flow_id` 猜 thread 身份
- 若跑 Desktop e2e，优先直接用 `cd butler_main/products/butler_flow/desktop && npm run test:e2e`；当前脚本会先 `build`，再优先使用现有 `DISPLAY`，无图形时自动尝试 `xvfb-run`
  - 若改模板启动或 managed flow materialization，先核对 `flow_definition.json` 是否与 `workflow_state.json` 同步、phase plan 是否仍为 ordered plan 而非任意 DAG
  - 最后补跑 `tools/butler-flow ... --help`、`butler-flow --help` 与 `python -m butler_main --help`
  - 若目标是系统级 CLI，再补跑 `./tools/install-butler-flow` 并确认 `command -v butler-flow`
  - 若开始实现 TUI，再补跑 `./.venv/bin/pip install -r requirements-cli.txt`，确认独立 CLI 依赖链可用
  - 并确认 `butler workflow/-workflow/codex-guard` 只返回迁移提示

## `system-layering`

- 额外必读：
  - [当前系统基线](./00_current_baseline.md)
  - [分层地图](./01_layer_map.md)
  - [真源矩阵](./03_truth_matrix.md)
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
  - [0327 Butler 系统分层与事件契约收口](../daily-upgrade/0327/03_Butler系统分层与事件契约收口.md)
- 默认代码目录：
  - `butler_main/platform/runtime/`（canonical alias）
  - `butler_main/compat/multi_agents_os/`（canonical alias）
  - `butler_main/products/campaign_orchestrator/orchestrator/`（canonical alias）
  - `butler_main/runtime_os/`
  - `butler_main/multi_agents_os/`
  - `butler_main/orchestrator/`
- 默认测试：
  - `test_runtime_os_namespace.py`
  - `test_runtime_os_root_package.py`
  - `test_agents_os_process_runtime_surface.py`
  - `test_orchestrator_workflow_ir.py`

## `feedback-feishu`

- 额外必读：
  - [功能地图](./02_feature_map.md)
  - [0327 后台任务固定输出区与严格验收收口](../daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)
  - [0329 后台任务双状态与前门弱化重构](../daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
  - [0326 当日总纲](../daily-upgrade/0326/00_当日总纲.md)
  - [0326 Harness 全系统稳定态运行梳理](../daily-upgrade/0326/03_Harness全系统稳定态运行梳理.md)
- 默认代码目录：
  - `butler_main/orchestrator/feedback_notifier.py`
  - `butler_main/chat/`
- 默认测试：
  - `test_orchestrator_feedback_notifier.py`
  - `test_chat_feishu_interaction.py`
  - `test_chat_feishu_replying.py`

## `visual-console`

- 额外必读：
  - [当前系统基线](./00_current_baseline.md)
  - [功能地图](./02_feature_map.md)
  - [真源矩阵](./03_truth_matrix.md)
  - [0330 后台任务操作面与多Agent编排控制台升级计划](../daily-upgrade/0330/01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md)
  - [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写（历史文件名保留草稿）](../daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)
  - [0326 可视化后台与前台画布 V1 实施方案](../daily-upgrade/0326/06_可视化后台与前台画布V1实施方案.md)
  - [0329 后台任务双状态与前门弱化重构](../daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
  - [0327 Skill Exposure Plane 与 Codex 消费边界](../daily-upgrade/0327/02_SkillExposurePlane与Codex消费边界.md)
  - [Visual Console API Contract v1](../runtime/Visual_Console_API_Contract_v1.md)
- 默认代码目录：
  - `butler_main/console/`
  - `butler_main/domains/campaign/`
  - `butler_main/orchestrator/interfaces/`
- 默认测试：
  - `test_console_services.py`
  - `test_console_server.py`
  - `test_orchestrator_campaign_dashboard.py`
  - `test_orchestrator_campaign_service.py`
- 默认动作：
  - 先确认当前目标是 V2 operator harness，而不再只是 V1 观察台
  - 新 campaign 主视图优先读取 `canonical_session_id / task_summary / latest_turn_receipt / latest_delivery_refs / harness_summary`
  - graph / board 默认按 `ledger -> turn -> delivery -> harness` 理解，不再默认套旧 `discover / implement / evaluate / iterate`
  - operator 主动作优先收口到 `pause / resume / abort / annotate_governance / force_recover_from_snapshot / append_feedback`
  - 旧 `force_transition / skip_to_step` 仅做 legacy/best-effort 兼容，不再写成主 UX 预期
  - 涉及 prompt / workflow / audit plane 时优先对照 0330 专题正文，但不要把高级 patch 面重新推回主视图中心
  - 不把 graph UI 反向变成 runtime 真源
  - 访问异常先区分“HTML 可达”与“静态资源可达”；至少复验 `/console/` 与 `/console/assets/*`
  - 收尾必须执行一次服务重启与状态复验

## `workflow-ir`

- 额外必读：
  - [真源矩阵](./03_truth_matrix.md)
  - [Butler Runtime 复用接入指南](../runtime/README.md)
  - [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
  - [0326 稳定 Harness 之后的下一阶段主线](../daily-upgrade/0326/04_稳定Harness之后的下一阶段主线_Anthropic长运行Harness吸收版.md)
- 默认代码目录：
  - `butler_main/orchestrator/workflow_ir.py`
  - `butler_main/orchestrator/workflow_vm.py`
  - `butler_main/runtime_os/process_runtime/workflow/`
- 默认测试：
  - `test_orchestrator_workflow_ir.py`
  - `test_orchestrator_workflow_vm.py`
  - `test_orchestrator_core.py`

## `agent-harness`

- 额外必读：
  - [当前系统基线](./00_current_baseline.md)
  - [分层地图](./01_layer_map.md)
  - [功能地图](./02_feature_map.md)
  - [真源矩阵](./03_truth_matrix.md)
  - [0330 Agent Harness 全景研究与 Butler 主线开发指南](../daily-upgrade/0330/02_AgentHarness全景研究与Butler主线开发指南.md)
  - [0330/02R 外部Harness映射与能力吸收开发计划](../daily-upgrade/0330/02R_外部Harness映射与能力吸收开发计划.md)
  - 按主层级命中目标子计划：
    - `L1` 读 [02A_runtime层详情.md](../daily-upgrade/0330/02A_runtime层详情.md)
    - `L3` 读 [02B_协议编排与能力包开发计划.md](../daily-upgrade/0330/02B_协议编排与能力包开发计划.md)
    - `L4` 读 [02C_会话协作与事件模型开发计划.md](../daily-upgrade/0330/02C_会话协作与事件模型开发计划.md)
    - `L2` 读 [02D_持久化恢复与产物环境开发计划.md](../daily-upgrade/0330/02D_持久化恢复与产物环境开发计划.md)
    - `Product Surface` 读 [02F_前门与Operator产品壳开发计划.md](../daily-upgrade/0330/02F_前门与Operator产品壳开发计划.md)
    - `Governance / Observability` 读 [02G_治理观测与验收闭环开发计划.md](../daily-upgrade/0330/02G_治理观测与验收闭环开发计划.md)
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
- 默认代码目录：
  - `butler_main/orchestrator/framework_*`
  - `butler_main/runtime_os/`
  - `butler_main/agents_os/`
  - `butler_main/multi_agents_os/`
  - `butler_main/console/`
  - `butler_main/chat/`
- 默认测试：
  - `test_orchestrator_framework_catalog.py`
  - `test_orchestrator_framework_mapping.py`
  - `test_orchestrator_framework_compiler.py`
  - `test_agents_os_runtime.py`
  - `test_multi_agents_os_collaboration.py`
  - `test_orchestrator_workflow_ir.py`
  - `test_console_server.py`
- 默认动作：
  - 先读 `02R`，再命中具体层级子计划
  - 不把 vendor DSL、UI 节点名或 API 表层对象名回灌 Butler 真源
  - 任何裁决变化都同步回写 `0330/02`、当天 `00_当日总纲.md`、`docs/README.md`、`03_truth_matrix.md`、`04_change_packets.md`

## `docs-only`

- 额外必读：
  - [仓库根 README](../../README.md)
  - [Project Map 入口](./README.md)
  - [功能地图](./02_feature_map.md)
  - [真源矩阵](./03_truth_matrix.md)
  - [0409 Root `AGENTS.md` 轻量化重写与本地 agent 协议收口](../daily-upgrade/0409/02_root_AGENTS轻量化重写与本地agent协议收口.md)
  - [0402 Vibecoding Agent 默认收尾动作与 `vibe-close` 收口](../daily-upgrade/0402/09_vibecoding_agent默认收尾动作与vibe_close收口.md)
  - [0331 根目录归档整理收口](../daily-upgrade/0331/05_根目录归档整理收口.md)
  - [0403 仓库级重构实施稿：三产品 / Platform / Repo Governance](../daily-upgrade/0403/04_仓库级重构实施稿_三产品_platform_repo治理.md)
  - [仓库级重构远景规划（产品 / Platform / Repo Governance 版）](../远景草稿/仓库级重构.md)
  - [文档生命周期](./05_doc_lifecycle.md)
  - [concepts/README.md](../concepts/README.md)
- 若目标涉及根 `AGENTS.md`、本地 agent 协议、`vibe-close` 收尾或 repo contract 误读，补读：
  - [0403 Butler Flow Codex 执行根隔离与 `repo_bound` 裁决](../daily-upgrade/0403/01_butler-flow_Codex执行根隔离与repo_bound裁决.md)
  - [0403 Butler Flow supervisor 控制画像与 agents-flow 治理升级](../daily-upgrade/0403/02_butler-flow_supervisor控制画像与agents-flow治理升级.md)
- 默认检查：
  - 当前入口是否仍指向最新日期
  - `AGENTS.md` 是否仍保持“本地 agent 轻量协议”，而不是重新膨胀成长手册
  - `AGENTS.md` 是否继续把深功能真源指向 `project-map/` 与 `daily-upgrade/`
  - `AGENTS.md` 是否明确 repo contract 需要显式绑定，而不是暗示 ambient authority
  - `AGENTS.md` 的日更读取规则是否带 fallback，而不是假设当天 `00_当日总纲.md` 必然存在
  - 历史文档是否被错误列为现役
  - 研究/脑暴材料是否已收敛到 `docs/每日头脑风暴/`，而不是继续写回旧 `docs/每日/`
  - 根目录说明是否与实际根目录保留项一致
  - `runtime_os/`、`tools/` 是否被错误写成可直接清理对象
  - `AGENTS.md` 是否仍把 `./tools/vibe-close` 作为 vibecoding 默认收尾动作
  - `vibe-close analyze/apply` 的 JSON 字段与当前文档协议是否一致
  - 远景稿与实施稿是否明确区分“当前现役事实”和“后续波次候选”
  - 仓库重构叙事是否已明确拆成三产品、共享 Platform 与 repo governance plane
  - 根 `README.md` 是否仍给 GitHub / ChatGPT 网页端读者清晰指向 `docs/` 与 `project-map/`
  - 功能条目是否能一跳命中代码目录和测试入口
  - 近期新增能力是否已回写到 `project-map/`
  - 跨机器开发说明是否仍能一跳命中 `.env.example`、`.codex/config.template.toml` 与 bootstrap 文档
  - runtime artifact / private overlay 的 git 边界是否仍清晰，避免把 `instances/`、`manage_sessions/`、`hot recent_memory/` 或 `.codex/config.toml` 再次纳入版本库

## `system-audit-upgrade`

- 额外必读：
  - [真源矩阵](./03_truth_matrix.md)
  - [系统级审计与并行升级协议](./06_system_audit_and_upgrade_loop.md)
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [0326 Harness 全系统稳定态运行梳理](../daily-upgrade/0326/03_Harness全系统稳定态运行梳理.md)
  - [0326 稳定 Harness 之后的下一阶段主线](../daily-upgrade/0326/04_稳定Harness之后的下一阶段主线_Anthropic长运行Harness吸收版.md)
  - [0326 长任务主线系统审计与并行升级执行方案](../daily-upgrade/0326/05_长任务主线系统审计与并行升级执行方案.md)
  - [0329 后台任务双状态与前门弱化重构](../daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
- 默认代码目录：
  - `butler_main/chat/`
  - `butler_main/orchestrator/`
  - `butler_main/runtime_os/process_runtime/`
  - `butler_main/butler_bot_code/run/orchestrator/`
  - `butler_main/chat/data/hot/recent_memory/`
- 默认测试：
  - `test_chat_campaign_negotiation.py`
  - `test_chat_long_task_frontdoor_regression.py`
  - `test_orchestrator_campaign_service.py`
  - `test_orchestrator_feedback_notifier.py`
  - `test_orchestrator_campaign_observe.py`
  - `test_request_intake_service.py`
- 默认动作：
  - 先建链路矩阵
  - 第一波按 routing / control / feedback / docs 并行
  - 中途强制 replan
  - 第二波再按问题束并行
  - 最后回写当日真源、project-map、acceptance 证据
  - 收尾补一轮实际重启与 `status` 复验
