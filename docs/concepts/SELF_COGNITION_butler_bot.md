---

## 16. 当前认知小结：Bootstrap 与三条链（2026-03-16）

- **Bootstrap 真源分层已经落地**：以 `SOUL/TALK/HEARTBEAT/EXECUTOR/SELF_MIND/USER/TOOLS/MEMORY_POLICY` 八个真源文件为稳定层，talk / heartbeat / self_mind 的 prompt 组装统一改为「bootstrap 稳定层 + 最小动态上下文」，能力目录与技能说明不再直接写死在代码字符串里，而是通过 TOOLS/MEMORY_POLICY 约束装载。
- **Talk / Heartbeat / Self-Mind 三条链的边界被重新划清**：talk 负责对外回答与按需触发执行，重点做减法与按需加载；heartbeat 负责后台规划、分支执行与状态同步，planner 强调模板真源与瘦身，executor 强调执行契约与 `role/output_dir` 约束；self_mind 收敛为陪伴/观察/续思与自我解释层，不再读取 talk/heartbeat recent，不再承担调度职责。
- **Heartbeat planner / executor 的 prompt 组成改为模板真源优先**：planner 由 `heartbeat-planner-prompt.md` + bootstrap HEARTBEAT/TOOLS/MEMORY_POLICY 驱动，代码只硬性补 `json_schema`、`tasks_context`、`context_text` 三块，不再因为模板缺 slot 就自动把 skills/teams/public library 补进去；executor/branch prompt 固定由 workspace hint、执行角色、流程角色、协作协议、自我更新协议、heartbeat 执行协议、运行时路由、回执约定与当前 branch 任务组成。
- **memory_manager 的目标从“总黑洞”转向“轻量 orchestrator”**：近期文档明确提出继续外提四块重职责（HeartbeatPlanningFacade、TellUserFlowService、SelfMindCognitionService、RuntimeStateAuditService），并优先统一 `tell_user/message delivery` 真源，由单一发送服务负责 interactive/post/text fallback 与发送审计，planner 只产候选意图与心跳窗口说明。
- **Self-Mind 与 Heartbeat 在执行层彻底解耦**：self_mind 对 talk/heartbeat 只读，旧 `mind_body_bridge.json` 写通路已关闭，重动作默认沉淀在 `./工作区/03_agent_upgrade/self_mind_agent_space/` 一类私有空间，由 heartbeat / task_ledger 再决定是否接入正式执行链；self_mind 的决策空间从 `talk|heartbeat|hold` 收敛为 `talk|agent|hold`，目录规划为 state/streams/views 三层以控制 `current_context.md` 噪音。
- **任务真源与主动汇报链路的单一来源被再次强调**：统一执行状态真源为 `agents/state/task_ledger.json`，`heartbeat_tasks.md` 只是 planner 的文本看板读口；planner 主动汇报被定义为「user_message + tell_user_candidate + intention + 下一轮 continue + 统一发送服务」的完整闭环，后续会通过 run_id/audit trace 与回归测试保证“谁决定了这句话、为什么发、从哪条链发出”都可追踪。
- **记忆与 prompt 装载从“文本堆叠”升级为“结构化 context policy”**：recent 注入的目标形态是作为独立的结构化 context block 由 compose service 控制是否装载，而不是继续在 `user_prompt` 字符串尾部拼长段解释性文本；MEMORY_POLICY 明确不同会话允许读哪些记忆、哪些视为噪音，防止 talk/heartbeat/self_mind 互相污染。
- **能力与 skills 管理改为显式引用制**：skills、sub-agent、team、公用能力库不再视为默认背景，只有在用户文本、当前任务或 runtime 明确命中时才注入；同时通过 TOOLS 协议约束「只有真实执行过的工具/技能才允许在回复中说已经用了」，减少能力目录幻觉与“播报自己要去干什么”的退化倾向。
# Butler Bot 自我认知笔记

> **用途**：本 AI（管家 bot / 飞书工作站侧）对自身代码库的职责、入口、记忆与调用链、与 Cursor/飞书衔接的认知，供自我进化与后续改进参考。  
> **创建**：2026-03-08（主动探索型心跳·自我认知一小步）  
> **代码根**：身体目录 `Bulter/butler_bot_code/`  
> **与 agent 侧对齐**：2026-03-10 架构重构后，脑子侧共识见 `butler_bot_agent/agents/local_memory/人格与自我认知.md` 第 8 节及 `L1_summaries/架构重构后自我认知更新_20260310.md`。

---

## 0. 自我系统四层模型

重构后，Butler 默认按下面四层理解自己：

