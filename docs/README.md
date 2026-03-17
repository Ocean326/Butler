# Butler Docs

`docs/` 是 Butler 的唯一正式文档入口。

## 目录结构

- `concepts/`
  - 长期有效的概念、架构、协议、接入说明、排障地图
- `daily-upgrade/`
  - 按日期归档的阶段性改动、现状、计划、排查记录
  - 统一使用 `docs/daily-upgrade/<MMDD>/` 目录
- `tools/`
  - 文档辅助脚本

## 最近改动入口

1. [0317 心跳与任务循环现状问题报告](./daily-upgrade/0317/0317_心跳与任务循环现状问题报告.md)
2. [0317 仓库现状与 manager 边界报告](./daily-upgrade/0317/0317_仓库现状与manager边界报告.md)
3. [0317 recent -> local memory 机制现状](./daily-upgrade/0317/0317_recent到local_memory机制现状.md)
4. [0316 执行结果：解耦与心跳治理](./daily-upgrade/0316/0316执行结果_解耦与心跳治理.md)
5. [0316 执行结果：Bootstrap 升级落地](./daily-upgrade/0316/0316执行结果_bootstrap升级落地.md)
6. [0316 Bootstrap 升级方案和计划](./daily-upgrade/0316/0316_bootstrap升级方案和计划.md)
7. [0316 Prompt 组成说明：Talk / Heartbeat / Self-Mind](./daily-upgrade/0316/0316_prompt组成说明_talk_heartbeat_self_mind.md)
8. [0316 现状分析与升级计划](./daily-upgrade/0316/0316现状分析与升级计划.md)
9. [0315 现状文档](./daily-upgrade/0315/0315现状文档.md)
10. [0315 计划文档](./daily-upgrade/0315/0315计划文档.md)
11. [工程化目标架构](./daily-upgrade/0315/工程化目标架构_20260315.md)

## 建议阅读顺序

1. [0313 升级对照总结](./daily-upgrade/0313/20260314_0313升级对照总结.md)
2. [0314 升级前现状：任务调度与记忆链路](./daily-upgrade/0314/20260314_0314升级前现状_任务调度与记忆链路.md)
3. [当前系统架构](./concepts/当前系统架构_20260314.md)
4. [0315 现状文档](./daily-upgrade/0315/0315现状文档.md)
5. 需要追历史时，再进入 `daily-upgrade/<MMDD>/`

## 维护规则

1. 新的阶段性文档不要直接放在 `docs/` 根目录。
2. 文档内优先使用相对路径，不写机器相关绝对路径。
3. `butler_main/butler_bot_code/docs/` 只保留迁移说明，不再承载正式正文。
