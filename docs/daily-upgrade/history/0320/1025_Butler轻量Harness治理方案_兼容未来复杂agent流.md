# Butler 轻量 Harness 治理方案（兼容未来复杂 agent 流）

更新时间：2026-03-20 10:25
时间标签：0320_1025

## 一、为什么现在做这个方案

当前 Butler 已经有：

- heartbeat 的单一控制面
- task ledger 为核心的任务真源
- talk 的 active rules / skill shortlist 治理
- 初步成形的 `agents_os` runtime core

但当前真正的短板不是“再加一层更复杂的治理系统”，而是：

1. 主链路缺统一结构化回执
2. 缺最小 smoke baseline
3. 缺统一 failure taxonomy
4. 缺最小 loop / stale 自动降级
5. 缺一层可重复验证的轻壳

所以本方案的目标不是把 Butler 立刻做成“大而全 Harness 平台”，而是：

> **先给现有 talk + heartbeat 套上一层轻量、统一、可验证的 Harness 治理壳；同时给未来更复杂 agent 流保留扩展缝。**

---

## 二、结论先行

### 2.1 当前阶段的总判断

对 Butler 现在的主链路来说，最合适的不是重治理，而是：

- **轻协议**
- **轻验证**
- **轻降级**
- **轻回放**

也就是说：

1. 不急着把 `talk / heartbeat / self_mind / future managers` 全部抽成复杂 runtime 平台
2. 先把当前最常跑、最重要的两条链路——`talk` 和 `heartbeat`——治理成“结构统一、可测、可退”
3. 未来若接入更复杂的 agent team / planner-executor / multi-manager，再沿着预留接口升级

### 2.2 一句话方案

> **现在做一个“thin harness shell”：统一 run 入口语义、统一 receipt、统一失败分类、统一 smoke/replay 基线；但不提前做重 session 平台、重 workflow 引擎、重 dashboard。**

---

## 三、治理范围

本轮轻量 Harness 治理只覆盖：

1. `talk` 主链路
2. `heartbeat` 主链路

本轮只要求它们在“运行治理层”上讲同一种语言，不要求它们共享所有业务逻辑。

### 3.1 talk 侧纳入治理的部分

- 输入进入 runtime 前的最小上下文装配结果
- skill / rule / recent 注入后的最终执行请求
- 运行结果回执
- 失败分类
- 最小 trace

### 3.2 heartbeat 侧纳入治理的部分

- planner 选择结果
- executor 分发结果
- selected / deferred / completed 等结构化结果
- tell_user 候选意图
- 降级与回退原因
- 最小 trace

### 3.3 本轮明确不纳入的部分

- 复杂 dashboard
- 跨 manager 运营分析
- 全量 context compaction 平台重构
- 通用多 agent 编排平台
- 很重的 policy engine

---

## 四、核心设计原则

### 4.1 只治理“共同外壳”，不强行统一业务内核

当前 talk 和 heartbeat 的业务形态不同：

- talk 是前台交互链路
- heartbeat 是后台调度链路

因此本轮不要强行把两者做成一个 workflow 模板，只需要统一：

1. run identity
2. receipt
3. failure taxonomy
4. trace skeleton
5. smoke baseline

### 4.2 先让系统“可验证”，再让系统“更聪明”

本轮的第一优先级不是：

- 更复杂的 planner
- 更强的 agent 自主性
- 更大的多 agent 编排能力

而是：

- 退化时能快速发现
- 卡住时能快速分类
- 重构后能快速回归
- 出问题时能快速定位

### 4.3 当前复杂度只增在协议层，不增在调度层

允许新增：

- dataclass / schema
- trace event type
- smoke fixtures
- failure class
- loop detection 规则

不建议新增：

- 新的心跳模式分支
- 新的 talk 模式大分叉
- 第二套任务真源
- 第二套长期运行控制面

### 4.4 所有新设计都必须留扩展缝，但默认不用

未来可能会有：

- planner-executor workflow
- team / sub-agent workflow
- manager of managers
- 更强 session continuity

所以接口可以保留字段，但当前实现必须保持：

- 默认简单
- 默认可空
- 默认不启用

---

## 五、轻量 Harness 的最小统一模型

本轮建议不要一口气上完整 runtime 平台，而是只定义一层“统一外壳对象”。

## 5.1 统一 Run 类型

建议先只支持两类：

