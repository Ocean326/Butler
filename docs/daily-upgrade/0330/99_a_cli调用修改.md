# 0330 CLI 调用修改复核稿

状态：已按当前代码与测试复核  
定位：`L1 Agent Execution Runtime` 变更记录，不是新的长期真源  
冲突裁决：若与 `docs/project-map/`、`docs/runtime/` 或代码 / 测试冲突，以后者为准

## 1. 这份文档记录什么

本文只记录 0330 这轮 CLI runtime 改动的**当前实现事实**，重点是：

1. 默认 `cursor` 配置下，未显式指定 `cli` 时如何升级为 `codex` 优先
2. `codex` 失败后，如何转入 `cursor` 回落与后续冷却 / 试探
3. stall / reconnect / 用户取消时，进程如何被中止与收口
4. 这些能力在整体框架中的**正确代码位置**

当前框架归位应这样理解：

- 主层级：`L1 Agent Execution Runtime`
- 现役入口：`butler_main/runtime_os/agent_runtime/`
- 兼容实现目录：`butler_main/agents_os/execution/`
- 上层消费方：`chat`、`orchestrator`、`campaign codex runtime`

因此，这轮改动**不应**被放到 `chat/` 或 `orchestrator/` 里实现；它们只是消费侧。

## 2. 本轮行为结论

| 主题 | 当前实现 |
|---|---|
| 默认选择 | `cli_runtime.active` 可以是 `cursor`；但在**未显式指定 cli**、`codex` 可用且未被 switchover 跳过时，`resolve_runtime_request()` 会把执行升级为 **Codex 优先**。 |
| Codex 失败后的主回落 | `run_prompt()` 里当前口径是：**Codex 主执行失败时，若 Cursor 可用，则尝试直接回落到 Cursor**。不再在这里发起第二条“换 fallback profile 的 Codex 执行链”。 |
| provider failover 的职责 | `provider_failover` 继续负责 **profile 状态管理、熔断状态记录、超时收紧与系统 Codex profile 同步**；但不负责在 `run_prompt()` 里触发第二次 Codex 执行。 |
| switchover 行为 | `codex` 主执行失败后，`codex_cursor_switchover` 会进入 `cooldown -> probing -> normal` 状态机：冷却期优先保留 `cursor`，冷却结束后按每小时上限做 `codex` 试探。 |
| stall / reconnect 处理 | 若 stdout / stderr 出现 `Reconnecting... n/m` 用尽、`timeout waiting for child process to exit` 等模式，Butler 会中止 Codex 进程树并把这次执行判为失败。 |
| 用户取消 | 若识别到 Codex 是“用户取消”而非普通失败，可按 `cursor_continue_after_codex_cancel` 配置，用带前缀的 prompt 转交给 Cursor 接续。 |
| Linux 进程树终止 | 非 Windows 下，Codex 使用 `start_new_session=True` 启动；终止时优先 `os.killpg(..., SIGKILL)`，失败再退回 `proc.kill()`。 |
| 流式收口 | `stream_halt` 会在 abort 后阻止后续 `on_segment` / `stderr` 继续外推，减少“进程已结束但外部流还在刷 reconnect 文案”的尾流。 |

## 3. 正确代码位置

### 3.1 L1 真正实现面

| 代码位置 | 角色 |
|---|---|
| `butler_main/agents_os/execution/cli_runner.py` | CLI 执行主入口；负责 `resolve_runtime_request()`、`run_prompt()`、`_run_codex()`、Cursor / Codex 回落、stall 检测、子进程终止、provider 可用性判断。 |
| `butler_main/agents_os/execution/codex_cursor_switchover.py` | `codex -> cursor` 的冷却 / 试探状态机。 |
| `butler_main/agents_os/execution/provider_failover.py` | Codex profile 熔断、超时策略、状态文件与 `~/.codex/config.toml` 同步。 |

### 3.2 现役命名与导出面

| 代码位置 | 角色 |
|---|---|
| `butler_main/runtime_os/agent_runtime/__init__.py` | 当前 `runtime_os` 迁移期的 **curated export surface**。CLI runtime 在整体框架里应从这里理解为 `runtime_os.agent_runtime` 的一部分，而不是继续把 `agents_os.execution` 当最终命名目标。 |

### 3.3 上层消费面

| 代码位置 | 角色 |
|---|---|
| `butler_main/orchestrator/runtime_adapter.py` | orchestrator 对 CLI runtime 的正式接线层。 |
| `butler_main/orchestrator/runtime_policy_adapter.py` | orchestrator 侧的 runtime 请求裁决与 provider 可用性协同。 |
| `butler_main/domains/campaign/codex_runtime.py` | campaign/codex 运行时对 CLI runner 的薄封装。 |
| `butler_main/chat/engine.py` | chat 侧运行时控制、模型查询、CLI 调用消费面。 |

