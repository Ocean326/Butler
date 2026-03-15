# Butler

Butler 的当前主工程已经收口到 `butler_main/`。

## 目录结构

1. `butler_main/`
   当前唯一主工程，负责对话主进程、heartbeat、记忆、agent、运行脚本与工作区映射。
2. `docs/`
   当前唯一正式文档入口。
3. `过时/`
   历史链路归档区。已下线的 `guardian` 工程迁入 `过时/guardian/`，只作留档，不再作为当前运行主链路。

## 当前运行约定

1. Butler 当前后台结构以 `talk 主进程 + heartbeat sidecar + self_mind` 为准。
2. 运行控制优先通过 Butler 主进程与现有管理脚本完成，不再把 `guardian` 视为必要守护前提。
3. 代码目录整理遵循“根目录只保留主机制代码，其余按职责归类到子目录”的原则。

## 维护边界

1. 当前真实代码入口在 `butler_main/butler_bot_code/`。
2. 当前真实文档入口在 `docs/`。
3. `过时/guardian/` 只保留历史代码、脚本、日志与设计资料，不继续承接新的运行职责。
