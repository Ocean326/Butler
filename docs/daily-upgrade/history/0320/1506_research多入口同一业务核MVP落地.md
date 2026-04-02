# 0320 research 多入口、同一业务核 MVP 落地

更新时间：2026-03-20 15:06
时间标签：0320_1506

## 一、这次落了什么

本轮把 research 线从“目录蓝图”推进到“最小可运行骨架”。

目标不是现在就把论文发现、项目推进、idea loop 全部做完，而是先把最关键的架构钉住：

> **heartbeat / talk / codex 三种入口，共用同一个 research 业务核。**

---

## 二、当前结构

research 相关资产现在统一收口到：

- `butler_main/research/`

其中分三层：

1. `units/`
   - 最小业务单元
2. `manager/`
   - 统一业务主管与入口适配
3. `legacy/`
   - 历史残留

---

## 三、当前代码落点

## 3.1 统一 contract

位置：

- `butler_main/research/manager/code/research_manager/contracts.py`

当前已定义：

- `ResearchInvocation`
- `ResearchResult`
- `ResearchUnitSpec`
- `ResearchUnitDispatch`
- `ResearchUnitHandler`

这一层的意义是：

- 入口先归一
- unit 先标准化
- 回执先结构化

## 3.2 统一业务核

位置：

- `butler_main/research/manager/code/research_manager/manager.py`

当前 `ResearchManager.invoke()` 已负责：

1. 解析 entrypoint
2. 选择目标 unit
3. 调 unit handler
4. 输出统一 `AcceptanceReceipt`

这意味着 research 不再是“每个入口各写一套业务逻辑”。

## 3.3 统一 handler 注册层

位置：

- `butler_main/research/manager/code/research_manager/services/unit_registry.py`

当前已把以下 unit 接成统一映射：

- `paper_finding.daily_paper_discovery`
- `paper_manager.project_next_step_planning`
- `paper_manager.progress_summary`
- `research_idea.idea_loop`

这层的作用是：

- 保证 `unit_id -> handler` 有单一映射点
- 不让入口层直接依赖具体 unit 实现
- 后续新增 unit 时不破坏 manager 主体结构

## 3.4 统一入口壳

位置：

- `butler_main/research/manager/code/research_manager/interfaces/heartbeat_entry.py`
- `butler_main/research/manager/code/research_manager/interfaces/talk_bridge.py`
- `butler_main/research/manager/code/research_manager/interfaces/codex_cli_entry.py`

当前三者都只做一件事：

- 把各自调用方式归一成 `ResearchInvocation`

然后统一进入 `ResearchManager`。

---

## 四、当前行为约束

为了避免入口和 unit 重新耦合，本轮固化了以下约束：

1. `heartbeat` 可以走默认 unit
   - 当前默认到 `paper_finding.daily_paper_discovery`
2. `talk` 可以走默认 research 推进 unit
   - 当前默认到 `paper_manager.project_next_step_planning`
3. `codex` 直调默认要求显式 `unit_id`
   - 避免开发态/手工态误打到错误单元

这不是最终业务策略，但适合作为 MVP 阶段的稳定边界。

---

## 五、为什么这版架构是对的

因为它把三个问题拆开了：

1. **怎么触发**
   - `heartbeat / talk / codex`
2. **谁来组织业务**
   - `ResearchManager`
3. **具体跑哪个 research 单元**
   - `unit_registry + handler`

这样后续无论你：

- 新增 API / webhook 入口
- 新增 `paper_reader` / `related_work_synthesis` unit
- 把某些 unit 换成更复杂的 harness

都不会破坏当前主结构。

---

## 六、验证结果

已通过：

- `butler_main.butler_bot_code.tests.test_research_manager_multi_entry`

另外：

- `butler_main.butler_bot_code.tests.test_agents_os_wave3_manager_bootstrap`
  - 在默认沙箱下出现临时目录权限问题
  - 提升权限后通过
  - 判断为环境/沙箱问题，不是本轮 research 架构回归

---

## 七、下一步建议

下一步不要急着铺太多新入口，优先把 `unit_registry` 后面的 handler 做实：

1. 先把 `daily_paper_discovery` 接真实 source adapter
2. 再把 `project_next_step_planning` 接真实 project truth
3. 最后再把 `progress_summary` 接输出聚合层

一句话：

> **入口统一这一步已经够了，下一阶段该补的是“同一业务核背后的真实 handler 能力”，而不是再发明第四种入口。**
