# runtime_os

`runtime_os/` 是 `0325` 任务包 A 的兼容期命名壳。

当前目标不是立刻把 `agents_os/` 和 `multi_agents_os/` 物理搬空，而是先把新的总名稳定下来，让后续 import 迁移、脚本替换和目录重排有一个明确落点。

当前约定：

- `runtime_os.agent_runtime`
  - 对应 L1 `Agent Execution Runtime（Agent 执行运行时）`
  - 承接单次 run、provider/CLI 适配、上下文、状态、skills 消费面
- `runtime_os.durability_substrate`
  - 对应 L2 `Durability Substrate（持久化基座）`
  - 承接 checkpoint、writeback、recovery、durable receipt 等稳定导出
- `runtime_os.multi_agent_protocols`
  - 对应 L3 `Multi-Agent Protocol（多 Agent 协议层）`
  - 承接 workflow template、typed primitive contract 等 compile-time 协议对象
- `runtime_os.multi_agent_runtime`
  - 对应 L4 `Multi-Agent Session Runtime（多 Agent 会话运行时）`
  - 承接 session、artifact registry、mailbox、handoff、join、event log、workflow factory
- `runtime_os.process_runtime`
  - 兼容期聚合别名，继续暴露旧的混合导出面
  - 新代码优先从上面四个层级面导入，只在兼容迁移时使用它

兼容期原则：

- 新代码优先从 `runtime_os` 的分层公开面导入。
- 旧代码的 `agents_os` / `multi_agents_os` 先继续可用，不在本轮强拆。
- `runtime_os.process_runtime` 保留兼容别名，但不再作为长期命名目标。
- 真正的物理 rename 留到 import 面收敛、字符串硬编码清完之后再做。
