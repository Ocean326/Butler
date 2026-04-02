# 风险边界

用途：记录需要守住的执行禁区、长期风险来源，以及在不确定性下的默认取舍策略。

## 当前风险与禁区（0319）

- 边界未闭环：虽然 docs 已给出 `runtime / session / run / workflow / worker / agent` 等分层，但仓库实现与验证基线仍处在过渡态；多个真源/兼容层会抬高定位与验证成本。
- 强约束偏弱：`memory governance` 的 recent->local 已形成 direct promote + per-turn sweep + maintenance sweep，但 long_term_candidate 尚未自动分类并强写入 `Current_User_Profile.private.md`，导致“用户画像偏好/对话规则/任务规则/引用规则”仍可能停留在普通 local memory。
- harness 不成熟：项目健康评估指出缺少更成熟的 harness/smoke suite 把“能解释自己”转为“能稳定验证自己”；因此本阶段优先做 repo 降噪与验证壳层建设，而非继续扩成功能面。
- docs 可能变噪：daily-upgrade 若不再被严格定义为阶段记录，易与 concepts 的稳定协议/总览页发生“当前有效性分叉”；需要把“当前有效总览/当前有效协议”作为低成本入口持续维护。
- 自我通道隔离风险：self_mind 注入更偏“陪伴/反思通道”而非主链路行为约束；普通 execution 或默认模式不保证稳定注入 self_mind，因此自我策略更新不能指望 self_mind 自动参与主 guardrails。
- content_share 裁剪风险：content_share 入口可能清空 `skills_prompt` / `agent_capabilities` exposure，导致关键动作在“用户看似在分享内容”时缺少 required skill/capability；关键动作需显式写 `requires_skill_read` 或走 maintenance/companion 承接。

## 本日校准（0320）
- daily-upgrade 治理增强“可回放顺序”：文件名默认使用 `HHmm_标题.md`（同一分钟多份用 `HHmmss_标题.md`），并在日更文档头部补充 `时间标签：MMDD_HHmm`；这降低心跳任务看板回顾时的时间歧义与跨日混淆。
- 当日持续变更按时间块追加：优先把持续更新追加到当日现状文档，而不是只改“最终结论”；保证执行链路可按顺序重放，减少顺序不确定性引发的误归因。
- 边界审计门槛更明确：当后续代码改动影响主链路、架构边界、测试结果、运行方式或维护规范时，必须同步更新对应文档时间戳；否则将把该信息视为“边界未闭环”，优先回归最近一次时间戳对齐的文档作为真源索引。

## 本轮默认取舍

遇到外部依赖或需要重启的改动时，默认延后；能在不改动关键代码/配置前提下完成的维护（索引更新、真源说明、验证入口补齐）优先做，以降低后续不确定性与回归风险。

## 0320 文档入口与身体改动闸门（增量）

- **文档真源错位风险**：若仍从 `butler_main/butler_bot_code/docs/` 找「正文」，会与运行约定冲突——**以根目录 `docs/README.md` 与 `docs/daily-upgrade/INDEX.md` 为准**；身体目录 `docs/` 仅迁移说明。**与旧叙述冲突 → 以现行索引与迁移 README 为准。**
- **身体层改动闸门**：涉及 `butler_main/butler_bot_code` 下须改代码/配置或须进程重启的升级，心跳分支侧**不得静默直改**；应走统一审批产物（例如工作区 `heartbeat_upgrade_request.json`）由聊天主进程接手——避免执行链与真源状态脱节。