1. `talk_turn`
2. `heartbeat_round`

它们都可以共享以下最小字段：

- `run_id`
- `run_type`
- `session_id`（可空）
- `manager_id`
- `started_at`
- `status`
- `goal`
- `context_refs`
- `policy_flags`

其中：

- `talk_turn` 的 `goal` 通常是“回应当前用户请求”
- `heartbeat_round` 的 `goal` 通常是“完成本轮后台调度/执行/同步”

### 5.1.1 为什么现在不强推重 session

`session_id` 可以先保留，但当前允许：

- talk 复用现有对话连续性
- heartbeat 只按 run 粒度工作

也就是说：

> **先保留 session 位，但不要求当前所有链路都成为强持久化 session。**

## 5.2 统一 AcceptanceReceipt

建议为 talk 和 heartbeat 共用最小回执结构：

- `goal_achieved: bool`
- `summary: str`
- `evidence: list[str]`
- `artifacts: list[str]`
- `uncertainties: list[str]`
- `next_action: str`
- `failure_class: str`

其中：

- talk 的 `evidence` 可以是“命中的规则、调用的 skill、生成的回复类型”
- heartbeat 的 `evidence` 可以是“selected tasks、completed branches、写入 ledger 的结果”

### 5.2.1 关键约束

不要再把“是否完成”主要埋在自然语言文本里。  
后续无论是 smoke、replay 还是自动降级，都优先读 receipt。

## 5.3 统一 Failure Taxonomy

当前建议先只固化最小集合：

- `policy_blocked`
- `context_missing`
- `worker_error`
- `tool_error`
- `acceptance_failed`
- `stale_loop`
- `invalid_plan`
- `degraded_status_only`

说明：

- `degraded_status_only` 对 heartbeat 特别重要
- `context_missing` 对 talk 特别重要
- 未来可以扩展，但当前不要一次做太细

## 5.4 统一 Trace Skeleton

不要求 talk 和 heartbeat 记录完全一样的全文 trace；只要求至少都有：

- `run_started`
- `context_prepared`
- `guardrail_checked`
- `worker_dispatched`
- `receipt_emitted`
- `run_completed` / `run_failed`

heartbeat 可额外记录：

- `plan_normalized`
- `degrade_status_only`
- `branch_completed`

talk 可额外记录：

- `skills_selected`
- `rules_applied`
- `reply_generated`

---

## 六、按链路拆开的落地方案

## 6.1 Talk 轻治理方案

talk 这边不需要更复杂的 agent runtime，先做这 4 件事：

1. 为每次 talk 输出统一 `AcceptanceReceipt`
2. 记录是否命中了 active rules / skills shortlist / local memory
3. 若未命中预期能力或上下文缺失，回填 `failure_class`
4. 建立 talk smoke case

### 6.1.1 Talk smoke 最小集合

- 正常用户提问 → 正常回复 → receipt 完整
- 命中 skill 语义 → skill shortlist / 强提醒生效
- 命中“当前对话硬约束” → receipt 中有 evidence
- 上下文不足 → `context_missing`
- 高风险能力未命中或不可用 → 明确失败分类，不伪装成功

### 6.1.2 Talk 当前不要做的事

- 不要把 talk 强行改成多 worker workflow
- 不要把用户画像、recent、rules 再拆成第二套真源
- 不要为了 harness 再增加很多 prompt 模式

## 6.2 Heartbeat 轻治理方案

heartbeat 这边不需要再加新的调度复杂度，先做这 5 件事：

1. planner / executor 统一输出 `AcceptanceReceipt`
2. 让 `selected_task_ids / complete_task_ids / defer_task_ids` 成为 receipt 证据的一部分
3. 把当前 degrade / fallback 归到 failure taxonomy
4. 做最小 loop / stale guard
5. 建立 heartbeat smoke case

### 6.2.1 Heartbeat smoke 最小集合

- 正常选任务并执行成功
- 无显式任务，进入 `status-only`
- planner 非法输出，正确降级
- guardrail / policy 拦截
- 连续重复无产物，触发 `stale_loop`

### 6.2.2 Heartbeat 当前不要做的事

- 不要引入第二套 heartbeat 生命周期
- 不要让 trace 反向驱动 truth
- 不要把 archive / quarantine 再喂回 planner
- 不要为了 harness 再造一层复杂 planner manager

---

## 七、最小 Loop / Stale 治理

