# Unlocking the Codex harness: how we built the App Server

- 机构：OpenAI
- 日期：2026-02-04
- 分类：Engineering
- 原文链接：https://openai.com/index/unlocking-the-codex-harness/
- 关键词：codex, app server, json-rpc, protocol, multi-client, harness

## 中文速览
- 这篇讲 Codex App Server：如何把同一套 Codex harness 暴露给不同前端形态，包括 web、CLI、IDE 扩展和桌面端。
- 关键设计是一个双向 JSON-RPC 风格协议，以及 thread / turn / item 等会话原语，让不同客户端都能稳定地驱动同一 agent loop。
- 它很像在回答：如果 agent 要跨多入口复用，系统边界和协议层该怎么抽。
- 做本地 agent / 多端 agent / IDE 集成的人，值得重点看。

## 备注
官方站原文链接；本地文件为中文整理摘要，不是网页镜像。
