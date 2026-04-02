# 分层地图

更新时间：2026-03-27  
状态：现役  
用途：先按层级确定改动的默认阅读入口、代码目录和测试面

## Product Surface（产品表面层）

- 职责：用户入口、查询、反馈、展示 projection、触发受控动作
- 主目录：`butler_main/chat/`、`butler_main/console/`
- 典型入口：`chat/mainline.py`、`chat/task_query.py`、`console/api/`
- 必读文档：
  - [当前系统基线](./00_current_baseline.md)
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [Visual Console API Contract v1](../runtime/Visual_Console_API_Contract_v1.md)
- 默认测试：
  - `test_chat_campaign_negotiation.py`
  - `test_chat_long_task_frontdoor_regression.py`
  - `test_chat_router_frontdoor.py`
  - `test_console_server.py`
- 不要再用的旧术语：`heartbeat 入口`、`guardian 前门`

## Domain & Control Plane（领域与控制平面）

- 职责：mission、campaign、orchestrator、template selection、verdict commit、projection assembly
- 主目录：`butler_main/orchestrator/`、`butler_main/domains/campaign/`
- 典型入口：`mission_orchestrator.py`、`campaign_service.py`、`query_service.py`、`runner.py`
- 必读文档：
  - [当前系统基线](./00_current_baseline.md)
  - [0327 Butler 系统分层与事件契约收口](../daily-upgrade/0327/03_Butler系统分层与事件契约收口.md)
  - [0327 后台任务固定输出区与严格验收收口](../daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)
- 默认测试：
  - `test_orchestrator_core.py`
  - `test_orchestrator_campaign_service.py`
  - `test_orchestrator_runner.py`
  - `test_orchestrator_campaign_observe.py`
- 不要再用的旧术语：`heartbeat manager`、`旧后台总控`

## L4 Multi-Agent Session Runtime（多 Agent 会话运行时）

- 职责：workflow session、shared state、artifact registry、mailbox、handoff、join、session event log
- 主目录：`butler_main/runtime_os/multi_agent_runtime/`、`butler_main/runtime_os/process_runtime/session/`
- 兼容目录：`butler_main/multi_agents_os/session/`
- 典型入口：`runtime_os.multi_agent_runtime`、`session/workflow_session.py`、`session/event_log.py`
- 必读文档：
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
- 默认测试：
  - `test_runtime_os_namespace.py`
  - `test_agents_os_process_runtime_surface.py`
  - `test_orchestrator_workflow_ir.py`
- 不要再用的旧术语：`multi_agents_os 真主体`

## L3 Multi-Agent Protocol（多 Agent 协议层）

- 职责：workflow template、role spec、contract spec、handoff/join/evidence/acceptance contract
- 主目录：`butler_main/runtime_os/multi_agent_protocols/`、`butler_main/runtime_os/process_runtime/templates/`
- 兼容目录：`butler_main/multi_agents_os/templates/`
- 典型入口：`runtime_os.multi_agent_protocols`、`templates/workflow_template.py`
- 必读文档：
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
- 默认测试：
  - `test_runtime_os_namespace.py`
  - `test_orchestrator_workflow_ir.py`
- 不要再用的旧术语：`multi-agent protocol = session state`

## L2 Durability Substrate（持久化基座）

- 职责：checkpoint、writeback、recovery、durable linkage、durability receipt
- 主目录：`butler_main/runtime_os/durability_substrate/`、`butler_main/runtime_os/process_runtime/engine/`
- 兼容目录：`butler_main/runtime_os/process_runtime/governance/`
- 典型入口：`runtime_os.durability_substrate`、`engine/session_support.py`
- 必读文档：
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
  - [Workflow IR 正式口径](../runtime/WORKFLOW_IR.md)
- 默认测试：
  - `test_runtime_os_namespace.py`
  - `test_orchestrator_workflow_vm.py`
  - `test_orchestrator_workflow_ir.py`
- 不要再用的旧术语：`process substrate`

## L1 Agent Execution Runtime（Agent 执行运行时）

- 职责：provider/CLI-native 执行适配、execution fact、单次 run 语义
- 主目录：`butler_main/runtime_os/agent_runtime/`
- 兼容目录：`butler_main/agents_os/`
- 典型入口：`runtime_os.agent_runtime`、provider adapter、CLI runner
- 必读文档：
  - [当前系统基线](./00_current_baseline.md)
  - [系统分层与事件契约](../runtime/System_Layering_and_Event_Contracts.md)
- 默认测试：
  - `test_runtime_os_root_package.py`
  - `test_runtime_os_namespace.py`
  - `test_agents_os_process_runtime_surface.py`
- 不要再用的旧术语：`自造 agent 内核`

## 兼容期说明

- `agents_os/`、`multi_agents_os/` 仍是兼容期核心目录
- 新改动优先按 `runtime_os.agent_runtime / durability_substrate / multi_agent_protocols / multi_agent_runtime` 定位
- `runtime_os.process_runtime` 保留聚合别名，只用于兼容迁移
- 如果任务描述出现旧术语，先去 [功能地图](./02_feature_map.md) 做映射，再读代码
