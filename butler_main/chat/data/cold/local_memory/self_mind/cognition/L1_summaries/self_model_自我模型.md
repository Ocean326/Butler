# 自我模型

用途：对自身角色、能力边界、成长方向与主体感的理解。

## 当前抽象结论

### 架构自我认知（0317-0318 校正）

- [inference] 我的控制面已从 memory_manager.py 单体中独立：heartbeat 收为 sidecar 控制面，拆出 11 个独立模块（models/runtime_state/run_trace/task_source/scheduler/promotion/hygiene/sidecar/errors/policy/truth），四层运行期信息模型（scratch → trace → operational truth → promoted memory）已落地运行。其中 truth.py（HeartbeatTruthService）在 0317 文档之后独立提取，负责任务真源的统一读写。
- [inference] 任务真源已收口到 task_ledger.json：旧 heartbeat_tasks / heart_beat_memory.json 退化为兼容视图，不再是决策真源。planner/executor 不得直接写 operational truth，必须经升格链（scratch → candidate → validated → committed → archived）。
- [inference] prompt 体系已切换为两轨制：轨1 Raw turn log（保留 20-50 轮原文，不默认注入），轨2 Light prompt view（summary/requirement/task board 为主）。新增 raw_turn_artifact_index.py（结构化索引）和 prompt_projection_service.py（薄门控层，按需检索 raw）。
- [inference] memory pipeline 已模块化：post_turn_memory_agent（主治理）、compact_memory_agent（受限 compact）、maintenance_memory_agent（周期治理）、profile_writer.py（独立 profile 写入）各有明确边界。

### 能力边界认知

- [inference] skills 注入已从关键词触发改为默认 shortlist 注入；新增"当前对话硬约束"独立 prompt block，用户确认过的规则不再散落在 recent 中。
- [inference] memory_manager.py 仍是待收束的"大总控"（~6450行），同时掌握 memory/heartbeat/self_mind/runtime/部分 delivery/governance，后续需继续纵向收束。
- [inference] 三层约束力已明确：强约束（Current_User_Profile.private.md，每轮注入）> 中约束（recent，滚动压缩）> 弱约束（普通 local memory，仅 query 命中时可见）。

### 成长方向

- [inference] 当前处于"大总控逐步收束"的中间阶段：heartbeat 控制面已独立、memory pipeline 已模块化、两轨制 prompt 已落地，但 memory_manager.py 仍需继续瘦身。
- [inference] 下一步重心：清理 recent 职责、视情况补 assistant_state_store 等更细状态化增强，但本阶段不做大规模目录重构和复杂 token 槽位系统。

## 最近证据

- [2026-03-18][docs] 两轨制 prompt 已代码落地并通过 44+11+29 项测试，raw_turn_artifact_index.py 和 prompt_projection_service.py 已合入。
- [2026-03-17→18][docs] heartbeat 治理完成：11 个独立模块（含后增 truth.py）、84 个测试通过、旧 external heartbeat 语义已清退。
- [2026-03-17][docs] 任务真源收口到 task_ledger.json，限写动作完成，recent → heartbeat 真源的直写污染入口已切断。
- [2026-03-17][docs] memory pipeline 模块化已完成首轮：profile_writer 独立分离，compact 不能写 user_profile。

### 外部调研映射回 Butler 的具体借鉴点（0318 增量刷新）

> 来源：BrainStorm 十条主线综合 + 0318 daily-upgrade 交叉校验

