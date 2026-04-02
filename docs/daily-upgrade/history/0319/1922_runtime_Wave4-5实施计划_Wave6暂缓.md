# 0319 runtime Wave4-5 实施计划（Wave6 暂缓）

更新时间：2026-03-19 19:22
时间标签：0319_1922

## 一、范围说明

基于 `docs/daily-upgrade/0319/1648_runtime阶段性总结与后续治理计划.md`，下一阶段先聚焦：

- **Wave 4：Runtime 协议固化**
- **Wave 5：Harness 验证壳层建设**

`Wave 6`（Governance / 经验飞轮）先不作为当前主攻方向，只保留接口和文档占位，不提前做重资产建设。

一句话：

> 先把 runtime 语言定死、把验证闭环补齐，再谈经验飞轮和治理资产化。

---

## 二、当前起点

当前 Butler 已有基础：

- `agents_os/runtime/contracts.py`：最小 run/session/result 数据结构
- `agents_os/runtime/kernel.py`：最小 dispatch / guardrail / context / trace 闭环
- `agents_os/state/*`：file-backed state / trace store
- `agents_os/tasking/task_store.py`：任务真源协议
- `butler_bot/agents_os_adapters/*`：Butler manager-local adapter
- `tests/test_agents_os_runtime.py`、`tests/test_agents_os_wave2_adapters.py`、`tests/test_agents_os_wave3_manager_bootstrap.py`

当前主要缺口：

1. run state 语言不够统一
2. session / workflow / acceptance 还没固化成正式协议
3. 执行结果缺少结构化回执 schema
4. 缺标准 smoke scenarios / replay / failure taxonomy
5. 缺 loop detection / 自动降级这类 harness 中间件

---

## 三、总策略

### 3.1 先协议，后能力

Wave 4 先做“语言统一”，确保后续所有验证与回放都站在统一结构上。

### 3.2 先最小闭环，后大全家桶

Wave 5 只补最关键的验证壳：

- smoke scenarios
- structured acceptance receipt
- replay-ready trace
- loop / stale detection

不先做仪表盘、经验库、复杂多 manager 统计平台。

### 3.3 新增逻辑优先落在 runtime core 或测试壳，不回流黑洞文件

尤其避免把新协议、新状态、新验证逻辑塞回：

- `memory_manager.py`
- `heartbeat_orchestration.py`
- 某个 manager 的临时大文件

---

## 四、Wave 4：Runtime 协议固化

目标：**把当前“能跑的最小 runtime”提升为“大家都讲同一种运行时语言”的正式 runtime。**

## 4.1 子目标 A：统一 run 生命周期状态字典

### 要解决的问题

当前 `Run.status`、`RunResult.status`、trace event 和 manager 侧状态表述仍可能漂移。

### 要做的事情

1. 在 `agents_os/runtime/contracts.py` 中固化状态集合
2. 明确最小状态字典，例如：
   - `pending`
   - `running`
   - `blocked`
   - `failed`
   - `completed`
   - `cancelled`
   - `stale`
3. 明确每个状态的允许来源和迁移规则
4. 让 `kernel.py` 和 adapter 层统一使用该字典

### 建议落点

- `butler_main/agents_os/runtime/contracts.py`
- `butler_main/agents_os/runtime/kernel.py`
- `butler_main/agents_os/state/models.py`
- `butler_main/butler_bot_code/tests/test_agents_os_runtime.py`

### 完成标志

- runtime core 内不再出现散装状态字符串
- 测试中能验证合法状态迁移和非法状态拒绝

## 4.2 子目标 B：固化结构化执行结果协议

### 要解决的问题

当前 `RunResult` 和 `WorkerResult` 还偏轻，适合最小闭环，但不够支撑 acceptance / replay / planner 再规划。

### 要做的事情

1. 为 `WorkerResult` / `RunResult` 增加结构化字段，而不是只依赖 `output` 和 `message`
2. 建议补充：
   - `acceptance`
   - `artifacts`
   - `next_action`
   - `uncertainties`
   - `failure_class`
   - `metrics`
3. 定义 `AcceptanceReceipt` / `ExecutionReceipt` 一类 dataclass
4. 明确哪些字段属于 runtime 通用协议，哪些字段只能进 manager metadata

### 建议落点

- `butler_main/agents_os/runtime/contracts.py`
- `butler_main/agents_os/runtime/kernel.py`
- `butler_main/butler_bot_code/tests/test_agents_os_runtime.py`
- 新增 `butler_main/butler_bot_code/tests/test_agents_os_protocols.py`

### 完成标志

- 单个 worker 返回的不再只是“完成/失败”，而有统一 receipt
- planner / adapter 可以用统一字段读取结果，而不是猜 output 结构

## 4.3 子目标 C：补 session 持久化语义

### 要解决的问题

现在 `Session` 还是轻数据结构，缺少持久化协议和恢复边界。

### 要做的事情

