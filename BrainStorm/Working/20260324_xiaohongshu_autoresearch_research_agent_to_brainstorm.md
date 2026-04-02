# 小红书：autoresearch / 研究计划收敛 / research agent harness 工程

## 来源

- 抓取方式：`web-note-capture-cn`，2026-03-24
- Raw 目录：`BrainStorm/Raw/daily/20260324/`
- 原始链接 1：`http://xhslink.com/o/2v58jkE9cY9`
- 原始链接 2：`http://xhslink.com/o/7vmI21xGFwO`
- 原始链接 3：`http://xhslink.com/o/9PrdQVtz15e`
- 对应 Raw：
  - `BrainStorm/Raw/daily/20260324/xiaohongshu_69bc19fb000000002301077c.{json,md}`
  - `BrainStorm/Raw/daily/20260324/xiaohongshu_69b5018f000000001f0066fa.{json,md}`
  - `BrainStorm/Raw/daily/20260324/xiaohongshu_69b82d62000000002800a5d8.{json,md}`

## 边界说明

- 第 1 条与第 3 条正文抓取得比较完整，可直接作为整理依据。
- 第 2 条抓取正文是完整的，但分享页标题命中了站点壳 `搜索小红书`；这里用用户分享文案里的标题线索“快速让 Idea 收敛成清晰技术路线｜ClaudeCode 项目早期...”作为主题名，不把壳标题当真标题。
- 3 条笔记的图片都已下载到本地，但本轮未逐张读图 OCR；以下整理以抓取到的正文和分享文案为主，不伪造图中文字。

## 一句话总判断

这 3 条内容其实在讲同一件事：**研究 agent 的关键不只是“会不会写代码”，而是能不能把模糊 idea 收敛成可验证路线，并用 harness 工程把这个过程做稳、做可复盘、做成可以持续优化的 skill。**

## 三条主线

### 1. 用 autoresearch 思路优化 skill，不要只盯“能不能跑”

第一条最关键的判断不是“skill 要强”，而是：

- 真正折磨人的不是完全坏掉的 skill，而是 **70% 可用、30% 翻车** 的 skill；
- 这种半可靠能力最消耗人，因为它会让人误以为系统大致可用，但在关键时刻掉链子；
- Karpathy 的 `autoresearch` 给出的启发是：可以把 skill 优化看作一个持续实验问题，而不是一次性 prompt 调优。

把这条思路翻成工程语言，就是：

- 不只问“这个 skill 跑没跑通”；
- 要问“它在哪些输入上稳定、在哪些输入上翻车、翻车模式是否可归因、优化是不是对总体成功率真的有帮助”。

### 2. 研究计划收敛阶段，最值钱的是把模糊方法感变成可验证 proposal

第二条的核心，是把“研究问题已经有了，但方法还只有朦胧直觉”的阶段，做成一条结构化流水线。

笔记里给出的做法可以压成四步：

1. 扫描本地资料：先读 `papers/`、`literature/`，建立 grounding。
2. 拆清问题：把核心问题、子问题、假设、挑战、评价标准先说透。
3. 把方法写成方案：把模糊 idea 展开成算法流程、关键设计、baseline、dataset、metric、ablation、风险和预算。
4. 形成可追踪产物：把 proposal、review、refinement 全落到日志目录，支持复盘。

更有价值的是它的角色分工：

- `Claude Code` 偏执行：读材料、写初稿、改方案、落盘。
- `Codex` 偏外部审稿：按 reviewer 视角打分，指出清晰度、新颖性、可行性、实验设计和 venue fit 的问题。
- 两者循环，直到方案质量过阈值，再进入实现。

这其实是在把“开始写代码前的研究设计阶段”前移成一条正式工作流，而不是靠人脑拍板。

### 3. research agent 真正难的不是想 idea，而是 harness 工程

第三条最强的点，是把 research agent 的难点拆成两个层面：

- `agent 基础设施`
- `research 工作流`

对应的两个真实问题是：

- 创新点能不能被正确实现；
- 所谓“创新”到底够不够真，能不能扛住 reviewer 质疑。

文中的解法几乎都是 harness 工程，而不是单 prompt：

