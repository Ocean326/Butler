# 功能地图

更新时间：2026-04-03  
状态：现役  
用途：按功能命中当前真源、代码目录、改前读包和测试入口

## chat / frontdoor / console 产品面

- 用户价值：让 chat/frontdoor 在一次前门编译里同时决定会话续接、模式、前门能力和 CLI lane；长任务先协商、再后台启动，并在产品面以自然语言 `task_summary + latest_turn_receipt + harness` 稳定查询与展示
- 主层级：`Product Surface（产品表面层）`
- 次层级：`Domain & Control Plane（领域与控制平面）`
- 关键代码目录：`butler_main/chat/`、`butler_main/console/`、`butler_main/orchestrator/interfaces/`
- 当前真源文档：
  - [当前系统基线](./00_current_baseline.md)
  - [0327 后台任务固定输出区与严格验收收口](../daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)
  - [0329 后台任务双状态与前门弱化重构](../daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
  - [0329 Chat 显式模式与 Project 循环收口](../daily-upgrade/0329/02_Chat显式模式与Project循环收口.md)
  - [0330 Chat 默认厚 Prompt 分层治理真源](../daily-upgrade/0330/04_Chat默认厚Prompt分层治理真源.md)
  - [0402 Chat Router 选会话能力升级回写](../daily-upgrade/0402/01_chat_router选会话能力升级回写.md)
  - [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写（历史文件名保留草稿）](../daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)
  - [Visual Console API Contract v1](../runtime/Visual_Console_API_Contract_v1.md)
- 改前读包：`frontdoor`
- 验收测试：
  - `test_chat_campaign_negotiation.py`
  - `test_chat_long_task_frontdoor_regression.py`
  - `test_talk_mainline_service.py`
  - `test_chat_router_frontdoor.py`
  - `test_chat_engine_model_controls.py`
  - `test_console_server.py`
- 历史别名：`heartbeat 后台入口`、`旧长任务 chat 接管`

## campaign / mission / orchestrator 控制面

- 用户价值：让长任务以 `campaign 宏账本 + workflow_session 内环 + agent turn receipt` 形式持续推进、查询、恢复和验收
- 主层级：`Domain & Control Plane（领域与控制平面）`
- 次层级：`L4 Multi-Agent Session Runtime（多 Agent 会话运行时）`、`L2 Durability Substrate（持久化基座）`
- 关键代码目录：`butler_main/orchestrator/`、`butler_main/domains/campaign/`
- 当前真源文档：
  - [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写（历史文件名保留草稿）](../daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)
  - [0327 Butler 系统分层与事件契约收口](../daily-upgrade/0327/03_Butler系统分层与事件契约收口.md)
  - [0327 后台任务固定输出区与严格验收收口](../daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)
  - [0329 后台任务双状态与前门弱化重构](../daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
- 改前读包：`campaign-control-plane`
- 验收测试：
  - `test_orchestrator_campaign_service.py`
  - `test_orchestrator_runner.py`
  - `test_orchestrator_campaign_observe.py`
- 历史别名：`后台任务总控`、`旧 mission manager`

## projection / feedback / observability

- 用户价值：让 query、console、Feishu 和控制面读取同一份稳定投影，同时不把 debug trace 混成产品态状态
- 主层级：`Product Surface（产品表面层）`
- 次层级：`Domain & Control Plane（领域与控制平面）`
- 关键代码目录：`butler_main/orchestrator/interfaces/query_service.py`、`butler_main/orchestrator/feedback_notifier.py`、`butler_main/chat/task_query.py`
- 当前真源文档：
  - [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写（历史文件名保留草稿）](../daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [0327 后台任务固定输出区与严格验收收口](../daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)
  - [0329 后台任务双状态与前门弱化重构](../daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
- 改前读包：`feedback-feishu`
- 验收测试：
  - `test_orchestrator_feedback_notifier.py`
  - `test_chat_feishu_interaction.py`
  - `test_chat_feishu_replying.py`
- 历史别名：`Webhook 播报`、`observe`

## multi-agent session runtime

- 用户价值：让 session、artifact、mailbox、handoff、join、event log 有单独运行态边界
- 主层级：`L4 Multi-Agent Session Runtime（多 Agent 会话运行时）`
- 次层级：`L3 Multi-Agent Protocol（多 Agent 协议层）`
- 关键代码目录：`butler_main/runtime_os/multi_agent_runtime/`、`butler_main/runtime_os/process_runtime/session/`、`butler_main/multi_agents_os/session/`
- 当前真源文档：
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
- 改前读包：`runtime-contract`
- 验收测试：
  - `test_runtime_os_namespace.py`
  - `test_agents_os_process_runtime_surface.py`
  - `test_orchestrator_workflow_ir.py`
- 历史别名：`multi_agents_os 真主体`

## multi-agent protocol / template / contract

- 用户价值：让 workflow template、role spec、handoff/acceptance contract 与 session instance 脱钩
- 主层级：`L3 Multi-Agent Protocol（多 Agent 协议层）`
- 次层级：`Domain & Control Plane（领域与控制平面）`
- 关键代码目录：`butler_main/runtime_os/multi_agent_protocols/`、`butler_main/runtime_os/process_runtime/templates/`
- 当前真源文档：
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
- 改前读包：`runtime-contract`
- 验收测试：
  - `test_runtime_os_namespace.py`
  - `test_orchestrator_workflow_ir.py`
- 历史别名：`workflow protocol = session runtime`

## durability substrate / workflow ir / writeback

- 用户价值：保证 checkpoint、writeback、recovery 和 runtime linkage 稳定
- 主层级：`L2 Durability Substrate（持久化基座）`
- 次层级：`Domain & Control Plane（领域与控制平面）`
- 关键代码目录：`butler_main/runtime_os/durability_substrate/`、`butler_main/runtime_os/process_runtime/engine/`、`butler_main/orchestrator/workflow_ir.py`
- 当前真源文档：
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
- 改前读包：`runtime-contract`
- 验收测试：
  - `test_orchestrator_workflow_ir.py`
  - `test_orchestrator_workflow_vm.py`
  - `test_runtime_module_layout.py`
- 历史别名：`process runtime / writeback contract`、`旧 runtime substrate`

## skill exposure / Codex skill injection

- 用户价值：让 skill 真源、collection 暴露和 provider 注入方式长期分离
- 主层级：`Domain & Control Plane（领域与控制平面）`
- 次层级：`L1 Agent Execution Runtime（Agent 执行运行时）`
- 关键代码目录：`butler_main/sources/skills/`、`butler_main/agents_os/skills/`、`butler_main/chat/`、`butler_main/domains/campaign/`
- 当前真源文档：
  - [0327 Skill Exposure Plane 与 Codex 消费边界](../daily-upgrade/0327/02_SkillExposurePlane与Codex消费边界.md)
  - [当前系统基线](./00_current_baseline.md)
- 改前读包：`runtime-contract`
- 验收测试：
  - `test_skill_exposure.py`
  - `test_talk_runtime_service.py`
  - `test_campaign_domain_runtime.py`
- 历史别名：`skills shortlist 注入`、`Codex local skill 共享`

## foreground butler-flow CLI / launcher / legacy aliases

- 用户价值：让用户在本地前台直接用 `butler-flow` 以 `new/resume/exec` 跑可恢复的 Codex workflow；`new` 必经 setup picker；默认 home 是 `workspace`；单 flow 页现役为 `flow 主要信息头 + supervisor 结构化流 + workflow 实时流 + inspector`；`simple` 单 session，`medium` 为 role-bound session；当前 `execution_context` 只表达执行位置：`coding_flow=repo_bound`，其他 role pack 默认 `isolated`，隔离执行根落在 `~/.butler/codex_exec_roots/<workflow_id>/`；长流治理当前收口为实例级 `control_profile`，由 manager 设计默认值、supervisor 运行时可调并回写实例态；repo contract 改成显式绑定，不再把仓库根 `AGENTS.md` 当 ambient authority；`/manage` 只管理 `builtin + template` shared assets，但现已升级为 transcript-first manage center，支持 `$asset` mention、manager staged lifecycle、shared asset bundle 与 source-asset materialization；manager chat 当前还会持久化 `manage_session / draft / pending_action`，只在纯确认时提交，并通过 `draft_payload -> manage_flow()` 落盘；shared/instance static asset 当前补入 `supervisor_profile / run_brief / source_bindings`
- 主层级：`L1 Agent Execution Runtime（Agent 执行运行时）`
- 次层级：`L2 Durability Substrate（持久化基座）`
- 关键代码目录：`butler_main/butler_flow/`、`butler_main/runtime_os/agent_runtime/`、`tools/butler-flow`、`butler_main/butler_cli.py`
- 当前真源文档：
  - [当前系统基线](./00_current_baseline.md)
  - [0403 当日总纲](../daily-upgrade/0403/00_当日总纲.md)
  - [0403 Butler Flow Codex 执行根隔离与 `repo_bound` 裁决](../daily-upgrade/0403/01_butler-flow_Codex执行根隔离与repo_bound裁决.md)
  - [0403 Butler Flow supervisor 控制画像与 agents-flow 治理升级](../daily-upgrade/0403/02_butler-flow_supervisor控制画像与agents-flow治理升级.md)
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [0401 当日总纲](../daily-upgrade/0401/00_当日总纲.md)
  - [0402 当日总纲](../daily-upgrade/0402/00_当日总纲.md)
  - [0402 Butler Flow Manage Center 资产中心升级与会话式交互落地](../daily-upgrade/0402/02_butler-flow_manage-center资产中心升级与会话式交互落地.md)
  - [0401 前台 Butler Flow 入口收口与 New 向导 V1](../daily-upgrade/0401/01_前台ButlerFlow入口收口与New向导V1.md)
  - [0401 Claude Code 对 Butler Flow 工作台化升级与 TUI 信息架构计划](../daily-upgrade/0401/02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)
  - [0401 Butler Flow workspace/manage 分工升级计划](../daily-upgrade/0401/04_butler-flow工作流分级与FlowsStudio升级草稿.md)
  - [0331 前台 Workflow Shell 收口](../daily-upgrade/0331/02_前台WorkflowShell收口.md)
  - [0331 前台 butler-flow 角色运行时与 role-session 绑定实施回写](../daily-upgrade/0331/06_前台butler-flow角色运行时与role-session绑定计划.md)
  - [0331 04c-butler-flow完备升级与视觉设计计划](../daily-upgrade/0331/04c_butler-flow完备升级与视觉设计计划.md)
  - [0331 Agent 监管 Codex 实践（exec 与 resume）](../daily-upgrade/0331/01_Agent监管Codex实践_exec与resume.md)
  - [0329 Codex 主备默认自动切换](../daily-upgrade/0329/01_Codex主备默认自动切换.md)
  - [0329 Chat 显式模式与 Project 循环收口](../daily-upgrade/0329/02_Chat显式模式与Project循环收口.md)
- 改前读包：`butler-flow`
- 验收测试：
  - `test_butler_flow.py`
  - `test_butler_cli.py`
  - `test_chat_cli_runner.py`
  - `test_agents_os_wave1.py`
  - `test_butler_flow_tui_controller.py`
  - `test_butler_flow_tui_app.py`
  - `test_codex_provider_failover.py`
  - `test_codex_cursor_switchover.py`
  - `test_runtime_os_namespace.py`
- 历史别名：`workflow shell`、`butler workflow`、`butler -workflow`、`codex-guard free`、`codex-guard resume`、`run/exec run`（兼容别名）、`butler-flow flows`（公开入口已隐藏）

## agent harness absorption / framework mapping / operator-aware runtime design

- 用户价值：让 Butler 吸收外部 harness 的稳定能力，同时把 vendor 术语压回内部 target/package/policy，而不是把外部框架直接写成真源
- 主层级：`Domain & Control Plane（领域与控制平面）`
- 次层级：`Product Surface（产品表面层）`、`L4 Multi-Agent Session Runtime（多 Agent 会话运行时）`、`L3 Multi-Agent Protocol（多 Agent 协议层）`、`L2 Durability Substrate（持久化基座）`、`L1 Agent Execution Runtime（Agent 执行运行时）`
- 关键代码目录：`butler_main/orchestrator/framework_*`、`butler_main/runtime_os/`、`butler_main/agents_os/`、`butler_main/multi_agents_os/`、`butler_main/console/`、`butler_main/chat/`
- 当前真源文档：
  - [0330 Agent Harness 全景研究与 Butler 主线开发指南](../daily-upgrade/0330/02_AgentHarness全景研究与Butler主线开发指南.md)
  - [0330/02R 外部Harness映射与能力吸收开发计划](../daily-upgrade/0330/02R_外部Harness映射与能力吸收开发计划.md)
  - [0330/02A Runtime 层详情](../daily-upgrade/0330/02A_runtime层详情.md)
  - [0330/02F 前门与Operator产品壳开发计划](../daily-upgrade/0330/02F_前门与Operator产品壳开发计划.md)
  - [0330/02G 治理观测与验收闭环开发计划](../daily-upgrade/0330/02G_治理观测与验收闭环开发计划.md)
- 改前读包：`agent-harness`
- 验收测试：
  - `test_orchestrator_framework_catalog.py`
  - `test_orchestrator_framework_mapping.py`
  - `test_orchestrator_framework_compiler.py`
  - `test_agents_os_runtime.py`
  - `test_multi_agents_os_collaboration.py`
  - `test_orchestrator_workflow_ir.py`
  - `test_console_server.py`
- 历史别名：`外部框架吸收`、`framework profile / mapping spec`、`super agent harness`

## docs only / 导航与治理

- 用户价值：让 agent 改动前先命中正确文档，不靠全文扫库
- 主层级：文档治理
- 次层级：跨层
- 关键代码目录：`AGENTS.md`、`tools/vibe-close`、`tools/README.md`
- 当前真源文档：
  - [Project Map 入口](./README.md)
  - [真源矩阵](./03_truth_matrix.md)
  - [0402 Vibecoding Agent 默认收尾动作与 `vibe-close` 收口](../daily-upgrade/0402/09_vibecoding_agent默认收尾动作与vibe_close收口.md)
  - [0402 GitHub / ChatGPT 网页端阅读入口增强](../daily-upgrade/0402/10_github_chatgpt网页端阅读入口增强.md)
  - [0331 根目录归档整理收口](../daily-upgrade/0331/05_根目录归档整理收口.md)
  - [仓库根 README](../../README.md)
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
- 改前读包：`docs-only`
- 验收测试：人工抽查 5 个常见功能词，必须能一跳命中主文档和主代码目录
- 历史别名：`概念文档总包`、`按时间翻 daily-upgrade`
