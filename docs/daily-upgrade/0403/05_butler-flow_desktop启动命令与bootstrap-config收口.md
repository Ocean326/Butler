# 0403 Butler Flow Desktop 启动命令与 bootstrap config 收口

日期：2026-04-03  
状态：已落代码 / 当前真源  
所属层级：L1 `Agent Execution Runtime`

## 1. 本轮目标

把 `Butler Flow Desktop` 的日常启动从“需要手工准备配置后才能打开”收口成：

- 仓库内有固定直达命令
- 没有正式 `butler_bot.json` 时也能先起 launcher
- bootstrap 配置落 machine-local overlay，而不是污染仓库

## 2. 当前裁决

本轮把启动面分成两层：

- `tools/flow-desktop`
  - 作为面向人和 agent 的直达入口，默认直接进入 `butler-flow` launcher
- `butler_main/butler_flow/app.py::_load_config()`
  - 当未显式传 `--config` 且默认 `butler_bot.json` 不存在时，自动寻找同目录下的 `butler_bot.json.example`
  - 读取示例配置后，把 `workspace_root` 改写为当前仓库根
  - 生成 machine-local bootstrap config 到 `~/.butler/bootstrap_configs/butler_flow_<hash>.json`
  - 再按正常 `load_active_config()` 路径继续启动

这样做的边界是：

- 只对“未显式传 `--config`”的默认启动生效
- 不修改仓库内正式配置文件
- 不把 bootstrap 文件写回 repo

## 3. 落地结果

现在可用的启动方式变成：

```bash
./tools/flow-desktop
```

若已执行安装脚本，也可以直接用：

```bash
flow-desktop
butler-flow
```

同时 `./tools/install-butler-flow --force` 现会一起安装：

- `~/.local/bin/butler-flow`
- `~/.local/bin/flow-desktop`

## 4. 验收

本轮直接相关验证：

- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow.py -q -k "load_config or main_without_subcommand_enters_launcher_on_interactive_tty or cli_version_prints_current_butler_flow_version"`
- `./tools/butler-flow --help`
- `./tools/flow-desktop --help`
- `./tools/flow-desktop`
- `./tools/install-butler-flow --force`

结果：

- 目标 pytest 子集：`4 passed`
- `flow-desktop` 已实际进入 launcher
- `butler-flow` / `flow-desktop` 已安装到 `~/.local/bin/`

## 5. 一句话

> `Butler Flow Desktop` 现在已经具备“clone 后可直接打开 launcher”的最小启动面，默认缺配置不再是第一次启动的硬阻塞。