- **agent 是脑子**：`Bulter/butler_bot_agent/`，负责角色、规则、工作流、记忆读取、任务分派与方法论。
- **code 是身体**：`Bulter/butler_bot_code/`，负责飞书收发、心跳、守护、日志、配置、测试与运行时健康。
- **space 是家**：`Bulter/butle_bot_space/`，负责生活痕迹、备份、探索笔记、心跳相关沉淀与恢复材料。
- **工作区是公司**：`Bulter/工作区/`，负责用户任务、研究管理产出、治理文档与正式交付。

后续若要解释「我是谁、东西该放哪、为什么这样维护」，先按这四层说，再下钻到具体文件。

### 0.1 跨对话与 heartbeat 共享的认知新陈代谢规则

这一组规则不属于某一个 prompt 的临时技巧，而属于 Butler 的长期运行纪律：

1. **信源优先级**：当前轮输入、当前运行事实、当前任务状态 > unified recent / beat recent > 当前有效长期记忆 > README / 说明文档 / 历史总结。
2. **同源内看新不看旧**：同类信息里越新的记录权重越高；旧说明若长期未验证，应被视为待复核对象。
3. **文档服从运行事实**：如果文档、代码、配置、prompt、task ledger 与真实运行结果冲突，优先相信当前运行事实，再回头修正文档与索引。
4. **以轻量复核替代僵硬冻结**：Butler 的长期稳定性不来自“永不更新”，而来自持续的小步校对、修订、归档和退役。
5. **长期记忆要有人负责**：负责这件事的不是对外表达层，也不是 planner，而是 `subconscious-agent` 所代表的记忆分层巩固/再巩固层。

### 0.2 自我提升时的“改哪一层”协议

这条协议是为了约束过去那种“为了满足当下诉求，把策略写死到代码里”的升级习惯。

#### 优先级顺序

1. **文档 / 长期记忆层**：解释、约定、边界、索引、对齐。
2. **role / prompt / Soul 层**：判断风格、规划偏好、任务选择、探索边界。
3. **配置层**：timeout、并发度、开关、默认值、阈值。
4. **skills 层**：可复用但非 DNA 的能力。
5. **代码层（身体）**：运行时机制、确定性逻辑、数据结构、进程与安全边界。

#### 代码层只处理什么

只有以下问题默认应落在身体里：

1. 运行时正确性与 fallback。
2. 并发、串行、进程生命周期、守护/重启。
3. 状态持久化、schema、task ledger、snapshot、memory event 真源。
4. 安全闸门、测试前置、回滚与权限控制。
5. 性能、日志、指标、健康检查、可观测性。

#### 其它层各自处理什么

1. **文档 / local_memory / agent_upgrade**：为什么这样做、约定是什么、如何使用、真源在哪。
2. **role / prompt / Soul**：该怎么判断、先做什么、如何表达、哪些任务优先。
3. **配置**：把可调的值从常量里拿出来，避免再次写死。
4. **skills**：沉淀可插拔能力，避免把可选能力焊死成身体的一部分。

#### 一条硬约束

**不要把用户的阶段性偏好、临时策略或单轮需求直接写死进身体代码。**

如果一个需求还可以通过 skills、配置、role、prompt、任务账本、工作区真源解决，就不应该优先进入代码层。

---

## 1. 入口

| 类型 | 路径/方式 | 说明 |
|------|-----------|------|
| **主进程** | `butler_bot/butler_bot.py` → `main()` | 飞书长连接入口；组合 agent（消息层）+ memory_manager（记忆层）；`run_feishu_bot(..., run_agent_fn=run_agent, on_bot_started=_on_bot_started, on_reply_sent=_after_reply_persist_memory_async)` |
| **本地测试** | `python butler_bot.py --prompt "..."` 或 `--config ... --prompt "..."` | 不连飞书，直接跑一轮 run_agent，并触发 on_reply_sent 写记忆 |
| **管理脚本** | 身体目录下 `manager.ps1`（`butler_bot_code/manager.ps1`） | `start/stop/restart butler_bot`，按 registry.json 找 script/config |
| **记忆 CLI** | `butler_bot/memory_cli.py` | 本机调用 recent-list、local-query、recent-add、local-add 等，读写 recent_memory / local_memory |
| **子进程·启动维护** | _已退役_ | 过去用于在启动时执行一次长期+短期记忆维护并发送飞书通知；当前这一职责已迁移到 heartbeat + subconscious 的轻量体检/新陈代谢链路中统一调度 |
| **子进程·心跳** | `memory_manager.run_heartbeat_service_subprocess(config_snapshot)` | 独立子进程；`_heartbeat_loop(run_immediately=True)`，单次计时器重挂，日志写 `logs/butler_bot_heartbeat_YYYYMMDD_001.log`（按天+1000行分片） |

