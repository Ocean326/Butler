# 0331 前台 Butler Flow CLI 收口（workflow shell 历史别名）

日期：2026-03-31  
状态：已落代码 / 当前真源  
所属层级：L1 `Agent Execution Runtime`，辅用 L2 状态/轨迹存储  
关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [01_Agent监管Codex实践_exec与resume.md](./01_Agent监管Codex实践_exec与resume.md)
- [系统分层与事件契约](../../runtime/System_Layering_and_Event_Contracts.md)
- [0329 Chat 显式模式与 Project 循环收口](../0329/02_Chat显式模式与Project循环收口.md)
- [0329 Codex 主备默认自动切换](../0329/01_Codex主备默认自动切换.md)

## 一句话裁决

Butler 新增一套**前台附着、用户可中断、用户可恢复**的本地 CLI `butler-flow`（当前版本 `1.2.0`）：

- Codex：主执行
- Cursor：守看、完成判定、续跑 prompt、相位推进建议

这套能力固定属于 L1 `Agent Execution Runtime`，复用 `cli_runner + FileRuntimeStateStore + FileTraceStore + ExecutionReceipt`，但**不进入** `campaign/orchestrator` 后台任务主链。

自 `1.2.0` 起，前台 `butler-flow` 还显式支持 `execution_mode=simple|medium|complex`：`simple=shared session`、`medium=role-bound session`、`complex=per_activation 合同预留`；角色运行时真源见 [06_前台butler-flow角色运行时与role-session绑定计划.md](./06_前台butler-flow角色运行时与role-session绑定计划.md)。

## 入口与兼容别名

当前公共入口固定为：

- `butler-flow run --kind single_goal`
- `butler-flow run --kind project_loop`
- `butler-flow run --kind managed_flow`
- `butler-flow exec run --kind single_goal`
- `butler-flow exec run --kind project_loop`
- `butler-flow flows`
- `butler-flow flows --manage <new|last|flow_id>`
- `butler-flow --version`
- `butler-flow resume --flow-id <id>`
- `butler-flow resume --workflow-id <id>`（兼容参数）
- `butler-flow resume --last`
- `butler-flow resume --codex-session-id <id>`
- `butler-flow exec resume --flow-id <id>`
- `butler-flow exec resume --workflow-id <id>`（兼容参数）
- `butler-flow exec resume --last`
- `butler-flow exec resume --codex-session-id <id>`
- `butler-flow status --flow-id <id>`
- `butler-flow status --workflow-id <id>`（兼容参数）
- `butler-flow status --last`
- `butler-flow list`
- `butler-flow preflight`
- `butler-flow action --type <pause|resume|append_instruction|retry_current_phase|abort>`
- `./tools/install-butler-flow`
- `tools/butler-flow run --kind single_goal`
- `tools/butler-flow run --kind project_loop`
- `tools/butler-flow run --kind managed_flow`
- `tools/butler-flow exec run --kind single_goal`
- `tools/butler-flow exec run --kind project_loop`
- `tools/butler-flow flows`
- `tools/butler-flow flows --manage <new|last|flow_id>`
- `tools/butler-flow resume --flow-id <id>`
- `tools/butler-flow resume --workflow-id <id>`（兼容参数）
- `tools/butler-flow resume --last`
- `tools/butler-flow resume --codex-session-id <id>`
- `tools/butler-flow exec resume --flow-id <id>`
- `tools/butler-flow exec resume --workflow-id <id>`（兼容参数）
- `tools/butler-flow exec resume --last`
- `tools/butler-flow exec resume --codex-session-id <id>`
- `tools/butler-flow status --flow-id <id>`
- `tools/butler-flow status --workflow-id <id>`（兼容参数）
- `tools/butler-flow status --last`
- `tools/butler-flow list`
- `tools/butler-flow preflight`
- `tools/butler-flow action --type <pause|resume|append_instruction|retry_current_phase|abort>`
- `python -m butler_main.butler_flow ...`
- `python -m butler_main ...`

其中：

- `butler-flow ...` 是系统级 CLI 入口
- `tools/butler-flow ...` 是仓库内兼容入口
- `./tools/install-butler-flow` 负责把命令安装到 `~/.local/bin/butler-flow`
- `python -m butler_main ...` 是仓库顶层模块入口，默认落到 `butler-flow`

