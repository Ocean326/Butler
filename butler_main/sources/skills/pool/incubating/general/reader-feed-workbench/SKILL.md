---
name: reader-feed-workbench
description: Incubating Butler wrapper spec for upstream 'reader'.
category: general
trigger_examples: 抓网页正文, 做RSS监控, 资料整理
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: reader
upstream_type: open_source_library
review_priority: P1
---
# reader

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- persistent feed workspace, read-state management, local feed review tool

## Upstream

- repo_or_entry: https://github.com/lemon24/reader
- docs: https://reader.readthedocs.io/
- upstream_type: open_source_library
- maturity: medium_high

## Why This Matters

- Stronger than raw feed parsing when Butler needs a durable watchlist or inbox model.
- Can back a future research-monitor or forum-monitor workflow.

## Risks

- Heavier than feedparser for simple one-shot pulls.
- Requires local state and lifecycle handling.

## Suggested Future Exposure

- automation_safe

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