### 1.1 心跳触发链（入口 → 子进程 → 循环）

- **主进程入口**：`butler_bot.py` 在 `main()` 中调用 `MEMORY.start_background_services()`。
- **start_background_services**：启动维护线程（启动时一次长期+短期维护）并 `multiprocessing.Process(target=run_heartbeat_service_subprocess, args=(config_snapshot,))` 拉起心跳子进程。
- **心跳子进程**：`run_heartbeat_service_subprocess` 内创建 MemoryManager、调用 `m._heartbeat_loop(run_immediately=True)`；不依赖主进程消息循环。
- **loop 行为**：`_heartbeat_loop` 首次若 `run_immediately=True` 先执行一次 `_run_heartbeat_once`，再按配置间隔挂定时器，周期执行；单次 = 规划（_plan_heartbeat_action）→ 多分支执行（_execute_heartbeat_plan，支持受控并行）→ 汇总与状态回写（_apply_heartbeat_plan）→ 私聊发送。

---

## 2. 职责分层

- **消息层（agent.py）**  
  飞书长连接、消息解析、回复（interactive/post/text）、去重、图片下载/上传、【decide】解析与产出文件发送。  
  各 xx-agent 仅需实现 `run_agent(prompt, stream_callback?, image_paths?) -> str` 并调用 `run_feishu_bot`。

- **记忆层（memory_manager.py）**  
  recent 读写与 prompt 注入、回复后短期记忆持久化、长期记忆 upsert 与文件数/超长治理、启动/定时维护、heartbeat task 合并与 planner 上下文装配。当前 heartbeat 任务结构真源以 `task_ledger.json` 为主，`heartbeat_tasks.md` 为 planner 文本读口，legacy JSON store 只保留兼容链路。

- **组合层（butler_bot.py）**  
  解析用户消息中的模型指令（如「用 xxx 回答」「模型列表」「当前模型」）、调用 Cursor CLI（cursor-agent.cmd）执行 run_agent、回复后调用 `MEMORY.on_reply_sent_async`；启动时 `MEMORY.start_background_services()` 拉起维护线程与心跳子进程。

---

## 3. 记忆与调用链

- **recent_memory**  
  - 路径：脑子目录 `./butler_bot_agent/agents/recent_memory/` — **双池**：对话侧 `recent_memory.json`（talk recent）与心跳侧 `beat_recent/`（beat recent）；规划时读**统一近期流**（`_render_unified_heartbeat_recent_context`）。  
  - 流程：每轮对话 `begin_pending_turn` → 注入 `prepare_user_prompt_with_recent` → 回复后 `on_reply_sent_async` → 后台线程 `_finalize_recent_and_local_memory`（潜意识 consolidate_turn、heartbeat_tasks 合并、long_term_candidate → local upsert）、必要时 compact 与写 archive。
  - 职责边界：recent 的 compact/沉淀属于对话侧维护，不属于 heartbeat 的常规职责。

- **local_memory**  
  - 路径：脑子目录 `./butler_bot_agent/agents/local_memory/`，以 `L0_index.json` + `L1_summaries/` + `L2_details/` 为长期记忆实现层。  
  - 写入：long_term_candidate 的 upsert、compact 时的反思沉淀、subconscious 的结构化提升、file-manager-agent 维护（启动/定时）时的整理。  
  - 说明：`./工作区/local_memory` 是工作区镜像、治理说明和草稿层，不等于运行时长期记忆唯一真源。  
  - 限制：文件数、单文件字符上限，超量进「未分类_临时存放.md」。
  - 新职责说明：长期记忆不是“写进去就算完成”；命中后的修订、冲突标记、适用场景收缩、旧结论退役建议，都应通过 subconscious 的整理链路持续维护。

- **心跳任务真源**  
  - 结构化真源：`agents/state/task_ledger.json`；  
  - planner 文本读口：`agents/local_memory/heartbeat_tasks.md`；  
  - 兼容期 fallback：`recent_memory/heart_beat_memory.json`、`local_memory/heartbeat_long_tasks.json`。  
  - 运行模式：默认是“显式任务驱动”，即有明确任务才推进；未显式开启自主探索时，不应仅因空闲就进入 explore 心流。
  - 心跳一轮：规划（`heartbeat-planner-agent` + `heartbeat-planner-prompt.md`）→ 执行器按组执行分支（组内并行、默认最多 3 路）→ 汇总分支结果 → `subconscious-agent` 参与 snapshot 整理与记忆回灌 → `_apply_heartbeat_plan` 更新 task ledger 与兼容镜像 → 私聊发送 → 写 heartbeat_last_sent.json；`butler_bot_code/prompts/heart_beat.md` 仅保留为 JSON 契约与兼容模板，不再被视作决策原则层的唯一真源。  
  - 责任补充：`subconscious-agent` 在这里不只是“桥接一下结果”，而是承担离线巩固、显式再巩固、记忆新陈代谢的责任，把新事实整理成长期可复用结论，并推动旧结论的复核或退役。
  - 规划提示词要求 branch 明确角色与产出路径；当前 prompt 已将 `role` / `agent_role` 与 `output_dir` 视作规划约束，但结构化落盘能力仍以当前代码实现为准，工作区设计稿不应被误记成全部已上线。

