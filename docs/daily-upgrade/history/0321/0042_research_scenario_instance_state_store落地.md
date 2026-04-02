# 0321 research scenario instance/state store 落地

更新时间：2026-03-21 00:42
时间标签：0321_0042

## 一、本轮落地结论

在完成外部对标和 `scenario_runner` 之后，research 这条线已经继续推进到了：

- `scenario asset`
- `scenario runner`
- `scenario instance/state store`

也就是说，现在 `brainstorm / paper_discovery / idea_loop` 不再只是：

- 有一份 workflow 规格

而是已经具备：

- 可共享的场景线程 id
- 可保存的 workflow cursor
- 可跨入口复用的当前 step 状态

---

## 二、落地文件

新增：

- `butler_main/research/manager/code/research_manager/services/scenario_instance_store.py`
- `butler_main/butler_bot_code/tests/test_research_scenario_instance_store.py`

修改：

- `butler_main/research/manager/code/research_manager/manager.py`
- `butler_main/research/manager/code/research_manager/__init__.py`
- `butler_main/research/manager/code/research_manager/services/__init__.py`
- `butler_main/research/manager/code/research_manager/services/README.md`
- `butler_main/research/README.md`
- `butler_main/butler_bot_code/tests/test_research_manager_multi_entry.py`

---

## 三、当前 state store 的职责

当前 `FileResearchScenarioInstanceStore` 负责：

1. 按 `scenario_instance_id` 显式绑定 instance
2. 按 `session_id / task_id / workspace` 为 unit 绑定稳定 thread key
3. 创建、加载、保存 scenario instance
4. 回写：
   - `workflow_cursor`
   - `active_step`
   - `output_template`
   - `last_step_receipt`
   - `last_handoff_receipt`
   - `last_decision_receipt`
   - `state`
5. 追加事件日志

当前 `ResearchManager` 在 invoke 时的主线已经变成：

1. resolve unit
2. bind/create scenario instance
3. 把 instance 里的 cursor 注回 invocation
4. 通过 unit handler + scenario runner 生成 dispatch
5. 用 dispatch 结果回写 scenario instance

---

## 四、当前共享语义

这轮最关键的行为变化是：

- `talk / heartbeat / codex`
- 只要落在同一个 `unit_id + session_id` 上
- 就会绑定到同一个 `scenario_instance`

因此现在跨入口共享的不是“同一套 prompt 假设”，而是：

- 同一个场景线程
- 同一份 cursor
- 同一份 step 状态

这和前面的语义判断一致：

> `scenario instance` 是 research 场景线程运行态，不是 skill 运行态，也不是大平台里的泛化 agent 容器。

---

## 五、验证结果

新增通过：

- `butler_main.butler_bot_code.tests.test_research_scenario_instance_store`

并且和现有 research / agents_os 回归一起验证通过：

- `butler_main.butler_bot_code.tests.test_research_manager_multi_entry`
- `butler_main.butler_bot_code.tests.test_research_scenario_runner`
- `butler_main.butler_bot_code.tests.test_agents_os_protocols`
- `butler_main.butler_bot_code.tests.test_agents_os_runtime_host`
- `butler_main.butler_bot_code.tests.test_agents_os_wave2_adapters`
- `butler_main.butler_bot_code.tests.test_task_ledger_service`

当前组合回归结果：

- `37` 个测试全部通过

---

## 六、下一步建议

到了这一步，research 线已经有：

- workflow spec
- runner
- instance/state store

下一步最值得继续的是：

1. 给 scenario instance 补更明确的 `state patch` 结构
2. 把 step 执行产出真正回灌到 `state`
3. 再往后才考虑把检索 skill、文献整理 skill、实验执行 skill 逐步挂进 step 执行层

一句话总结：

> 这轮的关键成果，不是多造了一个 store，而是让 research 三大场景第一次拥有了共享的场景线程运行态。
