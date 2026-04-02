# 07 任务包 C orchestrator control plane 收缩交付

日期：2026-03-25
时间标签：0325_0007
状态：已迁入完成态 / control plane 收缩输入冻结

## 这次交付做了什么

本轮先完成 `任务包 C` 的第一批目标：

1. 审计 `butler_main/orchestrator` 当前文件归属。
2. 明确 `service.py` 哪些是第三层 control plane 真职责，哪些只是临时塞进去的 runtime/gate 逻辑。
3. 落一版最小代码改动：
   - 建立 `application` / `runtime_bridge` 目录入口。
   - 把 `workflow session` 相关持久化与状态同步从 `service.py` 抽到独立 bridge。
   - 把 `approval / verification / recovery` 从 `service.py` 抽到独立 governance bridge。
4. 给出后续拆分顺序，不在这轮扩成大重构。

## 目录分层建议

| 分类 | 当前文件 | 判断 |
| --- | --- | --- |
| `domain` | `models.py` `scheduler.py` `policy.py` | 属于 control plane 核心，继续留在 orchestrator 内核 |
| `application` | `service.py` | 属于控制面用例层，但当前仍过大 |
| `compile` | `compiler.py` `workflow_ir.py` | `compiler.py` 留在第三层；`workflow_ir.py` 当前是交界文件，后续要把通用 IR 真语义往 process runtime 下沉 |
| `runtime_bridge` | `workflow_vm.py` `execution_bridge.py` `runtime_adapter.py` `judge_adapter.py` | 这些是 orchestrator 到 runtime 的桥接位，应和 `application` 分开 |
| `runtime_bridge`（临时） | `research_bridge.py` `research_projection.py` | 目前还在 orchestrator 内，但长期应迁到 `domains/research/*` |
| `infra` | `branch_store.py` `mission_store.py` `event_store.py` `paths.py` `workspace.py` `config.py` | 基础设施与装配层 |
| `interfaces` | `ingress_service.py` `query_service.py` `runner.py` `mission_orchestrator.py` `observe.py` | 面向前台、CLI、运行态观测的接口层 |
| `frameworks` | `framework_catalog.py` `framework_compiler.py` `framework_mapping.py` `framework_profiles.py` | 外部框架适配层 |
| `fixtures` | `templates.py` `demo_fixtures.py` `smoke.py` | 开发支撑与样例，不应继续挤在核心层心智里 |

## `service.py` 职责切分

### 仍应留在 control plane 的部分

1. mission / node / branch 的创建、调度、状态推进。
2. branch 预算、mission 终态刷新、ledger event 写回。
3. 对 runtime verdict 的消费与控制面投影。
4. 面向 query / observe 的 mission、branch 汇总接口。

### 应移出 `service.py` 的部分

1. `workflow session` 的读取、保存、恢复、状态同步。
2. `workflow_ir` 与 session 元数据绑定的桥接逻辑。
3. `approval / verification / recovery` 的运行时真语义。
4. research-specific collaboration projection 与 writeback。

## 首批拆分顺序

1. 先抽 `workflow session bridge`
   - 这是最独立、最机械、最不该继续留在 control plane 的一组逻辑。
2. 再抽 `governance runtime adapter`
   - 把 `approval / verification / recovery` 从 `service.py` 里的大段流程迁成薄适配。
3. 再拆 `workflow_ir.py`
   - orchestrator 只保留 mission compile 投影；通用 IR 与 VM 语义回到 process runtime。
4. 最后处理 `research_bridge.py`
   - 迁到 `domains/research/*`，orchestrator 只保留薄桥。

## 这轮已落地的最小改动

### 新增目录入口

1. `butler_main/orchestrator/application/`
2. `butler_main/orchestrator/runtime_bridge/`

### 新增文件

1. `butler_main/orchestrator/application/mission_service.py`
   - 先提供 `OrchestratorService` 的新目标路径 re-export。
2. `butler_main/orchestrator/runtime_bridge/workflow_session_bridge.py`
   - 收纳 session 读取、保存、summary、prepare、finalize、metadata refresh。
3. `butler_main/orchestrator/runtime_bridge/governance_bridge.py`
   - 收纳 approval / verification / recovery 的桥接语义，让 control plane 只消费治理结果。

### 已修改文件

1. `butler_main/orchestrator/service.py`
   - `summarize_workflow_session()` 和一组 `_workflow_*` helper 现在委托给 `OrchestratorWorkflowSessionBridge`。
   - `record_branch_result()` / `resolve_node_approval()` 现在委托给 `OrchestratorGovernanceBridge`。
   - `service.py` 删除了一整段 approval / verification / recovery 私有实现，继续收缩回 control plane consumer。
2. `butler_main/orchestrator/__init__.py`
   - 根导出改为优先走 `application` / `runtime_bridge` 包路径，并补导出 `OrchestratorGovernanceBridge`。
3. `butler_main/orchestrator/workspace.py`
   - 默认装配入口改为通过 `application` 包拿 `OrchestratorService`，避免继续把 `service.py` 当唯一正式入口。
4. `butler_main/butler_bot_code/tests/test_orchestrator_control_plane_layout.py`
   - 增加 governance bridge 的包导出校验。

## 为什么这一步值当先做

1. `workflow session` 是第二层 process runtime substrate 的一部分，不应该继续深埋在第三层 control plane 大文件里。
2. `approval / verification / recovery` 仍是桥接态，但至少已经不再继续挤在 control plane 主类里。
3. 这两步都不改现有 mission / branch contract，回归测试成本低。
4. 它们为下一步继续下沉到 `runtime_os process runtime` 留出了明确落点：`application` 只保留控制面用例，`runtime_bridge` 承接桥接杂质，再继续向第 2 层回收。

## 本轮非目标

1. 不在今天直接把 `approval / verification / recovery` 全搬出 orchestrator。
2. 不在今天把 governance bridge 直接改写成 `runtime_os process runtime` 真源。
3. 不在今天移动 `research_bridge.py` 到新 domain 包。
4. 不在今天大规模 rename 既有 orchestrator 模块 import。
5. 不在今天重写 `workflow_vm.py` 或 `compiler.py`。

## 下一批最值得动的文件

1. `butler_main/orchestrator/workflow_vm.py`
   - 明确它只负责 control plane 到 engine 的路由，不承载通用 VM 真语义。
2. `butler_main/orchestrator/workflow_ir.py`
   - 切出第三层 mission compile 投影和第二层通用 IR。
3. `butler_main/orchestrator/research_bridge.py`
   - 开始退出 orchestrator 内核。
4. `butler_main/orchestrator/service.py`
   - 继续朝 `application/mission_service.py` 目标路径收缩，最终把旧 `service.py` 退回兼容壳。

## 验证

建议至少跑：

1. `python -m unittest butler_main.butler_bot_code.tests.test_orchestrator_core`
2. `python -m unittest butler_main.butler_bot_code.tests.test_orchestrator_workflow_vm`
3. `python -m unittest butler_main.butler_bot_code.tests.test_orchestrator_control_plane_layout`
4. `python -m unittest butler_main.butler_bot_code.tests.test_orchestrator_runner`
5. `python -m unittest butler_main.butler_bot_code.tests.test_orchestrator_smoke`
