# Unrolling the Codex agent loop

- 机构：OpenAI
- 日期：2026-01-23
- 分类：Engineering
- 原文链接：https://openai.com/index/unrolling-the-codex-agent-loop/
- 关键词：codex, agent loop, tool use, cli, harness

## 中文速览
- 这是 Codex 工程系列里偏基础的一篇，拆解 Codex CLI 的 agent loop：模型推理、工具定义、执行结果回注、再规划。
- 对做 coding agent / harness 的人有价值，因为它把“agent 不是一句 prompt，而是一套循环执行系统”讲得很清楚。
- 如果你关心 plan、tool call、反馈闭环、以及为什么 CLI agent 能持续推进任务，这篇是入门视角。

## 备注
官方站原文链接；本地文件为中文整理摘要，不是网页镜像。
