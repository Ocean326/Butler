# Codex 原生能力边界与 Butler 吸收参考

日期：2026-03-25
时间标签：0325_0010
状态：实机验证完成 / 第四层与 operator plane 参考件

## 目标

1. 把本轮对 `Codex` 原生能力边界的摸排结果沉淀成 `0325` 的参考输入。
2. 回答哪些能力与 Butler 当前理念重合，可以直接吸收；哪些只能包裹复用；哪些不能误判为第 `2/3` 层真源。
3. 为后续 `campaign supervisor`、`operator plane`、项目级 agent 配置提供一份稳定裁决基线。

## 当前已确认事实

### 1. 本机 Codex CLI 事实

- 当前版本：`codex-cli 0.116.0`
- 已确认命令面：
  - `codex exec`
  - `codex resume`
  - `codex fork`
  - `codex review`
  - `codex mcp`
  - `codex app-server`
  - `codex cloud`
  - `codex features`
- `codex resume --help`
  - 支持按 `SESSION_ID` 或 thread name 恢复会话
  - 支持 `--last`、`--all`
- `codex fork --help`
  - 支持基于已有会话分叉新线程
  - 支持 `--last`、`--all`
- `codex features list` 当前关键结果：
  - `multi_agent = stable / true`
  - `tui_app_server = experimental / false`
  - `guardian_approval = experimental / false`
  - `apps = experimental / false`
- 已做一次真实 `exec` 验证：
  - 命令：`codex exec --json --color never --sandbox read-only --skip-git-repo-check --ephemeral -C . "Reply with exactly OK."`
  - 结果：返回 `OK`
  - 结论：当前本机 `Codex CLI` 可实际启动并完成最小一次 agent 运行，不只是 `--help` 可用
- 已做一轮项目级 role pack 修正后的复验：
  - 保留同类 `codex exec --json` 路径再次执行
  - 结果：不再出现 `.codex/agents/*.toml` malformed 提示
  - 结论：当前仓库级 Codex 角色导出已能被 `codex-cli 0.116.0` 正确加载

### 2. 当前仓库已具备的项目级落点

- 根目录已有 `AGENTS.md`
- 项目级 `.codex/config.toml` 已存在：
  - `[agents]`
  - `max_threads = 4`
  - `max_depth = 3`
  - `job_max_runtime_seconds = 1200`
- 项目级 `.codex/agents` 已存在：
  - `explorer.toml`
  - `worker.toml`
  - `reviewer.toml`
  - 以及 `planner`、`debugger`、`docs-researcher`
- 项目级 `.claude/agents` 也已有同名最小角色包
- 本轮实机验证先发现、后修正了一条关键兼容事实：
  - 初始状态下，`codex-cli 0.116.0` 会把仓库里的 `.codex/agents/*.toml` 判为 malformed
  - 直接报错为：`unknown field prompt`
  - 根因是旧版导出模板仍在使用 `prompt`
  - 本轮已把 `.codex/agents/*.toml` 与 `butler_main/sources/agent_teams/**/codex.toml` 统一切到当前字段
  - 因此现在可以把项目级 role pack 视为“已可用，但后续要持续按官方 schema 守卫”

### 2.1 当前 Butler harness 对接事实

- `butler_main/agents_os/execution/cli_runner.py`
  - 已实装 `codex exec --json` 调用
  - 已补 `--model`、`--sandbox`、`--profile`、`--skip-git-repo-check`、`--ephemeral`、配置覆盖与事件流解析
- `butler_main/orchestrator/interfaces/query_service.py`
  - 已提供 `get_codex_debug_status()`
  - 已把 `codex` 使用窗口并入 observation snapshot
- `butler_main/orchestrator/smoke.py`
  - 已允许用 `codex` 作为默认 runtime provider 做 smoke 配置

因此，本轮的真实结论不是“仓库还没有 Codex harness”，而是：

1. `CLI runtime harness` 已经存在并可用。
2. 当前真正需要守的是项目级 `.codex/agents` 导出 schema，而不是重造 Butler 的 Codex 运行壳。

### 3. Butler 当前主线边界

结合 [00_当日总纲.md](./00_当日总纲.md)、[08_第四层接口冻结_V1_简化版.md](./08_第四层接口冻结_V1_简化版.md)、[09_长期自治Campaign任务层_讨论草稿.md](./09_长期自治Campaign任务层_讨论草稿.md)，本轮判断尺子固定为：

