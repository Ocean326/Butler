# Butler Runtime Docs

`docs/runtime/` 收口 Butler 当前稳定 runtime / orchestrator 对外合同。  
这些文档不是临时笔记，而是后续代码、测试、接入与 refactor 的正式口径。

## 当前包含内容

1. [系统分层与事件契约](./System_Layering_and_Event_Contracts.md)
2. [Workflow IR 正式口径](./WORKFLOW_IR.md)
3. [Orchestrator 网页观察台设计稿 v1](./Orchestrator_网页观察台设计稿_v1.md)
4. [Visual Console API Contract v1](./Visual_Console_API_Contract_v1.md)

## 使用规则

1. 改 runtime / orchestrator 稳定合同前，先更新这里的正式口径。
2. 日更文档中的稳定结论，如果已经反复引用，应提升到这里。
3. 这里优先描述“稳定边界”和“对外合同”，不记录一次性排障过程。
4. 系统级分层、事件封套、projection/observability 边界，统一先看这里，再回到 `project-map/` 做导航定位。
