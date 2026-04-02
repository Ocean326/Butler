# 20260320 小红书 Agent 开发者悄悄换框架

## 来源

- 平台：小红书
- 作者：Aaron-OpenOnion
- 原始短链：`http://xhslink.com/o/5cB6kI0rXeN`
- note id：`69bb71cb000000002200d3de`
- 抓取文件：`工作区/网页抓取验证/xiaohongshu_69bb71cb000000002200d3de.md`
- 抓取 JSON：`工作区/网页抓取验证/xiaohongshu_69bb71cb000000002200d3de.json`
- OCR 文件：`BrainStorm/Raw/xiaohongshu_69bb71cb000000002200d3de_ocr.md`
- 发布时间：`2026-03-20T07:34:00+08:00`

## 正文核心

> 其实主要原因很反讽，现在的所有的 vibe coding 工具能写各种前后端代码，但就是无法写 Agent。

> Agent 开发有独特难点 (Prompt 管理、context 管理、多轮调试、信任），我们能看到许多很好的Agent 比如 claude code， OpenClaw， Codex，可惜无法迅速复制。因为你用 Claude Code 写一个开源版本的是不大可能的，简单来说就是模型不会，这一套Agent 开发的最佳实践只存在于一部分Agent 开发者的脑子里，不在模型里。

## 这条内容在说什么

1. Agent 开发和普通 vibe coding 不是同一个难度层级。
2. 难点不在“会不会生成代码”，而在 Prompt、context、loop、debug、trust 这些运行机制。
3. 真正稀缺的不是模型本身，而是 Agent harness 的隐性工程经验。
4. 所以开发者会“悄悄换框架”，本质上是在寻找更适合承载这些隐性最佳实践的骨架。

## 对 BrainStorm 的价值

- 它补强了一个判断：`AI 程序员 != Agent 工程师`。
- 它把“框架切换”从工具偏好问题，抬高成“谁更能承载隐藏的 Agent 最佳实践”问题。
- 它很适合挂到这些主线：
  - Harness Engineering
  - Agent 架构原则与模式
  - Claude Code / Coding Agent 工程化
  - 记忆与上下文工程

## 初步脑暴

### 判断 1

未来很多所谓的 Agent 框架竞争，表面看是 API / DX / 多 Agent 能力，底层其实是在争夺“谁把隐性 best practice 产品化得更深”。

### 判断 2

当前开源社区很难快速复刻 Claude Code / Codex 这类系统，不只是模型差距，更是：

- runtime 壳层差距
- context 管理差距
- 失败恢复机制差距
- 行为边界与信任机制差距

### 判断 3

“框架切换”可能是一个很好的观测信号：

- 开发者从什么框架迁出
- 迁入后最先夸什么
- 抱怨点集中在哪一层

这些信号能反推出 Agent 工程里真正有壁垒的部分。

## 值得继续追的问题

- 为什么普通 AI coding assistant 能快速普及，而 Agent builder 仍明显分层？
- 哪些能力已经从“开发者脑内经验”变成了框架内建？
- OpenClaw、Codex、Claude Code 各自把哪些 best practice 硬编码进了系统？
- 如果最佳实践不在模型里，那 Butler 应该把哪些经验沉淀为显式文件、runtime、policy，而不是寄希望于 prompt？

## 当前状态

- 抓取：已完成
- OCR：已下载图片，但当前环境无可用 OCR 后端
- 脑暴：已生成第一版
- 下一步建议：升格为 `Ideas/threads/` 或整理成一篇 `Working/` 对照稿