- `3 = orchestrator / control plane`
- `2 = runtime_os / process runtime`
- `1 = runtime_os / agent runtime`
- `campaign supervisor` 属于第 `4` 层 `domain & product plane`

因此，外部框架与原生工具能力的吸收，默认先看它更像：

- 第 `4` 层产品协议或 operator tooling
- 还是第 `2/3` 层 substrate 真语义

## 核心裁决

### A. 可直接吸收

这些能力与 Butler 当前方向重合度高，且更像第 `4` 层协作壳或 operator tooling：

| 能力 | 对 Butler 的对应位 | 当前裁决 |
| --- | --- | --- |
| `AGENTS.md` + 项目级 `.codex/agents` | 项目级 instruction 真源、角色模板分发 | 直接吸收，但 `.codex/agents` 必须先升级到当前官方字段 |
| `resume` / `fork` / transcript 持久化 | 外部会话恢复、回溯、分叉实验 | 直接吸收 |
| `subagents` / `multi_agent` | phase 内部多角色协作 | 直接吸收 |
| `review` / reviewer 型工作流 | `Evaluate` 阶段终审器 | 直接吸收 |
| `MCP` | 外部工具与能力接入层 | 直接吸收 |

直接吸收的含义是：

1. 不需要 Butler 自己重新发明同类外壳。
2. 可以直接成为当前仓库的默认协作方式。
3. 但吸收后仍要服从 Butler 的四层边界，不得反向污染第 `2/3` 层真源定义。

### A.1 项目级 role pack 的额外裁决

根据 OpenAI 官方 `Codex subagents` 文档，当前自定义 agent TOML 至少应采用：

- `name`
- `description`
- `developer_instructions`

可选再叠：

- `model`
- `model_reasoning_effort`
- `sandbox_mode`

因此，Butler 对 `.codex/agents` 的正确策略是：

1. `butler_main/sources/agent_teams/*/codex.toml` 继续作为 vendor 导出模板。
2. 导出目标 `.codex/agents/*.toml` 必须与当前官方 schema 对齐。
3. `prompt` 不再作为 Codex 自定义 agent 字段继续保留。

### B. 可包裹复用，但只应放在第 4 层或 operator plane

| 能力 | 更适合的 Butler 位置 | 当前裁决 |
| --- | --- | --- |
| `worktrees` / `local environments` / `automations` | operator plane、后台执行隔离、工程操作入口 | 包裹复用 |
| `cloud` | 远端执行通道、外包执行面 | 包裹复用，暂不设为核心依赖 |
| `app-server` | 客户端接入协议、自建前端/IDE 面板适配层 | 只做接入壳 |

这组能力的共同点是：

- 它们很适合做产品入口、后台调度、远端执行与 UI 接入。
- 但它们不应被误当作 Butler 内部 `control plane` 或 `process runtime` 的真源。

### C. 只能借鉴，不能替代 Butler 第 2/3 层

| Codex 概念 | 不能直接等同的 Butler 概念 |
| --- | --- |
| `session` / `thread` | `workflow_session` / checkpoint / recovery substrate |
| `subagent thread` | `mission / node / branch` |
| `MCP server` | `task_ledger` / `artifact_store` / `event_bus` |
| `app-server` / `cloud task` | `orchestrator control plane` |

当前必须避免四种误判：

1. 不把 `Codex resume/fork` 直接等同于 Butler 的 `workflow_session + recovery substrate`。
2. 不把 `Codex subagents` 直接等同于 Butler 的 `campaign supervisor` 或 `mission graph`。
3. 不把 `MCP` 直接等同于 Butler 的持久化真源。
4. 不把 `app-server` / `cloud` 直接等同于 Butler 第 `3` 层控制面。

## 与 Butler 当前理念的重合点

### 1. 和 `0319` 原子能力路线重合

在 [history/0319/0119_项目未来构想与落实计划_原子功能与业务复用.md](../history/0319/0119_项目未来构想与落实计划_原子功能与业务复用.md) 中，Butler 已明确提出：

- `sub_agent`
- `agent_team`
- `worker_adapter`
- `tool_gateway`
- `observer_recovery`

这与 Codex 的：

- `subagents`
- `multi_agent`
- `MCP`
- `resume/fork`
- transcript / review / worktree tooling

