## 简短结构化摘要（Simon · Multi-Agent Harness Engineering）

- **主题**：提出面向真实业务 Multi-Agent 系统的「四层 Harness 架构」，区分知识、编排、风险门控与治理四个层次来管理多 Agent 协作。
- **关键方法**：通过统一知识层管理参数化 / 非参数化 / 经验三类知识，避免把业务语义和案例散落在各个 Agent 的私有 Prompt 里。
- **关键方法**：用编排层（Orchestrator / Workflow）负责任务拆解与 handoff，让 Planner / Worker / Reviewer 等角色在清晰协议下协作，而不是依赖单一「超级 Agent」。
- **对 Butler 的启发**：把 `docs`、`BrainStorm` 与长期记忆显式标记为知识层，把 heartbeat、task pipeline 与 skills 视作编排层，并预留统一的 Guard / Governance 机制收拢权限、预算与工具白名单。
- **对 Butler 的启发**：在设计 future AgentTeam / 多 Agent 协作时，先画出「角色 → Harness 四层」映射，明确哪些逻辑在 Agent 内部、哪些应上收给 Harness 管理。
- **对 Butler 的启发**：将运行日志、失败模式与成功 playbook 组织成可检索的治理资产（如 dashboard 或案例库），让 heartbeat 不只是「报平安」，而是驱动下一轮架构与策略调优的经验飞轮。

