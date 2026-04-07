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
6. [0407 当日总纲](./daily-upgrade/0407/00_当日总纲.md)
- 补充：[0407 Canonical Team Runtime 最终收口：任务产物真源、治理真源与升级门槛](./daily-upgrade/0407/01_canonical_team_runtime最终收口_任务产物真源与升级门槛.md)
- 补充：[0407 CLI Agent Substrate -> Canonical Team Runtime -> Team OS 脑暴收口](./每日头脑风暴/0407/01_CLI_Agent_Substrate到Canonical_Team_Runtime再到Team_OS_脑暴收口.md)
- 补充：[0407 以 `Task + Artifact` 为真源的 Full-Stack Team OS 草稿](./每日头脑风暴/0407/02_以Task_Artifact为真源的Full_Stack_Team_OS草稿.md)
6. [0404 当日总纲](./daily-upgrade/0404/00_当日总纲.md)
- 补充：`0404/00` 已回写本轮仓库级重构完成态；当前应按 canonical tree 理解三产品与 repo 导航
- 补充：[0404 Butler Flow manager skill-contract 吸收与单 `main` worktree 收口](./daily-upgrade/0404/01_butler-flow_manager-skill-contract吸收与单main-worktree收口.md)
- 补充：0403 脑暴/资料稿当前统一落在 `docs/每日头脑风暴/0403/`，不再继续写回旧 `docs/每日/0403/`
7. [0403 当日总纲](./daily-upgrade/0403/00_当日总纲.md)
- 补充：[0403 Butler Flow Codex 执行根隔离与 `repo_bound` 裁决](./daily-upgrade/0403/01_butler-flow_Codex执行根隔离与repo_bound裁决.md)
- 补充：[0403 Butler Flow supervisor 控制画像与 agents-flow 治理升级](./daily-upgrade/0403/02_butler-flow_supervisor控制画像与agents-flow治理升级.md)
- 补充：[0403 跨机器开发仓库收口与私有层隔离](./daily-upgrade/0403/03_跨机器开发仓库收口与私有层隔离.md)
- 补充：[0403 Butler Flow Desktop 壳与 shared surface bridge 落地](./daily-upgrade/0403/03_butler-flow_desktop壳与shared_surface_bridge落地.md)
- 补充：[0403 仓库级重构实施稿：三产品 / Platform / Repo Governance](./daily-upgrade/0403/04_仓库级重构实施稿_三产品_platform_repo治理.md)
- 补充：`0403/04` 已在 `0404` 收口为完成态：`products/chat`、`products/butler_flow`、`products/campaign_orchestrator` 已成为真实主树，旧路径只保 compat 壳
- 补充：[跨机器开发仓库启动说明](./concepts/跨机器开发仓库启动说明.md)
- 补充：[仓库级重构远景规划（产品 / Platform / Repo Governance 版）](./远景草稿/仓库级重构.md)
- 补充：同日继续把 Butler Desktop 回写为“可测试的 Desktop 壳”：新增 renderer `vitest`、Electron `Playwright` 点击回归、`Config Path Fallback` 手填兜底，以及无图形环境下自动 `xvfb-run` 的 e2e 启动口径，正文仍收口在 [0403 Butler Flow Desktop 壳与 shared surface bridge 落地](./daily-upgrade/0403/03_butler-flow_desktop壳与shared_surface_bridge落地.md)
- 补充：0403 同日继续回写了 Manage Center manager 的 `session/draft/pending_action` 持久化与 `draft_payload` 提交口径；同日再补了 manager chat 的 target sticky、悬空 `$` 清理、非 JSON reply 的 `parse_status / raw_reply / error_text` 透传，以及 `resume` 失败后同 provider fresh Codex exec 的自愈口径；随后再把 manager 从“长 prompt 约束”进一步收口到 `skill-style` 机制：`manager skill registry + reference progressive disclosure + lightweight asset/session summary + draft ownership/action validator`，正文收口在 [0402 Butler Flow Manage Center 资产中心升级与会话式交互落地](./daily-upgrade/0402/02_butler-flow_manage-center资产中心升级与会话式交互落地.md)
7. [0402 当日总纲](./daily-upgrade/0402/00_当日总纲.md)
8. [0402 Chat Router 选会话能力升级回写（含 unified frontdoor compile 与 CLI lane）](./daily-upgrade/0402/01_chat_router选会话能力升级回写.md)
9. [0402 Butler Flow Manage Center 资产中心升级与会话式交互落地](./daily-upgrade/0402/02_butler-flow_manage-center资产中心升级与会话式交互落地.md)
10. [0402 Hermes Agent 专题：Butler Flow 详细参考学习资料](./daily-upgrade/0402/03_HermesAgent专题_ButlerFlow详细参考学习资料.md)
11. [0402 Hermes Agent 专题：Butler Flow 启发式资料](./daily-upgrade/0402/04_HermesAgent专题_ButlerFlow启发式资料.md)
12. [0402 Hermes Agent 专题：Chat 详细参考学习资料](./daily-upgrade/0402/05_HermesAgent专题_Chat详细参考学习资料.md)
13. [0402 Hermes Agent 专题：Chat 启发式资料](./daily-upgrade/0402/06_HermesAgent专题_Chat启发式资料.md)
14. [0402 Hermes Agent 专题：Campaign 详细参考学习资料](./daily-upgrade/0402/07_HermesAgent专题_Campaign详细参考学习资料.md)
15. [0402 Hermes Agent 专题：Campaign 启发式资料](./daily-upgrade/0402/08_HermesAgent专题_Campaign启发式资料.md)
16. [0402 Butler Flow 长流治理与 supervisor 可观测性升级](./daily-upgrade/0402/11_butler-flow_长流治理与supervisor可观测性升级.md)
- 补充：[0402 Butler-flow Desktop V2.1 PRD（main 分支对齐 / foreground flow CLI 入口 / TUI + Desktop 双轨）](./daily-upgrade/0402/20260402_Butler-flow Desktop V2.1 PRD_main分支对齐_flow CLI入口与双轨实施_更新版.md)
- 补充：[0402 Butler-flow-Desktop 开发计划（butler-flow 执行版，含 Desktop 技术选型与 Proma 复用边界）](./daily-upgrade/0402/20260402_Butler-flow-Desktop开发计划_butlerflow执行版.md)
- 补充：[0402 Vibecoding Agent 默认收尾动作与 vibe-close 收口](./daily-upgrade/0402/09_vibecoding_agent默认收尾动作与vibe_close收口.md)
- 补充：[0402 GitHub / ChatGPT 网页端阅读入口增强](./daily-upgrade/0402/10_github_chatgpt网页端阅读入口增强.md)
17. [0401 当日总纲](./daily-upgrade/0401/00_当日总纲.md)
18. [0401 前台 Butler Flow 入口收口与 New 向导 V1](./daily-upgrade/0401/01_前台ButlerFlow入口收口与New向导V1.md)
19. [0401 Claude Code 对 Butler Flow 工作台化升级与 TUI 信息架构计划](./daily-upgrade/0401/02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)
20. [0401 Butler Flow 主脑自治与预制 Flow 平衡概念设计稿](./daily-upgrade/0401/03_butler-flow主脑自治与预制flow平衡概念设计稿.md)
21. [0401 Butler Flow workspace/manage 分工升级计划（含第一轮实施回写）](./daily-upgrade/0401/04_butler-flow工作流分级与FlowsStudio升级草稿.md)
22. [0401 Claude / Codex CLI 单 Session 能力报告（含 vendor session 与 Butler recent/local memory 的边界裁决）](./daily-upgrade/0401/20260401_claude_codex_cli_session_report.md)
22. [0329 当日总纲](./daily-upgrade/0329/00_当日总纲.md)
23. [0330 当日总纲](./daily-upgrade/0330/00_当日总纲.md)
24. [0331 当日总纲](./daily-upgrade/0331/00_当日总纲.md)
25. [0331 Agent 监管 Codex 实践（exec 与 resume）](./daily-upgrade/0331/01_Agent监管Codex实践_exec与resume.md)
26. [0331 前台 Butler Flow CLI 收口（含 `/flows` `/manage`、managed_flow、exec 测试入口、系统级 CLI 安装入口与历史别名）](./daily-upgrade/0331/02_前台WorkflowShell收口.md)
27. [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写（历史文件名保留草稿）](./daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)
28. [0331 前台长Agent监督Workflow产品化草稿计划](./daily-upgrade/0331/04_前台长Agent监督Workflow产品化草稿计划.md)
29. [0331 04b-butler-flowV1 版本开发计划（含实施回写）](./daily-upgrade/0331/04b-butler-flowV1版本开发计划.md)
30. [0331 04c-butler-flow 完备升级与视觉设计主计划（含 Textual TUI 实施回写、single flow 主视图、`/history` `/settings`）](./daily-upgrade/0331/04c_butler-flow完备升级与视觉设计计划.md)
31. [0331 根目录归档整理收口](./daily-upgrade/0331/05_根目录归档整理收口.md)
32. [0331 前台 butler-flow 角色运行时与 role-session 绑定实施回写（medium 真源，含 role pack 与下一步计划）](./daily-upgrade/0331/06_前台butler-flow角色运行时与role-session绑定计划.md)
33. [0330 后台任务操作面与多Agent编排控制台升级计划](./daily-upgrade/0330/01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md)
34. [0330 Agent Harness 全景研究与 Butler 主线开发指南](./daily-upgrade/0330/02_AgentHarness全景研究与Butler主线开发指南.md)
35. [0330 Chat 默认厚 Prompt 分层治理真源](./daily-upgrade/0330/04_Chat默认厚Prompt分层治理真源.md)
36. [0329 Codex 主备默认自动切换](./daily-upgrade/0329/01_Codex主备默认自动切换.md)
37. [0329 Chat 显式模式与 Project 循环收口](./daily-upgrade/0329/02_Chat显式模式与Project循环收口.md)
38. [0329 后台任务双状态与前门弱化重构](./daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
39. [0327 当日总纲](./daily-upgrade/0327/00_当日总纲.md)
40. [0327 后台任务固定输出区与严格验收收口](./daily-upgrade/0327/01_后台任务固定输出区与严格验收收口.md)
41. [0327 Skill Exposure Plane 与 Codex 消费边界](./daily-upgrade/0327/02_SkillExposurePlane与Codex消费边界.md)
42. [0327 Butler 系统分层与事件契约收口](./daily-upgrade/0327/03_Butler系统分层与事件契约收口.md)
43. [系统分层与事件契约](./runtime/System_Layering_and_Event_Contracts.md)
44. [0326 Harness 全系统稳定态运行梳理](./daily-upgrade/0326/03_Harness全系统稳定态运行梳理.md)
45. [0326 稳定 Harness 之后的下一阶段主线](./daily-upgrade/0326/04_稳定Harness之后的下一阶段主线_Anthropic长运行Harness吸收版.md)
46. [0326 长任务主线系统审计与并行升级执行方案](./daily-upgrade/0326/05_长任务主线系统审计与并行升级执行方案.md)
47. [系统级审计与并行升级协议](./project-map/06_system_audit_and_upgrade_loop.md)
48. [Butler Runtime 复用接入指南](./runtime/README.md)
49. [Workflow IR 正式口径](./runtime/WORKFLOW_IR.md)
50. [0402 Butler Flow Doctor 恢复角色与实例级静态资产修复](./daily-upgrade/0402/12_butler-flow_doctor恢复角色与实例级静态资产修复.md)

## 建议阅读顺序

1. 先读仓库根 `README.md`
2. 再读 [Project Map 入口](./project-map/README.md)
3. 再读 [0329 当日总纲](./daily-upgrade/0329/00_当日总纲.md)
4. 涉及后台任务控制台、operator harness、prompt/workflow authoring、audit plane，或要对照 `agent_turn / task_summary / latest_turn_receipt / canonical_session_id` 的 console 外显时，先补读 [0330 后台任务操作面与多Agent编排控制台升级计划](./daily-upgrade/0330/01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md)，再补读 [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写](./daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)。
5. 涉及 chat 模式、frontdoor 单次编译、CLI lane、prompt 厚度、recent、internal chat session 续接/重开或 project 循环时，先补读 [0402 Chat Router 选会话能力升级回写](./daily-upgrade/0402/01_chat_router选会话能力升级回写.md) 与 [0329 Chat 显式模式与 Project 循环收口](./daily-upgrade/0329/02_Chat显式模式与Project循环收口.md)；需要对照**块顺序、门控、/pure 与 Codex 分支**时，再补读 [0330 Chat 默认厚 Prompt 分层治理真源](./daily-upgrade/0330/04_Chat默认厚Prompt分层治理真源.md)
6. 涉及 campaign 宏账本、agent turn receipt、workflow_session 内环、query/feedback 新稳定面时，先读 [0331 后台主线 Campaign 宏账本与 Agent 可重入内环实施回写（历史文件名保留草稿）](./daily-upgrade/0331/03_后台主线控制面瘦身与Agent内环提权草稿计划.md)，再按需要补读 [0329 后台任务双状态与前门弱化重构](./daily-upgrade/0329/03_后台任务双状态与前门弱化重构.md)
7. 涉及 skill / Codex / prompt 注入边界，或 console / Draft Board 的 skill 管理与选择面时，补读 [0327 Skill Exposure Plane 与 Codex 消费边界](./daily-upgrade/0327/02_SkillExposurePlane与Codex消费边界.md)
8. 涉及用宿主 Agent 子进程调用 Codex CLI（`exec` / `exec resume`、`profile` 顺序、非 TTY、MCP 鉴权边界）时，补读 [0331 Agent 监管 Codex 实践（exec 与 resume）](./daily-upgrade/0331/01_Agent监管Codex实践_exec与resume.md)
9. 涉及前台 `butler-flow` CLI、`workflow shell` / `codex-guard` 历史别名、旧 `butler -workflow` 迁移提示、前台 `single_goal / project_loop / managed_flow`、前台 `exec run/resume`、前台 resume 或 receipt 会话恢复、Textual single flow 主视图、`workspace`、`/manage` shared assets、以及 supervisor `fix` 自治/`issue_kind` `followup_kind`（当前 `fix` 仅处理本地 agent CLI 调用链故障）时，先读 [0331 前台 Workflow Shell 收口](./daily-upgrade/0331/02_前台WorkflowShell收口.md)；若涉及 `execution_mode / role_pack / role_sessions / handoff sidecar`，再补读 [0331 前台 butler-flow 角色运行时与 role-session 绑定实施回写](./daily-upgrade/0331/06_前台butler-flow角色运行时与role-session绑定计划.md)；若涉及 `coding_flow=repo_bound`、`research_flow=isolated`、`execution_context / execution_workspace_root` 或非仓库任务误读根 `AGENTS.md`，补读 [0403 Butler Flow Codex 执行根隔离与 `repo_bound` 裁决](./daily-upgrade/0403/01_butler-flow_Codex执行根隔离与repo_bound裁决.md)；若涉及 `control_profile`、supervisor 长流治理、显式 repo contract、operator `shrink_packet/bind_repo_contract/force_doctor` 或 manager->supervisor handoff，再补读 [0403 Butler Flow supervisor 控制画像与 agents-flow 治理升级](./daily-upgrade/0403/02_butler-flow_supervisor控制画像与agents-flow治理升级.md)；若涉及 `workspace / single flow` 页面的 `默认 supervisor 单栏流 + Shift+Tab 切到 workflow 流`、`workspace vs /manage` 分工、以及 `approval_state / action receipt / handoff / role / phase` 的结构化流式外显，补读 [0401 Claude Code 对 Butler Flow 工作台化升级与 TUI 信息架构计划](./daily-upgrade/0401/02_ClaudeCode对ButlerFlow工作台化升级与TUI信息架构计划.md)；若涉及 `/manage` transcript-first shell、`$asset` mention、manager chat vs asset edit 分离、manager/session queue、shared asset `bundle_manifest / review_checklist / lineage / role_guidance`、builtin `clone/edit` 裁决，再补读 [0402 Butler Flow Manage Center 资产中心升级与会话式交互落地](./daily-upgrade/0402/02_butler-flow_manage-center资产中心升级与会话式交互落地.md)。
- 补充：若目标是前台 `butler-flow` 的 Desktop/TUI 双轨规划、shared surface 抽取、Proma 壳技术栈吸收、或把多份 Butler Flow 计划收口成单一执行主计划，补读 [0402 Butler-flow Desktop V2.1 PRD（main 分支对齐 / foreground flow CLI 入口 / TUI + Desktop 双轨）](./daily-upgrade/0402/20260402_Butler-flow Desktop V2.1 PRD_main分支对齐_flow CLI入口与双轨实施_更新版.md) 与 [0402 Butler-flow-Desktop 开发计划（butler-flow 执行版，含 Desktop 技术选型与 Proma 复用边界）](./daily-upgrade/0402/20260402_Butler-flow-Desktop开发计划_butlerflow执行版.md)。
- 补充：若目标已进入 Butler Desktop 实装、Electron 壳、Python bridge、shared surface 共用投影、`Config Path Fallback`、或运行验证拆层，补读 [0403 Butler Flow Desktop 壳与 shared surface bridge 落地](./daily-upgrade/0403/03_butler-flow_desktop壳与shared_surface_bridge落地.md)。
10. 涉及 Agent Harness 能力吸收、framework mapping、subagent/session/guardrail/thread-turn-item 设计时，先读 [0330 Agent Harness 全景研究与 Butler 主线开发指南](./daily-upgrade/0330/02_AgentHarness全景研究与Butler主线开发指南.md)，再按 `02A/B/C/D/R/F/G` 命中子计划。
11. 涉及系统抽象、事件契约、multi-agent 语义或 observe/projection 边界时，补读 [系统分层与事件契约](./runtime/System_Layering_and_Event_Contracts.md)
12. 然后按 [改前读包](./project-map/04_change_packets.md) 命中目标专题
13. 若是跨链路排查或系统级升级，补读 [系统级审计与并行升级协议](./project-map/06_system_audit_and_upgrade_loop.md)
- 补充：若目标是 agent 默认工作流、文档回写协议、或 vibecoding 的 git / worktree 收口，补读 [0402 Vibecoding Agent 默认收尾动作与 vibe-close 收口](./daily-upgrade/0402/09_vibecoding_agent默认收尾动作与vibe_close收口.md)
- 补充：若目标是 GitHub / ChatGPT 网页端如何理解仓库入口与系统说明，补读 [0402 GitHub / ChatGPT 网页端阅读入口增强](./daily-upgrade/0402/10_github_chatgpt网页端阅读入口增强.md)
- 补充：若目标是前台 `butler-flow` 长流恢复、实例级静态资产修复、`doctor` 临时角色或 `resume/no-rollout` 自愈链路，补读 [0402 Butler Flow Doctor 恢复角色与实例级静态资产修复](./daily-upgrade/0402/12_butler-flow_doctor恢复角色与实例级静态资产修复.md)
14. 只有需要长期背景时，再进入 [`concepts/`](./concepts/README.md)
16. 需要追溯旧语义时，最后才进入 `concepts/history/` 或 `daily-upgrade/history/`

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