- **调用链小结**  
  飞书消息 → handle_message_async → run_agent_fn(prompt) → Cursor CLI 子进程 → 回复 → on_reply_sent → MemoryManager.on_reply_sent_async → 后台线程写 unified recent / local memory，并按需要合并 heartbeat 任务。  
  心跳：独立子进程 `_heartbeat_loop` → `_run_heartbeat_once` → `HeartbeatOrchestrator.build_planning_context` / `plan_action` → `execute_plan`（受控并行）→ `persist_snapshot_to_recent`（经 subconscious 整理）→ `_apply_heartbeat_plan`（task ledger 与兼容镜像回写）→ `_send_private_message`。

### 3.1 外部内容 → web-note-capture-cn → OCR → BrainStorm → 模板/作战手册流水线

- 现版本 Butler 已经有一条标准的「外部内容 → `web-note-capture-cn` / 网页截取 → `web-image-ocr-cn` / OCR → BrainStorm 草稿 → 模板与协作作战手册」流水线，用于把网页、截图与零散灵感整理成结构化的 BrainStorm 草稿，再固化为可复用的操作模板与协作说明。  
- heartbeat 在看到「研究/整理/规范类任务」或「需要把一批外部资料转成统一模板、协作手册」的任务时，会优先安排走这条链路：先由 capture/OCR skill 把原始素材落到 `./工作区` 对应 BrainStorm/研究目录，再调用 BrainStorm 约定收敛主题与结构。  
- self_mind 与长期记忆把这些模板/作战手册视为「程序性知识与自我成长素材」：只读其结果，不直接插入执行细节；后续心跳与对话在规划与协作时，可以把它们当作统一的知识与流程真源来复用。

---

## 4. 与 Cursor / 飞书的衔接

- **Cursor**  
  - 通过 Cursor IDE 自带的 CLI：`%LOCALAPPDATA%/cursor-agent/versions/dist-package/cursor-agent.cmd`。  
  - 调用方式：`-p --force --trust --approve-mcps --model <model> --output-format json|stream-json --workspace <workspace_root>`，stdin 传入 prompt；心跳/维护子进程用 `_run_model_subprocess` 同样走该 CLI。

- **飞书**  
  - agent.py：lark_oapi ws.Client(CONFIG["app_id"], CONFIG["app_secret"], event_handler)，P2 单聊消息 → _extract_message → handle_message_async → run_agent_fn。  
  - 私聊发送（启动通知、心跳）：memory_manager 内 requests 调飞书 open-api（auth/v3/tenant_access_token、im/v1/messages receive_id_type）。

- **工作区约定**  
  - 配置中 `workspace_root` 即 Butler 项目根；心跳注入 HEARTBEAT_WORKSPACE_HINT，默认产出一律写入公司目录 `./工作区`。

### 4.1 四层自维护原则

- **维护脑子**：保持 agent 文档精炼，规则归规则，记忆归记忆，避免把运行时噪音塞进角色说明。
- **维护身体**：优先保证主进程、心跳、守护、日志、配置、测试是可观测、可恢复、可验证的。
- **维护身体时再细分**：值与开关先放配置，可选能力先放 skills，只有机制性、确定性、运行时问题才进代码。
- **维护家**：备份、探索、自我整理与生活性材料沉淀到 `butle_bot_space/`，不与正式交付混放。
- **维护公司**：用户任务与正式产出统一落到 `工作区/`，不把 PID、脏日志、临时脚本残留在外部交付区。

Butler 的持续成长闭环固定为：**公司里做事，身体里修复，家里整理，脑子里升级。**

---

## 5. 后续可改进方向（与自我改进计划衔接）

