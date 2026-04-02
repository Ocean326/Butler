# 0330/02R_外部Harness映射与能力吸收开发计划

日期：2026-03-30  
最后更新：2026-03-31  
状态：现役 / 0330 Agent Harness 子计划真源（Reference 映射主轴）

关联文档：

- [02_AgentHarness全景研究与Butler主线开发指南.md](./02_AgentHarness全景研究与Butler主线开发指南.md)
- [02A_runtime层详情.md](./02A_runtime层详情.md)
- [02B_协议编排与能力包开发计划.md](./02B_协议编排与能力包开发计划.md)
- [02D_持久化恢复与产物环境开发计划.md](./02D_持久化恢复与产物环境开发计划.md)
- [02F_前门与Operator产品壳开发计划.md](./02F_前门与Operator产品壳开发计划.md)
- [02G_治理观测与验收闭环开发计划.md](./02G_治理观测与验收闭环开发计划.md)
- [System_Layering_and_Event_Contracts.md](../../runtime/System_Layering_and_Event_Contracts.md)

## 一句话裁决

`02R` 是 Butler 吸收“百家之长”的总翻译层。  
外部 harness 只能通过 `framework catalog / framework mapping / compiler inputs / governance defaults / runtime binding hints` 进入 Butler，不允许直接反向改写内部真源命名。

## 本文边界

- 主层级：`Domain & Control Plane`
- 次层级：`L3 Multi-Agent Protocol`、`L1/L2/L4`、`Product Surface`
- 主代码目录：
  - `butler_main/orchestrator/framework_catalog.py`
  - `butler_main/orchestrator/framework_mapping.py`
  - `butler_main/orchestrator/framework_compiler.py`
  - `butler_main/orchestrator/framework_profiles.py`
- 默认测试：
  - `test_orchestrator_framework_catalog.py`
  - `test_orchestrator_framework_mapping.py`
  - `test_orchestrator_framework_compiler.py`
  - `test_orchestrator_workflow_ir.py`

## 当前已对齐能力

1. 仓库中已经存在 `FrameworkCatalogEntry`、`FrameworkMappingSpec`、`FrameworkMappingBundle` 等正式对象。
2. `framework_compiler` 已能把 mapping/profile/mission payload 组装成可编译输入。
3. `framework_profiles` 已体现 approval、runtime binding、governance defaults 的结构化吸收方向。
4. `02_AgentHarness...` 已完成 LangGraph、OpenAI Agents SDK、Codex、DeerFlow、Dify、MCP、A2A 等外部参考的裁决分层。

## 当前缺口

1. 当前 catalog/mapping 仍偏向早期研究对象，尚未把 `0330` 调研形成的主力框架全部系统接入。
2. “吸收什么 / 不吸收什么 / 进入 Butler 的哪个 target kind” 还没有形成统一的对照矩阵。
3. mapping 虽然有对象，但缺少面向实现者的固定阅读与回写规范，容易重新回到“读一堆 vendor 文档再临场拍板”。
4. framework mapping 与子计划 `02A/B/C/D/F/G` 的关系还不够清晰，执行者容易不知道该落哪层。

## 现役吸收矩阵

1. `LangGraph`
  - 主吸收：`02B`、`02C`、`02D`
  - 重点：`interrupt / resume`、`checkpoint`、`state update / goto`
  - 明确不吸收：graph DSL、节点 UI 命名
2. `OpenAI Agents SDK`
  - 主吸收：`02A`、`02C`、`02G`
  - 重点：`handoff as typed contract`、`session`、`guardrail`、`tracing`
  - 明确不吸收：vendor API 表层对象名
3. `Codex Harness / App Server`
  - 主吸收：`02A`、`02F`、`02G`
  - 重点：`thread / turn / item`、approval 双向协议、subagent 继承式治理
  - 明确不吸收：CLI 交互细节、host-specific UX
