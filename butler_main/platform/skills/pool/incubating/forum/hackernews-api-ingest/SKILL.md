---
name: hackernews-api-ingest
description: Incubating Butler wrapper spec for upstream 'Hacker News API'.
category: forum
trigger_examples: 看论坛热帖, 拉评论树, 社区舆情
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: Hacker News API
upstream_type: official_api
review_priority: P0
---
# Hacker News API

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- HN top/new/best story ingestion, comment-tree fetch, launch sentiment snapshots

## Upstream

- repo_or_entry: https://github.com/HackerNews/API
- docs: https://github.com/HackerNews/API
- upstream_type: official_api
- maturity: high

## Why This Matters

- Official and lightweight. Easy to operationalize without complex auth.
- Excellent source for engineering, startup, and tool ecosystem signals.

## Risks

- Thread trees can be large and noisy.
- Needs rank-window and keyword filters to stay useful.

## Suggested Future Exposure

- automation_safe
- skill_ops

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

