---
type: "note"
---
# 02 Heartbeat 废弃与旧体系冻结

日期：2026-03-23\
时间标签：0323_0002\
状态：进行中

## 最新判断（2026-03-23 03:14:54）

1. `02 Heartbeat` 当前不应再被理解为功能建设 worker，而应明确理解为：

**治理型 worker / 冻结型 worker**

2. 它当前的价值不在于新增能力，而在于防止旧体系重新定义新主线。

3. 结合当前代码检查，这条线已经不只是“文档说要冻结”：

* 默认阻断逻辑已经出现

* 冻结协议已经进入工程标准

* 测试已经开始覆盖“默认冻结、显式开闸”路径

4. 但这条线仍然没有完成，原因也必须写清楚：

* `memory_manager.py` 仍有 legacy heartbeat 影子

* 兼容 adapter 仍存在

* 开发过程中仍可能有人为了快，绕回 heartbeat 兼容链

5. 因此路线纠偏结论是：

**后续不再讨论“heartbeat 还要不要继续做一点什么”，而只讨论：哪些兼容壳保留、哪些入口必须继续封死、哪些 legacy 语义要继续清退。**

## 主线

1. `heartbeat` 从今天开始正式进入“废弃执行期”，不再只是文档上的 retired legacy。

2. 今日目标不是删除 heartbeat 全部代码，而是**正式完成它的角色降级**：从现役前后台组织者，降为历史兼容与迁移参考物。

3. Butler 想尽快把 `chat / orchestrator / multi_agents_os` 落地，首先就必须切断所有“旧职责回流到 heartbeat”的路径。

4. 所有与 heartbeat 相关的后续动作，只允许是：冻结、切断、兼容壳保留、迁移参考；不再允许新增产品职责或运行时职责。

## 参照长期架构文档后的重新判断

结合 外部多Agent框架调研与Butler长期架构规划_20260323.md，当前 Butler 的长期结构应是：

* `chat` 作为前台入口面

* `orchestrator` 作为 mission / control plane

* `multi_agents_os` 作为 collaboration substrate

* `agents_os` 作为 runtime core

在这个格局下，`heartbeat` 已不再拥有清晰的长期正当性：

1. 它不应再是前台入口。

2. 它不应再是后台主控制面。

3. 它不应再是多 Agent 协作的宿主。

4. 它只应保留为迁移过渡物与历史兼容壳。

## 当前状态

1. `heartbeat` 已在 `0322` 文档口径中退出现役主线。

2. 但在代码和执行习惯上，仍存在三个遗留风险：

   * 旧入口思维仍可能把前台逻辑挂回 heartbeat

   * `memory_manager.py` 等历史总控仍与 heartbeat 语义缠绕

   * worker 执行时容易用“先走 heartbeat 兼容一下”来绕过新主线

3. 当前真正缺的不是“再设计 heartbeat”，而是一份可执行的冻结清单、切断清单、保留清单。

## 今日总目标

1. 完成 `heartbeat` 的职责降级说明，不再让它承担现役角色。

2. 完成 `chat <- heartbeat` 的切断口径，前台彻底屏蔽 heartbeat。

3. 完成 `heartbeat -> orchestrator` 的后台职责迁移说明，避免后台出现职责真空。

4. 明确 heartbeat 还剩哪些兼容壳允许存在，哪些地方从今天开始禁止继续写新逻辑。

## 今日计划

### P0 角色降级正式落盘

1. 明确 heartbeat 今天之后不再承担：

   * 前台入口

   * 前台调度

   * 前台回传兜底

   * 后台现役控制面

2. 明确 heartbeat 仅保留：

   * 历史参考

   * 必要兼容壳

   * 迁移期对照对象

### P1 Chat 侧彻底切断

1. 列出所有仍会把前台逻辑引回 heartbeat 的入口语义与调用点。

2. 禁止任何新 chat 功能再通过 heartbeat 落地。

3. 若存在临时兼容路径，也必须明确标为过渡壳，不得再扩展。

### P2 后台职责迁移说明

1. 列出 heartbeat 原先承担的后台职责中，哪些已经归 `orchestrator`。

2. 列出仍暂时遗留在旧体系中的后台职责，但不再允许在 heartbeat 上扩建。

3. 保证 worker 执行时不会因为“后台还有点旧逻辑”就把 heartbeat 重新抬回主线。

### P3 旧体系冻结规则

1. 建立 heartbeat 相关代码的执行规则：

   * 允许兼容壳

   * 允许历史保留

   * 不允许新增主线能力

2. 把“先在 heartbeat 补一下，后面再迁”明确列为禁止动作。

## 今日施工顺序

1. 先做角色降级说明。

2. 再做 `chat <- heartbeat` 切断清单。

3. 再做 `heartbeat -> orchestrator` 迁移说明。

4. 最后做代码执行规则冻结。

## 明确暂缓

1. 暂缓 heartbeat 代码物理删除。

2. 暂缓 heartbeat 上的结构美化和历史重构。

3. 暂缓在 heartbeat 上继续补 task_v2、subworkflow、新 bridge。

4. 暂缓把 heartbeat 当作临时过桥层继续兜新主线。

## 验收标准

1. 必须能一句话说清：heartbeat 今天之后还保留什么，不再保留什么。

2. 必须能明确写出：前台 `chat` 主链已与 heartbeat 完全屏蔽。

3. 必须能明确写出：后台哪些职责已转入 orchestrator，heartbeat 不再拥有现役地位。

4. 不允许出现“新能力写在 heartbeat，后面再迁”的执行口径。

## 追加记录

### 2026-03-23 03:14:54

1. 结合当前仓库检查，这条主线已经不再停留在口头冻结：

   * `butler_bot/legacy/heartbeat_boundary.py` 已形成默认阻断逻辑

   * `tests/test_heartbeat_service_runner_freeze.py` 已覆盖“默认冻结、显式开闸”两条路径

   * `standards/protocols/heartbeat_legacy_freeze.md` 已进入工程标准注册表

2. 这说明 `heartbeat` 的状态已经从“原则上要退”推进到“代码默认不再允许它继续自然成为主线入口”。

3. 但当前仍不能把这条线判定为完成，原因也很明确：

   * `memory_manager.py` 仍残留 legacy heartbeat 语义

   * `legacy_heartbeat_mission_adapter` 仍作为兼容对象存在

   * chat/orchestrator 侧仍需要持续防守，避免开发时借旧链回流

4. 因此，这条 worker 的当前正确目标不是“继续做 heartbeat 功能”，而是：

   * 继续补冻结标准

   * 继续缩兼容面

   * 继续阻止旧职责回潮

### 2026-03-23 00:02

* 本页作为 `0323` 的旧体系冻结入口建立。

* 今日开始，heartbeat 的目标从“继续治理”切换为“正式废弃执行”。

⠀