默认值固定为：

- `workflow run` 不带 `--kind` 时默认 `single_goal`
- `project_loop` 默认从 `plan` 开始
- `managed_flow` 默认仍是有序 phase plan，不支持任意 DAG；真源 sidecar 为每条 flow 下的 `flow_definition.json`
- `resume` 若同时给了 `--workflow-id` 与 `--codex-session-id`，优先恢复本地 `workflow_id`

历史别名（迁移提示，不再执行）：

- `butler workflow`
- `butler -workflow`
- `codex-guard`
- `tools/butler codex-guard ...`

这些入口只保留错误提示与新命令示例，不再作为可运行能力名。

当前 CLI 交互补充为：

- `butler-flow` 在交互终端下无子命令时，若已安装 `requirements-cli.txt` 且终端能力满足，默认进入 Textual 全屏 launcher；否则回退 plain launcher / 向导
- `butler-flow tui` 强制进入 Textual 全屏壳；缺依赖时直接报安装提示
- `butler-flow run` / `resume` 在交互终端下默认进入 Textual attached run screen
- `butler-flow run --plain` / `resume --plain` 强制回到当前 plain 路径
- `butler-flow exec run` / `exec resume` 固定不进入 TUI，stdout 只输出 JSONL 事件和最终 receipt
- launcher 固定展示：
  - config / workspace / flow root
  - Codex / Cursor 可用性
  - butler-flow 专用 MCP guard
  - flow 专用 `codex_exec_home`
  - 最近本地 flow 列表
  - `run / resume / status / list / preflight / flows / quit` 动作
- `butler-flow list` 展示最近本地 flow state，避免用户手抄目录
- `butler-flow flows` 作为 flow 浏览与管理入口；`--manage` 触发 manager agent 协议交接，写回 `workflow_state.json + flow_definition.json`
- `resume --last` / `status --last` 对齐类似 CLI 工具的“恢复最近一条”交互
- `butler-flow preflight` 输出 config、workspace、state root、Codex / Cursor 可用性、当前 flow MCP guard（默认 `stripe,supabase,vercel`，可显式清空），以及 `codex_exec_home=isolated per flow`
- `python -m butler_main` 在交互终端下与直接敲 `butler-flow` 保持同一行为
- `Ctrl+C` 中断 launcher / run / resume 时，固定返回 `130` 并打印 `[butler-flow] interrupted`
- TUI 内固定支持：
  - `/run`
  - `/resume`
  - `/status`
  - `/list`
  - `/flows`
  - `/manage`
  - `/preflight`
  - `/pause`
  - `/resume-run`
  - `/retry-phase`
  - `/abort`
  - `/inspect`
  - `/artifacts`
  - `/help`

## 前台 / 后台边界

这次能力固定是 `foreground attached runtime`：

- 不接 `manager` 常驻
- 不接 `orchestrator tick`
- 不生成 `campaign / mission / branch`
- 不进入 `console / query / feedback` 投影真源

允许写入：

- `run_state`
- `watchdog_state`
- `traces`
- `drafts`
- `codex_home`
- `turns.jsonl`
- `actions.jsonl`
- `artifacts.json`
- `flow_definition.json`

但这些文件只服务前台 shell 自己的恢复与观测，不进入后台任务真源。

本地状态目录固定为：

- `butler_main/butler_bot_code/run/butler_flow/<flow_id>/`

`workflow_state.json`（兼容历史字段名）当前最小稳定字段包括：

- `workflow_id`
- `workflow_kind`
- `goal`
- `guard_condition`
- `current_phase`
- `phase_history`
- `codex_session_id`
- `last_cursor_decision`
- `latest_supervisor_decision`
- `latest_judge_decision`
- `current_turn_id`
- `auto_fix_round_count`
- `trace_refs`
- `receipt_refs`
- `attempt_count`
- `status`

并保留旧 `flow_state.json` 的兼容读取与迁移写回。

## Workflow 语义

### 1. `single_goal`

