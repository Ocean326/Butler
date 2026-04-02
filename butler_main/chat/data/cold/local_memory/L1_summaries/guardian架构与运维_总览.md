# Guardian 架构与运维（总览）

> **时效说明（2026-03-25 更新）**：本文描述的 guardian 守护进程、互相拉起、guardian 侧重启 Butler 等机制均已退出当前 chat 主线，不再作为 prompt 认知真源。现行口径以 `人格与自我认知.md`、chat 侧 bootstrap 与 runtime 代码为准；本文仅保留为历史架构参考。
> 目的：汇总 guardian 的职责、升级规划、风控设计与 Butler 互相守护机制。
> 合并整理于 2026-03-19（scheduled memory maintenance）

---

## 一、Guardian 定位

- Guardian 为守护进程，负责重启 Butler 的权限在 Guardian。
- 用户只需在 guardian 端触发重启，由 guardian 对 Butler 主进程执行软重启或更彻底重启。
- 人格与规则按 feishu-workstation-agent.md 与 Butler_SOUL 重载。
- 应视为整体架构中的**一等公民**，而非幕后"无名苦力"，体现"先富带动后富"的系统演进理念。

---

## 二、Guardian v2 升级

- 将 guardian 升级为 v2，明确其进程与状态管理职责。
- 与 Butler 共享少量真源状态文件，设计**双向巡检与互相拉起机制**。
- 配套一键冷启动入口，确保在进程异常或人为误操作下系统仍能自愈与快速恢复。
- 中长期为 guardian 制定专门升级计划，标准化"guardian 重启"收尾动作。

---

## 三、架构重构与最小可恢复包

- 在架构层面区分**可热插拔与需重启的模块**。
- 重启前后通过真源记忆与进度快照维持认知与任务连续性。
- guardian 被赋予"重启与抢救"职责，需要**最小可恢复包**和可执行剧本来帮助系统在崩溃后快速恢复。
- 后续重构应减少即兴搬家、增加可恢复的迁移设计。

---

## 四、风控测试与能力边界

- 对 AI 在玩笑/调戏语境下的请求做风控测试。
- 系统既能识别请求性质，又不虚假承诺（如伪称能在指定时间主动提醒）。
- 本次对话沉淀为 guardian 的风控测试用例和能力边界规范。

---

> 本总览合并自：`Guardian负责重启Butler的约定`、`guardian_v2升级与Butler–guardian互相复活工程`、`将guardian视为一等公民并规划升级`、`Butler_guardian架构重构与最小可恢复包策略`、`guardian风控测试与能力边界设计`
