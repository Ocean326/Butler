---
name: paper-first-principles-review
description: 按第一性原理拆解论文的 Task、Challenge、Insight & Novelty、Potential Flaw、Motivation，输出科研导向 Markdown 精读笔记；适合用户已给出标题、摘要、正文片段、链接整理结果或 PDF 提取内容时使用。
category: research
family_id: paper-reading
family_label: 论文精读族
family_summary: 面向论文与技术文章的结构化精读、创新点拆解与科研动机复盘；命中后再区分首读、对比读和复现导向阅读。
family_trigger_examples: 读论文, 论文精读, 论文拆解, paper reading, paper review
variant_rank: 10
trigger_examples: 第一性原理读论文, 按模板拆论文, 论文创新点分析, paper insight, novelty analysis
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
status: active
---

# paper-first-principles-review

当用户需要把一篇论文或技术文章拆成“问题定义 -> 难点 -> insight -> novelty -> flaw -> motivation”这条科研主线时，使用本 skill。

## 本 skill 的边界

- 只基于**当前已经拿到的论文材料**做分析，不假装读过未提供的正文。
- 如果只有标题、摘要、结论或零散片段，仍可分析，但必须明确标注不确定性来源，例如：`基于摘要推断`、`基于片段推断`。
- 本 skill 负责**结构化精读与推演**，不负责抓取论文；若材料不足，先补标题、摘要、正文片段或先使用检索/抓取类 skill。
- 默认面向**单篇论文**；若用户要求多篇横向比较，可先分别拆解，再另行汇总。

## 输入要求

优先级从高到低：

1. 论文标题 + 摘要 + 方法/实验关键段落
2. 论文标题 + 全文或较完整正文提取
3. 论文标题 + 摘要
4. 仅有论文标题时，只能做标题级方向判断，所有结论都要标注 `基于标题推断`
5. 仅有链接、DOI 或截图时，先说明信息不足，不直接伪造细节

开始分析前，先判断当前材料足够支撑到哪一层：

- **全文级**：可以较完整讨论 task、challenge、insight、novelty、flaw、motivation
- **摘要级**：重点给 task、challenge、主 insight、粗粒度 novelty，并显式保留不确定项
- **片段级**：只分析能被证据覆盖的部分，不补脑正文细节

## 三种输入场景示例

### 示例 1：只给标题

用户可能会这样说：

> 帮我按这个模板拆一下《Language Models are Few-Shot Learners》

此时应这样处理：

- 可以输出一个**标题级初判版**
- `Task`、`Challenge`、`Motivation` 可以做方向性判断，但都要标 `基于标题推断`
- `Insight & Novelty` 只能写高层猜测，不能把具体方法细节写成已知事实
- `Potential Flaw` 只讨论这类问题设定通常会遇到的脆弱点，不假装知道论文实验结果
- 最后明确说明：若要进入摘要级或全文级精读，还需要摘要或正文片段

### 示例 2：给标题 + 摘要

用户可能会这样说：

> 下面是论文标题和摘要，按第一性原理拆一下，重点看 insight 和 novelty。

此时应这样处理：

- 输出完整五段结构，但不确定项要明确标 `基于摘要推断`
- `Task`、`Challenge`、主 `Insight` 通常可以较稳定提炼
- `Novelty` 只写摘要里真的能支撑的创新，不补脑方法实现
- `Potential Flaw` 优先写从问题设定、数据假设、泛化边界推出来的风险
- 若摘要没有覆盖 motivation 链条，就把问句链写成“高置信 + 低置信”两层

### 示例 3：给正文 / PDF 提取内容

用户可能会这样说：

> 我把 PDF 提取文本贴给你了，按模板完整拆一遍，尽量把 challenge 和 novelty mapping 讲具体。

此时应这样处理：

- 按**全文级**标准输出，优先引用当前材料里已经出现的 method、training、evaluation 证据
- `Insight & Novelty` 要尽量落到具体设计，而不是停在口号层
- `Novelty Mapping` 要逐点对齐：问题 -> insight -> 具体创新
- `Potential Flaw` 要结合正文里显露出的假设、实验覆盖和适用边界来写
- 如果 PDF 提取质量差、段落断裂或公式缺失，先点明哪些判断受提取噪声影响

## 输出模板

严格按下面结构输出，省略客套话：

## 1. Task

- 这篇文章解决的核心问题是什么
- 尽量形式化给出：输入、输出、目标、约束、优化对象
- 若论文是系统/benchmark/综述，也要把它还原为“本文试图改善什么决策或能力边界”

## 2. Challenge

- 传统方法为什么难以解决这个问题
- 关键挑战来自哪里：表示能力、搜索空间、数据质量、监督信号、效率、泛化、约束满足、评估缺口
- 不要只复述“以前方法不好”，要指出**具体卡点**

## 3. Insight & Novelty

### 3.1 Inspiration

- 作者的灵感可能来自什么观察、类比、失败经验或外部机制
- 若文中没明说，可做有限推断，但要标注证据等级

### 3.2 Insight

- Insight 是什么，属于哪一层：
  - 问题建模层
  - 架构层
  - 训练/优化层
  - 推理/搜索层
  - 数据/监督层
  - 评估/策略层
- 每个 insight 都要说明：它回应了哪个 challenge，受什么 inspiration 启发

### 3.3 Novelty

- Novelty 分清是：
  - 架构创新
  - 方法创新
  - 策略创新
  - 训练信号/数据构造创新
  - 系统工程创新
- 不要把“把已有模块拼在一起”轻易写成强 novelty；先判断是否真的支撑了 insight

### 3.4 Novelty Mapping

对每个创新点，严格使用下面格式：

- 【创新点解决的问题是什么】-> 【受哪个 insight 启发】-> 【设计了什么创新点，尽可能具体描述】

## 4. Potential Flaw

- 当前问题设定本身有哪些局限
- 如果扩展到更高维度、更多约束、更复杂环境，会先坏在哪里
- 哪类数据性质会让当前方法特别脆弱，例如：
  - 噪声大
  - 长尾严重
  - 分布偏移
  - 标注稀缺
  - 反馈延迟
  - 多目标冲突
- 在这些困难里，哪一个最值得继续深挖成下一篇 paper，并说明为什么

## 5. Motivation

- 用**问句链**重构作者是怎么想到这篇文章的
- 从问题本质出发，不要从“作者已经知道答案”倒推
- 优先写成这种推进方式：
  - 之前的方法真正卡在什么地方？
  - 这个卡点是表象问题还是建模问题？
  - 那可不可以换一个更贴近本质的表示/目标/约束？
  - 如果这样改，最自然的机制会是什么？

## 格式约束

- 只用 Markdown
- 省略所有客套话
- 不使用 LaTeX
- 公式一律写成纯文本形式
- 不确定内容必须显式标注：`基于摘要推断`、`基于片段推断`、`文中未明确说明`
- 输出重点是**清楚拆解与科研启发**，不是花哨措辞

## 额外提醒

- 不要把 `Insight`、`Novelty`、`Experiment Gain` 混成一件事。
- 不要把作者写在 related work 里的口号直接当 challenge。
- 如果论文贡献更偏工程系统，也要追问：真正的新东西是系统接口、调度策略、训练闭环，还是只是规模堆砌。