- 固定相位：`free`
- Cursor 判定：`COMPLETE | RETRY | ABORT`
- judge 当前还会补充：
  - `issue_kind = agent_cli_fault | bug | service_fault | plan_gap | none`
  - `followup_kind = fix | retry | replan | none`
- `RETRY` 时 Butler 自动复用上轮 `codex_session_id`，下一轮走 `codex_mode=resume`
- 只有 `issue_kind=agent_cli_fault + followup_kind=fix` 才会进入显式 `fix` turn
- `issue_kind=bug` 表示业务级实现 / 测试 / 集成问题，继续走普通 `execute/retry`，不进入 `fix` turn

### 2. `project_loop`

- 固定相位：`plan -> imp -> review`
- Cursor 判定：`ADVANCE | RETRY | COMPLETE | ABORT`
- 自动推进默认规则：
  - `plan` 完成后默认进入 `imp`
  - `imp` 完成后默认进入 `review`
  - `review` 只有在 Cursor 明确给出 `COMPLETE` 时才结束
  - `review` 若未完成，必须回到 `imp` 或 `plan`
  - `review` 若发现普通 bug，回到普通 `execute/retry` 继续修复，不进入显式 `fix` turn
  - 只有本地 agent CLI 调用链故障才进入显式 `fix` turn，并保持当前 phase 语义不变
  - `plan` 问题统一收口到 `plan_gap/replan`，不进入 `fix`

当前 judge prompt 固定吃入：

- `workflow_kind`
- `current_phase`
- `goal`
- `guard_condition`
- 最近一次 Codex receipt
- 最近若干轮 `phase_history`
- `current_phase_artifact`

Cursor judge 输出固定为严格 JSON。

### 3. supervisor fix 自治裁决

- `supervisor` 不亲自执行 repo 修复，只决定是否进入显式 `fix` turn。
- `fix` 默认复用同一 Codex session，由主 executor 执行。
- `fix` 只负责本地 `Butler -> Codex/Cursor CLI` 调用链故障：参数/解析错误、bootstrap/config、MCP worker 启动、CLI 运行时接线等。
- Codex timeout / provider / 网络 / 429 / 5xx 等上游服务类故障固定不进入 `fix`。
- 普通 bug 继续由正常 `execute/retry` 回合自治修复，不占用 `fix` turn。
- 连续 `agent_cli_fault` auto-fix 超过 `2` 轮后，flow 自动转 `paused + operator_required`，等待 operator 干预。

## 04c 升级已实施的当前事实

### 1. Textual TUI 已是现役前台产品壳

- 实际代码目录：`butler_main/butler_flow/tui/`
- 当前壳内包含：
  - launcher snapshot
  - single flow screen
  - history screen（`/history`）
  - settings screen（`/settings`）
  - transcript pane
  - flow summary + phase step history
  - history 左栏“头部样式 summary + 可选 flow list”
  - history 右栏“摘要 + recent step 简表 + latest judge/operator signals”
  - action bar
  - slash command input
  - confirm-based operator actions
  - session-scoped transcript preferences（follow / runtime events / filter）

### 1b. 当前 `/history` 交互语义

- `/history` 与 `/flows` 都进入左侧 flow list + 右侧 detail 的整屏模式。
- 左侧顶部不再单独保留 `history-status` 大块，而是收成“像列表项的非交互头部”。
- 打开 `/history` 后焦点默认落在左侧列表；方向键移动只更新右侧 detail，不直接切 flow。
- `Enter` 才会提交当前选中 flow：切回 single flow 主视图、更新 focused flow、并重载 transcript。
- 右侧 detail 当前默认展示：
  - flow 摘要
  - latest judge / latest operator
  - recent step 简表（与 single flow 页的 step 语义对齐）

### 2. `FlowUiEvent` 已落地

当前已新增 `butler_main/butler_flow/events.py`。  
`FlowRuntime` 在前台 flow 内已发出：

- `run_started`
- `supervisor_decided`
- `codex_segment`
- `codex_runtime_event`
- `judge_result`
- `operator_action_applied`
- `artifact_registered`
- `phase_transition`
- `run_completed`
- `run_failed`
- `run_interrupted`
- `warning`
- `error`

这些事件当前已可被 Textual TUI 消费，且保持可序列化字典结构，供 future native/web shell 复用。

