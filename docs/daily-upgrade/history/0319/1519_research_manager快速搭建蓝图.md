# 0319 research_manager 快速搭建蓝图

更新时间：2026-03-19 15:19
时间标签：0319_1519

## 目标

验证一个新并行主管，例如 `research_manager`，是否可以不重抄 Butler 黑洞总控，而是依靠：

- `agents_os` runtime 内核
- Butler/Research 自己的 adapter
- 自己的 prompt 资产
- 自己的 interface 壳层

快速搭起来。

结论：**可以，但前提是边界必须严格。**

## 最小搭建公式

一个新的 `research_manager` 至少需要四层：

### 1. runtime core

直接复用 `agents_os`：

- `execution/cli_runner.py`
- `state/run_state_store.py`
- `state/trace_store.py`
- `context/memory_backend.py`
- `tasking/task_store.py`
- `execution/runtime_policy.py`

这些不带 Butler 私有语义，可以直接共用。

### 2. manager 自己的 adapter

放在 manager 自己目录，而不是 `agents_os/`：

- `research_manager/agents_os_adapters/task_store.py`
- `research_manager/agents_os_adapters/runtime_policy.py`
- `research_manager/agents_os_adapters/task_source.py`
- `research_manager/agents_os_adapters/scheduler.py`
- `research_manager/agents_os_adapters/truth.py`

也就是说：

> adapter 跟 manager 走，不跟 runtime core 走。

### 3. prompt 资产层

例如：

- `research/manager/agent/research_manager_agent/bootstrap/`
- `research/manager/agent/research_manager_agent/prompts/`
- `research/manager/agent/research_manager_agent/roles/`
- `research/manager/agent/research_manager_agent/skills/`

这层决定 manager 的：

- 任务风格
- 研究方法
- 汇报口径
- 角色分工

### 4. interface 壳层

例如：

- 飞书入口
- CLI 入口
- API 入口
- 定时触发入口

这层只负责：

- 收请求
- 调 manager
- 发送结果
- 同步视图

不负责发明新 runtime。

## 当前已经抽出的快速搭建切面

本轮已经补出的 manager 蓝图：

- `butler_main/butler_bot_code/butler_bot/agents_os_adapters/manager_blueprint.py`

其中把一个新 manager 的最小条件收成三组 surface：

- `ManagerPromptSurface`
- `ManagerInterfaceSurface`
- `ManagerAdapterSurface`

以及总装对象：

- `ManagerBlueprint`

它表达的意思是：

> 只要 prompts、interfaces、adapters 三面齐了，一个并行 manager 就可以快速起壳。

## 对 `research_manager` 的建议目录

建议未来如果并行起：

```text
butler_main/
  research/
    manager/
      code/
        research_manager/
          research_manager.py
          agents_os_adapters/
            task_store.py
            runtime_policy.py
            task_source.py
            scheduler.py
            truth.py
          services/
            prompt_service.py
            interface_service.py
      agent/
        research_manager_agent/
          bootstrap/
          prompts/
          roles/
          skills/
```

## 不要复制的东西

`research_manager` 不要复制：

- `memory_manager.py` 整体
- `heartbeat_orchestration.py` 整体
- Butler 的 self_mind 私有链路
- Butler 的业务规则与人格 prompt

应复制/复用的只有：

- `agents_os` core
- manager blueprint 思路
- 自己 manager 的 adapter 壳

## 一句话结论

如果边界坚持为：

- `agents_os` = core
- manager 自己目录 = adapter + prompts + interfaces

那么新起一个并行的 `research_manager`，是可以快速搭建的，而且不会再次把 Butler 旧耦合整体复制过去。
