# Research Agents 链路打通前置输入

日期：2026-03-25
来源：2026-03-24 小红书 BrainStorm 整理
状态：明日执行前置输入

## 输入真源

- Working 汇总：
  - `BrainStorm/Working/20260324_xiaohongshu_autoresearch_research_agent_to_brainstorm.md`
- 对应 Raw：
  - `BrainStorm/Raw/daily/20260324/xiaohongshu_69bc19fb000000002301077c.{json,md}`
  - `BrainStorm/Raw/daily/20260324/xiaohongshu_69b5018f000000001f0066fa.{json,md}`
  - `BrainStorm/Raw/daily/20260324/xiaohongshu_69b82d62000000002800a5d8.{json,md}`

## 明天要吸收到 research agents 主线里的稳定结论

1. `idea 收敛先于编码`
   - research 链路不是“有个想法就直接让 agent 写代码”。
   - 明天的最小闭环应先出现：
     - 研究问题
     - 假设
     - 方法轮廓
     - baseline
     - metrics
     - ablation
     - 风险与预算

2. `harness 工程先于 agent 炫技`
   - research agent 的核心不是多加几个模型名词，而是：
     - novelty / reviewer 检查
     - rebuttal 预演
     - 日志落盘与可复盘
     - 对实现与 idea 的对齐检查

3. `skill 优化要看稳定性，不只看能不能跑`
   - 需要警惕“70% 可用、30% 翻车”的半可靠 skill。
   - 明天如果要打通 research 链路，验收标准不应只写“跑通一次”，而要至少写出：
     - 哪些步骤可重复
     - 哪些输入容易翻车
     - 哪些结果要落盘供复盘

4. `context rot 是 research agent 的一等故障`
   - 明天的方案默认要考虑：
     - 主 context 保持干净
     - 子任务给 subagent
     - 子任务结束后 compact 回主线程
     - skill 动态注入而不是全量堆上下文

## 明天最小链路建议

建议先打一条最小 research 链路，不追求一步到位：

1. 输入：
   - 一个研究题目
   - 一组本地论文/笔记
2. `planner / proposer`
   - 产出结构化 proposal 草稿
3. `reviewer`
   - 从清晰度、新颖性、可行性、实验设计 4 个维度给出可操作修改意见
4. `refiner`
   - 吸收 reviewer 意见，输出第二版 proposal
5. 落盘：
   - proposal
   - review
   - refine 结果
   - 本轮结论与下一步动作

## 明天不要做的事

1. 不要一开始就把 novelty DAG、日志回放、全量多源检索、subagent swarm 全部做齐。
2. 不要把“链路设计”退化成一个长 prompt。
3. 不要只做聊天展示，不做落盘。
4. 不要只验证“生成了一份文档”，不验证它是不是可评审、可复盘、可继续 refine。

## 明天的验收口径

1. 至少有一条 `research input -> proposal -> review -> refine -> 落盘` 的真实链路。
2. proposal 结构中必须显式出现：问题、假设、方法、baseline、metrics、ablation。
3. reviewer 输出必须是可执行修改项，不接受泛泛点评。
4. 全链路结果必须有文件落盘，而不是只存在于一次对话里。

## 后续可接的两条扩展线

1. `research-plan-refine skill`
   - 把 proposal 收敛流程固化成 skill / package。
2. `skill-eval-harness`
   - 把 skill 稳定性测试独立成一条评估链路，避免研究链路本身建立在半可靠 skill 上。