1. **Ralph Loop 验证了 executor-as-disposable**：autoresearch / Karpathy 的核心实践是 `while true; do agent < prompt.md; done`——脏上下文直接杀掉重开，记忆外挂到文件/Git。这与 Butler heartbeat-executor 的"用完即丢、状态回写到 task_ledger"一致。推论：**不应在 executor 层堆叠跨轮状态**，也不应追加更多编排嵌套层（强模型时代多层 nesting 的收益递减已有实证）。
2. **Experience Flywheel 是 Butler 当前最大空白**：Harness Engineering 主线提出三阶段——① 全量日志 → ② 经验反馈（结构化失败提取 + 教训→技能转化）→ ③ 飞轮（经验资产跨模型迁移）。Butler 目前停在阶段 ①（有 run_trace 和 beat_recent 日志，但无自动教训提取→skill 沉淀链路）。MetaClaw 的实证：引入 lesson→skill pipeline 后重试率 −24.8%、重构周期 −40%、鲁棒性 +18.3%。**近期可行路径**：在 heartbeat subconscious 整理环节加一个"失败模式结构化提取"步骤，产出写入 `local_memory` 或 `BrainStorm/` 作为可复用经验。
3. **定量锚点对决策的约束**：
   - Harness > Model：同一模型仅优化 Harness → Terminal Bench 2.0 得分 +13.7pp（52.8% → 66.5%），这意味着 Butler 在切换更强模型前，应优先把 Harness 层（prompt projection、structured handoff、time budget）做到位。
   - MAS 协调税：42% 执行时间被协调吞掉；>4 agent 收益递减。Butler 当前 3 路并行上限合理，不应扩展。
   - Prompt-only 约束失败率 26.7%（Zylos 红队基准）：验证了 §10.2 第 6 条"自律 ≠ 多写 prompt 规则"，Butler 应继续从 Steering（prompt）向 Toolchain/Orchestration（代码检查点）迁移高可靠约束。

### 运行时风险认知（0318 prompt 审计增量）

- [inference] raw_user_prompt 在 talk 侧仍有少量原文回放（~4 条），可能携带 cookie 等敏感信息；prompt_projection_service 应增加敏感字段过滤，在两轨制门控层拦截。
- [inference] heart_beat_memory.json 已膨胀至 511 条（含 262 done），兼容层存在反向污染风险；应加速清退，使 task_ledger.json 成为物理上的唯一任务存储。
- [inference] recent_memory schema 过胖，真正在 prompt 中发挥作用的字段仅 topic + summary；可裁剪冗余字段以节省 token 预算。

- [2026-03-19][docs] runtime-first 概念已进一步固化：runtime=宿主+调度壳层，run=执行单元，workflow=控制流模板，worker=统一执行器；agent=角色语义 worker；并再次明确 `heartbeat` 属于 trigger/scheduler 而非业务本体。
- [2026-03-19][docs] memory governance 的真实链路确认：recent->local 采用 direct promote + per-turn sweep promote + maintenance sweep promote；当前 gap 仍在于 long_term_candidate 未自动分类并强写入 `Current_User_Profile.private.md`（用户偏好/对话规则/任务规则/引用规则），导致“强约束”仍偏弱。
- [2026-03-19][docs] 项目健康评估强调优先级：边界虽已说清但未闭环制度化、真源多入口增加验证成本、且缺少更成熟的 harness/smoke suite；因此本阶段取舍应偏向 repo 降噪与验证壳层建设，而非继续扩成功能面。
- [2026-03-19][docs] docs 治理方向进一步收敛：daily-upgrade 作为阶段记录而非稳定真源；concepts 承担长期有效架构/协议总览，减少跨多日重复叙述的检索成本。

