# Research Agents 明日开工前复读

日期：2026-03-25
用途：开工前 3 分钟快速复读
状态：明日灵感文档

## 先记住 4 句

1. 不要一上来写代码，先把 idea 压成 proposal。
2. 不要迷信单 agent，真正让 research agent 稳的是 harness。
3. 不要只看 skill 能不能跑，要看它稳不稳。
4. 不要让上下文越滚越脏，`subagent + compact + 动态 skill 注入` 是默认方向。

## 这组内容真正提供的灵感

### 灵感 1：autoresearch 可以迁移到 skill 优化

- 最危险的 skill 不是彻底坏掉，而是半可靠。
- 以后优化 skill，应该按实验心态做：
  - 收样本
  - 分翻车类型
  - 做前后对比
  - 看总体成功率

### 灵感 2：研究计划收敛本身就是一条正式工作流

- 不是“想到一个方向 -> 开始写实现”。
- 而是：
  - 扫描资料
  - 拆问题
  - 写 proposal
  - reviewer 打分
  - refine 到可执行

### 灵感 3：research agent 的关键不在 prompt，而在 harness

- novelty check
- reviewer 预演
- rebuttal 风险前置
- 日志与可回放
- idea 与实现的对齐检查

### 灵感 4：context rot 是系统问题，不是模型性格问题

- skill 描述太多
- tool 返回太长
- debug 日志太噪
- 主任务被旁支信息淹没

看到这几个症状，就优先想：

- 主线程保留什么
- 子任务拆给谁
- 返回时 compact 什么

## 明早开工时只问自己 5 个问题

1. 明天这条 research 链路的最小输入是什么？
2. proposal 的固定输出结构是什么？
3. reviewer 的评分维度是什么？
4. 哪些结果必须落盘？
5. 今天不做哪些“看起来高级但会拖慢闭环”的扩展？

## 建议明天只拿到这 4 个结果就算赢

1. 一份结构化 proposal
2. 一份 reviewer 清单
3. 一份 refine 后 proposal
4. 一套最小落盘结构

## 对 Butler 的一句提醒

明天要打通的不是“一个会研究的炫酷 agent”，而是 **一条能把模糊研究想法稳定收敛成可验证计划的工程链路。**