1. 定义 `SessionStore` protocol
2. 明确 session 与 context store 的关系
3. 明确 session 元数据最小字段：
   - `session_id`
   - `topic`
   - `owner/manager_id`
   - `created_at`
   - `last_run_id`
   - `status`
4. 明确 session 生命周期：create / resume / archive / close

### 建议落点

- `butler_main/agents_os/runtime/contracts.py`
- 新增 `butler_main/agents_os/runtime/session_store.py` 或并入 `state/`
- `butler_main/butler_bot_code/tests/test_agents_os_runtime.py`

### 完成标志

- session 不再只是“有这个字段”，而是正式可恢复容器
- 新 manager blueprint 能说明 session 如何保存和续跑

## 4.4 子目标 D：固化 workflow contract

### 要解决的问题

当前默认只有 `single_worker`，workflow 作为概念存在，但还未真正成为 runtime 一级扩展点。

### 要做的事情

1. 明确 workflow protocol 输入输出边界
2. 至少内建 2 个正式 workflow：
   - `single_worker`
   - `planner_executor` 或 `manager_worker`
3. 规定 workflow 负责什么、不负责什么
4. 明确 workflow trace event 的最小规范

### 建议落点

- `butler_main/agents_os/runtime/kernel.py`
- 新增 `butler_main/agents_os/runtime/workflows.py`
- `butler_main/butler_bot_code/tests/test_agents_os_runtime.py`
- 新增 `butler_main/butler_bot_code/tests/test_agents_os_workflows.py`

### 完成标志

- workflow 不再只是字段，而是正式注册、执行、追踪对象
- manager 可切换 workflow，而不是硬编码执行序列

## 4.5 子目标 E：manager blueprint 协议升级

### 要解决的问题

当前 manager bootstrap 已有雏形，但对 contract completeness 的校验还可以更强。

### 要做的事情

1. 为 `ManagerBlueprint` 增加更严格的 validate 规则
2. 明确 manager 至少需要：
   - prompts surface
   - interface surface
   - adapter surface
   - workspace root
   - session policy
   - runtime policy
3. 明确哪些是必需、哪些可选
4. 让新 manager 的“快速启动”真正可由 contract 驱动

### 建议落点

- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/manager_blueprint.py`
- `butler_main/butler_bot_code/tests/test_agents_os_wave3_manager_bootstrap.py`

### 完成标志

- 新 manager 缺协议时，validate 会明确失败
- blueprint 真正成为 manager 接 runtime 的标准入口

## 4.6 Wave 4 验收标准

Wave 4 完成的标志不是“文件更多”，而是满足下面 6 条：

1. runtime 状态字典统一且可测试
2. receipt / acceptance / failure_class 有正式协议
3. session 有最小持久化语义
4. workflow 成为一级扩展点
5. manager blueprint 校验强化
6. 所有新增协议有配套单测

---

## 五、Wave 5：Harness 验证壳层建设

目标：**让 runtime 从“结构正确”升级为“可重复验证”。**

## 5.1 子目标 A：结构化回执与 acceptance 壳层

### 要解决的问题

当前执行回执偏文本，不利于自动验收和再规划。

### 要做的事情

1. 定义统一 `AcceptanceReceipt`
2. 最小字段建议：
   - `goal_achieved: bool`
   - `summary: str`
   - `evidence: list[str]`
   - `artifacts: list[str]`
   - `uncertainties: list[str]`
   - `next_action: str`
   - `failure_class: str`
3. 让关键 manager adapter 能回填该结构
4. 让测试能直接断言 acceptance 字段，而不是断言自然语言文本

### 建议落点

- `butler_main/agents_os/runtime/contracts.py`
- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/*`
- 新增 `butler_main/butler_bot_code/tests/test_agents_os_acceptance.py`

## 5.2 子目标 B：标准 smoke scenarios

### 要解决的问题

现在有单测，但缺一组“从运行时角度看关键主链是否活着”的标准场景。

### 要做的事情

建立最小 smoke set：

1. `talk` 请求 → adapter → runtime → receipt
2. heartbeat 取任务 → 调度 → worker dispatch → receipt
3. blocked guardrail 场景
4. recovery / resume 场景
5. context update / session continuity 场景

### 建议落点

- 新增 `butler_main/butler_bot_code/tests/test_runtime_smoke_scenarios.py`
- 需要时可补 `tests/fixtures/runtime_cases/`

### 完成标志

- 运行 smoke set 即可快速判断 runtime 主链是否退化
- 每次较大重构前后都能复跑

## 5.3 子目标 C：trace replay 能力

### 要解决的问题

当前 trace 主要是记录，不方便回放和复盘。

### 要做的事情

1. 规范 trace event 种类
2. 明确 replay 所需最小信息：
   - run id
   - worker dispatch
   - guardrail decision
   - worker result summary
   - state transitions
3. 给 trace store 增加 replay-friendly 读取接口
4. 增加至少一个 replay 测试

### 建议落点