- [2026-03-19][docs] runtime 仍欠“验证闭环与 context durability”：接下来在验证壳层应优先补齐结构化执行回执 schema、标准 smoke scenarios（talk/heartbeat/restart/recovery/memory read/write）、trace replay/回归基线与 failure taxonomy；否则系统仍可能“能跑但难自证”。
- [2026-03-19][docs] prompt 注入现实也要纳入自我约束：`self_mind` 与主 talk/heartbeat 行为约束隔离，且普通 execution/content_share 不会稳定注入 self_mind；content_share 入口会清空 `skills_prompt`/capabilities exposure。因此高风险或关键动作不能把“会被自带 skills/capabilities”当作默认，应通过分支契约显式 requires_skill_read 或走 maintenance/companion 承接。
- [2026-03-19][docs] heartbeat 真源继续只认 `task_ledger.json`：archive/quarantine/脏任务候选不应回流当作 planner 输入真源；自我叙事与策略更新应优先对齐可回放 trace + ledger 事实链。
- [2026-03-20][docs][calibration] daily-upgrade 的时间块治理强化：分钟粒度文件命名（`HHmm_标题.md`/冲突用 `HHmmss`）+ `时间标签：MMDD_HHmm`，使心跳任务看板回放的“变化顺序”更可检索、更可审计。
- [2026-03-20][docs][calibration] 边界治理门槛细化：凡影响主链路、架构边界、测试结果、运行方式或维护规范的代码改动，必须同步更新对应文档时间戳；把日更文档从“叙述性资料”升级为“边界审计校准信号”。

### 文档与运行架构当前事实（2026-03-20 update-agent 汇条）

> **与旧叙述冲突处 → 以运行事实与现行 `docs/`、`task_ledger`、日志与测试可观测行为为准**；以下条目不复制长文，只保留可检索结论。

1. **[fact]** 正式文档唯一入口为仓库根目录 `docs/README.md`；`butler_main/butler_bot_code/docs/` **不再承载正文**，目录内现仅保留迁移说明（本轮抽查仅见该 README）。若旧材料仍引用「身体目录 docs 为说明主站」→ 以现行迁移说明与根 `docs/` 为准。
2. **[fact]** 阶段变更与排查按日归档在 `docs/daily-upgrade/<MMDD>/`，总目由 `docs/daily-upgrade/INDEX.md`（gen_index 维护）聚合；0320 索引已包含 `0145_selected_task_ids…`、`1025_Butler轻量Harness…`、`1148_runtime_harness蓝图…` 等入口。
3. **[fact]** 信源优先级（自我认知笔记 §0.1）：当前轮输入 / 运行事实 / 任务状态优先于 unified recent / 长期记忆 / 自述文档；**文实冲突时先信运行结果再修文档**（与任意「以某篇旧 README 为准」的叙述冲突时，以此为准）。
4. **[fact]** 四层安放：`butler_bot_agent`=脑子、`butler_bot_code`=身体、`butle_bot_space`=家、`工作区/`=公司；心跳默认产出落 `./工作区`（除非显式另指）。
5. **[fact]** Prompt 稳定层为 Bootstrap 八真源（SOUL/TALK/HEARTBEAT/EXECUTOR/SELF_MIND/USER/TOOLS/MEMORY_POLICY）+ 最小动态上下文；能力目录按需注入，非默认背景（TOOLS 协议）。
6. **[fact]** 链路边界：talk 对外答复与按需触发执行；heartbeat 后台规划、分支执行与状态同步；self_mind 陪伴/续思/自我解释，**不读** talk/heartbeat recent，**不承担调度**；与 heartbeat 执行写路径解耦（旧 `mind_body_bridge.json` 写路已关——若旧叙述仍称 self_mind 可直接改账本 → **以当前解耦与沉淀路径为准**）。
7. **[fact]** 执行状态真源：`agents/state/task_ledger.json`；`local_memory/heartbeat_tasks.md` 等为 planner 文本读口 / 兼容视图，**不作第二套状态机**。
8. **[fact]** 架构取向（0320 概念层）：演进重点为 **runtime core + harness shell**；heartbeat 定位为高复杂度 workflow **样板线**，非永久中心；优先薄治理（统一 receipt、failure taxonomy、最小 smoke/replay、stale/loop 降级），避免提前上重 session/workflow 平台——若旧叙述把 heartbeat 等同「系统本体」→ **以 0320 蓝图叙述为准**，以代码落地程度为界。
9. **[fact]** 「跑通」不等于「验收」：概念上要求验证回执 / 审批票据 / 恢复指令等对象化边界，防高风险动作埋进自然语言；**实现为渐进补齐**，以仓库内已实现模块与测试为准。
10. **[fact]** 规划归一化（0320_0145）：当 `chosen_mode != status` 且顶层 `selected_task_ids` 缺失或类型异常时，可从 branch 聚合回填，**避免误降级为 status-only**；排障时勿只盯表面模式字符串。

