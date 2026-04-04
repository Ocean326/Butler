# Butler Runtime Body

`butler_bot_code/` 是 Butler 当前的 runtime body，负责共享资产、配置、运行态、日志、测试与管理脚本；它不是 `chat / butler-flow / campaign_orchestrator` 三产品的产品层真源。

## 当前结构

- `assets/`
  - flow builtin/template/instance 等共享资产
- `configs/`
  - 运行配置模板与本地配置
- `logs/`
  - 主进程与 orchestrator 日志
- `run/`
  - PID、状态文件、运行态快照
- `scripts/`
  - 管理、诊断与辅助脚本
- `tests/`
  - 回归测试与协议测试

## 当前运行事实

1. 系统级 CLI 入口是 `butler-flow`。
2. 对话产品面现役入口仍是 `chat`。
3. 后台现役控制面是 `orchestrator`。
4. 旧后台自动化 / sub-agent / team execution 运行体已从主仓主线移除，不再保留现役入口。
5. `guardian` 已退出当前运行主链路，历史代码迁入仓库根目录 `过时/guardian/`。
6. Windows `watch_stack.ps1` / `manager.ps1` 已退役，不再作为当前默认运维入口。

## 使用说明

```bash
./tools/install-butler-flow
butler-flow
butler-flow preflight

python -m butler_main.butler_bot_code.manager list
python -m butler_main.butler_bot_code.manager status
python -m butler_main.butler_bot_code.manager start butler_bot
python -m butler_main.butler_bot_code.manager stop butler_bot
python -m butler_main.butler_bot_code.manager restart butler_bot

./tools/butler status
./tools/butler restart butler_bot
./tools/butler chat
```

补充说明：

- `status` 反映 Butler 当前主链路状态。
- 更细的排障优先结合 `logs/`、`run/`、`python -m butler_main.butler_bot_code.manager status` 与 `./tools/butler status`。
- `butler-flow` 是当前系统级 CLI 入口；安装脚本默认链接到 `~/.local/bin/butler-flow`
- `tools/butler` 是 Linux 下的轻量入口：
  - 管理命令：`list/status/start/stop/restart`
  - `chat` 或无参数：进入 Butler CLI 对话
  - `core`：直接启动 chat core HTTP 服务