### 2b. `exec` 已落地为非 TUI 测试入口

- 当前入口：
  - `butler-flow exec run ...`
  - `butler-flow exec resume ...`
- 当前 stdout 协议固定为：
  - 运行中逐条输出 `FlowUiEvent.to_dict()`
  - 最后一行固定输出 `kind=flow_exec_receipt`
- `flow_exec_receipt` 当前最小稳定字段：
  - `receipt_id`
  - `kind`
  - `flow_id`
  - `workflow_kind`
  - `status`
  - `terminal`
  - `return_code`
  - `flow_dir`
  - `current_phase`
  - `attempt_count`
  - `codex_session_id`
  - `summary`
  - `last_judge_decision`
  - `latest_supervisor_decision`
  - `last_codex_receipt`
  - `last_cursor_receipt`
  - `trace_refs`
  - `receipt_refs`
  - `created_at`
- 退出码固定为：
  - `0` -> `completed`
  - `1` -> `failed`
  - `130` -> `interrupted`

### 3. CLI 依赖单独收口

- 新增 `requirements-cli.txt`
- `Textual` 不并入 `requirements-dev.txt`
- 安装命令固定为：
  - `./.venv/bin/pip install -r requirements-cli.txt`

## 执行适配裁决

### 1. `cli_runner` 升级为 receipt-first

`run_prompt()` 继续保留旧的 `(output, ok)` 兼容面；新的前台 shell 走：

- `run_prompt_receipt()`

当前 `ExecutionReceipt.metadata` 稳定补入：

- `external_session.provider`
- `external_session.thread_id`
- `external_session.resume_capable`
- `provider_returncode`
- `failure_class`
- `cli_events.usage`
- `cli_events.command_events`

### 2. Codex / Cursor 语义禁止自动混跑

butler-flow 调 `cli_runner` 时固定附：

- `cli=codex` 或 `cli=cursor`
- `_disable_runtime_fallback=true`

因此：

- Codex 主执行失败不会悄悄切到 Cursor
- Cursor judge 失败不会再被别的 provider 兜底

### 3. Codex 会话恢复事实

`cli_runner` 现在会显式提取 Codex JSONL 的：

- `thread.started.thread_id`

并写回 `ExecutionReceipt.metadata.external_session.thread_id`。  
这条事实随后进入 `workflow_state.codex_session_id`，让 `resume --workflow-id` 与 loop 内续跑不再依赖用户手填特判。

### 4. 本机 Codex CLI 参数面

2026-03-31 本机执行：

- `codex exec --help`
- `codex exec resume --help`

确认当前 `resume` 形态为：

- `codex exec resume [SESSION_ID] [PROMPT]`

Butler 当前适配策略是：

- 若调用侧显式指定 `profile`，仍挂在 `exec` 层
- 默认不再为 butler-flow 隐式注入 `--profile`；未显式指定时，直接继承本机 `codex` 的默认配置
- `session_id / prompt` 挂在 `resume` 层
- `--skip-git-repo-check` 继续作为 `exec` 选项透传

### 5. Workflow Shell 局部 MCP 隔离

当前发现本机 `codex mcp list` 已启用但未授权的远程 MCP（例如 `stripe`、`supabase`、`vercel`）会在前台 workflow 中引出：

- `rmcp::transport::worker`
- `AuthRequired`
- `timeout waiting for child process to exit`

这些症状会拖慢甚至拖死 `codex exec / exec resume`。  
因此当前裁决改为：

- butler-flow 在 workflow-local `CODEX_HOME` 下默认对 `stripe`、`supabase`、`vercel` 追加局部 MCP 禁用覆盖
- 默认仍继承本机 `codex` 的 profile / provider / auth 基础配置，但不把这些 OAuth 型远程 MCP 直接放进前台 flow 执行面
- 若用户明确需要这类 MCP，可将 `butler_flow.disable_mcp_servers` 显式配置为 `[]` 或自定义列表（兼容读取历史键 `workflow_shell.disable_mcp_servers`）

这层隔离若启用，也只作用于 butler-flow 自己，不改 chat / 其他 CLI 集成的默认配置。

### 6. Workflow Shell 隔离 `CODEX_HOME`

