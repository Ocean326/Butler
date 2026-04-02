# Beyond rate limits: scaling access to Codex and Sora

- 机构：OpenAI
- 日期：2026-02-13
- 分类：Engineering
- 原文链接：https://openai.com/index/beyond-rate-limits/
- 关键词：rate limits, credits, metering, billing, access control, sora, codex

## 中文速览
- 讲的是一种把 rate limit、实时使用量统计、credits 余额结合在一起的访问控制系统。
- 它不是传统“允许/拒绝”二元门，而是一个 waterfall 式决策：先吃免费额度/速率额度，不够再顺滑切到 credits。
- 对做 agent 平台的人，这篇的价值在于：用户体验、计费正确性、可审计性和实时控制，其实都是 agent 产品底层基础设施的一部分。

## 备注
官方站原文链接；本地文件为中文整理摘要，不是网页镜像。
