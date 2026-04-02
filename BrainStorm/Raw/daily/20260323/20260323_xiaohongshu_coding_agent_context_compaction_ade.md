# 20260323 小红书：Coding Agent 的 Context Compaction / JCT / IDE→ADE

## 来源

- 平台：小红书
- note id：`69c099e6000000001a026d68`
- 原始链接：`https://www.xiaohongshu.com/discovery/item/69c099e6000000001a026d68`
- 抓取文件：`BrainStorm/Raw/daily/20260323/xiaohongshu_69c099e6000000001a026d68.md`
- 抓取 JSON：`BrainStorm/Raw/daily/20260323/xiaohongshu_69c099e6000000001a026d68.json`
- OCR 记录：`BrainStorm/Raw/daily/20260323/xiaohongshu_69c099e6000000001a026d68_ocr.md`
- 二次抓取母本：`工作区/temp_xhs_capture_20260323_rerun/xiaohongshu_69c099e6000000001a026d68.md`
- 二次抓取 JSON：`工作区/temp_xhs_capture_20260323_rerun/xiaohongshu_69c099e6000000001a026d68.json`
- 发布时间：`2026-03-23T09:39:50+08:00`
- 抓取到的标题：
  - 首轮分享页：`#大模型[话题]# #vibecoding大赏[话题]# #openclaw[话题]# #深度学习[` 
  - 二轮分享页：`谈谈 CodingAgent`
- 互动数据：
  - 首轮分享页：点赞 `15` / 收藏 `18` / 分享 `5`
  - 二轮分享页：点赞 `18` / 收藏 `19` / 分享 `5`

## 抓取完整性说明

- **这条笔记没有被“完整抓下”。**
- 当前两轮抓取都只拿到了分享页 `HTML` 首屏可见数据：标题、话题标签、发布时间、部分互动数据、图片链接。
- **正文段落没有落盘**；评论区也没有抓到。
- 图片 `OCR` 已执行，但当前结果是**全部图片下载失败或超时**，因此没有从图片里自动还原文字。
- 本文后面的“图文提炼”属于**基于现有图片阅读后的人工整理稿**，可用于 BrainStorm 研究，但不能当成逐字原文。

## 这条内容核心在讲什么

这不是一条单纯聊某个模型或某个产品的笔记，而是在试图回答：

1. **Coding Agent 真的在消耗什么能力**
2. **推理系统该围绕什么指标重构**
3. **开发环境会不会从 IDE 演进到更适合 Agent 的 ADE**

作者把视角放在三层：

- **上下文压缩 / Compaction**
- **推理系统与工作负载的重新匹配**
- **Agent-first 开发环境**

## 图文提炼

### 1. Context Compaction 是 Coding Agent 的关键运行原语

- 文中把 `Compaction` 理解为：通过总结和压缩，把超长上下文收缩到更可持续运行的大小，让单个 Agent 可以不断续跑。
- 作者拿 Nano-Coder 举例，认为这类做法和 `Claude Code / OpenCode / Codex` 的某些思路相近。
- 重点不在“能不能压”，而在：**压缩策略会直接影响任务质量和效率**。

### 2. 压缩不是免费午餐，本质是稀疏化与损失控制

- 作者提出两个判断：
  - 人工引入的压缩策略，可能带来信息损失；
  - 如果把 KV 压缩看作 session 内稀疏化，那么 `Compaction` 更像 session 间稀疏化。
- 最终不能只看压了多少，而要看 **E2E 结果**。

### 3. 推理负载结构已经变了，指标重心也在变

- 从 Serving / MaaS 角度，作者强调 `Prefill` 和 `KV Cache` 复用越来越重要。
- 对 Coding Agent 来说，`TTFT`、`TPOT` 这类传统在线推理指标没有消失，但已经不够。
- 用户真正关心的是：
  - **最终结果是否可用**
  - **任务完成总时长 `JCT`（Job Completion Time）**

### 4. 模型设计要和系统设计联动

- 文中给出一个很重要的方向：**Model-System-Codesign**。
- 也就是模型结构、推理系统、工作负载模式，不能各自独立优化，而要一起看。
- Coding Agent 会反过来暴露模型真正缺的能力。

### 5. Coding Agent 需要的模型能力清单

文中点名的基础能力包括：

- `reasoning`
- `tool use`
- `multi-step`
- `agent swarm`

也就是说，Coding Agent 不是单纯“代码生成器”，而是对模型提出了**长链路、工具化、可协同**的更高要求。

### 6. IDE 可能只是过渡形态，未来会出现 ADE

- 文中提出：传统 `IDE` 是帮助碳基程序员编写、执行、测试代码；
- 而 `ADE`（Agent Development Environment）更像是帮助硅基 Agent 编写、执行、测试代码。
- 关键差异不只在 UI，而在：
  - 权限管理
  - 多 Agent 状态可见性
  - Agent 之间的交互方式
  - prompt-first / agent-first 的工作流组织

## 对 BrainStorm 的价值

- 它把 `Coding Agent` 从“产品形态”问题，拉回到了**系统负载与运行原语**问题。
- 它把 `Context Engineering` 和 `Inference Infra` 连接起来了：上下文压缩不是 prompt 小技巧，而是系统级能力。
- 它也补了一条很重要的产品判断：未来竞争点可能不是“谁更像 IDE”，而是“谁更像适合 Agent 的 ADE”。

## 可直接挂接的既有主线

- `BrainStorm/Working/20260317_codex_prompt_and_vendor_compression_instructions.md`
- `BrainStorm/Working/20260317_xiaohongshu_context_management_six_vendors_to_brainstorm.md`
- `BrainStorm/Working/20260317_xiaohongshu_multi_agent_harness_engineering_to_brainstorm.md`
- `BrainStorm/Working/20260317_xiaohongshu_agent_best_architecture_is_loop_to_brainstorm.md`

## 当前状态

- 链接抓取：已完成两轮分享页抓取
- 标题补全：已从二次抓取补到 `谈谈 CodingAgent`
- 正文抓取：未完成，当前仍缺正文原文
- OCR skill：已执行，但图片下载超时，未产出文字
- 图文内容：已保留人工提炼稿，并显式标注为“非逐字原文”
- 下一步建议：若你后续能补这条笔记的截图或正文文案，再把缺失原文并回这篇稿子