当前 Butler 确实需要 loop detection，但只需要最小闭环。

建议先用 2 条简单规则：

### 7.1 Heartbeat loop 规则

如果连续 N 次满足：

- 同类 `chosen_mode`
- 相近 `selected_task_ids`
- 无新增 artifact / 无 ledger 增量 / 无明确 completion

则标记：

- `failure_class = stale_loop`
- 自动降级为更保守模式（例如 `status-only` 或停止继续主动推进）

### 7.2 Talk stale 规则

如果连续 N 次满足：

- 同类请求被重复识别
- 回复结构无明显增量
- 明显缺上下文或缺能力

则标记：

- `failure_class = context_missing` 或 `stale_loop`
- 提示需要更多上下文、确认或能力补齐

### 7.3 当前不要做的 loop 治理

- 不做复杂图分析
- 不做通用策略引擎
- 不做大规模历史聚类

先把“明显卡住时别继续假装推进”做好。

---

## 八、给未来复杂 agent 流保留的设计空余

本方案不是否定未来复杂 agent 流，而是要求：

> **扩展点先留着，但默认不要把当前系统拖进去。**

## 8.1 预留字段，但默认可空

建议在统一协议层预留以下字段：

- `workflow_kind`
- `parent_run_id`
- `child_run_ids`
- `session_id`
- `artifact_refs`
- `policy_decisions`
- `delegation_summary`

当前要求：

- talk / heartbeat 可以只填其中很少一部分
- 不需要为了“字段完整”造假数据

## 8.2 预留 workflow 升级缝

当前默认只需要：

- `single_turn`
- `planner_executor`

未来若上复杂 agent 流，再扩：

- `team_parallel`
- `manager_worker`
- `review_revise`
- `long_horizon_session`

但这些名字现在只需要保留概念，不需要落成重实现。

## 8.3 预留 policy middleware 缝

当前只做最小 guardrail / approval / provider policy。  
未来复杂 agent 流可能需要：

- budget policy
- capability allowlist
- artifact promotion policy
- external side-effect policy

所以现在建议：

- 统一 policy decision 的记录位置
- 但不要现在就上复杂 middleware 链

## 8.4 预留 replay / baseline 扩展缝

当前只要求：

- 典型 talk case 可 replay
- 典型 heartbeat case 可 replay

未来复杂 agent 流再扩展为：

- parent-child run replay
- multi-branch replay
- acceptance-by-stage replay

所以 trace 只需保证最小骨架完整。

---

## 九、本轮建议的实施顺序

### P0：先把协议立住

1. 定义统一 `AcceptanceReceipt`
2. 定义最小 `FailureTaxonomy`
3. 统一 talk / heartbeat 的最小 trace skeleton

### P1：再把验证壳补上

4. 增加 talk smoke cases
5. 增加 heartbeat smoke cases
6. 增加最小 replay 读取能力

### P2：最后补最小自动治理

7. 增加 loop / stale detection
8. 增加自动降级钩子
9. 把关键结果纳入回归 baseline

### P3：保留未来接口，不急着实现

10. 预留 workflow_kind / parent-child run / session_id
11. 预留 policy_decisions / artifact_refs
12. 预留复杂 manager 接入规范

---

## 十、验收标准

本轮“轻量 Harness 治理方案”完成，不以“文件多了多少”为标准，而以以下结果为标准：

1. talk 与 heartbeat 都能产出统一结构化 receipt
2. 两条主链都有可重复运行的 smoke cases
3. 失败不再主要依赖自由文本判断
4. 至少能识别一类明显 stale / loop
5. 出问题时能通过 trace 快速重建关键路径
6. 新增字段和接口不会强迫当前链路走复杂 runtime

---

## 十一、最后的判断

对当前 Butler 来说，正确路线不是：

- 继续堆更复杂的治理结构
- 提前做重型 agent runtime 平台
- 为未来复杂场景过度设计当前系统

而是：

> **用一层轻量 Harness 壳，把现有 talk + heartbeat 治理成“统一、可测、可退”；同时给未来复杂 agent 流留下自然扩展位。**

这条路线的好处是：

1. 不打断当前已跑通的业务主链
2. 不把 heartbeat / talk 再次复杂化
3. 能快速提升可验证性和回归稳定性
4. 未来升级复杂 agent 流时，不需要推翻当前方案，只需沿预留接口渐进扩展
