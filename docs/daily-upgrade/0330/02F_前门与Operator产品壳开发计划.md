# 0330/02F_前门与Operator产品壳开发计划

日期：2026-03-30  
最后更新：2026-03-31  
状态：现役 / 0330 Agent Harness 子计划真源（Product Surface 主轴）

关联文档：

- [01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md](./01_后台任务操作面与多Agent编排控制台升级计划_未实施草稿版.md)
- [02_AgentHarness全景研究与Butler主线开发指南.md](./02_AgentHarness全景研究与Butler主线开发指南.md)
- [02C_会话协作与事件模型开发计划.md](./02C_会话协作与事件模型开发计划.md)
- [02G_治理观测与验收闭环开发计划.md](./02G_治理观测与验收闭环开发计划.md)
- [04_Chat默认厚Prompt分层治理真源.md](./04_Chat默认厚Prompt分层治理真源.md)
- [Visual_Console_API_Contract_v1.md](../../runtime/Visual_Console_API_Contract_v1.md)

## 一句话裁决

`02F` 只负责产品壳。  
chat/frontdoor、console、Draft Board、prompt surface、workflow authoring 都只能消费控制面和 runtime 的投影，并通过受控 action contract 发起操作，不能直接成为 Butler 真源。

## 本文边界

- 主层级：`Product Surface`
- 次层级：`Domain & Control Plane`
- 主代码目录：
  - `butler_main/chat/`
  - `butler_main/console/`
  - `butler_main/orchestrator/interfaces/`
- 默认测试：
  - `test_console_server.py`
  - `test_console_services.py`
  - `test_chat_router_frontdoor.py`
  - `test_talk_mainline_service.py`

## 当前已对齐能力

1. chat/frontdoor 已具备协商、启动、查询的基础主链。
2. console 已具备 operator 面板、prompt/workflow authoring、audit 入口等 V2 雏形。
3. `prompt-surface`、`workflow-authoring`、`audit-actions` 等接口已经进入 console API。
4. `trace_id / receipt_id / recovery_decision_id` 已开始回传到产品层。

## 当前缺口

1. 当前产品语义仍偏“看见后台在跑什么”，对“为什么触发某策略、为何允许某恢复动作”的解释还不够强。
2. `thread / turn / item` 还没有作为正式产品事件语义进入 Butler 前门与 operator shell。
3. prompt/workflow patch 能力已有基础，但受控写入口与 runtime 真源边界仍需要再收紧。
4. 多 agent 运行态在产品层仍偏观测，不够像真正的治理与编排操作面。

## P0 开发计划

1. 冻结 frontdoor 与 operator shell 的受控写边界：
   - 产品壳只发 action contract
   - 真状态更新只发生在 control/runtime 层
2. 把 `thread / turn / item` 作为产品事件模型补进 Butler operator 语义，但明确其只是 surface primitive，不替代 session 真源。
3. 为 prompt surface、workflow authoring、recovery actions 增加稳定的 diff/preview/read-only 契约。
4. 保证产品层能读到 `trace_id / receipt_id / recovery_decision_id / approval_state / risk_level / autonomy_profile`。

## P1 开发计划

1. 把 operator shell 从“观察台”继续推向“受控治理面”，但不反向做 runtime。
2. 增加更多多 agent session 的 operator 读模型，例如：
   - handoff timeline
   - mailbox summary
   - artifact lineage
3. 统一 chat/frontdoor 与 console 对同一 campaign 的状态解释，避免一边显示 idle、一边显示 blocked。
4. 为 prompt/workflow patch 增加更明确的 operator runbook。

## P2 开发计划

1. 增加更强的 graph/flow authoring 体验，但仍以 `Workflow IR` 为真源。
2. 增加 trigger-based product frontdoor 与 workspace-scoped operator presets。
3. 增加多视角 timeline 与 long-running campaign studio。

## 关键合同

1. `frontdoor action`
  - 只负责受控触发，不负责定义 runtime 真状态。
2. `operator action`
  - 必须落回 control plane 与 audit receipt。
3. `thread / turn / item`
  - 是产品事件模型，不是 `workflow session` 的替代名。
4. `prompt/workflow surface`
  - 只做 projection、diff、patch request，不直接写底层真源对象。

## 验收口径

1. `test_console_server.py` 验证 operator、prompt surface、workflow authoring、audit API 对外合同。
2. `test_console_services.py` 验证 console 服务拼装逻辑。
3. `test_chat_router_frontdoor.py`、`test_talk_mainline_service.py` 验证 chat/frontdoor 路由和受控入口没有回退成旧前门强接管。
4. 若涉及 query/feedback 口径，补验 `test_orchestrator_campaign_service.py` 或 `test_orchestrator_campaign_observe.py`。

## 文档回写要求

1. surface contract 改动后，回写：
   - `Visual_Console_API_Contract_v1.md`
   - `04_Chat默认厚Prompt分层治理真源.md`
   - `02G_治理观测与验收闭环开发计划.md`
2. 若新增 operator write action，同步检查 `01` 专题是否失真。

## 明确不做

1. 不把 graph UI、studio 布局或 chat shell 反向提升为运行真源。
2. 不把 vendor studio 的交互命名直接搬进 Butler 现役对象层。
3. 不让产品面绕过 control plane 直接修改 runtime/session/durability 对象。
