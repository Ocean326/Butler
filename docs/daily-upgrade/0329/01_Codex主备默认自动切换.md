# 0329 Codex 主备默认自动切换

日期：2026-03-29  
状态：现役 / 已落代码  

## 目标

让 `aixj` 成为默认主线，`openai` 成为备用，并把“当前默认可用 profile”提升为系统级运行事实，而不是只靠人工改 `~/.codex/config.toml`。

## 当前裁决

1. 默认主线固定为：
   - `aixj`
2. 备用固定为：
   - `openai`
3. 熔断触发条件固定为：
   - 超时
   - 网络错误
   - `429`
   - `5xx`
4. `aixj` 的主备超时阈值固定为：
   - `30s`
5. 周期探针固定为：
   - 每 `15min` 探测一次 `aixj`
6. 冷却窗口固定为：
   - `30min`

## 代码收口

1. Butler 执行层主真源：
   - `butler_main/agents_os/execution/provider_failover.py`
   - `butler_main/agents_os/execution/cli_runner.py`
2. 运行配置主真源：
   - `butler_main/butler_bot_code/configs/butler_bot.json -> cli_runtime.provider_failover`
3. 系统级默认 profile 主真源：
   - `~/.codex/config.toml` 顶层 `profile = "..."`  
   - 由 user systemd timer 周期性维护

## 当前行为

1. chat、orchestrator、campaign codex runtime 最终都汇到 `cli_runner.run_prompt`，因此默认 profile 使用同一份 failover 状态。
2. 若请求显式指定 `profile`，显式指定优先，不被自动主备改写。
3. 若自动路由命中 `aixj` 且失败，会立刻把全局状态切到 `openai`，并同步系统级 `~/.codex/config.toml` 顶层默认 profile。
4. 周期探针成功后，再把系统默认切回 `aixj`。

## 系统侧调度

1. user systemd 单元：
   - `~/.config/systemd/user/butler-codex-provider-failover.service`
   - `~/.config/systemd/user/butler-codex-provider-failover.timer`
2. timer 只负责短命 reconcile，不引入常驻守护进程。
