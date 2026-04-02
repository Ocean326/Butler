# 0320 agents_os 实例容器与 RuntimeHost 升级落地

更新时间：2026-03-20 18:32
时间标签：0320_1832

## 一、本轮目标

把前一份 `1608_runtime_instance完善方案_最小字段目录与ConnectOnion补充启发.md` 里的 3 个动作真正落到代码：

1. 在 `agents_os` 里补 `AgentRuntimeInstance + InstanceStore`
2. 在 `RuntimeKernel` 外补轻量 `RuntimeHost`
3. 从 ConnectOnion 只参考低耦合模块思路，不整层搬框架

本轮判断保持不变：

> Butler 要升级的是“实例容器和 host 生命周期”，不是把整个 agent 框架替换成 ConnectOnion。

---

## 二、本轮实际落地

## 2.1 新增 `AgentRuntimeInstance`

新增：

- `butler_main/agents_os/runtime/instance.py`

落地内容：

- `AgentRuntimeInstance` dataclass
- `INSTANCE_STATUSES`
- `normalize_instance_status()`
- `build_instance_roots()`

这层解决的是“实例不是单次 Run，而是可托管运行单元”。

本轮已把实例最小字段按 1608 方案落为结构化字段，覆盖：

- identity
- profile
- session
- context
- governance
- artifacts / handoff
- observability
- recovery

同时把实例根目录约定固化为 roots，避免后续继续把目录信息散在 adapter 和 manager 里。

## 2.2 新增 `FileInstanceStore`

新增：

- `butler_main/agents_os/runtime/instance_store.py`

落地内容：

- `create()`
- `load()`
- `save()`
- `update()`
- `retire()`
- `append_event()`

本轮真正落盘了实例目录骨架：

```text
instances/<instance_id>/
  instance.json
  profile.json
  status.json
  session/
    session.json
    checkpoints/
    overlays/
  context/
    working_summary.md
    recent_refs.json
    memory_refs.json
    overlay_refs.json
  traces/
    events.jsonl
    latest_trace.json
    metrics.json
  artifacts/
    drafts/
    handoff/
    published/
  approvals/
    tickets/
    decisions/
  recovery/
    directives/
    replay/
  workspace/
  inbox/
  outbox/
```

这意味着 `agents_os` 现在已经有了真正的实例根目录，不再只有 `Run`、`trace`、`run_state` 这些单点能力。

## 2.3 新增 `RuntimeHost`

新增：

- `butler_main/agents_os/runtime/host.py`

落地内容：

- `create_instance()`
- `load_instance()`
- `update_instance()`
- `submit_run()`
- `resume_instance()`
- `retire_instance()`

当前语义是：

- `RuntimeKernel` 仍负责执行一次 run
- `RuntimeHost` 负责托管 instance 生命周期

也就是说，`agents_os` 现在从“只能 execute 一次”向“能托管一个实例”迈了一步，但仍保持轻量，没有提前引入重型平台层。

## 2.4 补 session merge / checkpoint

新增：

- `butler_main/agents_os/runtime/session_support.py`

落地内容：

- `merge_session_snapshots()`
- `RuntimeSessionCheckpoint`
- `FileSessionCheckpointStore`

这里参考了 ConnectOnion 的两点思路，但没有直接复制 host：

1. 断点恢复依赖结构化 checkpoint
2. session merge 优先比较更细粒度的进度，再看更新时间

在 Butler 当前实现里，对应采用的是：

- `conversation_cursor`
- `updated_at`

这比只靠自然语言 summary 或 manager 内部变量稳定得多，后面接 heartbeat / manager adapter 会更顺。

## 2.5 补 bash chain permission 小模块

新增：

- `butler_main/agents_os/governance/bash_policy.py`

落地内容：

- `extract_bash_commands()`
- `matches_bash_permission()`
- `check_bash_chain_permissions()`

这部分参考的是 ConnectOnion 的 bash chain 校验思路，但实现保持 Butler 自己的轻量 contract：

- 能识别 `&&`、`;`、`||`、管道、命令替换等链式片段
- 检查的是“链中每个命令都必须被 permission 覆盖”
- 不把它和 WebSocket approval、前端 mode、tool plugin 体系绑死

这一点很关键，因为 Butler 现在需要的是“治理能力的可复用小模块”，不是把 ConnectOnion 的整套交互模式搬进来。

---

## 三、导出面变化

本轮已把新能力导出到：

- `butler_main/agents_os/runtime/__init__.py`
- `butler_main/agents_os/governance/__init__.py`

现在可直接从 `agents_os.runtime` 使用：

- `AgentRuntimeInstance`
- `FileInstanceStore`
- `RuntimeHost`
- `RuntimeSessionCheckpoint`
- `FileSessionCheckpointStore`
- `merge_session_snapshots`

也可直接从 `agents_os.governance` 使用：

- `extract_bash_commands`
- `matches_bash_permission`
- `check_bash_chain_permissions`

---

## 四、测试与验证

新增测试：

- `butler_main/butler_bot_code/tests/test_agents_os_runtime_host.py`

覆盖点：

1. `FileInstanceStore` 是否真的创建最小实例目录
2. `RuntimeHost.submit_run()` 与 `resume_instance()` 是否形成闭环
3. `merge_session_snapshots()` 是否按 cursor / timestamp 选新
4. `check_bash_chain_permissions()` 是否覆盖整条命令链

本轮已通过的测试：

- `test_agents_os_runtime.py`
- `test_agents_os_runtime_host.py`
- `test_agents_os_protocols.py`
- `test_agents_os_wave1.py`
- `test_runtime_smoke_scenarios.py`

结果：

- `24 passed`

---

## 五、这轮升级的意义

这次不是一次“看起来更先进”的抽象升级，而是把 `agents_os` 的运行语义往前推进了一层：

1. 从只有 `Run`，推进到有 `Instance`
2. 从只有 `execute()`，推进到有 `Host lifecycle`
3. 从只有零散 state / trace，推进到有实例根目录
4. 从只会单次运行，推进到有 checkpoint / resume 主链

这正是 1608 文档里想补的核心缺口。

---

## 六、当前边界

本轮还没有做的事：

1. 还没有把 heartbeat 主链切到 `RuntimeHost`
2. 还没有把 approval / verification / recovery 真正接到 instance 生命周期主链
3. 还没有把现有 adapter 的 workspace / handoff / publish 结果系统性迁入实例目录

因此当前状态更准确地说是：

> `agents_os` 已经具备 instance / host 的基础骨架，但 Butler 业务主链还处在“可接入、未完全切换”的阶段。

---

## 七、下一步建议

下一步最合适的不是继续横向扩展新抽象，而是把现有 heartbeat / manager adapter 逐步接到这套骨架：

1. 让 heartbeat round 先拥有稳定的 `instance_id`
2. 把当前 run trace / state 写入实例根目录
3. 让 approval / verification / recovery 回执进入实例主链
4. 再考虑是否要补更完整的 workflow runner

一句话总结：

> 本轮已经把 `agents_os` 从“轻量 runtime kernel”推进到了“带实例容器与 host 雏形的 runtime core”，并且只吸收了 ConnectOnion 的低耦合启发，没有引入整层框架耦合。
