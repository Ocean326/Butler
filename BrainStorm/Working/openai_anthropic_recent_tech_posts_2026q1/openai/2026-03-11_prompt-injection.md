# Designing AI agents to resist prompt injection

- 机构：OpenAI
- 日期：2026-03-11
- 分类：Security
- 原文链接：https://openai.com/index/designing-agents-to-resist-prompt-injection/
- 关键词：prompt injection, social engineering, agent security, safe url, atlas, deep research

## 中文速览
- 这篇把 prompt injection 视为更接近 social engineering 的问题，而不是单纯的恶意字符串检测问题。
- 核心思路是：不能只想着“完美识别所有恶意输入”，而要把 agent 的危险动作、敏感信息外传能力、确认机制和系统约束设计好。
- 如果你在做有浏览器、搜索、外部网页交互能力的 agent，这篇很值得加入安全材料包。

## 备注
官方站原文链接；本地文件为中文整理摘要，不是网页镜像。
