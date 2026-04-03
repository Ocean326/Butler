---
name: feedparser-rss-ingest
description: Incubating Butler wrapper spec for upstream 'feedparser'.
category: general
trigger_examples: 抓网页正文, 做RSS监控, 资料整理
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: feedparser
upstream_type: open_source_library
review_priority: P0
---
# feedparser

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- RSS and Atom feed polling, digest generation, watchlist monitoring

## Upstream

- repo_or_entry: https://github.com/kurtmckee/feedparser
- docs: https://feedparser.readthedocs.io/en/latest/
- upstream_type: open_source_library
- maturity: high

## Why This Matters

- Low-friction way to cover blogs, changelogs, forums, and publication feeds with one abstraction.
- Pairs naturally with automation-safe monitoring and periodic digests.

## Risks

- Only covers sources that expose feeds.
- Needs deduplication and per-feed freshness logic.

## Suggested Future Exposure

- automation_safe
- chat_content_share

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