当前再补一条运行时隔离裁决：

- butler-flow 调 Codex 时，默认不再直接复用全局 `~/.codex` 作为执行态 home
- 而是为每条 flow 在 `butler_main/butler_bot_code/run/butler_flow/<flow_id>/codex_home/` 下准备独立 `CODEX_HOME`
- 这份隔离 home 会同步最小必要文件（如 `config.toml`、`auth.json`、`version.json`），但不继承全局 MCP 注册状态
- 这样可保留 profile / provider / auth 相关配置，同时避免全局 `exec` 路径被已登录或未登录的远程 MCP 污染

因此当前默认理解应是：

- 前台 workflow 默认仍尽量沿用本机 Codex 配置
- 但执行态通过 workflow-local `CODEX_HOME` 收口，并默认 guard 已知 OAuth 型远程 MCP，避免 `exec / exec resume` 被全局 MCP state 拖死
- 若本机 `~/.codex/config.toml` 含坏字节或历史脏编码，Butler 当前对 profile 同步读取采用**容错 UTF-8**，会在下一次写回时清洗成稳定 UTF-8，而不再把前台 flow 直接炸成 `UnicodeDecodeError`

### 7. 用户中断收口

- `Ctrl+C` 中断 butler-flow 时，不再抛 Python traceback 到前台
- 当前固定收口为：
  - CLI 返回码 `130`
  - workflow 状态写为 `interrupted`
  - `last_completion_summary` 写为 `interrupted by user`

### 8. `project_loop` phase budget 修正

当前 `phase_attempt_count` 改为只统计**同 phase 下 Codex 成功完成的尝试**。  
因此：

- 真实 plan / imp / review 产出仍受 `max_phase_attempts` 约束
- 纯 timeout / 中断 / rmcp 卡死导致的失败，不再直接耗尽 phase budget
- 旧 state 文件若把这些失败累计进 `phase_attempt_count`，`resume` 时会先按 `phase_history` 自动重算，再决定能否继续

## 代码真源

- `butler_main/butler_flow/`
- `butler_main/agents_os/execution/cli_runner.py`
- `butler_main/runtime_os/agent_runtime/__init__.py`
- `butler_main/butler_cli.py`（旧入口迁移提示）
- `tools/butler-flow`

## 验收

本轮新增 / 扩展回归：

- `test_butler_flow.py`
- `test_butler_cli.py`
- `test_agents_os_wave1.py`
- `test_codex_provider_failover.py`
- `test_codex_cursor_switchover.py`
- `test_chat_cli_runner.py`
- `test_runtime_os_namespace.py`
- `test_runtime_os_root_package.py`

已通过的定向命令：

```bash
.venv/bin/python -m pytest \
  butler_main/butler_bot_code/tests/test_butler_cli.py \
  butler_main/butler_bot_code/tests/test_butler_flow.py \
  butler_main/butler_bot_code/tests/test_agents_os_wave1.py \
  butler_main/butler_bot_code/tests/test_codex_provider_failover.py \
  butler_main/butler_bot_code/tests/test_codex_cursor_switchover.py \
  butler_main/butler_bot_code/tests/test_chat_cli_runner.py \
  butler_main/butler_bot_code/tests/test_runtime_os_namespace.py \
  butler_main/butler_bot_code/tests/test_runtime_os_root_package.py -q

./tools/butler-flow --help
./tools/butler-flow
./tools/butler-flow list
./tools/butler-flow preflight
./tools/butler-flow run --help
./tools/butler-flow resume --help
./tools/butler-flow status --help
./tools/butler workflow   # 仅返回迁移提示，不再执行
./tools/butler -workflow  # 仅返回迁移提示，不再执行
./tools/butler codex-guard free  # 仅返回迁移提示，不再执行
```

## 最终结论

从 2026-03-31 起，Butler 里与历史 `workflow shell / codex-guard` 等价的正确现役理解应固定为：

1. 这是 `butler-flow`，不是后台任务壳
2. 它属于 L1 前台执行运行时，不属于 `campaign/orchestrator`
3. Codex 主执行与 Cursor 判定共享同一套本地 state/trace/resume 基座
4. `single_goal` 与 `project_loop` 共用外环，但 phase contract 不同
