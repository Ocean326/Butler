# guardian_bot_code

guardian 是与 Butler 并列的独立维护 bot。

灵魂机制说明见 `SOUL.md`，外部角色系统提炼见 `docs/外部机制_灵魂要素.md`；当前运行时接线点是 `guardian_bot/runtime.py` → `guardian_bot/reviewer.py`。

第一版目标不是一次做成完整智能运维平台，而是先建立一套稳定的维护骨架：

1. 接收来自 heartbeat / butler / 用户的维护请求
2. 审阅升级或修复请求
3. 对低风险问题自动修复
4. 对高风险问题先审阅再执行
5. 将请求、审阅、执行、测试、回滚写入独立 ledger

## 当前已确认约束

1. 目录位置：与 Butler 并列，而不是 Butler 内嵌子模块
2. 代码目录名：`guardian_bot_code`
3. 记忆组织：独立 recent + state，共享部分 Butler local memory
4. 文件投递：Butler / heartbeat 通过 `butler_main/butler_bot_agent/agents/state/guardian_requests` 投递 request
5. ledger：使用多文件事件目录
6. 改代码前：必须先生成 patch 预案
7. 测试策略：guardian 自动推断测试集合，但允许请求覆盖
8. 直接修复任务：仅低风险可直接执行，高风险先审阅

## 第一版建议模块

1. `guardian_bot/request_models.py`
2. `guardian_bot/request_inbox.py`
3. `guardian_bot/reviewer.py`
4. `guardian_bot/executor.py`
5. `guardian_bot/test_selector.py`
6. `guardian_bot/ledger_store.py`
7. `guardian_bot/runtime.py`

## 第一版交付顺序

1. request schema 与 inbox 读取
2. ledger 事件落盘
3. 审阅器
4. 低风险执行器
5. patch 预案生成器
6. 测试选择器
7. 飞书入口

## PID 与状态归口

- Butler 仍负责写主进程状态：`butler_main/butler_bot_code/run/butler_bot_main_state.json`
- 心跳 sidecar 仍负责写心跳状态：`butler_main/butler_bot_code/run/heartbeat_watchdog_state.json`
- Guardian 维护统一 PID 快照（固定位置）：`butler_main/butler_bot_code/run/guardian_pid_snapshot.json`
- 即使通过非 manager 渠道重启，Guardian 也会按固定周期刷新该快照，避免拿不到 PID

## 标准重启（必须走 Guardian）

- 标准重启命令：`guardian/manager.ps1 restart-stack`
- 顺序：先停 heartbeat sidecar -> 重启 butler talk 主进程 -> 启 heartbeat sidecar -> 健康校验
- 校验通过后才视为重启成功，确保 guardian、butler talk、heartbeat 的状态一致
- Guardian 主循环会在检测到栈不健康时自动调用标准重启（可由 `runtime.auto_repair_stack` 与冷却参数控制）