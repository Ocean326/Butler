# 改前读包

更新时间：2026-04-02  
状态：现役  
用途：把常见改动压成固定最小读包，避免 agent 自由扩散式读库

## 通用基础包

所有改动默认先读：

1. 仓库根 `README.md`
2. [docs/README.md](../README.md)
3. 当天 `docs/daily-upgrade/<MMDD>/00_当日总纲.md`

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
  - `butler_main/chat/`
  - `butler_main/orchestrator/interfaces/`
  - `butler_main/agents_os/execution/cli_runner.py`
- 默认测试：
  - `test_chat_campaign_negotiation.py`
  - `test_chat_long_task_frontdoor_regression.py`
  - `test_request_intake_service.py`
  - `test_talk_mainline_service.py`
  - `test_chat_router_frontdoor.py`
  - `test_talk_runtime_service.py`
  - `test_chat_recent_memory_runtime.py`
  - `test_conversation_turn_engine.py`
  - `test_chat_runtime_request_override_runtime.py`
- 临时熔断附加检查：
  - 先看 `butler_main/chat/feature_switches.py`
  - 再看 `butler_main/butler_bot_code/configs/butler_bot.json -> features.chat_frontdoor_tasks_enabled`
  - 回归优先补 `test_chat_router_frontdoor.py`、`test_talk_mainline_service.py`、`test_agent_soul_prompt.py`
  - 模式收口附加检查：
  - 先看 `butler_main/chat/frontdoor_modes.py` 的 slash 契约
  - 再看 `butler_main/chat/router_plan.py` 与 `butler_main/chat/routing.py` 的 `RouterCompilePlan`，确认当前 `main_mode / role_id / injection_tier / capability_policy` 是否仍是前台唯一编译真源
  - 若涉及“续接当前主线还是重开新题”，先看 `butler_main/chat/session_selection.py`、`butler_main/chat/mainline.py` 与 `butler_main/chat/memory_runtime/recent_turn_store.py`，确认 `chat_session_id` 是否已在当前 `session_scope_id` 内正确 bootstrap、写回、过滤 recent
  - 再看 `butler_main/chat/session_modes.py` 的 sticky state、recent 配额与 `project_artifact`
  - 再看 `butler_main/chat/mainline.py` 和 `butler_main/chat/prompting.py` 是否仍把 `/pure` 当成功能路由，而不是厚度 overlay
  - 改默认厚 prompt 块顺序、门控或 session selection 指示块时，对照 [0330 Chat 默认厚 Prompt 分层治理真源](../daily-upgrade/0330/04_Chat默认厚Prompt分层治理真源.md) 与 [0402 Chat Router 选会话能力升级回写](../daily-upgrade/0402/01_chat_router选会话能力升级回写.md) 同步更新文档
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
  - `butler_main/orchestrator/`
  - `butler_main/domains/campaign/`
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
  - [0401 当日总纲](../daily-upgrade/0401/00_当日总纲.md)
  - [0402 当日总纲](../daily-upgrade/0402/00_当日总纲.md)
  - [0402 Butler Flow Manage Center 资产中心升级与会话式交互落地](../daily-upgrade/0402/02_butler-flow_manage-center资产中心升级与会话式交互落地.md)
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
  - `butler_main/butler_flow/`
  - `butler_main/butler_flow/role_packs/`
  - `butler_main/__main__.py`
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
- TUI 信息架构附加检查：
  - 先确认当前实现是否已是 `workspace + single flow single-column dual-stream console + /manage + /settings`，并注意 `/history` `/flows` 都已经退成兼容语义，不要再把它们写成产品级主入口
  - 再看 `butler_main/butler_flow/tui/controller.py` 的 payload 是否已抽象成 `workspace / single_flow.navigator_summary / single_flow.supervisor_view / single_flow.workflow_view / single_flow.inspector` 这些现役投影；`operator_rail_payload / role_strip_payload` 只应作为兼容层
  - 若做本轮升级，主屏常驻信息以 `0401/02` 为准：`workspace navigator + default supervisor stream + Shift+Tab -> workflow stream`
  - 当前 `workspace` 左栏应是 instance runtime list，右栏应是 runtime preview / timeline；如保留 `/history` 语义，也只承接 archive/recovery，不回到主导航职责
  - 当前 `/manage` 已收口为 shared asset center，只显示 `builtin + template`；`/flows` 只保留兼容别名，free 设计链路只应在 setup 内部通过 `/manage template:new ...` 进入
  - 当前 `/manage` 主视图必须是 transcript-first shell，而不是栏式资产卡片；底部输入框是主入口，支持 `$template:<id>` / `$builtin:<id>` mention 与自然语言管理意图
  - 当前纯文本路由固定为：`manage -> manager chat`、`flow -> supervisor queue`、`history -> reject`
  - 若改 `/manage` 输入协议，先看 `butler_main/butler_flow/tui/manage_interaction.py` 与 `tui/app.py` 的 bare target/`$target` 解析、mention picker 7 项窗口、manager queue/session 续接；不要再把 manager chat 误接回 `manage_flow()` 的 builtin edit 分支
  - 若涉及 builtin 修改，必须核对当前是否仍要求显式 `clone` 或 `edit`，不要回退到隐式原地修改
  - 若涉及静态资产，补看 shared JSON 是否带有 `asset_state / lineage / instance_defaults / review_checklist / bundle_manifest`
  - 若涉及 runtime 注入，补看 instance `flow_definition.json` 是否已写入 `source_asset_key / source_asset_kind / source_asset_version`，以及 bundle 中 `supervisor.md + derived/supervisor_knowledge.json` 是否仍由 compiler/runtime 混合注入
  - 若涉及 `approval_state / judge / operator receipt / runtime events`，先核对它们是进入 transcript、rail 还是 detail，不要继续散落在 `/status`、`actions.jsonl` 和 raw timeline 之间
  - 若涉及 flow 管理，补看 repo-local `butler_main/butler_bot_code/assets/flows/{builtin,templates,instances}` 是否仍是唯一存储树；其中 `/manage` 只管 `builtin + template`，`instances` 只是 runtime/兼容布局
  - `test_codex_provider_failover.py`
  - `test_codex_cursor_switchover.py`
  - `test_runtime_os_namespace.py`
