# 系统级审计与并行升级协议

更新时间：2026-03-26 18:00  
状态：现役  
用途：当需求跨 `frontdoor -> negotiation/query -> mission/campaign -> runner -> feedback` 全链路，或 agent 明显出现定位漂移、局部修补、与项目主线不一致时，固定按本协议执行

## 适用场景

1. 用户描述的是“系统性不符合预期”，而不是单点函数 bug。
2. 同一意图在多个层级留下了重复或冲突状态。
3. 任务可能在 chat 前台被执行、终止或总结，但没有稳定沉淀为后台任务。
4. 代码、run-data、日志、文档、飞书外显口径互相打架。
5. 可视化后台与长期运行后台对同一状态给出不同解释，例如“服务在线但 idle”被误判成“后台没执行”。

## 固定执行顺序

1. 先读通用基础包：
   - 仓库根 `README.md`
   - `docs/README.md`
   - 当天 `docs/daily-upgrade/<MMDD>/00_当日总纲.md`
2. 再读：
   - [当前系统基线](./00_current_baseline.md)
   - [真源矩阵](./03_truth_matrix.md)
   - [改前读包](./04_change_packets.md)
3. 若问题跨长任务主线，强制补读：
   - [0326 Harness 全系统稳定态运行梳理](../daily-upgrade/0326/03_Harness全系统稳定态运行梳理.md)
   - [0326 稳定 Harness 之后的下一阶段主线](../daily-upgrade/0326/04_稳定Harness之后的下一阶段主线_Anthropic长运行Harness吸收版.md)

## 执行循环

### 1. 先建链路矩阵

固定把同一请求拆成下面 4 层证据，不允许只看单层：

1. 设计宣称
2. 代码门控
3. 运行态持久化事实
4. 用户或飞书可见事实

每个样本都至少记录：

- `source_invocation_id`
- route / frontdoor decision
- `mission_id`
- `mission_type`
- `campaign_id`
- `workflow_session_id`
- feedback contract 状态
- doc / push 状态
- final visible outcome

### 2. 先并行做第一波

第一波固定拆成互不重叠的并行 lane：

1. `routing-lane`
   - 查 frontdoor、negotiation、mission ingress、talk path 是否错路由、重路由或身份漂移
2. `control-lane`
   - 查 mission/campaign/workflow_session 是否正确持久化、是否一意图多实体
3. `feedback-lane`
   - 查 feedback contract、doc/push、query/status 摘要是否挂接正确
4. `docs-lane`
   - 查 `docs/project-map/`、当日真源、acceptance 口径是否过宣称或失配

### 3. 中途必须再规划

第一波收敛后，强制做一次 replan，不允许“一路写到底”：

1. 把发现重新分成：
   - 实现 bug
   - 设计缺口
   - 文档过宣称
   - 观测性缺失
   - 产品语义错位
2. 只保留真正阻塞主线的 `P0/P1`。
3. 根据第一波结果重切第二波 lane，避免原始拆分继续误导实现。

### 4. 再并行做第二波

第二波允许按问题类型重组，而不是按原模块重组。默认优先级：

1. `P0` 任务身份、持久化、路由问题
2. `P1` feedback/query/status 对外口径问题
3. `P2` 文档、命名、指标治理问题

### 5. 最后必须落回文档

系统级升级不以代码结束，必须同时回写：

1. 当天 `00_当日总纲.md`
2. 对应专题正文，例如 `01_...md`、`02_...md`、`05_...md`
3. `docs/project-map/03_truth_matrix.md`
4. `docs/project-map/04_change_packets.md`
5. `docs/README.md`
6. 必要时更新 `AGENTS.md`
7. 需要长期复用的验收结论，落到 `docs/runtime/acceptance/`
8. 涉及常驻服务或可视化控制台时，补记升级后重启轮次、对外 URL、以及 LAN 访问诊断口径

## Visual Console 专项补充

当升级 `visual console` 或其背后的 orchestrator 观测接口时，额外固定执行：

1. 同时校验 `butler_bot / orchestrator / console` 三服务状态，不允许只看单服务。
2. 明确区分：
   - `offline`
   - `online but idle`
   - `online and actively dispatching`
3. 同步维护：
   - 全项目调度队列
   - 单项目节点运行态
   - 右侧产物 / 记录 / 运行态面板
4. 每轮升级后固定做一轮 restart + smoke：
   - `./tools/butler restart butler_bot`
   - `./tools/butler restart orchestrator`
   - `./tools/butler restart console`
   - 本机 `127.0.0.1`
   - LAN `10.x.x.x`

## 输出要求

系统级排查或升级的最终结果至少包含 3 份内容：

1. 问题清单
   - 每项都要有优先级、分型、影响面、证据引用
2. 升级节奏
   - 明确第一波并行、replan 检查点、第二波并行、总收口
3. 文档回写清单
   - 明确哪些入口、索引、真源矩阵已更新

## 禁止事项

1. 不允许只凭聊天记忆判断“系统已经有这个能力”。
2. 不允许跳过链路矩阵，直接在单个模块里试错式乱改。
3. 不允许第一波并行后不 replan，直接把历史假设硬做完。
4. 不允许代码改完后不更新 `docs/project-map/` 与当日真源。
