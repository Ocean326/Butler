---
name: discourse-api-monitor
description: Incubating Butler wrapper spec for upstream 'Discourse API'.
category: forum
trigger_examples: 看论坛热帖, 拉评论树, 社区舆情
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: Discourse API
upstream_type: official_api
review_priority: P1
---
# Discourse API

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- Discourse forum topic fetch, category watch, announcement ingestion, support-thread summarization

## Upstream

- repo_or_entry: https://meta.discourse.org/t/discourse-rest-api-documentation/22706
- docs: https://meta.discourse.org/t/discourse-rest-api-documentation/22706
- upstream_type: official_api
- maturity: high

## Why This Matters

- A large number of product, devtool, and open-source communities run on Discourse.
- One integration can unlock many vendor and community forums.

## Risks

- Each forum has its own auth and rate constraints.
- Schema differences across versions need tolerant parsing.

## Suggested Future Exposure

- skill_ops

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

