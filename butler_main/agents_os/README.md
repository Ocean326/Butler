# agents_os

`agents_os/` 不是默认从零另起一套 Butler 替身系统。

它的定位是：**先审视 Butler 当前已有的 `code / agent / space` 三层，抽出其中干净、通用、稳定、可复用的 runtime 内核，把它们封装并收口到这里；如果 Butler 现有体系里没有合适部件，再补最小新实现。**

因此，`agents_os` 是 Butler 的：

- runtime 抽核层
- 新内核承接层
- 运行时真源未来落点

而不是：

- 新 prompt 包
- 新业务域包
- 旧总控的简单搬家目录
- Butler-specific adapter 容器

当前工作原则：

- 简洁：先抽最小必要内核，不预造复杂框架
- 高效：优先复用现有干净部件，只在必要时重写
- 必要：不搬运冗余、陈旧、脏代码与历史包袱

未来边界目标：

- `agents_os` 负责 runtime 内核、protocol、通用基础设施
- Butler 本体只保留：业务域、角色/prompt、接口适配、工作区资产
- 凡是 Butler-specific adapter，一律放在 `butler_main/butler_bot_code/butler_bot/agents_os_adapters/`

当前 Wave 1 已落地：

- `execution/cli_runner.py`：统一 CLI 执行入口，当前已收口 `cursor`，并为 `codex_cli`、`claude_cli` 预留 provider 槽位与 fallback 顺序
- `state/run_state_store.py`：通用 file-based runtime state store
- `state/trace_store.py`：通用 file-based trace store
- `context/memory_backend.py`：memory protocol + file backend 最小实现

当前 Wave 2 已落地：

- `tasking/task_store.py`：定义任务真源承接的最小协议
- `execution/runtime_policy.py`：定义 runtime branch policy 的最小协议
- Butler 侧 `agents_os_adapters/runtime_policy.py`：承接旧 runtime branch policy，并复用 `agents_os.execution.cli_runner`
- Butler 侧 `agents_os_adapters/paths.py`：承接运行目录落位与状态文件路径解析

当前承接状态：

- chat 主链已切到 `butler_main/chat/`，不再通过旧 `memory_manager.py` / 旧后台编排文件维持后台运行
- 旧后台自动化 / sub-agent / team execution 兼容壳已从主线代码移除
- 当前 Butler 侧保留的 adapter 以 runtime policy 与路径桥接为主，避免再次长出 Butler-specific runtime 内核

并行 manager 启动原则：

- 新的 `research_manager`、`project_manager` 等并行主管，可以直接复用 `agents_os` core
- 但它们自己的 `task_source / truth / scheduler / runtime_policy / task_store` adapter，必须放在各自 manager 目录
- 也就是说：`agents_os` 负责 runtime，manager 自己负责 adapter + prompts + interface
