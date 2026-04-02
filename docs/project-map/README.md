# Butler Project Map

`docs/project-map/` 是给人和 agent 共用的当前导航层。

更新时间：2026-03-27  
状态：现役

它只回答四个问题：

1. 当前系统基线是什么
2. 这个改动属于哪一层、哪个功能
3. 这类事实的当前真源在哪里
4. 改动前最小必读包是什么

跨长任务主线的系统级问题，还额外回答第五个问题：

5. 审计和升级应该按什么固定循环推进

当前新增约束：

6. 每轮升级收尾后必须执行一轮实际重启与状态复验

## 使用顺序

1. 先读仓库根 `README.md`
2. 再读 `docs/README.md`
3. 再读当天 `docs/daily-upgrade/<MMDD>/00_当日总纲.md`
4. 然后按本目录继续：
   - `00_current_baseline.md`
   - `01_layer_map.md`
   - `02_feature_map.md`
   - `03_truth_matrix.md`
   - `04_change_packets.md`
   - `06_system_audit_and_upgrade_loop.md`（仅系统级排查/升级必读）
5. 若涉及系统抽象、事件契约、multi-agent 语义或 observe/projection 边界，补读 [`docs/runtime/System_Layering_and_Event_Contracts.md`](../runtime/System_Layering_and_Event_Contracts.md)

## 冲突处理顺序

出现口径冲突时，默认按下面顺序裁决：

1. `docs/project-map/` 当前条目
2. 最新 `00_当日总纲.md` 及其明确链接的当日真源
3. `docs/runtime/` 稳定合同文档
4. `docs/concepts/` 现役文档
5. `docs/concepts/` 兼容期资料
6. `docs/concepts/history/` 与其他历史文档

## 使用边界

- 这里不重复写长篇设计正文，只做导航和裁决入口
- `daily-upgrade/` 仍负责时间线和推进记录
- `runtime/` 仍负责稳定合同和复用接入
- 系统抽象层级、事件契约与跨层命名，以 `runtime/` 的正式合同文档为准
- `concepts/` 只保留长期原则、仍有效概念和接入说明
- 升级收尾默认动作不是“代码和测试结束”，而是 `测试 -> 重启 -> status 复验 -> 文档回写`