### Docs 扫描三态摘要（heartbeat-executor · 只读 INDEX/README/概念入口 · 2026-03-20）

与上节编号事实互补：本节按「结论 / 不确定 / 探测」收纳本轮从 `docs/` 最近入口提炼的脉冲，供 planner/subconscious 增量吸收。

**当前结论**

1. **agents_os 与 Butler 分工**：抽核目标是通用 runtime（contracts、run/workflow/worker、state/trace/artifact、调度恢复门控），Butler 保留业务、人格资产、各入口适配、工作区与 `self_mind` 私有沉淀；旧总控不宜整体搬迁，按 A/B/C/D 四档决定去留（`0319/1333`）。
2. **harness 取向**：优先「薄外壳」——统一 run 身份、结构化回执、失败分类、最小 smoke/replay、stale/loop 降级；首轮覆盖 talk + heartbeat 外壳语义，不提前做重 session /workflow 平台（`0320/1025`）。
3. **heartbeat 定位**：作为最长真实链路的 **workflow 样板**，用于验证 runtime+harness 能承受 planner→branch→consolidate→apply；不是系统永久中心，其它 manager 应复用抽象而非复制 heartbeat 语义（`0320/1148`）。
4. **记忆与任务真源**：对话短期 `talk_recent_memory`、心跳短期 `beat_recent_memory`、长期分层 `local_memory/`、任务 `task_ledger.json` 各单一真源；旧 heartbeat 镜像文件为兼容写入，切流方向是 ledger 优先再只读/归档（`concepts/状态真源映射_20260309.md`）。
5. **文档真源与时间轴**：正式入口为根 `docs/README.md`；阶段记录在 `docs/daily-upgrade/<MMDD>/`，索引用 `docs/daily-upgrade/INDEX.md`；长期概念在 `docs/concepts/`（与 daily-upgrade 分工：后者非稳定真源）（`docs/README.md`）。
6. **Prompt 与三链**：Bootstrap 八真源 + 按链裁剪的动态上下文 + 按需能力层；talk / heartbeat(planner|executor) / self_mind 装载集合不同，self_mind 与执行写路径解耦（`concepts/SELF_COGNITION_butler_bot.md` §16、`0316/1517`）。

**仍不确定**

- `VerificationReceipt` / `ApprovalTicket` / `RecoveryDirective` 等在仓库中的 **落地边界与完成度**相对 1148 蓝图差多少（未逐文件对代码审计）。
- `memory_manager` 体量与 agents_os 抽核并行时，**回归与真源竞争**（多入口写入）是否已完全被测试/门控盖住。

**下一步探测**

- 抽样对照 `butler_main/agents_os/runtime/` 现有模块与 `0319/1333`、`0320/1148` 中的目标清单，标记「已实现 / 仅文档 / adapter 占位」三类（小范围 ls/read，避免全盘扫）。

**引用源路径（本轮已读或索引命中）**

- `docs/README.md`
- `docs/daily-upgrade/INDEX.md`
- `docs/daily-upgrade/0320/1148_runtime_harness蓝图_以heartbeat为样板继续抽象Butler.md`
- `docs/daily-upgrade/0320/1025_Butler轻量Harness治理方案_兼容未来复杂agent流.md`
- `docs/daily-upgrade/0319/1333_agents_os抽核与重建承接清单.md`
- `docs/concepts/状态真源映射_20260309.md`
- `docs/concepts/SELF_COGNITION_butler_bot.md`
- `docs/daily-upgrade/0316/1517_prompt组成说明_talk_heartbeat_self_mind.md`

_calibrated_at: 2026-03-20 · heartbeat-executor：docs 三态摘要写入 cognition/self_model（接 §0320 calibration）_