存在明显重合，因此这批能力应优先视作“可直接收编的外部成熟壳”，而不是额外再造一套平行能力。

### 2. 和 `0325` campaign supervisor 路线重合

在 [09_长期自治Campaign任务层_讨论草稿.md](./09_长期自治Campaign任务层_讨论草稿.md) 中，Butler 已把长期自治定义为：

- 外层由 `campaign supervisor` 承载
- 阶段内允许多角色协作
- `reviewer / evaluator` 是最终判定者
- 第 `2` 层 substrate 负责 `session / artifact / blackboard / mailbox / join / recovery`

这与 Codex 最容易形成自然配合的方式是：

- 用 `explorer / worker / reviewer` 做阶段内角色协作
- 用 `resume / fork` 做外部会话延续与试验分叉
- 用 `review` 做最小终审闭环
- 用 `MCP` 做工具和资料接入

## 当前仓库建议的最小采用组合

如果只考虑“现在就能用、风险最低、最符合当前架构”的组合，建议固定为：

1. `AGENTS.md` 作为 Codex 项目主说明文件。
2. `.codex/agents` 中的 `explorer / worker / reviewer` 作为第一套默认角色包。
3. `resume / fork` 作为外部会话恢复与试验分叉能力。
4. `review` 作为最小终审器。
5. `MCP` 作为可插拔工具接入层。

这套最小组合已经足够支撑：

- 本仓库内的读写分工
- 阶段内多 agent 协作
- reviewer 独立裁决
- 会话恢复与复盘
- 外部文档/工具接入

## 对后续实现的约束建议

### 1. 对第 4 层的建议

- 可在 `campaign`、`operator plane`、`research domain pack` 中直接消费 `Codex` 的 subagent / review / resume 能力。
- 第 `4` 层如果记录外部执行事实，建议只记录：
  - `provider = codex`
  - `external_session_id`
  - `external_thread_id`
  - `resume_capable`
  - `fork_capable`
  - `review_capable`

### 2. 对第 2/3 层的建议

- 第 `2` 层仍然要自己拥有：
  - `workflow_session`
  - checkpoint / resume substrate
  - governance / recovery 真执行语义
- 第 `3` 层仍然要自己拥有：
  - `mission / node / branch / ledger`
  - compile / projection / scheduler 真语义

### 3. 对项目治理的建议

- `AGENTS.md` 作为 Codex 主真源继续维护。
- `butler_main/sources/agent_teams/` 继续作为 Butler 第 4 层 vendor-neutral role source of truth。
- `.codex/agents/` 只是导出产物，不再承担 Butler 真源职责。
- `CLAUDE.md` 作为兼容层保留，但不要让 Codex 的项目级规则继续分裂到另一份主文档里。
- `cloud`、`app-server`、`apps` 在本轮全部视为未来扩展位，不纳入当前内核主线。

## 参考资料

### OpenAI 官方文档

- `https://developers.openai.com/codex/cli/features`
- `https://developers.openai.com/codex/cli/slash-commands`
- `https://developers.openai.com/codex/subagents`
- `https://developers.openai.com/codex/concepts/subagents`
- `https://developers.openai.com/codex/guides/agents-md`
- `https://developers.openai.com/codex/config-reference`
- `https://developers.openai.com/codex/mcp`
- `https://developers.openai.com/codex/workflows`
- `https://developers.openai.com/codex/app/automations`
- `https://developers.openai.com/codex/app/local-environments`
- `https://developers.openai.com/codex/app/worktrees`
- `https://developers.openai.com/codex/app-server`
- `https://developers.openai.com/codex/feature-maturity`

### Butler 本仓库文档

- [00_当日总纲.md](./00_当日总纲.md)
- [08_第四层接口冻结_V1_简化版.md](./08_第四层接口冻结_V1_简化版.md)
- [09_长期自治Campaign任务层_讨论草稿.md](./09_长期自治Campaign任务层_讨论草稿.md)
- [0119_项目未来构想与落实计划_原子功能与业务复用.md](../history/0319/0119_项目未来构想与落实计划_原子功能与业务复用.md)
- [1204_runtime概念分层_参考OpenAI Agents SDK与Butler映射.md](../history/0319/1204_runtime概念分层_参考OpenAI Agents SDK与Butler映射.md)
