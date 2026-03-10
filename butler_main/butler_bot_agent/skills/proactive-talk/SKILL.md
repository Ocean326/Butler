---
name: proactive-talk
description: 心跳主动沟通技能。用于在合适窗口向用户对话窗发送轻量跟进（tell_user），例如阶段完成、阻塞提醒、下一步建议、小结回执。避免只在心跳窗自言自语。
metadata:
  category: operations
---

# Proactive Talk

将 heartbeat 的 `plan.tell_user` 作为首选通道，在需要时主动向用户对话窗说一句人话。

## 使用场景

- 本轮有实质进展，需要让用户知道“做了什么、下一步是什么”。
- 发现阻塞或风险，需要用户补充输入或做决策。
- 完成一个小阶段，需要简短复盘而不是长汇报。

## 约束

- 频率受 `heartbeat.proactive_talk.min_interval_seconds` 控制，避免刷屏。
- 默认不在纯 `status` 轮次主动发话。
- 内容建议 1-3 句，偏轻量，不要写成长报告。

## 配置

在 `butler_bot_code/configs/butler_bot.json` 的 `heartbeat` 下可配置：

```json
{
  "heartbeat": {
    "proactive_talk": {
      "enabled": true,
      "min_interval_seconds": 10,
      "max_chars": 220
    }
  }
}
```

说明：

- `enabled`: 是否启用主动沟通 skill。
- `min_interval_seconds`: 两次主动发话最小间隔（秒），当前默认可设置到 `10` 秒。
- `max_chars`: 自动生成 `tell_user` 时的最大长度。
