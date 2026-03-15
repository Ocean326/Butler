# 飞书机器人统一管理

`butler_bot_code/` 是 Butler 当前的运行时身体层，负责对话主进程、heartbeat、配置、日志、测试与管理脚本。

## 当前结构

- `butler_bot/`
  - 主机制代码入口
  - 根目录仅保留主链路模块，如 `butler_bot.py`、`memory_manager.py`、`heartbeat_orchestration.py`
  - 其余模块已按职责归类到子目录：
    - `services/`
    - `runtime/`
    - `registry/`
    - `execution/`
    - `utils/`
    - `obsolete/`
- `configs/`
  - 运行配置模板与本地配置
- `logs/`
  - 主进程与 heartbeat 日志
- `run/`
  - PID、状态文件、运行态快照
- `tests/`
  - 回归测试与协议测试

## 当前运行事实

1. 后台结构以 Butler 主进程直管 `heartbeat` 与 `self_mind` 为准。
2. `guardian` 已退出当前运行主链路，历史代码迁入仓库根目录 `过时/guardian/`。
3. `watch_stack.ps1` 现在只观察 Butler 主进程、heartbeat 与 watchdog，不再把 guardian 当作现役组件。

## 使用说明

```powershell
.\manager.ps1 list
.\manager.ps1 status
.\manager.ps1 start butler_bot
.\manager.ps1 stop butler_bot
.\manager.ps1 restart butler_bot
```

补充说明：

- `status` 反映 Butler 当前主链路状态。
- 更细的排障可配合 `.\watch_stack.ps1` 与 `logs/` 下日志一起看。
