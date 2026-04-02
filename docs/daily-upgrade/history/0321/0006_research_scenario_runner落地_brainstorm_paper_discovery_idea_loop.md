# 0321 research scenario runner 落地：brainstorm / paper_discovery / idea_loop

更新时间：2026-03-21 00:06
时间标签：0321_0006

## 一、本轮落地结论

基于上一份方案文档：

- `docs/daily-upgrade/0320/2352_research_scenario_runner升级方案_brainstorm_paper_discovery_idea_loop.md`

本轮已经把 research 的轻量场景 runner 真正落下来了。

当前 `research_manager` 不再只是返回静态 `scenario + workflow_projection`，而是已经能返回：

- 当前场景的 `active_step`
- 当前 `workflow_cursor`
- 最小 `step / handoff / decision` receipts
- 当前 step 的 `output_template`
- 场景 `entry_contract / exit_contract`

也就是说，research 这条线已经从：

- 静态场景资产包

推进到了：

- 可解释、可推进、可接续的场景 workflow 解释层

---

## 二、落地文件

新增：

- `butler_main/research/manager/code/research_manager/services/scenario_runner.py`
- `butler_main/butler_bot_code/tests/test_research_scenario_runner.py`

修改：

- `butler_main/research/manager/code/research_manager/services/scenario_registry.py`
- `butler_main/research/manager/code/research_manager/services/unit_registry.py`
- `butler_main/research/manager/code/research_manager/services/__init__.py`
- `butler_main/research/manager/code/research_manager/services/README.md`
- `butler_main/research/README.md`
- `butler_main/butler_bot_code/tests/test_research_manager_multi_entry.py`

---

## 三、当前 runner 的职责

`scenario_runner.py` 当前承担的是轻量解释层职责：

1. 读取 scenario 对应的 `workflow.spec.json`
2. 根据 invocation 里的 `workflow_cursor / scenario_action / decision` 决定当前 step
3. 生成当前 `active_step`
4. 生成当前 `StepReceipt / HandoffReceipt / DecisionReceipt`
5. 生成 `output_template / entry_contract / exit_contract`
6. 生成新的 `workflow_projection`

它仍然不负责：

- 真正执行搜索/阅读/改代码
- 代替 `RuntimeHost`
- 变成通用 orchestrator

---

## 四、三个场景已具备的最小推进语义

### brainstorm

已支持：

- 初始从 `capture` 起步
- 正常按 `capture -> cluster -> expand -> converge -> archive` 推进
- 输出 brainstorm 场景的统一输出骨架

### paper_discovery

已支持：

- 初始从 `topic_lock` 起步
- 支持推进到 `query_plan -> search -> screen -> digest`
- 输出 `paper_digest` 场景的统一输出骨架

### idea_loop

已支持：

- 初始从 `idea_lock` 起步
- 正常按 `idea_lock -> plan_lock -> iterate -> final_verify -> archive` 推进
- 在 `final_verify` 上若 decision 是 `retry / refine`，自动切到 `recover`

---

## 五、manager 接线变化

这轮 `unit_registry.py` 已经不再自己拼 scenario payload，而是统一调用：

- `build_scenario_dispatch(invocation, unit)`

因此现在 `ResearchManager.invoke()` 的 dispatch payload 已包含：

- `scenario`
- `workflow_projection`
- `workflow_cursor`
- `active_step`
- `step_receipt`
- `handoff_receipt`
- `decision_receipt`
- `output_template`
- `entry_contract`
- `exit_contract`

这保证了：

- `heartbeat / talk / codex` 共享同一套场景解释层
- unit handler 不再自己解释 step 语义

---

## 六、验证结果

已通过：

- `butler_main.butler_bot_code.tests.test_research_scenario_runner`
- `butler_main.butler_bot_code.tests.test_research_manager_multi_entry`

并与上一轮 agents_os/workflow/protocol 基线做了组合回归：

- `butler_main.butler_bot_code.tests.test_agents_os_protocols`
- `butler_main.butler_bot_code.tests.test_agents_os_runtime_host`
- `butler_main.butler_bot_code.tests.test_agents_os_wave2_adapters`
- `butler_main.butler_bot_code.tests.test_task_ledger_service`
- `butler_main.butler_bot_code.tests.test_research_manager_multi_entry`
- `butler_main.butler_bot_code.tests.test_research_scenario_runner`

结果：

- `35` 个测试全部通过

---

## 七、下一步最合理的方向

在当前基础上，下一步不该立刻做大平台，而应继续沿着 scenario 线收口：

1. 给 scenario dispatch 补最小场景 state store
2. 让 `talk / heartbeat / codex` 真正共享同一个 scenario instance
3. 再往后才考虑把 step 解释推进到真正的执行层

一句话总结：

> 这轮已经把 research 的三大场景从“有资产描述”推进到了“有统一解释层”，下一轮应继续把它们推进到“有共享 instance 的可接续运行态”。
