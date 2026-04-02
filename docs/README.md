# Butler Docs

`docs/` 是 Butler 的唯一正式文档入口。  
从 2026-03-26 起，agent 改动前的当前导航层统一收口到 [`project-map/`](./project-map/README.md)。

## 目录结构

- `project-map/`
  - 当前导航层、真源矩阵、改前读包
- `runtime/`
  - 稳定合同、复用接入、Workflow IR 正式口径
- `concepts/`
  - 长期原则、仍有效概念、接入说明
- `concepts/history/`
  - 历史设计稿、旧术语快照、退役方案
- `daily-upgrade/`
  - 按日期归档的阶段性改动、现状、计划、排查记录
- `tools/`
  - 文档辅助脚本

## 当前入口

1. [Project Map 入口](./project-map/README.md)
2. [当前系统基线](./project-map/00_current_baseline.md)
3. [分层地图](./project-map/01_layer_map.md)
4. [功能地图](./project-map/02_feature_map.md)
5. [真源矩阵](./project-map/03_truth_matrix.md)
6. [0402 当日总纲](./daily-upgrade/0402/00_当日总纲.md)
7. [0402 Chat Router 选会话能力升级回写](./daily-upgrade/0402/01_chat_router选会话能力升级回写.md)
8. [0402 Butler Flow Manage Center 资产中心升级与会话式交互落地](./daily-upgrade/0402/02_butler-flow_manage-center资产中心升级与会话式交互落地.md)
9. [0402 Hermes Agent 专题：Butler Flow 详细参考学习资料](./daily-upgrade/0402/03_HermesAgent专题_ButlerFlow详细参考学习资料.md)
10. [0402 Hermes Agent 专题：Butler Flow 启发式资料](./daily-upgrade/0402/04_HermesAgent专题_ButlerFlow启发式资料.md)
11. [0402 Hermes Agent 专题：Chat 详细参考学习资料](./daily-upgrade/0402/05_HermesAgent专题_Chat详细参考学习资料.md)
12. [0402 Hermes Agent 专题：Chat 启发式资料](./daily-upgrade/0402/06_HermesAgent专题_Chat启发式资料.md)
13. [0402 Hermes Agent 专题：Campaign 详细参考学习资料](./daily-upgrade/0402/07_HermesAgent专题_Campaign详细参考学习资料.md)
14. [0402 Hermes Agent 专题：Campaign 启发式资料](./daily-upgrade/0402/08_HermesAgent专题_Campaign启发式资料.md)
15. [0401 当日总纲](./daily-upgrade/0401/00_当日总纲.md)
16. [0401 前台 Butler Flow 入口收口与 New 向导 V1](./daily-upgrade/0401/01_前台ButlerFlow入口收口与New向导V1.md)
17. [0401 Claude Code 对 Butler Flow 工作台化升级与 TUI 信息架构计划](./daily-upgrade/0401/02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)
18. [0401 Butler Flow 主脑自治与预制 Flow 平衡概念设计稿](./daily-upgrade/0401/03_butler-flow主脑自治与预制flow平衡概念设计稿.md)
19. [0401 Butler Flow workspace/manage 分工升级计划（含第一轮实施回写）](./daily-upgrade/0401/04_butler-flow工作流分级与FlowsStudio升级草稿.md)
20. [0401 Claude / Codex CLI 单 Session 能力报告（含 vendor session 与 Butler recent/local memory 的边界裁决）](./daily-upgrade/0401/20260401_claude_codex_cli_session_report.md)
21. [0329 当日总纲](./daily-upgrade/0329/00_当日总纲.md)
22. [0330 当日总纲](./daily-upgrade/0330/00_当日总纲.md)
23. [0331 当日总纲](./daily-upgrade/0331/00_当日总纲.md)
24. [0331 Agent 监管 Codex 实践（exec 与 resume）](./daily-upgrade/0331/01_Agent监管Codex实践_exec与resume.md)
25. [0331 前台 Butler Flow CLI 收口（含 `/flows` `/manage`、managed_flow、exec 测试入口、系统级 CLI 安装入口与历史别名）](./daily-upgrade/0331/02_前台WorkflowShell收口.md)
26. [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写（历史文件名保留草稿）](./daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)
27. [0331 前台长Agent监督Workflow产品化草稿计划](./daily-upgrade/0331/04_前台长Agent监督Workflow产品化草稿计划.md)
28. [0331 04b-butler-flowV1 版本开发计划（含实施回写）](./daily-upgrade/0331/04b-butler-flowV1版本开发计划.md)
29. [0331 04c-butler-flow 完备升级与视觉设计主计划（含 Textual TUI 实施回写、single flow 主视图、`/history` `/settings`）](./daily-upgrade/0331/04c_butler-flow完备升级与视觉设计计划.md)
30. [0331 根目录归档整理收口](./daily-upgrade/0331/05_根目录归档整理收口.md)
31. [0331 前台 butler-flow 角色运行时与 role-session 绑定实施回写（medium 真源，含 role pack 与下一步计划）](./daily-upgrade/0331/06_前台butler-flow角色运行时与role-session绑定计划.md)
32. [0330 后台任务操作面与多Agent编排控制台升级计划](./daily-upgrade/0330/01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md)
33. [0330 Agent Harness 全景研究与 Butler 主线开发指南](./daily-upgrade/0330/02_AgentHarness全景研究与Butler主线开发指南.md)
34. [0330 Chat 默认厚 Prompt 分层治理真源](./daily-upgrade/0330/04_Chat默认厚Prompt分层治理真源.md)
35. [0329 Codex 主备默认自动切换](./daily-upgrade/0329/01_Codex主备默认自动切换.md)
36. [0329 Chat 显式模式与 Project 循环收口](./daily-upgrade/0329/02_Chat显式模式与Project循环收口.md)
37. [0329 后台任务双状态与前门弱化重构](./daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
38. [0327 当日总纲](./daily-upgrade/0327/00_当日总纲.md)
39. [0327 后台任务固定输出区与严格验收收口](./daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)
40. [0327 Skill Exposure Plane 与 Codex 消费边界](./daily-upgrade/0327/02_SkillExposurePlane与Codex消费边界.md)
41. [0327 Butler 系统分层与事件契约收口](./daily-upgrade/0327/03_Butler系统分层与事件契约收口.md)
42. [系统分层与事件契约](./runtime/System_Layering_and_Event_Contracts.md)
43. [0326 Harness 全系统稳定态运行梳理](./daily-upgrade/0326/03_Harness全系统稳定态运行梳理.md)
44. [0326 稳定 Harness 之后的下一阶段主线](./daily-upgrade/0326/04_稳定Harness之后的下一阶段主线_Anthropic长运行Harness吸收版.md)
45. [0326 长任务主线系统审计与并行升级执行方案](./daily-upgrade/0326/05_长任务主线系统审计与并行升级执行方案.md)
46. [系统级审计与并行升级协议](./project-map/06_system_audit_and_upgrade_loop.md)
47. [Butler Runtime 复用接入指南](./runtime/README.md)
48. [Workflow IR 正式口径](./runtime/WORKFLOW_IR.md)

## 建议阅读顺序

1. 先读仓库根 `README.md`
2. 再读 [Project Map 入口](./project-map/README.md)
3. 再读 [0329 当日总纲](./daily-upgrade/0329/00_当日总纲.md)
4. 涉及后台任务控制台、operator harness、prompt/workflow authoring、audit plane，或要对照 `agent_turn / task_summary / latest_turn_receipt / canonical_session_id` 的 console 外显时，先补读 [0330 后台任务操作面与多Agent编排控制台升级计划](./daily-upgrade/0330/01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md)，再补读 [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写](./daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)。
5. 涉及 chat 模式、prompt 厚度、recent、internal chat session 续接/重开或 project 循环时，先补读 [0402 Chat Router 选会话能力升级回写](./daily-upgrade/0402/01_chat_router选会话能力升级回写.md) 与 [0329 Chat 显式模式与 Project 循环收口](./daily-upgrade/0329/02_Chat显式模式与Project循环收口.md)；需要对照**块顺序、门控、/pure 与 Codex 分支**时，再补读 [0330 Chat 默认厚 Prompt 分层治理真源](./daily-upgrade/0330/04_Chat默认厚Prompt分层治理真源.md)
6. 涉及 campaign 宏账本、agent turn receipt、workflow_session 内环、query/feedback 新稳定面时，先读 [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写（历史文件名保留草稿）](./daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)，再按需要补读 [0329 后台任务双状态与前门弱化重构](./daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
7. 涉及 skill / Codex / prompt 注入边界，或 console / Draft Board 的 skill 管理与选择面时，补读 [0327 Skill Exposure Plane 与 Codex 消费边界](./daily-upgrade/0327/02_SkillExposurePlane与Codex消费边界.md)
8. 涉及用宿主 Agent 子进程调用 Codex CLI（`exec` / `exec resume`、`profile` 顺序、非 TTY、MCP 鉴权边界）时，补读 [0331 Agent 监管 Codex 实践（exec 与 resume）](./daily-upgrade/0331/01_Agent监管Codex实践_exec与resume.md)
9. 涉及前台 `butler-flow` CLI、`workflow shell` / `codex-guard` 历史别名、旧 `butler -workflow` 迁移提示、前台 `single_goal / project_loop / managed_flow`、前台 `exec run/resume`、前台 resume 或 receipt 会话恢复、Textual single flow 主视图、`workspace`、`/manage` shared assets、以及 supervisor `fix` 自治/`issue_kind` `followup_kind`（当前 `fix` 仅处理本地 agent CLI 调用链故障）时，先读 [0331 前台 Workflow Shell 收口](./daily-upgrade/0331/02_前台WorkflowShell收口.md)；若涉及 `execution_mode / role_pack / role_sessions / handoff sidecar`，再补读 [0331 前台 butler-flow 角色运行时与 role-session 绑定实施回写](./daily-upgrade/0331/06_前台butler-flow角色运行时与role-session绑定计划.md)；若涉及 `workspace / single flow` 页面的 `默认 supervisor 单栏流 + Shift+Tab 切到 workflow 流`、`workspace vs /manage` 分工、以及 `approval_state / action receipt / handoff / role / phase` 的结构化流式外显，补读 [0401 Claude Code 对 Butler Flow 工作台化升级与 TUI 信息架构计划](./daily-upgrade/0401/02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)；若涉及 `/manage` transcript-first shell、`$asset` mention、manager chat vs asset edit 分离、manager/session queue、shared asset `bundle_manifest / review_checklist / lineage`、builtin `clone/edit` 裁决，再补读 [0402 Butler Flow Manage Center 资产中心升级与会话式交互落地](./daily-upgrade/0402/02_butler-flow_manage-center资产中心升级与会话式交互落地.md)。
10. 涉及 Agent Harness 能力吸收、framework mapping、subagent/session/guardrail/thread-turn-item 设计时，先读 [0330 Agent Harness 全景研究与 Butler 主线开发指南](./daily-upgrade/0330/02_AgentHarness全景研究与Butler主线开发指南.md)，再按 `02A/B/C/D/R/F/G` 命中子计划。
11. 涉及系统抽象、事件契约、multi-agent 语义或 observe/projection 边界时，补读 [系统分层与事件契约](./runtime/System_Layering_and_Event_Contracts.md)
12. 然后按 [改前读包](./project-map/04_change_packets.md) 命中目标专题
13. 若是跨链路排查或系统级升级，补读 [系统级审计与并行升级协议](./project-map/06_system_audit_and_upgrade_loop.md)
14. 只有需要长期背景时，再进入 [`concepts/`](./concepts/README.md)
15. 需要追溯旧语义时，最后才进入 `concepts/history/` 或 `daily-upgrade/history/`

## 维护规则

1. 新的阶段性文档不要直接放在 `docs/` 根目录。
2. 自 `0322` 起，`docs/daily-upgrade/<MMDD>/` 默认维护 `1+N` 文档：`00_当日总纲.md` 用于收口当天推进总览，`01_...md`、`02_...md` 用于承接二级计划。
3. `00_当日总纲.md` 需要明确当天影响到的 `project-map` 条目。
4. 同一二级主题从“先计划 -> 落实 -> 再计划”持续更新在同一份 `01_...md` / `02_...md` 文档里，不再为同一主题反复新开离散文档。
5. 已经稳定且反复引用的日更结论，应提升到 `project-map/` 或 `runtime/`，不要长期只埋在时间线里。
6. 文档内优先使用相对路径，不写机器相关绝对路径。
7. `butler_main/butler_bot_code/docs/` 只保留迁移说明，不再承载正式正文。
8. 系统级升级必须按“并行首轮 -> 再规划 -> 并行二轮 -> 文档回写”收口，不要停留在一次性聊天结论。
9. 若需要临时关闭 chat 侧后台任务入口，先查 `features.chat_frontdoor_tasks_enabled`，再读 [0327 后台任务固定输出区与严格验收收口](./daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)。