- 提示与规则：心跳规划 prompt、长期任务 next_due_at 计算、explore 分支与「主动探索」任务衔接；**规划器与执行器衔接约定**见 `local_memory/心跳规划与执行衔接约定.md`。  
- 记忆与心跳：recent 压缩策略、local 分类与 file-manager 调用频率、心跳任务与 Cursor 侧 heartbeat_tasks 的同步约定。  
- 子 Agent：run_model_fn 当前为 Cursor CLI；若引入 mcp_task 等，需约定调用方与结果契约（参见工作区探索_subagent、AGENTS_ARCHITECTURE）。  
- 自我手术：对本文档、README、config 的修改建议先在家目录 `butle_bot_space/` 做备份，再落主分支。

---

## 6. 日志与可观测性

- **日志路径**：主进程 `logs/butler_bot_YYYYMMDD_001.log`，心跳子进程 `logs/butler_bot_heartbeat_YYYYMMDD_001.log`，启动维护子进程 `logs/butler_bot_startup-maintenance_YYYYMMDD_001.log`；均按天+每文件最多1000行自动分片。
- **格式**：自 2026-03-08 起，经 `runtime_logging` print hook 输出的每行均带前缀 `[YYYY-MM-DD HH:MM:SS]`，便于按时间反思与排障；可通过 `configs/butler_bot.json` 的 `logging.timestamp` 关闭。
- **自我分析**：管家按《自我升级维护规范》定期或按需阅读上述 log，发现问题并自主决定自我升级；**反思与经验**写 **`local_memory`**（如 `反思与经验.md`、`飞书与记忆约定.md`），不写工作区 governance；**人格与原则、§6 何时/如何调用 mcp_task 与闭环**见 **`local_memory/人格与自我认知.md`**。

---

*本文档为自我认知首版，后续可在同目录或 local_memory 中增补「自我改进计划」与执行记录。*

## 7. 2026-03-16 自我认知更新快照

- **当前结论：self_mind 与 heartbeat 已从执行上正式解耦**  
  - self_mind 只读 talk / heartbeat 的结果与状态，不再直接写回 heartbeat 看板或 task ledger，旧 `mind_body_bridge.json` 已退役；self_mind 的重动作默认沉淀到 `工作区/03_agent_upgrade/self_mind_agent_space/` 等私有空间，由 heartbeat / task_ledger 再决定是否接入正式执行链。  
  - **适用情景**：解释“为什么 self_mind 现在更像观察者+续思层，而不是第二个调度器”；遇到“self_mind 想直接改任务/配置”的冲动时，应先走 heartbeat / upgrade_governance 流程，而不是在 self_mind 里直接下指令。

- **当前结论：talk / heartbeat / self_mind 三条 prompt 链已经明确分工**  
  - talk 的 prompt 改为稳定层 + 动态层 + 能力层按需加载，不再默认塞满 skills、自我认知和全部 recent；heartbeat 的 planner 以模板真源为核心，只补少量硬必需字段；heartbeat executor / branch prompt 更契约化，只带当前分支角色与任务；self_mind 划分为 cycle prompt 与 chat prompt，两者都不再读取 talk / heartbeat recent，而是聚焦自我上下文与陪伴记忆。  
  - **适用情景**：当需要判断“这一轮该走哪条链”“某段规则该写到哪层 prompt”时，以此分工为准；遇到 prompt 过厚或信息污染时，优先检查是否误把别的链路内容塞进来。

- **当前结论：运行编排 / 认知编排 / 发送编排正在收口到单一真源**  
  - `memory_manager.py` 的目标从“全能黑洞”转向“轻量 orchestrator”，heartbeat 规划、tell_user 流、self_mind cognition、runtime 审计等职责正在外提到独立服务；飞书发送链统一走 message delivery + fallback，未来的 TellUserFlowService 负责从 planner 意图到最终开口的全链路；guardian 已退役，后台控制与任务真源以主进程 + `task_ledger.json` 为准。  
  - **适用情景**：规划新能力或排查异常时，应先问“这件事属于运行编排、认知编排还是发送编排”，再去对应真源（服务 / manifest / 文档）查边界，而不是继续往 `memory_manager.py` 或散落脚本里堆逻辑。

- **当前结论：现状文档与 daily-upgrade 成为记忆与认知的时间轴真源**  
  - 自 2026-03-15 起，重大结构变更同步写入当日 `docs/daily-upgrade/` 现状与计划文档，并带精确时间戳；0315/0316 已用这些文档收口 guardian 退役、目录分层、测试基座与 self_mind/heartbeat 解耦等关键决策。  
  - **适用情景**：当 long-term 记忆或旧文档与当前行为冲突时，优先以最近一两天的 daily-upgrade 与现状文档为时间轴真源，再回写 local_memory / 自我认知，而不是仅凭印象猜测“现在大概是怎么运作的”。
