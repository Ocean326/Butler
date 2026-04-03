# research

`butler_main/incubation/research/` 是 Butler 内 research 相关资产的统一入口。

目标：

- 把分散的 research 目录收口到一个根下
- 按最小业务单元组织，而不是继续按历史来源分散摆放
- 保留 manager / prompt / harness 的边界，但以业务单元作为第一视图

## 目录

- `scenarios/`
  - `brainstorm/`：头脑风暴场景 workflow 资产
  - `paper_discovery/`：自动搜索与文献整理场景 workflow 资产
  - `idea_loop/`：idea -> code -> result 场景 workflow 资产
- `units/`
  - `research_idea/`：研究思路推进与方法改进
  - `paper_manager/`：论文池维护、阅读队列、进展汇总
  - `paper_finding/`：论文发现、初筛、候选集生成
- `manager/`
  - `code/research_manager/`：研究业务主管代码
  - `agent/research_manager_agent/`：研究业务主管 prompt 资产
- `legacy/`
  - `harness_research_plus/`：旧 research 试验残留，暂不作为正式入口

## 组织原则

1. `units/` 优先表达“做什么”
2. `scenarios/` 表达“这类业务怎么作为 workflow 资产包存在”
3. `manager/` 表达“谁来调度这些单元”
4. `legacy/` 只保留历史残留，不继续扩散

## 调用兼容原则

这些 research 单元默认必须兼容两类主入口：

1. Butler 内部入口
2. Codex 直接入口

进一步说，至少要兼容三种触发方式：

- `orchestrator` 周期推进
- `talk` 按需触发
- `codex` 直接调用

因此约束是：

- `units/` 不直接绑定 orchestrator 语义
- `units/` 不直接绑定 talk 对话格式
- `units/` 不直接绑定某个 CLI 工具名
- 触发差异只放在 `manager/code/research_manager/interfaces/`

一句话：

> `units/` 是无头业务单元，`interfaces/` 负责把 orchestrator / talk / codex 的调用差异适配进去。

## 最小运行架构

```text
orchestrator / talk / codex
  -> research/manager/code/research_manager/interfaces/*
    -> ResearchInvocation
      -> ResearchManager
        -> services/unit_registry.py
          -> services/scenario_runner.py
            -> research/scenarios/*
          -> research/units/*
```

这一层次的目的不是现在就把业务全做完，而是先把：

- 调用方式
- 业务调度核
- unit handler 映射
- 结构化回执

## 当前 scenario runner 边界

当前 `research_manager/services/scenario_runner.py` 负责：

- 把 scenario asset 包解释成当前 `active_step`
- 推导 `workflow_cursor`
- 输出最小 `step / handoff / decision` receipts
- 提供 `output_template / entry_contract / exit_contract`

当前 `research_manager/services/scenario_instance_store.py` 负责：

- 为 scenario 绑定稳定的 `scenario_instance_id`
- 让 `talk / orchestrator / codex` 在同一 `session_id / task_id` 上共享同一场景线程
- 保存 `workflow_cursor / active_step / output_template / last receipts / state`

它不负责：

- 真正执行检索、阅读、总结、改代码
- 取代 `agents_os.runtime`
- 变成通用 workflow orchestrator

一句话：

> `scenario_runner` 是 research 场景解释层，不是 research 执行引擎。

固定成一条清晰主线。
