# Butler — 变更与架构汇总（截至 2026-03-09）

## 概述
- 目标：将之前在会话中所做的改动、新增功能与架构细节汇总入新的 `Butler` 根目录，便于运维与后续开发。

## 关键新增功能
- Guardian 请求与分类流水线：引入基于文件的请求协议（guardian_requests → guardian_ledger）。
  - Butler 会通过心跳/compact 等时机将请求写入 Guardian 输入目录（record-only / upgrade）。
- Guardian 基线审核器：实现自动审核逻辑，返回三种结果：`approve` / `need-info` / `reject`，并写入审计账本。
- 管理脚本与运行时：新增 `manager.ps1`（用于启动/停止/状态）和守护运行循环（一次性处理 + 循环轮询）。

## 主要改动（文件与位置）
- Butler 端：
  - [butler_bot_code/butler_bot/butler_paths.py](butler_bot_code/butler_bot/butler_paths.py)：新增 `GUARDIAN_REQUESTS_DIR_REL`、`GUARDIAN_LEDGER_DIR_REL` 等常量。
  - [butler_bot_code/butler_bot/memory_manager.py](butler_bot_code/butler_bot/memory_manager.py)：新增将心跳升级请求与最近内存压缩记录写入 Guardian 请求文件的钩子与序列化逻辑。

- Guardian 端（新模块）：
  - [guardian_bot_code/guardian_bot/request_models.py](guardian_bot_code/guardian_bot/request_models.py)：`GuardianRequest` 与 `GuardianReviewResult` 的数据模型与序列化。
  - [guardian_bot_code/guardian_bot/request_inbox.py](guardian_bot_code/guardian_bot/request_inbox.py)：Inbox 列表、读取待办请求、持久化已决策请求（移动到决议目录）。
  - [guardian_bot_code/guardian_bot/reviewer.py](guardian_bot_code/guardian_bot/reviewer.py)：规则化审核器，输出 `approve/need-info/reject` 与 `review_notes`。
  - [guardian_bot_code/guardian_bot/ledger_store.py](guardian_bot_code/guardian_bot/ledger_store.py)：将审计事件写入 `guardian_ledger/reviews`，文件名带时间戳与请求副本。
  - [guardian_bot_code/guardian_bot/runtime.py](guardian_bot_code/guardian_bot/runtime.py)、[guardian_bot_code/guardian_bot/main.py](guardian_bot_code/guardian_bot/main.py)：处理循环与一次性运行入口。
  - [guardian_bot_code/configs/guardian_bot.json](guardian_bot_code/configs/guardian_bot.json)：Guardian 配置（请求目录、账本根目录等）。
  - [guardian_bot_code/manager.ps1](guardian_bot_code/manager.ps1)：Windows 启动/停止/状态脚本（使用 `cmd.exe` wrapper + 明确 `PYTHONPATH`，并将日志重定向）。

- 其他：
  - Probe 示例请求放在 Butler agent 状态目录，用于验证三种审核结果（approve/need-info/reject）。
  - 文档：在新 root 下加入 README 与变更说明。

## 架构说明（高层）
- 流程：
  1. Butler 在需要时（例如心跳升级、内存压缩）写入一个 JSON 请求到 `guardian_requests` 目录。
  2. Guardian 的运行时轮询该目录，加载请求并调用 `reviewer` 进行基线审核。
  3. 审核结果与审计副本写入 `guardian_ledger/reviews`，并将请求文件移动到对应的决策目录（例如 `processed/approve/`）。
  4. （未来）对于 `approve` 的请求，由执行层（execution layer）读取审计记录并按 `patch_plan`/`verification` 执行变更与回滚策略。

- 设计原则：
  - 可观测性：所有决策都写审计账本，包含请求副本与审核说明。
  - 最小权限与审查：审核器在改变系统之前先做“是否可接受”的判断，避免自动误动作。
  - 可扩展：将审核（review）、执行（execute）、观察（observe）分层，便于后续替换或增强每一层。