4. `DeerFlow`
  - 主吸收：`02D`、`02F`、`02G`
  - 重点：thread/filesystem/artifact 一体环境、middleware policy plane、runtime 与 gateway 分层
  - 明确不吸收：其全栈产品壳与具体实现栈
5. `Dify / CrewAI / AgentScope`
  - 主吸收：`02F`、`02G`
  - 重点：flow 与 autonomy 分离、operator shell、run/node history、msg hub/OTel 启发
  - 明确不吸收：平台壳、插件市场 UI、crew 术语本体
6. `MCP / A2A`
  - 主吸收：`02R`、`02G`
  - 重点：外部工具协议与外部 agent 协议的双协议分层
  - 明确不吸收：把协议接入层提升为 workflow/session 真源

## P0 开发计划

1. 把 `0330` 已裁决的主力框架补进 catalog/mapping 真源，并为每个 `framework_id` 明确：
   - `source_terms`
   - `butler_targets`
   - `absorbed_packages`
   - `governance_defaults`
   - `runtime_binding_hints`
   - `compiler_profile_templates`
2. 明确 `framework mapping -> compiler inputs -> governance defaults -> runtime binding hints` 的路径，不允许再靠自由文本把外部能力硬塞进 mission metadata。
3. 为每个外部框架写清 `adopt`、`do_not_copy`、`evidence source` 三类信息。
4. 建立 `02R -> 02A/B/C/D/F/G` 的固定跳转关系，让映射层永远只做翻译，不代替各层真源。

## P1 开发计划

1. 为 framework mapping 增加更明确的 target kind taxonomy，例如：
   - `workflow_package`
   - `capability_package`
   - `governance_policy`
   - `runtime_binding`
   - `product_surface_hint`
2. 为 compiler profile templates 增加更稳定的验证样板。
3. 为 MCP / A2A 的 adapter 预留 package 化入口。
4. 增加 mapping 回归样板，确保新增 framework entry 不会破坏既有 compile 行为。

## P2 开发计划

1. 增加 framework lineage 与版本变更说明。
2. 增加更多外部产品壳的运营语义映射，但仍保持其为参考层而非真源层。
3. 增加更细的 source evidence registry。

## 关键合同

1. `FrameworkCatalogEntry`
  - 定义某个外部框架“是什么、强在哪、明确不该复制什么”。
2. `FrameworkMappingSpec`
  - 定义某个外部框架“如何被翻译进 Butler target/package/policy”。
3. `FrameworkMappingBundle`
  - 连接 catalog 与 mapping，供 compiler 消费。
4. `framework profile`
  - 用于产生稳定的 compile/runtime default，不是最终任务实例本身。

## 验收口径

1. `test_orchestrator_framework_catalog.py` 验证 catalog entry 结构与查找。
2. `test_orchestrator_framework_mapping.py` 验证 mapping spec、bundle、target kind 与 defaults。
3. `test_orchestrator_framework_compiler.py` 验证 mapping/profile 到 Butler compile 结果的连接。
4. 若新增映射影响 workflow 或 surface，补验 `test_orchestrator_workflow_ir.py`、`test_console_server.py` 或 `test_skill_exposure.py`。

## 文档回写要求

1. 新增或改动 framework mapping 时，至少回写：
   - `02_AgentHarness全景研究与Butler主线开发指南.md`
   - 对应子计划 `02A/B/C/D/F/G`
   - `docs/project-map/02_feature_map.md`
   - `docs/project-map/03_truth_matrix.md`
   - `docs/project-map/04_change_packets.md`
2. 若仅新增研究材料但未形成 Butler target/package 裁决，不得直接写进现役真源。

## 明确不做

1. 不把 vendor-specific API、UI、DSL 当 Butler 主合同。
2. 不让“框架支持某能力”自动等同于“Butler 已正式吸收该能力”。
3. 不允许绕过 `framework mapping` 直接把外部术语灌入协议层、运行层或产品层。
