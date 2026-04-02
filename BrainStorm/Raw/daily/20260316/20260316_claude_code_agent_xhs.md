# 小红书笔记：把 Claude Code 拆开看，Agent 就不神秘了

- **来源**：小红书 | 作者：程序员彭涛 | 发布时间：2026-03-03
- **链接**：http://xhslink.com/o/8DZEqE1UQK7
- **互动**：点赞 633 / 评论 25 / 收藏 1096 / 分享 322
- **抓取**：web-note-capture-cn skill，2026-03-16

---

## 正文

最近刷到一个教学型项目 learn-claude-code，挺有意思。它不想当「替代品」，而是把 Claude Code 的工程骨架直接摊给你看。

从 **s01 → s12 递进**，每一节只加一个机制：  
**one tool + one loop = an agent** 再到：计划显式化、上下文压缩、子 Agent 隔离、技能按需加载、任务落盘、并发隔离、worktree 级协作……

一路拆下来你会发现：**Agent 的分水岭早就不是 prompt**，而是  
**状态怎么存｜上下文怎么控｜任务怎么追｜失败怎么回滚｜协作怎么对齐**。

亲手撸一遍，比让 AI 写 100 个需求有用得多。当这套骨架吃透了，看任何 Agent 框架都会突然「透明」。

话题：#AI编程 #ClaudeCode #Agent工程化 #learnclaudecode #AI出海 #一人公司 #AI工具 #深度学习 #开发者选项

---

## 第一张图片（笔记首图）

笔记共 4 张图，**第一张为首图/封面**，多为该篇的核心示意图（如 learn-claude-code 结构图、s01→s12 递进示意等）。当前抓取仅得到图片链接，未做 OCR 识别；若需图中文字/结构，请直接打开下方链接查看。

- **第一张图链接**：  
  http://sns-webpic-qc.xhscdn.com/202603161053/0fbcf6708979a236746b6b11195f376b/spectrum/1040g34o31t82pm1il83g5oeam5dk1a3i5vh0blo!nd_dft_wlteh_jpg_3

其余 3 张图链接已保存在同次抓取生成的 `工作区/temp/xiaohongshu_69a64a68000000001d010204.md`，需要时可复用。

---

## 与 Butler 的对齐（可选续思）

- learn-claude-code 的「状态怎么存、上下文怎么控、任务怎么追、失败怎么回滚、协作怎么对齐」与 Butler 的 self_mind、task_ledger、心跳规划器/执行器、技能与 sub-agent 分工可做对照，便于去神秘化、统一收口描述。
