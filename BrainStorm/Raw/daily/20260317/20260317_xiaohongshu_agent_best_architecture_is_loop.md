# 小红书原文 · Agent，最好的架构是死循环

- **platform**: xiaohongshu  
- **author**: 阿东玩AI  
- **title**: Agent，最好的架构是死循环  
- **source_share_text**: Agent，最好的架构是死循环 阿东发现，2026年聊的最多... http://xhslink.com/o/8G6SBS3ckF2 复制后打开【小红书】查看笔记！  
- **source_url_raw**: `http://xhslink.com/o/8G6SBS3ckF2`  
- **capture_time**: 2026-03-17（由 Butler via WebFetch 抓取网页文本层）  
- **note_id**: （未从当前网页 HTML 中解析到 noteId，后续若通过 `web-note-capture-cn` 抓取，可在此补全）  

---

## 一手正文（按网页文本直译记录）

> Agent，最好的架构是死循环  
>  
> 阿东发现，2026年聊的最多的不是新模型，而是一行bash代码：  
> `while true; do claude-code < prompt.md; done`  
> 这就是 Ralph Loop。  
>  
> 昨天，Claude官方也跟进了，出了 `/loop` 命令。  
>  
> 2026年，Claude、Cursor、Gemini、Qwen3.5，单次推理能力已经强到变态。  
> 很多以前需要多轮编排、工具调用、记忆管理才能完成的事，现在丢一个好 spec 加一次长上下文就能搞定。  
>  
> 结果就是 AutoGPT、BabyAGI、LangGraph 那种层层嵌套的 Agent 框架变得又贵又慢又容易崩。  
> ReAct、Plan-and-Execute、Reflection 这些优雅的学术范式，在长任务里反而成了负担。  
>  
> Ralph Loop 戳中了一个本质问题：  
> 以前瓶颈是「模型不够聪明」，现在模型强了，瓶颈变成了「上下文会腐烂」。  
>  
> Ralph Loop 的解法很简单：  
> 脏了就杀掉重开，不修不压缩，用 Git 当记忆，无限重试。  
> 本质上它不是一个推理策略，而是外层运行壳。  
>  
> 最好的 Agent 架构，正在变成「没有架构」。  

---

## 评论区（当前抓取结果）

> **说明**：当前通过通用网页抓取只拿到了正文文本，评论区内容在网页中以「加载中」的异步方式呈现，未直接暴露在静态 HTML 里。  
> 这意味着在**不使用带登录态的专用抓取脚本**的前提下，无法可靠获取全部评论原文。

- **当前状态**:  
  - 未抓到任何评论正文。  
  - 仅能确认存在评论模块，但实际内容需要额外接口 / 登录态支持。  

- **后续补全建议**:  
  1. 若本地已配置 `web-note-capture-cn` + 小红书 Cookie，可用该 skill 对同一链接执行一次完整抓取，并将 JSON/Markdown 输出落盘到 `工作区/网页抓取验证`；再由 `web-image-ocr-cn` +人工将评论整理汇总回写到本文件「评论区」小节。  
  2. 或由用户在飞书中**直接复制评论区文本 / 截图 OCR 文本**发给 Butler，由对话侧补写到本 Raw 中（推荐保留楼层、昵称与大致时间）。  

> 占位结论：**评论区尚未抓取成功，当前版本仅视为「正文一手真源 + 评论待补充」的 Raw 草稿。**