- `butler_main/agents_os/state/trace_store.py`
- `butler_main/agents_os/state/models.py`
- 新增 `butler_main/butler_bot_code/tests/test_agents_os_trace_replay.py`

### 完成标志

- 至少一条典型 run 能通过 trace 重建关键执行路径
- debug 不再完全依赖人工读全文日志

## 5.4 子目标 D：failure taxonomy 与 loop detection

### 要解决的问题

当前失败更多是字符串化错误，不利于自动治理。

### 要做的事情

1. 定义 failure taxonomy，例如：
   - `policy_blocked`
   - `worker_error`
   - `tool_error`
   - `stale_loop`
   - `acceptance_failed`
   - `context_missing`
2. 在 runtime / adapter 里回填 failure class
3. 增加最小 loop detection：
   - 同一 worker + 同类 payload + 无有效产物重复 N 次
   - trace 中连续无增量回执
4. 增加自动降级策略钩子

### 建议落点

- `butler_main/agents_os/runtime/contracts.py`
- `butler_main/agents_os/runtime/kernel.py`
- `butler_main/agents_os/state/trace_store.py`
- 新增 `butler_main/butler_bot_code/tests/test_agents_os_failure_modes.py`

### 完成标志

- 失败不再只是 `failed`，而有可统计分类
- 至少能发现一类明显死循环并中断

## 5.5 子目标 E：最小 regression baseline

### 要解决的问题

目前缺“做完改造后如何证明没有退化”的最小基准。

### 要做的事情

1. 在 `tests/fixtures/` 或 `docs/` 里建立最小 runtime cases
2. 固定 3~5 条典型 case：
   - 正常完成
   - guardrail 拦截
   - worker 报错
   - context 延续
   - stale / loop
3. 每条 case 有预期 receipt 和预期 trace 片段

### 建议落点

- `butler_main/butler_bot_code/tests/fixtures/runtime_cases/`
- `butler_main/butler_bot_code/tests/test_runtime_smoke_scenarios.py`
- `butler_main/butler_bot_code/tests/test_agents_os_trace_replay.py`

### 完成标志

- 回归验证从“临时想一个例子试试”升级为“跑固定 baseline”

## 5.6 Wave 5 验收标准

Wave 5 完成的标志是满足下面 6 条：

1. 执行回执统一结构化
2. 有最小 smoke scenarios 集
3. trace 可支持最小 replay
4. failure taxonomy 落地
5. loop detection 最小闭环可用
6. 有固定 regression baseline

---

## 六、Wave 4 与 Wave 5 的推荐顺序

### 第一阶段：先打协议地基

1. 统一 run state
2. 补 execution / acceptance receipt
3. 补 session store / workflow contract
4. 强化 manager blueprint validate

### 第二阶段：再建验证壳

5. 上 smoke scenarios
6. 上 trace replay
7. 上 failure taxonomy
8. 上 loop detection / auto fallback

### 第三阶段：最后做主链接入

9. 选择 Butler heartbeat 主链接入 structured receipt
10. 选择一个新 manager blueprint 做快速接入验证

顺序上不要反过来：  
不要先做复杂 replay，再回头改协议；那样会把旧临时结构固化下来。

---

## 七、当前明确不做的事（Wave 6 暂缓）

为了防止范围失控，以下事项先不作为当前主攻：

1. 大规模经验案例库平台化
2. 运行时 dashboard / Web 仪表盘
3. 复杂的跨 manager 运营分析
4. 大而全的动态 action space 引擎
5. 完整的 context compaction 平台化重构
6. 全仓库级熵增治理系统

这些事情不是不重要，而是必须建立在 Wave 4/5 完成之后。  
当前只允许：

- 为它们预留协议字段
- 在文档中预留边界
- 避免写死将来扩展方向

---

## 八、建议的近期交付拆分

如果按 2 个短周期推进，建议这样拆：

### Sprint A：Wave 4

- 统一状态字典
- 定义 execution / acceptance receipt
- session store 最小实现
- workflow contract + 第二个 workflow
- blueprint validate 强化
- 补对应单测

### Sprint B：Wave 5

- smoke scenarios
- trace replay
- failure taxonomy
- loop detection
- regression baseline
- heartbeat 主链接入一条 structured receipt

---

## 九、最小完成定义

如果要判断“Wave 4/5 算不算真的做完”，最低标准应该是：

1. 一个新 manager 可以靠 blueprint + adapter 起起来
2. 一次 run 可以产出结构化 receipt
3. 一条 trace 可以回放关键执行路径
4. 一类死循环可以被自动识别并降级
5. 一组固定 smoke case 可以证明主链没坏

只要这五件事成立，Butler runtime 才算真正进入：

> **从 runtime core 雏形迈向 Harness Runtime 骨架完备期。**

---

## 十、主题标签

`#RuntimeWave4` `#RuntimeWave5` `#HarnessVerification` `#RunProtocol` `#AcceptanceReceipt` `#TraceReplay` `#FailureTaxonomy`