- 默认动作：
  - 先确认目标是前台 `butler-flow` CLI，而不是后台 `campaign/orchestrator`
  - 入口以 `new/resume/exec` 为主；`run/exec run` 仅是兼容别名
  - TTY 下 `new` 固定进入 setup picker；`--plain` 表示走 plain 向导，不是跳过向导
  - `workspace` / single flow 负责 instance runtime；`/manage` 只负责 `builtin + template` shared assets；`/list` 与 `/manage` 同义；`/flows` 仅是迁移提示
  - 若改 `/manage`，优先检查 `build_manage_payload()`、`manage_flow()`、`tui/app.py` 的 transcript-first shell 与 `$asset` suggester，而不是回退到 `flows-list + flows-detail` 的卡片心智
  - `free` 设计链路固定是“setup -> /manage template:new -> template:<id> -> launch instance”，不要再把它写回 `/flows` 设计页
  - 若涉及角色运行时，先确认 `execution_mode` 与 `session_strategy`；当前口径是 `simple=shared`、`medium=role_bound`、`complex=per_activation(预留合同)`
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
  - 若排查 TUI，优先看 `butler_main/butler_flow/tui/`、`events.py` 与 `FlowRuntime` 的 `FlowUiEvent` 接线
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
  - [0331 根目录归档整理收口](../daily-upgrade/0331/05_根目录归档整理收口.md)
  - [文档生命周期](./05_doc_lifecycle.md)
  - [concepts/README.md](../concepts/README.md)
- 默认检查：
  - 当前入口是否仍指向最新日期
  - 历史文档是否被错误列为现役
  - 根目录说明是否与实际根目录保留项一致
  - `runtime_os/`、`tools/` 是否被错误写成可直接清理对象
  - 功能条目是否能一跳命中代码目录和测试入口
  - 近期新增能力是否已回写到 `project-map/`

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