结论：**代码放在 `agents_os/execution/` 是当前兼容实现位置；从整体架构上，它属于 `runtime_os.agent_runtime` 这层。**

## 4. 配置项复核

示例配置需要分开理解：

- `butler_main/butler_bot_code/configs/butler_bot.json.example`
  - 包含 `provider_failover`、`codex_cursor_switchover`、`cursor_continue_after_codex_cancel`、`codex_stall_detection`、`profile_aliases`
- `butler_main/chat/configs/butler_bot.json.example`
  - 当前只包含 `codex_cursor_switchover`、`cursor_continue_after_codex_cancel`、`codex_stall_detection` 和 `providers`
  - **不包含** `provider_failover` 与 `profile_aliases` 示例块

当前与本轮直接相关的配置有：

### 4.1 `cli_runtime.codex_cursor_switchover`

- `enabled`
- `cooldown_seconds`
- `probes_per_hour`
- `state_path`

### 4.2 `cli_runtime.codex_stall_detection`

- `enabled`
- `abort_on_reconnect_exhausted`
- `abort_on_child_process_timeout_message`
- `stall_wall_seconds`
- `min_reconnect_markers_for_stall`
- `poll_interval_seconds`

### 4.3 `cli_runtime.cursor_continue_after_codex_cancel`

- `enabled`
- `prompt_prefix`

### 4.4 `cli_runtime.provider_failover`

- `enabled`
- `primary_profile`
- `fallback_profile`
- `trip_timeout_seconds`
- `cooldown_seconds`
- `probe_timeout_seconds`
- `recovery_success_threshold`
- `state_path`
- `codex_config_path`

运维注意：

- `codex -> cursor` 自动回落能否成立，前提是 `cli_provider_available("cursor")` 为真
- 也就是 `cursor` 的 path 必须能解析到真实可执行文件；否则会返回 `Cursor CLI 不可用` 提示

## 5. 测试覆盖复核

本轮文档里提到的核心测试，当前都与实现匹配：

| 测试文件 | 当前覆盖点 |
|---|---|
| `test_codex_provider_failover.py` | failover profile 同步、主 profile 超时收紧、显式 profile 绕过管理、Codex 失败后 Cursor 回落协同。 |
| `test_codex_cursor_switchover.py` | 冷却、每小时 probe 限额、成功清空状态、`resolve_runtime_request()` 在冷却期保留 `cursor`。 |
| `test_codex_stall_detection.py` | reconnect 耗尽、child process timeout 文案匹配、最终输出强制判失败。 |
| `test_agents_os_wave1.py` | 默认 `cursor` 下的 Codex-first 升级、Codex 任意失败回落 Cursor、用户取消后 Cursor 接续。 |
| `test_chat_engine_model_controls.py` | `_run_codex()` 的 `Popen` 参数、stdin prompt 传递、provider override、`ephemeral`、Windows kwargs、安全读取 `call_args` 等。 |

本次复核实际执行结果：

```bash
PYTHONPATH=butler_main .venv/bin/python -m pytest \
  butler_main/butler_bot_code/tests/test_codex_provider_failover.py \
  butler_main/butler_bot_code/tests/test_codex_cursor_switchover.py \
  butler_main/butler_bot_code/tests/test_codex_stall_detection.py \
  butler_main/butler_bot_code/tests/test_agents_os_wave1.py \
  butler_main/butler_bot_code/tests/test_chat_engine_model_controls.py -q
```

结果：`57 passed`

## 6. 运维与验收备注

- 代码层当前没有发现需要继续修补的实现缺口；这次主要问题是文档口径不够准
- 若要做运行面复验，可执行：

```bash
./tools/butler restart butler_bot
```

- 日志位置：
  - `butler_main/butler_bot_code/logs/butler_bot.log`

## 7. 复核结论

1. 功能完善度：当前文档所述主能力已由代码和测试覆盖，核心行为成立。
2. 正确性：原稿大体方向对，但对**架构归位**和**配置样例差异**写得不够准，现已修正。
3. 简洁性：已删除过度展开的措辞，保留“行为结论 + 代码位置 + 配置 + 测试”四块。
4. 代码位置：当前正确口径是“实现落在 `agents_os/execution/`，框架归属属于 `runtime_os.agent_runtime` 的 L1 Agent Execution Runtime”。