- 用更细粒度的检查 skill 做重复性和 novelty 约束；
- 让 reviewer 角色先提前给出“必拒理由”，逼模型预演 rebuttal 风险；
- novelty check 不只靠 prompt，而是配 DAG、日志录制/回放测试；
- 搜索源不只看 arXiv，还把会议和期刊纳入，降低 toy 级误判；
- 针对 `context rot`，把主上下文保持干净，子任务交给 subagent，结束后 compact 再回主线程；
- skill 改为动态注入，避免技能描述和工具返回值不断淹没主任务。

这里最值得记住的一句话是：

**研究 agent 不是靠一个超强主 agent 串到底，而是靠上下文隔离、subagent、compaction、review 闭环和动态 skill 注入，把系统从“能跑”变成“跑不歪”。**

## 三条内容揉在一起后的统一模型

把这 3 条放在一起，可以得到一个很清晰的工程骨架：

1. `Auto-Research-Refine` 负责把模糊想法压成研究计划。
2. `Research Harness` 负责在 novelty、review、rebuttal、实现对齐上加闸门。
3. `Autoresearch for Skills` 负责把整个链路里的 skill 从“偶尔能用”优化到“稳定可依赖”。

也就是说，完整链路不是：

- 有个 idea
- 丢给 agent
- 等它出结果

而是：

- 先收敛 idea
- 再用 harness 工程约束工作流
- 再把各个 skill 当成可测、可调、可优化对象

## 对 Butler / BrainStorm 的直接启发

### 1. 可以做一个 `research-plan-refine` 类 skill

目标不是直接写论文，而是把一条模糊研究方向压成：

- 研究问题
- 假设
- 方法轮廓
- baseline
- metrics
- ablation
- 风险与预算

最小输入可以是：

- 一个题目
- 一组论文
- 当前的直觉想法

输出则必须是结构化 proposal，而不是自由散文。

### 2. 需要一个 `skill-eval-harness`

这 3 条笔记都在提醒：最危险的不是 skill 不可用，而是 skill 半可靠。

对 Butler 来说，应该有一套最小 harness 去做：

- 输入样本集
- 成功/失败标准
- 常见翻车模式分类
- 多轮对比
- 优化前后成功率变化

这样才能真的回答“这个 skill 变好了没有”。

### 3. 要把 `context rot` 当成一类一等故障

当前 Butler 的很多长链任务，本质风险不是模型能力不足，而是：

- 技能说明太多
- 工具返回太长
- debug 日志太噪
- 主任务被旁支信息淹没

因此后续所有长链 agent / skill 设计，都应该优先问：

- 哪些信息必须留在主 context；
- 哪些任务应拆给 subagent；
- 子任务返回时应该带回什么 compact 结果；
- skill catalog 是否应该按需注入，而不是默认全量挂进上下文。

### 4. novelty / rebuttal 思维可以迁移到项目评审

文里“先让 reviewer 给出必拒理由”这招，不只适合论文。

在 Butler 的项目设计里也可以迁移成：

- 为什么这个方案可能根本不成立；
- 为什么这个改动可能只是看起来高级；
- 如果上线/合并失败，最可能因为什么；
- 现有证据足不足以支撑继续实现。

这能把很多“先写了再说”的冲动，提前收敛成更硬的方案判断。

## 建议挂到后续任务池的 4 条候选

1. 设计 `research-plan-refine` 最小 skill：
   输入题目+参考文献，输出一份结构化 proposal markdown。
2. 设计 `skill-eval-harness` 最小框架：
   对现有高频 skill 做稳定性样本测试，先选 `web-note-capture-cn` 或文档类 skill。
3. 做一版 `dynamic skill injection + subagent compact` 约定稿：
   先写在 playbook 里，再决定是否下沉进运行时。
4. 给 BrainStorm 增一个“rebuttal 预演模板”：
   让新方案在进入实现前先过一轮“必拒理由”检查。

## 最后压一句

这组内容最有价值的共识不是“research agent 很酷”，而是：

**真正能把 agent 用到研究和工程里的人，靠的不是一个神奇 prompt，而是收敛 idea 的 workflow、约束过程的 harness，以及持续优化 skill 稳定性的实验心态。**
