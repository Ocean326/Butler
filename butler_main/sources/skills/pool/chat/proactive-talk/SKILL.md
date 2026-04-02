---
name: proactive-talk
description: chat 主动沟通技能。用于在合适窗口向用户对话窗发送轻量跟进（tell_user），例如阶段完成、阻塞提醒、下一步建议、小结回执。
metadata:
  category: operations
---

# Proactive Talk

在 chat 或 orchestrator 已经产出明确阶段结论时，用最短路径把一句人话推到用户对话窗。

## 使用场景

- 本轮有实质进展，需要让用户知道“做了什么、下一步是什么”。
- 发现阻塞或风险，需要用户补充输入或做决策。
- 完成一个小阶段，需要简短复盘而不是长汇报。

## 约束

- 频率受调用方自己的节流策略控制，避免刷屏。
- 默认不在纯 `status` 轮次主动发话。
- 内容建议 1-3 句，偏轻量，不要写成长报告。

## 配置

若后续需要正式配置化，建议在 chat 第四层入口下维护主动沟通参数，而不是回到旧后台自动化命名空间：

```json
{
  "chat": {
    "proactive_talk": {
      "enabled": true,
      "min_interval_seconds": 10,
      "max_chars": 220
    }
  }
}
```

说明：

- `enabled`: 是否启用主动沟通。
- `min_interval_seconds`: 两次主动发话最小间隔（秒）。
- `max_chars`: 自动生成消息时的最大长度。