## 运行与运维注意事项
- 唯一重启入口：强制通过 `Butler/guardian/manager.ps1` 启动/停止 Guardian，避免临时脚本直接重启导致环境不一致。
- Windows 后台启动：`manager.ps1` 使用 `cmd.exe` wrapper 并显式设置 `PYTHONPATH`，以确保后台进程获得正确环境变量与工作目录。
- 迁移与文件锁：在移动/重命名项目目录前，请停止相关进程并确保没有句柄占用（否则 Windows 会阻止移动）。

## 已验证的行为（测试样例）
- 一次性运行输出示例：`guardian runtime once | pending=3 | approve=3 | reject=0 | need-info=0`。
- Probe 结果：
  - `runtime-online-probe` → `approve`（记录到 ledger）。
  - `runtime-need-info-probe` → `need-info`（`review_notes` 包含缺失的 `patch_plan/verification/rollback`）。
  - `runtime-reject-probe` → `reject`（`review_notes` 指明来源非法）。

## 已完成（2026-03-09）
- 实现执行层（Execution Layer）：
  - 对 `approve` 的请求实现自动补丁应用、运行测试、回滚策略与执行审计条目（execution events）。
  - `GuardianLedgerStore.write_execution_event()` 写入 `guardian_ledger/executions/`。
  - `GuardianExecutor` 支持 record-only 备案、无补丁验证测试、有补丁时的应用/测试/回滚。
  - `GuardianRuntime` 在 approve 后对 `should_execute` 的请求调用 executor 并计入 `executed` 统计。
- 更细粒度的审核策略：引入策略配置、风险评分、以及基于历史的学习模型进行判定。
- 将 Guardian 作为受管服务部署（系统服务 / Windows Service / 守护进程），替代当前的 PowerShell manager + 背景终端方式。

## 快速操作（示例）
- 启动 Guardian（示例）：

```powershell
# 在 Butler/guardian 目录下
.\Butler\guardian\manager.ps1 start
```

- 手动一次性运行（调试）：

```powershell
# 在 Butler/guardian 目录下，或设置 PYTHONPATH
python -m guardian_bot.main
# 或指定 config
python -m guardian_bot.main --config configs/guardian_bot.json
```

## 关键文件索引
- Butler 端：
  - [butler_bot_code/butler_bot/butler_paths.py](butler_bot_code/butler_bot/butler_paths.py)
  - [butler_bot_code/butler_bot/memory_manager.py](butler_bot_code/butler_bot/memory_manager.py)
- Guardian 端：
  - [guardian_bot_code/guardian_bot/request_models.py](guardian_bot_code/guardian_bot/request_models.py)
  - [guardian_bot_code/guardian_bot/request_inbox.py](guardian_bot_code/guardian_bot/request_inbox.py)
  - [guardian_bot_code/guardian_bot/reviewer.py](guardian_bot_code/guardian_bot/reviewer.py)
  - [guardian_bot_code/guardian_bot/ledger_store.py](guardian_bot_code/guardian_bot/ledger_store.py)
  - [guardian_bot_code/guardian_bot/executor.py](guardian_bot_code/guardian_bot/executor.py)
  - [guardian_bot_code/guardian_bot/runtime.py](guardian_bot_code/guardian_bot/runtime.py)
  - [guardian_bot_code/manager.ps1](guardian_bot_code/manager.ps1)
- 配置与文档：
  - [guardian_bot_code/configs/guardian_bot.json](guardian_bot_code/configs/guardian_bot.json)
  - [Butler/README.md](Butler/README.md)
  - 本文件：[Butler/CHANGELOG_SUMMARY.md](Butler/CHANGELOG_SUMMARY.md)

---

需要我将这份摘要提交到 Git（创建 commit），还是继续把 `Execution Layer` 的初步实现草案写进同一文件？
