---
name: feishu-webhook-tools
description: 通过 PowerShell 向飞书 Webhook 推送消息，或执行 Cursor Agent 后把输出转发到飞书。用于轻量通知、自动化摘要推送和脚本化集成。
metadata:
  category: operations
---

# Feishu Webhook Tools

这个 skill 承载历史上散落在 body 层的飞书 Webhook PowerShell 工具，避免把外围脚本继续堆在运行时目录里。

## 包含脚本

- `SendToFeishu.ps1`: 直接向飞书 Webhook 推送文本消息。
- `agent-to-feishu.ps1`: 执行 Cursor Agent，并把结果转发到飞书。

## 适用场景

- 每日巡检、定时任务、批处理结束后发一个摘要到飞书。
- 需要用 PowerShell 快速验证飞书 Webhook 是否可用。
- 需要在本地脚本里复用“agent 输出 -> 飞书推送”的桥接能力。

## 约束

- 这是一组外围通知脚本，不属于 Butler 的 DNA 运行链。
- 需要显式提供 `WebhookUrl`，如启用了签名则同时传入 `Secret`。
- 大段输出应先截断或摘要，避免刷屏。