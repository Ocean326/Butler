# 0320 research_manager 目录蓝图：论文发现与项目推进

更新时间：2026-03-20 11:06
时间标签：0320_1106

## 一、目标

给 Butler 增加两类持续能力：

1. 每天帮用户发现并筛选相关论文
2. 围绕用户的研究项目持续推进下一步

这里的关键判断不是“都做进 Butler”或“都做进 harness”二选一，而是：

> **在 Butler 中起一个 `research_manager` 承载研究业务语义；把稳定、可验证、可回放的步骤抽成 harness task unit，由 `research_manager`/`heartbeat` 调度推进。**

---

## 二、结论先行

### 2.1 放在哪一层

应放在 `research_manager` 的：

- 研究方向画像
- 项目 backlog
- 论文池与优先级
- 对用户的汇报口径
- 每日/每周推进策略

应放在 harness task unit 的：

- `daily_paper_discovery`
- `project_next_step_planning`
- `progress_summary`
- 后续的 `experiment_patch_test_verify`

### 2.2 为什么不是只做其中一边

如果全部做进 Butler：

- 短期快
- 长期容易重新长成 heartbeat 黑洞

如果全部做进 harness：

- 通用层会被研究领域语义污染
- 你的项目优先级、论文筛选口径、汇报偏好会错误地下沉到 core/harness

所以正确边界是：

> **manager 管业务语义，harness 管可复用任务单元，heartbeat 管周期推进。**

---

## 三、推荐目录蓝图

```text
butler_main/
  agents_os/
    ...

  research/
    README.md
    units/
      research_idea/
        README.md
        docs/
        idea_loop/
          ...
      paper_manager/
        README.md
        project_next_step_planning/
          README.md
        progress_summary/
          README.md
      paper_finding/
        README.md
        daily_paper_discovery/
          README.md
    manager/
      code/
        research_manager/
          README.md
          agents_os_adapters/
            README.md
            task_store.py
            runtime_policy.py
            task_source.py
            scheduler.py
            truth.py
          services/
            README.md
            unit_registry.py
            paper_pipeline_service.py
            project_board_service.py
            progress_report_service.py
          interfaces/
            README.md
            heartbeat_entry.py
            talk_bridge.py
            codex_cli_entry.py
      agent/
        research_manager_agent/
          README.md
          bootstrap/
            README.md
          prompts/
            README.md
          roles/
            README.md
          skills/
            README.md
    legacy/
      harness_research_plus/
```

---

## 四、各层职责

## 4.1 `research/manager/code/research_manager/`

这是研究业务主管本体。

它负责：

- 维护研究主题、关键词、项目状态
- 决定今天先推论文发现，还是先推项目推进
- 调用哪些 harness unit
- 将结果写回研究真源
- 对用户输出日更/周更摘要

它不负责：

- 重造 runtime core
- 把论文发现流程写死在 `heartbeat_orchestration.py`
- 把研究领域字段塞进 `agents_os`

## 4.2 `research/manager/agent/research_manager_agent/`

这是 prompt 资产层。

它负责：

- 研究经理角色定义
- 论文筛选与总结模板
- 项目推进提示词
- 后续研究技能资产

它不负责：

- 存放任务真源
- 存放运行时状态
- 承担调度逻辑

## 4.3 `research/units/`

这是 research 场景下的可复用任务单元层。

它负责：

- 定义单元输入/输出契约
- 统一 receipt / verification / recovery 语言
- 给 `research_manager` 提供稳定步骤

它不负责：

- 记住用户是谁
- 决定哪个项目优先
- 决定今天汇报给用户什么

---

## 五、建议先做的 3 个 task unit

## 5.1 `daily_paper_discovery`

目标：

- 拉取候选论文
- 做首轮相关性筛选
- 产出“今日值得看”的短名单

最小输入：

- 研究主题
- 关键词/排除词
- 时间窗
- 最大候选数

最小输出：

- 候选论文列表
- relevance 简评
- 建议精读对象
- failure / uncertainty

## 5.2 `project_next_step_planning`

目标：

- 读取项目当前状态
- 识别卡点
- 产出下一步最小推进动作

最小输入：

- 项目目标
- 当前阶段
- 最近成果/阻塞
- 可用预算与时间

最小输出：

- next_step
- expected_signal
- blockers
- whether_needs_user_input

## 5.3 `progress_summary`

目标：

- 把论文发现与项目推进结果压成面向用户的可读摘要

最小输入：

- 今日新增论文
- 今日推进动作
- 未决风险

最小输出：

- 今日摘要
- 建议关注点
- 明日待办

---

## 六、和 heartbeat 的关系

heartbeat 不应承载 research 业务语义本体。

heartbeat 更适合做：

1. 定时触发 `research_manager`
2. 为 `research_manager` 提供统一 run / trace / receipt 外壳
3. 在失败时走统一 recovery 语言

也就是说：

- `heartbeat` 是推进器
- `research_manager` 是业务负责人
- `task_units` 是标准动作块

## 六点五、调用兼容性要求

这些 research 最小业务单元，当前就应按“多入口兼容”设计。

至少兼容：

1. Butler `heartbeat` 调用
2. Butler `talk` 调用
3. Codex 直接调用

推荐边界：

- `research/units/*` 只暴露统一输入/输出语义
- `research/manager/code/research_manager/` 负责选择单元、组织流程
- `research/manager/code/research_manager/services/unit_registry.py` 负责 `unit_id -> handler` 的统一映射
- `research/manager/code/research_manager/interfaces/heartbeat_entry.py` 负责把心跳触发映射进来
- `research/manager/code/research_manager/interfaces/talk_bridge.py` 负责把对话触发映射进来
- `research/manager/code/research_manager/interfaces/codex_cli_entry.py` 负责把 Codex/CLI 直调映射进来

不要做：

- 让 `daily_paper_discovery` 直接依赖 heartbeat snapshot
- 让 `project_next_step_planning` 直接读 talk prompt 原文
- 让 research unit 直接假设调用者一定是 Butler

建议的最小调用链：

```text
heartbeat / talk / codex
  -> interfaces/*
    -> ResearchInvocation
      -> ResearchManager
        -> unit_registry
          -> research unit handler
```

---

## 七、首版落地顺序

建议分三步：

1. 先把 `research_manager` 空骨架和 prompt 资产层起出来
2. 先落 3 个轻量 task unit：`daily_paper_discovery`、`project_next_step_planning`、`progress_summary`
3. 等这条线稳定后，再把更重的 `experiment_patch_test_verify` 接到 `research/units/research_idea/idea_loop`

当前不建议首版就做：

- 多 manager 自动协商
- 全自动论文下载与大规模解析
- 自动改代码并跑实验的长循环
- 重审批中心

---

## 八、一句话总纲

> **先在 Butler 中起 `research_manager`，再把稳定步骤做成 harness task unit，由 heartbeat 推进；不要把研究语义直接塞进 harness，也不要把所有 research 流程继续堆回 heartbeat。**
